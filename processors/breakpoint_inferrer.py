"""Breakpoint inference for responsive designs (Plan 005, Phase 2).

Analyzes Figma frame widths to infer responsive breakpoints and wraps
CSS or Tailwind classes accordingly.

Typical usage::

    inferrer = BreakpointInferrer()
    breakpoints = inferrer.infer_from_frames(frames_list)
    # -> {"mobile": 375, "tablet": 768, "desktop": 1440}
    
    css_block = inferrer.wrap_css(css_rules, breakpoints["tablet"], "max-width")
    # -> "@media (max-width: 768px) {\\n  ...\\n}"
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default breakpoints (matching common device widths)
# ---------------------------------------------------------------------------

DEFAULT_BREAKPOINTS: Dict[str, int] = {
    "mobile": 375,
    "tablet": 768,
    "desktop": 1440,
}

_DEFAULT_ORDER: List[str] = ["mobile", "tablet", "desktop"]


# ---------------------------------------------------------------------------
# Inferrer
# ---------------------------------------------------------------------------


class BreakpointInferrer:
    """Analyse frame widths to infer sensible responsive breakpoints."""

    def infer_from_frames(self, frames: List[Dict[str, Any]]) -> Dict[str, int]:
        """Return breakpoints inferred from the given frames' widths.

        Each frame dict should have a ``dimensions`` key with a ``width``
        field, or a ``width`` key directly.

        Returns a dict like ``{"mobile": 375, "tablet": 768, "desktop": 1440}``.
        """
        widths = self._collect_widths(frames)
        return self._infer(widths)

    def infer_from_widths(self, widths: List[float]) -> Dict[str, int]:
        """Infer breakpoints from a raw list of frame widths."""
        return self._infer(widths)

    def breakpoint_for_width(self, width: float, breakpoints: Dict[str, int]) -> str:
        """Return the breakpoint label (e.g. ``"mobile"``) for a given width."""
        ordered = sorted(breakpoints.items(), key=lambda kv: kv[1])
        for label, bp in ordered:
            if width <= bp:
                return label
        return ordered[-1][0] if ordered else "desktop"

    def wrap_css(
        self,
        css_rules: str,
        breakpoint: int,
        mode: str = "max-width",
    ) -> str:
        """Wrap CSS rules in a ``@media`` query.

        Args:
            css_rules: One or more CSS declarations/rules.
            breakpoint: Pixel value for the breakpoint.
            mode: ``"max-width"`` (desktop-first) or ``"min-width"`` (mobile-first).

        Returns:
            The wrapped media query string.
        """
        feature = f"({mode}: {breakpoint}px)"
        return f"@media {feature} {{\n{css_rules}\n}}"

    def wrap_tailwind_prefix(
        self,
        tailwind_classes: List[str],
        breakpoint_label: str,
    ) -> List[str]:
        """Prepend a Tailwind responsive prefix to each class.

        Example::

            wrap_tailwind_prefix(["flex-col", "gap-2"], "md")
            # -> ["md:flex-col", "md:gap-2"]
        """
        return [f"{breakpoint_label}:{c}" for c in tailwind_classes]

    @staticmethod
    def format_breakpoints_css(
        breakpoints: Dict[str, int],
        indent: str = "  ",
    ) -> str:
        """Generate a CSS custom-property block with breakpoint values.

        Useful for embedding in ``:root`` or Tailwind ``@theme``.
        """
        lines = [f"{indent}--bp-{label}: {value}px;" for label, value in breakpoints.items()]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_widths(frames: List[Dict[str, Any]]) -> List[float]:
        widths: List[float] = []
        for frame in frames:
            dims = frame.get("dimensions") or {}
            width = dims.get("width") or frame.get("width")
            if width and isinstance(width, (int, float)) and width > 0:
                widths.append(float(width))
        return widths

    def _infer(self, widths: List[float]) -> Dict[str, int]:
        if not widths:
            return dict(DEFAULT_BREAKPOINTS)

        unique = sorted(set(widths))

        # If only one unique width, use presets that encompass it
        if len(unique) == 1:
            return self._presets_for_single(unique[0])

        # Cluster widths into at most 3 groups
        return self._cluster_widths(unique)

    @staticmethod
    def _presets_for_single(width: float) -> Dict[str, int]:
        """Pick sensible breakpoint labels for a uniform design."""
        if width <= 480:
            return {"mobile": width, "tablet": 768, "desktop": 1440}
        if width <= 900:
            return {"mobile": 375, "tablet": width, "desktop": 1440}
        return {"mobile": 375, "tablet": 768, "desktop": width}

    @staticmethod
    def _cluster_widths(unique: List[float]) -> Dict[str, int]:
        """Assign up to 3 unique widths to mobile/tablet/desktop buckets."""
        result: Dict[str, int] = {}

        if len(unique) >= 3:
            result["mobile"] = int(unique[0])
            result["tablet"] = int(unique[len(unique) // 2])
            result["desktop"] = int(unique[-1])
        elif len(unique) == 2:
            smaller, larger = int(unique[0]), int(unique[-1])
            if smaller <= 480:
                result["mobile"] = smaller
                result["tablet"] = int(larger * 0.55)
                result["desktop"] = larger
            elif smaller <= 900:
                result["mobile"] = int(smaller * 0.5)
                result["tablet"] = smaller
                result["desktop"] = larger
            else:
                result["tablet"] = smaller
                result["desktop"] = larger
                result["mobile"] = int(smaller * 0.5)

        return result
