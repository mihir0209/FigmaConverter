# FigmaConverter

> Local-first tooling that turns a Figma file into a scaffolded project using the Figma REST API, a multi-provider AI engine, and a project assembler. Built for experimentation and service integrations rather than public deployment.

## What’s actually implemented today

- **FastAPI service (`main.py`)** that exposes three routes:
   - `POST /api/convert` to enqueue a conversion job
   - `GET /api/status/{job_id}` to poll progress (in-memory store)
   - `GET /api/download/{job_id}` to download the assembled ZIP archive
- **Figma ingestion** via `EnhancedFigmaProcessor`: pulls full file JSON, parses each frame with `EnhancedFrameParser`, and downloads referenced assets into the `components/` tree.
- **AI-assisted code generation** in `generate_framework_code` that:
   1. Detects the requested framework (`AIFrameworkDetector`)
   2. Summarises the design
   3. Generates project architecture and component files through the `ai_engine`
   4. Reconciles dependencies and assembles output files
- **Project assembly** that packages generated source files and downloaded assets under `data/output/job_{id}` and emits a ZIP archive for download.
- **Local configuration** through `.env` plus `MAX_THREADS` runtime tuning for frame generation.

## What’s deliberately out of scope

- No microservices, databases, Redis, S3, CI/CD, or production deployment targets
- No authentication, accounts, or collaboration features
- No built-in frontend dashboard beyond the static landing page in `web/`
- Tests in `tests/` are smoke scripts; they require a locally running server and valid API keys
- Reliability depends on upstream AI providers; malformed responses currently require manual triage

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
3. **Architecture + component generation** – `generate_framework_code` prompts the AI engine for app architecture, per-frame components, and dependency suggestions. Each frame runs in a thread pool capped by `MAX_THREADS`.
4. **Dependency reconciliation** – AI suggestions are merged and validated with guardrails that prevent known conflicts (e.g. `react-scripts` versus Vite).
5. **Assembly** – `ProjectAssembler` writes files under `data/output/job_{id}` and produces a ZIP exported by the `/api/download` endpoint.

## Output locations

- `components/` – cached assets (images, vectors, metadata)
- `data/output/job_{id}/` – intermediate project files for each conversion
- `data/assembled_projects/` – saved examples or later analysis artifacts
- `log` – latest conversion log (manual capture)

## Known limitations & troubleshooting

- **AI JSON responses can be malformed.** The current implementation logs parse errors but may stop generating a frame. Manual retries or prompt adjustments are sometimes required.
- **All job state lives in memory.** Restarting the process clears `/api/status`. Persist results you need.
- **Long-running requests.** Large designs can take minutes. The FastAPI background task keeps running, so keep polling `/api/status/{job_id}`.
- **Dependencies are heuristic.** Merged `package.json` entries should be reviewed before installing.
- **Figma API throttling.** The processor does not yet back off automatically; respect Figma’s rate limits.

## Suggested next steps

- Harden AI parsing with structured retries and schema validation (see open task).
- Persist job metadata and logs for reproducibility.
- Add automated tests that stub out Figma and AI responses.
- Expose diagnostics (timings, provider usage) for easier debugging.

## License

This repository is MIT licensed. See [LICENSE](LICENSE).