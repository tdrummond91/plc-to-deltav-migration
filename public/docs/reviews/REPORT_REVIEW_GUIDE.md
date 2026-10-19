# Reading the Phase 1 engineering report

The report explains captured PLC source and proposed engineering groupings.
No code reading is required. C14 return `adc5475`, testing `a53ca67`, closes the
automated pre-review gate for this export. Start with Tyler's readability and
appearance check, then team engineering review. No new parser run is needed.
See the [readiness assessment](PHASE_1_READINESS_REVIEW.md) for evidence and the
remaining source questions.

## Open the report on the work PC

Open the `review.html` already saved by your latest work-check run. The script
prints **Private review report:** followed by its path. If that terminal output
is gone, browse `confidential/workspaces/work-check/` and open the newest run's
`review.html`. There is no need to rerun the parser merely to find the report.
The report
works locally without a server. Keep the complete report and its neighboring
artifacts on the work machine. The automatically created local commit contains
only the validated feedback report; Git transport remains manual.

An independently invented [demonstration report](../../examples/control-interpretation-review-demo.html)
is available for learning the navigation. It is not a model of the plant.
The smaller [rack group demonstration](../../examples/rack-assemblies-review-demo.html)
shows a rack alias and direct adapter use sharing a source group, and a command
feeding a rack output guard. It also shows literal inputs counted separately.

## Suggested first pass

1. **Overview:** check the source snapshot and coverage. A partial analysis can
   still have useful evidence; open the missing or unsupported source regions.
2. **Engineering analysis:** choose a rung and inspect its candidate functions,
   ordered blocks, branch structure, comments, inputs, destinations and gaps.
   More than one candidate purpose can apply to one rung.
3. **Cross-rung groups:** follow one address into related signals, calculations,
   PID slots, stateful objects and sequence/file uses. Matching an exact address
   is evidence of source reuse, not proof of equipment identity or live flow.
4. **PID evidence**, **Signal relationships**, **Calculations** and **Alarm source evidence:**
   inspect the relevant specialized views. Names and comments are attributed
   hints. Zero explicit alarm records does not establish that no alarms exist.
5. **Execution context**, **Communication context** and **Sequence structure:**
   inspect routine calls, source arguments, message configuration and sequence
   transitions. Follow their source links before making a control-strategy claim.
6. **Unresolved analysis:** distinguish unclassified base blocks from blocks
   with specialized evidence. Open the remaining condition, signature, source
   and binding explanations. Missing readers or writers are investigation leads,
   not proof of dead code.

In **Unresolved analysis**, the source-population **Open evidence** links select
the counted group: missing comments or identifiers, no known local result,
read-only or write-only exact addresses, transition gaps, or indexed source
occurrences. The selected filter remains visible and can be changed. Opening a
record and using Back restores that selection. Indexed occurrences include
separately labeled unknown-role or unsupported forms; their count does not imply
that every selector was parsed.

SFR instructions now link their **Sequence reset target context** directly from
engineering and unresolved rows. A matched routine/step candidate explains
source identity. Its **Documented instruction operation** note explains the
enabled reset to the selected step and reset of stored actions; it does not
calculate actual execution, active actions or final values. Missing or conflicting
candidates stay flagged. Routine-call and boundary dossiers likewise explain
JSR invocation and normal-return continuation, SBR input reception, and enabled
RET termination. A zero-field RET still returns from the routine. The exact
RLL/SFC content links, raw fields and incoming conditions remain visible beside
these notes; parameter mapping and outgoing Boolean transfer are unresolved.
See the [current control-transfer assessment](ROUTINE_CALL_SHAPE_REVIEW.md#current-control-transfer-assessment-2026-10-19)
for the specific vendor/exporter evidence needed, with SBR prioritized because
it contributes to the sole remaining opaque coil guard in the latest return.

**Rack source addresses** separates rack declarations, candidate addresses and
individual RLL/SFC occurrences. A qualified correspondence shows the adapter
symbol and its captured `Slot` member path, with links through the declaration,
connection, data representation and member. The backing symbol can be derived
from exported module naming; its origin is shown in the declaration dossier.
Each occurrence still has its own source and alias qualification. A supported
address can therefore have a rejected occurrence. The original binding and
condition gaps remain visible, with links to this separate evidence. These
source paths do not establish physical wiring, process service or live values.

With assemblies3, **Cross-rung source associations** links qualified rack
occurrences to their backing-address groups, including matching direct adapter
uses. Membership rows retain **Rack qualification** links. **Related addresses**
also shows outputs whose guards read the selected input; these are source
associations, not a simulation. Literal and system-flag guard inputs remain
visible in the original guard dossier and have separate counts, rather than
being called failed addresses. Older saved reports retain their earlier model.

Routine-body questions account for supported AOI bodies in their dedicated
source view. Missing RLL bodies and protected or unsupported AOI bodies remain
explicit questions with links to the relevant source dossier.

Use search and filters to narrow each view. Open a row, follow its evidence
links, and use Back to return to the prior view. A report ID belongs to that
exact snapshot; copy the report/run identity alongside any record ID.

## What later feedback should contain

For the first pass, try one familiar rung, one PID or output group, and one
unresolved case. Check whether you can find their source, follow the links and
understand what is known versus uncertain. Report confusing labels, cramped
tables, missing context or broken links as well as incorrect interpretations.
You do not need to classify the entire export before returning feedback.

For each correction, identify the report/run, view and object/rung, then describe
the observed result, expected result and supporting evidence. Mark the kind of
correction: a reusable parser rule, a source-specific exception, an interpretation
requiring additional evidence, or a DeltaV design decision. Appearance feedback
can identify confusing labels, difficult navigation, cramped tables or missing
grouping without assigning engineering classifications.

Preserve the report that prompted the correction. Editable correction storage,
cross-snapshot reconciliation and PCSD/FHX generation are later phases; this
read-only report does not yet store review decisions or automatically carry them
across changing source exports.

## Remaining source questions to carry into review

- Missing routine bodies need the omitted source to determine behavior.
- Qualified rack source paths still need channel/wiring evidence before they
  can establish physical I/O. Rejected declaration, suffix or occurrence
  qualifications remain separate source investigations.
- Runtime selectors need runtime values. Caller parameter roles and
  control-transfer behavior need more than lexical addresses or source order;
  the reviewed primary references leave specific neutral-RLL serialization and
  outgoing-condition questions. A controlled version-recorded exporter example
  can settle serialization; applicable vendor semantics or a separate controlled
  execution check must settle Boolean behavior. Repeating the unchanged work-PC
  script supplies neither. These are parser evidence gaps, not team classifications.
- Generic message selectors identify configured numbers and catalogued service
  names; device object/attribute meaning and live transfer effects remain separate.
- Alarm severity, shutdown effects, equipment identities and target naming need
  supporting source or engineering decisions. Wording alone is insufficient.

One source-population description in **Unresolved analysis** says rack-name
candidates remain unconfirmed. That is
the preserved base binding view; use **Rack source addresses** and its qualified
cross-rung links for the later source correspondence. This wording is a known
presentation limitation for the feedback pass. A qualified source path still
does not prove a physical channel or a Boolean execution result.

The [completion tracker](../planning/PRE_TEAM_REVIEW_TRACKER.md) and
[current audit](PHASE_1_READINESS_REVIEW.md) distinguish these residual
questions from completed parser investigation. Engineering decisions remain
unreviewed until people confirm them.
