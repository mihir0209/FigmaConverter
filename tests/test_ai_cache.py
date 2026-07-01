"""Tests for the SQLite-backed AI response cache."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from processors.ai_cache import AICache, _cache_key, get_cache


@pytest.fixture
def cache(tmp_path: Path) -> AICache:
    db = tmp_path / "test_cache.db"
    return AICache(db_path=db, ttl=3600)


class TestCacheKey:
    def test_consistent_across_calls(self):
        k1 = _cache_key("abc", "frame1", "react", "tailwind")
        k2 = _cache_key("abc", "frame1", "react", "tailwind")
        assert k1 == k2

    def test_differs_on_file_key(self):
        k1 = _cache_key("abc", "frame1", "react")
        k2 = _cache_key("xyz", "frame1", "react")
        assert k1 != k2

    def test_differs_on_style(self):
        k1 = _cache_key("abc", "frame1", "react", "css")
        k2 = _cache_key("abc", "frame1", "react", "tailwind")
        assert k1 != k2


class TestAICache:
    def test_set_and_get(self, cache: AICache):
        key = _cache_key("abc", "f1", "react")
        payload = {"files": {"Comp.jsx": "..."}, "frame_name": "Comp"}
        cache.set(key, payload)
        assert cache.get(key) == payload

    def test_miss_returns_none(self, cache: AICache):
        assert cache.get("nonexistent") is None

    def test_expired_entry(self, cache: AICache):
        cache._ttl = -1  # expire immediately
        cache.set("k", {"v": 1})
        assert cache.get("k") is None

    def test_delete(self, cache: AICache):
        cache.set("k", {"v": 1})
        cache.delete("k")
        assert cache.get("k") is None

    def test_clear(self, cache: AICache):
        cache.set("k1", {"v": 1})
        cache.set("k2", {"v": 2})
        cache.clear()
        assert cache.get("k1") is None
        assert cache.get("k2") is None

    def test_overwrite(self, cache: AICache):
        key = _cache_key("abc", "f1", "react")
        cache.set(key, {"v": 1})
        cache.set(key, {"v": 2})
        assert cache.get(key) == {"v": 2}

    def test_close_twice(self, cache: AICache):
        cache.close()
        cache.close()  # should not raise


class TestGetCache:
    @pytest.fixture(autouse=True)
    def _reset_singleton(self):
        import processors.ai_cache as mod
        mod._cache_instance = None
        yield
        mod._cache_instance = None

    @patch.dict(os.environ, {"AI_CACHE_ENABLED": "true", "AI_CACHE_TTL_DAYS": "1"})
    def test_enabled_returns_instance(self):
        instance = get_cache()
        assert instance is not None
        assert isinstance(instance, AICache)

    @patch.dict(os.environ, {"AI_CACHE_ENABLED": "false"})
    def test_disabled_returns_none(self):
        assert get_cache() is None

    @patch.dict(os.environ, {"AI_CACHE_ENABLED": "", "AI_CACHE_TTL_DAYS": ""})
    def test_empty_env_var_defaults_disabled(self):
        assert get_cache() is None

    @patch.dict(os.environ, {"AI_CACHE_ENABLED": "true", "AI_CACHE_TTL_DAYS": "xyz"})
    def test_invalid_ttl_falls_back(self):
        instance = get_cache()
        assert instance is not None
        assert instance._ttl == 7 * 24 * 3600
