# Recognizing the first-scan system flag

Date: 2026-10-14. Branch: `feat/bounded-operand-example-pc`.
Returned baseline: `7f5db96`, testing clean `84dc393`.

## Confirmed work-machine result

[The follow-up report](../../inspection/work-check-20261014T191741Z-2009d02d.json)
returned in `d247f87`, testing clean `d64ee4d`, confirms this fix. All 269 selected
application cases (one skip) and 139 helpers passed, with no failures/errors.
Its commit changes only the report, has the tested revision as parent and records
a saved private run. Work/reference/source versions are 4/6/4.

Exactly the predicted evidence changes: system_flag is 1, unresolved operands
fall 320 to 319 (also the unresolved colon reason), direct rack comparisons and
their no-candidate count fall 1 to 0, and the diagnostic sample is null. Root
bindings, alias/rack candidate counts, source counts and all other reference
counters are unchanged. Full comparison excludes only the intentional contract
metadata and code revision. This confirms classification without proving source
byte identity or runtime first-scan behavior. No repeat flag-only check is needed.
The following slice is [basic calculation signatures](MATH_SIGNATURE_REVIEW.md);
the implementation/version/test sections below preserve this flag checkpoint.

## Returned evidence and interpretation

[The returned work report](../../inspection/work-check-20261014T183844Z-26f5b84a.json)
validates. Its commit changes only that JSON and its parent equals the tested
revision. All 241 selected application cases (one skip) and 139 helpers passed,
with no failures/errors. Analysis is partial and its private run was saved.
The entire nested source/reference aggregate equals the preceding `9597f18`
report after excluding code revision. This does not prove source byte identity.

