"""Prompt builders for AI-driven code generation workflows."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PromptRequest:
    """Container describing a chat-completion style prompt."""

    messages: List[Dict[str, str]]
    temperature: float
    autodecide: bool = False
    debug_context: Dict[str, Any] = field(default_factory=dict)


def build_framework_discovery_prompt(design_data: Dict[str, Any], framework: str) -> PromptRequest:
    """Construct the prompt for framework structure discovery."""
    frames = design_data.get("frames", [])
    total_frames = len(frames)
    total_components = design_data.get("total_components", 0)

    framework_examples = {
        "react": {
            "component_extension": ".jsx",
            "main_file": "src/App.jsx",
            "config_files": ["package.json", "vite.config.js"],
            "routing_library": "react-router-dom",
            "build_tool": "vite",
        },
        "vue": {
            "component_extension": ".vue",
            "main_file": "src/App.vue",
            "config_files": ["package.json", "vite.config.js"],
            "routing_library": "vue-router",
            "build_tool": "vite",
        },
        "angular": {
            "component_extension": ".ts",
            "main_file": "src/app/app.component.ts",
            "config_files": ["package.json", "angular.json", "tsconfig.json"],
            "routing_library": "@angular/router",
            "build_tool": "angular-cli",
        },
        "flutter": {
            "component_extension": ".dart",
            "main_file": "lib/main.dart",
            "config_files": ["pubspec.yaml"],
            "routing_library": "flutter/material navigation",
            "build_tool": "flutter",
        },
        "html": {
            "component_extension": ".html",
            "main_file": "index.html",
            "config_files": [],
            "routing_library": "native browser navigation",
            "build_tool": "none",
        },
        "html_css_js": {
            "component_extension": ".html",
            "main_file": "index.html",
            "config_files": [],
            "routing_library": "vanilla JavaScript routing",
            "build_tool": "none",
        },
    }

    framework_key = framework.lower()
    examples = framework_examples.get(framework_key, framework_examples["html"])

    user_prompt = f"""Analyze the {framework.upper()} framework and provide its complete structure for a project with {total_frames} frames and {total_components} components.

CRITICAL: You are working with {framework.upper()} framework specifically. Provide structure details specific to {framework.upper()} only.

Based on the Figma design analysis, determine the optimal project structure, dependencies, and configuration for {framework.upper()}.

IMPORTANT: Respond with ONLY a valid JSON object in this exact format (using {framework.upper()}-specific values):
{{
  "framework": "{framework}",
  "version": "latest stable version for {framework.upper()}",
  "structure": {{
    "component_extension": "{examples['component_extension']}",
    "main_file": "{examples['main_file']}",
    "config_files": {json.dumps(examples['config_files'])},
    "folder_structure": {{
      "src": ["components", "pages", "utils", "assets"],
      "public": ["index.html", "assets"],
      "config": []
    }}
  }},
  "styling": {{
    "primary": "{framework.upper()}-appropriate styling approach",
    "secondary": ["{framework.upper()}-compatible styling alternatives"]
  }},
  "routing": {{
    "library": "{examples['routing_library']}",
    "version": "latest version"
  }},
  "build_tool": "{examples['build_tool']}",
  "package_manager": "npm or appropriate for {framework.upper()}"
}}

Do NOT include any explanations, markdown formatting, or additional text. Return ONLY the JSON object with {framework.upper()}-specific values."""

    system_prompt = f"""You are an expert {framework} architect and developer with deep knowledge of {framework} ecosystem.

FRAMEWORK FOCUS: {framework}
You are analyzing requirements to create a complete {framework} project structure.

EXPERTISE AREAS:
- {framework} component architecture and best practices
- {framework} tooling, build systems, and dependencies
- Modern {framework} development patterns and conventions
- Project structure organization for {framework} applications

CRITICAL INSTRUCTIONS:
1. Focus specifically on {framework} technologies and patterns
2. Provide modern, production-ready {framework} configurations
3. Include proper dependencies and tooling for {framework}
4. Structure should follow {framework} community standards
5. Always respond with valid JSON only - no explanations

Remember: This is a {framework} project analysis. Every recommendation should be {framework}-specific."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    debug_context = {
        "framework": framework,
        "total_frames": total_frames,
        "total_components": total_components,
        "messages_preview": messages,
    }

    return PromptRequest(messages=messages, temperature=0.1, autodecide=False, debug_context=debug_context)


def build_app_architecture_prompt(design_summary: str, framework: str) -> PromptRequest:
    """Construct the prompt for overall app architecture generation."""
    user_prompt = f"""Analyze this comprehensive Figma design and create a complete app architecture with frame interconnections for {framework}.

{design_summary}

Based on the frames and their content, determine:

1. **Navigation Flow**: How frames connect to each other (signup -> login, dashboard navigation, etc.)
2. **Component Relationships**: Shared components between frames
3. **Data Flow**: How data moves between frames
4. **User Journey**: Logical user flow through the application
5. **Route Structure**: URL paths and routing patterns

IMPORTANT: Respond with ONLY a valid JSON object in this exact format:
{{
  "app_architecture": {{
    "app_type": "description of the app (e.g., 'E-commerce App', 'Dashboard App')",
    "primary_flow": "main user journey description",
    "navigation_pattern": "navigation style (tabs, drawer, stack, etc.)"
  }},
  "frame_connections": [
    {{
      "from_frame": "Frame Name",
      "to_frame": "Frame Name",
      "connection_type": "navigation|modal|redirect|back",
      "trigger": "button|link|automatic|gesture",
      "trigger_text": "text on button/link that triggers this connection"
    }}
  ],
  "shared_components": [
    {{
      "component_name": "Header",
      "used_in_frames": ["Frame1", "Frame2"],
      "description": "what this component does"
    }}
  ],
  "route_structure": {{
    "/": "Home Frame",
    "/login": "Login Frame",
    "/dashboard": "Dashboard Frame"
  }},
  "app_state": {{
    "global_state": ["user authentication", "theme", "language"],
    "shared_data": ["user profile", "preferences"]
  }}
}}

Do NOT include explanations or markdown. Return ONLY the JSON object."""

    system_prompt = f"""You are an expert {framework} application architect with deep knowledge of user experience and application design patterns.

FRAMEWORK EXPERTISE: {framework}
You are analyzing a comprehensive Figma design to create a logical application architecture.

ANALYSIS FOCUS:
- Identify logical connections between screens/frames
- Determine navigation patterns and user flows
- Extract shared components and data relationships
- Create proper routing structure for {framework}
- Understand the business logic and user journey

CRITICAL INSTRUCTIONS:
1. Analyze the frame content to understand the app's purpose
2. Look for UI elements that suggest navigation (buttons, links, menus)
3. Identify frames that are logically connected (login -> dashboard, signup -> login)
4. Consider {framework} best practices for navigation and routing
5. Always respond with valid JSON only - no explanations

Remember: You are creating the architecture foundation for a {framework} application. Every connection should be logical and user-friendly."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    debug_context = {
        "framework": framework,
        "design_summary_length": len(design_summary),
    }

    return PromptRequest(messages=messages, temperature=0.2, autodecide=False, debug_context=debug_context)
