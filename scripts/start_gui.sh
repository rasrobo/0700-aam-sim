#!/usr/bin/env bash
# 0700-AAM Web Simulator Launcher
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PORT="${1:-8080}"

echo "Starting 0700-AAM Sovereign Hardware Simulator GUI..."
python3 "${REPO_ROOT}/scripts/run_web_gui.py" --port "${PORT}"
