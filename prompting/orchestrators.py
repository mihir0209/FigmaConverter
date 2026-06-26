"""High-level orchestration helpers for AI prompting flows."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from parsers.ai_response_parser import AIResponseParser

from prompting.ai_runner import run_chat_prompt
from prompting.prompt_builder import (
    build_app_architecture_prompt,
    build_dependency_reconciliation_prompt,
    build_enhanced_frame_prompt,
    build_enhanced_main_app_prompt,
    build_framework_discovery_prompt,
    PromptRequest,
)
from prompting.refinement_prompts import (
    RefinementContext,
    build_refinement_prompt,
    parse_refinement_response,
)
from processors.ai_cache import AICache, _cache_key
from prompting.framework_utils import get_app_file_paths, get_component_file_path

if TYPE_CHECKING:
    from ai_engine.ai_engine import AI_engine


def discover_framework_structure(
    ai_engine: "AI_engine",
    parser: AIResponseParser,
    framework: str,
    design_data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Discover the framework project structure using the AI engine."""
    try:
        request = build_framework_discovery_prompt(design_data, framework)
        result = run_chat_prompt(ai_engine, request, label="Framework Discovery")

        if not result.success:
            print(f"❌ Framework discovery failed: {result.error_message}")
            return None

        try:
            structure_data = parser.parse_framework_discovery_response(
                (result.content or "").strip()
            )
            return structure_data
        except ValueError as exc:
            print(f"❌ Failed to parse framework discovery response: {exc}")
            print(f"Raw response: {(result.content or '')[:500]}...")
            return None
    except Exception as exc:
        print(f"❌ Error during framework discovery: {exc}")
        return None


def generate_app_architecture_with_ai(
    ai_engine: "AI_engine",
    design_summary: str,
    framework: str,
    parser: AIResponseParser,
) -> Optional[Dict[str, Any]]:
    """Generate an application architecture plan from the design summary."""
    try:
        request = build_app_architecture_prompt(design_summary, framework)
        result = run_chat_prompt(ai_engine, request, label="App Architecture Analysis")

        if not result.success:
            print(f"❌ Architecture analysis failed: {result.error_message}")
            return None

        try:
            cleaned_response = (result.content or "").strip()
            cleaned_response = re.sub(r"```json\n?", "", cleaned_response)
            cleaned_response = re.sub(r"```\n?", "", cleaned_response)
            cleaned_response = re.sub(r"^[^{\[]*", "", cleaned_response)
            cleaned_response = re.sub(r"[^}\]]*$", "", cleaned_response)
            architecture_data = json.loads(cleaned_response)
            return architecture_data
        except ValueError as exc:
            print(f"❌ Failed to parse architecture response: {exc}")
            print(f"Raw response: {(result.content or '')[:500]}...")
            return None
    except Exception as exc:
        print(f"❌ Architecture analysis error: {exc}")
        return None


