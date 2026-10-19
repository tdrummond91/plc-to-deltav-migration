# Authored communication interpretation

Updated 2026-10-19. This is a source-supported R3 investigation and implementation
record. It does not close R3 or establish communication behavior on the plant.
Return `883002a` validated context2: all 27 records are catalogued, including six
CIP Generic records whose configured service still needs interpretation.
Context3 adds the bounded numeric interpretation described below.

## Evidence and scope

The primary reference is Rockwell Automation's
[Logix 5000 Controllers Import/Export, 1756-RM014D-EN-P](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf),
September 2025, printed pages 140-142. It enumerates authored message types,
communication-method codes and local/remote field meanings. Printed page 375
independently confirms `SLC Typed Write`; the current table has defective
punctuation between that entry and `Unconfigured`. The catalogue uses those
separate exact entries, not the fused text produced by PDF extraction.

Communication context2 classifies the 21 documented exact `MessageType` strings.
The family groups are block transfer, CIP data table, CIP generic, PLC2
unprotected, PLC3 typed and word range, PLC5 typed and word range, SERCOS IDN,
SLC typed, unconfigured and module reconfigure. The nine read/write families
have separate authored read and write dispositions. CIP generic remains
`service_dependent`; reconfigure and unconfigured remain separate dispositions.
Matching is case-sensitive and exact. Missing, blank and unrecognized message
types remain distinct. Substrings, connection paths and service codes cannot
assign a family or direction.

The fixed communication-method catalogue recognizes `CommTypeCode` 0 through 4:
CIP, DH+, CIP with source ID, block transfer via universal remote I/O, and block
transfer via ControlNet. Missing values, malformed strings and unrecognized
numeric codes have separate dispositions. Only canonical unsigned ASCII decimal
strings are interpreted. Leading zeros, surrounding whitespace, signs, radix
prefixes and non-ASCII digits remain `invalid`; their exact authored text stays
in the private record. Unknown numeric codes are never converted to an unbounded
integer or published verbatim.

## Interpretation and populations

Each supported parameter record receives an `interpretation` with a message-type
status, family, authored direction, communication-method disposition and four
field-shape dispositions. Shape distinguishes missing, blank and present
`LocalElement`, `DestinationTag`, `RemoteElement` and `ConnectionPath` fields.
Unsupported owner, envelope or namespace contexts receive only
`unsupported_context` interpretation dispositions. Earlier source-capture status
and exact attributes remain intact.

These shapes make missing/blank evidence visible without imposing a universal
mandatory-field rule. Different message families use different addressing forms;
for example, the presence of rack/group/slot fields does not establish that a
missing remote tag is erroneous. A present path is not a validated route.

For a supported parameter record, a nonblank local-element field receives an
authored local-destination role for reads and a local-source role for writes.
Generic local elements remain service-dependent. A nonblank destination-tag
field retains its explicitly authored destination designation without claiming
that it is the destination of a completed transfer. Unconfigured records do not
promote either field into an active role. Blank endpoint fields become field
gaps. Binding status remains independent: an authored source role does not prove
that its spelling names a valid member or even resolves to a declaration.

Repeated calls, owners and parameter records have different denominators.
Coverage reports the unique owners referenced by occurrences, unique referenced
parameter records, unique owners with linked occurrences and unique linked
parameter records. Parameter family/direction counts include uncalled source
records. Occurrence directions count calls: only a `linked` occurrence can carry
its single parameter record's authored direction. All other occurrence states,
including duplicate representations, have `unavailable` direction. Parameter
records in a duplicate configuration are still independently described; no
effective configuration is selected.

The existing `status` continues to describe source capture. A complete capture
may contain unknown message types, invalid method codes or unresolved authored
directions. The new closed histograms carry these distinctions explicitly;
`complete` must not be presented as complete protocol or runtime analysis.

## Numeric generic selectors in context3

The current MessageParameters table in
[1756-RM014D-EN-P, printed pages 141-142](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf)
defines these selector ranges. Historical appendix tables contain different
ranges; context3 uses the current attribute table and does not treat its range
as proof of an on-wire service or a remote object's implementation.

| Authored field | Accepted encoding | Inclusive numeric range |
|---|---|---:|
| ServiceCode | `16#` followed by ASCII hexadecimal digits | 0-32767 |
| ObjectType (class) | `16#` followed by ASCII hexadecimal digits | 0-32767 |
| TargetObject (instance) | Canonical unsigned ASCII decimal | 0-32767 |
| AttributeNumber | `16#` followed by ASCII hexadecimal digits | 0-65535 |

Hexadecimal digits may use either case and zero padding. Decimal zero is `0`;
other decimal values cannot start with zero. Bare hexadecimal, decimal service
codes, `0x`, signs, separators, surrounding whitespace and non-ASCII digits stay
`unsupported_encoding`. Missing, blank and out-of-range selectors have separate
dispositions. String shape and bounded digit length are checked before integer
conversion; long values never require an unbounded numeric conversion.
This deliberately narrow encoding contract does not claim every undocumented
serialization spelling is invalid in Logix software.

The fixed catalogue identifies decimal service IDs 1, 14 and 16 as
`get_attributes_all`, `get_attribute_single` and `set_attribute_single`.
Rockwell's [22-COMM-D DeviceNet Adapter manual, Appendix C-3 and C-10](https://literature.rockwellautomation.com/idc/groups/literature/documents/um/22comm-um003_-en-p.pdf)
lists the corresponding codes and separately describes which objects implement
them. All other in-range IDs remain `unknown_service`, including vendor or
object-specific requests. No reset, socket or other service is inferred.

