#!/usr/bin/env bash
set -euo pipefail

# Container-only entrypoint
DATA_DIR="${OCTOCLAW_DATA_DIR:-/data}"
mkdir -p "$DATA_DIR"
export HOME="$DATA_DIR"

# Clean stale copilot CLI runtime cache (forces re-download of matching version)
COPILOT_INSTALLED="$(copilot --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo '')"
if [[ -n "$COPILOT_INSTALLED" && -d "$DATA_DIR/.copilot/pkg" ]]; then
    # Remove mismatched versions in both arch-specific and universal directories
    find "$DATA_DIR/.copilot/pkg" -mindepth 2 -maxdepth 2 -type d \
        ! -name "$COPILOT_INSTALLED" -exec rm -rf {} + 2>/dev/null || true
    echo "Copilot CLI v${COPILOT_INSTALLED} — runtime cache cleaned."
fi

# Azure CLI config on persistent volume so az login survives restarts
export AZURE_CONFIG_DIR="$DATA_DIR/.azure"

# Load .env from the persistent data volume
if [[ -f "$DATA_DIR/.env" ]]; then
    set -a
    source "$DATA_DIR/.env"
    set +a
fi

# Resolve Key Vault references (replaces @kv:* env vars with real values)
# This runs BEFORE the main process so the agent itself never sees the KV client.
if [[ -n "${KEY_VAULT_URL:-}" ]]; then
    echo "Resolving secrets from Key Vault..."
    eval "$(python -m octoclaw.keyvault_resolve)"
fi

AUTH_DONE="$DATA_DIR/.copilot-auth/.authenticated"

# --- GitHub Authentication ------------------------------------------------

if [[ -n "${GITHUB_TOKEN:-}" ]] || [[ -n "${GH_TOKEN:-}" ]]; then
    echo "Using token from environment."
elif [[ -f "$AUTH_DONE" ]]; then
    echo "Already authenticated (cached)."
else
    echo "GitHub not authenticated -- use the web admin UI to authenticate."
fi

# --- Launch ---------------------------------------------------------------

MODE="${OCTOCLAW_MODE:-auto}"

if [[ "$MODE" == "cli" ]]; then
    echo ""
    echo "Starting interactive CLI..."
    exec octoclaw
elif [[ "$MODE" == "bot" ]]; then
    export ADMIN_PORT="${ADMIN_PORT:-${BOT_PORT:-8080}}"
    echo ""
    echo "Starting octoclaw (bot mode) on port ${ADMIN_PORT}..."
    exec octoclaw-admin
else
    ADMIN_PORT="${ADMIN_PORT:-8080}"

    echo ""
    echo "Starting octoclaw admin on port ${ADMIN_PORT}..."
    # Use the env var (already resolved by keyvault_resolve above)
    if [[ -n "${ADMIN_SECRET:-}" ]]; then
        echo "  Admin UI:      http://localhost:${ADMIN_PORT}/?secret=${ADMIN_SECRET}"
    else
        echo "  Admin UI:      http://localhost:${ADMIN_PORT}"
        echo "  (admin secret will be auto-generated on first start)"
    fi
    echo "  Bot messages:  http://localhost:${ADMIN_PORT}/api/messages"
    echo ""
    exec octoclaw-admin
fi
