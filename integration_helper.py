#!/usr/bin/env python3
"""
Integration script to update the main Figma processor with enhanced frame parsing
"""

def generate_integration_code():
    """Generate the code to integrate enhanced parsing into main processor"""
    
    integration_code = '''
# Add this import at the top of enhanced_figma_processor.py
from enhanced_frame_parser import EnhancedFrameParser

# Add this method to the EnhancedFigmaProcessor class
def extract_comprehensive_frame_data(self, frame: Dict, design_data: Dict = None) -> Dict[str, Any]:
    """
    Extract comprehensive frame data using the enhanced parser
    """
    parser = EnhancedFrameParser()
    return parser.parse_frame_comprehensive(frame, design_data)

# Update the _process_single_frame method to include comprehensive data
def _process_single_frame_enhanced(self, frame: Dict, file_key: str, frame_index: int, include_components: bool, design_data: Dict = None) -> Optional[Dict]:
    """Process a single frame with comprehensive data extraction"""
    try:
        frame_name = frame['name']
        print(f"🔄 Processing frame {frame_index + 1}: {frame_name}")

        # Extract comprehensive frame data
        comprehensive_data = self.extract_comprehensive_frame_data(frame, design_data)
        
        # Extract components and get references only if requested
        frame_component_refs = {}
        if include_components:
            frame_components = self.extract_components_from_frame(frame)
            frame_component_refs = self.export_frame_components(frame_components, file_key, frame_name)

        # Create enhanced frame summary with comprehensive data
        frame_summary = {
            'name': frame_name,
            'id': frame['id'],
            'dimensions': comprehensive_data['basic_info']['dimensions'],
            'component_count': comprehensive_data['component_count'],
            'complexity_score': comprehensive_data['complexity_score'],
            'comprehensive_data': comprehensive_data,  # Include all the rich data
            'exported_components': len(frame_component_refs)
        }

        result = {
            'summary': frame_summary,
            'component_refs': frame_component_refs
        }

        return result

    except Exception as e:
        print(f"❌ Error processing frame {frame.get('name', 'Unknown')}: {e}")
        return None
'''
    
    return integration_code

def main():
    print("🔧 Integration Code for Enhanced Frame Processing")
    print("=" * 60)
    print(generate_integration_code())
    
    print("\n📋 Steps to integrate:")
    print("1. Add the import statement to enhanced_figma_processor.py")
    print("2. Add the extract_comprehensive_frame_data method")
    print("3. Update _process_single_frame to use comprehensive data")
    print("4. Update AI prompt generation to use the rich frame data")

if __name__ == "__main__":
    main()