"""
Framework Template Scaffolder

Downloads official project starter templates from framework sources (GitHub,
npm, etc.) and overlays AI-generated code on top. This replaces the previous
approach of generating config files inline.

Supported sources:
- GitHub archive downloads (most frameworks)
- npm create / npx commands (when Node.js is available)
- Flutter create (when Flutter SDK is available)
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

TEMPLATES_CACHE_DIR = Path("data") / "templates"

# Session-level cache: avoids re-downloading the same template within one process
_TEMPLATE_CACHE: Dict[str, Path] = {}

# Official template sources per framework.
# Structure: {
#     "framework_name": {
#         "github": (owner, repo, subdir, ref),  # for git archive
#         "description": "...",
#         "requires": ["node", "npm"],            # tools needed for scaffolding
#     }
# }
#
# Templates are downloaded as lightweight zip archives (no node_modules).

FRAMEWORK_TEMPLATES: Dict[str, Dict] = {
    "react": {
        "github": ("vitejs", "vite", "packages/create-vite/template-react", "main"),
        "description": "Vite + React starter (official)",
        "post_scaffold": ["npm", "install"],
        "requires": ["node", "npm"],
    },
    "react_ts": {
        "github": ("vitejs", "vite", "packages/create-vite/template-react-ts", "main"),
        "description": "Vite + React + TypeScript starter (official)",
        "post_scaffold": ["npm", "install"],
        "requires": ["node", "npm"],
    },
    "vue": {
        "github": ("vitejs", "vite", "packages/create-vite/template-vue", "main"),
        "description": "Vite + Vue 3 starter (official)",
        "post_scaffold": ["npm", "install"],
        "requires": ["node", "npm"],
    },
    "html_css_js": {
        "github": ("vitejs", "vite", "packages/create-vite/template-vanilla", "main"),
        "description": "Vite + vanilla JS starter (official)",
        "post_scaffold": ["npm", "install"],
        "requires": ["node", "npm"],
    },
    "nextjs": {
        "github": ("vercel", "next.js", "examples/hello-world", "canary"),
        "description": "Next.js hello-world example (official)",
        "post_scaffold": ["npm", "install"],
        "requires": ["node", "npm"],
    },
}

# For frameworks without an official GitHub archive, we define a minimal
# scaffold manually. These match the output of `flutter create` / `ng new`.
MANUAL_SCAFFOLDS: Dict[str, List[Dict]] = {
    "flutter": [
        {"path": "pubspec.yaml", "content": "name: figma_converted_app\ndescription: A Flutter project converted from Figma.\n\nenvironment:\n  sdk: '>=3.0.0 <4.0.0'\n\ndependencies:\n  flutter:\n    sdk: flutter\n"},
        {"path": "lib/main.dart", "content": "import 'package:flutter/material.dart';\n\nvoid main() {\n  runApp(const MyApp());\n}\n\nclass MyApp extends StatelessWidget {\n  const MyApp({super.key});\n\n  @override\n  Widget build(BuildContext context) {\n    return MaterialApp(\n      title: 'Figma Converted',\n      home: const MyHomePage(),\n    );\n  }\n}\n\nclass MyHomePage extends StatelessWidget {\n  const MyHomePage({super.key});\n\n  @override\n  Widget build(BuildContext context) {\n    return Scaffold(\n      appBar: AppBar(title: const Text('Figma Converted')),\n      body: const Center(child: Text('Replace with generated code')),\n    );\n  }\n}\n"},
        {"path": "analysis_options.yaml", "content": "analyzer:\n  errors:\n    unused_import: warning\n\nlinter:\n  rules:\n    - prefer_const_constructors\n"},
        {"path": ".gitignore", "content": "*.iml\n.idea/\n.dart_tool/\n.packages\n.pub/\nbuild/\n.flutter-plugins\n.flutter-plugins.dependencies\n"},
    ],
    "angular": [
        {"path": "angular.json", "content": "{\n  \"$schema\": \"./node_modules/@angular/cli/lib/config/schema.json\",\n  \"version\": 1,\n  \"newProjectRoot\": \"projects\",\n  \"projects\": {\n    \"figma-converted-app\": {\n      \"projectType\": \"application\",\n      \"root\": \"\",\n      \"sourceRoot\": \"src\",\n      \"prefix\": \"app\",\n      \"architect\": {\n        \"build\": {\n          \"builder\": \"@angular-devkit/build-angular:browser\",\n          \"options\": {\n            \"outputPath\": \"dist\",\n            \"index\": \"src/index.html\",\n            \"main\": \"src/main.ts\",\n            \"polyfills\": [\"zone.js\"]\n          }\n        }\n      }\n    }\n  }\n}\n"},
        {"path": "src/index.html", "content": "<!doctype html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"utf-8\">\n  <base href=\"/\">\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n  <title>FigmaConvertedApp</title>\n</head>\n<body>\n  <app-root></app-root>\n</body>\n</html>\n"},
        {"path": "src/main.ts", "content": "import { platformBrowserDynamic } from '@angular/platform-browser-dynamic';\nimport { AppModule } from './app/app.module';\n\nplatformBrowserDynamic().bootstrapModule(AppModule)\n  .catch(err => console.error(err));\n"},
        {"path": "src/app/app.module.ts", "content": "import { NgModule } from '@angular/core';\nimport { BrowserModule } from '@angular/platform-browser';\nimport { AppComponent } from './app.component';\n\n@NgModule({\n  declarations: [AppComponent],\n  imports: [BrowserModule],\n  providers: [],\n  bootstrap: [AppComponent],\n})\nexport class AppModule {}\n"},
        {"path": "src/app/app.component.ts", "content": "import { Component } from '@angular/core';\n\n@Component({\n  selector: 'app-root',\n  template: '<p>Replace with generated code</p>',\n})\nexport class AppComponent {}\n"},
        {"path": "tsconfig.json", "content": "{\n  \"compileOnSave\": false,\n  \"compilerOptions\": {\n    \"baseUrl\": \"./\",\n    \"outDir\": \"./dist\",\n    \"sourceMap\": true,\n    \"declaration\": false,\n    \"module\": \"esnext\",\n    \"moduleResolution\": \"node\",\n    \"target\": \"es2020\",\n    \"lib\": [\"es2020\", \"dom\"]\n  }\n}\n"},
    ],
}


def _check_tool(name: str) -> bool:
    """Return True if the given tool is available on PATH."""
    try:
        subprocess.run([name, "--version"], capture_output=True, timeout=10)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _github_archive_url(owner: str, repo: str, ref: str = "main") -> str:
    return f"https://github.com/{owner}/{repo}/archive/{ref}.zip"


def _download_and_extract_github_template(
    owner: str,
    repo: str,
    subdir: str,
    ref: str,
    target_dir: Path,
) -> bool:
    """Download a GitHub repo zip and extract a subdirectory into target_dir.

    For example, Vite's react template lives at:
    ``vite/packages/create-vite/template-react``

    This function downloads ``vite-<ref>.zip``, extracts only the files under
    ``<subdir>``, and places their content into ``target_dir`` (stripping the
    subdir prefix).

    A session-level cache avoids re-downloading the same template multiple times
    within a single server process.
    """
    cache_key = f"{owner}/{repo}/{subdir}@{ref}"
    cached = _TEMPLATE_CACHE.get(cache_key)
    if cached and cached.exists():
        log.info("Using cached template for %s", cache_key)
        shutil.copytree(cached, target_dir, dirs_exist_ok=True)
        _normalize_template(target_dir)
        return True

    archive_url = _github_archive_url(owner, repo, ref)
    log.info("Downloading template from %s", archive_url)

    try:
        import urllib.request

        with tempfile.TemporaryDirectory() as tmp:
            archive_path = Path(tmp) / "template.zip"
            # Hard timeout: 30s connect + 60s download
            req = urllib.request.Request(archive_url, headers={"User-Agent": "FigmaConverter/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                with open(archive_path, "wb") as f:
                    shutil.copyfileobj(resp, f, length=1024 * 1024)

            archive_prefix = f"{repo}-{ref.replace('/', '-')}"
            source_prefix = f"{archive_prefix}/{subdir}"

            with zipfile.ZipFile(archive_path) as zf:
                for member in zf.namelist():
                    # Must match the source_prefix at a path boundary
                    # so "template-react-ts" does not match "template-react".
                    prefix_match = (
                        member == source_prefix
                        or member.startswith(source_prefix + "/")
                    )
                    if not prefix_match:
                        continue
                    relative = Path(member).relative_to(source_prefix)
                    if not relative.parts:
                        continue
                    dest = target_dir / relative
                    if member.endswith("/"):
                        dest.mkdir(parents=True, exist_ok=True)
                    else:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(member) as src, open(dest, "wb") as dst:
                            shutil.copyfileobj(src, dst)

        # Populate session cache
        _TEMPLATE_CACHE[cache_key] = target_dir

        log.info("Template extracted to %s", target_dir)
        _normalize_template(target_dir)
        return True

    except Exception as exc:
        log.warning("Failed to download template from GitHub: %s", exc)
        return False


def _normalize_template(target_dir: Path) -> None:
    """Post-extraction cleanup shared across all scaffold methods.

    Vite's official templates ship files named ``_gitignore`` instead of
    ``.gitignore`` (because npm would interpret the leading dot). Rename
    them back so the generated project is correct on disk.
    """
    for child in target_dir.rglob("_*"):
        if child.is_file() or child.is_dir():
            # Rename _gitignore → .gitignore, _eslintrc.cjs → .eslintrc.cjs, etc.
            new_name = "." + child.name[1:]
            dest = child.with_name(new_name)
            if not dest.exists():
                child.rename(dest)


def _apply_manual_scaffold(framework: str, target_dir: Path) -> bool:
    """Create a minimal scaffold from MANUAL_SCAFFOLDS entries."""
    files = MANUAL_SCAFFOLDS.get(framework)
    if not files:
        return False

    target_dir.mkdir(parents=True, exist_ok=True)
    for entry in files:
        path = target_dir / entry["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(entry["content"], encoding="utf-8")

    log.info("Manual scaffold applied for %s in %s", framework, target_dir)
    _normalize_template(target_dir)
    return True


def scaffold_project(
    target_dir: Path,
    framework: str,
    *,
    run_install: bool = False,
    style_engine: Optional[str] = None,
    component_library: Optional[str] = None,
) -> bool:
    """Scaffold a new project directory using the official template.

    Steps:
    1. If the framework has an official GitHub archive, download + extract it.
    2. Otherwise, use the manual scaffold definition.
    3. Inject component library / style engine deps into package.json.
    4. Optionally run the package manager install.

    Returns True on success.
    """
    target_dir.mkdir(parents=True, exist_ok=True)

    template = FRAMEWORK_TEMPLATES.get(framework)

    if template:
        owner, repo, subdir, ref = template["github"]
        ok = _download_and_extract_github_template(
            owner, repo, subdir, ref, target_dir
        )
        if not ok:
            log.warning("GitHub template download failed, trying manual scaffold")
            ok = _apply_manual_scaffold(framework, target_dir)
    else:
        ok = _apply_manual_scaffold(framework, target_dir)

    if not ok:
        log.warning("No scaffold available for %s, using empty directory", framework)
        return False

    # Inject component library / style engine deps into the scaffolded package.json
    if component_library or style_engine:
        _inject_extra_deps(target_dir, framework, style_engine, component_library)

    # Optionally run package manager install
    install_cmd = template.get("post_scaffold") if template else None
    if run_install and install_cmd:
        log.info("Running %s in %s", " ".join(install_cmd), target_dir)
        try:
            subprocess.run(
                install_cmd,
                cwd=str(target_dir),
                capture_output=True,
                timeout=120,
            )
        except Exception as exc:
            log.warning("Post-scaffold install failed: %s", exc)

    return True


def _inject_extra_deps(
    target_dir: Path,
    framework: str,
    style_engine: Optional[str] = None,
    component_library: Optional[str] = None,
) -> None:
    """Merge style-engine and component-library deps into package.json."""
    from processors.style_library_matrix import DependencyResolver

    pkg_path = target_dir / "package.json"
    if not pkg_path.exists():
        return

    resolver = DependencyResolver(use_cache=True)
    extra = resolver.resolve_to_package_json(
        framework, style_engine or "", component_library or ""
    )

    try:
        pkg = json.loads(pkg_path.read_text("utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    changed = False
    deps = extra.get("dependencies", {})
    for name, version in deps.items():
        if name not in pkg.setdefault("dependencies", {}):
            pkg["dependencies"][name] = version
            changed = True

    dev_deps = extra.get("devDependencies", {})
    for name, version in dev_deps.items():
        if name not in pkg.setdefault("devDependencies", {}):
            pkg["devDependencies"][name] = version
            changed = True

    if changed:
        pkg_path.write_text(json.dumps(pkg, indent=2) + "\n")


def get_framework_template_info(framework: str) -> Optional[Dict]:
    """Return metadata about a framework's template source."""
    info = FRAMEWORK_TEMPLATES.get(framework)
    if info:
        return {
            "framework": framework,
            "source": f"github:{info['github'][0]}/{info['github'][1]}",
            "description": info["description"],
        }
    if framework in MANUAL_SCAFFOLDS:
        return {
            "framework": framework,
            "source": "builtin",
            "description": f"Built-in scaffold for {framework}",
        }
    return None


def list_supported_frameworks() -> List[str]:
    """Return all framework names that have a template available."""
    return sorted(set(FRAMEWORK_TEMPLATES.keys()) | set(MANUAL_SCAFFOLDS.keys()))
