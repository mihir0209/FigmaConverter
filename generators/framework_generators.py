"""
Framework Code Generators for Figma-to-Code Converter
Generates production-ready co        return        return f'''const {{{{component_name}}}} = () => {{
    return (
        <div className="{{{{component_name.toLowerCase()}}}}-container"
             style={{{{{{width: '{dimensions.get('width', 375)}px', height: '{dimensions.get('height', 812)}px'}}}}}}>
            <div className="{{{{component_name.toLowerCase()}}}}-content">
                <h2>{{{{{component_data["name"]}}}}}</h2>
                <p>Generated from Figma design</p>
            </div>
        </div>
    );
}};

export default {{{{component_name}}}};
'''mponent_name}} = () => {{
    return (
        <div className="{{component_name.toLowerCase()}}-container"
             style={{{{width: '{dimensions.get('width', 375)}px', height: '{dimensions.get('height', 812)}px'}}}}>
            <div className="{{component_name.toLowerCase()}}-content">
                <h2>{{{{component_data["name"]}}}}</h2>
                <p>Generated from Figma design</p>
            </div>
            </div>
        </div>
    );
}};

export default {{component_name}};
'''t frameworks from Figma designs
"""

import json
import os
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime
import re

class FrameworkCodeGenerator:
    """Base class for framework-specific code generators"""

    def __init__(self, framework_name: str):
        self.framework_name = framework_name
        self.templates_dir = Path("framework_templates") / framework_name
        self.templates_dir.mkdir(parents=True, exist_ok=True)

    def generate_project_structure(self, design_data: Dict, output_dir: Path) -> Dict[str, Any]:
        """Generate complete project structure for the framework"""
        raise NotImplementedError("Subclasses must implement generate_project_structure")

    def generate_component_code(self, component_data: Dict) -> str:
        """Generate code for a single component"""
        raise NotImplementedError("Subclasses must implement generate_component_code")

    def generate_main_app_code(self, frames_data: List[Dict]) -> str:
        """Generate main application code"""
        raise NotImplementedError("Subclasses must implement generate_main_app_code")

    def get_project_files(self) -> List[str]:
        """Get list of files that should be created for this framework"""
        raise NotImplementedError("Subclasses must implement get_project_files")


