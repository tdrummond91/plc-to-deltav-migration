# Scoped source-reference implementation review

Date: 2026-10-13. Branch: **feat/source-references-pc**, based on remote
**3dd1b25**. Tyler authorized continuing after the readable aggregate matched
the earlier baseline. No confidential sources were opened. This is Phase 1
source understanding, with private drill-down and approved aggregate feedback.

Implementation commit: **b8d92bc03ef7168b17d4e07a6beaddd1fce9f00f**
(`feat(references): bind scoped tags and aliases to ladder operands`).
The final full tests covered that implementation; the installed CLI then generated
the [synthetic aggregate example](../../examples/reference-summary.synthetic.json)
with clean code provenance at that exact commit. No main merge is authorized or claimed.

## Returned evidence and branch continuity

[summary-002.json](../../inspection/summary-002.json) records a clean application
revision 1a69d56, schema/policy v2. Closed-schema/count validation passes.
It matches the earlier public baseline: 4,606 parsed rungs, 17,874 instructions,
6,307 tags, 941 tag aliases, 120 modules, 70 routines (56 RLL/14 SFC), one AOI
and no encoded regions. All ladder totals and maxima reconcile. There are no
failed/excluded rungs. The remaining diagnostics are 14 unsupported SFC routines
and one RLL routine without its content block. This confirms readable evidence
and structural agreement, not byte identity or full engineering interpretation.

The previous [summary-001 review](WORK_MACHINE_SUMMARY_001_REVIEW.md) remains
historical: that export exposed 70 encoded regions and no readable rungs.
The work-machine force-push rewrote the report commit and omitted the earlier
review notes. The new branch starts from the current remote report commit and
restores those notes from 516a24a, preserving the original local branch too.
No remote history was reset or force-pushed from this PC. Work-machine test-suite
outcomes have not been supplied; aggregate validation is separate evidence.

## Implemented behavior

- `references.py` consumes the captured inventory without file IO,
  source mutation or a second XML parse. Symbols retain source declaration IDs.
  Occurrence IDs include snapshot, instruction ID and argument index.
- Case-insensitive program-local lookup precedes that program's controller.
  Duplicates in the nearest scope are ambiguous; lookup does not fall back after
  ambiguity. Controllers stay separate and AOI definitions are isolated.
- Alias traversal uses each alias declaration's scope, detects cycles by entity
  ID, and preserves the chain plus target-to-caller member/index suffix order.
  AOI alias-parameter targets are limited to local tags in the same AOI.
- Whole-operand recognition handles roots, member paths, numeric bit suffixes
  and static numeric indices, including multidimensional subscripts. Supported
  numeric/string constants and JMP/LBL label positions create no tag link.
- The small explicit signature catalog covers basic bit operations, comparisons,
  MOV/arithmetic/CLR, timer/counter-reset, copy and PID operand slots. CPT's result
  can bind, but its expression remains unsupported. Calls, opaque/custom AOIs,
  system selectors and sequence/file instructions are not guessed.
- `plc references` provides private text/JSON and optional append-only storage.
  Reference runs include source evidence plus references.json/references.txt;
  schema-2 manifests finalize all artifacts with hashes and combined status.
- `plc reference-summary` publishes fixed symbol/alias/operand counts plus the
  existing source summary. The publisher independently dispatches only the two
  approved report kinds; arbitrary private dictionaries cannot use this path.

These are declared-root bindings, not read/write dependencies. Member existence,
dimensions/bounds, access rules, datatype compatibility, call-instance semantics,
scan effects and engineering classifications are deliberately unimplemented.
Missing InputTag/OutputTag/ConfigTag modeling can leave module addresses unresolved.
Dynamic indexing and qualified cross-program addresses remain explicit gaps.

`complete` applies only to the declared scope. Unknown zero-argument instructions,
unnameable/duplicate declarations, incomplete aliases, unsupported operands and
source partial coverage prevent a complete reference result. Missing members on
otherwise bound roots are not discovered because member validation is not part
of this contract.

## Bounds and publication contract

The analyzer limits operands to 250,000, alias traversal to 64 links and each
recognized/expanded address to 65,536 characters. Retained alias-chain ID and
suffix characters share an 8,000,000-character budget across the result. Global
budget failure raises a fixed source-free error and produces no summary; it
does not silently truncate evidence or claim a successful report.

