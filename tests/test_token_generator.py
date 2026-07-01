"""Tests for the design-token generator (Plan 003)."""

import pytest

from models import (
    ColorToken,
    RadiusToken,
    ShadowToken,
    SpacingToken,
    TokenCollection,
    TypographyToken,
)
import json

from processors.token_generator import (
    _generate_css,
    _generate_scss,
    _generate_styled,
    _generate_tailwind,
    generate_token_file,
    token_file_path,
    tokens_to_dict,
)

# Styled-components outputs JS (not pure JSON); strip trailing ";" for parsing
def _parse_styled_js(js: str) -> dict:
    prefix = "export const tokens = "
    assert js.startswith(prefix), f"Expected JS prefix, got: {js[:60]}..."
    body = js[len(prefix):]
    if body.endswith(";"):
        body = body[:-1]
    return json.loads(body)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def empty_tokens() -> TokenCollection:
    return TokenCollection()


@pytest.fixture
def basic_tokens() -> TokenCollection:
    return TokenCollection(
        colors=[
            ColorToken(name="color-primary", value="#3B82F6"),
            ColorToken(name="color-secondary", value="#10B981"),
        ],
        spacing=[
            SpacingToken(name="spacing-md", value="16px"),
            SpacingToken(name="spacing-lg", value="24px"),
        ],
        radius=[
            RadiusToken(name="radius-sm", value="4px"),
            RadiusToken(name="radius-lg", value="8px"),
        ],
        shadows=[
            ShadowToken(name="shadow-sm", value="0 1px 2px rgba(0,0,0,0.1)"),
        ],
        typography=[
            TypographyToken(name="font-body", font_family="Inter", font_size="14px", font_weight=400),
            TypographyToken(name="font-heading", font_family="Inter", font_size="24px", font_weight=700),
        ],
    )


# ---------------------------------------------------------------------------
# CSS generator
# ---------------------------------------------------------------------------


class TestGenerateCSS:
    def test_basic(self, basic_tokens):
        css = _generate_css(basic_tokens)
        assert css.startswith(":root {")
        assert css.endswith("}")
        assert "--color-primary: #3B82F6;" in css
        assert "--color-secondary: #10B981;" in css
        assert "--spacing-md: 16px;" in css
        assert "--spacing-lg: 24px;" in css
        assert "--radius-sm: 4px;" in css
        assert "--radius-lg: 8px;" in css
        assert "--shadow-sm: 0 1px 2px rgba(0,0,0,0.1);" in css

    def test_typography_output(self, basic_tokens):
        css = _generate_css(basic_tokens)
        assert "--font-body: Inter;" in css
        assert "--font-size-body: 14px;" in css
        assert "--font-weight-body: 400;" in css
        assert "--font-heading: Inter;" in css
        assert "--font-size-heading: 24px;" in css
        assert "--font-weight-heading: 700;" in css

    def test_empty(self, empty_tokens):
        css = _generate_css(empty_tokens)
        assert css == ":root {\n}"

    def test_both_typography_entries(self, basic_tokens):
        """CSS emits one line per typography token."""
        css = _generate_css(basic_tokens)
        assert "--font-body: Inter;" in css
        assert "--font-heading: Inter;" in css

    def test_font_size_auto_px(self):
        tokens = TokenCollection(
            typography=[TypographyToken(name="font-body", font_family="Arial", font_size="16")],
        )
        css = _generate_css(tokens)
        assert "--font-size-body: 16px;" in css


# ---------------------------------------------------------------------------
# SCSS generator
# ---------------------------------------------------------------------------


