"""
AI-Powered Framework Detection System
Analyzes user requirements and determines the best framework/technology stack
"""

import json
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from ai_engine import AI_engine
from ai_response_parser import AIResponseParser

class AIFrameworkDetector:
    """
    Detects and recommends framework/technology stack based on user requirements
    """

    def __init__(self):
        self.ai_engine = AI_engine(verbose=True)
        self.parser = AIResponseParser()
        
        # Common framework patterns for fallback detection
        self.framework_patterns = {
            'react': ['react', 'jsx', 'create-react-app', 'vite react', 'next.js', 'nextjs'],
            'vue': ['vue', 'nuxt', 'vue.js', 'vuejs', 'vue 3'],
            'angular': ['angular', 'ng', 'typescript angular', 'angular cli'],
            'flutter': ['flutter', 'dart', 'mobile app', 'cross-platform mobile'],
            'svelte': ['svelte', 'sveltekit', 'svelte.js'],
            'html_css_js': ['html', 'css', 'javascript', 'vanilla js', 'static site', 'landing page'],
            'flask': ['flask', 'python flask', 'flask templates', 'jinja2'],
            'django': ['django', 'python django', 'django templates'],
            'express': ['express', 'node.js', 'nodejs', 'express.js'],
            'fastapi': ['fastapi', 'python fastapi', 'fastapi templates'],
            'spring': ['spring boot', 'java spring', 'thymeleaf'],
            'rails': ['ruby on rails', 'rails', 'erb templates'],
            'php': ['php', 'laravel', 'symfony', 'blade templates'],
            'asp_net': ['asp.net', 'c# mvc', 'razor pages', '.net core']
        }

    def detect_framework(self, user_requirement: str) -> Dict[str, Any]:
        """
        Detect framework from user requirement using AI with fallback pattern matching
        
        Args:
            user_requirement (str): User's framework requirement or description
            
        Returns:
            Dict containing framework info, structure, and confidence
        """
        print(f"🔍 Analyzing user requirement: '{user_requirement}'")
        
        # First try AI-powered detection
        ai_result = self._ai_detect_framework(user_requirement)
        if ai_result and ai_result.get('success'):
            return ai_result
        
        # Fallback to pattern matching
        print("⚠️ AI detection failed, using pattern matching fallback")
        return self._pattern_detect_framework(user_requirement)
    
    def _ai_detect_framework(self, user_requirement: str) -> Optional[Dict[str, Any]]:
        """Use AI to detect and recommend framework"""
        try:
            prompt = f"""Analyze the following user requirement and recommend the best framework/technology stack for frontend development.

User Requirement: "{user_requirement}"

Based on this requirement, determine:
1. The most suitable framework/technology
2. Project structure and organization
3. File extensions and naming conventions
4. Dependencies and build tools
5. Component storage locations

IMPORTANT: Respond with ONLY a valid JSON object in this exact format:
{{
  "framework": "react|vue|angular|flutter|svelte|html_css_js|flask|django|express|fastapi|php|other",
  "framework_name": "Human-readable framework name",
  "confidence": 0.95,
  "reasoning": "Why this framework was chosen",
  "technology_stack": {{
    "primary": "main framework/language",
    "styling": "css|scss|tailwind|styled-components|bootstrap",
    "build_tool": "vite|webpack|rollup|gulp|none",
    "package_manager": "npm|yarn|pip|composer|flutter|none"
  }},
  "project_structure": {{
    "root_folders": ["src", "public", "dist"],
    "component_location": "src/components",
    "assets_location": "src/assets",
    "main_file": "src/main.js|src/App.js|index.html",
    "config_files": ["package.json", "vite.config.js"]
  }},
  "file_conventions": {{
    "component_extension": ".jsx|.vue|.ts|.html|.dart",
    "style_extension": ".css|.scss|.module.css",
    "naming_convention": "PascalCase|kebab-case|camelCase"
  }},
  "dependencies": {{
    "core": ["react", "react-dom"],
    "build": ["vite", "@vitejs/plugin-react"],
    "styling": ["tailwindcss", "autoprefixer"]
  }},
  "special_instructions": "Any framework-specific setup instructions"
}}

Examples:
- "react" → React with modern setup
- "python" → Flask with Jinja2 templates (since Python isn't frontend)
- "mobile app" → Flutter for cross-platform
- "landing page" → HTML/CSS/JS for simple sites
- "vue 3" → Vue.js 3 with Composition API
- "django templates" → Django with template system

Do NOT include any explanations, markdown formatting, or additional text. Return ONLY the JSON object."""

            messages = [
                {"role": "system", "content": "You are an expert technology consultant specializing in framework selection and project architecture. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ]

            print(f"🤖 AI Request - Framework Detection:")
            print(f"   User Requirement: {user_requirement}")
            print(f"   Temperature: 0.1, Auto-decide: False")
            print()

            result = self.ai_engine.chat_completion(messages, temperature=0.1, autodecide=False)

            print(f"🤖 AI Response - Framework Detection:")
            print(f"   Success: {result.success}")
            if result.success:
                print(f"   Response Content: {result.content[:500]}...")
            else:
                print(f"   Error: {result.error_message}")
            print()

            if result.success:
                try:
                    # Parse JSON response
                    framework_data = json.loads(result.content.strip())
                    
                    # Validate required fields
                    if not all(key in framework_data for key in ['framework', 'confidence', 'project_structure']):
                        raise ValueError("Missing required fields in AI response")
                    
                    framework_data['success'] = True
                    framework_data['detection_method'] = 'ai'
                    framework_data['timestamp'] = datetime.now().isoformat()
                    
                    return framework_data
                    
                except (json.JSONDecodeError, ValueError) as e:
                    print(f"❌ Failed to parse AI framework detection response: {e}")
                    print(f"Raw response: {result.content[:500]}...")
                    return None
            else:
                print(f"❌ AI framework detection failed: {result.error_message}")
                return None

        except Exception as e:
            print(f"❌ Error during AI framework detection: {e}")
            return None
    
    def _pattern_detect_framework(self, user_requirement: str) -> Dict[str, Any]:
        """Fallback pattern matching for framework detection"""
        req_lower = user_requirement.lower().strip()
        
        # Find matching framework
        best_match = None
        best_confidence = 0.0
        
        for framework, patterns in self.framework_patterns.items():
            for pattern in patterns:
                if pattern in req_lower:
                    confidence = len(pattern) / len(req_lower)  # Simple confidence score
                    if confidence > best_confidence:
                        best_match = framework
                        best_confidence = confidence
        
        # Default fallback
        if not best_match:
            best_match = 'html_css_js'
            best_confidence = 0.3
        
        # Create framework structure based on detected framework
        framework_structures = {
            'react': {
                'framework_name': 'React',
                'technology_stack': {
                    'primary': 'React',
                    'styling': 'css',
                    'build_tool': 'vite',
                    'package_manager': 'npm'
                },
                'project_structure': {
                    'root_folders': ['src', 'public', 'node_modules'],
                    'component_location': 'src/components',
                    'assets_location': 'src/assets',
                    'main_file': 'src/App.jsx',
                    'config_files': ['package.json', 'vite.config.js']
                },
                'file_conventions': {
                    'component_extension': '.jsx',
                    'style_extension': '.css',
                    'naming_convention': 'PascalCase'
                }
            },
            'vue': {
                'framework_name': 'Vue.js',
                'technology_stack': {
                    'primary': 'Vue',
                    'styling': 'css',
                    'build_tool': 'vite',
                    'package_manager': 'npm'
                },
                'project_structure': {
                    'root_folders': ['src', 'public', 'node_modules'],
                    'component_location': 'src/components',
                    'assets_location': 'src/assets',
                    'main_file': 'src/App.vue',
                    'config_files': ['package.json', 'vite.config.js']
                },
                'file_conventions': {
                    'component_extension': '.vue',
                    'style_extension': '.css',
                    'naming_convention': 'PascalCase'
                }
            },
            'angular': {
                'framework_name': 'Angular',
                'technology_stack': {
                    'primary': 'Angular',
                    'styling': 'css',
                    'build_tool': 'angular-cli',
                    'package_manager': 'npm'
                },
                'project_structure': {
                    'root_folders': ['src', 'node_modules'],
                    'component_location': 'src/app',
                    'assets_location': 'src/assets',
                    'main_file': 'src/main.ts',
                    'config_files': ['package.json', 'angular.json', 'tsconfig.json']
                },
                'file_conventions': {
                    'component_extension': '.ts',
                    'style_extension': '.css',
                    'naming_convention': 'kebab-case'
                }
            },
            'flutter': {
                'framework_name': 'Flutter',
                'technology_stack': {
                    'primary': 'Flutter',
                    'styling': 'dart',
                    'build_tool': 'flutter',
                    'package_manager': 'flutter'
                },
                'project_structure': {
                    'root_folders': ['lib', 'assets'],
                    'component_location': 'lib/widgets',
                    'assets_location': 'assets',
                    'main_file': 'lib/main.dart',
                    'config_files': ['pubspec.yaml']
                },
                'file_conventions': {
                    'component_extension': '.dart',
                    'style_extension': '.dart',
                    'naming_convention': 'snake_case'
                }
            },
            'flask': {
                'framework_name': 'Flask',
                'technology_stack': {
                    'primary': 'Python Flask',
                    'styling': 'css',
                    'build_tool': 'none',
                    'package_manager': 'pip'
                },
                'project_structure': {
                    'root_folders': ['templates', 'static'],
                    'component_location': 'templates',
                    'assets_location': 'static',
                    'main_file': 'app.py',
                    'config_files': ['requirements.txt']
                },
                'file_conventions': {
                    'component_extension': '.html',
                    'style_extension': '.css',
                    'naming_convention': 'snake_case'
                }
            },
            'django': {
                'framework_name': 'Django',
                'technology_stack': {
                    'primary': 'Python Django',
                    'styling': 'css',
                    'build_tool': 'none',
                    'package_manager': 'pip'
                },
                'project_structure': {
                    'root_folders': ['templates', 'static', 'apps'],
                    'component_location': 'templates',
                    'assets_location': 'static',
                    'main_file': 'manage.py',
                    'config_files': ['requirements.txt', 'settings.py']
                },
                'file_conventions': {
                    'component_extension': '.html',
                    'style_extension': '.css',
                    'naming_convention': 'snake_case'
                }
            },
            'html_css_js': {
                'framework_name': 'HTML/CSS/JavaScript',
                'technology_stack': {
                    'primary': 'Vanilla Web',
                    'styling': 'css',
                    'build_tool': 'none',
                    'package_manager': 'none'
                },
                'project_structure': {
                    'root_folders': ['assets', 'css', 'js'],
                    'component_location': '.',
                    'assets_location': 'assets',
                    'main_file': 'index.html',
                    'config_files': []
                },
                'file_conventions': {
                    'component_extension': '.html',
                    'style_extension': '.css',
                    'naming_convention': 'kebab-case'
                }
            }
        }
        
        base_structure = framework_structures.get(best_match, framework_structures['html_css_js'])
        
        return {
            'success': True,
            'framework': best_match,
            'confidence': min(best_confidence * 2, 0.9),  # Scale confidence
            'reasoning': f"Pattern matched '{best_match}' from user requirement",
            'detection_method': 'pattern_matching',
            'timestamp': datetime.now().isoformat(),
            **base_structure
        }
    
    def validate_framework_detection(self, detection_result: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate framework detection result"""
        errors = []
        
        # Check required fields
        required_fields = ['framework', 'confidence', 'project_structure', 'file_conventions']
        for field in required_fields:
            if field not in detection_result:
                errors.append(f"Missing required field: {field}")
        
        # Validate confidence score
        confidence = detection_result.get('confidence', 0)
        if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
            errors.append("Confidence must be a number between 0 and 1")
        
        # Validate project structure
        project_structure = detection_result.get('project_structure', {})
        required_structure_fields = ['main_file', 'component_location']
        for field in required_structure_fields:
            if field not in project_structure:
                errors.append(f"Missing project_structure field: {field}")
        
        return len(errors) == 0, errors

# Example usage and testing
if __name__ == "__main__":
    detector = AIFrameworkDetector()
    
    # Test cases
    test_cases = [
        "react",
        "vue 3 with typescript", 
        "python flask templates",
        "mobile app development",
        "simple landing page",
        "django web application",
        "angular with material design",
        "flutter cross platform",
        "static website with bootstrap"
    ]
    
    print("🧪 Testing AI Framework Detection")
    print("=" * 50)
    
    for test_case in test_cases:
        print(f"\n🔍 Testing: '{test_case}'")
        result = detector.detect_framework(test_case)
        
        if result.get('success'):
            print(f"✅ Detected: {result['framework_name']} ({result['framework']})")
            print(f"   Confidence: {result['confidence']:.2f}")
            print(f"   Method: {result['detection_method']}")
            print(f"   Main file: {result['project_structure']['main_file']}")
        else:
            print(f"❌ Detection failed")
    
    print(f"\n🎉 Framework Detection System Ready!")