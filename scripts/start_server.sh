#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${VENV_DIR:-${PROJECT_ROOT}/.venv}"
"${SCRIPT_DIR}/bootstrap_venv.sh"
cd "${PROJECT_ROOT}"
exec "${VENV_DIR}/bin/python" -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
