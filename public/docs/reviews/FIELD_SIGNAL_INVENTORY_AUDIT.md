# Field signal inventory and reference audit

The Field I/O inventory includes qualified addresses captured in aliases,
decorated tag values and member comments as well as ladder operands. An address
can therefore exist, inherit a module description and have no captured RLL
reference. An address used in logic can also lack an authored description. The
inventory count is not the number of wired devices or addresses found in rungs.

## Source descriptions and result context

Each row labels the description's origin: channel/member, alias, backing tag or
module. Shared module/backing descriptions do not become specific point wording.
Conflicting original annotations remain inspectable.

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

1. In Field I/O, compare module wording with the labeled result descriptions and
   follow a result/reference link to the source.
2. Scroll a long table and confirm its column headers remain visible. Change
   **Signals per page** at the bottom. **Page help** explains the page without
   keeping long instructions above the table.
3. Toggle **Hide empty unreferenced rows**. Saved records remain available.
4. Select **Download I/O audit** in the footer and return `field-io-audit.json`.
   Its fixed keys contain only counts/flags: inventory, usage, description
   origins, field types, result contexts, recovered rack references and scan
   limits. The API run/revision guards are excluded from the downloaded file.

The download covers all signals, independent of the current filters or page.
It neither reparses the L5X nor sends anything over Git or an external service.
The actual work-PC totals must be measured before claiming how many of the
reported 2,071 no-reference entries were repaired or should be hidden.

## Validation

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
