---
title: "Azure"
weight: 2
---

# Azure Container Apps Deployment

When you select **Azure Container Apps** in the TUI target picker, the TUI provisions all Azure infrastructure, pushes the image, and deploys a persistent Container App. Unlike Local Docker, the container keeps running after you exit the TUI.

## Prerequisites

- **Azure CLI** (`az`) installed and logged in
- **Docker** running locally (for the image build)

If `az` is not installed or you are not logged in, the ACA option is greyed out in the target picker with a status message.

## How It Works

1. **Launch the TUI** with `./scripts/run-tui.sh` (see [Quickstart](/getting-started/quickstart/))
2. **Select "Azure Container Apps"** from the target picker
3. The TUI provisions all infrastructure and deploys the container
4. Once the health check passes, you land in the TUI dashboard
5. The container keeps running after you exit -- reconnect anytime by relaunching the TUI

![TUI deployment target selection](/screenshots/tui-deployoptions.png)

The TUI handles the entire provisioning and deployment sequence automatically, streaming progress in real time.

## What Gets Provisioned

The TUI creates the following Azure resources in a single resource group:

| Resource | Purpose |
|---|---|
| **Resource Group** | Contains all deployment resources (default: `octoclaw-acac-rg`) |
| **Azure Container Registry** | Stores the Octoclaw Docker image |
| **VNet + Subnet** | Network isolation for the Container Apps environment |
| **Premium FileStorage account** | NFS-backed persistent storage for `/data` |
| **NFS File Share** | Mounted into the Container App at `/data` |
| **Container Apps Environment** | Hosts the Container App with VNet integration |
| **Container App** | Runs the Octoclaw container (1 CPU, 2 GiB RAM, 1 replica) |

The deployment sequence is:

1. Create the resource group
2. Create or reuse the Azure Container Registry
3. Build the Docker image for `linux/amd64`
4. Push the image to ACR
5. Create the VNet and subnet (with storage service endpoints and ACA delegation)
6. Create the Premium FileStorage account with NFS share
7. Create the Container Apps environment with VNet integration
8. Link the NFS storage to the environment
9. Create the Container App with the NFS volume mounted at `/data`
10. Restart the revision to activate storage and retrieve the FQDN

All resource names, the admin secret, and the deployment configuration are saved to `~/.octoclaw-aca.json` so the TUI can reconnect on subsequent launches.

## Reconnecting

When you relaunch the TUI with an existing ACA deployment, it detects the saved configuration and offers to reconnect instead of redeploying. The TUI verifies the Container App still exists and connects directly, skipping the build and provisioning steps.

## Persistent Storage

Unlike Local Docker (which uses a Docker named volume), the ACA deployment uses Azure Premium FileStorage with NFS. This provides:

- Persistent data that survives container restarts and redeployments
- Network-attached storage accessible from the Container App inside the VNet
- The same `/data` mount path used by the entrypoint script

The storage holds the same data as the local deployment: configuration, auth state, skills, plugins, memory, and scheduler state.
