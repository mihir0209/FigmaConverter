"""Tests for the JobStore durability layer."""

import sqlite3
from datetime import datetime, timezone, timedelta

import pytest

import main


@pytest.fixture
def fresh_store(tmp_path):
    db_path = tmp_path / "jobs.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(main.JobStore.SCHEMA)
    return main.JobStore(db_path)


class TestJobStoreLifecycle:
    def test_create_then_get(self, fresh_store):
        fresh_store.create("job-1", "queued", idempotency="abc")
        record = fresh_store.get("job-1")
        assert record["status"] == "queued"
        assert record["progress"] == 0

    def test_create_rejects_duplicate_idempotency(self, fresh_store):
        fresh_store.create("job-1", "queued", idempotency="abc")
        with pytest.raises(Exception):
            fresh_store.create("job-2", "queued", idempotency="abc")

    def test_update_progress_and_status(self, fresh_store):
        fresh_store.create("job-1", "queued")
        fresh_store.update("job-1", progress=42, status="processing", message="working")
        record = fresh_store.get("job-1")
        assert record["status"] == "processing"
        assert record["progress"] == 42
        assert record["message"] == "working"

    def test_update_serialises_result_dict(self, fresh_store):
        fresh_store.create("job-1", "queued")
        fresh_store.update("job-1", result={"framework": "react", "files_generated": 5})
        record = fresh_store.get("job-1")
        assert record["result"]["framework"] == "react"
        assert record["result"]["files_generated"] == 5

    def test_find_by_idempotency_returns_existing(self, fresh_store):
        fresh_store.create("job-1", "queued", idempotency="duplicated-payload")
        result = fresh_store.find_by_idempotency("duplicated-payload")
        assert result["id"] == "job-1"


class TestJobStoreCleanup:
    def test_cleanup_older_than_removes_stale_only(self, fresh_store):
        now = datetime.now(timezone.utc)
        old_ts = (now - timedelta(days=14)).isoformat()
        new_ts = now.isoformat()
        with sqlite3.connect(str(fresh_store._db_path)) as conn:
            conn.execute(
                "INSERT INTO jobs(id, status, progress, message, created_at, updated_at) "
                "VALUES (?, 'completed', 100, '', ?, ?)",
                ("old", old_ts, old_ts),
            )
            conn.execute(
                "INSERT INTO jobs(id, status, progress, message, created_at, updated_at) "
                "VALUES (?, 'completed', 100, '', ?, ?)",
                ("new", new_ts, new_ts),
            )
        removed = fresh_store.cleanup_older_than(7)
        assert removed == 1
        assert fresh_store.get("old") is None
        assert fresh_store.get("new") is not None
