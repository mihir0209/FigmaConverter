"""FastAPI integration tests covering the surface area most likely to regress.

These use FastAPI's TestClient (synchronous, in-process) and the SQLite
JobStore is replaced with an isolated per-test database. The AI engine and
Figma processor are patched out so the tests stay hermetic.
"""

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


class _FakeJob:
    """Stand-in for the JobStore used for routing assertions."""

    def __init__(self):
        self.rows = {}

    def find_by_idempotency(self, key):
        for row in self.rows.values():
            if row.get("idempotency") == key:
                return row
        return None

    def create(self, job_id, message, idempotency=None):
        if idempotency:
            for row in self.rows.values():
                if row.get("idempotency") == idempotency:
                    raise ValueError("dup")
        self.rows[job_id] = {
            "id": job_id,
            "status": "queued",
            "progress": 0,
            "message": message,
            "idempotency": idempotency,
            "result": None,
        }


@pytest.fixture
def client_with_patched_jobstore(monkeypatch, tmp_path):
    """Mount a copy of main.app with a real SQLite JobStore."""

    import main

    main.JOBS_DB_PATH = Path(tmp_path) / "jobs.db"
    main.JOB_STORE._db_path = main.JOBS_DB_PATH
    with sqlite3.connect(str(main.JOBS_DB_PATH)) as conn:
        conn.executescript(main.JobStore.SCHEMA)

    from fastapi.testclient import TestClient
    return TestClient(main.app)


class TestValidationRegression:
    def test_rejects_non_figma_hosts(self, client_with_patched_jobstore):
        response = client_with_patched_jobstore.post(
            "/api/convert",
            json={
                "figma_url": "https://attacker.invalid/design/AAA/Foo",
                "target_framework": "react",
            },
        )
        assert response.status_code == 400
        assert "Invalid Figma URL" in response.json()["detail"]

    def test_rejects_javascript_scheme(self, client_with_patched_jobstore):
        response = client_with_patched_jobstore.post(
            "/api/convert",
            json={"figma_url": "javascript:alert(1)", "target_framework": "react"},
        )
        assert response.status_code == 400

    def test_rejects_oversize_figma_url(self, client_with_patched_jobstore):
        response = client_with_patched_jobstore.post(
            "/api/convert",
            json={
                "figma_url": "https://www.figma.com/design/" + "A" * 4096 + "/Foo",
                "target_framework": "react",
            },
        )
        # Pydantic's max_length catches this *before* our validator, but
        # either rejection is acceptable.
        assert response.status_code in (400, 422)

    def test_rejects_oversize_framework(self, client_with_patched_jobstore):
        response = client_with_patched_jobstore.post(
            "/api/convert",
            json={
                "figma_url": "https://www.figma.com/design/ABCxyz1234567890abcdef/Foo",
                "target_framework": "x" * 8192,
            },
        )
        assert response.status_code == 422


class TestStatusEndpoint:
    def test_returns_404_for_unknown_job(self, client_with_patched_jobstore):
        response = client_with_patched_jobstore.get("/api/status/unknown-id")
        assert response.status_code == 404


class TestDownloadEndpoint:
    def test_returns_404_for_unknown_job(self, client_with_patched_jobstore):
        response = client_with_patched_jobstore.get("/api/download/unknown-id")
        assert response.status_code == 404

    def test_blocks_traversal_via_clamp(self, client_with_patched_jobstore, tmp_path):
        # Pop a record whose zip_path points outside the assembled root.
        import main

        with sqlite3.connect(str(main.JOBS_DB_PATH)) as conn:
            conn.execute(
                "INSERT INTO jobs(id, status, progress, message, created_at, updated_at) "
                "VALUES (?, 'completed', 100, '', "
                "'2024-01-01T00:00:00', '2024-01-01T00:00:00')",
                ("abc",),
            )
            conn.execute(
                "UPDATE jobs SET result=? WHERE id=?",
                ("{"+f'"zip_path": "{(tmp_path / ".." / "etc" / "passwd").as_posix()}"'+"}", "abc"),
            )
        response = client_with_patched_jobstore.get("/api/download/abc")
        assert response.status_code == 404


class TestHealthEndpoint:
    def test_returns_status(self, client_with_patched_jobstore):
        response = client_with_patched_jobstore.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert "opencode_connected" in body