class ReactGenerator(FrameworkCodeGenerator):
    """React framework code generator"""

    def __init__(self):
        super().__init__("react")

    def generate_project_structure(self, design_data: Dict, output_dir: Path) -> Dict[str, Any]:
        """Generate React project structure"""
        project_files = {}

        # package.json
        project_files["package.json"] = self._generate_package_json(design_data)

        # src/App.js
        project_files["src/App.js"] = self.generate_main_app_code(design_data.get("frames", []))

        # src/index.js
        project_files["src/index.js"] = self._generate_index_js()

        # public/index.html
        project_files["public/index.html"] = self._generate_html_template(design_data)

        # src/components/
        # Note: Directory creation is handled by project assembler

        # Generate component files
        for frame in design_data.get("frames", []):
            component_name = self._sanitize_component_name(frame["name"])
            component_file = f"src/components/{component_name}.js"
            project_files[component_file] = self.generate_component_code(frame)

        # src/styles/
        # Note: Directory creation is handled by project assembler
        project_files["src/styles/App.css"] = self._generate_app_css()

        return {
            "framework": "react",
            "files": project_files,
            "main_file": "src/App.js",
            "total_files": len(project_files)
        }

    def generate_component_code(self, component_data: Dict) -> str:
        """Generate React component code"""
        component_name = self._sanitize_component_name(component_data["name"])
        dimensions = component_data.get("dimensions", {})

        # Build the JSX template without f-string conflicts
        width = dimensions.get('width', 375)
        height = dimensions.get('height', 812)
        name = component_data["name"]

        return f'''import React from 'react';
import './{component_name}.css';

const {component_name} = () => {{
    return (
        <div className="{component_name.lower()}-container"
             style={{{{width: '{width}px', height: '{height}px'}}}}>
            <div className="{component_name.lower()}-content">
                <h2>{name}</h2>
                <p>Generated from Figma design</p>
            </div>
        </div>
    );
}};

export default {component_name};
'''

    def generate_main_app_code(self, frames_data: List[Dict]) -> str:
        """Generate main App.js"""
        imports = ["import React from 'react';", "import './App.css';"]
        component_instances = []

        for frame in frames_data:
            component_name = self._sanitize_component_name(frame["name"])
            imports.append(f"import {component_name} from './components/{component_name}';")
            component_instances.append(f"                <{component_name} />")

        imports_str = "\n".join(imports)
        components_str = "\n".join(component_instances)

        return f'''{imports_str}

function App() {{
    return (
        <div className="App">
            <header className="App-header">
                <h1>Figma Converted App</h1>
            </header>
            <main>
{components_str}
            </main>
        </div>
    );
}}

export default App;
'''

    def _generate_package_json(self, design_data: Dict) -> str:
        """Generate package.json for React project"""
        return '''{
  "name": "figma-converted-app",
  "version": "0.1.0",
  "private": true,
  "dependencies": {
    "@testing-library/jest-dom": "^5.16.4",
    "@testing-library/react": "^13.3.0",
    "@testing-library/user-event": "^13.5.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-scripts": "5.0.1",
    "web-vitals": "^2.1.4"
  },
  "scripts": {
    "start": "react-scripts start",
    "build": "react-scripts build",
    "test": "react-scripts test",
    "eject": "react-scripts eject"
  },
  "eslintConfig": {
    "extends": [
      "react-app",
      "react-app/jest"
    ]
  },
  "browserslist": {
    "production": [
      ">0.2%",
      "not dead",
      "not op_mini all"
    ],
    "development": [
      "last 1 chrome version",
      "last 1 firefox version",
      "last 1 safari version"
    ]
  }
}'''

    def _generate_index_js(self) -> str:
        """Generate src/index.js"""
        return '''import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
'''

    def _generate_html_template(self, design_data: Dict) -> str:
        """Generate public/index.html"""
        return '''<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <link rel="icon" href="%PUBLIC_URL%/favicon.ico" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="theme-color" content="#000000" />
    <meta name="description" content="Figma Converted React App" />
    <link rel="apple-touch-icon" href="%PUBLIC_URL%/logo192.png" />
    <link rel="manifest" href="%PUBLIC_URL%/manifest.json" />
    <title>Figma Converted App</title>
  </head>
  <body>
    <noscript>You need to enable JavaScript to run this app.</noscript>
    <div id="root"></div>
  </body>
</html>'''

    def _generate_app_css(self) -> str:
        """Generate App.css"""
        return '''.App {
  text-align: center;
}

.App-header {
  background-color: #282c34;
  padding: 20px;
  color: white;
}

.App-header h1 {
  margin: 0;
}

main {
  padding: 20px;
}
'''

    def _sanitize_component_name(self, name: str) -> str:
        """Sanitize component name for React"""
        # Remove special characters and spaces
        sanitized = re.sub(r'[^a-zA-Z0-9]', '', name)
        # Ensure it starts with a capital letter
        return sanitized.capitalize() or "Component"

    def get_project_files(self) -> List[str]:
        """Get list of React project files"""
        return [
            "package.json",
            "src/index.js",
            "src/App.js",
            "public/index.html",
            "src/styles/App.css"
        ]


class VueGenerator(FrameworkCodeGenerator):
    """Vue.js framework code generator"""

    def __init__(self):
        super().__init__("vue")

    def generate_project_structure(self, design_data: Dict, output_dir: Path) -> Dict[str, Any]:
        """Generate Vue project structure"""
        project_files = {}

        # package.json
        project_files["package.json"] = self._generate_package_json(design_data)

        # src/App.vue
        project_files["src/App.vue"] = self.generate_main_app_code(design_data.get("frames", []))

        # src/main.js
        project_files["src/main.js"] = self._generate_main_js()

        # public/index.html
        project_files["public/index.html"] = self._generate_html_template(design_data)

        # src/components/
        # Note: Directory creation is handled by project assembler

        # Generate component files
        for frame in design_data.get("frames", []):
            component_name = self._sanitize_component_name(frame["name"])
            component_file = f"src/components/{component_name}.vue"
            project_files[component_file] = self.generate_component_code(frame)

        return {
            "framework": "vue",
            "files": project_files,
            "main_file": "src/App.vue",
            "total_files": len(project_files)
        }

    def generate_component_code(self, component_data: Dict) -> str:
        """Generate Vue component code"""
        component_name = self._sanitize_component_name(component_data["name"])
        dimensions = component_data.get("dimensions", {})

        return f'''<template>
  <div class="{component_name.lower()}-container"
       :style="{{{{ width: '{dimensions.get('width', 375)}px', height: '{dimensions.get('height', 812)}px' }}}}>
    <div class="{component_name.lower()}-content">
      <h2>{component_data["name"]}</h2>
      <p>Generated from Figma design</p>
      <!-- Component content will be populated based on Figma elements -->
    </div>
  </div>
</template>

<script>
export default {{
  name: '{component_name}',
  data() {{
    return {{
      // Component data
    }}
  }}
}}
</script>

<style scoped>
.{component_name.lower()}-container {{
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 20px;
  margin: 10px;
}}

.{component_name.lower()}-content {{
  text-align: center;
}}
</style>'''

    def generate_main_app_code(self, frames_data: List[Dict]) -> str:
        """Generate main App.vue"""
        component_imports = []
        component_instances = []

        for frame in frames_data:
            component_name = self._sanitize_component_name(frame["name"])
            component_imports.append(f"import {component_name} from './components/{component_name}.vue';")
            component_instances.append(f"    <{component_name} />")

        imports_str = "\n".join(component_imports)
        components_str = "\n".join(component_instances)

        return f'''<template>
  <div id="app">
    <header>
      <h1>Figma Converted Vue App</h1>
    </header>
    <main>
{components_str}
    </main>
  </div>
</template>

<script>
{imports_str}

export default {{
  name: 'App',
  components: {{
    {', '.join([self._sanitize_component_name(f["name"]) for f in frames_data])}
  }}
}}
</script>

<style>
#app {{
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #2c3e50;
}}

header {{
  background-color: #42b883;
  padding: 20px;
  color: white;
  text-align: center;
}}

main {{
  padding: 20px;
}}
</style>'''

    def _generate_package_json(self, design_data: Dict) -> str:
        """Generate package.json for Vue project"""
        return '''{
  "name": "figma-converted-vue-app",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "serve": "vue-cli-service serve",
    "build": "vue-cli-service build",
    "lint": "vue-cli-service lint"
  },
  "dependencies": {
    "core-js": "^3.8.3",
    "vue": "^3.2.13"
  },
  "devDependencies": {
    "@vue/cli-plugin-babel": "~5.0.0",
    "@vue/cli-plugin-eslint": "~5.0.0",
    "@vue/cli-service": "~5.0.0",
    "@vue/compiler-sfc": "^3.0.0",
    "eslint": "^7.32.0",
    "eslint-plugin-vue": "^8.0.3"
  }
}'''

    def _generate_main_js(self) -> str:
        """Generate src/main.js"""
        return '''import { createApp } from 'vue'
import App from './App.vue'

createApp(App).mount('#app')
'''

    def _generate_html_template(self, design_data: Dict) -> str:
        """Generate public/index.html"""
        return '''<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="viewport" content="width=device-width,initial-scale=1.0">
    <link rel="icon" href="<%= BASE_URL %>favicon.ico">
    <title>Figma Converted Vue App</title>
  </head>
  <body>
    <noscript>
      <strong>We're sorry but figma-converted-vue-app doesn't work properly without JavaScript enabled. Please enable it to continue.</strong>
    </noscript>
    <div id="app"></div>
    <!-- built files will be auto injected -->
  </body>
</html>'''

    def _sanitize_component_name(self, name: str) -> str:
        """Sanitize component name for Vue"""
        sanitized = re.sub(r'[^a-zA-Z0-9]', '', name)
        return sanitized.capitalize() or "Component"

    def get_project_files(self) -> List[str]:
        """Get list of Vue project files"""
        return [
            "package.json",
            "src/main.js",
            "src/App.vue",
            "public/index.html"
        ]


class AngularGenerator(FrameworkCodeGenerator):
    """Angular framework code generator"""

    def __init__(self):
        super().__init__("angular")

    def generate_project_structure(self, design_data: Dict, output_dir: Path) -> Dict[str, Any]:
        """Generate Angular project structure"""
        project_files = {}

        # package.json
        project_files["package.json"] = self._generate_package_json(design_data)

        # src/app/app.component.ts
        project_files["src/app/app.component.ts"] = self.generate_main_app_code(design_data.get("frames", []))

        # src/app/app.component.html
        project_files["src/app/app.component.html"] = self._generate_app_html(design_data.get("frames", []))

        # src/app/app.component.css
        project_files["src/app/app.component.css"] = self._generate_app_css()

        # src/main.ts
        project_files["src/main.ts"] = self._generate_main_ts()

        # src/index.html
        project_files["src/index.html"] = self._generate_index_html(design_data)

        # Generate component files
        for frame in design_data.get("frames", []):
            component_name = self._sanitize_component_name(frame["name"])
            component_dir = f"src/app/components/{component_name.lower()}"
            project_files[f"{component_dir}/{component_name.lower()}.component.ts"] = self._generate_component_ts(frame)
            project_files[f"{component_dir}/{component_name.lower()}.component.html"] = self._generate_component_html(frame)
            project_files[f"{component_dir}/{component_name.lower()}.component.css"] = self._generate_component_css(frame)

        return {
            "framework": "angular",
            "files": project_files,
            "main_file": "src/app/app.component.ts",
            "total_files": len(project_files)
        }

    def generate_component_code(self, component_data: Dict) -> str:
        """Generate Angular component (TypeScript)"""
        return self._generate_component_ts(component_data)

    def generate_main_app_code(self, frames_data: List[Dict]) -> str:
        """Generate main app.component.ts"""
        component_imports = []
        component_declarations = []

        for frame in frames_data:
            component_name = self._sanitize_component_name(frame["name"])
            component_imports.append(f"import {{ {component_name}Component }} from './components/{component_name.lower()}/{component_name.lower()}.component';")
            component_declarations.append(f"    {component_name}Component,")

        imports_str = "\n".join(component_imports)
        declarations_str = "\n".join(component_declarations)

        return f'''import {{ Component }} from '@angular/core';
{imports_str}

@Component({{
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
}})
export class AppComponent {{
  title = 'Figma Converted Angular App';
}}
'''

    def _generate_app_html(self, frames_data: List[Dict]) -> str:
        """Generate app.component.html"""
        component_instances = []
        for frame in frames_data:
            component_name = self._sanitize_component_name(frame["name"])
            component_instances.append(f"<app-{component_name.lower()}></app-{component_name.lower()}>")

        components_str = "\n  ".join(component_instances)

        return f'''<div class="app-container">
  <header class="app-header">
    <h1>{{{{title}}}}</h1>
  </header>
  <main class="app-main">
    {components_str}
  </main>
</div>'''

    def _generate_app_css(self) -> str:
        """Generate app.component.css"""
        return '''.app-container {
  font-family: Arial, sans-serif;
}

.app-header {
  background-color: #1976d2;
  color: white;
  padding: 20px;
  text-align: center;
}

.app-main {
  padding: 20px;
}
'''

    def _generate_component_ts(self, component_data: Dict) -> str:
        """Generate component TypeScript file"""
        component_name = self._sanitize_component_name(component_data["name"])
        selector_name = component_name.lower()

        return f'''import {{ Component }} from '@angular/core';

@Component({{
  selector: 'app-{selector_name}',
  templateUrl: './{selector_name}.component.html',
  styleUrls: ['./{selector_name}.component.css']
}})
export class {component_name}Component {{
  componentName = '{component_data["name"]}';

  constructor() {{ }}
}}
'''

    def _generate_component_html(self, component_data: Dict) -> str:
        """Generate component HTML template"""
        component_name = self._sanitize_component_name(component_data["name"])

        return f'''<div class="{component_name.lower()}-container">
  <div class="{component_name.lower()}-content">
    <h2>{{{{componentName}}}}</h2>
    <p>Generated from Figma design</p>
    <!-- Component content will be populated based on Figma elements -->
  </div>
</div>'''

    def _generate_component_css(self, component_data: Dict) -> str:
        """Generate component CSS"""
        component_name = self._sanitize_component_name(component_data["name"])
        dimensions = component_data.get("dimensions", {})

        return f'''.{component_name.lower()}-container {{
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 20px;
  margin: 10px;
  width: {dimensions.get('width', 375)}px;
  height: {dimensions.get('height', 812)}px;
}}

.{component_name.lower()}-content {{
  text-align: center;
}}
'''

    def _generate_package_json(self, design_data: Dict) -> str:
        """Generate package.json for Angular project"""
        return '''{
  "name": "figma-converted-angular-app",
  "version": "0.0.0",
  "scripts": {
    "ng": "ng",
    "start": "ng serve",
    "build": "ng build",
    "watch": "ng build --watch --configuration development",
    "test": "ng test"
  },
  "private": true,
  "dependencies": {
    "@angular/animations": "^15.2.0",
    "@angular/common": "^15.2.0",
    "@angular/compiler": "^15.2.0",
    "@angular/core": "^15.2.0",
    "@angular/forms": "^15.2.0",
    "@angular/platform-browser": "^15.2.0",
    "@angular/platform-browser-dynamic": "^15.2.0",
    "@angular/router": "^15.2.0",
    "rxjs": "~7.8.0",
    "tslib": "^2.3.0",
    "zone.js": "~0.12.0"
  },
  "devDependencies": {
    "@angular-devkit/build-angular": "^15.2.0",
    "@angular/cli": "~15.2.0",
    "@angular/compiler-cli": "^15.2.0",
    "typescript": "~4.9.4"
  }
}'''

    def _generate_main_ts(self) -> str:
        """Generate src/main.ts"""
        return '''import { platformBrowserDynamic } from '@angular/platform-browser-dynamic';
import { AppModule } from './app/app.module';

platformBrowserDynamic().bootstrapModule(AppModule)
  .catch(err => console.error(err));
'''

    def _generate_index_html(self, design_data: Dict) -> str:
        """Generate src/index.html"""
        return '''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Figma Converted Angular App</title>
  <base href="/">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" type="image/x-icon" href="favicon.ico">
</head>
<body>
  <app-root></app-root>
</body>
</html>'''

    def _sanitize_component_name(self, name: str) -> str:
        """Sanitize component name for Angular"""
        sanitized = re.sub(r'[^a-zA-Z0-9]', '', name)
        return sanitized.capitalize() or "Component"

    def get_project_files(self) -> List[str]:
        """Get list of Angular project files"""
        return [
            "package.json",
            "src/main.ts",
            "src/index.html",
            "src/app/app.component.ts",
            "src/app/app.component.html",
            "src/app/app.component.css"
        ]


class FlutterGenerator(FrameworkCodeGenerator):
    """Flutter framework code generator"""

    def __init__(self):
        super().__init__("flutter")

    def generate_project_structure(self, design_data: Dict, output_dir: Path) -> Dict[str, Any]:
        """Generate Flutter project structure"""
        project_files = {}

        # pubspec.yaml
        project_files["pubspec.yaml"] = self._generate_pubspec_yaml(design_data)

        # lib/main.dart
        project_files["lib/main.dart"] = self.generate_main_app_code(design_data.get("frames", []))

        # lib/screens/
        # Note: Directory creation is handled by project assembler

        # Generate screen files
        for frame in design_data.get("frames", []):
            screen_name = self._sanitize_screen_name(frame["name"])
            screen_file = f"lib/screens/{screen_name}_screen.dart"
            project_files[screen_file] = self.generate_component_code(frame)

        # lib/widgets/
        # Note: Directory creation is handled by project assembler

        return {
            "framework": "flutter",
            "files": project_files,
            "main_file": "lib/main.dart",
            "total_files": len(project_files)
        }

    def generate_component_code(self, component_data: Dict) -> str:
        """Generate Flutter screen code"""
        screen_name = self._sanitize_screen_name(component_data["name"])
        dimensions = component_data.get("dimensions", {})

        return f'''import 'package:flutter/material.dart';

class {screen_name}Screen extends StatelessWidget {{
  const {screen_name}Screen({{Key? key}}) : super(key: key);

  @override
  Widget build(BuildContext context) {{
    return Scaffold(
      appBar: AppBar(
        title: const Text('{component_data["name"]}'),
      ),
      body: Container(
        width: {dimensions.get('width', 375)}.0,
        height: {dimensions.get('height', 812)}.0,
        padding: const EdgeInsets.all(16.0),
        child: const Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: <Widget>[
              Text(
                '{component_data["name"]}',
                style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
              ),
              SizedBox(height: 16),
              Text(
                'Generated from Figma design',
                style: TextStyle(fontSize: 16),
                textAlign: TextAlign.center,
              ),
              // Screen content will be populated based on Figma elements
            ],
          ),
        ),
      ),
    );
  }}
}}
'''

    def generate_main_app_code(self, frames_data: List[Dict]) -> str:
        """Generate main.dart"""
        imports = ["import 'package:flutter/material.dart';"]
        routes = []
        route_definitions = []

        for frame in frames_data:
            screen_name = self._sanitize_screen_name(frame["name"])
            imports.append(f"import 'screens/{screen_name}_screen.dart';")
            routes.append(f"        '/{screen_name.lower()}': (context) => const {screen_name}Screen(),")
            route_definitions.append(f"      {screen_name}Screen(),")

        imports_str = "\n".join(imports)
        routes_str = "\n".join(routes)
        route_definitions_str = "\n        ".join(route_definitions)

        return f'''{imports_str}

void main() {{
  runApp(const MyApp());
}}

class MyApp extends StatelessWidget {{
  const MyApp({{Key? key}}) : super(key: key);

  @override
  Widget build(BuildContext context) {{
    return MaterialApp(
      title: 'Figma Converted Flutter App',
      theme: ThemeData(
        primarySwatch: Colors.blue,
      ),
      initialRoute: '/{self._sanitize_screen_name(frames_data[0]["name"]).lower() if frames_data else "home"}',
      routes: {{
{routes_str}
      }},
      home: const {self._sanitize_screen_name(frames_data[0]["name"]) if frames_data else "Home"}Screen(),
    );
  }}
}}
'''

    def _generate_pubspec_yaml(self, design_data: Dict) -> str:
        """Generate pubspec.yaml for Flutter project"""
        return '''name: figma_converted_app
description: A Flutter app converted from Figma design
version: 1.0.0+1

environment:
  sdk: '>=3.0.0 <4.0.0'

dependencies:
  flutter:
    sdk: flutter
  cupertino_icons: ^1.0.2

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^2.0.0

flutter:
  uses-material-design: true
'''

    def _sanitize_screen_name(self, name: str) -> str:
        """Sanitize screen name for Flutter"""
        sanitized = re.sub(r'[^a-zA-Z0-9]', '', name)
        return sanitized.capitalize() or "Screen"

    def get_project_files(self) -> List[str]:
        """Get list of Flutter project files"""
        return [
            "pubspec.yaml",
            "lib/main.dart"
        ]


# Framework registry
FRAMEWORK_GENERATORS = {
    "react": ReactGenerator,
    "vue": VueGenerator,
    "angular": AngularGenerator,
    "flutter": FlutterGenerator
}


def get_framework_generator(framework_name: str) -> FrameworkCodeGenerator:
    """Get framework generator instance"""
    if framework_name not in FRAMEWORK_GENERATORS:
        raise ValueError(f"Unsupported framework: {framework_name}")

    return FRAMEWORK_GENERATORS[framework_name]()


def generate_framework_code(design_data: Dict, framework: str, output_dir: Path) -> Dict[str, Any]:
    """Generate code for specified framework"""
    generator = get_framework_generator(framework)
    return generator.generate_project_structure(design_data, output_dir)


# Example usage
if __name__ == "__main__":
    # Example design data
    sample_design = {
        "frames": [
            {
                "name": "Home Screen",
                "dimensions": {"width": 375, "height": 812},
                "page_name": "Main App"
            },
            {
                "name": "Profile Screen",
                "dimensions": {"width": 375, "height": 812},
                "page_name": "Main App"
            }
        ]
    }

    # Generate React code
    react_generator = ReactGenerator()
    react_structure = react_generator.generate_project_structure(sample_design, Path("data/output/react"))
    print(f"Generated React project with {react_structure['total_files']} files")

    # Generate Vue code
    vue_generator = VueGenerator()
    vue_structure = vue_generator.generate_project_structure(sample_design, Path("data/output/vue"))
    print(f"Generated Vue project with {vue_structure['total_files']} files")