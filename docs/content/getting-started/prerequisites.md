---
title: "Prerequisites"
weight: 2
---

# Prerequisites

## Required

These are needed regardless of which deployment target you choose.

| Dependency | Version | Purpose |
|---|---|---|
| [Bun](https://bun.sh) | latest | Runs the TUI (`app/tui`) |
| [Docker](https://www.docker.com/) | 20+ | Builds and runs the Octoclaw container |
| Git | any | Cloning the repository |

The TUI installs its own Node dependencies automatically via `bun install` on first run.

> The container image includes Python, Node.js, the frontend build, and all runtime dependencies. You do not need to install them on your host machine.

## Optional -- Azure Container Apps Target

If you want to deploy to Azure instead of running locally, you also need:

| Dependency | Purpose |
|---|---|
| [Azure CLI](https://aka.ms/installazurecli) (`az`) | Provisioning ACA, ACR, storage, and VNet resources |
| Azure subscription | Hosting the Container App and associated resources |

The TUI checks for `az` availability and login status automatically. If `az` is not found or you are not logged in, the ACA target is disabled in the picker with a descriptive message.

Log in before launching the TUI:

```bash
az login
```

## Optional -- Extended Features

These are not required for basic operation but enable additional capabilities once octoclaw is running. Items marked **auto-deployed** are set up automatically during the initial deployment; the rest require manual configuration.

| Service / Tool | Required For | Deployed |
|---|---|---|
| Cloudflare CLI (`cloudflared`) | Tunnel to expose bot endpoint | **auto-deployed** |
| Playwright (`npx playwright install chromium`) | Browser automation MCP server | **auto-deployed** |
| Azure Bot Service | Telegram channel messaging | **auto-deployed** |
| Azure Communication Services | Inbound and outbound voice calls | manual |
| Azure Key Vault | Centralized secret management | manual |
| Azure Container Apps Dynamic Sessions | Sandboxed code execution | manual |
| Azure OpenAI | Realtime voice model (gpt-4o-realtime) | manual |
| GitHub CLI (`gh`) | GitHub MCP server plugin | manual |

These services are configured through the TUI setup screen or the web dashboard after initial deployment.

## Verification

Open the admin web dashboard and navigate to the **Preflight Check** page. It validates all required and optional dependencies inside the running container and shows their status at a glance.
