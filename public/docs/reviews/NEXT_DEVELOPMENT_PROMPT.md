Current checkpoint (2026-10-15): **CPT calculation access** connects the existing
expression trees to possible destination writes and individual tag reads.
Returned `cbb2965` tests clean `456786a`: all 175 newly supported instructions
and 336 operand slots were classified, and all 175 new data operands bound.
There are 17,701 classified instructions, 173 unsupported instructions, 595
unknown source operand roles and 321 unchanged binding gaps. All 695 application
cases passed (one expected Windows skip), as did 139 helpers. Six other summaries
match after removing only tool_revision; all 27 historical reports validate.

Current commands explicitly build access4 from authenticated calculation2
records. Expression reads remain separate from source operand counts, and repeat
occurrences retain their node/span links. Work21 requires access summary4 and
calculation summary2; work1-20 and explicit access2/3 replay remain frozen.
Review6/manifest9 still saves thirteen artifacts. The next work-machine run
checks the projected 45 CPT classifications and 132 expression reads. Only
bounded generated feedback is required; engineering/UI review remains optional.
Git synchronization stays manual and the listener stays disabled. See
[CPT access](CPT_ACCESS_REVIEW.md).

## Historical extended access implementation checkpoint

Historical checkpoint (2026-10-15): **extended explicit operand access** adds
counter controls, message controls, system-value operands and SFC-reset targets.
Returned `760448e` tests clean `36c0ff4`: all 45 CPT expressions now parse into
592 nodes, with 132 captured reference uses and all 45 destinations root-bound.
Four retained function calls use `SQR`; all expression-error counters are zero.
All 668 application cases passed (one expected Windows skip), as did 139 helpers.
Six earlier summaries match after removing only tool_revision. This establishes
syntax/root coverage for this export, not engineering validity or source-byte
identity. All 26 historical feedback reports validate.

Access3 owns the new bindings separately from unchanged reference6 evidence;
explicit access2 replay remains available. Work20 requires access summary3,
while work1-19 retain their exact contracts. Review6/manifest9 still saves
thirteen artifacts with actual nested versions. The next work-machine run
measures the new instruction families and binding gaps. Only generated feedback
is required; engineering/UI review remains optional. Git synchronization stays
manual and the listener stays disabled. See [Extended operand access](EXTENDED_ACCESS_REVIEW.md).

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

Historical checkpoint (2026-10-15): Phase 1 explicit instruction operand access
roles cover 34 supported mnemonic spellings with the timer/reset/copy extension.
Read [TIMER_COPY_ACCESS_REVIEW.md](TIMER_COPY_ACCESS_REVIEW.md),
[ACCESS_ROLE_REVIEW.md](ACCESS_ROLE_REVIEW.md) and
[WORK_MACHINE_REFERENCES_RUN.md](WORK_MACHINE_REFERENCES_RUN.md) first. Manually
pull the current `feat/bounded-operand-example-pc` branch, run the normal
`bash ./run-work-check.sh`, then
manually push the automatically committed feedback report. Supply the local
L5X filename on a checkout without a remembered source. No listener is required.

Returned `7cd9201` confirms initial access1 on clean `6642c5c`: 478 application
cases (one skip), 139 helpers and a saved private run. Access classified 16,952
of 17,874 instructions, retained 922 unsupported instructions and counted 321
binding gaps. Reference/source and SFC summaries remain equal to the preceding
`1332543` report after revision normalization. Tyler has not inspected the source/report and explicitly deferred
engineering and UI review. Do not require familiar-tag, SFC or navigation checks
before continuing parser work. The next work-PC run should return only its
generated aggregate feedback; optional engineering/UI review can happen later.

The new access layer labels possible explicit reads, writes, read-writes,
non-data and unknown operand uses. It is not an execution/effect model or a
dependency graph. Root groups do not establish overlap among member/index
suffixes. Unsupported instructions and invalid signatures remain unknown;
literal destinations cannot become bound write evidence. TON/TOF/RTO storage is
read-write only when both pseudo-operands are `?` or recognized integer literal forms;
those two slots are non-data. RES adds a possible storage write, while COP/CPS
add source-read/destination-write/length-read roles without range expansion.
Timing, initialization, datatype/range validation and execution remain unmodeled. Engineering
classifications, editable corrections, PCSD and FHX remain later milestones.
Do not infer semantics from pattern equality, JSR candidates, SFC links or
annotation ownership.

