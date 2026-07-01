"""Tests for the background worker and JobStore queue methods."""

from __future__ import annotations

from pathlib import Path

import pytest

from main import JobStore


@pytest.fixture
def store(tmp_path: Path) -> JobStore:
    return JobStore(tmp_path / "test_worker.db")


class TestJobQueue:
    def test_claim_queued_fifo(self, store: JobStore):
        store.create("job1", "first", priority="high")
        store.create("job2", "second", priority="high")
        assert store.claim_queued("worker-1") == "job1"
        assert store.claim_queued("worker-2") == "job2"

    def test_claim_priority_order(self, store: JobStore):
        store.create("low1", "low", priority="low")
        store.create("high1", "high", priority="high")
        assert store.claim_queued("w") == "high1"

    def test_claim_returns_none_when_empty(self, store: JobStore):
        assert store.claim_queued("w") is None

    def test_claim_only_queued(self, store: JobStore):
        store.create("j1", "test", priority="high")
        store.claim_queued("w")  # claims j1
        assert store.claim_queued("w") is None  # nothing left

    def test_cancel_queued_job(self, store: JobStore):
        store.create("j1", "test")
        assert store.cancel("j1") is True
        assert store.get("j1")["status"] == "cancelled"

    def test_cancel_completed_job(self, store: JobStore):
        store.create("j1", "test")
        store.update("j1", status="completed")
        assert store.cancel("j1") is False

    def test_cancel_nonexistent(self, store: JobStore):
        assert store.cancel("nope") is False

    def test_increment_retry(self, store: JobStore):
        store.create("j1", "test", priority="high")
        store.claim_queued("w")  # status -> processing
        assert store.increment_retry("j1") is True  # retry 1/3
        assert store.get("j1")["status"] == "queued"
        assert store.get("j1")["retry_count"] == 1

    def test_increment_retry_exhaustion(self, store: JobStore):
        store.create("j1", "test")
        conn = store._connect()
        try:
            conn.execute(
                "UPDATE jobs SET status = 'processing', retry_count = 2, max_retries = 3 "
                "WHERE id = 'j1'"
            )
            conn.commit()
        finally:
            conn.close()
        assert store.increment_retry("j1") is False
        assert store.get("j1")["status"] == "failed"
