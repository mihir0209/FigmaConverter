"""Tests for the AI chat refinement flow (Plan 004)."""

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Pure unit tests: prompting/refinement_prompts.py
# ---------------------------------------------------------------------------

from prompting.refinement_prompts import (
    RefinementContext,
    build_refinement_prompt,
    parse_refinement_response,
    render_diff,
    _truncate_text,
    _format_files_block,
)


class TestTruncateText:
    def test_no_truncation_when_short(self):
        result = _truncate_text("hello", 100)
        assert "[truncated" not in result

    def test_truncation_marker_when_long(self):
        long_text = "x" * 2000
        result = _truncate_text(long_text, 100)
        assert "[truncated" in result
        assert "1900 chars" in result

    def test_empty_text_returns_empty(self):
        assert _truncate_text("", 100) == ""
        assert _truncate_text(None, 100) == ""


class TestFormatFilesBlock:
    def test_empty_files(self):
        block = _format_files_block({}, None)
        assert "(no files" in block

    def test_includes_files(self):
        block = _format_files_block({"a.js": "code here"}, None)
        assert "a.js" in block
        assert "code here" in block

    def test_marks_target_files(self):
        block = _format_files_block(
            {"target.tsx": "// target", "other.tsx": "// other"},
            target_files=["target.tsx"],
        )
        assert "EDIT TARGET" in block
        assert "content omitted" in block  # non-target files are summarised

    def test_no_target_shows_all_files(self):
        block = _format_files_block(
            {"a.tsx": "code"},
            target_files=None,
        )
        assert "EDIT TARGET" not in block
        assert "code" in block


class TestBuildRefinementPrompt:
    def test_basic_prompt(self):
        ctx = RefinementContext(
            user_prompt="make buttons bigger",
            current_files={"src/App.tsx": "export function App() {}"},
            framework="react_ts",
            style_engine="tailwind",
            component_library="shadcn",
            refinement_iteration=1,
        )
        prompt = build_refinement_prompt(ctx)
        assert isinstance(prompt.messages, list)
        assert len(prompt.messages) == 2
        assert prompt.messages[0]["role"] == "system"
        assert prompt.messages[1]["role"] == "user"

    def test_user_prompt_includes_request(self):
        ctx = RefinementContext(
            user_prompt="color the buttons red",
            current_files={},
            framework="react",
            refinement_iteration=1,
        )
        prompt = build_refinement_prompt(ctx)
        content = prompt.messages[1]["content"]
        assert "color the buttons red" in content
        assert "react" in content.lower()

    def test_target_files_listed(self):
        ctx = RefinementContext(
            user_prompt="edit App",
            current_files={"src/App.tsx": "x", "src/main.tsx": "y"},
            target_files=["src/App.tsx"],
            framework="react",
            refinement_iteration=1,
        )
        prompt = build_refinement_prompt(ctx)
        content = prompt.messages[1]["content"]
        assert "TARGET FILES" in content
        assert "src/App.tsx" in content

    def test_design_summary_passed_through(self):
        ctx = RefinementContext(
            user_prompt="change colors",
            current_files={"a.tsx": "x"},
            design_summary="Primary: blue, secondary: gray",
            framework="react",
            refinement_iteration=1,
        )
        prompt = build_refinement_prompt(ctx)
        content = prompt.messages[1]["content"]
        assert "Primary: blue" in content

    def test_design_summary_truncated(self):
        long_summary = "design note " * 5000
        ctx = RefinementContext(
            user_prompt="change",
            current_files={"a": "x"},
            design_summary=long_summary,
            framework="react",
            refinement_iteration=1,
        )
        prompt = build_refinement_prompt(ctx)
        content = prompt.messages[1]["content"]
        assert "[truncated" in content

    def test_iteration_in_output(self):
        ctx = RefinementContext(
            user_prompt="refine",
            current_files={"a": "x"},
            refinement_iteration=5,
            framework="react",
        )
        prompt = build_refinement_prompt(ctx)
        text = " ".join(m["content"] for m in prompt.messages)
        assert "iteration 5" in text

    def test_previous_summary_passed(self):
        ctx = RefinementContext(
            user_prompt="keep going",
            current_files={"a": "x"},
            previous_summary="Made buttons blue",
            framework="react",
            refinement_iteration=2,
        )
        prompt = build_refinement_prompt(ctx)
        content = prompt.messages[1]["content"]
        assert "Made buttons blue" in content


