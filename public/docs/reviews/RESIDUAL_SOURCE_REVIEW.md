# Residual source context and investigated gaps

Return `31cc08b` validated this capture bundle on 2026-10-19. Current work and
remaining semantic investigations are recorded in the
[C14 readiness assessment](PHASE_1_READINESS_REVIEW.md).
The original implementation/validation record below remains historical.
Its assembly binding-exclusion counts include known non-address guard values;
the current audit records the discovered accounting issue and versioned fix.

Updated 2026-10-18. Phase 1, R3 bundle ready for work-machine validation. See the
[completion tracker](../planning/PRE_TEAM_REVIEW_TRACKER.md) for the current
cycle budget. R2 is closed; R3 and final readiness remain open.

## Returned R2 evidence

Return `cdad803`, [work report](../../inspection/work-check-20261018T123641Z-c1cdf30e.json),
tests clean `158868d`. All 1,786 application cases passed with two expected
Windows skips; all 139 helpers passed. The private run saved successfully.
All 55 historical work reports validate. All 25 preceding summary families,
including 104 signal coverage fields, are unchanged after excluding revision
metadata. The frozen sample envelope is unchanged: six charged examples,
eight reserved units of forty. No new plant sample was requested or exported.

Assemblies1 completed its scan with 7,408 exact-address groups and 54,123
memberships; 3,759 groups span rungs and 1,527 span providers. Evidence remains
partial because source and behavior boundaries are retained. Reserved size was
40,807,153 of 67,108,864 bytes; visits were 95,782 rows plus 64,065 links of
500,000. No scan truncation occurred.

| Provider | Memberships | Exclusions | Reconciled exclusion reason |
|---|---:|---:|---|
| Signal context | 45,916 | 2,136 | Binding / namespace qualification |
| PID connections | 1,307 | 0 | None |
| Calculations | 4,339 | 2 | Ineligible occurrences |
| Timers / counters | 1,772 | 0 | None |
| SFC context | 602 | 78 | 74 missing base addresses; four binding gaps |
| File operations | 187 | 5 | Four missing base addresses; one dynamic slot |
| Total | 54,123 | 2,221 | 2,140 binding + 78 missing address + two ineligible + one dynamic |

The 2,252 source-gap counts reconcile as 2,221 exclusions, four partial-provider
markers and 27 MSG semantics markers, across eleven provider/reason buckets.
These count evidence populations, not unique defects. The SFC exclusion total
and the all-provider missing-address total both happen to be 78.

Measured runtime was 14:11.031 versus 13:56.537, an increase of 14.494 seconds:
tests +5.072, analysis +6.352, save +2.003, summaries +1.006, other phases
+0.061. Two runs do not isolate the cost of one feature or establish a trend.

## Source-supported implementation

### Supplemental exact addresses

Assemblies2 admits qualified SFC/file addresses that the frozen base access
catalogue does not index. AVE/FAL/SQO slots can be exactly resolved by their
specialized provider while access4 still records unsupported binding; a
transition-only reference can likewise have no ladder occurrence. These were
missing assembly anchors, not absent plant source.

`supplemental_addresses` contains only `{id, target_id, suffix}`. Identity uses
the existing snapshot/declaration/exact-suffix hash, after canonical provider
replay. Scope, alias expansion and literal suffix spelling remain distinct.
Static qualification does not validate member types or array bounds. The
inclusive canonical 65,536-character expanded-suffix boundary is preserved.
Dynamic selectors, unresolved bindings and namespace gaps remain excluded.

The assembly-only lookup unions these rows with relationships1. It does not
invent legacy operand uses, overwrite access roles or modify earlier provider
payloads. Supplemental rows and ID references are budgeted atomically with
their first retained membership; truncation cannot leave orphan identities.
The report opens the provider dossier and source declaration for these groups,
and offers the legacy-address link only when that legacy record exists.

Expected same-export result, absent new truncation: memberships 54,123 -> 54,201;
exclusions 2,221 -> 2,143; missing-address exclusions 78 -> zero. The distinct
group increase cannot be predicted from the aggregate file-slot population.
Summary2 adds a supplemental-address count and a fixed provider/reason cross-tab
so exclusions can be reconciled directly on the next return.

### Communication source context

The approved XML profile already records 27 MessageParameters elements:
LocalElement/RemoteElement on 21, DestinationTag on six, and MessageType,
RequestedLength, ConnectionPath, CommTypeCode and LocalIndex on all 27. Tag-data1
preserves these as opaque elements. Neither matching record/MSG totals nor the
profile's withheld values establish one-to-one calls, message families or peers.

