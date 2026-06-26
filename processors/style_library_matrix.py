"""Framework × style_engine × component_library configuration matrix.

The matrix encodes the rules for which combinations are valid, what
dependencies each combination needs, and what file paths the output uses.

It also provides a simple `DependencyResolver` that merges dependency
sources from framework + style engine + library into a deduplicated
`package.json`-shaped dict.

Usage::

    from processors.style_library_matrix import (
        resolve_configuration,
        validate_combination,
        DependencyResolver,
    )

    ok, warnings = validate_combination("react", "tailwind", "shadcn")
    config = resolve_configuration("react", "tailwind", "shadcn")
    deps = DependencyResolver().resolve(framework, style, lib)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from processors.component_library_mapper import get_library_dependencies

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Compatibility tables
# ---------------------------------------------------------------------------

# What `style_engine`s each framework supports.
_FRAMEWORK_SUPPORTED_STYLES: Dict[str, List[str]] = {
    "react": ["css", "tailwind", "scss", "css_modules", "styled"],
    "react_ts": ["css", "tailwind", "scss", "css_modules", "styled"],
    "vue": ["css", "scss"],
    "angular": ["css", "scss"],
    "html": ["css"],
    "html_css_js": ["css"],
    "flutter": ["css"],  # Flutter uses inline theming (no separate CSS engine)
    "nextjs": ["css", "tailwind"],
}

# What `component_library`s each framework supports.
_FRAMEWORK_SUPPORTED_LIBRARIES: Dict[str, List[str]] = {
    "react": ["shadcn", "mui", "antd", "bootstrap"],
    "react_ts": ["shadcn", "mui", "antd", "bootstrap"],
    "vue": ["bootstrap"],
    "angular": [],
    "html": ["bootstrap"],
    "html_css_js": ["bootstrap"],
    "flutter": [],
    "nextjs": [],
}

# Combinations that are technically allowed but flagged with a warning.
# Format: `(framework, style, library)` → warning message.
# (Empty — all unsupported combos are rejected by validate_combination
# before warnings are surfaced.)
_INCOMPATIBLE_COMBINATIONS: List[Dict[str, str]] = []

# Inversely, well-known synergystic combos that work extra cleanly.
# These are surfaced as info messages when chosen together.
_PREFERRED_COMBINATIONS: List[Dict[str, str]] = [
    {
        "framework": "react_ts",
        "style": "tailwind",
        "library": "shadcn",
        "message": "shadcn/ui is built on Tailwind — this is the canonical shadcn setup.",
    },
    {
        "framework": "react_ts",
        "style": "css",
        "library": "mui",
        "message": "MUI emits its own CSS-in-JS via Emotion — no external stylesheet needed.",
    },
    {
        "framework": "react_ts",
        "style": "css",
        "library": "antd",
        "message": "Ant Design v5 uses CSS-in-JS internally — no external stylesheet needed.",
    },
]


# ---------------------------------------------------------------------------
# Style-engine metadata
# ---------------------------------------------------------------------------

_STYLE_ENGINE_DEPS: Dict[str, Dict[str, str]] = {
    # Always-included enging deps — only non-trivial ones.
    "tailwind": {
        # Dev deps — installed by Vite plugin pipeline
        "@tailwindcss/vite": "^4.0.0",
    },
    "scss": {
        "sass": "^1.70.0",
    },
    "css_modules": {},  # Built into Vite/Webpack — no extra deps
    "styled": {
        "styled-components": "^6.1.0",
    },
}

_STYLE_ENGINE_FILES: Dict[str, Dict[str, str]] = {
    "tailwind": {
        "styles_entry": "src/index.css",
        "extra_files": [],
    },
    "scss": {
        "styles_entry": "src/styles.scss",
        "extra_files": [],
    },
    "css_modules": {
        "styles_entry": "src/index.css",
        "extra_files": [],
    },
    "styled": {
        "styles_entry": "src/App.tsx",  # styled is JSX-level
        "extra_files": [],
    },
    "css": {
        "styles_entry": "src/index.css",
        "extra_files": [],
    },
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


@dataclass
class ConfigurationResult:
    """Resolved configuration for a (framework, style, library) triple."""

    framework: str
    style_engine: str
    component_library: str
    valid: bool
    warnings: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)
    paths: Dict[str, str] = field(default_factory=dict)
    dependencies: Dict[str, Dict[str, str]] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "framework": self.framework,
            "style_engine": self.style_engine,
            "component_library": self.component_library,
            "valid": self.valid,
            "warnings": self.warnings,
            "info": self.info,
            "paths": self.paths,
            "dependencies": self.dependencies,
            "error": self.error,
        }


def _normalize(framework: str, style: Optional[str], lib: Optional[str]) -> Tuple[str, str, str]:
    framework = (framework or "react").lower()
    style = (style or "css").lower()
    lib = (lib or "").lower()
    return framework, style, lib


def validate_combination(
    framework: str,
    style_engine: Optional[str] = None,
    component_library: Optional[str] = None,
) -> Tuple[bool, List[str], List[str], Optional[str]]:
    """Validate the combination and return ``(valid, warnings, info, error)``.

    ``error`` is non-None only if ``valid`` is False; ``warnings`` are
    raised for valid but suboptimal pairs.
    """
    framework, style, lib = _normalize(framework, style_engine, component_library)

    error: Optional[str] = None
    warnings: List[str] = []
    info: List[str] = []

    # Framework must always be recognised.
    if framework not in _FRAMEWORK_SUPPORTED_STYLES:
        return False, [], [], f"Unknown framework: {framework!r}"

    # Style engine must be supported by the framework.
    supported_styles = _FRAMEWORK_SUPPORTED_STYLES[framework]
    if style not in supported_styles:
        error = (
            f"Style engine {style!r} is not supported by {framework!r}. "
            f"Supported styles: {supported_styles}"
        )
        return False, [], [], error

    # Component library must be supported by the framework.
    if lib:
        supported_libs = _FRAMEWORK_SUPPORTED_LIBRARIES.get(framework, [])
        if lib not in supported_libs:
            error = (
                f"Component library {lib!r} is not supported by {framework!r}. "
                f"Supported libraries: {supported_libs}"
            )
            return False, [], [], error

    # Walk known-bad combinations.
    for combo in _INCOMPATIBLE_COMBINATIONS:
        if (
            combo["framework"] == framework
            and combo["style"] == style
            and combo.get("library", "") == lib
        ):
            warnings.append(combo["message"])

    # Walk known-good combinations.
    for combo in _PREFERRED_COMBINATIONS:
        if combo["framework"] == framework and combo["style"] == style and combo.get("library", "") == lib:
            info.append(combo["message"])

    return error is None, warnings, info, error


def _resolve_paths(framework: str, style: str) -> Dict[str, str]:
    paths: Dict[str, str] = {}
    framework_styles = _STYLE_ENGINE_FILES.get(style, _STYLE_ENGINE_FILES["css"])
    paths.update(framework_styles)

    if framework in {"html", "html_css_js"}:
        paths["main_entry"] = "index.html"
        paths["scripts"] = "js/main.js"
        paths["styles_entry"] = "css/styles.css"
    return paths


def resolve_configuration(
    framework: str,
    style_engine: Optional[str] = None,
    component_library: Optional[str] = None,
) -> ConfigurationResult:
    """Validate and resolve a (framework, style, library) triple."""
    framework, style, lib = _normalize(framework, style_engine, component_library)
    valid, warnings, info, error = validate_combination(framework, style, lib)

    paths = _resolve_paths(framework, style) if valid else {}
    deps = (
        DependencyResolver(use_cache=False).resolve(framework, style, lib) if valid else {"dependencies": {}, "devDependencies": {}}
    )

    return ConfigurationResult(
        framework=framework,
        style_engine=style,
        component_library=lib,
        valid=valid,
        warnings=warnings,
        info=info,
        paths=paths,
        dependencies=deps,
        error=error,
    )


def list_supported_combinations() -> List[Dict[str, str]]:
    """Return all valid (framework, style, library) triples."""
    combos: List[Dict[str, str]] = []
    for framework, styles in _FRAMEWORK_SUPPORTED_STYLES.items():
        libraries = _FRAMEWORK_SUPPORTED_LIBRARIES.get(framework, [""])
        for style in styles:
            for lib in libraries:
                combos.append(
                    {"framework": framework, "style": style, "library": lib}
                )
    return combos


# ---------------------------------------------------------------------------
# Dependency resolver
# ---------------------------------------------------------------------------

_CORE_DEPS_BY_FRAMEWORK: Dict[str, Dict[str, Dict[str, str]]] = {
    "react": {
        "dependencies": {
            "react": "^18.2.0",
            "react-dom": "^18.2.0",
            "react-router-dom": "^6.20.0",
        },
        "devDependencies": {
            "@vitejs/plugin-react": "^4.2.1",
            "vite": "^5.0.8",
        },
    },
    "react_ts": {
        "dependencies": {
            "react": "^18.2.0",
            "react-dom": "^18.2.0",
            "react-router-dom": "^6.20.0",
        },
        "devDependencies": {
            "@vitejs/plugin-react": "^4.2.1",
            "vite": "^5.0.8",
            "typescript": "^5.3.3",
            "@types/react": "^18.2.43",
            "@types/react-dom": "^18.2.17",
        },
    },
    "vue": {
        "dependencies": {"vue": "^3.2.13", "vue-router": "^4.0.0"},
        "devDependencies": {
            "@vitejs/plugin-vue": "^4.5.0",
            "vite": "^5.0.8",
            "typescript": "^5.3.3",
        },
    },
    "angular": {
        "dependencies": {
            "@angular/animations": "^15.2.0",
            "@angular/common": "^15.2.0",
            "@angular/core": "^15.2.0",
            "@angular/forms": "^15.2.0",
            "@angular/platform-browser": "^15.2.0",
            "@angular/router": "^15.2.0",
            "rxjs": "~7.8.0",
            "tslib": "^2.3.0",
            "zone.js": "~0.12.0",
        },
        "devDependencies": {
            "@angular-devkit/build-angular": "^15.2.0",
            "@angular/cli": "~15.2.0",
            "typescript": "~4.9.4",
        },
    },
    "nextjs": {
        "dependencies": {
            "next": "^14.0.0",
            "react": "^18.2.0",
            "react-dom": "^18.2.0",
        },
        "devDependencies": {"typescript": "^5.3.3"},
    },
    "html": {"dependencies": {}, "devDependencies": {}},
    "html_css_js": {"dependencies": {}, "devDependencies": {}},
    "flutter": {"dependencies": {}, "devDependencies": {}},  # Flutter uses pubspec
}


class DependencyResolver:
    """Collect dependencies from framework + style engine + library.

    Dedupes by package name (the most recent spec wins on conflict) and
    keeps dependencies / devDependencies split according to source.
    """

    def __init__(self, *, use_cache: bool = True):
        self._cache: Dict[Tuple[str, str, str], Dict[str, Dict[str, str]]] = {}
        self._use_cache = use_cache

    # Mockable glob to avoid subclassing for tests
    def _core_deps_for(self, framework: str) -> Dict[str, Dict[str, str]]:
        dep = _CORE_DEPS_BY_FRAMEWORK.get(framework)
        if dep:
            return dep
        log.warning("Unknown framework %s; defaulting to react deps", framework)
        return _CORE_DEPS_BY_FRAMEWORK["react"]

    def _engine_deps_for(self, style: str, lib: str) -> Dict[str, Dict[str, str]]:
        """Style-engine deps — split into deps / devDeps heuristically."""
        merged: Dict[str, Dict[str, str]] = {"dependencies": {}, "devDependencies": {}}
        engine_deps = _STYLE_ENGINE_DEPS.get(style, {})
        # Tailwind tooling is dev; runtime helper deps (clsx, etc.) would be deps.
        merged["devDependencies"].update(engine_deps)

        # shadcn requires Tailwind utility helpers as runtime deps
        if lib == "shadcn":
            merged["dependencies"]["class-variance-authority"] = "^0.7.0"
            merged["dependencies"]["clsx"] = "^2.1.0"
            merged["dependencies"]["tailwind-merge"] = "^2.2.0"
            merged["dependencies"]["lucide-react"] = "^0.344.0"

        return merged

    def _lib_deps_for(self, lib: str) -> Dict[str, Dict[str, str]]:
        if not lib:
            return {"dependencies": {}, "devDependencies": {}}
        # All known libraries place their package as a runtime dep today.
        return {"dependencies": dict(get_library_dependencies(lib)), "devDependencies": {}}

    def resolve(
        self,
        framework: str,
        style_engine: Optional[str] = None,
        component_library: Optional[str] = None,
    ) -> Dict[str, Dict[str, str]]:
        """Return a `package.json`-shaped `{"dependencies": …, "devDependencies": …}` dict."""
        framework, style, lib = _normalize(framework, style_engine, component_library)
        key = (framework, style, lib)
        if self._use_cache and key in self._cache:
            return self._cache[key]

        deps: Dict[str, str] = {}
        dev_deps: Dict[str, str] = {}

        sources = [
            ("core", self._core_deps_for(framework)),
            ("engine", self._engine_deps_for(style, lib)),
            ("library", self._lib_deps_for(lib)),
        ]

        for label, source in sources:
            for k, v in source.get("dependencies", {}).items():
                deps[k] = v  # last write wins — engine/library can override core
            for k, v in source.get("devDependencies", {}).items():
                if k not in dev_deps:
                    dev_deps[k] = v

        result = {"dependencies": deps, "devDependencies": dev_deps}
        if self._use_cache:
            self._cache[key] = result
        return result

    def resolve_to_package_json(
        self,
        framework: str,
        style_engine: Optional[str] = None,
        component_library: Optional[str] = None,
        name: str = "figma-converted-app",
        version: str = "0.1.0",
        private: bool = True,
        scripts: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Construct a full ``package.json`` for the resolved config."""
        deps = self.resolve(framework, style_engine, component_library)

        if scripts is None:
            scripts = _default_scripts_for(framework)

        return {
            "name": name,
            "version": version,
            "private": private,
            "scripts": scripts,
            **deps,
        }


def _default_scripts_for(framework: str) -> Dict[str, str]:
    """Return default ``scripts`` for a framework's package.json."""
    if framework in {"react", "react_ts", "vue", "html_css_js"}:
        return {"dev": "vite", "build": "vite build", "preview": "vite preview"}
    if framework == "nextjs":
        return {"dev": "next dev", "build": "next build", "start": "next start", "lint": "next lint"}
    if framework == "angular":
        return {"ng": "ng", "start": "ng serve", "build": "ng build", "watch": "ng build --watch --configuration development"}
    return {}
