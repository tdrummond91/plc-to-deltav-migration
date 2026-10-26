# Current handoff: PLC analysis workbench

## October 26 analysis blocked by preflight report tests (2026-10-26)

Returned work checks `20261026T162024Z-df5db8f5` and
`20261026T172248Z-e9e0a13c` both report sixteen application test failures,
`analysis.status = not_run`, `private_run_saved = false`, and no analysis/save
timings. No new October 26 analysis was created by those attempts; the workspace
therefore continued to show its earlier imported run. The previously reproduced
Application map capacity defect was real but did not explain these two runs.

The failures were stale exact-HTML expectations: `save_run` renders with captured
source bytes to qualify ladder drawings, while the expected reports in historical
workflow tests rendered without those bytes. Sixteen assertions now pass the
independently captured original fixture bytes, preserving full byte equality,
source-mutation checks, mismatched-source rejection and the normal test gate.
Parser evidence, display qualification and artifact contracts are unchanged.

Failed preflight output now explicitly states that analysis was skipped and no
new analysis was saved, distinguishes the feedback report from an analysis run,
and prints failure/error counts plus private log locations. It never opens the
workspace after a failed gate. The public feedback schema and manual Git transport
remain unchanged. Independent review found no blockers.

Validation: the exact work-machine application selection passed all 2,156 tests
(two skips), and all 139 helper tests passed. Both runners exited successfully.
The sixteen originally failing tests also passed independently after the fix.

A complete synthetic analysis using the same work-check analysis options saved
a new October 26 manifest and imported it into a temporary project with the
matching run timestamp and fourteen captured rungs. After pulling this fix, stop
the old workspace and run `bash ./run-work-check.sh` once: unlike reopening an
existing completed analysis, these failed attempts require a fresh run.

## Visible analysis identity and large application maps (2026-10-26)

The sticky header, Project tools and Home now show the selected manifest's
analysis creation time in the browser's local time zone, including seconds and
zone. Project tools retains the complete run ID and snapshot; the run chooser
lists dated choices and marks Current / Newer, not loaded / Previously imported.
Missing or invalid legacy dates remain explicitly unavailable. Import time and
filesystem timestamps are not substituted for analysis time.

Read-only saved-run discovery occurs on opening Project tools, returning focus
to a workspace window and refreshing project state. It flags a newer saved run
without switching source, changing revision or replacing pending edits. No
timer, listener or Git operation is involved. An occupied workspace port still
prevents automatic import; the terminal now explains how to select the already
completed run. Other failures after successful import do not claim it was skipped.

The Application map previously duplicated expanded value and owner provenance
records, exceeding its 96 MiB projection limit at realistic export sizes. It now
reuses authenticated values and owner context, expanding full provenance only
for requested pages/details. The limit is unchanged. An independently invented
6,600-owner / seven-member case exposes 52,852 register records and passes late
pagination, exact search, values and provenance checks. Capacity failures now
have a distinct visible explanation; missing/invalid evidence remains separate.
This fixes a reproduced scale defect, not a confirmed diagnosis of the private
work-machine symptom. Upstream evidence and response limits still apply.

After a manual pull, Stop workspace and run `bash ./open-workbench.sh`. Choose
the latest completed run under Project tools if needed; no parser rerun is
required. Existing saved decisions and source artifacts are retained. Browser
checks used invented source: current/newer run selection, timestamp change on
import, matching header/tools/Home, and 680px/normal desktop layouts. All 709
workspace/project-store tests passed, including the large-population regression.
Independent review found no remaining blockers. No private plant data was used
for the reproduction.

## Application map and representative-export re-audit (2026-10-23)

New **Application map** Home/Page entry separates Phase 1 source evidence from
editable migration interpretation: Hardware route, Registers & data, Coverage.
It shares authenticated saved-run indexes and supports historical read-only
requests without changing the selected run, review revision or saved decisions.
Connection attributes, parent-port attachments, raw payload containment, scoped
declarations, types, access sites and exact expressions remain traceable.

Scalar array elements now inherit qualified parent datatype/radix. Duplicate
paths and contradictory declaration/data metadata remain unresolved. Static
in-bounds arrays and UDT members resolve from declarations without fabricating
missing values. Exact description candidates, UDT definitions, backing/module
fallbacks and conflicts remain distinct. Cached translations use full original
text even when the visible preview is bounded. Field I/O labels physical layout
separately from numeric candidates; prior names and packages are preserved.

Re-audit used fourteen pinned public Rockwell exports plus invented route,
payload, namespace, alias and metadata-conflict fixtures. All public files
construct successfully, but several intentionally expose unsupported/protected
regions or noncanonical AOI wrappers; success is not semantic completeness.
ST/FBD, indirect addresses, copy ranges, AOI side effects, generic drive decoding
and comment-derived equipment conflicts remain explicitly limited. See the
[audit, evidence matrix and start path](docs/reviews/APPLICATION_MAP_REAUDIT.md).

After a manual pull, stop/reopen with `bash ./open-workbench.sh`, then choose
Application map. Existing imported source is sufficient; the normal
`bash ./run-work-check.sh` remains available for a fresh local analysis. No
work-PC automatic Git transport, listener, external translation, source artifact
schema or bounded return-envelope change was introduced.

Validation: 770 broad workspace/store/review tests and 193 focused integration
checks passed, followed by targeted checks for the final UDT-description changes.
Independent review found no remaining blockers after reproducing and closing
the metadata/description defects. All fourteen public exports were rerun through
the final projection and every register detail was checked. Browser interactions
and DOM layout bounds passed on invented data; screenshot capture timed out.

## Controller sections, full rung cards and retained translations (2026-10-23)

