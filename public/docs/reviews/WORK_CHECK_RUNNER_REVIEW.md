# Work-machine automation review

## Current behavior: local work-machine results (2026-10-14)

Tyler removed automatic synchronization and publication from the work-machine
workflow. The launcher now uses the already checked out clean named branch,
including `main`; it
does not fetch, pull, stage, commit or push, and matching origin/upstream setup
is no longer required. Code updates and report publication are manual actions.

The runner saves its validated aggregate at Git-ignored
`public/inspection/local/work-check-<run-id>.json`. The selected source path stays
in Git metadata; private logs and analysis artifacts retain their existing
`confidential/` locations. Review the aggregate, then manually copy or move only
its JSON into `public/inspection/` and explicitly stage, commit and push when
ready. The private log folder and engineering workspace are not shared artifacts.

Work-machine suites use explicit parser/helper module allowlists. Listener,
Windows process-host, Bash bootstrap and Git-fixture tests are excluded there;
full unittest discovery remains available on the development PC. The aggregate
envelope remains schema 1 and carries the tested SHA, allowing historical suite
scope to be identified from the corresponding revision. Reduced counts do not
mean tests were skipped or failed inside the selected suites.

The address-shape report returned in `b58af78` and awaits parser analysis. The
development listener remains disabled and paused pending the endpoint-security
incident review. Tyler is proceeding with a fresh clone and normal manual parser
checks. These code changes do not establish the detection's cause. The sections below preserve the original
implementation and its evidence; their automatic pull/commit/push behavior and
broad work-machine test scope are superseded by this section.

Fresh validation of the local-only revision: all **53 focused tests** passed
(24 workflow, eight bootstrap and 21 suite-selection/results tests). The selected
work-machine suites passed with **152 application tests, including one existing
Windows symlink-capability skip, and 139 helper tests**. The guard regression runs
these selected suites with `subprocess.Popen` and `socket.socket` blocked.

Two real CLI runs in a disposable clean checkout used an independently invented
L5X and an unreachable origin. Both saved valid schema-1 reports and private
outputs with unchanged HEAD and a clean worktree. The source and earlier report
were preserved, and the second run reused the remembered source selection.
Independent review found no remaining blockers. These checks establish the
revised workflow's behavior; they do not diagnose the endpoint detection.

## Original implementation and validation history

Date: 2026-10-13. Branch: `feat/source-references-pc`. Baseline: `5ea6b8d`,
which records the returned reference aggregate and Tyler's confirmation that
both work-machine suites passed. This slice automates the existing Phase 1
feedback cycle; it adds no new ladder interpretation or engineering mapping.

## User request and resulting behavior

Tyler requested one script to pull, test, run the current analysis and push
results, including test outcomes. Use `run-work-check.sh` from Git Bash. Its
first run accepts a source filename/path; subsequent runs use the selection
saved in Git metadata on that machine. Real filenames are not embedded in code
or documentation. The [work-machine procedure](WORK_MACHINE_REFERENCES_RUN.md)
is the user-facing entry point.

The Bash bootstrap checks the checkout/branch/upstream and performs only
`git pull --ff-only` before loading updated Python through `uv run --locked`.
There is no separate fetch step. Both suites run as fresh child processes to
avoid test-module discovery collisions. A failing application suite does not
prevent the helper suite from running. Failed tests skip source analysis but
still produce an automatically committed/pushed test-results report.

Successful tests enable one captured L5X snapshot, structural inventory, scoped
reference analysis, a new private workspace and the nested aggregate report.
This combines the current inspect/references/reference-summary capabilities
without parsing the source separately for each presentation. Useful partial
analysis exits 0; failed tests or analysis exit 1 after publishing their result.
Preflight, source-selection, publication or Git errors stop without claiming
that the complete workflow succeeded.

## Files and boundaries

- `run-work-check.sh`: clean-tree, `-pc` branch and matching origin guards;
  pull and updated Python launch. Repository/index environment overrides are
  removed; SSH/authentication settings are preserved.
- `.gitattributes`: shell scripts keep LF endings, including Windows checkouts
  with core.autocrlf=true.
- `work_check.py`: local selection, code-revision checks, orchestration, private
  storage, aggregate contract, report-only commit and exact-commit push.
- `work_check_tests.py`: fresh-process discovery and bounded unittest results.
- `summary_output.py`: explicit dispatch for the new report kind, with independent
  validation and the existing atomic no-overwrite publication rules.
- Three new test modules exercise the workflow, structured results and actual
  Bash/Git boundaries. They use invented data and disposable repositories.

The saved path is `plc-work-check.json` inside the actual checkout Git directory;
a redirected/symlinked config destination is rejected. Private logs live under
`confidential/work-checks/<run-id>/`. New saved analysis runs live beneath
`confidential/workspaces/work-check/`. No original source or previous run is
overwritten. Raw test output, exception details and Git mutation diagnostics
remain local. A secondary diagnostic-write error does not suppress the bounded
failure result, though publication still requires usable local storage.

The runner requires a clean checkout before and after tests/analysis, and pins
the checked branch and code commit. It stages only its new report, commits with
`--only`, checks the commit parent and changed path, then pushes that exact commit
SHA to the same origin branch. It never force-pushes, resets or stashes. Rejected
pushes leave the report committed locally. This is a sequential single-owner
workflow, not a general multi-writer coordination system.

