"""Tests for the style_builders package (Tailwind CSS v4 support)."""

import json

import pytest

from prompting.framework_utils import (
    get_style_engine_instructions,
    get_style_file_path,
)
from prompting.style_builders import build_styles, get_style_instructions
from prompting.style_builders.tailwind_v4 import (
    _to_slug,
    build_tailwind_theme_block,
    get_tailwind_instructions,
)


class TestTailwindInstructions:
    def test_contains_v4_reference(self):
        assert "tailwindcss v4" in get_tailwind_instructions()

    def test_mentions_import_syntax(self):
        assert "@import" in get_tailwind_instructions()

    def test_discourages_raw_css(self):
        assert "NEVER write raw CSS" in get_tailwind_instructions()

    def test_utility_class_examples(self):
        text = get_tailwind_instructions()
        for token in ("text-sm", "p-4", "bg-blue-500", "hover:"):
            assert token in text, f"Expected {token!r} in instructions"


class TestBuildTailwindThemeBlock:
    def test_default_empty(self):
        css = build_tailwind_theme_block(None)
        assert '@import "tailwindcss";' in css
        assert "@theme" not in css

    def test_empty_dict(self):
        css = build_tailwind_theme_block({})
        assert '@import "tailwindcss";' in css

    def test_colors_list_of_dicts(self):
        css = build_tailwind_theme_block({
            "colors": [
                {"name": "Primary", "value": "#3b82f6"},
                {"name": "secondary", "value": "#10b981"},
            ],
        })
        assert "--color-primary: #3b82f6;" in css
        assert "--color-secondary: #10b981;" in css

    def test_colors_list_of_strings(self):
        css = build_tailwind_theme_block({
            "colors": ["#ff0000", "#00ff00"],
        })
        assert "--color" in css

    def test_colors_dict(self):
        css = build_tailwind_theme_block({
            "colors": {"brand": "#ff5500", "accent": "#5500ff"},
        })
        assert "--color-brand: #ff5500;" in css
        assert "--color-accent: #5500ff;" in css

    def test_typography(self):
        css = build_tailwind_theme_block({
            "typography": {
                "heading1": {"font_family": "Inter"},
                "body": {"font_family": "Inter"},
                "code": {"font_family": "JetBrains Mono"},
            },
        })
        assert '--font-family-0: "Inter", sans-serif;' in css
        assert '--font-family-1: "JetBrains Mono", sans-serif;' in css

    def test_typography_with_camelCase_keys(self):
        css = build_tailwind_theme_block({
            "typography": {
                "heading": {"fontFamily": "Roboto"},
            },
        })
        assert '--font-family-0: "Roboto", sans-serif;' in css

    def test_spacing(self):
        css = build_tailwind_theme_block({
            "spacing": {"base": "16px", "lg": "32px"},
        })
        assert "--spacing-base: 16px;" in css
        assert "--spacing-lg: 32px;" in css

    def test_full_integration(self):
        ds = {
            "colors": [{"name": "primary", "value": "#1e40af"}],
            "typography": {"heading": {"font_family": "Inter"}},
            "spacing": {"page": "24px"},
        }
        css = build_tailwind_theme_block(ds)
        assert '@import "tailwindcss";' in css
        assert "--color-primary: #1e40af;" in css
        assert 'font-family-0' in css
        assert "--spacing-page: 24px;" in css


class TestToSlug:
    def test_lowercases(self):
        assert _to_slug("HelloWorld") == "helloworld"

    def test_replaces_spaces(self):
        assert _to_slug("light blue") == "light-blue"

    def test_replaces_underscores(self):
        assert _to_slug("dark_mode") == "dark-mode"

    def test_replaces_slashes(self):
        assert _to_slug("red/500") == "red-500"


class TestStyleBuildersIntegration:
    def test_build_styles_tailwind(self):
        css = build_styles("tailwind", None)
        assert '@import "tailwindcss"' in css

    def test_build_styles_css(self):
        css = build_styles("css", None)
        assert "No style engine configured" in css

    def test_build_styles_none(self):
        css = build_styles(None, None)
        assert "No style engine configured" in css

    def test_get_style_instructions_tailwind(self):
        text = get_style_instructions("tailwind")
        assert "tailwindcss v4" in text

    def test_get_style_instructions_css(self):
        assert get_style_instructions("css") == ""

    def test_get_style_instructions_none(self):
        assert get_style_instructions(None) == ""


class TestFrameworkUtilsStyleEngine:
    def test_get_style_engine_instructions_tailwind(self):
        text = get_style_engine_instructions("tailwind")
        assert "RULES" in text
        assert "tailwindcss v4" in text

    def test_get_style_engine_instructions_css(self):
        assert get_style_engine_instructions("css") == ""

    def test_get_style_engine_instructions_none(self):
        assert get_style_engine_instructions(None) == ""

    def test_style_file_path_react_tailwind(self):
        assert get_style_file_path("react", "tailwind") == "src/index.css"

    def test_style_file_path_react_css(self):
        assert get_style_file_path("react", "css") == "src/index.css"

    def test_style_file_path_react_none(self):
        assert get_style_file_path("react", None) == "src/index.css"

    def test_style_file_path_vue_tailwind(self):
        assert get_style_file_path("vue", "tailwind") == "src/assets/styles/main.css"