Field I/O keeps individual channel rows inside collapsible controller sections,
with Expand all/Collapse all and filtered controller totals. Source descriptions
wrap inside their cells. Original alias/base metadata includes alias target,
datatype, captured radix and external access; variable hovers also retain the
referenced alias description beside the resolved backing declaration. Unsaved
DeltaV names start from the source alias, otherwise its exact address. Proposals
remain unreviewed; existing saved names, including deliberate blanks, win.

An exact floating channel member with a qualified, unique decorated Data
representation and an input/output direction can suggest AI/AO even without a
documented card layout. Conflicts, ambiguous representations, status/configuration
and known output echo remain excluded. This does not certify a wired point:
source field type remains unresolved until documented or explicitly reviewed.

Rungs now use complete shared ladder drawings loaded near the viewport (at most
three requests concurrently), instead of truncated instruction previews. Card
headers put the rung at left, hierarchy in the center, and Connections/Open rung
at right. Page-size controls cover workspace directories, routines, source
members and report tables: 10/50/100/200/500 for ordinary lists; connection
diagrams use smaller choices and retain graph node/edge bounds. Existing API
defaults remain compatible. Field-signal and connection responses have 8 MiB
limits. Page changes preserve filters, drafts and off-page selections.

Completed translation results already persisted, including partial/failure
results. Interrupted inference now records an attempt in the local sidecar;
unchanged incomplete entries require **Retry incomplete translations** rather
than silently running again. Failed retries preserve earlier usable English.
Attempt changes invalidate rendered translation caches. Progress distinguishes
prior reuse from new/retried wording and saved gaps. The work-PC's reported
6022/6701 recurrence was not reproduced against its private cache; interruption
is a tested gap, not a confirmed diagnosis of that specific count.

After a manual pull, stop and reopen with `bash ./open-workbench.sh`. Existing
saved analysis is sufficient; no L5X rerun or model download is required. The
normal work-check entry point remains available. No automatic Git transport or
listener was added. UI proof uses invented source only.

Validation: all 700 workspace/project-store/related review tests passed;
translation service, API, UI, preparation and local-engine checks separately
passed 115 tests with one optional skip. Independent reviews found and fixed
retry wording loss, attempt-state cache invalidation, ambiguous profile hints,
the classification page-size default and stale connection focus. Browser DOM
checks verified controller collapse/expand, page sizes, retained saved names
and complete ladder loading. Screenshot capture was unavailable in this session.

## Individual field signals and editable DeltaV packages (2026-10-22)

Field I/O now starts with individual captured channel rows: type, alias/address,
source wording, DeltaV name and package status. Hardware is an information
popover with module/controller source links. The old module-card API remains
read-only for compatibility; the workspace loads the new signal assets.

`workspace_field_signals.py` projects exact captured channel addresses, dedupes
aliases and keeps unsupported member mappings as explicit candidates. It never
creates wired points from catalog capacity. It suggests bounded, source-qualified
one-hop related rungs through shared addresses, including another routine.
Suggestions do not automatically become accepted package members or establish
execution/dataflow, alarm consequence or a DeltaV class allocation.

Schema 2 adds durable editable signal IDs and explicit source bindings. Signal
names/descriptions/types and group `signal_ids`/`member_roles` are separate from
immutable source evidence. Users can keep a signal with chosen scaling, alarm,
reference and logic rungs in one package, including several packages per signal.
Legacy group edits preserve new memberships unless explicitly changed. Imports,
undo, backups and source correspondence preserve names and package references;
changed exports require explicit reconnect/revalidation rather than name/slot
matching. Schema-1 upgrades are additive and transactional. Backup restoration
copies from a read-only SQLite connection before migration.

The browser retains drafts across row/page navigation, binds saves to the
revision that supplied the form data, and offers an explicit latest-version
review after a conflict. It rejects rebasing onto a differently bound signal.
Same-snapshot reruns can confirm unchanged evidence without a redundant rebind.
Rows return compact package summaries/history counts so membership/history is
not duplicated throughout the channel directory. Whole-source report/parsing,
confidentiality policy and manual work-machine Git transport are unchanged.

All 626 workspace and project-store tests passed. Independent store/projection
and API/UI reviews are clear. Review found and
fixed stale-response revisions, large repeated record payloads, and source
correspondence/conflict edge cases. Chrome verified an invented AI name save,
a package containing scaling plus an alarm rung in another routine, persisted
names/membership/roles after server restart, group-to-signal navigation,
hardware details and dismissal, and a narrow 680px split-screen layout.
Ignored preview/proof files are under `confidential/field-signal-preview/`.
No work-machine physical I/O totals are claimed from these invented tests.

After a manual pull, stop and reopen with `bash ./open-workbench.sh`, then
choose **Field I/O**. Existing saved source companions suffice; no new analysis
run is required for this UI/data-model change. The normal work-check entry point
still works. PCSD/FHX emission and target-class allocation remain later work.


## Restore I/O wording and complete the routine drawing paths (2026-10-22)

The report's Routine ladder, Ladder directory and operand-reuse lists still
used text snippets after the individual-rung and pattern views gained drawings.
They now share the same ten-row graphic table, branch/equation rendering,
85% initial scale, help controls and scope/comment context. Narrow-window
context panels use space above or below the rung rather than covering its
click target.

Field I/O's previous DI/DO figures counted module declarations, not physical
points. Its 39-model lookup also omitted many analogue and infrastructure
products. The offline library now contains 223 exact vendor/catalog identities:
1756 digital, isolated/HART/RTD analogue and mixed cards, controllers and
communication products, plus selected 1794 analogue cards. Each record keeps
its vendor publication, page, function and rated/configuration-dependent
capacity. The four independently documented member layouts remain a separate
gate; recognizing a card does not prove which addresses map to wired devices.

