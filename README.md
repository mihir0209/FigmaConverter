# FigmaConverter

> Local-first tooling that turns a Figma file into a scaffolded project using the Figma REST API, a multi-provider AI engine, and a project assembler. Ships as both a FastAPI web service and an MCP server for AI agent integration.

## What it does

- **FastAPI service** with durable SQLite job store — enqueue conversions, poll progress, download ZIP
- **MCP server** (stdio or SSE) — 5 tools: `get_design_context`, `generate_code`, `get_design_tokens`, `get_framework_options`, `validate_design`
- **Figma ingestion** — full file JSON, frame parsing (layout/padding/hierarchy), asset downloads
- **AI code generation** — framework detection → architecture → per-frame components → dependency reconciliation → project assembly
- **7 frameworks**: React, React/TS, Vue, Angular, Next.js, Flutter, HTML/CSS/JS
- **5 style engines**: CSS, Tailwind v4, SCSS, styled-components, CSS Modules
- **4 component libraries**: shadcn/ui, MUI, Ant Design, Bootstrap 5
- **Design tokens** — extract colors/typography/spacing/radii/shadows from Figma Variables
- **Visual validation** — Playwright screenshot comparison against Figma references
- **Background worker** — priority queue, retry with exponential backoff, job cancellation
- **AI response cache** — SQLite-backed, configurable TTL, gated by `AI_CACHE_ENABLED`
- **VS Code extension** — workspace-aware Import from URL command

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env  # set FIGMA_API_TOKEN and an AI provider key
python main.py        # FastAPI on :8000
# or
python mcp_server.py  # MCP stdio server for AI agents
python mcp_server.py --transport sse --port 3845  # SSE for remote agents
```

## Key routes

| Route | Purpose |
|---|---|
| `POST /api/convert` | Enqueue conversion (idempotent) |
| `GET /api/status/{job_id}` | Poll progress |
| `GET /api/download/{job_id}` | Download assembled ZIP |
| `POST /api/cancel/{job_id}` | Cancel queued/processing job |
| `POST /api/refine/{job_id}` | Apply natural-language refinement |

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/
```

507 hermetic tests — no network, no API keys required.

## License

MIT
