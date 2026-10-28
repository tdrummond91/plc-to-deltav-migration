# Field signal inventory and reference audit

The Field I/O inventory includes qualified addresses captured in aliases,
decorated tag values and member comments as well as ladder operands. An address
can therefore exist, inherit a module description and have no captured RLL
reference. An address used in logic can also lack an authored description. The
inventory count is not the number of wired devices or addresses found in rungs.

## Workspace navigation

The brand is the Home link; **Menu** beside it opens the ordered page directory,
and the header names the current page. The **?** button beside Stop workspace
opens the review guide. Native keyboard navigation, modified clicks and
outside/Escape dismissal are supported. Normal Menu and brand URLs are relative
to the application root, so opening them from a source popout does not preserve
source-only query parameters. Source popouts display a source title during loading.

The existing FR/Canadian EN controls move between the shared footer and Field
I/O's full-width footer. This reuses one translation controller and preserves
pending state. Footer height is measured to reserve space for page content and
panes; language controls are not duplicated in the header.

## Signal table and editor

The table fills the page until a row is selected. Click any noninteractive part
of a row, or focus the row and press Enter/Space, to open the right-side editor.
The selected row has a colored edge and distinct background. Hardware information
opens on hover, focus or click; source links open their own source window.
Close restores the table width without discarding unsaved drafts. On a narrow
window the editor is a side drawer. Its heading and Close control remain visible
while the editor scrolls. The page title and filters use less vertical space.

The title, result count, scan disclosure and expand/collapse actions share the
toolbar's first row; search and filters occupy its second row at desktop widths.
The toolbar stays below the application header during page scrolling, and column
headings follow its measured bottom edge. Longer explanations remain in Page
help. Scan details open as a disclosure and dismiss on outside click or Escape.
The visible **Hide empty rows** checkbox retains the full accessible name and
the filtering rules documented below.

Pagination is outside the table/editor grid, fixed across the viewport bottom.
Its measured height reserves clearance for both panes, including short/empty
lists. It disappears when leaving Field I/O. Application menus remain above the
toolbar and editor. Successful automatic import no longer creates a persistent
startup alert; source and analysis time remain in the header. Genuine startup
warnings are retained.

## Source-display recovery

The reported source popout loaded its rung and comment before failing at a
missing renderer's `render` method. The explanation and ladder displays now load
independently. A missing renderer gets one bounded reload of its fixed same-origin
asset, with a ten-second timeout. Failure leaves original source text and a
**Retry display** action without preventing other displays or review controls.
Retry replaces only its captured display, preserving grouping controls and
unsaved corrections. A delayed completion for an old rung cannot replace the
current source or draft. The reason the work-PC asset was unavailable remains
unknown; this change repairs the failure boundary rather than claiming a
particular browser or network cause.

Chrome validation used independently invented CPT/COP logic. A test-only local
server rejected the initial explanation script in the main page and source
popout; the popout's automatic retry succeeded, with both ladder and explanation
views available. Normal and narrow-window checks covered sticky controls,
aligned table headings, full-width pagination with an editor, and footer hiding
after navigating Home. No source reanalysis is required.

Final desktop measurements: a 37-pixel footer spans the 1,905-pixel content
viewport with the editor open. Its bottom clears the footer both before scrolling
and after sticky positioning engages. At a 1,000-by-800 viewport the drawer also
clears the footer. Measurements are coalesced per frame, with no style writes for
unchanged values. All 187 focused UI/integration tests passed. Coverage includes layout lifecycle and
draft retention, unavailable renderers, retry failure/success, delayed completion
from an older rung, and retention of genuine startup warnings. Independent review
found no remaining issues.

## Source descriptions and result context

Each description cell labels and links its owner: direct channel/member or alias,
inherited datatype member, containing member, backing tag or module. A datatype
member link names the declared type and member; a containing-member link names
the exact authored parent suffix. Shared module/backing/parent descriptions do
not become individually authored point wording.
Conflicting original annotations remain inspectable.

Qualified datatype definitions are shared across instances without expanding
arrays. Lookup follows the requested static path and checks nested types, array
rank/bounds and captured layout conflicts. Foreign/protected or duplicate
declarations do not supply wording. An exact instance or alias description takes
priority over type wording. A nearest containing member comment is an explicit
fallback, with token boundaries so `.Data` cannot match `.Data10`.

Datatype member descriptions were already available in Application Map and the
translation catalog but were missing from Field I/O. Containing-member comments
were captured but only exact member matches were selected. The shared lookup
repairs both integrations over the saved source; a new analysis is not required.
This is source-description recovery, not a plant or manufacturer glossary lookup.
Unexported descriptions remain absent.

