"""Simplified orchestration with vision support and XML-structured prompts."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from parsers.ai_response_parser import AIResponseParser

from prompting.ai_runner import run_chat_prompt
from prompting.prompt_builder_v2 import (
    PromptRequest,
    build_architecture_prompt,
    build_frame_generation_prompt,
    build_main_app_prompt,
)
from prompting.refinement_prompts import (
    RefinementContext,
    build_refinement_prompt,
    parse_refinement_response,
)
from processors.ai_cache import AICache, _cache_key
from prompting.framework_utils import get_app_file_paths, get_component_file_path

if TYPE_CHECKING:
    from processors.opencode_adapter import OpenCodeAdapter


def generate_enhanced_frame_code_with_ai(
    ai_engine: "OpenCodeAdapter",
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
    vision_images: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run the enhanced frame generation workflow with retry safety and vision support."""

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
        base_request = build_frame_generation_prompt(
            frame,
            framework,
            job_id,
            framework_structure,
            app_architecture,
            design_summary,
            resolved_dependencies,
            style_engine,
            component_library,
            vision_images,
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
                                "The previous response was not valid JSON. Please respond with ONLY the JSON "
                                "object matching the schema specified in the original prompt. "
                                "Do NOT include markdown code blocks, explanations, or any text outside the JSON."
                            ),
                        }
                    ]

        print(f"❌ All attempts failed for frame '{frame_name}'")
        return {
            "files": {fallback_file_path: f"// Generation failed for {frame_name}"},
            "dependency_suggestions": {},
            "frame_name": frame_name,
            "error": str(last_error) if last_error else "Unknown error",
        }
    except Exception as exc:
        print(f"❌ Enhanced frame generation error: {exc}")
        target_framework = framework_structure.get("framework", framework).lower()
        frame_name = frame.get("name", "Frame")
        fallback_file_path = get_component_file_path(target_framework, frame_name)
        return {
            "files": {fallback_file_path: f"// Generation failed for {frame_name}: {exc}"},
            "dependency_suggestions": {},
            "frame_name": frame_name,
            "error": str(exc),
        }


def generate_app_architecture_with_ai(
    ai_engine: "OpenCodeAdapter",
    design_summary: str,
    framework: str,
    parser: AIResponseParser,
) -> Optional[Dict[str, Any]]:
    """Generate an application architecture plan from the design summary."""
    try:
        request = build_architecture_prompt([], framework, {})
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


def generate_main_app_with_ai(
    ai_engine: "OpenCodeAdapter",
    frames: List[Dict[str, Any]],
    framework: str,
    framework_structure: Dict[str, Any],
    app_architecture: Dict[str, Any],
    parser: AIResponseParser,
) -> Dict[str, Any]:
    """Generate the main application shell."""
    try:
        request = build_main_app_prompt(frames, framework, framework_structure, app_architecture)
        result = run_chat_prompt(ai_engine, request, label="Main App Generation")

        if not result.success:
            print(f"❌ Main app generation failed: {result.error_message}")
            return {"files": {}}

        try:
            cleaned_response = (result.content or "").strip()
            cleaned_response = re.sub(r"```json\n?", "", cleaned_response)
            cleaned_response = re.sub(r"```\n?", "", cleaned_response)
            cleaned_response = re.sub(r"^[^{\[]*", "", cleaned_response)
            cleaned_response = re.sub(r"[^}\]]*$", "", cleaned_response)
            app_data = json.loads(cleaned_response)
            return app_data
        except ValueError as exc:
            print(f"❌ Failed to parse main app response: {exc}")
            return {"files": {}}
    except Exception as exc:
        print(f"❌ Main app generation error: {exc}")
        return {"files": {}}
