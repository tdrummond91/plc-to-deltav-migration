#!/usr/bin/env bash
# One-time, explicit public package/model installation. No plant text is uploaded.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
exec uv run --project python-parser --locked --extra translation python -B -m plc_workbench.setup_translation "$@"