Communication context1 joins MSG occurrences to resolved scalar MESSAGE control
declarations and their direct Data/MessageParameters records. Repeated calls and
multiple representations stay separate. Every record preserves its owner,
content/element provenance, original attributes, namespace and qualification.
Missing, member/array, alias-only, non-base and custom-type controls remain gaps.
Malformed envelopes, extension siblings and namespace-confounded text remain
unsupported; no effective representation is selected.

LocalElement and DestinationTag receive scoped root-binding candidates, including
alias chains and exact expanded suffixes. They do not receive runtime access
roles or transfer extents. Program-qualified/unsupported forms and failed
bindings remain explicit. RemoteElement and ConnectionPath remain authored
remote fields and are never resolved against local tags. Protocol decoding,
message direction and remote behavior remain unimplemented.

Direct ProduceInfo/ConsumeInfo tag children are captured with source location
and qualification. These records do not establish remote availability, a peer
identity, a physical channel, scheduling or runtime values. The earlier source,
access and tag-data models remain unchanged.

### Report reconciliation

Communication context provides searchable MSG occurrences, parameter dossiers,
local candidates, declaration links and produced/consumed metadata. Engineering
analysis now includes MSG context alongside PID, file, call and AOI providers.
Adding this context does not promote base unknown roles.

Unresolved analysis shows one row per instruction with a base catalogue gap,
unknown role, opaque outgoing condition, binding gap or specialized-provider
gap. Categories overlap. It links exact source and existing provider dossiers,
and explicitly identifies unfinished condition rules as parser investigation.
Separate populations cover binding/alias contexts, indirect selectors, transition
gaps, missing comments/identifiers, read-only/write-only addresses, possible local
dead ends and routine-body gaps. SFC bodies with their own source view are
accounted for there. No entry declares a source-resolvable issue engineer-only.

## Residual investigation ledger

This ledger records the current explanation and next investigation. It is not
a declaration that R3 or the final completion gates are satisfied.

| Area | Evidence already investigated | Remaining boundary / next action |
|---|---|---|
| Source bodies | 56 RLL routines, 14 SFC; 55 RLL parsed, one RLL body missing; no observed encoded/protected regions | Keep the missing body's exact location. Export/source confirmation is needed for its absent contents; do not infer emptiness. |
| Base bindings | 319 uses of 94 rack candidates across eleven roots; two nonstatic index operands | Rack spelling gives candidates, not confirmed namespaces. Preserve alias/declaration evidence and runtime selector expressions. |
| SFC addresses | 267 exact references, four alias-chain gaps; 74 exact anchors omitted by assemblies1 | This bundle admits exact missing anchors. Four binding gaps remain; validate the return before closing this omission. |
| SFR | 140 calls, 139 matched; one missing local step has a peer-chart candidate | Peer spelling/identity is contextual evidence, not permission to redirect the reset. |
| File operations | 95 qualified operations, 294 slots; specialized roles/expression/index context captured | Admit four missing exact anchors; retain the dynamic selector and unevaluated ranges. |
| MSG / interfaces | Stored parameter shapes captured but not joined; produced tag metadata available | This bundle joins source records. Inspect returned cardinalities, qualification and endpoint dispositions; protocol/direction decoding remains parser work. |
| Conditions | 326 opaque transfers, one opaque output guard; branches and state preserved | Existing source review did not establish normal-scan transfer for every opcode. Reconcile specialized slots with documented instruction rules; do not equate captured fields with outgoing behavior. |
| Calls / AOI | 76 JSR candidates, one SBR and RET; one AOI declaration/call, two body rungs and three CPTs captured | Parameter mapping and call effects remain unmodeled. Source body/instance context does not establish the mapping or execution. |
| PID / calculations | 46 PID occurrences and controls, 322 named slots; 45 CPTs parsed; 2,136 eligible calculation blocks | Source slots/member catalogues are captured. Dynamic destinations, runtime path effects and engineering loop interpretation remain separate. |
| Alarms | Explicit supported alarm declarations/settings absent in this export; Boolean wording and conditions retained | Names do not establish warning versus shutdown or priority. Inspect actual source chains; absent HMI/alarm configuration may require external evidence. |
| Dead-end leads / purpose | Exact read-only/write-only profiles, branches, no-local-result rungs and comments retained | External use, initial values, indirect references and incomplete bodies prevent automatic dead-code conclusions. Report these alternatives rather than asserting dead ends. |

R3 closes only after remaining source-supported rules and useful diagnostics
are investigated. A complete bounded scan or a passing suite does not close
these semantic questions. R4 then verifies final report organization, counts,
navigation, representative scale and a short review guide against the Phase 1
completion gate. Tyler has supplied automated runs, not classification feedback.

## Version and resource contracts

