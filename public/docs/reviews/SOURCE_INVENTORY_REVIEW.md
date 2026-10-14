# First source-inventory implementation review

Date: 2026-10-12. Branch: `feat/source-inventory-pc`, based on documentation
checkpoint `3cfdb57`. Tested implementation: `f9f61bc`
(`feat(inventory): add snapshot-bound L5X source inspection`). All work is local;
no push, merge, confidential input access or real-export validation is reported.

## Problem and implemented behavior

The earlier prototype and scrubbed helpers could inspect files, but did not
provide one reusable private source inventory with exact evidence for subsequent
analysis. `plc inspect FILE` now captures the input once and uses those bytes for
all analysis and optional saved evidence. A changing input path cannot silently
switch the analyzed revision after capture.

- Versioned dataclasses represent scoped declarations, routine/rung coverage,
  ordered instruction/branch structure, raw operands and character spans.
- IDs bind kind and occurrence location to one captured byte snapshot. Duplicate
  names or identical rungs stay distinct. Changed snapshots intentionally get new
  IDs; stable engineering identities and reviewed correspondence are later work.
- JSON and readable overview/selected-rung views use the same records. Counts
  cover only successfully parsed outer ladder syntax, with explicit incomplete
  coverage for other routine languages, missing content and encoded regions.
- Optional `--workspace` writes a fresh private run: exact snapshot, complete
  JSON, text overview and artifact hashes in a manifest published last. Existing
  runs are not overwritten. A failed save never publishes a final manifest.
- The existing ladder grammar is shared from `plc_workbench.ladder.syntax` with
  the helper compatibility shim. It adds instruction spans and total allocation
  limits for empty branch legs and argument slots. The application does not
  import the tools directory. Direct helper execution still works from the repo.
- Packaging installs the `plc` command, removes obsolete argparse/pathlib
  backports and retains l5x for the original prototype/fixture checker.

The source adapter is deliberately structural. Entity attributes, schedules,
aliases and operands retain source facts without claiming resolved relationships
or validated instruction effects. Parent roles restrict declarations to supported
containers; unfamiliar XML stays preserved and visible as unmodeled paths.

## Independent review and fixes

Separate agents implemented shared grammar and CLI/storage, while another agent
reviewed the integration and challenged coverage. Confirmed findings were fixed:

1. Familiar Tag/Routine names inside arbitrary extensions no longer become
   declarations. Their rung text is preserved without being counted as parsed.
2. Unknown executable children or direct text under RLL routines/content/rungs
   prevent a complete instruction-count claim.
3. Duplicate or nested descriptions/comments produce linked ambiguity findings
   rather than silently appearing absent.
4. Storage rejects noncanonical snapshot IDs even when inventory metadata agrees
   with the same fabricated ID; tests use the real snapshot factory.

Regression tests reproduced these failures before the fixes. The reviewer then
reran independent bounded probes and found no remaining blocker in the fixes.
The reviewer also verified serialization at the permitted 64 branch-depth limit.

## Validation actually run

Run from the repository root in Git Bash:

```bash
uv run --project python-parser python -B -m unittest discover -s python-parser/tests -v
uv run --project python-parser python -B -m unittest discover -s tools/l5x_inspect/tests -v
uv run --project python-parser python -B tools/l5x_inspect/check_public_outputs.py --repo . --fixture-name minimized_review
uv run --project python-parser python -B public/tools/check_fixture.py --with-l5x
uv run --project python-parser plc inspect --help
git diff --check
```

- Application suite: 30 tests run, 29 passed, one skipped because this Windows
  account cannot create symlinks. No failures. Storage tests cover exact snapshot
  hashes, failed publication, collisions, separate reruns and output containment;
  the real symlink test remains unverified on this machine.
- Helper suite: all 139 tests passed, including nine new grammar regressions.
- Public minimized audit: PASS, with 7,303 source links, 276 rung records,
  194 paths, 431 variants, 19 ranked samples and 42 instruction labels checked;
  zero attribute-policy findings and no output files written.
- Synthetic checker: PASS for hash, counts, scopes, schedules and l5x tag access.
- Installed `plc.exe` was also executed from an unrelated temporary working
  directory against absolute paths to both public fixtures, using `--format
  json`. Stdout parsed as JSON, stderr was empty and no implicit files appeared.

| Input | Tags | Routines | Parsed rungs | Instructions | Result |
|---|---:|---:|---:|---:|---|
| Independently authored synthetic | 15 | 4 | 9 / 9 | 25 | Partial, exit 3: one SFC routine |
| Reviewed minimized structural fixture | 146 | 39 | 276 / 276 | 1,904 | Partial, exit 3: ten unsupported routines and one missing RLL content block |

These are counts of the fixtures, not the full original source. The minimized
sample's per-rung ARG identities do not establish cross-rung relationships.

## Limits and next bounded step

No source symbols/aliases or read/write effects are resolved. Alarm shutdowns,
control loops, equipment, sequences and engineering classifications remain
uninterpreted. Unknown mnemonics may parse successfully because this grammar
describes outer instruction syntax, not instruction validity. The resource
ceilings are explicit (64 MiB input, XML depth 128, 500,000 elements), not a
performance guarantee for every permitted input.

Private outputs contain names, operands, comments and snapshot hashes. They are
not approved public summaries and must not be returned to a reviewing chat as
though scrubbed. No work-machine action is necessary for this checkpoint.

Recommended next slice: a separately specified, bounded summary export from this
inventory, with tests proving which fields may leave the private workspace and
versioned results suitable for a work-machine comparison. Reuse the established
public policies where appropriate; do not export raw IDs/hashes, labels or source
paths by accident. Then add scoped symbols/aliases and instruction-reference
evidence against independently coherent synthetic fixtures before engineering
classification. A generic summary exporter must not be mistaken for permission
to publish a complete reconstruction of the source.

The editor/database, downstream correction overlays, PCSD schema, packaging for
non-programmers and FHX adapters remain separate milestones. Keeping source IDs
distinct from future engineering-object IDs preserves the design space for
sequential review and reconciliation of changed, split or combined objects.
