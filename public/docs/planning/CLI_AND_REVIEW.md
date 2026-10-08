# CLI, reports, and human review

Status: interface proposal. The commands below are not yet implemented.

## Command design

Use subcommands instead of a growing mutually exclusive flag group. A subcommand is the named action after `plc`; for example, `plc tags` and `plc rung` have different arguments and help pages.

The top-level CLI owns argparse, dispatch, error rendering, and exit codes. Domain functions return data. The existing `main.py` becomes a compatibility entry point calling the package CLI. A future GUI calls the services directly.

Proposed entry point:

```text
plc ingest
plc overview
plc tags
plc rung
plc refs
plc patterns list | show
plc classify
plc translate propose
plc review export | validate | import
plc checkpoint list | show | diff
plc sample structure | redact | synthetic
plc trace
```

Each level has `--help`, a short purpose, argument meanings, one minimal example, one filtered example, formats, output location, and a statement of coverage limitations.

## Example workflow

Examples assume execution from `python-parser/` and use invented file/case names:

```bash
# Create a confidential source snapshot and inventory.
uv run plc ingest "../confidential/plc-code/example.L5X" \
  --workspace "../confidential/workspaces/case_001"

# Inspect a completed run.
uv run plc overview --workspace "../confidential/workspaces/case_001" \
  --run RUN_ID --format json

# List declarations, with scope and descriptions.
uv run plc tags --workspace "../confidential/workspaces/case_001" \
  --run RUN_ID --scope "program:ExampleProgram" --verbose

# Draw one source rung; require a fully scoped selector.
uv run plc rung --workspace "../confidential/workspaces/case_001" \
  --run RUN_ID --program ExampleProgram --routine MainRoutine \
  --number 12 --format ascii

# Draw synthetic text supplied directly, without an L5X file.
uv run plc rung --text 'XIC(A)[XIC(B),XIC(C)]OTE(D);' --format ascii

# Find readers/writers/calls through stable IDs.
uv run plc refs --workspace "../confidential/workspaces/case_001" \
  --run RUN_ID --entity ENTITY_ID --direction both

# Generic shape -> occurrences -> source nodes.
uv run plc patterns show PATTERN_ID \
  --workspace "../confidential/workspaces/case_001" --run RUN_ID

# Explain the proposal-to-source chain.
uv run plc trace FINDING_ID \
  --workspace "../confidential/workspaces/case_001" --run RUN_ID
```

`--text` and source-rung selection are mutually exclusive. Direct text is synthetic by default in documentation; pasting proprietary text into a terminal can save it in shell history. The private CLI should also support a local text file or stdin when direct entry is inappropriate.

When a rung number or name is ambiguous, list candidate IDs and require a more specific selection. Do not silently select the first result.

## Shared behavior

- Human output is concise by default; `--verbose` adds per-object context, coverage, and unresolved evidence.
- Machine JSON retains a documented stable schema and never includes terminal color codes.
- Use stdout for requested data and stderr for progress and diagnostics, so piping works.
- Handle a closed pipe cleanly when a user quits `less`.
- Read-only query commands do not create a run unless explicitly saving a report.
- Processing commands always create a manifest and diagnostic artifacts.
- File outputs are confined to the resolved confidential workspace. Reject traversal and symlink escape.
- Workspace paths are explicit/configured and resolved predictably; no hardcoded workstation path.
- CLI options override workspace settings, which override safe defaults.
- Secrets live in environment variables or an approved credential store; logs do not print them.

Proposed exit codes: 0 success; 1 runtime or validation failure; 2 argument usage error; 3 completed with partial coverage. Document the distinction so automation does not treat partial analysis as complete. If `--allow-partial` is supported later, the JSON status still remains partial.

## AI-assisted French interpretation

AI translation is a provider adapter planned from the beginning, implemented after the source/context contracts and review mechanism. User preference is interpretation of Quebec French, abbreviations, and incomplete descriptions, rather than dictionary-only substitution.

A batch proposal workflow:
1. Select fields and context by source IDs.
2. Consult the approved glossary and exact reviewed records.
3. Send only the context allowed by the configured provider/data profile.
4. Ask for a proposed translation, alternatives, uncertain tokens, explanation, and abstention when needed.
5. Validate the response schema and bind every suggestion to source IDs.
6. Export a review queue for the Quebec team.
7. Import approved/corrected decisions into a new checkpoint.

Treat source comments and descriptions as data, never as AI instructions. Do not let an AI response execute commands, mutate identifiers, or invent source references.

Provider choice remains open: an approved enterprise service or an approved local model are possible. Ordinary parsing never contacts one. No provider credentials or actual plant text are bundled in this handoff.

A proposal is not automatically accepted because a confidence score is high. A useful triage combines missing context, ambiguity, contradictory glossary entries, affected references, and engineering significance. Record reviewer disagreement and later revisions.

## Review workbook contract

Use macro-free XLSX for people and JSON/JSONL for canonical state. The workbook is a review interface, not the database.

Suggested sheets:
- `Readme`: instructions, status choices, examples, and no-change meaning.
- `Manifest`: workbook schema, export ID, base run, source set, review type, row population.
- `Translations`: original, guessed English, alternatives, confidence estimate/basis, unresolved tokens, context reference, decision, approved English, question/comment.
- `Classifications`: source scope, suggested labels, evidence, decision, approved labels.
- `Mappings`: later source/target proposals and review state.
- `Questions`: items requiring Quebec/engineering input.

Write stable IDs as text to preserve leading zeros and long identifiers. Keep metadata columns separate from editable review fields. Sheet protection and hidden columns are conveniences, not trusted validation.

For confidentiality and safe spreadsheet handling:
- all real workbooks stay inside the confidential workspace;
- write source strings as literal text, not formulas;
- reject formulas and macros in editable import fields;
- do not evaluate workbook expressions or fetch external links;
- treat workbook error values as validation errors;
- give blank, unchanged, cleared, rejected, and deferred different meanings.

## Import protocol

`review validate` generates a preview of accepted changes, unresolved rows, and errors without applying decisions. Its output includes a hash of the reviewed workbook and the base decision-head.

Validation checks:
- expected schema, source snapshot, run ID, export ID, and current decision-head;
- duplicate/missing/unknown row IDs;
- changed immutable original text or source IDs;
- required decision values and data types;
- accidental numeric/date conversion and leading-zero loss;
- conflicts with newer decisions and changed proposals;
- formulas, unexpected worksheets/columns, external links, or unsupported features.

Missing rows do not mean delete. Default to rejecting an incomplete returned population unless an explicit subset-review policy is selected and recorded.

`review import` checks the same workbook hash and base head, then atomically creates one decision batch and a new analysis checkpoint. It never edits the source L5X. Reimporting an identical decision batch is a no-op with an audit entry.

The GUI must use the same validation and application services as workbook import. A user's unsaved GUI edits are a draft; saving creates a validated decision batch.

## Documentation and CLI tests

- Every command and subcommand has help that works without opening any source file or starting AI.
- The documentation examples are executable against a synthetic example case.
- Golden help snapshots detect accidental interface changes.
- Test stdout/stderr separation and JSON validity.
- Test ambiguous selectors, paths with spaces, Windows/Git Bash paths, missing files, and wrong workspace roots.
- Explain new flags and vocabulary in README examples rather than expecting users to infer them.

Reference: [Python argparse](https://docs.python.org/3.12/library/argparse.html) supplies subcommands and automatic help; the specific command design above is proposed for this application.
