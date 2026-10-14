# Closed malformed-address diagnostic

Date: 2026-10-13. Branch: `feat/source-references-pc`. Baseline/event commit:
`b06e7dc737da3d91805fcf667c0e0cc3fb3eee61`. This is one authorized Phase 1
follow-up in the listener's dedicated checkout. No real confidential source or
private work-machine output was opened; the primary checkout was not modified.

## Returned report and decision

The worker verified the selected report's Git blob
`efe738152d51b98f0111d84292695cbf7cc5f4a2` and validated
[work-check-20261013T234851Z-b10d84dc.json](../../inspection/work-check-20261013T234851Z-b10d84dc.json)
and its preceding work-check report. They test clean revisions
`6585443b3cd735f63da4490e6e169206a44389d3` and
`ad2ec8b1ca996c5ff4cf1420f3b34957a55f639d`, respectively.

The new report records 208 application cases (one skip), versus 155 previously;
both record 139 helper cases. Both suites report passed, with zero failure/error,
expected-failure or unexpected-success events and no failed IDs. Analysis is
partial with no failure code and `private_run_saved=true` in both. These are
returned counts, not independent verification of the private saved artifacts.

Bound aliases rise 45 to 842 and unresolved aliases fall 896 to 99. Bound operands
rise 17,856 to 20,178 and unresolved operands fall 2,642 to 320. The newer report
names all 252 module I/O declarations. The 870 unsupported-address operands are
unchanged, with 868 now identified as `malformed_address` and two as
`non_static_array_index`. Common source counts, instruction histogram, routine
types, ladder metrics and reference coverage match. Unmodeled XML accounting
changes as documented in [the module/I/O review](MODULE_IO_REVIEW.md).

No existing report supplies the spelling of those 868 occurrences. Counts do not
prove source byte identity, engineering meaning or a relationship to rack
connections. A parser expansion would be speculative. The documented next step
therefore adds the smallest useful closed observation partition and waits for
another work-machine run. No classification, correction system, PCSD/FHX,
service, deployment or listener change is included.

## Diagnostic behavior

Only operand occurrences whose final binding has `status=unsupported_address`
and `reason=malformed_address` enter `operands.malformed_address_shapes`.
The first matching row wins; all seven keys are present, including zero counts.
Examples below are independently invented, not scrubbed source samples.

| Key | Observation | Invented example |
|---|---|---|
| `alias_target_failure` | A verified nonempty alias chain led to the failure | `ToyAlias` targeting `Toy..Field` |
| `leading_hash_static_address` | Trimmed operand starts with `#`; removing exactly one hash leaves a spelling accepted by the existing static-address recognizer | `#Toy[3].Field` |
| `leading_hash_other` | Starts with `#`, but the remainder does not pass that recognizer | `##Toy` |
| `contains_brackets` | Contains either `[` or `]` | `Toy[-1]` |
| `contains_colon` | Contains `:` | `Toy::Input` |
| `contains_dot` | Contains `.` | `Toy..Field` |
| `other_form` | None of the preceding observations | `Toy+Other` |

The histogram counts occurrences, including repeated uses, not distinct
addresses. An alias caller's spelling does not describe the failing target;
those occurrences deliberately stay in the alias bucket. No alias-chain detail
is published. The leading-hash check reuses the current recognizer only for a
lexical observation: it does not recognize `#` as supported syntax, resolve the
remainder, validate members/types, or establish the prefix's meaning.

Precedence suppresses secondary features: a hash-prefixed bracket form is counted
once in a hash bucket. Coarse buckets and the alias bucket can remain insufficient
to select a grammar change. No arbitrary keys, strings, source examples, lengths,
values, source hashes, identifiers, rung order or cross-tabulations are added.

## Contract and changed files

`reference_summary.py` builds the histogram only after canonical private-record
validation and checks its sum against the malformed-address reason count. A
positive alias-target bucket also requires a malformed-address alias. Strict
closed-key and nonnegative integer checks apply at render/publication time.