The page separates controller/network records, mixed cards and unclassified
records with explicit reasons. Filter counts include mixed cards in each
supported category; disjoint module totals avoid double-counting. Manufacturer
functions remain separate from plant-authored descriptions. Zero recognized
AI/AO cards is explicitly incomplete recognition, not evidence of absence.

`workspace_io_comments.py` recovers direct/localized descriptions and
Comments/Comment Operand notes from the authenticated snapshot. Only exact
module/root/member and qualified alias-to-member joins attach prose; unrelated
tag comments do not consume the bounded I/O annotation budget. Cached English
wording is displayed without starting translation. Eight-note/512-character
previews link to the owner's complete paged report annotations, with a complete
comments directory for additional owners. Source bytes, saved analysis,
review decisions and work-machine Git behavior are unchanged.

Independent review found and fixed the unreachable full-comment links and
unrelated-comment budget issue. All 202 related catalog, annotation, field-I/O,
variable, report, workspace and language tests passed. Chrome verified an
invented ten-module export: HART/mixed filters, separate infrastructure roles,
matching channel/alias wording, complete long comments and later annotation
pages, ten-drawing routine pages and zoom, and first-click rung navigation at
400px width. Full-note search also includes text beyond the preview and ninth
notes. The preview project and screenshots are ignored under
`confidential/field-io-coverage-preview/`; temporary tabs/server were stopped.
Existing work-machine counts are not yet revalidated: this PC has only invented
examples and the bounded aggregate.

Manually pull, stop the existing workspace, then run `bash ./open-workbench.sh`.
These views can use existing saved source companions. Old standalone HTML files
keep their embedded presentation; use Full source analysis in the running
workspace, or rerun `bash ./run-work-check.sh` to generate a new standalone file.

## Patterns first and physical field-I/O inventory (2026-10-22)

Home and the Page menu lead with Patterns, then Field I/O. Patterns opens the
hosted evidence report in another window while preserving the editor selection
and saved source language. The report leads with pattern review, defaults to
descending numeric occurrence count, and supports ascending order. Pattern
occurrences reuse the shared ladder renderer in a two-column, ten-rung page.
Rung-number hover/focus context contains scope, routine, comment, parse status
and an editable-workspace link. Escape/outside click/navigation dismiss it;
shared instruction/member help, zoom and independent help windows remain.

Report syntax patterns include opcode spelling, arity and ordered branch shape;
operands/values are excluded. This is not behavioral equivalence or a bulk
classification edit. The existing editable `rung_pattern` category-rule contract
does not include arity and is unchanged. Do not imply identical membership or
save review decisions against snapshot-bound report pattern IDs.

Field I/O is a bounded read-only projection of authenticated source companions,
reusing the per-run variable index. It lists module cards by controller, parent,
declared slot, catalog, source description and recorded address/rung uses.
The exact catalog library recognizes 39 Rockwell 1756 DI/DO/AI/AO declarations.
Four documented member layouts (1756-IB16, 1756-OB16E, 1756-IF8, 1756-OF8)
require the correct direction and a unique qualified captured data profile.
Output echo/status, unknown catalogs, unsupported profiles, dynamic addresses,
ambiguous/foreign data and unresolved rack aliases are not promoted to points.
IF8 input mode stays unresolved; no installed-device or terminal claims are made.

Documented point addresses sort first; other addresses stay in a collapsed
section. Counts distinguish module cards, rated/configuration-dependent capacity
and mapped address records. Pages cap modules/addresses at 24, uses at 12 and
alias previews at 8; full source links remain. Cached FR/EN wording is displayed
without initiating translation. Whole-module selection uses the existing
revision-checked group editor and store; it never pretends to save a derived
channel ID as a source entity. Run/project changes invalidate selections and
late responses. No parser artifacts, source facts or work-PC Git workflow change.

Vendor evidence: Rockwell's 1756 digital/analog wiring catalogs; digital manual
1756-UM058L (September 2026), tables 44/48/49 and page 157; analog manual
1756-UM009G (March 2025), pages 130-131. Rendered manual tables were checked where
text extraction misaligned the analog datatype cells. References are linked
from the implementation and catalog details.

Validation includes source-authentication, namespace/type/address gaps, output
echo exclusions, page bounds, aliases, stale UI responses, shared cache reuse
and eviction, grouping, translations, numeric sorting and repeated rung numbers.
A synthetic 4,606-rung profile took 4.33 seconds for cold shared authentication,
0.18 seconds for the field projection, and 0.001 seconds for a cached selected-card
page (local measurements, not a work-PC guarantee). The final related suites
passed 221 tests. One initially mistyped test-module name was corrected and its
API suite passed. Independent review found and resolved an XML boolean display
bug (`Upstream="false"`/`"0"`); cache-eviction coverage confirms at most two shared
run indexes and unchanged project selection.

Chrome checks in the invented `confidential/field-io-preview/` project verified
point-first DI/DO/AI details, output-echo exclusion, use paging across two scopes,
English fallback, saved whole-module grouping after reload, pattern order in
both directions, ten-drawing paging, context dismissal, same-number rung scope
and independent instruction-help windows. Browser popup blocking exposed the
expected direct-link fallback, which opened the Patterns report successfully.

Manually pull, stop the running workspace and reopen with
`bash ./open-workbench.sh`. Existing saved analysis can supply these views;
rerun `bash ./run-work-check.sh` only for new analysis or missing companions.

## Visual report rungs and saved variable evidence (2026-10-22)

Engineering-review rung details now reuse the Programs & routines ladder
renderer, including branch geometry, colored operands, operation notation,
zoom, full original source and instruction help. Hosted `/analysis` refreshes
the saved report with current trusted assets; it does not replace its evidence
or require an L5X rerun. Newly generated standalone reports include offline
drawings and instruction examples. Saved variable lookups and separate help
windows are available through the running workspace.

