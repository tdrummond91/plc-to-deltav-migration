# Project state after the returned SFC annotation run

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
| 1: Understand L5X | Source-evidence foundation is implemented and repeatedly checked against this unit. Engineering interpretation and organized review still need substantial work. |
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

Build a private, navigable engineer-review package using existing evidence:
routine/SFC hierarchy, object/reference lookup, grouped pattern occurrences and
an unresolved-work queue. Add a first conservative set of instruction access
roles and dependency views with evidence links and explicit unknown effects.
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
