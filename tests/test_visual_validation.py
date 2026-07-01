"""Tests for visual validation (Plan 006)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from processors.visual_validator import (
    DEFAULT_BREAKPOINTS,
    VisualValidator,
    _load_image,
    pixel_match_percent,
)


@pytest.fixture
def white_rgba() -> Image.Image:
    return Image.new("RGBA", (100, 100), (255, 255, 255, 255))


@pytest.fixture
def black_rgba() -> Image.Image:
    return Image.new("RGBA", (100, 100), (0, 0, 0, 255))


class TestPixelMatch:
    def test_identical_images(self, white_rgba: Image.Image):
        score, diff = pixel_match_percent(white_rgba, white_rgba)
        assert score == 100.0

    def test_completely_different(self, white_rgba: Image.Image, black_rgba: Image.Image):
        score, diff = pixel_match_percent(white_rgba, black_rgba)
        assert score < 50.0

    def test_resizes_if_needed(self, white_rgba: Image.Image):
        small = white_rgba.resize((50, 50))
        score, diff = pixel_match_percent(white_rgba, small)
        assert score == 100.0

    def test_diff_output_size(self, white_rgba: Image.Image, black_rgba: Image.Image):
        score, diff = pixel_match_percent(white_rgba, black_rgba)
        assert diff.size == white_rgba.size
        assert diff.mode == "RGBA"

    def test_diff_has_alpha(self, white_rgba: Image.Image, black_rgba: Image.Image):
        score, diff = pixel_match_percent(white_rgba, black_rgba)
        # Different images should produce non-zero alpha in heatmap
        arr = np.array(diff)
        assert arr[..., 3].sum() > 0


class TestValidator:
    def test_capture_no_index_html(self, tmp_path: Path):
        v = VisualValidator(figma_token="test")
        result = v.capture_screenshots(tmp_path)
        assert result == {}

    def test_find_index_html(self, tmp_path: Path):
        index = tmp_path / "index.html"
        index.write_text("<html></html>")
        v = VisualValidator(figma_token="test")
        assert v._find_index_html(tmp_path) == index

    def test_find_public_index_html(self, tmp_path: Path):
        pub = tmp_path / "public"
        pub.mkdir()
        index = pub / "index.html"
        index.write_text("<html></html>")
        v = VisualValidator(figma_token="test")
        assert v._find_index_html(tmp_path) == index

    @patch("processors.visual_validator.VisualValidator.fetch_figma_reference")
    def test_validate_frame_no_reference(self, mock_fetch):
        mock_fetch.return_value = None
        v = VisualValidator(figma_token="test")
        result = v.validate_frame("key", {"id": "f1", "name": "Frame"}, Path("/nonexistent.png"))
        assert "error" in result
        assert result["frame_id"] == "f1"

    def test_close(self):
        v = VisualValidator(figma_token="test")
        v.close()  # should not raise

    def test_pixel_match_percent_edge(self, white_rgba: Image.Image):
        """Edge case: single pixel difference (mostly identical)."""
        base = Image.new("RGBA", (10, 10), (128, 128, 128, 255))
        modified = base.copy()
        modified.putpixel((5, 5), (255, 0, 0, 255))  # one red pixel
        score, diff = pixel_match_percent(base, modified)
        assert 0.0 < score < 100.0


class TestValidateIntegration:
    @patch("processors.visual_validator.VisualValidator.capture_screenshots")
    def test_validate_no_screenshots(self, mock_cap, tmp_path: Path):
        mock_cap.return_value = {}
        v = VisualValidator(figma_token="test")
        result = v.validate(tmp_path, "key", [{"id": "f1"}])
        assert result["success"] is False

    @patch("processors.visual_validator.VisualValidator.capture_screenshots")
    @patch("processors.visual_validator.VisualValidator.validate_frame")
    def test_validate_with_screenshots(self, mock_val, mock_cap, tmp_path: Path):
        png = tmp_path / "screenshot_desktop.png"
        png.write_text("fake")
        mock_cap.return_value = {"desktop": png}
        mock_val.return_value = {"frame_id": "f1", "score": 95.0}
        v = VisualValidator(figma_token="test")
        result = v.validate(tmp_path, "key", [{"id": "f1", "name": "F1"}])
        assert result["success"] is True
        assert result["overall_score"] == 95.0


class TestLoadImage:
    def test_loads_png(self, tmp_path: Path):
        png = tmp_path / "test.png"
        Image.new("RGBA", (10, 10), (255, 0, 0, 255)).save(png)
        img = _load_image(png)
        assert img is not None
        assert img.size == (10, 10)

    def test_returns_none_for_missing(self, tmp_path: Path):
        assert _load_image(tmp_path / "nonexistent.png") is None

    def test_returns_none_for_invalid(self, tmp_path: Path):
        bad = tmp_path / "bad.png"
        bad.write_text("not an image")
        assert _load_image(bad) is None