class TestParseRefinementResponse:
    def test_basic_clean_response(self):
        raw = json.dumps({
            "summary": "Updated colors",
            "updated_files": {"a.tsx": "new code", "b.tsx": "updated"},
            "changed_files": ["a.tsx", "b.tsx"],
        })
        result = parse_refinement_response(raw)
        assert result["summary"] == "Updated colors"
        assert result["updated_files"]["a.tsx"] == "new code"
        assert set(result["changed_files"]) == {"a.tsx", "b.tsx"}

    def test_strips_markdown_json_block(self):
        raw = (
            "```json\n" +
            json.dumps({
                "summary": "X",
                "updated_files": {"a": "y"},
                "changed_files": ["a"],
            }) +
            "\n```"
        )
        result = parse_refinement_response(raw)
        assert result["summary"] == "X"
        assert "a" in result["updated_files"]

    def test_recovers_partial_json(self):
        raw = (
            "Here is the result:\n\n" +
            json.dumps({
                "summary": "X",
                "updated_files": {"a": "y"},
                "changed_files": ["a"],
            }) +
            "\nDone."
        )
        result = parse_refinement_response(raw)
        assert result["summary"] == "X"

    def test_valid_paths_filters(self):
        raw = json.dumps({
            "summary": "X",
            "updated_files": {"good.tsx": "y", "bad.tsx": "x"},
            "changed_files": ["good.tsx", "bad.tsx"],
        })
        result = parse_refinement_response(raw, valid_paths=["good.tsx"])
        assert "good.tsx" in result["updated_files"]
        assert "bad.tsx" not in result["updated_files"]
        assert result["changed_files"] == ["good.tsx"]

    def test_missing_updated_files_key(self):
        raw = json.dumps({"summary": "X", "changed_files": []})
        result = parse_refinement_response(raw)
        assert result["updated_files"] == {}

    def test_unchanged_changed_files_drops(self):
        raw = json.dumps({
            "summary": "X",
            "updated_files": {"only.tsx": "y"},
            "changed_files": ["only.tsx", "phantom.tsx"],
        })
        result = parse_refinement_response(raw)
        assert set(result["changed_files"]) == {"only.tsx"}

    def test_raises_value_error_when_empty(self):
        with pytest.raises(ValueError):
            parse_refinement_response("")
        with pytest.raises(ValueError):
            parse_refinement_response("   ")

    def test_raises_value_error_when_invalid_json(self):
        with pytest.raises(ValueError):
            parse_refinement_response("not json at all")

    def test_skips_non_string_content(self):
        raw = json.dumps({
            "summary": "X",
            "updated_files": {"a": "ok", "b": 123, "c": None},
            "changed_files": ["a"],
        })
        result = parse_refinement_response(raw)
        # Only entries with str content remain
        assert "a" in result["updated_files"]
        assert "b" not in result["updated_files"]
        assert "c" not in result["updated_files"]


class TestRenderDiff:
    def test_identical_returns_empty(self):
        assert render_diff("same", "same") == ""

    def test_different_returns_diff(self):
        diff = render_diff("line one", "line two", "file.tsx")
        assert "file.tsx" in diff
        assert len(diff) > 0

    def test_includes_file_label(self):
        diff = render_diff("a", "b", "src/App.tsx")
        assert "src/App.tsx (old)" in diff
        assert "src/App.tsx (new)" in diff


# ---------------------------------------------------------------------------
# JobStore refinement history tests
# ---------------------------------------------------------------------------