def generate_enhanced_frame_code_with_ai(
    ai_engine: "AI_engine",
    frame: Dict[str, Any],
    framework: str,
    job_id: str,
    parser: AIResponseParser,
    framework_structure: Dict[str, Any],
    app_architecture: Dict[str, Any],
    design_summary: str,
    resolved_dependencies: Optional[Dict[str, Any]] = None,
    style_engine: Optional[str] = None,
    component_library: Optional[str] = None,
    ai_cache: Optional[AICache] = None,
) -> Dict[str, Any]:
    """Run the enhanced frame generation workflow with retry safety."""

    # Check cache first
    file_key = frame.get("_file_key", "")
    frame_id = frame.get("id", "")
    if ai_cache and file_key and frame_id:
        key = _cache_key(file_key, frame_id, framework, style_engine)
        cached = ai_cache.get(key)
        if cached is not None:
            print(f"✅ Cache hit for frame {frame.get('name', frame_id)}")
            return cached

    try:
        base_request = build_enhanced_frame_prompt(
            frame,
            framework,
            job_id,
            framework_structure,
            app_architecture,
            design_summary,
            resolved_dependencies,
            style_engine,
            component_library,
        )

        conversation = list(base_request.messages)
        last_error: Optional[Exception] = None
        target_framework = framework_structure.get("framework", framework).lower()
        frame_name = frame.get("name", "Frame")
        fallback_file_path = get_component_file_path(target_framework, frame_name)

        for attempt in range(1, 4):
            attempt_context = dict(base_request.debug_context)
            attempt_context.update({
                "attempt": attempt,
                "messages_preview": conversation,
            })
            attempt_request = PromptRequest(
                messages=conversation,
                temperature=base_request.temperature,
                autodecide=base_request.autodecide,
                debug_context=attempt_context,
            )

            result = run_chat_prompt(
                ai_engine,
                attempt_request,
                label="Enhanced Frame Generation",
            )

            if not result.success:
                last_error = ValueError(result.error_message or "Unknown AI error")
                print(
                    f"❌ Enhanced frame generation attempt {attempt} failed for '{frame_name}': {last_error}"
                )
                if attempt < 3:
                    conversation = list(conversation) + [
                        {
                            "role": "user",
                            "content": (
                                "The previous response did not succeed. Please respond again with ONLY the JSON "
                                "object that matches the requested schema."
                            ),
                        }
                    ]
                continue

            try:
                parsed = parser.parse_component_generation_response(
                    (result.content or "").strip()
                )
                file_path = parsed.get("file_path") or fallback_file_path
                content = parsed.get("content", "")
                dependencies = parsed.get("dependencies", {})
                outcome = {
                    "files": {file_path: content},
                    "dependency_suggestions": dependencies,
                    "frame_name": frame_name,
                }
                if ai_cache and file_key and frame_id:
                    key = _cache_key(file_key, frame_id, framework, style_engine)
                    ai_cache.set(key, outcome)
                return outcome
            except ValueError as exc:
                last_error = exc
                print(
                    f"❌ Failed to parse enhanced frame response for '{frame_name}' (attempt {attempt}): {exc}"
                )
                print(f"   Raw response: {(result.content or '')[:200]}...")
                if attempt < 3:
                    conversation = list(conversation) + [
                        {
                            "role": "user",
                            "content": (
                                "Your previous response was not valid JSON and could not be parsed ("
                                + str(exc)
                                + "). Please resend only the JSON object with the same schema, without any additional text or markdown."
                            ),
                        }
                    ]
                continue

        print(
            f"❌ Enhanced frame generation failed for '{frame_name}' after 3 attempts: {last_error}"
        )
        if result := locals().get("result"):
            print(f"   Last model response: {(getattr(result, 'content', '') or '')[:200]}...")
        return {}
    except Exception as exc:
        frame_name = frame.get("name", "Frame")
        print(f"❌ Error generating enhanced frame code for '{frame_name}': {exc}")
        return {}


def generate_enhanced_main_app_with_ai(
    ai_engine: "AI_engine",
    frames: List[Dict[str, Any]],
    framework: str,
    job_id: str,
    parser: AIResponseParser,
    framework_structure: Dict[str, Any],
    app_architecture: Dict[str, Any],
    style_engine: Optional[str] = None,
    component_library: Optional[str] = None,
) -> Dict[str, str]:
    """Generate the enhanced main application shell via the AI engine.

    Implements the same retry loop as `generate_enhanced_frame_code_with_ai`
    so a single malformed response doesn't silently lose the entire main-app
    shell.
    """

    try:
        request = build_enhanced_main_app_prompt(
            frames,
            framework,
            framework_structure,
            app_architecture,
            style_engine,
            component_library,
        )
        conversation = list(request.messages)
        last_error: Optional[Exception] = None
        file_paths = get_app_file_paths(framework_structure.get("framework", framework))

        for attempt in range(1, 4):
            attempt_context = dict(request.debug_context)
            attempt_context.update(
                {"attempt": attempt, "messages_preview": conversation}
            )
            attempt_request = PromptRequest(
                messages=conversation,
                temperature=request.temperature,
                autodecide=request.autodecide,
                debug_context=attempt_context,
            )

            result = run_chat_prompt(
                ai_engine, attempt_request, label="Main App Generation"
            )

            if not result.success:
                last_error = ValueError(result.error_message or "Unknown AI error")
                print(f"❌ Main app generation attempt {attempt} failed: {last_error}")
                if attempt < 3:
                    conversation = list(conversation) + [
                        {
                            "role": "user",
                            "content": (
                                "The previous response did not succeed. Please respond again with only "
                                "the JSON object for the application files."
                            ),
                        }
                    ]
                continue

            try:
                parsed = parser.parse_main_app_generation_response((result.content or "").strip())
                files: Dict[str, str] = {}

                if "main_app" in parsed:
                    info = parsed["main_app"]
                    files[info.get("file_path", file_paths["main_app"])] = info.get("content", "")
                if "routing" in parsed:
                    info = parsed["routing"]
                    files[info.get("file_path", file_paths["routing"])] = info.get("content", "")
                if "entry_point" in parsed:
                    info = parsed["entry_point"]
                    files[info.get("file_path", file_paths["entry_point"])] = info.get("content", "")
                if "global_styles" in parsed:
                    info = parsed["global_styles"]
                    files[info.get("file_path", file_paths["styles"])] = info.get("content", "")

                return files
            except ValueError as exc:
                last_error = exc
                print(f"❌ Failed to parse main app generation response (attempt {attempt}): {exc}")
                if attempt < 3:
                    conversation = list(conversation) + [
                        {
                            "role": "user",
                            "content": (
                                "Your previous response was not valid JSON and could not be parsed ("
                                + str(exc)
                                + "). Please resend the JSON object exactly as specified, without commentary or markdown."
                            ),
                        }
                    ]
                continue

        print(f"❌ Main app generation failed after 3 attempts: {last_error}")
        return {}
    except Exception as exc:
        print(f"❌ Error generating main app: {exc}")
        return {}


