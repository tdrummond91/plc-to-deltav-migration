# C12 return and rack source mapping

C13 has now returned and validates this bundle. See the
[C13 audit and C14 rack association work](RACK_ASSEMBLY_REVIEW.md) for current
status. The C12/C13 implementation and validation record below is historical.

## Returned evidence, 2026-10-19

Return `a5ccae8` contains `work-check-20261019T153207Z-5ce9d78c.json`,
testing clean `a58f3c0` under work51. All 2,045 application cases (two expected
skips) and 139 helper cases pass. The private run was saved; analysis remains
partial with no failure code. All 59 historical reports validate against their
own raw-size limits and replay byte-for-byte. The current report is 86,189 bytes
within 144 KiB. The complete targeted-sample envelope is unchanged; no new raw
source sample is needed for this investigation.

Only condition, execution and rack summary content changes after recursively
excluding tool revision metadata. Source populations remain 4,606 rungs,
17,874 instructions and 24,583 operands. All 104 signal coverage fields,
46 PID incoming condition links, 54,201 assembly memberships and 7,486 groups
remain unchanged. Assembly providers remain two complete and four partial.

| Investigation | C12 evidence | Consequence |
|---|---|---|
| AOI condition transfer | One modeled, zero body qualification gaps | The metadata qualification repair is validated |
| GSV instance syntax | Four modeled; one question-mark placeholder rejected | Investigate the precise placeholder semantics before extending the rule |
| Routine interfaces | All 76 calls associated: 62 RLL and 14 SFC | All 14 qualified SFC contents have no captured Subroutine/Return declaration; argument pairing and runtime transfer remain separate questions |
| Rack declarations | All 15 have the exact 1756-EN2T family and structured Slot layout | Investigate a supported source-address correspondence rule |
| Rack representations | 11 inputs have one Decorated representation; four outputs have Decorated plus L5K | A second format does not make the unique Decorated source shape ambiguous |
| Rack native headers | All 15 root/array/selected-slot headers agree in series and direction | Qualified scalar Data/Fault fields are available for every selected slot |

Opaque transfers fall from 220 to 219 and pass-through nodes rise from 2,824
to 2,825; total condition nodes stay 32,570. SFC joins increase boundary
contents from 54 to 68, distinct associated contents from 52 to 66 and
evidence links from 764 to 806. No remaining call targets have an unsupported
language in this exported population.

C12 took 980,618 ms (16m 21s), up 14,365 ms from C11. Application tests took
359,386 ms; analysis 197,168 ms; private save 225,249 ms; summary construction
197,805 ms; helpers 311 ms; sample replay 182 ms. This is a measured comparison,
not evidence of a general growth trend.

## C13 source correspondence

The opt-in rack companion requires the prior residual diagnostics. It creates
separate source declaration, address and occurrence records, authenticated
against the original snapshot. For qualified Vendor 1 / catalog 1756-EN2T rack
connections, the exported rack name projects to the uniquely bound adapter
input/output tag's captured `.Slot[n]` structure. Whole slots, DINT Data/input
Fault fields and static bits 0-31 are supported. Every alias declaration,
source envelope, scope and selected member must qualify. Unrecognized suffixes,
ambiguous names/backing identities, protection and unsupported shapes remain
explicit gaps. RLL and SFC uses retain their original evidence links.

The rule follows rack-object source addressing described in Rockwell's
[Logix design reference, publication 1756-RM094N, printed page 101](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm094_-en-p.pdf)
and the RackConnection / InAliasTag / OutAliasTag export description in the
[import/export reference, publication 1756-RM014D, printed page 87](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf).
The generic captured module-type grammar establishes series/direction and Slot
structure consistency; it is not certification of an EN2T product profile or
import validity. Decorated scalar envelopes must have the fields required by
the existing capture model. Scalar values are neither interpreted nor copied
into the correspondence summary.

The overlay deliberately preserves the original reference/access/condition and
assembly models. An address may qualify while a particular alias use does not.
Source correspondence does not establish physical wiring, process service,
effective configuration, live values, execution order or behavioral equivalence.

Review34 / manifest37 embed the companion without adding artifact files; there
are still sixteen. The private companion allows 8 MiB and its closed public
summary 8 KiB. Review JSON/HTML limits are 472/504 MiB. Work52 remains 144 KiB.
Exact nested versions/revisions and population checks reconcile declarations,
old rack dispositions, eligible captured layouts, RLL candidates, SFC gaps and
associated roles. Historical contracts and frozen samples remain unchanged.

## Report and residual investigation

Rack source addresses now offer declaration, address and occurrence views with
search, filters and source dossiers. Links from binding gaps and SFC references
retain the original diagnostic. SFR rows now expose their existing target
context. Residual-count navigation opens precisely the counted population;
supported AOI bodies no longer appear as unexplained missing routine bodies.

