# PLC analysis workbench

Understand an Allen-Bradley L5X export before mapping its control strategy to
DeltaV. The current tool builds a searchable, offline engineering report from
the source: rungs and branches, I/O, PID evidence, calculations, sequences,
alarms, communication and related groups, with uncertainty kept visible.

**On the work PC, keep using the same command from the repository folder:**

```bash
bash ./run-work-check.sh
```

It runs the checks, analyzes the remembered L5X, saves the complete private
result, creates the validated feedback commit locally, and opens the editable
workspace with that exact new analysis loaded. Review categories, groups and
engineering properties save in a local project database.

**Current step:** connecting Phase 1 source analysis to persistent engineering
review. The usual work-check command now carries the result into that review
workspace. PCSD and FHX generation remain later phases.

## What to do next

Use [START-HERE.html](START-HERE.html) for four short, checkable steps.
The app opens at <http://127.0.0.1:8745> after the check. Verify the source name
and total rung count in the automatically loaded result, and open a familiar rung.
Change its reviewed categories or properties and select **Save review**.

**Back up project** saves the whole private project. **Restore backup** opens
a new restored copy without replacing the original. The built-in **How to
review** page explains the controls. See the [workspace guide](public/docs/reviews/ENGINEERING_WORKSPACE.md)
only when you need storage, rerun or handoff details.

The script uses the work PC's existing parser environment. It does not fetch,
pull or push, and it does not install a background listener. **Close workspace**
stops the review application. Original saved HTML remains available as supporting
evidence.

## Your usual work cycle

Pull updated code yourself when needed, run the same script, then push the
locally created feedback commit yourself:

```bash
git pull
bash ./run-work-check.sh
git push
```

The two Git commands above are manual. The script handles testing, analysis,
the local feedback commit, and opening the editable project. Its terminal stays
occupied while the workspace is running. Select **Close workspace** when done
to return to Bash, then push. For a new checkout, supply the source once:

```bash
bash ./run-work-check.sh A19CHL02-unencrypted.L5X
```

The source belongs under `confidential/plc-code/`; an explicit local path also
works. See the [work-PC instructions](public/docs/reviews/WORK_MACHINE_REFERENCES_RUN.md)
for prerequisites, results and failure handling.

Normal reports include the reviewer instructions and engineering evidence.
To include developer version and rule diagnostics in a separate run, use
`bash ./run-work-check.sh --debug`. Keep the normal report for review.

## Reopen a saved review without another analysis

This optional shortcut opens the existing project directly:

```bash
bash ./open-workbench.sh
```

Double-clicking `Open-Workbench.cmd` is an alternative to this shortcut.
**Choose analysis run** remains available to import an already completed run
manually. Neither opener runs the parser or synchronizes Git.

If a workspace is already using port 8745, the work-check script leaves the new
completed run saved and does not import it into that running application. Select
**Close workspace**, run the optional opener above, and use **Choose analysis
run** to load the completed result. You do not need to repeat the long analysis.

## Supporting source evidence

The script prints **Private review report:** and its path. In File Explorer,
open `confidential/workspaces/work-check/`, choose the newest completed run and
double-click **`review.html`**. It works in a browser without a server.

For the current editing workflow, use **Open full source analysis** inside the
workspace. Source links connect the detailed analysis to editable source
records. Save categories, properties, groups and review status in the workspace.
Standalone HTML remains read-only; its older feedback-template controls are
superseded by these saved edits. Keep complete reports and project databases
within the approved work environment.

## Find things

| Location | Purpose |
|---|---|
| [START-HERE.html](START-HERE.html) | First-use path and your personal learning checklist. |
| `run-work-check.sh` | Usual command: test, analyze, save the result and local feedback commit, then open the updated editable project. |
| `open-workbench.sh` / `Open-Workbench.cmd` | Optional shortcuts to reopen an existing review without reanalysis. |
| `confidential/` | Ignored local exports, complete reports and logs; Git does not back these up. |
| [python-parser/](python-parser/README.md) | Application code, tests and locked Python environment. |
| [public/docs/](public/docs/README.md) | Current instructions, plans and retained review evidence. |
| [public/examples/](public/examples/README.md) | Invented reports for learning the interface. |
| [public/fixtures/synthetic/](public/fixtures/synthetic/README.md) | Independently invented test inputs. |
| `public/inspection/` | Validated work-PC feedback history used to check each change. |
| [tools/](tools/README.md) | Supporting L5X inspection tools and their tests. |
| [public/CODEX_HANDOFF.md](public/CODEX_HANDOFF.md) | Current checkpoint for the next coding session. |

Use the [completion tracker](public/docs/planning/PRE_TEAM_REVIEW_TRACKER.md)
for progress and the [readiness assessment](public/docs/reviews/PHASE_1_READINESS_REVIEW.md)
for evidence and remaining source questions. Developers can start with the
[development guide](public/docs/DEVELOPMENT_GUIDE.md); this pass is recorded in
the [cleanup review](public/docs/reviews/CLEANUP_REVIEW.md). The requested report
guide is recorded in [its implementation review](public/docs/reviews/REVIEW_GUIDE_IMPLEMENTATION.md).

The full earlier entrypoint notes are preserved in the
[2026-10-19 archive](public/docs/history/2026-10-19-pre-cleanup/README.md).