def reconcile_dependencies_with_ai(
    ai_engine: "AI_engine",
    preliminary_deps: Dict[str, Any],
    dependency_suggestions: List[Dict[str, Any]],
    framework_structure: Dict[str, Any],
    parser: AIResponseParser,
    style_engine: Optional[str] = None,
    component_library: Optional[str] = None,
) -> Dict[str, Any]:
    """Consolidate dependency suggestions and enforce conflict-free output."""

    try:
        request = build_dependency_reconciliation_prompt(
            preliminary_deps,
            dependency_suggestions,
            framework_structure,
            style_engine=style_engine,
            component_library=component_library,
        )
        result = run_chat_prompt(
            ai_engine,
            request,
            label="Dependency Reconciliation",
        )

        if not result.success:
            print(
                f"⚠️ Dependency reconciliation failed: {result.error_message} — "
                "falling back to preliminary deps; package.json may need manual review."
            )
            return preliminary_deps

        try:
            cleaned_response = (result.content or "").strip()
            cleaned_response = re.sub(r"```json\n?", "", cleaned_response)
            cleaned_response = re.sub(r"```\n?", "", cleaned_response)
            cleaned_response = re.sub(r"^[^{\[]*", "", cleaned_response)
            cleaned_response = re.sub(r"[^}\]]*$", "", cleaned_response)
            reconciled = json.loads(cleaned_response)

            pkg_deps = reconciled.get("dependencies", {}).get("package.json", {})
            dependencies = pkg_deps.get("dependencies", {})
            dev_dependencies = pkg_deps.get("devDependencies", {})

            has_react_scripts = "react-scripts" in dependencies or "react-scripts" in dev_dependencies
            has_vite = "vite" in dependencies or "vite" in dev_dependencies
            has_vite_plugin = "@vitejs/plugin-react" in dependencies or "@vitejs/plugin-react" in dev_dependencies
            typescript_version = dependencies.get("typescript") or dev_dependencies.get("typescript")

            conflicts_detected: List[str] = []

            if has_react_scripts and (has_vite or has_vite_plugin):
                conflicts_detected.append("react-scripts + vite build tools conflict")
                print("🚨 CRITICAL CONFLICT: react-scripts + vite detected - FORCING modern Vite setup...")
                dependencies.pop("react-scripts", None)
                dev_dependencies.pop("react-scripts", None)
                dev_dependencies.setdefault("@vitejs/plugin-react", "^4.2.1")
                dev_dependencies.setdefault("vite", "^5.0.8")

            if has_react_scripts and typescript_version and typescript_version.startswith("^5"):
                conflicts_detected.append("react-scripts 5.x + TypeScript 5.x peer dependency conflict")
                print("🚨 CRITICAL CONFLICT: react-scripts + TypeScript 5.x detected - FORCING TypeScript 4.x...")
                if "typescript" in dependencies:
                    dependencies["typescript"] = "^4.9.5"
                if "typescript" in dev_dependencies:
                    dev_dependencies["typescript"] = "^4.9.5"

            if has_react_scripts:
                conflicts_detected.append("react-scripts legacy tooling detected")
                print("🚨 LEGACY TOOLING: react-scripts detected - FORCING modern Vite for better compatibility...")
                dependencies.pop("react-scripts", None)
                dev_dependencies.pop("react-scripts", None)
                dev_dependencies["vite"] = "^5.0.8"
                dev_dependencies["@vitejs/plugin-react"] = "^4.2.1"
                if typescript_version:
                    if "typescript" in dependencies:
                        dependencies["typescript"] = "^5.3.3"
                    if "typescript" in dev_dependencies:
                        dev_dependencies["typescript"] = "^5.3.3"

            final_has_react_scripts = "react-scripts" in dependencies or "react-scripts" in dev_dependencies
            final_has_vite = "vite" in dependencies or "vite" in dev_dependencies
            final_has_vite_plugin = "@vitejs/plugin-react" in dependencies or "@vitejs/plugin-react" in dev_dependencies

            if final_has_react_scripts and (final_has_vite or final_has_vite_plugin):
                print("🚨 FINAL VALIDATION FAILED: Still have conflict after resolution!")
                dependencies.pop("react-scripts", None)
                dev_dependencies.pop("react-scripts", None)
                dev_dependencies["vite"] = "^5.0.8"
                dev_dependencies["@vitejs/plugin-react"] = "^4.2.1"
                conflicts_detected.append("FORCED clean Vite setup after validation failure")

            if conflicts_detected:
                print(f"✅ RESOLVED {len(conflicts_detected)} dependency conflicts:")
                for conflict in conflicts_detected:
                    print(f"   - {conflict}")
            else:
                print("✅ No dependency conflicts detected")

            return reconciled
        except (ValueError, KeyError, TypeError) as exc:
            print(
                f"⚠️ Failed to parse dependency reconciliation response: {exc} — "
                "falling back to preliminary deps."
            )
            print(f"Raw response: {(result.content or '')[:300]}...")
            return preliminary_deps
    except Exception as exc:
        print(f"⚠️ Error in dependency reconciliation: {exc} — using preliminary deps")
        return preliminary_deps


