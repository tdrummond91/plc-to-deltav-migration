# Decision record

Scope revision 0.3 — 2026-10-12. Implementation proposals remain subject to the selected development slice.

## Confirmed by Tyler

| ID | Decision | Consequence |
|---|---|---|
| D001 | Separate arguments/main from analysis; plan for a GUI | Shared library services and typed results |
| D002 | Ladder structure first | Detailed RLL work precedes other language semantics |
| D003 | Main report must count SFC, tags, ladder, JMP, and other components | JSON inventory includes every language and explicit incomplete counts |
| D004 | One ignored confidential root | Inputs and derived plant artifacts all remain below confidential/ |
| D005 | AI interpretation for Quebec French/shorthand | Provider adapter, proposals, uncertainty, unresolved queue, and Quebec review |
| D006 | Iterative reviewer documents and checkpoints | Immutable analysis runs and validated decision batches |
| D007 | Pattern view with occurrence drill-down and reverse trace | Separate pattern definitions, occurrences, and source bindings |
| D008 | No conversion design yet | FHX generation deferred |
| D009 | Work GUI remains read-only for project changes | Temporary handoff files and exact user-run copy commands |
| D010 | Files moved by user into confidential/ | Use confidential/plc-code and preserve the existing target backup directory |
| D011 | Public portable materials and synthetic L5X first | Public fixture, expected results, origin record, and handoff before application refactor |
| D012 | Copy into new project name and start fresh Git/GitHub | Omit old .git and environment; preserve original until verified; user performs Git setup |
| D013 | Reusable tool for several units | Keep unit-specific source data and engineering decisions outside reusable code |
| D014 | Five phases: L5X understanding; editable files; naming/data corrections; PCSD with feedback; class-based FHX and FHX-to-PCSD | PCSD and FHX are explicit project scope; conversion implementation remains a later phase |
| D015 | L5X analysis feeds both reading/scanning reports and editable engineering files | Share parsed evidence and trace links; editable files support organizing objects for PCSD |
| D016 | Review involves Tyler, Quebec and the development team, with no fixed handoff order | Import downstream corrections and preserve review history; D025 clarifies routing |
| D017 | Reruns must preserve intended corrections even as objects or rung groupings change | Track decisions independently and reconcile split/merged/changed objects |
| D018 | Synchronize only non-proprietary code and reviewed development artifacts across computers | Real L5X/private state remain local; bounded summaries and stripped examples support development |
| D019 | Private GitHub repository, one developer across computers; PC development branches end in -pc | Fetch/check state and preserve local edits; commit, push and merge remain separate actions. Runtime checks also support main. |
| D020 | PCSD means Process Control Strategy Document and supports plant test-sheet generation | Capture source evidence and reviewed strategy; detailed PCSD content follows ladder understanding |
| D021 | Prefer a standalone editor for non-programmers, with Excel still an option | Search/navigation, change review, import/export, backups and deployment without user-managed Python |
| D022 | An independent ChatGPT chat will review development | Maintain clear handoffs, decision rationale, useful comments and focused conventional commits |
| D023 | Slow work-machine feedback may warrant up to three experiment branches | Branch from one agreed baseline, use -pc suffixes and comparable validation/reporting; consolidate after results |
| D024 | Prefer sequential reviewer handoffs initially | One active editor and revision-bound handoff packages; validate returned changes against their base and flag stale copies; concurrent editing is a later option |
| D025 | Sequential review does not prescribe participant order | Choose recipients per handoff; separate assignment/routing from the single-editor policy so future workflows can extend it |
| D026 | Confidential means reconstructing the entire unit with data values, or more than 2% rung knowledge | Aggregate summaries with no individual rung logic or process values are approved for repository sync; remove the per-report sharing gate and allow public/inspection/ output. Raw exports and full inventories stay private. |
| D027 | Work-machine commands must not automatically pull or push; normal parsing is allowed. Tyler clarified that report commits should be automatic. | Use local code and automatically stage/commit only the newly validated feedback report, including failed outcomes. Fetch/pull/push remain manual; older ignored local reports and private outputs are not included. |
| D028 | Consolidate the current development history into one main commit and retire old branches; preserve documentation | Keep tested revision provenance under an archive tag. Future development uses new -pc branches from main; this checkpoint does not complete Phase 1. |
| D029 | One actual mystery-operand occurrence is within Tyler's sharing boundary; counts alone are unnecessarily restrictive for this investigation | Work-check schema 2 may include one exact operand up to 128 printable characters plus standard instruction/slot, with no rung or neighboring process context. Standalone source/reference summaries remain count-only. |

