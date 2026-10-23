# Source module map

The package keeps its existing import paths so saved report contracts, tests
and callers continue to work. This map groups the files by responsibility;
the table is a navigation guide, not a new execution order. Start with the
[development guide](../../../public/docs/DEVELOPMENT_GUIDE.md) for commands.

## Workflow and storage

| Files | Responsibility |
|---|---|
| [cli.py](cli.py), `__main__.py` | CLI argument handling and command orchestration. |
| [source.py](source.py), [models.py](models.py), [source_reuse.py](source_reuse.py) | Captured source, inventory structures and bounded reuse within an analysis. |
| [review.py](review.py) | Compose and validate the private engineering review. |
| [storage.py](storage.py) | Fresh private run directories, artifact serialization and final manifests. |
| [project_store.py](project_store.py) | Private SQLite projects: immutable imported artifacts, reviewed decisions, categories/groups/rules, revision checks, history and portable backups. |
| [workspace.py](workspace.py), [workspace_assets/](workspace_assets/) | Explicitly launched loopback editor, source browsing, structured review controls and restore workflow. |
| [workspace_application.py](workspace_application.py) | Read-only application map: configured routes, declarations, raw register containment, datatype provenance, exact uses and extraction gaps. |
| [workspace_variables.py](workspace_variables.py), [workspace_field_io.py](workspace_field_io.py), [workspace_io_comments.py](workspace_io_comments.py) | Authenticated source/value indexes, documented module layouts, original annotation provenance and description selection. |
| [workspace_field_signals.py](workspace_field_signals.py) | Field-channel candidates and source bindings for separate saved DeltaV names and packages. |
| [workspace_report.py](workspace_report.py) | Refresh saved evidence views with current navigation while preserving original artifacts. |
| [review_html.py](review_html.py), [review_assets/](review_assets/) | Offline HTML rendering, JavaScript navigation and CSS. |
| [review_assets/review_guide.js](review_assets/review_guide.js) | Embedded reviewer checklists, response guidance, glossary and selectable feedback template. |
| [work_check.py](work_check.py), [work_check_timing.py](work_check_timing.py) | Work-PC stages, bounded returned feedback, local commit and stage timings. |
| [work_check_tests.py](work_check_tests.py) | Reviewed test selection and closed test-result format. |
| [contracts/work_reports.py](contracts/work_reports.py) | Versioned work-report envelope caps and canonical JSON layout, independent of workflow imports. |
| [revision.py](revision.py), [summary_output.py](summary_output.py) | Code provenance and validated summary publication. |

`work_check.py` re-exports existing report-cap names for compatibility. The
contracts package does not decide whether a report is valid or shareable;
closed semantic validation remains in the relevant summary/workflow layer.

## Evidence and analysis layers

| Topic | Main modules |
|---|---|
| Ladder syntax and rung structure | [ladder/syntax.py](ladder/syntax.py), [rung_analysis.py](rung_analysis.py) |
| Scoped symbols, aliases and I/O | [references.py](references.py), [module_io.py](module_io.py), [binding_context.py](binding_context.py) |
| Rack declarations and source qualifications | [rack_candidates.py](rack_candidates.py), [rack_backing_context.py](rack_backing_context.py) |
| Explicit operand access and selectors | [access.py](access.py), [indexed_access.py](indexed_access.py), [custom_instruction_context.py](custom_instruction_context.py) |
| Stored tag data | [tag_data.py](tag_data.py) |
| PID declarations, members and source uses | [pid.py](pid.py), [pid_members.py](pid_members.py), [pid_connections.py](pid_connections.py) |
| Calculations and file operations | [calculations.py](calculations.py), [calculation_paths.py](calculation_paths.py), [file_operations.py](file_operations.py) |
| Boolean conditions, outputs and state | [conditions.py](conditions.py), [output_context.py](output_context.py), [stateful_objects.py](stateful_objects.py) |
| Signals, wording and candidate groups | [signal_context.py](signal_context.py), [signal_patterns.py](signal_patterns.py), [signal_authored.py](signal_authored.py), [signal_dependencies.py](signal_dependencies.py), [signal_candidates.py](signal_candidates.py) |
| Explicit alarm source evidence | [alarm_evidence.py](alarm_evidence.py) |
| Routine calls and execution context | [routine_shapes.py](routine_shapes.py), [routine_targets.py](routine_targets.py), [routine_metadata.py](routine_metadata.py), [routine_graph.py](routine_graph.py), [execution_context.py](execution_context.py) |
| Sequence structure and resets | [sfc_structure.py](sfc_structure.py), [sfc_conditions.py](sfc_conditions.py), [sfc_context.py](sfc_context.py), [sfr_context.py](sfr_context.py) |
| AOI bodies and communications | [aoi_body_context.py](aoi_body_context.py), [communication_context.py](communication_context.py) |
| Exact-address relationships and cross-rung groups | [relationships.py](relationships.py), [engineering_assemblies.py](engineering_assemblies.py) |

The `*_summary.py` modules build and validate the corresponding bounded shared
counts; private evidence remains in the analysis model. Some related summary
families share a module. [summary.py](summary.py) handles the source aggregate;
[reporting.py](reporting.py) and [reference_reporting.py](reference_reporting.py)
provide readable private views. Check the relevant layer's validator and
workflow tests when changing its model.

## Bounded diagnostic examples

[diagnostic_sample.py](diagnostic_sample.py),
[targeted_samples.py](targeted_samples.py) and
[targeted_sample_history.py](targeted_sample_history.py) implement the approved
bounded example and frozen-history workflow. Their cumulative limits and replay
rules are part of the data boundary, not disposable test scaffolding.

Tests live in [python-parser/tests](../../tests/); independently invented L5X
inputs live in [public/fixtures/synthetic](../../../public/fixtures/synthetic/README.md).
Use the [documentation index](../../../public/docs/README.md) to find each
layer's scope, investigated limits and historical validation.
