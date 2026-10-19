# Rack backing: captured evidence and remaining mapping work

## Why this investigation remains open

C10 retains 11 rack connections, 15 input/output alias declarations, 99
unresolved aliases and 319 alias-mediated RLL uses with unique logical rack
candidates. Binding context organizes 94 candidate addresses over 11 roots;
four SFC alias-gap references also have unique rack candidates. These are
logical source associations, not established adapter members or physical
channels.

The existing rack-name provider uses module/port topology. It does not consume
catalog/vendor/revision attributes, configuration data or backing-tag shapes.
Its `backing_status=not_analyzed` is an implementation boundary, not evidence
that the export lacks the required information.

Inventory already retains module and ordinary connection attributes. Tag-data
capture preserves direct Data/DefaultData representations under module
ConfigTag, InputTag and OutputTag records. Communications attributes and
ConfigData, ConfigScript, ExtendedProperties, EKey and Bus lack dedicated
evidence models; their XML remains in the immutable snapshot. Approved public
profiles show these regions exist, but their marginal totals do not identify
which records belong to the rack cards or adapters.

## Primary-source boundary

[Rockwell RM014D, printed pp. 79–83 and 87–90](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf)
defines module identity/topology, ConfigTag or ConfigData operating
characteristics, additional XML profile data and separate RackConnection alias
forms. Connection data depends on the module and configuration; the generic
format description does not supply a universal alias-target rule.

