# Current handoff: PLC analysis workbench

History cleanup: `main` contains eight consolidated milestones above the prior
baseline. The review-guide milestone includes the accepted C16 return and
history-cleanup notes. Completed branch names and iteration archive tags are
retired. The [history map](docs/reviews/HISTORY_CONSOLIDATION.md) records original
checkpoints, preservation checks and the work-PC synchronization procedure.

Updated 2026-10-21. First-time users start with
[START-HERE.html](../START-HERE.html): a short orientation, invented practice
report and fixed learning checkpoints. Progress is local to the browser with
bounded JSON export/import; it is not engineering review state. The start page
and newly generated reports include a light/dark switch. Existing private HTML
does not change merely by pulling this presentation update. No work-PC parser
run is needed to begin learning or use the accepted saved report.
The [first-use implementation record](docs/reviews/GETTING_STARTED_REVIEW.md)
contains the progress-storage contract and focused validation evidence.

Tyler's class-library composition constraints are recorded in
[decision D034](docs/planning/DECISIONS.md) and the
[future conversion boundary](docs/planning/ARCHITECTURE.md#team-class-library-constraints-confirmed-2026-10-21).
PID, alarm, equation and timer classifications are source interpretations,
not one-to-one target class assignments. Mapping and split/merge implementation
remain later work. For development status, start with the
[tracker](docs/planning/PRE_TEAM_REVIEW_TRACKER.md), then the
[readiness assessment](docs/reviews/PHASE_1_READINESS_REVIEW.md).

## Current state

Phase 1's fourteen analysis cycles, C15 cleanup and C16 review-guide refresh
are validated: sixteen completed cycles, zero further unchanged-source runs
before review. C16 return `23d073d` tested clean `07a935c`: 2,122 application
cases with two expected skips, 139 helpers and a successful private save
without a failure code. All 29 analysis summary families match C15 `d53e1ee`
after removing only `tool_revision`; the complete frozen sample and diagnostic
envelopes also match. All 64 retained reports pass their bounds, closed
validation and exact canonical replay; frozen-history acceptance also passes.

The current assembly scan contains 55,230 memberships in 7,580 groups, including
1,029 memberships with qualified rack occurrence proof. Signal/SFC assembly
exclusions are zero. Two dynamic calculation destinations and one dynamic file
address remain excluded pending runtime-selected values. Original provider
gaps and `partial`/`unreviewed` statuses remain evidence, not failed tests.

The cleanup centralizes work-report size/serialization policy under
`contracts/work_reports.py`, adds documentation entrypoints and clarifies the
report's base rack-binding labels. Its accepted return took 18m 06.389s. See the
[cleanup record](docs/reviews/CLEANUP_REVIEW.md) for validation and timing detail.

## Next action: complete a short orientation, then inspect one report item

Tyler requested an embedded page explaining what to check and how to answer,
with normal reviewer output free of development attribution and example
acquisition narrative. The guide now includes nine subject checklists,
response definitions, a glossary and a selectable feedback template. Detail
pages supply record, snapshot and selected context, with a return link.
Responses are written in separate notes; the HTML does not save or send them.

C16 completed in 18m 20.148s and confirms the guide-bearing private report was
saved. First follow the one-time [history synchronization procedure](docs/reviews/HISTORY_CONSOLIDATION.md#work-pc-synchronization)
if the work PC still has the pre-cleanup main tip. Then open the existing
`review.html` saved by check `20261019T201714Z-38434b5f` and choose
**Review guide**. Do not rerun the parser just to find or review that report.
Proceed to readability, navigation, appearance and official engineering review.
The private HTML has not been visually inspected here; prior guide browser
checks used invented reports. Engineering decisions remain unreviewed. See the
[implementation record](docs/reviews/REVIEW_GUIDE_IMPLEMENTATION.md) for current
validation and the [tracker](docs/planning/PRE_TEAM_REVIEW_TRACKER.md) for status.

Normal HTML omits only known generated version/rule metadata; `--debug` on
`run-work-check.sh` or `plc review` restores the canonical payload and developer
panels. Source comments, engineering evidence, IDs and uncertainty are retained
in both modes. Canonical saved JSON, manifests and sampling are unchanged.

For each feedback item, retain the report/run and record ID, observed and
expected behavior, and supporting evidence. Distinguish parser defects,
object-specific exceptions, missing evidence, interface issues and DeltaV
design decisions. Preserve the reviewed report. Investigate concrete feedback
before requesting another work-PC run; do not reopen completed analysis cycles
without new evidence. Frozen sampling remains six charged examples, eight
reserved units, cap forty; no new sample was requested or released by C16.

For a future requested check, the work-PC sequence remains manual `git pull`,
`bash ./run-work-check.sh`, then `git push`. The script creates only its local validated feedback commit and
performs no Git network operation. The listener remains outside the shipped
workflow. Future development belongs on a focused `-pc` branch. Build/test
iterations stay on that branch; consolidate them into meaningful feature or
fix commits before merging to `main`. Include validation and handoff notes
with the relevant change rather than adding routine status commits to main.
Preserve report bytes and recorded historical SHAs as provenance identifiers;
retaining every original Git commit or an iteration archive tag is not required.

## Boundaries and useful links

- Keep actual exports and full derived reports in `confidential/`. Use the
  existing validated aggregates, frozen bounded examples and independently
  synthetic fixtures for development. Preserve sample history and limits.
- Source associations do not establish physical wiring, runtime execution,
  equipment purpose, shutdown effect or engineering approval. The remaining
  source/vendor/runtime questions are explicit in the readiness assessment.
- The report does not yet persist corrections across exports. Editable records,
  naming/classification corrections, PCSD and FHX are later phases.
- Preserve sequential handoffs with adaptable routing and traceable decisions.

[Work-PC procedure](docs/reviews/WORK_MACHINE_REFERENCES_RUN.md) ·
[Reading guide](docs/reviews/REPORT_REVIEW_GUIDE.md) ·
[Development guide](docs/DEVELOPMENT_GUIDE.md) ·
[Documentation index](docs/README.md) ·
[Next-session checklist](docs/reviews/NEXT_DEVELOPMENT_PROMPT.md)

The [full prior handoff](docs/history/2026-10-19-pre-cleanup/files/public/CODEX_HANDOFF.md)
and other accumulated entrypoints remain in the
[verified archive](docs/history/2026-10-19-pre-cleanup/README.md).
