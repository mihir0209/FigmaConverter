"""High-level orchestration helpers for AI prompting flows."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, Dict, Optional

from parsers.ai_response_parser import AIResponseParser

from prompting.ai_runner import run_chat_prompt
from prompting.prompt_builder import (
    build_app_architecture_prompt,
    build_framework_discovery_prompt,
)

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
