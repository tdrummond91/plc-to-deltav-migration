# Codex handoff: PLC analysis workbench

Updated 2026-10-12. Current activity: **scope discovery on chore/project-scope-review-pc; five product phases confirmed, next implementation slice not yet selected**.

## Current scope and PC checkpoint (2026-10-12)

Tyler confirmed a reusable migration tool for several units. The five product
phases and workflow are recorded in docs/planning/ROADMAP.md and decisions D013-D024.
L5X analysis has two parallel outputs: information/scanning reports for source
understanding, and editable engineering files used to organize objects and build
the PCSD. Both need links to the same source evidence. PCSD feedback, class-based
FHX generation and FHX-to-PCSD are explicitly in the long-term scope.

Review runs Tyler -> Quebec -> Tyler -> development team -> Tyler. Approved
corrections must survive reruns. Changed, expanded, collapsed, split or combined
objects require reconciliation rather than losing prior decisions.

PCSD means Process Control Strategy Document. The earlier MOD-to-DeltaV workflow
used Excel, which was accessible to users but difficult to organize and version.
The PCSD supports generating plant test sheets for a DeltaV unit and simulation.
Candidate content includes I/O, selectors, PID relationships/flowcharts,
sequences/transitions, alarms, communications, external references, Boolean and
floating-point calculations, valves and pumps. Source understanding comes first;
the final PCSD content/schema is not settled. L5X sequences may require explicit
engineering design, and source grouping is not automatically target unit/module
or execution-location grouping.

Tyler prefers a standalone editor with search, useful navigation, change review,
import/export and backups, while retaining Excel if it proves useful. Design
deployment for non-programmers without a separately installed Python runtime.
SQLite as a local project store and PyInstaller-style Windows packaging are
recommendations to evaluate, not installed components or confirmed selections.
Tyler prefers sequential review initially: one active editor, followed by a
revision-bound handoff to the next reviewer. Validate returned changes against
their base revision and flag stale copies. Shared live editing and concurrent
copy reconciliation are later options, not initial requirements.

Only non-proprietary code/tools and reviewed development artifacts travel through
Git. Real L5X files and private engineering state stay local. Tyler may supply
bounded summary reports and stripped dummy ladder examples for development;
these should not enable reconstruction of the complete process.

On this editing PC, origin was fetched and main matched origin/main at bafc410.
Created local branch chore/project-scope-review-pc as requested. This scope
checkpoint is intended as one documentation commit; use git log/status for the
current commit/push state. All 130 helper tests passed, and the read-only
minimized_review audit passed (7,303 source links, 276 rung records, 194 paths,
431 variants). No confidential source was read. Changes in this scope discussion
are documentation only. Future PC development branches must end in -pc.

Scope-document validation: reviewed the changed requirements/proposals, checked
the referenced local review entry point, and passed git diff --check. The helper
test/audit results above are from the initial repository inspection in this
session; documentation changes did not trigger a repeated test run.

A separate ChatGPT chat will review the work. Keep focused conventional commits,
decision rationale, useful code comments and reproducible validation notes. Read
docs/reviews/NEXT_DEVELOPMENT_PROMPT.md (relative to public/) for the review entry
point. When work-machine turnaround is slow, Tyler may test up to three sibling
experiment branches from a common baseline and return their comparable results.
This is a workflow option, not a request to create three branches immediately.

The sections below retain the earlier work-machine evidence and chronology.
Their pending Git/checkpoint statements describe those earlier sessions, not
this PC's current state. The five product phases are distinct from helper
Stages 1-5 and the earlier technical implementation milestones.

Tyler wants one small helper at a time: provide code, let him run it, inspect the
result, then implement the next piece. Do not jump directly to a complete dummy
generator or migration framework.

## Historical inspection status (2026-10-09)

- Stage 1: Tyler reported 19 tests passed and supplied the counts JSON. Its nested
  counts reconcile with 83,942 elements, 213,876 attributes, 194 paths and depth 14.
  Codex did not read the original confidential input.
- Stage 2: Tyler reported "no errors". Codex has now independently audited the
  complete public skeleton against Stage 1: all structure/counts match, all
  attribute values and direct text are blank, and CDATA counts reconcile.
