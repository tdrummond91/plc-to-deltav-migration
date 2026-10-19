# Masked moves and byte-swap operand roles

Date: 2026-10-14. Branch: `feat/bounded-operand-example-pc`.
Returned baseline: `4244cf5`, testing clean `a6a2a71`.

## Confirmed work-machine result

[The returned bit-operation report](../../inspection/work-check-20261014T205025Z-cc9c4184.json)
returned in `08c2695`, testing clean `bdf09f1`, confirms all 26 new signatures.
It passed 296 application cases (one skip) and 139 helpers, saved a private run
and adds only the report with the tested revision as parent. Work/reference/
source versions are 6/8/4.

Independent comparison found the predicted changes: catalogued instructions
17,591 to 17,617, unsupported instruction slots 597 to 519, root_bound 20,234 to
20,286, literals 2,517 to 2,533 and non_data 868 to 878. Thus 78 newly accounted
slots split into 52 bound roots, 16 literals and ten selectors. All other source,
alias/rack, flag, sample and diagnostic evidence stayed unchanged apart from
intentional contract, run, revision and test-count metadata. This confirms
lexical classification without proving source byte identity or runtime behavior.
No repeat bit-operation-only run is needed. The following slice is
[routine-instruction argument shapes](ROUTINE_CALL_SHAPE_REVIEW.md); the sections
below preserve the bit-operation implementation checkpoint.

## Returned evidence and selected scope

[The returned calculation report](../../inspection/work-check-20261014T195120Z-0b07d834.json)
validates and confirms all 28 new math instructions and 56 bound arguments.
It passed 286 application cases (one skip) and 139 helpers, saved a private run,
and changes only the report with the tested revision as parent. Independent
comparison found no unexpected differences. Source/alias/rack/flag/sample
evidence remains unchanged. See [the confirmed math review](MATH_SIGNATURE_REVIEW.md).

Its public histogram includes MVM=16 and SWPB=10, still uncatalogued. This slice
uses verified operand roles to improve bit-manipulation reference evidence,
without treating an instruction option as a tag. No private examples or selector
spelling are needed for the positional-role contract.

The official [Logix Import/Export reference](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf),
Publication 1756-RM014D-EN-P, documents MVM's source/mask/destination order at
printed page 219 and SWPB's source/order-mode/destination order at page 221.
The [MVM reference](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-01/contents-ditamap/instruction-set/move-logical-instructions/masked-move--mvm-.html)
allows immediate/tag source and mask, with a tag destination. The
[SWPB reference](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-01/contents-ditamap/instruction-set/move-logical-instructions/swap-byte--swpb-.html)
identifies tag source/destination and a list-item order selector. An independent
explorer opened the actual official pages and manual. The help mentions mode
choices and an entry normalization, which alone does not establish every legacy
neutral-export spelling; this slice does not validate mode values.

## Implementation and interpretation boundaries

Add only MVM:3 and SWPB:3 to the explicit catalog. All three MVM fields and
SWPB fields 0/2 use existing lexical root/literal handling. For valid three-field
SWPB instructions, nonempty field 1 is `non_data` by documented positional
role, regardless of spelling. Wrong arity and empty-field handling take priority.
The shared `_swpb_order_mode` predicate gates this classification and diagnostic
sample validation. A same-named tag, numeric-looking option, unknown option,
malformed-looking text or colon address in that slot never becomes a tag lookup
or mystery-address sample. Raw evidence and occurrence IDs remain intact.

The selector is outside data-root lookup; `non_data` does not certify its mode
value. Mask widths, operand types, destination access, byte order, controller
execution effects and process intent remain unvalidated. Existing literal
admission in address-role fields remains lexical, including SWPB source and
destination. No expression grammar, read/write index, physical I/O mapping,
alarm consequence or DeltaV class mapping is added. Private reports state these
limits and retain the raw fields for later review.

## Contracts and historical compatibility

