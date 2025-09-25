"""
Figma-to-Code Converter - Main FastAPI Application
Web interface for converting Figma designs to code with real-time updates
"""

import asyncio
import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
import uvicorn
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import dotenv
from pydantic import BaseModel

# Import our custom modules
from enhanced_figma_processor import EnhancedFigmaProcessor
from ai_engine import AI_engine
from framework_generators import generate_framework_code
from component_collector import ComponentCollector
from project_assembler import ProjectAssembler
from ai_response_parser import AIResponseParser
from ai_framework_detector import AIFrameworkDetector

# Load environment variables
dotenv.load_dotenv()

# =============================================================================
# THREADING CONFIGURATION
# =============================================================================
# Global variable for maximum threads - None means unlimited (use all available cores)
# Can be configured by user or environment variable
MAX_THREADS = None

def set_max_threads(threads: Optional[int] = None):
    """
    Set the maximum number of threads for concurrent frame processing.
    
    Args:
        threads: Maximum number of threads. None for unlimited (default).
                 If not specified, checks environment variable MAX_THREADS.
    """
    global MAX_THREADS
    if threads is not None:
        MAX_THREADS = threads
    elif os.getenv('MAX_THREADS'):
        try:
            MAX_THREADS = int(os.getenv('MAX_THREADS'))
        except ValueError:
            print("⚠️ Invalid MAX_THREADS environment variable, using default (None)")
            MAX_THREADS = None
    
    if MAX_THREADS is None:
        print("🔄 Threading: Using unlimited threads (all available cores)")
    else:
        print(f"🔄 Threading: Limited to {MAX_THREADS} concurrent threads")

# Initialize threading configuration
set_max_threads()

