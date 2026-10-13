#!/usr/bin/env bash
# Keep this bootstrap small: Python is loaded only after the pull completes.
set -euo pipefail

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    cat <<'USAGE'
Usage: bash ./run-work-check.sh [SOURCE.L5X]

Pull, run both test suites, analyze the local source, and push aggregate results.
A bare filename is found under confidential/plc-code/. An explicit path also works.
The first run needs a source; later runs remember its path on this machine only.
Run on a clean branch ending in -pc with its matching origin upstream.
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
branch="$(git symbolic-ref --quiet --short HEAD)" || {
    printf '%s\n' 'Check out a branch ending in -pc before running this script.' >&2
    exit 1
}
if [[ "$branch" != *-pc ]]; then
    printf '%s\n' 'The work-check branch must end in -pc.' >&2
    exit 1
fi
upstream="$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}')" || {
    printf '%s\n' 'This branch needs its matching origin upstream.' >&2
    exit 1
}
if [[ "$upstream" != "origin/$branch" ]]; then
    printf '%s\n' 'This branch must track the same branch name on origin.' >&2
    exit 1
fi
command -v uv >/dev/null || {
    printf '%s\n' 'Install uv and make it available in Git Bash before running this script.' >&2
    exit 1
}

git pull --ff-only
exec uv run --project python-parser --locked python -B -m plc_workbench.work_check "$@"
