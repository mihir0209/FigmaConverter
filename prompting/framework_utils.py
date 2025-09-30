"""Framework-specific helper utilities for prompting flows."""

from __future__ import annotations

from typing import Dict, List


_FRAMEWORK_COMPONENT_EXTENSIONS: Dict[str, str] = {
    "react": ".jsx",
    "react_ts": ".tsx",
    "vue": ".vue",
    "angular": ".ts",
    "flutter": ".dart",
    "html": ".html",
    "html_css_js": ".html",
}

_FRAMEWORK_MAIN_FILES: Dict[str, str] = {
    "react": "src/components/{name}.jsx",
    "react_ts": "src/components/{name}.tsx",
    "vue": "src/components/{name}.vue",
    "angular": "src/app/components/{dash_name}/{dash_name}.component.ts",
    "flutter": "lib/screens/{snake_name}.dart",
    "html": "components/{snake_name}.html",
    "html_css_js": "components/{snake_name}.html",
}

_FRAMEWORK_DEFAULT_DEPENDENCIES: Dict[str, List[str]] = {
    "react": ["react", "react-dom", "react-router-dom"],
    "react_ts": ["react", "react-dom", "react-router-dom"],
    "vue": ["vue", "vue-router"],
    "angular": ["@angular/core", "@angular/router"],
    "flutter": ["flutter"],
    "html": [],
    "html_css_js": [],
}

_FRAMEWORK_APP_FILE_PATHS: Dict[str, Dict[str, str]] = {
    "react": {
        "main_app": "src/App.jsx",
        "routing": "src/router.jsx",
        "entry_point": "src/main.jsx",
        "styles": "src/index.css",
    },
    "react_ts": {
        "main_app": "src/App.tsx",
        "routing": "src/router.tsx",
        "entry_point": "src/main.tsx",
        "styles": "src/index.css",
    },
    "vue": {
        "main_app": "src/App.vue",
        "routing": "src/router/index.js",
        "entry_point": "src/main.js",
        "styles": "src/assets/styles/main.css",
    },
    "angular": {
        "main_app": "src/app/app.component.ts",
        "routing": "src/app/app-routing.module.ts",
        "entry_point": "src/main.ts",
        "styles": "src/styles.css",
    },
    "flutter": {
        "main_app": "lib/main.dart",
        "routing": "lib/routes/app_routes.dart",
        "entry_point": "lib/main.dart",
        "styles": "lib/theme/app_theme.dart",
    },
    "html": {
        "main_app": "index.html",
        "routing": "js/router.js",
        "entry_point": "js/main.js",
        "styles": "css/styles.css",
    },
    "html_css_js": {
        "main_app": "index.html",
        "routing": "js/router.js",
        "entry_point": "js/main.js",
        "styles": "css/styles.css",
    },
}


def _normalize_framework(framework: str) -> str:
    return (framework or "react").lower()


def get_component_extension(framework: str) -> str:
    """Return the default component file extension for the framework."""
    normalized = _normalize_framework(framework)
    return _FRAMEWORK_COMPONENT_EXTENSIONS.get(normalized, ".jsx")


def get_default_dependencies(framework: str) -> List[str]:
    """Return default dependency names for the framework."""
    normalized = _normalize_framework(framework)
    return _FRAMEWORK_DEFAULT_DEPENDENCIES.get(normalized, [])


def get_component_file_path(framework: str, component_name: str) -> str:
    """Compute the component file path for a generated component."""
    normalized = _normalize_framework(framework)
    template = _FRAMEWORK_MAIN_FILES.get(normalized, "src/components/{name}.jsx")
    sanitized = component_name.replace(" ", "")
    dash_name = sanitized.lower().replace("_", "-")
    snake_name = sanitized.lower().replace("-", "_")
    return template.format(name=sanitized, dash_name=dash_name, snake_name=snake_name)


def get_app_file_paths(framework: str) -> Dict[str, str]:
    """Return the standard app file paths for the framework."""
    normalized = _normalize_framework(framework)
    return _FRAMEWORK_APP_FILE_PATHS.get(normalized, _FRAMEWORK_APP_FILE_PATHS["react"]).copy()


def format_component_identifier(job_id: str, frame_name: str) -> str:
    """Return the default component identifier used in prompts."""
    cleaned_job = (job_id or "job").replace("-", "")
    cleaned_frame = (frame_name or "Component").replace(" ", "")
    return f"Frame{cleaned_job}_{cleaned_frame}"