def refine_code_with_ai(
    ai_engine: "AI_engine",
    current_files: Dict[str, str],
    user_prompt: str,
    *,
    framework: str = "",
    style_engine: str = "",
    component_library: str = "",
    design_summary: str = "",
    target_files: Optional[List[str]] = None,
    refinement_iteration: int = 1,
    previous_summary: str = "",
) -> Dict[str, Any]:
    """Run a single refinement iteration against the AI engine.

    Returns a dict with ``updated_files``, ``changed_files``, ``summary``,
    and ``raw_response``. Raises ``ValueError`` if the AI response cannot
    be parsed after the retry loop.
    """
    ctx = RefinementContext(
        user_prompt=user_prompt,
        current_files=current_files,
        target_files=target_files,
        design_summary=design_summary,
        framework=framework,
        style_engine=style_engine,
        component_library=component_library,
        refinement_iteration=refinement_iteration,
        previous_summary=previous_summary,
    )

    try:
        base_request = build_refinement_prompt(ctx)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Failed to build refinement prompt: {exc}") from exc

    conversation = list(base_request.messages)
    valid_paths = sorted(current_files.keys())

    last_error: Optional[Exception] = None
    last_result: Optional[Any] = None

    for attempt in range(1, 4):
        attempt_ctx = dict(base_request.debug_context)
        attempt_ctx.update({"attempt": attempt, "messages_preview": conversation})
        attempt_request = PromptRequest(
            messages=conversation,
            temperature=base_request.temperature,
            autodecide=base_request.autodecide,
            debug_context=attempt_ctx,
        )

        result = run_chat_prompt(ai_engine, attempt_request, label="Code Refinement")
        last_result = result

        if not result.success:
            last_error = ValueError(result.error_message or "Unknown AI error")
            print(f"❌ Refinement attempt {attempt} failed: {last_error}")
            if attempt < 3:
                conversation = list(conversation) + [
                    {
                        "role": "user",
                        "content": (
                            "The previous response did not succeed. Please respond again with ONLY the JSON object "
                            "that matches the requested schema."
                        ),
                    }
                ]
            continue

        try:
            parsed = parse_refinement_response(
                (result.content or "").strip(),
                valid_paths=valid_paths,
            )
            return {
                "updated_files": parsed["updated_files"],
                "changed_files": parsed["changed_files"],
                "summary": parsed["summary"],
                "raw_response": result.content,
                "iteration": refinement_iteration,
            }
        except ValueError as exc:
            last_error = exc
            print(f"❌ Failed to parse refinement response (attempt {attempt}): {exc}")
            print(f"   Raw response: {(result.content or '')[:200]}...")
            if attempt < 3:
                conversation = list(conversation) + [
                    {
                        "role": "user",
                        "content": (
                            "Your previous response was not valid JSON and could not be parsed ("
                            + str(exc)
                            + "). Please resend only the JSON object with the same schema, without any additional text or markdown."
                        ),
                    }
                ]
            continue

    if last_result is not None and not last_result.success:
        raise ValueError(
            f"AI did not return a successful response after 3 attempts: {last_error}"
        )
    raise ValueError(
        f"Refinement failed after 3 attempts — could not parse AI response: {last_error}"
    )
