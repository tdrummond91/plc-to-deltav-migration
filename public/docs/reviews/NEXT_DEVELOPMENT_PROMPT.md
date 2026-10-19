# Next development checkpoint

Updated 2026-10-19. Read the [current handoff](../../CODEX_HANDOFF.md),
[tracker](../planning/PRE_TEAM_REVIEW_TRACKER.md) and
[readiness assessment](PHASE_1_READINESS_REVIEW.md) before choosing work.

## Ready for report review

The fourteen Phase 1 analysis cycles and the requested cleanup confirmation
are complete. C15 return `d53e1ee` tested clean `4c5386c`: 2,112 application cases
(two expected skips), 139 helpers and a successful private save. All 62 reports
validate and replay exactly. All 29 analysis summaries match C14 after removing
revision metadata; complete frozen sample and diagnostic envelopes also match.

Engineering assemblies retain 55,230 memberships / 7,580 groups, 1,029
rack-qualified memberships, complete scans and three runtime-dependent
exclusions. See the [cleanup record](CLEANUP_REVIEW.md) and readiness assessment
for evidence and external questions. The report is ready for review; this does
not establish engineering approval or runtime equivalence.

Tyler's next step is to open the private `review.html` saved by run
`20261019T185822Z-acde7c64` for readability, navigation and appearance checks,
then official engineering review. No further unchanged-source run is planned.

When review feedback arrives:

1. Fetch, inspect local/upstream status, and integrate without overwriting work.
2. Identify the exact report/run, record, observed result and expected result.
3. Distinguish a parser rule, an object exception, an interface problem, missing
   evidence and a DeltaV design decision. Preserve the original reviewed report.
4. Use existing bounded evidence and invented fixtures to investigate. Frozen
   sampling remains six charged examples, eight reserved units, cap forty.
5. Implement and test a concrete correction; request a work-PC run only when
   the change needs source validation. Record what that run must establish.

Do not reopen automated source-analysis cycles without new evidence or a
specific defect. Team review supplies engineering decisions; it must not be
used to guess unresolved vendor/exporter semantics or runtime selectors.

## Where to work

The [development guide](../DEVELOPMENT_GUIDE.md) describes commands and ownership
boundaries. The [module map](../../../python-parser/src/plc_workbench/README.md)
groups the existing source modules by responsibility; imports remain stable.
`contracts/work_reports.py` owns shared work-report envelope sizes and canonical
JSON serialization, while `work_check.py` retains compatibility aliases and
semantic validation.

Work-PC transport remains manual. Keep private exports/reports local and
preserve all prior review decisions and sample history. The later editable
correction layer, PCSD and FHX are outside this cleanup.

The [full earlier next-session notes](../history/2026-10-19-pre-cleanup/files/public/docs/reviews/NEXT_DEVELOPMENT_PROMPT.md)
are preserved; use them for historical evidence, not the current next action.
