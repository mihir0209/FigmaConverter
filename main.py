"""Figma-to-Code Converter — FastAPI service.

The HTTP surface is intentionally small: enqueue a conversion, poll for status,
download the resulting ZIP. All heavy lifting (Figma scraping, AI code
generation, dependency reconciliation, project assembly) is delegated to the
modules in `ai_engine/`, `processors/`, `detectors/`, and `prompting/`.

This file is the glue: configuration, request validation, job lifecycle, and
HTTP routes. It deliberately contains no AI prompt building; that lives in
`prompting/` and is consumed via `prompting.orchestrators`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import dotenv
import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from models import (
    RefinementRequest,
    RefinementResponse,
)

from prompting import (
    discover_framework_structure,
    generate_app_architecture_with_ai,
    generate_enhanced_frame_code_with_ai,
    generate_main_app_with_ai,
    reconcile_dependencies_with_ai,
    refine_code_with_ai,
)
from prompting.framework_utils import (
    get_app_file_paths,
    get_component_file_path,
    get_component_extension,
    get_default_dependencies,
)
from processors.ai_cache import get_cache
from processors.enhanced_figma_processor import EnhancedFigmaProcessor
from processors.project_assembler import ProjectAssembler
from processors.workspace_builder import build_workspace
from parsers.ai_response_parser import AIResponseParser
from detectors.ai_framework_detector import AIFrameworkDetector
from validation import (
    DEFAULT_MAX_REFINEMENT_ITERATIONS,
    MAX_FIGMA_URL_LENGTH,
    MAX_FRAMEWORK_LENGTH,
    MAX_PAT_TOKEN_LENGTH,
    MAX_REFINE_PROMPT_LENGTH,
    MAX_REFINE_TARGET_FILES,
    clamp_zip_path,
    validate_figma_url,
)

# --------------------------------------------------------------------------- #
# Startup provider endpoint validation
# --------------------------------------------------------------------------- #


async def _validate_provider_endpoints() -> None:
    """Verify opencode serve is running at startup."""
    try:
        import httpx

        from processors.opencode_adapter import OpenCodeAdapter

        url = OpenCodeAdapter._server_url() + "/global/health"
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                log.warning("opencode serve not reachable at %s", url)
            else:
                data = resp.json()
                log.info(
                    "Connected to opencode serve v%s",
                    data.get("version", "?"),
                )
    except Exception as exc:
        log.warning("Provider endpoint validation failed: %s", exc)


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

dotenv.load_dotenv()

MAX_THREADS = 3
MAX_FRAMES_PER_JOB = 50
JOB_TTL_DAYS = 7
DATA_DIR = Path("data")
STATE_DIR = DATA_DIR / "state"
JOBS_DB_PATH = STATE_DIR / "jobs.db"
ASSEMBLED_ROOT = DATA_DIR / "assembled_projects"

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("figma_converter")


def _read_max_threads() -> int:
    raw = os.getenv("MAX_THREADS")
    if raw is None or raw == "":
        return MAX_THREADS
    try:
        value = int(raw)
        return max(1, value)
    except ValueError:
        log.warning("Invalid MAX_THREADS=%r, falling back to %s", raw, MAX_THREADS)
        return MAX_THREADS


MAX_THREADS = _read_max_threads()


# --------------------------------------------------------------------------- #
# Job store (SQLite, durable across restarts)
# --------------------------------------------------------------------------- #


class JobStore:
    """Tiny thread-safe store for conversion jobs.

    Replaces the previous in-memory dict so a server restart doesn't drop
    in-flight work. Two operations are guarded by a single lock — the store is
    driven by background tasks that run sequentially anyway, so the contention
    floor is fine.
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS jobs (
        id           TEXT PRIMARY KEY,
        status       TEXT NOT NULL,
        progress     INTEGER NOT NULL DEFAULT 0,
        message      TEXT NOT NULL DEFAULT '',
        result       TEXT,
        error        TEXT,
        created_at   TEXT NOT NULL,
        updated_at   TEXT NOT NULL,
        idempotency  TEXT UNIQUE,
        refinement_history TEXT,
        priority     TEXT NOT NULL DEFAULT 'high',
        retry_count  INTEGER NOT NULL DEFAULT 0,
        max_retries  INTEGER NOT NULL DEFAULT 3,
        worker_id    TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);
    """

    REFINEMENT_SCHEMA_UPGRADE = (
        "ALTER TABLE jobs ADD COLUMN refinement_history TEXT"
    )

    def __init__(self, db_path: Path) -> None:
        self._lock = threading.Lock()
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(self.SCHEMA)
            self._ensure_missing_columns(conn)

    def _ensure_missing_columns(self, conn: sqlite3.Connection) -> None:
        try:
            cols = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(jobs)").fetchall()
            }
        except sqlite3.DatabaseError:
            return
        upgrades = {
            "refinement_history": "ALTER TABLE jobs ADD COLUMN refinement_history TEXT",
            "priority": "ALTER TABLE jobs ADD COLUMN priority TEXT NOT NULL DEFAULT 'high'",
            "retry_count": "ALTER TABLE jobs ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0",
            "max_retries": "ALTER TABLE jobs ADD COLUMN max_retries INTEGER NOT NULL DEFAULT 3",
            "worker_id": "ALTER TABLE jobs ADD COLUMN worker_id TEXT",
        }
        for col, stmt in upgrades.items():
            if col not in cols:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError:
                    pass
        # Index on the queue-priority columns (created after ALTER TABLE above)
        try:
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_queued "
                "ON jobs(status, priority, created_at)"
            )
        except sqlite3.OperationalError:
            pass

    def _connect(self) -> sqlite3.Connection:
        # check_same_thread=False so BackgroundTasks threads can write; we
        # serialize access with self._lock.
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def create(self, job_id: str, message: str, idempotency: Optional[str] = None,
               priority: str = "high") -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            if idempotency:
                existing = conn.execute(
                    "SELECT id FROM jobs WHERE idempotency = ?", (idempotency,)
                ).fetchone()
                if existing:
                    raise _DuplicateJob(existing["id"])
            conn.execute(
                "INSERT INTO jobs(id, status, progress, message, created_at, updated_at, "
                "idempotency, priority) VALUES (?, 'queued', 0, ?, ?, ?, ?, ?)",
                (job_id, message, now, now, idempotency, priority),
            )

    def get(self, job_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
        if not row:
            return None
        payload = dict(row)
        if payload.get("result"):
            try:
                payload["result"] = json.loads(payload["result"])
            except json.JSONDecodeError:
                pass
        if payload.get("refinement_history"):
            try:
                payload["refinement_history"] = json.loads(payload["refinement_history"])
            except json.JSONDecodeError:
                payload["refinement_history"] = []
        else:
            payload["refinement_history"] = []
        return payload

    def find_by_idempotency(self, idempotency: str) -> Optional[dict]:
        if not idempotency:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE idempotency = ?", (idempotency,)
            ).fetchone()
        return dict(row) if row else None

    def update(self, job_id: str, *, status=None, progress=None, message=None,
               result=None, error=None) -> None:
        sets: list[str] = []
        values: list = []
        if status is not None:
            sets.append("status = ?")
            values.append(status)
        if progress is not None:
            sets.append("progress = ?")
            values.append(int(progress))
        if message is not None:
            sets.append("message = ?")
            values.append(message)
        if result is not None:
            sets.append("result = ?")
            values.append(json.dumps(result))
        if error is not None:
            sets.append("error = ?")
            values.append(error)
        if not sets:
            return
        sets.append("updated_at = ?")
        values.append(datetime.now(timezone.utc).isoformat())
        values.append(job_id)
        with self._lock, self._connect() as conn:
            conn.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE id = ?", values)

    def cleanup_older_than(self, days: int) -> int:
        cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT id, created_at FROM jobs").fetchall()
            stale = []
            for row in rows:
                try:
                    if datetime.fromisoformat(row["created_at"]).timestamp() < cutoff:
                        stale.append(row["id"])
                except ValueError:
                    continue
            if not stale:
                return 0
            placeholders = ",".join("?" for _ in stale)
            conn.execute(f"DELETE FROM jobs WHERE id IN ({placeholders})", stale)
            return len(stale)

    def get_refinement_history(self, job_id: str) -> list[dict]:
        """Return the refinement history for a job, defaulting to ``[]``."""
        record = self.get(job_id)
        if not record:
            return []
        return record.get("refinement_history") or []

    def append_refinement(self, job_id: str, entry: dict) -> list[dict]:
        """Append an entry to the refinement_history log and return the new list."""
        history = self.get_refinement_history(job_id)
        history.append(entry)
        if not entry.get("timestamp"):
            entry = {**entry, "timestamp": datetime.now(timezone.utc).isoformat()}
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET refinement_history = ?, updated_at = ? WHERE id = ?",
                (json.dumps(history), datetime.now(timezone.utc).isoformat(), job_id),
            )
        return history

    def refinement_count(self, job_id: str) -> int:
        """Number of refinement iterations recorded for this job."""
        return len(self.get_refinement_history(job_id))

    def claim_queued(self, worker_id: str) -> Optional[str]:
        """Claim the highest-priority queued job via FIFO within priority."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM jobs WHERE status = 'queued' "
                "ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, "
                "created_at ASC LIMIT 1"
            ).fetchone()
            if not row:
                return None
            conn.execute(
                "UPDATE jobs SET status = 'processing', worker_id = ?, updated_at = ? "
                "WHERE id = ?",
                (worker_id, datetime.now(timezone.utc).isoformat(), row["id"]),
            )
        return row["id"]

    def increment_retry(self, job_id: str) -> bool:
        """Increment retry_count; return True if still within max_retries."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT retry_count, max_retries FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if not row:
                return False
            new_count = row["retry_count"] + 1
            if new_count >= row["max_retries"]:
                conn.execute(
                    "UPDATE jobs SET status = 'failed', error = ?, retry_count = ?, "
                    "updated_at = ? WHERE id = ?",
                    ("Max retries exceeded", new_count,
                     datetime.now(timezone.utc).isoformat(), job_id),
                )
                return False
            conn.execute(
                "UPDATE jobs SET status = 'queued', retry_count = ?, updated_at = ?, "
                "message = 'Retrying...' WHERE id = ?",
                (new_count, datetime.now(timezone.utc).isoformat(), job_id),
            )
            return True

    def cancel(self, job_id: str) -> bool:
        """Cancel a job if it's not completed/failed. Returns True if cancelled."""
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if not row or row["status"] in ("completed", "failed", "cancelled"):
                return False
            conn.execute(
                "UPDATE jobs SET status = 'cancelled', message = 'Cancelled by user', "
                "updated_at = ? WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), job_id),
            )
            return True


