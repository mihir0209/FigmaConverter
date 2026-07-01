"""Tests for the component library mapper module."""

from processors.component_library_mapper import (
    get_library_dependencies,
    get_library_info,
    get_library_instructions,
    list_supported_libraries,
    map_component,
)


class TestListSupportedLibraries:
    def test_returns_sorted_list(self):
        libs = list_supported_libraries()
        assert isinstance(libs, list)
        assert len(libs) > 0
        assert libs == sorted(libs)

    def test_includes_expected(self):
        libs = list_supported_libraries()
        for expected in ("shadcn", "mui", "antd", "bootstrap"):
            assert expected in libs, f"Missing {expected}"


class TestGetLibraryInfo:
    def test_returns_none_for_unknown(self):
        assert get_library_info("unknown") is None

    def test_returns_none_for_empty(self):
        assert get_library_info("") is None

    def test_returns_none_for_none(self):
        assert get_library_info(None) is None

    def test_shadcn_has_components(self):
        info = get_library_info("shadcn")
        assert "components" in info
        assert "button" in info["components"]

    def test_mui_has_keywords(self):
        info = get_library_info("mui")
        assert "keywords" in info
        assert "btn" in info["keywords"]

    def test_antd_has_fallback(self):
        info = get_library_info("antd")
        assert info["fallback_element"] == "div"

    def test_bootstrap_framework_hint(self):
        info = get_library_info("bootstrap")
        assert info["framework_hint"] == "html"


class TestMapComponent:
    def test_exact_type_match_shadcn(self):
        result = map_component("shadcn", "button")
        assert result["component"] == "Button"
        assert "ui/button" in result["import_from"]
        assert result["match_type"] == "exact"

    def test_exact_type_match_mui(self):
        result = map_component("mui", "card")
        assert result["component"] == "Card"
        assert "@mui/material/Card" in result["import_from"]
        assert result["match_type"] == "exact"

    def test_exact_type_match_antd(self):
        result = map_component("antd", "table")
        assert result["component"] == "Table"
        assert result["import_from"] == "antd"
        assert result["match_type"] == "exact"

    def test_exact_type_match_bootstrap(self):
        result = map_component("bootstrap", "table")
        assert result["component"] == "table"
        assert result["props_hint"] == 'class="table table-striped"'
        assert result["match_type"] == "exact"

    def test_keyword_match_by_name_shadcn(self):
        result = map_component("shadcn", "unknown", "Submit Button")
        assert result["component"] == "Button"
        assert result["match_type"] == "keyword"

    def test_keyword_match_by_name_mui(self):
        result = map_component("mui", "unknown", "Search Input")
        assert result["component"] == "TextField"
        assert result["match_type"] == "keyword"

    def test_keyword_match_by_name_antd(self):
        result = map_component("antd", "unknown", "Navigation Menu")
        assert result["component"] == "Menu"
        assert result["match_type"] == "keyword"

    def test_fallback_for_unknown(self):
        result = map_component("shadcn", "unknown_element")
        assert result["component"] in ("div",)
        assert result["match_type"] == "fallback"

    def test_fallback_bootstrap(self):
        result = map_component("bootstrap", "unknown_element")
        assert result["component"] == "div"
        assert result["match_type"] == "fallback"

    def test_unknown_library_returns_fallback(self):
        result = map_component("nonexistent", "button")
        assert result["component"] == "div"
        assert result["match_type"] == "unknown_library"

    def test_shadcn_card_has_props(self):
        result = map_component("shadcn", "card")
        assert "CardHeader" in result["props_hint"]

    def test_mui_button_variants(self):
        result = map_component("mui", "button")
        assert "contained" in result["props_hint"]

    def test_antd_button_types(self):
        result = map_component("antd", "button")
        assert "primary" in result["props_hint"]

    def test_bootstrap_button_classes(self):
        result = map_component("bootstrap", "button")
        assert "btn btn-primary" in result["props_hint"]

    def test_case_insensitive_type(self):
        result = map_component("shadcn", "BUTTON")
        assert result["component"] == "Button"


class TestGetLibraryInstructions:
    def test_shadcn_instructions(self):
        text = get_library_instructions("shadcn")
        assert "COMPONENT LIBRARY: shadcn" in text
        assert "@radix-ui" not in text  # import paths are the shadcn ones
        assert "@/components/ui/button" in text

    def test_mui_instructions(self):
        text = get_library_instructions("mui")
        assert "@mui/material/Button" in text
        assert "MUST use" in text

    def test_antd_instructions(self):
        text = get_library_instructions("antd")
        assert "antd" in text
        assert "Typography" in text

    def test_bootstrap_instructions(self):
        text = get_library_instructions("bootstrap")
        assert "bootstrap" in text.lower()
        assert "class=" in text

    def test_empty_returns_empty(self):
        assert get_library_instructions("") == ""

    def test_none_returns_empty(self):
        assert get_library_instructions(None) == ""

    def test_unknown_returns_empty(self):
        assert get_library_instructions("unknown") == ""


class TestGetLibraryDependencies:
    def test_shadcn_deps(self):
        deps = get_library_dependencies("shadcn")
        assert "class-variance-authority" in deps
        assert "lucide-react" in deps

    def test_mui_deps(self):
        deps = get_library_dependencies("mui")
        assert "@mui/material" in deps
        assert "@emotion/react" in deps

    def test_antd_deps(self):
        deps = get_library_dependencies("antd")
        assert "antd" in deps
        assert "@ant-design/icons" in deps

    def test_bootstrap_deps(self):
        deps = get_library_dependencies("bootstrap")
        assert "bootstrap" in deps

    def test_empty_returns_empty(self):
        assert get_library_dependencies("") == {}

    def test_none_returns_empty(self):
        assert get_library_dependencies(None) == {}

    def test_unknown_returns_empty(self):
        assert get_library_dependencies("unknown") == {}
