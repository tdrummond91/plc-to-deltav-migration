# Bounded summary export review

## Policy correction, 2026-10-13

Tyler clarified that confidentiality means rebuilding the entire unit with data
values, or more than 2% rung knowledge. Count summaries contain no individual
rung logic or process values; they are authorized for direct repo sync. The
previous gate described below was unnecessarily restrictive for these reports.

Current exports use schema/policy 2, exporter aggregate-summary-2 and
sharing_status aggregate_sync_allowed. Public/inspection/ is an allowed summary
destination, and CLI save notices no longer request sharing review. The writer
now validates/canonicalizes the JSON independently of the CLI before publishing
into the synced tree; size and overwrite protections remain. Private source
inventory behavior is unchanged. Existing v1 reports need no source rerun.

Tests: 59 application tests run, 58 passed, one preexisting Windows symlink skip.
The new tests cover direct synced-folder publication and refusal of arbitrary
data/oversized reports. An independent reviewer passed all 25 summary tests and
confirmed hidden duplicate-key text is not written, with no blocking findings.
The helper code is unchanged; its last 139-test baseline remains recorded below.

## Original v1 implementation and evidence (historical)

Date: 2026-10-12. Branch: **feat/summary-export-pc**, based on **79d865f**.
Tested implementation: **ca9fcf8** (`feat(summary): add bounded L5X aggregate
review export`). The branch includes the preceding source-inventory work.
Tyler authorized implementation, tests and the GitHub branch push. This review
does not claim a real-export run or authorize a main merge.

## Behavior and rationale

The private `plc inspect` inventory contains source names, IDs, hashes, operands
and paths. Returning it for development would exceed the intended sharing scope.
`plc summarize FILE [--output NEW.json]` now captures/analyzes the source once
and rebuilds a bounded aggregate report from explicitly selected counters.

The report has a closed schema, not a copy of the private payload. It includes
component counts, routine/rung dispositions, approved routine languages and
instruction totals, global ladder measurements and diagnostic counts. Unknown
instruction/language/diagnostic names use pooled withheld buckets; no unknown
identity or source location is emitted. Missing Type is distinct from an actual
unlisted literal with the reader's internal missing-sentinel spelling.

Source attributes, text, names, descriptions, hashes, byte sizes, file/XML paths,
per-rung records, topology, IDs and mappings do not enter the report. Fixed
structural/semantic limitations and local-review-required status remain visible.
The report still reveals aggregate scale; local review decides whether the exact
candidate may be returned. This is not a general anonymization guarantee.

Policy/schema v1 accepts only source-inventory-1. The validator rejects additional
fields, arbitrary output labels, booleans/floats used as counts, impossible
parser measurements and inconsistent totals. Rendered JSON is capped at 32 KiB.
The number of output fields is bounded independently of the number of unknown
source labels. The approved instruction vocabulary is reused from the shared
grammar; no dependency on helper scripts was added to the application.

Local code provenance records HEAD plus clean/modified/unavailable state for
application sources and build/dependency metadata. Git reads are bounded,
network-free and anchored to the installed code checkout, never the L5X path.
Untrusted inherited Git environment is removed; Git failures disclose no paths
or diagnostics and produce unavailable provenance. This metadata identifies
software, not a plant-source revision.

An explicit new JSON destination is published with a same-directory temporary
file, flush/fsync and an atomic hard link that cannot overwrite an existing
destination. Existing files, symlinks, inputs and racing writers are preserved.
Unsupported hard-link filesystems fail without an overwrite fallback. Cleanup
failure can leave a .pending file; only the final JSON is a candidate. There is
no automatic upload and no saved raw inventory/source copy in summary mode.

## Review and validation

An explorer checked existing publication policies. A separate worker implemented
CLI/publication/provenance, while an independent reviewer challenged the summary
boundary. The reviewer found an error-channel issue: SourceError could include
arbitrary OS diagnostic text. Summary mode now emits a fixed source-failure
message; regression tests prove private error strings stay out of stderr.
Additional review probes led to rejecting impossible parser metrics and unknown
diagnostic severity combined with complete status. Final review found no
remaining blocker; all 23 summary-boundary/CLI/publication tests passed in the
independent review.

Commands run from the repository root in Git Bash:

```bash
uv run --project python-parser python -B -m unittest discover -s python-parser/tests
uv run --project python-parser python -B -m unittest discover -s tools/l5x_inspect/tests
uv run --project python-parser plc summarize public/fixtures/synthetic/controller_demo.L5X
git diff --check
```

- Application: **57 tests run, 56 passed, one skipped**, no failures. The skip is
  the preceding storage test requiring actual Windows symlink privileges.
- Helpers: **139 passed**. Shared grammar and existing helper behavior unchanged
  by this slice.
- Source sentinels in metadata, names, descriptions, aliases, operands, custom
  types/opcodes, comments, XML names/namespaces and diagnostics did not enter
  successful summaries. Source hashes and filenames were also absent.
- Private renaming and rung reordering produced identical aggregate output.
  Ten thousand distinct unknown opcodes pooled into one withheld count.
- Publication tests covered flush/link failure, existing input/output, a racing
  destination, extension/location checks and cleanup of owned temporary files.
- Provenance tests used an isolated synthetic Git repository for clean, staged,
  unstaged and untracked-code states, plus unavailable/wrong-root/changed-HEAD
  cases and sanitized subprocess execution.
- Installed `plc.exe` ran from an unrelated temporary directory against both
  public fixtures. Explicit output produced valid JSON and preserved input bytes.
  Repeated publication returned exit 1 and preserved the earlier output.
- After committing ca9fcf8, installed-command stdout checks on both fixtures
  reported that exact commit with clean code state, no stderr or implicit files.

| Fixture | Rungs | Instructions | Report bytes | Result |
|---|---:|---:|---:|---|
| Independently authored synthetic | 9 | 25 | 2,383 | Partial, exit 3: SFC is not interpreted |
| Reviewed minimized structural sample | 276 | 1,904 | 3,013 | Partial, exit 3: unsupported languages and missing RLL content |

The earlier pre-commit checks had three extra bytes because worktree was
`modified` instead of `clean`. These figures describe the public fixtures, not
the original private export. The committed
[synthetic example](../../examples/source-summary.synthetic.json) was generated
from the independently invented fixture at ca9fcf8 and validated before writing.

## Work-machine handoff

Use [WORK_MACHINE_SUMMARY_RUN.md](WORK_MACHINE_SUMMARY_RUN.md) for branch checkout,
tests, one version-labelled summary command, exit-code meanings and the artifact
to return. Tyler should review the candidate locally and return only that JSON
plus the test outcome. The full L5X and `plc inspect` output stay private.

Returned evidence will inform the next source-analysis slice. Scoped symbol/
alias and instruction-reference work remains a candidate; engineering
classifications, edit/correction persistence, standalone editor, PCSD and FHX are
not implemented by this change.
