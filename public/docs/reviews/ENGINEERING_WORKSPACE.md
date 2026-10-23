# Editable engineering workspace

Keep using **`bash ./run-work-check.sh`** from the repository folder on the
work PC. It tests the tools, analyzes the remembered L5X, saves the complete
private result and creates the validated feedback commit locally. It then
updates the editable project from that exact completed run and opens the
application at <http://127.0.0.1:8745>.

Git pull and push remain manual. There is no background listener.
Keep the command's terminal open while reviewing. **Stop workspace** stops
the local application and returns to Bash; Ctrl+C also stops the server.
Chrome's X closes only that window. The shared server and background translation
continue until you stop the workspace, so other review windows remain usable.

## First session

1. Start on **Home / page guide**. Verify the source name and total
   rung count in the automatically loaded result. There is no default
   demonstration. **Project tools → Choose analysis run** is a manual fallback for an already
   completed run under `confidential/workspaces/work-check`. Each Home card
   explains a page and links to it. **Home**, the **Page** selector and the
   **How to review** button are in the header. The Page dropdown follows the same
   order as the Home cards. Compact **FR / EN** flag buttons sit immediately to
   the right of the PLC Workbench logo and switch source language on any page.
   There is no permanent sidebar.
   **Project tools** holds the source details, analysis-run selection, source
   language, changes and reconciliation, reviewer name, refresh, theme and backups.
   **How to review** opens the checkable guide directly.
   **Full source analysis** is a Home card and Page-menu destination that opens
   the complete evidence report in a separate window, using your saved language.
   Cards and page headings state **Read only** or **Read & write**, with an
   explanation of what can change. Source evidence is never edited. Review
   decisions are saved separately in the project; guide checkmarks stay in this
   browser. Project tools are available regardless of the page label.
2. Start with **Patterns**, the first Home card. It opens the evidence report
   in another window with the most frequent structures first. Change **Sort
   occurrences** to reverse the order. Open a pattern to compare ten visual
   rungs per page, using the same drawing, zoom and instruction help as Programs
   & routines. Hover or focus a rung number for its routine, scope and comment;
   **F1** keeps that context panel available. Its color indicates syntax parse
   status. Use **Review categories in workspace** in that panel to edit the
   selected rung. Matching structure does not establish matching behavior or
   automatically apply a category to every occurrence.
   Open **Field I/O**, the second Home card, to work with individual DI, DO, AI
   and AO signals. Name a signal for DeltaV and package its related logic across
   rungs or routines. The detailed workflow is below.
   Open **Classification & groups** for the automatic functional overview.
   Choose **Function** to find DC, AC, PID, alarms, timers, counters, structured
   objects, or I/O candidates. Expand **Evidence, parameters & source links**
   on a relevant item, then follow its rung links to inspect the logic.
   You can browse every proposal before saving any groups.
3. Open **Programs & routines** and use the top filters to find a routine.
   Expand its arrow to see the captured ladder. **Open rung review** opens that
   rung's complete source and saved decisions. On **Rungs**, use the top routine
   picker or search for a known tag. The result count and
   page controls cover all captured rungs. The list previews formatted instructions
   and opens the first rung automatically when no selection is pending.
   **Logic summary** is the default: read **Inputs & constants**, follow the
   numbered **Logic paths**, and check **Outputs & stored state**. Conditions
   use plain TRUE/FALSE wording. Parallel branches keep their own conditions
   and actions. For a simple comparison feeding an output, the summary states
   the comparison and when that instruction writes TRUE or FALSE. It does not
   infer shutdown consequences, priority, or live values. Stateful and unknown
   blocks remain explicit; unsupported or oversized structures retain the full
   original text instead of a partial summary. **Rung flow**
   connects every displayed instruction from left to right, preserving nested
   splits, joins and empty bypass paths. Scroll and zoom to follow longer rungs.
   Calculations use fractions, powers, roots and comparison symbols. The
   arrow `destination ← expression` means storing a value when enabled.
   **Equations** offers a vertical reading view. **Branch structure** retains fragment selection;
   **Original text** shows the exact captured rung. **Every instruction & operand**
   retains the complete argument list. Parallel paths stay separate in both views.
4. Select **Explore inputs & outputs**. The **Connection map** places the focused
   rung between upstream writers and downstream readers, with exact signals
   between them. Click a signal to expand its fan-out, then click a neighboring
   rung to continue the trace. **Back in trace** restores the prior selection.
   Scope and direction filters narrow the view; signal and connected-rung page
   controls expose the remaining records. **Open focused rung** returns to its
   complete source and review form.