D010 supersedes the earlier transition plan to retain a root plc-code ignore rule. The repository has confidential/, public/, and python-parser/ roles; confidential/ is ignored. D012's fresh-repository setup is complete: origin was fetched on 2026-10-12 and main matched origin/main at bafc410. D009 applies to the restricted work-machine environment, not every computer. D014 establishes the later PCSD/FHX scope while retaining D008's deferral of conversion implementation during source understanding.

## Proposed for initial implementation

| ID | Proposal | Why |
|---|---|---|
| P001 | Package src/plc_workbench inside existing python-parser | Clear imports without moving the project immediately |
| P002 | argparse subcommands and generated help | Familiar standard library, separate command arguments |
| P003 | Versioned typed records, JSON/JSONL exchange reports and immutable run evidence | Portable contracts remain useful whichever private storage backend is selected |
| P004 | Pydantic 2 persisted models, safe XML adapter, existing l5x wrapper | Validate contracts while retaining access to unsupported source data |
| P005 | Evaluate SQLite as the local editor's canonical store, with versioned exports and backups | Search, relationships and atomic review changes justify reconsidering the earlier files-first proposal; no database decision is finalized |
| P006 | Generic review decision protocol before specialized workbooks | Same semantics for Excel and future GUI |
| P007 | Structural patterns before cross-rung motifs | Validate grammar and references before wider inference |
| P008 | Python cache exclusions alongside confidential/ | Avoid virtualenv/build/cache files entering Git |
| P009 | Package a Windows editor with a bundled Python runtime, for example using PyInstaller | Users should not need Python, SQL or command-line knowledge; verify distribution on a clean target machine |

Proposals can be revised before their implementation slice. No GUI framework or conversion engine is selected.

### First slice implementation choices (2026-10-12)

These are engineering choices for `feat/source-inventory-pc`, not new user
requirements. P001 and P002 are implemented; P003 is implemented only for private
source records and run evidence. P004 remains a proposal: this reader uses
standard-library dataclasses and bounded Expat parsing, with no new validation
framework. Existing l5x remains for the unchanged prototype and fixture checker.

Capture bytes once before parsing so records and saved evidence share one input.
Use deterministic snapshot-specific IDs; do not claim decision continuity across
exports. Move the existing outer ladder grammar into the application package
and retain a repository-helper compatibility alias, adding instruction spans and
allocation limits instead of a competing parser. Require explicit private
workspace selection and a new directory per saved run; publish the manifest
last. Preserve unfamiliar XML and report gaps rather than invent declarations
from element names or claiming complete executable coverage. See
[implementation review](../reviews/SOURCE_INVENTORY_REVIEW.md) for evidence.

### Aggregate feedback implementation choices (2026-10-12)

Original implementation on 2026-10-12 (sharing gate superseded by D026 on 2026-10-13): build the return report from a closed set of aggregate
fields instead of redacting a copy of the private inventory. Reuse the existing
instruction publication vocabulary, pool unknown labels and omit occurrence
links/topology. Preserve structural partial status and explicit unimplemented
semantics. Validate numeric types, reconciled totals and parser bounds before
publishing a candidate capped at 32 KiB. Human review still determines whether
the exact aggregate counts may be returned.

