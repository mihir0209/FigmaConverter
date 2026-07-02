"""Fallback adapter that uses Simon Willison's `llm` library directly.

Activated when opencode is not available. Supports OpenAI, Anthropic,
Google Gemini, Ollama, and 30+ other providers via plugins.
"""
import os
import time
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


class LLMFallbackAdapter:
    """Fallback AI adapter using the `llm` library directly.

    Used when `opencode serve` is not available. Supports any provider
    that has an `llm` plugin installed (OpenAI built-in, Anthropic via
    llm-anthropic, Google via llm-gemini, Ollama via llm-ollama, etc.).
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._model_id = os.getenv("LLM_FALLBACK_MODEL", "gpt-4o-mini")
        self._model = None
        self._conversation = None

    def _get_model(self):
        if self._model is None:
            import llm
            self._model = llm.get_model(self._model_id)
        return self._model

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        autodecide: bool = True,
        **kwargs,
    ) -> RequestResult:
        start = time.time()

        system_text = None
        user_texts = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                if system_text is None:
                    system_text = content
                else:
                    system_text += "\n" + content
            elif role == "user":
                user_texts.append(content)

        if not user_texts:
            user_texts.append("")

        prompt = "\n".join(user_texts)

        try:
            model = self._get_model()
            response = model.prompt(
                prompt,
                system=system_text,
                temperature=temperature,
            )
            elapsed = time.time() - start
            text = response.text()

            # Extract model ID from the response object
            model_used = self._model_id
            if hasattr(response, "model") and hasattr(response.model, "model_id"):
                model_used = response.model.model_id

            return RequestResult(
                success=True,
                content=text,
                response_time=elapsed,
                provider_used="llm_fallback",
                model_used=model_used,
            )

        except Exception as exc:
            elapsed = time.time() - start
            logger.warning("LLM fallback chat_completion failed: %s", exc)
            return RequestResult(
                success=False,
                error_message=str(exc),
                error_type="llm_fallback_error",
                response_time=elapsed,
                provider_used="llm_fallback",
                model_used=self._model_id,
            )

    def abort(self):
        pass

    def get_status(self) -> Dict[str, Any]:
        try:
            model = self._get_model()
            return {
                "connected": True,
                "provider": "llm_fallback",
                "model": self._model_id,
                "model_key": model.key if hasattr(model, "key") else None,
            }
        except Exception as exc:
            return {"connected": False, "error": str(exc)}
