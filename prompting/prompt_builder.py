"""Prompt builders for AI-driven code generation workflows."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from prompting.framework_utils import (
  format_component_identifier,
  get_app_file_paths,
  get_component_extension,
  get_component_file_path,
  get_default_dependencies,
)


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


def build_enhanced_frame_prompt(
    frame: Dict[str, Any],
    framework: str,
    job_id: str,
    framework_structure: Dict[str, Any],
    app_architecture: Dict[str, Any],
    design_summary: str,
    resolved_dependencies: Optional[Dict[str, Any]] = None,
) -> PromptRequest:
    """Construct the enhanced frame generation prompt with architectural context."""

    frame_name = frame.get("name", "Frame")
    frame_id = frame.get("id", "unknown")

    comprehensive_data = frame.get("comprehensive_data", {})
    component_count = comprehensive_data.get("component_count", {})
    content = comprehensive_data.get("content", {})
    design_system = comprehensive_data.get("design_system", {})
    layout = comprehensive_data.get("layout", {})

    frame_connections = [
        conn
        for conn in app_architecture.get("frame_connections", [])
        if conn.get("from_frame") == frame_name or conn.get("to_frame") == frame_name
    ]

    design_details = f"""
=== COMPREHENSIVE FRAME DESIGN DATA FOR '{frame_name}' ===

Frame Basic Info:
- Name: {frame_name}
- ID: {frame_id}
- Dimensions: {comprehensive_data.get('basic_info', {}).get('dimensions', {})}
- Complexity Score: {comprehensive_data.get('complexity_score', 0)}

Component Counts:
- Total Elements: {component_count.get('total', 0)}
- Text Elements: {component_count.get('texts', 0)}
- Image Elements: {component_count.get('images', 0)}
- Interactive Elements: {component_count.get('buttons', 0) + component_count.get('inputs', 0)}
- Containers: {component_count.get('containers', 0)}

TEXT CONTENT ({len(content.get('texts', []))} elements):
{chr(10).join([f"- '{text.get('content', '')[:80]}' (Font: {text.get('style', {}).get('font_family', 'Default')} {text.get('style', {}).get('font_size', 14)}px, Color: {text.get('style', {}).get('color', '#000000')}, Context: {text.get('context', 'text')})" for text in content.get('texts', [])[:12]])}

INTERACTIVE ELEMENTS ({len(content.get('interactive_elements', []))} elements):
{chr(10).join([f"- {elem.get('type', 'unknown').upper()}: '{elem.get('text', elem.get('name', ''))}' (Action: {elem.get('action', 'click')})" for elem in content.get('interactive_elements', [])[:8]])}

DESIGN SYSTEM:
- Colors: {design_system.get('colors', [])[:12]}
- Typography: {len(design_system.get('typography', {}))} font combinations
- Background: {layout.get('background_color', '#ffffff')}
- Layout Type: {layout.get('layout_type', 'unknown')}

FRAME CONNECTIONS:
{chr(10).join([f"- {conn.get('trigger', 'Unknown')} '{conn.get('trigger_text', '')}' -> Navigate to '{conn.get('to_frame', 'Unknown')}' ({conn.get('connection_type', 'navigation')})" for conn in frame_connections])}

LAYOUT CONTAINERS ({len(content.get('containers', []))} containers):
{chr(10).join([f"- {container.get('name', 'Container')} ({container.get('type', 'unknown')}, Role: {container.get('layout_role', 'component')}, Children: {container.get('children_count', 0)})" for container in content.get('containers', [])[:10]])}
"""

    app_context = f"""
=== APPLICATION ARCHITECTURE CONTEXT ===

App Type: {app_architecture.get('app_architecture', {}).get('app_type', 'Application')}
Primary User Flow: {app_architecture.get('app_architecture', {}).get('primary_flow', 'Basic navigation')}
Navigation Pattern: {app_architecture.get('app_architecture', {}).get('navigation_pattern', 'standard')}

Route Structure:
{chr(10).join([f"- {route}: {destination}" for route, destination in app_architecture.get('route_structure', {}).items()])}

