"""
AI Prompt Engineering System for Figma-to-Code Converter
Generates optimized prompts for HTML/CSS/JS code generation with component references
"""

import json
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime
import re

class AIPromptEngineer:
    """
    Generates AI prompts for converting Figma designs to HTML/CSS/JS code
    with proper component referencing and Bootstrap integration
    """

    def __init__(self, component_manifest_path: str = "components/metadata/manifest.json"):
        self.component_manifest_path = Path(component_manifest_path)
        self.component_references = self._load_component_manifest()

        # System prompt templates
        self.system_prompts = {
            'html_css_js': self._get_html_css_js_system_prompt(),
            'bootstrap_integration': self._get_bootstrap_system_prompt(),
            'responsive_design': self._get_responsive_system_prompt(),
            'component_assembly': self._get_component_assembly_prompt()
        }

    def _load_component_manifest(self) -> Dict[str, Dict]:
        """Load component references from manifest"""
        if not self.component_manifest_path.exists():
            print(f"⚠️ Component manifest not found: {self.component_manifest_path}")
            return {}

        try:
            with open(self.component_manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            return manifest.get('components', {})
        except Exception as e:
            print(f"❌ Error loading component manifest: {e}")
            return {}

    def _get_html_css_js_system_prompt(self) -> str:
        """Get the base system prompt for HTML/CSS/JS generation"""
        return """You are an expert frontend developer specializing in converting Figma designs to clean, semantic HTML, CSS, and JavaScript code.

Your task is to generate production-ready code that:
1. Uses semantic HTML5 elements
2. Implements modern CSS with Flexbox/Grid
3. Includes vanilla JavaScript for interactivity
4. Ensures pixel-perfect accuracy to the design
5. Maintains responsive design principles
6. Follows web accessibility standards (WCAG 2.1)
7. Uses clean, maintainable code structure

IMPORTANT: Always reference component assets using the provided paths and maintain exact dimensions and positioning from the design."""

    def _get_bootstrap_system_prompt(self) -> str:
        """Get system prompt for Bootstrap integration"""
        return """You are an expert in Bootstrap 5 integration for Figma-to-Code conversion.

Your task is to:
1. Use Bootstrap 5 utility classes for layout and styling
2. Implement responsive grid system (container, row, col-*)
3. Apply Bootstrap components (cards, buttons, forms, etc.)
4. Use Bootstrap spacing utilities (m-, p-, etc.)
5. Implement Bootstrap's color and typography system
6. Ensure mobile-first responsive design
7. Override Bootstrap with custom CSS only when necessary

Always prefer Bootstrap utilities over custom CSS when possible."""

    def _get_responsive_system_prompt(self) -> str:
        """Get system prompt for responsive design"""
        return """You are a responsive design expert specializing in mobile-first development.

Your task is to:
1. Implement mobile-first CSS approach
2. Use CSS Grid and Flexbox for layouts
3. Apply responsive breakpoints (sm, md, lg, xl)
4. Ensure touch-friendly interactive elements
5. Optimize for various screen sizes and orientations
6. Test layouts across different devices
7. Use relative units (rem, em, %) for scalability

Always ensure the design works perfectly on mobile, tablet, and desktop devices."""

    def _get_component_assembly_prompt(self) -> str:
        """Get system prompt for component assembly"""
        return """You are an expert in component-based frontend development.

Your task is to:
1. Assemble components into cohesive layouts
2. Maintain component relationships and hierarchies
3. Ensure proper spacing and alignment between components
4. Implement consistent design patterns
5. Handle component states and interactions
6. Optimize component loading and performance
7. Create reusable component structures

Always reference the component manifest for accurate asset paths and properties."""

    def generate_frame_prompt(self, frame_data: Dict, frame_components: List[Dict],
                            target_framework: str = "html_css_js") -> str:
        """Generate a complete prompt for a specific frame"""
        system_prompt = self.system_prompts.get(target_framework, self.system_prompts['html_css_js'])

        # Build component reference section
        component_refs = self._build_component_references(frame_components)

        # Build frame description
        frame_description = self._build_frame_description(frame_data)

        # Build technical requirements
        technical_reqs = self._build_technical_requirements(frame_data, target_framework)

        # Combine into final prompt
        prompt = f"""{system_prompt}

FRAME TO CONVERT: {frame_description}

AVAILABLE COMPONENTS:
{component_refs}

TECHNICAL REQUIREMENTS:
{technical_reqs}

OUTPUT FORMAT:
Please provide the complete HTML, CSS, and JavaScript code in the following format:

```html
<!-- HTML Code -->
```

```css
/* CSS Code */
```

```javascript
// JavaScript Code
```

Ensure all component references use the exact paths provided and maintain pixel-perfect accuracy to the original design."""

        return prompt

    def _build_component_references(self, frame_components: List[Dict]) -> str:
        """Build component reference section for the prompt"""
        if not frame_components:
            return "No components available for this frame."

        refs = []
        for component in frame_components:
            comp_ref = self.component_references.get(component['id'])
            if comp_ref:
                ref_str = f"""• {comp_ref['original_name']} ({comp_ref['type']})
  - Path: {comp_ref['path']}
  - Dimensions: {comp_ref['dimensions']['width']}x{comp_ref['dimensions']['height']}
  - ID: {component['id']}"""

                # Add image ref for debugging
                if 'image_ref' in component:
                    ref_str += f"\n  - Image Ref: {component['image_ref']}"

                refs.append(ref_str)

        return "\n".join(refs) if refs else "No component references found."

    def _build_frame_description(self, frame_data: Dict) -> str:
        """Build frame description for the prompt"""
        name = frame_data.get('name', 'Unknown Frame')
        dimensions = frame_data.get('dimensions', {})
        width = dimensions.get('width', 0)
        height = dimensions.get('height', 0)
        page_name = frame_data.get('page_name', 'Unknown Page')

        return f"""
• Frame Name: {name}
• Page: {page_name}
• Dimensions: {width}x{height} pixels
• Background: {frame_data.get('background_color', 'transparent')}
• Total Elements: {frame_data.get('element_summary', {}).get('total_elements', 0)}
• Component Count: {frame_data.get('component_count', 0)}"""

    def _build_technical_requirements(self, frame_data: Dict, target_framework: str) -> str:
        """Build technical requirements section"""
        requirements = [
            "• Use semantic HTML5 elements",
            "• Implement modern CSS (Flexbox/Grid)",
            "• Ensure pixel-perfect accuracy",
            "• Make design fully responsive",
            "• Include proper accessibility attributes",
            "• Optimize for performance",
            "• Use clean, maintainable code structure"
        ]

        if target_framework == "bootstrap_integration":
            requirements.extend([
                "• Use Bootstrap 5 utility classes",
                "• Implement responsive grid system",
                "• Apply Bootstrap components where appropriate",
                "• Use Bootstrap spacing and color utilities"
            ])

        return "\n".join(requirements)

    def generate_batch_prompt(self, frames_data: List[Dict], target_framework: str = "html_css_js") -> str:
        """Generate a prompt for processing multiple frames"""
        system_prompt = self.system_prompts.get(target_framework, self.system_prompts['html_css_js'])

        # Build overview of all frames
        frames_overview = []
        total_components = 0

        for i, frame in enumerate(frames_data, 1):
            frame_info = f"""Frame {i}: {frame.get('name', 'Unknown')}
  - Dimensions: {frame.get('dimensions', {}).get('width', 0)}x{frame.get('dimensions', {}).get('height', 0)}
  - Components: {frame.get('component_count', 0)}
  - Page: {frame.get('page_name', 'Unknown')}"""

            frames_overview.append(frame_info)
            total_components += frame.get('component_count', 0)

        frames_section = "\n".join(frames_overview)

        prompt = f"""{system_prompt}

BATCH PROCESSING REQUEST:
You are processing {len(frames_data)} frames with {total_components} total components.

FRAMES TO PROCESS:
{frames_section}

INSTRUCTIONS:
1. Process each frame individually
2. Maintain consistency across frames
3. Use shared components efficiently
4. Ensure proper navigation between frames
5. Optimize for performance across all frames

For each frame, provide:
- Complete HTML structure
- Consolidated CSS for all frames
- JavaScript for interactions
- Component usage documentation

OUTPUT FORMAT:
Provide code for each frame in separate sections, then consolidated styles and scripts."""

        return prompt

    def generate_component_prompt(self, component_data: Dict, context: str = "") -> str:
        """Generate a prompt for a specific component"""
        comp_ref = self.component_references.get(component_data['id'])

        if not comp_ref:
            return f"Component {component_data['id']} not found in manifest."

        prompt = f"""Generate code for the following component:

Component: {comp_ref['original_name']}
Type: {comp_ref['type']}
Path: {comp_ref['path']}
Dimensions: {comp_ref['dimensions']['width']}x{comp_ref['dimensions']['height']}
ID: {component_data['id']}

Context: {context}

Requirements:
• Use semantic HTML
• Apply appropriate CSS styling
• Include accessibility attributes
• Ensure responsive behavior
• Reference the asset path correctly

Provide HTML and CSS for this component:"""

        return prompt

    def validate_prompt_output(self, generated_code: str) -> Dict[str, Any]:
        """Validate the generated code for common issues"""
        validation_results = {
            'valid': True,
            'issues': [],
            'warnings': [],
            'suggestions': []
        }

        # Check for component path references
        if 'components/' not in generated_code:
            validation_results['warnings'].append("No component asset references found")

        # Check for semantic HTML
        semantic_tags = ['header', 'nav', 'main', 'section', 'article', 'aside', 'footer']
        found_semantic = any(tag in generated_code.lower() for tag in semantic_tags)
        if not found_semantic:
            validation_results['suggestions'].append("Consider using semantic HTML elements")

        # Check for accessibility attributes
        accessibility_attrs = ['alt=', 'aria-', 'role=']
        found_accessibility = any(attr in generated_code.lower() for attr in accessibility_attrs)
        if not found_accessibility:
            validation_results['warnings'].append("Consider adding accessibility attributes")

        # Check for responsive design
        responsive_indicators = ['@media', 'flex', 'grid', 'responsive']
        found_responsive = any(indicator in generated_code.lower() for indicator in responsive_indicators)
        if not found_responsive:
            validation_results['suggestions'].append("Consider adding responsive design features")

        return validation_results

    def optimize_prompt_for_provider(self, base_prompt: str, provider: str) -> str:
        """Optimize prompt for specific AI provider"""
        optimizations = {
            'openai': {
                'add_prefix': "You are a senior frontend developer with 10+ years of experience.",
                'max_tokens': "Be concise but complete.",
                'format_hint': "Use proper code formatting with syntax highlighting."
            },
            'anthropic': {
                'add_prefix': "You are an expert UI/UX developer specializing in design-to-code conversion.",
                'reasoning': "Explain your approach before providing code.",
                'format_hint': "Use clear, well-documented code."
            },
            'google': {
                'add_prefix': "You are a professional web developer creating production-ready code.",
                'structure': "Organize code into logical sections.",
                'format_hint': "Use consistent formatting and naming conventions."
            }
        }

        if provider.lower() in optimizations:
            opt = optimizations[provider.lower()]
            optimized_prompt = base_prompt

            if 'add_prefix' in opt:
                optimized_prompt = f"{opt['add_prefix']}\n\n{optimized_prompt}"

            if 'reasoning' in opt:
                optimized_prompt += f"\n\n{opt['reasoning']}"

            if 'max_tokens' in opt:
                optimized_prompt += f"\n\n{opt['max_tokens']}"

            if 'format_hint' in opt:
                optimized_prompt += f"\n\n{opt['format_hint']}"

            return optimized_prompt

        return base_prompt

    def create_prompt_template(self, template_name: str, custom_variables: Dict[str, Any] = None) -> str:
        """Create a reusable prompt template"""
        templates = {
            'single_component': """
Generate code for a single component with the following specifications:

Component Details:
- Name: {{component_name}}
- Type: {{component_type}}
- Dimensions: {{width}}x{{height}}
- Asset Path: {{asset_path}}

Requirements:
- Use semantic HTML
- Apply modern CSS techniques
- Ensure responsive design
- Include accessibility features
- Reference assets correctly

Context: {{context}}

Generate the HTML and CSS code:
""",

            'frame_layout': """
Convert the following frame to HTML/CSS/JS:

Frame Information:
- Name: {{frame_name}}
- Dimensions: {{width}}x{{height}}
- Component Count: {{component_count}}
- Page: {{page_name}}

Available Components:
{{component_list}}

Technical Requirements:
- Pixel-perfect accuracy
- Responsive design
- Modern CSS (Flexbox/Grid)
- Clean JavaScript
- Bootstrap integration (optional)

Generate complete code:
""",

            'interactive_component': """
Create an interactive component with the following features:

Component: {{component_name}}
Functionality: {{functionality}}
States: {{states}}
Interactions: {{interactions}}

Requirements:
- Smooth animations
- Proper state management
- Event handling
- Accessibility compliance
- Performance optimized

Generate HTML, CSS, and JavaScript:
"""
        }

        template = templates.get(template_name, "")
        if not template:
            return ""

        # Replace variables
        if custom_variables:
            for key, value in custom_variables.items():
                template = template.replace(f"{{{{key}}}}", str(value))

        return template

    def save_prompt_history(self, prompt: str, response: str, metadata: Dict[str, Any] = None):
        """Save prompt and response for analysis and improvement"""
        history_entry = {
            'timestamp': datetime.now().isoformat(),
            'prompt': prompt,
            'response': response,
            'metadata': metadata or {},
            'validation': self.validate_prompt_output(response)
        }

        # Save to history file
        history_file = Path("prompt_history.jsonl")
        with open(history_file, 'a', encoding='utf-8') as f:
            json.dump(history_entry, f, ensure_ascii=False)
            f.write('\n')

        print(f"💾 Prompt history saved to {history_file}")


# Example usage and testing
if __name__ == "__main__":
    # Initialize the prompt engineer
    prompt_engineer = AIPromptEngineer()

    # Test component manifest loading
    print(f"📋 Loaded {len(prompt_engineer.component_references)} component references")

    # Test prompt generation for a sample frame
    if prompt_engineer.component_references:
        sample_frame = {
            'name': 'Sample Frame',
            'dimensions': {'width': 375, 'height': 812},
            'page_name': 'Home Page',
            'component_count': 5,
            'element_summary': {'total_elements': 10}
        }

        sample_components = [
            {'id': list(prompt_engineer.component_references.keys())[0]},
            {'id': list(prompt_engineer.component_references.keys())[1]} if len(prompt_engineer.component_references) > 1 else None
        ]
        sample_components = [c for c in sample_components if c]

        if sample_components:
            prompt = prompt_engineer.generate_frame_prompt(sample_frame, sample_components)
            print("🎯 Generated Prompt Preview:")
            print(prompt[:500] + "..." if len(prompt) > 500 else prompt)

            # Test validation
            mock_response = "<div class='component'><img src='components/images/sample.png' alt='Sample'></div>"
            validation = prompt_engineer.validate_prompt_output(mock_response)
            print(f"✅ Validation Results: {validation}")

    print("🎉 AI Prompt Engineering System Ready!")
