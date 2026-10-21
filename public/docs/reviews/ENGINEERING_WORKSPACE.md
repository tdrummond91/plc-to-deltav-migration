# Editable engineering workspace

Keep using **`bash ./run-work-check.sh`** from the repository folder on the
work PC. It tests the tools, analyzes the remembered L5X, saves the complete
private result and creates the validated feedback commit locally. It then
updates the editable project from that exact completed run and opens the
application at <http://127.0.0.1:8745>.

Git pull and push remain manual. There is no background listener.
Keep the command's terminal open while reviewing. **Close workspace** stops
the local application and returns to Bash; Ctrl+C also stops the server.

## First session

1. When the work check opens the workspace, verify the source name and total
   rung count in the automatically loaded result. There is no default
   demonstration. **Choose analysis run** is a manual fallback for an already
   completed run under `confidential/workspaces/work-check`.
2. Choose a program/routine or search for a known tag. The result count and
   page controls cover all captured rungs. The list previews formatted instructions
   and opens the first rung automatically when no selection is pending. **Rung flow**
   connects every displayed instruction from left to right, preserving nested
   splits, joins and empty bypass paths. Scroll and zoom to follow longer rungs.
   Calculations use fractions, powers, roots and comparison symbols. The
   arrow `destination ← expression` means storing a value when enabled.
   **Equations** offers a vertical reading view. **Branch structure** retains fragment selection;
   **Original text** shows the exact captured rung. **Every instruction & operand**
   retains the complete argument list. Parallel paths stay separate in both views.
3. Select **Explore inputs & outputs**. The **Connection map** places the focused
   rung between upstream writers and downstream readers, with exact signals
   between them. Click a signal to expand its fan-out, then click a neighboring
   rung to continue the trace. **Back in trace** restores the prior selection.
   Scope and direction filters narrow the view; signal and connected-rung page
   controls expose the remaining records. **Open focused rung** returns to its
   complete source and review form.
4. In **Your engineering review**, select categories, change properties and
   press **Save review**. A rung can have multiple categories. Use groups to
   associate several rungs, individual instructions or source objects; a
   source record can belong to more than one group.
5. Reopen the application and verify the saved change. Select **Back up
   project**. **Restore backup** opens a new restored project and keeps the
   previous project and backup intact.

For later review sessions that do not need new analysis, the optional command
`bash ./open-workbench.sh` reopens the saved project. Double-clicking
`Open-Workbench.cmd` is an alternative to that shortcut. The opener does not
run tests, analyze the L5X, or perform Git operations.

## Reading layout and English wording

**Equation text** starts at **75%** of its previous size. Choose 50%, 75%, 100%
or 125% above the rung list. Drag the vertical divider to give either pane more
width. With the divider focused, Left/Right moves it, Shift makes larger moves,
and Home/End reaches the limits. Double-click resets the split; **Reset layout**
also restores 75% text. These reading preferences survive reopening in the same
browser. Narrow windows stack the panes.

For optional local French-to-English translation, close the workspace and run
this **once per computer**, from the repository in Git Bash:

```bash
bash ./setup-translation.sh
bash ./open-workbench.sh
```

Setup downloads optional Python translation packages and a public French-to-English
model (about 67 MB). No engineering comments are uploaded. The subsequent
translation process works offline on the CPU. Under **Source language**, choose
**English** or **Both languages** to prepare the imported source while reviewing.
**Original** changes the display without cancelling preparation. The progress
count covers unique wording across the whole export, not just the selected rung;
a selected comment appears when its batch is reached. Elapsed time, estimated
remaining time and any missing translations are shown in the sidebar.
English is a reading aid:
confirm terminology, negation and control meaning against the original,
especially abbreviations and mixed French/English wording. Text whose translation
changes checked values/identifiers or cannot be completed is withheld for review.
These checks do not prove semantic equivalence.

Identical text is translated once per model/rule version, including repeated
comments and later L5X exports. New or changed text is translated on the next
import while unchanged translations are reused. The usual `run-work-check.sh`
entry point still works; another parser run is unnecessary just for these
reading features. The source-analysis report follows the selected language, with
its own Original/English/Both control. Reopen the report to include translations
completed since it was opened. **Comments & descriptions** provides a searchable
index of captured wording and links back to its source context.

