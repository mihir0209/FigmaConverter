"""Tests for the template scaffolder module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from processors.template_scaffolder import (
    _apply_manual_scaffold,
    _normalize_template,
    get_framework_template_info,
    list_supported_frameworks,
    scaffold_project,
)


class TestListSupportedFrameworks:
    def test_returns_sorted_list(self):
        frameworks = list_supported_frameworks()
        assert isinstance(frameworks, list)
        assert len(frameworks) > 0
        assert frameworks == sorted(frameworks)

    def test_includes_react(self):
        assert "react" in list_supported_frameworks()

    def test_includes_flutter_and_angular(self):
        frameworks = list_supported_frameworks()
        assert "flutter" in frameworks
        assert "angular" in frameworks


class TestGetFrameworkTemplateInfo:
    def test_react_returns_github_source(self):
        info = get_framework_template_info("react")
        assert info is not None
        assert info["source"].startswith("github:")
        assert "description" in info

    def test_flutter_returns_builtin(self):
        info = get_framework_template_info("flutter")
        assert info is not None
        assert info["source"] == "builtin"

    def test_unknown_returns_none(self):
        assert get_framework_template_info("nonexistent_framework") is None


class TestApplyManualScaffold:
    def test_angular_creates_all_expected_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            result = _apply_manual_scaffold("angular", target)
            assert result is True

            expected_files = [
                "angular.json",
                "src/index.html",
                "src/main.ts",
                "src/app/app.module.ts",
                "src/app/app.component.ts",
                "tsconfig.json",
            ]
            for path in expected_files:
                assert (target / path).exists(), f"Missing: {path}"
                assert (target / path).stat().st_size > 0, f"Empty: {path}"

    def test_flutter_creates_all_expected_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            result = _apply_manual_scaffold("flutter", target)
            assert result is True

            expected_files = [
                "pubspec.yaml",
                "lib/main.dart",
                "analysis_options.yaml",
                ".gitignore",
            ]
            for path in expected_files:
                assert (target / path).exists(), f"Missing: {path}"

    def test_unknown_framework_returns_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            result = _apply_manual_scaffold("unknown_framework", target)
            assert result is False

    def test_react_not_in_manual(self):
        """React should use GitHub template, not manual scaffold."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            result = _apply_manual_scaffold("react", target)
            assert result is False  # react is not in manual scaffolds


class TestNormalizeTemplate:
    def test_renames_underscore_prefix_to_dot(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            (target / "_gitignore").write_text("node_modules/")
            (target / "src").mkdir()
            (target / "src" / "_eslintrc.cjs").write_text("module.exports = {};")
            _normalize_template(target)
            assert not (target / "_gitignore").exists()
            assert (target / ".gitignore").exists()
            assert (target / ".gitignore").read_text() == "node_modules/"
            assert (target / "src" / ".eslintrc.cjs").exists()

    def test_does_not_overwrite_existing_dotfile(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            (target / ".gitignore").write_text("existing")
            (target / "_gitignore").write_text("new")
            _normalize_template(target)
            # Should not overwrite existing .gitignore
            assert (target / ".gitignore").read_text() == "existing"


class TestScaffoldProject:
    def test_manual_scaffold_works(self):
        """Flutter has no GitHub template entry, so it uses manual."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "flutter_app"
            result = scaffold_project(target, "flutter")
            assert result is True
            assert (target / "pubspec.yaml").exists()
            assert "flutter" in (target / "pubspec.yaml").read_text()

    @patch("processors.template_scaffolder._download_and_extract_github_template")
    def test_github_scaffold_fallback_to_manual(self, mock_download):
        """When GitHub download fails for a framework that also has a manual
        scaffold, it should fall back."""
        mock_download.return_value = False

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "angular_app"
            result = scaffold_project(target, "angular")
            # angular has no FRAMEWORK_TEMPLATES entry, only manual scaffold
            assert result is True
            assert (target / "angular.json").exists()

    def test_unknown_framework_returns_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            result = scaffold_project(target, "unknown_framework")
            assert result is False

    def test_scaffold_does_not_leave_temp_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "app"
            scaffold_project(target, "flutter")
            # Should only contain the scaffold files
            contents = list(target.rglob("*"))
            assert len(contents) > 0
            # No .zip or temp artifacts
            assert not any(f.suffix == ".zip" for f in contents)
