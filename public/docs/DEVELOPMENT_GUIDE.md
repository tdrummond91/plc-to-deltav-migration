# Development guide

Start with the [current handoff](../CODEX_HANDOFF.md) and
[tracker](planning/PRE_TEAM_REVIEW_TRACKER.md). The application produces
source-backed reports; actual plant exports and complete results remain on the
work PC. Local development uses invented fixtures, validated returned counts
and the existing bounded examples.

## Find the code

| Area | Entry point |
|---|---|
| CLI arguments and command orchestration | [cli.py](../../python-parser/src/plc_workbench/cli.py) |
| Captured source and inventory | [source.py](../../python-parser/src/plc_workbench/source.py), [models.py](../../python-parser/src/plc_workbench/models.py) |
| Engineering report composition | [review.py](../../python-parser/src/plc_workbench/review.py) |
| Private artifact saving and manifests | [storage.py](../../python-parser/src/plc_workbench/storage.py) |
| Offline HTML and interaction | [review_html.py](../../python-parser/src/plc_workbench/review_html.py), [report.js](../../python-parser/src/plc_workbench/review_assets/report.js), [report.css](../../python-parser/src/plc_workbench/review_assets/report.css) |
| Embedded reviewer instructions and feedback template | [review_guide.js](../../python-parser/src/plc_workbench/review_assets/review_guide.js) |
| Work-PC check, validated feedback and local commit | [work_check.py](../../python-parser/src/plc_workbench/work_check.py) |
| Work-report size/serialization policy | [contracts/work_reports.py](../../python-parser/src/plc_workbench/contracts/work_reports.py) |
| Audited work-PC tests and bounded test result | [work_check_tests.py](../../python-parser/src/plc_workbench/work_check_tests.py) |
| Supporting inspection tools | [tools/l5x_inspect](../../tools/l5x_inspect/README.md) |

The [source module map](../../python-parser/src/plc_workbench/README.md) groups
the analysis layers by responsibility. Existing module paths remain stable;
there is no requirement to read every file to change a single layer.

## Local commands

Run in Git Bash from the repository root, with Python 3.12+ and `uv` available:

```bash
uv run --project python-parser --locked plc --help
uv run --project python-parser --locked plc review \
  public/fixtures/synthetic/control_interpretation_demo.L5X \
  --workspace confidential/workspaces/synthetic-review
```

The invented report can return exit 3 for deliberately partial source coverage.
Read the saved status and manifest before treating that as a failure. New runs
have unique directories; no earlier run is overwritten. The
[application README](../../python-parser/README.md) maps all CLI commands.

Add `--debug` to the `plc review` command when checking generated version and
rule diagnostics. Normal HTML uses a presentation projection that omits only
known implementation metadata; debug HTML retains the canonical review
payload. Both retain source evidence, uncertainty, source/record IDs and the
same review guide. Canonical evidence JSON and manifests are unchanged.

The renderer validates canonical input before making that projection. Do not
extract the payload from normal HTML and treat it as a canonical input for
regeneration: it deliberately lacks required version metadata. Rebuild from
the saved evidence/model or the source fixture. `review_guide.js` is bundled
with `report.js` into the existing offline, hash-authorized script; it does not
add a server or network dependency. See the
[implementation record](reviews/REVIEW_GUIDE_IMPLEMENTATION.md).

## Test the changed boundary

For the shared work-report policy:

```bash
uv run --project python-parser --locked python -B -m unittest discover \
  -s python-parser/tests -p test_work_report_contracts.py -v
```

For a different layer, select its explicit test filename and related workflow
tests. `test_*_summary.py` verifies bounded publication; `test_*_workflow.py`
usually checks composition, validation and saving. Report UI/DOM cases use
invented data and may require Node.js. A skipped optional UI test is not proof
that the rendered behavior works; inspect a generated report when changing UI.

For the full development application suite, explicitly exclude the optional,
ignored listener loader:

```bash
uv run --project python-parser --locked python -B - <<'PY'
from pathlib import Path
import sys
import unittest

folder = Path.cwd() / "python-parser/tests"
sys.path.insert(0, str(folder))
suite = unittest.TestSuite(
    unittest.defaultTestLoader.loadTestsFromName(path.stem)
    for path in sorted(folder.glob("test_*.py"))
    if path.stem != "test_feedback_listener"
)
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
PY
uv run --project python-parser --locked python -B -m unittest discover \
  -s tools/l5x_inspect/tests -v
```

The full development suite includes process/Git fixtures and optional UI cases.
The work PC instead uses the reviewed module allowlists and exclusions in
`work_check_tests.py`, selected by `run-work-check.sh`. Review new test modules
before adding them to that selection. Test counts can differ between these
scopes; record the exact command and result rather than comparing counts alone.

## Keep changes traceable

- Fetch before analysis and before an authorized push. Inspect status and
  upstream divergence; preserve local changes. Use a focused `-pc` branch and
  conventional commits with a clear rationale and validation record.
- Keep captured facts, analysis candidates and human decisions separate.
  Preserve source/record links and explicit uncertainty. A supported source
  association does not prove execution, physical I/O or process purpose.
- Treat historical report versions as replay contracts. Preserve canonical
  bytes, size limits, validators, artifact hashes and old reader behavior when
  refactoring. The shared contracts package handles layout/size policy only;
  semantic validation still belongs to the relevant layer and work-check.
- Keep private artifacts and validated shared summaries separate. A new field
  must pass its closed validator and approved data boundary. Preserve the
  frozen sample history; do not regenerate examples merely to simplify a test.
- Keep the work script's Git transport manual. Its local feedback commit is
  intentional; no fetch/pull/push or background listener belongs in that flow.
- Update the tracker, current handoff and the relevant review record after a
  completed change or returned run. Put historical investigation details in the
  review record, keeping the current entrypoints focused on the next action.

See [data contracts](planning/DATA_CONTRACTS.md),
[scope and phases](planning/ROADMAP.md), [architecture](planning/ARCHITECTURE.md)
and [confidentiality](planning/CONFIDENTIALITY.md). Older design pages contain
dated proposals; use the current handoff and implemented contracts to distinguish
what exists today from future editable-record/PCSD/FHX work.
