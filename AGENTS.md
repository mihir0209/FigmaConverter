# FigmaConverter MCP Server — Agent Guide

## Overview

FigmaConverter exposes an MCP server so AI agents (Claude Code, Cursor, Copilot,
Codex) can convert Figma designs into production-ready code without leaving the
agent's interface.

## Quick start

```bash
# Run the MCP server (stdio transport — default, for local agents)
python mcp_server.py

# Or SSE transport (for remote agents like Codex)
python mcp_server.py --transport sse --port 3845
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `FIGMA_API_TOKEN` | — | Figma personal access token (required) |
| `FIGMA_MCP_ENABLED` | `true` | Set to `false` to disable the MCP server |
| `FIGMA_MCP_TRANSPORT` | `stdio` | `stdio` or `sse` |
| `FIGMA_MCP_PORT` | `3845` | Port for SSE transport |
| `FIGMA_MCP_HOST` | `127.0.0.1` | Bind address for SSE transport |
| `FIGMA_MCP_API_KEY` | — | Optional auth key for SSE transport |

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
directory. Either add to `~/.claude/claude_desktop_config.json`:

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

Or run Claude Code from the project root — it discovers `mcp_server.py` in the
working directory.

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
deployment instructions.
