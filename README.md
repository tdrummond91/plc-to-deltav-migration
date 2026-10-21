# PLC analysis workbench

Understand an Allen-Bradley L5X export before mapping its control strategy to
DeltaV. The current tool builds a searchable, offline engineering report from
the source: rungs and branches, I/O, PID evidence, calculations, sequences,
alarms, communication and related groups, with uncertainty kept visible.

**First time here? Double-click [START-HERE.html](START-HERE.html) in the
repository folder.** It is an offline, 15-minute orientation with a practice
report and a small learning checklist. No code or Markdown reading is required.

**Current step:** Phase 1 source analysis, cleanup and the requested review-guide
refresh have passed. **The saved report is ready for the walkthrough and
official engineering review; no further parser run is needed.** Editable
records, persistent corrections, PCSD and FHX generation are later phases.

## What to do next

Begin with **START-HERE.html**. Each of its four steps has report links, a
specific task, a completion checkbox and a next-step link. Use **Go to step 1**,
open the linked report page, complete the task, then return and check it off.
Stop after one step if you like. Progress is saved locally and can be exported
or imported between computers; it does not record engineering approval.

The links initially use the invented practice report. To use your saved unit
report, expand **Use my actual unit report instead** and paste its full Windows
path using File Explorer's **Copy as path**. That path stays in this browser
and is excluded from progress exports. Older saved reports may open at Overview;
choose the named section in their sidebar. Current demos and newly generated
reports support direct links to sections and captured source records.

On the work PC, use the existing `review.html` saved by completed work check
`20261019T201714Z-38434b5f`. Start with **Review guide**. This return passed both
test suites and retained all 29 analysis summary families unchanged. You do not
need to run the script again to review it.

The start page and newly generated reports have a light/dark switch, defaulting
to the existing dark theme. The two current practice reports include it. A
previously saved unit report keeps its original interface and remains usable;
pulling updated code does not rewrite private HTML files.

## Run a future check when needed

For a changed export or a requested correction, use:

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

Normal reports include the reviewer instructions and engineering evidence.
To include developer version and rule diagnostics in a separate run, use
`bash ./run-work-check.sh --debug`. Keep the normal report for review.

## Read your report

The script prints **Private review report:** and its path. In File Explorer,
open `confidential/workspaces/work-check/`, choose the newest completed run and
double-click **`review.html`**. It works in a browser without a server.

Open **Review guide** from Overview or the left navigation. It explains what
to check by subject, what the report's terms mean, and how to write a useful
response. On a detail page, **Prepare review feedback** fills in its record ID,
source snapshot and selected context. Copy the template into your review notes
and complete it there; the HTML does not save or send responses. No code reading
is needed. The [reading guide](public/docs/reviews/REPORT_REVIEW_GUIDE.md)
provides additional context. Keep the full report within the approved work
environment.

## Find things

| Location | Purpose |
|---|---|
| [START-HERE.html](START-HERE.html) | First-use path and your personal learning checklist. |
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
the [cleanup review](public/docs/reviews/CLEANUP_REVIEW.md). The requested report
guide is recorded in [its implementation review](public/docs/reviews/REVIEW_GUIDE_IMPLEMENTATION.md).

The full earlier entrypoint notes are preserved in the
[2026-10-19 archive](public/docs/history/2026-10-19-pre-cleanup/README.md).