## Public report contract

`public/inspection/work-check-<UTC timestamp>-<random suffix>.json` has:

- `report_kind=l5x_work_machine_check`, schema 1, `workflow_version=work-check-1`;
- `tool_revision`: tested 40-character commit and clean worktree state;
- `tests.application` and `tests.helpers`: status, event counts and up to 20
  bounded base test IDs, plus an omitted-ID count;
- `analysis`: complete/partial/failed/not_run, fixed failure code, private-run
  saved flag and the existing validated reference summary when available;
- overall status passed/partial/failed, reconciled with tests and analysis.

All fields are closed and the rendered report is capped at 32 KiB. Test IDs come
from test code identity, never subtest parameter representations or overridable
display IDs. Counts include tests_run, failures, errors, skipped, expected_failures
and unexpected_successes. Failure/skip events can exceed case count for subtests;
the report does not invent a passed count by subtraction. runner_error/not_run
suite states have null counts, not fabricated zero-test successes.

The reference summary retains its existing validated structural counts, fixed
status vocabulary and provenance. Nested provenance must match the tested commit.
The report commit is necessarily later than that tested commit. Source filenames,
source hashes/IDs, raw instructions, names, values, tracebacks, subtest parameters
and dependency links are excluded. Tyler's approval of aggregate syncing applies;
there is no extra per-report sharing gate.

## Validation

Fresh commands on this PC:

```bash
bash -n run-work-check.sh
uv run --project python-parser --locked python -B -m unittest discover -s python-parser/tests
uv run --project python-parser --locked python -B -m unittest discover -s tools/l5x_inspect/tests
```

Application: **155 tests run, 154 passed, one existing Windows symlink skip**.
Helpers: **139 passed**. The 48 new tests include actual temporary local Git
remote/clone checks: pull updates the checkout before Python launches, arguments
with spaces remain intact, and dirty trees, detached/non-`-pc` branches, wrong or
missing upstreams and failed pulls stop before analysis. A Windows autocrlf clone
test verifies the launcher retains LF endings and runs after checkout. Orchestration tests cover
both-suite execution, failed-test reporting, snapshot capture once, unchanged code
requirements, private errors, no-clobber publication and rejected push recovery.

Independent review found and verified fixes for lost SSH environment settings,
secondary private-log write failures, discarded Git diagnostics and moving-HEAD
pushes. The final reviewer ran all 47 targeted tests and found no remaining blocker.
Before the final line-ending regression test was added, the full bootstrap was
also exercised in a temporary source checkout with a local
bare remote and the invented fixture. This used real uv, both real suites, private
storage, Git commits and normal pushes, rather than mocked orchestration:

| Scenario | Result |
|---|---|
| First run with a filename containing spaces | 154 application tests (one skip), 139 helper tests; partial analysis; exit 0; 5,692-byte aggregate pushed |
| Later no-argument run with one deliberately failing synthetic test | 155 application tests, one failure and one skip; all 139 helper tests passed; analysis not_run; exit 1; failure report pushed |
| Later no-argument run with malformed invented source | Both original suites passed; read_error analysis report; exit 1; failure report pushed |

Each case verified the remote tip, report-only commit contents, clean final tree,
tested-commit provenance and schema validation. The first run also verified
unchanged source bytes, a saved private manifest and remembered source selection.
The failed-test run produced no new private analysis. Shared JSON excluded the
invented source filename/path and a sentinel placed in the test assertion message.
All three reports and their local-only test commits remained in the temporary
repositories; they were not added to this project's GitHub history.

## Returned work-machine results

On 2026-10-13, Tyler ran the script and two aggregate reports reached GitHub:

| Report | Report commit | Tested clean commit |
|---|---|---|
| work-check-20261013T221312Z-4c286cdf.json | ad2ec8b | 0666542 |
| work-check-20261013T221358Z-0ad977a3.json | f38d81e | ad2ec8b |

Both pass validate_work_check_report using the committed implementation. Each
records 155 application tests (154 passed, one skip), all 139 helper tests passed,
zero failures/errors and no failed test IDs. Analysis is partial with no failure
code and private_run_saved=true. Both commits contain only their new report.

Each nested reference summary exactly matches the earlier returned reference
aggregate after excluding code provenance, including all 4,606 rungs and 17,874
instructions. No aggregate regression or new parser result appears. This confirms
the automated work-machine feedback cycle and successful GitHub publication;
it does not prove the two source files were byte-identical or independently verify
private artifact contents. The shared report deliberately omits that source data.
Review consisted of schema validation, aggregate comparison and Git history checks;
the suites were not rerun locally for this documentation-only review.

## Remaining scope

This PC never opens the real export. The end-to-end test uses independently
invented input and a local bare remote; actual GitHub authentication and the plant
export were exercised by Tyler's returned work-machine runs above. Setup failures cannot publish
results for tests which never started. Disk/network failures may require normal
local recovery; the script does not claim a failed push reached GitHub.

The next proposed parser slice remains module/I/O declarations and fixed aggregate
gap reasons, based on the returned evidence in [the reference review](SOURCE_REFERENCES_REVIEW.md).
It is not implemented by this automation change. PCSD, correction overlays, editor
packaging, reports about engineering intent and FHX generation remain later work.
