# Stage 5: minimized L5X example (policy 2)

This standalone helper follows the inspected structure counts, full blank skeleton,
value profile and ladder report. It reads the original local export and produces:

- public/fixtures/minimized/controller_demo.L5X
- public/fixtures/minimized/minimized-report.json

The source is opened read-only. Existing files at those output locations are
replaced after successful generation and verification. Use --output-dir to keep
a separate attempt. The earlier reports and helpers are not edited.

## Files

- minimize_l5x.py: arguments and console summary.
- dummy/model.py: XML reading and dummy-value replacement.
- dummy/selection.py: representative selection and coverage anchors.
- dummy/build.py: output serialization, counts, provenance and publication.
- tests/test_minimize_l5x.py: invented cases.
- MINIMIZE_VALIDATION.md: checks performed and their boundaries.

The helper reuses Stage 1 XML preflight, Stage 3 value policies and Stage 4
ladder parsing. It does not import the application or require another dependency.

## Run

From the repository root:

~~~bash
uv run --project python-parser python -B tools/l5x_inspect/minimize_l5x.py --help

uv run --project python-parser python -B tools/l5x_inspect/minimize_l5x.py \
  "confidential/plc-code/YOUR_FILE.L5X"
~~~

Use the original export. A blank skeleton contains no original datatypes, rung
metadata or ladder text from which this helper can select and substitute.

## Selection

Default --per-variant 5 keeps the first five occurrences of each local XML
variant under each retained parent, including when variants are interleaved.
Mandatory selections within those first five count toward the ordinary quota.
It also keeps:

- the first occurrence of every observed local variant anywhere in the export;
- the top five distinct ladder shapes for each Stage 4 ranking;
- a representative of every encountered instruction label, including masked ones;
- ancestors needed to preserve original nesting;
- every descendant of a selected ladder Rung.

The limit is not a global five-per-element cap. Mandatory coverage and complete
selected rung subtrees can exceed five; each retained parent has its own quota. Reduce
--per-variant to 1 in a separate attempt if the first result is too large:

~~~bash
uv run --project python-parser python -B tools/l5x_inspect/minimize_l5x.py \
  "confidential/plc-code/YOUR_FILE.L5X" \
  --per-variant 1 --output-dir public/fixtures/minimized_one
~~~

Policy 2 fixes the policy-1 counter reset between consecutive groups. A sequence
A, B, A, B with limit 1 now retains A, B unless later entries are mandatory.
Retained siblings stay in their original relative order; omitted interleaving
is available in the full blank skeleton. The minimized file does not preserve
every original child-name run or every ladder shape.

The minimized report now has schema_version 2 and policy_version 2. The selection
field is per_parent_variant_limit; per_consecutive_variant_run is retired.
Earlier stage report schemas are unchanged.

A local variant uses the XML path, attribute names and broad value categories,
approved technical values or masked datatype identity, the ordered child-name
runs, direct-text/CDATAness and replacement action. It does not represent
complete subtree equivalence, tag identity or execution behavior. Repeated
multiplicity is recorded in the original counts and the new coverage report.

The writer verifies that all source XML paths and all selected variant IDs are
represented, and that output element/attribute counts reconcile. Retained
children stay in source order. No omitted element is silently counted as retained.

## Replacement policies

| Source field | First-attempt behavior |
|---|---|
| Approved technical literals | Retain Stage 3 permission-list values, plus approved rung edit types |
| Ladder Rung Number | Retain numeric Number |
| DataType outside the permission list | Consistent DUMMY_TYPE labels |
| Names and recognized whole references | Consistent DUMMY_ID labels |
| Ladder Text | Keep instruction/branch layout; replace every whole operand with ARG labels |
| Unlisted instruction name | Consistent UNLISTED_OP label |
| Descriptions/comments | Invented example phrases |
| Other scalar values | Invented small numbers, Boolean literals, fixed example dates or dummy strings |
| Serialized non-ladder payload | DUMMY_SERIALIZED_DATA |
| ST line text | Comment placeholder: (* DUMMY_ST_TEXT *) |
| Mixed direct text with child elements | Invented mixed-text placeholder; report the replacement |
| Original XML comments/PIs | Omit and count |

The --seed option defaults to 0 and makes invented choices repeatable for the
same input/order and helper version. Random values are independent of original
magnitudes. An invented value may coincidentally equal a source value.

Only exact whole recognized identifier/reference strings share a dummy label.
Scope resolution, member paths and cross-rung tag relationships are not resolved.
Ladder ARG labels restart per rung and are separate from XML DUMMY_ID labels.
Private replacement dictionaries exist only in process memory. Public provenance
uses source and output ordinal XML locators plus attribute names.

Numeric formats, array dimensions/indices, task/SFC references and tag/member
links are not repaired for semantic coherence in this first attempt. Declared
BOOL values use 0/1; other numeric substitutions preserve broad lexical categories,
not every controller-specific validation rule.

## Report navigation

Start with:

- coverage: source/retained/omitted elements, paths, ladder rungs and shape counts;
- selection: variants, mandatory selections, ranking reasons and instruction coverage;
- attribute_actions and text_actions: counts of retained-field policies;
- unsupported_content: retained opaque/ST/mixed-text replacements needing later work;
- paths: complete per-path retained/omitted element, attribute and text-value counts;
- occurrence_map: every retained output element linked to its source ordinal locator;
- rungs: retained rung records and their original pattern IDs/structural metrics.

A source text value is counted when the source element has nonblank direct text
or CDATA, matching the profile convention. Whitespace-only container indentation
does not count as a value. Retained CDATA is normalized to one section per element.
The final report includes a SHA-256 of the generated dummy XML only. It is not a
hash of the confidential original.

The XML is published first and the report second. Each individual file uses the
existing atomic writer; the two-file bundle is not one filesystem transaction.
After any publication error, compare output_sha256 with the XML before using an
existing report. A fatal parse/generation error occurs before publication.

## Expected first run and limits

For the unchanged inspected export, source coverage should be 83,942 elements,
194 paths and 4,606 ladder rungs. The policy-1 result retained 44,545 elements
and 2,397 rungs. Policy-2 original-source retained counts remain pending a user
run. It recomputes the rung inventory rather
than trusting a stale saved report.

PASS means the structural fixture and its coverage counts were verified. This
first example has explicit placeholders in serialized data and non-ladder logic;
it has not been validated for Studio 5000 import or controller execution.

Return the console summary. Codex can inspect both new public files locally if
accessible. Keep the original export in confidential/.

## Next iteration

Inspect size, path/variant coverage, dummy values, complex ladder examples,
provenance links and unsupported-content counts. Then make bounded corrections
based on that result. General ASCII rendering, reference resolution, SFC/ST
interpretation and DeltaV conversion remain separate later work.

## Verify regenerated public files

Run the project-specific read-only cross-check after generation:

~~~bash
uv run --project python-parser python -B tools/l5x_inspect/check_public_outputs.py \
  --repo . --fixture-name minimized_review
~~~

This checks the pair against public/xml-skeleton.XML and the three earlier public
JSON reports. Use minimized for the policy-1 baseline. It verifies generated XML
hash, field categories, counts, source order, full retained rung subtrees,
mandatory selections, source/output links, rung metrics and ranked examples.
It writes no files and never opens confidential/. Run without Python -O.
A passing check establishes these structural contracts, not Studio validity.