5. In **Your engineering review**, select categories, change properties and
   press **Save review**. A rung can have multiple categories. Use groups to
   associate several rungs, individual instructions or source objects; a
   source record can belong to more than one group.
6. Reopen the application and verify the saved change. Open **Project tools →
   Back up project**. **Restore backup** opens a new restored project and keeps the
   previous project and backup intact.

For later review sessions that do not need new analysis, the optional command
`bash ./open-workbench.sh` reopens the saved project. Double-clicking
`Open-Workbench.cmd` is an alternative to that shortcut. The opener does not
run tests, analyze the L5X, or perform Git operations.

### Start from field I/O

Choose **Field I/O** on Home or in the Page menu. Each line is one captured
field-channel address, with its original alias, source description, DeltaV name
and package status. Aliases for the same exact channel share one record;
channels on the same card can have different names and packages. Filter DI,
DO, AI or AO and search original wording, an alias/address, a saved DeltaV name,
or a package name. FR / EN controls the displayed source wording.

Controller headings collapse their signal rows. **Expand all / Collapse all**
applies across the current filtered directory, including subsequent pages.
Choose **Signals per page** (10/50/100/200/500) for the directory and **Rungs per
candidate section** for related logic. Filters still search the entire source.
Descriptions wrap within the row rather than being forced into narrow lines.
The proposed DeltaV name is the source alias, or its exact address when no alias
is captured. It is labeled unreviewed until saved; a saved name is preserved.
Expand **Original source wording and evidence** for alias target, datatype,
captured radix and external access.

1. Select a signal. Enter its **DeltaV name**, reviewed description and field
   type, then save. The original L5X name, address and description stay intact.
2. Choose an existing package or create one, then include this signal. A package
   is an engineering group that keeps field signals and selected source logic
   together for later target-module design.
3. Review **Rungs using this signal** and **Related logic candidates**. Open a rung's
   source/connection view to inspect it, then tick only the members you want.
   Assign a package role such as scaling, alarm, reference or logic. Suggestions
   start unchecked; existing memberships stay selected until you remove them.
4. Save the package. **Classification & groups** shows its signal names and
   linked source records. One signal or rung can belong to several packages.

The information button on each row opens controller/module/rack/slot context
without giving hardware its own card. Hover or focus it for a quick look;
click to pin, and use Escape, Close or an outside click to dismiss it. Source
links open the captured hardware or complete annotations separately.

**Source-mapped** means the exact catalog, direction and captured member profile
support that channel interpretation. **Candidate** means its source member is
captured but the physical mapping still needs review. A card's advertised
capacity never creates invented wired signals. Known controller/network,
configuration, status and output-echo records are excluded from the signal list.
A missing field channel therefore remains a recognition gap, not proof it is
absent from the plant. The hardware popup retains catalog documentation.
For an unrecognized card, a qualified floating channel member and its I/O
direction can suggest AI/AO. The suggestion stays unreviewed and does not
establish physical wiring or approve a target class.

Related-rung suggestions follow a bounded, one-step shared-address connection
from a direct field use; this can reach another routine. They do not prove
execution order or that every member belongs in the target module. Use the
connection map and source review when the suggestion list reports a limit.
Patterns remain useful for comparing logic structures; a repeated pattern
alone does not identify the physical signal or approve a package.

Names and packages are saved in the private project database, with revision
history, undo and backups. Unsaved signal drafts remain while moving between
pages; save them before closing the browser. A stale-window save retains the
draft and asks you to review the latest saved version before retrying.
A changed source export retains earlier records and flags correspondence:
select the replacement channel, expand **Needs correspondence**, explicitly
reconnect the retained signal, then confirm its mapping. This keeps its durable
identity, DeltaV name and package memberships rather than guessing by name/slot.

After a manual pull, stop and reopen the workspace to use this page with the
existing saved analysis. No new L5X run is required when its saved companions
are present. This stores the migration package; allocating DeltaV classes and
emitting PCSD/FHX remain later steps.

### Reading rungs and saved variable settings

**Rungs** shows the full ladder on each card, with the source hierarchy centered
and **Connections / Open rung** at the right. Drawings load as they approach the
viewport. **Items per page** changes the number of cards without dropping selected
records on other pages. Opening a rung starts on **Full ladder**; other source
representations remain available when needed. Hovering an alias variable shows
its original name, target, description and access alongside the backing data.

