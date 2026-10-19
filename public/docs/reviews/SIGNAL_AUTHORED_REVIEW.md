# Authored wording attributed to signal declarations

## Returned evidence and next step

Return `8a6d7fb` tested clean `16d2c9b`. All 50 historical work reports validate.
The return passed 1,597 application cases (two expected Windows skips) and
139 helpers, saved its private analysis, and has no failure code. All 23
non-signal summaries and every preceding signal coverage field are unchanged
after revision normalization. The entire six-example/eight-reserved-unit
sample envelope is unchanged.

The Boolean-pattern slice found self contacts on 2,213 outputs (1,186 XIC and
1,030 XIO output-to-read links), and timer contacts on 446 outputs (470 DN and
eight TT links). There are 1,085 same-content set/reset groups across 1,085
addresses. All 4,163 output walks completed without truncation: 4,099 distinct
guards, 32,643 node visits and 32,439 edges. These are source associations,
not counts of independent physical contacts or verified engineering functions.

Total work-check time was 760.158 seconds, up 9.311 seconds (1.24%). Tests
account for 7.528 seconds of that increase; source analysis increased by
0.341 seconds. This comparison does not establish a timing trend.

The existing rung-level text candidates include 1,319 alarm, 1,043 equipment,
and 61 sensor hints. A rung comment or an input alias can supply these words;
assigning them to every output would misstate the evidence. This increment
attributes matching declaration fields to their actual captured uses.

## Meaning and attribution boundaries

Signal3 extends each existing address with authored evidence, scan status and
description-gap links. Each matching field records the source entity, name or
description field, root/alias relationship, namespace qualification, closed
matched words/categories, and the accepted operand/expression uses connecting
that declaration to this exact address. Original text is read from the existing
inventory; it is not duplicated in the evidence rows or public summaries.

Category counters count retained source-field associations, not independent
equipment or alarms. Address counts can include qualified and unqualified fields.
`authored_outputs_with_evidence` counts qualified fields linked to output targets;
unqualified output evidence is counted separately, and the populations may overlap.

The lexical catalog is unchanged: whole-word alarm, equipment and sensor terms,
including the existing French vocabulary. Matching does not interpret negation,
abbreviations, engineering intent, alarm ranking or shutdown behavior. Multiple
categories can coexist. A matching root description is declaration-wide context,
including when an operand addresses a particular member or index. This slice
does not resolve member descriptions, per-member tag comments or UDT metadata.

Only the explicitly referenced alias symbol and resolved root are attributed.
Unmentioned intermediate alias-chain names are not added. The output dossier
filters fields to its own target operand, so a reader alias's alarm wording
cannot become the output's name evidence. The address dossier can show all
associated declarations with their distinct source uses. Rung comments remain
in the explicitly rung-wide evidence view.

Duplicate or nested descriptions do not select one description as authoritative.
Their declaration IDs appear as description gaps; an independently usable Name
can still match. Foreign-namespace text remains qualified separately; unsupported
descriptions without matching vocabulary also retain navigable gap IDs. An empty
result does not establish that the signal lacks an engineering role.

## Bounded work and versioned contracts

The scan bounds 100,000 unique fields, 250,000 accepted use visits, eight million
characters examined, 100,000 retained evidence rows and 250,000 use/gap IDs.
An 8 MiB added-retention budget includes fixed metadata and per-address wrappers.
Exhaustion is explicit and makes the result partial; no complete absence claim
is made after truncation. The existing one-million-list-entry and whole-result
serialization caps remain hard rejection boundaries, distinct from a truncated
scan. Source qualification and canonical replay remain required before publication.

Signal1 remains the reusable API default. Signal1 and signal2 retain their
fields, bytes and limits. Signal3 has a 48 MiB private cap and a 16 KiB summary
cap. Review25 embeds signal3 with file operations1 under 352 MiB JSON /384 MiB
HTML limits. Manifest28 still has sixteen artifacts. Work43 requires signal3;
historical work42 requires signal2. The conservative maximum-width work43 report
is 95,158 bytes, below its unchanged 106,496-byte cap. Timing and sampling
reservations are unchanged.

## Report behavior and verification

The Signal relationships view adds Authored wording with category, source-gap
and truncation filters, search, and fifty-row paging. Address and output dossiers
show individual fields, original text and links to their source uses. Root
context, alias context, unqualified text and unavailable descriptions stay
distinct. Original text is rendered as text, including markup-like strings.

The [invented report](../../examples/signal-authored-review-demo.html) includes
a reader-only alarm alias, a different writer alias, root descriptions shared
by different member addresses, French sensor wording, lexical nonmatches,
foreign and duplicate descriptions, and enough findings to exercise paging.

Independent review passed all 30 new production cases and closed three findings:
unqualified nonmatching descriptions now retain visible gaps; retention charges
fixed metadata and address wrappers; source counts cannot exceed two declarations
per accepted use visit. The same 30 cases passed with process and socket creation
blocked before project imports. All 76 development workflow cases passed.

Three new and three preceding pattern DOM checks passed. Chrome verified 50/11
paging, source-gap filtering, ambiguous descriptions without a selected text,
reader-only alias exclusion, the separate writer alias's two fields, and original
field/use navigation. The gap layout was visually inspected and browser error
logs were empty. The temporary tab and local server were closed.

A full-scale invented capacity case retains 4,606 rungs, 4,163 coils and 12,741
predicate operands. It scans 3,975 sources, 7,950 fields, 4,475 matching field rows
and 18,304 operand links. All 3,975 address scans complete without gaps/truncation.
Signal3 JSON is 33,653,337 bytes (32.094 MiB), versus 29,464,848 for signal2;
its summary is 5,739 bytes. Canonical replay and summary validation passed.
An earlier deliberately denser fixture with three hint categories everywhere
hit the existing rung-analysis evidence cap before reaching signal3. The final
case uses one category per invented description plus 500 matching names; no
production limit was loosened. This is a size check, not a plant timing estimate.

The final isolated Bash-launcher run passed 1,627 application cases (two expected
Windows skips) and 139 helpers. It saved review25/manifest28, verified all sixteen
artifact hashes, replayed the unchanged sample envelope and created exactly one
local report commit with zero Git network operations. Two fresh saved analyses
passed canonical replay, and the CLI produced the same sixteen artifacts.
The committed invented demo reproduces byte for byte from its LF fixture.

All fifteen preceding non-review artifacts and 23 unrelated summaries match the
baseline. Every pre-existing signal2 row field and coverage count is unchanged.
All 50 historical reports remain byte-identical and validate alongside the new
isolated report. The final 230 runtime/test files match the tested snapshot;
both isolated repositories finish clean. Initial focused integration checks
caught two explicit version maps and one mocked-runner expectation needing the
new version; the corrected cases and the full release suite passed.

## Next work-machine return

Use the ordinary manual pull/check/push workflow. The next return measures
precisely attributed fields, qualified/unqualified categories, description gaps
and scan completeness. No additional source sample or team review is requested.
The listener remains disabled and no automatic Git transport is introduced.

This remains Phase 1. Explicit alarm declarations/instructions, stronger
equipment relationships, residual source gaps and report consolidation still
need assessment before engineering review and the editable PCSD stages.