# Initialize FastAPI app
app = FastAPI(
    title="Figma-to-Code Converter",
    description="Convert Figma designs to production-ready code",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Pydantic models
class ConversionRequest(BaseModel):
    figma_url: str
    pat_token: Optional[str] = None
    target_framework: str  # Can now be any text description
    include_components: bool = True

class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: int
    message: str
    result: Optional[Dict] = None

# Global job storage (in production, use Redis/database)
jobs: Dict[str, Dict] = {}

def discover_framework_structure(ai_engine: 'AI_engine', parser: AIResponseParser, framework: str, design_data: Dict) -> Optional[Dict[str, Any]]:
    """Discover framework structure using AI - first phase of code generation"""
    try:
        frames = design_data.get("frames", [])
        total_frames = len(frames)
        total_components = design_data.get("total_components", 0)

        prompt = f"""Analyze the {framework} framework and provide its complete structure for a project with {total_frames} frames and {total_components} components.

Based on the Figma design analysis, determine the optimal project structure, dependencies, and configuration for {framework}.

IMPORTANT: Respond with ONLY a valid JSON object in this exact format:
{{
  "framework": "{framework}",
  "version": "latest stable version",
  "structure": {{
    "component_extension": ".jsx or .vue or .ts etc",
    "main_file": "src/App.jsx",
    "config_files": ["package.json", "vite.config.js", "tsconfig.json"],
    "folder_structure": {{
      "src": ["components", "pages", "utils", "assets"],
      "public": ["index.html", "assets"],
      "config": ["webpack.config.js"]
    }}
  }},
  "styling": {{
    "primary": "css-modules or styled-components or tailwind",
    "secondary": ["alternative styling approaches"]
  }},
  "routing": {{
    "library": "react-router-dom or vue-router etc",
    "version": "latest version"
  }},
  "build_tool": "vite or webpack or rollup",
  "package_manager": "npm or yarn or pnpm"
}}

Do NOT include any explanations, markdown formatting, or additional text. Return ONLY the JSON object."""

        # Enhanced system prompt for framework discovery
        framework_discovery_system = f"""You are an expert {framework} architect and developer with deep knowledge of {framework} ecosystem.

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
            {"role": "system", "content": framework_discovery_system},
            {"role": "user", "content": prompt}
        ]

        print(f"🤖 AI Request - Framework Discovery:")
        print(f"   Framework: {framework}")
        print(f"   Messages: {json.dumps(messages, indent=2)}")
        print(f"   Temperature: 0.1, Auto-decide: False")
        print()

        result = ai_engine.chat_completion(messages, temperature=0.1, autodecide=False)

        print(f"🤖 AI Response - Framework Discovery:")
        print(f"   Success: {result.success}")
        if result.success:
            print(f"   Response Content: {result.content[:500]}...")
        else:
            print(f"   Error: {result.error_message}")
        print()

        if result.success:
            try:
                # Parse JSON response using the parser
                structure_data = parser.parse_framework_discovery_response(result.content.strip())
                return structure_data
            except ValueError as e:
                print(f"❌ Failed to parse framework discovery response: {e}")
                print(f"Raw response: {result.content[:500]}...")
                return None
        else:
            print(f"❌ Framework discovery failed: {result.error_message}")
            return None

    except Exception as e:
        print(f"❌ Error during framework discovery: {e}")
        return None

def generate_frame_code_with_ai(ai_engine: 'AI_engine', frame: Dict, framework: str, job_id: str, parser: AIResponseParser, framework_structure: Dict) -> Dict[str, str]:
    """Generate component code for a single frame using AI with comprehensive design data"""
    try:
        frame_name = frame.get('name', 'Frame')
        frame_id = frame.get('id', 'unknown')
        
        # Get comprehensive frame data - this is the rich information!
        comprehensive_data = frame.get('comprehensive_data', {})
        component_count = comprehensive_data.get('component_count', {})
        content = comprehensive_data.get('content', {})
        design_system = comprehensive_data.get('design_system', {})
        layout = comprehensive_data.get('layout', {})

        # Format comprehensive design information for AI
        design_details = f"""
COMPREHENSIVE FRAME DESIGN DATA:

Frame Basic Info:
- Name: {frame_name}
- ID: {frame_id}
- Dimensions: {comprehensive_data.get('basic_info', {}).get('dimensions', {})}
- Complexity Score: {comprehensive_data.get('complexity_score', 0)}

Component Counts:
- Total Elements: {component_count.get('total', 0)}
- Text Elements: {component_count.get('texts', 0)}
- Image Elements: {component_count.get('images', 0)}
- Interactive Elements (Buttons/Inputs): {component_count.get('buttons', 0) + component_count.get('inputs', 0)}
- Containers: {component_count.get('containers', 0)}

Text Content ({len(content.get('texts', []))} text elements):
{chr(10).join([f"- '{text.get('content', '')[:50]}...' ({text.get('style', {}).get('font_family', 'Unknown')} {text.get('style', {}).get('font_size', 14)}px, {text.get('context', 'text')})" for text in content.get('texts', [])[:8]])}

Images ({len(content.get('images', []))} images):
{chr(10).join([f"- {img.get('name', 'Image')} ({img.get('context', 'image')}, {img.get('position', {}).get('width', 0)}x{img.get('position', {}).get('height', 0)}px)" for img in content.get('images', [])[:5]])}

Interactive Elements ({len(content.get('interactive_elements', []))} elements):
{chr(10).join([f"- {elem.get('type', 'unknown').upper()}: '{elem.get('text', elem.get('name', ''))}'" for elem in content.get('interactive_elements', [])[:5]])}

Design System:
- Colors Used: {design_system.get('colors', [])[:10]}
- Typography: {len(design_system.get('typography', {}))} font combinations
- Background: {layout.get('background_color', '#ffffff')}
- Layout Type: {comprehensive_data.get('structure', {}).get('layout_type', 'unknown')}

Layout Containers ({len(content.get('containers', []))} containers):
{chr(10).join([f"- {container.get('name', 'Container')} ({container.get('type', 'unknown')}, {container.get('layout_role', 'component')})" for container in content.get('containers', [])[:8]])}

IMPORTANT: Use this comprehensive design data to generate accurate, complete component code that matches the actual design structure, styling, content, and interactions."""

        prompt = f"""You are generating {framework_structure.get('framework', framework)} code for the frame "{frame_name}".

{design_details}

Framework Structure to Follow:
{json.dumps(framework_structure.get('structure', {}), indent=2)}

Technology Stack:
{json.dumps(framework_structure.get('technology_stack', {}), indent=2)}

IMPORTANT: Generate complete, production-ready component code that:
1. Includes ALL text content exactly as specified
2. Implements ALL interactive elements (buttons, inputs, etc.)
3. Uses the specified colors and typography
4. Maintains proper layout structure and positioning
5. Includes proper styling and responsive design
6. Follows {framework_structure.get('framework', framework)} best practices

Respond with ONLY a valid JSON object in this exact format:
{{
  "component_name": "Frame{job_id.replace('-', '')}",
  "content": "complete component code as string with all design elements implemented",
  "dependencies": ["react", "react-dom"],
  "file_path": "src/components/Frame{job_id.replace('-', '')}.jsx"
}}

Do NOT include any explanations, markdown formatting, or additional text. Return ONLY the JSON object."""

        # Enhanced system prompt with framework context
        system_prompt = f"""You are an expert {framework_structure.get('framework', framework)} developer specialized in {framework} development.

FRAMEWORK CONTEXT:
- Target Framework: {framework_structure.get('framework', framework)}
- Technology Stack: {', '.join(framework_structure.get('technology_stack', {}).get('core_libraries', [framework]))}
- Component Architecture: {framework_structure.get('structure', {}).get('component_style', 'modern')}

IMPORTANT INSTRUCTIONS:
1. Generate clean, production-ready {framework} component code
2. Follow {framework} best practices and conventions
3. Include proper imports, styling, and component structure
4. Implement ALL design elements from the comprehensive data provided
5. Use the exact text content, colors, and styling specified
6. Always respond with valid JSON only - no explanations or markdown

Remember: You are building {framework} components. Stay focused on {framework} syntax and patterns."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        print(f"🤖 AI Request - Frame Code Generation:")
        print(f"   Frame: {frame_name} (ID: {frame_id})")
        print(f"   Framework: {framework}")
        print(f"   Total Components: {component_count.get('total', 0)}")
        print(f"   Texts: {component_count.get('texts', 0)}, Images: {component_count.get('images', 0)}")
        print(f"   Interactive: {component_count.get('buttons', 0) + component_count.get('inputs', 0)}")
        print(f"   Complexity Score: {comprehensive_data.get('complexity_score', 0)}")
        print(f"   Temperature: 0.3, Auto-decide: False")
        print()

        result = ai_engine.chat_completion(messages, temperature=0.3, autodecide=False)

        print(f"🤖 AI Response - Frame Code Generation:")
        print(f"   Success: {result.success}")
        if result.success:
            print(f"   Response Content: {result.content[:500]}...")
        else:
            print(f"   Error: {result.error_message}")
        print()

        if result.success:
            try:
                # Parse JSON response using the parser
                component_data = parser.parse_component_generation_response(result.content.strip())
                return {
                    component_data['file_path']: component_data['content']
                }
            except ValueError as e:
                print(f"❌ Failed to parse component generation response for frame {frame_name}: {e}")
                return {}
        else:
            print(f"❌ Component generation failed for frame {frame_name}: {result.error_message}")
            return {}

    except Exception as e:
        print(f"❌ Error generating frame code for {frame.get('name', 'unknown')}: {e}")
        return {}

def generate_main_app_with_ai(ai_engine: 'AI_engine', frames: List[Dict], framework: str, job_id: str, parser: AIResponseParser, framework_structure: Dict) -> Dict[str, str]:
    """Generate main app file using AI"""
    try:
        total_frames = len(frames)
        frame_names = [f.get('name', 'Frame') for f in frames]

        prompt = f"""Generate the main app file for {framework} with {total_frames} frames: {', '.join(frame_names)}.

Framework structure: {json.dumps(framework_structure.get('structure', {}), indent=2)}

IMPORTANT: Respond with ONLY a valid JSON object in this exact format:
{{
  "main_app": {{
    "content": "complete main app code as string",
    "file_path": "src/App.jsx"
  }},
  "routing": {{
    "content": "routing configuration code",
    "file_path": "src/router.jsx"
  }},
  "entry_point": {{
    "content": "entry point code (index.js/main.js)",
    "file_path": "src/main.jsx"
  }},
  "global_styles": {{
    "content": "global CSS/styles",
    "file_path": "src/index.css"
  }}
}}

Do NOT include any explanations, markdown formatting, or additional text. Return ONLY the JSON object."""

        # Enhanced system prompt for main app generation
        main_app_system = f"""You are an expert {framework} application architect specializing in {framework} development.

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
            {"role": "system", "content": main_app_system},
            {"role": "user", "content": prompt}
        ]

        print(f"🤖 AI Request - Main App Generation:")
        print(f"   Framework: {framework}")
        print(f"   Frames: {frame_names}")
        print(f"   Total Frames: {total_frames}")
        print(f"   Messages: {json.dumps(messages, indent=2)}")
        print(f"   Temperature: 0.3, Auto-decide: False")
        print()

        result = ai_engine.chat_completion(messages, temperature=0.3, autodecide=False)

        print(f"🤖 AI Response - Main App Generation:")
        print(f"   Success: {result.success}")
        if result.success:
            print(f"   Response Content: {result.content[:500]}...")
        else:
            print(f"   Error: {result.error_message}")
        print()

        if result.success:
            try:
                # Parse JSON response using the parser
                app_data = parser.parse_main_app_generation_response(result.content.strip())
                
                # Extract all files from the response
                files = {}
                if 'main_app' in app_data:
                    files[app_data['main_app']['file_path']] = app_data['main_app']['content']
                if 'routing' in app_data:
                    files[app_data['routing']['file_path']] = app_data['routing']['content']
                if 'entry_point' in app_data:
                    files[app_data['entry_point']['file_path']] = app_data['entry_point']['content']
                if 'global_styles' in app_data:
                    files[app_data['global_styles']['file_path']] = app_data['global_styles']['content']
                
                return files
            except ValueError as e:
                print(f"❌ Failed to parse main app generation response: {e}")
                return {}
        else:
            print(f"❌ Main app generation failed: {result.error_message}")
            return {}

    except Exception as e:
        print(f"❌ Error generating main app: {e}")
        return {}

def generate_enhanced_frame_code_with_ai(ai_engine: 'AI_engine', frame: Dict, framework: str, job_id: str, parser: AIResponseParser, framework_structure: Dict, app_architecture: Dict, design_summary: str) -> Dict[str, str]:
    """Generate enhanced component code for a single frame using AI with complete architecture context"""
    try:
        frame_name = frame.get('name', 'Frame')
        frame_id = frame.get('id', 'unknown')
        
        # Get comprehensive frame data
        comprehensive_data = frame.get('comprehensive_data', {})
        component_count = comprehensive_data.get('component_count', {})
        content = comprehensive_data.get('content', {})
        design_system = comprehensive_data.get('design_system', {})
        layout = comprehensive_data.get('layout', {})

        # Extract connections for this frame from architecture
        frame_connections = []
        for conn in app_architecture.get('frame_connections', []):
            if conn.get('from_frame') == frame_name or conn.get('to_frame') == frame_name:
                frame_connections.append(conn)

        # Format comprehensive design information for AI
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

        # Application architecture context
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

        prompt = f"""You are generating {framework_structure.get('framework', framework)} code for the frame "{frame_name}" within a complete application architecture.

{app_context}

{design_details}

Framework Structure to Follow:
{json.dumps(framework_structure.get('structure', {}), indent=2)}

Technology Stack:
{json.dumps(framework_structure.get('technology_stack', {}), indent=2)}

CRITICAL INSTRUCTIONS FOR CODE GENERATION:
1. Include ALL text content exactly as specified with proper styling
2. Implement ALL interactive elements (buttons, inputs, etc.) with proper navigation
3. Use the specified colors, typography, and layout structure
4. Implement frame connections (navigation to other frames)
5. Follow {framework_structure.get('framework', framework)} best practices
6. Include proper imports and component structure
7. Add event handlers for interactive elements
8. Use consistent styling and responsive design
9. Implement proper state management for interactive elements
10. Include proper routing/navigation for connected frames

NAVIGATION IMPLEMENTATION:
- Implement all frame connections specified above
- Use proper {framework} navigation patterns
- Include proper event handlers for buttons/links
- Handle form submissions and user interactions

STYLING REQUIREMENTS:
- Use exact colors from design system
- Implement proper typography (font families, sizes, weights)
- Maintain layout structure and spacing
- Include hover states and interactive feedback

Respond with ONLY a valid JSON object in this exact format:
{{
  "component_name": "Frame{job_id.replace('-', '')}_{frame_name.replace(' ', '')}",
  "content": "complete component code with ALL design elements, interactions, and navigation implemented",
  "dependencies": ["react", "react-router-dom", "styled-components"],
  "file_path": "src/components/{frame_name.replace(' ', '')}.jsx"
}}

Do NOT include explanations, markdown formatting, or additional text. Return ONLY the JSON object."""

        # Enhanced system prompt with complete context
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
            {"role": "user", "content": prompt}
        ]

        result = ai_engine.chat_completion(messages, temperature=0.3, autodecide=False)

        if result.success:
            try:
                # Parse JSON response directly
                # Clean JSON response
                cleaned_response = result.content.strip()
                # Remove markdown code blocks if present
                cleaned_response = re.sub(r'```json\n?', '', cleaned_response)
                cleaned_response = re.sub(r'```\n?', '', cleaned_response)
                # Remove any text before the first { or [
                cleaned_response = re.sub(r'^[^{\[]*', '', cleaned_response)
                # Remove any text after the last } or ]
                cleaned_response = re.sub(r'[^}\]]*$', '', cleaned_response)
                frame_data = json.loads(cleaned_response)
                
                # Return as file dictionary
                return {
                    frame_data.get('file_path', f"src/components/{frame_name.replace(' ', '')}.jsx"): frame_data.get('content', '')
                }
            except (ValueError, KeyError, TypeError) as e:
                print(f"❌ Failed to parse enhanced frame response for '{frame_name}': {e}")
                print(f"Raw response: {result.content[:200]}...")
                return {}
        else:
            print(f"❌ Enhanced frame generation failed for '{frame_name}': {result.error_message}")
            return {}

    except Exception as e:
        print(f"❌ Error generating enhanced frame code for '{frame_name}': {e}")
        return {}

def generate_enhanced_main_app_with_ai(ai_engine: 'AI_engine', frames: List[Dict], framework: str, job_id: str, parser: AIResponseParser, framework_structure: Dict, app_architecture: Dict) -> Dict[str, str]:
    """Generate enhanced main app file using AI with complete architecture context"""
    try:
        total_frames = len(frames)
        frame_names = [f.get('name', 'Frame') for f in frames]

        # Extract routing information from architecture
        route_structure = app_architecture.get('route_structure', {})
        shared_components = app_architecture.get('shared_components', [])
        app_info = app_architecture.get('app_architecture', {})

        prompt = f"""Generate the complete main app structure for {framework} with full application architecture integration.

=== APPLICATION ARCHITECTURE ===
App Type: {app_info.get('app_type', 'Application')}
Primary User Flow: {app_info.get('primary_flow', 'Navigation between frames')}
Navigation Pattern: {app_info.get('navigation_pattern', 'standard')}

Total Frames: {total_frames}
Frame Names: {', '.join(frame_names)}

ROUTING STRUCTURE:
{chr(10).join([f"- {route}: {destination}" for route, destination in route_structure.items()])}

SHARED COMPONENTS:
{chr(10).join([f"- {comp.get('component_name', 'Unknown')}: {comp.get('description', 'Component')}" for comp in shared_components])}

FRAME CONNECTIONS:
{chr(10).join([f"- {conn.get('from_frame', 'Unknown')} -> {conn.get('to_frame', 'Unknown')} ({conn.get('connection_type', 'navigation')})" for conn in app_architecture.get('frame_connections', [])])}

Framework Structure:
{json.dumps(framework_structure.get('structure', {}), indent=2)}

IMPORTANT: Generate a complete {framework} application that includes:
1. Proper routing for all frames based on the route structure
2. Navigation implementation matching the architecture
3. Shared component integration
4. Global state management setup
5. Main app layout and structure
6. Entry point configuration
7. Global styling and theme setup

Respond with ONLY a valid JSON object in this exact format:
{{
  "main_app": {{
    "content": "complete main app code with routing and architecture implementation",
    "file_path": "src/App.jsx"
  }},
  "routing": {{
    "content": "routing configuration with all frame routes",
    "file_path": "src/router.jsx"
  }},
  "entry_point": {{
    "content": "entry point code with providers and setup",
    "file_path": "src/main.jsx"
  }},
  "global_styles": {{
    "content": "global CSS with design system colors and typography",
    "file_path": "src/index.css"
  }}
}}

Do NOT include explanations, markdown formatting, or additional text. Return ONLY the JSON object."""

        # Enhanced system prompt for main app generation
        main_app_system = f"""You are an expert {framework} application architect specializing in {framework} development with deep knowledge of application structure and routing.

FRAMEWORK CONTEXT:
- Target Framework: {framework_structure.get('framework', framework)}
- Technology Stack: {', '.join(framework_structure.get('technology_stack', {}).get('core_libraries', [framework]))}
- Routing System: {framework_structure.get('structure', {}).get('routing', {}).get('library', 'standard')}
- Build Tool: {framework_structure.get('build_tool', 'vite')}

APPLICATION REQUIREMENTS:
- Create a complete {framework} application foundation
- Implement proper routing for all frames/pages
- Include modern {framework} patterns and best practices
- Generate production-ready, scalable code architecture
- Integrate shared components and global state management
- Set up proper navigation and user flow

ARCHITECTURAL EXPERTISE:
1. Generate clean, production-ready {framework} main app code
2. Follow {framework} conventions and best practices
3. Include proper imports, routing, and app structure
4. Set up complete application foundation with providers
5. Implement proper routing based on architecture analysis
6. Include global styling with design system integration
7. Create scalable, maintainable application structure

Remember: You are building the core {framework} application foundation that will host all the generated frame components. The architecture must be robust and follow {framework} best practices."""

        messages = [
            {"role": "system", "content": main_app_system},
            {"role": "user", "content": prompt}
        ]

        result = ai_engine.chat_completion(messages, temperature=0.3, autodecide=False)

        if result.success:
            try:
                # Parse JSON response using the parser
                app_data = parser.parse_main_app_generation_response(result.content.strip())
                
                # Extract all files from the response
                files = {}
                for section_name, section_data in app_data.items():
                    if isinstance(section_data, dict) and 'content' in section_data and 'file_path' in section_data:
                        files[section_data['file_path']] = section_data['content']
                
                return files
            except ValueError as e:
                print(f"❌ Failed to parse enhanced main app generation response: {e}")
                return {}
        else:
            print(f"❌ Enhanced main app generation failed: {result.error_message}")
            return {}

    except Exception as e:
        print(f"❌ Error generating enhanced main app: {e}")
        return {}

def generate_config_files_from_structure(framework_structure: Dict, frames: List[Dict]) -> Dict[str, str]:
    """Generate configuration files based on discovered framework structure"""
    files = {}
    framework = framework_structure.get('framework', 'react')
    structure = framework_structure.get('structure', {})
    config_files = structure.get('config_files', [])

    # Generate package.json based on framework
    if 'package.json' in config_files or framework in ['react', 'vue', 'angular']:
        if framework == 'react':
            files['package.json'] = generate_react_package_json(frames)
        elif framework == 'vue':
            files['package.json'] = generate_vue_package_json(frames)
        elif framework == 'angular':
            files['package.json'] = generate_angular_package_json(frames)

    # Generate entry point files
    main_file = structure.get('main_file', 'src/App.js')
    if main_file.endswith('.js') or main_file.endswith('.jsx'):
        files['src/index.js'] = generate_react_index_js()
    elif main_file.endswith('.ts'):
        files['src/main.ts'] = generate_angular_main_ts()

    # Generate HTML files
    if framework in ['react', 'vue']:
        files['public/index.html'] = generate_react_html() if framework == 'react' else generate_vue_html()
    elif framework == 'angular':
        files['src/index.html'] = generate_angular_index_html()

    # Generate Flutter files
    if framework == 'flutter':
        files['pubspec.yaml'] = generate_flutter_pubspec(frames)
        files['lib/main.dart'] = generate_flutter_main_dart()

    # Generate CSS
    files['src/index.css'] = generate_basic_css()

    return files

def create_comprehensive_design_summary(design_data: Dict) -> str:
    """
    Parse all Figma data and create one comprehensive string with frames, components, and data
    organized by frames for AI context.
    """
    frames = design_data.get("frames", [])
    total_components = design_data.get("total_components", 0)
    file_key = design_data.get("file_key", "unknown")
    
    summary_parts = []
    
    # Header with overall design info
    summary_parts.append(f"""=== FIGMA DESIGN COMPREHENSIVE SUMMARY ===
File Key: {file_key}
Total Frames: {len(frames)}
Total Components: {total_components}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

""")
    
    # Process each frame in detail
    for frame_idx, frame in enumerate(frames, 1):
        frame_name = frame.get('name', f'Frame_{frame_idx}')
        frame_id = frame.get('id', 'unknown')
        
        summary_parts.append(f"""--- FRAME {frame_idx}: {frame_name} ---
Frame ID: {frame_id}
""")
        
        # Check for comprehensive data from EnhancedFrameParser
        comprehensive_data = frame.get('comprehensive_data', {})
        
        if comprehensive_data:
            # Extract rich information
            basic_info = comprehensive_data.get('basic_info', {})
            component_count = comprehensive_data.get('component_count', {})
            content = comprehensive_data.get('content', {})
            design_system = comprehensive_data.get('design_system', {})
            layout = comprehensive_data.get('layout', {})
            
            # Basic frame info
            dimensions = basic_info.get('dimensions', {})
            if dimensions:
                summary_parts.append(f"Dimensions: {dimensions.get('width', 0)}x{dimensions.get('height', 0)}px\n")
            
            summary_parts.append(f"Background: {basic_info.get('background_color', '#ffffff')}\n")
            summary_parts.append(f"Complexity Score: {comprehensive_data.get('complexity_score', 0)}\n")
            
            # Component counts
            summary_parts.append(f"""
Component Breakdown:
- Total Elements: {component_count.get('total', 0)}
- Text Elements: {component_count.get('texts', 0)}
- Image Elements: {component_count.get('images', 0)}
- Interactive Elements: {component_count.get('buttons', 0) + component_count.get('inputs', 0)}
- Containers: {component_count.get('containers', 0)}
""")
            
            # Text content details
            texts = content.get('texts', [])
            if texts:
                summary_parts.append("Text Content:\n")
                for i, text in enumerate(texts[:10], 1):  # Limit to first 10 texts
                    text_content = text.get('content', '')
                    style = text.get('style', {})
                    context = text.get('context', 'text')
                    summary_parts.append(f"  {i}. '{text_content}' ({style.get('font_family', 'Unknown')} {style.get('font_size', 14)}px, {style.get('color', '#000000')}, {context})\n")
                if len(texts) > 10:
                    summary_parts.append(f"  ... and {len(texts) - 10} more text elements\n")
            
            # Interactive elements
            interactive_elements = content.get('interactive_elements', [])
            if interactive_elements:
                summary_parts.append("\nInteractive Elements:\n")
                for i, elem in enumerate(interactive_elements, 1):
                    elem_type = elem.get('type', 'unknown').upper()
                    elem_text = elem.get('text', elem.get('name', ''))
                    summary_parts.append(f"  {i}. {elem_type}: '{elem_text}'\n")
            
            # Design system
            colors = design_system.get('colors', [])
            if colors:
                summary_parts.append(f"\nColor Palette: {', '.join(colors[:8])}")
                if len(colors) > 8:
                    summary_parts.append(f" (and {len(colors) - 8} more)")
                summary_parts.append("\n")
            
            typography = design_system.get('typography', {})
            if typography:
                summary_parts.append(f"Typography: {len(typography)} font combinations\n")
            
            # Layout info
            layout_type = layout.get('layout_type', 'unknown')
            summary_parts.append(f"Layout Type: {layout_type}\n")
            
        else:
            # Fallback to basic component info if no comprehensive data
            components = frame.get('components', [])
            summary_parts.append(f"Components: {len(components)} components\n")
            if components:
                for i, comp in enumerate(components[:5], 1):
                    comp_name = comp.get('name', f'Component_{i}')
                    comp_type = comp.get('type', 'UNKNOWN')
                    summary_parts.append(f"  {i}. {comp_name} ({comp_type})\n")
        
        summary_parts.append("\n")
    
    return "".join(summary_parts)

def generate_app_architecture_with_ai(ai_engine: 'AI_engine', design_summary: str, framework: str, parser: AIResponseParser) -> Dict[str, Any]:
    """
    Use AI to determine frame interconnections and app architecture based on comprehensive design data.
    """
    try:
        print("🏗️ Generating app architecture and frame interconnections...")
        
        architecture_prompt = f"""Analyze this comprehensive Figma design and create a complete app architecture with frame interconnections for {framework}.

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

        # Enhanced system prompt for architecture analysis
        architecture_system = f"""You are an expert {framework} application architect with deep knowledge of user experience and application design patterns.

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
            {"role": "system", "content": architecture_system},
            {"role": "user", "content": architecture_prompt}
        ]

        print(f"🤖 AI Request - App Architecture Analysis:")
        print(f"   Framework: {framework}")
        print(f"   Design Summary Length: {len(design_summary)} characters")
        print(f"   Temperature: 0.2, Auto-decide: False")
        print()

        result = ai_engine.chat_completion(messages, temperature=0.2, autodecide=False)

        print(f"🤖 AI Response - App Architecture:")
        print(f"   Success: {result.success}")
        if result.success:
            print(f"   Response Content: {result.content[:300]}...")
        else:
            print(f"   Error: {result.error_message}")
        print()

        if result.success:
            try:
                # Parse JSON response directly
                # Clean JSON response
                cleaned_response = result.content.strip()
                # Remove markdown code blocks if present
                cleaned_response = re.sub(r'```json\n?', '', cleaned_response)
                cleaned_response = re.sub(r'```\n?', '', cleaned_response)
                # Remove any text before the first { or [
                cleaned_response = re.sub(r'^[^{\[]*', '', cleaned_response)
                # Remove any text after the last } or ]
                cleaned_response = re.sub(r'[^}\]]*$', '', cleaned_response)
                architecture_data = json.loads(cleaned_response)
                return architecture_data
            except ValueError as e:
                print(f"❌ Failed to parse architecture response: {e}")
                print(f"Raw response: {result.content[:500]}...")
                return None
        else:
            print(f"❌ Architecture analysis failed: {result.error_message}")
            return None

    except Exception as e:
        print(f"❌ Architecture analysis error: {e}")
        return None

def generate_framework_code(design_data: Dict, framework: str, job_id: str, framework_detection: Dict = None) -> Dict[str, Any]:
    """Generate code for the specified framework using AI engine"""
    try:
        from pathlib import Path
        from ai_engine import AI_engine
        output_dir = Path(f"output/job_{job_id}")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize AI engine and parser
        ai_engine = AI_engine(verbose=True)
        parser = AIResponseParser()

        # Use detected framework structure if available
        if framework_detection:
            framework_structure = {
                'framework': framework_detection['framework'],
                'structure': framework_detection.get('project_structure', {}),
                'file_conventions': framework_detection.get('file_conventions', {}),
                'technology_stack': framework_detection.get('technology_stack', {})
            }
            print(f"🤖 Using AI-detected framework structure: {framework_detection['framework_name']}")
        else:
            # Fallback to old framework discovery
            framework_structure = discover_framework_structure(ai_engine, parser, framework, design_data)
            if not framework_structure:
                print(f"❌ Framework discovery failed for {framework}")
                return {
                    "framework": framework,
                    "files": {},
                    "main_file": "index.html",
                    "error": "Framework discovery failed"
                }

        print(f"🤖 Discovered {framework} structure: {framework_structure.get('structure', {})}")

        # =============================================================================
        # PHASE 1: Create comprehensive design summary
        # =============================================================================
        print("📊 Creating comprehensive design summary...")
        design_summary = create_comprehensive_design_summary(design_data)
        print(f"   📝 Generated {len(design_summary)} character design summary")

        # =============================================================================
        # PHASE 2: Generate app architecture and frame interconnections
        # =============================================================================
        app_architecture = generate_app_architecture_with_ai(ai_engine, design_summary, framework, parser)
        if not app_architecture:
            print("⚠️ Architecture analysis failed, using basic structure")
            app_architecture = {
                "app_architecture": {"app_type": "Multi-page Application", "primary_flow": "Basic navigation"},
                "frame_connections": [],
                "shared_components": [],
                "route_structure": {},
                "app_state": {"global_state": [], "shared_data": []}
            }

        # =============================================================================
        # PHASE 3: Generate code for each frame using AI with concurrent processing
        # =============================================================================
        generated_files = {}
        frames = design_data.get("frames", [])
        
        print(f"🚀 Using AI engine with threading to generate {framework} code for {len(frames)} frames...")
        print(f"   🔄 Threading: {'Unlimited threads' if MAX_THREADS is None else f'{MAX_THREADS} threads'}")
        
        # Function to process a single frame
        def process_frame(frame):
            """Process a single frame with enhanced context"""
            try:
                thread_id = threading.current_thread().ident
                frame_name = frame.get('name', 'Unknown')
                print(f"   🧵 Thread {thread_id}: Processing frame '{frame_name}'")
                
                frame_code = generate_enhanced_frame_code_with_ai(
                    ai_engine, frame, framework, job_id, parser, 
                    framework_structure, app_architecture, design_summary
                )
                
                if frame_code:
                    print(f"   ✅ Thread {thread_id}: Completed frame '{frame_name}'")
                    return frame_code
                else:
                    print(f"   ❌ Thread {thread_id}: Failed frame '{frame_name}'")
                    return {}
                    
            except Exception as e:
                frame_name = frame.get('name', 'Unknown')
                print(f"   💥 Thread error processing frame '{frame_name}': {e}")
                return {}

        # Process frames concurrently
        start_time = time.time()
        
        if len(frames) == 1:
            # Single frame - no need for threading
            print("   📄 Single frame detected, processing directly")
            frame_code = process_frame(frames[0])
            generated_files.update(frame_code)
        else:
            # Multiple frames - use ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
                # Submit all frame processing tasks
                future_to_frame = {
                    executor.submit(process_frame, frame): frame 
                    for frame in frames
                }
                
                # Collect results as they complete
                for future in as_completed(future_to_frame):
                    frame = future_to_frame[future]
                    try:
                        frame_code = future.result()
                        generated_files.update(frame_code)
                    except Exception as e:
                        frame_name = frame.get('name', 'Unknown')
                        print(f"   💥 Frame processing exception for '{frame_name}': {e}")

        processing_time = time.time() - start_time
        print(f"   ⏱️ Frame processing completed in {processing_time:.2f} seconds")
        print(f"   📁 Generated {len(generated_files)} frame files")

        # =============================================================================
        # PHASE 4: Generate main app file with architecture context
        # =============================================================================
        main_app_code = generate_enhanced_main_app_with_ai(
            ai_engine, frames, framework, job_id, parser, 
            framework_structure, app_architecture
        )
        if main_app_code:
            generated_files.update(main_app_code)

        # Fourth phase: Generate config files based on discovered structure
        config_files = generate_config_files_from_structure(framework_structure, frames)
        generated_files.update(config_files)

        # Fifth phase: Dependency analysis and resolution
        print(f"🔍 Analyzing dependencies for {len(generated_files)} files...")
        dependency_analysis = analyze_file_dependencies(generated_files, framework)

        dependency_resolution = resolve_project_dependencies(ai_engine, dependency_analysis, framework_structure, parser)
        if dependency_resolution:
            generated_files = apply_dependency_resolution(generated_files, dependency_resolution)
            print("✅ Dependencies resolved and applied")
        else:
            print("⚠️ Dependency resolution skipped")

        print(f"✅ AI-generated {framework} code with {len(generated_files)} files")
        return {
            "framework": framework,
            "files": generated_files,
            "main_file": framework_structure.get('structure', {}).get('main_file', 'src/App.js'),
            "total_files": len(generated_files),
            "framework_structure": framework_structure,
            "dependency_analysis": dependency_analysis,
            "dependency_resolution": dependency_resolution
        }

    except Exception as e:
        print(f"❌ AI code generation failed: {e}")
        # Fallback to basic structure
        return {
            "framework": framework,
            "files": {},
            "main_file": "index.html",
            "error": str(e)
        }

def get_file_extension(framework: str) -> str:
    """Get the main file extension for the framework"""
    extensions = {
        "react": "js",
        "vue": "vue",
        "angular": "ts",
        "flutter": "dart"
    }
    return extensions.get(framework, "js")

def sanitize_component_name(name: str) -> str:
    """Sanitize component name for code generation"""
    import re
    # Remove special characters and spaces, capitalize first letter
    sanitized = re.sub(r'[^a-zA-Z0-9]', '', name)
    return sanitized.capitalize() or "Component"

# Configuration file generators
def generate_react_package_json(frames: List[Dict]) -> str:
    """Generate package.json for React project"""
    return '''{
  "name": "figma-converted-app",
  "version": "0.1.0",
  "private": true,
  "dependencies": {
    "@testing-library/jest-dom": "^5.16.4",
    "@testing-library/react": "^13.3.0",
    "@testing-library/user-event": "^13.5.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-scripts": "5.0.1",
    "web-vitals": "^2.1.4"
  },
  "scripts": {
    "start": "react-scripts start",
    "build": "react-scripts build",
    "test": "react-scripts test",
    "eject": "react-scripts eject"
  },
  "eslintConfig": {
    "extends": [
      "react-app",
      "react-app/jest"
    ]
  },
  "browserslist": {
    "production": [
      ">0.2%",
      "not dead",
      "not op_mini all"
    ],
    "development": [
      "last 1 chrome version",
      "last 1 firefox version",
      "last 1 safari version"
    ]
  }
}'''

def generate_react_index_js() -> str:
    """Generate src/index.js"""
    return '''import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
'''

def generate_basic_css() -> str:
    """Generate basic CSS"""
    return '''body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
    'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

code {
  font-family: source-code-pro, Menlo, Monaco, Consolas, 'Courier New',
    monospace;
}
'''

def generate_react_html() -> str:
    """Generate public/index.html"""
    return '''<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <link rel="icon" href="%PUBLIC_URL%/favicon.ico" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="theme-color" content="#000000" />
    <meta name="description" content="Figma Converted React App" />
    <title>Figma Converted App</title>
  </head>
  <body>
    <noscript>You need to enable JavaScript to run this app.</noscript>
    <div id="root"></div>
  </body>
</html>'''

def generate_vue_package_json(frames: List[Dict]) -> str:
    """Generate package.json for Vue project"""
    return '''{
  "name": "figma-converted-vue-app",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "serve": "vue-cli-service serve",
    "build": "vue-cli-service build",
    "lint": "vue-cli-service lint"
  },
  "dependencies": {
    "core-js": "^3.8.3",
    "vue": "^3.2.13"
  },
  "devDependencies": {
    "@vue/cli-plugin-babel": "~5.0.0",
    "@vue/cli-plugin-eslint": "~5.0.0",
    "@vue/cli-service": "~5.0.0",
    "@vue/compiler-sfc": "^3.0.0",
    "eslint": "^7.32.0",
    "eslint-plugin-vue": "^8.0.3"
  }
}'''

def generate_vue_main_js() -> str:
    """Generate src/main.js"""
    return '''import { createApp } from 'vue'
import App from './App.vue'

createApp(App).mount('#app')
'''

def generate_vue_html() -> str:
    """Generate public/index.html"""
    return '''<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="viewport" content="width=device-width,initial-scale=1.0">
    <link rel="icon" href="<%= BASE_URL %>favicon.ico">
    <title>Figma Converted Vue App</title>
  </head>
  <body>
    <noscript>
      <strong>We're sorry but figma-converted-vue-app doesn't work properly without JavaScript enabled. Please enable it to continue.</strong>
    </noscript>
    <div id="app"></div>
    <!-- built files will be auto injected -->
  </body>
</html>'''

def generate_angular_package_json(frames: List[Dict]) -> str:
    """Generate package.json for Angular project"""
    return '''{
  "name": "figma-converted-angular-app",
  "version": "0.0.0",
  "scripts": {
    "ng": "ng",
    "start": "ng serve",
    "build": "ng build",
    "watch": "ng build --watch --configuration development",
    "test": "ng test"
  },
  "private": true,
  "dependencies": {
    "@angular/animations": "^15.2.0",
    "@angular/common": "^15.2.0",
    "@angular/compiler": "^15.2.0",
    "@angular/core": "^15.2.0",
    "@angular/forms": "^15.2.0",
    "@angular/platform-browser": "^15.2.0",
    "@angular/platform-browser-dynamic": "^15.2.0",
    "@angular/router": "^15.2.0",
    "rxjs": "~7.8.0",
    "tslib": "^2.3.0",
    "zone.js": "~0.12.0"
  },
  "devDependencies": {
    "@angular-devkit/build-angular": "^15.2.0",
    "@angular/cli": "~15.2.0",
    "@angular/compiler-cli": "^15.2.0",
    "typescript": "~4.9.4"
  }
}'''

def generate_angular_main_ts() -> str:
    """Generate src/main.ts"""
    return '''import { platformBrowserDynamic } from '@angular/platform-browser-dynamic';
import { AppModule } from './app/app.module';

platformBrowserDynamic().bootstrapModule(AppModule)
  .catch(err => console.error(err));
'''

def generate_angular_index_html() -> str:
    """Generate src/index.html"""
    return '''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Figma Converted Angular App</title>
  <base href="/">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" type="image/x-icon" href="favicon.ico">
</head>
<body>
  <app-root></app-root>
</body>
</html>'''

def generate_flutter_pubspec(frames: List[Dict]) -> str:
    """Generate pubspec.yaml for Flutter project"""
    return '''name: figma_converted_app
description: A Flutter app converted from Figma design
version: 1.0.0+1

environment:
  sdk: '>=3.0.0 <4.0.0'

dependencies:
  flutter:
    sdk: flutter
  cupertino_icons: ^1.0.2

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^2.0.0

flutter:
  uses-material-design: true
'''

def generate_flutter_main_dart() -> str:
    """Generate lib/main.dart"""
    return '''import 'package:flutter/material.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Figma Converted Flutter App',
      theme: ThemeData(
        primarySwatch: Colors.blue,
      ),
      home: const HomeScreen(),
    );
  }
}

class HomeScreen extends StatelessWidget {
  const HomeScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Figma Converted App'),
      ),
      body: const Center(
        child: Text(
          'Welcome to your Figma converted app!',
          style: TextStyle(fontSize: 24),
        ),
      ),
    );
  }
}
'''

async def collect_components(design_result: Dict, job_id: str) -> Dict[str, Any]:
    """Collect and organize components"""
    try:
        # Extract nodes data from design result
        nodes_data = []
        if 'frames' in design_result:
            # Extract nodes from frames
            for frame in design_result['frames']:
                if 'component_references' in frame:
                    # Add component nodes to collection
                    for comp_id, comp_data in frame['component_references'].items():
                        nodes_data.append({
                            'id': comp_id,
                            'name': comp_data.get('name', 'Unknown Component'),
                            'type': comp_data.get('type', 'COMPONENT'),
                            'dimensions': comp_data.get('dimensions', {})
                        })

        # Initialize component collector
        collector = ComponentCollector(api_token=os.getenv("FIGMA_API_TOKEN"))

        # Extract file key for asset downloads
        file_key = design_result.get('file_key', '')

        # Collect components
        collection_result = collector.collect_components_from_design(file_key, nodes_data)

        print(f"📦 Collected {collection_result['total_components']} components")
        return collection_result

    except Exception as e:
        print(f"❌ Component collection failed: {e}")
        return {
            "total_components": 0,
            "components": [],
            "error": str(e)
        }

async def assemble_project(code_result: Dict, components_result: Dict, framework: str, job_id: str) -> Dict[str, Any]:
    """Assemble the final project structure"""
    try:
        # Initialize project assembler
        assembler = ProjectAssembler()

        # Generate project name
        project_name = f"figma_converted_{framework}_{job_id}"

        # Assemble complete project
        assembly_result = assembler.assemble_project(
            code_result,
            components_result,
            framework,
            job_id,
            project_name
        )

        print(f"📦 Project assembly complete: {assembly_result.get('files_created', 0)} files")

        return {
            "output_path": assembly_result["project_dir"],
            "zip_path": assembly_result.get("zip_path"),
            "project_name": project_name,
            "framework": framework,
            "files_generated": assembly_result.get("files_created", 0),
            "components_collected": assembly_result.get("components_added", 0),
            "assembly_result": assembly_result
        }

    except Exception as e:
        print(f"❌ Project assembly failed: {e}")
        return {
            "output_path": f"output/job_{job_id}",
            "error": str(e)
        }

@app.get("/")
async def root():
    """Serve the main web interface"""
    return templates.TemplateResponse("index.html", {"request": {}})

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/api/convert")
async def start_conversion(request: ConversionRequest, background_tasks: BackgroundTasks):
    """Start Figma design conversion"""
    job_id = str(uuid.uuid4())

    # Initialize job status
    jobs[job_id] = {
        "status": "queued",
        "progress": 0,
        "message": "Initializing conversion...",
        "result": None,
        "created_at": datetime.now()
    }

    # Add background task for conversion
    background_tasks.add_task(process_conversion, job_id, request.figma_url, request.pat_token, request.target_framework, request.include_components)

    return {"job_id": job_id, "status": "queued", "message": "Conversion started"}

async def process_conversion(job_id: str, figma_url: str, pat_token: Optional[str], framework: str, include_components: bool):
    """Process the Figma design conversion in background"""
    try:
        # Update status to processing
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["progress"] = 5
        jobs[job_id]["message"] = "Analyzing framework requirements..."

        # Initialize AI framework detector
        detector = AIFrameworkDetector()
        
        # Detect framework from user input
        framework_detection = detector.detect_framework(framework)
        if not framework_detection.get('success'):
            raise ValueError(f"Could not determine framework from: {framework}")
        
        detected_framework = framework_detection['framework']
        framework_name = framework_detection['framework_name']
        
        # Update status
        jobs[job_id]["progress"] = 10
        jobs[job_id]["message"] = f"Detected framework: {framework_name}. Processing Figma URL..."

        # Initialize Figma processor
        processor = EnhancedFigmaProcessor(api_token=pat_token or os.getenv("FIGMA_API_TOKEN"))

        # Update progress
        jobs[job_id]["progress"] = 20
        jobs[job_id]["message"] = "Fetching design data from Figma..."

        # Process the Figma design using the enhanced processor
        design_data = processor.process_frame_by_frame(figma_url, include_components)

        # Update progress
        jobs[job_id]["progress"] = 40
        jobs[job_id]["message"] = f"Analyzing {len(design_data.get('frames', []))} frames..."

        # Process frames and components (already done by process_frame_by_frame)
        processed_data = design_data  # The data is already processed

        # Update progress
        jobs[job_id]["progress"] = 60
        jobs[job_id]["message"] = f"Generating {framework} code..."

        # Generate code using detected framework
        code_result = generate_framework_code(processed_data, detected_framework, job_id, framework_detection)

        # Update progress
        jobs[job_id]["progress"] = 80
        jobs[job_id]["message"] = "Collecting components and assets..."

        # Components are already collected by process_frame_by_frame
        components_result = {
            "total_components": design_data.get("design_info", {}).get("total_components", 0),
            "components": design_data.get("component_references", {}),
            "component_manifest_path": design_data.get("component_manifest_path")
        }

        # Update progress
        jobs[job_id]["progress"] = 90
        jobs[job_id]["message"] = "Assembling final project..."

        # Assemble project
        assembly_result = await assemble_project(code_result, components_result, detected_framework, job_id)

        # Update final status
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["message"] = "Conversion completed successfully!"
        jobs[job_id]["result"] = {
            "framework": detected_framework,
            "framework_name": framework_name,
            "original_request": framework,
            "detection_confidence": framework_detection.get('confidence', 0.5),
            "files_generated": code_result.get("total_files", 0),
            "components_collected": components_result.get("total_components", 0),
            "output_path": assembly_result.get("output_path"),
            "zip_path": assembly_result.get("zip_path"),
            "project_name": assembly_result.get("project_name")
        }

    except Exception as e:
        # Update status on error
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["message"] = f"Conversion failed: {str(e)}"
        print(f"❌ Conversion failed for job {job_id}: {e}")

@app.get("/api/status/{job_id}")
async def get_conversion_status(job_id: str):
    """Get conversion job status"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    return {
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "message": job["message"],
        "result": job.get("result")
    }

