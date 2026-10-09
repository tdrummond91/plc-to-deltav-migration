# Stage 2: full blank XML skeleton

Run this only after Stage 1 has counted the original local L5X. Keep both helpers
together under `tools/l5x_inspect/`; `write_skeleton.py` uses the Stage 1 parser
for preflight and count verification. Neither helper imports the application.

## Run from the repository root

```bash
uv run --project python-parser python -B tools/l5x_inspect/write_skeleton.py --help

uv run --project python-parser python -B tools/l5x_inspect/write_skeleton.py \
  "confidential/plc-code/YOUR_FILE.L5X"
```

Default output: `public/xml-skeleton.XML`. Use `--output PATH` to choose another
location. A successful run replaces the chosen output; archive an earlier skeleton
first if you want to retain it. The source file is always opened read-only.

## Preserved and removed

Preserved:
- every element instance, including repeated siblings and nested records;
- original element order and the attribute names on each particular element;
- each CDATA section as `<![CDATA[]]>`;
- local XML names and their nesting.

Removed:
- every attribute value, including Number, Type, DataType, names, dates and IDs;
- all source text, CDATA contents, comments and processing instructions;
- namespace prefixes, URIs, and namespace declarations.

Keeping selected technical values or rung layouts belongs to the later minimized
dummy L5X stage. This full skeleton has **all** values blank. It is a structural
XML example, not an importable Studio 5000 project.

Whitespace, empty-element spelling, XML declaration, and encoding are normalized
to readable UTF-8 XML. The source is not reproduced byte-for-byte.

For example:

```xml
<Root>
  <Tag Name=""></Tag>
  <Other></Other>
  <Tag AliasFor=""></Tag>
  <Rung Number="" Type="">
    <Text>
      <![CDATA[]]>
    </Text>
  </Rung>
</Root>
```

The two Tag records remain separate and keep their own attribute names. No
sampling, merging of repeated paths, or dummy-data generation occurs.

## Automatic checks

The helper:
1. Counts the original input using the existing Stage 1 parser.
2. Reads the source again and streams only blank XML into a temporary output.
3. Counts the temporary skeleton and compares its complete nested/global summary
   to the original, allowing only the expected loss of text.
4. Publishes the skeleton only if those counts match and it has no nonblank text.

The comparison covers element and attribute occurrence counts, paths, nesting
depth, first-seen path order and elements containing CDATA. The renderer preserves
every CDATA section and full sibling sequence; dedicated tests check those, since
the aggregated count report alone cannot prove complete sibling order.

Do not edit the source during a run. Preflight rejects malformed XML, DTD/entities,
namespace-name collisions and the same depth/path limits as Stage 1.
Failed parsing or verification leaves an existing output in place. Temporary
output contains only blank XML. IO permissions must be checked by the local run.

XML names, counts and full structural ordering remain visible intentionally.
This does not prove that every unusual extension name is nonconfidential; review
the output before sharing.

## Expected first-run result

For the unchanged export represented by the submitted Stage 1 JSON:

```text
PASS: 83942 elements; 213876 attributes; 194 paths; 18351 elements with CDATA; depth 14.
```

These numbers are acceptance targets from the user's report. The script itself
compares against fresh counts from the selected source, not hardcoded targets.
Different counts may mean the export changed or a different file was selected.

Start by returning the PASS line or error, plus a small reviewed excerpt if
anything looks wrong. There is no need to paste the entire full skeleton at once.

## Validation

On 2026-10-09, 35 tests passed: 19 existing count tests and 16 new skeleton tests.
All tests use invented XML and in-memory or mocked output; no actual plant L5X was
read by Codex, and real filesystem publication remains user-run verification.

Coverage includes repeated records and sibling order, optional attributes per
record, removal of values/text/comments/PIs, empty/multiple CDATA sections, mixed
content, UTF-16 input, namespaces, DTD rejection, structural mismatch detection,
same-file protection, and publication only after successful verification.

```bash
uv run --project python-parser python -B -m unittest discover \
  -s tools/l5x_inspect/tests -p 'test_*.py' -v
```

Next stages remain separate: local type/value profiling and routine coverage,
then a minimized dummy L5X including selected rung patterns and branch metrics.
