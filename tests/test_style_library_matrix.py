"""Tests for the framework × style × library configuration matrix."""

import pytest

from processors.style_library_matrix import (
    ConfigurationResult,
    DependencyResolver,
    _FRAMEWORK_SUPPORTED_LIBRARIES,
    _FRAMEWORK_SUPPORTED_STYLES,
    _PREFERRED_COMBINATIONS,
    list_supported_combinations,
    resolve_configuration,
    validate_combination,
)


class TestValidateCombination:
    def test_react_tailwind_shadcn_valid(self):
        ok, warnings, info, err = validate_combination("react_ts", "tailwind", "shadcn")
        assert ok
        assert err is None
        # Preferred combo — should have at least one info message
        assert any("shadcn" in m.lower() for m in info)

    def test_react_css_none_valid(self):
        ok, warnings, info, err = validate_combination("react", "css", "")
        assert ok
        assert err is None

    def test_unknown_framework_invalid(self):
        ok, warnings, info, err = validate_combination("cobol", "css", "")
        assert not ok
        assert err is not None
        assert "cobol" in err.lower()

    def test_angular_with_shadcn_invalid(self):
        ok, warnings, info, err = validate_combination("angular", "css", "shadcn")
        assert not ok
        assert "shadcn" in err

    def test_angular_with_no_lib_valid(self):
        ok, _, _, err = validate_combination("angular", "css", "")
        assert ok
        assert err is None

    def test_normalizes_case(self):
        ok, _, _, _ = validate_combination("REACT", "TAILWIND", "SHADCN")
        assert ok

    def test_none_args_default(self):
        ok, _, _, _ = validate_combination("react", None, None)
        assert ok

    def test_empty_args_default(self):
        ok, _, _, _ = validate_combination("react", "", "")
        assert ok

    def test_unmatched_engine_for_framework(self):
        ok, _, _, err = validate_combination("vue", "tailwind", "")
        assert not ok
        assert err is not None

    def test_bootstrap_supported_for_html(self):
        ok, _, _, _ = validate_combination("html", "css", "bootstrap")
        assert ok

    def test_mui_unsupported_for_html(self):
        ok, _, _, err = validate_combination("html", "css", "mui")
        assert not ok

    def test_scss_supported_for_vue(self):
        ok, _, _, _ = validate_combination("vue", "scss", "bootstrap")
        assert ok


class TestResolveConfiguration:
    def test_returns_valid_config(self):
        cfg = resolve_configuration("react_ts", "tailwind", "shadcn")
        assert cfg.valid
        assert cfg.error is None
        assert "dependencies" in cfg.dependencies
        assert "devDependencies" in cfg.dependencies

    def test_invalid_combination_returns_error(self):
        cfg = resolve_configuration("cobol")
        assert not cfg.valid
        assert cfg.error is not None

    def test_paths_dict_present(self):
        cfg = resolve_configuration("react", "css", "")
        assert "styles_entry" in cfg.paths
        assert cfg.paths["styles_entry"] == "src/index.css"

    def test_to_dict_round_trip(self):
        cfg = resolve_configuration("vue", "scss", "")
        d = cfg.to_dict()
        assert d["framework"] == "vue"
        assert d["style_engine"] == "scss"
        assert d["valid"]
        assert "paths" in d
        assert "dependencies" in d

    def test_html_uses_correct_styles_path(self):
        cfg = resolve_configuration("html", "css", "bootstrap")
        assert cfg.valid
        assert cfg.paths["styles_entry"] == "css/styles.css"


class TestListSupportedCombinations:
    def test_returns_list(self):
        combos = list_supported_combinations()
        assert isinstance(combos, list)
        assert len(combos) > 0

    def test_includes_react_shadcn(self):
        combos = list_supported_combinations()
        assert {"framework": "react", "style": "css", "library": "shadcn"} in combos

    def test_includes_vue_bootstrap(self):
        combos = list_supported_combinations()
        assert {"framework": "vue", "style": "scss", "library": "bootstrap"} in combos

    def test_only_string_values(self):
        for combo in list_supported_combinations():
            assert all(isinstance(v, str) for v in combo.values())


