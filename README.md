# PLC analysis workbench — planning draft

Status: architecture plan and independently synthetic fixture, revision 0.2, 2026-10-08. The modular application described here has not been implemented. The existing Python reader remains the working prototype.

The aim is to understand exported PLC projects, retain evidence, and guide an engineering review before any future conversion is designed. Initial work prioritizes ladder logic. Other routine languages, including SFC, remain visible in the inventory even before detailed analysis is implemented.

Start with [CODEX_HANDOFF.md](CODEX_HANDOFF.md). Read [the architecture](public/docs/planning/ARCHITECTURE.md), then [the implementation roadmap](public/docs/planning/ROADMAP.md).

## Agreed direction

- Keep command-line argument parsing and presentation separate from the reusable analysis functions.
- Keep all real exports and every derived plant artifact under root `confidential/`.
- Retain immutable source snapshots and versioned analysis runs; use Git for application code and synthetic tests.
- Publish machine-readable JSON results and coverage reports at every stage.
- Show both the source hierarchy and relationships across rungs, programs, tasks, and controllers.
- Treat translations, classifications, and equipment mappings as proposals with evidence and reviewer decisions.
- Use AI-assisted Quebec French interpretation, with explicit data/provider configuration and a review queue. No translation service has been chosen.
- Defer DeltaV FHX generation and any claim of behavioral equivalence.

## Documentation map

| Document | Purpose |
|---|---|
| [Architecture](public/docs/planning/ARCHITECTURE.md) | Module boundaries, source model, graph analysis, pattern discovery |
| [Data contracts](public/docs/planning/DATA_CONTRACTS.md) | IDs, traceability, JSON reports, checkpoints, status meanings |
| [Roadmap](public/docs/planning/ROADMAP.md) | Small implementation slices, tests, completion criteria |
| [CLI and human review](public/docs/planning/CLI_AND_REVIEW.md) | Proposed commands, help, Excel round trips, translation review |
| [Confidentiality](public/docs/planning/CONFIDENTIALITY.md) | Local data layout, synthetic examples, sharing and Git checks |
| [Decisions](public/docs/planning/DECISIONS.md) | Confirmed decisions, proposals, unresolved choices |
| [Synthetic glossary](public/examples/glossary.synthetic.json) | Illustrative reviewable translation record |
| [Synthetic pattern](public/examples/pattern.synthetic.json) | Illustrative pattern, occurrences, and trace links |

All examples in `public/examples/` are invented. Their JSON is illustrative; the implementation must define and validate formal versioned schemas.

## Work-machine rule

On the work machine, Codex may inspect the project read-only and produce handoff files in its designated task artifact directory. Tyler applies repository changes and runs repository tests. A later editing-capable Codex session must read its own current instructions; this document does not override its host restrictions.

## Intended usage

The planned command name is `plc`, installed from the Python package in `python-parser/`. Commands in the planning documents are interface proposals, not commands already available in the prototype.

Unit test source belongs in `python-parser/tests/`. Logs, test run output, reports, reviewer workbooks, source snapshots, and checkpoints belong under `confidential/`. Real data must not be placed in synthetic fixtures or application documentation.

## First development input

Start with [the synthetic fixture](public/fixtures/synthetic/README.md) and its expected counts. It is independently invented, contains no copied plant logic, and has not been tested for Studio 5000 import. The Python sanity checker is supplied for user-run validation.

Repository roles:
- `public/`: portable planning docs, synthetic fixtures, examples, schemas as implemented, and non-proprietary tools.
- `python-parser/`: application source, dependency files, and test code.
- `confidential/`: actual exports and every derived private artifact.

The full repository is the portable development bundle; `public/` complements the Python source rather than duplicating it. Generated production outputs never go to public automatically.

For the new-copy workflow, read [fresh Git setup](public/docs/planning/GIT_FRESH_START.md).
