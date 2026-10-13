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
tips. These temporary commits/reports were not pushed to GitHub. Real-source
improvement and production topology coverage still require the next user run.

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

## Next work-machine evidence

Run `bash ./run-work-check.sh` on the existing branch. The script remembers the
local source, pulls, tests, analyzes, and pushes only its aggregate/test report.
No manual output copying or new sharing approval is required.

On return, validate the report and tested revision, then compare ordinary source
counts, module declarations/naming, alias and operand status/reason counts, and
remaining gaps. The preceding real-source baseline had 896 unresolved aliases
and 2,642 unresolved operands; those totals were not proven to be entirely I/O.
Do not claim improvement until the new real-source aggregate arrives.

Tyler's listener idea remains a follow-up proposal. No background monitor or
scheduled task has been activated. Future polling should process new work reports
once, serialize repository work, ignore its own code pushes and stop for required
investigation, questions or a phase decision.
