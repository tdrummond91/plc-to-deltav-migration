# Embedded review guide and report presentation

Updated 2026-10-19. Tyler requested a page in the review HTML explaining what
to check and how to answer, with developer details available through `--debug`.
This is C16, a requested presentation refresh after C14 source-analysis closure
and C15 cleanup acceptance. The prior fifteen completed cycles remain closed.
C16 is now accepted from return `23d073d`, testing clean `07a935c`. Sixteen
cycles are complete and no further unchanged-source run is needed before review.

## Reviewer experience

**Review guide** is available from the left navigation and Overview. It contains:

- A short explanation of the review purpose and how to navigate evidence.
- Nine expandable subject checklists, each with specific checks, response
  guidance and links to the sections available in that report.
- Definitions of **Checked**, **Needs correction**, **Evidence missing** and
  **Not applicable**, with **Not reviewed** reserved for unchecked items.
- A glossary covering source evidence, candidate interpretations, unresolved
  status, bindings, guards, common instruction terms and process acronyms.
- A selectable feedback template and an illustrative completed correction.

**Prepare review feedback** on a detail page opens the guide with the selected
record, source snapshot and relevant instruction/content context. A return
button restores the selected record. Direct guide navigation starts without a
selected item. The template is read-only: reviewers copy it into their review
notes, supply the observed and expected results or missing evidence, and return
those notes through their agreed process. The report does not save, submit or
carry decisions across exports. Complete source scans and successful bindings
are explicitly distinguished from engineering approval.

The generated reviewer instructions contain no development attribution or
narrative about acquiring occasional source examples. Existing source wording
is preserved. In particular, `AI` still means analog input where used as a
process-control abbreviation; it is not indiscriminately removed.

## Normal and debug presentation

Normal HTML retains engineering evidence, source comments and attributes,
snapshot/record identities, candidate reasons, coverage, limits and uncertainty.
Its embedded JSON omits only the known generated metadata described below.
This omission is a presentation projection, not merely a hidden UI panel.

`render_review_html` validates the original canonical model and enforces its
size limits before projection. `_presentation_data` removes `report_version`,
`parser_version`, `analyzer_version`, `catalog_version` and `tool_revision` at
the top level and the explicitly enumerated provider envelopes where present.
It also removes `rule_id` and `rule_version` from rung-analysis candidates.
It does not recursively rewrite source attributes, comments or similarly named
source fields. Schema discriminators, source snapshot and record IDs remain.

`plc review --debug` and `run-work-check.sh --debug` select diagnostic HTML with
the exact canonical payload and the developer version/rule panels. The guide
is available in both modes. Canonical evidence JSON, final manifests, analysis
schemas and rules, summary contracts and sampling behavior are unchanged.
Normal HTML is not canonical input for regeneration because its implementation
versions are omitted; regenerate from the saved model/evidence or source fixture.

The new `review_assets/review_guide.js` asset is combined with `report.js` in
the existing hash-authorized executable script. CSS retains the existing dark
theme and adds readable checklists, response cards, template and narrow-screen
layout. The report stays offline with no server, form submission or external
script dependency. Text is added through the existing safe DOM helpers.

## Workflow and boundaries

For future requested checks, the work-PC sequence remains manual:

```bash
git pull
bash ./run-work-check.sh
git push
```

The script creates its validated feedback commit locally. It performs no
fetch, pull or push and enables no listener. For diagnostic HTML, replace the
middle command with `bash ./run-work-check.sh --debug`; an optional source path
can follow the flag. The standard run produces the normal reviewer report.

The requested regeneration is complete. Synchronize `main` with `git switch
main` and `git pull --ff-only`, then open the existing `review.html` saved by
completed check `20261019T201714Z-38434b5f`. Use its printed private-report path
or the newest completed workspace folder; the folder name can differ from the
check ID. Proceed to the walkthrough and official engineering review. Keep
the reviewed report and its neighboring evidence artifacts together.

