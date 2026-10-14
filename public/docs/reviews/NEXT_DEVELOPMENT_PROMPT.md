Read public/CODEX_HANDOFF.md,
public/docs/reviews/MODULE_IO_REVIEW.md,
public/docs/reviews/WORK_CHECK_RUNNER_REVIEW.md,
public/docs/reviews/SOURCE_REFERENCES_REVIEW.md and
public/docs/reviews/WORK_MACHINE_REFERENCES_RUN.md for the current
feat/source-references-pc checkpoint. Then read
public/docs/reviews/SUMMARY_EXPORT_REVIEW.md and
public/docs/reviews/SOURCE_INVENTORY_REVIEW.md first for the implemented
snapshot-bound source inventory on feat/source-inventory-pc, then
public/docs/reviews/STAGE_5_CODE_REVIEW.md.

Then read the 2026-10-12 scope in public/docs/planning/DECISIONS.md,
ROADMAP.md, ARCHITECTURE.md and DATA_CONTRACTS.md. The five product phases
are distinct from the completed helper stages and earlier technical milestones.
PCSD means Process Control Strategy Document. The current priority is L5X
understanding that feeds both reading/scanning reports and editable engineering
records. Detailed PCSD design follows source discovery. Editor/storage/packaging
choices remain proposals; do not treat them as implemented capabilities.

Use public/fixtures/minimized_review/controller_demo.L5X as the
current structural example. Its companion minimized-report.json
provides coverage and source mappings.

For implementation/review involving helper behavior, run the existing tests:
uv run --project python-parser python -B -m unittest discover \
  -s tools/l5x_inspect/tests -v

Current baseline: 139 passing helper tests. Also run:
uv run --project python-parser python -B -m unittest discover -s python-parser/tests -v

Use the final application test count and tested revision in MODULE_IO_REVIEW.md;
one Windows symlink-capability skip is expected on this PC. The helper suite
passed all 139 tests again on 2026-10-13.
For documentation-only changes, review the diff and links; do not describe an old
test run as fresh execution.

The module/I/O slice is implemented and its returned work-machine report is
reviewed in MODULE_IO_REVIEW.md. Tyler has explicitly authorized the feedback
listener; implementation fde4fc2 is installed on the development PC and its
scheduled launch check passed. Consult FEEDBACK_LISTENER.md for concrete behavior
and verification, and the local status command for current monitoring/worker state.
The latest returned report is selected for its first follow-up; no extra work-machine
run is needed to trigger that work. The next bounded parser candidate is a closed
aggregate address-shape breakdown for 868 operands outside the current address
grammar. Establish evidence with invented examples before changing resolution.
Continue work already authorized in the active session; stop for a decision
when the evidence or a phase boundary needs Tyler's input.

Keep parsing and analysis reusable by both CLI and a future GUI.
Preserve source mappings and account for unsupported content.
Do not access confidential/ or begin DeltaV conversion.

Tyler uses a second ChatGPT chat for independent review. For each change, record:

- the baseline and tested commit, affected files and concrete behavior;
- rationale and alternatives, distinguishing user decisions from proposals;
- exact validation commands/results and remaining limitations;
- unresolved evidence and a bounded next step.

Use useful code comments/docstrings and focused conventional commits on branches
ending in -pc for this machine. Do not publish proprietary data in review notes.
Slow work-machine feedback may call for up to three experiment branches from a
common parent, using the same test/report contract. Label each result with its
tested revision and keep outputs separate. Choose experiments deliberately;
do not create three alternatives for every change.

Pay particular attention to decision survival across reruns, source-to-target
identity, partial coverage, and source-derived versus engineer-designed strategy.
The minimized fixture is a structural sample; use independently coherent
synthetic inputs to validate relationships it no longer preserves.

## Independent code/fixture review checkpoint (2026-10-12)

Tyler explicitly invited subagents to test and challenge the design. Independent
validation, parser review and design-readiness review inspected the existing code
at e8a1ede while only documentation was being changed. No confidential files were
opened and no implementation files changed during this review.

Fresh validation commands, run from the repository root with Git Bash:

