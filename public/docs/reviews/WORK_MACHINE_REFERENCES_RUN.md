# Work-machine check: one command

Use the existing **feat/source-references-pc** branch. This remains Phase 1:
source inventory, declared tag roots and alias chains. Engineering classifications,
editable corrections, PCSD and FHX generation are still later work.

## First run

Open Git Bash in the repository. Pull once to receive the new script, then supply
the readable export's local filename (replace YOUR_READABLE_EXPORT.L5X):

```bash
git pull --ff-only
bash ./run-work-check.sh YOUR_READABLE_EXPORT.L5X
```

A bare filename is looked up under `confidential/plc-code/`. An explicit relative
or absolute path also works; quote paths with spaces. The selected path is shown
locally and saved in this checkout's Git metadata, outside tracked files. The
script never embeds it in the shared report. Use the readable export that produced
summary-002 and the returned reference summary: 4,606 rungs, 17,874 instructions,
6,307 tags, 120 modules and no encoded regions.

## Every later run

```bash
bash ./run-work-check.sh
```

The script pulls with `git pull --ff-only`, uses the locked Python dependencies,
runs both test suites in separate processes, analyzes the saved source and writes
the current reports. It then commits and pushes the new aggregate result to the
same branch. There is no separate fetch command or manual staging step. Passing
a different filename/path replaces the machine-local selection for future runs.

Git, Git Bash, uv and working GitHub authentication must already be available.
The checkout must be clean, on a branch ending in `-pc`, with its matching branch
on origin as upstream. Local changes or divergent history stop the script without
discarding anything. A failed push leaves the report committed locally; resolve
the reported Git problem and push normally. Do not force-push.

## What it produces

| Location | Contents |
|---|---|
| `public/inspection/work-check-<run-id>.json` | Automatically committed/pushed: tested code revision, both suites' counts/statuses and bounded failed test IDs, analysis status and the reference/structural aggregate |
| `confidential/work-checks/<run-id>/` | Local test logs and structured results; analysis exception details if needed |
| `confidential/workspaces/work-check/<new-run>/` | Local snapshot.L5X, inventory.json, overview.txt, references.json, references.txt and manifest.json |
| Git metadata `plc-work-check.json` | Local remembered source path; not committed or pushed |

Open `overview.txt` for the source overview and `references.txt` for declarations,
alias chains and operand occurrences. Their JSON counterparts preserve structured
records and source links for later analysis. Every run gets new output locations;
the original source and previous runs are preserved.

The public report contains no source filename, names, values, source hashes,
per-rung examples, raw logs or individual reference links. The reference aggregate
is at `analysis.reference_summary`, with the structural summary nested beneath
`source_summary`. The top-level `tool_revision` identifies the tested code commit;
the report's own later Git commit is intentionally different.

## Reading completion and failures

`Check status: partial` is expected for the current source and exits successfully.
Known SFC/empty-routine gaps and unsupported reference forms remain visible. Partial
means usable results with gaps, not a failed save. A complete result also refers
only to the implemented analysis scope, not all process behavior.

If either suite fails, both suites are still attempted, source analysis is skipped,
and the test-results report is committed/pushed. The script exits 1 after reporting
that failure. Analysis failures also produce a failed report with a fixed reason
code; detailed diagnostics remain local. Pull/setup/source-selection errors occur
before the check and do not produce a test-results report. Changes to the branch,
commit or tracked/untracked files during the run stop automatic publication or push.

Once it says **Pushed work-machine report**, tell this chat it finished. No copied
terminal output, manual test summary or proprietary source is needed. A Git/setup
failure may need a short description if no report reached GitHub.

Interpret the reference counters as follows:

- `root_bound`: a declared root/alias chain was found; members, dimensions,
  access rules and instruction effects are not validated.
- `unresolved`: no applicable declaration was found. Missing module-tag modeling
  or partial export context can cause this; it does not prove a source typo.
- `ambiguous`: multiple declarations matched the same case-insensitive name.
- `unsupported_instruction`, `unsupported_expression`, `unsupported_address`:
  private evidence was retained but this slice did not interpret it.
- `alias_cycle`, `alias_depth_limit`: alias traversal could not complete.
- `literal` and `non_data`: recognized values/label positions, without tag links.

Manual commands remain available in the [Python README](../../../python-parser/README.md).
See [runner implementation and validation](WORK_CHECK_RUNNER_REVIEW.md) for the
automated workflow's contract and test evidence.
