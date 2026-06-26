"""Design-token extractor (Plan 003).

Reads Figma Variables when available, falls back to extracting hardcoded
values from parsed frame data when variables are not in use.

Output: ``TokenCollection`` covering colors / typography / spacing / radius /
shadows, with standardised ``name`` fields and a flat values map for
generators.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from models import (
    ColorToken,
    RadiusToken,
    ShadowToken,
    SpacingToken,
    TokenCollection,
    TypographyToken,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_tokens(
    figma_variables: Optional[Dict[str, Any]] = None,
    frames: Optional[List[Dict[str, Any]]] = None,
) -> TokenCollection:
    """Build a ``TokenCollection`` from Figma Variables and/or extracted frames.

    Resolution order:
    1. If ``figma_variables`` contains structured variables → parse them.
    2. If ``frames`` is provided and variables were missing/empty → fall back
       to extracting from each frame's ``comprehensive_data.design_system``.
    3. Both can contribute; ``source`` reports ``"mixed"`` in that case.

    Both inputs are optional. Returns an empty ``TokenCollection`` when
    neither yields anything.
    """
    has_figma = bool(
        figma_variables
        and (
            figma_variables.get("variables")
            or figma_variables.get("meta")
            or figma_variables.get("values")
        )
    )
    has_frames = bool(frames)

    collection = TokenCollection()
    if has_figma:
        collection = _tokens_from_figma_variables(figma_variables or {})
    if has_frames:
        fallback = _tokens_from_frames(frames or [])
        collection = _merge_collections(collection, fallback)

    if has_figma and has_frames:
        collection.source = "mixed"
    elif has_figma:
        collection.source = "figma_variables"
    elif has_frames:
        collection.source = "extracted_fallback"
    else:
        collection.source = ""

    collection.token_count = sum(
        [
            len(collection.colors),
            len(collection.typography),
            len(collection.spacing),
            len(collection.radius),
            len(collection.shadows),
        ]
    )
    return collection


def tokens_as_dict(tokens: TokenCollection) -> Dict[str, Dict[str, str]]:
    """Convert a ``TokenCollection`` to ``{category: {name: value}}`` for piping
    into a generator.
    """
    layout: Dict[str, Dict[str, str]] = {}
    layout["color"] = {t.name: t.value for t in tokens.colors if t.name and t.value}
    layout["typography"] = {
        t.name: f'{t.font_family} {t.font_size} {t.font_weight}' for t in tokens.typography if t.name
    }
    layout["spacing"] = {t.name: t.value for t in tokens.spacing if t.name and t.value}
    layout["radius"] = {t.name: t.value for t in tokens.radius if t.name and t.value}
    layout["shadow"] = {t.name: t.value for t in tokens.shadows if t.name and t.value}
    return layout


# ---------------------------------------------------------------------------
# Figma Variables parser
# ---------------------------------------------------------------------------

# Figma's REST API returns variables with these characteristics:
# /v1/files/{file_key}/variables/local returns:
#   {
#     "values": {...collection-id...: { "N:0": "Variable-id", ... }},
#     "resolvedTypeForProxy": {...},
#     "variableCollections": {"VariableCollection-id": {...}},
#     "variables": { "Variable-id": { id, name, resolvedType, valuesByMode, ...} }
#   }
#
# `valuesByMode` maps mode-id → value. The value is structured differently per
# resolvedType (COLOR / FLOAT / STRING / BOOLEAN).

_RESOLVED_COLOR_KEYS = {"r", "g", "b", "a"}


def _tokens_from_figma_variables(raw: Dict[str, Any]) -> TokenCollection:
    """Parse the Figma Variables payload into a TokenCollection."""
    collection = TokenCollection(source="figma_variables")
    variables = raw.get("variables") or {}
    if not variables and isinstance(raw.get("meta"), dict):
        variables = raw["meta"].get("variables") or {}

    collections_meta = raw.get("variableCollections") or {}
    if not collections_meta and isinstance(raw.get("meta"), dict):
        collections_meta = raw["meta"].get("variableCollections") or {}

    colors: List[ColorToken] = []
    typography: List[TypographyToken] = []
    spacing: List[SpacingToken] = []
    radii: List[RadiusToken] = []
    shadows: List[ShadowToken] = []

    for var in variables.values():
        name = var.get("name") or ""
        resolved_type = (var.get("resolvedType") or "").upper()
        # Figure out a default mode's value.
        values_by_mode = var.get("valuesByMode") or {}
        if not values_by_mode:
            continue
        first_value = next(iter(values_by_mode.values()))

        if resolved_type == "COLOR":
            hex_value = _parse_figma_color(first_value)
            if hex_value:
                colors.append(_make_color(name, hex_value, source="figma_variable"))
        elif resolved_type == "FLOAT":
            str_value = _parse_figma_float(first_value)
            if str_value is not None:
                first_segment = _lower_token_name(name).split("/")[0]
                if first_segment in {"radius", "cornerradius", "borderradius"}:
                    radii.append(RadiusToken(name=_normalize_name(name), value=str_value))
                elif _looks_like_spacing(name):
                    spacing.append(SpacingToken(name=_normalize_name(name), value=str_value))
                else:
                    spacing.append(SpacingToken(name=_normalize_name(name), value=str_value))
        elif resolved_type == "STRING":
            str_value = first_value if isinstance(first_value, str) else ""
            typography_name = name.lower()
            if any(kw in typography_name for kw in ("font", "text", "typography")):
                typography.append(
                    TypographyToken(
                        name=_normalize_name(name),
                        font_family=str_value,
                        font_size="",
                        font_weight=400,
                    )
                )
        elif resolved_type == "SHADOW" or "shadow" in name.lower():
            text = _shadow_to_string(first_value)
            if text:
                shadows.append(ShadowToken(name=_normalize_name(name), value=text))

    collection.colors = colors
    collection.typography = typography
    collection.spacing = spacing
    collection.radius = radii
    collection.shadows = shadows
    return collection


def _parse_figma_color(value: Any) -> Optional[str]:
    """Convert a Figma Color RGBA dict to a hex string."""
    if not isinstance(value, dict):
        return None
    # Could be {r,g,b,a}, a hex alias, or a bound variable reference
    if value.get("type") == "VARIABLE_ALIAS":
        return None
    if not all(k in value for k in _RESOLVED_COLOR_KEYS):
        return None
    r = float(value.get("r", 0))
    g = float(value.get("g", 0))
    b = float(value.get("b", 0))
    a = float(value.get("a", 1.0))
    r255 = max(0, min(255, int(round(r * 255))))
    g255 = max(0, min(255, int(round(g * 255))))
    b255 = max(0, min(255, int(round(b * 255))))
    hex_str = f"#{r255:02X}{g255:02X}{b255:02X}"
    if a < 1.0:
        a255 = max(0, min(255, int(round(a * 255))))
        return f"rgba({r255}, {g255}, {b255}, {a})"
    return hex_str


def _parse_figma_float(value: Any) -> Optional[str]:
    if isinstance(value, dict) and "value" in value:
        try:
            return f"{float(value['value']):g}"
        except (TypeError, ValueError):
            return None
    if isinstance(value, (int, float)):
        return f"{float(value):g}"
    return None


def _shadow_to_string(value: Any) -> Optional[str]:
    if not isinstance(value, list) or not value:
        return None
    parts: List[str] = []
    for shadow in value:
        offset = shadow.get("offset", {})
        x = offset.get("x", 0)
        y = offset.get("y", 0)
        radius = shadow.get("radius", 0)
        spread = shadow.get("spread", 0)
        color = _parse_figma_color(shadow.get("color", {}))
        if color is None:
            color = "rgba(0, 0, 0, 0.1)"
        parts.append(f"{x:g} {y:g} {radius:g} {spread:g} {color}")
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# Fallback extractor (from comprehensive frame data)
# ---------------------------------------------------------------------------


def _tokens_from_frames(frames: List[Dict[str, Any]]) -> TokenCollection:
    """Extract tokens from already-parsed frame data when variables are absent."""
    collection = TokenCollection(source="extracted_fallback")

    seen_colors: Dict[str, ColorToken] = {}
    seen_fonts: Dict[str, TypographyToken] = {}
    seen_spacing: Dict[str, SpacingToken] = {}
    seen_radii: Dict[str, RadiusToken] = {}
    seen_shadows: Dict[str, ShadowToken] = {}

    for frame in frames:
        cd = frame.get("comprehensive_data", {})
        ds = cd.get("design_system", {}) if isinstance(cd, dict) else {}

        # Colors
        colors = ds.get("colors", []) or []
        for idx, hex_value in enumerate(colors):
            if not isinstance(hex_value, str):
                continue
            slug = _slugify(hex_value) or f"color-idx-{idx}"
            token_name = f"color-{slug}"
            if token_name not in seen_colors:
                seen_colors[token_name] = ColorToken(
                    name=token_name,
                    value=hex_value,
                    source="hex_literal",
                    description=frame.get("name", ""),
                )

        # Typography
        typography = ds.get("typography", {}) or {}
        for key, style in typography.items():
            if not isinstance(style, dict):
                continue
            font_family = style.get("font_family") or style.get("fontFamily") or "Unknown"
            font_size = style.get("font_size") or style.get("fontSize") or 14
            font_weight = style.get("font_weight") or style.get("fontWeight") or 400
            slug = _slugify(str(font_family)) or "sans"
            token_name = f"font-{slug}-{font_size}"
            if token_name not in seen_fonts:
                seen_fonts[token_name] = TypographyToken(
                    name=token_name,
                    font_family=str(font_family),
                    font_size=f"{font_size}px",
                    font_weight=int(font_weight) if str(font_weight).isdigit() else 400,
                )

        # Spacing — pulled off layout / containers
        layout = cd.get("layout", {}) if isinstance(cd, dict) else {}
        gap = layout.get("gap")
        if isinstance(gap, (int, float)) and gap > 0:
            slug = _slugify(f"gap-{gap:g}") or f"gap-{idx}"
            token_name = f"spacing-{slug}"
            if token_name not in seen_spacing:
                seen_spacing[token_name] = SpacingToken(
                    name=token_name, value=f"{gap:g}px"
                )
        padding = layout.get("padding") or {}
        if isinstance(padding, dict):
            for side, val in padding.items():
                if isinstance(val, (int, float)) and val > 0:
                    token_name = f"spacing-{side}"
                    if token_name not in seen_spacing:
                        seen_spacing[token_name] = SpacingToken(
                            name=token_name, value=f"{val:g}px"
                        )

        # Radii — look for cornerRadius / borderRadius on layout containers
        for container in cd.get("content", {}).get("containers", []) or []:
            rx = container.get("border_radius") if isinstance(container, dict) else None
            if isinstance(rx, (int, float)) and rx > 0:
                token_name = f"radius-md"
                if token_name not in seen_radii:
                    seen_radii[token_name] = RadiusToken(
                        name=token_name, value=f"{rx:g}px"
                    )

        # Shadows — currently we only have a `effects` blob
        # in comprehensive_data. Skip detailed parsing; we only count them.
        # Future: extract individual shadow offsets + colors.

    collection.colors = list(seen_colors.values())
    collection.typography = list(seen_fonts.values())
    collection.spacing = list(seen_spacing.values())
    collection.radius = list(seen_radii.values())
    collection.shadows = list(seen_shadows.values())
    return collection


def _merge_collections(base: TokenCollection, extra: TokenCollection) -> TokenCollection:
    """Merge two TokenCollections — extra fills gaps but does not override base."""
    if not extra.has_tokens():
        return base
    if not base.has_tokens():
        return extra
    merged = TokenCollection(
        colors=_merge_lists(base.colors, extra.colors, lambda t: t.name),
        typography=_merge_lists(base.typography, extra.typography, lambda t: t.name),
        spacing=_merge_lists(base.spacing, extra.spacing, lambda t: t.name),
        radius=_merge_lists(base.radius, extra.radius, lambda t: t.name),
        shadows=_merge_lists(base.shadows, extra.shadows, lambda t: t.name),
    )
    return merged


def _merge_lists(items, extras, key) -> list:
    seen = {key(item) for item in items}
    merged = list(items)
    for item in extras:
        if key(item) not in seen:
            merged.append(item)
            seen.add(key(item))
    return merged


# ---------------------------------------------------------------------------
# Helpers — name normalisation, slugification
# ---------------------------------------------------------------------------

_RE_NON_SLUG = re.compile(r"[^a-z0-9]+")


def _slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = _RE_NON_SLUG.sub("-", s).strip("-")
    return s


def _normalize_name(name: str) -> str:
    """Convert a Figma variable name to a stable kebab-case token name.

    Figma convention is ``Category/Subcategory/Role``, e.g.
    ``Color/Brand/Primary`` → ``color-brand-primary``.
    """
    if not name:
        return ""
    parts = [_ for _ in (p.strip() for p in name.split("/")) if _]
    return "-".join(_slugify(p) for p in parts).strip("-")


def _make_color(name: str, value: str, source: str) -> ColorToken:
    token_name = _normalize_name(name)
    return ColorToken(
        name=token_name,
        value=value,
        source=source,
        description=name,
    )


def _lower_token_name(name: str) -> str:
    return (name or "").strip().lower()


def _looks_like_spacing(name: str) -> bool:
    lowered = name.lower()
    spacing_keywords = ("spacing", "space", "padding", "margin", "gap", "stack", "inset")
    return any(kw in lowered for kw in spacing_keywords)
