# Work-machine check: local results and manual publication

Use **main** for the consolidated baseline. The next rack-candidate check is on
**feat/bounded-operand-example-pc**. Pull that branch manually, then run the script. This remains Phase 1:
source inventory, module I/O declarations, declared tag roots and alias chains. Engineering classifications,
editable corrections, PCSD and FHX generation are still later work.

Current returned evidence: `1195d40` tested `112ee82`, passed 177 application
cases (one skip) and 139 helpers, and confirms malformed addresses 868 to 0,
non-data 0 to 868, and unsupported addresses 870 to 2. Other source/reference
counters are unchanged; the diagnostic sample is null. See
[TIMER_PLACEHOLDER_REVIEW.md](TIMER_PLACEHOLDER_REVIEW.md) for results and limits.
The new rack slice keeps work-check schema 2 and emits reference/source schemas
5/4. It needs a work-machine run to measure candidate matches for the remaining
99 unresolved aliases and 320 operand occurrences. Ordinary binding counts stay
unchanged for an unchanged export. See [rack review](RACK_CANDIDATE_REVIEW.md).

## Manual runs

The development listener remains disabled and paused. Its files are excluded
from the tracked project; normal manual parser checks do not require them.
Update or clone the code manually, then
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
saved source and automatically stages and commits only its new validated
feedback report. It never fetches, pulls or pushes. Passing a different
filename/path replaces the machine-local source
selection for future runs.

Git, Git Bash and uv must already be available. The checkout must be clean and
on a named branch (including `main`); an upstream and GitHub authentication are not required
by the runner. A configured Git author identity is needed for the local commit.
Local changes stop the script without discarding anything.
Dependency setup may still use uv's configured package sources.

The work-machine test lists exclude listener, Windows process-host, Bash
bootstrap and Git-fixture tests. Full unittest discovery remains the development
check. New reports use schema 2 and their tested SHA identifies which suite
implementation ran; older reports can therefore have a broader test scope.

## What it produces

| Location | Contents |
|---|---|
| `public/inspection/work-check-<run-id>.json` | Automatically committed feedback: tested revision, suite results, reference/structural counts, and at most one actual mystery operand with instruction/argument position |
| `confidential/work-checks/<run-id>/` | Local test logs and structured results; analysis exception details if needed |
| `confidential/workspaces/work-check/<new-run>/` | Local snapshot.L5X, inventory.json, overview.txt, references.json, references.txt and manifest.json |
| Git metadata `plc-work-check.json` | Local remembered source path; not committed or pushed |

Open `overview.txt` for the source overview and `references.txt` for declarations,
alias chains, operand occurrences and rack candidate lookups. Their JSON counterparts preserve structured
records and source links for later analysis. Every run gets new output locations;
the original source and previous runs are preserved.

The public report includes at most one actual operand in `diagnostic_sample`,
with its standard opcode and zero-based argument position. The operand can
contain a real name/value; Tyler authorized this bounded example to investigate
unknown syntax. It is limited to 128 printable characters, with no full rung,
source filename/hash, routine, neighboring logic or individual reference links.
Repeated unchanged runs select the same eligible example. Null means no eligible
example was available or analysis did not succeed. The reference aggregate
is at `analysis.reference_summary`, with the structural summary nested beneath
`source_summary`. The top-level `tool_revision` identifies the tested code commit;
the automatically created report commit is intentionally different.

`analysis.reference_summary.rack_candidates` is the new comparison section.
It counts named/unavailable rack declarations and match statuses separately for
aliases, direct operands and alias-mediated operands. `unique_candidate` is a
possible logical declaration with unexamined backing; `candidate_names_unavailable`
is inconclusive. Do not expect `root_bound` to increase in this diagnostic slice.

## Manual review and publication

Review the saved feedback report, then publish the already committed result:

```bash
git push
```

No manual copy, staging or commit step is needed. Older reports saved by the
previous runner under `public/inspection/local/` remain ignored and are not
included automatically. The private log folder, workspace and source export
are never included in the report commit. The runner does not contact a remote.

## Reading completion and failures

`Check status: partial` is expected for the current source and exits successfully.
Known SFC/empty-routine gaps and unsupported reference forms remain visible. Partial
means usable results with gaps, not a failed save. A complete result also refers
only to the implemented analysis scope, not all process behavior.

If either suite fails, both suites are still attempted, source analysis is skipped,
and the test-results report is committed locally. The script exits 1 after reporting
that failure. Analysis failures also produce a failed report with a fixed reason
code and a local report commit; detailed diagnostics remain local. Setup/source-selection errors occur
before the check and do not produce a test-results report. Changes to the branch,
commit or tracked/untracked files during the run stop normal completion.

If staging or committing fails, the report remains on disk and the script exits
1 without pushing. The local `git.log` contains the Git error (for example,
missing author identity). Resolve that error before retrying; the retained
uncommitted report must be handled before another run can pass the clean-tree
check. The runner never clears or silently commits unrelated changes.

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
- `literal`: recognized literal values, without tag links.
- `non_data`: labels and recognized timer placeholders, without tag links. A
  timer placeholder supplies no value and does not validate timer configuration.

Manual commands remain available in the [Python README](../../../python-parser/README.md).
See [runner implementation and validation](WORK_CHECK_RUNNER_REVIEW.md) for the
automated workflow's contract and test evidence.

The module/I/O update adds `module_io` naming/provenance counts and fixed reason
counts under both `aliases` and `operands`. Source module ports, connections and
input/output/config declarations are counted separately from ordinary tags.
Actual names, topology and per-reference detail remain in the private reports.
See [module/I/O review](MODULE_IO_REVIEW.md) for comparison targets and
[listener operation](FEEDBACK_LISTENER.md) for its local status controls.

The report returned in `349ee29` supplied `?` at TON argument 1. Report `1195d40`
now confirms schema-4 timer-slot recognition: malformed occurrences fall 868 to
zero while non-data rises by 868. Only two dynamic-index unsupported addresses
remain. The outer work-check stays schema 2. See [timer review](TIMER_PLACEHOLDER_REVIEW.md)
for the complete comparison and remaining Phase 1 gaps.
These seven closed counters partition the malformed-address operand total;
they do not change parsing or binding. Alias-target failures have their own
bucket, and direct spellings are grouped by fixed precedence. Those counters
contain no actual addresses, values or individual relationships; the separate
authorized operand sample is the explicit exception in schema 2. The current histogram sum is zero; later
changes should be compared with the confirmed `1195d40` baseline. See [address-shape review](ADDRESS_SHAPE_REVIEW.md).
