# Grouped source candidates and consolidated block evidence

## Returned evidence

Return `b9240c8` tested clean `1b78327`: 1,707 application cases (two expected
Windows skips) and 139 helpers passed. All 53 historical reports validate.
The 24 non-signal summaries, all 76 preceding signal fields and the frozen
six-example/eight-unit sample envelope are unchanged. No diagnostic sample
was requested or returned.

All 4,163 output dependency scans completed without truncation, covering
4,099 unique guards. They retained 15,082 condition/output associations and
12,269 qualified reverse address/output associations on 4,144 addresses.
Of 4,053 outputs with captured reads, 4,033 have exact reads. The 110 complete
scans with no retained reads do not establish dead or unconditional logic.
The 346 unbound associations reuse existing unresolved occurrences; they
are not 346 newly discovered source failures.

Work-check took 826.631 seconds (13:46.631), up 7.494 seconds (0.915%).
Application tests account for 7.337 seconds of that difference; analysis
was 0.894 seconds faster. This comparison does not establish a timing trend.

## Candidate rule

Signal5 joins each qualified exact output target to exact-address condition
occurrences already retained in its guard dependency index. A pair is retained
when either endpoint has qualified, use-linked alarm/equipment/sensor wording
or an exported module input/output root. These five seeds can overlap.
The rule retains contact occurrences separately, including repeated contacts,
comparison operands and ONS storage. It preserves branch ancestry through
the original guard, without enumerating execution paths.

Each output carries `candidate_context`: a scan status, target categories,
and condition records containing `condition_read_id` and categories. Source
fields are recoverable from the exact address's authored evidence and operand
membership. Reader-only aliases do not supply wording for a target writer.
Root descriptions remain root context; member/channel meaning is unverified.

Namespace-gap guards and unresolved targets do not become paired candidates.
Binding-gap, opaque and stateful guards can retain qualified source pairs;
their original uncertainty remains attached. Stored settings, other writers,
active edits, engineering purpose, shutdown behavior and priority remain
unresolved by this rule. A source pair does not prove causal influence or a
necessary input. No new source sample or broader private-data export is added.

## Report consolidation

**Signal relationships > Grouped source candidates** groups output occurrences,
with filters for the five seed types and incomplete scans. Open an output to
see each condition occurrence, exact address, contact kind and seed fields.
Full source wording is available as inert text so negation and surrounding
context remain visible. Search includes linked condition evidence.

**Engineering analysis** joins specialized PID, routine-call, file-operation
and custom-instruction context to exact block IDs. It preserves base catalogue
classification and unknown-role counts. In this return, all 128 unsupported
base instructions reconcile to 46 PID, 78 execution-control, three file-operation
and one custom-instruction occurrences. The 82 base block gaps omit the 46
signature-known PID blocks. The 505 unknown-role fields reconcile to 322 PID,
164 execution, 18 file-operation and one custom instance fields. Only the
18 file slots receive additional access roles from the specialized evidence.

These totals explain where context exists. They do not relabel the 66 base
unidentified rungs as approved engineering functions. The private report
computes overlaps from actual IDs and keeps missing source, unknown roles,
binding gaps and opaque condition transfers visible.

## Contracts and validation

Review28 embeds signal5; manifest31 retains sixteen artifacts. Work46 returns
only closed count summaries. Signal5 private JSON is limited to 72 MiB, its
summary to 24 KiB, review JSON to 384 MiB and HTML to 416 MiB. Historical
contracts and the reusable API's default signal1 behavior remain unchanged.
Candidate joins and retention are bounded, with explicit truncation inherited
from contributing scans. The fixed rule is `qualified-direct-signal-context-1`.
Limits are 250,000 authored operand visits, 100,000 indexed category links,
100,000 dependency visits and 50,000 retained pairs. A separate conservative
8 MiB allowance charges 4,096 fixed bytes, 256 per output wrapper, 128 per
categorized target and 384 per retained pair before allocation. Exhaustion
leaves an explicit subset. Index truncation conservatively marks eligible
outputs incomplete. Complete scans describe this rule's scope, not complete
plant understanding.

