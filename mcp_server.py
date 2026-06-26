#!/usr/bin/env python3
"""MCP Server for FigmaConverter (Plan 001).

Exposes the code-generation pipeline as MCP tools consumable by AI agents
(Claude Code, Cursor, Copilot, Codex).

Transports
----------
- stdio (default):   pipe-based, ideal for local agent integrations
- sse:               Server-Sent Events over HTTP, for remote agents

Usage
-----
    # stdio (default)
    python mcp_server.py

    # SSE on port 3845
    python mcp_server.py --transport sse --port 3845

Environment variables
---------------------
    FIGMA_MCP_ENABLED     — set to "true" (default) to enable the server
    FIGMA_MCP_TRANSPORT   — "stdio" (default) | "sse"
    FIGMA_MCP_PORT        — 3845 (default)
    FIGMA_MCP_API_KEY     — optional auth key for HTTP/SSE transport
    FIGMA_API_TOKEN       — Figma personal access token (required)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.requests import Request

from processors.ai_cache import get_cache
from processors.enhanced_figma_processor import EnhancedFigmaProcessor
from processors.template_scaffolder import list_supported_frameworks
from processors.style_library_matrix import list_supported_combinations
from processors.project_assembler import ProjectAssembler
from detectors.ai_framework_detector import AIFrameworkDetector
from parsers.ai_response_parser import AIResponseParser
from prompting import (
    generate_app_architecture_with_ai,
    generate_enhanced_frame_code_with_ai,
    generate_enhanced_main_app_with_ai,
    reconcile_dependencies_with_ai,
)
from prompting.framework_utils import get_default_dependencies, get_app_file_paths
class _MCPEngineSingleton:
    """Deferred AI engine binding — mirrors main._AISingleton."""
    _instance = None

    @classmethod
    def get(cls):
        if cls._instance is None:
            from ai_engine.ai_engine import AI_engine
            cls._instance = AI_engine(verbose=False)
        return cls._instance

MAX_FRAMES_PER_JOB = 50

log = logging.getLogger("figma_converter.mcp")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_processor_cache: Dict[str, EnhancedFigmaProcessor] = {}


def _get_processor(pat_token: Optional[str] = None) -> EnhancedFigmaProcessor:
    token = pat_token or os.getenv("FIGMA_API_TOKEN")
    if token not in _processor_cache:
        _processor_cache[token] = EnhancedFigmaProcessor(api_token=token)
    return _processor_cache[token]


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

server = FastMCP(
    name="FigmaConverter",
    instructions=(
        "Convert Figma designs to production-ready code (React, Vue, Angular, "
        "Flutter, HTML, Next.js). Supports Tailwind CSS v4, shadcn/ui, MUI, "
        "Ant Design, and Bootstrap. Extracts design tokens and Auto Layout."
    ),
    host=os.getenv("FIGMA_MCP_HOST", "127.0.0.1"),
    port=int(os.getenv("FIGMA_MCP_PORT", "3845")),
)


# ---------------------------------------------------------------------------
# Tool: get_design_context
# ---------------------------------------------------------------------------


@server.tool(
    description="Fetch and parse a Figma design, returning structured frame/component/style metadata.",
)
def get_design_context(
    figma_url: str,
    pat_token: Optional[str] = None,
    include_components: bool = True,
) -> str:
    """Fetch design context from a Figma URL.

    Args:
        figma_url: Full Figma file URL (e.g. https://www.figma.com/file/...).
        pat_token: Optional Figma personal access token (falls back to env).
        include_components: Whether to include component references.

    Returns:
        JSON string with frame summaries, design tokens (if available),
        and component references.
    """
    processor = _get_processor(pat_token)
    design_data = processor.process_frame_by_frame(figma_url, include_components)

    summary = {
        "file_key": design_data.get("design_info", {}).get("file_key"),
        "file_name": design_data.get("design_info", {}).get("file_name"),
        "total_frames": len(design_data.get("frames", [])),
        "total_components": design_data.get("design_info", {}).get("total_components", 0),
        "frames": [
            {
                "id": f.get("id"),
                "name": f.get("name"),
                "page_name": f.get("page_name"),
                "dimensions": f.get("dimensions"),
                "component_count": f.get("component_count", 0),
                "layout_type": (
                    f.get("comprehensive_data", {})
                    .get("structure", {})
                    .get("layout_type", "unknown")
                ),
            }
            for f in design_data.get("frames", [])
        ],
        "has_design_tokens": design_data.get("design_tokens") is not None,
        "component_references": list(design_data.get("component_references", {}).keys()),
    }
    return json.dumps(summary, indent=2)


# ---------------------------------------------------------------------------
# Tool: generate_code
# ---------------------------------------------------------------------------


@server.tool(
    description="Generate production code from a Figma URL for a given framework.",
)
def generate_code(
    figma_url: str,
    target_framework: str,
    pat_token: Optional[str] = None,
    include_components: bool = True,
    style_engine: Optional[str] = None,
    component_library: Optional[str] = None,
) -> str:
    """Generate framework code from a Figma design URL.

    Args:
        figma_url: Full Figma file URL.
        target_framework: Target framework (react, vue, angular, flutter, html, nextjs, react_ts).
        pat_token: Optional Figma personal access token.
        include_components: Whether to include component image exports.
        style_engine: Style engine (css, tailwind, scss, styled).
        component_library: Component library (shadcn, mui, antd, bootstrap).

    Returns:
        JSON string with generated files and metadata.
    """
    processor = _get_processor(pat_token)
    design_data = processor.process_frame_by_frame(figma_url, include_components)

    frames_count = len(design_data.get("frames", []))
    if frames_count > MAX_FRAMES_PER_JOB:
        return json.dumps({
            "error": f"Design contains {frames_count} frames; the limit is {MAX_FRAMES_PER_JOB}.",
        })

    detector = AIFrameworkDetector()
    framework_detection = detector.detect_framework(target_framework)
    if not framework_detection.get("success"):
        return json.dumps({
            "error": f"Could not determine framework from: {target_framework!r}",
        })

    detected_framework = framework_detection["framework"]
    synthetic_job_id = f"mcp_{design_data.get('design_info', {}).get('file_key', 'unknown')}"

    # Replicate generate_framework_code logic from main.py without importing it
    ai_engine = _MCPEngineSingleton.get()
    parser = AIResponseParser()
    ai_cache = get_cache()

    framework_structure = {
        "framework": framework_detection["framework"],
        "structure": framework_detection.get("project_structure", {}),
        "file_conventions": framework_detection.get("file_conventions", {}),
        "technology_stack": framework_detection.get("technology_stack", {}),
    }
    framework_structure["structure"] = framework_detection.get("project_structure", {})

    # Build design summary
    from datetime import datetime, timezone
    frames = design_data.get("frames", [])
    parts = [
        f"=== FIGMA DESIGN SUMMARY ===\n"
        f"File: {design_data.get('design_info', {}).get('file_name', 'Unknown')}\n"
        f"Total Frames: {len(frames)}\n"
        f"Total Components: {design_data.get('design_info', {}).get('total_components', 0)}\n"
    ]
    for idx, frame in enumerate(frames, 1):
        cd = frame.get("comprehensive_data", {})
        parts.append(
            f"--- Frame {idx}: {frame.get('name', '?')} ---\n"
            f"  Layout: {cd.get('structure', {}).get('layout_type', 'unknown')}\n"
            f"  Elements: {cd.get('component_count', {})}\n"
        )
    design_summary = "\n".join(parts)

    app_architecture = generate_app_architecture_with_ai(
        ai_engine, design_summary, detected_framework, parser
    )
    if not app_architecture:
        app_architecture = {
            "app_architecture": {"app_type": "Application", "primary_flow": "Basic navigation"},
            "frame_connections": [], "shared_components": [],
            "route_structure": {}, "app_state": {"global_state": [], "shared_data": []},
        }

    generated_files: Dict[str, str] = {}
    dependency_suggestions: list = []

    # Generate code for each frame
    from concurrent.futures import ThreadPoolExecutor
    _MAX_THREADS = 3

    def _process_one_frame(frame: dict) -> dict:
        return generate_enhanced_frame_code_with_ai(
            ai_engine, frame, detected_framework, synthetic_job_id, parser,
            framework_structure, app_architecture, design_summary, {},
            style_engine, component_library, ai_cache=ai_cache,
        )

    if len(frames) == 1:
        result = _process_one_frame(frames[0])
        f = result.get("files") or {}
        generated_files.update(f)
        if result.get("dependency_suggestions"):
            dependency_suggestions.append({
                "frame_name": result.get("frame_name"),
                "suggestions": result["dependency_suggestions"],
            })
    else:
        with ThreadPoolExecutor(max_workers=_MAX_THREADS) as executor:
            fut_map = {executor.submit(_process_one_frame, f): f for f in frames}
            from concurrent.futures import as_completed
            for future in as_completed(fut_map):
                try:
                    r = future.result() or {}
                    generated_files.update(r.get("files") or {})
                    if r.get("dependency_suggestions"):
                        dependency_suggestions.append({
                            "frame_name": r.get("frame_name"),
                            "suggestions": r["dependency_suggestions"],
                        })
                except Exception as exc:
                    log.warning("Frame generation failed: %s", exc)

    # Reconcile dependencies
    if dependency_suggestions:
        reconciled = reconcile_dependencies_with_ai(
            ai_engine, {}, dependency_suggestions, framework_structure, parser
        )
        final_deps = reconciled or {}
    else:
        final_deps = {}

    # Generate main app shell
    main_app_files = generate_enhanced_main_app_with_ai(
        ai_engine, frames, detected_framework, synthetic_job_id, parser,
        framework_structure, app_architecture, style_engine, component_library,
    )
    if main_app_files:
        generated_files.update(main_app_files)

    # Merge design tokens
    figma_variables = design_data.get("design_tokens")
    if figma_variables:
        from processors.token_extractor import extract_tokens
        from processors.token_generator import generate_token_file, token_file_path
        tokens = extract_tokens(figma_variables=figma_variables, frames=frames)
        style = (style_engine or "css").lower()
        from prompting.style_builders import build_styles
        token_path = token_file_path(detected_framework, style)
        if token_path not in generated_files:
            content = generate_token_file(tokens, style)
            if content:
                generated_files[token_path] = content

    # Framework config (package.json, index.css)
    if detected_framework in {"react", "vue", "angular", "nextjs"} and "package.json" not in generated_files:
        from processors.style_library_matrix import DependencyResolver
        pkg_data = DependencyResolver(use_cache=True).resolve_to_package_json(
            detected_framework, style_engine, component_library
        )
        generated_files["package.json"] = json.dumps(pkg_data, indent=2)

    if detected_framework not in {"html", "html_css_js"}:
        styles_path = "src/index.css"
        if styles_path not in generated_files:
            from prompting.style_builders import build_styles
            generated_files[styles_path] = build_styles(style_engine or "css", None)

    result = {
        "framework": detected_framework,
        "files": list(generated_files.keys()),
        "main_file": framework_structure.get("structure", {}).get("main_file", "src/App.js"),
        "file_contents": generated_files,
        "dependency_suggestions": dependency_suggestions,
    }
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tool: get_design_tokens
# ---------------------------------------------------------------------------


@server.tool(
    description="Extract design tokens (colors, typography, spacing, radii, shadows) from a Figma file.",
)
def get_design_tokens(
    figma_url: str,
    pat_token: Optional[str] = None,
) -> str:
    """Extract design tokens from a Figma file.

    Uses Figma Variables API when available; falls back to hardcoded values
    parsed from frame data.

    Args:
        figma_url: Full Figma file URL.
        pat_token: Optional Figma personal access token.

    Returns:
        JSON string with token categories (color, typography, spacing, radius, shadow).
    """
    processor = _get_processor(pat_token)
    design_data = processor.process_frame_by_frame(figma_url, include_components=False)

    # Check for design_tokens from Figma Variables API
    figma_variables = design_data.get("design_tokens")

    from processors.token_extractor import extract_tokens, tokens_as_dict

    tokens = extract_tokens(
        figma_variables=figma_variables,
        frames=design_data.get("frames", []),
    )
    result = {
        "source": tokens.source,
        "token_count": tokens.token_count,
        "tokens": tokens_as_dict(tokens),
    }
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tool: get_framework_options
# ---------------------------------------------------------------------------


@server.tool(
    description="List all supported frameworks, style engines, and component libraries.",
)
def get_framework_options() -> str:
    """Return available frameworks, style engines, and component libraries."""
    frameworks = list_supported_frameworks()

    style_engines = ["css", "tailwind", "scss", "styled", "css_modules"]

    component_libraries = ["shadcn", "mui", "antd", "bootstrap", "none"]

    combos = list_supported_combinations()

    result = {
        "frameworks": frameworks,
        "style_engines": style_engines,
        "component_libraries": component_libraries,
        "valid_combinations": [
            {
                "framework": c["framework"],
                "style": c.get("style_engine", c.get("style", "")),
                "library": c.get("component_library", c.get("library", "")),
            }
            for c in combos
        ],
        "default_dependencies": {
            fw: get_default_dependencies(fw) for fw in frameworks
        },
        "app_file_paths": {
            fw: get_app_file_paths(fw) for fw in frameworks
        },
    }
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tool: validate_design
# ---------------------------------------------------------------------------


@server.tool(
    description="Analyse a Figma design for code-generation readiness.",
)
def validate_design(
    figma_url: str,
    pat_token: Optional[str] = None,
) -> str:
    """Check the Figma file structure quality for code generation.

    Scores the design on auto-layout coverage, named-layers ratio, and
    component usage.

    Args:
        figma_url: Full Figma file URL.
        pat_token: Optional Figma personal access token.

    Returns:
        JSON string with quality scores and recommendations.
    """
    processor = _get_processor(pat_token)
    design_data = processor.process_frame_by_frame(figma_url, include_components=True)

    frames = design_data.get("frames", [])
    total_frames = len(frames)

    # Analysis
    auto_layout_count = 0
    named_frame_count = 0
    total_elements = 0
    layer_name_issues: List[str] = []

    for frame in frames:
        cd = frame.get("comprehensive_data", {})
        structure = cd.get("structure", {})
        layout_type = structure.get("layout_type", "")
        if layout_type in ("horizontal-flow", "vertical-flow"):
            auto_layout_count += 1

        name = frame.get("name", "")
        if name and name != "Frame" and not name.startswith("Frame "):
            named_frame_count += 1
        else:
            layer_name_issues.append(f"Frame '{frame.get('id', '?')}' has generic name")

        element_types = cd.get("design_system", {}).get("colors", [])
        total_elements += len(element_types)

    auto_layout_pct = (auto_layout_count / total_frames * 100) if total_frames else 0
    named_pct = (named_frame_count / total_frames * 100) if total_frames else 0

    scores = {
        "auto_layout_coverage": round(auto_layout_pct, 1),
        "named_frames_ratio": round(named_pct, 1),
        "total_frames": total_frames,
        "total_components": design_data.get("design_info", {}).get("total_components", 0),
        "has_design_tokens": design_data.get("design_tokens") is not None,
        "recommendations": [],
        "warnings": [],
    }

    if auto_layout_pct < 50:
        scores["recommendations"].append(
            "Use Figma Auto Layout (Shift+A) on containers for better responsive output."
        )
    if named_pct < 80:
        scores["recommendations"].append(
            "Rename frames with meaningful names (e.g. 'Header', 'Card') for better component generation."
        )
    if not scores["has_design_tokens"]:
        scores["recommendations"].append(
            "Define Figma Variables (colors, spacing, typography) for automatic design-token extraction."
        )
    if layer_name_issues:
        scores["warnings"] = layer_name_issues[:5]

    # Overall readiness score (0-100)
    readiness = (
        (auto_layout_pct * 0.4)
        + (named_pct * 0.3)
        + (scores["has_design_tokens"] * 15)
        + (min(scores["total_components"], 20) / 20 * 15)
    )
    scores["readiness_score"] = round(min(readiness, 100), 1)

    return json.dumps(scores, indent=2)


# ---------------------------------------------------------------------------
# Auth middleware (SSE transport only)
# ---------------------------------------------------------------------------


class _AuthMiddleware(BaseHTTPMiddleware):
    """Check Authorization: Bearer <FIGMA_MCP_API_KEY> on every request."""

    async def dispatch(self, request: Request, call_next):
        api_key = os.getenv("FIGMA_MCP_API_KEY")
        if api_key:
            auth_header = request.headers.get("authorization", "")
            token = auth_header.removeprefix("Bearer ").strip()
            if token != api_key:
                return JSONResponse(
                    {"error": "Unauthorized"},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
        return await call_next(request)


def _make_sse_app():
    """Return the SSE ASGI app wrapped with auth middleware."""
    app = server.sse_app()
    api_key = os.getenv("FIGMA_MCP_API_KEY")
    if api_key:
        app = _AuthMiddleware(app)
    return app


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="FigmaConverter MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default=os.getenv("FIGMA_MCP_TRANSPORT", "stdio"),
        help="MCP transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("FIGMA_MCP_PORT", "3845")),
        help="Port for SSE transport (default: 3845)",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("FIGMA_MCP_HOST", "127.0.0.1"),
        help="Bind address for SSE transport (default: 127.0.0.1)",
    )
    args = parser.parse_args()

    if os.getenv("FIGMA_MCP_ENABLED", "true").lower() != "true":
        print("FIGMA_MCP_ENABLED is not 'true'; MCP server will not start.")
        sys.exit(0)

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    # Patch server settings from CLI args
    server.settings.host = args.host
    server.settings.port = args.port

    if args.transport == "sse":
        import uvicorn
        app = _make_sse_app()
        api_key_set = os.getenv("FIGMA_MCP_API_KEY") is not None
        print(
            f"FigmaConverter MCP server starting on http://{args.host}:{args.port}/sse"
            + (" (auth enabled)" if api_key_set else "")
        )
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    else:
        print("FigmaConverter MCP server starting (stdio transport)...")
        server.run(transport="stdio")


if __name__ == "__main__":
    main()
