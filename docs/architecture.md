# FigmaConverter architecture notes

> A monolithic FastAPI service that orchestrates Figma ingestion, AI-driven code generation, and project assembly. This document describes the actual runtime today so future refactors start from an honest baseline.

## High-level view

```
POST /api/convert
        │
        ▼
FastAPI background task (process_conversion)
        │
        ├── Framework detection (AIFrameworkDetector)
        ├── Figma ingestion (EnhancedFigmaProcessor)
        ├── AI code generation (generate_framework_code)
        │      ├── Architecture + design summary prompts
        │      ├── Per-frame component generation (thread pool)
        │      ├── Dependency reconciliation
        │      └── Main app scaffolding
        ├── Project assembly (ProjectAssembler)
        └── In-memory job record (jobs[job_id])
```

The service is single-process. All state lives on disk (generated files, component assets) or in memory (job metadata). There are no background workers, databases, caches, or queues.

## Runtime environment

- **Language/runtime**: Python 3.12 (tested locally)
- **Framework**: FastAPI + Uvicorn
- **HTTP clients**: `requests` (synchronous) for both Figma and asset downloads
- **Concurrency**: Python threads only (via `ThreadPoolExecutor` inside `main.py`)
- **AI integration**: `ai_engine.AI_engine` (multi-provider wrapper with retry/rotation logic backed by `ai_engine/config.py`)

## Request lifecycle

1. **Job bootstrap**
   - `POST /api/convert` validates payload and writes an entry to the global `jobs` dict.
   - A FastAPI `BackgroundTasks` coroutine invokes `process_conversion`.

2. **Framework detection**
   - `AIFrameworkDetector` maps the free-form request (e.g., “React with Vite + Tailwind”) to an internal framework descriptor.

3. **Design ingestion**
   - `EnhancedFigmaProcessor.process_frame_by_frame`:
     - Extracts the file key from the Figma URL
     - Retrieves the full document JSON
     - Spawns up to eight worker threads that parse frames via `EnhancedFrameParser`
     - Collects component references and exports assets into `components/`
     - Writes a manifest (`components/metadata/manifest.json`)

4. **AI-driven generation** (`generate_framework_code`)
   - Builds a design summary string for prompting (`create_comprehensive_design_summary`).
   - Requests an app architecture graph (`generate_app_architecture_with_ai`).
   - Spawns frame-generation tasks (capped by `MAX_THREADS`). Each task:
     - Creates a contextual prompt with comprehensive frame data
     - Calls `AI_engine.chat_completion`
     - Parses the JSON using `AIResponseParser`; on failure it currently stops for that frame.
   - Collects dependency suggestions and runs a second AI prompt to merge them (`reconcile_dependencies_with_ai`).
   - Generates core application files (main app, routing, entry point, global styles) via AI.
   - Fills in gaps with deterministic templates (`generate_config_files_from_structure`).

5. **Assembly**
   - `ProjectAssembler.assemble_project` writes all files into `data/output/job_{id}` and zips them.
   - `/api/download/{job_id}` streams the ZIP when requested.

## Module map

| Area | Modules | Responsibility |
|------|---------|----------------|
| API gateway | `main.py` | FastAPI app, background job management, orchestration |
| Figma ingest | `processors/enhanced_figma_processor.py`, `parsers/enhanced_frame_parser.py`, `processors/component_collector.py` | Fetch file JSON, parse frames, download assets |
| AI integration | `ai_engine/*`, `parsers/ai_response_parser.py`, `parsers/ai_prompt_engineer.py` | Prompt construction, provider rotation, JSON parsing |
| Prompt orchestration | `prompting/{prompt_builder,ai_runner,orchestrators}.py`, thin wrappers in `main.py` | Build prompts, call AI engine, parse JSON (remaining flows migrating out of `main.py`) |
| Assembly | `processors/project_assembler.py` | Write directories, inject assets, create archives |
| Diagnostics | `ai_engine/statistics_manager.py`, `log` | Basic key usage stats and manual logs |

## Data artefacts

- **Components cache**: `components/{images,vectors,icons,fonts}` with metadata JSON.
- **Job output**: `data/output/job_{uuid}/` containing generated code, assets, and a summary JSON.
- **Assembled projects**: optional archives or curated results under `data/assembled_projects/`.
- **Log file**: manually recorded session logs to aid debugging (not rolled automatically).

## Error handling today

- **Figma HTTP errors**: logged and bubble up; the job fails.
- **AI response parsing**: logged per frame. Failures prevent that frame from producing files; there is no retry yet.
- **Dependency reconciliation conflicts**: the reconciliation prompt plus hard-coded guards try to remove incompatible packages (e.g., `react-scripts` vs Vite).
- **Job state**: failures set the job status to `failed` with a message; results remain on disk for manual inspection.

## Limitations

- **Synchronous HTTP** – long-running Figma calls block worker threads.
- **Threading inside async** – `ThreadPoolExecutor` mitigates CPU-bound work but still runs inside the FastAPI process.
- **In-memory jobs** – restarting the process loses job metadata.
- **No rate limiting** – repeated large downloads can hit Figma’s quotas.
- **Logging** – relies on `print`; there is no structured or persisted logging pipeline.

## Immediate improvement backlog

1. **Robust AI parsing**: add schema validation and automatic retries/backoff when responses aren’t valid JSON.
2. **Job persistence**: store status and artifacts in SQLite/JSON to survive restarts.
3. **Structured logging**: switch to Python’s `logging` and capture timings per stage.
4. **Testability**: create contract tests that stub Figma + AI to protect against regressions.
5. **Modularisation**: break `main.py` into smaller service modules before introducing new features.

## Decision record

- Prioritise local workflows over hosted deployments.
- Use AI for scaffolding but keep deterministic fallbacks for critical files.
- Optimise for clarity (documented prompts, logs) so future refactors can swap providers or move to queues.
