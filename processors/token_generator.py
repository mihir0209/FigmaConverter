"""Design-token generator (Plan 003).

Converts a ``TokenCollection`` (from ``token_extractor.py``) into a
style-engine-specific tokens file:

- ``css``   → ``:root { --color-primary: ...; }`` block
- ``scss``  → ``$color-primary: ...;`` variables
- ``tailwind`` → Tailwind v4 ``@theme`` block (uses tokens from the design system)
- ``css_modules`` → same as CSS for now
- ``styled`` → JS object literal

The same token list goes into the
``prompting/style_builders/tailwind_v4.build_tailwind_theme_block`` function
when Tailwind is selected.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from models import TokenCollection

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_token_file(tokens: TokenCollection, style_engine: str) -> str:
    """Generate a tokens file for the requested style engine.

    Returns an empty string when the token collection has nothing.
    """
    style = (style_engine or "css").lower()
    if not tokens.has_tokens():
        return ""

    if style == "tailwind":
        return _generate_tailwind(tokens)
    if style == "scss":
        return _generate_scss(tokens)
    if style == "styled":
        return _generate_styled(tokens)
    if style == "css_modules":
        return _generate_css(tokens)
    if style == "css":
        return _generate_css(tokens)
    return _generate_css(tokens)


def token_file_path(framework: str, style_engine: str) -> str:
    """Where to put the generated tokens file in the output project."""
    style = (style_engine or "css").lower()
    if framework in {"html", "html_css_js"}:
        return "css/tokens.css"
    if style == "scss":
        return "src/styles/_tokens.scss"
    if style == "tailwind":
        return "src/index.css"  # Tailwind v4 inlines via `@theme`
    return "src/tokens.css"


def tokens_to_dict(tokens: TokenCollection) -> Dict[str, List[Dict[str, Any]]]:
    """Render ``TokenCollection`` as a flat dict for serialisation / lookup."""
    return {
        "colors": [t.model_dump() for t in tokens.colors],
        "typography": [t.model_dump() for t in tokens.typography],
        "spacing": [t.model_dump() for t in tokens.spacing],
        "radius": [t.model_dump() for t in tokens.radius],
        "shadows": [t.model_dump() for t in tokens.shadows],
        "source": tokens.source,
        "token_count": tokens.token_count,
    }


# ---------------------------------------------------------------------------
# Generators per style engine
# ---------------------------------------------------------------------------


def _generate_css(tokens: TokenCollection) -> str:
    lines: List[str] = [":root {"]
    for color in tokens.colors:
        lines.append(f"  --{color.name}: {color.value};")
    for sp in tokens.spacing:
        lines.append(f"  --{sp.name}: {sp.value};")
    for r in tokens.radius:
        lines.append(f"  --{r.name}: {r.value};")
    for sh in tokens.shadows:
        lines.append(f"  --{sh.name}: {sh.value};")
    for ty in tokens.typography:
        fname = ty.name
        if fname.startswith("font-"):
            fname = fname[len("font-"):]
        if ty.font_family:
            lines.append(f"  --font-{fname}: {ty.font_family};")
        if ty.font_size:
            size = ty.font_size.strip()
            if not size.endswith("px") and not size.endswith("em") and not size.endswith("rem"):
                size += "px"
            lines.append(f"  --font-size-{fname}: {size};")
        if ty.font_weight:
            lines.append(f"  --font-weight-{fname}: {ty.font_weight};")
    lines.append("}")
    return "\n".join(lines)


def _generate_scss(tokens: TokenCollection) -> str:
    lines: List[str] = ["// SCSS variables: design tokens"]
    for color in tokens.colors:
        lines.append(f"${color.name}: {color.value};")
    for sp in tokens.spacing:
        lines.append(f"${sp.name}: {sp.value};")
    for r in tokens.radius:
        lines.append(f"${r.name}: {r.value};")
    for sh in tokens.shadows:
        lines.append(f"${sh.name}: {sh.value};")
    for ty in tokens.typography:
        fname = ty.name
        if fname.startswith("font-"):
            fname = fname[len("font-"):]
        if ty.font_family:
            lines.append(f"$font-{fname}: {ty.font_family};")
        if ty.font_size:
            size = ty.font_size.strip()
            if not size.endswith("px") and not size.endswith("em") and not size.endswith("rem"):
                size += "px"
            lines.append(f"$font-size-{fname}: {size};")
        if ty.font_weight:
            lines.append(f"$font-weight-{fname}: {ty.font_weight};")
    return "\n".join(lines)


def _generate_tailwind(tokens: TokenCollection) -> str:
    """Generate a Tailwind v4 ``@theme { }`` block.

    Reuses the colour / typography / spacing keys already supported by
    ``prompting/style_builders/tailwind_v4.build_tailwind_theme_block``.
    """
    lines: List[str] = [
        '@import "tailwindcss";',
        "",
        "/* Design tokens extracted from Figma Variables */",
        "",
        "@theme {",
        "",
    ]

    for color in tokens.colors:
        # Strip a leading "color-" prefix because Tailwind's `--color-<x>`
        # convention would otherwise double-prefix us into `--color-color-x`.
        name = color.name
        if name.startswith("color-"):
            name = name[len("color-"):]
        lines.append(f"  --color-{name}: {color.value};")

    families: List[str] = []
    for ty in tokens.typography:
        fname = ty.name
        if fname.startswith("font-"):
            fname = fname[len("font-"):]
        if ty.font_family and ty.font_family not in families:
            families.append(ty.font_family)
            lines.append(f'  --font-family-{len(families) - 1}: "{ty.font_family}", sans-serif;')
        if ty.font_size:
            size = ty.font_size.strip()
            if not size.endswith("px") and not size.endswith("em") and not size.endswith("rem"):
                size += "px"
            lines.append(f"  --font-size-{fname}: {size};")
        if ty.font_weight:
            lines.append(f"  --font-weight-{fname}: {ty.font_weight};")

    for sp in tokens.spacing:
        name = sp.name
        if name.startswith("spacing-"):
            name = name[len("spacing-"):]
        lines.append(f"  --spacing-{name}: {sp.value};")
    for r in tokens.radius:
        name = r.name
        if name.startswith("radius-"):
            name = name[len("radius-"):]
        lines.append(f"  --radius-{name}: {r.value};")
    for sh in tokens.shadows:
        name = sh.name
        if name.startswith("shadows-"):
            name = name[len("shadows-"):]
        elif name.startswith("shadow-"):
            name = name[len("shadow-"):]
        lines.append(f"  --shadow-{name}: {sh.value};")

    lines.append("}")
    return "\n".join(lines)


def _generate_styled(tokens: TokenCollection) -> str:
    """Emit JS tokens for styled-components / emotion."""
    layout = {
        "colors": {c.name: c.value for c in tokens.colors},
        "spacing": {s.name: s.value for s in tokens.spacing},
        "radius": {r.name: r.value for r in tokens.radius},
        "shadows": {s.name: s.value for s in tokens.shadows},
        "typography": {
            t.name: {
                "fontFamily": t.font_family,
                "fontSize": t.font_size,
                "fontWeight": t.font_weight,
            }
            for t in tokens.typography
        },
    }
    import json
    return "export const tokens = " + json.dumps(layout, indent=2) + ";"
