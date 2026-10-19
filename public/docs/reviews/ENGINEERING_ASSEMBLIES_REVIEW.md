# Exact-address engineering assemblies

## Returned grouped-candidate validation

Return `d6c5fc1`, report
[work-check-20261018T060208Z-324ece4a.json](../../inspection/work-check-20261018T060208Z-324ece4a.json),
tested clean `f5399e6`. All 1,743 application cases passed with two expected
Windows skips; all 139 helpers passed. Private results saved with no failure
code. All 54 historical/current work reports validate.

All 24 preceding non-signal summaries and 92 prior signal coverage fields are
unchanged after revision normalization. The frozen six-example/eight-reserved-unit
sample record is identical, and no diagnostic sample was returned.

All 4,163 candidate scans completed with zero truncation. They retained 4,969
pairs across 2,296 outputs; 906 outputs have target categories. Pair partitions:

| Dimension | Counts |
|---|---|
| Seed | 2,259 both endpoints; 1,839 condition only; 871 target only |
| Condition kind | 2,872 XIC; 1,305 XIO; 768 comparison; 24 ONS storage |
| Guard quality | 4,323 modeled; 547 binding gaps; 99 stateful |

Target categories have 1,005 overlapping memberships across 906 outputs.
Condition categories have 4,741 memberships across 4,098 condition-seeded pair
occurrences. These overlaps are expected and do not establish a number of
distinct physical objects. The conservative retained extension is 3,093,888
bytes of its 8 MiB allowance. The public report is 65,505 bytes.

Work-check took 836.537 seconds (13:56.537), 9.906 seconds longer than the prior
run. Application tests account for 6.836 seconds, analysis 1.953, private save
0.818 and summaries 0.294. This is a comparison of two runs, not a timing trend.

This closes tracker R1. Seven cycles in the reconciled window are complete;
three remain as the central estimate, with a two-to-five range. The original
four-cycle baseline and its consumed R1 cycle remain in the
[completion tracker](../planning/PRE_TEAM_REVIEW_TRACKER.md).

## R2 implementation scope

The new source assembly index groups qualified provider occurrences by exact
relationship address. It joins Boolean conditions and output guards, PID named
slots and member uses, eligible calculation inputs/destinations, timer/counter
controls and members, ladder/SFC transition references, and file-operation slots.
It retains references to the original source evidence instead of copying source
text or expanding all transitive paths.

Each group lists source memberships, related rungs, evidence types, context
markers and a bounded scan status. A membership keeps its provider, source
occurrence, captured role, instruction/rung, related address and context flags.
Repeated contacts remain distinct. Different members of a structure, literal
array spellings, scopes and source edits remain distinct. Provider-specific
qualification controls admission; relationship identity alone is insufficient.

The report adds **Cross-rung groups**, with search, evidence-type filters,
multiple-rung/type filters and explicit incomplete/uncertain selections.
Selected groups show captured roles, original provider dossiers, related exact
addresses and source/edit context. Related-address navigation is bounded to
5,000 visits and 500 displayed links per selection; truncation is visible.

These are source associations, not confirmed equipment objects. PID slots do
not become read/write roles merely because their names are known. A shared
address or instruction does not prove a calculation transfer across branches,
an active cascade, a command/feedback pairing, a delay, a shutdown or alarm
ranking. Original provider views retain the branch, guard, stored-state,
master/selector and sequence evidence needed to assess those questions.

## Remaining scope and source gaps

R2 requires its own returned export distribution before it can close. R3 still
owns unresolved source-supported rules and the reasoned residual-gap inventory.
In particular, MSG currently exposes control-operand context rather than payload
endpoints. Some exact file slots have no base relationship address because the
base access layer retained unknown roles; these are explicit assembly exclusions,
not invented address matches. Missing/unsupported source and condition transfer
remain visible alongside accepted groups.

No new plant sample or broader private export is requested. The sixteen saved
artifacts remain private; work-machine transport remains manual and the listener
stays disabled. The editor, correction overlays, PCSD and FHX remain later phases.

## Contracts and bounds

Assemblies1 is opt-in for reusable APIs and enabled by the current CLI/work
check. Review29 and manifest32 embed it in the existing review artifact; the
sixteen saved artifact names remain unchanged. Work47 adds a closed assembly
summary. Historical version gates and API defaults remain available.

The private assembly allowance is 64 MiB, with 100,000 memberships, 20,000 groups
and 500,000 provider-row/link visits. Review29 JSON/HTML limits are 448 MiB /
480 MiB. The summary allowance is 8 KiB and the work report remains 104 KiB.
The maximum-width transport envelope is 103,810 bytes, leaving 2,686 bytes;
its new summary is 3,522 bytes. No private address or occurrence identifier is
included in this aggregate extension.

Retention charges serialized memberships and ID links before append, unique
rung IDs once per group, 1,024 bytes of fixed group metadata plus address IDs,
and 32,768 bytes of fixed top-level metadata. Maximum closed group metadata is
544 bytes before the separately charged lists/IDs. Final serialization verifies
actual size does not exceed the reservation. Exhaustion and upstream scan
truncation produce visible incomplete groups and partial status.

