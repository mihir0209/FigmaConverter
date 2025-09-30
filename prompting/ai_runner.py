"""Utility helpers for executing AI prompts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from prompting.prompt_builder import PromptRequest

if TYPE_CHECKING:
    from ai_engine.ai_engine import AI_engine


def run_chat_prompt(ai_engine: "AI_engine", request: PromptRequest, *, label: str) -> Any:
    """Execute a chat prompt using the shared logging format."""
    debug = request.debug_context or {}

    print(f"🤖 AI Request - {label}:")
    for key, value in debug.items():
        if key == "messages_preview":
            continue
        print(f"   {key.replace('_', ' ').title()}: {value}")

    if "messages_preview" in debug:
        print(f"   Messages: {debug['messages_preview']}")

    print(f"   Temperature: {request.temperature}, Auto-decide: {request.autodecide}")
    print()

    result = ai_engine.chat_completion(
        request.messages,
        temperature=request.temperature,
        autodecide=request.autodecide,
    )

    print(f"🤖 AI Response - {label}:")
    print(f"   Success: {result.success}")
    if result.success:
        preview = getattr(result, "content", "") or ""
        print(f"   Response Content: {preview[:500]}...")
    else:
        print(f"   Error: {getattr(result, 'error_message', 'Unknown error')}")
    print()

    return result