class TestJobStoreRefinementHistory:
    def test_initializer_adds_refinement_column(self, tmp_path):
        import main
        db_path = tmp_path / "test.db"
        main.JobStore(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
        conn.close()
        assert "refinement_history" in cols

    def test_alter_table_on_existing_db(self, tmp_path):
        """If the DB was created without refinement_history, the upgrade fills it in."""
        import main
        db_path = tmp_path / "legacy.db"
        # Create a legacy DB with the old schema
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                "CREATE TABLE jobs ("
                "id TEXT PRIMARY KEY, status TEXT NOT NULL, progress INTEGER NOT NULL,"
                "message TEXT NOT NULL DEFAULT '', result TEXT, error TEXT,"
                "created_at TEXT NOT NULL, updated_at TEXT NOT NULL, idempotency TEXT UNIQUE"
                ")"
            )
        # Now init the store — it should upgrade
        store = main.JobStore(db_path)
        store.create("j1", "queued")
        store.update("j1", progress=10)
        store.append_refinement("j1", {"iteration": 1, "prompt": "hi"})
        record = store.get("j1")
        assert record["refinement_history"][0]["prompt"] == "hi"

    def test_append_refinement_increases_count(self, tmp_path):
        import main
        store = main.JobStore(tmp_path / "test.db")
        store.create("j1", "queued")
        assert store.refinement_count("j1") == 0
        store.append_refinement("j1", {"iteration": 1, "prompt": "first"})
        assert store.refinement_count("j1") == 1
        store.append_refinement("j1", {"iteration": 2, "prompt": "second"})
        assert store.refinement_count("j1") == 2

    def test_get_refinement_history_default_empty(self, tmp_path):
        import main
        store = main.JobStore(tmp_path / "test.db")
        store.create("j1", "queued")
        assert store.get_refinement_history("j1") == []
        assert store.get_refinement_history("does-not-exist") == []

    def test_get_returns_parsed_history(self, tmp_path):
        import main
        store = main.JobStore(tmp_path / "test.db")
        store.create("j1", "queued")
        store.append_refinement("j1", {"iteration": 1, "prompt": "x", "summary": "ok"})
        record = store.get("j1")
        assert isinstance(record["refinement_history"], list)
        assert record["refinement_history"][0]["iteration"] == 1


# ---------------------------------------------------------------------------
# Endpoint / API tests
# ---------------------------------------------------------------------------


@pytest.fixture
def client_with_patched_jobstore(monkeypatch, tmp_path):
    import main
    main.JOBS_DB_PATH = Path(tmp_path) / "jobs.db"
    main.JOB_STORE._db_path = main.JOBS_DB_PATH
    with sqlite3.connect(str(main.JOBS_DB_PATH)) as conn:
        conn.executescript(main.JobStore.SCHEMA)
    return TestClient(main.app)


@pytest.fixture
def seeded_job(client_with_patched_jobstore, tmp_path):
    """Plant a completed job with a project dir we can write to."""
    import main

    project_dir = tmp_path / "figma_converted"
    project_dir.mkdir()
    (project_dir / "src").mkdir()
    (project_dir / "src" / "App.tsx").write_text("// initial code", encoding="utf-8")

    file_list = ["src/App.tsx"]
    job_id = "seeded-1"
    with sqlite3.connect(str(main.JOBS_DB_PATH)) as conn:
        conn.execute(
            "INSERT INTO jobs(id, status, progress, message, created_at, updated_at, result)"
            " VALUES (?, 'completed', 100, '', ?, ?, ?)",
            (
                job_id,
                "2024-01-01T00:00:00",
                "2024-01-01T00:00:00",
                json.dumps({
                    "framework": "react_ts",
                    "framework_name": "React + TypeScript",
                    "output_path": str(project_dir),
                    "project_name": "demo",
                    "file_list": file_list,
                }),
            ),
        )
    return job_id, project_dir, file_list


class _FakeAISuccess:
    def __init__(self, content: str):
        self.success = True
        self.content = content
        self.error_message = None


class _FakeAIFailure:
    success = False
    content = ""
    error_message = "network error"