- Stage 3: Tyler supplied 58 passing tests and a successful real-input run:
  194 paths, 213,876 attribute values, 70 routines. Codex read the generated public
  JSON and reconciled value accounting and source totals with Stage 1. The original
  confidential export was not read.
- All work by Codex remains in task handoff artifacts. No repository/Git writes.

## Reviewed Stage 3 findings

The report accounts for all 213,876 attribute values: 90,414 approved technical
literal observations plus 123,462 withheld observations. Per-field occurrence,
unique-value and missing-attribute counts reconcile. Source totals match Stage 1.

Routine types: 56 RLL and 14 SFC. Exactly one reported Routine has no child
elements: global routine ordinal 68, located at
/RSLogix5000Content[1]/Controller[1]/Programs[1]/Program[2]/Routines[1]/Routine[1].
Its declared Type is RLL. This explains the 70-record/69-content-block gap.
The empty element is observed; intentionality is not established.

Tag kinds across controller/program scopes: 5,364 Base, 941 Alias, 2 Produced.
Declared Tag datatypes include 2,993 BOOL, 1,536 REAL, 434 TIMER, 129 DINT,
39 INT, 27 MESSAGE, 7 SINT, 4 CONTROL and 3 COUNTER observations.
194 Tag DataType observations remain withheld (177 controller, 17 program);
do not label them all as custom or infer the actual names.

Across Data and DefaultData elements: 5,597 Decorated, 5,511 L5K and 27 Message
formats. These are representation counts, not separate tag counts.
Task types are 1 CONTINUOUS and 2 PERIODIC; actual scan rates remain withheld.

## Stage 4: rung inventory implemented and reviewed

The helper is ready as a task handoff. It adds:
- `tools/l5x_inspect/inspect_rungs.py`: arguments and console summary.
- `tools/l5x_inspect/rungs/syntax.py`: pure neutral-text structure parser,
  measurements and sanitized representations.
- `tools/l5x_inspect/rungs/inventory.py`: XML reading, coverage, grouping,
  ranked samples and JSON publication.
- Two test modules plus RUNGS.md and RUNG_VALIDATION.md.

The 58 unchanged earlier tests and 36 new tests passed together (94 total).
CLI help passed. Tests used invented in-memory inputs and mocked writes.
Tyler has now copied the helper, passed all 94 tests locally, and run the actual
export successfully. Codex reviewed the generated public report; see below.

Default output: `public/rung-structure.json`, schema_version 1, parser_version 1.
Coverage accounts for every encountered ladder rung as parsed or unparsed, and
separately counts ignored non-ladder Rung elements. Program and AOI ladders are
included. The actual report accounts for all 4,606 ladder rungs as parsed.

The JSON provides per-rung ordinal locators, numeric Number, approved Type,
metrics, pattern IDs and diagnostic codes; pattern records link back to rung IDs.
It counts instruction calls, argument positions, expression-bearing instruction
calls (CMP/CPT/FAL/FSC only), branch groups/legs, depth, normalized height and
normalized width. Inner expressions remain opaque. Height counts parallel lanes;
width counts instruction boxes and excludes wiring. These are structural measures,
not Studio pixels, execution timing or proof of behavioral complexity.

Shapes preserve ordered instruction labels, arity, empty argument positions and
branch topology. Operand values, reuse and inner expression structure do not
define shape identity. Select up to five distinct shapes per ranking by default:
tallest, widest, deepest and most frequent. The sample list is deduplicated across
rankings; tied scores use first source occurrence.

Samples retain the authorized instruction/branch layout with every nonempty
whole argument replaced by ARG placeholders. Identical stripped arguments share
a label only within a sample. Unlisted instruction names become run-local
UNLISTED_OP labels; this is not a declaration that they are custom or invalid.
No raw comments, identifiers, operands, source filename/path or source hash
enter the report. Private mappings are not persisted in this slice.

PASS means all encountered ladder rungs were structurally parsed. PARTIAL means
a report was still saved, with unparsed locators and error codes; valid runs
return exit code 2 in this case. Measured totals and rankings cover only parsed
rungs. No partial instruction counts are guessed from failed rungs.

