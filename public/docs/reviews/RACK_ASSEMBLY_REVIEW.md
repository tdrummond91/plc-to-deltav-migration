# C13 return and cross-rung rack associations

C14 returned as `adc5475`, testing clean `a53ca67`. Its full suites pass and
the downstream grouping counts reconcile. See the
[final readiness assessment](PHASE_1_READINESS_REVIEW.md) for the returned
evidence, gate closure and review questions. The implementation record below
is preserved as historical evidence.

## Returned evidence, 2026-10-19

Return `c67be2e` contains
[`work-check-20261019T163607Z-70b315df.json`](../../inspection/work-check-20261019T163607Z-70b315df.json),
testing clean `eebe469` under work52. All 2,074 application cases pass with two
expected skips; all 139 helpers pass. The private run saved with no failure
code. Analysis remains partial because its source and interpretation limits
remain visible. All 60 historical work reports pass their own raw-size limits,
closed validation and byte-exact canonical replay. This report is 88,697 bytes
within 144 KiB. All 28 preceding summary families and the complete frozen sample
envelope are unchanged after excluding revision metadata. No new sample was
requested; six charged examples/eight reserved units of forty remain frozen.

Rack source correspondence1 is complete: 15 declarations (11 input/four
output), 94 addresses (78 input/16 output), 319 RLL uses and four SFC uses all
associate, with no qualification gaps. Eleven roots are used. The 323 uses
comprise 307 reads and 16 writes; 303 are ladder predicates and 16 are output
targets. The two SFC addresses also occur in RLL. This validates source
correspondence, not physical I/O, active configuration or runtime behavior.

C13 took 1,077,512 ms (17m 58s), versus C12's 980,618 ms (16m 21s):
96,894 ms longer. Application tests took 407,907 ms; helpers 312 ms; analysis
213,570 ms; private save 240,773 ms; summary construction 214,268 ms; sample
replay 187 ms. Tests account for 48,521 ms of the increase. These two runs do
not isolate feature cost or establish a continuing runtime trend.

## Independent readiness audit

The report audit confirms that every captured rung has a base group: 4,332
identified, 208 partial and 66 unidentified; none unparsed. Existing C13
navigation, source links, saved 4,606-rung synthetic scale checks and dark-screen
presentation are suitable for review. The semantic audit found two concrete
implementation gaps before the final gate can close:

1. The independent rack companion is not consumed by assemblies2. Its 303
   predicates, 16 output targets and four SFC references remain outside the
   cross-rung groups despite their now-qualified backing identities. The 16
   skipped targets also suppress 41 already-exact guard-input links.
2. The guard-dependency assembly loop counts literal and system-flag inputs as
   binding failures, even though the direct-condition loop correctly treats
   them as non-address values. Of 2,136 signal exclusions, 303 are direct
   reads, 16 are targets and 1,817 are guard-dependency occurrences. The latter
   contains 1,471-1,474 legitimate non-address inputs and 343-346 actual
   unresolved reads. The exact split needs the locally derived rows; aggregate
   totals cannot determine it. Do not claim that all 2,136 are recovered links.

The tracker therefore records thirteen completed cycles and explicitly extends
the central total to fourteen. C14 combines these corrections and their final
report verification. No additional raw plant source is needed to implement it.

Other residuals are investigated: two dynamic MOV destinations and one file
selector need runtime values; one RLL body is absent; one SFR target does not
match its requested chart. Call serialization/outgoing-condition semantics and
the GSV question-mark instance need specific vendor/exporter evidence, as
recorded in the [control assessment](ROUTINE_CALL_SHAPE_REVIEW.md) and
[GSV assessment](CONDITION_TRANSFER_REVIEW.md). Do not substitute a peer-chart
step or guessed Boolean transfer. SBR contributes the sole opaque coil guard.

Base unsupported signature counts reconcile through specialist providers:
128 instructions = 46 PID + 78 JSR/SBR/RET + three file instructions + one AOI;
505 unknown slots = 322 PID + 164 call/boundary + 18 file + one AOI. These are
source signature reconciliations, not proof of parameter effects. The 82 base
unknown blocks are a different population and must not be relabeled as 128.

## C14 source association contract

