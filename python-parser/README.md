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
now participate in root lookup. Explicit names or conservative ICP/Ethernet
module/port topology supply the name; private symbols retain `name_origin` and
`name_reason`. Missing or ambiguous topology leaves an unnamed declaration.
RackConnection mappings remain unsupported and explicitly diagnosed. These gaps
do not establish that the source project has an invalid tag.

Private inventory schema 2 (`source-inventory-2`) adds module ports, ordinary
connections and input/output/configuration tag records without changing ordinary
tag/alias totals. Reference schema 2 (`source-references-2`) adds those three I/O
symbol kinds and a fixed `reason` on unresolved/unsupported-address bindings.
Reasons distinguish missing declared roots, qualified or dynamic addresses and
other bounded syntax gaps; they do not claim to identify every gap's engineering
cause. Raw declarations remain separate from inferred names.

Both text and JSON reports are private. The workspace option creates a NEW run
containing the existing snapshot/inventory/overview, plus `references.json` and
`references.txt`. Its schema-2 `source_reference_run` manifest records artifact
hashes, versions, limits of analysis and combined partial status. The existing
`inspect` run manifest remains schema 1. Old runs and inputs are never overwritten.

For portable feedback, run:

```bash
uv run --project python-parser plc reference-summary "confidential/plc-code/unit.L5X" \
  --output "public/inspection/reference-summary-001.json"
```

This approved aggregate includes fixed symbol-kind, alias/operand status and
reason counts, module naming origins/unavailable reasons, analysis coverage and
a nested schema-3 `source_summary`. Code provenance is
`source_summary.tool_revision`. It contains no names, values, source identities
or individual reference links. Its report kind is `l5x_reference_review_summary`,
schema 3, policy 2, exporter `reference-summary-3`, analyzer `source-references-2`.
`operands.malformed_address_shapes` partitions only malformed-address occurrences
into seven fixed observational buckets, including a separate alias-target bucket.
The diagnostic does not change address recognition or binding. See the
[address-shape contract](../public/docs/reviews/ADDRESS_SHAPE_REVIEW.md).
The validator also accepts reference schema 1/source schema 2 and reference
schema 2/source schema 3; mixed version combinations are rejected.
The publisher accepts only the source, reference and work-check aggregate schemas and validates again
before writing. New filename, location, 32-KiB limit and no-overwrite rules apply.

Exit 3 means useful partial results were produced. Reference analysis can be
partial even when the structural inventory is complete. Exit 0 means this bounded
root-binding scope completed; it never means all engineering behavior is understood.
See [validation and exact scope](../public/docs/reviews/MODULE_IO_REVIEW.md)
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

New summaries use schema 3, policy 2 and exporter `aggregate-summary-3`, built from
the source-inventory-2 contract. Counts now include module ports, ordinary
connections and input/output/configuration tags. The validator retains support
for the previous schema-2 source aggregate and rejects mixed version fields.
A complete validated report is capped at 32 KiB.
All counts are strict nonnegative integers and reconcile across groups. Output
cardinality does not grow with unrecognized source labels. The code revision
comes from this application's checkout, with a clean/modified/unavailable flag;
it is not a source-data fingerprint. Modified includes tracked or untracked
application sources/build metadata; docs and plant inputs are excluded. The
command never accesses a network for revision collection.

Policy 2 records `sharing_status=aggregate_sync_allowed` without a review warning.
Existing v1 aggregate reports remain suitable for sync under Tyler's
clarification; they do not require a fresh source run. Their old status string
records the previous policy. They remain historical feedback rather than a
directly accepted input to the current validator.

Exit codes match `inspect`: 0 structural completion, 3 partial coverage with a
usable candidate, 1 failure, 2 usage. Parsed syntax is not understood engineering
purpose. See [the work-machine procedure](../public/docs/reviews/WORK_MACHINE_SUMMARY_RUN.md)
for checkout, testing, generation and the exact artifact to return.

## Local work-machine feedback

The development listener remains disabled and paused. Its files and test loader
are ignored local development tools and are not included in normal checkouts.
Manual parser checks are independent of that service. Update or clone the code manually, then
run from the repository root in Git Bash:

```bash
bash ./run-work-check.sh YOUR_READABLE_EXPORT.L5X
# Later runs in this checkout remember the source path:
bash ./run-work-check.sh
```

The launcher uses the code already checked out on a
clean named branch, including `main`. It never fetches, pulls, stages, commits or pushes,
and does not require an upstream branch. Code updates are a separate manual
action. The first run accepts a source filename/path; later runs reuse the
selection saved in this checkout's Git metadata.

The application and helper checks use explicit module allowlists in fresh
processes. Work-machine checks exclude listener, Windows process-host, Bash
bootstrap and Git-fixture tests. Full unittest discovery remains available for
development validation; its test totals must not be compared as if it had the
same scope as the work-machine checks.

Successful tests enable a single captured-source inventory/reference analysis
and a new private workspace. A closed aggregate includes test counts, bounded
code-only failing test IDs, the tested commit and the nested reference summary.
It is saved to Git-ignored `public/inspection/local/work-check-<run-id>.json`.
Failed tests also produce a local report and skip source analysis. Useful partial
analysis exits 0; test or analysis failure exits 1 after saving the report.
Preflight or save failures stop without claiming completion.

The outer report remains schema 1 and carries reference schema 3 with source
schema 3 when analysis succeeds. Existing reports remain readable. The tested
SHA identifies the implementation and therefore its suite scope; historical
reports may include the broader development suites. The latest work-machine
aggregate returned in `b58af78` and awaits parser analysis; a rerun is not needed
just to obtain its address-shape counters.

Review the local aggregate before sharing. Manually copy or move only that JSON
into `public/inspection/`, then explicitly stage, commit and push it when ready.
Raw logs, full results, source and older outputs stay under `confidential/` and
must not be included. Read the [work-machine procedure](../public/docs/reviews/WORK_MACHINE_REFERENCES_RUN.md)
for output locations and the [implementation review](../public/docs/reviews/WORK_CHECK_RUNNER_REVIEW.md)
for the bounded report contract. This runs the implemented Phase 1 tools; it does
not generate engineering classifications, PCSD or FHX.

## Run individual commands from Git Bash

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