Keep the original source local. Ladder branching is parsed from Rung/Text, not
the XML Branch elements belonging to SFC. Syntactic samples do not establish
semantic equivalence or Studio import validity. The complete minimized dummy L5X
and general ASCII renderer remain later slices.

## Reviewed Stage 4 findings

Tyler ran all 94 tests successfully in 0.037 seconds, then ran the helper on
the actual local export. The console reported PASS. Codex subsequently read
public/rung-structure.json and independently recalculated its shape metrics,
weighted totals, rankings and occurrence links from the saved public trees.
The confidential source was not opened by Codex.

- 4,606/4,606 ladder rungs parsed; 0 unparsed; 0 metadata findings.
- 4,604 program rungs and 2 AOI rungs; totals agree with earlier stages.
- 554 distinct ordered structural shapes; every rung links to exactly one.
- 17,874 instruction calls; 24,583 argument positions, all nonempty.
- 3,719 branch groups; 8,887 branch legs; no empty branch legs.
- Maximum nesting depth 4, height 59 lanes, width 18 instruction boxes.
- 46 expression-bearing calls: 45 CPT plus 1 FAL. Inner mathematical operators
  are not counted.
- 19 selected samples after deduplicating the four top-five rankings.
- All sample operands were checked as ARG placeholders; rendered sample text
  matches its saved tree and shape. This is an output-format check, not a
  comparison against original confidential values or a general secrecy proof.

The tallest example is pattern_00038, rung_000237, original rung Number 5.
It has 94 calls, 6 branch groups, 64 total legs, and depth 2. Its outer branch
has 49 legs; five nested three-leg branches add ten lanes: 49 + 5*(3-1) = 59.
Its normalized width is 3 instruction boxes.
The widest example is pattern_00420, rung_003215, Number 33: width 18,
height 6, depth 2, 25 instructions.

The most frequent shape, pattern_00048, occurs 999 times:
XIO(ARG_001)OTU(ARG_002);. Equal shapes do not prove equal behavior.

UNLISTED_OP_0001 occurs exactly once, in pattern_00007 / rung_000007:
ordinal locator
/RSLogix5000Content[1]/Controller[1]/Programs[1]/Program[1]/Routines[1]/Routine[1]/RLLContent[1]/Rung[5],
Number 4. Its structure parsed successfully. Its original mnemonic remains
unknown and masked; do not infer that it is custom or invalid. It is outside
the 19 ranked sample selections; retain a sanitized representative for this
case in the next dummy fixture.

Source totals still match Stages 1 and 3: 83,942 elements, 213,876 attributes,
194 paths, depth 14. All 554 shape metrics, 4,606 occurrence links, weighted
instruction/branch totals, four rankings and 19 sample/tree links reconciled.
No new parser correction is indicated by this report review.
This verifies report consistency, not instruction semantics or Studio validity.

## Stage 5: first minimized fixture generated and reviewed

The handoff adds minimize_l5x.py, dummy/model.py, dummy/selection.py and
dummy/build.py under tools/l5x_inspect/, plus test_minimize_l5x.py, MINIMIZE.md
and MINIMIZE_VALIDATION.md. Earlier helpers and the application are unchanged.

The helper opens the original export read-only and recomputes its rung inventory.
It requires complete rung parsing and no rung metadata findings. It sanitizes
values, selects representative XML, writes a structural L5X example and a
companion report. No dependency installation is needed.

Default outputs:
- public/fixtures/minimized/controller_demo.L5X
- public/fixtures/minimized/minimized-report.json

The initial policy-1 --per-variant 5 sampled consecutive equivalent local runs.
The reviewed policy-2 handoff counts first N occurrences per variant under each
retained parent, including interleaved variants. Mandatory
anchors retain the first occurrence of every global local variant, the ranked
ladder examples, every instruction label (including masked ones), and all needed
ancestors. Selected ladder Rung subtrees are retained completely. Retained
siblings stay in source order. The cap is not a global five-per-element limit.

