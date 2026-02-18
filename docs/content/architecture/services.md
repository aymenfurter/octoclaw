---
title: "Services Layer"
weight: 4
---

# Services Layer

The services layer provides infrastructure management, secret handling, and external integrations.

## Tunnel Service

**Module**: `app/runtime/services/tunnel.py`

Manages a Cloudflare quick-tunnel subprocess to expose local endpoints publicitly.

| Feature | Description |
|---|---|
| Auto-start | Launched during server startup |
| URL detection | Parses tunnel URL from subprocess output |
| Health monitoring | Detects tunnel disconnections |
| Restricted mode | `TUNNEL_RESTRICTED=true` limits access to bot/voice endpoints |

The tunnel URL is used as the Bot Framework messaging endpoint and ACS callback URL.

## Key Vault Service

**Module**: `app/runtime/services/keyvault.py`

Integrates with Azure Key Vault for secret management.

| Feature | Description |
|---|---|
| `@kv:` resolution | Secrets prefixed with `@kv:secret-name` are resolved at startup |
| Write-back | `Settings.write_env()` stores secrets in Key Vault and writes `@kv:` references |
| Firewall allowlisting | Automatically adds current IP to Key Vault firewall rules |
| Credential chain | Uses `AzureCliCredential` or `DefaultAzureCredential` |

## Provisioner

**Module**: `app/runtime/services/provisioner.py`

Orchestrates full infrastructure lifecycle:

1. **Start tunnel** -- establish Cloudflare tunnel
2. **Deploy bot** -- create Azure Bot resource with the tunnel URL
3. **Configure channels** -- set up Teams, Telegram, and other channels
4. **Decommission** -- reverse all steps on shutdown

## Deployer

**Module**: `app/runtime/services/deployer.py`

Azure Bot resource management:

| Operation | Description |
|---|---|
| Create | Register a new Azure Bot with the tunnel endpoint |
| Update | Change the messaging endpoint URL |
| Delete | Remove the Azure Bot resource |

## Azure CLI Wrapper

**Module**: `app/runtime/services/azure.py`

Wraps `az` CLI commands for:

- Bot creation and deletion
- Channel management (Teams, Telegram)
- Resource group operations
- Subscription queries

## Other Services

| Module | Purpose |
|---|---|
| `github.py` | GitHub API integration |
| `foundry_iq.py` | Azure AI Foundry IQ indexing and search |
| `resource_tracker.py` | Azure resource tracking and cost awareness |
| `misconfig_checker.py` | Configuration auditing and validation |