## Validation

- Final UI and debug-argument boundary group: **50 passed** in 70.886 seconds.
  Modules: `test_review_guide_ui`, `test_rung_analysis_review_ui`,
  `test_binding_context_review_ui`, `test_control_interpretation_ui`,
  `test_engineering_assemblies_rack_ui`, `test_residual_navigation_ui`, plus
  `test_work_check_bootstrap.WorkCheckBootstrapTests.test_uses_local_checkout_without_pulling_and_preserves_argument_boundaries`.
  These cover normal/debug presentation, response guidance, record context,
  SFC content selection, return navigation and `--debug` argument forwarding.
- Independent code review: **no remaining blockers**. The reviewer ran 40
  presentation, guide, HTML-boundary and rung UI cases, plus checks for empty
  collections, page-two return navigation, hostile source markup and default
  or stale SFC selection context. The final SFC regression is committed with
  the guide tests.
- Audited work-machine selection: **2,122 application cases, two expected
  skips; 139 helper cases, no skips; zero failures or errors**. Application
  runtime was 1,015.612 seconds. Both selections ran through
  `work_check_tests._load_work_machine_suite` and `run_suite` with process,
  socket and connection guards; none of those guards was invoked.
- Browser verification: default guide, expandable checklists, read-only
  template selection and completed example checked; no console errors observed.
  Both current invented demonstrations were regenerated with the guide.
- Historical compatibility: all **62** work reports under schemas 1-53 passed
  their versioned size limits, closed validation and exact-byte replay; frozen
  history acceptance also passed under process/socket guards.
- Repository checks: all 308 local link targets in the 14 updated documents
  resolve, staged changes pass `git diff --check`, and the work-script and
  Python CLI help expose the optional `--debug` flag. Only intended code,
  tests, documentation and invented demonstrations are staged.
- Private C16 work-PC return: **accepted**, as detailed below.

## Accepted C16 return

Return `23d073d4ee7f1dd8b59966feb8878a4d0753c237` contains
[`work-check-20261019T201714Z-38434b5f.json`](../../inspection/work-check-20261019T201714Z-38434b5f.json),
88,955 bytes under schema 53. It tested clean
`07a935cdac26e525ac312038718ade041157ff5d`: 2,122 application cases with two
expected skips, 139 helper cases, and no failures or errors. The private run
saved successfully with no failure code.

All 29 analysis summary families match C15 `d53e1ee` after removing only
`tool_revision`. Complete `targeted_samples` and `diagnostic_sample` envelopes
match exactly. All 64 retained reports pass their versioned caps, closed
validation and exact serialization; the unchanged frozen record is accepted
by the history reader under process/socket guards. The count includes the
62 previous feature reports, C16 and the earlier main-only report preserved
during history consolidation.

Code, tests, tools, report assets, demonstrations, fixtures and script blobs
in the final consolidated review-guide milestone match the tested feature checkpoint.
No application-suite rerun was needed for carrying the report and documentation
into the consolidated history. The private HTML was not visually inspected
here; browser verification above used invented reports.

| Work-PC phase | Duration |
|---|---:|
| Application tests | 428.759 s |
| Helper tests | 0.362 s |
| Source analysis | 213.112 s |
| Private save | 246.879 s |
| Summary | 210.229 s |
| Sample handling | 0.208 s |
| Total check | 1,100.148 s (18m 20.148s) |

These timings describe this run and do not establish a performance trend.
The completed C14/R3/R4 gate and C15 cleanup remain closed. No new source
example was introduced or requested. The next step is human report review.

The [tracker](../planning/PRE_TEAM_REVIEW_TRACKER.md) records completion and the
[work-PC instructions](WORK_MACHINE_REFERENCES_RUN.md) describe synchronization
and finding the saved report.
The [reading guide](REPORT_REVIEW_GUIDE.md) explains the reviewer workflow.
