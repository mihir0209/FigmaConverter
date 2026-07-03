"""Tests for the MCP server tools (Plan 001).

Uses mocked ``process_frame_by_frame`` and AI orchestrators to keep tests
fast and deterministic.
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

import mcp_server

# Set a dummy token so EnhancedFigmaProcessor constructor works
os.environ.setdefault("FIGMA_API_TOKEN", "test_token_123")

_FAKE_FRAMES = [
    {
        "id": "frame1",
        "name": "Header",
        "page_name": "Page 1",
        "dimensions": {"width": 1440, "height": 80},
        "component_count": 5,
        "comprehensive_data": {
            "structure": {"layout_type": "horizontal-flow"},
            "component_count": {"total": 5, "texts": 2, "images": 0},
        },
    },
    {
        "id": "frame2",
        "name": "Card",
        "page_name": "Page 1",
        "dimensions": {"width": 375, "height": 500},
        "component_count": 3,
        "comprehensive_data": {
            "structure": {"layout_type": "vertical-flow"},
            "component_count": {"total": 3, "texts": 1, "images": 1},
        },
    },
]

_FAKE_DESIGN_DATA = {
    "design_info": {
        "file_key": "abc123",
        "file_name": "Test Design",
        "total_frames": 2,
        "total_components": 8,
    },
    "frames": _FAKE_FRAMES,
    "component_references": {"comp1": {}, "comp2": {}},
    "design_tokens": None,
}


@pytest.fixture(autouse=True)
def _mock_pipeline():
    """Mock AI orchestration and processor internals."""
    patcher_proc = patch.object(
        mcp_server.EnhancedFigmaProcessor,
        "process_frame_by_frame",
        return_value=_FAKE_DESIGN_DATA,
    )
    patcher_proc.start()
    patcher_detector = patch.object(
        mcp_server,
        "AIFrameworkDetector",
    )
    mock_detector_cls = patcher_detector.start()
    mock_detector_cls.return_value.detect_framework.return_value = {
        "success": True,
        "framework": "react",
        "framework_name": "React",
        "confidence": 0.95,
        "project_structure": {
            "main_file": "src/App.jsx",
            "root_folders": ["src", "public"],
            "component_location": "src/components",
        },
        "file_conventions": {
            "component_extension": ".jsx",
            "style_extension": ".css",
            "naming_convention": "PascalCase",
        },
        "technology_stack": {},
    }
    patcher_engine = patch.object(
        mcp_server._MCPEngineSingleton,
        "get",
        return_value=MagicMock(),
    )
    patcher_engine.start()
    patcher_arch = patch(
        "mcp_server.generate_app_architecture_with_ai",
        return_value={
            "app_architecture": {"app_type": "Application"},
            "frame_connections": [],
            "shared_components": [],
            "route_structure": {},
            "app_state": {},
        },
    )
    patcher_gen = patch(
        "mcp_server.generate_enhanced_frame_code_with_ai",
        return_value={
            "files": {
                "src/components/Header.jsx": (
                    "export default function Header() { return <header>Hi</header>; }"
                ),
            },
            "frame_name": "Header",
            "dependency_suggestions": [],
        },
    )
    patcher_main = patch(
        "mcp_server.generate_main_app_with_ai",
        return_value={
            "files": {
                "src/App.jsx": "export default function App() { return <div />; }",
            },
        },
    )
    patcher_recon = patch(
        "mcp_server.reconcile_dependencies_with_ai",
        return_value={},
    )

    patcher_arch.start()
    patcher_gen.start()
    patcher_main.start()
    patcher_recon.start()
    yield
    patcher_recon.stop()
    patcher_main.stop()
    patcher_gen.stop()
    patcher_arch.stop()
    patcher_engine.stop()
    patcher_detector.stop()
    patcher_proc.stop()
    patcher_proc.stop()


# ---------------------------------------------------------------------------
# get_design_context
# ---------------------------------------------------------------------------


class TestGetDesignContext:
    def test_returns_json(self):
        raw = mcp_server.get_design_context(figma_url="https://www.figma.com/file/abc/Test")
        data = json.loads(raw)
        assert data["file_key"] == "abc123"
        assert data["total_frames"] == 2
        assert len(data["frames"]) == 2

    def test_includes_frame_details(self):
        raw = mcp_server.get_design_context("https://www.figma.com/file/abc/Test")
        data = json.loads(raw)
        assert data["frames"][0]["name"] == "Header"
        assert data["frames"][0]["layout_type"] == "horizontal-flow"

    def test_reports_tokens_availability(self):
        raw = mcp_server.get_design_context("https://www.figma.com/file/abc/Test")
        data = json.loads(raw)
        assert data["has_design_tokens"] is False

    def test_component_references_listed(self):
        raw = mcp_server.get_design_context("https://www.figma.com/file/abc/Test")
        data = json.loads(raw)
        assert "comp1" in data["component_references"]


# ---------------------------------------------------------------------------
# generate_code
# ---------------------------------------------------------------------------


class TestGenerateCode:
    def test_returns_json_structure(self):
        raw = mcp_server.generate_code(
            figma_url="https://www.figma.com/file/abc/Test",
            target_framework="react",
        )
        data = json.loads(raw)
        assert data["framework"] == "react"
        assert "files" in data
        assert "file_contents" in data

    def test_includes_generated_files(self):
        raw = mcp_server.generate_code(
            figma_url="https://www.figma.com/file/abc/Test",
            target_framework="react",
        )
        data = json.loads(raw)
        assert "src/components/Header.jsx" in data["files"]

    def test_file_contents_present(self):
        raw = mcp_server.generate_code(
            figma_url="https://www.figma.com/file/abc/Test",
            target_framework="react",
        )
        data = json.loads(raw)
        assert "Header" in data["file_contents"]["src/components/Header.jsx"]

    def test_handles_unknown_framework(self):
        with patch("mcp_server.AIFrameworkDetector") as mock_d:
            det = MagicMock()
            det.detect_framework.return_value = {"success": False}
            mock_d.return_value = det
            raw = mcp_server.generate_code(
                figma_url="https://www.figma.com/file/abc/Test",
                target_framework="unknown_framework",
            )
            data = json.loads(raw)
            assert "error" in data


# ---------------------------------------------------------------------------
# get_design_tokens
# ---------------------------------------------------------------------------


class TestGetDesignTokens:
    def test_returns_token_structure(self):
        raw = mcp_server.get_design_tokens(
            figma_url="https://www.figma.com/file/abc/Test",
        )
        data = json.loads(raw)
        assert "source" in data
        assert "token_count" in data
        assert "tokens" in data

    def test_empty_tokens_when_none_available(self):
        raw = mcp_server.get_design_tokens(
            figma_url="https://www.figma.com/file/abc/Test",
        )
        data = json.loads(raw)
        assert data["token_count"] == 0


# ---------------------------------------------------------------------------
# get_framework_options
# ---------------------------------------------------------------------------


class TestGetFrameworkOptions:
    def test_returns_all_sections(self):
        raw = mcp_server.get_framework_options()
        data = json.loads(raw)
        assert "frameworks" in data
        assert "style_engines" in data
        assert "component_libraries" in data
        assert "valid_combinations" in data
        assert "default_dependencies" in data

    def test_frameworks_listed(self):
        raw = mcp_server.get_framework_options()
        data = json.loads(raw)
        assert "react" in data["frameworks"]
        assert "vue" in data["frameworks"]

    def test_style_engines(self):
        raw = mcp_server.get_framework_options()
        data = json.loads(raw)
        assert "tailwind" in data["style_engines"]

    def test_dependencies_per_framework(self):
        raw = mcp_server.get_framework_options()
        data = json.loads(raw)
        assert "react" in data["default_dependencies"]
        assert "react" in data["default_dependencies"]["react"]
        # The real get_default_dependencies returns 3 deps (react, react-dom, react-router-dom)


# ---------------------------------------------------------------------------
# validate_design
# ---------------------------------------------------------------------------


class TestValidateDesign:
    def test_returns_readiness_score(self):
        raw = mcp_server.validate_design(
            figma_url="https://www.figma.com/file/abc/Test",
        )
        data = json.loads(raw)
        assert "readiness_score" in data
        assert data["readiness_score"] >= 0

    def test_auto_layout_coverage(self):
        raw = mcp_server.validate_design(
            figma_url="https://www.figma.com/file/abc/Test",
        )
        data = json.loads(raw)
        # Both frames have horizontal-flow or vertical-flow layout
        assert data["auto_layout_coverage"] == 100.0

    def test_named_frames_ratio(self):
        raw = mcp_server.validate_design(
            figma_url="https://www.figma.com/file/abc/Test",
        )
        data = json.loads(raw)
        assert data["named_frames_ratio"] == 100.0

    def test_has_tokens_flag(self):
        raw = mcp_server.validate_design(
            figma_url="https://www.figma.com/file/abc/Test",
        )
        data = json.loads(raw)
        assert data["has_design_tokens"] is False

    def test_recommendations_when_no_tokens(self):
        raw = mcp_server.validate_design(
            figma_url="https://www.figma.com/file/abc/Test",
        )
        data = json.loads(raw)
        assert any("Figma Variables" in r for r in data["recommendations"])


# ---------------------------------------------------------------------------
# Module-level constants / entrypoint
# ---------------------------------------------------------------------------


class TestServerConfig:
    def test_max_frames_constant(self):
        assert mcp_server.MAX_FRAMES_PER_JOB == 50

    def test_server_has_expected_tools(self):
        """Ensure the FastMCP instance registered all tools."""
        tool_names = [t.name for t in mcp_server.server._tool_manager.list_tools()]
        assert "get_design_context" in tool_names
        assert "generate_code" in tool_names
        assert "get_design_tokens" in tool_names
        assert "get_framework_options" in tool_names
        assert "validate_design" in tool_names
