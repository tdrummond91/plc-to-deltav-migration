#!/usr/bin/env bash
# Run the already checked-out code; repository synchronization is manual.
set -euo pipefail

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    cat <<'USAGE'
Usage: bash ./run-work-check.sh [SOURCE.L5X]

Run parser tests, analyze the local source, and save results locally.
No automatic fetch, pull, staging, commit or push. Review before sharing manually.
A bare filename is found under confidential/plc-code/. An explicit path also works.
The first run needs a source; later runs remember its path on this machine only.
Run on any clean named branch, including main. No upstream connection is required.
USAGE
    exit 0
fi

# Match the Python workflow: anchor Git to this checkout while retaining SSH
# and authentication settings supplied by the user's shell.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY \
    GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_COMMON_DIR GIT_CEILING_DIRECTORIES \
    GIT_DISCOVERY_ACROSS_FILESYSTEM GIT_IMPLICIT_WORK_TREE GIT_PREFIX \
    GIT_NAMESPACE GIT_SHALLOW_FILE GIT_GRAFT_FILE GIT_REPLACE_REF_BASE

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
script_root="$(pwd -P)"
repo_root="$(git rev-parse --show-toplevel)"
if [[ "$(cd -- "$repo_root" && pwd -P)" != "$script_root" ]]; then
    printf '%s\n' 'Run the script from its original repository checkout.' >&2
    exit 1
fi
if [[ -n "$(git status --porcelain --untracked-files=all)" ]]; then
    printf '%s\n' 'The checkout has local changes. Commit or move them before running this script.' >&2
    exit 1
fi
git symbolic-ref --quiet --short HEAD >/dev/null || {
    printf '%s\n' 'Check out a named branch before running this script; detached HEAD is not supported.' >&2
    exit 1
}
command -v uv >/dev/null || {
    printf '%s\n' 'Install uv and make it available in Git Bash before running this script.' >&2
    exit 1
}

exec uv run --project python-parser --locked python -B -m plc_workbench.work_check "$@"
