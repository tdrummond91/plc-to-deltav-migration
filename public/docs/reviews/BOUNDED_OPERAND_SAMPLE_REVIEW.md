# One bounded mystery operand in work-machine feedback

Date: 2026-10-14. Baseline: `46467af`, testing clean code `bd846fa`.
Branch: `feat/bounded-operand-example-pc`.

## Returned result and user clarification

[The returned report](../../inspection/work-check-20261014T072717Z-4d71aaff.json)
passes `validate_work_check_report`. Its commit changes only that JSON and its
parent equals the reported tested revision. The work machine reports 152
application tests (one skip), 139 helper tests, no failures/errors, partial
analysis and a saved private run. This confirms the restored automatic local
report commit; the user pushed it manually.

Its entire reference/source aggregate equals the preceding address-shape report
after removing only the tested revision. The 868 malformed operand occurrences
all fall in `other_form`; the other six shape counters are zero. Counts identify
occurrences, not distinct tags or rungs. They do not establish source byte
identity or the spelling of any rejected operand.

Tyler explicitly clarified that one actual mystery-address occurrence is within
the agreed sharing boundary. Requiring only counts or invented tokens for this
investigation was unnecessarily restrictive. The new feedback includes one
actual operand example, separately from the count-only reference summary.

## Contract and selection

Work-check schema 2 / `work-check-2` adds required top-level `diagnostic_sample`.
It is either null or one object with exactly these fields:

| Field | Meaning |
|---|---|
| `kind` | Fixed `direct_malformed_operand` |
| `opcode` | Standard supported instruction mnemonic |
| `argument_index` | Zero-based operand slot within that instruction |
| `raw_text` | Actual operand text, at most 128 printable characters |

The builder validates the source/reference pairing and selects the first eligible
direct malformed operand in the existing source order. It excludes alias-target
failures, unsupported instructions, wrong arities, labels, expression slots and
recognized literals. It skips overlong/nonprintable candidates rather than
truncating them, and accepts only one lexical operand. The sample does not add
a rung, source path, routine/tag listing, IDs, neighboring logic or engineering
values from other records. A name or value already inside the selected operand
is preserved under Tyler's specific authorization.

Selection is deterministic, so repeating an unchanged input does not rotate
through new examples. Null means analysis failed/did not run, or no eligible
short direct malformed operand was available. No full rung export or cumulative
rung-coverage certification is added by this feature.

Public validation rejects extra fields, invalid slots/text, inconsistent versions
and samples with failed analysis or no matching direct-malformed population.
The unchanged count-only reference/source schemas remain 3/3. Exact historical
work-check schema 1 remains readable and cannot carry the new sample field.
The 32-KiB report limit and report-only local commit/content checks remain.
The runner still never fetches, pulls or pushes; the listener remains disabled.

## Next evidence and limits

The aggregate contains 390 TON and 44 RTO instructions. Twice that sum is 868,
making repeated trailing timer operands a useful hypothesis. The scrubbed
examples preserve repeated trailing slots but replace their original spelling,
so they do not prove those slots contain question marks.
[Rockwell's import/export reference](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf)
lists timer, preset and accumulator slots in the neutral timer syntax (printed
pages 220-221). That alone does not establish the rejected token's spelling.

Run the ordinary work check and manually push its locally committed report.
Inspect the one returned example before changing parser recognition. A sample
can establish one real occurrence; it does not establish that all 868 share its
syntax or justify globally accepting an otherwise unsupported token. There is
no timer semantic interpretation, classification, PCSD or FHX change here.

## Validation

The full application/workflow suite passed 259 tests (one existing Windows
symlink skip), excluding the ignored listener loader before import. The focused
work-check/bootstrap/suite-selection run passed 71 tests; the new diagnostic
module passed 14. Independent review found no code blockers and prompted two
documentation clarifications about the sample exception and schema versions.

Two real CLI runs in a temporary checkout with invented timer syntax and an
unreachable origin passed 166 selected application tests (one skip) and all 139
helper tests each. Both emitted the same exact `?` sample at TON argument 1,
validated schema 2, made one report-only local commit and left clean `main`.
The second run reused the remembered source; source and previous outputs were
unchanged. Invented controller/routine/timer names remained absent from feedback.
All five existing work-check reports validated unchanged. No private source,
listener or actual work-machine execution occurred during these local checks.

The new tests exercise deterministic selection, alias/role exclusion, bounds,
single-operand grammar, forged-reference rejection, unchanged count-only output,
null/failure cases, schema compatibility, exact sample publication and captured
snapshot reuse. The selected suite still runs under its process/network guard.

## Returned sample and follow-up (2026-10-14)

Report `work-check-20261014T075024Z-a11d87b8.json`, returned in `349ee29`,
tested clean `2851dbd`: 166 application cases (one skip) and all 139 helpers
passed. Aggregate counts match the prior report except code revision. The sample
is `?` at TON argument 1. The preceding request to obtain that sample is complete.
See [the timer follow-up](TIMER_PLACEHOLDER_REVIEW.md) for the narrow recognition
rule, version change, tests and next measurement. One sample does not prove all
868 malformed occurrences share this syntax.
