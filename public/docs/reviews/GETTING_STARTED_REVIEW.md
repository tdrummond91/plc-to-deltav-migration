# First-use path and report themes

Implemented 2026-10-21 on `feat/getting-started-pc`.

Open the root [START-HERE.html](../../../START-HERE.html) for a short first
session: understand the current Phase 1 deliverable, try one invented report
item, then find a familiar item in the already saved private report. Technical
documentation and subject-specific learning topics are optional disclosures.
No new work-PC parser run is required.

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