The work report cap remains 104 KiB. The maximum-width probe, including the
existing frozen sample envelope, is 100,254 bytes, leaving 6,242 bytes.

The [invented fixture](../../fixtures/synthetic/signal_candidates_demo.L5X)
contains alias attribution, repeated contacts, branch alternatives, I/O roots,
stateful/unknown transfers, unresolved targets and pagination. Its
[offline report](../../examples/signal-candidates-review-demo.html) contains
no plant source. A separate [mixed-provider report](../../examples/engineering-evidence-review-demo.html)
exercises PID/file/call/AOI evidence, malformed signatures, namespaces and
missing routine bodies.

The 36 new production cases passed with process and socket creation blocked
before project imports. Independent review tightened impossible counter
combinations: target-only pair populations and mutually exclusive module
directions. Final summary mutation regressions and guarded cases pass.

An invented capacity probe contains 4,606 rungs, 5,000 tags and 4,259 outputs.
All 4,259 candidate scans completed without truncation, retaining 10,503 pairs:
4,212 condition-seeded only, 4,210 target-seeded only and 2,081 seeded on both
ends. Signal5 JSON is 37,148,756 bytes and its summary is 8,031 bytes. Removing
the new fields exactly reproduces signal4's 34,532,302 bytes. The actual
extension is 2,616,454 bytes, below the conservative 5,400,064-byte allowance
and 8 MiB cap. Canonical replay and final summary validation passed.

An earlier, denser invented fixture with three wording categories on 2,500
declarations reached the existing 32 MiB rung-analysis limit before signal
analysis. The passing probe uses one category on those declarations; no cap
was raised to accommodate the synthetic stress case. These invented results
do not predict plant run times.

All four new candidate DOM cases and thirteen engineering evidence DOM cases
passed. Existing rung, file, signal and authored-wording UI regressions passed,
as did 55 execution/AOI/PID workflow cases and 76 development workflow cases.
Independent review corrected omitted AOI array/protection/symbol gaps, valid
PID array-header handling, and PID/execution context-gap summaries. Final
independent review found no remaining blocking issues.

Chrome verified 50/14-row candidate pagination, module-root filtering, exact
I/O source links, reader-alias field attribution, mixed-block navigation and
the final provider gap labels. The ordered block table was visually inspected;
no browser errors were recorded. The test tab and loopback server were closed.

The actual Bash launcher passed 1,743 application cases (two expected Windows
skips) and all 139 helpers in an isolated repository. It saved all sixteen
hashed artifacts, replayed the unchanged sample reservation and made one local
feedback commit with zero Git network calls. The invented run took 653.346
seconds; this is local verification timing, not a plant-run prediction.

The full-suite snapshot preceded the final summary-invariant and report-label
review corrections. Those four changed runtime/test files were checked with
the final guarded production cases and targeted DOM regressions, then copied
into the isolated repository for two fresh saved analyses. Both pass canonical
replay and match all sixteen artifacts. The CLI reproduces the final candidate
and engineering demos byte for byte. All 249 final runtime, asset and test files
match the verified repository; the five core/test hashes match the guarded run.

All 24 non-signal summaries, 92 preceding signal coverage fields and fifteen
non-review artifacts match the baseline. All 53 historical work reports remain
byte-identical and validate alongside the isolated report. Both verification
repositories finish clean. Candidate and engineering HTML sizes are 1,822,736
and 703,894 bytes respectively. No new sample allowance was consumed.

## Next return and remaining work

The next ordinary work-machine run measures candidate pairs, their seed
intersections and incomplete scans on the export. Aggregates from earlier
stages cannot establish these intersections. No manual team review is required.

This remains Phase 1. Multi-rung equipment/alarm interpretation, residual
binding and transfer gaps, source-content limitations and final report
consolidation still precede engineering review and editable PCSD delivery.
Git transport stays manual and the listener stays disabled.