Open a rung in **Full source analysis / Engineering review** to see the same
ladder drawing as **Programs & routines**. Zoom, Fit width, colored variables,
branch paths and block help work the same way. **Original rung text (complete)**
keeps the captured source available below the drawing. Reports opened through
the workspace use the current drawing tools even when their analysis is older.
The report's **Ladder** directory, **Routine ladder** source page and related-rung
lists also use these drawings, initially ten per page with a page-size selector. Hover or focus the rung number for
its scope and comment; its color indicates parse status.

Timer and counter blocks show exported preset and accumulator values when
the saved tag data establishes them. For example, `5000 ms (export)` is a value
stored in the L5X, not a live timer reading or a promise about startup state.
The original instruction can still contain `?`. Missing or ambiguous values
are labeled rather than replaced with zero.

Hover over a variable such as `Delay.PRE`, or focus it and press **F1**. Its help
shows the declaration and program/controller scope, the member's meaning when
known, stored values, and rungs that can write it. An explicit `MOV` to `.PRE`
is distinguished from a whole-timer instruction whose effect on that member
has not been established. **Ctrl-click** opens an independent help window;
write-site links open the captured writing instruction from the same analysis.
Custom members retain their source information even when their meaning is
unknown. No current value or execution order is inferred.

The first variable lookup prepares a local evidence index and can take a few
seconds; later lookups reuse it. Standalone HTML files retain their drawings
and instruction examples offline. Open the report through the workspace for
saved variable lookups and separate help windows.

Click outside **Project tools** or press Escape to close it. Dialogs also close
when you click their shaded backdrop or press Escape. Unsaved dialog edits still
require a discard confirmation; a save in progress must finish first. Clicking
inside a dialog or dragging out of it does not dismiss it. Expanded routines and
inline help sections remain open until you collapse them.

## Programs and routines

Choose **Programs & routines** from Home or the header's Page selector.
Filter by program or AOI, routine type, or a name/path search at the top.
Same-named routines retain their full scope, including separate AOI definitions.
Expand the arrow beside a routine to load its ladder; opening another routine
closes the previous one. Routine directories and expanded ladders have their
own page-size controls. Choose 10, 50, 100, 200 or 500 entries; the existing
20-rung default is also available for expanded ladders. Source order is retained. The page controls keep
all captured rungs reachable without drawing an entire export at once.

The drawing uses contacts, coils and instruction blocks. Nested branches split
and rejoin as captured; empty legs remain bypass wires. Slashed contacts mean XIO;
L/U coils mean latch/unlatch. Neutral colors represent source logic, not live
energized state. **How to read these ladders** explains these conventions once.
Drawings start at **85%**, with compact branch spacing. Comments sit beside the
rung number; zoom controls sit on the right, and **Reset zoom** returns to 85%.
Long comments show a three-line preview with **Show full comment / Collapse
comment**. Their language status stays visible below the preview; opening the
comment survives a language change while that rung page stays open. The main
header stays at the top while scrolling, with a distinct lower border.
Known comparison blocks show the actual test, such as **Mode != RequestedMode**.
Calculation blocks show the destination and operation, such as
**Adjusted ← Pressure − Offset**; the arrow means a write when the incoming
path is TRUE. Moves and clears follow that convention. CPT displays its captured
expression with original grouping, without evaluating or validating its syntax
again. Timers, counters, one-shots and PID use named fields, including all seven
PID operands. Preset/accumulator values are captured operands, not live readings.
Long expressions can use two lines; shortened names retain their full source in
help and selection. Unknown blocks or unsupported argument counts retain their
captured positions rather than receiving guessed operators or parameter roles.
Variable names use distinct colors, with repeated exact names retaining their
color within a rung. Operators, instruction names and ladder symbols use orange;
constants have a neutral foreground. The six variable colors repeat for larger
rungs and do not represent live state or input/output roles. The same convention
applies to the Rungs equation, flow, branch and instruction displays in both themes.
Hover over a block or expression for an interactive **Instruction help** panel:
what it does, captured arguments, and a separate worked example using invented
values. Move into the panel to scroll and read it. Click outside, press Escape,
or use its close button to dismiss it.
**Ctrl-click** (Command-click on Mac) opens a separate read-only help window.
Each click opens another window, so several instructions can stay visible on
different monitors. Each window retains its saved analysis and instruction even
when the workspace selection changes. **Open help window** is the equivalent
panel button; keyboard users can focus a block and press **F1**, or **Ctrl+Enter**
for a window. If the browser blocks a popup, the panel offers a new-tab link.
Normal clicks still open source details. Unknown/custom instructions and
unsupported argument shapes keep their effects unresolved, without a fabricated
worked result. Examples explain standard behavior; they do not evaluate the
captured rung or assign a DeltaV class. All help works locally; optional vendor
reference links open only when selected.
If no nonblank comment was captured, its header says **Rung N — No comment**.
Existing comments stay beside the rung number, including original wording when
English is unavailable; long comments still have **Show full comment**.
Zoom and scroll to inspect a long rung. Select a symbol for its complete arguments and a
source inspector; **Open rung review** opens that exact rung in the main review
page. Unknown instructions remain labeled blocks rather than guessed symbols.

