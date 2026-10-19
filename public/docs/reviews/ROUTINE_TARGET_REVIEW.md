# JSR first-field declared routine candidates

Implemented 2026-10-14 on `feat/bounded-operand-example-pc`. This is Phase 1
source understanding; editable engineering records, PCSD and FHX are later work.

## Returned shape checkpoint

Report `0a2610f`, [work-check-20261014T212041Z-8cac2026.json](../../inspection/work-check-20261014T212041Z-8cac2026.json),
tests clean `9c56b50` with 308 application cases (one Windows symlink skip) and
139 helpers passing. Its work7/reference9/source4 contracts validate. JSR has
76 occurrences and 163 fields: 65 two-field calls with exact trimmed second text
`0`, and 11 three-field calls whose second text differs. SBR has one occurrence
with one field; RET has one occurrence with no fields. All earlier source,
binding, catalog, alias, rack, flag and diagnostic counters are unchanged.
The report-only commit has the tested revision as parent. These counts establish
field shapes, not parameter roles, export byte identity or valid execution.

## Evidence and decision

Both RLL-neutral and structured-text JSR layouts identify the first field as a
routine name in Rockwell's [L5X reference, RM014D](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf)
(printed pages 215 and 294); their later parameter layouts differ. This slice
uses only that common first field and leaves later fields uninterpreted.
[Program/routine guidance](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/studio-5000-logix-designer/controller-organizer/use-the-controller-organizer/use-tasks--programs--and-routines.html)
restricts routine access to the owning program. Routine lookup therefore uses a
separate program-local namespace, with no tag or cross-program fallback.

[Routine guidance](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/studio-5000-logix-designer/tasks--programs--and-routines/routines.html)
identifies main, current and phase-state restrictions; [JSR help](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/program-control-instructions/jump-to-subroutine--jsr---subroutine--sbr---and-re.html)
also describes fault-routine behavior. These motivate separate context labels,
not execution or call-validity conclusions. Explicit caller identity and
MainRoutineName/FaultRoutineName attributes supply context; routine spelling
alone does not. Phase-state designation remains unmodeled.

