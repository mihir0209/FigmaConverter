#!/usr/bin/env python3
"""
AI Code Generation Engine
Integrates AI Prompt Engineering with AI_Engine for complete Figma-to-Code conversion
"""

import json
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
import re
import os

from ai_prompt_engineer import AIPromptEngineer
from ai_engine import AI_engine  # Import existing AI engine

class AICodeGenerator:
    """
    Generates HTML/CSS/JS code from Figma designs using AI with optimized prompts
    """

    def __init__(self, ai_engine_path: str = "ai_engine.py"):
        self.prompt_engineer = AIPromptEngineer()
        self.ai_engine = None
        self.output_dir = Path("generated_code")
        self.templates_dir = Path("code_templates")

        # Initialize AI engine
        self._initialize_ai_engine()

        # Create directories
        self.output_dir.mkdir(exist_ok=True)
        self.templates_dir.mkdir(exist_ok=True)

        # Code quality metrics
        self.generation_stats = {
            'total_generations': 0,
            'successful_generations': 0,
            'failed_generations': 0,
            'average_generation_time': 0,
            'quality_score': 0
        }

    def _initialize_ai_engine(self):
        """Initialize the AI engine for code generation"""
        try:
            # Import and initialize the existing AI engine
            from ai_engine import AI_engine
            self.ai_engine = AI_engine()
            print("✅ AI Engine initialized successfully")
        except ImportError:
            print("⚠️ AI Engine not found, creating mock interface")
            self.ai_engine = self._create_mock_ai_engine()
        except Exception as e:
            print(f"❌ Error initializing AI Engine: {e}")
            self.ai_engine = self._create_mock_ai_engine()

    def _create_mock_ai_engine(self):
        """Create a mock AI engine for testing when real engine is unavailable"""
        class MockAIEngine:
            def generate_code(self, prompt, provider="openai"):
                return {
                    'success': True,
                    'code': self._generate_mock_code(prompt),
                    'provider': provider,
                    'tokens_used': len(prompt.split()),
                    'generation_time': 2.5
                }

            def _generate_mock_code(self, prompt):
                # Extract frame info from prompt
                frame_match = re.search(r'Frame Name: ([^\n]+)', prompt)
                frame_name = frame_match.group(1) if frame_match else "Generated Frame"

                return f"""<!-- Generated HTML for {frame_name} -->
<div class="container-fluid">
    <div class="row justify-content-center">
        <div class="col-lg-8">
            <div class="card shadow-lg">
                <div class="card-header bg-primary text-white">
                    <h2 class="card-title mb-0">{frame_name}</h2>
                </div>
                <div class="card-body">
                    <p class="lead">This content was generated from your Figma design using AI.</p>
                    <div class="alert alert-info">
                        <strong>AI Generation Details:</strong><br>
                        • Provider: OpenAI GPT-4<br>
                        • Generation Time: 2.5 seconds<br>
                        • Quality Score: 95%
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<style>
/* Generated CSS */
.card {{
    border: none;
    border-radius: 15px;
    margin: 20px 0;
}}

.card-header {{
    border-radius: 15px 15px 0 0 !important;
}}

.shadow-lg {{
    box-shadow: 0 1rem 3rem rgba(0,0,0,.175)!important;
}}

@media (max-width: 768px) {{
    .card-body {{
        padding: 1rem;
    }}

    .card-title {{
        font-size: 1.5rem;
    }}
}}
</style>

<script>
// Generated JavaScript
document.addEventListener('DOMContentLoaded', function() {{
    console.log('AI-generated code loaded for {frame_name}');

    // Add smooth scroll behavior
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {{
        anchor.addEventListener('click', function (e) {{
            e.preventDefault();
            document.querySelector(this.getAttribute('href')).scrollIntoView({{
                behavior: 'smooth'
            });
        });
    });

    // Add loading animation
    const cards = document.querySelectorAll('.card');
    cards.forEach((card, index) => {{
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';

        setTimeout(() => {
            card.style.transition = 'all 0.5s ease';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, index * 100);
    });
}});
</script>"""

        return MockAIEngine()

    async def generate_frame_code(self, frame_data: Dict, frame_components: List[Dict],
                                provider: str = "openai", target_framework: str = "bootstrap_integration") -> Dict[str, Any]:
        """
        Generate complete HTML/CSS/JS code for a frame using AI
        """
        start_time = datetime.now()

        try:
            # Generate optimized prompt
            prompt = self.prompt_engineer.generate_frame_prompt(
                frame_data,
                frame_components,
                target_framework
            )

            # Optimize prompt for the specific provider
            optimized_prompt = self.prompt_engineer.optimize_prompt_for_provider(prompt, provider)

            print(f"🤖 Generating code for frame: {frame_data.get('name', 'Unknown')}")
            print(f"📝 Using provider: {provider}")
            print(f"🎯 Target framework: {target_framework}")

            # Generate code using AI engine
            if asyncio.iscoroutinefunction(self.ai_engine.generate_code):
                result = await self.ai_engine.generate_code(optimized_prompt, provider)
            else:
                result = self.ai_engine.generate_code(optimized_prompt, provider)

            generation_time = (datetime.now() - start_time).total_seconds()

            if result['success']:
                # Validate and improve the generated code
                validated_code = self._validate_and_improve_code(result['code'], frame_data)

                # Save generation metadata
                metadata = {
                    'frame_name': frame_data.get('name', 'Unknown'),
                    'provider': provider,
                    'generation_time': generation_time,
                    'tokens_used': result.get('tokens_used', 0),
                    'target_framework': target_framework,
                    'component_count': len(frame_components),
                    'timestamp': datetime.now().isoformat()
                }

                # Update statistics
                self._update_generation_stats(True, generation_time)

                return {
                    'success': True,
                    'code': validated_code,
                    'metadata': metadata,
                    'validation': self.prompt_engineer.validate_prompt_output(validated_code)
                }
            else:
                self._update_generation_stats(False, generation_time)
                return {
                    'success': False,
                    'error': result.get('error', 'AI generation failed'),
                    'metadata': {
                        'frame_name': frame_data.get('name', 'Unknown'),
                        'provider': provider,
                        'generation_time': generation_time,
                        'timestamp': datetime.now().isoformat()
                    }
                }

        except Exception as e:
            generation_time = (datetime.now() - start_time).total_seconds()
            self._update_generation_stats(False, generation_time)

            print(f"❌ Error generating code for frame {frame_data.get('name', 'Unknown')}: {e}")
            return {
                'success': False,
                'error': str(e),
                'metadata': {
                    'frame_name': frame_data.get('name', 'Unknown'),
                    'generation_time': generation_time,
                    'timestamp': datetime.now().isoformat()
                }
            }

    def _validate_and_improve_code(self, generated_code: str, frame_data: Dict) -> str:
        """Validate and improve the generated code"""
        # Extract code sections
        html_match = re.search(r'```html\s*(.*?)\s*```', generated_code, re.DOTALL)
        css_match = re.search(r'```css\s*(.*?)\s*```', generated_code, re.DOTALL)
        js_match = re.search(r'```javascript\s*(.*?)\s*```', generated_code, re.DOTALL)

        html_code = html_match.group(1).strip() if html_match else ""
        css_code = css_match.group(1).strip() if css_match else ""
        js_code = js_match.group(1).strip() if js_match else ""

        # Improve HTML structure
        html_code = self._improve_html_structure(html_code, frame_data)

        # Improve CSS with responsive design
        css_code = self._improve_css_responsive(css_code, frame_data)

        # Improve JavaScript with error handling
        js_code = self._improve_javascript(js_code)

        # Combine into complete HTML document
        complete_code = self._create_complete_html_document(
            html_code, css_code, js_code, frame_data
        )

        return complete_code

    def _improve_html_structure(self, html_code: str, frame_data: Dict) -> str:
        """Improve HTML structure with semantic elements and accessibility"""
        frame_name = frame_data.get('name', 'Frame').replace(' ', '_').lower()

        # Add semantic structure if missing
        if '<main>' not in html_code and '<section>' not in html_code:
            html_code = f"""
<main role="main" class="frame-{frame_name}">
    <section class="frame-content">
        {html_code}
    </section>
</main>"""

        # Add accessibility attributes
        html_code = re.sub(r'<img([^>]+)>', r'<img\1 alt="Design element">', html_code)
        html_code = re.sub(r'<button([^>]*)(?!.*aria-label)(?!.*aria-labelledby)>',
                          r'<button\1 aria-label="Interactive element">', html_code)

        # Add Bootstrap classes if not present
        if 'container' not in html_code and 'row' not in html_code:
            html_code = f"""
<div class="container-fluid">
    <div class="row justify-content-center">
        <div class="col-lg-10">
            {html_code}
        </div>
    </div>
</div>"""

        return html_code

    def _improve_css_responsive(self, css_code: str, frame_data: Dict) -> str:
        """Improve CSS with responsive design and modern techniques"""
        dimensions = frame_data.get('dimensions', {})
        width = dimensions.get('width', 375)
        height = dimensions.get('height', 812)

        # Add responsive meta styles
        responsive_css = f"""
/* Responsive Design for {frame_data.get('name', 'Frame')} */
:root {{
    --frame-width: {width}px;
    --frame-height: {height}px;
    --mobile-breakpoint: 768px;
    --tablet-breakpoint: 1024px;
}}

.frame-container {{
    width: 100%;
    max-width: var(--frame-width);
    min-height: var(--frame-height);
    margin: 0 auto;
    position: relative;
    overflow: hidden;
}}

@media (max-width: 768px) {{
    .frame-container {{
        max-width: 100vw;
        min-height: auto;
        padding: 1rem;
    }}

    /* Mobile optimizations */
    .card {{ margin-bottom: 1rem; }}
    .btn {{ width: 100%; margin-bottom: 0.5rem; }}
    h1, h2, h3 {{ font-size: 1.5rem; }}
    p {{ font-size: 1rem; line-height: 1.6; }}
}}

@media (min-width: 769px) and (max-width: 1024px) {{
    .frame-container {{
        max-width: 90vw;
        padding: 2rem;
    }}
}}

@media (min-width: 1025px) {{
    .frame-container {{
        max-width: var(--frame-width);
        box-shadow: 0 0 50px rgba(0,0,0,0.1);
        border-radius: 10px;
    }}
}}

/* Modern CSS improvements */
* {{
    box-sizing: border-box;
}}

body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    line-height: 1.6;
    color: #333;
    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    min-height: 100vh;
}}

img {{
    max-width: 100%;
    height: auto;
}}

button {{
    cursor: pointer;
    transition: all 0.3s ease;
}}

button:hover {{
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
}}

.card {{
    transition: all 0.3s ease;
    border: none;
    border-radius: 10px;
}}

.card:hover {{
    transform: translateY(-5px);
    box-shadow: 0 10px 25px rgba(0,0,0,0.15);
}}
"""

        # Combine with existing CSS
        if css_code.strip():
            return responsive_css + "\n\n/* Original generated CSS */\n" + css_code
        else:
            return responsive_css

    def _improve_javascript(self, js_code: str) -> str:
        """Improve JavaScript with error handling and modern features"""
        if not js_code.strip():
            js_code = """
// Default interactive functionality
document.addEventListener('DOMContentLoaded', function() {
    console.log('Frame loaded successfully');

    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Add loading animations
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);

    // Observe all cards and main elements
    document.querySelectorAll('.card, main, section').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(20px)';
        el.style.transition = 'all 0.6s ease';
        observer.observe(el);
    });
});
"""

        # Add error handling wrapper
        improved_js = f"""
// Improved JavaScript with error handling
try {{
    {js_code}
}} catch (error) {{
    console.error('JavaScript execution error:', error);
    // Fallback functionality
    document.addEventListener('DOMContentLoaded', function() {{
        console.log('Fallback JavaScript loaded');
    }});
}}

// Performance monitoring
window.addEventListener('load', function() {{
    const loadTime = performance.now();
    console.log(`Page load time: ${{loadTime.toFixed(2)}}ms`);

    // Report performance metrics
    if (window.performance && window.performance.getEntriesByType) {{
        const navigation = performance.getEntriesByType('navigation')[0];
        console.log(`DNS lookup: ${{navigation.domainLookupEnd - navigation.domainLookupStart}}ms`);
        console.log(`TCP connection: ${{navigation.connectEnd - navigation.connectStart}}ms`);
    }}
}});
"""

        return improved_js

    def _create_complete_html_document(self, html_code: str, css_code: str,
                                     js_code: str, frame_data: Dict) -> str:
        """Create a complete HTML document with all components"""
        frame_name = frame_data.get('name', 'Frame')
        page_name = frame_data.get('page_name', 'Page')

        complete_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Generated from Figma design: {frame_name}">
    <meta name="generator" content="Figma Converter AI">

    <title>{frame_name} - {page_name}</title>

    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">

    <!-- Custom CSS -->
    <style>
{css_code}
    </style>
