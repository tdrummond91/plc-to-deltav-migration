# Project state: calculation evidence and prior Phase 1 assessments

Current checkpoint (2026-10-15): **legacy CPT function support** adds the seven
documented older spellings and fixed function counts. Original expression text
and function spelling remain source evidence; no expression is evaluated.
Returned `6d19d5e` confirms 43 of 45 CPT expressions parsed, 456 syntax nodes,
122 reference occurrences all root-bound and all 45 destinations root-bound.
The other two expressions stop at unsupported functions; their names are not
in the feedback. Older spellings are a possible explanation, not a confirmed
cause. The run passed 656 application cases (one expected Windows skip) and
139 helpers. Six earlier summaries remain equal after revision normalization.

Review6/manifest9 still saves thirteen hashed artifacts. Calculation2 and
summary2 add fixed function-spelling counts and first-unsupported-function
buckets; work19 requires summary2 while work18 remains strict summary1.
Explicit calculation1 replay preserves its original grammar and evidence.
The next work-machine run checks whether this extension resolves the two gaps.
Only generated feedback is needed. Engineering/UI review remains optional,
Git synchronization remains manual and the listener stays disabled. See
[Calculation function follow-up](CALCULATION_FUNCTION_REVIEW.md).

## Historical PID member implementation checkpoint

Historical checkpoint (2026-10-15): **documented PID member evidence** organizes
linked stored fields into readable groups, checks captured names/types/shapes,
and exposes absent and duplicate catalog entries without selecting effective
values. Returned `28b5d1f` confirms all 46 PID instruction occurrences linked to
46 distinct declarations, with 2,346 direct member occurrences and no PID
association gaps. It passed 586 application cases (one skip) and 139 helpers;
previous summaries stayed equal after revision normalization.

Current review5/manifest8 adds `pid-members.json` as the twelfth hashed artifact.
Work17 adds count-only `analysis.pid_member_summary` schema1 beside unchanged
PID1, Tag Data1, access2, SFC2 and reference12/source4 summaries. Older optional
paths and work1-16 remain strict. The next work-machine run measures member
coverage and gaps; only generated feedback is needed. Manual engineering/UI
review remains optional. Git synchronization stays manual and the listener
remains disabled. See [PID member review](PID_MEMBER_REVIEW.md) for scope and validation.

## Historical PID occurrence checkpoint

Historical checkpoint (2026-10-15): **PID occurrence evidence** links parsed PID
instructions and their seven named operand functions to retained references and
conservatively eligible stored PID structures. Repeated occurrences, aliases,
representations and duplicate members remain separate evidence. No active
cascade, runtime mode, effective value or distinct control-loop count is inferred.
The previously observed 46 PID instructions are source occurrences.

Current review4/manifest7 saves eleven hashed private artifacts, adding `pid.json`
beside unchanged Tag Data1/access2/reference6/SFC2/inventory3 evidence. Work16 adds
closed count-only `analysis.pid_summary` schema1 and keeps Tag Data1/access2/SFC2/
reference12/source4 summaries. Review1-3, manifest1-6 and work1-15 keep their exact
contracts; review4 retains review3's 128 MiB JSON and 160 MiB HTML limits.
See [PID evidence review](PID_EVIDENCE_REVIEW.md) for scope, validation and
remaining limits. The next ordinary work-machine run measures PID evidence;
only generated aggregate feedback is needed. Engineering/UI review remains
optional later. Manual pull/run/push and private artifact storage still apply.

## Historical Tag Data checkpoint

Historical checkpoint (2026-10-15): **stored Tag Data evidence** is a separate
capture layer beside the unchanged source/reference/SFC/access contracts.
Review3/manifest6 adds `tag-data.json` as the tenth hashed private artifact;
work15 adds a count-only tag-data summary1. Missing Data remains absent evidence.
Stored text and attributes do not establish effective values, initialization,
runtime state, member validity or approved settings. Read the
[Tag Data review](TAG_DATA_REVIEW.md) for scope and complete validation results.
All 642 development cases pass with one existing Windows symlink skip.
Two actual isolated runs, explicit then remembered source, each pass 546
application cases (one existing symlink skip) and 139 helpers, with report-only
local commits and no Git network calls. All ten hashes and canonical review3/
Tag Data schema1 verify; fresh CLI artifacts are identical. Eight legacy artifacts
match `122f230` byte for byte, source/reference/SFC/access summaries match after
revision normalization, and all 21 historical work1-14 reports validate.

Returned `122f230` confirms timer/reset/copy access2 on clean `bdcc101`: 496
application cases (one skip), 139 helpers, 17,526 classified instructions of
17,874, 348 unsupported instructions, 931 unknown operand roles and 321 binding
gaps. All 434 timers have 868 placeholder initialization fields. Source/reference
and SFC summaries equal `7cd9201` after revision normalization; aggregate equality
does not prove source byte identity. The next normal work-machine run measures
Tag Data capture. Only generated aggregate feedback is needed; engineering/UI
review remains deferred and does not gate parser work. Manual pull/run/push
and private artifact storage continue as described below.

