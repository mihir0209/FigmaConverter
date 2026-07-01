"""Tests for the Auto Layout → Flexbox/Grid converter (Plan 005)."""

import pytest

from processors.layout_converter import (
    LayoutConverter,
    _counter_to_tailwind,
    _format_px,
    _padding_to_tailwind,
    _primary_to_tailwind,
    _px_to_tailwind_gap,
)

converter = LayoutConverter()


# ---------------------------------------------------------------------------
# CSS output
# ---------------------------------------------------------------------------


class TestConvertLayoutCSS:
    def test_non_auto_layout_is_block(self):
        props = converter.convert_layout({"layout_mode": None})
        assert props == {"display": "block"}

    def test_horizontal_flexbox(self):
        props = converter.convert_layout({
            "layout_mode": "HORIZONTAL",
            "gap": 16,
        })
        assert props["display"] == "flex"
        assert props["flex-direction"] == "row"
        assert props["gap"] == "16px"

    def test_vertical_flexbox(self):
        props = converter.convert_layout({
            "layout_mode": "VERTICAL",
            "gap": 8,
        })
        assert props["display"] == "flex"
        assert props["flex-direction"] == "column"
        assert props["gap"] == "8px"

    def test_no_gap_omitted(self):
        props = converter.convert_layout({
            "layout_mode": "HORIZONTAL",
            "gap": 0,
        })
        assert "gap" not in props

    def test_primary_axis_alignment(self):
        cases = [
            ("MIN", "flex-start"),
            ("CENTER", "center"),
            ("MAX", "flex-end"),
            ("SPACE_BETWEEN", "space-between"),
        ]
        for figma_val, expected in cases:
            props = converter.convert_layout({
                "layout_mode": "HORIZONTAL",
                "primaryAxisAlignItems": figma_val,
            })
            assert props.get("justify-content") == expected, f"{figma_val} → {expected}"

    def test_primary_axis_uses_snake_case_key(self):
        props = converter.convert_layout({
            "layout_mode": "HORIZONTAL",
            "primary_axis_align_items": "CENTER",
        })
        assert props.get("justify-content") == "center"

    def test_counter_axis_alignment(self):
        cases = [
            ("MIN", "flex-start"),
            ("CENTER", "center"),
            ("MAX", "flex-end"),
            ("STRETCH", "stretch"),
            ("BASELINE", "baseline"),
        ]
        for figma_val, expected in cases:
            props = converter.convert_layout({
                "layout_mode": "HORIZONTAL",
                "counterAxisAlignItems": figma_val,
            })
            assert props.get("align-items") == expected, f"{figma_val} → {expected}"

    def test_wrap_produces_flex_wrap(self):
        props = converter.convert_layout({
            "layout_mode": "HORIZONTAL",
            "layoutWrap": "WRAP",
        })
        assert props.get("flex-wrap") == "wrap"

    def test_no_wrap_omits_flex_wrap(self):
        props = converter.convert_layout({
            "layout_mode": "HORIZONTAL",
            "layoutWrap": "NO_WRAP",
        })
        assert "flex-wrap" not in props

    def test_sizing_fill(self):
        props = converter.convert_layout({
            "layout_mode": "HORIZONTAL",
            "sizing_horizontal": "FILL",
        })
        assert props.get("width") == "100%"

    def test_sizing_hug(self):
        props = converter.convert_layout({
            "layout_mode": "HORIZONTAL",
            "sizing_vertical": "HUG",
        })
        assert props.get("height") == "fit-content"

    def test_sizing_fixed_with_dimensions(self):
        props = converter.convert_layout({
            "layout_mode": "HORIZONTAL",
            "sizing_horizontal": "FIXED",
            "dimensions": {"width": 120},
        })
        assert props.get("width") == "120px"

    def test_sizing_fixed_no_dimensions(self):
        props = converter.convert_layout({
            "layout_mode": "HORIZONTAL",
            "sizing_horizontal": "FIXED",
        })
        assert "width" not in props

    def test_full_css_block(self):
        css = converter.convert_to_css_block({
            "layout_mode": "VERTICAL",
            "gap": 16,
            "primaryAxisAlignItems": "CENTER",
            "counterAxisAlignItems": "CENTER",
            "sizing_horizontal": "FILL",
        })
        assert "display: flex;" in css
        assert "flex-direction: column;" in css
        assert "gap: 16px;" in css
        assert "justify-content: center;" in css
        assert "align-items: center;" in css
        assert "width: 100%;" in css

    def test_empty_layout_returns_block(self):
        props = converter.convert_layout({})
        assert props == {"display": "block"}


# ---------------------------------------------------------------------------
# Tailwind output
# ---------------------------------------------------------------------------


