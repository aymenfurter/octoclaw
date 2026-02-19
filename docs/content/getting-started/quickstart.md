---
title: "Quickstart"
weight: 1
---

# Quickstart

Get Polyclaw running in under five minutes using the TUI.

## 1. Clone the Repository

```bash
git clone https://github.com/aymenfurter/polyclaw.git
cd polyclaw
```

## 2. Install Bun

The TUI runs on [Bun](https://bun.sh). If you do not have it installed:

```bash
curl -fsSL https://bun.sh/install | bash
```

## 3. Install Docker

The TUI builds and runs Polyclaw inside a Docker container. Make sure Docker is installed and the daemon is running:

```bash
docker --version
```

If you do not have Docker, install [Docker Desktop](https://www.docker.com/products/docker-desktop/) or use your system package manager.

## 4. Launch the TUI

```bash
./scripts/run-tui.sh
```

The script installs TUI dependencies automatically on first run, then launches the interactive interface.

## 5. Accept the Disclaimer

On first launch, a risk disclaimer is shown. Read it carefully and type `accept` to continue. This only appears once -- the acceptance is persisted to disk.

## 6. Choose a Deployment Target

The target picker presents two options:

**Local Docker** -- Builds the image locally and runs a container. The container stops when you exit the TUI. This is the default and requires only Docker.

**Azure Container Apps** -- Deploys to Azure with a persistent container that keeps running after the TUI exits. Requires the Azure CLI (`az`) with an active login. If `az` is not installed or you are not logged in, this option is greyed out with a status message.

Use the arrow keys to select a target and press Enter.

![TUI deployment target selection](/screenshots/tui-deployoptions.png)

## 7. Wait for Build and Deploy

The TUI streams build output in real time. For Local Docker, this builds the image and starts the container. For ACA, it additionally pushes to Azure Container Registry and provisions the Container App.

Once the server passes its health check, you are dropped into the TUI dashboard with:

- Live container logs
- Interactive chat with the agent
- Plugin and skill management
- Scheduler controls
- Session browser

The following services are deployed automatically during this step:

- **Cloudflare tunnel** -- public endpoint for webhooks, no manual setup required
- **Playwright browser** -- headless browser for web-based skills
- **Bot Service** -- Bot Framework registration for Telegram and other channels

All other integrations (voice via ACS, Key Vault secrets, additional MCP servers) are optional and can be configured later through the [Setup Wizard](/getting-started/setup-wizard/) or [Configuration](/configuration/).

![TUI interactive chat](/screenshots/tui-chat.png)

## 8. Open the Web Dashboard

The admin web dashboard is available at the URL shown in the TUI (typically `http://localhost:8080` for local, or the ACA FQDN for Azure). The admin secret is displayed in the TUI output.

## Next Steps

- [Prerequisites](/getting-started/prerequisites/) -- full dependency reference
- [Setup Wizard](/getting-started/setup-wizard/) -- identity and channel configuration
- [Configuration](/configuration/) -- environment variable reference
