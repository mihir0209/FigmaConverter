"""
JSON Response Parsers for Framework-Agnostic Code Generation
Handles parsing of AI responses in JSON format for robust code generation
"""

import json
import re
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

class AIResponseParser:
    """Parser for AI-generated JSON responses"""

    def __init__(self):
        self.supported_frameworks = [
            'react', 'vue', 'angular', 'flutter', 'svelte',
            'solidjs', 'qwik', 'astro', 'html', 'vanilla-js'
        ]

    def parse_framework_discovery_response(self, response: str) -> Dict[str, Any]:
        """
        Parse AI response for framework discovery phase

        Expected JSON format:
        {
          "framework": "react",
          "version": "18.2.0",
          "structure": {
            "component_extension": ".jsx",
            "main_file": "src/App.jsx",
            "config_files": ["package.json", "vite.config.js"],
            "folder_structure": {
              "src": ["components", "pages", "utils"],
              "public": ["assets"]
            }
          },
          "styling": {
            "primary": "css-modules",
            "secondary": ["styled-components", "tailwind"]
          },
          "routing": {
            "library": "react-router-dom",
            "version": "6.8.0"
          },
          "build_tool": "vite",
          "package_manager": "npm"
        }
        """
        try:
            data = json.loads(response.strip())

            # Validate required fields
            required_fields = ['framework', 'structure']
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")

            # Validate framework
            if data['framework'] not in self.supported_frameworks:
                raise ValueError(f"Unsupported framework: {data['framework']}")

            return data

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in framework discovery response: {e}")

    def parse_component_generation_response(self, response: str) -> Dict[str, Any]:
        """
        Parse AI response for component generation phase

        Expected JSON format:
        {
          "component_name": "Button",
          "content": "complete component code as string",
          "dependencies": ["react", "styled-components"],
          "file_path": "src/components/Button.jsx",
          "styling": {
            "type": "css-modules",
            "files": ["Button.module.css"]
          },
          "props": [
            {"name": "onClick", "type": "function", "required": true},
            {"name": "children", "type": "node", "required": false}
          ]
        }
        """
        try:
            data = json.loads(response.strip())

            # Validate required fields
            required_fields = ['component_name', 'content', 'file_path']
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")

            # Validate file path
            if not self._is_valid_file_path(data['file_path']):
                raise ValueError(f"Invalid file path: {data['file_path']}")

            return data

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in component generation response: {e}")

    def parse_main_app_generation_response(self, response: str) -> Dict[str, Any]:
        """
        Parse AI response for main app generation phase

        Expected JSON format:
        {
          "main_app": {
            "content": "complete main app code",
            "file_path": "src/App.jsx"
          },
          "routing": {
            "content": "routing configuration code",
            "file_path": "src/router.jsx"
          },
          "entry_point": {
            "content": "entry point code (index.js/main.js)",
            "file_path": "src/main.jsx"
          },
          "global_styles": {
            "content": "global CSS/styles",
            "file_path": "src/index.css"
          }
        }
        """
        try:
            data = json.loads(response.strip())

            # Validate main_app is present
            if 'main_app' not in data:
                raise ValueError("Missing required field: main_app")

            # Validate main_app has required fields
            main_app = data['main_app']
            if not isinstance(main_app, dict) or 'content' not in main_app or 'file_path' not in main_app:
                raise ValueError("main_app must be an object with 'content' and 'file_path' fields")

            return data

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in main app generation response: {e}")

    def parse_css_framework_response(self, response: str) -> Dict[str, Any]:
        """
        Parse AI response for CSS framework integration

        Expected JSON format:
        {
          "css_framework": "tailwind",
          "version": "3.2.0",
          "config": {
            "content": "tailwind.config.js content",
            "file_path": "tailwind.config.js"
          },
          "global_styles": {
            "content": "@tailwind base; @tailwind components; @tailwind utilities;",
            "file_path": "src/index.css"
          },
          "dependencies": ["tailwindcss", "autoprefixer", "postcss"]
        }
        """
        try:
            data = json.loads(response.strip())

            # Validate required fields
            if 'css_framework' not in data:
                raise ValueError("Missing required field: css_framework")

            return data

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in CSS framework response: {e}")

    def parse_dependency_resolution_response(self, response: str) -> Dict[str, Any]:
        """
        Parse AI response for dependency resolution phase

        Expected JSON format:
        {
          "dependencies": {
            "package.json": {
              "dependencies": {
                "react": "^18.2.0",
                "react-dom": "^18.2.0"
              },
              "devDependencies": {
                "@types/react": "^18.2.0"
              }
            }
          },
          "file_updates": {
            "src/App.jsx": {
              "add_imports": [
                "import React from 'react';",
                "import './App.css';"
              ],
              "add_to_top": "// Generated by MiHiR's Figma Converter\\n"
            }
          },
          "missing_dependencies": ["lodash", "axios"],
          "framework_specific": {
            "react": {
              "additional_deps": ["@testing-library/react"]
            }
          }
        }
        """
        try:
            data = json.loads(response.strip())

            # Validate required fields
            if 'dependencies' not in data and 'file_updates' not in data:
                raise ValueError("Response must contain either 'dependencies' or 'file_updates'")

            return data

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in dependency resolution response: {e}")

    def parse_error_response(self, response: str) -> Optional[str]:
        """
        Attempt to extract error message from failed AI response
        Returns None if no error can be extracted
        """
        try:
            # Try to parse as JSON first
            data = json.loads(response.strip())
            if isinstance(data, dict) and 'error' in data:
                return data['error']
        except json.JSONDecodeError:
            pass

        # Try to extract error from text
        error_patterns = [
            r'error[:\s]*(.+?)(?:\n|$)',
            r'Error[:\s]*(.+?)(?:\n|$)',
            r'failed[:\s]*(.+?)(?:\n|$)',
            r'Failed[:\s]*(.+?)(?:\n|$)'
        ]

        for pattern in error_patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def _is_valid_file_path(self, file_path: str) -> bool:
        """Validate file path for security"""
        try:
            path = Path(file_path)

            # Check for dangerous patterns
            dangerous_patterns = ['..', '~', '$', '`']
            if any(pattern in str(path) for pattern in dangerous_patterns):
                return False

            # Check file extension
            allowed_extensions = [
                '.js', '.jsx', '.ts', '.tsx', '.vue', '.dart', '.svelte',
                '.astro', '.html', '.css', '.scss', '.less', '.json', '.yaml', '.yml'
            ]

            if path.suffix.lower() not in allowed_extensions:
                return False

            return True

        except Exception:
            return False

    def sanitize_code_content(self, content: str) -> str:
        """Sanitize code content to prevent injection attacks"""
        if not isinstance(content, str):
            return ""

        # Remove potentially dangerous patterns
        dangerous_patterns = [
            r'<script[^>]*>.*?</script>',  # Script tags
            r'javascript:',                # JavaScript URLs
            r'data:',                      # Data URLs that might execute code
            r'vbscript:',                  # VBScript
        ]

        for pattern in dangerous_patterns:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.DOTALL)

        return content