[Rockwell 1789-UM002K, printed pp. 220–221](https://literature.rockwellautomation.com/idc/groups/literature/documents/um/1789-um002_-en-p.pdf)
gives a 1794-ACN15 FLEX example where an individual digital module alias refers
to an adapter Data array element indexed by slot. Direct-connection tags remain
distinct. This is a documented investigation lead, not proof that the returned
project uses that configuration.

[Rockwell RM094N, printed pp. 100–101](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm094_-en-p.pdf)
distinguishes module-dependent layouts and connection formats, including
enhanced rack optimization. A generic `.Data[slot]` remapping would exceed that
evidence. Even a verified backing-memory rule would not establish field wiring,
equipment identity or runtime behavior.

## Frozen schema1 diagnostic returned by C11

`rack_backing_summary.py` produces a separate fixed summary within
work50. It adds no private artifact and changes no reference, review, manifest,
condition, SFC or binding schema. Existing default and historical models remain
unchanged. No new source sample is emitted.

API:

```python
build_rack_backing_summary(snapshot, inventory, references, tag_data,
                          tool_revision=revision)
validate_rack_backing_summary(summary)
render_rack_backing_summary(summary)
```

The builder authenticates the inventory/tag-data pair against the existing
snapshot and replays reference analysis. Snapshot nodes qualify already
modeled declarations and their ancestry; no additional configuration values are
extracted. Different namespaces, namespaced attributes and protection markers
fail closed. Parent-module identifiers must be ASCII names before case-folded,
controller-scoped lookup. Duplicate parents and ordinary connection contexts
cannot silently select a winner.

Each rack alias declaration receives one first-gap or observed-shape
disposition along this sequence:

1. Qualify the rack/module source and find one parent adapter.
2. Require an available existing rack name and qualified topology ancestry.
3. Find one ordinary adapter tag in the declaration's input/output direction,
   with an unambiguous connection and the expected adapter-root name.
4. Require one captured representation. Multiple representations, including a
   Decorated/L5K pair, remain ambiguous; the diagnostic does not choose an
   effective representation. Missing and unsupported formats remain distinct.
5. Observe one Decorated Structure containing one Data array member with DINT
   element type, a supported one-dimensional size and scalar indexed elements.
   Look up the candidate's slot without merging duplicate numeric indices.

The final disposition is `slot_shape_observed_mapping_unchecked`. It does not
validate element values, complete array population, member legality, alias
projection, communication format, firmware support, effective configuration or
physical mapping. Missing or unusual data shapes remain useful evidence for
the next parser rule rather than being relabeled absent hardware support.

The adapter family partition recognizes only exact source attributes
`Vendor="1"` and `CatalogNumber="1794-ACN15"` after qualification. Other
identities, missing identities and unavailable contexts use fixed bins.
This identifies a documented catalog example; it establishes neither installed
hardware nor supported configuration. Raw catalog strings and all unknown
source values remain private.

Public coverage contains rack connection/declaration totals, declaration
direction, candidate-name availability, adapter-family counts and disposition
counts. Each partition conserves declaration totals. The additional
`observed_shape_by_family` partition joins observed shapes to family categories,
so mixed-family marginals cannot imply the documented example matched. It
conserves the final observed-shape disposition, cannot exceed family totals and
cannot count unavailable context. Revision metadata is the only free provenance
field and follows the existing closed commit/worktree contract.

Summary schema1 uses fixed keys and a 4 KiB canonical JSON cap. Counts are bounded
by the source element capacity. Indexed entity, representation and member
lookups avoid candidate-by-source scans; shared adapter representations are
analyzed once and retain row references, not expanded per-card copies. The
existing source/reference/tag-data budgets continue to apply during replay.

## C11 result and schema2 follow-up

The [C11 work50 return](../../inspection/work-check-20261019T140719Z-904afb98.json)
retains 11 rack connections and 15 declarations: 11 input and four output.
All 15 qualified adapter identities fall in schema1's `other` bin; 11
declarations stop at `data_member_missing`, four at
`representation_ambiguous`, and none reaches observed shape. Direction and
disposition are separate marginals in schema1, so those counts do not establish
that the 11 missing members belong to the 11 inputs. They also do not establish
which catalogues were encountered, which alternative formats coexist, or
whether a `Slot` layout exists. `data_member_missing` means the checked root
lacked the specific `Data` member that schema1 requested.

[Rockwell's CNB/CNBR data-type tables](https://www.rockwellautomation.com/en-dk/docs/studio-5000-logix-designer/37-02/contents-ditamap/module-information/1756-controllogix-i-o-modules/module-defined-data-types--1756-cnb---cnbr-/module-data-types-1756-cnb---cnbr.html)
document a root `Slot` array, input `SlotStatusBits`, and slot structures with
input `Fault`/`Data` or output `Data` DINT members. This is a second documented
shape worth investigating. The page spells the array element type differently
from its element-table heading; this implementation therefore does not invent
an exact native-type alias or remapping rule from that discrepancy. It requires
the captured array and element type strings to agree exactly.

[Rockwell's module-defined type format](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-03/contents-ditamap/studio-5000-logix-designer/module-defined-data-type-format.html)
describes vendor, module-specific identifier, tag direction and version fields,
and explains that generated types depend on module and communication format.
Recognizing a bounded native-looking header is consequently a source-shape
observation, not verification of an installed profile or its configuration.

Schema2 is selected explicitly by work51:

```python
build_rack_backing_summary(snapshot, inventory, references, tag_data,
                          tool_revision=revision, schema_version=2)
```

Omitting `schema_version` still produces schema1. Its serialized fixture hash
and historical behavior are unchanged. The schema2 validator and renderer use
the same public API names and an 8 KiB cap; schema1 remains capped at 4 KiB.
No private artifact, raw sample, sample-history entry or binding is added.

Schema2 reuses the same authenticated capture and source qualification. Its
additional observations are:

- Exact product bins for 1756-ENET, ENBT, EN2T, EN2F, EN2TR, EN3TR, CNB, CNBR,
  CN2 and CN2R; 1794-ACN15, ACNR15, AENT and AENTR; and 1734/1738-AENT and AENTR.
  Each requires exact `Vendor="1"`, exact catalogue spelling and no
  `UserDefinedCatalogNumber` attribute. These are identity bins, not supported
  hardware/configuration declarations. Other, missing and unavailable
  identities remain closed categories. Rockwell's [product comparison](https://compatibility.rockwellautomation.com/Pages/HandlePrint.aspx?params=53687%2C52236%2C52394%2C52395&type=1),
  [compatibility release note](https://compatibility.rockwellautomation.com/GeneratedReleaseNote.aspx?o=&pdf=0&v1=58000&v2=58000)
  and [FLEX catalogue certificate](https://literature.rockwellautomation.com/idc/groups/literature/documents/ct/1794-ct001_-en-e.pdf)
  provide catalogue identity references; the [POINT release note](https://netstorage.rockwellautomation.com/WebFiles/ReleaseNotes/1734-RN002F-EN-E.pdf)
  includes POINT and ArmorPOINT adapters.
- A per-direction census of missing, single Decorated, Decorated with L5K,
  Decorated with other formats, multiple Decorated, L5K-only, other-only and
  mixed non-Decorated representations, plus unavailable context. One Decorated
  representation may be inspected alongside other formats. This observes that
  representation's shape; it neither merges their contents nor selects an
  effective value. Multiple Decorated representations stay ambiguous.
- Two observed layouts: a one-dimensional scalar `Data` array with BOOL, SINT,
  INT or DINT element type; and a one-dimensional native-looking `Slot` array
  whose selected structure has `Data:DINT` and, for input, `Fault:DINT`. Slot
  root/array/element series and I/O direction must agree; array/element type
  strings must be identical. Scalar values, full array population and other
  members remain uninterpreted. Missing, duplicate and unsupported shapes
  receive distinct first-gap bins.
- Fixed root-type series categories, top-level presence counts for Data, Slot,
  SlotStatusBits, Fault and other members, and root-header consistency bins.
  Header comparison checks only the recognized catalogue's numeric series and
  the tag's I/O direction. It cannot certify that a module-specific identifier,
  version or communication format is legal. Unknown identifiers are never
  published.

The strict native Slot observation uses the documented four-part header form.
That form is documented for the CNB/CNBR child structures; this investigation
does not establish that every nested type from every adapter family has the
same spelling. An unfamiliar child header must therefore remain a diagnostic
gap rather than being treated as evidence that the source lacks useful fields.

The separate `slot_header_field_shapes` joint map inspects the selected Slot
structure's fields independently of its header spelling. Its seven fixed bins
are `not_examined`, `slot_missing_or_ambiguous`, `structure_unqualified`,
`fields_unqualified`, `qualified_header_fields_present`,
`unrecognized_header_fields_present` and `mismatched_header_fields_present`.
Inspection still requires qualified ancestry and representation, a unique Slot
array, supported dimensions/index syntax and an unambiguous selected element.
The field test requires one scalar DINT Data member and, for input, one scalar
DINT Fault member. Unrecognized/missing root, array or element type spellings
remain unrecognized; recognized but disagreeing headers remain mismatched.
No new type spelling is accepted as native or published.

These source-only observations preserve the strict first-gap dispositions:
an unknown array type still yields `array_unsupported`, and a later header
failure still yields `slot_shape_unsupported`. The joint map makes their
qualified field evidence visible without promoting either to a native observed
shape or a binding. Its total equals rack declarations, including repeated
candidates sharing a representation; it is not a count of unique source
elements. Qualified-header fields exactly conserve strict observed Slot shapes;
other examined bins are bounded by Slot presence and the corresponding strict
gap populations. Earlier qualification failures stay `not_examined`.

Every disposition is joined to input/output direction, and every observed
layout is joined to exact known product. Observed header-consistency counts
also conserve observed shape totals. These joint counts prevent combining
unrelated marginals into a stronger claim. The header categories distinguish
unavailable context, unrecognized type, unknown product identity, direction
mismatch, series mismatch and consistent series/direction. Consistent/mismatch
claims require known product counts; observed Slot shapes cannot borrow an
unrecognized or wrong-direction header. Top-level member counts are presence
counts per declaration context and may overlap, rather than a partition.

All outputs are fixed keys and bounded counts. Unknown catalogue/type/member
strings, source names, values, IDs, addresses, slot indices and dimensions stay
private. Shared representations are indexed once; each candidate contributes
only its counts, without per-card source copies. Independently widening every
public count slot to 500,000 and using full revision metadata produces 6,773
canonical bytes, below 8,192. Normal authenticated input and existing source,
reference and tag-data resource limits still apply.

## Validation and remaining decision

Focused invented tests cover every disposition, source qualification and
protection ancestry, ASCII identity collisions, controller isolation, missing
and duplicate contexts, alternative formats, unsupported and duplicate numeric
indices, replay tampering, closed publication keys, count conservation, shared
adapters and worst-width/exact-byte publication limits. Schema2 adds catalogue,
representation census, native Slot shape, direction/type mismatch, header joint
feasibility, unknown/mismatched child headers with independently qualified
fields, malicious count-reassignment and frozen-schema1 regressions. No
confidential export or ignored listener is accessed by these tests.

The next return must conserve the same rack/source denominators and show which
known products, layouts, alternative representations and direction-specific
gaps actually occur together. It must preserve frozen samples and existing
bindings. If known product and native Slot observations align, that supports a
focused, documented mapping-rule investigation without another raw-header
request. If unknown products or layouts remain, these finite bins may still be
insufficient; any further source disclosure needs its own bounded approval and
immutable history. A positive observed-shape count alone does not close backing
eligibility, member projection or configuration questions.

The diagnostic targets C12's investigation. A mapping implementation and its
private-source validation may still require a subsequent return; this bundle
does not claim guaranteed completion or Phase 1 acceptance.
The current estimate belongs to the
[pre-team-review tracker](../planning/PRE_TEAM_REVIEW_TRACKER.md); any revision
must retain the eleven completed cycles and explain any added investigation.
