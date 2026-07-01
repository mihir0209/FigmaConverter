"""Tests for the dependency reconciliation helper.

This avoids actually calling an AI; we stub `chat_completion` on a real
`AI_engine` instance by monkey-patching it before invoking the orchestrator.
"""

import pytest

from parsers.ai_response_parser import AIResponseParser
from prompting.orchestrators import (
    generate_enhanced_frame_code_with_ai,
    generate_enhanced_main_app_with_ai,
    reconcile_dependencies_with_ai,
)


class _StubResult:
    """Minimal RequestResult-compatible object."""

    def __init__(self, *, success: bool, content: str = "", error_message: str = ""):
        self.success = success
        self.content = content
        self.error_message = error_message
        self.response_time = 0.0


class _StubEngine:
    """Implements just the `chat_completion` method the orchestrators call."""

    def __init__(self, scripted):
        # `scripted` is a list of (request, response) pairs in order
        self.scripted = list(scripted)
        self.calls = 0

    def chat_completion(self, messages, **kwargs):
        if self.calls < len(self.scripted):
            plan = self.scripted[self.calls]
            self.calls += 1
            return plan
        return _StubResult(success=False, error_message="scripted exhausted")


SAMPLE_FRAME = {
    "id": "0:1",
    "name": "Landing",
    "comprehensive_data": {
        "basic_info": {"dimensions": {"width": 1280, "height": 720}},
        "component_count": {"total": 5, "texts": 2, "images": 1, "buttons": 1, "inputs": 0, "containers": 1, "icons": 0},
        "content": {"texts": [], "images": [], "containers": [], "interactive_elements": []},
        "design_system": {"colors": ["#ffffff", "#000000"], "typography": {}},
        "layout": {"background_color": "#ffffff", "layout_type": "vertical-flow"},
        "structure": {"layout_type": "vertical-flow"},
    },
}

SAMPLE_FRAMEWORK_STRUCTURE = {
    "framework": "react",
    "structure": {"component_extension": ".jsx",
                  "main_file": "src/App.jsx",
                  "config_files": ["package.json"],
                  "folder_structure": {"src": ["components"]}},
    "file_conventions": {"component_extension": ".jsx"},
    "technology_stack": {"core_libraries": ["react"]},
    "build_tool": "vite",
}

SAMPLE_ARCHITECTURE = {
    "app_architecture": {"app_type": "Landing", "primary_flow": "view", "navigation_pattern": "none"},
    "frame_connections": [],
    "shared_components": [],
    "route_structure": {"/": "Landing"},
    "app_state": {"global_state": [], "shared_data": []},
}


class TestFrameOrchestrator:
    def test_generates_file_on_clean_response(self):
        engine = _StubEngine([
            '{"component_name": "Fr", "content": "ok", "file_path": "src/Fr.jsx", "dependencies": {"required": ["react"]}}'
            # then an empty string for the second attempt? no — see below
        ])
        # Make every call return the same valid JSON for the three retries
        engine.scripted = [
            _StubResult(success=True, content='{"component_name":"Fr","content":"ok","file_path":"src/Fr.jsx","dependencies":{"required":["react"]}}'),
        ]
        result = generate_enhanced_frame_code_with_ai(
            engine,
            SAMPLE_FRAME,
            "react",
            "job-1",
            AIResponseParser(),
            SAMPLE_FRAMEWORK_STRUCTURE,
            SAMPLE_ARCHITECTURE,
            "summary",
            {"dependencies": {"package.json": {"dependencies": {}, "devDependencies": {}}}},
        )
        assert "src/Fr.jsx" in result["files"]
        assert result["dependency_suggestions"]["required"] == ["react"]
        assert result["frame_name"] == "Landing"

    def test_retries_then_gives_up(self):
        engine = _StubEngine(
            [
                _StubResult(success=False, error_message="provider down"),
                _StubResult(success=False, error_message="provider still down"),
                _StubResult(success=False, error_message="provider still down"),
            ]
        )
        result = generate_enhanced_frame_code_with_ai(
            engine,
            SAMPLE_FRAME,
            "react",
            "job-1",
            AIResponseParser(),
            SAMPLE_FRAMEWORK_STRUCTURE,
            SAMPLE_ARCHITECTURE,
            "summary",
            None,
        )
        assert result == {}
        assert engine.calls == 3

    def test_recovers_from_first_attempt_parse_failure(self):
        engine = _StubEngine(
            [
                _StubResult(success=True, content="not json {} ]]"),
                _StubResult(success=True, content='{"component_name":"X","content":"y","file_path":"src/X.js"}'),
            ]
        )
        result = generate_enhanced_frame_code_with_ai(
            engine,
            {"id": "0:1", "name": "Page"},
            "react",
            "job-1",
            AIResponseParser(),
            SAMPLE_FRAMEWORK_STRUCTURE,
            SAMPLE_ARCHITECTURE,
            "summary",
            None,
        )
        assert "src/X.js" in result["files"]
        assert engine.calls == 2


class TestMainAppOrchestrator:
    def test_returns_files_on_valid_response(self):
        engine = _StubEngine(
            [
                _StubResult(
                    success=True,
                    content='{"main_app": {"file_path": "src/App.jsx", "content": "ok"}, "entry_point": {"file_path": "src/index.jsx", "content": "ep"}}',
                )
            ]
        )
        result = generate_enhanced_main_app_with_ai(
            engine,
            [SAMPLE_FRAME],
            "react",
            "job-1",
            AIResponseParser(),
            SAMPLE_FRAMEWORK_STRUCTURE,
            SAMPLE_ARCHITECTURE,
        )
        assert result["src/App.jsx"] == "ok"
        assert result["src/index.jsx"] == "ep"

    def test_retries_when_first_response_unparsable(self):
        engine = _StubEngine(
            [
                _StubResult(success=True, content="not valid json at all"),
                _StubResult(
                    success=True,
                    content='{"main_app": {"file_path": "src/App.jsx", "content": "ok"}}',
                ),
            ]
        )
        result = generate_enhanced_main_app_with_ai(
            engine,
            [SAMPLE_FRAME],
            "react",
            "job-1",
            AIResponseParser(),
            SAMPLE_FRAMEWORK_STRUCTURE,
            SAMPLE_ARCHITECTURE,
        )
        assert result["src/App.jsx"] == "ok"
        assert engine.calls == 2

    def test_returns_empty_when_all_attempts_fail(self):
        engine = _StubEngine([_StubResult(success=False, error_message="bad")] * 3)
        result = generate_enhanced_main_app_with_ai(
            engine,
            [SAMPLE_FRAME],
            "react",
            "job-1",
            AIResponseParser(),
            SAMPLE_FRAMEWORK_STRUCTURE,
            SAMPLE_ARCHITECTURE,
        )
        assert result == {}
