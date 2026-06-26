"""Visual validation of generated code against Figma references.

Takes screenshots of generated HTML via Playwright, downloads Figma frame
references, and computes pixel-match fidelity scores.
"""

from __future__ import annotations

import json
import os
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
import numpy as np
from PIL import Image

DEFAULT_BREAKPOINTS: Dict[str, int] = {
    "desktop": 1440,
    "tablet": 768,
    "mobile": 375,
}

FIGMA_IMAGE_URL = "https://api.figma.com/v1/images/{file_key}"


def _load_image(path: Path) -> Optional[Image.Image]:
    try:
        return Image.open(path).convert("RGBA")
    except Exception:
        return None


def pixel_match_percent(img_a: Image.Image, img_b: Image.Image) -> Tuple[float, Image.Image]:
    """Compare two RGBA images.

    Returns ``(match_percent, diff_heatmap)`` where *match_percent* is
    0–100 and the heatmap highlights differing pixels in red.
    """
    if img_a.size != img_b.size:
        img_b = img_b.resize(img_a.size, Image.LANCZOS)

    arr_a = np.array(img_a, dtype=np.float32)
    arr_b = np.array(img_b, dtype=np.float32)

    diff = np.abs(arr_a - arr_b)
    per_pixel = diff.mean(axis=2)
    max_diff = per_pixel.max()
    if max_diff == 0:
        return 100.0, Image.new("RGBA", img_a.size, (0, 255, 0, 128))

    threshold = 10.0
    matching = (per_pixel < threshold).sum()
    score = round(matching / per_pixel.size * 100, 1)

    normalized = (per_pixel / max_diff * 255).astype(np.uint8)
    h, w = img_a.size[::-1]
    heatmap = np.zeros((h, w, 4), dtype=np.uint8)
    heatmap[..., 0] = 255
    heatmap[..., 3] = normalized
    diff_img = Image.fromarray(heatmap, "RGBA")

    return score, diff_img


class VisualValidator:
    """Screenshots generated HTML and compares against Figma frame references."""

    def __init__(self, figma_token: Optional[str] = None):
        self.figma_token = figma_token or os.getenv("FIGMA_API_TOKEN", "")
        self._http = httpx.Client(
            headers={"X-Figma-Token": self.figma_token} if self.figma_token else {},
            timeout=30,
        )

    def capture_screenshots(
        self, project_dir: Path, breakpoints: Optional[Dict[str, int]] = None
    ) -> Dict[str, Path]:
        """Render *project_dir*'s index.html in Playwright and capture PNGs."""
        from playwright.sync_api import sync_playwright

        bps = breakpoints or DEFAULT_BREAKPOINTS
        index_html = self._find_index_html(project_dir)
        if not index_html:
            return {}

        screenshots: Dict[str, Path] = {}
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(index_html.as_uri(), wait_until="networkidle")

            for name, width in bps.items():
                page.set_viewport_size({"width": width, "height": 900})
                page.wait_for_timeout(500)
                out = project_dir / f"screenshot_{name}.png"
                page.screenshot(path=str(out), full_page=True)
                screenshots[name] = out

            browser.close()

        return screenshots

    def _find_index_html(self, project_dir: Path) -> Optional[Path]:
        for c in (
            project_dir / "index.html",
            project_dir / "public" / "index.html",
        ):
            if c.exists():
                return c
        return None

    def fetch_figma_reference(self, file_key: str, frame_id: str) -> Optional[Image.Image]:
        """Download a Figma frame as a reference PNG."""
        url = FIGMA_IMAGE_URL.format(file_key=file_key)
        try:
            resp = self._http.get(url, params={"ids": frame_id, "format": "png", "scale": "2"})
            resp.raise_for_status()
            data = resp.json()
            image_url = data.get("images", {}).get(frame_id)
            if not image_url:
                return None
            img_resp = self._http.get(image_url)
            img_resp.raise_for_status()
            return Image.open(BytesIO(img_resp.content)).convert("RGBA")
        except Exception:
            return None

    def validate_frame(
        self, file_key: str, frame: Dict[str, Any], rendered_png: Path
    ) -> Dict[str, Any]:
        """Compare a rendered screenshot against the Figma reference."""
        frame_id = frame.get("id", "")
        frame_name = frame.get("name", "")

        reference = self.fetch_figma_reference(file_key, frame_id)
        if reference is None:
            return {"frame_id": frame_id, "frame_name": frame_name, "error": "No Figma reference"}

        rendered = _load_image(rendered_png)
        if rendered is None:
            return {"frame_id": frame_id, "frame_name": frame_name, "error": "No rendered screenshot"}

        score, diff_img = pixel_match_percent(rendered, reference)
        diff_path = rendered_png.with_name(f"diff_{rendered_png.name}")
        diff_img.save(str(diff_path))

        return {
            "frame_id": frame_id,
            "frame_name": frame_name,
            "score": score,
            "diff_path": str(diff_path),
            "rendered_path": str(rendered_png),
        }

    def validate(
        self,
        project_dir: Path,
        file_key: str,
        frames: List[Dict[str, Any]],
        breakpoints: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """Full validation pipeline: screenshot → compare → report."""
        bps = breakpoints or DEFAULT_BREAKPOINTS

        screenshots = self.capture_screenshots(project_dir, bps)
        if not screenshots:
            return {"success": False, "error": "No index.html found in project"}

        frame_results = []
        desktop_png = screenshots.get("desktop")
        for frame in frames:
            if desktop_png and desktop_png.exists():
                frame_results.append(self.validate_frame(file_key, frame, desktop_png))

        scores = [r["score"] for r in frame_results if "score" in r]
        overall = round(sum(scores) / len(scores), 1) if scores else 0.0

        return {
            "success": True,
            "overall_score": overall,
            "frame_results": frame_results,
            "screenshots": {k: str(v) for k, v in screenshots.items()},
            "breakpoints": dict(bps),
        }

    def close(self) -> None:
        self._http.close()
