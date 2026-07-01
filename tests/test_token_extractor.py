"""Tests for the design-token extractor (Plan 003)."""

import pytest

from processors.token_extractor import (
    _looks_like_spacing,
    _make_color,
    _normalize_name,
    _parse_figma_color,
    _parse_figma_float,
    _shadow_to_string,
    _slugify,
    _tokens_from_figma_variables,
    _tokens_from_frames,
    extract_tokens,
    tokens_as_dict,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestSlugify:
    def test_basic(self):
        assert _slugify("Hello World") == "hello-world"

    def test_multiple_spaces(self):
        assert _slugify("foo   bar") == "foo-bar"

    def test_special_chars(self):
        assert _slugify("Primary$Color@123") == "primary-color-123"

    def test_empty(self):
        assert _slugify("") == ""

    def test_none(self):
        assert _slugify(None) == ""

    def test_already_slug(self):
        assert _slugify("hello-world") == "hello-world"

    def test_leading_trailing_dashes(self):
        assert _slugify("-hello-world-") == "hello-world"


class TestNormalizeName:
    def test_figma_slash_convention(self):
        assert _normalize_name("Color/Brand/Primary") == "color-brand-primary"

    def test_single_component(self):
        assert _normalize_name("Primary") == "primary"

    def test_extra_slashes(self):
        assert _normalize_name("Shadow//Small") == "shadow-small"

    def test_empty(self):
        assert _normalize_name("") == ""

    def test_with_spaces(self):
        assert _normalize_name("Color / Accent / Light") == "color-accent-light"


class TestMakeColor:
    def test_basic(self):
        token = _make_color("Color/Primary", "#FF0000", "figma_variable")
        assert token.name == "color-primary"
        assert token.value == "#FF0000"
        assert token.source == "figma_variable"

    def test_description_is_original_name(self):
        token = _make_color("My Color", "#00FF00", "hex_literal")
        assert token.description == "My Color"


class TestLooksLikeSpacing:
    def test_spacing_keyword(self):
        assert _looks_like_spacing("spacing-md") is True

    def test_padding_keyword(self):
        assert _looks_like_spacing("padding-lg") is True

    def test_margin_keyword(self):
        assert _looks_like_spacing("margin-xl") is True

    def test_gap_keyword(self):
        assert _looks_like_spacing("gap-sm") is True

    def test_non_spacing(self):
        assert _looks_like_spacing("font-size") is False

    def test_empty(self):
        assert _looks_like_spacing("") is False


# ---------------------------------------------------------------------------
# Figma Variable Parsing
# ---------------------------------------------------------------------------


class TestParseFigmaColor:
    def test_rgba_fully_opaque(self):
        result = _parse_figma_color({"r": 1.0, "g": 0.5, "b": 0.0, "a": 1.0})
        assert result == "#FF8000"

    def test_rgba_with_alpha(self):
        result = _parse_figma_color({"r": 0.0, "g": 0.0, "b": 1.0, "a": 0.5})
        assert result == "rgba(0, 0, 255, 0.5)"

    def test_variable_alias(self):
        result = _parse_figma_color({"type": "VARIABLE_ALIAS", "id": "123"})
        assert result is None

    def test_missing_keys(self):
        result = _parse_figma_color({"r": 0.5, "g": 0.5})
        assert result is None

    def test_not_a_dict(self):
        assert _parse_figma_color("#FF0000") is None
        assert _parse_figma_color(None) is None
        assert _parse_figma_color(42) is None

    def test_edge_values(self):
        result = _parse_figma_color({"r": 0, "g": 0, "b": 0, "a": 1.0})
        assert result == "#000000"


class TestParseFigmaFloat:
    def test_dict_with_value(self):
        assert _parse_figma_float({"value": 16}) == "16"
        assert _parse_figma_float({"value": 3.5}) == "3.5"

    def test_direct_number(self):
        assert _parse_figma_float(8) == "8"
        assert _parse_figma_float(2.5) == "2.5"

    def test_none(self):
        assert _parse_figma_float(None) is None

    def test_unexpected_type(self):
        assert _parse_figma_float("foo") is None


class TestShadowToString:
    def test_single_shadow(self):
        value = [
            {
                "offset": {"x": 0, "y": 2},
                "radius": 4,
                "spread": 0,
                "color": {"r": 0, "g": 0, "b": 0, "a": 0.25},
            }
        ]
        result = _shadow_to_string(value)
        assert "0 2 4 0 rgba(" in result

    def test_multiple_shadows(self):
        value = [
            {
                "offset": {"x": 0, "y": 1},
                "radius": 2,
                "spread": 0,
                "color": {"r": 0, "g": 0, "b": 0, "a": 0.1},
            },
            {
                "offset": {"x": 0, "y": 4},
                "radius": 8,
                "spread": 0,
                "color": {"r": 0, "g": 0, "b": 0, "a": 0.15},
            },
        ]
        result = _shadow_to_string(value)
        assert ", " in result
        assert "rgba" in result

    def test_empty_list(self):
        assert _shadow_to_string([]) is None

    def test_not_a_list(self):
        assert _shadow_to_string(None) is None
        assert _shadow_to_string({}) is None


# ---------------------------------------------------------------------------
# Figma Variables → TokenCollection
# ---------------------------------------------------------------------------


class TestTokensFromFigmaVariables:
    def test_color_variable(self):
        raw = {
            "variables": {
                "var1": {
                    "name": "Color/Primary",
                    "resolvedType": "COLOR",
                    "valuesByMode": {"mode1": {"r": 0.23, "g": 0.51, "b": 0.96, "a": 1.0}},
                }
            },
            "variableCollections": {},
        }
        col = _tokens_from_figma_variables(raw)
        assert len(col.colors) == 1
        assert col.colors[0].name == "color-primary"
        assert col.colors[0].value == "#3B82F5"
        assert col.colors[0].source == "figma_variable"

    def test_float_variable_spacing(self):
        raw = {
            "variables": {
                "var1": {
                    "name": "Spacing/MD",
                    "resolvedType": "FLOAT",
                    "valuesByMode": {"mode1": {"value": 16}},
                }
            },
            "variableCollections": {},
        }
        col = _tokens_from_figma_variables(raw)
        assert len(col.spacing) == 1
        assert col.spacing[0].name == "spacing-md"
        assert col.spacing[0].value == "16"

    def test_float_variable_radius(self):
        raw = {
            "variables": {
                "var1": {
                    "name": "Radius/LG",
                    "resolvedType": "FLOAT",
                    "valuesByMode": {"mode1": {"value": 8}},
                }
            },
            "variableCollections": {},
        }
        col = _tokens_from_figma_variables(raw)
        assert len(col.radius) == 1
        assert col.radius[0].name == "radius-lg"
        assert col.radius[0].value == "8"

    def test_float_fallback_to_spacing(self):
        raw = {
            "variables": {
                "var1": {
                    "name": "Unknown/Val",
                    "resolvedType": "FLOAT",
                    "valuesByMode": {"mode1": {"value": 12}},
                }
            },
            "variableCollections": {},
        }
        col = _tokens_from_figma_variables(raw)
        # Falls through to spacing default
        assert len(col.spacing) == 1
        assert col.spacing[0].name == "unknown-val"
        assert col.spacing[0].value == "12"

    def test_string_variable_as_typography(self):
        raw = {
            "variables": {
                "var1": {
                    "name": "Font/Body",
                    "resolvedType": "STRING",
                    "valuesByMode": {"mode1": "Inter"},
                }
            },
            "variableCollections": {},
        }
        col = _tokens_from_figma_variables(raw)
        assert len(col.typography) == 1
        assert col.typography[0].name == "font-body"
        assert col.typography[0].font_family == "Inter"

    def test_shadow_variable(self):
        raw = {
            "variables": {
                "var1": {
                    "name": "Shadow/SM",
                    "resolvedType": "SHADOW",
                    "valuesByMode": {
                        "mode1": [
                            {
                                "offset": {"x": 0, "y": 1},
                                "radius": 2,
                                "spread": 0,
                                "color": {"r": 0, "g": 0, "b": 0, "a": 0.1},
                            }
                        ]
                    },
                }
            },
            "variableCollections": {},
        }
        col = _tokens_from_figma_variables(raw)
        assert len(col.shadows) == 1
        assert col.shadows[0].name == "shadow-sm"

    def test_no_variables(self):
        col = _tokens_from_figma_variables({})
        assert col.has_tokens() is False

    def test_empty_variables(self):
        col = _tokens_from_figma_variables({"variables": {}})
        assert col.has_tokens() is False

    def test_variable_with_no_values_by_mode(self):
        raw = {
            "variables": {
                "var1": {
                    "name": "Color/Primary",
                    "resolvedType": "COLOR",
                    "valuesByMode": {},
                }
            },
            "variableCollections": {},
        }
        col = _tokens_from_figma_variables(raw)
        assert col.has_tokens() is False

    def test_meta_fallback(self):
        raw = {
            "meta": {
                "variables": {
                    "var1": {
                        "name": "Color/Primary",
                        "resolvedType": "COLOR",
                        "valuesByMode": {"mode1": {"r": 1.0, "g": 0.0, "b": 0.0, "a": 1.0}},
                    }
                },
                "variableCollections": {},
            }
        }
        col = _tokens_from_figma_variables(raw)
        assert len(col.colors) == 1
        assert col.colors[0].value == "#FF0000"

    def test_radius_via_lowercase_name(self):
        raw = {
            "variables": {
                "var1": {
                    "name": "Radius/sm",
                    "resolvedType": "FLOAT",
                    "valuesByMode": {"mode1": {"value": 4}},
                }
            },
            "variableCollections": {},
        }
        col = _tokens_from_figma_variables(raw)
        assert len(col.radius) == 1
        assert col.radius[0].value == "4"


# ---------------------------------------------------------------------------
# Frame fallback extraction
# ---------------------------------------------------------------------------


class TestTokensFromFrames:
    def test_extract_colors(self):
        frames = [
            {
                "name": "Button Frame",
                "comprehensive_data": {
                    "design_system": {
                        "colors": ["#FF0000", "#00FF00", "#0000FF"],
                    },
                },
            }
        ]
        col = _tokens_from_frames(frames)
        assert len(col.colors) == 3
        assert col.colors[0].value == "#FF0000"
        assert col.colors[0].source == "hex_literal"
        assert "button" in col.colors[0].description.lower()

    def test_extract_typography(self):
        frames = [
            {
                "comprehensive_data": {
                    "design_system": {
                        "typography": {
                            "heading": {"font_family": "Inter", "font_size": 24, "font_weight": 700},
                            "body": {"font_family": "Inter", "font_size": 14, "font_weight": 400},
                        },
                    },
                },
            }
        ]
        col = _tokens_from_frames(frames)
        # Both are "Inter" → different sizes produce different slugs
        assert len(col.typography) == 2

    def test_extract_spacing_from_gap(self):
        frames = [
            {
                "comprehensive_data": {
                    "layout": {"gap": 8},
                    "design_system": {},
                },
            }
        ]
        col = _tokens_from_frames(frames)
        assert len(col.spacing) >= 1
        assert "gap-8" in col.spacing[0].name or "spacing-gap-8" in col.spacing[0].name

    def test_extract_spacing_from_padding(self):
        frames = [
            {
                "comprehensive_data": {
                    "layout": {"padding": {"top": 16, "bottom": 16}},
                    "design_system": {},
                },
            }
        ]
        col = _tokens_from_frames(frames)
        assert len(col.spacing) >= 2

    def test_extract_radius(self):
        frames = [
            {
                "comprehensive_data": {
                    "content": {
                        "containers": [
                            {"border_radius": 8},
                        ],
                    },
                    "design_system": {},
                },
            }
        ]
        col = _tokens_from_frames(frames)
        assert len(col.radius) == 1
        assert col.radius[0].value == "8px"

    def test_skips_invalid_colors(self):
        frames = [
            {
                "comprehensive_data": {
                    "design_system": {"colors": [42, None, "#FF0000"]},
                },
            }
        ]
        col = _tokens_from_frames(frames)
        assert len(col.colors) == 1

    def test_no_design_system(self):
        frames = [{"comprehensive_data": {}}]
        col = _tokens_from_frames(frames)
        assert col.has_tokens() is False

    def test_empty_frames(self):
        col = _tokens_from_frames([])
        assert col.has_tokens() is False

    def test_typography_camelCase_keys(self):
        frames = [
            {
                "comprehensive_data": {
                    "design_system": {
                        "typography": {
                            "h1": {"fontFamily": "Roboto", "fontSize": 32, "fontWeight": 900},
                        },
                    },
                },
            }
        ]
        col = _tokens_from_frames(frames)
        assert len(col.typography) == 1
        assert col.typography[0].font_family == "Roboto"


# ---------------------------------------------------------------------------
# extract_tokens() integration
# ---------------------------------------------------------------------------


class TestExtractTokens:
    def test_empty(self):
        col = extract_tokens()
        assert col.has_tokens() is False
        assert col.source == ""

    def test_figma_only(self):
        col = extract_tokens(
            figma_variables={
                "variables": {
                    "v1": {
                        "name": "Color/Primary",
                        "resolvedType": "COLOR",
                        "valuesByMode": {"m1": {"r": 1.0, "g": 0.0, "b": 0.0, "a": 1.0}},
                    }
                },
                "variableCollections": {},
            }
        )
        assert col.source == "figma_variables"
        assert len(col.colors) == 1

    def test_frames_fallback(self):
        col = extract_tokens(
            frames=[
                {
                    "comprehensive_data": {
                        "design_system": {"colors": ["#FF0000"]},
                    },
                }
            ]
        )
        assert col.source == "extracted_fallback"
        assert len(col.colors) == 1

    def test_mixed(self):
        col = extract_tokens(
            figma_variables={
                "variables": {
                    "v1": {
                        "name": "Color/Primary",
                        "resolvedType": "COLOR",
                        "valuesByMode": {"m1": {"r": 1.0, "g": 0.0, "b": 0.0, "a": 1.0}},
                    }
                },
                "variableCollections": {},
            },
            frames=[
                {
                    "comprehensive_data": {
                        "design_system": {"colors": ["#00FF00"]},
                    },
                }
            ],
        )
        assert col.source == "mixed"
        # Figma takes priority; frames fill in gaps
        assert len(col.colors) == 2

    def test_neither_input(self):
        col = extract_tokens(figma_variables=None, frames=None)
        assert col.has_tokens() is False
        assert col.source == ""

    def test_token_count_on_empty(self):
        col = extract_tokens()
        assert col.token_count == 0

    def test_token_count_populated(self):
        col = extract_tokens(
            figma_variables={
                "variables": {
                    "v1": {
                        "name": "Color/Primary",
                        "resolvedType": "COLOR",
                        "valuesByMode": {"m1": {"r": 1.0, "g": 0.0, "b": 0.0, "a": 1.0}},
                    }
                },
                "variableCollections": {},
            }
        )
        assert col.token_count == 1


class TestTokensAsDict:
    def test_empty(self):
        col = extract_tokens()
        d = tokens_as_dict(col)
        for key in ("color", "typography", "spacing", "radius", "shadow"):
            assert d[key] == {}

    def test_with_colors(self):
        col = extract_tokens(
            figma_variables={
                "variables": {
                    "v1": {
                        "name": "Color/Primary",
                        "resolvedType": "COLOR",
                        "valuesByMode": {"m1": {"r": 1.0, "g": 0.0, "b": 0.0, "a": 1.0}},
                    }
                },
                "variableCollections": {},
            }
        )
        d = tokens_as_dict(col)
        assert d["color"]["color-primary"] == "#FF0000"

    def test_with_typography(self):
        col = extract_tokens(
            figma_variables={
                "variables": {
                    "v1": {
                        "name": "Font/Body",
                        "resolvedType": "STRING",
                        "valuesByMode": {"m1": "Inter"},
                    }
                },
                "variableCollections": {},
            }
        )
        d = tokens_as_dict(col)
        assert "font-body" in d["typography"]
        assert "Inter" in d["typography"]["font-body"]

    def test_with_spacing(self):
        col = extract_tokens(
            figma_variables={
                "variables": {
                    "v1": {
                        "name": "Spacing/MD",
                        "resolvedType": "FLOAT",
                        "valuesByMode": {"m1": {"value": 16}},
                    }
                },
                "variableCollections": {},
            }
        )
        d = tokens_as_dict(col)
        assert d["spacing"]["spacing-md"] == "16"
