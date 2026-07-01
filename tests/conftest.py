"""Shared pytest fixtures for FigmaConverter tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def sample_frame_node() -> dict:
    """A minimal Figma frame payload."""

    return {
        "id": "0:1",
        "name": "Sign Up",
        "type": "FRAME",
        "layoutMode": "VERTICAL",
        "paddingLeft": 12,
        "paddingRight": 16,
        "paddingTop": 8,
        "paddingBottom": 24,
        "itemSpacing": 14,
        "absoluteBoundingBox": {"x": 0, "y": 0, "width": 375, "height": 812},
        "backgroundColor": {"r": 1, "g": 1, "b": 1, "a": 1},
        "children": [
            {
                "id": "0:2",
                "name": "EmailLabel",
                "type": "TEXT",
                "characters": "Email",
                "style": {"fontFamily": "Inter", "fontSize": 14, "fontWeight": 500},
                "fills": [],
                "absoluteBoundingBox": {"x": 16, "y": 100, "width": 50, "height": 18},
            },
            {
                "id": "0:3",
                "name": "SubmitButton",
                "type": "RECTANGLE",
                "fills": [
                    {
                        "type": "SOLID",
                        "color": {"r": 0.39, "g": 0.4, "b": 0.95, "a": 1},
                    }
                ],
                "absoluteBoundingBox": {"x": 16, "y": 250, "width": 343, "height": 48},
            },
            {
                "id": "0:4",
                "name": "LoginLinkButton",
                "type": "RECTANGLE",
                "fills": [],
                "absoluteBoundingBox": {"x": 16, "y": 320, "width": 60, "height": 20},
            },
        ],
    }


@pytest.fixture
def sample_response_success() -> dict:
    """A canonical success-shaped AI response used by parser tests."""

    return {
        "component_name": "Frame",
        "content": "export default function Frame() { return <div>Hello</div>; }",
        "dependencies": {"required": ["react"], "additional_suggestions": [], "reasoning": ""},
        "file_path": "src/components/Frame.jsx",
    }


@pytest.fixture
def tmp_samples_dir(tmp_path: Path) -> Path:
    path = tmp_path / "components"
    path.mkdir()
    return path


@pytest.fixture
def figma_url() -> str:
    return "https://www.figma.com/design/ABCxyz1234567890abcdef/Sample-Design"