Variant identity includes path, attribute names/categories, approved technical
values or masked datatype identity, collapsed ordered child-name runs, source
direct-text/CDATAness and text action. It is not full subtree or behavior
equivalence. Publication checks all source paths and variant IDs are represented
and verifies emitted element/attribute counts.

Stage 3 approved technical literals and numeric rung Number/approved Type remain.
Other identifiers, datatypes, descriptions and scalars receive invented values.
Whole recognized identifier/reference strings share run-local DUMMY_ID labels;
other datatypes share DUMMY_TYPE labels. Ladder ARG labels are separate per rung.
No scope/member/reference resolution is claimed. Private replacement dictionaries
exist only in process memory; every retained element has public source/output
ordinal XML locators for back-reference.

Serialized non-ladder text, ST lines and mixed direct text receive explicit
placeholders and are reported. Original comments/PIs are omitted and counted.
Task/SFC links, array dimensions/indices and member references are not repaired
for semantic coherence. Output is for structural parser development; controller
import/operation has not been validated.

The coverage JSON records source/retained/omitted elements, attributes and text
values by path, selection reasons, replacement action counts, unsupported retained
payloads, rung records and source/output occurrence links. output_sha256 hashes
the generated XML only. XML and report are individually atomic, with XML written
first and report second; they are not one atomic two-file transaction.

Validation completed:
- 118 combined tests passed (94 unchanged plus 24 new), 0.116 seconds.
- CLI help passed.
- Full actual public skeleton verified: 83,942 elements, 213,876 attributes,
  194 paths, depth 14, 18,351 CDATA-bearing elements, all values/text blank.
- An in-memory integration using the 19 approved public rung examples plus the
  masked-opcode shape passed. From 20 inputs it selected 16 with per-variant 1
  and preserved depth 4, 49-leg maximum, 59-lane height and width 18.
- No confidential export was opened and no repository/Git writes occurred.

Actual Stage 5 run and public-output review are complete.

Tyler passed all 118 tests locally (0.057 seconds), committed the helpers and
earlier reviewed public reports as 6c50244, and successfully pushed main to
origin/main. The push created the remote branch and set tracking. The new
minimized files were generated afterward; no subsequent commit/push was reported.

The real-input generator reported:
- 44,545 of 83,942 elements retained; 39,397 omitted.
- 194 of 194 XML paths and 431 of 431 local variants represented.
- 2,397 of 4,606 ladder rungs retained, covering 458 of 554 source shapes.
- All 42 encountered instruction labels represented, including the masked one.
- 4,171 opaque payload replacements, 107 ST-line replacements and 12 mixed-text
  replacements among retained elements.
- Generated XML 4,078,792 bytes; companion report 14,379,883 bytes.

Codex read the two public files and ran a read-only audit, without opening the
confidential original. The generated XML hash matches its report. Every one of
44,545 output/source occurrence links was verified against the full blank
skeleton, including unchanged element names and attribute-name sets. All 194
per-path source/retained/omitted counts reconcile with the earlier reports and
actual output. All 2,397 rung source records, metadata, shapes and metrics match
the Stage 4 report. All 19 ranked source examples and 42 instruction labels remain.
Maxima remain depth 4, 49 direct legs, 59 lanes and width 18. All 108,252 output
attributes were checked against the stated public/dummy value categories, with
zero findings. All 13,131 nonblank direct text fields, including whole ladder
operands, passed their replacement-policy checks.

These checks verify output structure, provenance and stated replacement policies;
they do not establish instruction semantics, coherent runtime references, Studio
import validity or a general confidentiality certification. Public source/output
ordinal locators apply to this source ordering only.

## Stage 5 review corrections: installed and verified by user

The independent review confirmed two issues. See
public/docs/reviews/STAGE_5_CODE_REVIEW.md and
public/inspection/stage_5_corrections.json for original file/line evidence.

1. The sampler reset its quota between consecutive variant runs. It now counts
   the first N occurrences of each variant across each retained parent.
   Mandatory anchors and their ancestors, full selected rung subtrees, global
   path/local-variant coverage, ranked examples, instruction representatives,
   source ordering and occurrence mappings are retained.