```bash
uv run --project python-parser python -B -m unittest discover -s tools/l5x_inspect/tests -v
uv run --project python-parser python -B tools/l5x_inspect/check_public_outputs.py --repo . --fixture-name minimized_review
uv run --project python-parser python -B public/tools/check_fixture.py --with-l5x
```

All three exited 0. The unit suite passed 130 tests in 0.077 seconds. The public
audit verified 7,303 source links, 276 rung records, 194 paths, 431 variants,
19 ranked examples and 42 instruction labels, with zero attribute-policy
findings. The synthetic checker also passed hash/count/scope/schedule and l5x
tag-access checks. No stable-input blocker was established for the documented
outer-syntax and metrics contract.

Fixture limits matter for the next work: minimized_review contains only 276 of
4,606 source rungs and 161 of 554 source shapes. Its ARG labels restart per rung
and do not connect to XML DUMMY_ID values. Retained placeholders include 204
opaque payloads, 78 ST lines and 11 mixed-text fields. Use it for structural
breadth, not cross-rung relationships, alarm consequences or persistent identity.

Three review findings to carry forward:

1. Allocation limits: syntax.py counts instruction/branch nodes but not each
   empty branch leg or argument slot. With MAX_NODES temporarily set to 2,
   a branch containing 100 commas still creates 101 legs, and an instruction
   argument list with 100 commas creates 101 slots. This is within the narrowly
   documented node definition but can allocate large collections near MAX_TEXT.
   Add explicit allocation limits and small synthetic boundary tests before
   relying on these guards for unattended ingestion.
2. Scrubbed opcode identity: converting InventedOp(a); to a public sample and
   then reprocessing that sample with the same OpcodeLabels object changes
   UNLISTED_OP_0001 to UNLISTED_OP_0002. Current generation is not broken; ordinary
   source-labeling is not an identity-preserving reader for sanitized samples.
   Keep public shape policies separate from future source/engineering identity.
3. Changing input: inventory_stream reads twice and compares structural counts.
   A synthetic stream changing XIC(a); to OTE(a); between passes retains those
   counts and produces a complete second-pass inventory. This is a changing-input
   limitation, not a stable-file failure. Analyze frozen snapshot bytes in the
   new source reader and test that contract explicitly.

## Selected and completed first implementation slice

The snapshot-bound source inventory with selected-rung evidence and explicit
gap reporting is implemented. JSON and readable views share one reusable result
model. The following list records the selected scope; do not repeat this work.
See SOURCE_INVENTORY_REVIEW.md for implementation, validation and limitations.

- Inventory task/program/routine envelopes, languages, scoped tag declarations,
  module envelopes and AOI definitions from one captured L5X snapshot.
- Bind records to snapshot identity, scoped deterministic IDs and XML locators;
  preserve exact source text privately. Keep future engineering-object IDs separate.
- Reuse/adapt XML safeguards and the ordered rung parser/metrics. Add source
  offsets deliberately; preserve raw mnemonics/operands without claiming to know
  their effects. Avoid a second competing ladder grammar.
- Distinguish structurally parsed, unsupported and failed content from semantic
  classifications. A parsed rung may still have no identified engineering role.
- Produce an overview and selected-rung detail from the same records. Retain the
  existing sanitized-helper reports as a distinct publication contract; raw
  source records must never inherit those helpers' default public output paths.
- Verify the independently authored fixture's 15 tags, four routines, nine rungs
  and 25 instruction occurrences. Add independent tiny cases for duplicate
  scoped names/identical rungs, partial exports, encoded/unknown content and
  malformed input. Require deterministic semantic output, resolved source links,
  unchanged inputs and complete gap accounting.

Full symbol/alias resolution, read/write effects, calls/jumps and cross-rung
analysis follow this foundation. These enable later alarm, control-loop and
equipment interpretation. GUI/database implementation, PCSD schema design,
translation providers and FHX generation remain later work.

## Completed aggregate slice and next action

The corrected public/inspection/summary-002.json at 3dd1b25 matches the earlier
readable baseline: 4,606 parsed rungs, 17,874 instructions, 6,307 tags and no
encoded regions. It validates; partial status reflects 14 SFC routines and one
empty RLL routine. Source byte identity and work-machine suite results are not
established by this aggregate. The original encoded summary remains historical.