Timer/counter blocks can display unambiguous exported PRE/ACC values even when
the instruction contains question marks. Hover or focus a variable for its
declared scope, member meaning, stored representations and possible write
sites. Ctrl-click keeps the same saved-run evidence in a separate window.
Exact member assignments, whole-control uses and possible overlaps remain
distinct. Exported settings are not live values or guaranteed startup state.
Unknown custom members retain their captured values without inferred meanings.

`workspace_variables.py` authenticates saved inventory, references, access and
tag-data evidence before building a bounded per-run index. No analysis artifact
or review record is rewritten. Case-insensitive member joins preserve original
spelling and withhold ambiguous values. A synthetic 4,606-rung / 6,000-owner
profile took 7.1 seconds for the first authenticated lookup and 0.011 seconds
for a cached member; this is a local measurement, not a work-PC guarantee.

Manually pull, stop the existing workspace and reopen it. Existing saved
analysis companions supply the member information; a parser rerun is needed
only if the required companions are absent, or to produce a new standalone
report file.

Validation: 117 combined rendering, member/API and report tests passed. Follow-up
HTTP/CSP, disconnect and offline-help regressions passed after browser checks
exposed the old opaque-origin report header. Independent reviews covered the
backend, shared UI and trusted report boundary. Chrome verified exported
PRE/ACC values, local/global shadowing, an unknown custom member, exact versus
whole-control writers, and report Ctrl-click help windows using invented data.
The refreshed report uses only the installed scripts and their CSP hashes;
raw imported HTML retains its restrictive sandbox. Standalone reports remain
offline, and no parser source facts or review decisions are modified.

## Equality comparison notation (2026-10-22)

EQU now uses == in the shared ladder drawing, equation renderer (including rung
previews), and worked help example. Assignment expressions keep the left arrow.
The CPT worked example describes simplification with "becomes" instead of an
equals sign so it cannot be mistaken for an assignment. Captured source remains
unchanged. All 49 focused rendering/help tests passed; Chrome verified EQU next
to MOV in both drawing and equation views, plus the EQU help example. Manually
pull and refresh the workspace; no L5X reanalysis is required.

## Wheel navigation over rung drawings (2026-10-22)

The shared ladder viewport used overscroll containment on both axes, trapping
vertical wheel gestures even when the drawing had no vertical overflow. Only
horizontal containment remains; vertical scrolling now continues to the parent
page or pane at the drawing boundary. Native drawing scrollbars and zoom remain.

Chrome checks on invented data reproduced the stuck page before the change,
then verified wheel-down/up over a rung, navigation over a branched rung, and
horizontal scrolling inside a zoomed wide rung. This CSS-only fix requires a
manual pull and workspace reload, with no L5X reanalysis.

## Readable operations inside ladder blocks (2026-10-22)

The ladder drawing previously sent every non-contact/coil through a generic
numbered-operand layout, even though the equation view knew many operations.
Known comparisons now display A != B, A >= B and the corresponding tests.
Arithmetic, moves, clears and unary operations show destination ← expression;
CPT retains its captured expression/grouping without a second parse. NEQ uses
!= in the equation view too. SVG programming ligatures are disabled so those
characters remain visible as written.

Timers/counters label their structure, Preset and Accum; one-shots label storage
and pulse output; RES names its target without implying a whole-object clear.
PID shows all seven fields in captured order, including master-loop and hold
operands. These are captured parameters, not live values. Wrong arity, blank
operands and custom instructions retain the generic source layout. Contacts,
coils, branch structure, original text and review data keep their meanings.

Card dimensions are computed before branch layout, including tall PID blocks.
Long calculations retain their destination/operator on two lines as needed;
full arguments remain available in hover help and selection. This is a display
update: manually pull and reopen the workspace, with no L5X reanalysis required.

Validation: 116 focused tests passed across ladder/equation rendering, routine
browsing, workspace integration and instruction-help content. Independent review
found no blocking issues. Chrome checks used invented source data to verify
comparisons, destination order, stateful fields, long operands, branch spacing
and working F1 help; rendered semantic text stayed inside its block bounds.

## Interactive instruction help and independent windows (2026-10-22)

Hover help now uses an interactive panel instead of native browser tooltips.
Ladder symbols, equations, previews, flow blocks, branch expressions and opcode
headers expose explanations, complete captured arguments and worked examples.
The 31 supported instruction shapes have deliberately invented examples;
custom/unsupported effects stay unresolved. Stateful examples link to verified
Rockwell documentation and state their execution/state assumptions.

Ctrl-click opens a new read-only help window each time. Windows capture both
instruction and analysis IDs and validate the historical source response, so
later navigation or imports cannot silently retarget them. F1, Ctrl+Enter and
the panel's Open help window button provide keyboard/visible alternatives.
Outside click, Escape, navigation and source changes dismiss transient help;
moving into its panel keeps it readable. Pointer-caused focus cannot insert a
panel before a click completes. Popups use local assets/read APIs, with safe text
rendering, bounded content, blocked-window fallback and timeout/retry handling.

Validation: 137 focused tests passed across content, interaction, renderer,
routine/flow/workspace integration and historical source reads. Independent
review and browser checks caught and resolved pointer-focus and narrow-placement
issues; reconciliation also explicitly propagates its historical run identity.
Chrome checks used invented data for multiple simultaneous Ctrl-click windows,
keyboard/equation help, unknown instructions, dark/light themes and a 900px
viewport with the panel clear of its instruction. Transient help inside a native
dialog shares that dialog's top layer. No parser or plant evaluation is performed.

