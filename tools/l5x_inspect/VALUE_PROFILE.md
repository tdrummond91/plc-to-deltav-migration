# Stage 3: values, types, and routine coverage

This helper profiles the original local L5X. It writes one JSON report at
`public/xml-value-profile.json`, using paths that connect back to Stage 1's
nested structure. It is separate from the application and needs only Python's
standard library plus the existing `summarize_xml.py` beside it.

## Run

From the repository root:

```bash
uv run --project python-parser python -B tools/l5x_inspect/profile_values.py --help

uv run --project python-parser python -B tools/l5x_inspect/profile_values.py \
  "confidential/plc-code/YOUR_FILE.L5X"
```

Use the original export, not the blank skeleton: values are needed locally to
count types and distinct values. Add `--output PATH` to select another JSON.
A successful run replaces the report at that path. It opens the source read-only.
No network, AI service, package installation, or application import is involved.

## What each path records

The report's `paths` array has one entry per XML element-name path.
Each entry contains its element count, attribute profiles, and optional direct-text
profile. Missing attributes are counted relative to elements at that same path.

| Field | Meaning |
|---|---|
| `occurrences` | Values encountered for this particular path/attribute |
| `unique_value_count` | Distinct parsed strings, counted privately in memory |
| `lexical_type_counts` | Empty, boolean, integer, radix integer, real, date-like, identifier-like or other string |
| `technical_value_counts` | Observed literal values permitted by the explicit technical allowlist, with counts |
| `withheld_occurrences` | Observations whose literal value is not published |
| `withheld_unique_value_count` | Distinct withheld values |
| `declared_datatypes_on_same_element` | DataType metadata for a Value/ForceValue or direct-text field; no inherited/resolved type inference |
| `missing_on_elements` | Elements at this path that lack this attribute |
| `repeated_small_value_set` | A heuristic for a small repeated set; not proof that a field is an enum |
| `synthetic_examples` | Invented placeholders, not source excerpts or anonymized quotes |

An **enum** is a field with a limited set of named choices. Low cardinality alone
does not establish that a field is an enum: two repeated equipment names must not
be published just because only two names exist.

A **lexical type** describes how text is written. `Value="0"` is an integer
literal, even when the same element says `DataType="BOOL"`. Those two facts
are reported separately. `date_like` recognizes a limited set of date shapes;
it does not validate the calendar or convert units. Unrecognized formats remain
strings. Integer syntax never selects SINT/INT/DINT based on the value's size.

The distinct count is based on parsed strings, including surrounding whitespace.
XML parser normalization of entities/attribute whitespace applies. This is not a
comparison of the original source bytes. Direct text is concatenated per element;
descendant text is not included. Whitespace-only indentation is excluded unless
an explicit CDATA section is present. Empty CDATA is an empty text observation.

## What values can appear in the shared report

The initial permission list includes common built-in datatypes; routine types;
task types; TagType, Radix and ExternalAccess options; and documented Data formats
such as L5K, Decorated, Message, String, Alarm and HMIBC.

This is deliberately **not** a complete catalog of valid Logix values. A valid
built-in datatype outside the list is withheld, just like a custom name. The
report does not label every withheld type as a user-defined type.

Attribute names and field context determine which list applies. For example, a
Name value that happens to equal DINT is still withheld. Names, descriptions, tag
references, dates, constants, and source logic are not included as actual values.
All description examples are independently invented.

Literal permissions and format distinctions were checked against Rockwell's
[Logix 5000 Controllers Import/Export Reference Manual, 1756-RM014D](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf)
(data formats, tag definitions, and routine definitions). This helper is not a
complete schema validator. Later iterations may expand the permission list.

The JSON still contains XML names, structure/counts, and approved technical
choices. Review it before sharing, including any unusual extension names.
There are no source hashes, input filenames, source paths, raw unique-value lists,
or real-to-dummy mapping dictionaries in the report.

## Routine gap investigation

`routine_coverage` contains:
- total Routine records and counts of approved Type values;
- counts of review findings;
- one record per Routine, identified by an ordinal XML path.

For example:

```text
/RSLogix5000Content[1]/Controller[1]/Programs[1]/Program[2]/Routines[1]/Routine[6]
```

This identifies the sixth Routine under that second Program without publishing
either name. It is usable against the same source and full skeleton. It is not a
stable identity across exports whose element order changes.

Coverage uses **direct routine children**. An STContent beneath an SFC transition
Condition does not count as an ST routine. Records flag absent/unrecognized
content, multiple blocks, Type/content differences, unknown/missing types, and
direct protection markers. These are review findings, not proof that the PLC
project is invalid. For example, an empty routine may be intentional.

This is intended to explain the previously observed 70 Routine records versus
69 recognized content blocks. That explanation remains pending the real run.

## Coverage, limits, and next step

`source_totals` preserves fresh Stage 1 totals for comparison. `coverage` records
profiled fields, ignored comments/PIs, routine records, and EncodedData element
counts. Opaque payloads are profiled as text shapes/counts; they are not decoded.

Ladder instructions, branch dimensions, reference resolution, and PLC semantics
remain unimplemented. Synthetic ladder/ST placeholders are not compilable examples.

The tool preflights XML with the existing parser and verifies structural counts
again while profiling. It retains source strings only in local process memory for
exact distinct counts, then writes only the permitted report fields. Limits stop
the run at one million accumulated distinct field values or 16,777,216 direct-text
characters per element. No partial report is published on a parsing/profile error.

Do not edit the source during a run. Input/output must differ. Failed runs leave
the previous report in place. Real filesystem output is checked by the user run.

Next: inspect this report, especially routine findings and withheld value counts.
Use those results to select the next small extension before constructing a
minimized dummy L5X or ladder parser.
