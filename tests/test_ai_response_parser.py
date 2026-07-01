"""Tests for the AI response parser.

We don't stub out the AI engine here — just verify the parser's repair and
validation paths. The parser is the single safety net the rest of the pipeline
relies on, so it's worth covering thoroughly.
"""

import json

import pytest
from hypothesis import given, strategies as st

from parsers.ai_response_parser import (
    AIResponseParser,
    _coerce_dependencies,
    _strip_smart_quotes,
)


class TestCoerceDependencies:
    def test_list_form_becomes_required(self):
        result = _coerce_dependencies(["react", "react-dom"])
        assert result == {
            "required": ["react", "react-dom"],
            "additional_suggestions": [],
            "reasoning": "",
        }

    def test_dict_form_is_preserved_and_padded(self):
        result = _coerce_dependencies(
            {"required": ["react"], "custom_field": "value"}
        )
        assert result["required"] == ["react"]
        assert result["additional_suggestions"] == []
        assert result["custom_field"] == "value"
        assert result["reasoning"] == ""

    def test_none_becomes_empty_envelope(self):
        assert _coerce_dependencies(None) == {
            "required": [],
            "additional_suggestions": [],
            "reasoning": "",
        }

    def test_scalar_becomes_string_list(self):
        result = _coerce_dependencies("react")
        assert result["required"] == ["react"]


class TestSmartQuoteStripping:
    def test_strips_left_right_smart_quotes(self):
        assert _strip_smart_quotes("‘react’") == "'react'"
        assert _strip_smart_quotes("“react”") == '"react"'

    def test_replaces_em_dashes(self):
        assert _strip_smart_quotes("foo—bar") == "foo-bar"


class TestLoadJsonWithRepairs:
    def test_handles_markdown_fenced_json(self, sample_response_success):
        body = "```json\n" + json.dumps(sample_response_success) + "\n```"
        parsed = AIResponseParser().parse_component_generation_response(body)
        assert parsed["component_name"] == "Frame"

    def test_handles_smuggled_markdown_block(self, sample_response_success):
        body = (
            "Sure, here is the JSON you asked for:\n\n"
            "```json\n"
            + json.dumps(sample_response_success)
            + "\n```\n\nLet me know if you need anything else."
        )
        parsed = AIResponseParser().parse_component_generation_response(body)
        assert parsed["file_path"] == "src/components/Frame.jsx"

    def test_handles_smart_quotes(self, sample_response_success):
        body = "```json\n" + json.dumps(sample_response_success) + "```"
        body = body.replace("react", "rea‌ct")  # no-op for our impl
        # Inject smart quotes around the JSON
        body = "“" + json.dumps(sample_response_success) + "”"
        parsed = AIResponseParser().parse_component_generation_response(body)
        assert parsed["component_name"] == "Frame"

    def test_rejects_missing_required_field(self, sample_response_success):
        bad = dict(sample_response_success)
        del bad["file_path"]
        with pytest.raises(ValueError, match="Missing required field: file_path"):
            AIResponseParser().parse_component_generation_response(json.dumps(bad))

    def test_normalises_dependency_shape(self, sample_response_success):
        # The docstring has the legacy list shape, downstream reads dict.
        bad = dict(sample_response_success)
        bad["dependencies"] = ["react", "react-dom"]
        parsed = AIResponseParser().parse_component_generation_response(json.dumps(bad))
        assert isinstance(parsed["dependencies"], dict)
        assert parsed["dependencies"]["required"] == ["react", "react-dom"]


class TestFilePathValidation:
    @pytest.mark.parametrize(
        "path",
        [
            "src/components/Frame.jsx",
            "lib/main.dart",
            "src/App.vue",
            "index.html",
            "deeply/nested/path/with/dots/config.yaml",
        ],
    )
    def test_accepts_clean_paths(self, path):
        assert AIResponseParser()._is_valid_file_path(path)

    @pytest.mark.parametrize(
        "path",
        [
            "src/../etc/passwd",
            "../etc/passwd",
            "/etc/passwd",
            "src/components/../App.jsx",
            "C:/Windows/System32/file.jsx",
        ],
    )
    def test_rejects_traversal_or_absolute(self, path):
        assert not AIResponseParser()._is_valid_file_path(path)

    def test_accepts_double_dot_within_filename(self):
        # Versions like `1.0..react.jsx` should not be flagged.
        assert AIResponseParser()._is_valid_file_path("lib/1.0..react.jsx")

    def test_rejects_unknown_extension(self):
        assert not AIResponseParser()._is_valid_file_path("components/foo.exe")


# ---------------------------------------------------------------------------
# Property-based tests (hypothesis) — edge cases the hand-written tests miss
# ---------------------------------------------------------------------------


@given(st.text(min_size=0, max_size=200))
def test_strip_smart_quotes_never_raises(arb_text: str):
    """_strip_smart_quotes should never crash, regardless of input."""
    result = _strip_smart_quotes(arb_text)
    assert isinstance(result, str)


@given(st.dictionaries(
    keys=st.text(min_size=1, max_size=20),
    values=st.one_of(st.none(), st.booleans(), st.integers(), st.text()),
    min_size=0, max_size=10,
))
def test_coerce_dependencies_dict_never_crashes(arb_dict):
    """_coerce_dependencies should handle any dict shape."""
    result = _coerce_dependencies(arb_dict)
    assert isinstance(result, dict)
    assert "required" in result
    assert "additional_suggestions" in result
    assert "reasoning" in result


@given(st.lists(st.text(min_size=1, max_size=30), min_size=0, max_size=10))
def test_coerce_dependencies_list_never_crashes(arb_list):
    """_coerce_dependencies should handle any list."""
    result = _coerce_dependencies(arb_list)
    assert isinstance(result, dict)
    assert "required" in result


@given(st.text(min_size=1, max_size=100))
def test_is_valid_file_path_never_crashes(arb_path: str):
    """_is_valid_file_path should never crash, regardless of input."""
    AIResponseParser()._is_valid_file_path(arb_path)  # just must not raise


@given(st.text(min_size=1, max_size=500))
def test_load_json_with_repairs_never_crashes(arb_text: str):
    """_load_json_with_repairs should never crash from unexpected exceptions.
    ValueError is expected when the text has no JSON content.
    """
    parser = AIResponseParser()
    try:
        result = parser._load_json_with_repairs(arb_text)
        assert isinstance(result, (dict, list, type(None), int, float, bool))
    except ValueError:
        pass  # expected when no JSON is found
