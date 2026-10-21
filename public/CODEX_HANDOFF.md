# Current handoff: PLC analysis workbench

## Active implementation: editable engineering workspace (2026-10-21)

The previous report-only handoff below is superseded. Tyler needs structured
recategorization and saved engineering corrections before meaningful review;
copying text feedback was not an acceptable substitute. Development branch:
`feat/engineering-workspace-pc`, based on the prior onboarding branch.

Tyler's primary entry point remains **`bash ./run-work-check.sh`**. It runs the
existing tests and L5X analysis, verifies its local feedback commit, then imports
that exact completed run into the selected editable project and opens the
browser at `http://127.0.0.1:8745`. Complete and partial analyses can proceed;
failed checks cannot import an older result. Saved corrections remain in the
project, with changed evidence flagged for revalidation. The terminal stays
occupied until **Close workspace** or Ctrl+C. Git synchronization remains manual.

`bash ./open-workbench.sh` is an optional shortcut to reopen saved work without
analysis; `Open-Workbench.cmd` is the optional double-click equivalent. Do not
replace the established work-check command with a separate mandatory import
workflow. Existing completed runs can still be chosen manually, including after
an editor launch failure; another 18-minute parser run is unnecessary for that.

Implemented: program/routine navigation; complete rung text/comments and a
series/parallel structural diagram; every instruction/operand and linked
source evidence; editable category registry, many-to-many engineering groups,
structured properties and review status; bulk changes that preserve omitted
fields; reusable category proposals based on exact opcode/branch patterns;
SQLite revisions/history, stale-save rejection, undo, changed-source explicit
correspondence, portable backups and restore-as-new-project.

Source facts, parser proposals, project rules and reviewed decisions stay
separate. The editor changes the engineering model, not executable L5X.
Class allocation, PCSD/FHX generation and packaged reviewer distribution
remain later deliverables. Source-dependent uncertainty is not an approved
engineering purpose. Read the [workspace guide](docs/reviews/ENGINEERING_WORKSPACE.md)
for the implementation boundary and concrete operating steps.

Validation completed on invented sources: 121 focused feature/presentation
tests passed. A separate 116-test regression command passed with one expected
skip; its boundary tests executed the complete audited work-PC application and
helper suites while denying subprocess/socket access. The final presentation
follow-up passed 56 tests, including current manifest-38/report-35 import.
Independent review ended with no blockers.

Chrome verification covered 105 rungs / 234 instructions, all three pages,
source text/comments, category and property saves, group membership, a rule
with 104 exact-pattern matches, reopen, complete backup/restore into a new
project, a post-restore save, source-report round-trip links, light/dark themes
and clean shutdown. Adding a rule preserves categories/properties and marks
affected saved reviews for revalidation. No private report has been opened
here. The first actual work-PC import/editing walkthrough remains outstanding;
do not equate synthetic validation with accepted team usability or source
engineering approval.

Launcher follow-up: the work-check script's original-checkout check compared
path strings and could reject a correct Windows checkout when capitalization
differed. It now compares filesystem identity; copied launchers below the
repository root still fail before invoking the parser. This message belongs
to `run-work-check.sh`, not the editor launcher. The Bash editor launcher has
also been checked directly with `--help` through the existing uv environment.

Single-command follow-up validation: 8 exact-run handoff tests, 26 workspace
tests, 17 onboarding tests, and 58 work-check/presentation tests passed. Four
focused Bash bootstrap regressions passed, including Windows path capitalization,
copied-launcher rejection and argument forwarding; argument forwarding passed
again after adding the workspace flag. The new handoff tests cover finalized
manifests, partial results, failed saves/checks, verified local commits and editor
failure recovery. Workspace tests cover occupied ports before import, preserved
restored-project selection and invalid selection files without fallback writes.
Independent review found no blockers. Both the Bash launcher and direct
work-check CLI require the repository root before selecting the local project.
These are focused follow-up checks; the broader suites above preceded this wiring
change. The actual work-PC source and editing walkthrough remain to be checked.