| Artifact | Current contract |
|---|---|
| Private source inventory | schema 3 / source-inventory-3, unchanged |
| Private references | schema 4 / source-references-7; unchanged field layout |
| Public source aggregate | schema 4 / aggregate-summary-4, unchanged |
| Public reference aggregate | schema 8 / reference-summary-8; unchanged fields/statuses |
| Work-check report | schema 6 / work-check-6, requiring reference 8 |
| Private reference-run manifest | schema 2; updated analyzer metadata |

Reference versions 1 through 7 retain exact constants/keys. Versions 6/7/8
share the system-flag vocabulary and conservative bounds; versions 1 through 5
exclude that key. Source and rack mappings remain unchanged. Work3/reference5,
work4/reference6 and work5/reference7 remain readable; work1/2 retain their prior
supported-nested-reference behavior. SWPB was previously absent from the sample
validator's opcode catalog, so no previously accepted SWPB selector sample is
invalidated by the new role exclusion. Timer/flag sample rules remain in place.

The publication cap, closed counts, single 128-character sample limit, private
artifact paths and local report-only commits stay unchanged. Pull/push remain
manual and the development listener stays disabled and untracked.

## Validation and next work-machine check

Synthetic coverage checks mask/data lookup, aliases/suffixes/case, selector
collisions and raw preservation, malformed/empty arity, unchanged other roles,
canonical integrity, bounded publication, selector sample exclusion with other
eligible gaps, and actual historical report/version compatibility.

Final development validation: **392 application/workflow cases**, OK with one
existing Windows symlink-capability skip, excluding the ignored listener loader.
The core worker passed 74 focused cases and the summary worker passed 74 summary
cases. Independent review verified neutral operand order against the official
manual, passed all nine new bit-operation tests and found no blockers. Tests
reject both forged selector sample kinds with another eligible positive gap,
and assert that address parsing is never called for the excluded slot. All
eleven stored work reports validate unchanged.

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
current tracked working bytes and the new bit-operation test module. It added
one masked move and one byte swap to the invented rack fixture, using declared
module roots and one literal mask. Baseline/current comparison verifies exactly
+2 catalogued instructions, +6 operands, +4 root-bound, +1 literal and +1 non_data.
Existing alias, rack, unresolved, malformed-shape and diagnostic evidence stayed
unchanged, with a null sample. The actual commands were:

```bash
bash ./run-work-check.sh BitSynthetic.L5X
bash ./run-work-check.sh
```

Both explicit-source and remembered-source commands exited 0, each passing
**296 application cases (one skip) and 139 helpers** without failures/errors.
Public work/reference/source schemas are 6/8/4; private inventory/reference/
manifest are 3/4/2, with analyzer7. Both runs retain the fixture's existing
partial rack gap and have verified artifact hashes.

Disposable commits `5980e3e2e575` and `fcafe6aac3f6` each change only their report,
have the tested revision as parent and leave a clean named branch. Git Trace2
records 31 Git process starts per run and zero fetch/pull/push. All 80 copied
code/test/config files match final root working bytes; all 23 prior artifacts,
including the synthetic source and first run's outputs, remain unchanged.
No project confidential data or listener execution was used.

All 54 relative Markdown links in changed documentation resolve, and
`git diff --check` passes. Historical report files remain untouched.

The original prediction, now confirmed above, was that if all 26 occurrences
have their documented three fields,
expect catalogued instructions 17,591 to 17,617 and unsupported-instruction
operand slots 597 to 519. If all ten selector slots are nonempty, non_data rises
868 to 878. The remaining 68 newly analyzed data slots can be roots, literals
or gaps; their distribution and additional alias-mediated rack occurrences are
unknown until the real run. Do not predict all 68 as bound or require unchanged
operand occurrence splits. Source counts, declared symbols/aliases, 15 named
rack candidates, flag recognition and other instruction families should stay
stable. Partial remains expected.

Run the normal work-machine script on this branch, review its newly committed
report and push manually. Inspect that delta before selecting the next Phase 1
slice; no repeat math-only or first-scan-only check is needed.
