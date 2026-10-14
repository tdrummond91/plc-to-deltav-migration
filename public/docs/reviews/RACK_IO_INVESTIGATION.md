# Investigation of unresolved I/O roots

Date: 2026-10-14. Code baseline: `112ee82`; reviewed branch baseline: `7c998f8`.
The work-machine evidence is [report 1195d40](../../inspection/work-check-20261014T162634Z-2a7e40fe.json).
This investigation changes documentation and adds an independently invented
fixture. It does not change parser behavior, result schemas or Git automation.

## Finding

There is a demonstrated source-model gap: the reader does not create declarations
for `RackConnection`, `InAliasTag` or `OutAliasTag`. A coherent invented rack
reproduces missing slot roots while references to the adapter's ordinary I/O
bind. This supports a rack investigation, but does not establish that all 99
unresolved aliases or 320 unresolved operands in the real report are rack cases.

The current failure is not rejected colon syntax. `_address` accepts the root;
`_Resolver.lookup` returns `colon_root_not_declared` when the exact root is absent
from the visible symbol table. That label says nothing about why it is absent.

## Evidence already available

The returned report has zero malformed addresses after the timer correction.
All 99 unresolved aliases and 320 unresolved operands have the missing-colon-root
reason. All 252 modeled ordinary module I/O names are available, with no ambiguous
symbol groups. That rules out an unavailable name among those modeled records;
it does not rule out omitted declarations, a different requested suffix, or scope.

The shared [structure counts](../../xml-structure-counts.json) and
[value profile](../../xml-value-profile.json) record 11 RackConnection elements,
11 InAliasTag children and four OutAliasTag children. Those elements have no
attributes or text. The minimized fixture retains two representative shapes,
but its surrounding module names, port IDs/types and other values are scrubbed.
It cannot serve as a coherent topology oracle. The profile has five distinct
Port.Type values, all withheld; the current naming code supports ICP/Ethernet.
Neither that profile nor the successful ordinary declarations establishes the
port types of the omitted rack records. These older shared artifacts are
structural evidence, not proof of byte identity with the latest export.

Relevant code paths:

- [source.py](../../../python-parser/src/plc_workbench/source.py): supported
  declaration kinds/parents omit rack forms. `analyze_snapshot` preserves their
  generic XML paths and attaches `module_rack_connection_not_analyzed` to the
  owning module; exact XML remains in the saved snapshot.
- [module_io.py](../../../python-parser/src/plc_workbench/module_io.py): names
  ordinary I/O through checked module/port ancestry. ICP uses parent name plus
  slot; Ethernet uses module name. Connection suffixes remain significant.
- [references.py](../../../python-parser/src/plc_workbench/references.py): exact
  scoped root lookup follows aliases in each alias declaration's scope. The last
  alias-chain entity's `AliasFor` identifies a missing terminal root; the caller's
  operand can be a simple alias name with no colon.
- [reference_summary.py](../../../python-parser/src/plc_workbench/reference_summary.py):
  current reason counts combine direct and alias-mediated missing operands. The
  malformed-address alias bucket does not apply to these unresolved references.

## What the official format supports

[Rockwell RM014D](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf)
(printed pages 87-88) defines RackConnection with InAliasTag/OutAliasTag children
separately from ordinary Connection input/output tags. This supports dedicated
source records; the diagram alone does not define every generated alias target.

[Rockwell RM094N](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm094_-en-p.pdf)
(printed page 101) documents location/slot/type I/O names and access to a
rack-optimized module either through its individual tag or the rack-object entry.
Thus the empty alias elements are relevant declaration evidence, not merely
irrelevant containers to discard.