Unparsed, unsupported or oversized structures show their complete original text.
Non-ladder and empty routines remain listed with an explanation and source link.
This page changes no classifications or source logic. English wording uses the
same **Project tools → Source language** setting and preserves the drawings
while translations arrive. Drawn connections do not establish execution order,
physical consequences or target DeltaV class boundaries.

## Whole-ladder map and multiple monitors

Open **Ladder map** to browse every captured rung, including empty, unparsed,
and disconnected rungs. The initial overview groups rungs into count tiles.
Click a tile to zoom in, use the mouse wheel or **Zoom in / Zoom out**, and
drag the background to pan. **Fit all** returns to the full overview. Drag a
rung card to arrange it; this changes the current view only. Positions are
not saved as engineering changes and reset when you reopen the page.

Use **Search all captured rungs**, **Routine**, or **Function family** to narrow
the overview. Search includes full captured rung text and comments, even if
the card preview is shorter. **Find and select rungs** provides a paged list
with keyboard access and a page-number field. It remains available when cards
are offscreen or grouped into tiles.

**Function family** is also available on **Rungs**, using the same captured
instruction families and counts. These families differ from the engineering
functions on **Classification & groups** and from your reviewed categories.
A mixed rung can match several families; filtering changes no saved decision.
Choose **Show rung descriptions** for captured comment previews on cards and
**Show signal names** for labels beside signal points. **Map help** explains
the colors, connections, filters, controls, display limits and multiple windows.

Select a rung to open its complete **Rung flow**, equations, original source,
and saved review beside the map. Hover or keyboard-focus a card for its block
families and descriptions. Choose **Pin information** above the map to use the
preview's links; an unpinned preview lets clicks pass through to the map.
The pinned panel has its own **Unpin panel** and **Close panel** controls.
Clicking outside or pressing Escape also dismisses it. Panning, zooming, changing filters or leaving the map
closes the panel; delayed hover responses cannot reopen a dismissed preview.
Within the inspector, instruction cards also open information on hover/focus.
Where the export contains an unambiguous supported
declaration, information links expose its captured AOI parameters or datatype
declaration. A declaration candidate does not confirm the instruction's behavior;
uncertain meanings and unavailable member layouts stay explicit.

Orange signal points connect the visible rungs. Solid arrows show recorded
writers/readers; dashed lines show uses whose direction is unknown. Click a
signal or its entry under **Signals connected to the visible rungs** to find
all of its recorded rungs, including other routines. Offscreen counts and signal
pages expose fan-out beyond the current view. The coverage notice explains
unresolved addresses, unsupported source, and other gaps. These are static
source relationships: no live Boolean state, scan timing, or complete implicit
instruction behavior is inferred. Missing lines do not prove unused logic.

For one screen, drag the divider between the map and inspector, or select
**Hide source**. The split and equation size have their own saved browser preferences.
For two or three screens, use **Pop out map**, **Pop out selected source**, and
**Pop out connections**, then move the browser windows to your monitors. Each
window has an independent selection and shares the same saved project. A
successful source popout hides the matching original pane; **Show source**
restores it. Opening a different instruction or declaration does not hide the
selected rung. Save an edited source before moving it to another window.
After saving in one window, choose **Project tools → Refresh saved data** in the others. Unsaved edits
require an explicit decision before replacement; an out-of-date save is rejected.
Close popouts with their browser window controls. **Stop workspace** in the
main window stops the shared local server.

The page loads compact metadata in batches and renders only the visible cards.
Full rung diagrams and declaration information load on selection/hover. Zooming
out uses tiles instead of thousands of diagrams; visible signals use shared
address points instead of every possible writer-to-reader pair. Reopening an
existing completed project is sufficient; another work-check run is unnecessary
for this view. If saved connection companions are unavailable, all rungs remain
browsable and the map shows the missing-evidence notice.

## Classifications, parameters, and migration decisions

