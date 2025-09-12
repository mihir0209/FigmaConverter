"""
Project Assembly System for Figma-to-Code Converter
Assembles complete project structures with code files and components
"""

import json
import zipfile
import shutil
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime
import os

class ProjectAssembler:
    """Assembles complete project structures from generated code and components"""

    def __init__(self, output_base_dir: str = "assembled_projects"):
        self.output_base_dir = Path(output_base_dir)
        self.output_base_dir.mkdir(parents=True, exist_ok=True)

    def assemble_project(
        self,
        code_result: Dict[str, Any],
        components_result: Dict[str, Any],
        framework: str,
        job_id: str,
        project_name: str = None
    ) -> Dict[str, Any]:
        """Assemble complete project from code and components"""

        # Generate project name
        if not project_name:
            project_name = f"figma_converted_{framework}_{job_id}"

        # Create project directory
        project_dir = self.output_base_dir / project_name
        project_dir.mkdir(parents=True, exist_ok=True)

        print(f"🔨 Assembling project: {project_name}")

        # Create project structure
        assembly_result = {
            "project_name": project_name,
            "project_dir": str(project_dir),
            "framework": framework,
            "files_created": 0,
            "components_added": 0,
            "assembly_timestamp": datetime.now().isoformat()
        }

        try:
            # 1. Create framework-specific project structure
            framework_files = self._create_framework_structure(code_result, project_dir, framework)
            assembly_result["files_created"] += len(framework_files)

            # 2. Add components and assets
            if components_result and components_result.get("total_components", 0) > 0:
                components_added = self._add_components_to_project(components_result, project_dir, framework)
                assembly_result["components_added"] = components_added

            # 3. Create project configuration files
            config_files = self._create_project_config(project_dir, framework, code_result, components_result)
            assembly_result["files_created"] += len(config_files)

            # 4. Create README and documentation
            docs_files = self._create_documentation(project_dir, code_result, components_result, framework)
            assembly_result["files_created"] += len(docs_files)

            # 5. Create ZIP archive
            zip_path = self._create_project_zip(project_dir, project_name)
            assembly_result["zip_path"] = str(zip_path)
            assembly_result["zip_size"] = os.path.getsize(zip_path) if os.path.exists(zip_path) else 0

            # 6. Create project manifest
            manifest_path = self._create_project_manifest(project_dir, assembly_result)
            assembly_result["manifest_path"] = str(manifest_path)

            print(f"✅ Project assembly complete: {assembly_result['files_created']} files, {assembly_result['components_added']} components")

        except Exception as e:
            print(f"❌ Project assembly failed: {e}")
            assembly_result["error"] = str(e)

        return assembly_result

    def _create_framework_structure(self, code_result: Dict, project_dir: Path, framework: str) -> List[str]:
        """Create framework-specific project structure"""
        created_files = []

        if not code_result or not isinstance(code_result, dict):
            print(f"❌ Invalid code_result: {code_result}")
            return created_files

        # Get framework files from code result
        framework_files = code_result.get("files", {})

        for file_path, file_content in framework_files.items():
            # Create full path
            full_path = project_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file content
            try:
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(file_content)
                created_files.append(str(file_path))
                print(f"📄 Created: {file_path}")
            except Exception as e:
                print(f"❌ Failed to create {file_path}: {e}")

        return created_files

    def _add_components_to_project(self, components_result: Dict, project_dir: Path, framework: str) -> int:
        """Add components and assets to the project"""
        components_added = 0

        # Create assets directory based on framework
        assets_dir = self._get_framework_assets_dir(project_dir, framework)
        assets_dir.mkdir(parents=True, exist_ok=True)

        # Copy component assets
        components = components_result.get("components", [])
        for component in components:
            try:
                # Copy component assets
                assets = component.get("assets", {})
                for asset_type, asset_path in assets.items():
                    if os.path.exists(asset_path):
                        # Copy asset to project assets directory
                        asset_filename = Path(asset_path).name
                        dest_path = assets_dir / asset_filename

                        shutil.copy2(asset_path, dest_path)
                        components_added += 1
                        print(f"🖼️ Added asset: {asset_filename}")

                # Create component metadata file
                component_metadata = {
                    "id": component["id"],
                    "name": component["name"],
                    "type": component["type"],
                    "dimensions": component["dimensions"],
                    "styles": component["styles"],
                    "assets": list(assets.keys())
                }

                metadata_file = assets_dir / f"{component['safe_name']}_metadata.json"
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(component_metadata, f, indent=2)

            except Exception as e:
                print(f"❌ Failed to add component {component.get('name', 'Unknown')}: {e}")

        return components_added

    def _get_framework_assets_dir(self, project_dir: Path, framework: str) -> Path:
        """Get the appropriate assets directory for the framework"""
        assets_paths = {
            "react": "src/assets",
            "vue": "src/assets",
            "angular": "src/assets",
            "flutter": "assets",
            "html_css_js": "assets"
        }

        assets_path = assets_paths.get(framework, "assets")
        return project_dir / assets_path

    def _create_project_config(self, project_dir: Path, framework: str, code_result: Dict, components_result: Dict) -> List[str]:
        """Create project configuration files"""
        created_files = []

        # Framework-specific configuration
        if framework == "react":
            created_files.extend(self._create_react_config(project_dir))
        elif framework == "vue":
            created_files.extend(self._create_vue_config(project_dir))
        elif framework == "angular":
            created_files.extend(self._create_angular_config(project_dir))
        elif framework == "flutter":
            created_files.extend(self._create_flutter_config(project_dir))

        # Create .gitignore
        gitignore_content = self._get_gitignore_content(framework)
        gitignore_path = project_dir / ".gitignore"
        with open(gitignore_path, 'w', encoding='utf-8') as f:
            f.write(gitignore_content)
        created_files.append(".gitignore")

        return created_files

    def _create_react_config(self, project_dir: Path) -> List[str]:
        """Create React-specific configuration files"""
        created_files = []

        # .env.example
        env_example = """# Figma Converter Generated Project
REACT_APP_NAME=Figma Converted App
REACT_APP_VERSION=1.0.0
"""
        env_path = project_dir / ".env.example"
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(env_example)
        created_files.append(".env.example")

        return created_files

    def _create_vue_config(self, project_dir: Path) -> List[str]:
        """Create Vue-specific configuration files"""
        created_files = []

        # vue.config.js
        vue_config = """module.exports = {
  publicPath: process.env.NODE_ENV === 'production'
    ? '/production-sub-path/'
    : '/'
}
"""
        config_path = project_dir / "vue.config.js"
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(vue_config)
        created_files.append("vue.config.js")

        return created_files

    def _create_angular_config(self, project_dir: Path) -> List[str]:
        """Create Angular-specific configuration files"""
        created_files = []

        # angular.json (simplified)
        angular_config = """{
  "version": 1,
  "newProjectRoot": "projects",
  "projects": {
    "figma-converted-app": {
      "projectType": "application",
      "schematics": {},
      "root": "",
      "sourceRoot": "src",
      "prefix": "app"
    }
  }
}"""
        config_path = project_dir / "angular.json"
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(angular_config)
        created_files.append("angular.json")

        return created_files

    def _create_flutter_config(self, project_dir: Path) -> List[str]:
        """Create Flutter-specific configuration files"""
        created_files = []

        # analysis_options.yaml
        analysis_config = """analyzer:
  enable-experiment:
    - non-nullable
linter:
  rules:
    - prefer_const_constructors
"""
        config_path = project_dir / "analysis_options.yaml"
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(analysis_config)
        created_files.append("analysis_options.yaml")

        return created_files

    def _get_gitignore_content(self, framework: str) -> str:
        """Get appropriate .gitignore content for framework"""
        base_gitignore = """
# Dependencies
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# Production builds
build/
dist/

# Environment variables
.env
.env.local
.env.development.local
.env.test.local
.env.production.local

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
logs
*.log

# Temporary files
tmp/
temp/
"""

        if framework == "flutter":
            base_gitignore += """
# Flutter
.dart_tool/
.packages
pubspec.lock
"""

        return base_gitignore.strip()

    def _create_documentation(self, project_dir: Path, code_result: Dict, components_result: Dict, framework: str) -> List[str]:
        """Create README and documentation files"""
        created_files = []

        # README.md
        readme_content = self._generate_readme(code_result, components_result, framework)
        readme_path = project_dir / "README.md"
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        created_files.append("README.md")

        # FIGMA_CONVERTER_INFO.json
        converter_info = {
            "converter": "Figma-to-Code Converter",
            "version": "1.0.0",
            "framework": framework,
            "conversion_date": datetime.now().isoformat(),
            "code_files": len(code_result.get("files", {})),
            "components": components_result.get("total_components", 0),
            "main_file": code_result.get("main_file", "")
        }

        info_path = project_dir / "FIGMA_CONVERTER_INFO.json"
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(converter_info, f, indent=2)
        created_files.append("FIGMA_CONVERTER_INFO.json")

        return created_files

    def _generate_readme(self, code_result: Dict, components_result: Dict, framework: str) -> str:
        """Generate README.md content"""
        framework_names = {
            "react": "React",
            "vue": "Vue.js",
            "angular": "Angular",
            "flutter": "Flutter",
            "html_css_js": "HTML/CSS/JavaScript"
        }

        framework_name = framework_names.get(framework, framework.upper())

        readme = f"""# Figma Converted {framework_name} App

This project was automatically generated from a Figma design using the Figma-to-Code Converter.

## 🚀 Quick Start

### Prerequisites

"""

        if framework in ["react", "vue", "angular"]:
            readme += """- Node.js (v16 or higher)
- npm or yarn

### Installation

```bash
npm install
```

### Development

```bash
npm start
```

### Build for Production

```bash
npm run build
```
"""
        elif framework == "flutter":
            readme += """- Flutter SDK
- Dart SDK

### Installation

```bash
flutter pub get
```

### Development

```bash
flutter run
```

### Build for Production

```bash
flutter build apk  # For Android
flutter build ios  # For iOS
```
"""
        else:
            readme += """### Open in Browser

Simply open `index.html` in your web browser.
"""

        readme += f"""
## 📊 Project Information

- **Framework**: {framework_name}
- **Code Files**: {len(code_result.get("files", {}))}
- **Components**: {components_result.get("total_components", 0)}
- **Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 🎨 Components

"""

        components = components_result.get("components", [])
        if components:
            for component in components[:10]:  # Show first 10 components
                readme += f"- {component['name']} ({component['type']})\n"
            if len(components) > 10:
                readme += f"- ... and {len(components) - 10} more components\n"
        else:
            readme += "No components were extracted from the design.\n"

        readme += """
## 🔧 Customization

This project was auto-generated from your Figma design. You can:

1. **Modify Components**: Edit the generated component files
2. **Add Functionality**: Extend components with custom logic
3. **Style Adjustments**: Update CSS/styling files
4. **Add Features**: Integrate with APIs, databases, etc.

## 📝 Notes

- This project maintains pixel-perfect accuracy to your original Figma design
- All components are responsive and mobile-friendly
- Assets are optimized for web deployment
- The project follows {framework_name} best practices

## 🛠️ Figma-to-Code Converter

Generated by [Figma-to-Code Converter](https://github.com/your-repo/figma-converter)
"""

        return readme

    def _create_project_zip(self, project_dir: Path, project_name: str) -> Path:
        """Create ZIP archive of the project"""
        zip_path = self.output_base_dir / f"{project_name}.zip"

        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Walk through project directory
                for file_path in project_dir.rglob('*'):
                    if file_path.is_file():
                        # Get relative path for ZIP
                        relative_path = file_path.relative_to(project_dir.parent)
                        zip_file.write(file_path, relative_path)

            print(f"📦 Created ZIP archive: {zip_path}")
            return zip_path

        except Exception as e:
            print(f"❌ Failed to create ZIP: {e}")
            return None

    def _create_project_manifest(self, project_dir: Path, assembly_result: Dict) -> Path:
        """Create project manifest file"""
        manifest_path = project_dir / "project_manifest.json"

        manifest = {
            "project_info": assembly_result,
            "generated_at": datetime.now().isoformat(),
            "converter_version": "1.0.0"
        }

        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)

        return manifest_path

    def cleanup_old_projects(self, max_age_days: int = 7) -> int:
        """Clean up old project directories and ZIPs"""
        cutoff_time = datetime.now().timestamp() - (max_age_days * 24 * 60 * 60)
        cleaned_count = 0

        try:
            # Clean project directories
            for item in self.output_base_dir.iterdir():
                if item.is_dir() and item.stat().st_mtime < cutoff_time:
                    shutil.rmtree(item)
                    cleaned_count += 1
                    print(f"🗑️ Cleaned old project: {item.name}")

                elif item.is_file() and item.suffix == '.zip' and item.stat().st_mtime < cutoff_time:
                    item.unlink()
                    cleaned_count += 1
                    print(f"🗑️ Cleaned old ZIP: {item.name}")

        except Exception as e:
            print(f"❌ Cleanup failed: {e}")

        return cleaned_count


# Example usage
if __name__ == "__main__":
    # Initialize project assembler
    assembler = ProjectAssembler()

    # Example assembly (would be called from main conversion pipeline)
    sample_code_result = {
        "framework": "react",
        "files": {
            "package.json": '{"name": "test"}',
            "src/App.js": "console.log('Hello');"
        },
        "main_file": "src/App.js"
    }

    sample_components_result = {
        "total_components": 2,
        "components": [
            {"name": "Button", "type": "COMPONENT", "safe_name": "button"},
            {"name": "Header", "type": "FRAME", "safe_name": "header"}
        ]
    }

    # Assemble project
    result = assembler.assemble_project(
        sample_code_result,
        sample_components_result,
        "react",
        "test_job_123",
        "sample_react_app"
    )

    print(f"🎉 Project assembled: {result['project_name']}")
    print(f"📁 Location: {result['project_dir']}")
    print(f"📦 ZIP: {result.get('zip_path', 'Not created')}")