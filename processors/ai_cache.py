"""SQLite-backed AI response cache for generated code.

Cache key is SHA-256 of (figma_file_key, frame_id, framework, style_engine).
Default TTL is 7 days. Opt-in via ``AI_CACHE_ENABLED=true`` env var.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional


_DEFAULT_DB_PATH = Path("data/state/ai_cache.db")
_DEFAULT_TTL_SECONDS = 7 * 24 * 3600


def _cache_key(
    file_key: str,
    frame_id: str,
    framework: str,
    style_engine: Optional[str] = None,
) -> str:
    raw = f"{file_key}|{frame_id}|{framework}|{style_engine or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class AICache:
    """Thread-safe, SQLite-backed cache for AI-generated code responses."""

    def __init__(self, db_path: Optional[Path] = None, ttl: int = _DEFAULT_TTL_SECONDS):
        self._db_path = db_path or _DEFAULT_DB_PATH
        self._ttl = ttl
        self._lock = threading.Lock()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS ai_cache ("
            "  cache_key TEXT PRIMARY KEY,"
            "  response TEXT NOT NULL,"
            "  created_at REAL NOT NULL"
            ")"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ai_cache_key ON ai_cache(cache_key)"
        )
        self._conn.commit()

    def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Return cached response if present and not expired, else None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT response, created_at FROM ai_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()

        if row is None:
            return None

        age = time.time() - row["created_at"]
        if age > self._ttl:
            self.delete(cache_key)
            return None

        return json.loads(row["response"])

    def set(self, cache_key: str, response: Dict[str, Any]) -> None:
        """Store a response in the cache."""
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO ai_cache (cache_key, response, created_at) "
                "VALUES (?, ?, ?)",
                (cache_key, json.dumps(response), time.time()),
            )
            self._conn.commit()

    def delete(self, cache_key: str) -> None:
        """Remove a single cache entry."""
        with self._lock:
            self._conn.execute("DELETE FROM ai_cache WHERE cache_key = ?", (cache_key,))
            self._conn.commit()

    def clear(self) -> None:
        """Wipe the entire cache."""
        with self._lock:
            self._conn.execute("DELETE FROM ai_cache")
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()


# Module-level singleton (enabled by env var)
_cache_instance: Optional[AICache] = None
_cache_lock = threading.Lock()


def get_cache() -> Optional[AICache]:
    """Return the global AICache singleton if AI_CACHE_ENABLED=true."""
    global _cache_instance
    if _cache_instance is None:
        enabled = os.getenv("AI_CACHE_ENABLED", "false").lower() == "true"
        if not enabled:
            return None
        with _cache_lock:
            if _cache_instance is None:
                ttl = int(os.getenv("AI_CACHE_TTL_DAYS", "7")) * 24 * 3600
                _cache_instance = AICache(ttl=ttl)
    return _cache_instance
