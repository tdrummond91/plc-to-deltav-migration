# Next development checkpoint

Updated 2026-10-19. Read the [current handoff](../../CODEX_HANDOFF.md),
[tracker](../planning/PRE_TEAM_REVIEW_TRACKER.md) and
[readiness assessment](PHASE_1_READINESS_REVIEW.md) before choosing work.

## Accepted analysis baseline

The fourteen Phase 1 analysis cycles, cleanup confirmation and C16 guide refresh
are complete. C16 return `23d073d` tested clean `07a935c`: 2,122 application cases
(two expected skips), 139 helpers and a successful private save with no failure
code. All 64 retained reports validate and replay exactly. All 29 analysis
summaries match C15 after removing only `tool_revision`; complete frozen sample
and diagnostic envelopes also match, and frozen-history acceptance passes.

Engineering assemblies retain 55,230 memberships / 7,580 groups, 1,029
rack-qualified memberships, complete scans and three runtime-dependent
exclusions. See the [cleanup record](CLEANUP_REVIEW.md) and readiness assessment
for evidence and external questions. The report is ready for review; this does
not establish engineering approval or runtime equivalence.

## Ready for report review

Tyler requested an embedded review guide and clearer instructions for people
receiving the HTML. C16 adds nine topic checklists, a glossary, response
definitions and a copyable feedback template linked to the selected record,
snapshot and detail context. It explicitly explains that responses must be
saved in separate notes. Normal HTML omits only generated implementation
versions and candidate rule identifiers; `--debug` restores developer detail.
Source evidence, uncertainty, saved canonical JSON and sampling remain intact.

Tyler authorized integrating the consolidated history and accepted return into
`main`. The next work-PC action is `git switch main` then `git pull --ff-only`.
Open the existing private `review.html` saved by completed check
`20261019T201714Z-38434b5f`, choose **Review guide**, and begin the walkthrough
and official review. No parser rerun is needed. The actual private HTML was
not visually inspected here; previous browser checks used invented reports.
The [implementation record](REVIEW_GUIDE_IMPLEMENTATION.md) records the
accepted return. C14/R3/R4, C15 and C16 remain closed until concrete new evidence
requires a correction.

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
correction layer, PCSD and FHX are outside this presentation refresh.

The [full earlier next-session notes](../history/2026-10-19-pre-cleanup/files/public/docs/reviews/NEXT_DEVELOPMENT_PROMPT.md)
are preserved; use them for historical evidence, not the current next action.