## Equation presentation follow-up (2026-10-21)

Rung detail now opens with an **Equations** tab above the engineering review.
Native offline MathML displays CPT expression trees, arithmetic and comparisons;
**Branch structure** retains instruction-fragment selection, and **Original text**
retains the complete captured source. Unsupported/stateful instructions remain
named calls. No branch is algebraically collapsed, no expression is evaluated,
and no review decision or database schema changes for this display.

The source-detail API exposes only the selected instruction/rung's calculation
syntax. Saved syntax is authenticated against the existing bounded CPT grammar,
without rebinding addresses or rerunning L5X analysis. Missing/corrupt optional
evidence retains a readable original-instruction fallback. Run selection and
restored projects invalidate the presentation cache. This also works with
already imported runs after restarting the updated workspace.

Validation: 9 new projection tests and 26 existing workspace tests passed;
11 new typesetting/interaction tests and 17 existing workspace UI tests passed.
Chrome verified fractions, radicals, left-associated powers, literal unsupported
calls, separate branch paths, original text, keyboard tab navigation and both
themes on invented source. Read-only viewing left the project revision unchanged.
Independent review found no blockers. The saved preview is local and ignored at
`confidential/equation-preview/equations-verified.png`.

## Connected rung views and signal tracing (2026-10-21)

This supersedes the equation-only presentation above. The previous inventory
still displayed raw instructions and opened an empty detail pane; it did not
provide the connected rung-to-rung exploration Tyler requested. Rung inventory
now previews two typeset instructions with explicit remaining-instruction and
branch counts. An untouched empty detail pane selects the first result; pending
manual/deep-link selections, unsaved forms and view changes take precedence.

The default **Rung flow** tab uses connected SVG wires and mathematical HTML
cards. Nested branches, downstream joins and empty bypasses preserve captured
topology. Zoom and scrolling expose longer rungs. Malformed, excessive or missing
structure falls back to the complete original text with an explanation; it is
never silently flattened. **Equations**, **Branch structure** and **Original
text** remain available. Local contact/coil notation explains incoming `EN`;
stateful and unsupported operations retain named calls. Redundant expression
fences were removed without altering precedence or explicit grouping.

**Explore inputs & outputs** opens the **Connection map**: known writer rungs,
exact signals, focused rung, written signals and reader rungs. Select a signal
to expand fan-out, click another rung to refocus, and use **Back in trace** to
return to the prior signal/page. Routine/direction filters, signal pagination,
endpoint pagination, zoom and source-detail links are implemented. Signal details
retain competing writers, same-rung reuse, unknown-role neighbors and known
neighbors of unknown-role uses. No directed edge is invented through an unknown
role. Coverage gaps and scope exclusions are explicit.

`workspace_connections.py` validates stored companions once per imported run,
then serves an in-memory exact-address index. Alias expansion, scoped identities
and literal member/index suffixes remain distinct. Authentication uses captured
inventory and bounded derivation of references, access roles and CPT syntax;
there is no L5X read or full pipeline replay during navigation. Missing, repeated,
oversized or inconsistent evidence fails to an unavailable panel while source
records stay accessible. Import and restore invalidate the index and map focus.
No database schema, reviewed decisions, parser classification or work-machine
Git synchronization behavior changed.

The work-PC screenshots also showed an aborted report response followed by an
attempted second response. Response disconnects now close quietly, and request
body disconnects stop before mutation. Storage failures still report controlled
errors. The cause of the original Windows connection abort was not established.

Validation: all **143 workspace tests** passed in the final discovery run;
the **8 work-check workspace handoff tests** also passed. Tests cover real
synthetic parser topology, physical split/join geometry, exact identities,
multiple writers, cycles, unknown roles, fan-out/pagination, authenticated
companions, cached navigation, corrupted evidence, selection races, MathML,
safe DOM construction and response disconnects. Independent review ended with
no blocking findings after direction-filter and unknown-neighbor regressions
were added. These are focused development checks, not a new full work-PC run.