Shared Components Available:
{chr(10).join([f"- {comp.get('component_name', 'Unknown')}: {comp.get('description', 'No description')}" for comp in app_architecture.get('shared_components', [])])}

Global App State:
- State: {app_architecture.get('app_state', {}).get('global_state', [])}
- Shared Data: {app_architecture.get('app_state', {}).get('shared_data', [])}
"""

    dependencies_context = ""
    if resolved_dependencies:
        package_deps = resolved_dependencies.get("dependencies", {}).get("package.json", {})
        dependencies_context = f"""
=== RESOLVED PROJECT DEPENDENCIES ===

Current Dependencies:
{json.dumps(package_deps.get('dependencies', {}), indent=2)}

Current DevDependencies:
{json.dumps(package_deps.get('devDependencies', {}), indent=2)}

IMPORTANT: Use these existing dependencies. Only suggest additional dependencies if absolutely necessary for this specific frame's functionality.
"""

    target_framework = framework_structure.get("framework", framework).lower()
    default_dependencies = get_default_dependencies(target_framework)
    main_file_path = get_component_file_path(target_framework, frame_name)
    component_identifier = format_component_identifier(job_id, frame_name)

    user_prompt = f"""You are generating {target_framework.upper()} code for the frame "{frame_name}" within a complete application architecture.

CRITICAL: You are working with {target_framework.upper()} framework specifically. Generate ONLY {target_framework.upper()} code with {target_framework.upper()} syntax, imports, and patterns.

{app_context}

{dependencies_context}

{design_details}

Framework Structure to Follow:
{json.dumps(framework_structure.get('structure', {}), indent=2)}

Technology Stack:
{json.dumps(framework_structure.get('technology_stack', {}), indent=2)}

CRITICAL INSTRUCTIONS FOR {target_framework.upper()} CODE GENERATION:
1. Include ALL text content exactly as specified with proper styling
2. Implement ALL interactive elements (buttons, inputs, etc.) with proper navigation
3. Use the specified colors, typography, and layout structure
4. Implement frame connections (navigation to other frames)
5. Follow {target_framework.upper()} best practices and syntax conventions
6. Include proper {target_framework.upper()} imports and component structure
7. ESSENTIAL: Ensure component is properly exported as default export for easy importing
7. Add event handlers for interactive elements using {target_framework.upper()} patterns
8. Use consistent styling and responsive design appropriate for {target_framework.upper()}
9. Implement proper state management for interactive elements using {target_framework.upper()} patterns
10. Include proper routing/navigation for connected frames using {target_framework.upper()} navigation

NAVIGATION IMPLEMENTATION:
- Implement all frame connections specified above
- Use proper {target_framework.upper()} navigation patterns (NOT React Router or other framework patterns)
- Include proper event handlers for buttons/links using {target_framework.upper()} syntax
- Handle form submissions and user interactions with {target_framework.upper()} event handling

STYLING REQUIREMENTS:
- Use exact colors from design system
- Implement proper typography (font families, sizes, weights)
- Maintain layout structure and spacing
- Include hover states and interactive feedback using {target_framework.upper()} styling approaches

DEPENDENCY MANAGEMENT:
- Use the resolved dependencies provided above as your primary dependency base
- Only suggest additional dependencies if this frame requires specific functionality not covered
- Be conservative with new dependencies - avoid duplication
- Suggest only {target_framework.upper()}-compatible dependencies

Respond with ONLY a valid JSON object in this exact format (using {target_framework.upper()} syntax and file extension):
{{
  "component_name": "{component_identifier}",
  "content": "complete {target_framework.upper()} component code with ALL design elements, interactions, and navigation implemented",
  "dependencies": {{
    "required": {json.dumps(default_dependencies)},
    "additional_suggestions": [],
    "reasoning": "framework-specific dependencies for {target_framework.upper()}"
  }},
  "file_path": "{main_file_path}"
}}

