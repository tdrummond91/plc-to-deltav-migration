# Guard dependencies and bounded source trails

## Returned evidence

Return `d9eca23` tested clean `8f63a10`. All 52 historical work reports
validate; the 24 preceding summaries match after removing revision metadata.
The application suite ran 1,672 cases with two expected skips and no failures
or errors; all 139 helper cases passed. Private results were saved. The frozen
six-example/eight-reserved-unit envelope is unchanged, with no diagnostic sample.

The explicit alarm scan inspected 83,942 XML elements, 7,035 source entities
and 11,117 stored-data contents. It found no supported typed alarm declarations,
alarm containers or alarm elements, and no capture gaps. Parsed RLL also has
no ALMA, ALMD or ASO occurrences. These results narrow the next investigation
to conventional Boolean logic and other sources; external HMI alarms and logic
outside parsed RLL are not ruled out.

Total work-check time was 819.137 seconds, 27.629 seconds longer than the prior
run (3.49%). Application tests account for 17.608 seconds of the increase;
analysis, saving and summaries account for 2.954, 4.109 and 2.988 seconds.
This comparison alone does not establish a timing trend.

## Source evidence

Signal4 adds a saved, bounded index from each output guard to its captured
condition operands, plus a reverse index from qualified exact addresses to
output occurrences. Contacts, comparison operands, literals, system flags,
unresolved operands and ONS storage remain distinguishable. Reverse links
require an exact input address and a namespace-qualified guard. An unresolved
output target does not erase the captured input association.

The index records condition ancestry, not necessary conditions or causal
influence. Branch structure remains in the original condition DAG. Outputs,
multiple writers, source-content edits and routine identities remain separate.
Signal1 through signal3 retain their historical contracts and default behavior.

Every output carries a scan status. Each unique guard is walked once, with
limits of 4,096 nodes and 16,384 edges; global limits are one million nodes
and two million edges. Cached condition IDs and retained forward/reverse
links have separate 100,000-entry limits. Forward and required reverse links
are reserved together. Exhaustion retains an explicit partial result. If any
output scan truncates, all reverse lists must be treated as subsets.

## Report navigation

**Signal relationships > Source trail starting points** offers search and
filters for qualified alarm, equipment and sensor wording, plus module input
and output roots. Wording is a search lead, not a verified physical class.
Open an address and select **Trace upstream writers** or **Trace downstream
guards**. Each step links to the original operand, output guard and next address.

The bounded trace follows contact/OTE source associations. It shows and stops
at competing writers, other/unknown writes, timer/counter state, set/reset
actions, comparisons, unresolved references, unknown/stateful guards and
different routines or source edits. It does not silently select an active edit
or a winning writer. Branches may continue, retaining their original guard;
their presence does not mean every input is required.

A repeated address on the retained witness ancestry is a captured source cycle;
a previously reached address through another branch is a shared destination.
Neither describes a proven runtime loop. Exploration is limited to eight steps,
128 address states, 256 displayed rows and 4,096 inspected index entries.
Tables page at fifty rows. Finished exploration means inspection reached the
displayed boundaries, not complete process coverage. Missing captured uses do
not establish dead or unused logic. Traces do not cross SFC, numeric calculations,
indirect aliases, communication channels or physical wiring by inference.

The [invented report](../../examples/signal-dependencies-review-demo.html)
contains linear chains, a diamond, a cycle, alternate source contents,
competing writers, stateful and unresolved transfers, paging and a depth limit.
It contains no plant source.

## Contracts and verification

Review27 embeds signal4 with unchanged alarm evidence1 and file operations1;
manifest30 retains sixteen artifacts. Work45 carries the closed signal4 counts.
Signal4 private JSON is bounded at 64 MiB, its closed summary at 20 KiB, and
review27 at 376 MiB JSON / 408 MiB HTML. Historical limits are unchanged.
The outer work report remains bounded at 104 KiB. Its maximum-width probe,
including the existing frozen sample envelope, is 99,198 bytes, leaving
7,298 bytes below that cap.

All 35 new production cases passed with process and socket creation blocked
before project imports. All 76 development workflow cases passed. Independent
review found no blocking issues; its empty-index wording correction now says
that no qualified indexed downstream coil guard was captured. The review also
noted a bounded repeated index-status scan and additional UI limit test coverage
as nonblocking follow-up opportunities.

Four DOM cases passed, covering both trace directions, exact XIC/XIO display,
source-content boundaries, shared branches versus cycles, competing writers,
stateful/unknown/binding and comparison boundaries, depth limits, pagination,
wording filters and incomplete reverse indices. Chrome verified the three-rung
chain, two source-content boundaries, cycle termination and 50/50-row fanout
paging. The layout was visually inspected; no browser errors were reported.
The test tab and loopback server were closed.

The invented capacity probe contains 4,606 rungs, 5,000 tags/addresses,
12,741 condition operands and 4,259 outputs. All 4,259 dependency scans completed
without truncation. It visited 32,359 nodes and 31,286 edges over 4,195 unique
guards, retaining 12,585 forward and 12,585 reverse links. Private signal4 JSON
is 32,443,742 bytes; its summary is 6,992 bytes. Canonical replay and summary
validation passed. Projecting to signal3 reproduced its 29,265,379 bytes exactly.
These are invented capacity checks, not work-machine timing predictions.

The isolated actual Bash launcher passed 1,707 application cases (two expected
Windows skips) and all 139 helpers. It saved review27/manifest30 with all sixteen
artifact hashes verified, replayed the unchanged six-example/eight-unit
reservation, and made exactly one local feedback commit with zero Git network
calls. The entire invented run took 702.642 seconds; that is local verification
timing, not a prediction for the plant export.

Two separately saved analyses passed canonical replay. The CLI reproduced all
sixteen artifacts and the committed invented HTML byte for byte. All fifteen
preceding non-review artifact bytes, all 24 non-signal summaries and all 76
preceding signal coverage fields are unchanged. All 52 historical work reports
are byte-identical and validate alongside the new isolated report. All 242
runtime/asset/test files match the full-run snapshot; both isolated verification
repositories finish clean. The fixture is 12,570 bytes and the report is
2,136,985 bytes. No actual private source or listener state was read or changed.

## Next work-machine return

Use the ordinary manual pull/check/push sequence. The next return measures
direct guard associations, reverse-index coverage and any traversal limits.
No additional plant sample or manual team review is requested. This remains
Phase 1: candidate equipment/alarm relationships, remaining source gaps and
report consolidation precede engineering review and editable PCSD delivery.
Git transport stays manual; the listener remains disabled.
