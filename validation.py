"""Input validation helpers shared across the FastAPI surface."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

MAX_FIGMA_URL_LENGTH = 2048
MAX_FRAMEWORK_LENGTH = 1024
MAX_PAT_TOKEN_LENGTH = 512
MAX_REFINE_PROMPT_LENGTH = 4000
MAX_REFINE_TARGET_FILES = 100
DEFAULT_MAX_REFINEMENT_ITERATIONS = 20

ALLOWED_FIGMA_HOSTS = frozenset({"www.figma.com", "figma.com"})

_FIGMA_FILE_KEY_RE = re.compile(r"^[A-Za-z0-9]{6,40}$")
_DANGEROUS_FILE_KEY_CHARS = re.compile(r"[^A-Za-z0-9]")


def validate_figma_url(url: str) -> Optional[str]:
    """Return the file_key for a well-formed Figma URL, else None.

    Rejects anything that is not on www.figma.com / figma.com, anything that
    does not match the canonical `/design/<key>/...`, `/file/<key>/...` or
    `/proto/<key>/...` shape, and any key that contains unexpected characters.

    The Figma file key is opaque to clients but is documented to be alphanumeric
    with no separators, typically 22 characters. We accept 10-40 chars to give
    some headroom for older or partner-shaped URLs.
    """

    if not url or not isinstance(url, str):
        return None
    if len(url) > MAX_FIGMA_URL_LENGTH:
        return None

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return None
    if parsed.netloc.lower() not in ALLOWED_FIGMA_HOSTS:
        return None

    parts = [segment for segment in parsed.path.split("/") if segment]
    if len(parts) < 2:
        return None
    if parts[0] not in ("design", "file", "proto"):
        return None

    file_key = parts[1]
    if not _FIGMA_FILE_KEY_RE.match(file_key):
        return None
    if _DANGEROUS_FILE_KEY_CHARS.search(file_key):
        return None
    return file_key


def is_safe_under(path: Path, root: Path) -> bool:
    """Return True when `path` resolves under `root` without escaping it."""

    try:
        canonical = Path(path).resolve()
    except (OSError, RuntimeError):
        return False
    try:
        canonical_root = Path(root).resolve()
    except (OSError, RuntimeError):
        return False
    if not canonical.is_file():
        return False
    try:
        canonical.relative_to(canonical_root)
    except ValueError:
        return False
    return True


def clamp_zip_path(zip_path: str, allowed_root: Path) -> Optional[Path]:
    """Resolve `zip_path` and confirm it is a real file under `allowed_root`.

    Returns the canonical Path on success, None if the path escapes the root
    or does not exist. Designed for /api/download handlers that must never
    serve arbitrary locations on disk.
    """

    if not zip_path or not isinstance(zip_path, str):
        return None
    return None if not is_safe_under(Path(zip_path), allowed_root) else Path(zip_path).resolve()
