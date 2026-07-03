"""Build .figma-workspace/ directory with parsed design data for AI consumption.

Creates a structured workspace containing:
- Frame screenshots (PNG)
- Extracted design tokens (colors, typography, layout)
- AI-readable design brief
- OpenCode configuration for the workspace
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional


WORKSPACE_DIR = ".figma-workspace"


def build_workspace(
    design_data: Dict[str, Any],
    vision_images: Dict[str, str],
    job_id: str,
    output_base: Optional[str] = None,
) -> Path:
    """Build the .figma-workspace/ directory for a conversion job.

    Args:
        design_data: Full Figma processing result from EnhancedFigmaProcessor.
        vision_images: Dict mapping frame_id → local PNG path from export_frame_screenshots.
        job_id: Unique job identifier.
        output_base: Base directory for the workspace. Defaults to data/jobs/{job_id}/.

    Returns:
        Path to the created workspace directory.
    """
    if output_base is None:
        output_base = os.path.join("data", "jobs", job_id)

    workspace = Path(output_base) / WORKSPACE_DIR
    _clear_workspace(workspace)

    frames = design_data.get("frames", [])

    # 1. Copy screenshots
    screenshots_dir = workspace / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    screenshot_paths = {}
    for frame in frames:
        fid = frame.get("id", "")
        if fid in vision_images:
            src = Path(vision_images[fid])
            if src.exists():
                dst = screenshots_dir / f"frame-{fid.replace(':', '-')}.png"
                shutil.copy2(src, dst)
                screenshot_paths[fid] = str(dst.relative_to(workspace))

    # 2. Extract design tokens
    extracted_dir = workspace / "extracted"
    extracted_dir.mkdir(parents=True, exist_ok=True)
    _extract_colors(frames, extracted_dir / "colors.json")
    _extract_typography(frames, extracted_dir / "typography.json")
    _extract_layout(frames, extracted_dir / "layout.json")
    _extract_components(frames, extracted_dir / "components.json")

    # 3. Save raw design data
    _save_json(workspace / "design-data.json", design_data)

    # 4. Generate AI-readable design brief
    ai_context_dir = workspace / "ai-context"
    ai_context_dir.mkdir(parents=True, exist_ok=True)
    _generate_design_brief(frames, screenshot_paths, ai_context_dir / "design-brief.md")
    _generate_component_map(frames, ai_context_dir / "component-map.md")

    # 5. Create opencode config for workspace
    _create_opencode_config(workspace)

    print(f"📁 Workspace built: {workspace}")
    return workspace


def get_screenshot_paths(workspace: Path, frame_id: str) -> Optional[str]:
    """Get the screenshot path for a frame within the workspace."""
    fname = f"frame-{frame_id.replace(':', '-')}.png"
    path = workspace / "screenshots" / fname
    return str(path) if path.exists() else None


def get_all_screenshot_paths(workspace: Path) -> Dict[str, str]:
    """Get all screenshot paths mapped by frame_id."""
    result = {}
    screenshots_dir = workspace / "screenshots"
    if screenshots_dir.exists():
        for f in screenshots_dir.glob("frame-*.png"):
            # frame-1:2.png → 1:2
            fid = f.stem.replace("frame-", "").replace("-", ":", 1)
            result[fid] = str(f)
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clear_workspace(workspace: Path) -> None:
    """Remove existing workspace if present."""
    if workspace.exists():
        shutil.rmtree(workspace)


def _save_json(path: Path, data: Any) -> None:
    """Write JSON data to a file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def _extract_colors(frames: List[Dict], out_path: Path) -> None:
    """Extract unique colors from all frames."""
    all_colors = set()
    for frame in frames:
        comp = frame.get("comprehensive_data", {})
        ds = comp.get("design_system", {})
        colors = ds.get("colors", [])
        for c in colors:
            if isinstance(c, str):
                all_colors.add(c)
            elif isinstance(c, dict):
                hex_val = c.get("hex") or c.get("value", "")
                if hex_val:
                    all_colors.add(hex_val)

    _save_json(out_path, {
        "palette": sorted(all_colors),
        "count": len(all_colors),
    })


