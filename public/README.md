# Portable development materials

Signal4 adds saved guard dependencies and bounded source trails across rungs.
Search alarm/equipment/sensor wording, follow upstream writers or downstream
guards, and inspect branches, cycles and explicit stop boundaries.
See [scope and validation](docs/reviews/SIGNAL_DEPENDENCIES_REVIEW.md).

Latest analysis bundle: [explicit alarm source evidence](docs/reviews/ALARM_EVIDENCE_REVIEW.md)
and its [invented report](examples/alarm-evidence-review-demo.html). This adds
source declarations and configuration alongside the existing ladder, signal,
PID, calculation and sequence views. Automated Phase 1 development continues.

This directory contains independently synthetic inputs, generic helper code, and planning documents. Application source and tests stay in ../python-parser/. Real exports and all private derived outputs stay in ../confidential/.

Start here:

1. [Canonical Codex handoff](CODEX_HANDOFF.md).
2. [Synthetic fixture and user-run checks](fixtures/synthetic/README.md).
3. [Architecture](docs/planning/ARCHITECTURE.md) and [milestones](docs/planning/ROADMAP.md).
4. [Artifact validation record](VALIDATION.md).
5. [Fresh Git workflow](docs/planning/GIT_FRESH_START.md).
6. [Engineering review guide](docs/reviews/ENGINEERING_REVIEW_REPORT.md) and
   [invented HTML demonstration](examples/engineering-review-demo.html).
7. [Explicit operand reads/writes](docs/reviews/ACCESS_ROLE_REVIEW.md) and
   [confirmed timer/reset/copy checkpoint](docs/reviews/TIMER_COPY_ACCESS_REVIEW.md).
8. [Confirmed stored tag data checkpoint](docs/reviews/TAG_DATA_REVIEW.md).
9. [Confirmed PID member checkpoint](docs/reviews/PID_MEMBER_REVIEW.md), with the [PID association checkpoint](docs/reviews/PID_EVIDENCE_REVIEW.md).

10. [Confirmed CPT calculation checkpoint](docs/reviews/CALCULATION_REVIEW.md).

11. [Confirmed CPT function follow-up](docs/reviews/CALCULATION_FUNCTION_REVIEW.md).

12. [Confirmed extended operand access](docs/reviews/EXTENDED_ACCESS_REVIEW.md).

13. [Current CPT expression access](docs/reviews/CPT_ACCESS_REVIEW.md).

The fixtures are small parser inputs, not deployable controller projects. The
read-only inventory, reference, SFC and offline engineering-review CLI commands
are implemented. Editable engineering records, PCSD and FHX generation remain
planned. Download/open the invented HTML demonstration in a browser to explore
the report interface; GitHub's source view does not execute its navigation.
Manual source or interface review can wait until you are ready; current parser
development needs only the generated work-machine feedback at each run boundary.

Edit this material deliberately as development advances. Do not direct production report output here. A file being in public/ does not automatically make it suitable for publication; review new content before committing.

For the first parsing discussion, read [L5X structure and branch locations](docs/planning/L5X_STRUCTURE.md).

14. [Current rung analysis and candidates](docs/reviews/RUNG_ANALYSIS_REVIEW.md),
    with the [Phase 1 completion gate](docs/planning/PHASE_1_ENGINEERING_ANALYSIS.md).

15. [Current exact-address relationships and operand-reuse patterns](docs/reviews/RELATIONSHIP_REVIEW.md).

16. [Current Boolean conditions and output actions](docs/reviews/CONDITION_REVIEW.md).

17. [Confirmed binding gaps and rack context](docs/reviews/BINDING_CONTEXT_REVIEW.md).

18. [Fixed targeted diagnostic rung examples](docs/reviews/TARGETED_RUNG_SAMPLES_REVIEW.md).

19. [Custom-instruction declarations and symbolic array selectors](docs/reviews/INSTRUCTION_CONTEXT_REVIEW.md),
    with the [invented context report](examples/instruction-context-demo.html).

20. [Stored-state conditions and SFC reset targets](docs/reviews/STATEFUL_SEQUENCE_REVIEW.md),
    with the [invented stored-state and sequence report](examples/stateful-sequence-demo.html).

21. [AOI bodies and unmatched SFR target context](docs/reviews/AOI_BODY_REVIEW.md),
    with the [invented body-context report](examples/aoi-body-demo.html).

See [PID connections and observed member uses](docs/reviews/PID_CONNECTIONS_REVIEW.md)
and its [invented report](examples/pid-connections-demo.html).

See [calculation inputs and destinations](docs/reviews/CALCULATION_PATHS_REVIEW.md)
for the current checkpoint and [invented report](examples/calculation-paths-demo.html).

- [Boolean output context](docs/reviews/OUTPUT_CONTEXT_REVIEW.md) and
  [invented output-context report](examples/output-context-demo.html).

Timer/counter/reset relationships: [scope and validation](docs/reviews/STATEFUL_OBJECTS_REVIEW.md), with an [invented demonstration](examples/stateful-objects-demo.html).

Sequence transition expressions: [scope and validation](docs/reviews/SFC_CONDITIONS_REVIEW.md), with an [invented demonstration](examples/sfc-conditions-demo.html).

Sequence reference relationships: [scope and validation](docs/reviews/SFC_CONTEXT_REVIEW.md), with an [invented demonstration](examples/sfc-context-demo.html).

Work-check timing and alias diagnostics: [scope and validation](docs/reviews/WORK_CHECK_TIMING_REVIEW.md).

Current performance checkpoint: [bounded source reuse](docs/reviews/SOURCE_REUSE_REVIEW.md)
uses the returned work38 timings to reduce repeated source work while preserving
validation and saved report contents. The next work-machine run measures its effect.

- [Source-declared execution context](docs/reviews/EXECUTION_CONTEXT_REVIEW.md),
  with the [invented report](examples/execution-context-demo.html).