Historical extension evidence: 592 development cases pass with one existing symlink
skip. Two actual isolated runs, explicit then remembered source, each pass 496
application cases (one skip) and 139 helpers, with report-only local commits
and no Git network calls. Nine artifact hashes, canonical access2/review2 and
identical CLI artifacts verify. Seven legacy artifacts match `7cd9201` byte for
byte; source/reference/SFC summaries match after revision normalization. All 20
historical work1-13 reports validate.

Initial access1 evidence (historical): 574 development cases passed with one existing symlink skip.
Two final synthetic launcher runs each pass 478 application cases (one skip)
and 139 helpers, verifying manifest hashes, canonical access/review evidence
and identical CLI HTML. Seven legacy artifacts match baseline `1332543` byte
for byte on the same invented input; source/reference/SFC summaries match after
revision normalization. All 19 historical work1-12 reports validate.
The standalone command is `uv run --project python-parser
--locked plc review FILE --workspace PRIVATE_DIRECTORY`; the workspace is
required, the printed HTML path is private, and exit 3 is usable partial output.
At that checkpoint, review2 runs kept manifest5 with nine hashed artifacts, carrying private access2
as `access.json`. Work14 requires count-only access summary2; frozen work13
retains access summary1. Public
reference12/source4/SFC2 and private inventory3/reference6/SFC2 contracts remain
unchanged, as do plain reference manifest2 and standalone SFC manifest3.
Historical work1-13 and review1/manifest4 contracts remain readable. Preserve
the historical checkpoints below.

Read public/CODEX_HANDOFF.md,
public/docs/reviews/TIMER_COPY_ACCESS_REVIEW.md,
public/docs/reviews/ACCESS_ROLE_REVIEW.md,
public/docs/reviews/PROJECT_STATE_REVIEW.md,
public/docs/reviews/SFC_ANNOTATION_REVIEW.md,
public/docs/reviews/SFC_STRUCTURE_REVIEW.md,
public/docs/reviews/ROUTINE_GRAPH_REVIEW.md,
public/docs/reviews/ROUTINE_METADATA_REVIEW.md,
public/docs/reviews/ROUTINE_TARGET_REVIEW.md,
public/docs/reviews/ROUTINE_CALL_SHAPE_REVIEW.md,
public/docs/reviews/BIT_OPERATION_REVIEW.md,
public/docs/reviews/MATH_SIGNATURE_REVIEW.md,
public/docs/reviews/SYSTEM_FLAG_REVIEW.md,
public/docs/reviews/UNMATCHED_OPERAND_REVIEW.md,
public/docs/reviews/RACK_CANDIDATE_REVIEW.md,
public/docs/reviews/RACK_IO_INVESTIGATION.md,
public/docs/reviews/TIMER_PLACEHOLDER_REVIEW.md,
public/docs/reviews/ADDRESS_SHAPE_REVIEW.md,
public/docs/reviews/MODULE_IO_REVIEW.md,
public/docs/reviews/WORK_CHECK_RUNNER_REVIEW.md,
public/docs/reviews/SOURCE_REFERENCES_REVIEW.md and
public/docs/reviews/WORK_MACHINE_REFERENCES_RUN.md for the current
consolidated main baseline. Then read
public/docs/reviews/SUMMARY_EXPORT_REVIEW.md and
public/docs/reviews/SOURCE_INVENTORY_REVIEW.md first for the implemented
snapshot-bound source inventory on feat/source-inventory-pc, then
public/docs/reviews/STAGE_5_CODE_REVIEW.md.

Current instruction (2026-10-14): keep the development listener disabled and
paused pending the endpoint incident review. Tyler is proceeding with a fresh
clone and normal manual parser checks using the local-only workflow below.
Do not turn the listener hold into an approval requirement for manual parsing.

The listener launcher, tools/feedback_listener/ and its application test loader
are now ignored local development-PC files, removed from the tracked project.
They must not ship to the work machine or be required for parser tests. Existing
local copies remain disabled; source and operational evidence are archived.
Do not restore them to tracking as part of normal parser development.

The development history was squash-merged into main; documentation and evidence
remain intact. The archive/phase1-before-squash-20261014 tag retains historical
tested revisions. Start future work from main on a new -pc feature branch;
do not revive or merge the retired topic branches.