def _extract_typography(frames: List[Dict], out_path: Path) -> None:
    """Extract typography styles from all frames."""
    fonts = {}
    for frame in frames:
        comp = frame.get("comprehensive_data", {})
        content = comp.get("content", {})
        for text in content.get("texts", []):
            style = text.get("style", {})
            key = f"{style.get('font_family', 'default')}-{style.get('font_size', 14)}-{style.get('font_weight', 400)}"
            if key not in fonts:
                fonts[key] = {
                    "font_family": style.get("font_family", "default"),
                    "font_size": style.get("font_size", 14),
                    "font_weight": style.get("font_weight", 400),
                    "color": style.get("color", "#000000"),
                    "samples": [],
                }
            sample = text.get("content", "")
            if sample and len(fonts[key]["samples"]) < 3:
                fonts[key]["samples"].append(sample[:60])

    _save_json(out_path, {
        "styles": fonts,
        "count": len(fonts),
    })


def _extract_layout(frames: List[Dict], out_path: Path) -> None:
    """Extract layout properties from all frames."""
    layouts = []
    for frame in frames:
        comp = frame.get("comprehensive_data", {})
        layout = comp.get("layout", {})
        basic = comp.get("basic_info", {})
        dims = basic.get("dimensions", {})
        layouts.append({
            "frame_name": frame.get("name", "Frame"),
            "frame_id": frame.get("id", ""),
            "width": dims.get("width", frame.get("width", 0)),
            "height": dims.get("height", frame.get("height", 0)),
            "layout_type": layout.get("layout_type", "unknown"),
            "layout_mode": layout.get("layout_mode") or layout.get("layoutMode"),
            "gap": layout.get("gap") or layout.get("itemSpacing", 0),
            "padding": layout.get("padding", {}),
            "background_color": layout.get("background_color", "#ffffff"),
        })

    _save_json(out_path, {
        "frames": layouts,
        "count": len(layouts),
    })


def _extract_components(frames: List[Dict], out_path: Path) -> None:
    """Extract component/element inventory from all frames."""
    components = []
    for frame in frames:
        comp = frame.get("comprehensive_data", {})
        content = comp.get("content", {})

        frame_info = {
            "frame_name": frame.get("name", "Frame"),
            "frame_id": frame.get("id", ""),
            "texts": [
                {"content": t.get("content", ""), "context": t.get("context", "text")}
                for t in content.get("texts", [])[:20]
            ],
            "interactive_elements": [
                {"type": e.get("type", ""), "text": e.get("text", e.get("name", "")), "action": e.get("action", "")}
                for e in content.get("interactive_elements", [])[:15]
            ],
            "containers": [
                {"name": c.get("name", ""), "type": c.get("type", ""), "children": c.get("children_count", 0)}
                for c in content.get("containers", [])[:10]
            ],
        }
        components.append(frame_info)

    _save_json(out_path, {
        "frames": components,
        "total_frames": len(components),
    })