IMPORTANT: The content must be pure {target_framework.upper()} code. Do NOT mix other framework patterns, syntax, or imports.
Do NOT include explanations, markdown formatting, or additional text. Return ONLY the JSON object."""

    system_prompt = f"""You are an expert {framework_structure.get('framework', framework)} developer specializing in {framework} development with deep knowledge of application architecture and user experience.

FRAMEWORK CONTEXT:
- Target Framework: {framework_structure.get('framework', framework)}
- Technology Stack: {', '.join(framework_structure.get('technology_stack', {}).get('core_libraries', [framework]))}
- Component Architecture: {framework_structure.get('structure', {}).get('component_style', 'modern')}
- Navigation System: {framework_structure.get('structure', {}).get('routing', {}).get('library', 'standard')}

APPLICATION CONTEXT:
- App Type: {app_architecture.get('app_architecture', {}).get('app_type', 'Application')}
- Total Frames: {len(app_architecture.get('route_structure', {}))}
- Navigation Pattern: {app_architecture.get('app_architecture', {}).get('navigation_pattern', 'standard')}

EXPERTISE REQUIREMENTS:
1. Generate production-ready {framework} component code
2. Implement complete design fidelity (colors, typography, layout)
3. Include proper navigation and user interactions
4. Follow {framework} best practices and conventions
5. Create responsive, accessible components
6. Implement proper state management and event handling
7. Include proper imports and dependencies

CRITICAL SUCCESS FACTORS:
- Every text element must be included with exact content and styling
- Every interactive element must have proper event handlers
- All navigation connections must be implemented
- Design system colors and typography must be used correctly
- Component must be fully functional and production-ready

Remember: You are building a complete {framework} component that perfectly matches the design and integrates with the application architecture. Every detail matters for user experience."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    debug_context = {
        "frame_name": frame_name,
        "framework": target_framework,
        "component_extension": get_component_extension(target_framework),
        "messages_preview": messages,
        "design_summary_length": len(design_summary or ""),
    }

    return PromptRequest(
        messages=messages,
        temperature=0.3,
        autodecide=False,
        debug_context=debug_context,
    )


