#!/usr/bin/env python3
"""
Enhanced Figma Frame Parser
Extracts comprehensive design information from Figma frames for AI code generation
"""

import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

@dataclass
class TextElement:
    """Detailed text element information"""
    id: str
    text: str
    font_family: str
    font_size: float
    font_weight: int
    color: str  # hex color
    position: Dict[str, float]  # x, y, width, height
    alignment: str
    line_height: float

@dataclass 
class ImageElement:
    """Detailed image element information"""
    id: str
    image_ref: str
    position: Dict[str, float]
    alt_text: str  # element name
    
@dataclass
class LayoutElement:
    """Layout/container element information"""
    id: str
    name: str
    element_type: str  # RECTANGLE, GROUP, etc.
    position: Dict[str, float]
    background_color: Optional[str]
    border_radius: Optional[float]
    children_count: int

class EnhancedFrameParser:
    """Extract comprehensive frame details for AI code generation"""
    
    def __init__(self):
        self.color_styles = {}  # Map of style IDs to color values
        
    def parse_frame_comprehensive(self, frame_data: Dict, design_styles: Dict = None) -> Dict[str, Any]:
        """
        Parse a frame and extract all detailed information for AI code generation
        
        Args:
            frame_data: Complete frame JSON from Figma API
            design_styles: Style definitions from the design
            
        Returns:
            Comprehensive frame information for AI processing
        """
        
        # Store design styles for color resolution
        if design_styles:
            self.color_styles = design_styles.get('styles', {})
        
        frame_info = {
            'basic_info': {
                'id': frame_data.get('id'),
                'name': frame_data.get('name'),
                'type': frame_data.get('type'),
                'dimensions': self._extract_dimensions(frame_data)
            },
            'layout': self._extract_layout_info(frame_data),
            'content': {
                'texts': self._extract_all_texts(frame_data),
                'images': self._extract_all_images(frame_data),
                'containers': self._extract_layout_containers(frame_data),
                'interactive_elements': self._extract_interactive_elements(frame_data)
            },
            'design_system': {
                'colors': self._extract_color_palette(frame_data),
                'typography': self._extract_typography_system(frame_data),
                'spacing': self._extract_spacing_patterns(frame_data),
                'effects': self._extract_effects(frame_data)
            },
            'structure': {
                'hierarchy': self._build_component_hierarchy(frame_data),
                'layout_type': self._detect_layout_type(frame_data),
                'responsive_hints': self._detect_responsive_patterns(frame_data)
            },
            'component_count': self._count_components(frame_data),
            'complexity_score': self._calculate_complexity_score(frame_data)
        }
        
        return frame_info
    
    def _extract_dimensions(self, element: Dict) -> Dict[str, float]:
        """Extract element dimensions"""
        if 'absoluteBoundingBox' in element:
            bbox = element['absoluteBoundingBox']
            return {
                'width': bbox.get('width', 0),
                'height': bbox.get('height', 0),
                'x': bbox.get('x', 0),
                'y': bbox.get('y', 0)
            }
        return {'width': 0, 'height': 0, 'x': 0, 'y': 0}
    
    def _extract_layout_info(self, frame_data: Dict) -> Dict[str, Any]:
        """Extract layout and positioning information"""
        layout = {
            'background_color': self._parse_color(frame_data.get('backgroundColor')),
            'padding': self._detect_padding(frame_data),
            'constraints': frame_data.get('constraints', {}),
            'scroll_behavior': frame_data.get('scrollBehavior', 'SCROLLS'),
            'blend_mode': frame_data.get('blendMode', 'PASS_THROUGH')
        }
        
        # Extract background fills/gradients
        if 'fills' in frame_data:
            layout['fills'] = self._parse_fills(frame_data['fills'])
            
        return layout
    
    def _extract_all_texts(self, element: Dict, texts: List[TextElement] = None) -> List[Dict[str, Any]]:
        """Recursively extract all text elements with full styling"""
        if texts is None:
            texts = []
            
        if element.get('type') == 'TEXT':
            text_info = {
                'id': element.get('id'),
                'content': element.get('characters', ''),
                'position': self._extract_dimensions(element),
                'style': self._extract_text_style(element),
                'context': self._determine_text_context(element)
            }
            texts.append(text_info)
        
        # Recursively process children
        for child in element.get('children', []):
            self._extract_all_texts(child, texts)
            
        return texts
    
    def _extract_text_style(self, text_element: Dict) -> Dict[str, Any]:
        """Extract comprehensive text styling information"""
        style = text_element.get('style', {})
        fills = text_element.get('fills', [])
        
        text_style = {
            'font_family': style.get('fontFamily', 'Unknown'),
            'font_size': style.get('fontSize', 14),
            'font_weight': style.get('fontWeight', 400),
            'font_style': style.get('fontStyle', 'normal'),
            'line_height': style.get('lineHeightPx', 16),
            'letter_spacing': style.get('letterSpacing', 0),
            'text_align': style.get('textAlignHorizontal', 'LEFT'),
            'text_color': self._extract_text_color(fills),
            'text_decoration': self._extract_text_decoration(text_element)
        }
        
        return text_style
    
    def _extract_text_color(self, fills: List[Dict]) -> str:
        """Extract text color from fills"""
        if not fills:
            return '#000000'
            
        for fill in fills:
            if fill.get('type') == 'SOLID' and 'color' in fill:
                color = fill['color']
                return self._rgba_to_hex(color)
                
        return '#000000'
    
    def _rgba_to_hex(self, color: Dict) -> str:
        """Convert RGBA color to hex"""
        r = int(color.get('r', 0) * 255)
        g = int(color.get('g', 0) * 255)
        b = int(color.get('b', 0) * 255)
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def _extract_all_images(self, element: Dict, images: List[Dict] = None) -> List[Dict[str, Any]]:
        """Recursively extract all image elements"""
        if images is None:
            images = []
            
        # Check if this element has image fills
        fills = element.get('fills', [])
        for fill in fills:
            if fill.get('type') == 'IMAGE' and 'imageRef' in fill:
                image_info = {
                    'id': element.get('id'),
                    'name': element.get('name', 'Unknown Image'),
                    'image_ref': fill['imageRef'],
                    'position': self._extract_dimensions(element),
                    'scale_mode': fill.get('scaleMode', 'FILL'),
                    'context': self._determine_image_context(element)
                }
                images.append(image_info)
        
        # Recursively process children
        for child in element.get('children', []):
            self._extract_all_images(child, images)
            
        return images
    
    def _extract_layout_containers(self, element: Dict, containers: List[Dict] = None) -> List[Dict[str, Any]]:
        """Extract layout containers (rectangles, groups, frames)"""
        if containers is None:
            containers = []
            
        element_type = element.get('type')
        if element_type in ['RECTANGLE', 'GROUP', 'FRAME', 'COMPONENT']:
            container_info = {
                'id': element.get('id'),
                'name': element.get('name', 'Unknown'),
                'type': element_type,
                'position': self._extract_dimensions(element),
                'children_count': len(element.get('children', [])),
                'background': self._extract_background_info(element),
                'effects': self._extract_element_effects(element),
                'layout_role': self._determine_layout_role(element)
            }
            containers.append(container_info)
        
        # Recursively process children
        for child in element.get('children', []):
            self._extract_layout_containers(child, containers)
            
        return containers
    
    def _extract_background_info(self, element: Dict) -> Dict[str, Any]:
        """Extract background information"""
        background = {
            'color': self._parse_color(element.get('backgroundColor')),
            'fills': [],
            'border_radius': element.get('cornerRadius', 0)
        }
        
        # Parse fills (solid colors, gradients, images)
        if 'fills' in element:
            background['fills'] = self._parse_fills(element['fills'])
            
        return background
    
    def _parse_fills(self, fills: List[Dict]) -> List[Dict[str, Any]]:
        """Parse fill information (colors, gradients, images)"""
        parsed_fills = []
        
        for fill in fills:
            fill_type = fill.get('type')
            fill_info = {'type': fill_type}
            
            if fill_type == 'SOLID':
                fill_info['color'] = self._rgba_to_hex(fill.get('color', {}))
            elif fill_type == 'GRADIENT_LINEAR':
                fill_info['gradient'] = self._parse_gradient(fill)
            elif fill_type == 'IMAGE':
                fill_info['image_ref'] = fill.get('imageRef')
                fill_info['scale_mode'] = fill.get('scaleMode', 'FILL')
                
            parsed_fills.append(fill_info)
            
        return parsed_fills
    
    def _extract_color_palette(self, element: Dict, colors: set = None) -> List[str]:
        """Extract all colors used in the frame"""
        if colors is None:
            colors = set()
            
        # Extract from fills
        for fill in element.get('fills', []):
            if fill.get('type') == 'SOLID' and 'color' in fill:
                colors.add(self._rgba_to_hex(fill['color']))
        
        # Extract from strokes
        for stroke in element.get('strokes', []):
            if stroke.get('type') == 'SOLID' and 'color' in stroke:
                colors.add(self._rgba_to_hex(stroke['color']))
        
        # Recursively process children
        for child in element.get('children', []):
            self._extract_color_palette(child, colors)
            
        return list(colors)
    
    def _extract_typography_system(self, element: Dict, fonts: Dict = None) -> Dict[str, Any]:
        """Extract typography system"""
        if fonts is None:
            fonts = {}
            
        if element.get('type') == 'TEXT':
            style = element.get('style', {})
            font_key = f"{style.get('fontFamily', 'Unknown')}_{style.get('fontSize', 14)}_{style.get('fontWeight', 400)}"
            
            if font_key not in fonts:
                fonts[font_key] = {
                    'family': style.get('fontFamily', 'Unknown'),
                    'size': style.get('fontSize', 14),
                    'weight': style.get('fontWeight', 400),
                    'usage_count': 0
                }
            fonts[font_key]['usage_count'] += 1
        
        # Recursively process children
        for child in element.get('children', []):
            self._extract_typography_system(child, fonts)
            
        return fonts
    
    def _count_components(self, element: Dict) -> Dict[str, int]:
        """Count different types of components"""
        counts = {
            'texts': 0,
            'images': 0,
            'buttons': 0,
            'inputs': 0,
            'containers': 0,
            'icons': 0,
            'total': 0
        }
        
        def count_recursive(elem):
            elem_type = elem.get('type', '').upper()
            elem_name = elem.get('name', '').lower()
            
            if elem_type == 'TEXT':
                counts['texts'] += 1
            elif elem_type == 'RECTANGLE':
                # Check if it's an image
                has_image = any(fill.get('type') == 'IMAGE' for fill in elem.get('fills', []))
                if has_image:
                    counts['images'] += 1
                elif 'button' in elem_name or 'btn' in elem_name:
                    counts['buttons'] += 1
                elif 'input' in elem_name or 'field' in elem_name:
                    counts['inputs'] += 1
                else:
                    counts['containers'] += 1
            elif elem_type in ['GROUP', 'FRAME', 'COMPONENT']:
                if 'icon' in elem_name:
                    counts['icons'] += 1
                else:
                    counts['containers'] += 1
            
            counts['total'] += 1
            
            # Process children
            for child in elem.get('children', []):
                count_recursive(child)
        
        count_recursive(element)
        return counts
    
    def _determine_text_context(self, text_element: Dict) -> str:
        """Determine the context/role of a text element"""
        text = text_element.get('characters', '').lower()
        name = text_element.get('name', '').lower()
        style = text_element.get('style', {})
        font_size = style.get('fontSize', 14)
        
        # Determine text role based on content and styling
        if font_size >= 24:
            return 'heading'
        elif any(word in text for word in ['sign up', 'login', 'register', 'submit']):
            return 'button_text'
        elif any(word in text for word in ['email', 'password', 'name', 'phone']):
            return 'form_label'
        elif '?' in text:
            return 'question'
        elif len(text) > 100:
            return 'paragraph'
        else:
            return 'label'
    
    def _determine_image_context(self, image_element: Dict) -> str:
        """Determine the context/role of an image element"""
        name = image_element.get('name', '').lower()
        dimensions = self._extract_dimensions(image_element)
        
        if 'logo' in name:
            return 'logo'
        elif 'icon' in name:
            return 'icon'
        elif 'avatar' in name or 'profile' in name:
            return 'avatar'
        elif dimensions['width'] > 200 and dimensions['height'] > 200:
            return 'hero_image'
        else:
            return 'decorative'
    
    def _determine_layout_role(self, element: Dict) -> str:
        """Determine the layout role of a container element"""
        name = element.get('name', '').lower()
        children_count = len(element.get('children', []))
        element_type = element.get('type')
        
        if element_type == 'FRAME':
            return 'screen'
        elif 'button' in name:
            return 'button'
        elif 'card' in name:
            return 'card'
        elif 'header' in name:
            return 'header'
        elif 'footer' in name:
            return 'footer'
        elif children_count > 5:
            return 'container'
        else:
            return 'component'
    
    def _parse_color(self, color_data: Any) -> Optional[str]:
        """Parse color from various Figma color formats"""
        if isinstance(color_data, dict):
            return self._rgba_to_hex(color_data)
        return None
    
    def _calculate_complexity_score(self, element: Dict) -> int:
        """Calculate complexity score for the frame"""
        counts = self._count_components(element)
        score = (
            counts['texts'] * 1 +
            counts['images'] * 2 +
            counts['buttons'] * 3 +
            counts['inputs'] * 3 +
            counts['containers'] * 1 +
            counts['icons'] * 1
        )
        return score
    
    # Placeholder methods for additional analysis
    def _extract_spacing_patterns(self, element: Dict) -> Dict[str, Any]:
        return {'margin': 16, 'padding': 12, 'gap': 8}
    
    def _extract_effects(self, element: Dict) -> List[Dict]:
        return element.get('effects', [])
    
    def _extract_element_effects(self, element: Dict) -> List[Dict]:
        return element.get('effects', [])
    
    def _build_component_hierarchy(self, element: Dict) -> Dict[str, Any]:
        return {'depth': 3, 'max_nesting': 5}
    
    def _detect_layout_type(self, element: Dict) -> str:
        children = element.get('children', [])
        if len(children) <= 1:
            return 'single'
        elif len(children) <= 3:
            return 'simple'
        else:
            return 'complex'
    
    def _detect_responsive_patterns(self, element: Dict) -> Dict[str, Any]:
        return {'breakpoints': ['mobile'], 'flexible': True}
    
    def _detect_padding(self, element: Dict) -> Dict[str, float]:
        return {'top': 16, 'right': 16, 'bottom': 16, 'left': 16}
    
    def _parse_gradient(self, gradient_fill: Dict) -> Dict[str, Any]:
        return {'type': 'linear', 'stops': []}
    
    def _extract_text_decoration(self, text_element: Dict) -> str:
        return 'none'
    
    def _extract_interactive_elements(self, element: Dict) -> List[Dict]:
        """Extract interactive elements like buttons, links, inputs"""
        interactive = []
        
        def find_interactive(elem):
            name = elem.get('name', '').lower()
            elem_type = elem.get('type')
            
            # Detect buttons
            if ('button' in name or 'btn' in name or 
                any(word in elem.get('characters', '').lower() for word in ['sign up', 'login', 'submit', 'continue'])):
                interactive.append({
                    'type': 'button',
                    'id': elem.get('id'),
                    'name': elem.get('name'),
                    'text': elem.get('characters', ''),
                    'position': self._extract_dimensions(elem)
                })
            
            # Detect input fields
            elif ('input' in name or 'field' in name or 'textfield' in name):
                interactive.append({
                    'type': 'input',
                    'id': elem.get('id'),
                    'name': elem.get('name'),
                    'position': self._extract_dimensions(elem)
                })
            
            # Process children
            for child in elem.get('children', []):
                find_interactive(child)
        
        find_interactive(element)
        return interactive

