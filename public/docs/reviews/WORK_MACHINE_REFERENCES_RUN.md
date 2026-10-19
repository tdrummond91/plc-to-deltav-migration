# Work-PC check and manual return

## Current action

The guide refresh passed: return `23d073d` tested clean `07a935c`, with 2,122
application cases (two expected skips), 139 helpers, the private report saved
and all 29 analysis summaries unchanged from C15 except `tool_revision`.
**No further run is needed before review.** See the
[tracker](../planning/PRE_TEAM_REVIEW_TRACKER.md).

In Git Bash, from the repository root, synchronize the consolidated history:

```bash
git switch main
git pull --ff-only
```

Open the existing `review.html` saved by completed check
`20261019T201714Z-38434b5f`. Use the **Private review report:** path printed by
that run, or find its newest completed report under
`confidential/workspaces/work-check/`. The private workspace directory name can
differ from the work-check ID. Start with **Review guide**. Switching branches
does not require regenerating the saved report.

## Run a future check when requested

In Git Bash, from this repository's root:

```bash
git pull
bash ./run-work-check.sh
git push
```

The script remembers your chosen source locally. For a new checkout, use this
middle command instead:

```bash
bash ./run-work-check.sh A19CHL02-unencrypted.L5X
```

A bare filename is found under `confidential/plc-code/`. An explicit local path
also works. The source is read without modification. The checkout must be clean
and on a named branch; Python 3.12+ and `uv` must be available. `uv` uses the
locked project environment and may need to install dependencies on first use.

The normal report includes **Review guide**, the topic checklists and the
feedback template. For a separate developer-diagnostic report, use this middle
command instead:

```bash
bash ./run-work-check.sh --debug
```

You may supply the source after `--debug` when needed. The flag adds generated
version and rule details to the HTML; it does not request more source examples
or change the analysis. Normal mode is the intended report for engineering
review. Both modes retain the source evidence and explicit uncertainty.

## What the script does

1. Runs the audited application and helper suites on invented inputs.
2. Captures the local L5X and builds the source-analysis report.
3. Saves a fresh private run, with artifact hashes and a final manifest.
4. Validates a bounded feedback report and creates its local Git commit.

The script performs **no automatic fetch, pull or push**. You run the Git
commands yourself; no separate `git add` or `git commit` is needed for the
generated feedback. It does not enable a listener. Raw logs and full engineering
records remain local.

## Find the results

| Location | Contents |
|---|---|
| `confidential/workspaces/work-check/<run>/review.html` | Complete offline engineering report; open in a browser. |
| The same run directory | Captured source, evidence files and final `manifest.json`; keep them together. |
| `confidential/work-checks/<run-id>/` | Detailed test logs, timing and local failure information. |
| `public/inspection/work-check-<run-id>.json` | Validated feedback report committed locally for your manual push. |
| Git metadata `plc-work-check.json` | This checkout's remembered source path; not committed. |

The console prints **Private review report:** with the exact HTML path. If the
output is gone, browse the private workspace and open the newest completed
run's `review.html`. A successful run has a final manifest. Git does not back
up `confidential/`; preserve it separately using your approved local backup.

## Understand completion

**Tests passed**, **private results saved**, and **no failure code** establish a
successful check. Analysis may still say `partial`: the report deliberately
retains missing source, opaque behavior and runtime-dependent questions. It
does not mean the script failed. Expected skips are recorded in the test result.

If the script stops, keep its console message and private logs. Report the
stage/status or a bounded screenshot of the error; do not paste full plant
source or logs. Do not delete the checkout or private folder to repair a test
failure. If Git reports local changes before the run, inspect them before
trying again. If `git push` says everything is up to date, check whether the
script completed and created a local feedback commit.

The accepted C16 guide run took 18m 20.148s; C15 took about 18 minutes and C14
about 37 minutes. These are observations, not duration guarantees.
Let a requested check finish rather than starting a duplicate run.

## After the return is checked

Open the saved report and choose **Review guide** from Overview or the left
navigation. It explains the subject checks, terms and response categories.
On a detail page, choose **Prepare review feedback**, select and copy the
template, and complete it in separate review notes. The source snapshot,
record ID and selected context are filled in for that item. State the displayed
result, expected result or unanswered question, and supporting evidence. The
HTML does not save or send answers. No code reading is required. The
[reading guide](REPORT_REVIEW_GUIDE.md) provides further context, and the
[readiness assessment](PHASE_1_READINESS_REVIEW.md) lists the engineering and
external-source questions that remain.

The [full earlier work-machine notes](../history/2026-10-19-pre-cleanup/files/public/docs/reviews/WORK_MACHINE_REFERENCES_RUN.md)
remain available for historical commands, returned evidence and prior schemas.
