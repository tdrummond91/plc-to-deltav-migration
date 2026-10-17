# Calculation inputs and destinations

## Confirmed work-machine return

Return `48dcd22` tested clean `2105ce3`: 1,254 application cases passed with two
expected Windows skips and all 139 helpers. The private analysis saved. All
2,138 selected blocks are retained; 2,136 are eligible and two have unresolved
destinations. There are 2,137 segments, including 1,294 blocks in branched rungs,
2,990 input operands and 132 CPT reads. One CPT local reuse link was found.
Incoming contexts are 2,021 modeled, 85 with binding gaps and 32 stateful.
All sixteen preceding summaries and the frozen six examples are unchanged;
all 40 historical reports validate. Next is
[Boolean output context](OUTPUT_CONTEXT_REVIEW.md), not a relaxation of branch
boundaries or an assumption that unmatched inputs/results are unused.

## Returned evidence and scope

Return `693e419` tested clean `f4f704d`: 1,216 application cases passed with
two expected Windows symlink skips, plus all 139 helpers. Private analysis saved
without a failure code. All 39 historical reports validate. Fifteen prior
summaries match after removing only tool revision; the six diagnostic examples
and eight-unit reservation replay exactly.

PID connection coverage accounts for all 46 controls and 322 slots. The 515
exact-address records include 333 direct members. All master operands are
literals, so no explicit master-reference candidates were found. There are no
recorded connection gaps in this bounded scope; execution and engineering loop
identity remain unproven. See the [confirmed PID return](PID_CONNECTIONS_REVIEW.md).

The earlier relationship analysis excludes 13,053 instructions in 1,863 branched
rungs from local calculation links and finds only one such link. The existing
ten-opcode catalog covers 2,138 source occurrences: MOV 1,131; CLR 41; ADD 32;
SUB 463; MUL 121; DIV 277; ABS 8; LN 2; SQR 18; CPT 45. Capturing inputs and
destinations for these occurrences is useful even when no local link exists.

## Analysis rules

The new companion retains each selected math/move occurrence with its existing
input operands, CPT reference occurrences, destination and incoming-condition
evidence. Literal inputs retain source operand links rather than copied values.
Unknown inputs, dynamic selectors, malformed signatures and unsupported
expressions remain visible. The old relationship, access and condition payloads
are unchanged.

Regions follow the parsed series/branch structure. Prior writers are cleared
at every fork, join, rung boundary and unsupported instruction. Sibling legs
are separate, including nested and empty bypass cases. The algorithm does not
enumerate every possible branch path. Timers, PID, copy ranges, calls, unknown
blocks and other unsupported operations remain boundaries.

A classified pure predicate can change incoming conditions without ending the
segment. Possible reuse links join an earlier eligible destination to a later
read of the same exact expanded address in that segment. They do not establish
execution, reaching definitions, a value, a guaranteed producer or a write
guard. A false condition or fault can prevent a data operation; physical wiring,
types, member validity, scheduling and process intent are not proved here.

Reads are considered before recording an occurrence's write. Repeated CPT
references remain distinct reads. A different member or whole-root write
invalidates the previously remembered writer for that root; suffix spellings
are not merged. No earlier local producer means only that this analysis found
no link, not that an input is unused or a process path ends.

## Report and workflow

The report's **Calculation inputs and destinations** view provides source,
input, destination, condition and segment navigation. **Possible local reuse**
is explicitly conditional source evidence. Existing source and calculation
views link to these records; unresolved cases remain available for inspection.

The independently invented [fixture](../../fixtures/synthetic/calculation_paths_demo.L5X)
and [HTML report](../../examples/calculation-paths-demo.html) exercise branch
boundaries, predicates, aliases, overlapping roots, repeated reads, malformed
inputs, unknown blocks, pagination and literal display of source markup.
They contain no plant-derived logic or values and are not controller-ready.

On the work machine, from the repository folder on the feature branch:

```bash
git pull
bash ./run-work-check.sh
git push
```

The script tests the checked-out code, saves the private report and commits the
validated feedback locally. Git transport remains manual, the listener remains
disabled, and no additional plant samples or engineering/team review are
requested. The next returned counts determine the next analysis slice.

## Contracts and validation

Calculation paths1 is bounded to 8 MiB and 250,000 records. Its closed public
summary permits 4 KiB. Review16 reserves 216 MiB JSON and 248 MiB HTML;
manifest19 retains sixteen hashed artifacts because the companion is embedded
in the review payload. Work33 retains the 80 KiB outer limit, older contract
limits and the 16 KiB diagnostic-record cap. Existing sample selection is frozen.

The conservative public envelope is 69,108 bytes against the unchanged 81,920-byte
limit. Independent core review exercised 75 generated mixed programs and three
hash seeds. A dense invented case with 2,400 selected operations, 2,400 links
and 1,200 segments used 5,495,115 bytes of the 8 MiB companion allowance.
The demonstration companion uses 277,819 bytes; its public summary uses 2,664.

Focused checks passed: 26 core cases, 229 existing integration cases, 12 new
workflow cases and one development-only DOM regression. The DOM regression
fails when the original rejected-destination-link bug is restored in memory;
it remains outside the work-machine test selection.

Browser review of the invented report confirmed search, unresolved-case filters,
50/50/50/8 occurrence pagination, branch-segment navigation, repeated CPT reads,
condition graphs and source/address links. Rejected destinations retain source
navigation without an accepted-address link. Source markup displays literally;
the report has no horizontal overflow or application console errors. An unrelated
browser-extension warning was present. Encoding and destination-link spacing
issues found during review were corrected before final verification.

The actual Bash launcher passed in an isolated repository using only the invented
fixture: 1,254 application cases (two expected Windows symlink skips) and 139
helpers. It saved review16/manifest19, verified all sixteen artifact hashes and
created exactly one local feedback commit. Git tracing recorded no transport
calls. The work33 feedback was 40,166 bytes, with the frozen six examples and
eight-unit reservation unchanged.

Repeated analysis and a separate CLI invocation produced the same sixteen
artifact bytes. The CLI returned its expected partial-analysis exit code 3, and
the checked-in invented HTML is an exact copy of that output. Comparison against
`693e419` found all fifteen earlier non-HTML artifacts byte-identical; all sixteen
prior summaries match after normalizing only tool revision. Existing embedded
companions also match. All 39 historical feedback files remain unchanged and
validate alongside the new invented return. Canonical payload reconstruction,
manifest hashes and isolated-repository cleanliness checks passed. The 171
runtime, asset and test files matched the frozen working tree used for publishing.

Full development regression passed: 1,556 cases, zero failures/errors and two
expected Windows symlink skips (744.122 seconds). Discovery excluded the ignored
listener test before import. This includes the guard that reruns the selected
work-machine suites with subprocess creation and sockets prohibited.
