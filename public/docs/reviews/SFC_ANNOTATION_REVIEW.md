# SFC annotation capture and separate attachments

## Returned baseline and selected scope

Report commit `42e0188` adds only
`public/inspection/work-check-20261015T015742Z-873f283d.json`, testing its clean
parent `4b00f5a`. It passes 399 application cases (one existing Windows symlink
skip) and 139 helpers, saves a private run and reports partial analysis.
Reference12/source4 counts equal the previous report after excluding revision.

The new SFC1 profile contains 14 routines and 14 content blocks, all with absent
edit-kind attributes. It captures 145 steps, 155 transitions, 14 branches,
34 legs, 324 directed links, 280 text boxes and 213 attachments. All 628 block
IDs are valid, with no duplicate groups; all 648 link endpoints resolve.
There are 329 ST lines/5,390 characters and 280 unmodeled elements, accounting
for all 280 issues. No action descriptors are observed. These counts describe
the export, not valid execution or complete sequence understanding.

The approved minimized fixture has immediate Text children in its TextBoxes.
Its 45 boxes each have one such child. The coincidence of 280 unmodeled elements
and 280 real-source boxes suggests that shape may explain the gaps; the shared
report does not establish their XML names. The next work run tests that inference.
Scrubbed IDs do not support real topology conclusions.

## Evidence and interpretation boundaries

Rockwell's [L5X reference, RM014D](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf)
(printed pages 274-275) shows direct CDATA in TextBox and numeric attachment
FromID/ToID references. TextBox to diagram-object attachments are distinct from
DirectedLink flow edges; action targets are possible. Support for an immediate
Text child is observed compatibility with the approved fixture, rather than a
claim that the manual requires that wrapper.

Rockwell's [SFC programming manual, PM006L](https://literature.rockwellautomation.com/idc/groups/literature/documents/pm/1756-pm006_-en-p.pdf)
(printed page 67) describes text-box notes as offline documentation. Preserve
authored text without treating it as a tag description, executable ST, a correct
process explanation or an automatically selected engineering description.

Protection reporting is unchanged: current markers count opaque encoded or
encrypted payload regions. EncryptionInfo metadata can also accompany protected
plaintext exports (RM014D printed page 257); an absent counted marker does not
prove the routine is unprotected.

## Implemented contracts

Private SFC schema2 / sfc-structure-2 adds required annotations, preserving one
row per Attachment with separate source/target status and element IDs. Direction
is strict: FromID must resolve uniquely to a TextBox; ToID must resolve uniquely
to a flow block or Action. Numeric normalization and the complete ID index stay
content-local, including unknown declarations and collisions. Wrong kinds,
missing/invalid IDs and ambiguous targets remain gaps; there is no reversal,
cross-edit lookup or fallback. Annotation edges never enter control-flow links.

Only immediate Text children of recognized TextBoxes become text_box_text.
Both direct TextBox text and child text remain exact independent fragments,
including whitespace and mixed or duplicate children. They are not concatenated.
Other Text contexts and nested unknown markup remain explicit unknowns. Elements,
attributes and raw text print once, with parent IDs; the attachment section
references those descriptors. Repeated attachments cannot multiply a large note
or endpoint attribute in the rendered report.

The 100,000-annotation cap and complete key/value evidence-character budget apply
before publication/storage. Canonical replay validates the new rows from the
same immutable captured bytes. Inventory3/reference6/analyzer9 and the existing
reference12/source4 aggregates remain unchanged.

Public SFC schema2 / sfc-structure-summary-2 keeps policy2 and its report kind.
It adds closed annotation-status and endpoint-status partitions, distinct note
and target counts for fully resolved pairs, and annotation_text counts. The
four text shapes are empty, direct_only, child_only and mixed: nonblank direct
text sets the direct flag, while presence of immediate Text children sets the
child flag even when their text is empty. Character counts include raw whitespace.
No text, IDs, attributes or note-to-target pairs leave private storage. Counts
must reconcile with element kinds, block-ID capacities, issue totals and limits.
Historical SFC1 retains its original exact vocabulary and text-issue rules.

