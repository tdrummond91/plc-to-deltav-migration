# Basic calculation operand signatures

Date: 2026-10-14. Branch: `feat/bounded-operand-example-pc`.
Returned baseline: `d247f87`, testing clean `d64ee4d`.

## Baseline and selected scope

[The returned report](../../inspection/work-check-20261014T191741Z-2009d02d.json)
confirms the first-scan fix: system_flag=1, unresolved operands 320 to 319,
direct rack comparisons 1 to 0, and sample null. All 269 selected application
cases (one skip) and 139 helpers passed. Its commit changes only the report and
has the tested revision as parent. Independent comparison found no unexpected
changes. See [the completed flag review](SYSTEM_FLAG_REVIEW.md).

Remaining uncatalogued instructions total 311, accounting for 653 operand
slots. Their public opcode histogram includes ABS=8, LN=2 and SQR=18. These
28 occurrences have a small documented signature useful for identifying
calculation references around loops, alarms and miscellaneous logic. No private
example is required to add the grammar. Wider SFC/routine control, physical rack
backing and expression analysis remain separate investigations.

The official [Logix Import/Export reference](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf),
Publication 1756-RM014D-EN-P, Chapter 9, specifies two neutral-text arguments in
source/destination order for ABS (printed page 212), LN (216), and SQR (220).
Official [ABS](https://www.rockwellautomation.com/en-gb/docs/studio-5000-logix-designer/38-03/contents-ditamap/instruction-set/compute-math-instructions/absolute-value--abs-.html)
and [LN](https://www.rockwellautomation.com/en-gb/docs/studio-5000-logix-designer/38-02/contents-ditamap/instruction-set/advanced-math-instructions/ln.html)
operand tables accept a numeric immediate/tag source and a tag destination.
The [square-root reference](https://www.rockwellautomation.com/en-pl/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/compute-math-instructions/square-root--sqrt-.html)
documents the later SQR-to-SQRT rename. The neutral-text manual independently
establishes legacy SQR's two-slot signature; this slice adds only ABS/LN/SQR.
An independent explorer opened the actual primary pages and PDF for this check.

## Implemented behavior and limits

Add only ABS:2, LN:2 and SQR:2 to the explicit operand catalog. Valid two-field
instructions reuse the existing root lookup, literal recognition, scope/alias
rules and suffix handling. Raw text, occurrence IDs, snapshot evidence and
source inventory remain intact. Wrong arity, empty fields, expressions, dynamic
indices and unrelated instructions retain explicit gap handling.

This is lexical reference analysis. The existing catalog admits recognized
literals in address-role slots, including destination slots; that status does
not certify an instruction-valid destination. This slice does not validate
datatypes, destination access, math domains, values, execution effects or alarm
purpose. It does not add read/write indexes, evaluate formulas, parse CPT
expressions, recognize SQRT, or convert calculations to DeltaV classes. Private
text reports state these limits. Non-programmer editing and persistent reviewed
classifications remain later phases.

## Contracts and compatibility

| Artifact | Current contract |
|---|---|
| Private source inventory | schema 3 / source-inventory-3, unchanged |
| Private references | schema 4 / source-references-6; field layout unchanged |
| Public source aggregate | schema 4 / aggregate-summary-4, unchanged |
| Public reference aggregate | schema 7 / reference-summary-7; field layout unchanged |
| Work-check report | schema 5 / work-check-5, requiring reference 7 |
| Private reference-run manifest | schema 2; updated analyzer metadata |

The analyzer/export versions distinguish the changed signature catalog from
the prior result. Public reference schema 6 is frozen with analyzer 5 and its
system_flag vocabulary/bounds. Versions 1 through 5 retain their exact previous
keys/constants. References 5/6/7 require source 4; older mappings are unchanged.
Work3/reference5 and work4/reference6 remain readable with their original
sample rules. Work1/2 retain their previous supported-nested-version handling.
Current known flag/timer samples remain rejected as mystery samples. No private
run migration or source byte identity is implied by aggregate compatibility.

The existing public field set, one-sample limit, private output paths and
report-only local commits remain in place. Pull/push are manual and the listener
stays disabled and untracked.

## Validation and next work-machine check

Focused synthetic cases cover all three signatures, source/destination evidence,
literal boundaries, alias/scope/suffix lookup, mixed case, wrong/empty arity,
expressions and dynamic gaps, unchanged other instructions, canonical integrity,
public metadata/privacy/reconciliation, historical version 6 and actual stored
report compatibility, and private persistence/source preservation.

Final development validation: **382 application/workflow cases**, OK with one
existing Windows symlink-capability skip; the ignored listener loader was
excluded. All 17 new math cases pass. The core worker also passed 39 focused
cases and the summary worker passed 73 summary cases. An independent reviewer
passed the initial 16 math cases plus scripted historical/current sample and
work1/2 compatibility checks. Its recommendation to retain historical work4/
reference6 known-flag and timer rejection coverage was implemented as the 17th
math case, with another eligible gap present in both subcases.

The review caught a test that globbed all reports and asserted exactly ten;
that would fail after the next report and mis-handle future failed runs. It now
uses ten explicit historical baseline filenames. The two actual CLI runs below
prove repeated report growth does not break selected tests. No production
blockers remain. All ten committed work reports validate unchanged.

The final full development command, from the repository root, was:

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

An independent workflow agent used a disposable clean checkout with no remotes,
current tracked bytes and the three new test modules. It added ABS/LN/SQR to the
invented rack fixture, using two literal sources, one declared-root source and
three declared-root destinations. Baseline/current comparison confirms exactly
+3 catalogued instructions and +6 operands (+4 root_bound, +2 literal), with
existing unresolved, alias, module and rack counts unchanged. The agent ran:

```bash
bash ./run-work-check.sh MathSynthetic.L5X
bash ./run-work-check.sh
```

Both explicit-source and remembered-source commands exited 0, each passing
**286 selected application cases (one skip) and 139 helpers**. Public schemas
are work5/reference7/source4; private inventory/reference/manifest are 3/4/2,
with analyzer6. Partial status is the fixture's existing rack-backing gap.
Disposable commits `bae3092f103d` and `c7ee5938191d` each change only their report,
record their parent as tested revision and leave a clean tree. Both Git traces
contain zero fetch/pull/push commands. The input and prior run files remain
unchanged; all 74 copied code/test/project-config files match final working
bytes. No project confidential data or listener execution was used.

All 49 relative Markdown links in changed documentation resolve, and
`git diff --check` passes. Historical report files remain untouched.

For the unchanged export, if all 28 occurrences have the documented two-field
signature, expect catalogued instructions 17,563 to 17,591 and unsupported
instruction operand slots 653 to 597. Their 56 newly analyzed slots will be
partitioned into existing root/literal/gap statuses. The root/literal split
cannot be predicted from the public opcode histogram. Newly analyzed slots can
also reveal additional alias-mediated rack comparisons, so do not require those
occurrence totals to stay unchanged. Source counts/ladder metrics, symbol and
alias declarations, 15 named rack candidates, flag recognition and other
instruction families should remain stable. Partial remains expected.

Run the normal work-machine script on this branch, review its new locally
committed report, then push manually. Inspect that delta before selecting the
following Phase 1 slice. No repeat first-scan-only run is needed.
