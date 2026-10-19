# Timer placeholder recognition

Date: 2026-10-14. Baseline: `349ee29`, on `feat/bounded-operand-example-pc`.
This Phase 1 reference-analysis follow-up is confirmed by the work-machine
report returned in `1195d40`.

## Returned evidence

The [returned work check](../../inspection/work-check-20261014T075024Z-a11d87b8.json)
tested clean `2851dbd840f93217290a9f211e41417bb6337460`. Its report-only commit
`349ee29` has that revision as its parent. Both suites passed: 166 application
cases (one skip) and 139 helper cases, with no failures/errors. Private analysis
was saved; its partial status and aggregate counts are unchanged from the prior
report after removing only the tested revision.

Its authorized sample is exactly `?` at zero-based argument 1 of `TON`. The
aggregate still reports 868 malformed operands, all `other_form`. It also counts
390 TON and 44 RTO instructions; twice their sum is 868. This supports testing a
timer-slot rule, but one sample does not prove all 868 occurrences have that form.

[Rockwell's import/export reference](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf)
(1756-RM014D-EN-P, printed pages 220-221) documents the timer, preset and
accumulator slots for RTO, TOF and TON. It does not document the `?` token there.
[Rockwell's release notes](https://compatibility.rockwellautomation.com/GeneratedReleaseNote.aspx?v1=65258)
(L5X import anomaly 3174411/3174415/3174418/3161896) describe Logix inserting `?`
for a missing operand. This supports its placeholder interpretation, not a claim
that a timer's configuration is valid or that the placeholder supplies a value.

## Narrow behavior and limits

For catalogued three-argument TON/TOF/RTO instructions only, exact trimmed `?`
in slots 1 or 2 becomes `non_data`: no standalone address lookup is needed.
Original operand text and snapshot/instruction/rung links remain in private
records. No preset/accumulator value, member validity, datatype or effect is
inferred. A complete root-binding result still does not validate timer settings.

The root slot, other instructions, alias targets, wrong arities, empty slots and
near-miss spellings retain existing behavior. Quoted question marks stay literals.
The address grammar itself remains unchanged. A global `?` literal/address rule
was rejected because it would hide unrelated missing operands.

Known timer placeholders are skipped by mystery-sample selection; a later eligible
malformed operand can be selected instead. Historical samples remain readable.
For current schema-4 reference reports, publication also rejects a forged sample
that labels a known timer placeholder as malformed, even if another malformed
operand supplies a positive aggregate count.

| Artifact | Current contract |
|---|---|
| Private inventory | Schema 2 / `source-inventory-2` |
| Private references | Schema 2 / `source-references-3` |
| Private reference-run manifest | Schema 2, records the new analyzer version |
| Source aggregate | Schema 3 / `aggregate-summary-3` |
| Reference aggregate | Schema 4 / `reference-summary-4` / `source-references-3` |
| Work-machine report | Schema 2 / `work-check-2` |

Reference schema 4 changes analyzer provenance, not the field layout or approved
sharing boundary. Exact historical reference schemas 1/2/3 and work-check schemas
1/2 remain readable; non-null work samples require reference schema 3 or 4.
This is public-report compatibility, not migration of saved private runs.
New private runs are separate; older runs are never rewritten.

## Original work-machine check (completed)

Stay on `feat/bounded-operand-example-pc` and run from the repository root:

```bash
git pull &&
bash ./run-work-check.sh
```

Review the new feedback, then run `git push`. The runner commits only the report
locally; it never fetches, pulls or pushes. The listener remains disabled and
excluded from tracked code and work-machine tests.

Compare the result with the returned baseline above. For each recognized slot,
`non_data` should increase by one while malformed-address, `other_form` and
unsupported-address counts each decrease by one. Source totals, root-bound
counts and alias outcomes should remain unchanged for the same export.
If all 868 are covered, expected totals are `non_data=868`, malformed=0 and
unsupported-address=2 (the existing dynamic-index cases). The sample should then
be null unless another eligible malformed occurrence remains. These are
conditional expectations before the return below. Other gaps keep
the report partial; Phase 1 is not complete.

## Work-machine confirmation (2026-10-14)

[The new report](../../inspection/work-check-20261014T162634Z-2a7e40fe.json),
returned in `1195d40`, tested clean `112ee82e5cdc284534c31c428dfe75f1c38a8a33`.
The report validates; its commit changes only that JSON, with the tested revision
as its parent. Both suites passed: 177 application cases (one skip) and 139
helper cases, without failures/errors. Private output was saved.

| Reference counter | Before | Returned |
|---|---:|---:|
| Malformed-address operands | 868 | 0 |
| `other_form` shape | 868 | 0 |
| `non_data` operands | 0 | 868 |
| Unsupported-address operands | 870 | 2 |
| Root-bound operands | 20,178 | 20,178 |
| Unresolved operands | 320 | 320 |
| Bound aliases | 842 | 842 |
| Unresolved aliases | 99 | 99 |

The diagnostic sample is null. Apart from analyzer/exporter/schema provenance,
the three disposition/reason changes and shape change above are the only changes
to the nested aggregate after removing the tested revision. Source counts,
coverage, instruction totals, ladder metrics, symbols and module naming match
exactly. This confirms the predicted 868-occurrence classification improvement
for the returned export; aggregate equality does not establish source byte
identity or per-occurrence correspondence between runs.

The remaining two unsupported addresses are non-static array indexes. Other
reference gaps remain: 320 unresolved operand occurrences and 99 unresolved
aliases (all `colon_root_not_declared`), 45 expression operands and 653 operands
of unsupported instructions. Alias and operand counts describe different
populations and must not be added as independent plant defects. Source gaps
still include 14 unsupported SFC routines and one RLL routine lacking content.
The expected partial status remains; timer settings/effects are still unverified.

No repeat work-machine run is needed to confirm this fix. The next Phase 1
investigation is the undeclared colon-root population and its possible relation
to rack I/O. Existing shared XML structure records 11 RackConnection elements,
11 InAliasTag and four OutAliasTag children, with no attributes/text on those
elements. The reader currently counts these paths and emits rack diagnostics,
but does not create structured rack declarations. Minimized surrounding port
identifiers/types were scrubbed and do not prove topology relationships.
This is enough evidence to design dedicated structural capture using coherent
invented tests, but not to invent rack naming/alias targets or explain all
99/320 missing roots. Check the official format before expanding root binding.

The follow-up [rack-I/O investigation](RACK_IO_INVESTIGATION.md) now reproduces
that declaration omission with invented data and records the official format
basis. It recommends dedicated evidence and candidate matching before changing
bindings; the actual 99/320 population remains unassigned.

Independent review verified the report, exact count deltas and Git provenance.
This return review changed documentation only; no full test suite was rerun.
The implementation checks below remain their original evidence.

## Validation

The full application/workflow suite passed 273 tests (one existing Windows
symlink skip), excluding the ignored listener loader before import. Ten timer
cases exercise all six slots, root/alias exclusions, arity, literals, raw evidence,
version/canonical validation and count-only summaries. Sample/publication cases
cover skipped known slots, remaining malformed text, forged current samples and
unchanged historical feedback. Independent review found two integration issues
(a test's return-shape assumption and schema-4 sample validation); both were fixed
and the reviewer confirmed no remaining blockers.

Two real CLI runs in a disposable checkout with an unreachable local origin each
passed 177 selected application cases (one skip) and all 139 helper cases. The
first source contained three timers with six placeholders and emitted no sample;
the second added one invented malformed operand and emitted only that operand.
Both emitted work/reference/source schemas 2/4/3, bound the three timer roots and
counted six non-data slots. Each committed only its report with the tested SHA as
parent and left clean main. The second run reused the remembered source. Private
runs preserved six raw question marks, reference schema 2/analyzer 3 and manifest
schema 2. Source bytes and prior reports were preserved.

All six stored work reports and stored reference summaries validate unchanged.
The full suite was run from the root using:

```bash
uv run --project python-parser --locked python -B - <<'PYTEST'
from pathlib import Path
import sys, unittest
folder = Path.cwd() / 'python-parser/tests'
sys.path.insert(0, str(folder))
loader = unittest.TestLoader()
suite = unittest.TestSuite(
    loader.loadTestsFromName(path.stem)
    for path in sorted(folder.glob('test_*.py'))
    if path.stem != 'test_feedback_listener'
)
result = unittest.TextTestRunner(verbosity=1).run(suite)
raise SystemExit(not result.wasSuccessful())
PYTEST
```

The CLI exercise invoked `python -B -m plc_workbench.work_check` from its temporary
checkout, first with the invented source path and then with remembered selection.
It used the checked-out module via PYTHONPATH and separate temporary Git identity.
No private plant source, listener or actual work-machine execution occurred here.