For a signal without a specific description, a supported rung with one described
result can provide **From result …** context. The matcher requires a parsed,
qualified rung, condition-only prefixes/branches and one final supported
assignment. Multiple outputs, timers/stateful instructions, result readback,
unqualified operands, conflicting result descriptions, unresolved overlapping
uses and other matched use rungs prevent that inference. It uses the same scoped
alias and member evidence as source review, not name similarity. This context
describes the calculation's result, not the physical identity of each input.
Uniqueness is scoped to checked RLL source; SFC is outside this lookup. Original
source wording and saved reviewer edits are never overwritten. English display
uses the existing local translation cache keyed by the full original wording.
When the result itself inherits a datatype-member description, its cell includes
both the result link and the actual description-owner link.

For COP/CPS, one fixed destination element can supply **From result ...** context
to its completely covered source words. This uses authenticated static storage
layouts and the existing byte-range resolver; it includes source words reached
by the copy even if they have no exact operand occurrence. For example, copying
two INT registers into one described REAL gives both input rows the same linked
destination context. A fixed single array element is also supported. A condition
that enables the copy is not itself copied and does not inherit that context.

The byte mapping follows [Rockwell's COP/CPS reference](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-01/contents-ditamap/instruction-set/array-file-misc-instructions/copy-synchronous-copy-file--cps-.html):
Length counts destination elements, and the copy transfers bytes rather than
performing a numeric conversion. Existing range bounds apply. Multi-element
destinations, zero/dynamic length, unknown/conflicting layouts, partly covered
source words, self-overlap and other competing uses cannot provide this simple
context. Multiple destination elements need explicit per-element correspondence;
the first element's description is never spread across the whole source range.
Original source wording and saved DeltaV names remain unchanged.

Validation for navigation and copy context: 271 focused tests passed across
workspace UI, translation UI, Field I/O UI, copy/result context, usage ranges,
signal usage, signal inventory and the closed I/O audit. Independent review found
no remaining issues. Chrome verified both INT input rows' destination wording,
the linked annotation window, full workspace navigation from a source popout,
normal/narrow footer clearance and menu dismissal. Fixtures are independently
invented; no fresh work-PC export is required.

If the supported result has no description, its rung's direct comment can supply
**From Rung N comment** context instead. This covers two-register calculations
whose purpose is described on the rung. The rung comment and result have separate
links: the prose is not falsely attributed to the result tag. Only one plain,
namespace-qualified, unprotected comment is accepted; duplicate, foreign or
nested comments are excluded. Conflicting result descriptions block fallback.

An unrelated unread rung or unsupported routine no longer suppresses context
from qualified captured RLL. The displayed context stays scoped to its matched
rung, and the editor discloses other unscanned source. Known additional uses,
range/dynamic overlaps and an unread member selector on the same backing root
still prevent single-use context. This does not prove whole-source uniqueness.

Description links open the exact selected source annotation above the review
editor. The API verifies its owner and snapshot, returns the complete original
wording within its response bound, and uses any exact local translation-cache
match. Ordinary source links remain unchanged. Implicit module I/O owners use
their resolved source name rather than an empty XML `Name` attribute.

**Hide empty unreferenced rows** hides only no-reference addresses with neither
specific source wording nor derived result context. It does not hide used,
indirect or unchecked addresses. Shared module/backing wording alone does not
keep an empty address visible. Saved active signal records and their packages
remain visible. The checkbox defaults off, reports hidden counts and changes no
stored data; turn it off to restore the list.

## Recovered rack references

The prior returned rack summary proved 319 RLL occurrences across 94 logical
addresses against captured backing source paths. Field I/O had not consumed
that association. `workspace_rack_references.py` now reuses the existing bounded
rack shape checks on authenticated source/inventory/reference/tag-data inputs.
Qualified Rockwell EN2T slot layouts can associate logical rack names and aliases
with their actual backing members. Authenticated expression leaves are included.
Source IDs, access roles and rung links remain attached to those occurrences.
Recovered occurrences append after existing address materialization, preserving
old bindings and spelling. Unsupported vendor/layout, conflicting aliases,
protected or foreign evidence cannot create a correspondence. Recovery has its
own retained-data bound and is cached once per imported run.

The same detached binding overlay is used for supported COP/CPS/FLL ranges,
including both copy operands and fill destinations. Logical rack spelling and
canonical backing spelling produce the same footprint. FLL reads one source
value while its destination footprint spans Length elements. Existing bounds,
type, alias and zero-length rules still apply.

This repairs source-use lookup; it does not identify every physical card channel.
SFC uses and nested field references inside array-index expressions remain
separate disclosed scope limits. Do not mark unreferenced addresses as physically
spare based only on this RLL lookup.

## Verification on the work PC

Close the old workspace, pull the branch and run `bash ./open-workbench.sh`.
This reuses the saved analysis; its original analysis date remains correct.

1. In Field I/O, compare module wording with the labeled result descriptions or
   rung-comment context. Follow the inline owner link to its actual source.
   Click a plain row cell, verify its highlight and right-side editor, then Close
   to restore the full-width table. Existing drafts should remain available.
2. Scroll a long table and confirm its column headers remain visible. The
   **Signals per page** footer stays at the viewport bottom throughout the table.
   **Page help** explains the page without
   keeping long instructions above the table.
3. Toggle **Hide empty unreferenced rows**. Saved records remain available.
4. Select **Download I/O audit** in the footer and return `field-io-audit.json`.
   Its fixed keys contain only counts/flags: inventory, usage, description
   origins, field types, result contexts, recovered rack references and scan
   limits. Declaration lookup outcomes include available, blank,
   missing definition/member, conflicting, unsupported or capacity-limited;
   retained description-candidate origins and truncated candidate lists. Up to
   six anonymous profiles summarize a used/unused missing or inherited case,
   a datatype-member case and a use-context case. Schema 3 separately counts
   result-description and rung-comment context, plus fixed context reasons:
   specific source wording, no direct use, multiple rungs, nonread or overlapping
   use, unsupported result, absent/conflicting/unqualified wording, unavailable
   evidence or capacity. Profiles contain only fixed
   keys, counts and flags: never source names, addresses, descriptions, values,
   XML or rung content. The API run/revision guards are excluded from the file.

The download covers all signals, independent of the current filters or page.
It neither reparses the L5X nor sends anything over Git or an external service.
The actual work-PC totals must be measured before claiming how many of the
reported 2,071 no-reference entries were repaired or should be hidden.

## Validation

The full-width row/rung-comment follow-up passed 249 affected context, audit,
field-signal, API, UI, type-description, source-annotation, usage and rack tests,
including both large saved/imported capacity fixtures. Independent review caught
and verified the fix for a stale row response stealing focus from another row's
input. Regression tests cover all three open paths, close-before-response,
draft retention, nested controls and incomplete-scan context disclosure.

Chrome checks confirmed full-width rows before selection, plain-cell and keyboard
activation, active-row highlighting, draft retention through Close/reopen,
independent hardware information, and a pinned source popout showing the correct
rung comment and CPT. A 1000-by-800 viewport check confirmed the side drawer,
sticky Close heading and Escape dismissal. The schema-3 audit downloaded through
the UI contained 201 invented signals, two rung-comment contexts and only
numeric/Boolean leaves. Original, inherited and context wording remain distinct.
Actual work-PC description coverage has not yet been measured with this version.

Earlier sticky-footer/description validation:

The sticky-footer/description follow-up passed 135 inheritance, field, context,
audit and application tests; 170 source/API/UI tests; and a final 95-test affected
suite after correcting implicit module owner labels. Both large saved/imported
capacity fixtures also passed. Independent review found and resolved separate
result-description owners and exact-member source links. Invalid annotation
parameters, wrong owners/snapshots, historical lookup, full original text and
local translation-cache lookup have explicit regression coverage.

Chrome checks confirmed the sticky footer at the top, middle and end of a long
table and in a narrower single-column window. Per-row links identify the type,
parent member, module or result; the datatype link visibly opens its exact member
wording above the review editor. The schema-2 download was inspected on disk:
201 invented signals, three populated anonymous profiles and numeric/Boolean
leaves only. These are synthetic checks; work-PC gaps still require its audit.

Earlier inventory/reference validation:

The complete 789-test workspace suite passed. The final 242-test affected suite
also passed, including both large saved/imported capacity fixtures. Subsequent
range/rack regressions passed all 25 tests; the final 87 field-signal, result-context
and UI regressions also passed. Independent review checked recovered
expression references, scoped result context, logical-address search, audit
payload privacy, seven rack range cases and twenty FLL width/boundary cases.

Chrome checks used invented data: column headings remained visible while the
table scrolled, both inputs displayed their linked result context, the filter
hid 198 empty rows while retaining the two used inputs, Page help opened and
closed, and the result link opened the selected source without the full report.
The downloaded JSON was inspected on disk: 200 inventoried signals, two used,
198 unreferenced, and no source identifiers or project revision in its payload.
These synthetic numbers are validation evidence, not work-PC plant totals.