Public reference schema/exporter advance to 3 / `reference-summary-3`; policy 2
and analyzer `source-references-2` remain. Private inventory/reference contracts
stay 2/2, source aggregate stays 3 and the work-check envelope stays 1. Exact
historical reference schema 1/source 2 and reference schema 2/source 3 reports
still validate without added fields. Mixed contracts are rejected; old reports
are not rewritten. The 32-KiB publication limit remains.

New tests in `test_address_shape_summary.py` exercise independently invented
inputs and privacy boundaries; the existing module-summary test updates its
public version expectation while private schema-3 records remain rejected.
The handoff, data contracts, Python README, development prompt, module review
and work-machine procedure identify the new contract and next run.

## Validation

Commands from the dedicated checkout:

```bash
uv run --project python-parser --locked python -B -m unittest discover -s python-parser/tests
uv run --project python-parser --locked python -B -m unittest discover -s tools/l5x_inspect/tests
git diff --check
```

The full application suite ran **246 tests: 245 passed, one existing Windows
symlink-capability skip**, with no failures/errors (124.442 seconds). All **139
helper tests passed**. These fresh runs covered the staged implementation over
baseline b06e7dc; only validation notes changed afterwards.

The 14 new tests cover exact bucket counts/precedence, repeated occurrences,
direct and chained aliases, static versus dynamic/qualified/overlength forms,
excluded operand roles, unchanged private results, zero-filled empty input,
renaming/value/order invariance, forged private records, unknown keys, invalid
count types/totals, legacy schemas, version hybrids, nested work-check acceptance
and publication/no-clobber behavior. Invented sentinels and snapshot identities
remain absent from public output and errors.

An independent reviewer passed all **37 focused tests** (14 address-shape,
12 reference-summary and 11 module-summary tests), round-tripped all three
historical work-check reports unchanged and probed chained aliases,
qualification/dynamic/overlength exclusions, empty input and 1/100/1,000 repeated
occurrences. Output cardinality remained fixed. Review corrected an unnecessary
test edit so private schema 3 remains explicitly rejected while public schema 3
is accepted. No blocking findings remained.

The actual `bash ./run-work-check.sh` launcher also passed in a disposable
checkout with a local bare Git remote and independently invented XML. The
temporary candidate commit was `4a98e402a244acbc2be55cb0193fa5fd341d66da`;
its implementation/test blobs match this change. This local-only validation
commit is not a GitHub revision or a work-machine result. The runner pulled,
ran all 246 application tests (one skip) and 139 helper tests, saved the private
bundle and pushed an 8,214-byte aggregate-only commit to that disposable remote.

Assertions verified work/reference/source schemas 1/3/3, private manifest,
inventory and reference schemas 2/2/2, clean tested-commit provenance, all saved
artifact hashes, unchanged source bytes, remembered source selection and absence
of invented names, values, source path and source hash from the public report.
The histogram had two alias-target occurrences and one in each remaining bucket
(eight total); a separate dynamic-index occurrence stayed outside it. The saved
remote JSON was independently read back and compared with the validated local
report. Parent commit, report-only changed path, clean worktree and matching
local/remote tips were checked; exit 0 alone was not treated as proof.

These checks validate the synthetic diagnostic/publication boundary. They do
not classify any of the 868 real-source occurrences or verify Studio import,
engineering meaning or the contents of a real private run.

## Next work-machine action

Run `bash ./run-work-check.sh` once on the existing branch. It pulls the change,
tests, analyzes the remembered local export and pushes only the aggregate report.
No additional listener installation, raw files or terminal logs are needed.

Validate the new report and tested revision first. Compare existing statuses,
reasons, source counts and coverage with this baseline; no binding improvement is
expected from the diagnostic itself. If the same malformed-address population
remains, its seven counters must sum to 868. Review any changed population before
interpreting the distribution. A nonzero bucket indicates only its stated
observation. Use returned evidence and independent documentation before selecting
a bounded syntax change. If the buckets cannot resolve the question, record a
specific work-machine investigation and stop. Phase 1 remains active.
