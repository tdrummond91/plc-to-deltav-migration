#!/usr/bin/env bash
# Prepare the already imported analysis locally. No Git or model downloads.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
exec uv run --project python-parser --locked python -B -m plc_workbench.prepare_english "$@"
