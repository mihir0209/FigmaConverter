# MCP Server Deployment Guide

Deploy the FigmaConverter MCP server as a remote endpoint so AI agents (Codex,
Copilot, etc.) can connect over SSE.

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `FIGMA_API_TOKEN` | Yes | — | Figma personal access token |
| `FIGMA_MCP_TRANSPORT` | No | `stdio` | Set to `sse` for remote deployment |
| `FIGMA_MCP_PORT` | No | `3845` | Port to listen on |
| `FIGMA_MCP_HOST` | No | `0.0.0.0` | Bind address |
| `FIGMA_MCP_API_KEY` | No | — | Auth key for SSE requests |

> **Security:** Always set `FIGMA_MCP_API_KEY` in production. Without it,
> anyone who can reach the endpoint can invoke MCP tools.

---

## Railway

1. Create a new project from your Git repository.
2. Add a `Procfile` (or use the Railway web UI):

```yaml
web: python mcp_server.py --transport sse --port $PORT
```

3. Set environment variables in the Railway dashboard:
   - `FIGMA_API_TOKEN` — your Figma PAT
   - `FIGMA_MCP_API_KEY` — a strong random token
   - `FIGMA_MCP_TRANSPORT` → `sse`
   - `FIGMA_MCP_HOST` → `0.0.0.0`

4. Deploy. Railway assigns a `*.railway.app` URL.

5. Configure your agent:

```json
{
  "mcpServers": {
    "figma-converter": {
      "url": "https://your-project.up.railway.app/sse",
      "headers": {
        "Authorization": "Bearer <FIGMA_MCP_API_KEY>"
      }
    }
  }
}
```

---

## Render

1. Create a new **Web Service** from your Git repository.
2. Set:
   - **Start Command:** `python mcp_server.py --transport sse --port $PORT`
   - **Instance Type:** Free or paid
3. Add environment variables in the Render dashboard:
   - `FIGMA_API_TOKEN`
   - `FIGMA_MCP_API_KEY`
   - `FIGMA_MCP_TRANSPORT` → `sse`
   - `FIGMA_MCP_HOST` → `0.0.0.0`
4. Deploy. Render assigns a `*.onrender.com` URL.

5. Configure your agent with the Render URL + API key.

---

## Fly.io

1. Create a `fly.toml` in the project root:

```toml
app = "figma-converter"

[build]
  builder = "heroku/buildpacks:20"

[env]
  FIGMA_MCP_TRANSPORT = "sse"
  FIGMA_MCP_HOST = "0.0.0.0"

[http_service]
  internal_port = 3845
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 1
```

2. Set secrets:

```bash
fly secrets set FIGMA_API_TOKEN=<your-token>
fly secrets set FIGMA_MCP_API_KEY=<your-key>
```

3. Deploy:

```bash
fly launch
fly deploy
```

4. Configure your agent with the `*.fly.dev` URL + API key.

---

## Docker (any platform)

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 3845

CMD ["python", "mcp_server.py", "--transport", "sse", "--port", "3845"]
```

```bash
docker build -t figma-converter .
docker run -d \
  -p 3845:3845 \
  -e FIGMA_API_TOKEN=<token> \
  -e FIGMA_MCP_API_KEY=<key> \
  -e FIGMA_MCP_TRANSPORT=sse \
  figma-converter
```

---

## Health check

The SSE endpoint at `/sse` accepts long-lived connections. There is no dedicated
health endpoint; a successful SSE upgrade confirms the server is running.

---

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Agent gets `401 Unauthorized` | `FIGMA_MCP_API_KEY` is set but the `Authorization` header is missing or wrong |
| Agent gets `ECONNREFUSED` | Port not exposed or firewall blocking access |
| Agent gets `404 Not Found` | Wrong URL path — should end with `/sse` |
| SSE connection drops | Platform idle timeout; set `auto_stop_machines = false` on Fly.io |