@app.get("/api/download/{job_id}")
async def download_project(job_id: str):
    """Download the generated project as a zip file"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed yet")

    result = job["result"]
    zip_path = result.get("zip_path")

    if not zip_path or not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="Project zip file not found")

    # Return the zip file
    return FileResponse(
        path=zip_path,
        filename=f"{result.get('project_name', 'figma_project')}.zip",
        media_type='application/zip'
    )

def analyze_file_dependencies(files: Dict[str, str], framework: str) -> Dict[str, Any]:
    """Analyze generated files to extract imports and dependencies"""
    import re

    file_analysis = {}
    all_imports = set()
    all_components = set()

    for file_path, content in files.items():
        if not file_path.endswith(('.js', '.jsx', '.ts', '.tsx', '.vue', '.dart', '.py')):
            continue

        file_info = {
            'imports': [],
            'exports': [],
            'components': [],
            'framework_imports': []
        }

        lines = content.split('\n')

        # Extract first 20 lines for import analysis
        import_lines = lines[:20]

        for line in import_lines:
            line = line.strip()

            # Extract ES6 imports
            if line.startswith('import'):
                file_info['imports'].append(line)
                all_imports.add(line)

                # Check for framework-specific imports
                if framework == 'react' and ('react' in line.lower() or 'jsx' in line):
                    file_info['framework_imports'].append(line)
                elif framework == 'vue' and ('vue' in line.lower()):
                    file_info['framework_imports'].append(line)
                elif framework == 'angular' and ('@angular' in line):
                    file_info['framework_imports'].append(line)

            # Extract component definitions
            if framework == 'react':
                # Function components
                func_match = re.search(r'function\s+(\w+)', line)
                if func_match:
                    file_info['components'].append(func_match.group(1))
                    all_components.add(func_match.group(1))

                # Arrow function components
                arrow_match = re.search(r'const\s+(\w+)\s*=\s*\(', line)
                if arrow_match and '=>' in content:
                    file_info['components'].append(arrow_match.group(1))
                    all_components.add(arrow_match.group(1))

            elif framework == 'vue':
                if '<template>' in content and '<script>' in content:
                    file_info['components'].append(file_path.split('/')[-1].replace('.vue', ''))

            elif framework == 'angular':
                class_match = re.search(r'export\s+class\s+(\w+)', line)
                if class_match:
                    file_info['components'].append(class_match.group(1))
                    all_components.add(class_match.group(1))

        file_analysis[file_path] = file_info

    return {
        'file_analysis': file_analysis,
        'all_imports': list(all_imports),
        'all_components': list(all_components),
        'framework': framework,
        'total_files_analyzed': len(file_analysis)
    }

def resolve_project_dependencies(ai_engine: 'AI_engine', dependency_analysis: Dict, framework_structure: Dict, parser: AIResponseParser) -> Dict[str, Any]:
    """Send dependency analysis to AI for resolution"""
    try:
        framework = framework_structure.get('framework', 'react')
        structure = framework_structure.get('structure', {})

        prompt = f"""Analyze the following dependency analysis for a {framework} project and provide dependency resolution.

