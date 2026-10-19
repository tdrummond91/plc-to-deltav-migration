# PLC analysis workbench

Understand an Allen-Bradley L5X export before mapping its control strategy to
DeltaV. The current tool builds a searchable, offline engineering report from
the source: rungs and branches, I/O, PID evidence, calculations, sequences,
alarms, communication and related groups, with uncertainty kept visible.

**Current step:** Phase 1 source analysis and the final cleanup confirmation
have passed. **The saved report is ready for Tyler's walkthrough and official
engineering review.** No further parser run is currently needed. Editable
records, persistent corrections, PCSD and FHX generation are later phases.

## What to do next

On the work PC, open the `review.html` saved by the completed run
`20261019T185822Z-acde7c64`. Start with the reading steps below; you do not need
to read code or rerun the parser. Return the first confusing or incorrect cases.

## Run a future check when needed

For a new source export or a requested parser change, use Git Bash in this
repository:

```bash
git pull
bash ./run-work-check.sh
git push
```

The script runs the parser tests, analyzes the remembered local L5X, saves a
fresh private report and creates the validated feedback commit locally. It does
not fetch, pull or push; the two Git commands above are manual. For a new
checkout, supply the source once:

```bash
bash ./run-work-check.sh A19CHL02-unencrypted.L5X
```

The source belongs under `confidential/plc-code/`; an explicit local path also
works. See the [work-PC instructions](public/docs/reviews/WORK_MACHINE_REFERENCES_RUN.md)
for prerequisites, results and failure handling.

## Read your report

The script prints **Private review report:** and its path. In File Explorer,
open `confidential/workspaces/work-check/`, choose the newest completed run and
double-click **`review.html`**. It works in a browser without a server.

Start with one familiar rung, one PID or output group and one unresolved case.
No code reading is needed. Follow the
[report reading guide](public/docs/reviews/REPORT_REVIEW_GUIDE.md); return the
run/record ID, what seems wrong or confusing, and what you expected. Keep the
full report on the work PC.

## Find things

| Location | Purpose |
|---|---|
| `run-work-check.sh` | The normal work-PC entrypoint. |
| `confidential/` | Ignored local exports, complete reports and logs; Git does not back these up. |
| [python-parser/](python-parser/README.md) | Application code, tests and locked Python environment. |
| [public/docs/](public/docs/README.md) | Current instructions, plans and retained review evidence. |
| [public/examples/](public/examples/README.md) | Invented reports for learning the interface. |
| [public/fixtures/synthetic/](public/fixtures/synthetic/README.md) | Independently invented test inputs. |
| `public/inspection/` | Validated work-PC feedback history used to check each change. |
| [tools/](tools/README.md) | Supporting L5X inspection tools and their tests. |
| [public/CODEX_HANDOFF.md](public/CODEX_HANDOFF.md) | Current checkpoint for the next coding session. |

Use the [completion tracker](public/docs/planning/PRE_TEAM_REVIEW_TRACKER.md)
for progress and the [readiness assessment](public/docs/reviews/PHASE_1_READINESS_REVIEW.md)
for evidence and remaining source questions. Developers can start with the
[development guide](public/docs/DEVELOPMENT_GUIDE.md); this pass is recorded in
the [cleanup review](public/docs/reviews/CLEANUP_REVIEW.md).

The full earlier entrypoint notes are preserved in the
[2026-10-19 archive](public/docs/history/2026-10-19-pre-cleanup/README.md).
