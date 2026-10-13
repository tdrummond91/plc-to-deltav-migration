# Work-machine reference check

Use **feat/source-references-pc**. It starts from the returned summary reports
and includes the earlier review notes. This check remains Phase 1: declared tag
roots and alias chains, not engineering classifications or PCSD generation.

## Get the branch

Open Git Bash in the existing repository:

```bash
git fetch origin
git status --short --branch
git switch --track origin/feat/source-references-pc
```

Preserve any local edits before switching. If the local branch already exists,
use `git switch feat/source-references-pc`, then
`git merge --ff-only origin/feat/source-references-pc`. If a fast-forward fails,
inspect the divergence; do not reset or force-push. Routine report updates use
new commits and filenames so both computers retain their evidence.

## Check tools and generate one portable report

```bash
uv sync --project python-parser --locked
uv run --project python-parser python -B -m unittest discover -s python-parser/tests
uv run --project python-parser python -B -m unittest discover -s tools/l5x_inspect/tests
```

Use the readable L5X that produced summary-002.json: 4,606 rungs, 17,874
instructions, 6,307 tags, 120 modules and no encoded regions. The earlier
summary-001 had no exposed rungs and is retained as comparison evidence.
Replace YOUR_READABLE_EXPORT.L5X below with the local filename:

```bash
report="public/inspection/reference-summary-$(date -u +%Y%m%dT%H%M%SZ).json"
uv run --project python-parser plc reference-summary \
  "confidential/plc-code/YOUR_READABLE_EXPORT.L5X" --output "$report"
reference_exit=$?
printf 'Reference exit: %s\nReport: %s\n' "$reference_exit" "$report"
```

Exit **3 is expected** for this source: the known SFC/empty-routine gaps remain,
and some reference forms/instructions are deliberately unsupported. The file
is still useful. Exit 0 means the bounded scope is covered, not that all process
behavior is understood. Exit 1/2 indicates failure/usage; investigate before
committing a presumed new report. Existing reports cannot be overwritten.

The file contains source counts under `source_summary` and new aggregate groups
`symbols`, `aliases`, `operands` and `coverage`. Code provenance is nested at
`source_summary.tool_revision`; it should say `clean` for a comparable run.
No identifiers, process values, per-rung examples or individual dependency links
are included. These aggregate counts are approved for sync under D026.

Interpret the counters carefully:

- `root_bound`: a declared root/alias chain was found; members, dimensions,
  access rules and instruction effects have not been validated.
- `unresolved`: no applicable declaration was found. Missing module-tag modeling
  or partial export context can cause this; it does not prove a source typo.
- `ambiguous`: more than one declaration matched the same case-insensitive name.
- `unsupported_instruction`, `unsupported_expression`, `unsupported_address`:
  evidence was preserved privately but this slice did not interpret it.
- `alias_cycle`, `alias_depth_limit`: alias traversal could not complete safely.
- `literal` and `non_data`: recognized values/label positions, without tag links.

## Optional private drill-down

To read individual declarations, alias chains and operand occurrences locally:

```bash
uv run --project python-parser plc references \
  "confidential/plc-code/YOUR_READABLE_EXPORT.L5X" \
  --workspace "confidential/workspaces/reference-check"
```

The new run contains snapshot.L5X, inventory.json, overview.txt, references.json,
references.txt and manifest.json. Open references.txt for the readable view,
or references.json for structured evidence; rung/instruction IDs link back to
inventory.json in the same run. These files stay private. The command copies the
input snapshot into the private run and never edits the original or an old run.

## Return through Git

Commit only the new aggregate file after successful generation:

```bash
git status --short --branch
git add -- "$report"
git commit --only -m "test(references): add work-machine aggregate results" -- "$report"
git fetch origin
git merge --ff-only origin/feat/source-references-pc
git push origin feat/source-references-pc
```

If integration fails, stop and inspect the history before pushing. No force-push
is needed. Tell this chat that it is pushed and whether the two test suites
passed; no pasted terminal output or proprietary source is requested.

The returned aggregate will tell us whether the next slice should expand module
declarations, address/expression recognition or instruction-role coverage before
attempting read/write relationships and engineering classifications.
