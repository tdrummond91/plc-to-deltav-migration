# Editable engineering workspace

The review entry point is now **Open-Workbench.cmd** in the repository root.
Double-click it on the work PC. It opens the application at
<http://127.0.0.1:8745> using the same local Python environment as the parser.
The application runs only while open; **Close workspace** stops it. It does
not fetch, pull, push, watch GitHub, or run the parser automatically.

## First session

1. Select **Choose analysis run**, then a completed run from
   `confidential/workspaces/work-check`. This imports its saved inventory and
   analysis; it does not repeat the full work check. Verify the source name
   and total rung count before continuing. There is no default demonstration.
2. Choose a program/routine or search for a known tag. The result count and
   page controls cover all captured rungs. Open a rung to see its complete
   text, source comment, instruction arguments and nested branch structure.
   The diagram describes source structure, not a simulated operating state.
3. In **Your engineering review**, select categories, change properties and
   press **Save review**. A rung can have multiple categories. Use groups to
   associate several rungs, individual instructions or source objects; a
   source record can belong to more than one group.
4. Reopen the application and verify the saved change. Select **Back up
   project**. **Restore backup** opens a new restored project and keeps the
   previous project and backup intact.

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

Import a newer completed analysis through **Choose analysis run**. Reimporting
the identical run has no effect. Unchanged source keeps its decisions. A
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
