"""Simplified prompt builders with XML structure and vision support."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PromptRequest:
    """Container describing a chat-completion style prompt."""

    messages: List[Dict[str, Any]]
    temperature: float
    autodecide: bool = False
    debug_context: Dict[str, Any] = field(default_factory=dict)


def _load_reference_file(filename: str) -> str:
    """Load a reference file from .opencode/references/."""
    ref_path = os.path.join(os.path.dirname(__file__), "..", ".opencode", "references", filename)
    try:
        with open(ref_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def _file_ext(framework: str) -> str:
    """Map framework name to its standard file extension."""
    exts = {
        "react": "jsx",
        "vue": "vue",
        "angular": "ts",
        "svelte": "svelte",
        "nextjs": "tsx",
        "flutter": "dart",
        "html": "html",
        "html_css_js": "html",
    }
    return exts.get(framework, "jsx")


def _extract_text_content(frame: Dict[str, Any]) -> List[Dict[str, str]]:
    """Extract text content from frame data."""
    comprehensive = frame.get("comprehensive_data", {})
    content = comprehensive.get("content", {})
    texts = []
    for text in content.get("texts", []):
        texts.append({
            "content": text.get("content", ""),
            "font_size": text.get("style", {}).get("font_size", 14),
            "font_weight": text.get("style", {}).get("font_weight", 400),
            "color": text.get("style", {}).get("color", "#000000"),
            "context": text.get("context", "text"),
        })
    return texts


def _extract_interactive_elements(frame: Dict[str, Any]) -> List[Dict[str, str]]:
    """Extract interactive elements from frame data."""
    comprehensive = frame.get("comprehensive_data", {})
    content = comprehensive.get("content", {})
    elements = []
    for elem in content.get("interactive_elements", []):
        elements.append({
            "type": elem.get("type", "button"),
            "text": elem.get("text", elem.get("name", "")),
            "action": elem.get("action", "click"),
            "target": elem.get("target", ""),
        })
    return elements


def _extract_colors(frame: Dict[str, Any]) -> List[str]:
    """Extract colors from frame data."""
    comprehensive = frame.get("comprehensive_data", {})
    design_system = comprehensive.get("design_system", {})
    colors = design_system.get("colors", [])
    result = []
    for c in colors:
        if isinstance(c, str):
            result.append(c)
        elif isinstance(c, dict):
            hex_val = c.get("hex", c.get("value", ""))
            if hex_val:
                result.append(hex_val)
    return result


def build_frame_generation_prompt(
    frame: Dict[str, Any],
    framework: str,
    job_id: str,
    framework_structure: Dict[str, Any],
    app_architecture: Dict[str, Any],
    design_summary: str,
    resolved_dependencies: Optional[Dict[str, Any]] = None,
    style_engine: Optional[str] = None,
    component_library: Optional[str] = None,
    vision_images: Optional[List[str]] = None,
) -> PromptRequest:
    """Build a simplified, XML-structured prompt for frame generation with vision support."""

    frame_name = frame.get("name", "Frame")
    frame_id = frame.get("id", "unknown")
    frame_width = frame.get("width", 1440)
    frame_height = frame.get("height", 900)

    comprehensive = frame.get("comprehensive_data", {})
    layout = comprehensive.get("layout", {})
    design_system = comprehensive.get("design_system", {})

    texts = _extract_text_content(frame)
    interactive = _extract_interactive_elements(frame)
    colors = _extract_colors(frame)

    # Build structured frame data
    frame_data = {
        "name": frame_name,
        "id": frame_id,
        "dimensions": f"{frame_width}x{frame_height}",
        "layout": {
            "type": layout.get("layout_type", "flex"),
            "direction": (layout.get("layout_mode") or "VERTICAL").lower(),
            "gap": layout.get("gap", 0),
            "padding": layout.get("padding", {}),
        },
        "background": layout.get("background_color", "#ffffff"),
        "text_content": texts[:15],
        "interactive_elements": interactive[:10],
        "colors": colors[:12],
    }

    # Load framework-agnostic reference data
    ref_figma_data = _load_reference_file("figma-data-format.md")

    system_prompt = f"""You are an expert {framework} developer. You generate production-ready code from Figma design data.

RULES:
1. Return ONLY valid JSON - no markdown, no explanations
2. Use the framework's standard component pattern
3. Use the specified style engine for styling ({style_engine or 'tailwind'})
4. Include all text content exactly as specified
5. Add aria-labels to interactive elements
6. Use semantic HTML elements
7. Follow the framework's file conventions
8. Use the specified component library ({component_library or 'none'}) if provided

