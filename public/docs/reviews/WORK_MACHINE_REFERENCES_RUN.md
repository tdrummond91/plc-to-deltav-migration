# Work-machine check: local results and manual publication

Use **main** for the consolidated baseline. This remains Phase 1:
source inventory, module I/O declarations, declared tag roots and alias chains. Engineering classifications,
editable corrections, PCSD and FHX generation are still later work.

## Manual runs

The development listener remains disabled and paused; normal manual parser
checks are separate from that service. Update or clone the code manually, then
open Git Bash in the repository root on `main` or a chosen development branch:

```bash
bash ./run-work-check.sh YOUR_READABLE_EXPORT.L5X
# Later runs in this checkout remember the source path:
bash ./run-work-check.sh
```

The first run accepts the readable export's local filename or path. A fresh
clone has no remembered source selection, so supply it again on that first run.

A bare filename is looked up under `confidential/plc-code/`. An explicit relative
or absolute path also works; quote paths with spaces. The selected path is shown
locally and saved in this checkout's Git metadata, outside tracked files. The
script never embeds it in the shared report. Use the readable export that produced
summary-002 and the returned reference summary: 4,606 rungs, 17,874 instructions,
6,307 tags, 120 modules and no encoded regions.

The script uses the code already checked out and locked Python dependencies. It
runs explicit parser/helper test allowlists in separate processes, analyzes the
saved source and writes local reports. It never fetches, pulls, stages, commits
or pushes. Passing a different filename/path replaces the machine-local source
selection for future runs.

Git, Git Bash and uv must already be available. The checkout must be clean and
on a named branch (including `main`); an upstream and GitHub authentication are not required
by the runner. Local changes stop the script without discarding anything.
Dependency setup may still use uv's configured package sources.

The work-machine test lists exclude listener, Windows process-host, Bash
bootstrap and Git-fixture tests. Full unittest discovery remains the development
check. The report retains schema 1 and its tested SHA identifies which suite
implementation ran; older reports can therefore have a broader test scope.

## What it produces

| Location | Contents |
|---|---|
| `public/inspection/local/work-check-<run-id>.json` | Git-ignored local aggregate: tested code revision, both suites' counts/statuses and bounded failed test IDs, analysis status and the reference/structural aggregate |
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
any later manually created report commit is intentionally different.

## Manual review and publication

Review the saved aggregate. To share a result,
manually copy or move only its final JSON from `public/inspection/local/` into
`public/inspection/`, then explicitly stage, commit and push that file. Leaving
the report in `local/` keeps it excluded from ordinary Git staging. Do not share
the private log folder, workspace, source export or temporary pending files.
The runner does not perform any of these publication actions.

## Reading completion and failures

`Check status: partial` is expected for the current source and exits successfully.
Known SFC/empty-routine gaps and unsupported reference forms remain visible. Partial
means usable results with gaps, not a failed save. A complete result also refers
only to the implemented analysis scope, not all process behavior.

If either suite fails, both suites are still attempted, source analysis is skipped,
and the test-results report is saved locally. The script exits 1 after reporting
that failure. Analysis failures also produce a failed report with a fixed reason
code; detailed diagnostics remain local. Setup/source-selection errors occur
before the check and do not produce a test-results report. Changes to the branch,
commit or tracked/untracked files during the run stop normal completion.

A local save does not send anything to the development PC. A report becomes
available there only after manual publication. No copied terminal output,
manual test summary or proprietary source is needed. The listener remains
disabled; do not assume it will process a newly published result automatically.

Interpret the reference counters as follows:

- `root_bound`: a declared root/alias chain was found; members, dimensions,
  access rules and instruction effects are not validated.
- `unresolved`: no applicable declaration was found. Missing module-tag modeling
  for unsupported topologies or partial export context can cause this; it does
  not prove a source typo. Fixed `by_reason` counts explain the supported cases;
  `colon_root_not_declared` only describes address syntax, not proven I/O intent.
- `ambiguous`: multiple declarations matched the same case-insensitive name.
- `unsupported_instruction`, `unsupported_expression`, `unsupported_address`:
  private evidence was retained but this slice did not interpret it.
- `alias_cycle`, `alias_depth_limit`: alias traversal could not complete.
- `literal` and `non_data`: recognized values/label positions, without tag links.

Manual commands remain available in the [Python README](../../../python-parser/README.md).
See [runner implementation and validation](WORK_CHECK_RUNNER_REVIEW.md) for the
automated workflow's contract and test evidence.

The module/I/O update adds `module_io` naming/provenance counts and fixed reason
counts under both `aliases` and `operands`. Source module ports, connections and
input/output/config declarations are counted separately from ordinary tags.
Actual names, topology and per-reference detail remain in the private reports.
See [module/I/O review](MODULE_IO_REVIEW.md) for comparison targets and
[listener operation](FEEDBACK_LISTENER.md) for its local status controls.

The report returned in `b58af78` already contains reference schema 3 with
`operands.malformed_address_shapes` and awaits parser analysis. No new run is
needed merely to obtain that diagnostic.
These seven closed counters partition the malformed-address operand total;
they do not change parsing or binding. Alias-target failures have their own
bucket, and direct spellings are grouped by fixed precedence. Actual addresses,
values and individual relationships remain private. Compare the histogram sum
with the previous 868 occurrences and review any change in existing statuses or
reasons before interpreting the new counts. See [address-shape review](ADDRESS_SHAPE_REVIEW.md).
