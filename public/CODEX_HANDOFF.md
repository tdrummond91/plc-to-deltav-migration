# Codex handoff: PLC analysis workbench

Updated 2026-10-09. Current slice: **Stage 5 helper ready; user copy/test/run pending**.

Tyler wants one small helper at a time: provide code, let him run it, inspect the
result, then implement the next piece. Do not jump directly to a complete dummy
generator or migration framework.

## Current status

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

## Stage 5: first minimized fixture helper ready; user run pending

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

Default --per-variant 5 samples consecutive equivalent local runs. Mandatory
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

Actual Stage 5 retained counts and output size remain unknown. The unchanged
source should still report 83,942 elements, 194 paths and 4,606 ladder rungs.
Immediate next step: Tyler copies the additions, runs 118 tests, runs
minimize_l5x.py on the local original, and returns the console summary. Codex
then reads the two generated public files, reviews sampling and replacements,
and makes the next bounded correction. Do not claim a real-input run before it
happens or expand semantic conversion work before reviewing this first result.

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
| Minimized dummy L5X | Stage 5 helper tested; actual user run/output inspection pending |

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

Earlier planning remains under `docs/planning/`: ARCHITECTURE, DATA_CONTRACTS,
CLI_AND_REVIEW, L5X_STRUCTURE, ROADMAP, CONFIDENTIALITY, and DECISIONS. Treat it as
a proposal subject to actual-structure findings and the staged sequence above.

## Progress and handoff maintenance

Stages 3 and 4 results are recorded above. Stage 4 user tests and source run
succeeded, and Codex inspected the generated public report. The first minimized
L5X generator is now implemented/tested in the Stage 5 handoff; actual user run
and output inspection remain pending.
Keep user-reported runs distinct from inspected output and semantic validation.

After each slice, update:
- implemented behavior and schema/script versions;
- actual commands run, results, and limits of those results;
- unresolved structures and unsupported syntax;
- agreed next bounded step.

Keep real tag names, plant paths, raw ladder text, confidential hashes, and private
diagnostics out of this public document.
