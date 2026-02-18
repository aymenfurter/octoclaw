---
title: "Docker"
weight: 1
---

# Local Docker Deployment

When you select **Local Docker** in the TUI target picker, the TUI builds the Docker image, starts a container, and connects to it automatically. The container lifecycle is tied to the TUI process -- it stops when you exit.

## How It Works

1. **Launch the TUI** with `./scripts/run-tui.sh` (see [Quickstart](/getting-started/quickstart/))
2. **Select "Local Docker"** from the target picker
3. The TUI builds the image and starts a container
4. Once the health check passes, you land in the TUI dashboard

![TUI deployment target selection](/screenshots/tui-deployoptions.png)

The TUI handles the full build-deploy-healthcheck cycle and streams build output in real time.

## What Gets Built

The Dockerfile uses a two-stage build:

| Stage | Base Image | What It Does |
|---|---|---|
| **Frontend** | `node:22-slim` | Runs `npm ci` and `npm run build` to produce the Vite/React dashboard |
| **Runtime** | `python:3.12-slim` | Installs the Python runtime, Node.js 22, and all system tools |

### Bundled Tools

The image includes everything the agent needs to operate:

- **GitHub Copilot CLI** (`@github/copilot`) -- the agent engine
- **GitHub CLI** (`gh`) -- authentication
- **Azure CLI** (`az`) -- infrastructure provisioning and bot registration
- **Cloudflare tunnel** (`cloudflared`) -- automatic public endpoint for webhooks
- **Playwright MCP + Chromium** -- headless browser for web-based skills
- **Python runtime** -- the Octoclaw server, agent, and all backend services
- **React dashboard** -- embedded frontend static assets

### Ports

| Port | Service |
|---|---|
| `8080` | Admin server (configurable via `ADMIN_PORT`) |
| `3978` | Bot Framework endpoint |

## Persistent Data

The TUI creates a Docker named volume (`octoclaw-data`) mounted at `/data` inside the container. This volume persists across container restarts and stores:

- Agent configuration and `.env` file
- GitHub and Azure CLI authentication state
- Skills, plugins, and MCP server configs
- Memory, conversation history, and scheduler state
- Key Vault cache

Because the volume is a named Docker volume, your data survives even when the container is stopped and recreated on the next TUI launch.

## Container Entrypoint

When the container starts, the entrypoint script runs the following sequence automatically:

1. Sets `HOME` to the data directory for consistent tool configuration
2. Cleans stale Copilot CLI runtime cache (keeps only the matching version)
3. Loads environment variables from the persisted `.env` file
4. Resolves any `@kv:` Key Vault secret references (if configured)
5. Checks GitHub authentication state (token, cached session, or deferred to web UI)
6. Starts the server (`octoclaw-admin`)

## What Happens on Exit

When you exit the TUI (Ctrl+C or `/quit`), the container is stopped and removed. The named volume is preserved, so the next launch picks up where you left off -- same configuration, same auth state, same data.

## Integrations Deployed Automatically

These services start automatically inside the container without any manual configuration:

| Service | Description |
|---|---|
| **Cloudflare tunnel** | Exposes a public HTTPS endpoint for Bot Framework webhooks |
| **Playwright browser** | Headless Chromium for web-based skills and MCP servers |
| **Bot Service** | Azure Bot registration using the tunnel URL (if Azure CLI is authenticated) |

All other integrations (voice, Key Vault, sandbox, additional MCP servers) are optional and configured through the [Setup Wizard](/getting-started/setup-wizard/) or the [Web Dashboard](/deployment/#user-interfaces) after deployment.
