# Work-machine summary check

Use branch **feat/summary-export-pc**. It includes the source inventory and the
bounded summary exporter. Copy/switch the whole branch: the inspection helpers
now share the ladder grammar in python-parser/src.

## Get the branch

Open Git Bash in the existing plc-to-deltav-migration repository:

```bash
git fetch origin
git status --short --branch
```

If the status lists local edits, preserve and resolve them before switching;
do not reset or discard them. For the first checkout of this branch:

```bash
git switch --track origin/feat/summary-export-pc
```

If that local branch already exists, use this instead:

```bash
git switch feat/summary-export-pc
git merge --ff-only origin/feat/summary-export-pc
```

A failed fast-forward means the histories need inspection. Do not force the
update. These commands keep the feature separate from main.

## Check the tools

Run from the repository root. These tests use invented data and public fixtures:

```bash
uv sync --project python-parser --locked
uv run --project python-parser python -B -m unittest discover -s python-parser/tests
uv run --project python-parser python -B -m unittest discover -s tools/l5x_inspect/tests
uv run --project python-parser plc summarize --help
```

The PC validation record is in [SUMMARY_EXPORT_REVIEW.md](SUMMARY_EXPORT_REVIEW.md).
A skipped real-symlink test can reflect Windows account privileges. Any failure
should be investigated before using the report as comparison evidence.

## Generate one candidate summary

Replace only `YOUR_EXPORT.L5X` with the real local filename. This captures and
analyzes the source without changing it. It saves only the aggregate JSON, not
a copied L5X or private inventory. The source still stays on the work machine.

```bash
report="confidential/review-exports/source-summary-$(date -u +%Y%m%dT%H%M%SZ).json"
uv run --project python-parser plc summarize \
  "confidential/plc-code/YOUR_EXPORT.L5X" --output "$report"
summary_exit=$?
printf 'Summary exit: %s\nReport: %s\n' "$summary_exit" "$report"
```

Exit **0** means structurally complete within this reader's scope. Exit **3**
means the summary was saved with partial coverage, for example an SFC routine
that is counted but not interpreted. Both can produce useful review evidence.
Exit **1** is a read/validation/save failure; **2** is a command usage error.
Do not treat a nonzero exit alone as proof that no report was produced.

The command refuses to overwrite an existing report or input. Choose a new name
for each trial. Its atomic publication requires a destination supporting local
hard links (such as this PC's NTFS checkout). If the destination cannot support
them, use an approved local private directory instead; the command fails without
publishing its candidate. Without `--output`, JSON goes to stdout; shell
redirection does not have the command's overwrite protection.
Interrupted runs or cleanup failures can leave `.plc-summary-*.pending` files.
Only the requested final JSON is a published candidate.

## Review and return

Open the file named by `$report` locally. It should contain only:

- Tool/schema/policy versions, code commit and clean/modified/unavailable state.
- Aggregate component counts and routine languages from a fixed vocabulary.
- Parsed/failed/unsupported coverage, approved instruction totals and pooled
  withheld totals for unrecognized names.
- Global ladder measurements and diagnostic counts, with no source locations.

For a comparable run, `tool_revision.worktree` should be `clean`. `modified`
means application code differs from the named commit; `unavailable` means Git
provenance could not be established. Preserve local changes and report that
condition instead of resetting them merely to make this field clean.

The report omits source filenames/paths/hashes, source IDs, tags, descriptions,
operands, XML paths, per-rung records and ladder layouts. Exact aggregate counts
still describe source scale. Review the actual candidate before sharing it.
Return **only the reviewed summary JSON**, plus whether the test suites passed.
Do not return the real L5X or `plc inspect` reports/private run directories.

For an example of the permitted shape, see the independently generated
[synthetic summary](../../examples/source-summary.synthetic.json). Its counts
describe the toy fixture, not a real unit. No GUI, PCSD or FHX conversion is part
of this work-machine check.
