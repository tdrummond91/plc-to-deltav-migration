# Work-PC check and manual return

## Current action

The cleanup confirmation passed: return `d53e1ee` tested clean `4c5386c`, with
both suites passing, the private report saved and all 29 analysis summaries
unchanged. Open the saved `review.html` for run `20261019T185822Z-acde7c64`
and follow the [reading guide](REPORT_REVIEW_GUIDE.md). No additional run or
plant sample is requested. See the [tracker](../planning/PRE_TEAM_REVIEW_TRACKER.md).

## Future check when requested

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

The accepted C15 cleanup run took about 18 minutes; C14 took about 37 minutes,
largely in application tests. These are observations, not duration guarantees.
Let a requested check finish rather than starting a duplicate run.

## After the return is checked

Open the saved report and follow the [reading guide](REPORT_REVIEW_GUIDE.md).
Start with one familiar rung, one PID/output group and one unresolved case.
For feedback, retain the report/run ID and record ID, the observed result and
what you expected. No code reading is required. The
[readiness assessment](PHASE_1_READINESS_REVIEW.md) lists the engineering and
external-source questions that remain.

The [full earlier work-machine notes](../history/2026-10-19-pre-cleanup/files/public/docs/reviews/WORK_MACHINE_REFERENCES_RUN.md)
remain available for historical commands, returned evidence and prior schemas.
