"""Tests for the project assembler, particularly the previously-broken
component-copy path."""

import json
import zipfile
from pathlib import Path

import pytest

from processors.project_assembler import ProjectAssembler


@pytest.fixture
def assembler(tmp_path):
    return ProjectAssembler(output_base_dir=str(tmp_path / "assembled"))


@pytest.fixture
def assets_dir(tmp_path):
    base = tmp_path / "components"
    (base / "images").mkdir(parents=True)
    img = base / "images" / "logo.png"
    img.write_bytes(b"fake-png")
    return base, img


class TestAddComponents:
    def test_copies_files_from_dict_mapping(self, assembler, assets_dir, tmp_path):
        base, img = assets_dir
        components_result = {
            "total_components": 1,
            "components": {
                "0:1": {
                    "id": "0:1",
                    "name": "Logo",
                    "type": "image",
                    "path": str(img),
                    "original_name": "Logo",
                    "dimensions": {"width": 32, "height": 32},
                }
            },
        }
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        added = assembler._add_components_to_project(components_result, project_dir, "react")
        assert added == 1
        # The asset lands under framework-aware assets dir.
        target = project_dir / "src" / "assets" / "logo.png"
        assert target.exists()
        # A metadata file is written alongside.
        metadata = list((project_dir / "src" / "assets").glob("*_metadata.json"))
        assert metadata and json.loads(metadata[0].read_text())["id"] == "0:1"

    def test_handles_list_shaped_components_payload(self, assembler, assets_dir, tmp_path):
        base, img = assets_dir
        components_result = {
            "total_components": 1,
            "components": [
                {
                    "id": "0:1",
                    "name": "Logo",
                    "type": "image",
                    "safe_name": "logo",
                    "assets": {"image": str(img)},
                    "dimensions": {"width": 32, "height": 32},
                }
            ],
        }
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        added = assembler._add_components_to_project(components_result, project_dir, "html_css_js")
        assert added == 1
        target = project_dir / "assets" / "logo.png"
        assert target.exists()
        metadata = list((project_dir / "assets").glob("*_metadata.json"))
        assert metadata


class TestCreateProjectZip:
    def test_zip_only_contains_project_dir(self, assembler, tmp_path):
        # Lay down two unrelated projects.
        project_a = tmp_path / "assembled" / "job_a"
        project_a.mkdir(parents=True)
        (project_a / "a.txt").write_text("alpha")
        project_b = tmp_path / "assembled" / "job_b"
        project_b.mkdir()
        (project_b / "b.txt").write_text("beta")

        zip_path = assembler._create_project_zip(project_a, "job_a")
        assert zip_path.exists()

        with zipfile.ZipFile(zip_path) as archive:
            names = set(archive.namelist())
        # zip_path is also at output_base_dir/job_a; the archive should not
        # include job_b's nor its own zipped file.
        assert "job_a/a.txt" in names
        assert not any(name.startswith("job_b/") for name in names)
        assert "job_a.zip" not in names


class TestAssembleProject:
    def test_writes_files_and_emits_zip(self, assembler, tmp_path):
        code_result = {
            "framework": "react",
            "files": {"src/App.jsx": "console.log('Hello')", "package.json": '{}'},
            "main_file": "src/App.jsx",
        }
        result = assembler.assemble_project(
            code_result=code_result,
            components_result={"total_components": 0, "components": []},
            framework="react",
            job_id="job-1",
        )
        assert result["files_created"] >= 2
        assert Path(result["zip_path"]).exists()
        with zipfile.ZipFile(Path(result["zip_path"])) as archive:
            names = set(archive.namelist())
        # The assembler uses the project_name as the top-level folder inside
        # the zip; we don't pin to `figma_converted_*` to keep the test
        # independent of the assembler naming convention.
        assert any(name.endswith("src/App.jsx") for name in names)

    def test_returns_zip_path_none_on_failure(self, assembler, tmp_path, monkeypatch):
        from processors import project_assembler

        def boom(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(project_assembler.zipfile, "ZipFile", boom)
        result = assembler.assemble_project(
            code_result={"framework": "react", "files": {}, "main_file": "src/App.jsx"},
            components_result={"total_components": 0, "components": []},
            framework="react",
            job_id="job-2",
        )
        assert result["zip_path"] is None
