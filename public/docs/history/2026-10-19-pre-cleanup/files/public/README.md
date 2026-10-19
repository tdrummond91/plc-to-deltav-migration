# Portable development materials

Current checkpoint: [C14 validated; reports ready for review](../../../../reviews/PHASE_1_READINESS_REVIEW.md).
Use the [completion tracker](../../../../planning/PRE_TEAM_REVIEW_TRACKER.md) for the
remaining estimate and the [report guide](../../../../reviews/REPORT_REVIEW_GUIDE.md)
for navigation. The automated pre-review gate is complete for this export.
Open the existing private report for readability, appearance and engineering
feedback; no new normal work-machine run is requested.

Historical signal and alarm checkpoints:

Signal4 adds saved guard dependencies and bounded source trails across rungs.
Search alarm/equipment/sensor wording, follow upstream writers or downstream
guards, and inspect branches, cycles and explicit stop boundaries.
See [scope and validation](../../../../reviews/SIGNAL_DEPENDENCIES_REVIEW.md).

Earlier analysis bundle: [explicit alarm source evidence](../../../../reviews/ALARM_EVIDENCE_REVIEW.md)
and its [invented report](../../../../../examples/alarm-evidence-review-demo.html). This adds
source declarations and configuration alongside the existing ladder, signal,
PID, calculation and sequence views. Automated Phase 1 development continues.

This directory contains independently synthetic inputs, generic helper code, and planning documents. Application source and tests stay in ../python-parser/. Real exports and all private derived outputs stay in ../confidential/.

Start here:

1. [Canonical Codex handoff](CODEX_HANDOFF.md).
2. [Synthetic fixture and user-run checks](../../../../../fixtures/synthetic/README.md).
3. [Architecture](../../../../planning/ARCHITECTURE.md) and [milestones](../../../../planning/ROADMAP.md).
4. [Artifact validation record](../../../../../VALIDATION.md).
5. [Fresh Git workflow](../../../../planning/GIT_FRESH_START.md).
6. [Engineering review guide](../../../../reviews/ENGINEERING_REVIEW_REPORT.md) and
   [invented HTML demonstration](../../../../../examples/engineering-review-demo.html).
7. [Explicit operand reads/writes](../../../../reviews/ACCESS_ROLE_REVIEW.md) and
   [confirmed timer/reset/copy checkpoint](../../../../reviews/TIMER_COPY_ACCESS_REVIEW.md).
8. [Confirmed stored tag data checkpoint](../../../../reviews/TAG_DATA_REVIEW.md).
9. [Confirmed PID member checkpoint](../../../../reviews/PID_MEMBER_REVIEW.md), with the [PID association checkpoint](../../../../reviews/PID_EVIDENCE_REVIEW.md).

10. [Confirmed CPT calculation checkpoint](../../../../reviews/CALCULATION_REVIEW.md).

11. [Confirmed CPT function follow-up](../../../../reviews/CALCULATION_FUNCTION_REVIEW.md).

12. [Confirmed extended operand access](../../../../reviews/EXTENDED_ACCESS_REVIEW.md).

13. [Current CPT expression access](../../../../reviews/CPT_ACCESS_REVIEW.md).

The fixtures are small parser inputs, not deployable controller projects. The
read-only inventory, reference, SFC and offline engineering-review CLI commands
are implemented. Editable engineering records, PCSD and FHX generation remain
planned. Download/open the invented HTML demonstration in a browser to explore
the report interface; GitHub's source view does not execute its navigation.
The current source-analysis reports are ready for review. Preserve report/run
and record IDs with feedback; the report does not yet store corrections across
changing source exports.

Edit this material deliberately as development advances. Do not direct production report output here. A file being in public/ does not automatically make it suitable for publication; review new content before committing.

For the first parsing discussion, read [L5X structure and branch locations](../../../../planning/L5X_STRUCTURE.md).

14. [Current rung analysis and candidates](../../../../reviews/RUNG_ANALYSIS_REVIEW.md),
    with the [Phase 1 completion gate](../../../../planning/PHASE_1_ENGINEERING_ANALYSIS.md).

15. [Current exact-address relationships and operand-reuse patterns](../../../../reviews/RELATIONSHIP_REVIEW.md).

16. [Current Boolean conditions and output actions](../../../../reviews/CONDITION_REVIEW.md).

17. [Confirmed binding gaps and rack context](../../../../reviews/BINDING_CONTEXT_REVIEW.md).

18. [Fixed targeted diagnostic rung examples](../../../../reviews/TARGETED_RUNG_SAMPLES_REVIEW.md).

19. [Custom-instruction declarations and symbolic array selectors](../../../../reviews/INSTRUCTION_CONTEXT_REVIEW.md),
    with the [invented context report](../../../../../examples/instruction-context-demo.html).

20. [Stored-state conditions and SFC reset targets](../../../../reviews/STATEFUL_SEQUENCE_REVIEW.md),
    with the [invented stored-state and sequence report](../../../../../examples/stateful-sequence-demo.html).

21. [AOI bodies and unmatched SFR target context](../../../../reviews/AOI_BODY_REVIEW.md),
    with the [invented body-context report](../../../../../examples/aoi-body-demo.html).

See [PID connections and observed member uses](../../../../reviews/PID_CONNECTIONS_REVIEW.md)
and its [invented report](../../../../../examples/pid-connections-demo.html).

See [calculation inputs and destinations](../../../../reviews/CALCULATION_PATHS_REVIEW.md)
for the current checkpoint and [invented report](../../../../../examples/calculation-paths-demo.html).

- [Boolean output context](../../../../reviews/OUTPUT_CONTEXT_REVIEW.md) and
  [invented output-context report](../../../../../examples/output-context-demo.html).

Timer/counter/reset relationships: [scope and validation](../../../../reviews/STATEFUL_OBJECTS_REVIEW.md), with an [invented demonstration](../../../../../examples/stateful-objects-demo.html).

Sequence transition expressions: [scope and validation](../../../../reviews/SFC_CONDITIONS_REVIEW.md), with an [invented demonstration](../../../../../examples/sfc-conditions-demo.html).

Sequence reference relationships: [scope and validation](../../../../reviews/SFC_CONTEXT_REVIEW.md), with an [invented demonstration](../../../../../examples/sfc-context-demo.html).

Work-check timing and alias diagnostics: [scope and validation](../../../../reviews/WORK_CHECK_TIMING_REVIEW.md).

Current performance checkpoint: [bounded source reuse](../../../../reviews/SOURCE_REUSE_REVIEW.md)
uses the returned work38 timings to reduce repeated source work while preserving
validation and saved report contents. The next work-machine run measures its effect.

- [Source-declared execution context](../../../../reviews/EXECUTION_CONTEXT_REVIEW.md),
  with the [invented report](../../../../../examples/execution-context-demo.html).