2. Skeleton publication checked counts/text but could accept nonblank attributes.
   parse_structure now has an opt-in require_blank_attributes gate, enabled when
   create_skeleton verifies its completed output. A failing gate prevents
   publication without printing the unexpected value.

The new minimized report uses schema_version 2 and policy_version 2.
selection.per_parent_variant_limit replaces per_consecutive_variant_run.
Other report schemas are unchanged. Variant identity itself is unchanged;
retained parents may lose entire later child-name runs when redundant examples
are omitted. The full blank skeleton remains the authority for complete nesting.

Twelve new tests were run against the unchanged helpers first: four expected
failures established the two quota cases, version contract and skeleton gate.
After the bounded correction, all 130 tests passed in 0.182 seconds. Existing
count, parser, sanitizer and publication tests also passed. Tests use memory
and mocks, with Python -B; no workspace writes or confidential reads occurred.

The existing policy-1 public pair was freshly audited: 44,545 links, 2,397 rung
records/shapes/metrics, 194 paths, 431 variant IDs, all 19 source ranked samples,
42 instruction labels, counts, source order, full retained rung descendants and
replacement policies reconciled. The actual public skeleton also passed strict
blank-attribute verification; no existing retained attribute value was found.

A separate in-memory re-minimization of the existing public fixture retained
7,303 of 44,545 elements and 276 of 2,397 rungs. It preserved 194 paths, 431
variants, 19 rankings selected for that public input, all 42 instruction labels
and maxima depth 4 / direct legs 49 / height 59 / width 18. Every retained source
link and rung tree was checked. These are public-fixture integration counts;
that check did not regenerate the original confidential source. The subsequent
user-run original-source results are recorded below; keep the two evidence
sources distinct.

The handoff files are under the task outputs/l5x-inspect-stage-5-fixes directory.
Tyler has installed them; both pre/post-install verification checks passed.
Codex did not install files in the repository. COPY_AND_RUN.md contains bounded
backup/copy commands. verify_handoff.py checks all destination code/document
hashes before replacement and detects skipped/changed files after installation.
It handles line-ending differences only, not other edits. The package also
contains unchanged helper snapshots for task-local tests; copy only the paths
listed in install-files.txt, never the whole snapshot.

## Policy-2 original-source run and public review: complete

Tyler supplied the completed install/test/generation/audit output. Both checks
verified 13 handoff files and 12 dependencies. All 130 tests passed in 0.061
seconds. The original-source run produced public/fixtures/minimized_review.
Codex read that public JSON and generated XML bytes, confirmed schema/policy 2,
reconciled the report summary and independently verified its generated-file hash.
Codex did not open the confidential original or repeat the production run.

Actual original-source coverage:
- 7,303 of 83,942 elements retained; 76,639 omitted.
- 194/194 XML paths and 431/431 local variants represented.
- 276 of 4,606 rungs retained, representing 161 of 554 ladder shapes.
- All 19 ranked source examples and 42 instruction labels preserved.
- Maxima unchanged: branch depth 4, direct legs 49, height 59, width 18.
- 204 opaque payload, 78 ST-line and 11 mixed-text replacements retained.
- Output: 18,539 attributes; 1,493 nonblank text-bearing elements;
  1,016 CDATA-bearing elements; XML depth 14.
- XML 714,140 bytes; JSON 2,854,812 bytes.

The user's public checker returned PASS: generated XML hash matches; all 7,303
occurrence links and 276 rung shape/metric pairs verified; all required path,
variant, ranked-example and instruction-label coverage accounted; zero attribute
policy findings; all 1,493 nonblank text fields passed policy checks.
These are user-run checker results plus Codex's direct public-report/hash review.

The previously oversized parent/variant group fell from 614 retained rungs to 7.
Codex inspected their recorded source locators and mandatory selection reasons:
first five ordinary examples plus one CTU and one RES instruction representative.
The two extra examples are intentional quota exceptions, not counter resets.

The fixture is representative, not complete ladder-pattern coverage. The full
rung-structure.json retains all 554 shape records and all 4,606 rung occurrences.
Keep the policy-1 minimized folder as a comparison until a separate cleanup is
chosen. No helper code changed after the 130-test review checkpoint.