The [EtherNet/IP Web Server Module manual, printed pages 132 and 157-159](https://literature.rockwellautomation.com/idc/groups/literature/documents/um/enet-um527_-en-p.pdf)
illustrates Get/Set requests using particular class and instance selectors.
Those examples support retaining service and selector context separately;
they do not establish that an arbitrary target supports that service or that a
configured request will succeed. Context3 keeps the existing
`service_dependent` direction and authored endpoint roles even for a recognized
Get/Set service. It does not select a transfer length, source/destination extent,
target device, effective configuration or runtime behavior.

Only a supported record whose exact type is `CIP Generic` receives numeric
interpretation. Unsupported records remain `unsupported_context`; other types
remain `not_applicable`, even if service fields happen to be present. Private
`interpretation.generic` retains the service disposition, selector statuses,
bounded decoded values and a completeness shape. `all_selectors_parsed` means
only that all four captured selectors use accepted encodings and ranges. It
does not declare them mandatory for every service or validate an entire request.
Original selector text remains in the private attributes.

Public feedback separates three populations:

- `generic_parameter_services` counts every stored parameter record, including
  uncalled and duplicate records.
- `generic_linked_parameter_services` counts distinct generic parameter records
  referenced by linked occurrences.
- `generic_linked_occurrence_services` counts calls; repeated calls can exceed
  the number of records. Unlinked or duplicate-configured calls remain
  `unavailable` and never select one representation.

Four closed selector-status maps and `generic_parameter_completeness` describe
the per-record shapes. All raw and decoded selector values stay private.
Validation checks exact population partitions, service-code dispositions,
feasible selector-completeness intersections and distinct-record/call bounds.
It does not invent correlations between different records' selector gaps.

## Version, privacy and resource contracts

`analyze_communication_context(..., schema_version=2)` and `schema_version=3`
are explicit. The default
remains schema1. Validation replays the supplied version against authenticated
source companions. Summary construction detects the model version. Schema1 and
schema2 output fields, constants and bytes are preserved; schema2 adds interpretation
fields, authored endpoint/occurrence dispositions and closed count maps.
Schema3 adds the generic record/occurrence interpretations and closed maps;
its protocol scope is `authored_catalogue_and_generic_selectors_only`.

The private context retains the existing 8 MiB and 250,000-record bounds.
Interpretations are charged with their enclosing records and final serialization
is bounded again. Public summary1 keeps its 4 KiB cap; summaries2 and3 each have
an 8 KiB cap.
The current summary2 fixture is 4,556 bytes; a conservative width envelope with
every count set to six digits and a full revision is 5,194 bytes. That width
envelope bounds string size; it is not a feasible source population.
The summary3 smoke fixture is 6,536 bytes and its conservative six-digit-count
width envelope is 7,474 bytes, leaving 718 bytes below the unchanged 8 KiB cap.

Only fixed vocabulary and counts enter public summaries. Unknown message names,
method values, service identifiers, addresses, paths and original attributes
remain private. Summary validation conserves parameter, endpoint and occurrence
partitions and checks unsupported contexts, field-presence bounds, direction
availability and unique-reference populations. Present message-type fields must
fit supported interpretations plus the unqualified raw-field allowance.
Endpoint roles must form a feasible partition of the supported directions and
present local/destination fields; unclassified roles cannot absorb known writes,
and an unconfigured record cannot supply two local fields. The check does not
invent field correlations across repeated calls or duplicate records.
Canonical replay rejects altered
interpretations before publication.

## Validation and remaining questions

The schema2 release passed 55 focused communication cases. Those checks cover every
catalogued message type, exact matching, absent/blank/malformed/unknown codes,
generic service non-inference, supported root namespaces, foreign attributes,
invalid envelopes/owners, repeated calls, uncalled controls, duplicate source
representations, forged private and public interpretations, resource boundaries,
and historical schema1 hashes generated from return `31cc08b` using invented
fixtures. These tests use no plant input.

With context3, both focused modules pass 69 cases. New cases cover all three
service IDs, unknown IDs, every selector's encoding and range edges, very long
numeric strings, source qualification, duplicate and uncalled records, repeated
calls, impossible public count combinations, private replay forgeries, exact
byte limits, and preserved schema2 model/summary hashes. The original schema1
hash checks still pass. The new catalogue does not change prior authored
directions or endpoint roles.

This interpretation does not establish remote-object support, select an effective
configuration, prove configured peers or paths, validate members and bounds,
derive transfer extents, resolve remote tags locally or infer actual runtime
reads/writes. `RequestedLength` and indices remain authored source facts.
Further object-specific behavior would require its documented semantics and
source qualification; recognizing a common service ID is insufficient.

The next ordinary work-machine report can establish the authored family,
direction and method distributions, blank/missing field populations, local-role
dispositions and unique owner/parameter reference counts. It must also verify
that original communication source-capture counts and frozen samples are
preserved. The next context3 report adds service and selector-shape counts for
the six generic records without exporting their selector values. It needs no
new plant excerpts. These counts can identify the next
specific source-supported question without exporting arbitrary values.