class _DuplicateJob(Exception):
    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        super().__init__(job_id)


JOB_STORE = JobStore(JOBS_DB_PATH)


# --------------------------------------------------------------------------- #
# FastAPI app + lifespan
# --------------------------------------------------------------------------- #

app = FastAPI(
    title="Figma-to-Code Converter",
    description="Convert Figma designs to production-ready code",
    version="1.1.0",
)

# CORS is restricted by default. The previous wildcard + credentials combo made
# browsers silently drop the response; explicit allow-list is safer.
ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "").split(",") if origin.strip()]

from fastapi.middleware.cors import CORSMiddleware  # placed after app for clarity

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["http://localhost:8000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# CSP — only allow our own assets + the CDN scripts the template already loads
@app.middleware("http")
async def _security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "font-src 'self' https://cdnjs.cloudflare.com https://fonts.gstatic.com; "
        "img-src 'self' data:;",
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


STATIC_DIR = Path(__file__).parent / "web" / "static"
TEMPLATES_DIR = Path(__file__).parent / "web" / "templates"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


# --------------------------------------------------------------------------- #
# Pydantic request models
# --------------------------------------------------------------------------- #

from pydantic import BaseModel, Field


class ConversionRequest(BaseModel):
    figma_url: str = Field(..., max_length=MAX_FIGMA_URL_LENGTH)
    pat_token: Optional[str] = Field(default=None, max_length=MAX_PAT_TOKEN_LENGTH)
    target_framework: str = Field(..., max_length=MAX_FRAMEWORK_LENGTH)
    include_components: bool = True
    style_engine: Optional[str] = Field(default=None, max_length=50)
    component_library: Optional[str] = Field(default=None, max_length=50)


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #


def _build_design_summary(design_data: dict) -> str:
    """Render a human-readable summary of the Figma file for AI prompts.

    Mirrors the previous in-`main.py` behaviour; kept as its own function so it
    can be unit-tested without spinning up FastAPI.
    """

    frames = design_data.get("frames", [])
    total_components = design_data.get("total_components", 0)
    file_key = design_data.get("file_key", "unknown")

    parts = [
        "=== FIGMA DESIGN COMPREHENSIVE SUMMARY ===\n"
        f"File Key: {file_key}\n"
        f"Total Frames: {len(frames)}\n"
        f"Total Components: {total_components}\n"
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    ]

    for idx, frame in enumerate(frames, 1):
        name = frame.get("name", f"Frame_{idx}")
        frame_id = frame.get("id", "unknown")
        parts.append(f"--- FRAME {idx}: {name} ---\nFrame ID: {frame_id}\n")

        comprehensive = frame.get("comprehensive_data", {})
        if not comprehensive:
            parts.append(f"Components: {len(frame.get('components', []))} components\n\n")
            continue

        counts = comprehensive.get("component_count", {})
        content = comprehensive.get("content", {})
        design_system = comprehensive.get("design_system", {})
        layout = comprehensive.get("layout", {})
        basic = comprehensive.get("basic_info", {})

        dims = basic.get("dimensions", {})
        if dims:
            parts.append(f"Dimensions: {dims.get('width', 0)}x{dims.get('height', 0)}px\n")
        parts.append(
            "Complexities: "
            f"total={counts.get('total', 0)}, "
            f"texts={counts.get('texts', 0)}, "
            f"images={counts.get('images', 0)}, "
            f"buttons={counts.get('buttons', 0) + counts.get('inputs', 0)} "
            f"containers={counts.get('containers', 0)}\n"
        )

        colors = design_system.get("colors", [])
        if colors:
            parts.append("Color Palette: " + ", ".join(colors[:8]) + "\n")

        typography = design_system.get("typography", {})
        parts.append(f"Typography: {len(typography)} font combinations\n")
        parts.append(f"Layout Type: {comprehensive.get('structure', {}).get('layout_type', 'unknown')}\n\n")

    return "".join(parts)


def _preliminary_dependencies(
    framework: str,
    framework_structure: dict,
    style_engine: Optional[str] = None,
    component_library: Optional[str] = None,
) -> dict:
    """Build the baseline dependency set passed into the AI reconciliation."""

    from processors.style_library_matrix import DependencyResolver

    resolver = DependencyResolver(use_cache=True)
    raw = resolver.resolve_to_package_json(framework, style_engine or "", component_library or "")

    deps = {
        "dependencies": {
            "package.json": raw,
        }
    }

    return deps


def generate_framework_code(
    design_data: dict,
    framework: str,
    job_id: str,
    framework_detection: dict,
    style_engine: Optional[str] = None,
    component_library: Optional[str] = None,
    vision_images: Optional[dict] = None,
) -> dict:
    """Drive the full AI code-generation pipeline.

    This implementation deliberately delegates to `prompting.orchestrators`,
    which owns the retry logic and conflict resolution. We keep the same
    high-level return shape as the previous in-file implementation so the
    downstream `ProjectAssembler` keeps working without changes.
    
    Args:
        vision_images: Optional dict mapping frame_id to local file path for vision input.
    """

    ai_engine = AI_engine_singleton.get()
    parser = AIResponseParser()
    ai_cache = get_cache()

    framework_structure = {
        "framework": framework_detection["framework"],
        "structure": framework_detection.get("project_structure", {}),
        "file_conventions": framework_detection.get("file_conventions", {}),
        "technology_stack": framework_detection.get("technology_stack", {}),
    }
    # The detector's `project_structure` is shared verbatim with the
    # `structure` slot expected by every prompt builder.
    framework_structure["structure"] = framework_detection.get("project_structure", {})

    log.info("Framework structure locked: %s (%s)", framework_structure["framework"],
             framework_detection.get("framework_name"))

    JOB_STORE.update(job_id, progress=25, message="Building design summary...")
    design_summary = _build_design_summary(design_data)

    JOB_STORE.update(job_id, progress=35, message="Analyzing application architecture...")
    app_architecture = generate_app_architecture_with_ai(ai_engine, design_summary, framework, parser)
    if not app_architecture:
        log.warning("Architecture analysis returned empty; using fallback")
        app_architecture = {
            "app_architecture": {"app_type": "Multi-page Application", "primary_flow": "Basic navigation"},
            "frame_connections": [],
            "shared_components": [],
            "route_structure": {},
            "app_state": {"global_state": [], "shared_data": []},
        }

    JOB_STORE.update(job_id, progress=45, message="Computing preliminary dependencies...")
    preliminary_deps = _preliminary_dependencies(framework, framework_structure, style_engine, component_library)

    frames = design_data.get("frames", [])
    if not frames:
        return {
            "framework": framework,
            "files": {},
            "main_file": framework_structure.get("structure", {}).get("main_file", "src/App.js"),
            "framework_structure": framework_structure,
            "dependency_resolution": preliminary_deps,
            "dependency_suggestions": [],
        }

    JOB_STORE.update(
        job_id,
        progress=55,
        message=f"Generating code for {len(frames)} frame(s) (threads={MAX_THREADS})...",
    )

    generated_files: dict[str, str] = {}
    dependency_suggestions: list[dict] = []

    if len(frames) == 1:
        frame_id = frames[0].get("id", "")
        frame_vision = [vision_images.get(frame_id)] if vision_images and frame_id in vision_images else None
        result = generate_enhanced_frame_code_with_ai(
            ai_engine, frames[0], framework, job_id, parser, framework_structure,
            app_architecture, design_summary, preliminary_deps, style_engine,
            component_library, ai_cache=ai_cache, vision_images=frame_vision,
        )
        files = result.get("files") or {}
        generated_files.update(files)
        if result.get("dependency_suggestions"):
            dependency_suggestions.append({
                "frame_name": result.get("frame_name"),
                "suggestions": result["dependency_suggestions"],
            })
    else:
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            futures = {
                executor.submit(
                    generate_enhanced_frame_code_with_ai, ai_engine, frame, framework,
                    job_id, parser, framework_structure, app_architecture,
                    design_summary, preliminary_deps, style_engine,
                    component_library, ai_cache,
                    [vision_images.get(frame.get("id", ""))] if vision_images and frame.get("id", "") in vision_images else None,
                ): frame
                for frame in frames
            }
            for future, frame in futures.items():
                try:
                    result = future.result() or {}
                except Exception as exc:  # noqa: BLE001 — log and continue
                    log.error("Frame generation failed for %s: %s", frame.get("name"), exc)
                    continue
                files = result.get("files") or {}
                generated_files.update(files)
                if result.get("dependency_suggestions"):
                    dependency_suggestions.append({
                        "frame_name": result.get("frame_name"),
                        "suggestions": result["dependency_suggestions"],
                    })

    JOB_STORE.update(job_id, progress=75, message="Reconciling dependencies...")
    final_dependencies = preliminary_deps
    if dependency_suggestions:
        reconciled = reconcile_dependencies_with_ai(
            ai_engine, preliminary_deps, dependency_suggestions, framework_structure,
            parser, style_engine=style_engine, component_library=component_library,
        )
        if reconciled:
            final_dependencies = reconciled

    JOB_STORE.update(job_id, progress=85, message="Generating main app shell...")
    main_app_files = generate_main_app_with_ai(
        ai_engine, frames, framework, framework_structure, app_architecture, parser,
    )
    if main_app_files:
        generated_files.update(main_app_files.get("files", {}))

    JOB_STORE.update(job_id, progress=92, message="Extracting design tokens...")
    generated_files = _merge_design_tokens(
        framework, design_data, generated_files, style_engine, component_library
    )

    JOB_STORE.update(job_id, progress=95, message="Generating config files...")

    generated_files = _apply_framework_config(framework, generated_files, frames, framework_structure, style_engine, component_library)

    return {
        "framework": framework,
        "files": generated_files,
        "main_file": framework_structure.get("structure", {}).get("main_file", "src/App.js"),
        "framework_structure": framework_structure,
        "dependency_resolution": final_dependencies,
        "dependency_suggestions": dependency_suggestions,
    }


def _apply_framework_config(
    framework: str,
    files: dict,
    frames: list,
    framework_structure: dict,
    style_engine: Optional[str] = None,
    component_library: Optional[str] = None,
) -> dict:
    """Insert fallback `package.json` / entry-point files when the AI skipped them."""

    if framework in {"react", "vue", "angular", "nextjs"} and "package.json" not in files:
        from processors.component_library_mapper import get_library_dependencies
        from processors.style_library_matrix import DependencyResolver

        ok, warnings, info, error = _validate_style_library_choice(framework, style_engine, component_library)
        if not ok:
            log.warning("Skipping package.json fallback: %s", error)
        else:
            pkg_data = DependencyResolver(use_cache=True).resolve_to_package_json(
                framework, style_engine, component_library
            )
            files["package.json"] = json.dumps(pkg_data, indent=2)

    if framework not in {"html", "html_css_js"}:
        styles_path = "src/index.css"
        if style_engine and style_engine.lower() == "tailwind":
            if styles_path not in files:
                from prompting.style_builders import build_styles
                files[styles_path] = build_styles("tailwind", None)
        elif styles_path not in files:
            files[styles_path] = _basic_css()

    return files


def _validate_style_library_choice(
    framework: str, style: Optional[str], lib: Optional[str],
) -> tuple[bool, list[str], list[str], Optional[str]]:
    """Wrap validate_combination so we can patch / log warnings in one place."""
    from processors.style_library_matrix import validate_combination
    return validate_combination(framework, style, lib)


def _merge_design_tokens(
    framework: str,
    design_data: dict,
    files: dict,
    style_engine: Optional[str],
    component_library: Optional[str] = None,
) -> dict:
    """Extract design tokens and inject the appropriate tokens file into ``files``.

    - For Tailwind v4 the tokens are merged into ``src/index.css`` if present,
      keeping the import + @theme block in sync.
    - For all other style engines a standalone tokens file is added:
      - ``css``      → ``src/tokens.css`` (or ``css/tokens.css`` for plain HTML)
      - ``scss``     → ``src/styles/_tokens.scss``
    Returns ``files`` (mutated + the dict, for chaining).
    """
    try:
        from processors.token_extractor import extract_tokens
        from processors.token_generator import generate_token_file, token_file_path
    except ImportError as exc:  # pragma: no cover — defensive
        log.warning("Token modules unavailable: %s", exc)
        return files

    figma_variables = (design_data or {}).get("design_tokens")
    frames = (design_data or {}).get("frames", []) or []
    tokens = extract_tokens(figma_variables=figma_variables, frames=frames)
    if not tokens.has_tokens():
        return files

    log.info(
        "Design tokens extracted: %d total (source=%s)",
        tokens.token_count,
        tokens.source,
    )

    style = (style_engine or "css").lower()
    target_style_for_tailwind = "tailwind"

    if style == "tailwind":
        # Merge into the existing src/index.css (which carries `@import "tailwindcss";`).
        token_block = generate_token_file(tokens, target_style_for_tailwind)
        default_index = "src/index.css"
        if default_index in files:
            existing = files[default_index]
            if "@theme" in existing:
                # Already has @theme — strip the existing one and replace
                head, _, rest = existing.partition("@theme {")
                if "}" in rest:
                    _, _, tail = rest.partition("}")
                    rest = tail
                files[default_index] = (
                    head.rstrip()
                    + "\n\n"
                    + token_block
                    + rest
                )
            else:
                # Existing CSS file but no @theme — append ours
                files[default_index] = existing.rstrip() + "\n\n" + token_block + "\n"
        else:
            files[default_index] = token_block + "\n"
        return files

    # Non-Tailwind style: standalone tokens file
    tokens_path = token_file_path(framework, style)
    content = generate_token_file(tokens, style)
    if content and tokens_path not in files:
        files[tokens_path] = content + "\n"

    # Component-library-specific theming
    if component_library == "mui" and tokens.has_tokens():
        _inject_mui_theme(files, tokens)
    elif component_library == "antd" and tokens.has_tokens():
        _inject_antd_theme(files, tokens)

    return files


def _inject_mui_theme(files: dict, tokens: Any) -> None:
    """Inject a MUI v5 theme file with tokens as the theme config."""
    from models import TokenCollection, ColorToken

    if not isinstance(tokens, TokenCollection):
        return

    if not tokens.colors:
        return

    palette_lines = []
    for ct in tokens.colors:
        if isinstance(ct, ColorToken):
            palette_lines.append(f'      {ct.name}: "{ct.value}",')

    if not palette_lines:
        return

    theme_content = f"""import {{ createTheme }} from "@mui/material/styles";

const theme = createTheme({{
  palette: {{
{chr(10).join(palette_lines)}
  }},
}});

export default theme;
"""
    theme_path = "src/theme.ts"
    if theme_path not in files:
        files[theme_path] = theme_content


def _inject_antd_theme(files: dict, tokens: Any) -> None:
    """Inject an Ant Design v5 theme config with tokens."""
    from models import TokenCollection, ColorToken

    if not isinstance(tokens, TokenCollection):
        return

    if not tokens.colors:
        return

    token_lines = []
    for ct in tokens.colors:
        if isinstance(ct, ColorToken):
            token_lines.append(f"        {ct.name}: '{ct.value}',")

    if not token_lines:
        return

    theme_content = f"""import {{ ConfigProvider }} from "antd";

const themeConfig = {{
  token: {{
{chr(10).join(token_lines)}
  }},
}};

export default themeConfig;
"""
    theme_path = "src/theme.ts"
    if theme_path not in files:
        files[theme_path] = theme_content


def _react_package_json() -> str:
    return json.dumps(
        {
            "name": "figma-converted-app",
            "version": "0.1.0",
            "private": True,
            "dependencies": {
                "react": "^18.2.0",
                "react-dom": "^18.2.0",
                "react-router-dom": "^6.20.0",
            },
            "devDependencies": {
                "@vitejs/plugin-react": "^4.2.1",
                "vite": "^5.0.8",
                "typescript": "^5.3.3",
                "@types/react": "^18.2.43",
                "@types/react-dom": "^18.2.17",
            },
            "scripts": {
                "dev": "vite",
                "build": "vite build",
                "preview": "vite preview",
            },
        },
        indent=2,
    )


def _vue_package_json() -> str:
    return json.dumps(
        {
            "name": "figma-converted-vue-app",
            "version": "0.1.0",
            "private": True,
            "dependencies": {"vue": "^3.2.13", "vue-router": "^4.0.0"},
            "devDependencies": {
                "@vitejs/plugin-vue": "^4.5.0",
                "vite": "^5.0.8",
                "typescript": "^5.3.3",
            },
            "scripts": {"dev": "vite", "build": "vite build", "preview": "vite preview"},
        },
        indent=2,
    )


def _angular_package_json() -> str:
    return json.dumps(
        {
            "name": "figma-converted-angular-app",
            "version": "0.0.0",
            "private": True,
            "dependencies": {
                "@angular/animations": "^15.2.0",
                "@angular/common": "^15.2.0",
                "@angular/core": "^15.2.0",
                "@angular/forms": "^15.2.0",
                "@angular/platform-browser": "^15.2.0",
                "@angular/router": "^15.2.0",
                "rxjs": "~7.8.0",
                "tslib": "^2.3.0",
                "zone.js": "~0.12.0",
            },
            "devDependencies": {
                "@angular-devkit/build-angular": "^15.2.0",
                "@angular/cli": "~15.2.0",
                "typescript": "~4.9.4",
            },
        },
        indent=2,
    )


def _basic_css() -> str:
    return (
        "body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', "
        "Roboto, sans-serif; -webkit-font-smoothing: antialiased; }\n"
        "code { font-family: source-code-pro, Menlo, Monaco, Consolas, monospace; }\n"
    )


# --------------------------------------------------------------------------- #
# Background processing
# --------------------------------------------------------------------------- #

class _OpenCodeSingleton:
    """Deferred adapter binding — delegates AI inference to opencode serve."""

    def __init__(self) -> None:
        self._adapter = None

    def get(self):
        if self._adapter is None:
            from processors.opencode_adapter import OpenCodeAdapter

            self._adapter = OpenCodeAdapter(verbose=False)
        return self._adapter


AI_engine_singleton = _OpenCodeSingleton()


def _is_cancelled(job_id: str) -> bool:
    """Return True if the job has been cancelled (caller should stop work)."""
    record = JOB_STORE.get(job_id)
    return record is not None and record.get("status") == "cancelled"


def _idempotency_key(payload: ConversionRequest) -> str:
    """Stable hash so duplicate POSTs share a job_id while the first runs."""

    raw = json.dumps(
        {"url": payload.figma_url, "framework": payload.target_framework},
        sort_keys=True,
        separators=(",", ":"),
    )
    import hashlib

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def process_conversion(
    job_id: str,
    figma_url: str,
    pat_token: Optional[str],
    target_framework: str,
    include_components: bool,
    style_engine: Optional[str] = None,
    component_library: Optional[str] = None,
) -> None:
    """Convert a Figma URL into a ZIP, updating ``JobStore`` as we go."""

    try:
        if _is_cancelled(job_id):
            return

        JOB_STORE.update(
            job_id, status="processing", progress=10,
            message="Detecting framework...",
        )

        detector = AIFrameworkDetector()
        framework_detection = await asyncio.to_thread(detector.detect_framework, target_framework)
        if not framework_detection.get("success"):
            raise ValueError(f"Could not determine framework from: {target_framework!r}")

        if _is_cancelled(job_id):
            return

        detected_framework = framework_detection["framework"]
        framework_name = framework_detection.get("framework_name", detected_framework)
        JOB_STORE.update(
            job_id, progress=20,
            message=f"Detected framework: {framework_name}. Fetching Figma file...",
        )

        processor = EnhancedFigmaProcessor(
            api_token=pat_token or os.getenv("FIGMA_API_TOKEN")
        )
        try:
            design_data = await processor.async_process_frame_by_frame(figma_url, include_components)

            if _is_cancelled(job_id):
                return

            frames_count = len(design_data.get("frames", []))
            if frames_count > MAX_FRAMES_PER_JOB:
                raise ValueError(
                    f"Design contains {frames_count} frames; the limit is {MAX_FRAMES_PER_JOB}."
                )

            # Export frame screenshots for vision input (reuse same processor)
            vision_images = {}
            try:
                file_key = processor.extract_file_key_from_url(figma_url)
                if file_key:
                    frames = design_data.get("frames", [])
                    vision_images = processor.export_frame_screenshots(
                        file_key, frames, scale=2.0
                    )
                    log.info("Exported %d frame screenshots for vision input", len(vision_images))
            except Exception as exc:
                log.warning("Failed to export frame screenshots for vision: %s", exc)
        finally:
            processor.close()

        # Build workspace with parsed design data for AI consumption
        workspace_dir = None
        try:
            workspace_dir = build_workspace(design_data, vision_images, job_id)
            log.info("Workspace built: %s", workspace_dir)
        except Exception as exc:
            log.warning("Failed to build workspace: %s", exc)

        JOB_STORE.update(
            job_id, progress=50,
            message=f"Generating {framework_name} code for {frames_count} frame(s)...",
        )

        code_result = await asyncio.to_thread(
            generate_framework_code, design_data, detected_framework, job_id,
            framework_detection, style_engine, component_library, vision_images,
        )

        if _is_cancelled(job_id):
            return

        JOB_STORE.update(
            job_id, progress=90,
            message="Assembling project and creating ZIP archive...",
        )

        components_result = {
            "total_components": design_data.get("design_info", {}).get("total_components", 0),
            "components": design_data.get("component_references", {}),
            "component_manifest_path": design_data.get("component_manifest_path"),
        }

        assembler = ProjectAssembler()
        assembly_result = await asyncio.to_thread(
            assembler.assemble_project,
            code_result=code_result,
            components_result=components_result,
            framework=detected_framework,
            job_id=job_id,
            style_engine=style_engine,
            component_library=component_library,
        )

        if _is_cancelled(job_id):
            return

        JOB_STORE.update(
            job_id, status="completed", progress=100,
            message="Conversion completed successfully",
            result={
                "framework": detected_framework,
                "framework_name": framework_name,
                "original_request": target_framework,
                "detection_confidence": framework_detection.get("confidence", 0.5),
                "files_generated": code_result.get("total_files") or len(code_result.get("files", {})),
                "components_collected": components_result.get("total_components", 0),
                "output_path": assembly_result.get("project_dir"),
                "zip_path": assembly_result.get("zip_path"),
                "project_name": assembly_result.get("project_name"),
                "file_list": sorted(list(code_result.get("files", {}).keys())),
            },
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("Conversion failed for job %s", job_id)
        JOB_STORE.update(
            job_id, status="failed",
            message=f"Conversion failed: {exc}",
            error=str(exc),
        )


# --------------------------------------------------------------------------- #
# Refinement (post-generation natural-language code edits)
# --------------------------------------------------------------------------- #


def _read_project_files(project_dir: Path, rel_paths: List[str]) -> Dict[str, str]:
    """Read the listed files (relative paths) from the assembly directory.

    Returns a dict keyed by relative path. Missing files are silently skipped.
    """
    files: Dict[str, str] = {}
    for rel_path in rel_paths:
        full = (project_dir / rel_path).resolve()
        # Detach zip-slip style safety: only read from under project_dir
        try:
            full.relative_to(project_dir.resolve())
        except ValueError:
            log.warning("Refinement: %s escapes project dir, skipping", rel_path)
            continue
        if not full.is_file():
            continue
        try:
            files[rel_path] = full.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            log.warning("Refinement: failed to read %s", rel_path, exc_info=True)
            continue
    return files


def _write_project_files(project_dir: Path, files: Dict[str, str]) -> List[str]:
    """Write `files` (relative paths) to ``project_dir``; return paths written."""
    written: List[str] = []
    for rel_path, content in files.items():
        if not isinstance(content, str):
            log.warning("Refinement: skipping non-str content for %s", rel_path)
            continue
        full = project_dir / rel_path
        try:
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content, encoding="utf-8")
            written.append(rel_path)
        except OSError:
            log.warning("Refinement: failed to write %s", rel_path, exc_info=True)
    return written


def _resolve_project_dir(record: dict) -> Optional[Path]:
    """Pick the on-disk project directory for a completed job, if any."""
    result = record.get("result") or {}
    project_dir_str = result.get("output_path")
    if not project_dir_str:
        return None
    path = Path(project_dir_str)
    return path if path.is_dir() else None


def process_refinement(
    job_id: str,
    payload: "RefinementRequest",
    ai_engine,
) -> Dict:
    """Run a refinement iteration and persist the updates.

    Returns a dict shaped like the ``RefinementResponse`` body. Raises
    ``ValueError`` for known recoverable errors that should turn into 4xx
    responses in the HTTP layer.
    """
    record = JOB_STORE.get(job_id)
    if not record:
        raise ValueError("Job not found")

    project_dir = _resolve_project_dir(record)
    if project_dir is None:
        raise ValueError(
            "Job has no on-disk project to refine — generate code first."
        )

    result = record.get("result") or {}
    framework = result.get("framework") or "react"
    file_list = result.get("file_list") or []

    if not file_list:
        raise ValueError("Job has no files to refine.")

    target_files = payload.target_files
    if target_files is not None:
        target_files = list(target_files)
        # Cap target list size to prevent prompt injection
        if len(target_files) > MAX_REFINE_TARGET_FILES:
            raise ValueError(
                f"target_files may not exceed {MAX_REFINE_TARGET_FILES} entries."
            )
        valid_set = set(file_list)
        invalid = [p for p in target_files if p not in valid_set]
        if invalid:
            raise ValueError(
                f"target_files contains unknown paths: {invalid[:3]}…"
            )

    current_files = _read_project_files(project_dir, file_list)

    history = JOB_STORE.get_refinement_history(job_id)
    iteration = len(history) + 1
    previous_summary = history[-1].get("summary", "") if history else ""

    JOB_STORE.update(
        job_id, message=f"Refining code (iteration {iteration})…",
        progress=max(95, 90 - iteration),
    )

    try:
        outcome = refine_code_with_ai(
            ai_engine,
            current_files=current_files,
            user_prompt=payload.prompt,
            framework=framework,
            target_files=target_files,
            refinement_iteration=iteration,
            previous_summary=previous_summary,
        )
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    updated = outcome["updated_files"]
    changed = outcome["changed_files"]
    summary = outcome["summary"]

    written = _write_project_files(project_dir, updated)

    entry = {
        "iteration": iteration,
        "prompt": payload.prompt,
        "changed_files": changed,
        "written_files": written,
        "summary": summary,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    JOB_STORE.append_refinement(job_id, entry)

    # Update result.file_list (add new files, drop deleted) and bump refined count
    result_files = set(file_list)
    for rel_path in updated.keys():
        result_files.add(rel_path)
    result["file_list"] = sorted(result_files)
    result["refined_files_count"] = len(written)
    JOB_STORE.update(
        job_id,
        result=result,
        message=f"Refinement {iteration} applied — {len(written)} file(s) updated",
    )

    new_zip_path = None
    try:
        from processors.project_assembler import ProjectAssembler
        assembler = ProjectAssembler()
        project_name = result.get("project_name") or project_dir.name
        zip_candidate = assembler._create_project_zip(
            project_dir, f"{project_name}_refined_{iteration}"
        )
        new_zip_path = str(zip_candidate)
        result["zip_path"] = new_zip_path
        JOB_STORE.update(job_id, result=result)
    except Exception as exc:  # noqa: BLE001
        log.warning("Refinement: failed to recreate zip (%s)", exc)
        new_zip_path = result.get("zip_path")

    return {
        "job_id": job_id,
        "iteration": iteration,
        "summary": summary,
        "updated_files": updated,
        "changed_files": written,
        "zip_path": new_zip_path,
    }


# --------------------------------------------------------------------------- #
# HTTP routes
# --------------------------------------------------------------------------- #


@app.get("/", response_class=HTMLResponse)
async def root(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html")


@app.get("/health")
@app.get("/api/health")
async def health() -> dict:
    engine = AI_engine_singleton.get()
    status = engine.get_status()
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ai_providers_available": status.get("providers_available", 0),
        "opencode_version": status.get("version", ""),
        "opencode_connected": status.get("connected", False),
        "job_store": str(JOBS_DB_PATH),
    }


@app.get("/api/check-token")
async def check_figma_token() -> dict:
    """Check Figma token status and rate limits.

    Probes a Tier 1 endpoint (GET /v1/files) to read rate-limit headers.
    Even with a non-existent file key, a 429 response contains seat type info.
    """
    import httpx as _httpx

    token = os.getenv("FIGMA_API_TOKEN")
    if not token:
        return {"error": "No FIGMA_API_TOKEN configured"}

    headers = {"X-Figma-Token": token}

    try:
        async with _httpx.AsyncClient(timeout=10.0) as client:
            # Step 1: validate token
            me_resp = await client.get("https://api.figma.com/v1/me", headers=headers)
            if me_resp.status_code == 403:
                return {"error": "Token is invalid or revoked", "http_status": 403}
            user = me_resp.json() if me_resp.status_code == 200 else {}

            # Step 2: probe Tier 1 endpoint to read rate-limit headers
            # Use a dummy file key — 404/403 still carries rate-limit headers
            probe_resp = await client.get(
                "https://api.figma.com/v1/files/000000000000000000000",
                headers=headers,
            )

            h = probe_resp.headers
            result = {
                "http_status": probe_resp.status_code,
                "token_valid": True,
                "user": {
                    "id": user.get("id"),
                    "email": user.get("email"),
                    "handle": user.get("handle"),
                },
                "rate_limit_type": h.get("x-figma-rate-limit-type", "?"),
                "plan_tier": h.get("x-figma-plan-tier", "?"),
                "rate_limit_remaining": h.get("x-rate-limit-remaining", "?"),
                "rate_limit_limit": h.get("x-rate-limit-limit", "?"),
                "rate_limit_reset": h.get("x-rate-limit-reset", "?"),
            }

            seat = result["rate_limit_type"]
            plan = result["plan_tier"]

            if probe_resp.status_code == 429:
                retry_after = h.get("retry-after", "?")
                upgrade = h.get("x-figma-upgrade-link", "")
                result["error"] = "Rate limited"
                result["retry_after"] = retry_after
                result["upgrade_link"] = upgrade
                if seat == "low":
                    result["message"] = (
                        f"View/Collab seat on {plan} plan. "
                        f"Tier 1 (file/image) endpoints: 6 requests/MONTH. "
                        f"Upgrade: {upgrade or 'https://www.figma.com/settings'}"
                    )
                else:
                    result["message"] = (
                        f"Dev/Full seat on {plan} plan. "
                        f"Retry after {retry_after}s."
                    )
            elif probe_resp.status_code in (403, 404):
                # Token valid, file not found/not accessible — but headers still present
                if seat == "low":
                    result["warning"] = (
                        f"View/Collab seat on {plan} plan — "
                        f"6 requests/month for file/image endpoints. "
                        f"Upgrade to Dev/Full (free on Starter): https://www.figma.com/settings"
                    )
                elif seat == "high":
                    result["info"] = (
                        f"Dev/Full seat on {plan} plan — "
                        f"{result['rate_limit_remaining']}/{result['rate_limit_limit']} remaining/min. "
                        f"Token is good!"
                    )
                else:
                    result["info"] = f"Token valid. Response: {probe_resp.text[:200]}"
            elif probe_resp.status_code == 200:
                if seat == "low":
                    result["warning"] = (
                        f"View/Collab seat on {plan} plan — 6 requests/month. "
                        f"Upgrade: https://www.figma.com/settings"
                    )
                else:
                    result["info"] = (
                        f"Dev/Full seat on {plan} plan — "
                        f"{result['rate_limit_remaining']}/{result['rate_limit_limit']} remaining/min."
                    )

            return result

    except Exception as exc:
        return {"error": f"Failed to reach Figma API: {exc}"}


@app.post("/api/convert")
async def start_conversion(
    payload: ConversionRequest, background_tasks: BackgroundTasks,
    idempotency_key: Optional[str] = None,
) -> dict:
    file_key = validate_figma_url(payload.figma_url)
    if not file_key:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid Figma URL. Expected "
                "https://www.figma.com/{design|file|proto}/<file_key>/..."
            ),
        )

    idempotency = idempotency_key or _idempotency_key(payload)
    existing = JOB_STORE.find_by_idempotency(idempotency)
    if existing:
        # Re-queue stale failed/cancelled jobs so retries actually run
        if existing.get("status") in ("failed", "cancelled"):
            # Refresh job params in case the user changed anything
            JOB_STORE.update(
                existing["id"],
                status="queued",
                progress=0,
                message="Re-queuing after previous failure...",
                error=None,
                result={
                    "figma_url": payload.figma_url,
                    "pat_token": payload.pat_token,
                    "target_framework": payload.target_framework,
                    "include_components": payload.include_components,
                    "style_engine": payload.style_engine,
                    "component_library": payload.component_library,
                },
            )
            background_tasks.add_task(
                process_conversion,
                existing["id"],
                payload.figma_url,
                payload.pat_token,
                payload.target_framework,
                payload.include_components,
                payload.style_engine,
                payload.component_library,
            )
            return {"job_id": existing["id"], "status": "queued", "message": "Re-queuing previous job"}
        return {"job_id": existing["id"], "status": existing["status"], "message": "Reusing existing job"}

    job_id = str(uuid.uuid4())
    try:
        JOB_STORE.create(job_id, message="Initializing conversion...", idempotency=idempotency)
    except _DuplicateJob as dup:
        return {"job_id": dup.job_id, "status": "queued", "message": "Reusing existing job"}

    # Store job params so worker.py can pick them up
    JOB_STORE.update(job_id, result={
        "figma_url": payload.figma_url,
        "pat_token": payload.pat_token,
        "target_framework": payload.target_framework,
        "include_components": payload.include_components,
        "style_engine": payload.style_engine,
        "component_library": payload.component_library,
    })

    background_tasks.add_task(
        process_conversion,
        job_id,
        payload.figma_url,
        payload.pat_token,
        payload.target_framework,
        payload.include_components,
        payload.style_engine,
        payload.component_library,
    )
    return {"job_id": job_id, "status": "queued", "message": "Conversion started"}


