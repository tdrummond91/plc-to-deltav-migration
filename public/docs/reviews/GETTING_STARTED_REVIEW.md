# First-use path and report themes

Implemented 2026-10-21 on `feat/getting-started-pc`.

Open the root [START-HERE.html](../../../START-HERE.html) for a short first
session: understand the current Phase 1 deliverable, try one invented report
item, then find a familiar item in the already saved private report. Technical
documentation and subject-specific learning topics are optional disclosures.
No new work-PC parser run is required.

The follow-up walkthrough puts links, specific tasks, expected observations and
completion checkboxes together in four ordered lessons. The same progress IDs
are retained. Each optional learning subject also has a report link. A local
Windows path selector lets the user point the links at their existing unit
report without reading or uploading it. Paths are saved separately from progress
and excluded from exports. Older reports without fragment support use the
explicit sidebar fallback; the current demos and new reports open directly to
the selected section or known source record. Unknown, malformed and oversized
fragments are ignored, including ordinary anchors such as `#main`.

## Behavior and boundaries

- Four orientation checkpoints and seven optional subjects track personal
  learning. They do not record engineering review decisions or approvals.
- Progress is stored in the current browser. Export/import uses a closed,
  versioned JSON format containing only fixed checkpoint IDs, limited to 8 KiB.
  Imports merge completed checks. Storage failures leave checks usable for the
  current visit and prompt a backup. Before changes or exports, the page reads
  newer saved checks and preserves any local changes that could not be saved.
- The start page and new reports have a light/dark toggle. Existing report dark
  colors remain the default. Theme storage is optional; blocked storage cannot
  disable report navigation. Saved private HTML is not rewritten by a Git pull.
- The two current invented demonstrations were rendered from their retained
  canonical synthetic models. Their complete embedded normal evidence payloads
  are unchanged. No parser, sampling, work-check or private-data changes apply.
- [D034](../planning/DECISIONS.md) and the
  [architecture](../planning/ARCHITECTURE.md#team-class-library-constraints-confirmed-2026-10-21)
  retain Tyler's class composition, alarms, equations and timer/DC constraints
  for later mapping. Source classification does not assign a target class.

## Validation

Linked-walkthrough follow-up: 75 focused tests passed (21 onboarding tests and
54 report/link/guide/theme/presentation/rung tests). New coverage exercises every
linked demo destination, the exact MOV example, path quoting/encoding/rejection,
selection restoration, export privacy, storage failure and strict fragment
navigation. Final independent code review found no blockers. Chrome confirmed
the guide and specific rung destinations, checkbox persistence, and local-path
retargeting/restoration. Only invented paths were entered; no unit file was read.
Both refreshed demo evidence payloads still match their previous complete payloads.

```bash
PYTHONPATH='python-parser/src;python-parser/tests' python-parser/.venv/Scripts/python.exe -m unittest \
  test_start_here_ui test_review_links test_review_html test_review_guide_ui \
  test_review_theme test_rung_analysis_review_ui test_review_presentation
```

Original first-use implementation validation:

- 13 onboarding tests passed: local resources and links, accessible checkpoint
  labels, counts, next actions, persistence, bounded import validation, export,
  storage failures and preservation of changes made in another tab. Regression
  coverage includes both unsaved checks and unchecks when reads work but writes
  fail. Independent final code review found no remaining blocking issues.
- 56 focused report tests passed across theme, HTML, guide, presentation and
  navigation behavior. Theme tests include blocked storage and 22 contrast
  combinations. Evidence payload preservation was checked for both refreshed
  demonstrations.
- Chrome checks used an isolated localhost copy containing only public
  onboarding assets and the two invented demonstrations. Dark/light rendering,
  theme restoration, saved checklist restoration and the practice link passed.
  The report path passed through Review guide, Engineering analysis, a rung,
  PID evidence, Back, and Prepare review feedback with the selected record ID.
  Existing private reports were not inspected or modified.
- JavaScript syntax checks and `git diff --check` passed. The full parser and
  helper suites were not repeated for this presentation/documentation change.

To repeat the 69 focused tests from the repository root in Git Bash with the
existing Windows Python environment:

```bash
PYTHONPATH='python-parser/src;python-parser/tests' python-parser/.venv/Scripts/python.exe -m unittest \
  test_start_here_ui test_review_theme test_review_html test_review_guide_ui \
  test_review_presentation test_access_review_ui test_control_interpretation_ui \
  test_engineering_assemblies_rack_ui test_residual_navigation_ui
```

Learning progress is browser-local and is not a Git-tracked project record.
Export it before moving browsers/computers or clearing browser storage.
