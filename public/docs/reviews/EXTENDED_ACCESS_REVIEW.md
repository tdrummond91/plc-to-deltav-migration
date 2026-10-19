# Counter, message, system-value and SFC-reset operand access

## Confirmed work-machine return

Returned `cbb2965` tests clean `456786a`. All 695 application cases pass (one
expected Windows skip), as do 139 helpers. All 175 projected instructions and
336 operand slots classified: three counters, 27 messages, five system-value
reads and 140 named-step resets. All 175 data operands bound, with zero new
binding gaps. Unsupported instructions fell from 348 to 173; unknown source
roles fell from 931 to 595. The 321 existing binding gaps remain unchanged.
Six other summaries match after removing only tool_revision; this does not
prove source-byte identity. All 27 historical reports validate. The work20
return is 31,787 bytes. [CPT access](CPT_ACCESS_REVIEW.md) is the next slice.

## Confirmed starting point

Returned `760448e` tests clean `36c0ff4`. Its 668 application cases pass with one
expected Windows symlink skip, and all 139 helpers pass. All 45 CPT expressions
parse into 592 nodes; all 132 captured reference uses and 45 destinations bind
to roots. Four retained functions use SQR. All expression errors are zero.
Six previous summaries match after removing only tool_revision. This does not
prove source-byte identity or engineering equivalence. All 26 historical work
reports validate, and the latest occupies 31,380 bytes.

The remaining access2 gaps include 348 unsupported instructions and 931 unknown
operand roles. Among them are 140 SFR, 27 MSG, five GSV and three CTU occurrences.
This slice covers their documented explicit operand roles, plus the related CTD
and SSV forms. Subject to actual signatures and operand forms, those 175 source
occurrences could classify 336 additional operand slots. These are projections,
not confirmed work-machine results. Binding gaps may remain after classification.

## Operand contract and evidence

| Instructions | Possible explicit roles | Scope |
|---|---|---|
| CTU / CTD | Counter read/write; two non-data pseudo-fields | Preset/accumulator text is not a runtime reference or evaluated initialization. |
| MSG | Message-control structure read/write | Payloads, communication paths and remote destinations remain unmodeled. |
| GSV | Three non-data selectors; destination write | Class, instance and attribute are not tag addresses. |
| SSV | Three non-data selectors; source read | System-object changes and transfer ranges are not expanded. |
| SFR | Routine selector non-data; step possible write | Exact trimmed `0` instead selects the initial step and is non-data. |

