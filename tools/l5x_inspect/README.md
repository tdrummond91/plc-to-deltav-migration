# L5X inspection helpers: Stage 1

Standalone auxiliary tools live here, outside the application in `python-parser/`.
This first script discovers XML structure from your actual local export. It uses
only Python's standard library; it does not import `main.py` or the `l5x` package.

## Run from the repository root

```bash
uv run --project python-parser python -B tools/l5x_inspect/summarize_xml.py --help

uv run --project python-parser python -B tools/l5x_inspect/summarize_xml.py \
  "confidential/plc-code/YOUR_FILE.L5X"
```

Replace `YOUR_FILE.L5X` with your filename. Use the original export, not an
earlier compact skeleton. Output defaults to `public/xml-structure-counts.json`
relative to the installed script's repository root, regardless of your current
directory. A successful rerun replaces that report. To keep successive attempts:

```bash
uv run --project python-parser python -B tools/l5x_inspect/summarize_xml.py \
  "confidential/plc-code/YOUR_FILE.L5X" \
  --output "confidential/inspection_runs/attempt_02/xml-structure-counts.json"
```

`--project python-parser` tells uv which Python project to use.
`-B` tells Python not to write bytecode caches.
`--output` selects a different report file. The input is opened read-only.

## What the JSON means

The entire input is counted. There is no sampling limit.

| Field | Meaning |
|---|---|
| `totals.element_occurrences` | Every XML element instance, including containers |
| `totals.attribute_occurrences` | Every attribute present on those instances |
| `totals.distinct_element_paths` | Different element-name paths from the root |
| `totals.max_depth` | Deepest XML nesting; the root is depth 1 |
| `counts_by_element_name` | Element counts summed across all paths |
| `counts_by_attribute_name` | Attribute-name counts summed across all paths |
| `root` and its nested `children` | Counts at each particular XML path |
| `count` on a nested element | All source instances at that path |
| `attributes.Name.count` | Instances at that path with a Name attribute |
| `elements_with_text` | Instances with non-whitespace direct text, including CDATA |
| `elements_with_cdata` | Instances containing any CDATA section, even an empty one |

For example, if 156 source `Data` elements occur under the same element-name path,
that nested node has `"element": "Data", "count": 156`. A `Data` under a different
parent path gets its own nested node. The global `Data` count includes both.

Repeated paths are collapsed in the report, with attributes and children combined.
The report therefore does **not** preserve which individual record had a particular
combination of attributes or children, or the full sibling sequence. Its low line
count does not imply a low source count. Attribute counts are presence counts,
not unique-value counts.

CDATA containing rung text or encoded content is counted as text presence. Its
contents are not interpreted as XML. Ladder instruction and branch counts are
a later stage; an XML `Rung` count alone does not describe those instructions.

## Information included and excluded

Included: XML element names, attribute names, nesting paths, occurrence counts,
and text/CDATA presence counts.

Excluded: attribute values, element text, comments, processing instructions, source
filename/path/hash, namespace prefixes and namespace URIs. Namespace declarations
are not counted as ordinary attributes. Ambiguous names after namespace removal
cause an error instead of being combined.

Counts reveal document size and structure, as requested. XML element and attribute
names remain visible; if an unusual extension encodes private identifiers in those
names, they remain visible too. Review the JSON before sharing it. This is a
structural report, not a general guarantee of anonymity.

The parser accepts XML names it encounters without assuming a complete L5X schema.
Malformed XML, DTD/entity declarations, ambiguous namespaces, more than 128 nested
levels, or more than 50,000 distinct paths stop the run. A failed parse does not
replace an existing report. Diagnostic messages omit source text.

## Tests

```bash
uv run --project python-parser python -B -m unittest discover \
  -s tools/l5x_inspect/tests -p 'test_*.py' -v
```

The 19 tests use invented, in-memory XML and mocked report writes. They exercise
counts, repetition, different paths, optional attributes, text/CDATA, chunk
boundaries, namespace handling, and failure behavior. They do not test a real L5X,
Studio 5000 compatibility, or actual filesystem replacement.

## Next iteration

Run the helper locally, inspect the report, then bring back that JSON and any
error message. We will use it to choose the next small implementation.

The eventual four outputs are a count report, a full blank XML skeleton, a
minimized dummy L5X, and a value/type profile. Only the count report is implemented.
The future full skeleton must keep every element instance; only summary views
collapse repeated paths. Later rung samples may preserve instruction/branch layout
and rung Number/Type while replacing identifiers and constants. Tallest/widest
branch examples and complexity counts remain planned.
