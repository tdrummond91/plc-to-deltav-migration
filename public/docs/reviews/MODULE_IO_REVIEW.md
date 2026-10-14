# Module I/O declarations and reference gap reasons

Implemented on `feat/source-references-pc`, from baseline `73f9a33` after Tyler
authorized the next parser slice. This remains product Phase 1. The new work is
source discovery and scoped root binding; engineering interpretation, editable
correction overlays, PCSD and FHX remain later stages.

## Behavior

Previously, module InputTag/OutputTag/ConfigTag elements were outside the symbol
model. An alias referring to one of those roots could stay unresolved even when
its declaration was present. The reader now captures module ports, ordinary
connections and these three I/O declaration kinds, with raw attributes and
controller scope. Their counts are separate from ordinary Tag definitions.

Reference analysis retains explicit I/O names and can infer names when supported
topology is coherent. In the invented example, an unnamed InputTag on Local slot
3 supplies `Local:3:I`, and an alias to `Local:3:I.Data.0` binds to that declaration.
This proves root lookup only; the member and bit suffix are not validated.

Private symbols record name_origin and name_reason. Naming supports ICP
backplane slots, directly attached Ethernet modules and connection-specific
I/O suffixes. It verifies unique controller/module/port/connection context and
the ancestor chain to the Local anchor. Missing, ambiguous, unsupported or cyclic
context leaves a named gap. Raw inventory records are never changed. Duplicate
resulting names remain ambiguous in the resolver. AOI scope stays isolated.

RackConnection/InAliasTag/OutAliasTag are not treated as ordinary connections
or tags; each rack connection has an explicit unsupported diagnostic. Module-root
configuration tags without a supported child-slot/Ethernet edge remain unnamed.
Values, Data children, channel types and CatalogNumber are not used to guess names.

Every private alias/operand binding has a reason field. Fixed unresolved reasons
distinguish missing ordinary/colon-shaped roots, invalid scope and AOI-local alias
restrictions. Unsupported-address reasons distinguish qualification, dynamic
indices, malformed syntax and length/expanded-suffix limits. A terminal alias
failure preserves its reason. `colon_root_not_declared` is a syntax observation,
not proof that an address is I/O or that the source is invalid.

## Basis and limits

Rockwell documents module ports, configuration data, connections and I/O suffix
attributes in [1756-RM014, chapter 4](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf).
Its [Logix design manual, chapter 10](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm094_-en-p.pdf)
describes location/slot/type I/O addressing. The implemented mapping from the
captured topology to root strings is a conservative inference from those
conventions, tested with invented examples. It does not claim support for every
hardware family, rack-optimized layout or exported project topology.

Source grammar tests deliberately exclude vendor metadata named Connection.
No member existence, data types, array bounds, read/write effects, execution order,
alarm consequence, shutdown behavior or DeltaV equivalence is inferred here.

## Versioned outputs

| Artifact | Current contract |
|---|---|
| Private inventory | schema 2, source-inventory-2 |
| Private references | schema 2, source-references-2 |
| Source aggregate | schema 3, policy 2, aggregate-summary-3 |
| Reference aggregate | schema 2, policy 2, reference-summary-2; nested source schema 3 |
| Work-check envelope | schema 1, work-check-1, unchanged |
| Private run manifests | inventory 1 / reference run 2, unchanged |

The public reference report adds module_io counts by naming origin and fixed
unavailable reason, plus unresolved/unsupported-address reason counts for aliases
and operands. Counts reconcile with statuses, source declarations and parent
presence. Fields and labels are closed, rendered reports stay below 32 KiB, and
private reference records undergo canonical reanalysis before aggregation.

Previously supported source-v2 and reference-v1/source-v2 reports still validate,
including the returned work-check reports. Mixed versions are rejected. Historic
source-v1 files are preserved without expanding the supported validator contract.
No private-run import or migration is introduced.

## Validation

```bash
uv run --project python-parser --locked python -B -m unittest discover -s python-parser/tests
uv run --project python-parser --locked python -B -m unittest discover -s tools/l5x_inspect/tests
git diff --check
```

Final application run: **208 tests, 207 passed and one existing Windows symlink
skip**. All **139 helper tests passed**. The 49 focused module tests cover raw
hierarchy, exact paths, naming/provenance, collision and scope isolation, source
immutability, failure reasons, privacy, forgery rejection, legacy compatibility,
mixed-version rejection, publisher validation and nested work-check acceptance.
Additional reference tests cover reason classification and alias propagation.

Independent review reproduced and then verified three fixes:

- Name expansion now has a 65,536-character per-name limit and an 8-million-character
  total budget checked before joining strings. A 55,532-byte invented XML that
  previously expanded into 65,540,000 name characters now fails with a fixed
  resource-limit error. The public workflow can report the failure without names.
- Port IDs are indexed once, avoiding repeated scans of a wide parent. Reviewer
  timing for 2,000/4,000 ports and children improved from 0.274/1.107 seconds to
  0.032/0.081 seconds. These timings demonstrate the issue/fix, not a performance SLA.