Save/stop, manually pull and reopen with `bash ./open-workbench.sh`. No L5X
reanalysis or translation rerun is needed. Parser/source/review data are unchanged.

## Rung variable colors, comments and operation help (2026-10-22)

Variable names now have distinct reading colors across routine ladder drawings,
Rungs previews, equations, flow, branch selection and complete argument lists.
The palette is assigned by exact spelling in source argument order within each
rung; repeated names retain their color, and the six colors repeat when needed.
Operators/opcodes and contact/coil symbols use orange; constants stay neutral.
Colors do not establish bindings, input/output roles, alarm rank or live state.
Indexed addresses remain opaque labels and shortened labels retain full identity.
Shared source-colors.js/css are local assets served through the workspace allowlist.

Blocks/expressions expose bounded operation summaries on hover. SVG symbols also
have accessible descriptions and show the summary with selected arguments.
Summaries reuse the existing explanation rules; unsupported/custom instructions,
wrong arities and malformed records remain explicit. No new execution semantics
or source edits are introduced.

The routine API still supplies original comments separately from translation.
There was no observed path stripping nonblank comments, but empty comments were
hidden and whitespace-only comments looked blank. Those cases now say
Rung N — No comment. Original comments remain visible when English is missing;
long comments retain their expandable preview.

Validation: 124 focused tests passed across the renderer, exact text/highlighter,
both theme contrast palettes, equation/hover semantics, routine comments/API and
workspace UI. Independent review caught and resolved opcode CSS specificity and
a whitespace-only argument preview edge. Chrome checks used six invented rungs
to inspect actual SVG/MathML colors, comment/no-comment headers, raw expression
fallbacks and unknown-block help in dark and light themes. Save/stop, manually
pull and reopen with `bash ./open-workbench.sh`; no L5X reanalysis is needed.

## Compact comments and partial English (2026-10-22)

Programs & routines now previews long comments in about three lines, with Show
full comment / Collapse comment. Complete wording remains available; expansion
survives language-only updates on the current rung page. Translation status stays
outside the preview, and keyboard access reveals controls inside longer comments.
The main header is opaque and sticky at every width with a stronger cyan edge.
Its measured height offsets sticky lists, inspectors and dividers, including
wrapped headers; anchor scrolling and the Project tools menu use the same space.

English mode immediately displays the original when a translation is unavailable.
Accepted English sentences/lines now survive a neighboring segment's failure;
rejected portions retain exact original wording and formatting, marked English
partial. Identifier/value, negation, end-token and bounded-work checks still apply.
The full evidence report also displays these partial results and source fallbacks.
Existing source facts and saved review decisions are unchanged.

The translation cache adds partial status and segment counts without changing the
model/rule identity or invalidating completed translations. Retry missing
translations explicitly retries failed/partial comments, rechecking each comment
as a whole. Old failed entries need that one-time retry to benefit from segment
fallback; the original is readable immediately. No new model setup or analysis
run is required. Save/stop the workspace, manually pull, then reopen with
`bash ./open-workbench.sh`.

Validation: 209 focused tests completed successfully (one existing symlink skip),
including the installed offline model, cache migration/retry, report/source
fallbacks, comment disclosure and responsive header offsets. Independent review
found no remaining blockers. Chrome checks used invented comments with seeded
partial, failed and completed translations: three-line preview, full expansion,
FR/EN continuity, visible status, desktop scrolling and 480px wrapping without
page overflow. The Rungs inspector remained below the pinned header.

## Compact Programs & routines (2026-10-22)

Routine drawings now start and reset at 85% with tighter instruction heights,
branch gaps and vertical padding. Comments share the rung-number header; zoom
controls and Open rung review sit on its right and wrap in narrow windows.
Short two-argument blocks, including GEQ, place their numbered operands on one
line with a visible separator. Long previews retain stacked slots, with complete
values in symbol details, tooltips and original source text.

The repeated instruction-count/path/neutral-state sentence is now explained once
in How to read these ladders. Routine source-order numbers are retained in the
accessible symbol labels without another visible line under each block. These
changes apply only to Programs & routines; other drawing views retain their
existing scale. Translation-only updates preserve drawings, selection and zoom.

Validation: 36 focused ladder-renderer, routine-browser and routine-API tests
passed; independent review found no blockers. Chrome checks used four invented
rungs: short GEQ operands, nested branches with an empty bypass, long operands
and comment, and an uncommented timer. Verified 85% reset, text within symbol
bounds, and wrapped header controls at 480px without page overflow. These are
presentation changes; reopen the saved workspace without reanalyzing the L5X.

## Analysis directory and page access (2026-10-22)

Full source analysis is the first Home card and Page-menu destination, removed
from the general Project tools menu. It opens a separate evidence window, keeps
the editor's selection and unfinished review, and offers a native new-tab link
when popups are blocked. The server applies the saved source-language setting;
native modified clicks also work before the language status finishes loading.

Home cards, page headings, source popouts and the evidence report identify
Read only or Read & write and explain what is adjustable. These describe page
content, not security permissions; global Project tools remain available. Source
L5X evidence stays immutable, engineering decisions are separate project records,
and the guide checklist stays in this browser. No current page is write-only.
Source-only access wording hides when its popout returns to normal browsing.

Validation: 95 focused workspace, translation and evidence-report tests passed.
Chrome checks on invented source verified the new analysis window, directory/menu
order, saved English on reopen, editable-page labels and source-mode label
dismissal on return to Home or internal Connection map navigation. Existing saved
analyses need no rerun.

Home cards are now full-card native links, with no separate bottom link. Clicking
the heading, description or card space opens its page; Tab/Enter and modified
clicks retain normal link behavior. Hover and keyboard focus identify the card.

## Header language shortcuts and consistent page order (2026-10-22)