**Classification & groups** projects the saved analysis into source-linked
proposals. Opening it reads the imported snapshot and saved evidence once; it
does not rerun the analysis pipeline. Existing completed projects can use this
view after updating and reopening the application.

**DC** means a discrete calculation with a true/false result. Latches and edge
storage retain their stateful qualification. **AC** means an analogue calculation
whose captured result type is REAL or LREAL. Integer or unproved result types
remain under **Calculation — result type unresolved**.

**AI/AO/DI/DO** are candidates supported by module direction and a uniquely
captured data leaf. An internal BOOL is not automatically a digital output;
module status flags are not automatically physical digital inputs. Packed
integer channels, missing types, unsupported XML paths and other gaps stay
visible for investigation. Names and comments can suggest alarms or equipment,
but do not establish shutdown consequences or physical identity.

PID, timer/counter, structured object and AOI groups collect captured settings
and related source uses. Each value links back to its source. These are exported
values, not a selection of the effective live setting. A PID may span several
DeltaV classes; nested timers remain separate source objects. Shared addresses
associate evidence without asserting one equipment item or module boundary.

To save an interpretation:

1. Choose **Adopt & edit group**. This creates a saved engineering group from
   the detected source memberships, without confirming its meaning.
2. Select all applicable function categories and a **Migration decision**:
   retain, replace with a DeltaV implementation, exclude, or investigate.
3. Adjust its name or memberships and choose **Save**. Changes are stored in
   the project database with revision history, undo and backup support.
4. Use **Migration decision → Hide reviewed exclusions** to narrow the working
   list. **All migration decisions** shows those items again.

If you remove members from an adopted group, its saved decisions apply to that
smaller group. The larger detected proposal keeps its original categories and
stays in scope for investigation, so an exclusion cannot hide the omitted logic.

Use **Function → Allen-Bradley platform detail** to examine controller-specific
configuration and logic. Exclusion requires a saved decision: status reads,
communication, timing and control-flow instructions can express behavior the
target still needs. Exclusion changes this review filter, not the original L5X
or a generated FHX.

Saved decisions survive reopening and reruns. Changed source or classification
evidence flags the old decision for rechecking; a stale exclusion remains in
scope as **Investigate before deciding**. Changed source IDs require explicit
correspondence. A count of rungs linked to groups does not mean every function
has been identified. Display limits, unknowns and unresolved evidence remain
visible, and all original rungs stay accessible in **Rungs**.

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
translation process works offline on the CPU. Under **Project tools → Source
language**, use the flag buttons **EN / English** and **FR / French** to switch
quickly. The compact header flags control the same saved setting; both flags are
highlighted when bilingual display is selected. French displays the original source wording, including any existing
English or mixed-language comments. **Show both languages** displays the source
and English together; press it again to return to English. English or bilingual
view prepares the imported source while reviewing. Switching to French changes
the display without cancelling preparation. The progress
count covers unique wording across the whole export, not just the selected rung;
a selected comment appears when its batch is reached. Elapsed time, estimated
remaining time and any missing translations are shown in Project tools.
English is a reading aid:
confirm terminology, negation and control meaning against the original,
especially abbreviations and mixed French/English wording. Each sentence or line
is checked separately. Accepted English remains visible; portions that change
checked values/identifiers, fail negation checks or cannot be completed keep their
exact original wording. **English partial** identifies this mixed result. If no
English is available, the original still displays in the same comment area with
**Original shown · English unavailable**. These checks do not prove semantic
equivalence.

Identical text is translated once per model/rule version, including repeated
comments and later L5X exports. New or changed text is translated on the next
import while unchanged translations are reused. The usual `run-work-check.sh`
entry point still works; another parser run is unnecessary just for these
reading features. The source-analysis report follows the selected language, with
its own Original/English/Both control. Reopen the report to include translations
completed since it was opened. **Comments & descriptions** provides a searchable
index of captured wording and links back to its source context.
Partial, failed, unchanged and interrupted translations are retained across
reopening and later analyses with identical wording and model/rule versions.
They do not automatically run again. **Reused from before this pass** stays
fixed while new/retried counts increase; saved gaps are listed separately.
Use **Retry incomplete translations** under **Project tools → Source language**
when you want another attempt. It rechecks each incomplete comment as a whole;
a failed retry preserves any useful English from the earlier result and marks
the failed attempt. The original remains readable throughout. No new model
download or L5X analysis is required for this update.

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
`--retry` retries missing/failed/partial translations. There are no Git operations or
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
