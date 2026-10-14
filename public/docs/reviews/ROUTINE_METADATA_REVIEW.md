# Metadata observations for unique JSR candidates

Implemented 2026-10-14 on `feat/bounded-operand-example-pc`, continuing Phase 1.
This slice explains incomplete routine context without changing candidate links,
tag bindings, parameter roles or execution interpretation.

## Returned candidate checkpoint

Commit `7e15843` adds only
[work-check-20261014T221436Z-721c15dd.json](../../inspection/work-check-20261014T221436Z-721c15dd.json)
and has tested clean `3598710` as parent. Work8/reference10/source4 validates;
325 application cases (one Windows symlink skip) and 139 helpers pass. All 76
JSRs have a unique program-local declaration candidate, with 66 distinct targets.
There are no missing, ambiguous or unsupported candidates. Every candidate's
target context is not_analyzed. Earlier source, binding, catalog, alias/rack,
shape, flag, sample and diagnostic evidence is exactly unchanged. Analysis is
partial, private results are saved and the diagnostic sample is null.

The context counter establishes no self/main/fault matches and no explicit
Normal fallback, but cannot distinguish missing Type from another Type value.
The source parser retains all raw program attributes. Public scrubbed/synthetic
program envelopes omit Type, illustrating a possible cause without establishing
the private input's metadata.

## Primary evidence and conservative choice

Rockwell's [RM014D Import/Export manual](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf),
printed page 196, documents Program.Type choices EquipmentPhase, Sequence and
Normal, and MainRoutineName as the designated main routine. Its normal-program
example on printed page 204 omits Type. We found no explicit omitted-Type default
rule. Treating absence as Normal would therefore be an inference, and this slice
preserves unknown context instead. EquipmentSequence remains an unknown explicit
value; the documented value is Sequence. Program.Type and Routine.Type are
separate attributes with different meanings.

## Contract

The new routine_target_metadata object observes only unique parsed RLL JSR
candidate occurrences. Fixed metadata is analysis_scope=
parsed_rll_unique_jsr_candidate_metadata, program_type_semantics=not_analyzed and
target_execution=not_analyzed. The object contains total and three count groups:

- by_program_type: absent, empty, explicit_normal, explicit_equipment_phase,
  explicit_sequence and other_explicit.
- by_target_language: RLL, FBD, SFC, ST, missing and other.
- unclassified_context_by_program_type: the same six program-type buckets,
  restricted to target_context=not_analyzed.

Attribute values are compared exactly. Missing keys differ from present empty
strings; whitespace, case variants and unrecognized explicit values stay in
other_explicit/other. No raw unknown value is published. Counts are weighted by
call occurrences: two calls to the same target contribute two observations,
regardless of distinct-target count. Language records declaration metadata,
not body availability, parse success or executable behavior. Protected/partial
target envelopes keep their existing candidate status.

All counts are bounded integers with exact keys. Total equals unique_candidate;
each complete partition sums to total, and unclassified counts sum to existing
not_analyzed context. Each subset counter cannot exceed its program-type bucket;
explicit_normal cannot have unclassified context under the unchanged analyzer.
Known-language observations require a corresponding source routine envelope.
Ordinary contexts cannot exceed explicit-Normal observations; self contexts
cannot exceed RLL observations. Distinct targets cannot exceed the sum of each
language bucket's minimum call/declaration population (other declarations combine
withheld and Sequence). These checks reject impossible profiles even when all
individual partitions sum correctly.
Fixed validation errors contain no source strings. No per-call rows, names,
source identities, parameter values or raw Type labels leave this profile.

Public references advance to schema11 / reference-summary-11 while retaining
source-references-8. Reference10 remains frozen and rejects even an all-zero
metadata field; older versions retain their earlier keys and metadata. Work9 /
work-check-9 requires reference11. Work8/reference10 and prior pairings stay
readable. Private references5, inventory3, source aggregate4 and manifest2 keep
their exact structures and analyzer metadata. The profile is derived from the
captured inventory and canonical candidate rows, with no source reread.

Private text adds the same count section when captured inventory is supplied;
calls without inventory keep their existing API. Saved text/CLI output receives
the inventory. Private JSON keeps its canonical candidate result. Automatic
local report commits, manual pull/push, paths and sharing policy are unchanged.

## Next work-machine evidence

The next normal run should preserve all existing counts, including 76 unique
candidates, 66 distinct targets and 76 not_analyzed contexts. The new profile's
total should be 76. Program-type and target-language partitions remain unknown
until that report returns. Use those observations to choose a justified context
rule or focus further analysis on target bodies. Partial remains expected;
there is no need to repeat previous flag/math/bit/shape/candidate-only checks.
See [the normal run procedure](WORK_MACHINE_REFERENCES_RUN.md).

## Validation

Full development validation passes **431 cases with one existing Windows symlink
skip**. Eight new metadata cases and two public contract cases cover exact enums,
missing/empty values, repeated calls, protected/non-RLL envelopes, join failures,
private-contract independence, saved text/manifests, historical version10 and
privacy. The 152 related regression cases pass. Independent review passes 26
focused cases and reproduces rejection of all three partition-preserving
forgeries after their fixes. No remaining blockers were found.

All 14 stored work reports validate unchanged. All 67 relative Markdown links in
changed documentation resolve, and git diff --check passes.

The full development command excludes the ignored listener loader:

```bash
uv run --project python-parser --locked python -B - <<'PY'
from pathlib import Path
import sys, unittest
folder = Path.cwd() / 'python-parser/tests'
sys.path.insert(0, str(folder))
suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(p.stem)
    for p in sorted(folder.glob('test_*.py')) if p.stem != 'test_feedback_listener')
result = unittest.TextTestRunner().run(suite)
raise SystemExit(not result.wasSuccessful())
PY
```

Only invented fixtures and approved public reports are used; no project
confidential input or listener execution is needed.

An independent workflow agent runs the actual launcher twice in a disposable
clean checkout without remotes: an explicit invented source followed by its
remembered source. Each passes **335 application cases (one skip) and 139
helpers**. Its 13 JSRs produce ten unique candidate calls and nine distinct
targets. Profile totals are call-weighted: Normal4/absent2/empty1/Sequence3 and
RLL7/ST2/SFC1, with unknown-context absent1/empty1/Sequence3. Repeated calls,
known main/self context, protected and non-RLL target envelopes verify.

Reports use work9/reference11/source4; inventory/reference/manifest stay3/5/2
with analyzer8. Compared with clean baseline `7e15843` on the same fixture,
private inventory and reference JSON are identical; public summaries differ only
by the new profile, schema/exporter and tested revision. Saved and CLI text show
metadata with inventory; calls without inventory omit that section. CLI text/JSON
return expected partial exit3; JSON equals saved canonical private references.
Input, earlier runs and all manifest artifact hashes remain intact. Report-only
local commits cite their tested parents and leave a clean checkout. Git traces
contain no fetch/pull/push, and copied root code/test/config hashes match final
working bytes. No normal project confidential input or listener was used.