The initial 24 MiB proposal was rejected before publication after checking the
returned counts: signal evidence alone requires 45,913-45,957 memberships and
at least 31,980,794 reserved bytes (30.50 MiB). Qualified guard contact
occurrences are not interchangeable with deduplicated reverse-address links.
Across all providers, the closed counts imply approximately 53,833-54,242
memberships, at most 7,591 groups and roughly 160,000 visits. The practical
reservation estimate is 38-44 MiB. A deliberately exaggerated calculation using
all closed flags, maximum canonical ID widths, nonnull related addresses and
unique rungs on every membership gives 65,538,466 bytes (62.502 MiB).
These are pre-run bounds/estimates, not observed private assembly results.
Increasing the local allowance avoids predictable truncation; the aggregate
sharing cap, sampling reservation and transport behavior are unchanged.

## Capacity and report verification

A wholly invented 4,606-rung / 2,702-tag source contains 12,897 instructions.
It produces 3,000 groups, all spanning rungs, with 35,006 memberships and 600
multi-provider groups. All grouping scans complete. Actual JSON is 21,248,928
bytes and conservative reservation is 24,352,084 bytes. The projection visits
85,218 rows and 41,455 links. Replaying the canonical invented providers matches
exactly. Final projection time was 2.056 seconds; the separate provider build took
312.803 seconds. These are local invented-input measurements, not a work-PC
runtime prediction.

Its 1,842 file-slot exclusions were audited: exact specialized slots absent
from the base relationship universe remain visible as missing addresses.
That source-rule gap stays on R3's list. The smaller checked-in demo covers all
six providers, SFC/edit context, repeated contacts, PID slot/member distinctions,
timer member links, expression leaves and unresolved cases. It has fifteen
groups and eighty-four memberships, with no grouping truncation.

The saved HTML was inspected in Chrome. Exact-address groups, source roles,
calculation navigation and TIMER.DN member navigation display correctly; the
private/offline badge uses the original Unicode separator. No application
console errors occurred (one browser-extension warning was unrelated). Search,
pagination, all six source links, bounded neighbor lists and literal source
markup are additionally covered by eleven DOM tests. The temporary preview
server and browser tab were closed.

## Release verification

The actual isolated Bash launcher passed 1,786 application cases (two expected
Windows skips) and 139 helpers. It saved a valid work47 report, one local
feedback commit and sixteen manifest32 artifacts, with zero Git network calls.
Total local rehearsal time was 599.138 seconds. The frozen six-example/eight-unit
sample record replayed identically; no diagnostic sample was added.

An initial rehearsal exposed an editing-time Unicode encoding error in five
legacy label assertions. The original Unicode lines were restored, all five
checks passed, and the full rehearsal above passed afterward. No test
expectations were weakened. The only changes after that full-suite snapshot
were the assembly/review byte allowances and their matching regression in four
files. Final 30 guarded core/summary cases and 13 workflow/work-report cases
passed against the 64 MiB version. Eleven DOM cases, renderer checks and 48
development work-check cases also passed. Independent code review found no
remaining blockers.

Two fresh final saves passed canonical source replay and matched all sixteen
artifact bytes; all manifest hashes were verified. The final CLI save matched
both, including the public invented demo. Against `d6c5fc1`, all 25 preceding
summary families (including all 104 signal coverage fields) and fifteen
non-review artifact bytes are unchanged. All 54 real historical/current reports
remain byte-identical and validate; including the isolated work47 report,
55 reports validate. All 256 runtime/asset/test files match the final verified
isolated snapshot. The real confidential tree and ignored listener files were
not read or copied.

The [invented report](../../examples/engineering-assemblies-review-demo.html)
is 832,166 bytes, SHA-256
`f3ecca25c72b2de816b83c30d1ae5e09a7fbb9d0540aee9bc5713db64ef3f3f4`.
Its fixture SHA-256 is
`875a97cffdd78e03a7ab6f31fdced263a872bca3c497d88069afff1f1a891d44`.

R2 is ready for a normal work-machine run. Its returned provider/gap/budget
counts must be analyzed before closing R2. Reports are not yet at the R4
team-review gate; no manual classification or aesthetics review is requested
for this run.

## Returned export validation (2026-10-18)

Return `cdad803` tested clean `158868d`: 1,786 application cases (two expected
skips), 139 helpers and all 55 historical reports passed. Assembly scans were
complete: 54,123 memberships, 7,408 groups, 3,759 spanning rungs and 1,527
spanning providers. All 25 preceding summaries and frozen samples were unchanged.
This closes the supported R2 grouping deliverable. The 78 missing-address
exclusions comprise 74 SFC references and four file slots; four SFC binding
gaps and one dynamic file slot are separate. The full reconciliation, runtime
and R3 follow-up are recorded in [RESIDUAL_SOURCE_REVIEW.md](RESIDUAL_SOURCE_REVIEW.md).
