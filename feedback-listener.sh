#!/usr/bin/env bash
# Local PC controls. This does not install a listener on the work machine.
set -euo pipefail
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ -n "${PLC_LISTENER_STATE_DIR:-}" ]]; then
  state_dir=$PLC_LISTENER_STATE_DIR
else
  state_dir="$(cygpath -u "${LOCALAPPDATA:?LOCALAPPDATA is required}")/PLCWorkbench/feedback-listener"
fi
cd -- "$repo_dir"
if [[ $# -eq 0 ]]; then set -- status; fi
exec uv run --project python-parser --locked python -B tools/feedback_listener/listener.py \
  --state-dir "$state_dir" "$@"