## Historical timer/reset/copy checkpoint

Historical milestone (2026-10-15): [timer/reset/copy access](TIMER_COPY_ACCESS_REVIEW.md)
extends [initial explicit operand access](ACCESS_ROLE_REVIEW.md) to 34 supported mnemonic spellings alongside the
[offline source-review package](ENGINEERING_REVIEW_REPORT.md). Roles describe
potential explicit reads, writes, read-writes and non-data uses; unsupported or
invalid signatures remain unknown. Existing root bindings are grouped without
claiming member/index overlap, execution effects or dependencies. This advances
Phase 1 interpretation while preserving its stated limits. Timer storage and
pseudo-operands, reset writes and copy source/destination/length roles are
bounded lexical observations; timing, initialization, copy extents and
datatypes remain unmodeled.

Returned [work report `7cd9201`](../../inspection/work-check-20261015T045543Z-7f2b0763.json)
confirms initial access1: clean tested `6642c5c`, 478 application cases (one skip),
139 helpers and a saved private run. It classified 16,952 of 17,874 instructions,
retained 922 unsupported instructions and counted 321 access binding gaps.
Reference/source and SFC summaries equal the preceding `1332543` report after
revision normalization. This does not prove source byte identity. Tyler has not
inspected the source/report and explicitly deferred engineering and UI review.
That optional later review is not a gate to continued parser work. The next
work-machine run is needed for the timer/reset/copy extension; only its generated aggregate
feedback is required, without familiar-tag or SFC manual checks.

Historical extension validation was 592 development cases with one existing symlink
skip. Two actual isolated runs, explicit then remembered source, each pass 496
application cases (one skip) and 139 helpers, creating report-only local commits
without Git network calls. Nine artifact hashes, canonical access2/review2 and
identical CLI artifacts verify. Seven legacy artifacts match `7cd9201` byte for
byte; source/reference/SFC summaries match after revision normalization. All 20
historical work1-13 reports validate.

Initial access1
validation is historical: 574 development cases passed with one existing symlink skip;
two final synthetic launcher runs each pass 478 application cases (one skip)
and 139 helpers. Both verify manifest hashes, canonical access/review evidence
and identical CLI HTML. Seven legacy artifacts match baseline `1332543` byte
for byte on the same invented input, source/reference/SFC summaries match after
revision normalization, and all 19 then-stored work1-12 reports validated. At that checkpoint, work14 required
access summary2 beside unchanged reference12/source4/SFC2; frozen work13 retains
access summary1. Private access2 and
review2 use manifest5 with nine hashed artifacts. Historical contracts remain
readable. See [TIMER_COPY_ACCESS_REVIEW.md](TIMER_COPY_ACCESS_REVIEW.md) for current evidence
and remaining access limitations.

The assessment and iteration ranges below are preserved as the preceding SFC
checkpoint, not a new estimate after access coverage or deferred UI feedback.

## Historical assessment after the returned SFC annotation run

Assessment date: 2026-10-14. Reviewed code/report HEAD: `90923ab`, whose only
change is the work-machine feedback from clean parent `f8411bc`. Tyler requested
an independent subagent assessment after this report was analyzed, including
remaining-iteration estimates. This checkpoint records that assessment and the
recommended next milestone; it does not introduce parser changes.

## Confirmed result

The [returned report](../../inspection/work-check-20261015T030020Z-8c576eed.json)
passes contract/revision checks: 416 application cases (one existing Windows
symlink skip) and 139 helpers pass, a private run is saved, and the diagnostic
sample is null. The complete reference12/source4 summary matches the preceding
report except code revision. All previous SFC flow-link, ID and ST counts stay
unchanged.

SFC2 structural capture is complete for this export. All 280 note boxes use
recognized Text children, with 16,481 raw text characters. All 213 attachments
and 426 endpoints resolve, covering 213 distinct boxes/targets. The former
280 unmodeled elements and all SFC issues are now zero. This completes the
bounded structure/annotation slice; it does not establish sequence execution
semantics or complete Phase 1. No repeat annotation-only run is needed.

## Position in the five phases

| Phase | Current position |
|---|---|
| 1: Understand L5X | At this historical SFC checkpoint, source evidence was implemented and repeatedly checked against this unit. The current milestone above adds organized review and initial explicit operand roles; broader engineering interpretation remains. |
| 2: Editable files/editor | Proposed. Raw private JSON exists, but a nonprogrammer editing workflow and persistent engineering-object store are not implemented. |
| 3: Naming and corrections | Proposed. Target naming, approved interpretation overlays and preservation of decisions across changing sources are not implemented. |
| 4: PCSD and feedback | Proposed. PCSD/test sheets and upstream correction import are not implemented. |
| 5: FHX workflows | Proposed. Class-based FHX generation and FHX-to-PCSD are not implemented; target contracts remain unselected. |