Assemblies1 remains the reusable default. Assemblies2 and communication1 are an
explicit combined opt-in at review/storage/work boundaries. Current CLI/work
select review30 / manifest33 / work48. Communication is derived and replayed
from authenticated source companions, not accepted as caller-supplied evidence.
The same sixteen private artifact names remain; new evidence is embedded in
`review.html`. Earlier public schemas and save/replay gates remain supported.

| Boundary | Limit / measured maximum |
|---|---|
| Assemblies2 private | Existing 64 MiB, 100,000 memberships, 20,000 groups, 500,000 visits |
| Communication1 private | 8 MiB; 250,000 derived records |
| Assembly summary2 | 8 KiB; maximum-width fixture 6,262 bytes |
| Communication summary1 | 4 KiB; closed names/statuses/counts only |
| Review30 | 456 MiB JSON / 488 MiB HTML |
| Work48 | 112 KiB; maximum-width envelope 107,787 bytes, 6,901 bytes headroom |

Work-machine Git transport remains manual. The script tests, saves private
artifacts, validates and locally commits the public feedback report. It does not
fetch, pull or push; the listener remains disabled and ignored.

## Validation and next run

The actual Bash launcher in an isolated checkout passed all 1,844 application
cases (two expected Windows skips) and 139 helpers, saved its sixteen private
artifacts, and made exactly one local feedback commit with zero Git network
calls. All inputs were invented fixtures plus already approved public history.
The first rehearsal also exposed fifteen stale current-version test expectations;
those were corrected before this passing full run.

End-to-end verification then caught a stale 64 KiB read limit in sample history:
the latest valid returned report is 68,150 bytes. The parser artifacts were
correct, but sample replay reported `history_error`. The repair aligns the
bounded pre-parse read with the current 112 KiB publication envelope, then
checks each validated report against its own original raw and canonical limits.
The 512-file, 32 MiB total-history and private reservation limits stay unchanged.
It never selects another sample on a history conflict or error.

The narrow repair passed 40 focused history/workflow/integration cases with one
expected Windows symlink skip, with processes and sockets blocked. One isolated
harness lacked an allowlisted fixture import; its affected case passed on a
properly loaded guarded retry. The unchanged full suite was not rerun after
this narrow repair. Two fresh final analyses restored the exact frozen sample
record without reselection and preserved all sixteen original launcher artifacts.
Both canonical saved runs and the CLI agree byte for byte; the checked-in demo
matches. All 25 prior summaries, 104 signal fields and fifteen non-review
artifacts match the baseline. All 55 original history files remain unchanged;
all 56 reports in the isolated checkout validate. The final 262 runtime/test
files match the verified source snapshot, including the replay repair.

Other completed focused checks (these populations overlap):

- 76 core cases covering supplemental identities, source qualification,
  resource limits and closed summary validation passed.
- All 46 communication/integration cases passed with process launches and
  network sockets blocked. The audited work-machine allowlist includes these
  three new modules; its import path also works in a fresh isolated selection.
- All 15 current-CLI compatibility cases and 21 focused runner cases passed.
  Historical defaults remain unchanged. Feedback validation accepts growing
  report history; a temporary 56th-report regression passed.
- Eighteen DOM cases passed, including supplemental sequence/file navigation,
  MSG occurrence/rung/object links, metadata text, old-report navigation and
  inert source text. Final browser checks followed a supplemental sequence
  address to its exact transition, with no console errors or warnings.
- Independent review has no open findings after fixes for source qualification,
  the inclusive suffix limit, direct metadata text and growing report history.

Two independently invented 4,606-rung capacity probes passed. The assembly
probe retained 36,848 memberships, 3,002 groups and two supplemental addresses
with no exclusions or truncation: 22,426,194 actual bytes and 25,554,209 reserved
bytes; 85,218 row plus 41,455 link visits. The separate communication probe
linked all 4,606 MSG occurrences to 256 controls/parameter records and 256 local
root candidates. Its private context was 3,026,574 bytes and its closed public
summary was 2,008 bytes; canonical replay passed. These are invented stress
fixtures, not measurements of the plant export.

The invented [fixture](../../fixtures/synthetic/residual_source_demo.L5X) and
[saved HTML demo](../../examples/residual-source-review-demo.html) exercise
supplemental addresses, alias/repeated MSG calls, missing/alternate parameters,
namespace gaps, produced/consumed metadata and an absent routine body.

The fixture SHA-256 is
`179bad082761ac98302e21ed348ac501766f55b99ab7466bf5200a0bd43298ae`.
The 638,722-byte demo SHA-256 is
`dfe6cf4206086e68c146fac15d1b452bb9d9ce5ec8a1e6c3432b7d6a7004af6a`.

The next ordinary work-PC run must confirm the expected exact-address delta,
MSG/parameter association cardinalities, endpoint dispositions, tag metadata,
resource bounds and unchanged prior summaries/sample envelope. It does not
require new plant excerpts or team classification feedback.
