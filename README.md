# FigmaConverter

> Local-first tooling that turns a Figma file into a scaffolded project using the Figma REST API, opencode's runtime for AI inference, and a project assembler. Ships as both a FastAPI web service and an MCP server for AI agent integration.

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
- **OpenCode runtime** — AI inference delegates to opencode serve (no built-in provider management)

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env  # set FIGMA_API_TOKEN
python main.py        # FastAPI on :8000 (auto-starts opencode serve)
# or
python mcp_server.py  # MCP stdio server for AI agents
python mcp_server.py --transport sse --port 3845  # SSE for remote agents
```

You need the opencode CLI on your PATH:
```bash
curl -fsSL https://opencode.ai/install.sh | sh
```

**Fallback without opencode:** Install the `llm` library instead:
```bash
pip install -r requirements-fallback.txt
pip install llm-anthropic   # optional, for Claude models
export LLM_FALLBACK_MODEL=gpt-4o-mini
python main.py
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `FIGMA_API_TOKEN` | — | Figma personal access token **(required)** |
| `OPENCODE_HOST` | `127.0.0.1` | opencode serve host |
| `OPENCODE_PORT` | `4096` | opencode serve port |
| `OPENCODE_PROVIDER_ID` | — | Force a specific AI provider |
| `OPENCODE_MODEL_ID` | — | Force a specific model |
| `OPENCODE_SKIP` | — | Set to `1` to skip opencode and use llm fallback |
| `LLM_FALLBACK_MODEL` | `gpt-4o-mini` | Model for llm fallback adapter |
| `AI_CACHE_ENABLED` | `false` | Enable SQLite-backed AI response cache |

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

519 hermetic tests — no network, no API keys required.

## Output quality

Tested with a 6-frame EV-HUB charging app design. Generated React+Tailwind output
includes proper navigation, responsive layout, and accurate color extraction from
Figma. Some frames may fail AI parsing (retried up to 3x). For best results:

1. Use a strong model — `OPENCODE_PROVIDER_ID=anthropic` `OPENCODE_MODEL_ID=claude-sonnet-4-6`
2. Ensure Figma frames have meaningful names and auto-layout
3. Set `FIGMA_INCLUDE_VISION=true` (future) to pass frame screenshots as vision input

## License

MIT