Compact FR/EN flags now sit immediately to the right of the PLC Workbench brand,
vertically centered on the same line. EN uses the Canadian flag in both locations,
as requested. Project tools retains its language controls
and bilingual option. Both sets share one translation controller and request
guard; they disable together during changes and mirror the saved setting. Both
header flags are highlighted in bilingual mode. No additional polling, preference
store, model or translation cache was introduced.

The Page dropdown now follows the Home cards: Full source analysis, Programs & routines, Rungs, Ladder
map, Connection map, Classification & groups, then Tags & source objects. Home
remains the first navigation option.

Validation: 69 focused translation/workspace UI tests passed, including a shared
control regression for pending requests and bilingual synchronization. Independent
review found no blockers. Chrome checks on invented data verified header-to-tools
and tools-to-header switching, identical card/dropdown order, and centered header
alignment at desktop and 480px widths. Existing saved analyses need no rerun;
save and stop the old workspace, manually pull, then `bash ./open-workbench.sh`.

## Language shortcuts and overlay dismissal (2026-10-22)

**Project tools → Source language** now uses **FR / French** and **EN / English**
buttons with local SVG flag icons, including on Windows without flag-emoji
support. French is the original source wording, including any mixed-language
comments. The backend retains `original`, `english` and `both` identifiers, so
saved preferences and cached translations remain compatible. **Show both
languages** toggles the bilingual display; pressing it again returns to English.
Switching to French does not cancel translation preparation or discard its cache.
Names, logic and saved engineering decisions are unchanged.

Project tools closes on outside click or Escape. Native modal dialogs accept
backdrop clicks through the existing dirty/save guards; dialog padding, drags,
cancelled pointers and non-primary gestures do not trigger dismissal. Escape
uses the same guard. Pinned map information closes on outside pointer input and
cancels queued/late previews. Native dialogs take Escape priority. Inline help,
routine expansion and other non-overlay details retain their existing behavior.

Validation: 103 focused translation UI/API, workspace UI and ladder-map UI tests
passed across targeted suites. Independent review found no blockers. Chrome
checks on invented data verified saved FR/EN/bilingual choices, continued/cached
preparation, flag layout at 480px, menu outside/Escape dismissal, clean dialog
backdrop dismissal and the expected unsaved-edit confirmation. Browser automation
could not dismiss that native confirmation; declined-discard and in-flight-save
protection were verified by the regression tests. No proprietary source was used.

Work-PC use: save and stop the older workspace, manually pull this branch, then
run `bash ./open-workbench.sh`. No parser or translation rerun is required.

## Dedicated routine ladders and project controls (2026-10-22)

The permanent sidebar is removed. **Home**, the engineering **Page** selector
and **How to review** are header controls. **Project tools** contains the source
summary, **Choose analysis run**, the single **Source language** controller,
**Changes & reconciliation**, reviewer, refresh, theme and backup/restore.
Successful navigation closes the tools menu; unsaved-review guards remain in
place. The expanded menu stays within narrow viewports. Earlier sidebar/Menu
instructions below describe the previous version.

**Programs & routines** is a separate full-width page. Top filters cover name/
path, program or AOI scope, and routine type. Native disclosure arrows load one
routine at a time, using 50 directory rows and 20 captured rungs per page.
Same-named AOI routines keep distinct scope IDs. A read-only `/api/routine-ladder`
route uses saved inventory and cached source qualification, preserves source
order, rejects stale run IDs, and does not rerun analysis or start translation.

The new local SVG renderer draws qualified XIC/XIO contacts and OTE/OTL/OTU
coils, retaining other instructions as labeled blocks with complete arguments.
Series order, nested split/join paths, mid-rung outputs and empty bypass legs
are preserved. Selecting a symbol opens its source inspector and arguments;
**Open rung review** opens the exact rung with its routine filter. No live
states, equipment consequences or target class allocation are inferred.
Unsupported, malformed or oversized structures retain complete original text.
Limits are 160 instructions, 1,200 structure nodes, depth 64, extent 40,000,
128 argument slots per instruction and 131,072 text characters for drawing.
Non-ladder/empty routines remain visible with source links and explanations.

Routine requests discard obsolete results after collapse, navigation, changed
analysis or changed project. Translation-only refreshes preserve drawings,
zoom and selection, including a pending request for another rung page. Retry
has one current warning and clears it on recovery. Different-run refreshes
also clear obsolete Rungs routine filters.

Validation: 181 focused workspace, routine API/controller/renderer, map, family,
reading-layout, equation, explanation and flow tests passed. Final integration
wording and accessibility changes passed the overlapping 39 workspace UI and
14 routine controller tests. Independent review found no remaining blockers.
Chrome checks used independently invented 28-rung data with a 26-rung routine,
two same-named AOI routines, ST and empty routines. Verified complete two-page
access, exact rung review, scope/type/search filters, nested branches, zoom,
non-ladder guidance, header help, tool navigation and 480px/800px layouts.
No proprietary source was opened and no saved engineering decision was changed.

Work-PC use: save and **Stop workspace**, manually pull this branch, then run
`bash ./open-workbench.sh`. Existing saved analyses work; no full work-check or
translation rerun is required. No automatic Git or background listener was added.

## Workspace navigation and readable logic (2026-10-22)

The default entry is now **Home / page guide**, with actual page links, filter
explanations and the existing checkable review guide. **Menu** collapses the
sidebar; **Home** and **Page** stay available. Reviewer name, refresh, theme and
backups live under **Project tools**. A successful popout hides only its matching
clean source pane; **Show source** restores the retained inspector. Drafts must
be saved before moving their source, and blocked popups do not collapse it.
Explicit navigation out of a source-only window clears that layout and URL mode.
Popouts remain independent selections sharing saved project revisions.

