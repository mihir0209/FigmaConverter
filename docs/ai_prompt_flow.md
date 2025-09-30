# AI Prompting and Response Flow

This document maps the current design-to-code prompting pipeline implemented in `main.py` (and supporting modules). It clarifies when we talk to the AI engine, how each prompt is constructed, and which parsers consume the responses.

## End-to-End Pipeline Overview

1. **Job kickoff** (`process_conversion` in `main.py`)
   - Detects the requested framework via `AIFrameworkDetector`.
   - Pulls and enriches Figma data through `EnhancedFigmaProcessor.process_frame_by_frame`, which embeds comprehensive frame metadata used by later prompts.
2. **Framework discovery** (`prompting.orchestrators.discover_framework_structure` via `main.py`)
   - First AI call: asks the model for a JSON description of an optimal project structure for the detected framework.
   - Response parsed by `AIResponseParser.parse_framework_discovery_response`.
3. **Design summary creation** (`create_comprehensive_design_summary`)
   - No AI involved, but prepares the long-form design context injected into later prompts.
4. **App architecture inference** (`prompting.orchestrators.generate_app_architecture_with_ai`)
   - Second AI call: leverages the design summary to infer routes, shared components, and navigation edges.
   - Response manually cleaned and loaded with `json.loads` inside the function (no dedicated parser helper).
5. **Frame-level code generation** (`generate_enhanced_frame_code_with_ai`)
   - Per-frame AI call inside a retry loop (max 3 attempts). Uses the architecture, design summary, and resolved dependencies as context.
   - Response parsed by `AIResponseParser.parse_component_generation_response`.
6. **Dependency suggestions collation**
   - Each frame response may return dependency hints (collected for reconciliation).
7. **Main app generation** (`generate_enhanced_main_app_with_ai`)
   - Another AI call, with retries, to obtain the shell app (routing, entrypoint, styles) tailored to the selected framework.
   - Response parsed by `AIResponseParser.parse_main_app_generation_response`.
8. **Fallback config generation** (`generate_config_files_from_structure`)
   - Pure Python generation of base scaffolding if earlier steps did not produce the files.
9. **Dependency reconciliation** (`reconcile_dependencies_with_ai`)
   - Consolidates dependency suggestions via an AI prompt, including hard rules about vite/react-scripts conflicts.
   - Response cleaned manually and then `json.loads` is used (the parser is not reused here; function-level cleaning ensures JSON).
10. **Dependency application** (`apply_dependency_resolution`)
    - Applies AI-suggested `package.json` mutations and import injections.
11. **Assembly**
    - `ProjectAssembler` writes files and packages the project.

## Prompt Construction Details

### 1. Framework Discovery (`discover_framework_structure`)
- **System prompt**: positions the model as an expert architect for the chosen framework (React, Vue, Flutter, etc.).
- **User prompt**: requests a strict JSON object describing structure, configs, routing, build tool, and styling, pre-populated with fallback values.
- **Response handling**: parsed with `_load_json_with_repairs` to tolerate formatting issues.

### 2. App Architecture (`generate_app_architecture_with_ai`)
- **System prompt**: frames the model as an application architect focusing on navigation, shared components, and data flow.
- **User prompt**: includes the entire design summary plus instructions to return navigation and state data in JSON.
- **Parsing**: manual cleanup (regex to strip code fences) followed by `json.loads`.

### 3. Frame Code (`generate_enhanced_frame_code_with_ai`)
- **System prompt**: enforces framework-specific patterns, navigation, and dependency discipline.
- **User prompt**: embeds:
  - Rich frame-specific details (texts, colors, layout, connections).
  - Global architecture context.
  - Resolved dependency snapshot (if available).
  - A schema for the JSON response.
- **Retries**: up to 3 attempts; on parse failure, the conversation is appended with explicit correction instructions.
- **Parser**: `parse_component_generation_response` validates `component_name`, `content`, and `file_path`.

### 4. Main App (`generate_enhanced_main_app_with_ai`)
- **System prompt**: similar enforcement, but for overall app assembly (routing, global styles, entry point).
- **User prompt**: enumerates frames, architecture, shared components, and the JSON schema for expected files.
- **Retries**: same 3-attempt loop with corrective messages.
- **Parser**: `parse_main_app_generation_response` ensures `main_app` exists and extracts optional sections (`routing`, `entry_point`, `global_styles`).

### 5. Dependency Resolution (`reconcile_dependencies_with_ai`)
- **System prompt**: emphasises conflict avoidance (vite vs react-scripts, TypeScript compatibility).
- **User prompt**: provides base dependencies, raw suggestions, and a curated list of forbidden combinations.
- **Post-processing**: the code re-validates the JSON output and forcibly corrects known conflicts (removing `react-scripts`, enforcing Vite, etc.).

## Response Parsing & Error Handling

- **`AIResponseParser`** centralizes repairs via `_load_json_with_repairs`, which:
  - Strips markdown fences.
  - Attempts plain `json.loads`, then `strict=False` fallback, then escaping stray backslashes.
- **Retry logic** exists for both frame and main app generation. Each retry appends a user message instructing the model to resend only valid JSON.
- **Dependency reconciliation** and **architecture inference** perform their own manual cleanup before loading JSON.
- **Error surfaces**: when parsing fails after retries, the pipeline logs the raw response but currently returns empty dicts (call sites treat this as failure and continue with fallbacks).

## Supporting Modules

- `EnhancedFigmaProcessor`: pre-processes Figma data, adding `comprehensive_data` used extensively in prompts.
- `AI_engine`: handles provider selection, retries at the transport layer, and rate-limit-aware key rotation. It does not build prompts but is vital infrastructure.
- `prompting/`: new prompt builders (`prompt_builder.py`), execution helpers (`ai_runner.py`), and orchestrators (`orchestrators.py`) that now own framework discovery and architecture prompts.
- Legacy `generators/` package was removed (2025-09-30); prompt orchestration continues to migrate out of `main.py`.

## Key Observations

- Every AI call is orchestrated from `main.py`; the `parsers/ai_prompt_engineer.py` helper is not wired into the running pipeline.
- Prompts are already large and repetitive; the same framework facts are injected into multiple steps. There is no central prompt template abstraction yet.
- JSON-only responses are strictly enforced, but schema validation is minimal beyond required fields.
- Dependency reconciliation mixes AI judgement with deterministic safety checks to avoid known React conflicts.

This mapping should serve as the baseline for refactoring prompts, introducing search-backed context, or relocating orchestration into dedicated modules.
