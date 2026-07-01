"""Tests for the breakpoint inference module (Plan 005, Phase 2)."""

import pytest

from processors.breakpoint_inferrer import (
    DEFAULT_BREAKPOINTS,
    BreakpointInferrer,
)

inferrer = BreakpointInferrer()


# ---------------------------------------------------------------------------
# Inference from widths
# ---------------------------------------------------------------------------


class TestInferFromWidths:
    def test_empty_returns_defaults(self):
        bp = inferrer.infer_from_widths([])
        assert bp == DEFAULT_BREAKPOINTS

    def test_single_mobile_width(self):
        bp = inferrer.infer_from_widths([375])
        assert bp["mobile"] == 375
        assert bp["tablet"] == 768
        assert bp["desktop"] == 1440

    def test_single_desktop_width(self):
        bp = inferrer.infer_from_widths([1440])
        assert bp["desktop"] == 1440
        assert bp["mobile"] == 375
        assert bp["tablet"] == 768

    def test_single_medium_width(self):
        bp = inferrer.infer_from_widths([800])
        assert bp["tablet"] == 800

    def test_two_widths_mobile_and_desktop(self):
        bp = inferrer.infer_from_widths([375, 1440])
        assert bp["mobile"] == 375
        assert bp["desktop"] == 1440

    def test_two_widths_tablet_and_desktop(self):
        bp = inferrer.infer_from_widths([768, 1440])
        assert bp["tablet"] == 768
        assert bp["desktop"] == 1440

    def test_three_widths(self):
        bp = inferrer.infer_from_widths([375, 768, 1440])
        assert bp["mobile"] == 375
        assert bp["tablet"] == 768
        assert bp["desktop"] == 1440

    def test_many_widths_clusters(self):
        bp = inferrer.infer_from_widths([320, 375, 414, 768, 1024, 1440, 1920])
        assert "mobile" in bp
        assert "tablet" in bp
        assert "desktop" in bp
        assert bp["mobile"] < bp["tablet"] < bp["desktop"]


# ---------------------------------------------------------------------------
# Inference from frame dicts
# ---------------------------------------------------------------------------


class TestInferFromFrames:
    def test_uses_dimensions_key(self):
        bp = inferrer.infer_from_frames([
            {"dimensions": {"width": 375, "height": 812}},
            {"dimensions": {"width": 1440, "height": 900}},
        ])
        assert bp["mobile"] == 375
        assert bp["desktop"] == 1440

    def test_fallback_to_width_key(self):
        bp = inferrer.infer_from_frames([
            {"width": 768},
            {"width": 1024},
        ])
        assert bp["tablet"] in (768, 1024)

    def test_skips_zero_width(self):
        bp = inferrer.infer_from_frames([
            {"dimensions": {"width": 0}},
            {"dimensions": {"width": 1440}},
        ])
        assert bp["desktop"] == 1440

    def test_empty_frames_returns_defaults(self):
        bp = inferrer.infer_from_frames([])
        assert bp == DEFAULT_BREAKPOINTS


# ---------------------------------------------------------------------------
# Breakpoint for width
# ---------------------------------------------------------------------------


class TestBreakpointForWidth:
    def test_mobile(self):
        bp = {"mobile": 375, "tablet": 768, "desktop": 1440}
        assert inferrer.breakpoint_for_width(320, bp) == "mobile"
        assert inferrer.breakpoint_for_width(375, bp) == "mobile"

    def test_tablet(self):
        bp = {"mobile": 375, "tablet": 768, "desktop": 1440}
        assert inferrer.breakpoint_for_width(768, bp) == "tablet"
        assert inferrer.breakpoint_for_width(600, bp) == "tablet"

    def test_desktop(self):
        bp = {"mobile": 375, "tablet": 768, "desktop": 1440}
        assert inferrer.breakpoint_for_width(1440, bp) == "desktop"
        assert inferrer.breakpoint_for_width(1920, bp) == "desktop"

    def test_empty_breakpoints(self):
        assert inferrer.breakpoint_for_width(1024, {}) == "desktop"


# ---------------------------------------------------------------------------
# wrap_css
# ---------------------------------------------------------------------------


class TestWrapCSS:
    def test_max_width(self):
        wrapped = inferrer.wrap_css("  display: none;", 768)
        assert "@media (max-width: 768px) {" in wrapped
        assert "  display: none;" in wrapped
        assert wrapped.endswith("}")

    def test_min_width(self):
        wrapped = inferrer.wrap_css("  flex-direction: column;", 768, mode="min-width")
        assert "@media (min-width: 768px) {" in wrapped

    def test_multi_rule(self):
        css = "  flex-direction: column;\n  gap: 8px;"
        wrapped = inferrer.wrap_css(css, 375)
        assert "flex-direction: column;" in wrapped
        assert "gap: 8px;" in wrapped


# ---------------------------------------------------------------------------
# wrap_tailwind_prefix
# ---------------------------------------------------------------------------


class TestWrapTailwindPrefix:
    def test_single(self):
        result = inferrer.wrap_tailwind_prefix(["flex-col"], "md")
        assert result == ["md:flex-col"]

    def test_multiple(self):
        result = inferrer.wrap_tailwind_prefix(
            ["flex-col", "gap-2", "items-center"], "lg"
        )
        assert result == ["lg:flex-col", "lg:gap-2", "lg:items-center"]

    def test_empty(self):
        assert inferrer.wrap_tailwind_prefix([], "sm") == []


# ---------------------------------------------------------------------------
# format_breakpoints_css
# ---------------------------------------------------------------------------


class TestFormatBreakpointsCSS:
    def test_generates_custom_properties(self):
        result = inferrer.format_breakpoints_css({"mobile": 375, "desktop": 1440})
        assert "--bp-mobile: 375px;" in result
        assert "--bp-desktop: 1440px;" in result

    def test_custom_indent(self):
        result = inferrer.format_breakpoints_css({"mobile": 375}, indent="    ")
        assert "    --bp-mobile: 375px;" in result