Chrome verification used a separate invented 17-rung export: branch equations,
12-reader fan-out across two pages, consumer refocus, trace-back restoration,
scope/direction controls, light/dark themes, return to exact rung and clean
shutdown. The project stayed at revision 1. No application console errors were
observed; unrelated extension warnings were present. Local ignored proofs:
`confidential/connection-preview/rung-flow-verified.png` and
`confidential/connection-preview/connections-verified.png`.

Work-PC next step: close the current workspace, pull this branch manually, then
use `bash ./open-workbench.sh` to reopen the saved project. Current completed runs
already carrying the required companions need no new analysis. The usual
`bash ./run-work-check.sh` remains the complete test/analyze/open workflow when
a fresh run is wanted. Actual plant-scale map performance and engineering
interpretation still require Tyler's local walkthrough.

## Prior analysis and report history

History cleanup: `main` contains eight consolidated milestones above the prior
baseline. The review-guide milestone includes the accepted C16 return and
history-cleanup notes. Completed branch names and iteration archive tags are
retired. The [history map](docs/reviews/HISTORY_CONSOLIDATION.md) records original
checkpoints, preservation checks and the work-PC synchronization procedure.

Updated 2026-10-21. First-time users start with
[START-HERE.html](../START-HERE.html): a short orientation, invented practice
report and fixed learning checkpoints. Each task now contains direct report
links, explicit instructions and its own completion checkbox. An optional
drive-qualified local report path retargets section links; that path is stored
only in the browser and never included in progress exports. Older private HTML
uses the explained sidebar fallback. New reports accept bounded section/source
fragment links while preserving internal Back navigation.
Progress is local to the browser with
bounded JSON export/import; it is not engineering review state. The start page
and newly generated reports include a light/dark switch. Existing private HTML
does not change merely by pulling this presentation update. No work-PC parser
run is needed to begin learning or use the accepted saved report.
The [first-use implementation record](docs/reviews/GETTING_STARTED_REVIEW.md)
contains the progress-storage contract and focused validation evidence.