[Rockwell 1789-UM002K](https://literature.rockwellautomation.com/idc/groups/literature/documents/um/1789-um002_-en-p.pdf)
(printed pages 220-221) illustrates a FLEX individual I/O tag backed by an element
of an adapter array and distinguishes ordinary direct-connection tags. That is
a concrete family example, not a universal member-layout rule for every rack.
The investigation does not invent a `.Data[slot]` target for this project's modules.

## Reproduction with invented data

[rack_io_gap_demo.L5X](../../fixtures/synthetic/rack_io_gap_demo.L5X) has four
modules, six ports, one ordinary connection, one controller alias and five rungs.
The Local/bridge/remote/slot topology is deliberately coherent for the currently
supported ICP/Ethernet rules. Documentation-only addresses and invented names
are used throughout. It is not certified for Studio 5000 import or deployment.

The adapter has ordinary InputTag/OutputTag children. Slot 3 has ConfigTag and
an attribute-free RackConnection with both alias children. The program probes
the two slot roots, an ordinary alias targeting the input slot, and the two
adapter roots. It makes no assertion about backing members or hardware behavior.

| Invented case | Bound operands | Unresolved operands | Ordinary alias |
|---|---:|---:|---|
| Rack fixture | 2 | 3 | Unresolved |
| Element-name-only ordinary control | 5 | 0 | Bound |
| Ordinary control with missing parent | 2 | 3 | Unresolved |
| Ordinary control with input record outside controller context | 3 | 2 | Unresolved |

The base names are `Remote:I`, `Remote:O`, `Remote:3:C`. The three unresolved
operands refer to the absent slot input/output declarations, directly or through
`ProbeAlias`. One rack diagnostic and three unmodeled rack paths remain.

For the control only, change the three rack element names in memory to
Connection/InputTag/OutputTag. The current topology code then derives
`Remote:3:I` and `Remote:3:O`, and all five roots bind. The unnamed ordinary
Connection still causes `entity_name_missing`, so the control remains partial.
This is an experiment isolating declaration handling, not a valid conversion
of rack XML into ordinary connection XML. No control variant was saved.

The missing-parent control leaves three names unavailable. The scope control
leaves one input name unavailable. These distinguish declaration capture from
topology/scope validity and confirm that the existing guards still matter.
All inventories and the fixture bytes stayed unchanged during analysis.

## Competing explanations and next implementation

Independent experiments also reproduced the same missing-colon reason for a
connection suffix mismatch (`I` versus `I2`), a module-name versus slot-prefix
mismatch, and an ordinary alias chain terminating at a missing root. Therefore
neither the reason label nor a null mystery sample identifies a rack cause.
The current sample builder selects only malformed operands; unresolved roots
are outside its selection rule.

The next bounded slice should:

1. Capture rack connections and their input/output alias declarations as distinct
   private source records with parentage, raw attributes and source locators.
2. Derive candidate logical roots only for explicitly supported, unambiguous
   topology. Preserve unavailable/unsupported naming and unknown backing mapping.
3. Compare candidates to terminal missing roots under the existing scope and
   alias rules. Keep alias declarations, direct operands and alias-mediated
   operand counts separate; these populations cannot be added as plant defects.
4. Publish closed candidate-match counts, with ambiguity and unavailable-topology
   accounting, before promoting any current binding. A lack of matches cannot
   exclude racks when candidate naming is unavailable. Account for suffix/prefix
   and outside-scope alternatives rather than labeling every miss a rack problem.

Do not simply admit rack aliases as ordinary non-alias module symbols. Current
`root_bound`/`target_id` follows modeled aliases to a terminal declaration;
stopping at a rack alias with unknown backing would silently change that meaning.
A future logical-declaration match needs explicit semantics distinct from a
resolved backing target. Do not erase the rack provenance or invent member/bit
mappings. Duplicate candidates, ordinary-symbol collisions, controller isolation,
AOI isolation and program shadowing must remain visible.

This next implementation can be developed here with invented fixtures. One later
work-machine check can measure the rack hypothesis using bounded feedback; no
repeat of the current unchanged parser is requested for this investigation.

## Validation

The existing module source/naming/reference suites passed 38 tests. The actual
`references` CLI returned the expected partial exit 3 with two bound and three
unresolved operands on the new fixture. Canonical validation accepted the base
and in-memory controls, with unchanged inputs. An independent code/design review
confirmed the declaration omission and challenged the proposed shortcut of
treating rack aliases as ordinary terminal symbols; that shortcut is rejected.

Run the invented example from the repository root:

```bash
uv run --project python-parser --locked plc references public/fixtures/synthetic/rack_io_gap_demo.L5X
```

For the controlled comparison, load that fixture with `snapshot_from_bytes` and
`analyze_snapshot`, then call `analyze_references`. Repeat with an in-memory copy
replacing only RackConnection/ InAliasTag/ OutAliasTag element names by
Connection/ InputTag/ OutputTag; never apply that substitution to plant data.

No real source, listener or work-machine execution was used. No production
parser code changed; the full application/helper suites were not rerun for this
investigation. Existing historical test results remain attributed to their runs.
