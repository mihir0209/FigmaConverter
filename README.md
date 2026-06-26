# FigmaConverter

> Local-first tooling that turns a Figma file into a scaffolded project using the Figma REST API, a multi-provider AI engine, and a project assembler. Built for experimentation and service integrations rather than public deployment.

## What’s actually implemented today

- **FastAPI service (`main.py`)** that exposes three routes:
   - `POST /api/convert` to enqueue a conversion job (validates Figma URL, supports idempotency on duplicate submissions)
   - `GET /api/status/{job_id}` to poll progress (durable SQLite store under `data/state/jobs.db`)
   - `GET /api/download/{job_id}` to download the assembled ZIP archive (clamped to the assembled-projects root, blocks path traversal)
- **Figma ingestion** via `EnhancedFigmaProcessor`: pulls full file JSON, parses each frame with `EnhancedFrameParser` (real layout/padding/spacing/hierarchy extraction — no longer stubbed), and downloads referenced assets into `components/`.
- **AI-assisted code generation** in `generate_framework_code` that:
   1. Detects the requested framework (`AIFrameworkDetector`)
   2. Summarises the design
   3. Generates project architecture and component files through `prompting.orchestrators` (retry-safe, conflict-aware)
   4. Reconciles dependencies and assembles output files
- **Project assembly** that packages generated source files and downloaded assets under `data/output/job_{id}` and emits a ZIP archive for download.
- **Local configuration** through `.env` plus `MAX_THREADS` runtime tuning for frame generation.
- **Operational**: structured logging, idempotent job store, daily cleanup thread.

## What’s deliberately out of scope

- No microservices, databases (beyond our local SQLite job store), Redis, S3, CI/CD, or production deployment targets
- No authentication, accounts, or collaboration features
- No built-in frontend dashboard beyond the static landing page in `web/`
- Tests in `tests/` are hermetic — they exercise the validation, parser, job store, assembler, orchestrators, and HTTP surface without calling any external AI or Figma API
- Reliability depends on upstream AI providers; malformed responses are handled by `AIResponseParser._load_json_with_repairs` plus the orchestrators' retry loops

## Prerequisites

- Python 3.10 or newer (developed on 3.12)
- A Figma personal access token (`FIGMA_API_TOKEN`)
- At least one AI provider API key supported by `ai_engine` (OpenAI, Anthropic, etc.)
- Optional: Node.js or Flutter toolchains if you plan to run generated projects

## Getting started locally

```bash
git clone https://github.com/mihir0209/FigmaConverter.git
cd FigmaConverter
python -m venv .venv
.venv\Scripts\activate  # PowerShell
pip install -r requirements.txt
cp .env.example .env  # create if it does not exist
```

Populate the following minimum variables inside `.env`:

```env
FIGMA_API_TOKEN=...
OPENAI_API_KEY=...        # or another provider supported by ai_engine
MAX_THREADS=3             # optional; defaults to 3
```

Run the FastAPI app:

```bash
python main.py
```

Open `http://localhost:8000` and submit a Figma file URL plus a natural-language description of the target framework (for example: “React with Vite and Tailwind”).

## Conversion workflow in detail

1. **Framework detection** – user request is normalised to one of the supported templates (React, Vue, Angular, Flutter, HTML/CSS/JS, …).
2. **Design harvesting** – `EnhancedFigmaProcessor` downloads the file, extracts frames, builds an enriched description, and saves assets.
3. **Architecture + component generation** – `generate_framework_code` delegates to `prompting.orchestrators` for app architecture, per-frame components, and dependency suggestions. Each frame runs in a thread pool capped by `MAX_THREADS`. The orchestrators own retry-attempt loops (3 attempts) and conversation memory to shape the AI's responses.
4. **Dependency reconciliation** – thread-level dependency suggestions are merged and validated with guardrails that prevent known conflicts (e.g. `react-scripts` versus Vite).
5. **Assembly** – `ProjectAssembler` writes files under the assembled-projects root and produces a ZIP emitted by the `/api/download` endpoint.

## Output locations

- `components/` – cached assets (images, vectors, metadata)
- `data/output/job_{id}/` – intermediate project files for each conversion
- `data/assembled_projects/` – finished converted projects
- `data/state/jobs.db` – SQLite-backed job store (durable across restarts)
- `data/state/key_statistics.json` – per-provider, per-key success/failure counters
- `data/state/model_cache.json` – shared autocomplete cache for AI providers

## Known limitations & troubleshooting

- **AI JSON responses can be malformed.** `parsers/ai_response_parser.py:_load_json_with_repairs` handles smart quotes and bare-JSON fences; orchestrators retry up to three times before falling back.
- **All job state lives in SQLite.** Restarts preserve queued/processing/completed jobs.
- **Long-running requests.** Large designs can take minutes. The FastAPI background task keeps running; keep polling `/api/status/{job_id}`.
- **Dependencies are heuristic.** Merged `package.json` entries should be reviewed before installing.
- **Figma API throttling.** The processor does not yet back off automatically; respect Figma’s rate limits.

## Suggested next steps

- Harden AI parsing with provider-side schema validation (pydantic-validated AI responses).
- Persist logs to disk for observability.
- Add property-based tests around the parser.
- Expose diagnostics (timings, provider usage) for easier debugging.

## Running tests

```bash
python -m pytest tests/
```

The suite is hermetic: it patches the AI engine and Figma processor where needed and runs without network or live API keys.

## License

This repository is MIT licensed. See [LICENSE](LICENSE).