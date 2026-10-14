# First work-machine aggregate review

Historical result: Tyler subsequently returned the readable summary-002.json,
which matches the earlier structural baseline. See the
[current reference review](SOURCE_REFERENCES_REVIEW.md); the next action below
records the original investigation and is no longer pending.

Reviewed 2026-10-13 on feat/summary-export-pc. Returned artifact:
[summary-001.json](../../inspection/summary-001.json), committed by Tyler in
61b9ca722301154793bb2d57437e04440ead565c. The report identifies application
revision 028537dc39f4e45b68c58dbd373601d257efb589 with a clean code worktree.
No confidential source or private inventory was opened for this review.

## Findings

The report is internally consistent but provides no readable ladder evidence.
Its partial status is accompanied by 70 encoded_content warnings and no other
diagnostics. Instruction coverage is explicitly incomplete.

| Aggregate | Returned report | Earlier public source baseline |
| --- | ---: | ---: |
| Controllers | 1 | 1 |
| Programs / tasks | 3 / 3 | 3 / 3 |
| Modules | 111 | 120 |
| Controller / program tags | 5,954 / 46 | 6,261 / 46 |
| Total tags | 6,000 | 6,307 |
| Aliases | 879 | 941 |
| AOI definitions | 0 | 1 |
| Routines | 0 | 70 |
| Rungs | 0 | 4,606 |
| Instructions | 0 | 17,874 |
| EncodedData elements | 70 | 0 |

The earlier baseline is recorded in [CODEX_HANDOFF.md](../../CODEX_HANDOFF.md)
under the Stage 1, Stage 3 and rung-structure findings. These are differing
aggregate observations, not proof that the same source changed. The summaries
intentionally omit source identity, so source equivalence is unresolved.

The current source reader is unchanged from the reported code revision.
It counts every EncodedData element regardless of its parent, without inspecting
its payload or classifying encoding/protection. A Routine element outside a
supported parent would produce declaration_context_not_analyzed; every Rung
element is counted before its context is checked. Zero routines/rungs and no
context diagnostics therefore indicate no exposed Routine/Rung XML elements
under this reader's contract. Ordinary unexpected wrapping of those same element
names does not explain the report. An independent explorer confirmed this reading.

Do not label these as 70 confirmed encrypted routines, assume each encoded block
maps to a routine, or infer that the controller has no logic. Whether this input
is a different export, uses different export settings, or requires another
supported representation remains to be established on the work machine.

The report also counts 68,428 XML elements and 56,375 unmodeled elements across
134 paths. Unmodeled XML includes data outside the current modeling scope; those
counts are not a count of lost rungs or parser errors.

## Validation and limitations

The original v1 report remains valid approved feedback under D026. A read-only
compatibility check loaded a copy in memory, changed only schema_version,
policy_version, exporter_version and sharing_status to their current v2 constants,
and called plc_workbench.summary.validate_summary. It passed the closed-field,
type and count-consistency checks. The saved report was verified unchanged.
This does not independently validate the source or certify parser correctness.

This review changed documentation only. Application/helper suites were not rerun,
and the work-machine test outcomes have not been supplied. Prior suite results
remain in [SUMMARY_EXPORT_REVIEW.md](SUMMARY_EXPORT_REVIEW.md).

## Next bounded action

Confirm whether this report used the unchanged L5X behind the earlier 4,606-rung
baseline or a different/new export. Tyler said he may have sent the wrong one
and is checking locally; this remains a possibility, not a confirmed cause.
If a different file was selected and the
earlier readable export remains available, summarize that earlier file into a new
aggregate report for comparison. If the source was unchanged, investigate locally
which file the command read and compare using the existing independent structural
helper before changing parser behavior. Keep source paths and payloads private.

The current phase is Phase 1 source understanding. Resolving this input-evidence
gap precedes conclusions about rung patterns, loops, alarms or sequences from
this run. Scoped symbol/alias/reference analysis remains a proposed next coding
slice, pending the source comparison and agreement on that slice.
