"""Style engine builders — generate styling instructions and config for each engine."""

from __future__ import annotations

from prompting.style_builders.tailwind_v4 import (
    build_tailwind_theme_block,
    get_tailwind_instructions,
)


def build_styles(
    style_engine: str | None,
    design_system: dict | None = None,
) -> str:
    """Return style config content (e.g. CSS with @theme block) for the engine."""
    engine = (style_engine or "css").lower()
    if engine == "tailwind":
        return build_tailwind_theme_block(design_system)
    return "/* No style engine configured */"


def get_style_instructions(
    style_engine: str | None,
) -> str:
    """Return human-readable styling instructions to inject into AI prompts."""
    engine = (style_engine or "css").lower()
    if engine == "tailwind":
        return get_tailwind_instructions()
    return ""


__all__ = ["build_styles", "get_style_instructions"]
