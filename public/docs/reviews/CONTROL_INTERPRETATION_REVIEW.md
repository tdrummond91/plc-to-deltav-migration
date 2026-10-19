# Control interpretation and final-report verification

## Returned evidence: C10

Return `883002a` adds `work-check-20261019T122333Z-6f881251.json`, testing
clean `7dcc4fa`. All 57 historical reports pass bounded raw reads, their own
schema limits, cross-summary validation and exact canonical-byte comparison.
Tests: 1,920 application cases, two expected skips, 139 helpers, zero failures
or errors. Private save succeeded. The analysis remains partial.

Condition4 changes 106 transfers from opaque to pass-through: PID46, MSG27,
MVM16, SWPB10, GSV4, AVE/FAL/SQO one each. Residuals are SFR140, JSR76,
GSV1, SBR1, RET1 and one custom occurrence. The only opaque output guard
contributor is SBR. This does not establish outgoing control-flow semantics.

Communication2 accounts for 27 distinct owners, parameters and linked calls:
20 CIP data-table, six CIP-generic, one PLC5-typed; CIP26/DH+1;
12 read, nine write, six service-dependent. AOI2 links four exact member uses
to four parameters (three writes to Input, one read of Output). Its instance-only
call has no required trailing parameters; four optional and two system
parameters are retained. No parameter ordering is inferred.

### Downstream regression and unchanged evidence

PID incoming condition links changed 46 to zero because the old reader only
accepted opaque transfer nodes; the new PID pass-through nodes still retained
their incoming child. Assemblies consequently changed from two complete/four
partial providers to one complete/five partial, with one extra gap bucket/count.
PID connections2 repairs that reader; version1 preserves historical replay.

Excluding revision metadata, 22 of 27 summary families are unchanged. All 104
signal fields, 54,201 memberships, 7,486 groups, 3,759 multirung and 1,527
multiprovider groups are unchanged. All 4,163 pattern/dependency/candidate scans
and 5,064 authored scans complete, without truncation. Assembly reservation is
40,956,623 of 67,108,864 bytes.

The complete sample envelope is unchanged: six charged/eight reserved of 40,
replayed with no new diagnostic sample. Public report size is 75,826 bytes.
Runtime is 15:09.044 versus 14:34.978; two observations do not isolate feature cost.
Source coverage still includes 55 parsed RLL routines, 14 preserved SFC routines
and one missing/failed body. All 4,606 captured rungs parse; whole-source
instruction completeness is false.

## New bundle

Opt-in `include_control_interpretation=True` requires the preceding full
residual bundle. It selects condition5, PID connections2, execution2 and
communication3 under review32/manifest35/work50. AOI2, assemblies2 and signal5
remain. Defaults and historical schemas retain replay. Sixteen private artifacts,
manual Git transport and the frozen sample boundary remain.

- Condition5 admits a custom AOI pass-through only after a closed source proof
  excludes an EnableOut override in a narrowly supported body. Other AOIs retain
  explicit proof-failure categories. Control-transfer instructions remain opaque.
- PID connections2 follows authenticated PID pass-through or opaque nodes to
  their incoming source condition; no execution guard or active cascade claim.
- Execution2 associates exact routine contents and captured SBR/RET boundaries
  with calls, and classifies argument source forms. It does not assign InputCount,
  input/output roles, parameter pairs, types, values or execution paths.
- Communication3 catalogs explicitly encoded common generic service identifiers
  and validates numeric source shapes/ranges. Object/attribute meanings, device
  support, effective runtime configuration and successful transfer remain unknown.
- Work50 adds a closed count-only rack-backing investigation diagnostic. It
  joins already captured card, adapter and stored backing-shape evidence without
  resolving a binding or exporting raw configuration. Communication-format and
  profile interpretation remain explicitly unimplemented.