File Structure: {json.dumps(structure, indent=2)}

Dependency Analysis: {json.dumps(dependency_analysis, indent=2)}

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
        "@types/react-dom": "^18.2.0"
      }}
    }}
  }},
  "file_updates": {{
    "src/App.jsx": {{
      "add_imports": [
        "import React from 'react';",
        "import {{ BrowserRouter, Routes, Route }} from 'react-router-dom';"
      ],
      "add_to_top": "// Generated by MiHiR's Figma Converter\\n// Author: MiHiR\\n"
    }},
    "src/index.js": {{
      "add_imports": [
        "import React from 'react';",
        "import ReactDOM from 'react-dom/client';"
      ],
      "add_to_top": "// Generated by MiHiR's Figma Converter\\n// Author: MiHiR\\n"
    }}
  }},
  "missing_dependencies": ["lodash", "axios"],
  "framework_specific": {{
    "react": {{
      "additional_deps": ["@testing-library/react", "@testing-library/jest-dom"]
    }}
  }}
}}

Do NOT include any explanations, markdown formatting, or additional text. Return ONLY the JSON object."""

        messages = [
            {"role": "system", "content": f"You are an expert {framework} developer. Analyze dependencies and provide complete dependency resolution with author credits. Always respond with valid JSON only."},
            {"role": "user", "content": prompt}
        ]

        print(f"🤖 AI Request - Dependency Resolution:")
        print(f"   Framework: {framework}")
        print(f"   Dependency Analysis Keys: {list(dependency_analysis.keys())}")
        print(f"   Framework Structure Keys: {list(framework_structure.keys())}")
        print(f"   Messages: {json.dumps(messages, indent=2)}")
        print(f"   Temperature: 0.2, Auto-decide: False")
        print()

        result = ai_engine.chat_completion(messages, temperature=0.2, autodecide=False)

        print(f"🤖 AI Response - Dependency Resolution:")
        print(f"   Success: {result.success}")
        if result.success:
            print(f"   Response Content: {result.content[:500]}...")
        else:
            print(f"   Error: {result.error_message}")
        print()

        if result.success:
            try:
                # Parse JSON response using the parser
                dep_resolution = parser.parse_dependency_resolution_response(result.content.strip())
                return dep_resolution
            except ValueError as e:
                print(f"❌ Failed to parse dependency resolution response: {e}")
                return {}
        else:
            print(f"❌ Dependency resolution failed: {result.error_message}")
            return {}

    except Exception as e:
        print(f"❌ Error resolving dependencies: {e}")
        return {}

def apply_dependency_resolution(files: Dict[str, str], dependency_resolution: Dict) -> Dict[str, str]:
    """Apply dependency resolution to generated files"""
    updated_files = files.copy()

    # Apply file updates
    file_updates = dependency_resolution.get('file_updates', {})
    for file_path, updates in file_updates.items():
        if file_path in updated_files:
            content = updated_files[file_path]

            # Add imports
            add_imports = updates.get('add_imports', [])
            if add_imports:
                # Find the first non-comment, non-empty line
                lines = content.split('\n')
                insert_index = 0

                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if stripped and not stripped.startswith('//') and not stripped.startswith('/*'):
                        insert_index = i
                        break

                # Insert imports at the found position
                imports_text = '\n'.join(add_imports) + '\n'
                lines.insert(insert_index, imports_text)
                content = '\n'.join(lines)

            # Add to top (author credits, etc.)
            add_to_top = updates.get('add_to_top', '')
            if add_to_top:
                content = add_to_top + content

            updated_files[file_path] = content

    # Update package.json with dependencies
    package_deps = dependency_resolution.get('dependencies', {}).get('package.json', {})
    if 'package.json' in updated_files and package_deps:
        try:
            package_data = json.loads(updated_files['package.json'])

            # Add dependencies
            if 'dependencies' in package_deps:
                package_data.setdefault('dependencies', {}).update(package_deps['dependencies'])

            # Add devDependencies
            if 'devDependencies' in package_deps:
                package_data.setdefault('devDependencies', {}).update(package_deps['devDependencies'])

            updated_files['package.json'] = json.dumps(package_data, indent=2)

        except json.JSONDecodeError:
            print("❌ Failed to update package.json with dependencies")

    return updated_files

if __name__ == "__main__":
    import uvicorn
    print("Server is available at: http://localhost:8000")
    print()

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )