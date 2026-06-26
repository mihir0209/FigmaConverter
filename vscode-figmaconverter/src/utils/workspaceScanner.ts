import * as vscode from "vscode";
import * as fs from "fs";
import * as path from "path";
import { CodebaseContext } from "../api/types";

export function scanWorkspace(rootUri: vscode.Uri): CodebaseContext {
  const root = rootUri.fsPath;

  const pkgJsonPath = path.join(root, "package.json");
  let dependencies: Record<string, string> = {};
  let framework: string | null = null;
  let styling: string | null = null;

  if (fs.existsSync(pkgJsonPath)) {
    try {
      const pkg = JSON.parse(fs.readFileSync(pkgJsonPath, "utf-8"));
      dependencies = { ...pkg.dependencies, ...pkg.devDependencies };
      framework = detectFramework(dependencies);
      styling = detectStyling(dependencies);
    } catch {
      // ignore parse errors
    }
  }

  if (!framework) {
    if (fs.existsSync(path.join(root, "next.config.js")) || fs.existsSync(path.join(root, "next.config.ts"))) {
      framework = "nextjs";
    } else if (fs.existsSync(path.join(root, "nuxt.config.js")) || fs.existsSync(path.join(root, "nuxt.config.ts"))) {
      framework = "vue";
    } else if (fs.existsSync(path.join(root, "angular.json"))) {
      framework = "angular";
    }
  }

  const srcDir = path.join(root, "src");
  const existingComponents: string[] = [];
  if (fs.existsSync(srcDir)) {
    const compDir = path.join(srcDir, "components");
    if (fs.existsSync(compDir)) {
      existingComponents.push(
        ...fs.readdirSync(compDir).filter((f) => /\.(tsx?|jsx?|vue)$/.test(f))
      );
    }
  }

  return { framework, dependencies, existing_components: existingComponents, styling_approach: styling };
}

function detectFramework(deps: Record<string, string>): string | null {
  if (deps["next"]) return "nextjs";
  if (deps["react"] || deps["react-dom"]) {
    if (deps["typescript"]) return "react_ts";
    return "react";
  }
  if (deps["vue"] || deps["nuxt"]) return "vue";
  if (deps["@angular/core"]) return "angular";
  return null;
}

function detectStyling(deps: Record<string, string>): string | null {
  if (deps["tailwindcss"]) return "tailwind";
  if (deps["styled-components"]) return "styled";
  if (deps["@emotion/react"]) return "styled";
  if (deps["@mui/material"]) return "css";
  if (deps["antd"] || deps["ant-design"]) return "css";
  return null;
}