Assemblies3 consumes the canonically replayed rack companion. Qualified
occurrences project to the same backing declaration and exact suffix identity
used by direct-address groups. Every added membership retains the rack source
use IDs supporting it; guard links can cite both their input and output proof.
Unsupported or unqualified occurrences retain their gaps. Whole structures,
members and bits remain separate; no transitive execution or physical wiring
is inferred. Original bindings, signal, condition and SFC models stay unchanged.

Literal and system-flag guard inputs are counted separately from address
exclusions. Source groups expose forward and reverse relationships, including
outputs whose guard reads the selected address. Reverse links retain the
original output and input evidence; they do not prove necessary inputs or a
shutdown. Rack dossiers link into the groups and group rows link back to the
exact occurrence qualification. Display traversal is explicitly bounded.

Work53/review35/manifest38 select assemblies3 only with the full rack bundle.
Historical defaults and assemblies1/2 stay replayable. Public summaries contain
closed counters, not names or values. The work-machine script still creates a
local report commit and performs no Git network operation.

## Validation and next return

Focused C14 validation passes: 20 new core/summary tests, 42 historical
core/summary tests, nine new workflow tests, three current work-entry checks,
six review-workflow checks and the allowlist check. All 60 historical public
reports validate and replay exactly. The new save tests verify all sixteen
artifact sizes and hashes and preserve earlier saved bytes. Canonical replay
rejects altered occurrence proof; schema/size/publication tests reject invalid
version pairings and limits.

Twenty-seven development-only UI cases pass, including rack/direct/SFC joins,
reverse guard navigation, rejected aliases, original gap links, known-value
counts, historical reports, display truncation and inert source text. These
checks caught an existing guard-input navigation bug: instruction IDs were
looked up in an output-ID map. The explicit instruction index now opens the
correct output dossier. GSV question-mark follow-up wording now names the
specific external evidence boundary.

Independent review found and verified fixes for reversed role labels and an
aggregate contradiction that allowed a rack-backed guard count without a
qualified rack predicate/target. The new negative cases also reject unrelated
raw rack reads as guard proof. The reviewer checked the bound independently
over 159 successive membership/visit cutoffs; no blocking issue remains.

The previously saved, independently invented 4,606-rung report was verified
against its manifest hash, then reprojected through assemblies3 and rendered as
review35. All 36 other top-level payload fields remain unchanged. Its complete
scan retains 48,741 memberships and 7,939 groups, reserves 39,614,173 bytes of
64 MiB, and uses 161,006 of 500,000 visits. HTML is 170,164,809 bytes, below
504 MiB. This isolates the changed grouping/rendering stage; the earlier full
pipeline scale run and new sixteen-artifact save tests cover the surrounding
pipeline. Chrome opened this artifact and paged to 51-100 of 7,939 groups
(page 2 of 159), with no console errors.

The refreshed control demonstration and new
[five-rung rack demonstration](../../examples/rack-assemblies-review-demo.html)
use only invented source. Chrome verifies forward/reverse links, corrected
anchor/output roles, rack occurrence qualification and the retained unbound
original output alongside the new group. The dark report layout is readable;
no console errors appeared. Temporary browser/server resources were closed.

The complete guarded application selection ran 2,103 cases in 910.657 seconds,
with two expected skips, zero errors and fifteen failures from current-CLI
expectations loaded before their corrections. Its exact failed-test IDs match
the fifteen corrected cases that passed a separate guarded rerun; no additional
failure remains. This is full-selection coverage plus focused reruns, not a
single clean full-suite run. The separately guarded 139 helper cases pass, as
do 68 development workflow/driver cases. Application, corrected-case and helper
checks deny process launches and socket access. Production code was unchanged
during the complete run; only stale current-CLI test expectations changed.

The next return must preserve all prior summaries except assemblies, preserve
the frozen sample envelope, account for qualified RLL/SFC joins and known
non-address inputs, and report complete bounded grouping scans. Inspect any
remaining signal/SFC exclusion individually by its fixed reason before closing
R3. Final team readiness remains conditional on this audit and the completion
gates in the [tracker](../planning/PRE_TEAM_REVIEW_TRACKER.md).