class FrameworkStructureValidator:
    """Validates framework structures discovered by AI"""

    def __init__(self):
        self.required_structure_fields = [
            'component_extension',
            'main_file',
            'config_files',
            'folder_structure'
        ]

    def validate_framework_structure(self, structure: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate framework structure data
        Returns (is_valid, error_messages)
        """
        errors = []

        # Check required fields
        for field in self.required_structure_fields:
            if field not in structure:
                errors.append(f"Missing required field: {field}")

        # Validate component_extension
        if 'component_extension' in structure:
            ext = structure['component_extension']
            if not isinstance(ext, str) or not ext.startswith('.'):
                errors.append("component_extension must be a string starting with '.'")

        # Validate main_file
        if 'main_file' in structure:
            if not isinstance(structure['main_file'], str):
                errors.append("main_file must be a string")

        # Validate config_files
        if 'config_files' in structure:
            if not isinstance(structure['config_files'], list):
                errors.append("config_files must be a list")
            else:
                for config_file in structure['config_files']:
                    if not isinstance(config_file, str):
                        errors.append(f"config_files entries must be strings, got {type(config_file)}")

        # Validate folder_structure
        if 'folder_structure' in structure:
            if not isinstance(structure['folder_structure'], dict):
                errors.append("folder_structure must be a dictionary")
            else:
                for folder, contents in structure['folder_structure'].items():
                    if not isinstance(contents, list):
                        errors.append(f"folder_structure['{folder}'] must be a list")

        return len(errors) == 0, errors

class CodeGenerationValidator:
    """Validates generated code for security and correctness"""

    def __init__(self):
        self.max_file_size = 1024 * 1024  # 1MB limit
        self.forbidden_patterns = [
            r'eval\s*\(',           # eval() calls
            r'Function\s*\(',       # Function constructor
            r'document\.write',     # document.write
            r'innerHTML\s*=',       # innerHTML assignment
            r'outerHTML\s*=',       # outerHTML assignment
            r'process\.env',        # Environment variable access
            r'__dirname',           # Node.js __dirname
            r'__filename',          # Node.js __filename
            r'require\s*\(',        # Node.js require
            r'import\s*\(\s*.*\s*\)', # Dynamic imports
        ]

    def validate_code(self, code: str, framework: str) -> Tuple[bool, List[str]]:
        """
        Validate generated code
        Returns (is_valid, error_messages)
        """
        errors = []

        # Check file size
        if len(code.encode('utf-8')) > self.max_file_size:
            errors.append("Generated code exceeds maximum file size limit")

        # Check for forbidden patterns
        for pattern in self.forbidden_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                errors.append(f"Code contains forbidden pattern: {pattern}")

        # Framework-specific validations
        if framework == 'react':
            errors.extend(self._validate_react_code(code))
        elif framework == 'vue':
            errors.extend(self._validate_vue_code(code))
        elif framework == 'angular':
            errors.extend(self._validate_angular_code(code))
        elif framework == 'flutter':
            errors.extend(self._validate_flutter_code(code))

        return len(errors) == 0, errors

    def _validate_react_code(self, code: str) -> List[str]:
        """Validate React-specific code patterns"""
        errors = []

        # Check for proper React imports
        if 'React' in code and 'import React' not in code and 'from "react"' not in code:
            errors.append("React code should import React properly")

        # Check for JSX without proper setup
        if '<' in code and '>' in code and 'React' not in code:
            errors.append("JSX code should import React")

        return errors

    def _validate_vue_code(self, code: str) -> List[str]:
        """Validate Vue-specific code patterns"""
        errors = []

        # Check for template/script/style structure
        if '<template>' in code and '</template>' not in code:
            errors.append("Vue template tag not properly closed")

        if '<script>' in code and '</script>' not in code:
            errors.append("Vue script tag not properly closed")

        return errors

    def _validate_angular_code(self, code: str) -> List[str]:
        """Validate Angular-specific code patterns"""
        errors = []

        # Check for @Component decorator
        if '@Component' in code and 'selector:' not in code:
            errors.append("Angular component should have selector")

        return errors

    def _validate_flutter_code(self, code: str) -> List[str]:
        """Validate Flutter-specific code patterns"""
        errors = []

        # Check for proper widget structure
        if 'StatelessWidget' in code and 'build' not in code:
            errors.append("Flutter StatelessWidget should have build method")

        if 'StatefulWidget' in code and 'createState' not in code:
            errors.append("Flutter StatefulWidget should have createState method")

        return errors