class TestConvertLayoutTailwind:
    def test_horizontal_flex(self):
        classes = converter.convert_to_tailwind_classes({
            "layout_mode": "HORIZONTAL",
        })
        assert "flex" in classes
        assert "flex-row" in classes

    def test_vertical_flex(self):
        classes = converter.convert_to_tailwind_classes({
            "layout_mode": "VERTICAL",
        })
        assert "flex" in classes
        assert "flex-col" in classes

    def test_gap_conversion(self):
        classes = converter.convert_to_tailwind_classes({
            "layout_mode": "HORIZONTAL",
            "gap": 16,
        })
        assert "gap-4" in classes

    def test_gap_rounds(self):
        classes = converter.convert_to_tailwind_classes({
            "layout_mode": "HORIZONTAL",
            "gap": 10,
        })
        assert "gap-3" in classes or "gap-2" in classes

    def test_primary_axis(self):
        classes = converter.convert_to_tailwind_classes({
            "layout_mode": "HORIZONTAL",
            "primaryAxisAlignItems": "CENTER",
        })
        assert "justify-center" in classes

    def test_counter_axis(self):
        classes = converter.convert_to_tailwind_classes({
            "layout_mode": "HORIZONTAL",
            "counterAxisAlignItems": "CENTER",
        })
        assert "items-center" in classes

    def test_sizing_fill(self):
        classes = converter.convert_to_tailwind_classes({
            "layout_mode": "HORIZONTAL",
            "sizing_horizontal": "FILL",
        })
        assert "w-full" in classes

    def test_uniform_padding(self):
        classes = converter.convert_to_tailwind_classes({
            "layout_mode": "HORIZONTAL",
            "padding": {"top": 16, "right": 16, "bottom": 16, "left": 16},
        })
        assert "p-4" in classes

    def test_uneven_padding(self):
        classes = converter.convert_to_tailwind_classes({
            "layout_mode": "HORIZONTAL",
            "padding": {"top": 8, "right": 16, "bottom": 8, "left": 16},
        })
        assert "pt-2" in classes
        assert "pr-4" in classes
        assert "pb-2" in classes
        assert "pl-4" in classes

    def test_non_auto_layout_returns_empty(self):
        classes = converter.convert_to_tailwind_classes({})
        assert classes == []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestFormatPx:
    def test_integer(self):
        assert _format_px(16) == "16px"

    def test_float(self):
        assert _format_px(8.5) == "8.5px"

    def test_zero(self):
        assert _format_px(0) == "0px"


class TestPxToTailwindGap:
    def test_exact(self):
        assert _px_to_tailwind_gap(16) == 4

    def test_rounds(self):
        assert _px_to_tailwind_gap(10) == 3  # 10/4 = 2.5 → 3

    def test_zero(self):
        assert _px_to_tailwind_gap(0) == 0

    def test_small(self):
        assert _px_to_tailwind_gap(2) == 1  # 2/4 = 0.5 → 1


class TestPrimaryToTailwind:
    def test_all_mappings(self):
        assert _primary_to_tailwind("MIN") == "justify-start"
        assert _primary_to_tailwind("CENTER") == "justify-center"
        assert _primary_to_tailwind("MAX") == "justify-end"
        assert _primary_to_tailwind("SPACE_BETWEEN") == "justify-between"
        assert _primary_to_tailwind("SPACE_AROUND") == "justify-around"
        assert _primary_to_tailwind("SPACE_EVENLY") == "justify-evenly"

    def test_unknown(self):
        assert _primary_to_tailwind("FOO") is None

    def test_none(self):
        assert _primary_to_tailwind(None) is None


class TestCounterToTailwind:
    def test_all_mappings(self):
        assert _counter_to_tailwind("MIN") == "items-start"
        assert _counter_to_tailwind("CENTER") == "items-center"
        assert _counter_to_tailwind("MAX") == "items-end"
        assert _counter_to_tailwind("STRETCH") == "items-stretch"
        assert _counter_to_tailwind("BASELINE") == "items-baseline"

    def test_unknown(self):
        assert _counter_to_tailwind("FOO") is None

    def test_none(self):
        assert _counter_to_tailwind(None) is None


class TestPaddingToTailwind:
    def test_uniform(self):
        classes = _padding_to_tailwind(16, 16, 16, 16)
        assert classes == ["p-4"]

    def test_per_side(self):
        classes = _padding_to_tailwind(8, 16, 12, 4)
        assert "pt-2" in classes
        assert "pr-4" in classes
        assert "pb-3" in classes
        assert "pl-1" in classes

    def test_zero_omitted(self):
        classes = _padding_to_tailwind(0, 16, 0, 16)
        assert "pt-0" not in classes
        assert "pr-4" in classes

    def test_all_zero(self):
        assert _padding_to_tailwind(0, 0, 0, 0) == []


# ---------------------------------------------------------------------------
# Integration: parser output → converter
# ---------------------------------------------------------------------------


class TestParserIntegration:
    """Verify the converter works with the exact dict shape the parser emits."""

    def test_parser_like_dict_horizontal(self):
        """Simulate `_extract_layout_info` output for a horizontal frame."""
        layout = {
            "background_color": "#ffffff",
            "padding": {"top": 16, "right": 24, "bottom": 16, "left": 24},
            "constraints": {},
            "scroll_behavior": "SCROLLS",
            "blend_mode": "PASS_THROUGH",
            "layout_mode": "HORIZONTAL",
            "primary_axis_align_items": "CENTER",
            "counter_axis_align_items": "CENTER",
            "sizing_horizontal": "FILL",
            "sizing_vertical": "HUG",
            "layout_grow": 0,
            "layout_align": "MIN",
            "layout_wrap": "NO_WRAP",
        }
        css = converter.convert_to_css_block(layout)
        assert "display: flex;" in css
        assert "flex-direction: row;" in css
        assert "justify-content: center;" in css
        assert "align-items: center;" in css
        assert "width: 100%;" in css
        assert "height: fit-content;" in css

    def test_parser_like_dict_vertical(self):
        layout = {
            "background_color": "#f5f5f5",
            "padding": {"top": 8, "right": 8, "bottom": 8, "left": 8},
            "layout_mode": "VERTICAL",
            "primary_axis_align_items": "SPACE_BETWEEN",
            "sizing_horizontal": "FILL",
        }
        css = converter.convert_to_css_block(layout)
        assert "flex-direction: column;" in css
        assert "justify-content: space-between;" in css
        assert "width: 100%;" in css