Tyler's class-library composition constraints are recorded in
[decision D034](docs/planning/DECISIONS.md) and the
[future conversion boundary](docs/planning/ARCHITECTURE.md#team-class-library-constraints-confirmed-2026-10-21).
PID, alarm, equation and timer classifications are source interpretations,
not one-to-one target class assignments. Mapping and split/merge implementation
remain later work. For development status, start with the
[tracker](docs/planning/PRE_TEAM_REVIEW_TRACKER.md), then the
[readiness assessment](docs/reviews/PHASE_1_READINESS_REVIEW.md).

## Current state

Phase 1's fourteen analysis cycles, C15 cleanup and C16 review-guide refresh
are validated: sixteen completed cycles, zero further unchanged-source runs
before review. C16 return `23d073d` tested clean `07a935c`: 2,122 application
cases with two expected skips, 139 helpers and a successful private save
without a failure code. All 29 analysis summary families match C15 `d53e1ee`
after removing only `tool_revision`; the complete frozen sample and diagnostic
envelopes also match. All 64 retained reports pass their bounds, closed
validation and exact canonical replay; frozen-history acceptance also passes.

The current assembly scan contains 55,230 memberships in 7,580 groups, including
1,029 memberships with qualified rack occurrence proof. Signal/SFC assembly
exclusions are zero. Two dynamic calculation destinations and one dynamic file
address remain excluded pending runtime-selected values. Original provider
gaps and `partial`/`unreviewed` statuses remain evidence, not failed tests.

The cleanup centralizes work-report size/serialization policy under
`contracts/work_reports.py`, adds documentation entrypoints and clarifies the
report's base rack-binding labels. Its accepted return took 18m 06.389s. See the
[cleanup record](docs/reviews/CLEANUP_REVIEW.md) for validation and timing detail.

## Superseded report-only review handoff

Tyler requested an embedded page explaining what to check and how to answer,
with normal reviewer output free of development attribution and example
acquisition narrative. The guide now includes nine subject checklists,
response definitions, a glossary and a selectable feedback template. Detail
pages supply record, snapshot and selected context, with a return link.
Responses are written in separate notes; the HTML does not save or send them.

C16 completed in 18m 20.148s and confirms the guide-bearing private report was
saved. First follow the one-time [history synchronization procedure](docs/reviews/HISTORY_CONSOLIDATION.md#work-pc-synchronization)
if the work PC still has the pre-cleanup main tip. Then open the existing
`review.html` saved by check `20261019T201714Z-38434b5f` and choose
**Review guide**. Do not rerun the parser just to find or review that report.
Proceed to readability, navigation, appearance and official engineering review.
The private HTML has not been visually inspected here; prior guide browser
checks used invented reports. Engineering decisions remain unreviewed. See the
[implementation record](docs/reviews/REVIEW_GUIDE_IMPLEMENTATION.md) for current
validation and the [tracker](docs/planning/PRE_TEAM_REVIEW_TRACKER.md) for status.

Normal HTML omits only known generated version/rule metadata; `--debug` on
`run-work-check.sh` or `plc review` restores the canonical payload and developer
panels. Source comments, engineering evidence, IDs and uncertainty are retained
in both modes. Canonical saved JSON, manifests and sampling are unchanged.

For each feedback item, retain the report/run and record ID, observed and
expected behavior, and supporting evidence. Distinguish parser defects,
object-specific exceptions, missing evidence, interface issues and DeltaV
design decisions. Preserve the reviewed report. Investigate concrete feedback
before requesting another work-PC run; do not reopen completed analysis cycles
without new evidence. Frozen sampling remains six charged examples, eight
reserved units, cap forty; no new sample was requested or released by C16.

For a future requested check, the work-PC sequence remains manual `git pull`,
`bash ./run-work-check.sh`, then `git push`. The script creates only its local validated feedback commit and
performs no Git network operation. The listener remains outside the shipped
workflow. Future development belongs on a focused `-pc` branch. Build/test
iterations stay on that branch; consolidate them into meaningful feature or
fix commits before merging to `main`. Include validation and handoff notes
with the relevant change rather than adding routine status commits to main.
Preserve report bytes and recorded historical SHAs as provenance identifiers;
retaining every original Git commit or an iteration archive tag is not required.

## Boundaries and useful links

- Keep actual exports and full derived reports in `confidential/`. Use the
  existing validated aggregates, frozen bounded examples and independently
  synthetic fixtures for development. Preserve sample history and limits.
- Source associations do not establish physical wiring, runtime execution,
  equipment purpose, shutdown effect or engineering approval. The remaining
  source/vendor/runtime questions are explicit in the readiness assessment.
- The report does not yet persist corrections across exports. Editable records,
  naming/classification corrections, PCSD and FHX are later phases.
- Preserve sequential handoffs with adaptable routing and traceable decisions.

[Work-PC procedure](docs/reviews/WORK_MACHINE_REFERENCES_RUN.md) ·
[Reading guide](docs/reviews/REPORT_REVIEW_GUIDE.md) ·
[Development guide](docs/DEVELOPMENT_GUIDE.md) ·
[Documentation index](docs/README.md) ·
[Next-session checklist](docs/reviews/NEXT_DEVELOPMENT_PROMPT.md)

The [full prior handoff](docs/history/2026-10-19-pre-cleanup/files/public/CODEX_HANDOFF.md)
and other accumulated entrypoints remain in the
[verified archive](docs/history/2026-10-19-pre-cleanup/README.md).