The updated work-machine runner operates on the already checked out clean named
branch, including main. Tyler clarified that local report commits should be
automatic; only fetching, pulling and pushing remain manual. No matching upstream
is required. The runner saves a validated feedback report to
public/inspection/work-check-<run-id>.json and automatically stages and commits
only that file, including failed test/analysis outcomes. It checks the tested
branch/revision, clean tree and report commit scope. Review the report, then run
git push manually. Old reports under public/inspection/local/ stay ignored and
are not included. Private log folders, source and workspaces remain under
confidential/ and must not be shared.

Work-machine suites now use explicit parser/helper allowlists, excluding
listener, Windows process-host, Bash bootstrap and Git-fixture tests. Full
development unittest discovery remains available, excluding the ignored listener
loader on this development checkout. Work schemas 1/2/3/4/5/6/7/8/9/10/11/12/13/14/15 remain readable. Current
schema16 requires reference12, SFC summary2, access summary2,
`analysis.tag_data_summary` schema1 and `analysis.pid_summary` schema1, and retains
at most one authorized operand example. Private review4/manifest7 runs contain
eleven hashed artifacts, including `tag-data.json` and `pid.json`.
The tested SHA identifies the suite implementation and scope.
Older instructions below that describe automatic Git publication or broader
work-machine tests are historical and superseded by this paragraph.

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

Current baseline: 139 passing helper tests. Also run the full development
application command in SFC_STRUCTURE_REVIEW.md, which explicitly excludes the
ignored listener loader. Do not run that local loader through broad discovery.

Use the final application test count and tested revision in TIMER_COPY_ACCESS_REVIEW.md;
one Windows symlink-capability skip is expected on this PC. The helper suite
passed all 139 tests again on 2026-10-13.
For documentation-only changes, review the diff and links; do not describe an old
test run as fresh execution.

The module/I/O slice is implemented and its returned work-machine report is
reviewed in MODULE_IO_REVIEW.md. The feedback listener remains installed but
disabled and paused under the current hold. Consult FEEDBACK_LISTENER.md for
concrete behavior, verification and current operational history.
The first follow-up has implemented a closed address-shape histogram for operands
outside the current grammar, without changing resolution. Reference aggregate
schema 3 adds seven fixed counters; private contracts, source aggregate and outer
work-check schema are unchanged. Read ADDRESS_SHAPE_REVIEW.md for precedence,
alias-target handling, compatibility, validation and limits. The diagnostic report
returned in b58af78 and was confirmed unchanged by the report in 46467af,
public/inspection/work-check-20261014T072717Z-4d71aaff.json. Both validate; all
868 malformed operand occurrences fall in other_form. Tyler explicitly clarified
that one actual mystery operand is within the sharing boundary. Schema 2 now
adds diagnostic_sample, separate from count-only reference summaries: at most one
exact operand of 128 printable characters with standard opcode/argument index.
Read BOUNDED_OPERAND_SAMPLE_REVIEW.md and TIMER_PLACEHOLDER_REVIEW.md. Report
349ee29 supplied `?` at TON argument 1. The timer correction is now confirmed
by report 1195d40, testing clean 112ee82: 177 application cases (one skip) and
139 helpers passed. Malformed/other_form 868 to 0, non_data 0 to 868,
unsupported-address 870 to 2; all other source/reference counters unchanged
and sample null. No repeat work-machine run is needed to confirm this fix.
Do not infer byte identity or timer configuration/effects from these aggregates.

The rack slice introduced private inventory/reference schemas 3/3,
source-inventory-3/source-references-4, public source/reference schemas 4/5,
and manifest2 (the original rack slice used work-check2). The current system-flag
slice below supersedes these reference/work-check versions. Read
RACK_CANDIDATE_REVIEW.md for rack validation.
Dedicated rack declarations and separate candidate diagnostics preserve ordinary
bindings. Public counts partition unresolved aliases, direct operands and
alias-mediated operands. Matching uses the terminal failed target and scope.
Candidates with unknown backing are never ordinary terminal root_bound symbols;
unsupported topology/content/attributes and ambiguity remain explicit.

Report `9597f18` now confirms all 15 rack roots are named; all 99 unresolved aliases
and 319 alias-mediated occurrences have unique candidates; one direct occurrence
has no candidate. It tested clean `9d159e0`, passed 220 application cases (one skip)
and 139 helpers, with source/reference counters unchanged except intended rack
capture/diagnostics. This measures logical candidate matches, not backing maps.

The completed one-address follow-up used work-check schema 3 with one bounded
sample, prioritizing eligible malformed operands before a direct unresolved colon
operand with canonical no_candidate_match evidence. The four fields and 128-character
bound stay unchanged; old schema 2 rejects the new kind. Private contracts and
count-only reference/source schemas stayed 3/3 and 5/4 respectively.

