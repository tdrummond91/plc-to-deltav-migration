# Routine-instruction argument shapes

Date: 2026-10-14. Branch: `feat/bounded-operand-example-pc`.
Returned baseline: `08c2695`, testing clean `bdf09f1`.

## Returned evidence and the next question

[The returned bit report](../../inspection/work-check-20261014T205025Z-cc9c4184.json)
confirms all 26 MVM/SWPB instructions: catalogued increases 17,591 to 17,617,
unsupported instruction slots fall 597 to 519, root_bound increases by 52,
literals by 16 and non_data by ten. Its 296 application cases (one skip) and
139 helpers passed. The report-only commit has the tested revision as parent,
records clean code and a saved private run. Independent full comparison found
no unexpected changes. See [the confirmed bit review](BIT_OPERATION_REVIEW.md).

The next source-context question is how routine calls use their argument fields.
The public histogram contains JSR=76, SBR=1 and RET=1. All remain outside the
binding catalog. Understanding these instructions will prepare routine links
and eventually help distinguish conditional execution and sequence context.
It does not by itself identify process transitions or execution reachability.

## Why parameter roles are deferred

The actual [Logix Import/Export reference](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf),
Publication 1756-RM014D-EN-P, shows different language-specific layouts:

| Instruction | RLL neutral table | Structured-text table |
|---|---|---|
| JSR | Routine name, inputs, returns (printed page 215) | Routine name, InputCount, inputs, returns (page 294) |
| SBR | Routine name, inputs (page 220) | Inputs (page 299) |
| RET | Returns (page 220) | Returns (page 299) |

The [Studio 5000 routine-instruction help](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/program-control-instructions/jump-to-subroutine--jsr---subroutine--sbr---and-re.html)
describes optional parameters and their source/destination roles. Its generalized
form does not resolve the neutral-table differences. An independent explorer
opened the primary manual/help and identified this evidence gap. A second field
spelled zero cannot yet be claimed as a validated zero-input RLL signature.
Do not silently transfer the structured-text layout into the ladder parser.

Routine targets belong to the owning program according to the official
[task/program/routine guidance](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/studio-5000-logix-designer/controller-organizer/use-the-controller-organizer/use-tasks--programs--and-routines.html).
The inventory already preserves program/routine identities and attributes for
later scoped linking. This slice performs no target resolution and does not
put routine names into the tag-symbol namespace.

## Implemented observations

`routine_shapes.py` derives fixed counts from successful parsed RLL instruction
records. It recognizes only ASCII JSR/SBR/RET opcode spellings, ignoring case,
and emits no per-instruction rows or source strings. Public reference schema 9
adds `routine_instruction_shapes` with fixed metadata: analysis_scope is
parsed_rll_routine_instruction_fields; parameter_roles and target_resolution are
not_analyzed. `by_opcode` contains exactly JSR, SBR and RET.

Every group has total, argument_slots, noncanonical_spelling and by_arity.
Noncanonical spelling counts recognized mixed/lowercase opcodes that source
schema 4 pools into its withheld bucket. JSR bins are zero_fields, one_field,
two_fields_second_zero, two_fields_second_other, three_or_more_second_zero and
three_or_more_second_other. SBR/RET bins are zero_fields, one_field, two_fields
and three_or_more. The zero observation means the second argument, trimmed,
is exactly ASCII text `0`; `00`, `+0`, `0.0`, quoted zero and Unicode lookalikes
remain other. Empty second fields also belong to other. No parameter-count,
source/destination, datatype or call-validity meaning is assigned.

Closed validation requires strict nonnegative integers, exact keys/constants,
partition totals and arity/slot lower bounds (exact slots when no larger-arity
bucket is present). Each total equals its uppercase source opcode count plus
noncanonical_spelling; the combined spelling count cannot exceed the source
withheld pool. Call totals cannot exceed uncatalogued instruction coverage;
slots cannot exceed total operands or unsupported-instruction slots. These
checks prevent reusing the withheld pool independently for every opcode.

Private text receives the captured inventory through the CLI/storage render
path and prints the same observations, including zero-field SBR/RET calls that
operand rows alone cannot represent. The existing renderer API without an
inventory still works. Private reference JSON and its canonical result are
unchanged. No source file is reread for this diagnostic.

## Contracts and sharing

Public references are schema 9 / reference-summary-9, with analyzer
source-references-7 unchanged. Private references stay schema 4; source inventory
3, source aggregate 4 and manifest 2 retain their layouts. Work schema 7 /
work-check-7 requires reference 9. Work3/5, work4/6, work5/7 and work6/8 pairings
remain frozen, and work1/2 retain supported nested-reference handling.