Record the local code commit and code-worktree state without publishing a source
fingerprint or private path. Use atomic no-clobber publication for an explicit new
JSON destination; unsupported filesystems fail without an overwrite fallback.
Tyler authorized the feature-branch push and bounded work-machine check. This
does not authorize merging into main or publishing plant data.

### Root-reference implementation choices (2026-10-13)

After summary-002 matched the readable-source baseline, Tyler authorized continuing
with the next Phase 1 slice. Implement scoped root binding, alias traversal and
operand occurrences as a separate derived result; retain the source-inventory-1
contract. Use an explicit conservative signature catalog so routine labels and
instruction options cannot accidentally bind to same-named tags. Root lookup is
distinct from member/access validation, effects and engineering classifications.

Provide private `references` drill-down and a closed `reference-summary` aggregate
for the next work-machine run. A shared integrity check canonically reanalyzes the
captured inventory before either publication path; this avoids maintaining a
second set of binding rules and rejects mutated derived records. The second pass
does not read the source again and its initial synthetic cost is recorded in the
[reference review](../reviews/SOURCE_REFERENCES_REVIEW.md). Future optimization
must preserve these validation and publication boundaries.

The feature branch starts at the user's current remote report commit 3dd1b25,
preserves prior notes, ends in -pc and does not merge into main. Return aggregate
coverage before choosing broader expression, module, call or instruction-effect
analysis. These are implementation choices within the authorized slice, not a
final PCSD schema or an expansion of the source-sharing policy.

### Basic calculation catalog extension (2026-10-14)

After `d247f87` confirmed first-scan classification, choose ABS/LN/SQR as a
small Phase 1 reference slice. The returned public histogram contains 28 such
instructions. Official neutral-text grammar specifies two source/destination
fields, allowing reuse of the existing lexical catalog without private examples
or a math-expression parser. Preserve raw evidence and existing literal rules;
do not imply valid destination access, types, domains or execution behavior.

Version the changed analyzer/catalog and freeze prior public contracts. Verify
synthetic lookup/publication/persistence and a real work-machine aggregate before
claiming production counts. Additional alias-mediated occurrence counts may
appear when formerly unknown slots are analyzed. This is an implementation
choice within authorized source understanding, not a final loop/class mapping.
See [scope, primary sources and validation](../reviews/MATH_SIGNATURE_REVIEW.md).

### Bit-operation argument roles (2026-10-14)

After `4244cf5` confirmed the calculation catalog, select MVM/SWPB as the next
small Phase 1 reference slice. Official neutral grammar documents three fields
for each; SWPB's middle field is a list-item order selector. Classify that field
as non_data by positional role and share the predicate with diagnostic sampling,
so tag-like option text never becomes a binding or address example. Preserve
raw selector values without validating allowed mode spelling or byte ordering.

Reuse existing lexical root/literal rules for data fields; do not infer mask
widths, types, destination access or effects. Freeze prior contracts and confirm
the occurrence split using a normal work-machine aggregate. This is an authorized
source-reference implementation choice, not a final process classification.
See [primary evidence and validation](../reviews/BIT_OPERATION_REVIEW.md).

### Observe routine-call fields before assigning roles (2026-10-14)

After `08c2695` confirms bit-operation roles, choose a closed JSR/SBR/RET
argument-shape diagnostic. Rockwell's RLL-neutral and structured-text tables
show different layouts; generalized instruction help does not resolve that
difference. Do not assume the second ladder field is InputCount or copy SBR
parameter roles from structured text. Profile fixed arity bins and exact second
zero text without publishing names, argument strings or occurrence links.

Keep the binding catalog, analyzer and private JSON unchanged. Derive counts
from captured instruction records and make them available in aggregate JSON
and private text, including zero-field instructions. Confirm the real shape
distribution before a scoped routine-link slice; target resolution stays separate
from tag lookup and from execution/sequence interpretation. See
[the evidence and validation](../reviews/ROUTINE_CALL_SHAPE_REVIEW.md).