def build_enhanced_main_app_prompt(
    frames: List[Dict[str, Any]],
    framework: str,
    framework_structure: Dict[str, Any],
    app_architecture: Dict[str, Any],
) -> PromptRequest:
    """Construct the prompt for generating the enhanced main application shell."""

    frame_names = [frame.get("name", "Frame") for frame in frames]
    route_structure = app_architecture.get("route_structure", {})
    shared_components = app_architecture.get("shared_components", [])
    app_info = app_architecture.get("app_architecture", {})

    target_framework = framework_structure.get("framework", framework).lower()
    file_paths = get_app_file_paths(target_framework)

    user_prompt = f"""Generate the complete main app structure for {target_framework.upper()} with full application architecture integration.

CRITICAL: You are working with {target_framework.upper()} framework specifically. Generate ONLY {target_framework.upper()} code with {target_framework.upper()} syntax, imports, and patterns.

=== APPLICATION ARCHITECTURE ===
App Type: {app_info.get('app_type', 'Application')}
Primary User Flow: {app_info.get('primary_flow', 'Navigation between frames')}
Navigation Pattern: {app_info.get('navigation_pattern', 'standard')}

Total Frames: {len(frames)}
Frame Names: {', '.join(frame_names)}

ROUTING STRUCTURE:
{json.dumps(route_structure, indent=2)}

SHARED COMPONENTS:
{json.dumps(shared_components, indent=2)}

GLOBAL APP STATE:
{json.dumps(app_architecture.get('app_state', {}), indent=2)}

FRAME STRUCTURE DETAILS:
{json.dumps(framework_structure.get('structure', {}), indent=2)}

TECHNOLOGY STACK:
{json.dumps(framework_structure.get('technology_stack', {}), indent=2)}

CRITICAL OUTPUT REQUIREMENTS:
{{
  "main_app": {{
    "content": "Complete application shell with layout, providers, and routing",
    "file_path": "{file_paths['main_app']}"
  }},
  "routing": {{
    "content": "Routing configuration code",
    "file_path": "{file_paths['routing']}"
  }},
  "entry_point": {{
    "content": "Entry point bootstrap code",
    "file_path": "{file_paths['entry_point']}"
  }},
  "global_styles": {{
    "content": "Global styles / theming",
    "file_path": "{file_paths['styles']}"
  }}
}}

Do NOT include explanations, markdown formatting, or additional text. Return ONLY the JSON object."""

    system_prompt = f"""You are an expert {framework_structure.get('framework', framework)} application architect specializing in {framework} development.

FRAMEWORK CONTEXT:
- Target Framework: {framework_structure.get('framework', framework)}
- Technology Stack: {', '.join(framework_structure.get('technology_stack', {}).get('core_libraries', [framework]))}
- Routing System: {framework_structure.get('structure', {}).get('routing', {}).get('library', 'standard')}
- Build Tool: {framework_structure.get('build_tool', 'vite')}

APPLICATION REQUIREMENTS:
- Create a complete {framework} application structure
- Implement proper routing for all frames/pages
- Include modern {framework} patterns and best practices
- Generate production-ready, scalable code architecture

CRITICAL INSTRUCTIONS:
1. Generate clean, production-ready {framework} main app code
2. Follow {framework} conventions and best practices
3. Include proper imports, routing, and app structure
4. Set up complete application foundation
5. Always respond with valid JSON only - no explanations

Remember: You are building the core {framework} application. Focus on {framework}-specific patterns and structure."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    debug_context = {
        "framework": target_framework,
        "total_frames": len(frames),
        "file_paths": file_paths,
        "messages_preview": messages,
    }

    return PromptRequest(
        messages=messages,
        temperature=0.3,
        autodecide=False,
        debug_context=debug_context,
    )


def build_dependency_reconciliation_prompt(
    preliminary_deps: Dict[str, Any],
    dependency_suggestions: List[Dict[str, Any]],
    framework_structure: Dict[str, Any],
) -> PromptRequest:
    """Construct the prompt for consolidating dependency suggestions."""

    framework = framework_structure.get("framework", "react")
    structure = framework_structure.get("structure", {})

    user_prompt = f"""Analyze these dependency suggestions and produce a single conflict-free dependency set for the {framework} project.

PROJECT CONTEXT:
Framework: {framework}
Structure: {json.dumps(structure, indent=2)}

PRELIMINARY DEPENDENCIES:
{json.dumps(preliminary_deps, indent=2)}

DEPENDENCY SUGGESTIONS FROM FRAMES:
{json.dumps(dependency_suggestions, indent=2)}

KNOWN COMPATIBLE COMBINATIONS:
Option 1 - Modern Vite Setup (Preferred):
{{
  "dependencies": {{
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0"
  }},
  "devDependencies": {{
    "typescript": "^5.3.3",
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "vite": "^5.0.8",
    "@vitejs/plugin-react": "^4.2.1"
  }}
}}

Option 2 - CRA Setup (ONLY if specifically needed):
{{
  "dependencies": {{
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0"
  }},
  "devDependencies": {{
    "react-scripts": "5.0.1",
    "typescript": "^4.9.5",
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0"
  }}
}}

NEVER MIX: react-scripts 5.x + TypeScript 5.x (GUARANTEED CONFLICT)

FORBIDDEN COMBINATIONS (WILL CAUSE npm install ERRORS):
❌ react-scripts + vite (conflicting build tools)
❌ react-scripts + @vitejs/plugin-react (conflicting build systems)
❌ react-scripts 5.x + typescript ^5.x (peer dependency conflict)
❌ Multiple build tools in same project (choose ONE: vite OR react-scripts)

MANDATORY CONSTRAINT: Choose EXACTLY ONE build system approach:
🟢 OPTION A (Modern Vite - RECOMMENDED): Use Vite + TypeScript 5.x
🟢 OPTION B (Legacy CRA): Use react-scripts + TypeScript 4.x (NOT 5.x)

YOU MUST NOT OUTPUT BOTH vite AND react-scripts IN SAME PACKAGE.JSON