Reference versions 1 through 8 retain exact fields and constants, rejecting even
an all-zero routine_instruction_shapes field. Version 8 and 9 share analyzer 7
because binding behavior did not change. Existing timer/flag/selector sample
rules, statuses and bounds are retained.

The additional field contains only fixed observational counts. It adds no routine
names, raw arguments, source/rung IDs, hashes, locations, neighboring logic or
relationships. The publication cap and single bounded mystery sample remain
unchanged. Private outputs stay local; report commits remain automatic and
pull/push manual. The listener stays disabled and untracked.

## Validation and next work-machine check

Synthetic coverage includes zero-field and larger-arity calls, exact zero versus
other spellings, empty slots, case/withheld accounting, failed-rung/ST exclusion,
unchanged bindings/catalog/private JSON, saved private text, public privacy,
strict types/fields/invariants and actual historical report compatibility.

Final development validation: **404 application/workflow cases**, OK with one
existing Windows symlink-capability skip; ignored listener loader excluded.
The core module passed ten new cases and the existing summary suite passed 76.
Independent review passed 68 focused cases, checked the actual CLI text boundary
and found no blockers. All twelve committed work reports validate unchanged.

The full development command, from the repository root, was:

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
current tracked bytes and the new module/test. Its invented rack fixture adds
two routine calls (one lowercase), a zero-field SBR and zero-field RET. Total
instructions rise 5 to 9 while catalogue coverage stays 5; four new operand
slots remain unsupported_instruction. Every other operand, alias, rack, module
and symbol count is unchanged. Observations are JSR total2/slots4/noncanonical1,
with one two-field second-zero and one second-other; SBR/RET each total1/slots0/
zero_fields1. These facts assign no parameter or target semantics.

Actual commands were:

```bash
bash ./run-work-check.sh RoutineSynthetic.L5X
bash ./run-work-check.sh
uv run --project python-parser --locked plc references \
  confidential/plc-code/RoutineSynthetic.L5X --format text \
  --workspace confidential/workspaces/cli-routine
```

Both launchers exited 0, each passing **308 application cases (one skip) and
139 helpers** without failures/errors. Direct CLI returned the expected partial
exit 3. Public schemas are work7/reference9/source4; private inventory/reference/
manifest stay3/4/2 with analyzer7. Actual CLI and all three saved references.txt
reports include zero-field observations. Private JSON has its exact unchanged
structure and no new shape field. All fifteen artifact hashes across three
manifests verify; prior outputs and the input remain intact.

Disposable report-only commits `6a25336a4857` and `dc9b9ee41d9b` cite their clean
tested parents and leave a clean checkout. Git traces contain zero fetch/pull/
push commands. All 81 copied code/test/config files match final working bytes;
five Python test files were normalized to repository LF without semantic changes.
No project confidential input or listener execution was used.

All 58 relative Markdown links in changed documentation resolve, and
`git diff --check` passes. Historical report files remain untouched.

The next real report should preserve every existing binding, catalog, source,
alias/rack, flag/sample and diagnostic counter. It should add shape groups with
JSR=76, SBR=1 and RET=1 if the export is unchanged. Their field distributions
are unproven until the run. Inspect which JSR arities and second-zero spellings
dominate, and SBR/RET field counts, before choosing scoped routine links or a
further bounded export-format clarification. Shape agreement alone does not
prove parameter roles. No repeat bit/math-only check is needed.

## Returned work-machine confirmation (2026-10-14)

Commit `0a2610f` adds only
[work-check-20261014T212041Z-8cac2026.json](../../inspection/work-check-20261014T212041Z-8cac2026.json)
and has tested clean `9c56b50` as parent. The work7/reference9/source4 report
validates; all 308 application cases (one skip) and 139 helpers pass. JSR=76
and argument_slots=163: 65 two-field second-zero calls, 11 larger second-other
calls. Slot reconciliation proves those eleven have exactly three fields. SBR
has one occurrence with one field; RET has one with zero fields. Noncanonical
spelling counts are zero. All preceding source/reference/diagnostic counters
are identical. Analysis remains partial with private results saved and sample
null. Aggregate agreement does not prove source byte identity or parameter roles.

The next slice uses only the JSR first-field routine name shared by both official
layouts, deriving separate program-local declaration candidates. It leaves later
arguments and all tag/catalog counts unchanged. Read
[the candidate review](ROUTINE_TARGET_REVIEW.md) for the current contracts,
validation and next work-machine check. No repeat shape-only run is needed.
