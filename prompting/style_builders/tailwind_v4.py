"""Tailwind CSS v4 style output builder.

Tailwind v4 uses `@import "tailwindcss"` and `@theme { }` blocks in CSS
instead of a `tailwind.config.js` file.  This module generates:

1. A CSS file (`src/index.css`) with the `@theme` block populated from
   the extracted design system (colors, fonts, spacing, etc.).
2. Prompt instructions that tell the AI to emit Tailwind utility classes
   instead of raw CSS / inline styles.
"""

from __future__ import annotations

from typing import Any

_TAILWIND_PROMPT_INSTRUCTIONS = """
STYLE ENGINE: tailwindcss v4

You MUST use Tailwind CSS v4 utility classes for ALL styling.

RULES:
- NEVER write raw CSS or inline styles. Always use Tailwind utility classes.
- Use Tailwind v4 syntax — `@import "tailwindcss"` in CSS, NOT `@tailwind base`.
- Apply colors, spacing, typography, layout, and hover/focus states via utility classes.
- For dynamic / conditional styles, use clsx() or template literal class merging.
- Extract repeated utility patterns into reusable components, NOT custom CSS.
- Respect the design system tokens from the `@theme` block.

Example mapping:
  - font-size → `text-sm`, `text-lg`, `text-2xl`
  - padding   → `p-4`, `px-6`, `py-2`
  - colors    → `bg-blue-500`, `text-gray-900`
  - flex/grid → `flex flex-row items-center justify-between`
  - border    → `border border-gray-200 rounded-lg`
  - shadow    → `shadow-md`, `shadow-lg`
  - hover     → `hover:bg-blue-600 hover:shadow-xl`
  - responsive → `md:flex-row lg:w-1/2`
"""


def get_tailwind_instructions() -> str:
    """Return the prompt instructions block for Tailwind v4."""
    return _TAILWIND_PROMPT_INSTRUCTIONS


def _to_slug(name: str) -> str:
    """Convert a design-system colour/name to a Tailwind-compatible slug."""
    return name.lower().replace(" ", "-").replace("_", "-").replace("/", "-")


def build_tailwind_theme_block(design_system: dict[str, Any] | None) -> str:
    """Generate a `@theme { }` block from an extracted design system dict.

    The returned string is ready to be written as ``src/index.css`` (or
    the framework's styles entry point).
    """
    if not design_system:
        return _default_theme_css()

    lines = ['@import "tailwindcss";', "", "@theme {", ""]

    # ── Colours ──────────────────────────────────────────────────────────
    colors = design_system.get("colors") or design_system.get("color", [])
    if isinstance(colors, list):
        for c in colors:
            if isinstance(c, dict):
                name = _to_slug(c.get("name", "unknown"))
                value = c.get("value") or c.get("color") or c.get("hex", "#000000")
                lines.append(f'  --color-{name}: {value};')
            elif isinstance(c, str):
                lines.append(f"  --color-{_to_slug(c)}: {c};")
    elif isinstance(colors, dict):
        for name, value in colors.items():
            lines.append(f"  --color-{_to_slug(name)}: {value};")

    # ── Typography ───────────────────────────────────────────────────────
    typography = design_system.get("typography", {})
    if isinstance(typography, dict):
        font_families: set[str] = set()
        for _key, styles in typography.items():
            if isinstance(styles, dict):
                ff = styles.get("font_family") or styles.get("fontFamily")
                if ff:
                    font_families.add(str(ff))
        for idx, ff in enumerate(sorted(font_families)):
            lines.append(f'  --font-family-{idx}: "{ff}", sans-serif;')

    # ── Spacing / sizing hints ───────────────────────────────────────────
    spacing = design_system.get("spacing", {})
    if isinstance(spacing, dict):
        for name, value in spacing.items():
            lines.append(f"  --spacing-{_to_slug(name)}: {value};")

    lines.extend(["", "}"])
    return "\n".join(lines)


def _default_theme_css() -> str:
    return """@import "tailwindcss";
"""