The [GSV investigation](CONDITION_TRANSFER_REVIEW.md#c13-returned-gsv-marker-remains-unresolved-2026-10-19)
records why the remaining question mark is not silently interpreted as a blank
instance. The exported placeholder is source evidence, not proof of an invalid
controller program. That GSV does not cause the one opaque output guard.

The 218 other opaque transfers are 140 SFR, 76 JSR, one SBR and one RET.
Target/body links do not establish a Boolean outgoing equation or runtime call
sequence. The reviewed Logix call documentation explains parameter direction
and routine transfer, while the import/export reference's RLL and ST neutral
text signatures differ. A numeric RLL field is not sufficient proof of an
InputCount contract; SLC/PLC-5 calling conventions must not be substituted.
One remaining SBR-related output guard therefore stays unresolved. The
[dated control assessment](ROUTINE_CALL_SHAPE_REVIEW.md#current-control-transfer-assessment-2026-10-19)
now records each population's supported operation, unresolved alternatives and
precise missing vendor/exporter evidence. Dossiers explain enabled calls,
normal-return continuation, input reception, enabled returns and chart resets
without computing runtime paths or erasing gaps. Another unchanged parser run
cannot establish the exporter grammar or the missing Boolean equations.

## Validation

- Full audited application selection: **2,074 cases pass, two expected skips**,
  with subprocess creation, socket creation and connections denied. All **139
  helper cases** pass under the same guards. The separate current workflow and
  test-driver checks pass **68 cases**; guarded application/helper coverage
  supplies the two deliberately excluded full-suite wrapper checks.
- The early wrapper process loaded a superseded missing-value test while the
  provider review was still finishing. It failed that same case in each nested
  selection. The final test distinguishes uninterpreted values from malformed
  missing-Value envelopes; the complete final 2,074-case run passes it. No
  production validation was relaxed to accept missing scalar envelopes.
- All **59 historical public reports** pass their own raw/canonical limits,
  closed validation and exact byte replay. Integration tests cover the full
  frozen sample envelope, work52 publication, private size refusal, legacy
  gates and coherent-but-foreign aggregate substitutions.
- The rack provider/summary has **23 focused cases**; the earlier frozen rack
  diagnostic suite has **33**. Independent review found and verified fixes for
  three impossible aggregate combinations, then strengthened cross-provider
  conservation. No remaining provider or integration finding was reported.
- **35 DOM checks** cover rack navigation, exact residual cohorts, engineering
  views and SFC joins. All six rack cases passed again after final label/search
  and wording refinements. **Eight final control UI checks** cover documented
  operations, missing targets/selectors, historical compatibility and payload
  immutability. Independent review of these additions found no issue.
- A fully invented **4,606-rung** export completes production analysis, save,
  summary and sample replay. All sixteen saved artifact sizes/hashes and source
  bytes verify under manifest37/review34. HTML is **168,934,035 bytes**, below
  504 MiB; condition capture retains 30,447 nodes / 4,546 outputs. There are
  48,733 assembly memberships / 7,937 groups. The added rack overlay retains
  two qualified roots, two addresses, three RLL uses and two SFC uses.
- Synthetic timings: analysis 263,332 ms, save 305,133 ms, summaries 256,005 ms,
  sample replay 37,193 ms. Other checks ran concurrently; these timings are
  capacity evidence, not an isolated benchmark or work-PC runtime prediction.
- Chrome loaded the large saved report, paged to **page 2 of 93**, and followed
  a seven-rung residual count into **exactly seven of 4,606 rungs**. No report
  console errors appeared. Initial whole-page automation exceeded its 64 MiB
  transport limit; inspecting rendered content only succeeded without changing
  the report. The small current demo verifies rack/SFC source links, original
  unresolved bindings, adapter symbol labels and SBR's retained condition gap.
- Screen styling now uses charcoal/midnight, teal/cyan and restrained violet,
  with a light print palette. Minimum checked text contrast is **6.10:1 screen**
  and **4.68:1 print**. Actual dark rendering was inspected in Chrome. Existing
  layout and navigation sizes remain unchanged.

The [synthetic demonstration](../../examples/control-interpretation-review-demo.html)
is refreshed to review34. Its nineteen invented rungs combine the residual
control fixture (including matched/missing calls and reset targets) with the
independent rack fixture. It contains no plant-derived configuration. Final
control wording was checked in this saved demo after the large pipeline run;
these report-only changes do not alter the scale payload's analysis.

## Next work-machine return

Run the ordinary manual pull, script and push sequence. C13 must reconcile all
fifteen declarations, 319 RLL candidate uses, 94 addresses and eleven used roots,
plus the four SFC binding gaps. Review all non-associated dispositions before
requesting any further bounded evidence. Preserve the original summaries,
104 signal fields, 46 PID incoming links, assembly populations and complete
six-example/eight-reserved-unit sample envelope. No new raw sample is requested.

The [completion tracker](../planning/PRE_TEAM_REVIEW_TRACKER.md) retains twelve
completed cycles, one remaining centrally and a one-to-two planning range.
R3/R4 stay open until source-rule investigation, saved/export evidence and
presentation checks are individually satisfied. This bundle alone does not
announce team-review readiness.