To prepare an English review phase before browsing, close the workspace, then run:

```bash
bash ./prepare-english.sh
bash ./open-workbench.sh
```

This uses the selected saved project; it does not reanalyze the L5X. Completed
translations survive stopping and restarting. The command selects English and
saves `review-english.html` plus `source-wording.json` in a new private
`english-analysis/` folder beside the project. The final `complete.json` records
the source identity, coverage and any wording gaps. A partial result (exit code 3)
means some eligible wording still needs review; the report remains usable.
`--retry` retries missing/withheld translations. There are no Git operations or
automatic model downloads. Use one workspace/preparation process per project.

Coverage includes supported description/comment fields, localized notes,
tag-member/bit notes, FBD/SFC text boxes and separately captured, validated SFC
transition comments. Names, addresses, stored values and executable text stay
exact. Other comments embedded in structured-text code and unsupported XML
namespaces remain original; the report states these limits. English mode keeps
the original available in a collapsed disclosure and explicitly marks missing
English. It does not create or import a translated L5X.

The model lives in ignored `confidential/translation/fr-en/`. English text and
its preparation and display preferences live in `<project>.translations.sqlite` beside the local
project. This is a reproducible cache, separate from source evidence and saved
engineering decisions. **Back up project** backs up engineering decisions;
it does not bundle this cache or the model. A restored project starts with
translation disabled and can regenerate its English wording. A machine without
the optional packages still opens and edits the original source normally.

An approved local copy of the pinned model can be installed with
`bash ./setup-translation.sh --package /path/to/translate-fr_en-1_9.argosmodel`.
This avoids a model download; Python packages must still be installed or cached
for an entirely offline setup. Regular analysis and editor launchers never
download a translation model automatically.

The equation display works offline using the browser's mathematical typesetting.
It uses the saved CPT expression structure after checking it against the source.
Supported arithmetic instructions and comparisons also receive mathematical
notation. Timers, unfamiliar instructions and unsupported expressions keep their
instruction names and exact arguments; no branch or sequence is collapsed into
an assumed combined equation. Formatting does not evaluate values or change
classifications. Existing completed runs can use this display after restarting
the updated workspace; another full work check is not needed for formatting.

Expression grouping follows the existing parser and the documented
[CPT operation order](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/compute-math-instructions/compute--cpt-.html).
Explicit groups, signed bases and left-associated powers remain distinguishable.
Bitwise operators retain their names, and tag/address spelling stays literal.
Arithmetic notation does not replace the controller's data-conversion, rounding
or enable-condition rules.