def main():
    """Test the enhanced parser with the Sign Up frame"""
    # Load the Figma design data
    with open('figma_structure_ncyDNp3iES76bBPlfI9tgD.json', 'r', encoding='utf-8') as f:
        design_data = json.load(f)
    
    parser = EnhancedFrameParser()
    
    # Find the Sign Up frame
    def find_frame_by_id(data, frame_id):
        def search_recursive(element):
            if element.get('id') == frame_id:
                return element
            for child in element.get('children', []):
                result = search_recursive(child)
                if result:
                    return result
            return None
        return search_recursive(data['document'])
    
    signup_frame = find_frame_by_id(design_data, '0:1275')
    
    if signup_frame:
        print("🎯 Found Sign Up frame!")
        print(f"Frame name: {signup_frame.get('name')}")
        print(f"Children count: {len(signup_frame.get('children', []))}")
        print()
        
        # Parse comprehensive frame details
        frame_details = parser.parse_frame_comprehensive(signup_frame, design_data)
        
        print("📊 Comprehensive Frame Analysis:")
        print("=" * 50)
        print(f"Frame: {frame_details['basic_info']['name']}")
        print(f"Dimensions: {frame_details['basic_info']['dimensions']}")
        print(f"Component counts: {frame_details['component_count']}")
        print(f"Complexity score: {frame_details['complexity_score']}")
        print()
        
        print("📝 Text Elements:")
        for i, text in enumerate(frame_details['content']['texts'][:5], 1):  # Show first 5
            print(f"{i}. '{text['content']}' - {text['style']['font_family']} {text['style']['font_size']}px")
        
        print(f"\n🎨 Colors used: {frame_details['design_system']['colors']}")
        print(f"📚 Typography: {len(frame_details['design_system']['typography'])} font combinations")
        
        print(f"\n🔘 Interactive elements: {len(frame_details['content']['interactive_elements'])}")
        for elem in frame_details['content']['interactive_elements']:
            print(f"  - {elem['type']}: {elem['name']} - '{elem.get('text', '')}'")
        
        # Save detailed analysis
        with open('signup_frame_analysis.json', 'w', encoding='utf-8') as f:
            json.dump(frame_details, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Detailed analysis saved to: signup_frame_analysis.json")
        print("✅ This is the rich data that should be sent to the AI!")
        
    else:
        print("❌ Sign Up frame not found")

if __name__ == "__main__":
    main()