Work12 / work-check-12 requires SFC2 beside unchanged reference12/source4.
Historical work11 requires SFC1; mixed pairs reject. Earlier envelopes remain
readable. Manifest3 layout stays unchanged and records current SFC versions;
ordinary source/reference-only commands retain manifest1/2.

## Validation and next run

Focused regression coverage verifies both note forms, mixed/empty/duplicate text,
wrong parents, endpoint kinds and direction, edit namespaces, collision handling,
canonical tampering, exact budgets, privacy, frozen contracts and version pairing.
Independent review found one rendering amplification blocker: repeating full
endpoint payloads for every attachment. The fix prints descriptors once. A
regression repeats 500 attachments against 5,000-character note, source-label
and target-operand payloads and requires each payload to occur exactly once.

Final full development discovery passes **512 cases, one existing Windows
symlink skip**, excluding the ignored listener loader. The 71 CLI/storage/work
and reference regressions pass; 44 core/summary cases pass. All 17 stored work
reports validate unchanged. Independent follow-up review finds no remaining
blockers: its repeated-payload reproduction renders 246,806 characters with each
large payload exactly once. The full-suite command is retained in
[the structure review](SFC_STRUCTURE_REVIEW.md#validation).

Actual launcher execution in a disposable clean checkout passes twice: explicit
invented source, then remembered source, each with **416 application cases
(one skip) and 139 helpers**. Both reports use work12/SFC2/reference12/source4
and make only a local report commit whose parent is its tested revision. Git
traces contain no fetch/pull/push; both runs leave clean trees. Source, the
first run's artifacts and every manifest hash remain intact. Combined manifest3
has seven artifacts; standalone SFC retains manifest3/five and plain references
retain manifest2/five. Actual private JSON/text CLI outputs equal saved artifacts;
aggregate CLI counts equal the feedback report and expose no invented names.

The invented chart has Original and PendingEdits content, five notes (one direct,
two child, one mixed, one empty) and nine attachments: four resolved/five
unresolved. Its 18 annotation endpoints split into 12 resolved, three wrong-kind,
two missing-target and one missing-attribute. Two flow links retain four resolved
endpoints; ST stays two lines/40 characters. Compared with `42e0188` on these
identical invented bytes, inventory JSON, reference JSON and reference summary
are exact; SFC routines, contents, flow links and element evidence are exact
except the newly recognized child kind. All 192 copied tracked/new files match
the tested working bytes at the checkpoint; subsequent edits add only this
documentation evidence. The initial harness incorrectly expected exit0 for a
partial aggregate CLI; accepting documented exit3 let the remaining checks pass
without rerunning already successful launcher tests or changing parser code.

Run the normal work-machine script after pulling this branch. Earlier source,
reference, graph, SFC flow-link, ID and ST counts should stay stable. If the
inferred wrapper explains the real gaps, text_box_text should become 280 and
unmodeled should fall from 280 to zero. Attachment resolution and text-shape
counts remain unknown until returned. A structurally complete SFC result still
does not establish runtime semantics or finish Phase 1. Keep listener execution
disabled; local report commits are automatic and pull/push remain manual.

## Returned annotation checkpoint (2026-10-14)

Commit `90923ab` adds only
`public/inspection/work-check-20261015T030020Z-8c576eed.json`, testing its clean
parent `f8411bc`. The report validates with 416 application cases (one existing
Windows symlink skip) and 139 helpers, all without failures/errors. A private
run was saved, the diagnostic sample is null, and overall analysis stays partial.

SFC2 is now structurally complete with zero issues for this export. All 280
previously unknown elements are recognized text_box_text children. All 280 boxes
are child_only, with 16,481 raw text characters. All 213 attachments resolve
both endpoints (426 total), covering 213 distinct boxes and 213 distinct targets.
There are 67 boxes without an attachment in this captured chart population;
free-standing notes are supported and this does not itself imply a defect.
Earlier SFC element totals, flow links, block IDs and ST counts are unchanged.
The entire reference12/source4 summary is unchanged except code revision.

This confirms the predicted compatibility correction and completes this bounded
SFC structural/annotation slice. It does not prove source byte identity across
runs, execute transition expressions, determine alarm effects, or complete
Phase 1. No repeat annotation-only work-PC run is required. See the
[project-state assessment](PROJECT_STATE_REVIEW.md) for the broader milestone.
