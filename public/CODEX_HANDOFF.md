# Current handoff: PLC analysis workbench

Updated 2026-10-19. Start with the
[tracker](docs/planning/PRE_TEAM_REVIEW_TRACKER.md), then the
[readiness assessment](docs/reviews/PHASE_1_READINESS_REVIEW.md).

## Current state

Phase 1's fourteen tracked analysis cycles and the requested C15 cleanup
confirmation are validated. C15 return `d53e1ee` tested clean `4c5386c`: 2,112
application cases with two expected skips, 139 helpers and a successful private
save without a failure code. All 62 historical reports passed their own bounds,
validation and exact canonical replay. All 29 analysis summary families match
C14 return `adc5475` after excluding revision metadata; the complete frozen
sample and diagnostic envelopes also match.

The current assembly scan contains 55,230 memberships in 7,580 groups, including
1,029 memberships with qualified rack occurrence proof. Signal/SFC assembly
exclusions are zero. Two dynamic calculation destinations and one dynamic file
address remain excluded pending runtime-selected values. Original provider
gaps and `partial`/`unreviewed` statuses remain evidence, not failed tests.

The cleanup centralizes work-report size/serialization policy under
`contracts/work_reports.py`, adds documentation entrypoints and clarifies the
report's base rack-binding labels. Its accepted return took 18m 06.389s. See the
[cleanup record](docs/reviews/CLEANUP_REVIEW.md) for validation and timing detail.

## Next action: report review

Tyler should open the private `review.html` saved by work run
`20261019T185822Z-acde7c64`, check readability/navigation/appearance, then present
it for official engineering review. No further unchanged-source run is planned.
The report is ready for review; engineering decisions remain unreviewed.

For each feedback item, retain the report/run and record ID, observed and
expected behavior, and supporting evidence. Distinguish parser defects,
object-specific exceptions, missing evidence, interface issues and DeltaV
design decisions. Preserve the reviewed report. Investigate concrete feedback
before requesting another work-PC run; do not reopen completed analysis cycles
without new evidence. Frozen sampling remains six charged examples, eight
reserved units, cap forty; no new sample was requested or released by C15.

The work-PC sequence is manual `git pull`, `bash ./run-work-check.sh`, then
`git push`. The script creates only its local validated feedback commit and
performs no Git network operation. The listener remains outside the shipped
workflow. Work on a `-pc` branch; do not merge main without authorization.

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
