# L5X source inventory and references

`plc inspect` is the first read-only application slice. It captures one local L5X as
immutable in-memory bytes, inventories source envelopes and scoped tags, and
reports each rung's preserved text, outer syntax, instruction arguments, offsets
and structural coverage. JSON and readable text use the same inventory records.

All `inspect` outputs are **private**: they can contain names, comments, raw ladder logic,
source hashes and identifiers. This command is not a scrubber. Keep real inputs
and outputs in approved private storage; do not put them in `public/` or Git.
The existing `tools/l5x_inspect/` publication helpers remain a separate workflow.

## Scoped tag and alias references

`plc references` analyzes the captured source inventory without rereading the
file. It binds supported whole operands to declared tag roots, follows aliases
in each alias's declaring scope, and retains each occurrence with its rung and
instruction IDs. Program locals shadow controller tags; AOI definitions use only
their own parameters/local tags. Case-insensitive collisions are ambiguous.

```bash
uv run --project python-parser plc references public/fixtures/synthetic/controller_demo.L5X
uv run --project python-parser plc references "confidential/plc-code/unit.L5X" \
  --format json --workspace "confidential/workspaces/reference-check"
```

`root_bound` means the declared root and any alias chain were found. It does not
prove valid members, array dimensions/bounds, access permissions, instruction
types, read/write direction or engineering meaning. Static member/index suffixes
are retained as evidence. Expressions, dynamic indexing, cross-program qualified
addresses, uncatalogued instructions and malformed argument lists remain explicit
gaps. Routine labels in JMP/LBL are accounted as non-data; call/sequence/system
instruction roles are not guessed. Module InputTag/OutputTag/ConfigTag declarations
are not yet modeled, so unresolved module addresses may reflect missing model
coverage. This is not evidence that the source project has an invalid tag.

Both text and JSON reports are private. The workspace option creates a NEW run
containing the existing snapshot/inventory/overview, plus `references.json` and
`references.txt`. Its schema-2 `source_reference_run` manifest records artifact
hashes, versions, limits of analysis and combined partial status. The existing
`inspect` run contract remains schema 1. Old runs and inputs are never overwritten.

For portable feedback, run:

```bash
uv run --project python-parser plc reference-summary "confidential/plc-code/unit.L5X" \
  --output "public/inspection/reference-summary-001.json"
```

This approved aggregate includes fixed symbol-kind, alias-status and operand-status
counts, analysis coverage, and a nested `source_summary` using the existing v2
contract. Code provenance is `source_summary.tool_revision`. It contains no names,
values, source identities or individual reference links. Its new report kind is
`l5x_reference_review_summary`, schema 1, policy 2, analyzer `source-references-1`.
The publisher accepts only the two closed aggregate schemas and validates again
before writing. New filename, location, 32-KiB limit and no-overwrite rules apply.

Exit 3 means useful partial results were produced. Reference analysis can be
partial even when the structural inventory is complete. Exit 0 means this bounded
root-binding scope completed; it never means all engineering behavior is understood.
See [validation and exact scope](../public/docs/reviews/SOURCE_REFERENCES_REVIEW.md)
and [work-machine steps](../public/docs/reviews/WORK_MACHINE_REFERENCES_RUN.md).

## Bounded summary for feedback

`plc summarize` applies a separate aggregate publication policy to the captured
inventory. It contains approved count fields, routine-language and instruction
totals, diagnostic counts and global ladder measurements. Unknown source labels
are pooled into fixed withheld buckets. No source hashes, names, operands, XML
paths, rung IDs or layouts are included. Tyler has approved these aggregates for
repository sync: they expose no individual rung logic or process values. His
confidentiality boundary is unit reconstruction with data values, or more than
2% rung knowledge. This command exports no rung samples and does not assess
that threshold for other artifacts.

```bash
uv run --project python-parser plc summarize "public/fixtures/synthetic/controller_demo.L5X"
uv run --project python-parser plc summarize "confidential/plc-code/unit.L5X" \
  --output "public/inspection/source-summary-001.json"
```

Without `--output`, stdout is JSON. An explicit output creates a new UTF-8 JSON
file and prints a fixed save notice to stderr. Existing files/symlinks are never
overwritten. Output inside this checkout may be beneath public/inspection/ or
confidential/. The publisher independently validates and canonicalizes the JSON
before writing, so this path is not a general private-data copy mechanism.
Publication uses a temporary sibling plus an atomic no-clobber hard link; an
unsupported filesystem fails without publishing the candidate. Normal local
NTFS storage is covered by the tests; network-share support is not assumed.
If temporary-file cleanup fails, a `.plc-summary-*.pending` file may remain.
Only the requested final `.json` is the published candidate; a pending file is
never a report to share.