- Public source and nested reference validators reject positive input/output
  counts with no ordinary connection parent. Regression tests cover both paths.

The final reviewer reported no remaining blocker after running all 49 focused
tests and repeating the resource/accounting reproductions.

The actual `run-work-check.sh` launcher also passed in a temporary checkout with
an independently invented 1,181-byte source and a local bare Git remote. It
fast-forward pulled the updated code, ran 208 application tests (one skip) and
139 helper tests, saved the private six-file bundle, and committed/pushed only
the new 7,880-byte aggregate. Exit 0 correctly represented useful partial analysis.
Three unnamed I/O declarations derived backplane names; one alias and four
operands bound, with one colon-root operand unresolved. Validation checked
manifest/inventory/reference schemas 2/2/2, work/reference/source report schemas
1/2/3, artifact hashes, unchanged source bytes, remembered input selection, absence
of source sentinels in the aggregate, a clean checkout and matching local/remote
tips. These temporary commits/reports were not pushed to GitHub. The subsequent
real-source result is recorded below; it does not establish every topology case.

The [invented module fixture](../../fixtures/synthetic/module_io_demo.L5X) and
[aggregate example](../../examples/module-reference-summary.synthetic.json)
provide a small review case: six derived I/O names, one bound alias, six bound
operands and one missing alias/operand root. Manually specified counts in its
README were independently checked against the analysis. Revision is unavailable
in this illustrative aggregate; it is not a real work-machine result.

The public blank XML skeleton yields 120 modules, 137 ports, 104 ordinary
connections, 104 input tags, 65 output tags and 83 configuration tags, plus 11
rack diagnostics. All 252 I/O names remain unavailable because attributes are
blank/scrubbed. This confirms structural capture only. Those naming reasons do
not predict real-source failures. No actual confidential input was opened.

## Returned work-machine evidence (2026-10-13)

Commit f91ae18 contains
[work-check-20261013T234851Z-b10d84dc.json](../../inspection/work-check-20261013T234851Z-b10d84dc.json),
testing clean revision 6585443. It passes the current validate_work_check_report
validator, as does the preceding report from f38d81e. The new report records
208 application tests (207 passed, one skipped), all 139 helper tests passed,
no failures/errors, partial analysis, no analysis failure code and
private_run_saved=true. This is returned work-machine evidence, not a fresh local
test-suite execution or independent inspection of its private bundle.

| Measure | Previous report | Module/I/O report |
|---|---:|---:|
| Named module I/O declarations | not modeled | 252 of 252 |
| Bound aliases | 45 | 842 |
| Unresolved aliases | 896 | 99 |
| Bound operand occurrences | 17,856 | 20,178 |
| Unresolved operand occurrences | 2,642 | 320 |
| Unsupported-address operands | 870 | 870 |

The reader captures 137 ports, 104 ordinary connections, 104 input tags,
65 output tags and 83 configuration tags. Naming derives 164 backplane-slot
roots and 88 module-name roots, with no unavailable names, unnamed symbols or
ambiguous symbol groups. Alias bindings increase by 797 and operand bindings by
2,322. These are root-lookup improvements, not evidence of correct member types,
instruction effects or engineering interpretation.

All shared source counts match the preceding report: 4,606 rungs, 17,874
instructions, 6,307 ordinary tags, 941 aliases and 120 modules. Instruction
histograms, routine types, ladder metrics and reference coverage are unchanged.
Routine/rung accounting still reports 14 unsupported SFC routines and one RLL
routine without content. Unmodeled XML decreases from 60,814 elements/149 paths
to 59,975 elements/141 paths. Diagnostics now also expose 11 unsupported rack
connections and 10 declarations outside supported context; the earlier routine
diagnostics remain unchanged. These aggregate comparisons do not prove source
byte identity.

All remaining 99 unresolved aliases and 320 unresolved operands have
colon_root_not_declared. The aggregate does not link these occurrences to the
11 rack connections, so it cannot prove rack support would resolve them all.
Of the 870 unsupported-address operands, 868 have malformed_address and two have
non_static_array_index. "Malformed" means outside the current address grammar;
the report does not prove the original PLC source is invalid. Literal operands
(2,517), unsupported expressions (45) and operands in uncatalogued instructions
(653) are unchanged. No cycles, depth limits, ambiguity or argument-count
mismatches appear.

## Next bounded work

Tyler explicitly authorized a listener after this result returned. Listener
implementation is in progress; see the forthcoming FEEDBACK_LISTENER.md for
the implementation and verified activation status. This note does not claim that
a background monitor is active.

After that workflow is complete, prioritize evidence for the 868 addresses
outside the current grammar. Design a closed aggregate address-shape breakdown
and independently invented examples before broadening resolution. Preserve
qualified/dynamic and missing-root gaps as separate cases. If the aggregate
cannot distinguish the required syntax, stop for bounded work-machine
investigation instead of requesting raw addresses, reference records or logs.
Rack mappings are another bounded candidate, but their relationship to remaining
unresolved roots is unproven. No parser change or extra work-machine run is
required just to review this returned report. Phase 1 remains active.