@app.get("/api/status/{job_id}")
async def get_conversion_status(job_id: str) -> dict:
    record = JOB_STORE.get(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": record["id"],
        "status": record["status"],
        "progress": record["progress"],
        "message": record["message"],
        "result": record["result"],
    }


@app.post("/api/cancel/{job_id}")
async def cancel_conversion(job_id: str) -> dict:
    record = JOB_STORE.get(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job not found")
    cancelled = JOB_STORE.cancel(job_id)
    if not cancelled:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel job in status '{record['status']}'",
        )
    return {"job_id": job_id, "status": "cancelled", "message": "Conversion cancelled"}


@app.get("/api/download/{job_id}")
async def download_project(job_id: str):
    record = JOB_STORE.get(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job not found")

    result = record.get("result") or {}
    zip_path = clamp_zip_path(result.get("zip_path", ""), ASSEMBLED_ROOT)
    if not zip_path:
        raise HTTPException(status_code=404, detail="Project zip not available")

    return FileResponse(
        path=str(zip_path),
        filename=f"{result.get('project_name', 'figma_project')}.zip",
        media_type="application/zip",
    )


class FileListRequest(BaseModel):
    files: list[str] = []


@app.post("/api/download-files/{job_id}")
async def download_files(job_id: str, payload: FileListRequest) -> dict:
    """Return file contents for a completed job (used by the VS Code extension)."""
    record = JOB_STORE.get(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job not found")
    result = record.get("result") or {}
    file_list = payload.files or result.get("file_list", [])
    project_dir = _resolve_project_dir(record)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project directory not found")
    contents: dict[str, str] = {}
    for rel_path in file_list:
        full = (project_dir / rel_path).resolve()
        if not str(full).startswith(str(ASSEMBLED_ROOT.resolve())):
            continue
        if full.exists() and full.is_file():
            contents[rel_path] = full.read_text("utf-8")
    return {
        "files": contents,
        "file_list": list(contents.keys()),
        "framework": result.get("framework", ""),
        "framework_name": result.get("framework_name", ""),
    }


def _read_max_refinement_iterations() -> int:
    raw = os.getenv("MAX_REFINEMENT_ITERATIONS")
    if raw is None or raw == "":
        return DEFAULT_MAX_REFINEMENT_ITERATIONS
    try:
        return max(1, int(raw))
    except ValueError:
        log.warning("Invalid MAX_REFINEMENT_ITERATIONS=%r, using default", raw)
        return DEFAULT_MAX_REFINEMENT_ITERATIONS


MAX_REFINEMENT_ITERATIONS = _read_max_refinement_iterations()


@app.post("/api/refine/{job_id}")
async def refine_project(job_id: str, payload: RefinementRequest) -> dict:
    """Apply a natural-language refinement to a previously generated project.

    Synchronous: returns when the changes have been written to disk.
    Use ``GET /api/refine/{job_id}/history`` to read iteration history.
    """
    record = JOB_STORE.get(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job not found")

    if record.get("status") != "completed":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Job status is {record.get('status')!r}; refinement requires "
                "a completed conversion."
            ),
        )

    current_iterations = JOB_STORE.refinement_count(job_id)
    if current_iterations >= MAX_REFINEMENT_ITERATIONS:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Maximum refinement iterations ({MAX_REFINEMENT_ITERATIONS}) "
                "reached for this job."
            ),
        )

    try:
        ai_engine = AI_engine_singleton.get()
    except Exception as exc:  # noqa: BLE001
        log.exception("AI engine unavailable for refinement")
        raise HTTPException(
            status_code=503,
            detail=f"AI engine unavailable: {exc}",
        ) from exc

    try:
        refinement_result = process_refinement(job_id, payload, ai_engine)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        log.exception("Refinement failed for job %s", job_id)
        raise HTTPException(status_code=500, detail=f"Refinement failed: {exc}") from exc

    return {
        "job_id": job_id,
        "iteration": refinement_result["iteration"],
        "max_iterations": MAX_REFINEMENT_ITERATIONS,
        "summary": refinement_result["summary"],
        "updated_files": refinement_result["updated_files"],
        "changed_files": refinement_result["changed_files"],
        "zip_path": refinement_result["zip_path"],
        "refinement_count": JOB_STORE.refinement_count(job_id),
    }