{ref_figma_data}

OUTPUT FORMAT:
{{
  "files": [
    {{
      "path": "src/components/ComponentName.{_file_ext(framework)}",
      "content": "complete component code"
    }}
  ],
  "dependencies": ["{framework}", "{style_engine or 'tailwind'}"],
  "suggestions": []
}}"""

    user_prompt = f"""<figma_design>
<frame name="{frame_name}" id="{frame_id}" width="{frame_width}" height="{frame_height}">
<layout type="{frame_data['layout']['type']}" direction="{frame_data['layout']['direction']}" gap="{frame_data['layout']['gap']}">
{json.dumps(frame_data['layout']['padding'], indent=2)}
</layout>

<background color="{frame_data['background']}" />

<text_content>
{json.dumps(frame_data['text_content'], indent=2)}
</text_content>

<interactive_elements>
{json.dumps(frame_data['interactive_elements'], indent=2)}
</interactive_elements>

<color_palette>
{json.dumps(frame_data['colors'], indent=2)}
</color_palette>
</frame>
</figma_design>

<requirements>
<framework>{framework}</framework>
<component_library>{component_library or 'none'}</component_library>
<style_engine>{style_engine or 'tailwind'}</style_engine>
</requirements>

<instructions>
Generate a {framework} component for the frame "{frame_name}".
Use {style_engine or 'tailwind'} for all styling.
Include all text content exactly as shown.
Add proper accessibility attributes.
Use semantic HTML elements.
</instructions>"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt, "images": vision_images or []},
    ]

    debug_context = {
        "frame_name": frame_name,
        "framework": framework,
        "has_vision": bool(vision_images),
        "text_count": len(texts),
        "interactive_count": len(interactive),
    }

    return PromptRequest(
        messages=messages,
        temperature=0.2,
        autodecide=False,
        debug_context=debug_context,
    )


def build_architecture_prompt(
    frames: List[Dict[str, Any]],
    framework: str,
    framework_structure: Dict[str, Any],
) -> PromptRequest:
    """Build a simplified architecture prompt."""

    frame_names = [f.get("name", "Frame") for f in frames]
    frame_summaries = []
    for f in frames[:10]:
        comp = f.get("comprehensive_data", {})
        texts = [t.get("content", "") for t in comp.get("content", {}).get("texts", [])[:5]]
        frame_summaries.append({
            "name": f.get("name"),
            "width": f.get("width"),
            "height": f.get("height"),
            "texts": texts,
        })

    system_prompt = f"""You are a {framework} application architect.
Analyze the frames and determine navigation flow and shared components.
Return ONLY valid JSON - no markdown."""

    user_prompt = f"""<frames>
{json.dumps(frame_summaries, indent=2)}
</frames>

<instructions>
Analyze these frames and determine:
1. Navigation flow between frames
2. Shared components
3. Route structure
</instructions>

<output_format>
{{
  "app_type": "description",
  "navigation_pattern": "tabs|drawer|stack",
  "frame_connections": [
    {{"from": "Frame1", "to": "Frame2", "trigger": "button", "trigger_text": "text"}}
  ],
  "shared_components": ["Header", "Footer"],
  "routes": {{"/": "Home", "/login": "Login"}}
}}
</output_format>"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    return PromptRequest(
        messages=messages,
        temperature=0.2,
        autodecide=False,
        debug_context={"frame_count": len(frames)},
    )


def build_main_app_prompt(
    frames: List[Dict[str, Any]],
    framework: str,
    framework_structure: Dict[str, Any],
    app_architecture: Dict[str, Any],
) -> PromptRequest:
    """Build a simplified main app prompt."""

    frame_names = [f.get("name", "Frame") for f in frames]
    routes = app_architecture.get("routes", {})

    system_prompt = f"""You are a {framework} developer.
Generate the main application shell with routing.
Return ONLY valid JSON - no markdown."""

    user_prompt = f"""<application>
<framework>{framework}</framework>
<frames>{json.dumps(frame_names)}</frames>
<routes>{json.dumps(routes)}</routes>
</application>

<instructions>
Generate the main App component with:
1. React Router setup
2. Layout component
3. Route definitions for all frames
4. Global styles
</instructions>

<output_format>
{{
  "files": [
    {{"path": "src/App.jsx", "content": "main app component"}},
    {{"path": "src/main.jsx", "content": "entry point"}}
  ]
}}
</output_format>"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    return PromptRequest(
        messages=messages,
        temperature=0.2,
        autodecide=False,
        debug_context={"frame_count": len(frames)},
    )
