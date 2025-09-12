"""
Component Collection System for Figma-to-Code Converter
Extracts and organizes design components with multi-threading support
"""

import json
import os
import asyncio
import concurrent.futures
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
import requests
import re
from urllib.parse import urlparse
import dotenv

# Load environment variables
dotenv.load_dotenv()

class ComponentCollector:
    """Collects and organizes components from Figma designs with threading"""

    def __init__(self, api_token: Optional[str] = None, max_workers: int = 8):
        self.api_token = api_token or os.getenv("FIGMA_API_TOKEN")
        self.max_workers = max_workers
        self.base_url = "https://api.figma.com/v1"
        self.images_url = "https://api.figma.com/v1/images"

        # Create output directories
        self.output_dir = Path("collected_components")
        self.images_dir = self.output_dir / "images"
        self.vectors_dir = self.output_dir / "vectors"
        self.metadata_dir = self.output_dir / "metadata"

        for dir_path in [self.output_dir, self.images_dir, self.vectors_dir, self.metadata_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def collect_components_from_design(self, file_key: str, nodes_data: List[Dict]) -> Dict[str, Any]:
        """Collect components from Figma design with multi-threading"""
        print(f"🔍 Starting component collection for {len(nodes_data)} nodes...")

        # Prepare component extraction tasks
        extraction_tasks = []
        for node_data in nodes_data:
            if self._is_component_node(node_data):
                extraction_tasks.append(node_data)

        print(f"📦 Found {len(extraction_tasks)} component nodes to process")

        # Process components with threading
        collected_components = []
        component_metadata = {}

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all component processing tasks
            future_to_node = {
                executor.submit(self._process_component_node, node, file_key): node
                for node in extraction_tasks
            }

            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_node):
                node = future_to_node[future]
                try:
                    result = future.result()
                    if result:
                        collected_components.append(result['component'])
                        component_metadata.update(result['metadata'])
                        print(f"✅ Processed component: {node.get('name', 'Unknown')}")
                    else:
                        print(f"⚠️ Failed to process component: {node.get('name', 'Unknown')}")
                except Exception as exc:
                    print(f"❌ Component {node.get('name', 'Unknown')} generated an exception: {exc}")

        # Save collection metadata
        self._save_collection_metadata(collected_components, component_metadata)

        result = {
            "total_components": len(collected_components),
            "components": collected_components,
            "metadata": component_metadata,
            "output_directory": str(self.output_dir),
            "collection_timestamp": datetime.now().isoformat()
        }

        print(f"📊 Component collection complete: {len(collected_components)} components collected")
        return result

    def _is_component_node(self, node_data: Dict) -> bool:
        """Check if a node is a component that should be extracted"""
        node_type = node_data.get('type', '')

        # Component types to extract
        extractable_types = [
            'FRAME', 'GROUP', 'COMPONENT', 'COMPONENT_SET',
            'INSTANCE', 'RECTANGLE', 'ELLIPSE', 'VECTOR'
        ]

        # Skip certain node types
        skip_types = ['TEXT', 'LINE', 'SLICE']

        if node_type in skip_types:
            return False

        # Check if node has visual content (fills, strokes, etc.)
        has_visual_content = (
            node_data.get('fills') or
            node_data.get('strokes') or
            node_data.get('background') or
            node_data.get('children')
        )

        return node_type in extractable_types and has_visual_content

    def _process_component_node(self, node_data: Dict, file_key: str) -> Optional[Dict]:
        """Process a single component node"""
        try:
            node_id = node_data.get('id')
            node_name = node_data.get('name', 'Unnamed Component')
            node_type = node_data.get('type', 'UNKNOWN')

            # Sanitize component name for file system
            safe_name = self._sanitize_filename(node_name)

            # Extract component metadata
            metadata = self._extract_component_metadata(node_data)

            # Download component assets (images, vectors)
            asset_paths = self._download_component_assets(node_data, file_key, safe_name)

            # Create component data structure
            component_data = {
                "id": node_id,
                "name": node_name,
                "type": node_type,
                "safe_name": safe_name,
                "metadata": metadata,
                "assets": asset_paths,
                "dimensions": metadata.get('dimensions', {}),
                "styles": metadata.get('styles', {}),
                "extracted_at": datetime.now().isoformat()
            }

            return {
                "component": component_data,
                "metadata": {node_id: component_data}
            }

        except Exception as e:
            print(f"❌ Error processing component {node_data.get('name', 'Unknown')}: {e}")
            return None

    def _extract_component_metadata(self, node_data: Dict) -> Dict[str, Any]:
        """Extract metadata from component node"""
        metadata = {
            "dimensions": {
                "width": node_data.get('absoluteBoundingBox', {}).get('width', 0),
                "height": node_data.get('absoluteBoundingBox', {}).get('height', 0),
                "x": node_data.get('absoluteBoundingBox', {}).get('x', 0),
                "y": node_data.get('absoluteBoundingBox', {}).get('y', 0)
            },
            "styles": {},
            "fills": [],
            "strokes": [],
            "effects": [],
            "constraints": node_data.get('constraints', {}),
            "layout": {
                "layoutMode": node_data.get('layoutMode'),
                "layoutAlign": node_data.get('layoutAlign'),
                "layoutGrow": node_data.get('layoutGrow'),
                "layoutSizingHorizontal": node_data.get('layoutSizingHorizontal'),
                "layoutSizingVertical": node_data.get('layoutSizingVertical')
            }
        }

        # Extract visual styles
        if 'fills' in node_data:
            metadata['fills'] = node_data['fills']

        if 'strokes' in node_data:
            metadata['strokes'] = node_data['strokes']

        if 'effects' in node_data:
            metadata['effects'] = node_data['effects']

        # Extract text styles if it's a text node
        if node_data.get('type') == 'TEXT':
            metadata['text_styles'] = {
                "fontFamily": node_data.get('style', {}).get('fontFamily'),
                "fontSize": node_data.get('style', {}).get('fontSize'),
                "fontWeight": node_data.get('style', {}).get('fontWeight'),
                "letterSpacing": node_data.get('style', {}).get('letterSpacing'),
                "lineHeightPx": node_data.get('style', {}).get('lineHeightPx'),
                "textAlignHorizontal": node_data.get('style', {}).get('textAlignHorizontal'),
                "textAlignVertical": node_data.get('style', {}).get('textAlignVertical')
            }

        return metadata

    def _download_component_assets(self, node_data: Dict, file_key: str, safe_name: str) -> Dict[str, str]:
        """Download component assets (images, vectors)"""
        asset_paths = {}

        try:
            # Check if component has image fills
            if 'fills' in node_data:
                for i, fill in enumerate(node_data['fills']):
                    if fill.get('type') == 'IMAGE' and 'imageRef' in fill:
                        image_ref = fill['imageRef']
                        image_path = self._download_image_asset(file_key, image_ref, f"{safe_name}_fill_{i}")
                        if image_path:
                            asset_paths[f"fill_{i}"] = str(image_path)

            # Export component as image if it's a visual component
            if node_data.get('type') in ['FRAME', 'COMPONENT', 'GROUP']:
                component_image_path = self._export_component_image(file_key, node_data['id'], safe_name)
                if component_image_path:
                    asset_paths['component_image'] = str(component_image_path)

        except Exception as e:
            print(f"⚠️ Error downloading assets for {safe_name}: {e}")

        return asset_paths

    def _download_image_asset(self, file_key: str, image_ref: str, filename: str) -> Optional[Path]:
        """Download a specific image asset"""
        try:
            headers = {"X-Figma-Token": self.api_token}
            params = {"ids": image_ref, "format": "png", "scale": 2}

            response = requests.get(
                f"{self.images_url}/{file_key}",
                headers=headers,
                params=params
            )
            response.raise_for_status()

            image_data = response.json()
            image_url = image_data['images'].get(image_ref)

            if image_url:
                # Download the actual image
                image_response = requests.get(image_url)
                image_response.raise_for_status()

                # Save image
                image_path = self.images_dir / f"{filename}.png"
                with open(image_path, 'wb') as f:
                    f.write(image_response.content)

                return image_path

        except Exception as e:
            print(f"❌ Error downloading image {filename}: {e}")

        return None

    def _export_component_image(self, file_key: str, node_id: str, filename: str) -> Optional[Path]:
        """Export component as PNG image"""
        try:
            headers = {"X-Figma-Token": self.api_token}
            params = {"ids": node_id, "format": "png", "scale": 2}

            response = requests.get(
                f"{self.images_url}/{file_key}",
                headers=headers,
                params=params
            )
            response.raise_for_status()

            image_data = response.json()
            image_url = image_data['images'].get(node_id)

            if image_url:
                # Download the image
                image_response = requests.get(image_url)
                image_response.raise_for_status()

                # Save image
                image_path = self.images_dir / f"{filename}_component.png"
                with open(image_path, 'wb') as f:
                    f.write(image_response.content)

                return image_path

        except Exception as e:
            print(f"❌ Error exporting component image {filename}: {e}")

        return None

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for file system"""
        # Remove or replace invalid characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # Remove leading/trailing whitespace and dots
        sanitized = sanitized.strip(' .')
        # Ensure it's not empty
        return sanitized or "unnamed_component"

    def _save_collection_metadata(self, components: List[Dict], metadata: Dict) -> None:
        """Save collection metadata to file"""
        collection_data = {
            "collection_info": {
                "total_components": len(components),
                "collection_timestamp": datetime.now().isoformat(),
                "output_directory": str(self.output_dir)
            },
            "components": components,
            "component_metadata": metadata
        }

        metadata_file = self.metadata_dir / "collection_manifest.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(collection_data, f, indent=2, ensure_ascii=False)

        print(f"📝 Collection manifest saved to: {metadata_file}")

    def get_component_manifest(self) -> Dict[str, Any]:
        """Get the component collection manifest"""
        manifest_file = self.metadata_dir / "collection_manifest.json"

        if not manifest_file.exists():
            return {"error": "No collection manifest found"}

        try:
            with open(manifest_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            return {"error": f"Failed to load manifest: {e}"}


class ThreadedComponentProcessor:
    """Processes multiple component collections concurrently"""

    def __init__(self, max_concurrent_collections: int = 3):
        self.max_concurrent = max_concurrent_collections
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent_collections)

    def process_multiple_designs(self, design_configs: List[Dict]) -> List[Dict]:
        """Process multiple designs concurrently"""
        print(f"🚀 Starting concurrent processing of {len(design_configs)} designs...")

        results = []

        # Submit all design processing tasks
        future_to_config = {
            self.executor.submit(self._process_single_design, config): config
            for config in design_configs
        }

        # Collect results as they complete
        for future in concurrent.futures.as_completed(future_to_config):
            config = future_to_config[future]
            try:
                result = future.result()
                results.append(result)
                print(f"✅ Completed design: {config.get('name', 'Unknown')}")
            except Exception as exc:
                print(f"❌ Design {config.get('name', 'Unknown')} generated an exception: {exc}")
                results.append({"error": str(exc), "config": config})

        self.executor.shutdown()
        return results

    def _process_single_design(self, config: Dict) -> Dict[str, Any]:
        """Process a single design configuration"""
        file_key = config.get('file_key')
        api_token = config.get('api_token')
        design_name = config.get('name', 'Unknown Design')

        if not file_key or not api_token:
            raise ValueError("Missing file_key or api_token in config")

        # Create collector for this design
        collector = ComponentCollector(api_token=api_token)

        # Fetch design data (simplified - you'd need the actual node data)
        # This is a placeholder - you'd need to integrate with your Figma fetching logic
        nodes_data = []  # This should be populated with actual node data

        # Collect components
        result = collector.collect_components_from_design(file_key, nodes_data)
        result['design_name'] = design_name
        result['config'] = config

        return result


# Example usage and testing
if __name__ == "__main__":
    # Initialize component collector
    collector = ComponentCollector()

    # Example: Process components from design data
    # This would typically be called from your main conversion pipeline

    print("🎨 Component Collection System Ready!")
    print(f"📁 Output directory: {collector.output_dir}")
    print(f"⚡ Max workers: {collector.max_workers}")

    # Test manifest loading
    manifest = collector.get_component_manifest()
    if "error" not in manifest:
        print(f"📋 Loaded collection with {manifest.get('collection_info', {}).get('total_components', 0)} components")
    else:
        print("📋 No existing collection manifest found")