CRITICAL DEPENDENCY RECONCILIATION REQUIREMENTS:
1. Merge all dependency suggestions intelligently
2. Resolve version conflicts using COMPATIBLE versions (not just latest)
3. Remove duplicate dependencies
4. Ensure all required {framework} dependencies are included
5. Group dependencies vs devDependencies correctly
6. Include only necessary dependencies (avoid bloat)
7. Add framework-specific testing and development dependencies
8. **CRITICAL**: Ensure compatibility between ALL selected packages - NO PEER DEPENDENCY CONFLICTS
9. **CRITICAL**: Check peer dependency requirements before selecting versions
10. **CRITICAL**: Use proven, stable version combinations that work together
11. **CRITICAL**: Avoid mixing incompatible versions (e.g., react-scripts 5.x with TypeScript 5.x)
12. **CRITICAL**: Prefer modern build tools (Vite) over legacy tools (CRA/react-scripts) to avoid conflicts
13. **CRITICAL**: Test-validate version compatibility in your knowledge base before recommending

IMPORTANT: Respond with ONLY a valid JSON object in this exact format:
{{
  "dependencies": {{
    "package.json": {{
      "dependencies": {{
        "react": "^18.2.0",
        "react-dom": "^18.2.0",
        "react-router-dom": "^6.8.0"
      }},
      "devDependencies": {{
        "@types/react": "^18.2.0",
        "@vitejs/plugin-react": "^4.2.1",
        "vite": "^5.0.8"
      }}
    }}
  }},
  "resolution_summary": {{
    "total_dependencies": 15,
    "conflicts_resolved": 3,
    "duplicates_removed": 2,
    "framework_specific_added": 5
  }}
}}

Do NOT include explanations, markdown formatting, or additional text. Return ONLY the JSON object."""

    system_prompt = f"""You are an expert {framework} dependency manager and package resolution specialist with deep knowledge of avoiding peer dependency conflicts.

FRAMEWORK EXPERTISE: {framework}
You have deep knowledge of {framework} ecosystem, package compatibility, version management, and build tools.

CRITICAL CONFLICT PREVENTION KNOWLEDGE:
- react-scripts 5.x is INCOMPATIBLE with TypeScript 5.x (use TypeScript 4.x or avoid react-scripts)
- Vite is PREFERRED over Create React App/react-scripts for modern {framework} projects
- Always check peer dependency requirements before selecting versions
- Use @vitejs/plugin-react with Vite instead of react-scripts for zero conflicts
- For TypeScript projects: Vite + TypeScript 5.x works perfectly
- For CRA projects: react-scripts + TypeScript 4.x max
- Styled-components, emotion, tailwind should specify compatible versions
- Testing libraries (@testing-library/*) should match {framework} version

CRITICAL RESPONSIBILITIES:
1. **PREVENT PEER DEPENDENCY CONFLICTS** - This is your #1 priority
2. Resolve dependency conflicts intelligently using compatible versions
3. Ensure version compatibility across ALL packages (no exceptions)
4. Minimize package bloat while meeting all functionality requirements
5. Group dependencies correctly (runtime vs development)
6. Include essential {framework} tooling and testing dependencies
7. Provide clean, production-ready dependency resolution that npm install will succeed

QUALITY STANDARDS:
- ALL packages must be compatible with each other (zero conflicts)
- Use stable, well-maintained package versions that work together
- Follow {framework} community best practices for modern development
- Ensure optimal build performance and bundle size
- Prefer modern tooling (Vite) over legacy (CRA) when possible
- Include proper TypeScript support with compatible versions

VALIDATION REQUIREMENT:
Before suggesting any dependencies, mentally verify that npm install will succeed without conflicts.

Remember: A dependency file that causes npm install errors is COMPLETELY USELESS. Your job is to create a conflict-free, installable package.json."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    debug_context = {
        "framework": framework,
        "suggestion_count": len(dependency_suggestions),
        "messages_preview": messages,
    }

    return PromptRequest(
        messages=messages,
        temperature=0.2,
        autodecide=False,
        debug_context=debug_context,
    )
