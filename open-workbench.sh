#!/usr/bin/env bash
# Explicit interactive application; no Git calls, listener or automatic analysis.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
exec uv run --project python-parser --locked python -B -m plc_workbench.workspace "$@"