Summary schema/policy version 2 and exporter `aggregate-summary-2` accept only
the source-inventory-1 contract. A complete validated report is capped at 32 KiB.
All counts are strict nonnegative integers and reconcile across groups. Output
cardinality does not grow with unrecognized source labels. The code revision
comes from this application's checkout, with a clean/modified/unavailable flag;
it is not a source-data fingerprint. Modified includes tracked or untracked
application sources/build metadata; docs and plant inputs are excluded. The
command never accesses a network for revision collection.

V2 records `sharing_status=aggregate_sync_allowed` and removes the old review
warning. Existing v1 aggregate reports remain suitable for sync under Tyler's
clarification; they do not require a fresh source run. Their old status string
records the previous policy. Source-inventory schemas are unchanged.

Exit codes match `inspect`: 0 structural completion, 3 partial coverage with a
usable candidate, 1 failure, 2 usage. Parsed syntax is not understood engineering
purpose. See [the work-machine procedure](../public/docs/reviews/WORK_MACHINE_SUMMARY_RUN.md)
for checkout, testing, generation and the exact artifact to return.

## Run from Git Bash

From the repository root, with Python 3.12+ and `uv` available:

```bash
uv run --project python-parser plc inspect --help
uv run --project python-parser plc inspect "public/fixtures/synthetic/controller_demo.L5X"
uv run --project python-parser plc inspect "confidential/plc-code/unit.L5X" \
  --format json --workspace "confidential/workspaces/demo"
```

The first run installs the local package and dependencies. End users will
eventually receive a standalone app; executable packaging is not implemented in
this slice. `uv run --project python-parser python -m plc_workbench` is an
equivalent entry point. The original `main.py` prototype remains available.

Without `--workspace`, the command writes only the requested report to stdout.
`--format text` is the default; `--format json` returns the full inventory. Both
use UTF-8 to preserve multilingual source text, including when redirected. Save
paths go to stderr so redirected JSON stays machine-readable. To inspect one
rung, copy its exact `id` from the inventory's `rungs` list:

```bash
uv run --project python-parser plc inspect "confidential/plc-code/unit.L5X" \
  --rung-id "EXACT_ID_FROM_THE_SAME_SNAPSHOT" --format json
```

IDs identify occurrences within one byte snapshot. Changing the source creates
new IDs; they are not persistent review-object IDs. Unknown or ambiguous IDs
fail before any workspace is created. The selected JSON view includes one
`rung`, its direct diagnostics and the report's snapshot/status metadata.

## Private saved runs

An explicit workspace creates a fresh `run-<UTC timestamp>-<random id>/`:

- `snapshot.L5X`: the exact bytes analyzed, copied without changing the input.
- `inventory.json`: the complete private inventory, even when `--rung-id` selects
  a narrower stdout view.
- `overview.txt`: the complete readable overview and gap list.
- `manifest.json`: snapshot identity, parser/schema versions, coverage status,
  artifact byte counts and SHA-256 hashes.

Existing runs are never reused or overwritten. Files are exclusively created
and flushed before the final manifest is atomically published. Readers must
ignore runs without `manifest.json`; an interrupted/failed run may leave files
and `.manifest.pending` but does not become a successful checkpoint. A saved
`partial` run is a finished inventory with explicitly incomplete coverage.
These checks do not promise durability against every power-loss/filesystem case.

Destinations inside this development checkout must resolve beneath
`confidential/`. Other explicit private locations are supported, including paths
with spaces. Resolved workspace/run containment checks reject symlink escapes
and artifact collisions. This is a local, single-owner workspace; it is not a
security boundary against concurrent hostile filesystem modification. A
packaged installation without a checkout relies on the user-selected private
destination. Shell redirection is outside the command's destination checks.

Git does not back up ignored private workspaces. Retain the whole run directory
in an approved backup location to preserve relative artifact links. This slice
does not implement editable records, correction overlays, handoffs or backups.

## Coverage and exit status

| Exit | Meaning |
| --- | --- |
| 0 | Structural report completed within this reader's scope |
| 1 | Read, validation, selection or save failure |
| 2 | Invalid command-line arguments |
| 3 | Report produced with partial structural coverage |

Parsed syntax does not establish engineering purpose. SFC/other unsupported
content and opaque regions are preserved in the snapshot and reported as gaps.
The separate `references` command adds bounded root binding; `inspect` remains
structural. Alarm shutdown analysis, PID relationships, equipment/sequence
classification, PCSD and FHX generation are not implemented.
Instruction subtotals cover only parsed rungs; inspect coverage before using
them as source-wide totals. The synthetic fixture includes unsupported SFC and
therefore intentionally returns exit 3.

## Tests

Run from the repository root:

```bash
uv run --project python-parser python -m unittest discover -s python-parser/tests -v
uv run --project python-parser python -m unittest discover -s tools/l5x_inspect/tests -v
```

Tests use invented data or the reviewed public fixtures. The private workspace
tests use temporary directories; no proprietary source is required.
