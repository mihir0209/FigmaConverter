"""Tests for the EnhancedFrameParser — including the previously-stub helpers."""

import pytest

from parsers.enhanced_frame_parser import EnhancedFrameParser


def _autolayout_node():
    """Single frame with two siblings — exercises the auto-layout paths."""

    return {
        "id": "0:1",
        "name": "Auto Layout Frame",
        "type": "FRAME",
        "layoutMode": "VERTICAL",
        "paddingLeft": 12,
        "paddingRight": 16,
        "paddingTop": 8,
        "paddingBottom": 24,
        "itemSpacing": 14,
        "absoluteBoundingBox": {"x": 0, "y": 0, "width": 375, "height": 812},
        "backgroundColor": {"r": 1, "g": 1, "b": 1, "a": 1},
        "children": [
            {"id": "0:2", "type": "FRAME", "name": "card-1", "children": []},
            {"id": "0:3", "type": "FRAME", "name": "card-2", "children": []},
        ],
    }


class TestFrameParserBasic:
    def test_returns_extractable_payload(self, sample_frame_node):
        parser = EnhancedFrameParser()
        out = parser.parse_frame_comprehensive(sample_frame_node, None)
        for key in (
            "basic_info",
            "layout",
            "content",
            "design_system",
            "structure",
            "component_count",
            "complexity_score",
        ):
            assert key in out

    def test_counts_text_and_interactive_elements(self, sample_frame_node):
        parser = EnhancedFrameParser()
        out = parser.parse_frame_comprehensive(sample_frame_node, None)
        counts = out["component_count"]
        # Two rectangles, one of them is named button-like and the other input-like
        # in the sample fixture, plus one text.
        assert counts["texts"] >= 1
        assert counts["containers"] >= 1

    def test_color_palette_uses_hex(self, sample_frame_node):
        parser = EnhancedFrameParser()
        out = parser.parse_frame_comprehensive(sample_frame_node, None)
        assert all(c.startswith("#") and len(c) == 7 for c in out["design_system"]["colors"])


class TestLayoutHelpers:
    def test_detect_layout_type_vertical(self):
        parser = EnhancedFrameParser()
        assert (
            parser._detect_layout_type(_autolayout_node()) == "vertical-flow"
        )

    def test_detect_layout_type_horizontal(self):
        node = _autolayout_node()
        node["layoutMode"] = "HORIZONTAL"
        parser = EnhancedFrameParser()
        assert parser._detect_layout_type(node) == "horizontal-flow"

    def test_detect_padding_reads_each_side(self):
        node = _autolayout_node()
        detected = EnhancedFrameParser()._detect_padding(node)
        assert detected == {"top": 8, "right": 16, "bottom": 24, "left": 12}

    def test_detect_padding_falls_back_to_uniform(self):
        node = {"padding": 8}
        assert EnhancedFrameParser()._detect_padding(node) == {
            "top": 8, "right": 8, "bottom": 8, "left": 8,
        }

    def test_spacing_patterns_reads_item_spacing(self):
        node = _autolayout_node()
        spacing = EnhancedFrameParser()._extract_spacing_patterns(node)
        assert spacing["gap"] == 14
        assert spacing["padding"]["left"] == 12
        assert spacing["layout_mode"] == "VERTICAL"

    def test_build_hierarchy_reports_actual_depth(self):
        node = {
            "id": "r",
            "children": [
                {
                    "id": "a",
                    "children": [
                        {"id": "b", "children": [{"id": "c", "children": []}]}
                    ],
                }
            ],
        }
        hierarchy = EnhancedFrameParser()._build_component_hierarchy(node)
        assert hierarchy["depth"] >= 3

    def test_responsive_hints_surface_layout_mode(self):
        node = _autolayout_node()
        hints = EnhancedFrameParser()._detect_responsive_patterns(node)
        assert hints["auto_layout"] == "VERTICAL"
        assert hints["flexible"] is True