Rockwell documents the counter structure and immediate fields for
[CTU](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/timer-and-counter-instructions/count-up--ctu-.html)
and [CTD](https://www.rockwellautomation.com/en-il/docs/studio-5000-logix-designer/38-01/contents-ditamap/instruction-set/timer-and-counter-instructions/count-down--ctd-.html).
The lexical pseudo-field grammar matches the existing timer treatment: `?` or
signed decimal/radix integer text, without conversion, width/range checks or an
initialization model. A malformed counter pseudo-field leaves all its slots
unknown. Timer counts remain a separate population.

The [MSG reference](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/input-output-instructions/message--msg-.html)
describes the control structure and state/configuration members. The new role
covers that explicit structure only. The
[GSV/SSV reference](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/input-output-instructions/get-system-value--gsv--and-set-system-value--ssv-.html)
defines the three selectors and final data operand. An empty instance selector
is accepted; empty class, attribute or data operands remain gaps. Selector
existence and attribute compatibility are not validated.

The [SFR reference](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/program-control-instructions/reset-sfc--sfr-.html)
defines the routine, step and zero sentinel. Classifying the named step as a
possible write is a bounded interpretation of the Reset member update described
in the [Step reference](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/sfc-instructions/step.html).
Other actions/steps, routine execution, step membership and SFC_STEP type are
not validated. Nonzero or differently spelled numeric targets are not promoted
to initial-step selectors; they retain an unbound write gap. The field name
`sfc_reset_step` counts non-sentinel operand slots, not validated chart steps.

These roles remain potential explicit access. They do not establish execution,
dependencies, data types, member validity, array bounds or suffix overlap.

## Versioned binding evidence

Access3 / instruction-access-3 keeps operand IDs shared with reference6 but owns
new bindings for its documented slots. Existing reference6/analyzer9 evidence
and reference-summary12/source-summary4 remain unchanged. The existing resolver
handles scope, aliases and address suffixes. Class/routine/attribute selectors
never become tag references even when an identically named tag exists.

Each access3 operand records binding_origin (`source_references`,
`access_resolver` or `access_non_data`), source_reference_status, binding_reason
and alias_chain alongside its effective binding status, symbol, target and
suffix. Canonical replay derives this evidence from authenticated source data.
Explicit `schema_version=2` replay preserves access2 evidence byte for byte.
Access3 checks cumulative retained suffix and alias-chain expansion against an
8,000,000-character budget before appending each operand, including inherited
metadata. The independent review identified and corrected late-only checking;
new regressions verify rejection before remaining resolutions or serialization.
The existing 32 MiB private access and 32 KiB public report limits remain.

Access summary3 adds fixed classified-family counts under extended_instructions,
counter_pseudo_operands_by_kind, counter_invalid_forms and
extended_bound_operands. It subtracts the documented family signatures before
checking ordinary-role capacity. Fixed counters contain no source-controlled
names, paths, values or rung text. Older access summaries1/2 retain their exact
closed contracts.

Work20 requires access summary3 and reconciles added classifications and bound
operands with the unchanged reference population and source opcode capacities.
Work1-19 retain their prior contracts. Review6/manifest9 still saves thirteen
hashed artifacts and records actual nested versions. The report displays the
original reference results separately from access-owned bindings; declaration
reverse links use the effective access targets, suffixes and alias chains.

## Work-machine handoff

From the repository root on `feat/bounded-operand-example-pc`:

```bash
git pull
bash ./run-work-check.sh
git push
```

The runner tests the clean checked-out code, saves private outputs and makes
only a local feedback-report commit. Git synchronization remains manual and
the listener stays disabled. Return only the generated feedback; engineering
and appearance review remain optional. Phase 1 continues. Editable corrections,
PCSD and FHX remain later phases.

The next analysis should check classified-family counts, invalid counter forms,
new binding counts and remaining gaps, without assuming all 175 occurrences
match. PID and CPT companions already expose evidence; an expression-aware
access index and documented conditional PID roles remain useful later slices.

## Validation

The final development suite passed **796 cases** in 100.783 seconds with one
expected Windows symlink-capability skip. The ignored listener loader was
excluded before import. The independent reviewer passed 32 focused extended
core, summary, workflow and UI cases and reported no remaining blockers.
Core cases include 289 mixed signature combinations, canonical provenance,
ASCII opcode variants, scope/AOI/alias handling, malformed pseudo-fields,
zero versus nonzero SFR targets, empty system instances, size limits and
incremental expansion rejection. Five UI behavior tests use Node when present;
they stay outside the Python-only work-machine application allowlist.

Two actual isolated Bash runs, explicit then remembered source, each passed
**695 application cases** (one expected skip) and **139 helpers**. Both saved
work20/review6/manifest9 with access3, verified thirteen artifact hashes, and
created one report-only local commit. Git traces show no network commands.
Both public reports are 30,621 bytes. All 26 historical reports remain unchanged
and validate alongside the two new reports. The actual returned work19 envelope
with zero-valued new fields is 31,781 bytes, leaving 987 bytes under 32 KiB;
that measurement establishes size headroom, not future real-source coverage.

Fresh CLI generation exits 3 for the intentionally partial fixture and matches
all thirteen artifacts byte for byte. Eleven unchanged evidence artifacts and
six revision-normalized summaries match baseline `760448e` on the same invented
input. Explicit access2 replay reproduces baseline access.json bytes. All 104
runtime, asset and test files in the isolated checkout match the final working
files. Source inputs, earlier runs and real HEAD were preserved; temporary
checkouts finish clean. A deliberately larger fresh-binding stress input with
4,606 rungs, 17,874 instructions, 24,583 operands and 6,000 invented declarations
renders access3 in 29,609,263 bytes, within the unchanged 32 MiB limit. It does
not reproduce plant topology or establish every real input will fit.

Chrome verifies the new family counts, alias-backed GSV binding with resolved
suffix `[2]`, declaration-to-rung reverse navigation, separately labeled original
reference findings, blank/non-data selector handling and the SFR zero sentinel.
Script-like source stays inert; no page JavaScript errors occur. Historical
access2 reports retain their old scope and omit new family counters. The
[independently invented fixture](../../fixtures/synthetic/extended_access_review_demo.L5X)
has 56 rungs, deliberate malformed forms and selector/tag name collisions.
The regenerated [HTML demonstration](../../examples/engineering-review-demo.html)
is 723,905 bytes. Earlier fixture files remain unchanged. The temporary QA tab
and loopback server were closed after validation.