**Logic summary** precedes the existing flow/equation/source tabs. It lists
captured operands, follows nested branch-local conditions/actions and describes
supported output writes in plain language. Boolean contact equations use TRUE
and FALSE instead of the negation glyph. Derived output conditions include the
rung-entry gate. Stateful/unknown blocks stop Boolean simplification; unsupported
or oversized structures fall back to complete original text. Instruction meaning
requires source qualification from the cached snapshot check. No live state,
alarm consequence, priority or DeltaV class allocation is inferred.

Rungs and Ladder map share qualified function-family filtering. Missing family
choices after a different import/restore/refresh are cleared before rendering
results. These are instruction families, separate from engineering function
groups and reviewed categories. Map Help, captured-description and signal-name
toggles explain the display. Pinned panels have local Unpin/Close controls;
Escape, pan, zoom, filters and view changes cancel pending previews. A delayed
response cannot reopen a dismissed panel.

**Stop workspace** explicitly stops the local server. Chrome's X continues to
close only its window; other windows and background translation can keep using
the server. Ctrl+C in the launcher terminal is the other stop method. No
automatic Git or new background process was added.

Validation: 196 distinct focused workspace, explanation/equation, map, connection,
family-filter and reading-layout tests passed across the targeted runs. Initial
test selection included two nonexistent module names; the intended suites were
then run successfully. Independent review caught and verified the family-reset
and rung-entry wording corrections. Chrome checks used the existing invented
nine-rung project: branch/alarm summaries, Home links, menu, popout collapse and
restore, map descriptions/help, pinned Close/Escape, and 800px/480px layouts.
No proprietary source was opened. Saved review data and the analysis are unchanged.

Work-PC use: save and stop the older workspace, manually pull this branch, then
run `bash ./open-workbench.sh`. No full work-check/translation rerun is needed.

## Whole-ladder visual map (2026-10-21)

**Ladder map** adds complete rung discovery, viewport-limited SVG rendering,
zoomed-out count tiles, drag/pan/zoom, source/comment/routine/function filters,
and a paged keyboard list. The shared connection index supplies exact-address
signal buses, paged fan-out and explicit offscreen/unknown-role counts. Full
rung logic remains in the existing inspector; cached hover details link to
supported captured declarations and AOI parameters. A separate map qualification
projection rejects unsupported rung text, declarations and alias associations
before filtering, counts or edges. Original source remains visible for review.

The map inspector uses independently persisted reading-layout preferences.
User-initiated map/source/connection popouts share the local project, with
independent selections and **Refresh saved data** for other-window saves.
Refresh retains edits/navigation begun while its request was pending, including
the original form revision. Popouts omit the server-stop button. No new network
service, background Git operation, model or runtime dependency was added.

Bounds: metadata pages250, visible rung cards80, signal pages80, rendered edges320,
hover cache80, hover block/parameter lists64. Remaining records stay reachable
through lists, signal filters and original source. Diagram placement is temporary
view state; arrows do not establish execution order, live Boolean states, member
overlap or implicit instruction effects. The underlying original neighborhood
connection view retains its existing model; the new map projection adds XML
qualification gating without rewriting saved analysis artifacts.

Validation: 139 focused map, connection, workspace, reading-layout and rung-flow
tests passed. The final pending-hover pin correction passed all 17 map UI tests
(overlapping coverage). The map UI suite includes 10,000 indexed rungs.
Independent review found and verified fixes for stale filters, pending-refresh
edits and unsupported XML associations. Chrome checks on invented 271-rung and
nine-rung exports covered full-comment search, 268-rung signal fan-out, card
dragging, tile zoom, a 380px map pane, complete parallel branches, pinned AOI
parameters, separate source/connection windows and saved edits refreshed from
another inspector. Unpinned previews let pointer clicks pass through. Popup
input automation timed out; saved-edit interaction was verified in an independent
source-inspector tab using the same page. No plant source was opened.
Work-PC use: manually pull, close any older workspace and run
`bash ./open-workbench.sh`, then choose **Ladder map**. The usual
`bash ./run-work-check.sh` also opens it; another full analysis is unnecessary
when the saved run already includes the connection artifacts.

## Functional classification workspace (2026-10-21)

The editable workspace now exposes **Classification & groups** before any manual
group creation. `workspace_classification.py` projects authenticated saved report
companions plus the captured snapshot into deterministic source/address groups,
PID and stateful objects, captured parameters, and residual rung functions.
The XML read qualifies namespace/binding paths; it does not rerun the analysis
pipeline. DC means a true/false calculation; AC requires a floating-point result.
Typed module data supports AI/AO/DI/DO candidates. Status flags, packed integer
channels, unsupported types/namespaces, and unresolved instruction functions do
not gain physical signal identity through these labels.

Groups support multiple function categories and a separate reviewed migration
disposition. Adoption copies canonical source memberships into a saved group;
it never changes source artifacts or confirms engineering meaning. Existing JSON
group records gain optional classification/disposition/proposal fields without
a database schema migration. Omitted fields survive membership-only edits.
Imports flag changed source/proposal evidence; a per-group content signature
also detects provider changes stored only in the report. Stale exclusions remain
visible for investigation. Source changes do not automatically match old groups.
Removing members limits saved decisions to the edited group; the original
proposal remains in scope rather than inheriting a subset's exclusion.
Manual source category rules remain distinct from these function group proposals.

The browser filters by function, migration decision and text. Evidence disclosures
load their DOM lazily; source links and group-editor members page in batches of
50. Projection limits are 20,000 groups, 100,000 memberships, 100,000 displayed
parameters total and 128 parameters per group. Limits are explicit and never
remove original evidence. This is review organization, not approved DeltaV class
allocation, physical wiring inference, runtime simulation, or FHX generation.

