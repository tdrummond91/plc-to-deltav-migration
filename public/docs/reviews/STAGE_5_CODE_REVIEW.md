# Stage 5 code review and bounded corrections

Reviewed 2026-10-09. Repository/Git remained read-only. No confidential files were read.

## Findings (line numbers refer to the pre-correction repository)

1. **R1 - sampling quota resets on interleaving (medium).**
   tools/l5x_inspect/dummy/selection.py:59-66 resets run_count whenever the
   next sibling has a different variant. Alternating 20 children with quota 2
   retained all 20; the desired per-parent policy retains four. The public
   report also contains 614 rungs of one local variant under a single parent.
   Corrected with a per-parent Counter keyed by variant. Mandatory anchors,
   their ancestors, complete selected rungs and relative source order remain.
2. **R2 - skeleton publication does not reject retained attribute values (medium).**
   tools/l5x_inspect/write_skeleton.py:124-126 feeds a count-only summary into
   verify_skeleton. summarize_xml.py:84-95 counts attribute names but ignores
   values. A mocked completed output with the expected structure and an
   unexpected nonblank Name value was accepted and published. Added the
   require_blank_attributes option to parse_structure and enabled it only for
   the completed skeleton. This fails before replacement, without printing
   the unexpected value. The actual public skeleton passed the stricter gate;
   this finding concerns a verification gap, not an observed data exposure.

## Changes and compatibility

- Minimized JSON schema_version and policy_version advance to 2.
- selection.per_parent_variant_limit replaces per_consecutive_variant_run.
- Earlier report schemas are unchanged. parse_structure defaults retain their
  previous behavior; strict attributes are opt-in for skeleton verification.
- One existing test expectation changes from A/B/A to A/B at quota 1; retained
  source order is preserved although every omitted interleaving run is not.
- Twelve new regression tests cover interleaved quotas, independent parents,
  mandatory/rare retention, complete rung descendants, provenance/accounting,
  both publication-failure positions, hardlink/alias guards and skeleton values.
- check_public_outputs.py is a project-specific, read-only integration checker
  for the four earlier public reports/skeleton and the generated XML/JSON pair.
  It is intentionally not a general validator for arbitrary controller projects.

## Verified results

The twelve new tests were first run against unchanged helpers: four expected
failures (two quota cases, the new version contract and skeleton publication).
After correction, all **130 tests passed in 0.182 seconds**. Tests use invented
in-memory inputs and mocked writes; Python -B prevents bytecode-cache writes.

A fresh audit of the existing public pair passed: 44,545 occurrence mappings,
2,397 rung shapes/metrics, 194 paths, 431 variant IDs, 19 ranked examples and
42 instruction labels. Counts, generated XML hash, mandatory presence, complete
selected rung subtrees, source order and replacement categories reconciled.
Variant checks reconcile IDs and counts; confidential source values were not
used to independently reconstruct variant identities.

Re-minimizing that existing public fixture **in memory** retained **7,303 of
44,545 elements and 276 of 2,397 rungs**, preserving all 194 paths, 431 variants,
19 rankings selected for that public input, 42 instruction labels and maxima
(depth 4, 49 direct legs, height 59, width 18). All 7,303 occurrence links and
retained rung trees were checked. No generated output files were written.
This is a public-fixture integration result, not a prediction of counts from
regenerating the original confidential source. Its ranking frequencies can
also differ from those of the original source.

## Review boundaries and remaining work

Reviewed XML preflight, skeleton serialization/verification, value profiling,
ladder tokenizer/branch measurements, selection, sanitization, coverage,
publication and existing tests. The outer ladder parser treats arguments as
opaque and does not validate instruction arity, instruction semantics or timing.
Its lane/width measures implement the documented structural definitions.

Arbitrary attribute/text values are replaced by the explicit policies; XML
names remain visible. Scope/member references, custom datatype definitions,
SFC graphs, numeric ranges/array dimensions and opaque/ST payloads are not
repaired for semantic coherence. No Studio import or runtime proof is claimed.

The two-file writer's partial-failure behavior is documented and now covered by
regression tests. XML may update while JSON remains old; the hash cross-check
rejects that mismatch. No transaction redesign was attempted in this slice.

Next: Tyler copies the bounded files, runs 130 tests, regenerates into
public/fixtures/minimized_review, and runs check_public_outputs.py. Inspect that
new public pair before replacing the policy-1 baseline or preparing another push.
Keep the source local. No new Git operation has been performed or verified here.
