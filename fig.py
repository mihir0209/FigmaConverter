import json
import requests
from urllib.parse import urlparse
import dotenv
dotenv.load_dotenv()
import os
def extract_file_key_from_url(figma_url):
    """Extract file key from Figma community URL"""
    try:
        # Parse URL and extract file key
        path_parts = urlparse(figma_url).path.split('/')
        if 'design' in path_parts:
            design_index = path_parts.index('design')
            file_key = path_parts[design_index + 1]
            return file_key
    except:
        return None
    return None

def fetch_figma_design_data(file_key, api_token):
    """Fetch design data from Figma API"""
    url = f"https://api.figma.com/v1/files/{file_key}"
    headers = {"X-Figma-Token": api_token}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching data: {e}")
        return None

def count_elements_by_type(children, element_type):
    """Count specific element types in children array"""
    if not children:
        return 0
    return len([child for child in children if child.get('type') == element_type])

def extract_design_metadata(figma_response):
    """Extract comprehensive design metadata from Figma API response"""
    if not figma_response or 'document' not in figma_response:
        return None
    
    document = figma_response['document']
    
    # Document level information
    design_metadata = {
        'file_name': figma_response.get('name', 'Unknown'),
        'document_id': document.get('id'),
        'document_name': document.get('name'),
        'last_modified': figma_response.get('lastModified'),
        'version': figma_response.get('version'),
        'total_pages': 0,
        'pages': []
    }
    
    # Extract pages
    pages = document.get('children', [])
    design_metadata['total_pages'] = len(pages)
    
    for page in pages:
        if page.get('type') != 'CANVAS':  # Skip non-page elements
            continue
            
        page_info = {
            'page_id': page.get('id'),
            'page_name': page.get('name'),
            'background_color': page.get('backgroundColor'),
            'children': page.get('children', [])
        }
        
        # Extract frames from this page
        page_children = page.get('children', [])
        frames = [child for child in page_children if child.get('type') == 'FRAME']
        page_info['total_frames'] = len(frames)
        page_info['frames'] = []
        
        # Count different element types on this page
        page_info['total_text_elements'] = count_elements_by_type(page_children, 'TEXT')
        page_info['total_groups'] = count_elements_by_type(page_children, 'GROUP')
        page_info['total_components'] = count_elements_by_type(page_children, 'COMPONENT')
        page_info['total_instances'] = count_elements_by_type(page_children, 'INSTANCE')
        
        # Extract detailed frame information
        for frame in frames:
            frame_info = {
                'frame_id': frame.get('id'),
                'frame_name': frame.get('name'),
                'frame_type': frame.get('type'),
                'children_count': len(frame.get('children', [])),
                'background_color': frame.get('backgroundColor')
            }
            
            # Get frame dimensions if available
            if 'absoluteBoundingBox' in frame:
                bbox = frame['absoluteBoundingBox']
                frame_info['dimensions'] = {
                    'width': bbox.get('width'),
                    'height': bbox.get('height'),
                    'x': bbox.get('x'),
                    'y': bbox.get('y')
                }
            
            # Count elements inside this frame
            frame_children = frame.get('children', [])
            frame_info['elements'] = {
                'text_count': count_elements_by_type(frame_children, 'TEXT'),
                'group_count': count_elements_by_type(frame_children, 'GROUP'),
                'rectangle_count': count_elements_by_type(frame_children, 'RECTANGLE'),
                'vector_count': count_elements_by_type(frame_children, 'VECTOR'),
                'component_count': count_elements_by_type(frame_children, 'COMPONENT'),
                'instance_count': count_elements_by_type(frame_children, 'INSTANCE')
            }
            
            page_info['frames'].append(frame_info)
        
        design_metadata['pages'].append(page_info)
    
    # Calculate total elements across all pages
    design_metadata['totals'] = {
        'total_frames': sum(page['total_frames'] for page in design_metadata['pages']),
        'total_text_elements': sum(page['total_text_elements'] for page in design_metadata['pages']),
        'total_groups': sum(page['total_groups'] for page in design_metadata['pages']),
        'total_components': sum(page['total_components'] for page in design_metadata['pages']),
        'total_instances': sum(page['total_instances'] for page in design_metadata['pages'])
    }
    
    return design_metadata

def analyze_figma_design(figma_url, api_token):
    """Complete workflow to analyze Figma design from URL"""
    print(f"🔍 Analyzing Figma design: {figma_url}")
    
    # Step 1: Extract file key from URL
    file_key = extract_file_key_from_url(figma_url)
    if not file_key:
        print("❌ Could not extract file key from URL")
        return None
    
    print(f"📋 File Key: {file_key}")
    
    # Step 2: Fetch design data from API
    print("🌐 Fetching design data from Figma API...")
    figma_data = fetch_figma_design_data(file_key, api_token)
    
    if not figma_data:
        print("❌ Failed to fetch design data")
        return None
    
    # Step 3: Extract metadata
    print("📊 Extracting design metadata...")
    metadata = extract_design_metadata(figma_data)
    
    return metadata

def print_design_summary(metadata):
    """Print a formatted summary of the design metadata"""
    if not metadata:
        print("No metadata available")
        return
    
    print("\n" + "="*50)
    print("📋 FIGMA DESIGN ANALYSIS SUMMARY")
    print("="*50)
    
    print(f"📄 File Name: {metadata['file_name']}")
    print(f"📄 Document Name: {metadata['document_name']}")
    print(f"📅 Last Modified: {metadata['last_modified']}")
    print(f"🔢 Version: {metadata['version']}")
    
    print(f"\n📊 OVERALL STATISTICS:")
    print(f"   📑 Total Pages: {metadata['total_pages']}")
    print(f"   🖼️  Total Frames: {metadata['totals']['total_frames']}")
    print(f"   📝 Total Text Elements: {metadata['totals']['total_text_elements']}")
    print(f"   👥 Total Groups: {metadata['totals']['total_groups']}")
    print(f"   🧩 Total Components: {metadata['totals']['total_components']}")
    print(f"   📦 Total Instances: {metadata['totals']['total_instances']}")
    
    print(f"\n📑 PAGE BREAKDOWN:")
    for i, page in enumerate(metadata['pages'], 1):
        print(f"\n   📄 Page {i}: {page['page_name']}")
        print(f"      🖼️  Frames: {page['total_frames']}")
        print(f"      📝 Text Elements: {page['total_text_elements']}")
        print(f"      👥 Groups: {page['total_groups']}")
        
        if page['frames']:
            print(f"      📋 Frame Details:")
            for frame in page['frames']:
                print(f"         • {frame['frame_name']} ({frame['children_count']} elements)")
                if 'dimensions' in frame:
                    dims = frame['dimensions']
                    print(f"           Size: {dims['width']}×{dims['height']}px")

# Example usage
if __name__ == "__main__":
    API_TOKEN = os.getenv("FIGMA_API_TOKEN")
    FIGMA_URL = "https://www.figma.com/design/complete-the-url-with-your-file-key"
    
    result = analyze_figma_design(FIGMA_URL, API_TOKEN)
    
    if result:
        print_design_summary(result)
        
        # Save detailed metadata to JSON file
        with open('figma_design_metadata.json', 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\n💾 Detailed metadata saved to 'figma_design_metadata.json'")
    else:
        print("❌ Failed to analyze design")