See public/inspection/stage_5_run_review.json for the portable result record.

## Next bounded step: documentation checkpoint and Git review

Copy the updated handoff and stage_5_run_review.json from the task
outputs/l5x-inspect-stage-5-run-review directory. Then Tyler should fetch origin
and return git status and ahead/behind evidence before commit/push instructions.
No new commit/push is reported. The earlier successful main push is the last
confirmed remote event; Codex has not fetched or modified Git.

Generated references, array dimensions/indices, sampled SFC graphs and opaque/ST
payload placeholders remain outside semantic validity. Two output files are
individually atomic, not a transaction. GUI, translation and DeltaV conversion
remain deferred. Next development scope should be chosen after this checkpoint;
do not start another broad implementation automatically.

## Stage 3 report contract

The report includes source_totals, coverage, policies, routine_coverage and paths.
Every path row has an element count and per-attribute/direct-text statistics:
occurrences, distinct parsed strings, lexical-type counts, approved technical
literal counts, withheld counts, invented examples, and missing-attribute counts.

Lexical types are syntax categories. Integer 0 is not proof of BOOL or DINT.
Same-element DataType context is reported separately for Value/ForceValue or
direct text; parent inheritance and tag/reference resolution are not implemented.
Date-like shapes are not calendar validation. Distinct strings are kept only in
local process memory and are never dumped, hashed into the report, or sent online.

An explicit limited permission list allows common builtin types, routine types,
task types, TagType, Radix, ExternalAccess and selected documented Data formats.
Unrecognized values stay withheld but counted. Do not label all withheld types
as custom: some may be valid builtin types outside the initial list.
A small repeated value set is only a heuristic, never permission to emit values.
Actual descriptions, identifiers, constants and source logic remain absent;
examples are independently invented placeholders.

Routine records use ordinal XML locators, not names. Direct children establish
content coverage; STContent inside an SFC transition condition does not establish
an ST routine. Missing/multiple/mismatched blocks and protection markers are
review findings, not proof of an invalid PLC project. Ordinal locators apply only
to this source ordering, not as stable IDs across future reordered exports.

Opaque payloads are not decoded. Stage 4 now implements outer ladder syntax and
structural dimensions. Semantic analysis, persistent mappings, translation and
GUI logic remain separate future work.

## Findings from the Stage 1 JSON

There are 3 programs, 3 tasks, 120 Module records, 1 AOI definition,
70 Routine records, 4,606 ladder Rung elements, and 6,307 Tag elements
(6,261 controller plus 46 program). InputTag/OutputTag/ConfigTag, AOI Parameter
and AOI LocalTag records are different element types and excluded from Tag counts.

55 RLLContent blocks comprise 54 program blocks plus one AOI block.
14 SFCContent blocks contain 14 Branch elements and 34 Leg elements.
The 155 STContent blocks are under SFC transition Conditions.
No EncodedData element is present in this particular report. DataTypes exists
without child definitions; this alone does not exclude custom type references.

Resolved by Stage 3: one RLL Routine has no child elements. See the reviewed
findings above for its ordinal XML location.

Different Data representations and scopes must stay distinct. Profile Format
values before interpreting payloads; a Data count is not a tag count.

## Required eventual outputs

| Output | State |
|---|---|
| Nested counts JSON | User-run report inspected; totals reconciled |
| Full blank XML skeleton | Complete public skeleton independently verified against Stage 1 |
| Type/value profile | User run and public JSON reviewed; accounting reconciled |
| Minimized dummy L5X | Policy-2 original-source run and public audit passed; 276 sampled rungs with required coverage |

Full skeleton: preserve every element, repeated instance, sibling order and
attribute name; blank all values, including Number, Type and DataType.
The later dummy L5X may retain approved technical values.

Tyler permits retaining sampled rung instruction and branch layouts, rung Number
and Type, with tag names and constants replaced. Include tallest/widest branch
examples and branch/expression-call counts. Stage 4 implements the first pass;
actual-input coverage and the saved public report have now been reviewed. Define metrics against observed
neutral syntax; do not infer ladder branching from SFC Branch elements or the
blank XML skeleton. Keep real reverse mappings in confidential/.