class TestDependencyResolver:
    def test_resolve_returns_dict_shape(self):
        resolver = DependencyResolver(use_cache=False)
        result = resolver.resolve("react")
        assert "dependencies" in result
        assert "devDependencies" in result
        assert isinstance(result["dependencies"], dict)
        assert isinstance(result["devDependencies"], dict)

    def test_react_has_react_in_deps(self):
        result = DependencyResolver(use_cache=False).resolve("react")
        assert "react" in result["dependencies"]
        assert result["dependencies"]["react"].startswith("^")

    def test_react_ts_has_typescript(self):
        result = DependencyResolver(use_cache=False).resolve("react_ts")
        assert "typescript" in result["devDependencies"]

    def test_vue_has_vue_router(self):
        result = DependencyResolver(use_cache=False).resolve("vue")
        assert "vue-router" in result["dependencies"]

    def test_angular_has_zone_js(self):
        result = DependencyResolver(use_cache=False).resolve("angular")
        assert "zone.js" in result["dependencies"]

    def test_tailwind_adds_devdep(self):
        result = DependencyResolver(use_cache=False).resolve("react", "tailwind")
        assert "@tailwindcss/vite" in result["devDependencies"]

    def test_scss_adds_sass(self):
        result = DependencyResolver(use_cache=False).resolve("react", "scss")
        assert "sass" in result["devDependencies"]

    def test_styled_adds_styled_components(self):
        result = DependencyResolver(use_cache=False).resolve("react", "styled")
        assert "styled-components" in result["devDependencies"]

    def test_shadcn_adds_radix_deps(self):
        result = DependencyResolver(use_cache=False).resolve("react_ts", "css", "shadcn")
        assert "@radix-ui/react-dialog" in result["dependencies"]
        assert "class-variance-authority" in result["dependencies"]

    def test_mui_adds_mui_deps(self):
        result = DependencyResolver(use_cache=False).resolve("react", "css", "mui")
        assert "@mui/material" in result["dependencies"]
        assert "@emotion/react" in result["dependencies"]

    def test_antd_adds_antd_dep(self):
        result = DependencyResolver(use_cache=False).resolve("react", "css", "antd")
        assert "antd" in result["dependencies"]

    def test_bootstrap_adds_bootstrap(self):
        result = DependencyResolver(use_cache=False).resolve("react", "css", "bootstrap")
        assert "bootstrap" in result["dependencies"]

    def test_deduplicates(self):
        result = DependencyResolver(use_cache=False).resolve("react", "css", "antd")
        assert isinstance(result["dependencies"], dict)
        assert len(result["dependencies"]) == len(set(result["dependencies"].keys()))

    def test_resolve_to_package_json(self):
        result = DependencyResolver(use_cache=False).resolve_to_package_json("react", "css", "mui")
        assert result["name"] == "figma-converted-app"
        assert result["private"] is True
        assert "scripts" in result
        assert result["scripts"]["dev"] == "vite"
        assert "@mui/material" in result["dependencies"]

    def test_package_json_nextjs(self):
        result = DependencyResolver(use_cache=False).resolve_to_package_json("nextjs", "tailwind", "")
        assert result["scripts"]["dev"] == "next dev"
        assert "next" in result["dependencies"]

    def test_package_json_angular(self):
        result = DependencyResolver(use_cache=False).resolve_to_package_json("angular", "css", "")
        assert "ng" in result["scripts"]

    def test_resolver_uses_cache(self):
        resolver = DependencyResolver(use_cache=True)
        r1 = resolver.resolve("react")
        r2 = resolver.resolve("react")
        # Same dict identity proves caching
        assert r1 is r2

    def test_resolver_no_cache(self):
        resolver = DependencyResolver(use_cache=False)
        r1 = resolver.resolve("react")
        r2 = resolver.resolve("react")
        # Different dict instances (no cache)
        assert r1 is not r2
        # But equal content
        assert r1 == r2

    def test_unknown_framework_falls_back(self):
        result = DependencyResolver(use_cache=False).resolve("cobol")
        # Fallback to react deps
        assert "react" in result["dependencies"]


class TestCompatibilityTables:
    def test_all_frameworks_have_styles(self):
        for framework in _FRAMEWORK_SUPPORTED_STYLES:
            assert framework in _FRAMEWORK_SUPPORTED_LIBRARIES

    def test_react_supports_main_libs(self):
        libs = _FRAMEWORK_SUPPORTED_LIBRARIES["react"]
        for lib in ("shadcn", "mui", "antd", "bootstrap"):
            assert lib in libs

    def test_html_supports_bootstrap_only(self):
        libs = _FRAMEWORK_SUPPORTED_LIBRARIES["html"]
        assert libs == ["bootstrap"]

    def test_html_supports_css_only(self):
        styles = _FRAMEWORK_SUPPORTED_STYLES["html"]
        assert styles == ["css"]


class TestPreferredCombos:
    def test_react_ts_tailwind_shadcn_in_preferred(self):
        assert any(
            c["framework"] == "react_ts" and c["style"] == "tailwind" and c.get("library") == "shadcn"
            for c in _PREFERRED_COMBINATIONS
        )
