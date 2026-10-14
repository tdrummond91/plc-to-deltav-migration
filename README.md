# PLC analysis workbench

Status: updated 2026-10-14. The consolidated baseline on `main` includes source inventory, module/I/O declarations, conservative module-root naming, scoped tag/alias bindings and aggregate address-shape diagnostics. Phase 1 remains in progress. The latest work-machine report returned in `b58af78` and awaits parser analysis. See [module/I/O implementation evidence](public/docs/reviews/MODULE_IO_REVIEW.md) for scope, validation and limitations. The editor, engineering interpretation, PCSD and FHX stages remain planned.

The development listener remains disabled and paused. Manual work-machine checks
save results locally; the runner does not fetch, pull, stage, commit or push.

The aim is a reusable tool for migrating several units from L5X source analysis through editable engineering records and PCSD to class-based DeltaV FHX. FHX input must also support producing a PCSD. Phase 1 analyzes L5X in two parallel paths: reports for reading and understanding the source, and editable engineering files for organizing and mapping it. Both need source traceability. Other routine languages, including SFC, remain visible even before detailed analysis is implemented.

The [feedback listener](public/docs/reviews/FEEDBACK_LISTENER.md) is an optional,
ignored local development-PC tool. Its launcher, implementation and test loader
are no longer tracked or delivered to work-machine checkouts. The existing local
copy and scheduled task remain disabled; historical source is preserved in the
archive tag. Normal parser commands do not depend on it.

Start with [CODEX_HANDOFF.md](CODEX_HANDOFF.md). Read [the architecture](public/docs/planning/ARCHITECTURE.md), then [the implementation roadmap](public/docs/planning/ROADMAP.md).

## Agreed direction

- Keep command-line argument parsing and presentation separate from the reusable analysis functions.
- Keep real exports and private engineering artifacts under root `confidential/`; approved count summaries can be synced in `public/inspection/`.
- Retain immutable source snapshots and versioned analysis runs; use Git for application code and synthetic tests.
- Publish machine-readable JSON results and coverage reports at every stage.
- Show both the source hierarchy and relationships across rungs, programs, tasks, and controllers.
- Treat translations, classifications, and equipment mappings as proposals with evidence and reviewer decisions.
- Use AI-assisted Quebec French interpretation, with explicit data/provider configuration and a review queue. No translation service has been chosen.
- Preserve approved corrections across stage reruns and reconcile changes to source objects.
- Support sequential review between chosen participants, with configurable handoff order and room to extend the workflow later.
- Include PCSD feedback, class-based FHX generation, and FHX-to-PCSD in the later project phases; their implementation remains deferred.
- Synchronize non-proprietary tools and reviewed development examples across computers. Real inputs and private engineering state stay outside Git.
- PCSD means Process Control Strategy Document and supports plant test-sheet generation. Determine its detailed contents from the L5X analysis before fixing its schema.
- Prefer a standalone editor with search, change review, import/export and backups for non-programmers. Excel remains an exchange/fallback option; packaging and database choices are proposals.
- Keep reviewable notes and focused commits for an independent reviewing chat. When work-machine feedback is slow, use comparable experiment branches from one baseline, each ending in -pc.

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

All examples in `public/examples/` are invented. Glossary/pattern JSON remains
illustrative; source/reference summaries follow their implemented versioned contracts.

## Work-machine rule

On the work machine, Codex may inspect the project read-only and produce handoff files in its designated task artifact directory. Tyler applies repository changes and runs repository tests. A later editing-capable Codex session must read its own current instructions; this document does not override its host restrictions.

## Intended usage

`run-work-check.sh` accepts a source
filename on the first run and remembers it locally for later runs. It tests the
already checked out clean named branch, including `main`, using explicit parser/helper test lists,
saves private analysis and writes a validated aggregate under the Git-ignored
`public/inspection/local/` folder. Updating code and publishing a reviewed report
are manual actions. See the [work-machine procedure](public/docs/reviews/WORK_MACHINE_REFERENCES_RUN.md).

The first available command is `plc inspect`, installed from `python-parser/`:

```bash
uv run --project python-parser plc inspect public/fixtures/synthetic/controller_demo.L5X
```

This fixture intentionally returns exit 3 (partial) because SFC interpretation is not implemented. See [command usage and private run storage](python-parser/README.md) and [source-inventory review](public/docs/reviews/SOURCE_INVENTORY_REVIEW.md). JSON and readable reports use the same snapshot-bound records. `inspect` retains private source data; it is not a public-report scrubber.

For bounded aggregate feedback, `plc summarize FILE --output public/inspection/NEW.json` emits validated counts and global measurements. Unknown labels are pooled; source identifiers, hashes, operands, paths and rung layouts are omitted. Tyler has approved these aggregate reports for repository sync. His confidentiality boundary is unit reconstruction with data values, or more than 2% rung knowledge; these summaries expose no individual rung logic or process values. See [summary implementation evidence](public/docs/reviews/SUMMARY_EXPORT_REVIEW.md).

`plc references FILE` produces private scoped declarations, alias chains and
operand occurrences linked to declared roots. Module input/output/configuration
tags can bind through explicit names or supported module/port topology; inferred
names retain their provenance, and incomplete topology has fixed gap reasons.
Root binding does not validate structure members, array bounds, instruction
effects or engineering purpose.
`plc reference-summary FILE --output public/inspection/NEW.json` exports only
binding/coverage counts, module naming and gap-reason counts, plus the structural
summary. Follow the
[current work-machine procedure](public/docs/reviews/WORK_MACHINE_REFERENCES_RUN.md).

Unit test source belongs in `python-parser/tests/`. Private reports, reviewer workbooks, source snapshots and checkpoints belong under `confidential/`; approved aggregate reports are the explicit sync exception. Real data must not be placed in synthetic fixtures or application documentation.

## First development input

Start with [the synthetic fixture](public/fixtures/synthetic/README.md) and its expected counts. It is independently invented, contains no copied plant logic, and has not been tested for Studio 5000 import. The Python sanity checker is supplied for user-run validation.

Repository roles:
- `public/`: portable planning docs, synthetic fixtures, examples, schemas as implemented, and non-proprietary tools.
- `python-parser/`: application source, dependency files, and test code.
- `confidential/`: actual exports and every derived private artifact.

The full repository is the portable development bundle; `public/` complements the Python source rather than duplicating it. The work-machine runner saves its validated aggregate/test-results report locally. Only a manually reviewed aggregate may be copied or moved from `public/inspection/local/` to `public/inspection/` and explicitly staged, committed and pushed. Detailed production outputs and raw logs stay private.

For the new-copy workflow, read [fresh Git setup](public/docs/planning/GIT_FRESH_START.md).