### Derive declared JSR candidates separately from parameter roles (2026-10-14)

Returned `0a2610f` confirms 65 two-field second-zero and 11 three-field
second-other JSRs, one one-field SBR and one zero-field RET. It does not establish
InputCount or parameter boundaries. RLL/ST reference tables agree on JSR's first
routine-name field, allowing a scoped declaration-candidate slice without
expanding the tag-binding catalog or interpreting later arguments.

Match static ASCII first fields only within the caller program's separate routine
namespace. Keep ambiguity and unsupported ownership explicit, and allow declared
non-RLL target envelopes. Identify known self/main/fault contexts from IDs and
program attributes; classify other only for Normal programs. Never infer phase
states from names or equate unique candidates with valid calls or reachability.
Private rows retain snapshot provenance; public feedback uses closed counts.
Read [the candidate contract and evidence](../reviews/ROUTINE_TARGET_REVIEW.md).

### Observe missing program context before assigning a default (2026-10-14)

Returned `7e15843` confirms 76 unique JSR declaration candidates and 66 distinct
targets, but all 76 contexts remain not_analyzed. Existing counters are stable.
The parser retains program attributes, and Rockwell's normal-program example
omits Type; no explicit omitted-Type default was verified. Keep candidate/context
results unchanged and derive closed unique-call program-Type/target-language
counts, separating absent, empty, known enums and other explicit values. The
unknown-context subset explains the gap without exposing labels or inventing
Normal/phase roles. The official program sequence enum is Sequence, distinct
from Routine.Type and an unknown EquipmentSequence spelling. See
[evidence and contract](../reviews/ROUTINE_METADATA_REVIEW.md).

### Map declared routine relationships before runtime interpretation (2026-10-14)

Returned `3431389` confirms all 76 candidate program-Type observations are absent
and target-language occurrences are RLL62/SFC14, with earlier evidence stable.
Retain that gap without inventing an omitted-Type default. Build a bounded
program-local graph of declared JSR candidates, grouping repeated calls while
retaining their instruction links. Include isolated nodes, explicit main metadata
and observed body coverage; use iterative SCCs for candidate cycles. Do not infer
SFC outgoing calls, runtime leaves, recursion, scheduling or parameter roles.
The graph supports private reading and future source-linked engineering records;
public feedback remains closed counts only. See
[the graph contract](../reviews/ROUTINE_GRAPH_REVIEW.md).

## Open questions for the relevant milestone

- Which parts of the earlier Excel PCSD/test-sheet format should be retained after understanding the L5X evidence?
- What information do developers correct, and when does a correction apply to one object versus a reusable parser/classification rule?
- Which changes happen in the source L5X versus the engineering representation, and what evidence should carry decisions across splits/merges?
- Which existing class libraries or generators will the PCSD/FHX adapters use?
- Which AI service or local runtime is approved, and what context may it receive?
- What exact review fields and workbook layout suit the Quebec team?
- What source export revisions and partial-export variants must be supported first?
- Are multiple controller snapshots synchronized, and how will peer identities be confirmed?
- Which missing language analysis should follow RLL?
- What private backup destination and retention policy should cover checkpoints?
- Which DeltaV library/version and engineering acceptance tests will eventually define conversion?

These do not block writing the source-reader contracts and initial synthetic tests. Provider approval/data profile does block real AI calls.

## Small glossary

- Adapter: code that translates one interface into another, such as L5X XML into project records.
- Model: structured in-memory data with named fields.
- AST: the ordered tree representing a rung's syntax.
- Provenance: records of where a result came from and which processing/review produced it.
- Schema: the contract defining fields, types, and required values in saved data.
- Checkpoint: a saved version of inputs, analysis, and decisions that can be reopened.
- Idempotent import: repeating the same import does not duplicate or reapply changes.
- Occurrence: a specific place in the source matching a generic pattern.
- Correspondence: a proposed link between entities in different source snapshots.
