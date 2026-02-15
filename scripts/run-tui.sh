#!/usr/bin/env bash
# Launch the Octoclaw TUI (app/tui) -- the updated CLI that can manage
# the backend and frontend from an interactive terminal UI.
#
# Usage:
#   ./scripts/run-tui.sh          # admin mode (default)
#   ./scripts/run-tui.sh bot      # headless bot mode
#   ./scripts/run-tui.sh --help
set -euo pipefail

exec "$(dirname "$0")/../app/tui/run.sh" "$@"
