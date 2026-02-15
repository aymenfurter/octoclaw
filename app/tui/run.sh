#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v bun &> /dev/null; then
  echo "Error: Bun is required (OpenTUI dependency). Install from https://bun.sh"
  exit 1
fi

if [ ! -d "node_modules" ]; then
  echo "Installing dependencies..."
  bun install
fi

bun run src/index.ts "$@"
RET=$?

# Force-reset terminal in case TUI didn't clean up mouse tracking
printf '\e[?1000l\e[?1002l\e[?1003l\e[?1006l\e[?25h\e[0m'
stty sane 2>/dev/null || true

exit $RET