The authorized sample is exactly `S:FS`, at argument 0 of `XIC`. Rockwell's
[runtime controller status reference](https://www.rockwellautomation.com/en-gb/docs/studio-5000-logix-designer/38-00/contents-ditamap/studio-5000-logix-designer/controller-properties/runtime-controller-configuration-and-status.html)
identifies this as the First Scan flag, restricts its use to XIC/XIO, and says
these flags are not tags and cannot be alias targets. The
[keyword reference](https://www.rockwellautomation.com/en-za/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/keywords.html)
documents case-insensitive spelling. Both official pages were checked for this
slice. No plant-specific interpretation or surrounding rung was needed.

## Implemented rule

The analyzer classifies only a direct exact trimmed ASCII `S:FS` operand, ignoring
letter case, in a valid one-argument XIC or XIO instruction as `system_flag`.
Instruction recognition remains case-insensitive. It retains raw text and the
existing operand/rung/instruction IDs. The record has no symbol/target ID,
alias chain, suffix or failure reason. No synthetic tag declaration is created.
Private text explains this distinct status.

Alias targets, other instruction roles, wrong arity, indexed/member suffixes,
Unicode lookalikes and other `S:` names keep their previous handling. The rule
does not broaden the general address grammar or turn the entire S namespace
into a recognized class. It identifies a supported operand role without modeling
when the flag is true, initialization effects, execution order or DeltaV strategy.
Rack candidates and their unexamined backing relationships are unchanged.

## Version and publication contracts

| Artifact | Contract after this change |
|---|---|
| Private source inventory | schema 3 / `source-inventory-3`, unchanged |
| Private references | schema 4 / `source-references-5` |
| Public source aggregate | schema 4 / `aggregate-summary-4`, unchanged |
| Public reference aggregate | schema 6 / `reference-summary-6` |
| Work-check report | schema 4 / `work-check-4` |
| Private reference-run manifest | schema 2; current analyzer metadata |

Reference schema 6 adds only `operands.by_status.system_flag`; aliases retain
their old vocabulary. Recognized flags satisfy this bounded operand-analysis
scope but do not count as root_bound, literal or non_data. Counts reconcile to
the same operand total. The flag count cannot exceed catalogued instructions or
the sum of named XIC/XIO occurrences plus withheld instruction occurrences.
The withheld allowance is necessary because source schema 4 preserves original
opcode case and pools lowercase spellings. That public bound is conservative;
canonical private reanalysis establishes each occurrence's actual role.

Reference schemas 1 through 5 retain their exact old status keys and analyzer
constants; even a zero system_flag field is rejected there. Current private
canonical validation requires schema 4/analyzer 5. Work schema 3 continues to
require reference 5; work schema 4 requires reference 6. Older work schemas 1/2
retain their existing ability to contain a supported reference summary, with
schema 2 still limited to malformed-kind samples. Historical returned S:FS
samples remain readable under their original schema 3/reference 5 contract.
Current reports reject recognized XIC/XIO S:FS as an unmatched sample even if
another unrelated direct address is still unmatched. The shared recognizer
keeps classification and this contradiction check aligned.

The one-sample bound, count-only summaries, private artifact paths and local
report-only commits are unchanged. Pull/push remain manual; the listener stays
disabled and untracked.

## Validation and next work-machine check

Synthetic tests cover exact role/case/whitespace, preserved raw evidence and IDs,
aliases, suffixes/indices, wrong arity, unrelated opcodes, Unicode lookalikes,
resource limits, private persistence, public count bounds, lowercase opcode
pooling, legacy version keys and current/historical diagnostic samples.
The report rejection test includes a separate unmatched operand so zero unmatched
counts cannot conceal a missing S:FS-specific check.

Final development validation passed **365 application/workflow cases**, with one
existing Windows symlink-capability skip. The ignored listener loader was
excluded. An independent reviewer ran **99 focused cases**, all passing, and
found no remaining blockers. All nine stored work reports remain readable;
their files were not changed.

From the repository root, the full development check was:

```bash
uv run --project python-parser --locked python -B - <<'PY'
from pathlib import Path
import sys, unittest
folder = Path.cwd() / 'python-parser/tests'
sys.path.insert(0, str(folder))
loader = unittest.TestLoader()
suite = unittest.TestSuite(loader.loadTestsFromName(path.stem)
    for path in sorted(folder.glob('test_*.py'))
    if path.stem != 'test_feedback_listener')
result = unittest.TextTestRunner(verbosity=1).run(suite)
raise SystemExit(not result.wasSuccessful())
PY
```

The selected work-machine suite includes the 28 new flag/summary/report cases.
An independent agent ran the actual CLI twice in a disposable checkout with no
remotes, using current tracked file bytes plus the three new test modules:

```bash
bash ./run-work-check.sh SystemFlagSynthetic.L5X
bash ./run-work-check.sh
```

Both explicit-source and remembered-source runs exited 0, each passing **269
application cases (one skip) and 139 helpers**. The synthetic input adds one
first-scan contact to the existing invented rack fixture. Both reports validate
as work4/reference6/source4, with system_flag=1 and a null sample. Existing
root_bound=2/unresolved=3 and rack/module/alias counts match the original fixture.
Private inventory/reference/manifest schemas are 3/4/2; raw S:FS is preserved,
and the only diagnostic is the expected rack-backing-not-analyzed warning.

Disposable commits `d33b6ea0239b` and `36d38b6cc7b7` each change only their report,
have the tested revision as parent and leave a clean checkout. The original
synthetic input is unchanged; both private runs have identical artifact hashes
and the first run remains intact. Git traces contain no fetch/pull/push.
All 71 copied code/test/config files still matched final working bytes after
validation. No project confidential input or listener execution was used.

All 42 relative Markdown links in changed documentation resolve, and
`git diff --check` passes. Historical report files remain untouched.

The original prediction, now confirmed above, was system_flag=1, unresolved
operands 320 to 319, direct rack comparisons 1 to 0, and a null diagnostic sample.
Root-bound operands (20,178), unresolved aliases (99), their unique rack matches
(99), and alias-mediated candidate matches (319) should stay unchanged. All
source counts and other reference counters should remain stable. These are
predictions to check, not claimed work-machine results. Partial remains expected
because rack backing, unsupported instructions/expressions and source-language
gaps still exist. Next inspect the returned delta before choosing the following
Phase 1 slice; do not request the same unmatched operand again.
