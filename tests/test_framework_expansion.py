"""Tests for framework expansion: component library integration, theming, and dependency injection."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from models import TokenCollection, ColorToken
from processors.component_library_mapper import (
    get_library_dependencies,
    get_library_info,
    map_component,
)
from prompting.prompt_builder import _build_library_component_mapping


class TestBuildLibraryComponentMapping:
    """Test the mapping of Figma elements to library components."""

    def test_empty_library_returns_empty(self):
        result = _build_library_component_mapping("", {})
        assert result == ""

    def test_no_elements_returns_empty(self):
        result = _build_library_component_mapping("shadcn", {})
        assert result == ""

    def test_maps_interactive_elements(self):
        frame = {
            "comprehensive_data": {
                "content": {
                    "interactive_elements": [
                        {"type": "button", "text": "Submit"},
                        {"type": "input", "name": "Email Input"},
                    ],
                    "containers": [],
                }
            }
        }
        result = _build_library_component_mapping("shadcn", frame)
        assert "Submit" in result
        assert "Button" in result
        assert "@/components/ui/button" in result
        assert "Email Input" in result
        assert "Input" in result

    def test_maps_containers(self):
        frame = {
            "comprehensive_data": {
                "content": {
                    "interactive_elements": [],
                    "containers": [
                        {"type": "card", "name": "Product Card", "layout_role": "component"},
                    ],
                }
            }
        }
        result = _build_library_component_mapping("shadcn", frame)
        assert "Product Card" in result
        assert "Card" in result

    def test_deduplicates_elements(self):
        frame = {
            "comprehensive_data": {
                "content": {
                    "interactive_elements": [
                        {"type": "button", "text": "Submit"},
                        {"type": "button", "text": "Submit"},
                    ],
                    "containers": [],
                }
            }
        }
        result = _build_library_component_mapping("shadcn", frame)
        assert result.count("Submit") == 1

    def test_mui_mapping(self):
        frame = {
            "comprehensive_data": {
                "content": {
                    "interactive_elements": [
                        {"type": "button", "text": "Click Me"},
                    ],
                    "containers": [],
                }
            }
        }
        result = _build_library_component_mapping("mui", frame)
        assert "Click Me" in result
        assert "Button" in result
        assert "@mui/material/Button" in result

    def test_antd_mapping(self):
        frame = {
            "comprehensive_data": {
                "content": {
                    "interactive_elements": [
                        {"type": "table", "text": "Data Table"},
                    ],
                    "containers": [],
                }
            }
        }
        result = _build_library_component_mapping("antd", frame)
        assert "Data Table" in result
        assert "Table" in result
        assert "antd" in result

    def test_bootstrap_mapping(self):
        frame = {
            "comprehensive_data": {
                "content": {
                    "interactive_elements": [
                        {"type": "button", "text": "Submit"},
                    ],
                    "containers": [],
                }
            }
        }
        result = _build_library_component_mapping("bootstrap", frame)
        assert "Submit" in result
        assert "button" in result


class TestComponentLibraryDependencyInjection:
    """Test that component library deps are properly formatted."""

    @patch("processors.style_library_matrix.DependencyResolver")
    def test_preliminary_deps_includes_library(self, MockResolver):
        from main import _preliminary_dependencies

        mock_resolver = MagicMock()
        mock_resolver.resolve_to_package_json.return_value = {
            "dependencies": {
                "@mui/material": "^5.15.0",
                "@emotion/react": "^11.11.3",
            },
            "devDependencies": {},
        }
        MockResolver.return_value = mock_resolver

        result = _preliminary_dependencies(
            "react",
            {"framework": "react"},
            style_engine="css",
            component_library="mui",
        )
        pkg = result["dependencies"]["package.json"]
        assert "@mui/material" in pkg["dependencies"]
        assert pkg["dependencies"]["@mui/material"] == "^5.15.0"


class TestGetLibraryDependencies:
    """Test library dependency definitions."""

    def test_shadcn_deps(self):
        deps = get_library_dependencies("shadcn")
        assert "class-variance-authority" in deps
        assert "clsx" in deps
        assert "tailwind-merge" in deps
        assert "lucide-react" in deps
        assert "@radix-ui/react-dialog" in deps

    def test_mui_deps(self):
        deps = get_library_dependencies("mui")
        assert "@mui/material" in deps
        assert "@emotion/react" in deps
        assert "@mui/icons-material" in deps

    def test_antd_deps(self):
        deps = get_library_dependencies("antd")
        assert "antd" in deps
        assert "@ant-design/icons" in deps

    def test_bootstrap_deps(self):
        deps = get_library_dependencies("bootstrap")
        assert "bootstrap" in deps

    def test_empty_returns_empty(self):
        assert get_library_dependencies("") == {}
        assert get_library_dependencies(None) == {}

    def test_unknown_returns_empty(self):
        assert get_library_dependencies("nonexistent") == {}


class TestScaffoldProjectDeps:
    """Test that scaffold_project injects library deps into package.json."""

    @patch("processors.template_scaffolder._download_and_extract_github_template")
    @patch("processors.template_scaffolder._apply_manual_scaffold")
    @patch("processors.style_library_matrix.DependencyResolver")
    def test_injects_deps_into_existing_package_json(
        self, MockResolver, mock_manual, mock_download
    ):
        from processors.template_scaffolder import scaffold_project

        mock_download.return_value = True
        mock_resolver = MagicMock()
        mock_resolver.resolve_to_package_json.return_value = {
            "dependencies": {"@mui/material": "^5.15.0", "@emotion/react": "^11.11.3"},
            "devDependencies": {},
        }
        MockResolver.return_value = mock_resolver

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            pkg_path = target / "package.json"
            pkg_path.write_text(
                json.dumps({
                    "name": "test-app",
                    "version": "0.1.0",
                    "dependencies": {"react": "^18.2.0"},
                    "devDependencies": {"vite": "^5.0.0"},
                })
            )

            result = scaffold_project(
                target, "react",
                style_engine="css", component_library="mui",
            )
            assert result is True

            pkg = json.loads(pkg_path.read_text("utf-8"))
            assert "@mui/material" in pkg["dependencies"]
            assert pkg["dependencies"]["@mui/material"] == "^5.15.0"
            assert pkg["dependencies"]["react"] == "^18.2.0"

    def test_no_package_json_does_not_fail(self):
        from processors.template_scaffolder import _inject_extra_deps

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            # No package.json — should not raise
            _inject_extra_deps(target, "react", style_engine="css", component_library="mui")


class TestMapComponentFrameworkExpansion:
    """End-to-end mapping tests for all supported libraries."""

    def test_shadcn_button_keyword(self):
        result = map_component("shadcn", "div", "Submit Button")
        assert result["component"] == "Button"
        assert result["match_type"] == "keyword"

    def test_mui_btn_keyword(self):
        result = map_component("mui", "div", "Submit Button")
        assert result["component"] == "Button"
        assert result["match_type"] == "keyword"

    def test_antd_sidebar_keyword(self):
        result = map_component("antd", "div", "Sidebar Menu")
        assert result["component"] == "Menu"
        assert result["match_type"] == "keyword"

    def test_bootstrap_hero_keyword(self):
        result = map_component("bootstrap", "div", "Hero Section")
        assert result["component"] == "div"
        assert result["match_type"] == "fallback"

    def test_unknown_library(self):
        result = map_component("nonexistent", "button", "Submit")
        assert result["match_type"] == "unknown_library"
        assert result["component"] == "div"

    def test_bootstrap_navbar(self):
        result = map_component("bootstrap", "nav", "Navbar")
        assert result["component"] == "nav"
        assert "navbar" in result["props_hint"]
        assert result["match_type"] == "keyword"

    def test_shadcn_dialog_exact(self):
        result = map_component("shadcn", "dialog")
        assert result["component"] == "Dialog"
        assert result["import_from"] == "@/components/ui/dialog"
        assert result["match_type"] == "exact"

    def test_mui_fallback_defaults(self):
        result = map_component("mui", "unknown_element", "Random")
        assert result["component"] == "Box"
        assert result["match_type"] == "fallback"

    def test_antd_fallback_defaults(self):
        result = map_component("antd", "unknown_element", "Random")
        assert result["component"] == "div"
        assert result["match_type"] == "fallback"


class TestThemeInjection:
    """Test library-specific theme file injection."""

    def _make_tokens(self, colors: list | None = None) -> TokenCollection:
        if colors is None:
            colors = [
                ColorToken(name="primary", value="#1976d2", type="color", category="action"),
                ColorToken(name="secondary", value="#dc004e", type="color", category="action"),
                ColorToken(name="background", value="#ffffff", type="color", category="surface"),
            ]
        return TokenCollection(colors=colors, token_count=len(colors))

    def test_inject_mui_theme_creates_theme_file(self):
        from main import _inject_mui_theme

        files: dict[str, str] = {}
        tokens = self._make_tokens()
        _inject_mui_theme(files, tokens)
        assert "src/theme.ts" in files
        theme = files["src/theme.ts"]
        assert 'createTheme' in theme
        assert '@mui/material/styles' in theme
        assert '#1976d2' in theme
        assert '#dc004e' in theme

    def test_inject_mui_theme_does_not_overwrite_existing(self):
        from main import _inject_mui_theme

        files: dict[str, str] = {"src/theme.ts": "// existing"}
        tokens = self._make_tokens()
        _inject_mui_theme(files, tokens)
        assert files["src/theme.ts"] == "// existing"

    def test_inject_mui_theme_no_colors(self):
        from main import _inject_mui_theme

        files: dict[str, str] = {}
        tokens = self._make_tokens([])
        _inject_mui_theme(files, tokens)
        assert "src/theme.ts" not in files

    def test_inject_antd_theme_creates_theme_config(self):
        from main import _inject_antd_theme

        files: dict[str, str] = {}
        tokens = self._make_tokens()
        _inject_antd_theme(files, tokens)
        assert "src/theme.ts" in files
        theme = files["src/theme.ts"]
        assert 'ConfigProvider' in theme
        assert 'antd' in theme
        assert '#1976d2' in theme

    def test_inject_antd_theme_does_not_overwrite_existing(self):
        from main import _inject_antd_theme

        files: dict[str, str] = {"src/theme.ts": "// existing"}
        tokens = self._make_tokens()
        _inject_antd_theme(files, tokens)
        assert files["src/theme.ts"] == "// existing"

    def test_inject_antd_theme_no_colors(self):
        from main import _inject_antd_theme

        files: dict[str, str] = {}
        tokens = self._make_tokens([])
        _inject_antd_theme(files, tokens)
        assert "src/theme.ts" not in files