[AOI programming, PM010N](https://literature.rockwellautomation.com/idc/groups/literature/documents/pm/1756-pm010_-en-p.pdf)
(printed pages 21-24) excludes AOI JSR use and permits several routine languages
for program subroutines. AOI callers are unsupported_context. Declared ST/FBD/SFC
or protected target envelopes can remain candidates even when their bodies are
not modeled; a declaration match does not prove body availability or validity.

## Private contract and lookup

Private references are schema5 / source-references-8. The new routine_targets
object has fixed analysis_scope=parsed_rll_jsr_first_field_candidates,
parameter_roles=not_analyzed and call_validation=not_analyzed, plus occurrences.
Each parsed RLL ASCII case-insensitive JSR contributes one occurrence, including
zero-field calls. Rows retain instruction/rung/caller/program IDs, the captured
first argument, status, candidate count, unique target ID and target context.
Other arguments are ignored for this derivation. Existing operand rows remain
unsupported_instruction; the binding catalog and all earlier counts are intact.

Caller ownership must agree across the rung, caller routine and actual program.
The first argument is trimmed for lookup, while declaration Names are not
trimmed. ASCII identifier-shaped names use `[A-Za-z_][A-Za-z0-9_]*` and ASCII case
normalization. This admits a conservative static lookup shape, not a complete
IEC/controller identifier validator. Unicode lookalikes, expressions and
qualified names are unsupported_target_name. No guessed compiler length rule
or parameter-count meaning is introduced.

Statuses are unique_candidate, missing_candidate, ambiguous_candidate,
missing_target_field, empty_target_field, unsupported_target_name and
unsupported_context. Missing fields take precedence, then unsupported caller
context, then empty/name/lookup handling. Only a unique candidate carries a
target ID. Its context priority is current_routine by identity, main_routine by
explicit attribute, fault_routine by explicit attribute, other_routine only for
Type=Normal, then not_analyzed. Explicit self/main/fault evidence can be retained
for other program types; phase/sequence names are never classified by spelling.

Limits are 250,000 JSR occurrences, 8,000,000 retained evidence characters and
65,536 characters per first field. Fixed errors expose no captured source text.
Canonical private validation reanalyzes and rejects changed rows. Private text
lists these candidates separately from tag operands and observation-only field
shapes. Source inventory3, source aggregate4 and manifest2 retain their layouts;
saved manifests record the updated analyzer. New runs preserve previous outputs.

## Public contract and next real run

Public reference schema10 / reference-summary-10 / source-references-8 requires
routine_targets with the same three fixed metadata values, total, by_status,
unique_by_target_context and distinct_targets. No rows, names, source IDs or
argument values are published. Totals reconcile to JSR shape counts; statuses
partition the total, contexts partition unique candidates and distinct targets
cannot exceed unique occurrences or declared source routines. Missing-field
counts equal zero-field JSR counts; other field-dependent statuses fit nonzero
calls. Ambiguity requires at least two routine envelopes. Counts are bounded
integers with exact keys.

Reference9 stays frozen as analyzer7 and rejects even an all-zero routine_targets
field. References1-8 keep their preceding contracts. The existing shape profile's
target_resolution=not_analyzed describes that observation-only profile; candidate
links are in the separate new object. Work8 / work-check-8 requires reference10;
work3/5, work4/6, work5/7, work6/8 and work7/9 retain exact earlier pairings.
Work1/2 retain their supported nested-reference handling. Sharing policy, sample
limits, paths, automatic local report commits and manual pull/push stay unchanged.

The next normal work-machine run should add candidate counts for 76 JSRs while
preserving every earlier binding/catalog/source/alias/rack/shape/flag/sample
counter. Candidate status, context and distinct-target counts are unknown until
that report returns. Partial remains expected. Investigate those aggregates
before choosing parameter semantics, call graphs or sequence interpretation.
See [the normal run procedure](WORK_MACHINE_REFERENCES_RUN.md).

## Validation

Full development validation passes **421 cases with one existing Windows symlink
skip**, excluding the ignored listener loader. The new core suite has 14 cases;
the public validator adds 25 negative mutations covering types, partitions,
JSR/source reconciliation, target bounds, ambiguity and source-label injection.
All 13 stored work reports validate without changes. Independent review passes
62 focused cases and finds no remaining blockers after fixes to context priority,
test registration and historical fixtures.

The full suite command is:

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

An independent workflow agent snapshots final code/test/config bytes into a
disposable clean checkout with no remotes and an invented multi-program fixture.
Actual `bash ./run-work-check.sh RoutineTargetSynthetic.L5X`, followed by a
remembered-source run, each passes **325 application cases (one skip) and 139
helpers**. Eight JSR candidate rows include five unique declarations, two missing
declarations and one missing field. Known current/main/fault/ordinary contexts
verify; an ST target is retained and a cross-program-only declaration does not
match. SBR/RET and every JSR argument remain outside the binding catalog.

Both saved reports use work8/reference10/source4; saved inventory/reference/
manifest use3/5/2 with analyzer8. Direct CLI text and JSON return expected partial
exit3; JSON equals saved canonical private references and text includes target
links/context. Every artifact hash verifies; the source and first-run artifacts
remain unchanged. Both report commits are local, contain only their report, cite
the tested parent and leave a clean checkout. Git traces show no fetch/pull/push.
Copied root code/test/config hashes match final working bytes. All 63 relative
Markdown links in changed documentation resolve and git diff --check passes.
Only invented
fixtures and approved public reports are used; no project confidential input
or listener execution occurred.

## Returned candidate confirmation (2026-10-14)

`7e15843` adds only
[work-check-20261014T221436Z-721c15dd.json](../../inspection/work-check-20261014T221436Z-721c15dd.json)
with tested clean `3598710` as parent. Both suites pass: 325 application cases
(one skip), 139 helpers. All 76 JSRs have unique candidates, covering 66 distinct
target declarations; other candidate statuses are zero. All target contexts are
not_analyzed. Every earlier source/reference/shape/diagnostic count is unchanged;
partial/private_run_saved and null sample are expected. This confirms scoped
declaration lookup, not valid calls, parameter roles or export byte identity.

The next observation-only slice adds unique-candidate program-Type provenance
and target-language counts, including the unknown-context subset, to explain
which metadata prevents context classification. It retains every existing
private candidate and public count. Read [the metadata review](ROUTINE_METADATA_REVIEW.md)
for current versions and next-run expectations. No repeat candidate-only check
is needed.