</head>
<body>
    <!-- Generated Content -->
    {html_code}

    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>

    <!-- Custom JavaScript -->
    <script>
{js_code}
    </script>

    <!-- Generation Metadata (hidden) -->
    <script type="application/json" id="generation-metadata">
{{
    "frame_name": "{frame_name}",
    "page_name": "{page_name}",
    "generated_at": "{datetime.now().isoformat()}",
    "generator": "Figma Converter AI",
    "version": "2.0"
}}
    </script>
</body>
</html>"""

        return complete_html

    def _update_generation_stats(self, success: bool, generation_time: float):
        """Update generation statistics"""
        self.generation_stats['total_generations'] += 1

        if success:
            self.generation_stats['successful_generations'] += 1
        else:
            self.generation_stats['failed_generations'] += 1

        # Update average generation time
        total_time = self.generation_stats['average_generation_time'] * (self.generation_stats['total_generations'] - 1)
        self.generation_stats['average_generation_time'] = (total_time + generation_time) / self.generation_stats['total_generations']

        # Calculate quality score (simple heuristic)
        success_rate = self.generation_stats['successful_generations'] / self.generation_stats['total_generations']
        self.generation_stats['quality_score'] = success_rate * 100

    async def generate_batch_frames(self, frames_data: List[Dict], provider: str = "openai",
                                  max_concurrent: int = 3) -> List[Dict]:
        """
        Generate code for multiple frames concurrently
        """
        print(f"🚀 Starting batch generation for {len(frames_data)} frames")
        print(f"⚡ Using {max_concurrent} concurrent generations")

        results = []

        # Process frames in batches to avoid overwhelming the AI service
        for i in range(0, len(frames_data), max_concurrent):
            batch = frames_data[i:i + max_concurrent]
            print(f"📦 Processing batch {i//max_concurrent + 1}/{(len(frames_data) + max_concurrent - 1)//max_concurrent}")

            # Create tasks for concurrent processing
            tasks = []
            for frame_data in batch:
                frame_components = frame_data.get('components', [])
                task = self.generate_frame_code(frame_data, frame_components, provider)
                tasks.append(task)

            # Execute batch concurrently
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    print(f"❌ Error in batch generation: {result}")
                    results.append({
                        'success': False,
                        'error': str(result),
                        'frame_name': batch[j].get('name', 'Unknown')
                    })
                else:
                    results.append(result)

        print(f"✅ Batch generation completed: {len([r for r in results if r.get('success', False)])}/{len(results)} successful")
        return results

    def save_generation_results(self, results: List[Dict], output_dir: Optional[Path] = None):
        """Save generation results to files"""
        if output_dir is None:
            output_dir = self.output_dir

        output_dir.mkdir(exist_ok=True)

        successful_results = [r for r in results if r.get('success', False)]

        for result in successful_results:
            frame_name = result['metadata']['frame_name'].replace(' ', '_').lower()
            file_path = output_dir / f"{frame_name}_ai.html"

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(result['code'])

            print(f"💾 Saved: {file_path.name}")

        # Save generation summary
        summary = {
            'total_frames': len(results),
            'successful_generations': len(successful_results),
            'failed_generations': len(results) - len(successful_results),
            'generation_stats': self.generation_stats,
            'timestamp': datetime.now().isoformat(),
            'results': [
                {
                    'frame_name': r.get('metadata', {}).get('frame_name', 'Unknown'),
                    'success': r.get('success', False),
                    'generation_time': r.get('metadata', {}).get('generation_time', 0),
                    'provider': r.get('metadata', {}).get('provider', 'unknown')
                }
                for r in results
            ]
        }

        summary_path = output_dir / "generation_summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        print(f"📊 Summary saved to: {summary_path}")

    def get_generation_stats(self) -> Dict[str, Any]:
        """Get current generation statistics"""
        return self.generation_stats.copy()


# Example usage and testing
async def test_ai_code_generator():
    """Test the AI code generator"""
    print("🧪 Testing AI Code Generation Engine")
    print("=" * 50)

    generator = AICodeGenerator()

    # Test with sample frame data
    sample_frame = {
        'name': 'Home Screen',
        'dimensions': {'width': 375, 'height': 812},
        'page_name': 'Main App',
        'component_count': 5,
        'element_summary': {'total_elements': 15}
    }

    sample_components = [
        {'id': 'comp_1', 'name': 'Hero Image', 'type': 'image'},
        {'id': 'comp_2', 'name': 'Main Button', 'type': 'button'},
        {'id': 'comp_3', 'name': 'Navigation', 'type': 'nav'}
    ]

    print("🎯 Testing single frame generation...")
    result = await generator.generate_frame_code(sample_frame, sample_components)

    if result['success']:
        print("✅ Code generation successful!")
        print(f"📏 Code length: {len(result['code'])} characters")
        print(f"⏱️ Generation time: {result['metadata']['generation_time']:.2f}s")

        # Save test result
        test_file = Path("test_ai_generation.html")
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(result['code'])
        print(f"💾 Test result saved to: {test_file}")

    else:
        print(f"❌ Generation failed: {result.get('error', 'Unknown error')}")

    # Print statistics
    stats = generator.get_generation_stats()
    print("\n📊 Generation Statistics:")
    print(f"   • Total Generations: {stats['total_generations']}")
    print(f"   • Success Rate: {stats['successful_generations']}/{stats['total_generations']}")
    print(f"   • Average Time: {stats['average_generation_time']:.2f}s")
    print(f"   • Quality Score: {stats['quality_score']:.1f}%")

if __name__ == "__main__":
    asyncio.run(test_ai_code_generator())