class TestGenerateSCSS:
    def test_basic(self, basic_tokens):
        scss = _generate_scss(basic_tokens)
        assert scss.startswith("// SCSS variables")
        assert "$color-primary: #3B82F6;" in scss
        assert "$color-secondary: #10B981;" in scss
        assert "$spacing-md: 16px;" in scss
        assert "$radius-sm: 4px;" in scss
        assert "$shadow-sm: 0 1px 2px rgba(0,0,0,0.1);" in scss

    def test_typography(self, basic_tokens):
        scss = _generate_scss(basic_tokens)
        assert "$font-body: Inter;" in scss
        assert "$font-size-body: 14px;" in scss
        assert "$font-weight-body: 400;" in scss

    def test_empty(self, empty_tokens):
        assert _generate_scss(empty_tokens) == "// SCSS variables: design tokens"

    def test_font_size_auto_px(self):
        tokens = TokenCollection(
            typography=[TypographyToken(name="font-body", font_family="Arial", font_size="16")],
        )
        scss = _generate_scss(tokens)
        assert "$font-size-body: 16px;" in scss


# ---------------------------------------------------------------------------
# Tailwind generator
# ---------------------------------------------------------------------------


class TestGenerateTailwind:
    def test_basic(self, basic_tokens):
        tw = _generate_tailwind(basic_tokens)
        assert '@import "tailwindcss";' in tw
        assert "@theme {" in tw
        assert "}" in tw

    def test_color_prefix_stripping(self):
        """Strip 'color-' prefix to avoid double-prefixing with --color-."""
        tokens = TokenCollection(
            colors=[ColorToken(name="color-primary", value="#3B82F6")],
        )
        tw = _generate_tailwind(tokens)
        assert "--color-primary: #3B82F6;" in tw
        assert "--color-color-primary" not in tw

    def test_color_no_prefix(self):
        tokens = TokenCollection(
            colors=[ColorToken(name="primary", value="#FF0000")],
        )
        tw = _generate_tailwind(tokens)
        assert "--color-primary: #FF0000;" in tw

    def test_spacing_prefix_stripping(self):
        tokens = TokenCollection(
            spacing=[SpacingToken(name="spacing-md", value="16px")],
        )
        tw = _generate_tailwind(tokens)
        assert "--spacing-md: 16px;" in tw

    def test_radius_prefix_stripping(self):
        tokens = TokenCollection(
            radius=[RadiusToken(name="radius-sm", value="4px")],
        )
        tw = _generate_tailwind(tokens)
        assert "--radius-sm: 4px;" in tw

    def test_shadow_prefix_stripping_singular(self):
        tokens = TokenCollection(
            shadows=[ShadowToken(name="shadow-sm", value="0 1px 2px #000")],
        )
        tw = _generate_tailwind(tokens)
        assert "--shadow-sm: 0 1px 2px #000;" in tw

    def test_shadow_prefix_stripping_plural(self):
        tokens = TokenCollection(
            shadows=[ShadowToken(name="shadows-sm", value="0 1px 2px #000")],
        )
        tw = _generate_tailwind(tokens)
        assert "--shadow-sm: 0 1px 2px #000;" in tw

    def test_empty(self, empty_tokens):
        assert _generate_tailwind(empty_tokens) == '@import "tailwindcss";\n\n/* Design tokens extracted from Figma Variables */\n\n@theme {\n\n}'

    def test_typography(self, basic_tokens):
        tw = _generate_tailwind(basic_tokens)
        assert '--font-family-0: "Inter", sans-serif;' in tw
        assert "--font-size-body: 14px;" in tw
        assert "--font-weight-body: 400;" in tw

    def test_typography_dedup_families(self, basic_tokens):
        tw = _generate_tailwind(basic_tokens)
        count = tw.count("--font-family-")
        assert count == 1

    def test_font_size_auto_px(self):
        tokens = TokenCollection(
            typography=[TypographyToken(name="font-body", font_family="Arial", font_size="16")],
        )
        tw = _generate_tailwind(tokens)
        assert "--font-size-body: 16px;" in tw


# ---------------------------------------------------------------------------
# Styled-components generator
# ---------------------------------------------------------------------------