def _generate_design_brief(
    frames: List[Dict],
    screenshot_paths: Dict[str, str],
    out_path: Path,
) -> None:
    """Generate a markdown design brief for the AI agent."""
    lines = ["# Design Brief\n"]

    for frame in frames:
        fname = frame.get("name", "Frame")
        fid = frame.get("id", "")
        comp = frame.get("comprehensive_data", {})
        content = comp.get("content", {})
        ds = comp.get("design_system", {})
        layout = comp.get("layout", {})
        basic = comp.get("basic_info", {})
        dims = basic.get("dimensions", {})

        lines.append(f"## {fname}\n")
        lines.append(f"- **ID:** {fid}")
        lines.append(f"- **Size:** {dims.get('width', '?')} x {dims.get('height', '?')}px")
        lines.append(f"- **Layout:** {layout.get('layout_type', 'unknown')}")
        if layout.get("background_color"):
            lines.append(f"- **Background:** {layout.get('background_color')}")
        lines.append("")

        # Screenshots
        if fid in screenshot_paths:
            lines.append(f"**Screenshot:** `{screenshot_paths[fid]}`\n")

        # Text content
        texts = content.get("texts", [])
        if texts:
            lines.append("### Text Content\n")
            for t in texts[:15]:
                style = t.get("style", {})
                lines.append(
                    f"- \"{t.get('content', '')}\" — "
                    f"{style.get('font_family', 'default')} "
                    f"{style.get('font_size', 14)}px "
                    f"wt{style.get('font_weight', 400)} "
                    f"({t.get('context', 'text')})"
                )
            lines.append("")

        # Interactive elements
        interactives = content.get("interactive_elements", [])
        if interactives:
            lines.append("### Interactive Elements\n")
            for e in interactives[:10]:
                lines.append(
                    f"- **{e.get('type', 'element')}**: \"{e.get('text', e.get('name', ''))}\" "
                    f"→ action: {e.get('action', 'click')}"
                )
            lines.append("")

        # Colors
        colors = ds.get("colors", [])
        if colors:
            color_strs = [c if isinstance(c, str) else c.get("hex", str(c)) for c in colors[:12]]
            lines.append(f"### Colors\n`{'`, `'.join(color_strs)}`\n")

        lines.append("---\n")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _generate_component_map(frames: List[Dict], out_path: Path) -> None:
    """Generate a component hierarchy map for the AI agent."""
    lines = ["# Component Map\n"]
    lines.append("Frame hierarchy and component relationships:\n")

    for frame in frames:
        fname = frame.get("name", "Frame")
        fid = frame.get("id", "")
        comp = frame.get("comprehensive_data", {})
        content = comp.get("content", {})
        counts = comp.get("component_count", {})

        lines.append(f"## {fname} (`{fid}`)\n")
        lines.append(f"- Total elements: {counts.get('total', 0)}")
        lines.append(f"- Text elements: {counts.get('texts', 0)}")
        lines.append(f"- Images: {counts.get('images', 0)}")
        lines.append(f"- Interactive: {counts.get('buttons', 0) + counts.get('inputs', 0)}")
        lines.append(f"- Containers: {counts.get('containers', 0)}")
        lines.append("")

        # Suggested components
        lines.append("**Suggested components:**\n")
        texts = content.get("texts", [])
        interactives = content.get("interactive_elements", [])

        if any(t.get("context") == "heading" for t in texts):
            lines.append("- Header/PageHeader — heading text found")
        if interactives:
            button_texts = [e.get("text", "") for e in interactives if e.get("type") == "button"]
            if button_texts:
                lines.append(f"- Buttons: {', '.join(button_texts[:5])}")
            input_texts = [e.get("text", "") for e in interactives if e.get("type") == "input"]
            if input_texts:
                lines.append(f"- Inputs: {', '.join(input_texts[:5])}")
        lines.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _create_opencode_config(workspace: Path) -> None:
    """Create opencode.json and AGENTS.md inside the workspace."""
    opencode_dir = workspace / "opencode"
    opencode_dir.mkdir(parents=True, exist_ok=True)

    # opencode.json pointing to workspace context
    config = {
        "$schema": "https://opencode.ai/config.json",
        "instructions": [
            "../AGENTS.md",
            "ai-context/design-brief.md",
            "ai-context/component-map.md",
        ],
    }
    with open(opencode_dir / "opencode.json", "w") as f:
        json.dump(config, f, indent=2)

    # AGENTS.md that loads workspace context
    agents_md = """# Code Generation Context

Read these files for design context:
- `ai-context/design-brief.md` — visual description of each frame with screenshot paths
- `ai-context/component-map.md` — component hierarchy and relationships
- `extracted/colors.json` — extracted color palette
- `extracted/typography.json` — extracted typography styles
- `extracted/layout.json` — layout properties for each frame
- `screenshots/` — PNG screenshots of each frame (use as visual reference)

Follow the rules in `../../AGENTS.md` for code generation.
"""
    with open(opencode_dir / "AGENTS.md", "w") as f:
        f.write(agents_md)