See [condition rules](CONDITION_TRANSFER_REVIEW.md),
[call boundary contract](ROUTINE_CALL_SHAPE_REVIEW.md), and
[generic-service interpretation](COMMUNICATION_INTERPRETATION_REVIEW.md).
The [rack-backing investigation](RACK_BACKING_INVESTIGATION.md) records the
remaining mapping boundary and its new diagnostic.

## Validation and readiness

Independent component and integration reviews found no remaining issue in the
condition, execution, PID and communication changes. The broad partition passed
305 development cases plus the audited 1,980 application cases (two expected
skips) and 139 helpers. The application/helper suites ran under the existing
subprocess/socket-denial guard; an additional 171-case subset also passed.
The partition avoids running the entire application suite twice through full
discovery and the nested boundary test.

After the later rack addition, 55 current-workflow/work-check cases passed;
three further cases checked cross-schema rejection, coherent forged rack
populations and the complete work50 maximum-width cap. The current audited
application selection is 1,995 cases. All 13 new rack tests passed with subprocess
and socket creation denied. Independent review caught and verified fixes for
inherited protection, Unicode parent-name matching and ambiguous backing
connection context; no findings remain. The earlier 27-case
condition/current-workflow/DOM run also passed. These are incremental
verification runs; the broad partition was not repeated after the small addition.

The fully invented scale input contains 4,606 rungs with repeated writers,
branches, timers, calculations, 46 PID calls and messages. The production
analysis, private-save, summary and sample-replay stages completed. All sixteen
artifact hashes/sizes and the saved source bytes matched. Manifest35/review32
produced a 168,974,457-byte HTML report within its 496 MiB limit; its escaped
payload was 168,555,227 bytes within 464 MiB. Condition5 retained 30,471 nodes
and 4,549 outputs, occupying 24,089,569 bytes within 32 MiB. Assembly grouping
retained 48,784 memberships across 7,937 groups; candidate and authored scans
completed without truncation. These are synthetic capacity results, not plant
coverage or performance forecasts.

The temporary QA script initially failed while collecting its final metadata
because not every summary has a `coverage` key. The production pipeline had
already succeeded. A separate read-only verifier recovered the evidence from
saved artifacts without rerunning analysis. Stage timings were 247,589 ms build,
285,118 ms save, 234,777 ms summaries and 36,522 ms synthetic sample replay;
concurrent verification work makes these unsuitable as isolated benchmarks.

Rendered browser checks passed for the small new demo's call boundaries,
generic selectors and PID incoming link. Chrome also passed the full-scale
overview counts, page 2 of 93, search yielding the expected 200 authored hints,
cross-rung memberships, exact-rung branch navigation and AOI proof links. The
initial automation attempted to transfer oversized page content; querying only
rendered content avoided its 64 MiB transport limit. No report console error
was observed. One unrelated extension warning was excluded. Both temporary
loopback servers were stopped after verification.

All 57 historical public reports passed schema-specific validation, caps and
exact canonical-byte comparison after the bounded 128 KiB preread.

The next returned export must restore 46 PID condition links and independently
reconcile assembly provider recovery; explain the five GSV signature outcomes;
disposition the custom AOI call; account for 76 JSR calls and 164 routine fields;
catalogue the six generic messages; and reconcile the rack diagnostic against
11 rack connections and 15 input/output declarations. Unchanged source and
scan populations, frozen samples and the saved report must remain intact.

The readiness challenge found rack backing was fixed to `not_analyzed` even
though module attributes and tag representations were captured. Existing public
totals could not join those facts to individual rack declarations. This is
unfinished parser investigation, not proven missing source or an engineering-only
question. The diagnostic informs the next supported rule or documented boundary.
The 82 base unknown blocks and 505 unknown-role slots remain distinct from
additional source context; specialized evidence does not silently resolve them.

R3/R4 stay open until the [completion gate](../planning/PHASE_1_ENGINEERING_ANALYSIS.md)
is met. Ten cycles are complete; two remain centrally (range 1-3). The tracker
records the explicit extension from eleven to twelve for the missed rack
investigation, with C11 diagnostic validation and C12 rule/closeout planned.
