Read public/CODEX_HANDOFF.md and
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

Expected baseline: 130 passing tests.
This baseline and the minimized_review public audit passed locally on 2026-10-12.
For documentation-only changes, review the diff and links; do not describe an old
test run as fresh execution.

Summarize the current architecture, implemented capabilities,
limitations, and propose the next bounded development milestone.
Wait for agreement before implementing that milestone.

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

## Proposed next bounded implementation slice

Build a snapshot-bound source inventory with selected-rung evidence and explicit
gap reporting. Generate JSON and readable views from one reusable result model.
This proposal needs selection before implementation; the five-phase application
is not the scope of a single refactor.

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