Validation: 153 classification/workspace/store/presentation tests passed before
final refinements; the final focused run passed 104 tests (overlapping coverage).
Review findings were fixed with real-parser regressions for foreign owners,
attributes, aliases, scopes, Text, decorated data and ambiguous structural
ancestors, plus API tests for partial/empty group exclusions. Browser checks on
an invented nine-rung source verified automatic groups, PID parameter evidence,
AC and AI filters, source navigation, saved multi-function migration edits, and
theme switching. Work-PC use: manually pull the development
branch, close any older workspace, run `bash ./open-workbench.sh`, then choose
**Classification & groups**. A full work-check rerun is unnecessary for this view.

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

## Reading layout and local English wording (2026-10-21)

The rung/source divider now resizes by pointer or keyboard. Equation-only text
defaults to 75% of its earlier size, adjustable to 50/75/100/125%; the browser
retains the split and size. Narrow windows stack the panes. Object layouts,
original expressions and engineering decisions are unchanged.

Optional French-to-English neural translation uses pinned CTranslate2 and
SentencePiece with the Argos fr-en 1.9 model. The explicit
`bash ./setup-translation.sh` command installs packages and a hash-verified public
model under ignored `confidential/translation/fr-en`. Normal launches never
download a translation model or transmit comments. Ordinary locked `uv run`
was verified to retain the installed optional extra. After setup, the sidebar's
**Source language** control prepares captured comments/descriptions in
a CPU worker without blocking review. Identical text is reused across imports;
changed text or model/rules identities get new cache entries. Original text and
reviewed descriptions remain separate from generated wording.

The derived cache and enabled preference use `<project>.translations.sqlite`
beside the project, with separate SQLite connections per operation/worker.
This sidecar/model is deliberately not part of an engineering-project backup;
restored projects start translation disabled and can regenerate the wording.
Literal value/unit/identifier and obvious sentence-negation changes are withheld.
Those checks cannot establish translation correctness or control meaning.
The original saved analysis remains immutable; the English reading layer below
also supports the current static report presentation.

Validation: all 186 workspace regression tests passed, followed by 63 focused
engine/setup/cache/API/UI/work-check handoff tests after the review fixes (these
sets overlap). The latter includes the added retry regression, actual installed
model inference with socket connections forbidden, exact cache reuse, missing
runtime behavior and safe installation. Independent review found no remaining
blockers. Chrome checked drag/keyboard resizing, 75% sizing and persistence,
1050px stacking without horizontal overflow, both themes, mixed-language and
long-equation display, retained unsaved classification and reused translations.
The invented project stayed at revision 1. No application console errors were
reported. The disposable preview server was stopped. Saved screenshot:
`confidential/reading-preview/reading-verified.png` (independently invented data).

Work-PC next step: manual pull, one-time translation setup if desired, then
reopen with `bash ./open-workbench.sh`. The established `run-work-check.sh`
workflow remains available, but no full L5X rerun is required for these features.
Actual Quebec plant terminology still needs Tyler's review; synthetic checks do
not substitute for that acceptance.

## Prepared English analysis (2026-10-21)

Tyler selected an English analysis/view option with the original L5X retained.
`bash ./prepare-english.sh` now prepares the selected existing project before a
review phase and writes a private English HTML report, wording catalogue and
completion manifest beside it. Close the workspace first; reopen afterward.
There are no Git operations, model downloads, parser reruns or translated L5X
imports. Original/English/Both is a persisted reading preference independent of
background preparation. Original mode does not cancel an active batch.

`translation_catalog.py` reads the bounded saved XML and validates its snapshot
against inventory plus inert saved report evidence. It includes supported
localized/member/bit notes, SFC/FBD text boxes and source-verified SFC transition
comments, with explicit limitations for other embedded comments and unsupported
namespaces. The report exposes a searchable source-linked annotation index.
Canonical evidence JSON, IDs, executable text and reviewed decisions are
unchanged; derived wording is a separate inert overlay. Report cache keys include
source run, language and translation generation. Historical wording polls avoid
reloading the full analysis/calculation maps.

Inference packs multiple comments; the service saves 16-comment chunks, with
measured elapsed/estimated remaining time. Cache model/rules identities are
unchanged, so existing translations remain reusable. An invented 64-comment
installed-model benchmark produced identical results in 4.1 seconds batched
versus 7.3 seconds serial; this is not a plant workload timing guarantee.
Tyler's old-version 2,427/6,701 counter was increasing: the old whole-source
queue placed object descriptions before rung comments, so selecting a rung did
not prioritize it. Poll failures now replace stale waiting indicators with an
interruption message and bounded retries, retaining finished English wording.

Exports record known excluded notes or withheld wording as partial (exit 3).
An active-source change during preparation prevents a completion manifest.
Interrupted work retains completed cache entries; a new/restored project has a
separate cache. Source and engineering backups retain their existing semantics.

Validation: 217 workspace tests passed, plus 84 engine/catalog/report/preparation
checks (one Windows symlink-permission skip). After final polling recovery and
historical-instruction fixes, 70 focused tests passed with the same skip;
these test sets overlap. Independent review found no remaining blockers.
The actual Bash command created a report for an invented project and reused all
five unique translations on its next run. Chrome verified English list/detail
wording, Original/Both switching, English search, the source-linked annotation
index and readable unclipped cards. No application console errors occurred.
Saved proof: `confidential/reading-preview/english-verified.png`; preview tabs and
server were closed. Work-PC next step: close the old workspace, manually pull,
run `bash ./prepare-english.sh`, then `bash ./open-workbench.sh`. Actual plant
wording, speed and reuse of the work-PC cache still need that local confirmation.

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