Private reference schema/analyzer: 1 / source-references-1. Aggregate kind:
l5x_reference_review_summary, schema 1, policy 2, exporter reference-summary-1.
The nested source_summary remains schema 2 and owns code revision metadata.
Both private saving and aggregate building call a shared integrity validator.
It repeats the bounded reference analysis over the captured inventory and compares
every field using exact types; it never rereads XML or serializes an unchecked
candidate. This trades a second reference pass for one canonical set of lookup
rules and rejects altered targets/chains/statuses even when counts still agree.
The builder also reconciles private snapshot IDs and symbol/alias/operand occurrence
sets before reconstructing counts. Publication checks exact fields, fixed enums,
strict numeric types, reconciled totals and partial status, with a 32-KiB cap.
No source names, values, hashes, identities or individual relationship records
enter the public format. No extra per-report sharing gate is imposed (D026).

## Evidence for lookup rules and catalog boundaries

- Case, scope precedence, module root forms and ordinary alias chains:
  [Rockwell PM004L](https://literature.rockwellautomation.com/idc/groups/literature/documents/pm/1756-pm004_-en-p.pdf),
  sections on tag scope, naming and aliases.
- AOI isolation, externally accessible parameters and alias restrictions:
  [Rockwell PM010N](https://literature.rockwellautomation.com/idc/groups/literature/documents/pm/1756-pm010_-en-p.pdf),
  sections on encapsulation, parameters/local tags and alias parameters.
  Definition binding does not substitute for call-instance analysis.
- L5X module tag envelopes, AliasFor syntax and neutral ladder signatures:
  [Rockwell RM014D](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf),
  printed pp.87-89,128,212-222. Metadata/selector arguments are why an explicit
  catalog is used instead of binding every identifier-shaped argument.
- Qualified direct program-parameter access:
  [Rockwell PM021E](https://literature.rockwellautomation.com/idc/groups/literature/documents/pm/1756-pm021_-en-p.pdf),
  printed p.33. The documented backslash form is distinct from external
  [FactoryTalk tag paths](https://www.rockwellautomation.com/en-ie/docs/factorytalk-services-platform/6-60/factorytalk-services-platform-help-ditamap/factorytalk-linx-help/frequently-asked-questions/tag-name-ftds-l5k.html).
  Both qualified forms stay unsupported here rather than claiming ordinary local-tag access.

The manuals guide conservative syntax/lookup rules, not a controller validator.
The independently authored fixture is not certified for Studio 5000 import.

## Validation

Commands from the repository root:

```bash
uv run --project python-parser python -B -m unittest discover -s python-parser/tests -v
uv run --project python-parser python -B -m unittest discover -s tools/l5x_inspect/tests
```

Final integrated result: 107 application tests run, 106 passed, one existing
Windows symlink-capability skip; all 139 helper tests passed. New tests cover
scope/case collisions, AOI isolation, aliases/cycles/limits, static/dynamic
addresses, labels and unknown roles, deterministic occurrence IDs, source
immutability, private storage, publication filtering and aggregate reconciliation.
Independent review passed all 48 reference tests. Its record-integrity finding
was fixed: both output paths now reject dangling/cross-snapshot targets, missing
bound symbols, changed alias chains/raw targets and wrong targets that happen to
exist in the source. Private rejection precedes workspace creation. Final review
reported no remaining blocking issue.

Installed CLI checks ran from an unrelated temporary working directory using
the synthetic fixture. Both commands returned the expected partial status,
source bytes remained unchanged, the private run finalized with matching report
and hashes, and a repeated aggregate destination was refused without altering it.
The fixture yields 15 symbols, one bound alias, 30 operands (23 bound roots,
three literals, two non-data label arguments and two unsupported JSR arguments),
with 24 of 25 instruction signatures catalogued. Its SFC routine remains unsupported.

An independent scale probe constructed 4,606 invented rungs, 18,424 instructions
and 27,636 operands in memory. On this PC it took 0.338s to inventory, 0.299s to
analyze references and 0.675s to validate/build the aggregate (1.312s total).
The aggregate was 3,856 bytes. These are synthetic timing observations, not a
performance guarantee for the private export or another computer.

## Next bounded action

Run [the work-machine reference procedure](WORK_MACHINE_REFERENCES_RUN.md) on the
readable export and return the aggregate through Git. Prioritize the next model/
catalog gap from those counts before adding instruction effects or classifications.
Editable review records, correction survival, PCSD, FHX and GUI remain later work.
