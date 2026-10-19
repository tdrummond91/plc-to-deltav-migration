# Portable development materials

This folder contains project documentation, independently invented examples
and fixtures, and validated feedback returned from the work PC. Application
source and tests are in [python-parser](../python-parser/README.md). Complete
plant exports and reports belong in ignored `confidential/`.

## Start here

| Need | Open |
|---|---|
| Run the work-PC check | [Work-PC instructions](docs/reviews/WORK_MACHINE_REFERENCES_RUN.md) |
| Read an engineering report | [Report reading guide](docs/reviews/REPORT_REVIEW_GUIDE.md) |
| Check current readiness | [Tracker](docs/planning/PRE_TEAM_REVIEW_TRACKER.md) and [readiness assessment](docs/reviews/PHASE_1_READINESS_REVIEW.md) |
| Explore invented reports | [Examples index](examples/README.md) |
| Continue development | [Current handoff](CODEX_HANDOFF.md) and [development guide](docs/DEVELOPMENT_GUIDE.md) |
| Find a design or past investigation | [Documentation index](docs/README.md) |

Phase 1's fourteen analysis cycles and the requested cleanup confirmation are
validated. The saved report is ready for Tyler's walkthrough and official
engineering review; no further parser run is currently needed. The report is
read-only; editable corrections, PCSD and FHX remain later work.

## Folder map

- `docs/planning/`: scope, decisions, contracts and the progress tracker.
- `docs/reviews/`: current run/reading instructions and dated implementation evidence.
- `docs/history/`: full prior versions of the long entrypoint documents.
- `examples/`: invented HTML demonstrations and small JSON examples.
- `fixtures/synthetic/`: invented source inputs and expected results.
- `inspection/`: validated shared feedback; `inspection/local/` remains ignored.
- `tools/`: fixture validation helpers. General inspection tools are in
  [tools/l5x_inspect](../tools/l5x_inspect/README.md).

Existing feedback and review records retain their paths for traceability.
A file's location in `public/` does not make it automatically suitable for
sharing; preserve the [approved data boundary](docs/planning/CONFIDENTIALITY.md).
See [validation records](VALIDATION.md) and the
[complete pre-cleanup notes](docs/history/2026-10-19-pre-cleanup/README.md).
