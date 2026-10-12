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
| D019 | Private GitHub repository, one developer across computers; PC branches end in -pc | Fetch/check state and preserve local edits; commit, push and merge remain separate actions |
| D020 | PCSD means Process Control Strategy Document and supports plant test-sheet generation | Capture source evidence and reviewed strategy; detailed PCSD content follows ladder understanding |
| D021 | Prefer a standalone editor for non-programmers, with Excel still an option | Search/navigation, change review, import/export, backups and deployment without user-managed Python |
| D022 | An independent ChatGPT chat will review development | Maintain clear handoffs, decision rationale, useful comments and focused conventional commits |
| D023 | Slow work-machine feedback may warrant up to three experiment branches | Branch from one agreed baseline, use -pc suffixes and comparable validation/reporting; consolidate after results |
| D024 | Prefer sequential reviewer handoffs initially | One active editor and revision-bound handoff packages; validate returned changes against their base and flag stale copies; concurrent editing is a later option |
| D025 | Sequential review does not prescribe participant order | Choose recipients per handoff; separate assignment/routing from the single-editor policy so future workflows can extend it |

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
