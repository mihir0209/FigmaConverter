"""Auto Layout to CSS Flexbox/Grid converter (Plan 005).

Translates Figma Auto Layout properties parsed by
``EnhancedFrameParser._extract_layout_info()`` into CSS declarations.

Usage::

    converter = LayoutConverter()
    css_props = converter.convert_layout(layout_dict)
    # -> {"display": "flex", "flex-direction": "row", "gap": "16px", ...}
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Axis alignment mapping
# ---------------------------------------------------------------------------

_PRIMARY_AXIS_MAP: Dict[str, str] = {
    "MIN": "flex-start",
    "CENTER": "center",
    "MAX": "flex-end",
    "SPACE_BETWEEN": "space-between",
    "SPACE_AROUND": "space-around",
    "SPACE_EVENLY": "space-evenly",
}

_COUNTER_AXIS_MAP: Dict[str, str] = {
    "MIN": "flex-start",
    "CENTER": "center",
    "MAX": "flex-end",
    "STRETCH": "stretch",
    "BASELINE": "baseline",
}

_SIZING_MAP: Dict[str, Optional[str]] = {
    "FILL": "100%",
    "HUG": "fit-content",
}

# ---------------------------------------------------------------------------
# Converter
# ---------------------------------------------------------------------------


class LayoutConverter:
    """Convert Figma Auto Layout data into CSS property declarations."""

    def convert_layout(self, layout: Dict[str, Any]) -> Dict[str, str]:
        """Return CSS properties for the given Auto Layout frame.

        Accepts the dict produced by ``_extract_layout_info()``.
        Returns a mapping of CSS property → value (e.g.
        ``{"display": "flex", "flex-direction": "column"}``).
        """
        props: Dict[str, str] = {}
        layout_mode = layout.get("layout_mode") or layout.get("layoutMode")

        if layout_mode in ("HORIZONTAL", "VERTICAL"):
            self._apply_flexbox(layout, layout_mode, props)
        else:
            props["display"] = "block"

        # Sizing (width / height)
        self._apply_sizing(layout, "sizing_horizontal", "width", props)
        self._apply_sizing(layout, "sizing_vertical", "height", props)

        return props

    def convert_to_css_block(
        self, layout: Dict[str, Any], indent: str = "  "
    ) -> str:
        """Return a CSS rule body string.

        Example::

            display: flex;
            flex-direction: row;
            gap: 16px;
            justify-content: center;
            align-items: center;
        """
        props = self.convert_layout(layout)
        return "\n".join(f"{indent}{k}: {v};" for k, v in props.items())

    def convert_to_tailwind_classes(self, layout: Dict[str, Any]) -> List[str]:
        """Return a list of Tailwind utility classes.

        Example::

            ["flex", "flex-row", "gap-4", "items-center", "justify-center"]
        """
        classes: List[str] = []
        layout_mode = layout.get("layout_mode") or layout.get("layoutMode")

        if layout_mode in ("HORIZONTAL", "VERTICAL"):
            classes.append("flex")
            classes.append("flex-row" if layout_mode == "HORIZONTAL" else "flex-col")

            # Gap — convert px to Tailwind spacing scale (divide by 4)
            gap = layout.get("gap") or layout.get("itemSpacing") or 0
            if gap:
                tw_gap = _px_to_tailwind_gap(float(gap))
                classes.append(f"gap-{tw_gap}")

            # Primary axis → justify-*
            primary = layout.get("primary_axis_align_items") or layout.get("primaryAxisAlignItems")
            tw_justify = _primary_to_tailwind(primary)
            if tw_justify:
                classes.append(tw_justify)

            # Counter axis → items-*
            counter = layout.get("counter_axis_align_items") or layout.get("counterAxisAlignItems")
            tw_items = _counter_to_tailwind(counter)
            if tw_items:
                classes.append(tw_items)

            # Sizing
            sizing_h = layout.get("sizing_horizontal") or layout.get("layoutSizingHorizontal")
            sizing_v = layout.get("sizing_vertical") or layout.get("layoutSizingVertical")
            if sizing_h == "FILL":
                classes.append("w-full")
            if sizing_v == "FILL":
                classes.append("h-full")

            # Padding
            padding = layout.get("padding") or {}
            if padding:
                top = padding.get("top", 0)
                right = padding.get("right", 0)
                bottom = padding.get("bottom", 0)
                left = padding.get("left", 0)
                tw_pad = _padding_to_tailwind(top, right, bottom, left)
                if tw_pad:
                    classes.extend(tw_pad)

        return classes

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_flexbox(
        layout: Dict[str, Any], layout_mode: str, props: Dict[str, str]
    ) -> None:
        props["display"] = "flex"
        props["flex-direction"] = "row" if layout_mode == "HORIZONTAL" else "column"

        # Gap
        gap = layout.get("gap") or layout.get("itemSpacing") or 0
        if gap:
            props["gap"] = _format_px(float(gap))

        # Primary axis → justify-content
        primary = (
            layout.get("primary_axis_align_items")
            or layout.get("primaryAxisAlignItems")
        )
        if primary and primary in _PRIMARY_AXIS_MAP:
            props["justify-content"] = _PRIMARY_AXIS_MAP[primary]

        # Counter axis → align-items
        counter = (
            layout.get("counter_axis_align_items")
            or layout.get("counterAxisAlignItems")
        )
        if counter and counter in _COUNTER_AXIS_MAP:
            props["align-items"] = _COUNTER_AXIS_MAP[counter]

        # Layout wrap → flex-wrap
        wrap = layout.get("layout_wrap") or layout.get("layoutWrap")
        if wrap == "WRAP":
            props["flex-wrap"] = "wrap"

    @staticmethod
    def _apply_sizing(
        layout: Dict[str, Any],
        key: str,
        css_prop: str,
        props: Dict[str, str],
    ) -> None:
        value = layout.get(key) or layout.get(
            "layoutSizingHorizontal" if css_prop == "width" else "layoutSizingVertical"
        )
        if value in _SIZING_MAP:
            mapped = _SIZING_MAP[value]
            if mapped:
                props[css_prop] = mapped
        elif value == "FIXED":
            # Take explicit dimension from the frame bounding box
            dims = layout.get("dimensions") or {}
            px_value = dims.get(css_prop)
            if px_value:
                props[css_prop] = _format_px(float(px_value))


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _format_px(value: float) -> str:
    """Format a number as a CSS pixel value, e.g. ``16`` → ``"16px"``."""
    return f"{value:g}px" if value == int(value) else f"{value}px"


def _px_to_tailwind_gap(px: float) -> int:
    """Convert a pixel gap to the nearest Tailwind spacing unit (1 = 4px)."""
    return max(0, int(math.ceil(px / 4)))


def _primary_to_tailwind(value: Optional[str]) -> Optional[str]:
    """Map Figma primary-axis alignment to Tailwind ``justify-*`` class."""
    mapping = {
        "MIN": "justify-start",
        "CENTER": "justify-center",
        "MAX": "justify-end",
        "SPACE_BETWEEN": "justify-between",
        "SPACE_AROUND": "justify-around",
        "SPACE_EVENLY": "justify-evenly",
    }
    if value:
        return mapping.get(value)


def _counter_to_tailwind(value: Optional[str]) -> Optional[str]:
    """Map Figma counter-axis alignment to Tailwind ``items-*`` class."""
    mapping = {
        "MIN": "items-start",
        "CENTER": "items-center",
        "MAX": "items-end",
        "STRETCH": "items-stretch",
        "BASELINE": "items-baseline",
    }
    if value:
        return mapping.get(value)


def _padding_to_tailwind(top: float, right: float, bottom: float, left: float) -> List[str]:
    """Convert per-side padding to Tailwind padding classes."""
    classes: List[str] = []
    if top == right == bottom == left and top > 0:
        unit = _px_to_tailwind_gap(top)
        classes.append(f"p-{unit}")
    else:
        if top > 0:
            classes.append(f"pt-{_px_to_tailwind_gap(top)}")
        if right > 0:
            classes.append(f"pr-{_px_to_tailwind_gap(right)}")
        if bottom > 0:
            classes.append(f"pb-{_px_to_tailwind_gap(bottom)}")
        if left > 0:
            classes.append(f"pl-{_px_to_tailwind_gap(left)}")
    return classes
