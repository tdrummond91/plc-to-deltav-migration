# Decision record

Planning revision 0.2 — 2026-10-08.

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

D010 supersedes the earlier transition plan to retain a root plc-code ignore rule. The new project copy has confidential/, public/, and python-parser/ at root. The user's root ignore file currently contains confidential/. The new copy has no .git yet. Old history and remote state remain unverified.

## Proposed for initial implementation

| ID | Proposal | Why |
|---|---|---|
| P001 | Package src/plc_workbench inside existing python-parser | Clear imports without moving the project immediately |
| P002 | argparse subcommands and generated help | Familiar standard library, separate command arguments |
| P003 | Typed JSON/JSONL contracts and immutable run directories | Readable state, GUI-friendly data, recoverability |
| P004 | Pydantic 2 persisted models, safe XML adapter, existing l5x wrapper | Validate contracts while retaining access to unsupported source data |
| P005 | File-based checkpoints first; SQLite only as a later index | Avoid premature database/event-platform complexity |
| P006 | Generic review decision protocol before specialized workbooks | Same semantics for Excel and future GUI |
| P007 | Structural patterns before cross-rung motifs | Validate grammar and references before wider inference |
| P008 | Python cache exclusions alongside confidential/ | Avoid virtualenv/build/cache files entering Git |

Proposals can be revised before their implementation slice. No GUI framework or conversion engine is selected.

## Open questions for the relevant milestone

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