@app.get("/api/refine/{job_id}/history")
async def get_refinement_history(job_id: str) -> dict:
    record = JOB_STORE.get(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job not found")
    history = record.get("refinement_history") or []
    return {
        "job_id": job_id,
        "max_iterations": MAX_REFINEMENT_ITERATIONS,
        "count": len(history),
        "history": history,
    }


# --------------------------------------------------------------------------- #
# Best-effort cleanup task
# --------------------------------------------------------------------------- #

import threading as _threading
from contextlib import asynccontextmanager


_cleanup_started = _threading.Event()


@asynccontextmanager
async def _lifespan(app: FastAPI):
    ASSEMBLED_ROOT.mkdir(parents=True, exist_ok=True)
    await _validate_provider_endpoints()
    if not _cleanup_started.is_set():
        _cleanup_started.set()
        _threading.Thread(target=_scheduled_cleanup, name="jobs-cleanup", daemon=True).start()
    yield


app.router.lifespan_context = _lifespan


def _scheduled_cleanup() -> None:
    """Daily best-effort purge of stale jobs and assembled projects."""

    while True:
        try:
            removed = JOB_STORE.cleanup_older_than(JOB_TTL_DAYS)
            if removed:
                log.info("Removed %s expired jobs from store", removed)
            _purge_old_assemblies(JOB_TTL_DAYS)
        except Exception:  # noqa: BLE001
            log.exception("Cleanup task failed")
        time.sleep(86400)


def _purge_old_assemblies(max_age_days: int) -> None:
    if not ASSEMBLED_ROOT.exists():
        return
    cutoff = datetime.now(timezone.utc).timestamp() - max_age_days * 86400
    for entry in ASSEMBLED_ROOT.iterdir():
        try:
            if entry.stat().st_mtime < cutoff:
                if entry.is_dir():
                    import shutil

                    shutil.rmtree(entry, ignore_errors=True)
                else:
                    entry.unlink(missing_ok=True)
        except OSError:
            continue


# --------------------------------------------------------------------------- #
# Entrypoint
# --------------------------------------------------------------------------- #


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    log.info("Listening on http://%s:%s", host, port)
    uvicorn.run("main:app", host=host, port=port, reload=False, log_level=LOG_LEVEL.lower())