Report 7f5db96 tested clean 84dc393, passed 241 application cases (one skip) and
139 helpers, and returned S:FS at XIC argument 0. Other aggregates are unchanged.
The first-scan rule is now implemented and documented in SYSTEM_FLAG_REVIEW.md:
direct exact trimmed ASCII S:FS, ignoring case, in valid one-argument XIC/XIO
receives system_flag status. Raw evidence is preserved, with no declared-tag
binding or runtime simulation. Private references now use schema4/analyzer5,
public references schema6, work-check schema4; source and manifest are unchanged.
Historical status vocabularies and samples remain readable under their original
contracts. Current samples reject recognized S:FS even if other gaps remain.

Report d247f87 tested clean d64ee4d, passed 269 application cases (one skip) and
139 helpers, and confirms that delta: system_flag=1, unresolved operands 320 to
319, direct rack comparisons 1 to 0, sample null, with all other source/reference
counters unchanged. No repeat flag-only check is needed.

The preceding calculation slice added only ABS/LN/SQR two-field source/destination signatures
to existing lexical reference analysis. Private references stay schema4 with
analyzer6; public references use schema7; work schema5 requires reference7.
Source contracts and private manifest layout are unchanged. Public reference6
and work4/reference6 remain readable under their frozen earlier contracts.
Read MATH_SIGNATURE_REVIEW.md for exact primary evidence, validation and limits.

Report 4244cf5 tested clean a6a2a71, passed 286 application cases (one skip) and
139 helpers, and confirms all 28 signatures and 56 bound slots. Catalogued rises
17563 to 17591, root_bound 20178 to 20234 and unsupported instruction slots
fall 653 to 597. All other source/reference counters stay unchanged. No repeat
calculation-only check is needed.

The preceding bit slice catalogs MVM/SWPB with three fields. SWPB argument 1 is an
order-mode selector accounted as non_data by role before root/literal lookup;
the shared predicate rejects it as either diagnostic sample kind regardless
raw spelling. Arity/empty checks take priority. Mode values, masks, types,
destination access, byte ordering and execution effects remain unvalidated.
Private references are schema4/analyzer7; public references schema8; work6
requires reference8. All prior metadata/field contracts remain readable.
Read BIT_OPERATION_REVIEW.md for role evidence and exact validation.

Report 08c2695 tested clean bdf09f1, passed 296 application cases (one skip) and
139 helpers, and confirms all 26 signatures: catalogue 17,591 to 17,617;
unsupported slots 597 to 519; 52 newly bound roots, 16 literals and ten selectors.
Every other source/reference counter is unchanged. No repeat bit-only check
is needed. Do not infer runtime behavior from these lexical classifications.

The preceding slice observes JSR/SBR/RET argument shapes without changing binding
or catalog rules. Official RLL-neutral and ST tables differ, so no parameter
roles or routine links are assigned. Public reference9 adds closed shape counts;
private reference4/analyzer7, source3/aggregate4 and manifest2 stay unchanged.
Work7 requires reference9; work6/reference8 and all earlier contracts remain
readable. Private text receives captured inventory, including zero-field calls;
private JSON keeps the canonical result. Read ROUTINE_CALL_SHAPE_REVIEW.md.

Returned `0a2610f` tests clean `9c56b50`, passing 308 application cases (one skip)
and 139 helpers. JSR=76/163fields: 65 two-field second-zero and 11 three-field
second-other calls; SBR=1/onefield; RET=1/zerofields. Earlier counters are unchanged.
This establishes shapes without InputCount or parameter roles.

Preceding slice: private5/analyzer8, public10 and work8 add program-local declared
JSR first-field candidates. Existing tag/alias/operand/catalog/source/shape
evidence stays unchanged. Static ASCII names use a separate routine namespace;
self identity and explicit main/fault attributes provide limited context, other
requires Normal, phase names are not guessed. Non-RLL target envelopes remain
candidates. No call-validity, reachability or parameter claim is made. Read
ROUTINE_TARGET_REVIEW.md. Returned `7e15843` tests clean `3598710`: 325
application cases (one skip) and 139 helpers pass. There are 76 unique candidates,
66 distinct targets and 76 not_analyzed contexts; earlier counters are unchanged.