Tyler authorized and the branch implements the next bounded root-reference slice:
`plc references` private records and `plc reference-summary` aggregate feedback.
Do not repeat that implementation or claim instruction effects/member validation.
The first reference aggregate has now returned in 7328809 and validates: 98.26%
of instruction signatures catalogued, 17,856 bound operand occurrences and only
45 of 941 aliases bound. Tyler confirmed both work-machine suites passed. Read
SOURCE_REFERENCES_REVIEW.md for all counters and exact structural reconciliation.
Tyler then requested a one-command work-machine runner. That workflow is now
implemented by run-work-check.sh: pull, both test suites, private analysis, then
aggregate report-only commit/push. New work-check reports automatically carry test
outcomes; do not ask Tyler to paste terminal output or manually stage reports.
Read WORK_CHECK_RUNNER_REVIEW.md and the updated work-machine procedure first.

The runner's first two work-machine reports have returned in ad2ec8b and f38d81e.
Both validate, include successful suites (155 application tests with one skip;
139 helper tests), and report saved private runs with expected partial analysis.
Their reference aggregates match the previous report exactly except code revision.
The automated feedback cycle is verified. Do not repeat the runner implementation.

Tyler then authorized implementing module/I/O declarations and fixed aggregate
reasons for unresolved/unsupported-address bindings. That slice is now present:
inventory schema 2, reference schema 2, source aggregate schema 3 and reference
aggregate schema 2. Module InputTag/OutputTag/ConfigTag roots can bind using
explicit names or conservative supported topology; inferred names retain
provenance, and incomplete/ambiguous context remains a gap. RackConnection is
explicitly unsupported. Ordinary tag/alias counts stay separate from module I/O.
See MODULE_IO_REVIEW.md and DATA_CONTRACTS.md for exact scope and validation.

The new work-machine report has returned in f91ae18, testing clean 6585443.
work-check-20261013T234851Z-b10d84dc.json validates, records 208 application tests
(207 passed, one skipped) and all 139 helper tests passed, and reports saved
private output with expected partial analysis. All 252 I/O declarations receive
names (164 backplane-slot and 88 module-name). Bound aliases increase 45 to 842;
unresolved aliases decrease 896 to 99. Bound operands increase 17,856 to 20,178;
unresolved operands decrease 2,642 to 320. Ordinary source counts, instruction
histograms, routine types, ladder metrics and reference coverage are unchanged.
No additional work-machine run is needed merely to review this report.

The remaining unresolved aliases/operands are all colon_root_not_declared,
but their relationship to 11 unsupported rack connections is unproven. The
870 unsupported-address operands comprise 868 malformed_address and two
non_static_array_index. The first label describes the current grammar's limit,
not confirmed invalid source. Prioritize safe aggregate shape evidence for those
868 cases before expanding the grammar. Separate missing declarations from
unsupported syntax and never request private addresses or source/reference
reports here. Root binding still does not validate members, types, effects,
alarm consequences, control loops or equipment/sequence classifications.

Tyler has explicitly authorized the listener; implementation and review are complete.
Process each new work report once, continue only agreed work and stop for user
questions, investigation or phase decisions. Avoid overlapping repository writers
and loops triggered by the development agent's own pushes. Activation must be
verified and recorded in FEEDBACK_LISTENER.md, not assumed from authorization.
Before interactive edits on a development PC with the listener installed, check
`bash ./feedback-listener.sh status`, pause monitoring, and let any running worker
finish before taking over. Its dedicated worker must not pause its own listener.

Tyler clarified confidentiality on 2026-10-13: unit reconstruction with data
values, or more than 2% rung knowledge. Aggregate summaries contain no individual
rung logic or process values and are approved for sync in public/inspection/.
Do not reintroduce an extra per-report sharing gate. New source/reference
aggregates use schemas 3/2 with policy 2. The validator retains the preceding
source schema 2 and reference schema 1 with its schema-2 source; hybrid versions
are rejected. Already-generated v1 source summaries remain historical feedback.
The full `inspect` output still stays private. Read D026 and the current handoff.

The historical allocation-limit finding above is fixed in the shared grammar.
The new reader captures bytes once; the earlier two-pass public helper retains
its documented changing-input limitation. Scrubbed opcode labels remain run-local
and are not persistent source or engineering identities.
