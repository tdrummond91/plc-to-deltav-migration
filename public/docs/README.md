# Documentation index

Use the current pages below for the next action. The dated plans and review
records preserve why the implementation works as it does; older status and
"next run" instructions are historical checkpoints.

## Current workflow and review

| Need | Page |
|---|---|
| First use; learn what to inspect | [Offline start page and learning checklist](../../START-HERE.html) |
| Understand the start page, progress and themes | [First-use implementation](reviews/GETTING_STARTED_REVIEW.md) |
| Resume development | [Project README](../../README.md) and [current handoff](../CODEX_HANDOFF.md) |
| Synchronize main and open the accepted report | [Work-PC instructions](reviews/WORK_MACHINE_REFERENCES_RUN.md) |
| Read the generated report | [Report reading guide](reviews/REPORT_REVIEW_GUIDE.md) |
| Check completed gates and review readiness | [Pre-team-review tracker](planning/PRE_TEAM_REVIEW_TRACKER.md) |
| Understand accepted evidence and remaining external questions | [Readiness assessment](reviews/PHASE_1_READINESS_REVIEW.md) |
| Review this organization/refactoring pass | [Cleanup record](reviews/CLEANUP_REVIEW.md) |
| Understand the embedded guide and debug option | [Review-guide implementation](reviews/REVIEW_GUIDE_IMPLEMENTATION.md) |
| Handle review feedback | [Next-development checklist](reviews/NEXT_DEVELOPMENT_PROMPT.md) |
| Find commands and code ownership | [Development guide](DEVELOPMENT_GUIDE.md) and [source module map](../../python-parser/src/plc_workbench/README.md) |
| Learn with invented reports | [Examples index](../examples/README.md) |

Phase 1 source analysis has fourteen validated cycles, followed by successful
cleanup and embedded-guide confirmations: sixteen completed cycles, zero
further unchanged-source runs before review. Synchronize `main`, open the
accepted saved report and start with **Review guide**. Editable corrections,
PCSD and FHX remain later phases.

## Planning and contracts

| Area | Documents |
|---|---|
| Product scope and acceptance | [Roadmap](planning/ROADMAP.md), [Phase 1 analysis plan](planning/PHASE_1_ENGINEERING_ANALYSIS.md) |
| Architecture and decisions | [Architecture](planning/ARCHITECTURE.md), [decisions](planning/DECISIONS.md) |
| Versioned data boundaries | [Data contracts](planning/DATA_CONTRACTS.md), [confidentiality](planning/CONFIDENTIALITY.md) |
| Source and interface background | [L5X structure](planning/L5X_STRUCTURE.md), [CLI/review design](planning/CLI_AND_REVIEW.md) |
| Repository setup history | [Git fresh-start notes](planning/GIT_FRESH_START.md) |

Some plans describe the destination architecture as well as implemented work.
Use their dates and the current handoff to distinguish future editor/database
proposals from the working read-only report.

## Implementation evidence and historical reviews

These records stay at their original paths. They explain specific rules,
limits, test evidence and rejected interpretations. Their earlier next steps
do not supersede the current workflow above.

### Source inventory, bindings and access

- [Source inventory](reviews/SOURCE_INVENTORY_REVIEW.md)
- [Source references](reviews/SOURCE_REFERENCES_REVIEW.md)
- [Access roles](reviews/ACCESS_ROLE_REVIEW.md)
- [Extended access](reviews/EXTENDED_ACCESS_REVIEW.md)
- [CPT access](reviews/CPT_ACCESS_REVIEW.md)
- [Address shapes](reviews/ADDRESS_SHAPE_REVIEW.md)
- [Binding context](reviews/BINDING_CONTEXT_REVIEW.md)
- [Stored tag data](reviews/TAG_DATA_REVIEW.md)
- [Timer/reset/copy access](reviews/TIMER_COPY_ACCESS_REVIEW.md)
- [Timer placeholders](reviews/TIMER_PLACEHOLDER_REVIEW.md)
- [System flags](reviews/SYSTEM_FLAG_REVIEW.md)
- [Bit operations](reviews/BIT_OPERATION_REVIEW.md)

### Rungs, conditions and engineering groups

- [Rung analysis](reviews/RUNG_ANALYSIS_REVIEW.md)
- [Relationships](reviews/RELATIONSHIP_REVIEW.md)
- [Boolean conditions](reviews/CONDITION_REVIEW.md)
- [Condition transfers](reviews/CONDITION_TRANSFER_REVIEW.md)
- [Output context](reviews/OUTPUT_CONTEXT_REVIEW.md)
- [Initial engineering report](reviews/ENGINEERING_REVIEW_REPORT.md)
- [Engineering assemblies](reviews/ENGINEERING_ASSEMBLIES_REVIEW.md)
- [Qualified rack groups / C14 implementation](reviews/RACK_ASSEMBLY_REVIEW.md)
- [Control interpretation](reviews/CONTROL_INTERPRETATION_REVIEW.md)

### Signals, authored wording and alarms

- [Signal context](reviews/SIGNAL_CONTEXT_REVIEW.md)
- [Signal patterns](reviews/SIGNAL_PATTERNS_REVIEW.md)
- [Authored wording](reviews/SIGNAL_AUTHORED_REVIEW.md)
- [Signal dependencies](reviews/SIGNAL_DEPENDENCIES_REVIEW.md)
- [Signal candidates](reviews/SIGNAL_CANDIDATES_REVIEW.md)
- [Explicit alarm evidence](reviews/ALARM_EVIDENCE_REVIEW.md)

### PID, calculations and stateful objects

- [PID evidence](reviews/PID_EVIDENCE_REVIEW.md)
- [PID members](reviews/PID_MEMBER_REVIEW.md)
- [PID connections](reviews/PID_CONNECTIONS_REVIEW.md)
- [Calculations](reviews/CALCULATION_REVIEW.md)
- [Calculation functions](reviews/CALCULATION_FUNCTION_REVIEW.md)
- [Math signatures](reviews/MATH_SIGNATURE_REVIEW.md)
- [Calculation paths](reviews/CALCULATION_PATHS_REVIEW.md)
- [File operations](reviews/FILE_OPERATIONS_REVIEW.md)
- [Stateful objects](reviews/STATEFUL_OBJECTS_REVIEW.md)

### Sequences, calls and communication

- [SFC structure](reviews/SFC_STRUCTURE_REVIEW.md)
- [SFC annotations](reviews/SFC_ANNOTATION_REVIEW.md)
- [SFC conditions](reviews/SFC_CONDITIONS_REVIEW.md)
- [SFC context](reviews/SFC_CONTEXT_REVIEW.md)
- [Stored state and resets](reviews/STATEFUL_SEQUENCE_REVIEW.md)
- [Instruction context](reviews/INSTRUCTION_CONTEXT_REVIEW.md)
- [AOI bodies](reviews/AOI_BODY_REVIEW.md)
- [Call field shapes](reviews/ROUTINE_CALL_SHAPE_REVIEW.md)
- [Routine targets](reviews/ROUTINE_TARGET_REVIEW.md)
- [Routine metadata](reviews/ROUTINE_METADATA_REVIEW.md)
- [Routine graph](reviews/ROUTINE_GRAPH_REVIEW.md)
- [Execution context](reviews/EXECUTION_CONTEXT_REVIEW.md)
- [Communication interpretation](reviews/COMMUNICATION_INTERPRETATION_REVIEW.md)

### I/O, rack context and residual investigations

- [Module I/O](reviews/MODULE_IO_REVIEW.md)
- [Rack candidates](reviews/RACK_CANDIDATE_REVIEW.md)
- [Rack I/O investigation](reviews/RACK_IO_INVESTIGATION.md)
- [Rack backing investigation](reviews/RACK_BACKING_INVESTIGATION.md)
- [Rack source mapping](reviews/RACK_SOURCE_MAPPING_REVIEW.md)
- [Residual diagnostics](reviews/RESIDUAL_DIAGNOSTICS_REVIEW.md)
- [Residual interpretation](reviews/RESIDUAL_INTERPRETATION_REVIEW.md)
- [Residual source context](reviews/RESIDUAL_SOURCE_REVIEW.md)

### Bounded feedback and work-PC validation

- [Summary export](reviews/SUMMARY_EXPORT_REVIEW.md)
- [Early work-machine summary procedure](reviews/WORK_MACHINE_SUMMARY_RUN.md)
- [First returned summary](reviews/WORK_MACHINE_SUMMARY_001_REVIEW.md)
- [Work-check runner](reviews/WORK_CHECK_RUNNER_REVIEW.md)
- [Stage timing](reviews/WORK_CHECK_TIMING_REVIEW.md)
- [Source reuse](reviews/SOURCE_REUSE_REVIEW.md)
- [Save-failure repair](reviews/SAVE_FAILURE_REVIEW.md)
- [Bounded operand sample](reviews/BOUNDED_OPERAND_SAMPLE_REVIEW.md)
- [Unmatched operands](reviews/UNMATCHED_OPERAND_REVIEW.md)
- [Targeted rung samples](reviews/TARGETED_RUNG_SAMPLES_REVIEW.md)

### Earlier project/tooling assessments

- [Project-state review](reviews/PROJECT_STATE_REVIEW.md)
- [Stage 5 helper review](reviews/STAGE_5_CODE_REVIEW.md)
- [Earlier independent-review prompt](reviews/ASTRA_REVIEW_PROMPT.md)
- [Listener history (excluded from the work-PC workflow)](reviews/FEEDBACK_LISTENER.md)

## Preserved history and fixtures

The [2026-10-19 entrypoint archive](history/2026-10-19-pre-cleanup/README.md)
preserves all six earlier long entrypoints in full, with a reversible link
manifest. No investigation notes were condensed or removed.

[Synthetic fixtures](../fixtures/synthetic/README.md), [validation records](../VALIDATION.md),
[supporting tools](../../tools/README.md) and returned feedback in
`public/inspection/` retain their existing locations and identities.