class TestGenerateStyled:
    def test_basic(self, basic_tokens):
        js = _generate_styled(basic_tokens)
        assert js.startswith("export const tokens = ")
        assert '"colors"' in js

    def test_structure(self, basic_tokens):
        data = _parse_styled_js(_generate_styled(basic_tokens))
        assert "colors" in data
        assert "spacing" in data
        assert "radius" in data
        assert "shadows" in data
        assert "typography" in data
        assert data["colors"]["color-primary"] == "#3B82F6"

    def test_typography_shape(self, basic_tokens):
        data = _parse_styled_js(_generate_styled(basic_tokens))
        body = data["typography"]["font-body"]
        assert body["fontFamily"] == "Inter"
        assert body["fontSize"] == "14px"
        assert body["fontWeight"] == 400

    def test_empty(self, empty_tokens):
        data = _parse_styled_js(_generate_styled(empty_tokens))
        assert data["colors"] == {}


# ---------------------------------------------------------------------------
# generate_token_file()
# ---------------------------------------------------------------------------


class TestGenerateTokenFile:
    def test_empty_tokens_returns_empty(self, empty_tokens):
        assert generate_token_file(empty_tokens, "css") == ""

    def test_css_style(self, basic_tokens):
        result = generate_token_file(basic_tokens, "css")
        assert result.startswith(":root {")

    def test_tailwind_style(self, basic_tokens):
        result = generate_token_file(basic_tokens, "tailwind")
        assert '@import "tailwindcss";' in result

    def test_scss_style(self, basic_tokens):
        result = generate_token_file(basic_tokens, "scss")
        assert result.startswith("// SCSS variables")

    def test_styled_style(self, basic_tokens):
        result = generate_token_file(basic_tokens, "styled")
        assert "export const tokens" in result

    def test_css_modules_aliases_to_css(self, basic_tokens):
        result = generate_token_file(basic_tokens, "css_modules")
        assert result.startswith(":root {")

    def test_unknown_style_falls_back_to_css(self, basic_tokens):
        result = generate_token_file(basic_tokens, "unknown")
        assert result.startswith(":root {")

    def test_none_style_defaults_to_css(self, basic_tokens):
        result = generate_token_file(basic_tokens, None)
        assert result.startswith(":root {")

    def test_case_insensitive(self, basic_tokens):
        result = generate_token_file(basic_tokens, "TAILWIND")
        assert '@import "tailwindcss";' in result


# ---------------------------------------------------------------------------
# token_file_path()
# ---------------------------------------------------------------------------


class TestTokenFilePath:
    def test_html_framework(self):
        assert token_file_path("html", "css") == "css/tokens.css"

    def test_html_css_js_framework(self):
        assert token_file_path("html_css_js", "css") == "css/tokens.css"

    def test_scss_style(self):
        assert token_file_path("react", "scss") == "src/styles/_tokens.scss"

    def test_tailwind_style(self):
        assert token_file_path("react", "tailwind") == "src/index.css"

    def test_default_css(self):
        assert token_file_path("react", "css") == "src/tokens.css"

    def test_default_without_style(self):
        assert token_file_path("react", None) == "src/tokens.css"

    def test_unknown_framework_defaults(self):
        assert token_file_path("flutter", "css") == "src/tokens.css"


# ---------------------------------------------------------------------------
# tokens_to_dict()
# ---------------------------------------------------------------------------


class TestTokensToDict:
    def test_empty(self, empty_tokens):
        d = tokens_to_dict(empty_tokens)
        assert d["colors"] == []
        assert d["token_count"] == 0
        assert d["source"] == ""

    def test_populated(self, basic_tokens):
        d = tokens_to_dict(basic_tokens)
        assert len(d["colors"]) == 2
        assert len(d["spacing"]) == 2
        assert len(d["radius"]) == 2
        assert len(d["shadows"]) == 1
        assert len(d["typography"]) == 2
        assert d["source"] == ""

    def test_color_fields(self, basic_tokens):
        d = tokens_to_dict(basic_tokens)
        primary = next(c for c in d["colors"] if c["name"] == "color-primary")
        assert primary["value"] == "#3B82F6"