## Layout and machine boundaries

- `python-parser/`: current application prototype; do not refactor in this slice.
- `tools/l5x_inspect/`: standalone auxiliary inspection helpers.
- `public/`: portable documentation, invented fixtures, and reviewed structural
  reports/examples approved for sharing.
- `confidential/`: source exports, private derived data, mappings, logs, reviewer
  workbooks, and checkpoints. Inputs are under `confidential/plc-code/`.
- Root `.gitignore` excludes `confidential/` and Python environments/caches.
  Preserve the current ignore files; no replacement is needed for this slice.

Read the current machine's AGENTS instructions first. On the work machine, Codex
may only create handoff artifacts in its designated task artifact directory.
Repository files, configuration, Git metadata, and remote state are read-only.
Provide exact Git Bash commands for Tyler to run; do not execute them or request
permission to bypass that boundary. On an authorized editing machine, make the
selected changes directly within that machine's instructions.

Tyler created the renamed project copy, initialized Git on main, and configured
origin. Do not rerun git init, discard history, or add origin again. Current
working-tree/staging status and remote freshness were not verified for these
handoffs; a read-only Git status attempt was denied by the environment. Preserve
local changes and inspect status before staging. Fetch/check remote state must be
user-run before recommending a push; do not use force push to resolve rejection.

The old independently invented fixture passed Tyler's checker including l5x tag
access. That verifies the toy's internal checks, not coverage of his real export,
nor Studio 5000 import validity. Use it as a limited test fixture, not as authority
for the source schema.

## Broader direction retained

The future application should have a thin argument/UI layer and reusable parsing,
analysis, and reporting services. Ladder is the first detailed target. Inventory
must still count SFC and other routine types, tags by scope, tasks, modules, rungs,
and instructions such as JMP where their text can be parsed.

JSON should drive overview reports and a future GUI. Navigate from broad counts
and pattern groups down to concrete occurrences. Keep explicit links to source
locations and support many-to-many mappings; one classification can span rungs,
and one rung can have multiple classifications. Patterns alone do not establish
behavioral equivalence. Preserve scan order, jumps, timing/task context, and
inter-controller relationships during later execution-graph analysis.

Each stage must account for parsed content, preserved unknowns, deliberately
ignored content, and errors. Immutable original inputs, versioned checkpoints,
and review overlays must support resume, back-reference, and Excel export/import
round trips without silently overwriting prior decisions.

French/Quebec shorthand interpretation should eventually support AI suggestions,
uncertainty, unresolved items, and bilingual human review. Provider and data scope
are unresolved. A confidence score is not automatically a calibrated probability.
Keep a reversible glossary/mapping; do not alter the original source text.

DeltaV FHX conversion is deferred. Target library/version, mapping semantics,
execution behavior, acceptance tests, and the conversion design are not chosen.
No PLC download or runtime change is part of this work.

Earlier planning remains under `public/docs/planning/`: ARCHITECTURE, DATA_CONTRACTS,
CLI_AND_REVIEW, L5X_STRUCTURE, ROADMAP, CONFIDENTIALITY, and DECISIONS. Treat it as
a proposal subject to actual-structure findings and the staged sequence above.

## Progress and handoff maintenance

Stages 3 and 4 results are recorded above. Stage 4 user tests and source run
succeeded, and Codex inspected the generated public report. The first minimized
L5X generator has now passed the user run and public-output audit. The code
checkpoint was pushed; generated outputs have no reported subsequent push.
Fresh review corrections are installed by Tyler. Policy-2 original-source
generation and the public checker passed; Codex reviewed the generated public
report/hash and mandatory exceptions. Documentation checkpoint and user-run Git
review are next; no new commit/push has been reported.
Keep user-reported runs distinct from inspected output and semantic validation.

After each slice, update:
- implemented behavior and schema/script versions;
- actual commands run, results, and limits of those results;
- unresolved structures and unsupported syntax;
- agreed next bounded step.

Keep real tag names, plant paths, raw ladder text, confidential hashes, and private
diagnostics out of this public document.
