# FigmaConverter MCP Server — Agent Guide

## Overview

FigmaConverter converts Figma designs into production-ready code via an MCP server,
a FastAPI web API, or a CLI. AI inference is handled entirely by the **opencode
runtime** (`opencode serve`), which manages providers, API keys, and model routing.

## Prerequisites

- **Python 3.10+**
- **opencode CLI** (for AI inference) — install: `curl -fsSL https://opencode.ai/install.sh | sh`
- **Figma personal access token** — get one at https://www.figma.com/developers/api#access-tokens

If opencode is not installed, the server will start but AI features will not be
available. See [Fallback adapters](#fallback-adapters) for alternative harnesses.

## Quick start

```bash
pip install -r requirements.txt

# Figma token
export FIGMA_API_TOKEN=figd_xxx

# Start the server (auto-starts opencode serve on port 4096)
python main.py

# Or run the MCP server only
# python mcp_server.py
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `FIGMA_API_TOKEN` | — | Figma personal access token **(required)** |
| `OPENCODE_HOST` | `127.0.0.1` | opencode serve host |
| `OPENCODE_PORT` | `4096` | opencode serve port |
| `OPENCODE_PROVIDER_ID` | — | Force a specific AI provider (e.g. `anthropic`) |
| `OPENCODE_MODEL_ID` | — | Force a specific model (e.g. `claude-sonnet-4-6`) |
| `FIGMA_MCP_ENABLED` | `true` | Set to `false` to disable the MCP server |
| `FIGMA_MCP_TRANSPORT` | `stdio` | `stdio` or `sse` |
| `FIGMA_MCP_PORT` | `3845` | Port for SSE transport |
| `FIGMA_MCP_HOST` | `127.0.0.1` | Bind address for SSE transport |
| `FIGMA_MCP_API_KEY` | — | Optional auth key for SSE transport |
| `AI_CACHE_ENABLED` | `false` | Enable SQLite-backed AI response cache |
| `FIGMA_MAX_CONCURRENCY` | `5` | Max parallel Figma API calls |

## Architecture

```
FigmaConverter (Python)
  │
  ├── FastAPI server (main.py) — /api/convert, /api/status, /api/download
  ├── MCP server (mcp_server.py) — stdio / SSE transport
  └── Worker (worker.py) — background job processing
        │
        └── OpenCodeAdapter (processors/opencode_adapter.py)
              │
              └── opencode serve (subprocess on port 4096)
                    │
                    └── Your configured AI provider(s)
                          (Anthropic, OpenAI, Google, etc.)
```

The old 27-provider `AI_engine` (from the `core/` package) has been replaced by
`OpenCodeAdapter`, a thin (~150 line) wrapper that:

1. Starts `opencode serve` as a subprocess if not already running
2. Creates a session via the `opencode-ai` Python SDK
3. Maps FigmaConverter's `chat_completion(messages, ...)` calls to
   `client.session.chat(id, provider_id, model_id, parts)`
4. Extracts text responses and returns `RequestResult`-compatible objects

## Available tools

### `get_design_context`

Fetch structured metadata from a Figma file — frames, dimensions, component
counts, layout types, and design token availability.

**Parameters:**
- `figma_url` (string, required) — Full Figma file URL
- `pat_token` (string, optional) — Figma personal access token override
- `include_components` (bool, default `true`) — Include component references

**Returns:** JSON with file key, frame summaries, layout types, design token
availability, and component reference keys.

### `generate_code`

Generate framework code from a Figma design URL.

**Parameters:**
- `figma_url` (string, required) — Full Figma file URL
- `target_framework` (string, required) — `react`, `vue`, `angular`, `flutter`,
  `html`, `nextjs`, `react_ts`
- `pat_token` (string, optional) — Figma personal access token override
- `include_components` (bool, default `true`) — Include component image exports
- `style_engine` (string, optional) — `css`, `tailwind`, `scss`, `styled`,
  `css_modules`
- `component_library` (string, optional) — `shadcn`, `mui`, `antd`, `bootstrap`,
  `none`

**Returns:** JSON with generated files, file contents, framework info, and
dependency suggestions.

### `get_design_tokens`

Extract design tokens from a Figma file — colors, typography, spacing, radii,
shadows. Uses Figma Variables API when available.

**Parameters:**
- `figma_url` (string, required) — Full Figma file URL
- `pat_token` (string, optional) — Figma personal access token override

**Returns:** JSON with token source, token count, and token definitions.

### `get_framework_options`

List all supported frameworks, style engines, and component libraries.

**Parameters:** None

**Returns:** JSON with frameworks, style engines, component libraries, valid
combinations, default dependencies, and app file paths.

### `validate_design`

Analyse a Figma design for code-generation readiness — auto-layout coverage,
named-layers ratio, component usage.

**Parameters:**
- `figma_url` (string, required) — Full Figma file URL
- `pat_token` (string, optional) — Figma personal access token override

**Returns:** JSON with readiness score, auto-layout coverage, named frames
ratio, recommendations, and warnings.

## Output quality notes

The AI-generated code quality depends heavily on the model used. Based on live
testing with a 6-frame EV-HUB charging app design:

**Strengths:**
- Design tokens (colors, typography, layout) are accurately extracted from Figma
- Navigation between screens is implemented with proper route structure
- Responsive Tailwind classes are used (`flex`, `h-screen`, `ml-80`)
- Semantic component structure with proper imports and exports

**Known issues:**
- Some frames may fail AI parsing (model returns non-JSON text) — the pipeline
  retries up to 3x per frame
- Import path mismatches (App.jsx uses `./pages/` but components live in `./components/`)
- `react-redux`/`store` may be imported without being generated
- `router.jsx` may duplicate routing from `App.jsx`
- Font references like `font-roboto-mono` are not always consistent

**How to improve output:**
- Use a stronger model (set `OPENCODE_PROVIDER_ID=anthropic` / `OPENCODE_MODEL_ID=claude-sonnet-4-6`)
- Enable vision mode (see [Vision input](#vision-input)) to give the AI actual
  frame screenshots alongside structured data

## Vision input

FigmaConverter can export frame screenshots from Figma and pass them as vision
input to the AI model. This gives the AI a pixel-perfect visual reference
alongside the structured frame data, significantly improving layout and styling
accuracy.

**How it works:**
1. Each frame is rendered to PNG via the Figma Image API
   `GET /v1/images/{file_key}?ids={frame_id}&scale=2`
2. The image URL is passed as a vision attachment via opencode's API
   (using `FilePart` with image data)
3. The AI model processes both the structured JSON data and the screenshot

**Supported by:** opencode's built-in models (`deepseek-v4-flash-free`),
Anthropic Claude (all models), OpenAI GPT-4o, Google Gemini.

**To enable:** Set `FIGMA_INCLUDE_VISION=true` in `.env` (future feature —
not yet implemented).

## Fallback adapters

The `OpenCodeAdapter` requires the opencode CLI to be installed. If opencode is
not available, you can use a fallback adapter via the `llm` library:

```bash
pip install llm llm-anthropic llm-openai
export LLM_FALLBACK_MODEL=claude-sonnet-4-6
python main.py
```

The `LLMFallbackAdapter` (at `processors/llm_fallback_adapter.py`) uses
Simon Willison's `llm` library — a lightweight (~100KB core) Python LLM
wrapper with plugin-based provider support (OpenAI built-in, Anthropic via
`llm-anthropic`, local models via `llm-ollama`, and 30+ community plugins).

The factory in `ai_engine/__init__.py` auto-detects which adapter to use:
1. Try `OpenCodeAdapter` (opencode serve)
2. If unavailable, try `LLMFallbackAdapter` (llm library)
3. If neither available, raise a clear error with install instructions

## Transport modes

### stdio (default)

For local AI agents (Claude Code, Cursor). The agent spawns the server as a
subprocess and communicates over stdin/stdout.

```bash
python mcp_server.py
```

### SSE

For remote agents or long-running deployments. The server listens on HTTP and
exposes the SSE endpoint at `/sse`.

```bash
python mcp_server.py --transport sse --port 3845
```

If `FIGMA_MCP_API_KEY` is set, SSE requests must include the header:

```
Authorization: Bearer <FIGMA_MCP_API_KEY>
```

## Integration examples

### Claude Code

Claude Code auto-detects the MCP server when launched from the project
directory. Ensure the opencode CLI is available on `PATH`.

Add to `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "figma-converter": {
      "command": "python",
      "args": ["mcp_server.py"]
    }
  }
}
```

### Cursor

Add to Cursor MCP settings:

```json
{
  "mcpServers": {
    "figma-converter": {
      "command": "python",
      "args": ["mcp_server.py"]
    }
  }
}
```

### Remote (SSE + API key)

For agents that support remote MCP servers (e.g., Codex):

```json
{
  "mcpServers": {
    "figma-converter": {
      "url": "https://your-deployment.example.com/sse",
      "headers": {
        "Authorization": "Bearer <FIGMA_MCP_API_KEY>"
      }
    }
  }
}
```

## Deployment

See [Deployment Guide](docs/mcp-deployment.md) for Railway, Render, and Fly.io
deployment instructions. When deploying, ensure `opencode` is installed in the
container (add to Dockerfile) or configure the fallback adapter.
