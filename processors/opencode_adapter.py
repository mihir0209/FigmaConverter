"""Thin adapter that delegates AI inference to opencode serve.

Replaces the entire AI_engine class (27 providers, key rotation,
failover, rate limiting) with a single HTTP call to the user's
existing opencode runtime.
"""
import os
import time
import subprocess
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class RequestResult:
    success: bool
    content: str = ""
    status_code: int = 0
    response_time: float = 0.0
    error_message: str = ""
    error_type: str = "unknown"
    provider_used: str = ""
    model_used: str = ""
    raw_response: Optional[Dict] = None


class OpenCodeAdapter:
    """Adapter that delegates AI inference to opencode serve.

    Manages the opencode serve subprocess, creates sessions, and
    maps FigmaConverter's chat_completion calls to opencode's HTTP API.
    """

    _opencode_client = None
    _session = None
    _process = None

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._provider_cache = None
        self._provider_cache_time = 0
        self._ensure_server()

        # lazy imports to avoid circular deps at module level
        import opencode_ai

        if self.__class__._opencode_client is None:
            base_url = self._server_url()
            logger.info("Connecting to opencode serve at %s", base_url)
            self.__class__._opencode_client = opencode_ai.Opencode(
                base_url=base_url,
                timeout=120.0,
            )

        if self.__class__._session is None:
            sess = self.__class__._opencode_client.session.create()
            self.__class__._session = sess
            logger.info("Created opencode session %s", sess.id)

    # -- server management ------------------------------------------------

    @staticmethod
    def _server_url() -> str:
        host = os.getenv("OPENCODE_HOST", "127.0.0.1")
        port = int(os.getenv("OPENCODE_PORT", "4096"))
        return f"http://{host}:{port}"

    @staticmethod
    def _ensure_server():
        """Start opencode serve if not already running."""
        host = os.getenv("OPENCODE_HOST", "127.0.0.1")
        port = int(os.getenv("OPENCODE_PORT", "4096"))
        url = f"http://{host}:{port}/global/health"

        try:
            import httpx
            resp = httpx.get(url, timeout=2.0)
            if resp.status_code == 200:
                logger.info("Found running opencode serve at %s", url)
                return
        except Exception:
            pass

        logger.info("Starting opencode serve on %s:%d", host, port)

        proc = subprocess.Popen(
            ["opencode", "serve", "--port", str(port), "--hostname", host],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                import httpx
                resp = httpx.get(url, timeout=1.0)
                if resp.status_code == 200:
                    logger.info("opencode serve started (pid %d)", proc.pid)
                    OpenCodeAdapter._process = proc
                    return
            except Exception:
                pass
            time.sleep(0.5)

        proc.kill()
        proc.wait()
        raise RuntimeError(
            "Could not start opencode serve after 15s. "
            "Ensure opencode CLI is installed (https://opencode.ai)"
        )

    def close(self):
        if self.__class__._opencode_client:
            self.__class__._opencode_client.close()
            self.__class__._opencode_client = None
        if self.__class__._process:
            self.__class__._process.kill()
            self.__class__._process.wait()
            self.__class__._process = None

    # -- provider discovery ------------------------------------------------

    def _get_connected_providers(self) -> List[Dict[str, str]]:
        now = time.time()
        if self._provider_cache and now - self._provider_cache_time < 60:
            return self._provider_cache

        try:
            import httpx
            url = f"{self._server_url()}/provider"
            resp = httpx.get(url, timeout=5.0)
            data = resp.json()
            connected = data.get("connected", [])
            defaults = data.get("default", {})
            result = []
            for pid in connected:
                result.append({
                    "provider_id": pid,
                    "model_id": defaults.get(pid, ""),
                })
            self._provider_cache = result
            self._provider_cache_time = now
            return result
        except Exception as exc:
            logger.warning("Failed to discover opencode providers: %s", exc)
            return []

    def _resolve_provider(
        self, preferred_provider: Optional[str] = None, model: Optional[str] = None
    ) -> tuple:
        """Return (provider_id, model_id) to use for the next request."""
        env_provider = os.getenv("OPENCODE_PROVIDER_ID")
        env_model = os.getenv("OPENCODE_MODEL_ID")

        if env_provider and env_model:
            return env_provider, env_model

        if preferred_provider and "/" in preferred_provider:
            parts = preferred_provider.split("/", 1)
            return parts[0], parts[1]

        providers = self._get_connected_providers()
        if not providers:
            return "opencode", "deepseek-v4-flash-free"

        if preferred_provider:
            for p in providers:
                if p["provider_id"] == preferred_provider:
                    return p["provider_id"], p["model_id"] or model or ""

        if env_provider:
            for p in providers:
                if p["provider_id"] == env_provider:
                    return p["provider_id"], env_model or p["model_id"] or model or ""

        first = providers[0]
        return first["provider_id"], first["model_id"] or model or ""

    # -- core chat_completion method --------------------------------------

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        autodecide: bool = True,
        **kwargs,
    ) -> RequestResult:
        """Send a chat completion request via opencode runtime.

        Args:
            messages: List of dicts with 'role' and 'content' keys.
                Each dict can have 'images' key with list of image paths or
                base64-encoded images for vision models.
            temperature: Sampling temperature.
            autodecide: Ignored — opencode handles provider selection.
            **kwargs: Supports preferred_provider, model, response_format.

        Returns:
            RequestResult-compatible object.
        """
        start = time.time()
        preferred = kwargs.get("preferred_provider")
        model_hint = kwargs.get("model")

        parts = []
        system_text = None

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            images = msg.get("images", [])

            if role == "system":
                if system_text is None:
                    system_text = content
                else:
                    system_text += "\n" + content
            else:
                # Add text content
                if content:
                    parts.append({"type": "text", "text": content})

                # Add images (vision support) - encode as base64 in text for compatibility
                for image_path in images:
                    try:
                        import base64
                        import mimetypes

                        if image_path.startswith("data:"):
                            # Already a data URL - extract base64
                            parts.append({
                                "type": "text",
                                "text": f"[IMAGE: {image_path}]",
                            })
                        else:
                            # File path - read and encode
                            mime_type = mimetypes.guess_type(image_path)[0] or "image/png"
                            with open(image_path, "rb") as f:
                                image_data = base64.b64encode(f.read()).decode("utf-8")
                            data_url = f"data:{mime_type};base64,{image_data}"
                            parts.append({
                                "type": "text",
                                "text": f"[IMAGE: {data_url}]",
                            })
                    except Exception as img_err:
                        logger.warning("Failed to add image %s: %s", image_path, img_err)

        if not parts:
            parts.append({"type": "text", "text": ""})

        provider_id, model_id = self._resolve_provider(preferred, model_hint)

        try:
            client = self.__class__._opencode_client
            session_id = self.__class__._session.id

            chat_kwargs = dict(
                provider_id=provider_id,
                model_id=model_id,
                parts=parts,
            )
            if system_text:
                chat_kwargs["system"] = system_text

            response_format = kwargs.get("response_format")
            if response_format and isinstance(response_format, dict):
                if response_format.get("type") == "json_object":
                    schema = response_format.get("schema")
                    if schema:
                        chat_kwargs["format"] = {
                            "type": "json_schema",
                            "schema": schema,
                        }

            result = client.session.chat(session_id, **chat_kwargs)
            elapsed = time.time() - start

            info = getattr(result, "info", {}) or {}
            result_parts = getattr(result, "parts", []) or []

            text_parts = [p["text"] for p in result_parts if isinstance(p, dict) and p.get("type") == "text"]
            content = "\n".join(text_parts) if text_parts else ""

            actual_provider = info.get("providerID", provider_id)
            actual_model = info.get("modelID", model_id)
            finish = info.get("finish", "stop")

            if finish == "error":
                return RequestResult(
                    success=False,
                    content=content,
                    error_message=info.get("error", {}).get("message", "opencode request failed"),
                    error_type="provider_error",
                    response_time=elapsed,
                    provider_used=actual_provider,
                    model_used=actual_model,
                    raw_response=result_parts,
                )

            return RequestResult(
                success=True,
                content=content,
                response_time=elapsed,
                provider_used=actual_provider,
                model_used=actual_model,
                raw_response=result_parts,
            )

        except Exception as exc:
            elapsed = time.time() - start
            logger.warning("opencode chat_completion failed: %s", exc)
            return RequestResult(
                success=False,
                error_message=str(exc),
                error_type="opencode_error",
                response_time=elapsed,
                provider_used=provider_id,
                model_used=model_id,
            )

    def abort(self):
        if self.__class__._session and self.__class__._opencode_client:
            try:
                self.__class__._opencode_client.session.abort(self.__class__._session.id)
            except Exception:
                pass

    def get_status(self) -> Dict[str, Any]:
        try:
            import httpx
            url = f"{self._server_url()}/global/health"
            resp = httpx.get(url, timeout=2.0)
            health = resp.json()
            providers = self._get_connected_providers()
            return {
                "connected": health.get("healthy", False),
                "version": health.get("version", ""),
                "providers_available": len(providers),
                "providers": [p["provider_id"] for p in providers],
            }
        except Exception as exc:
            return {"connected": False, "error": str(exc)}
