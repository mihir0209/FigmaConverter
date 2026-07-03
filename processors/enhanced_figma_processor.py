import asyncio
import json
import httpx
import os
from urllib.parse import urlparse
from typing import Dict, List, Any, Optional, Tuple
import time
from pathlib import Path
import shutil
from datetime import datetime
from dotenv import load_dotenv
import concurrent.futures
import threading
from parsers.enhanced_frame_parser import EnhancedFrameParser

class EnhancedFigmaProcessor:
    """
    Enhanced Figma processor that handles frame-by-frame processing
    and component export with proper referencing
    """

    def __init__(self, api_token: str = None):
        # Load environment variables from .env file
        load_dotenv()

        self.api_token = api_token or os.getenv('FIGMA_API_TOKEN')
        if not self.api_token:
            raise ValueError("FIGMA_API_TOKEN not found in environment variables")

        # Load processing configuration from .env
        self.max_frame_size = int(os.getenv('MAX_FRAME_SIZE', '5000'))
        self.component_export_quality = int(os.getenv('COMPONENT_EXPORT_QUALITY', '2'))
        self.timeout_seconds = int(os.getenv('TIMEOUT_SECONDS', '30'))
        self.output_dir = os.getenv('OUTPUT_DIR', './output')
        self._request_delay = float(os.getenv('FIGMA_REQUEST_DELAY', '0.5'))  # seconds between API calls
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')

        self.headers = {"X-Figma-Token": self.api_token}
        self.base_url = "https://api.figma.com/v1"
        self.images_url = "https://api.figma.com/v1/images"

        # HTTP clients with connection pooling
        self.max_concurrency = int(os.getenv('FIGMA_MAX_CONCURRENCY', '5'))
        self._figma_client = httpx.Client(
            headers=self.headers,
            timeout=httpx.Timeout(self.timeout_seconds),
            limits=httpx.Limits(max_keepalive_connections=self.max_concurrency),
        )
        self._http_client = httpx.Client(
            timeout=httpx.Timeout(self.timeout_seconds),
            limits=httpx.Limits(max_keepalive_connections=self.max_concurrency),
        )
        self._async_figma_client: Optional[httpx.AsyncClient] = None
        self._async_http_client: Optional[httpx.AsyncClient] = None

        # Per-session response cache: url → (timestamp, response_json)
        self._response_cache: Dict[str, Tuple[float, Any]] = {}
        self._cache_ttl = float(os.getenv('FIGMA_CACHE_TTL', '300'))  # 5 minutes

        # Create components directory structure
        self.components_dir = Path("components")
        self.setup_component_structure()
        
        # Initialize enhanced frame parser
        self.frame_parser = EnhancedFrameParser()

    async def _get_async_figma_client(self) -> httpx.AsyncClient:
        if self._async_figma_client is None:
            self._async_figma_client = httpx.AsyncClient(
                headers=self.headers,
                timeout=httpx.Timeout(self.timeout_seconds),
                limits=httpx.Limits(max_keepalive_connections=self.max_concurrency),
            )
        return self._async_figma_client

    async def _get_async_http_client(self) -> httpx.AsyncClient:
        if self._async_http_client is None:
            self._async_http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout_seconds),
                limits=httpx.Limits(max_keepalive_connections=self.max_concurrency),
            )
        return self._async_http_client

    def close(self):
        """Close all HTTP clients and release connections."""
        self._figma_client.close()
        self._http_client.close()

    # ------------------------------------------------------------------ #
    # Retry helpers for Figma API rate limits (HTTP 429)
    # ------------------------------------------------------------------ #

    _RETRY_STATUSES = {429, 502, 503, 504}
    _MAX_RETRIES = 3
    _MAX_RETRY_DELAY = 60.0  # seconds — never wait longer than this
    _BASE_DELAY = 1.0  # seconds

    @staticmethod
    def _parse_retry_after(value: str) -> Optional[float]:
        """Parse ``Retry-After`` header (seconds or HTTP-date)."""
        if not value:
            return None
        # Try plain seconds
        try:
            return float(value)
        except ValueError:
            pass
        # Try HTTP-date (RFC 7231 §7.1.1.1)
        try:
            from email.utils import parsedate_to_datetime
            from datetime import datetime, timezone
            dt = parsedate_to_datetime(value)
            return (dt - datetime.now(timezone.utc)).total_seconds()
        except Exception:
            pass
        return None

    def _log_rate_limit_info(self, response: httpx.Response) -> None:
        """Dump rate-limit headers and response snippet so we can diagnose."""
        rl_remaining = response.headers.get("x-rate-limit-remaining", "?")
        rl_limit = response.headers.get("x-rate-limit-limit", "?")
        rl_reset = response.headers.get("x-rate-limit-reset", "?")
        ra = response.headers.get("retry-after", "?")
        seat_type = response.headers.get("x-figma-rate-limit-type", "?")
        plan_tier = response.headers.get("x-figma-plan-tier", "?")
        upgrade_link = response.headers.get("x-figma-upgrade-link", "")
        body = (response.text or "")[:300]
        print(
            f"🔴 FIGMA 429  "
            f"Limit={rl_limit}  Remaining={rl_remaining}  "
            f"Reset={rl_reset}  Retry-After={ra}\n"
            f"   Seat={seat_type}  Plan={plan_tier}  "
            f"Upgrade={upgrade_link or 'n/a'}\n"
            f"   Response: {body}"
        )
        # Store last rate-limit info for callers to inspect
        self._last_rate_limit = {
            "seat_type": seat_type,
            "plan_tier": plan_tier,
            "upgrade_link": upgrade_link,
            "retry_after": ra,
            "remaining": rl_remaining,
        }

    def get_last_rate_limit_info(self) -> Optional[Dict[str, str]]:
        """Return rate-limit headers from the last 429, or None."""
        return getattr(self, "_last_rate_limit", None)

    def _retry_delay(self, attempt: int, response: httpx.Response) -> float:
        """Compute delay with a hard cap, falling back to exponential backoff."""
        import random

        retry_after = self._parse_retry_after(response.headers.get("retry-after", ""))
        if retry_after is not None and retry_after > 0:
            return min(retry_after, self._MAX_RETRY_DELAY)

        return min(
            self._BASE_DELAY * (2 ** attempt) + random.uniform(0, 1),
            self._MAX_RETRY_DELAY,
        )

    def _cache_get(self, url: str) -> Optional[Any]:
        """Return cached response body if still valid."""
        entry = self._response_cache.get(url)
        if entry:
            ts, data = entry
            if time.monotonic() - ts < self._cache_ttl:
                return data
            del self._response_cache[url]
        return None

    def _cache_put(self, url: str, data: Any) -> None:
        """Store response body in cache."""
        self._response_cache[url] = (time.monotonic(), data)

    def _figma_get(self, url: str, **kwargs) -> httpx.Response:
        """GET with automatic retry on 429/5xx, caching, and proactive delay."""
        # Check cache first
        cached = self._cache_get(url)
        if cached is not None:
            # Return a synthetic 200 response from cache
            resp = httpx.Response(200, json=cached)
            return resp

        for attempt in range(self._MAX_RETRIES + 1):
            response = self._figma_client.get(url, **kwargs)
            if response.status_code not in self._RETRY_STATUSES:
                # Cache successful responses
                try:
                    self._cache_put(url, response.json())
                except Exception:
                    pass
                # Proactive delay to stay under Figma's rate limit
                time.sleep(self._request_delay)
                return response
            self._log_rate_limit_info(response)
            if attempt >= self._MAX_RETRIES:
                return response
            delay = self._retry_delay(attempt, response)
            print(f"⏳ Figma {response.status_code} — retry {attempt+1}/{self._MAX_RETRIES} in {delay:.1f}s")
            time.sleep(delay)
        return response  # unreachable — satisfies type-checker

    async def _async_figma_get(self, url: str, **kwargs) -> httpx.Response:
        """Async GET with automatic retry on 429/5xx, caching, and proactive delay."""
        # Check cache first
        cached = self._cache_get(url)
        if cached is not None:
            resp = httpx.Response(200, json=cached)
            return resp

        client = await self._get_async_figma_client()
        for attempt in range(self._MAX_RETRIES + 1):
            response = await client.get(url, **kwargs)
            if response.status_code not in self._RETRY_STATUSES:
                # Cache successful responses
                try:
                    self._cache_put(url, response.json())
                except Exception:
                    pass
                # Proactive delay to stay under Figma's rate limit
                await asyncio.sleep(self._request_delay)
                return response
            self._log_rate_limit_info(response)
            if attempt >= self._MAX_RETRIES:
                return response
            delay = self._retry_delay(attempt, response)
            print(f"⏳ Figma {response.status_code} — retry {attempt+1}/{self._MAX_RETRIES} in {delay:.1f}s")
            await asyncio.sleep(delay)
        return response

    def setup_component_structure(self):
        """Create the component directory structure"""
        # Main components directory
        self.components_dir.mkdir(exist_ok=True)

        # Subdirectories for different file types
        subdirs = ['images', 'videos', 'vectors', 'icons', 'fonts']
        for subdir in subdirs:
            (self.components_dir / subdir).mkdir(exist_ok=True)

        # Metadata directory
        (self.components_dir / 'metadata').mkdir(exist_ok=True)

    def extract_file_key_from_url(self, figma_url: str) -> Optional[str]:
        """Extract file key from various Figma URL formats"""
        try:
            from validation import validate_figma_url

            # Delegate to the shared validator so both the HTTP layer and the
            # processor agree on what counts as a valid Figma URL.
            return validate_figma_url(figma_url)
        except Exception as exc:
            print(f"Error extracting file key: {exc}")
            return None

    def fetch_design_data(self, file_key: str) -> Optional[Dict]:
        """Fetch complete design data from Figma API"""
        url = f"{self.base_url}/files/{file_key}"

        try:
            print(f"🌐 Fetching design data for file: {file_key}")
            response = self._figma_get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            print(f"❌ Error fetching design data: {e}")
            return None

    async def _async_fetch_design_data(self, file_key: str) -> Optional[Dict]:
        url = f"{self.base_url}/files/{file_key}"
        try:
            response = await self._async_figma_get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                rl_info = self.get_last_rate_limit_info() or {}
                seat = rl_info.get("seat_type", "unknown")
                upgrade = rl_info.get("upgrade_link", "")
                if seat == "low":
                    raise ValueError(
                        "Figma API rate limit: your token is from a View/Collab seat "
                        "(6 requests/month). Upgrade to a Dev or Full seat (free on Starter plan) "
                        "to get 10 requests/minute. "
                        f"{'Upgrade: ' + upgrade if upgrade else ''}"
                    ) from e
                raise ValueError(
                    f"Figma API rate limit exceeded. "
                    f"Seat={seat}, Upgrade={upgrade or 'n/a'}. "
                    f"Try again later or reduce the number of frames/components."
                ) from e
            print(f"❌ Error fetching design data: {e}")
            return None
        except httpx.HTTPError as e:
            print(f"❌ Error fetching design data: {e}")
            return None

    def fetch_figma_variables(self, file_key: str) -> Optional[Dict]:
        """Fetch Figma Variables (design tokens) for a file.

        Hits ``GET /v1/files/{file_key}/variables/local``. Returns None if the
        endpoint isn't available (older Figma plans don't support variables),
        the file has no variables, or the request fails — so callers can treat
        a None result as "fall back to hardcoded extraction".
        """
        url = f"{self.base_url}/files/{file_key}/variables/local"
        try:
            print(f"📐 Fetching Figma variables for file: {file_key}")
            response = self._figma_get(url)
            if response.status_code == 404:
                print("   ℹ️ Variables endpoint unavailable; will fall back to extraction.")
                return None
            response.raise_for_status()
            payload = response.json()
            # Empty / absent variables both mean "nothing to extract"
            if not (payload.get("variables") or payload.get("meta", {}).get("variables")):
                return None
            return payload
        except httpx.HTTPError as e:
            print(f"⚠️ Could not fetch variables: {e}")
            return None

    async def _async_fetch_figma_variables(self, file_key: str) -> Optional[Dict]:
        url = f"{self.base_url}/files/{file_key}/variables/local"
        try:
            response = await self._async_figma_get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            payload = response.json()
            if not (payload.get("variables") or payload.get("meta", {}).get("variables")):
                return None
            return payload
        except httpx.HTTPError:
            return None

    def identify_frames(self, design_data: Dict) -> List[Dict]:
        """Identify and extract all frames from the design"""
        frames = []

        if not design_data or 'document' not in design_data:
            return frames

        document = design_data['document']
        pages = document.get('children', [])

        for page in pages:
            if page.get('type') != 'CANVAS':
                continue

            page_children = page.get('children', [])
            page_frames = [child for child in page_children if child.get('type') == 'FRAME']

            for frame in page_frames:
                frame_info = {
                    'id': frame.get('id'),
                    'name': frame.get('name'),
                    'page_name': page.get('name'),
                    'page_id': page.get('id'),
                    'dimensions': self.extract_dimensions(frame),
                    'children': frame.get('children', []),
                    'background_color': frame.get('backgroundColor'),
                    'export_settings': frame.get('exportSettings', [])
                }
                frames.append(frame_info)

        print(f"📋 Identified {len(frames)} frames in the design")
        return frames

    def extract_dimensions(self, element: Dict) -> Dict:
        """Extract dimensions from Figma element"""
        if 'absoluteBoundingBox' in element:
            bbox = element['absoluteBoundingBox']
            return {
                'width': bbox.get('width', 0),
                'height': bbox.get('height', 0),
                'x': bbox.get('x', 0),
                'y': bbox.get('y', 0)
            }
        return {'width': 0, 'height': 0, 'x': 0, 'y': 0}

    def extract_components_from_frame(self, frame: Dict) -> List[Dict]:
        """Extract all components (images, vectors, etc.) from a frame"""
        components = []

        def traverse_element(element: Dict, parent_path: str = ""):
            element_type = element.get('type', '')
            element_id = element.get('id', '')
            element_name = element.get('name', '')

            # Handle different component types
            if element_type == 'RECTANGLE' and 'fills' in element:
                # Check for image fills
                for fill in element.get('fills', []):
                    if fill.get('type') == 'IMAGE' and 'imageRef' in fill:
                        component = {
                            'id': element_id,  # Use node ID instead of imageRef
                            'name': element_name,
                            'type': 'image',
                            'image_ref': fill['imageRef'],  # Keep for reference
                            'dimensions': self.extract_dimensions(element),
                            'frame_id': frame['id'],
                            'frame_name': frame['name']
                        }
                        components.append(component)

            elif element_type == 'VECTOR':
                # Vector graphics
                component = {
                    'id': element_id,
                    'name': element_name,
                    'type': 'vector',
                    'dimensions': self.extract_dimensions(element),
                    'frame_id': frame['id'],
                    'frame_name': frame['name']
                }
                components.append(component)

            # Recursively traverse children
            if 'children' in element:
                current_path = f"{parent_path}/{element_name}" if parent_path else element_name
                for child in element['children']:
                    traverse_element(child, current_path)

        # Start traversal from frame children
        for child in frame.get('children', []):
            traverse_element(child)

        return components

    def export_component_images(self, file_key: str, components: List[Dict]) -> Dict[str, str]:
        """Export component images from Figma and save to components folder"""
        component_references = {}

        if not components:
            return component_references

        print(f"📥 Exporting {len(components)} components...")

        # Group components by type for batch processing
        image_components = [c for c in components if c['type'] == 'image']
        vector_components = [c for c in components if c['type'] == 'vector']

        # Export images
        if image_components:
            # Use node IDs for API calls, not image refs
            node_ids = list(set([c['id'] for c in image_components]))
            exported_images = self._export_images_batch(file_key, node_ids)

            for component in image_components:
                node_id = component['id']
                if node_id in exported_images:
                    # Save image to components folder
                    local_path = self._save_component_file(
                        exported_images[node_id],
                        component,
                        'images',
                        'png'
                    )
                    if local_path:
                        component_references[component['id']] = {
                            'type': 'image',
                            'path': local_path,
                            'original_name': component['name'],
                            'dimensions': component['dimensions'],
                            'image_ref': component['image_ref']  # Keep for reference
                        }

        # Export vectors (as SVG)
        if vector_components:
            for component in vector_components:
                # For vectors, we'll use Figma's export API
                vector_url = self._get_vector_export_url(file_key, component['id'])
                if vector_url:
                    local_path = self._save_component_file(
                        vector_url,
                        component,
                        'vectors',
                        'svg'
                    )
                    if local_path:
                        component_references[component['id']] = {
                            'type': 'vector',
                            'path': local_path,
                            'original_name': component['name'],
                            'dimensions': component['dimensions']
                        }

        print(f"✅ Exported {len(component_references)} components successfully")
        return component_references

    def _export_images_batch(self, file_key: str, node_ids: List[str]) -> Dict[str, str]:
        """Export multiple images in batch from Figma using node IDs"""
        exported_images = {}

        batch_size = 50
        for i in range(0, len(node_ids), batch_size):
            batch_ids = node_ids[i:i + batch_size]

            params = {
                'ids': ','.join(batch_ids),
                'format': 'png',
                'scale': str(self.component_export_quality)
            }

            try:
                response = self._figma_get(
                    f"{self.images_url}/{file_key}",
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

                if 'images' in data:
                    exported_images.update(data['images'])

            except httpx.HTTPError as e:
                print(f"❌ Error exporting image batch: {e}")

        return exported_images

    async def _async_export_images_batch(self, file_key: str, node_ids: List[str]) -> Dict[str, str]:
        exported_images = {}
        batch_size = 50
        for i in range(0, len(node_ids), batch_size):
            batch_ids = node_ids[i:i + batch_size]
            params = {
                'ids': ','.join(batch_ids),
                'format': 'png',
                'scale': str(self.component_export_quality)
            }
            try:
                response = await self._async_figma_get(f"{self.images_url}/{file_key}", params=params)
                response.raise_for_status()
                data = response.json()
                if 'images' in data:
                    exported_images.update(data['images'])
            except httpx.HTTPError as e:
                print(f"❌ Error exporting image batch: {e}")
        return exported_images

    def export_frame_screenshots(self, file_key: str, frames: List[Dict[str, Any]], scale: float = 2.0) -> Dict[str, str]:
        """Export full-frame screenshots for vision input.
        
        Args:
            file_key: Figma file key
            frames: List of frame dicts with 'id' and 'name' keys
            scale: Export scale (1.0, 2.0, or 3.0)
            
        Returns:
            Dict mapping frame_id to local file path
        """
        frame_screenshots = {}
        node_ids = [frame.get("id") for frame in frames if frame.get("id")]
        
        if not node_ids:
            return frame_screenshots
            
        batch_size = 50
        for i in range(0, len(node_ids), batch_size):
            batch_ids = node_ids[i:i + batch_size]
            params = {
                'ids': ','.join(batch_ids),
                'format': 'png',
                'scale': str(scale)
            }
            
            try:
                response = self._figma_get(
                    f"{self.images_url}/{file_key}",
                    params=params,
                )
                response.raise_for_status()
                data = response.json()
                
                if 'images' in data:
                    import urllib.request
                    import tempfile
                    import os
                    
                    for node_id, image_url in data['images'].items():
                        if image_url:
                            # Download to temp file
                            temp_dir = tempfile.mkdtemp(prefix="figma_vision_")
                            local_path = os.path.join(temp_dir, f"{node_id}.png")
                            urllib.request.urlretrieve(image_url, local_path)
                            frame_screenshots[node_id] = local_path
                            
            except Exception as e:
                print(f"❌ Error exporting frame screenshots: {e}")
                
        return frame_screenshots

    def _get_vector_export_url(self, file_key: str, node_id: str) -> Optional[str]:
        """Get export URL for vector graphics"""
        try:
            params = {'ids': node_id, 'format': 'svg'}
            response = self._figma_get(
                f"{self.images_url}/{file_key}",
                params=params,
            )
            response.raise_for_status()
            data = response.json()
            if 'images' in data and node_id in data['images']:
                return data['images'][node_id]
        except httpx.HTTPError as e:
            print(f"❌ Error getting vector export URL: {e}")
        return None

    async def _async_get_vector_export_url(self, file_key: str, node_id: str) -> Optional[str]:
        try:
            params = {'ids': node_id, 'format': 'svg'}
            response = await self._async_figma_get(f"{self.images_url}/{file_key}", params=params)
            response.raise_for_status()
            data = response.json()
            if 'images' in data and node_id in data['images']:
                return data['images'][node_id]
        except httpx.HTTPError:
            pass
        return None

    def _save_component_file(self, url: str, component: Dict, subdir: str, extension: str) -> Optional[str]:
        """Save component file to the components folder"""
        try:
            clean_name = self._generate_component_filename(component, extension)
            file_path = self.components_dir / subdir / clean_name

            response = self._http_client.get(url)
            response.raise_for_status()

            with open(file_path, 'wb') as f:
                f.write(response.content)

            return f"components/{subdir}/{clean_name}"

        except Exception as e:
            print(f"❌ Error saving component {component['id']}: {e}")
            return None

    async def _async_save_component_file(self, url: str, component: Dict, subdir: str, extension: str) -> Optional[str]:
        client = await self._get_async_http_client()
        try:
            clean_name = self._generate_component_filename(component, extension)
            file_path = self.components_dir / subdir / clean_name
            response = await client.get(url)
            response.raise_for_status()
            with open(file_path, 'wb') as f:
                f.write(response.content)
            return f"components/{subdir}/{clean_name}"
        except Exception as e:
            print(f"❌ Error saving component {component['id']}: {e}")
            return None

    def _generate_component_filename(self, component: Dict, extension: str) -> str:
        """Generate a clean, unique filename for component"""
        # Clean the component name
        name = component.get('name', 'component').replace(' ', '_').replace('/', '_')

        # Add frame info for uniqueness
        frame_name = component.get('frame_name', 'unknown').replace(' ', '_')
        component_id = component['id'].split(':')[-1]  # Get last part of ID

        # Format: frameName_componentName_componentID.ext
        filename = f"{frame_name}_{name}_{component_id}.{extension}"

        # Ensure filename is not too long
        if len(filename) > 100:
            filename = f"{frame_name}_{component_id}.{extension}"

        return filename

    def extract_comprehensive_frame_data(self, frame: Dict, design_data: Dict = None) -> Dict[str, Any]:
        """
        Extract comprehensive frame data using the enhanced parser
        """
        return self.frame_parser.parse_frame_comprehensive(frame, design_data)

    def process_frame_by_frame(self, figma_url: str, include_components: bool = True) -> Dict[str, Any]:
        """Main method to process Figma design frame by frame with parallel processing"""
        print("🚀 Starting frame-by-frame Figma processing...")

        # Extract file key
        file_key = self.extract_file_key_from_url(figma_url)
        if not file_key:
            raise ValueError("Could not extract file key from URL")

        print(f"📋 File Key: {file_key}")

        # Fetch design data
        design_data = self.fetch_design_data(file_key)
        if not design_data:
            raise ValueError("Could not fetch design data")

        # Identify all frames
        frames = self.identify_frames(design_data)
        print(f"📊 Found {len(frames)} frames to process")

        # Process frames in parallel batches
        processed_frames, all_component_references = self._process_frames_parallel(frames, file_key, include_components, design_data)

        # Save component manifest only if components were collected
        if include_components:
            self._save_component_manifest(all_component_references)

        # Try to fetch Figma Variables (design tokens). Best-effort — None
        # means "fall back to extracting tokens from the parsed frames".
        figma_variables = self.fetch_figma_variables(file_key)

        # Inject file_key into each frame so callers (e.g. AI cache) can
        # build per-frame cache keys without passing figma_url around.
        for f in processed_frames:
            f["_file_key"] = file_key

        # Create final result
        result = {
            'design_info': {
                'file_key': file_key,
                'file_name': design_data.get('name', 'Unknown'),
                'total_frames': len(frames),
                'total_components': len(all_component_references),
                'processed_at': datetime.now().isoformat()
            },
            'frames': processed_frames,
            'component_references': all_component_references,
            'component_manifest_path': str(self.components_dir / 'metadata' / 'manifest.json'),
            'design_tokens': figma_variables,  # may be None
        }

        print("✅ Frame-by-frame processing completed!")
        print(f"📊 Processed {len(frames)} frames with {len(all_component_references)} components")

        return result

    async def async_process_frame_by_frame(self, figma_url: str, include_components: bool = True) -> Dict[str, Any]:
        """Async version of process_frame_by_frame with async HTTP and asyncio.gather."""
        print("🚀 Starting async frame-by-frame Figma processing...")

        file_key = self.extract_file_key_from_url(figma_url)
        if not file_key:
            raise ValueError("Could not extract file key from URL")

        print(f"📋 File Key: {file_key}")

        design_data = await self._async_fetch_design_data(file_key)
        if not design_data:
            raise ValueError("Could not fetch design data")

        frames = self.identify_frames(design_data)
        print(f"📊 Found {len(frames)} frames to process")

        processed_frames, all_component_references = await self._async_process_frames_parallel(
            frames, file_key, include_components, design_data
        )

        if include_components:
            self._save_component_manifest(all_component_references)

        figma_variables = await self._async_fetch_figma_variables(file_key)

        for f in processed_frames:
            f["_file_key"] = file_key

        result = {
            'design_info': {
                'file_key': file_key,
                'file_name': design_data.get('name', 'Unknown'),
                'total_frames': len(frames),
                'total_components': len(all_component_references),
                'processed_at': datetime.now().isoformat()
            },
            'frames': processed_frames,
            'component_references': all_component_references,
            'component_manifest_path': str(self.components_dir / 'metadata' / 'manifest.json'),
            'design_tokens': figma_variables,
        }

        print("✅ Async frame-by-frame processing completed!")
        return result

    async def _async_process_frames_parallel(self, frames: List[Dict], file_key: str, include_components: bool, design_data: Dict = None) -> Tuple[List[Dict], Dict[str, Dict]]:
        """Process frames in parallel using asyncio.gather."""
        sem = asyncio.Semaphore(self.max_concurrency)

        async def _run_one(frame: Dict, idx: int) -> Optional[Dict]:
            async with sem:
                return await asyncio.to_thread(
                    self._process_single_frame, frame, file_key, idx, include_components, design_data
                )

        results = await asyncio.gather(
            *[_run_one(frame, i) for i, frame in enumerate(frames)],
            return_exceptions=True,
        )

        processed_frames = []
        all_component_references = {}
        for frame, result in zip(frames, results):
            if isinstance(result, Exception):
                print(f"❌ Frame {frame['name']} failed: {result}")
                continue
            if result:
                processed_frames.append(result['summary'])
                all_component_references.update(result['component_refs'])
                print(f"✅ Completed frame: {frame['name']}")
            else:
                print(f"⚠️ Failed to process frame: {frame['name']}")

        return processed_frames, all_component_references

    def _process_frames_parallel(self, frames: List[Dict], file_key: str, include_components: bool, design_data: Dict = None) -> Tuple[List[Dict], Dict[str, Dict]]:
        """Process frames in parallel using threading with batching"""
        processed_frames = []
        all_component_references = {}

        # Use exactly 8 threads maximum, one frame per thread
        total_frames = len(frames)
        max_workers = min(8, total_frames)  # Max 8 threads, or total frames if less

        print(f"⚡ Using {max_workers} threads - one frame per thread")

        # Process frames in parallel - one frame per thread
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all frame processing tasks
            future_to_frame = {
                executor.submit(self._process_single_frame, frame, file_key, i, include_components, design_data): frame
                for i, frame in enumerate(frames)
            }

            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_frame):
                frame = future_to_frame[future]
                try:
                    result = future.result()
                    if result:
                        processed_frames.append(result['summary'])
                        all_component_references.update(result['component_refs'])
                        print(f"✅ Completed frame: {frame['name']}")
                    else:
                        print(f"⚠️ Failed to process frame: {frame['name']}")
                except Exception as exc:
                    print(f"❌ Frame {frame['name']} generated an exception: {exc}")

        return processed_frames, all_component_references

    def _process_single_frame(self, frame: Dict, file_key: str, frame_index: int, include_components: bool, design_data: Dict = None) -> Optional[Dict]:
        """Process a single frame and return its results with comprehensive data"""
        try:
            frame_name = frame['name']
            print(f"🔄 Processing frame {frame_index + 1}: {frame_name}")

            # Extract comprehensive frame data using enhanced parser
            comprehensive_data = self.extract_comprehensive_frame_data(frame, design_data)
            print(f"   📊 Extracted {comprehensive_data['component_count']['total']} components")
            print(f"   📝 Found {len(comprehensive_data['content']['texts'])} text elements")
            print(f"   🎨 Found {len(comprehensive_data['design_system']['colors'])} colors")

            # Extract components from this frame (for backward compatibility)
            frame_components = self.extract_components_from_frame(frame)

            # Export components and get references only if requested
            frame_component_refs = {}
            if include_components:
                frame_component_refs = self.export_component_images(file_key, frame_components)

            # Create enhanced frame summary with comprehensive data
            frame_summary = {
                'id': frame['id'],
                'name': frame_name,
                'page_name': frame.get('page_name', 'Unknown'),
                'dimensions': comprehensive_data['basic_info']['dimensions'],
                'component_count': comprehensive_data['component_count']['total'],
                'component_references': frame_component_refs,
                'comprehensive_data': comprehensive_data,  # This is the rich data for AI
                'legacy_element_summary': self._analyze_frame_elements(frame)  # Keep for compatibility
            }

            return {
                'summary': frame_summary,
                'component_refs': frame_component_refs
            }

        except Exception as e:
            print(f"❌ Error processing frame {frame['name']}: {e}")
            return None

    def _analyze_frame_elements(self, frame: Dict) -> Dict[str, int]:
        """Analyze elements in a frame for summary"""
        elements = frame.get('children', [])
        summary = {
            'total_elements': len(elements),
            'text_elements': 0,
            'image_elements': 0,
            'vector_elements': 0,
            'group_elements': 0,
            'rectangle_elements': 0
        }

        def count_elements(element_list):
            for element in element_list:
                element_type = element.get('type', '')
                if element_type == 'TEXT':
                    summary['text_elements'] += 1
                elif element_type == 'RECTANGLE':
                    summary['rectangle_elements'] += 1
                    # Check if it has image fills
                    if 'fills' in element:
                        for fill in element['fills']:
                            if fill.get('type') == 'IMAGE':
                                summary['image_elements'] += 1
                                break
                elif element_type == 'VECTOR':
                    summary['vector_elements'] += 1
                elif element_type == 'GROUP':
                    summary['group_elements'] += 1

                # Recursively count children
                if 'children' in element:
                    count_elements(element['children'])

        count_elements(elements)
        return summary

    def _save_component_manifest(self, component_references: Dict) -> None:
        """Save component manifest for reference"""
        manifest = {
            'generated_at': datetime.now().isoformat(),
            'total_components': len(component_references),
            'components': component_references
        }

        manifest_path = self.components_dir / 'metadata' / 'manifest.json'
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        print(f"📝 Component manifest saved to: {manifest_path}")

    def get_component_reference_for_ai(self, component_id: str) -> Optional[Dict]:
        """Get component reference formatted for AI prompts"""
        manifest_path = self.components_dir / 'metadata' / 'manifest.json'

        if not manifest_path.exists():
            return None

        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)

            if component_id in manifest.get('components', {}):
                component = manifest['components'][component_id]
                return {
                    'id': component_id,
                    'type': component['type'],
                    'path': component['path'],
                    'name': component['original_name'],
                    'width': component['dimensions']['width'],
                    'height': component['dimensions']['height']
                }
        except Exception as e:
            print(f"❌ Error reading component manifest: {e}")

        return None


# Example usage
if __name__ == "__main__":
    # Initialize processor
    processor = EnhancedFigmaProcessor()
    FIGMA_URL = "https://www.figma.com/file/your_file_key_here"
    try:
        # Process design frame by frame
        result = processor.process_frame_by_frame(FIGMA_URL)

        # Save processing result
        with open('frame_processing_result.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print("💾 Processing result saved to: frame_processing_result.json")
        # Example: Get component reference for AI
        if result['frames']:
            first_frame = result['frames'][0]
            if first_frame['component_references']:
                component_id = list(first_frame['component_references'].keys())[0]
                ai_ref = processor.get_component_reference_for_ai(component_id)
                if ai_ref:
                    print(f"🤖 AI Component Reference: {ai_ref}")

    except Exception as e:
        print(f"❌ Processing failed: {e}")
