# PID connections and observed member uses

## Confirmed work-machine return

Return `693e419` tested clean `f4f704d`. All 1,216 application cases passed
(two expected Windows symlink skips), as did 139 helpers. The private run saved
without a failure code. All 39 historical reports validate; fifteen preceding
summaries and the frozen diagnostic record are unchanged.

All 46 PID controls link, all 322 slots are accounted for (184 exact addresses,
138 literals), and all occurrences retain incoming condition context. The 515
address records include 333 direct members, 136 slot addresses and 46 whole
owners. Direct-member groups contain 46 setpoint, 139 mode, 88 scaling, 48 tuning,
eight limit and four process-value addresses. No member spelling, namespace or
binding gap was recorded in this companion's scope.

All 46 master operands are literals, so there are no explicit master candidates.
Zero alarm/status member accesses does not establish absence of process alarms.
The next analysis extends math/move records into branch legs; see
[calculation inputs and destinations](CALCULATION_PATHS_REVIEW.md).

## Returned evidence

Return `4018156` tested clean `4b04e28`. The work31 report passed 1,183
application cases with two expected Windows symlink skips, plus all 139 helper
cases. The private run saved with no failure code. All 38 historical reports
validate. Thirteen preceding summaries match after removing only tool revision;
the six diagnostic examples and eight-unit reservation replay exactly.

The custom AOI has one declared RLL body, two parsed rungs, three classified
calculation instructions, six operands and nine expression reads. Six parameters
and two local tags have no recorded context gaps. The single call resolves to a
whole-root instance with a matching declared datatype. Complete body context
does not mean simulated execution or confirmed engineering purpose.

The unmatched SFR target has one exact address match in another chart in the
same program. All thirteen peer contents were eligible; none were excluded.
The selected chart still has no matching step. This is a diagnostic relationship,
not permission to retarget the instruction or proof of an erroneous source.

## Why PID connections are next

The source already has 46 recognized PID occurrences, 46 associated backing
declarations and 2,346 catalogued member headers without header gaps. Earlier
reports exposed these separately from their cross-rung uses. This companion
assembles the existing evidence into navigable PID dossiers, preserving the
underlying access and condition models.

The [Rockwell PID operand reference](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/special-instructions/proportional-integral-derivative--pid-.html)
defines the seven instruction slots and identifies SP as a structure member.
Its [configuration guidance](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/special-instructions/proportional-integral-derivative--pid-/using-pid-instructions.html)
documents separate cascade and mode configuration. Consequently, a master-slot
reference supplies an explicit source relationship but cannot establish active
cascade control by itself.

## Evidence and interpretation boundaries

Each PID occurrence links its seven operand slots to existing exact-address
groups where available. Those shared groups retain explicit reads, writes,
read/write uses, unknown-role operands and CPT expression reads separately.
Same-address use does not establish runtime value propagation, a unique writer,
physical wiring, scheduling or final values. A source with no captured uses is
not declared unused or disconnected.

Direct PID member addresses are grouped using the existing field catalog:
setpoint, mode, alarms, limits, tuning, scaling and other recorded groups.
Captured member headers remain separate from external ladder accesses. Multiple
representations and duplicate headers remain visible. Whole-root uses do not
become individual-member writes; nested, indexed and unknown member spellings
retain their limits. The external PV operand and the PID's internal PV member
remain different source addresses.

Master-slot candidates preserve repeated invocations, unavailable candidates,
self references, unsupported suffixes and declaration gaps. Incoming condition
links reuse the existing condition node; the PID transfer itself remains opaque.
These links do not claim a complete execution or output-write guard. Alarm-field
consumers are useful review evidence but do not prove a plant alarm, warning,
shutdown consequence or priority.

Existing access4, conditions3, PID1, PID member1 and relationship1 outputs remain
unchanged. The new companion uses snapshot-bound IDs and does not assign approved
loop identities, select effective stored values or start DeltaV conversion.

## Report and work-machine workflow

The existing PID evidence pages gain connection and member-use navigation,
including related source rungs and incoming conditions. The independently
invented [fixture](../../fixtures/synthetic/pid_connections_demo.L5X) exercises
shared storage, aliases, master-reference gaps, scope shadowing and many setpoint
writes. Its [HTML example](../../examples/pid-connections-demo.html) is safe to
open without a plant export; it is not controller-ready logic.

The normal work-machine run measures these connections on the private export:

```bash
git pull
bash ./run-work-check.sh
git push
```

The runner commits the validated aggregate report locally. All Git transport is
manual, and the listener remains disabled. No additional source samples or
engineering/team review are requested for this checkpoint. The returned counts
will guide the next source-analysis slice.

## Contracts and validation

PID connections1 is bounded to 8 MiB and 250,000 records; its public count-only
summary has a 4 KiB limit. Review15 reserves 208 MiB for JSON and 240 MiB for
HTML. Manifest18 still hashes sixteen artifacts because this companion is
embedded in the review payload. Work32 adds the summary without changing any
older analysis version or the diagnostic sample request.

The conservative work32 envelope is 66,728 bytes, exceeding the prior 65,536-byte
limit by 1,192 bytes. Work32 therefore permits 80 KiB; work28-31 retain 64 KiB.
The additional allowance is for fixed counters. Targeted examples retain their
existing 16 KiB limit and frozen selection. Work31 and work32 render compact
JSON, while earlier report formatting remains unchanged.

Validation used the independently invented fixture and isolated copies of the
tracked tree; the development machine's confidential files were not inspected.

- The full discovery run executed 1,517 cases, with two expected Windows
  symlink skips. Its two failures came from one obsolete analyzer call-count
  assertion, directly and again inside the process/socket guard. The assertion
  was replaced with checks for one save handoff, original captured bytes and
  the exact member result. Source capture, stored evidence and sanitized failure
  coverage remain intact; an independent reviewer checked the correction.
  Both originally failing tests then passed in a fresh focused run, including
  the process/socket guard's complete application and helper selections.
- A fresh actual Bash launcher run passed all 1,216 selected application cases
  (the same two skips) and all 139 helpers. It saved sixteen hashed artifacts
  and committed one 38,104-byte aggregate locally. Instrumentation recorded
  zero Git transport calls with an intentionally unavailable origin.
- The runner, a second analysis process and the direct CLI produced identical
  bytes for all sixteen artifacts. The CLI's exit code 3 correctly denotes the
  synthetic fixture's partial analysis. The published HTML example matches
  that CLI output exactly.
- Against baseline `4018156`, all fifteen earlier non-HTML artifacts are byte
  identical. Fifteen preceding summaries match after normalizing only the
  revision. All 38 historical reports remain unchanged and all 39 reports,
  including the isolated synthetic return, validate. The six diagnostic
  examples and eight-unit reservation remain frozen.
- Browser checks covered source and incoming-condition navigation, shared and
  self master candidates, scope isolation, member categories, separate
  `.SP`/`.sp` spellings, and setpoint uses paginated as 50 plus 7. Source markup
  displays literally, no injected scripts or console errors appeared, and
  the report had no horizontal overflow at a 1,009-pixel viewport.
- Independent core and workflow reviews found no remaining blockers. Core
  tests include malformed signatures, aliases, namespace boundaries, repeated
  invocations, summary count conservation and deterministic ordering; three
  fresh hash-seed processes produced identical companion bytes. JavaScript
  syntax and Git whitespace checks also passed.