Contact and coil notation uses the incoming rung condition, labelled `EN`:
`XIC` passes when its bit is true, `XIO` when false, and `OTE` stores the incoming
condition in its output bit. These local illustrations follow the documented
[XIC](https://www.rockwellautomation.com/en-gb/docs/factorytalk-design-studio/current/contents-ditamap/instructions/instruction-set/bit-instructions/examine-if-closed--xic-.html)
and [OTE](https://www.rockwellautomation.com/en-be/docs/studio-5000-logix-designer/38-02/contents-ditamap/instruction-set/bit-instructions1/output-energize--ote-11.html)
behavior during normal instruction execution; they do not simulate prescan,
task scheduling or retained state.

The connection map reads the saved reference, access, calculation and relationship
artifacts once per imported run. Navigating the map does not analyze the L5X again
or alter review decisions. Existing saved runs with these companions work after
restarting the updated app. A missing or inconsistent companion produces an
explicit unavailable notice while original rungs remain accessible.

A connection means an explicit read and write share the same captured tag identity
and exact member/index suffix. It does **not** establish scan timing, which of
several writes reaches a read, or physical wiring. Multiple writers, same-rung
reuse, unknown roles and filtered-out neighbors remain visible in signal details.
Unknown-role uses have no directed edge; their known neighboring readers/writers
remain navigable in details. Whole-tag/member overlap, implicit timer/PID/AOI
effects, copied ranges and runtime indices are stated coverage limits. An absent
line is not proof of unused logic. The timeline-like rung view is source progression,
not an elapsed-time simulation.

If port 8745 is occupied by an existing workspace, the work-check script keeps
its completed result and does not automatically import into the running app.
Close that workspace, use the optional opener, and select **Choose analysis
run** to load the new completed result. No second parser run is necessary.

**Tags & source objects** exposes declarations, descriptions and I/O/module
context. **Open full source analysis** retains the existing detailed PID,
alarm, calculation, SFC and other evidence views as read-only references.
The old HTML feedback template is not the editing workflow. Review decisions
are saved through the workspace controls.
Older saved reports receive the current navigation when opened in the workspace;
their captured evidence and original stored HTML remain unchanged. This display
refresh does not rerun the parser.

## What a saved change means

| Layer | Meaning |
|---|---|
| Original source | Captured L5X, rung text, comments, instructions and declarations. Preserved unchanged. |
| Parser interpretation | Generated candidates and supporting analysis. A recognized family does not prove equipment purpose, a complete loop or target class fit. |
| Project rule proposal | Your reusable category suggestion for the same ordered instruction/branch pattern. Operand values and engineering behavior can differ. |
| Reviewed decision | Your categories, review status and named engineering properties for a specific source record. Saved with a project revision and history. |

Properties can include name, description, purpose, equation, PV, SP, output,
alarm behavior and target-class notes. These are reviewed engineering values,
not executable edits to the L5X or an automatically validated DeltaV design.
Add or rename properties using the form. Manage categories independently of
the parser's generated categories.

Select several rungs for a bulk category/status change. Unchanged fields stay
unchanged on each selected record. Grouping can include only selected
instructions when a rung contains more than one engineering responsibility.

## Reusable rules and reruns

**Create a reusable category rule from this pattern** previews all matching
rungs before saving. Pattern matching retains ordered opcodes and nested
branches; it ignores operand values. A rule proposes categories; it does not
approve matching rungs or replace an individual reviewed category. Rules can
be renamed, reclassified and disabled. Parser-wide code changes remain a
separate tested development change.
Adding or editing a rule retains existing categories and properties, but marks
affected saved reviews for revalidation. The full source analysis shows the
imported parser proposals; the workspace shows your current saved decisions.

The usual work-check command imports its new completed analysis into the
project automatically. **Choose analysis run** can import a saved result
manually without reanalysis. Reimporting the identical run has no effect.
Unchanged source keeps its decisions. A
change in saved analysis evidence conservatively requests revalidation rather
than silently retaining an approval. A changed export preserves old decisions
and requires explicit correspondence to current records. **Changes &
reconciliation** shows the earlier evidence beside the current choice; a
transferred decision still needs review. Rung numbers and names are not
treated as persistent identities.

Every save checks the project revision. A stale page cannot overwrite a newer
save. Reload and compare before resubmitting. **Undo latest change** records
a compensating revision; it does not erase history. Undo covers edits since
the latest source import. Imported evidence is retained.

## Project storage and recovery

The default project is `confidential/projects/engineering.sqlite`. It contains
the imported source and analysis artifacts as well as decisions and history.
Backups are complete SQLite files under the adjacent `backups` directory;
the original saved-run directories are not required to reopen a backup.
These files contain private engineering data and stay out of Git.

Restoring creates `restored-<timestamp>.sqlite` beside the original. The local
`last-project.json` pointer makes the normal launcher reopen the selected
restored project. The original project and every backup remain available.
For a separate unit or an explicitly selected project, the development command
is `bash ./open-workbench.sh --project confidential/projects/unit-name.sqlite`.
Keep whole project files in the approved private handoff/backup location;
Git synchronization of code does not back up this data.

## Development and acceptance

Implementation: `project_store.py` owns SQLite, artifact validation, decision
transactions and history. `workspace.py` projects source records and hosts the
loopback application. `workspace_assets` owns the interface. Existing parser
contracts and saved-run publication remain separate.

Use independently invented sources for development. The acceptance boundary is
an actual browser import, source drill-down, category/property/group save,
reopen, rerun preservation and backup restoration. Test complete pagination
and changed-source correspondence, not just that HTML contains labels.

This replaces the earlier report-only review handoff. Phase 1 analysis remains
available, and the first editable review workflow is now the focus. PCSD/FHX
generation, target-class allocation and packaged reviewer distribution are
separate later deliverables.