Current capabilities include immutable snapshots, source links and gaps; all
4,606 observed RLL rungs parsed into outer syntax; 17,874 instruction occurrences
inventoried; scoped declarations/aliases and supported operand-root lookup;
static routine-call candidates/graphs; SFC structure and authored notes; private
text/JSON reports; and bounded feedback with repeatable local report commits.
The helper also groups ordered opcode/arity/branch shapes. Those groups omit
operand-reuse and inner-expression meaning and are not engineering classifiers.

Recognizing 17,617 of 17,874 instruction signatures is useful coverage of the
existing reference catalog, not a percentage of migration completion. Bound
roots do not establish member validity, writes, dependencies or behavior.
The code explicitly marks semantic/effect/member analysis as unimplemented.
The source reader captures declaration attributes/descriptions but does not yet
normalize tag Data contents needed for many PID, alarm and I/O settings.

Overall partial status also includes an RLL routine without expected content,
the older inventory contract's separately analyzed SFC envelopes and retained
unsupported material. Do not spend feedback cycles merely making every status
green. A useful review workflow must show exactly what is understood and what
still requires investigation.

## Recommended next milestone and batching

The historical recommendation was to build a private, navigable engineer-review package using existing evidence:
routine/SFC hierarchy, object/reference lookup, grouped pattern occurrences and
an unresolved-work queue. Add a first conservative set of instruction access
roles and dependency views with evidence links and explicit unknown effects.
The current package and role layer now cover the first parts of that recommendation;
dependency interpretation remains future work and deferred manual review is not a prerequisite.
This can be generated locally through the library/CLI before committing to the
standalone editor's storage and packaging design.

Acceptance for that first milestone: Tyler can locate an object, find its
occurrences, follow supported relationships, inspect source context and notes,
and see which gaps block interpretation. An apparent connection must remain
distinguishable from a verified read/write dependency or engineering role.

Subsequent coherent batches should cover selected configuration values and
member paths, then PID/I/O/calculation candidates, equipment/alarm relationships
and sequence understanding. This export has 46 PID instructions and 45 CPT
expressions, providing concrete starting populations. Shutdown versus warning
classification needs dependencies/control context and human review. Names alone
are insufficient. Additional units must eventually test reusability.

Most parser contracts, reporting behavior and synthetic edge cases can be
developed and tested on the development PC. Work-PC runs are needed for real
export variations, coverage/performance and engineering spot checks. Bundle
related local changes into a useful milestone before requesting another run;
do not require a round trip for every small opcode or aggregate-counter change.
Counts cannot resolve every semantic question. Request only the bounded
evidence or local human check needed for a particular gap.

## Provisional iteration estimate

One iteration here means a coherent development bundle, one work-machine
run/review, and returned feedback. It can contain multiple logical commits and
many local tests; these ranges are not commit counts or calendar estimates.

| Outcome | Additional work-PC round trips from this checkpoint |
|---|---|
| Confirm current SFC annotation slice | 0; latest report already confirms it |
| First organized engineer-review package and initial relationship views | Approximately 2-4 |
| Broader selected Phase 1 coverage across PID/I/O/calculations, equipment/alarm candidates and sequences | Approximately 8-15 total, including the first 2-4 |
| Entire editable PCSD/FHX pipeline | Not responsibly estimable yet |

These are low-confidence planning ranges from the independent audit, adopted as
a provisional work plan. They assume coherent batching, a representative
current unit, and bounded examples or engineering feedback when aggregates
cannot answer a question. Additional unit/export variants, unexpected semantics
or wider accepted coverage can increase the total. The broader estimate is a
useful reviewed Phase 1 scope, not exhaustive Logix support or proof of behavioral
equivalence in DeltaV. Re-estimate after the first engineer-review milestone.

Full-pipeline sizing needs concrete PCSD/test-sheet contents, correction/rerun
examples and the DeltaV class-library/version contracts. Immutable source runs
already protect evidence, but they do not implement preservation of engineering
edits through source splits, merges or changed exports.

## Audit and validation references

The independent read-only subagent checked the roadmap/architecture/contracts,
available CLI workflows, source extraction, root binding, SFC reporting and
existing helper pattern limits. Its recommendation is to shift effort from
isolated count additions toward user-facing review and interpretation batches.
No confidential input or listener execution was used.

The new feedback and all 18 stored work reports validate. This checkpoint changes
documentation only; parser code remains the tested `f8411bc` implementation.
No application-suite rerun is claimed for documentation edits. Prior implementation
validation (512 development cases, one skip, plus two actual synthetic runner
checks) remains in the [annotation review](SFC_ANNOTATION_REVIEW.md).

Scope and acceptance sources: [product phases](../planning/ROADMAP.md),
[engineering categories](../planning/ARCHITECTURE.md),
[contracts and proposed decision survival](../planning/DATA_CONTRACTS.md),
[source extraction](../../../python-parser/src/plc_workbench/source.py),
[root-reference analysis](../../../python-parser/src/plc_workbench/references.py),
[SFC rendering](../../../python-parser/src/plc_workbench/sfc_structure.py), and
[helper pattern limits](../../../tools/l5x_inspect/RUNGS.md).