class TestRefineEndpoint:
    def test_returns_404_for_unknown_job(self, client_with_patched_jobstore):
        response = client_with_patched_jobstore.post(
            "/api/refine/no-such-job",
            json={"prompt": "do something"},
        )
        assert response.status_code == 404

    def test_rejects_in_progress_job(self, client_with_patched_jobstore):
        import main
        with sqlite3.connect(str(main.JOBS_DB_PATH)) as conn:
            conn.execute(
                "INSERT INTO jobs(id, status, progress, message, created_at, updated_at)"
                " VALUES ('processing-1', 'processing', 50, '', '2024-01-01', '2024-01-01')"
            )
        response = client_with_patched_jobstore.post(
            "/api/refine/processing-1",
            json={"prompt": "x"},
        )
        assert response.status_code == 409

    def test_rejects_oversize_prompt(self, client_with_patched_jobstore):
        response = client_with_patched_jobstore.post(
            "/api/refine/anything",
            json={"prompt": "x" * 5000},
        )
        # Pydantic rejects >2000 chars before our route runs
        assert response.status_code in (400, 422)

    def test_applies_refinement(self, monkeypatch, client_with_patched_jobstore, seeded_job):
        """End-to-end patch of refine_code_with_ai writing back to disk."""
        job_id, project_dir, file_list = seeded_job

        updated_src = "// refined code"
        fake_outcome = {
            "updated_files": {"src/App.tsx": updated_src},
            "changed_files": ["src/App.tsx"],
            "summary": "Refined App.tsx",
            "raw_response": "{}",
            "iteration": 1,
        }

        def fake_ai(*_args, **_kwargs):
            return fake_outcome

        import prompting
        monkeypatch.setattr(prompting, "refine_code_with_ai", fake_ai)
        # Also patch the import inside main and orchestrators used inside main
        import main as main_mod
        monkeypatch.setattr(main_mod, "refine_code_with_ai", fake_ai)

        # Patch ProjectAssembler._create_project_zip to keep tests hermetic
        import processors.project_assembler as pa
        monkeypatch.setattr(
            pa.ProjectAssembler,
            "_create_project_zip",
            lambda self, d, name: d / f"{name}.zip",
        )

        response = client_with_patched_jobstore.post(
            f"/api/refine/{job_id}",
            json={"prompt": "make it better"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["iteration"] == 1
        assert body["summary"] == "Refined App.tsx"
        assert body["changed_files"] == ["src/App.tsx"]
        assert body["updated_files"]["src/App.tsx"] == updated_src

        # Disk should now contain the new content
        on_disk = (project_dir / "src" / "App.tsx").read_text(encoding="utf-8")
        assert on_disk == updated_src

    def test_refinement_history_endpoint(self, client_with_patched_jobstore, seeded_job):
        import main

        job_id, _, _ = seeded_job
        main.JOB_STORE.append_refinement(
            job_id,
            {
                "iteration": 1,
                "prompt": "hi",
                "summary": "ok",
                "changed_files": ["src/App.tsx"],
                "written_files": ["src/App.tsx"],
            },
        )

        response = client_with_patched_jobstore.get(
            f"/api/refine/{job_id}/history"
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["count"] == 1
        assert body["history"][0]["prompt"] == "hi"

    def test_history_returns_404_for_unknown_job(self, client_with_patched_jobstore):
        response = client_with_patched_jobstore.get(
            "/api/refine/no-such-job/history"
        )
        assert response.status_code == 404

    def test_max_iterations_enforced(self, monkeypatch, client_with_patched_jobstore, seeded_job):
        import main

        job_id, _, _ = seeded_job
        # Append 20 entries already (the default cap)
        for i in range(20):
            main.JOB_STORE.append_refinement(
                job_id,
                {"iteration": i + 1, "prompt": f"refine {i}", "summary": "x",
                 "changed_files": [], "written_files": []},
            )

        response = client_with_patched_jobstore.post(
            f"/api/refine/{job_id}",
            json={"prompt": "final refine"},
        )
        assert response.status_code == 429
        assert "Maximum" in response.json()["detail"]


class TestValidationConstants:
    def test_validation_imports(self):
        from validation import (
            DEFAULT_MAX_REFINEMENT_ITERATIONS,
            MAX_REFINE_PROMPT_LENGTH,
            MAX_REFINE_TARGET_FILES,
        )
        assert DEFAULT_MAX_REFINEMENT_ITERATIONS == 20
        assert MAX_REFINE_PROMPT_LENGTH == 4000
        assert MAX_REFINE_TARGET_FILES == 100