The preceding slice adds routine_target_metadata unique-call observations: exact
program-Type provenance and target-language declarations, with a program-Type
subset for unknown context. Public11/exporter11 keeps analyzer8/private5; work9
requires reference11. Earlier contracts remain frozen/readable. Do not default
missing Program.Type to Normal: the official example suggests it but no explicit
default rule was verified. Program Sequence is a documented enum;
EquipmentSequence remains unknown. Read ROUTINE_METADATA_REVIEW.md.
Returned `3431389` tests clean `5f91400`, passing 335 application cases (one
skip) and 139 helpers. All 76 program-Type observations are absent; call-weighted
languages are RLL62/SFC14. All earlier counters remain unchanged.

The preceding slice adds a static program-local declared-candidate JSR graph, grouping
repeated calls with private instruction links, isolated routine nodes, observed
structural body coverage, explicit main designations and iterative candidate
cycles. Private6/analyzer9, public12 and work10 record the new derivation. SFC
bodies remain unmodeled; no outgoing observed edges does not mean runtime leaf.
Missing Type is still not defaulted, and no parameters, scheduling, valid-call
or runtime reachability are inferred. Read ROUTINE_GRAPH_REVIEW.md. Returned
`2f37ae3` tests clean `e17ceeb`, passes 354 application cases (one skip) and 139
helpers: 69 nodes/68 pairs/76 linked calls, three repeats/eight extras, three
unique mains, one isolated node, no cycles/self edges. Earlier counts are stable.

Returned `90923ab` tests clean `f8411bc`: 416 application cases (one skip) and
139 helpers pass. The bounded SFC structural/annotation slice is complete for
this export: 280 Text-child boxes, 213 attachments with all 426 endpoints
resolved, zero SFC issues. All earlier reference and SFC flow/ID/ST counts are
unchanged. The report-only commit has its tested revision as parent. Overall
analysis remains partial; semantic/effect/member analysis remains unimplemented.
No repeat annotation-only work-PC run is needed. Read SFC_ANNOTATION_REVIEW.md
for confirmation and PROJECT_STATE_REVIEW.md for the independent state audit,
next user-facing milestone and provisional iteration estimates. That review's
recommendation to bundle a private engineering review package is implemented
and its generated output is confirmed by `1332543`. Initial access roles are
confirmed by `7cd9201`; timer/reset/copy roles and Tag Data capture have also
returned aggregate evidence. The current extension adds PID occurrence evidence.
The next work-machine run measures this evidence through generated aggregates; Tyler's deferred engineering/UI
review is not a development gate.
Preserve existing identity/provenance contracts and keep edits/correction survival
as explicit future design work, not a capability implied by immutable snapshots.
Continue authorized work until a specific evidence gap or phase boundary needs
Tyler's input. Do not activate the listener or access confidential inputs.

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
Tyler then requested a one-command work-machine runner. Its original workflow
was pull, both test suites, private analysis, then aggregate report-only
commit/push. Automatic pull/push is superseded by the local-report-commit workflow
at the top of this prompt. Work-check reports carry test outcomes;
publication requires review and a manual git push, with no manual commit step.
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

Tyler previously authorized the listener; the current operational hold supersedes
activation instructions. Keep it disabled and paused. Its designed workflow is to
process each new work report once, continue only agreed work and stop for user
questions, investigation or phase decisions. Avoid overlapping repository writers
and loops triggered by the development agent's own pushes. Activation must be
verified and recorded in FEEDBACK_LISTENER.md, not assumed from authorization.
Before interactive edits on a development PC with the listener installed, check
`bash ./feedback-listener.sh status`, pause monitoring, and let any running worker
finish before taking over. Its dedicated worker must not pause its own listener.

Tyler clarified confidentiality on 2026-10-13: unit reconstruction with data
values, or more than 2% rung knowledge. Aggregate summaries contain no individual
rung logic or process values and are approved for sync in public/inspection/.
The current requirement for manual report review/publication controls the runner;
it does not change which aggregate fields are approved for sharing. Current source/reference
aggregates use schemas 3/4 with policy 2 (the earlier module slice used 3/2). The validator retains the preceding
source schema 2 and reference schema 1 with its schema-2 source; hybrid versions
are rejected. Already-generated v1 source summaries remain historical feedback.
The full `inspect` output still stays private. Read D026 and the current handoff.

The historical allocation-limit finding above is fixed in the shared grammar.
The new reader captures bytes once; the earlier two-pass public helper retains
its documented changing-input limitation. Scrubbed opcode labels remain run-local
and are not persistent source or engineering identities.
