# Confidential data, synthetic examples, and Git

Status: updated 2026-10-15 with Tyler's targeted-sampling clarification. Aggregate summaries and bounded diagnostic examples are implemented; general data exchange/editing remains planned. No audit of the old repository's history is claimed.

## Confirmed confidentiality boundary

2026-10-15 clarification: Tyler authorizes small, targeted source-derived pulls
for cases where the parser needs more information or the result does not make
sense. This is standing authorization to investigate within the boundary below;
do not impose a new approval request for each small diagnostic case. Selection
should follow parser evidence and avoid accumulating enough connected logic to
reconstruct the unit.

Tyler confirmed that the 2% limit counts **new informative examples**, separately
from the older scrubbed structural catalogs. Work28's first fixed request selects
at most six whole-rung examples and conservatively reserves two units for the
older operand clues. It removes names/values, preserves local syntax/relationships,
and can retain one bounded unknown instruction mnemonic as a diagnostic clue.
Existing report history and a local reservation freeze the selected record across
reruns, including changed exports. No automatic next request or dependency
expansion is allowed. See [the targeted-sample contract](../reviews/TARGETED_RUNG_SAMPLES_REVIEW.md).

Tyler defines confidential material here as information that enables rebuilding
the entire unit with data values, or provides more than 2% rung knowledge.
Aggregate counts and technical codes without individual rung logic or process
values are approved for repository sync. Do not impose a separate sharing
approval step on `plc summarize` reports solely because they came from a real L5X.
On 2026-10-14 Tyler explicitly authorized one actual mystery-operand occurrence
for parser investigation. Work-check schema 2 can include at most one printable
operand of 128 characters with its standard instruction and argument position.
It may retain a real name/value inside that operand; it does not include a full
rung, neighboring logic, source IDs/paths or other engineering values. This is a
specific bounded diagnostic exception, not a general raw-export permission.
Standalone source/reference summaries remain count-only. See the
[sample contract](../reviews/BOUNDED_OPERAND_SAMPLE_REVIEW.md).

Full exports and detailed inventories remain private. The targeted sampler has
its own new-information accounting; the standalone aggregate exporter exposes no
samples and does not certify the 2% threshold for other artifacts.

## Current layout and output boundary

Keep the existing layout:
```text
repository/
  confidential/
    plc-code/
    <existing DeltaV backup folder>/
    workspaces/                    new processing results go here
  public/                        synthetic input, docs, generic tools
  python-parser/
```

There is no need to rename or unpack the existing target backup for this plan. Paths are configuration, not hardcoded in source.

Full source exports, detailed source inventories and engineering state that meet the boundary above remain inside `confidential/`. Bounded aggregate summaries belong in `public/inspection/` for sync. Software and generic tooling remain portable.

Private application workspaces resolve paths and restrict locations inside this checkout to confidential/. Validated aggregate summaries may also be saved under public/inspection/. Explicit external locations remain supported. Shared synthetic examples use an explicit development workflow. These are local single-owner checks, not a security boundary against hostile concurrent filesystem changes; shell redirection is outside them.

## Git ignore rules

Keep the user's single plant-data boundary:
```gitignore
confidential/
```

The root `.gitignore` also excludes ordinary Python caches, virtual environments, build artifacts, and local credential files. Those entries are software hygiene, not additional plant-data locations. It intentionally does not ignore all JSON/CSV/XML because schemas and independently synthetic fixtures must remain trackable.

The root and nested ignore files both apply. uv.lock, source code, tests, generic rules, and synthetic documentation are tracked; do not reintroduce a uv.lock ignore rule.

Git ignore rules do not remove files that are already tracked or erase older commits. A file renamed into `confidential/` can still have a prior committed version. See the [Git ignore documentation](https://git-scm.com/docs/gitignore).

## Read-only checks before a cloud push

Run from the repository root in Git Bash:

```bash
# Should print nothing: tracked files still beneath confidential/.
git ls-files -- confidential/

# Should print nothing: tracked files now matched by ignore rules.
git ls-files -ci --exclude-standard

# Confirm that a hypothetical new file matches the confidential rule.
git check-ignore -v --no-index confidential/__ignore_probe__.txt

# Review historical paths from before/after the move.
git log --all --format= --name-only -- confidential/ plc-code/ 'DeltaV_System-*'

# Review all historical tracked filenames for unexpected sensitive locations.
git log --all --format= --name-only | sort -u

# Review what would be committed.
git diff --cached --name-status
```

The ignore probe does not create a file. Empty historical results for selected paths do not prove other paths or code contents are safe. Inspect staged content locally as appropriate.

The chosen clean-repository workflow is documented in [GIT_FRESH_START.md](GIT_FRESH_START.md). Run history checks in the old repository if needed; the new empty repository has no history until its first commit. If confidential history is found in the original, do not transfer or push it. This handoff does not run history rewriting or recommend force-pushing. Remote state and past cloud exposure are unknown.

The pasted directory listing contains large loose Git objects. That is a reason to audit; it does not identify their contents or prove sensitive data was committed.

## Public code and fixtures

Default tracked areas:
- Python implementation and generic instruction catalogs;
- documentation and schemas with invented examples;
- independently synthetic L5X fixtures and expected outputs;
- tests and dependency lock files.

Do not put actual tag names, plant descriptions, IPs, source paths, credentials, schedules, export fragments, equipment topology, or private hashes in code, documentation or synthetic fixtures. Authorized work-check diagnostic fields under `public/inspection/` are bounded exceptions: historical single operands and current targeted samples. Work28 disables new legacy single-operand selection so it cannot bypass the fixed sample budget. Tests that use real exports run locally under the confidential workspace and do not upload full reports to CI.

A future local pre-commit/publish checker should flag:
- files under confidential even if force-added;
- real-data exports or workbooks outside approved synthetic paths;
- hardcoded private paths/names in source or docs;
- credentials, addresses, opaque encoded payloads, and oversized unexpected artifacts;
- fixture files without a declared synthetic origin.

This is a review aid, not proof of confidentiality. Git ignore is not encryption, an access-control boundary, an AI-tool access policy, or a backup strategy.

## Sharing modes

Implemented aggregate feedback mode: `plc summarize` rebuilds a bounded fixed
schema from generated counters. It omits source IDs/hashes, paths, raw fields,
occurrence records and ladder topology; unknown instruction/language/diagnostic
labels become pooled withheld counts. Known labels use explicit publication
vocabularies. Tyler has authorized counts and global measurements for sync;
the generated JSON can go directly into public/inspection/.
The code commit in its metadata identifies software, not plant source data.
See [the work-machine procedure](../reviews/WORK_MACHINE_SUMMARY_RUN.md).

1. Schema-only inventory: element/attribute names, ordering, value kinds, and bounded shape examples. Omit literal values and counts unless needed and explicitly approved.
2. Tag-only sample: tags can still reveal the process. Use invented identifiers and minimal synthetic descriptions unless the actual naming pattern is approved for disclosure.
3. Pseudonymized structural slice: replace names consistently within a bounded sample, preserve only requested relationships, and keep the reverse mapping private.
4. Independently synthetic fixture: construct a small example from the grammar rather than exporting plant structure. Preferred for public tests and AI assistance.

Removing names alone does not hide plant logic. Branch topology, task rates, timer values, scaling, AOI bodies, module inventories, communications, and comments can reveal design. The user's standing authorization covers the bounded targeted sampler above; broader structural exports need a separate sharing decision.

## Redaction helper requirements

- An allowlist of fields and a maximum slice size.
- Token-aware identifier replacement across declarations, aliases, operand references, array members, AOI bindings, and selected interlinks.
- Preserve syntax validity and within-sample equality relationships without exposing original identifiers.
- Substitute typed dummy values and invented descriptions; remove real addresses, credentials, serials, comments, owner/export metadata, and hidden raw/decorated duplicate data.
- Default to removing unsupported/opaque/encoded sections, with a private omission report.
- No automatic full dependency closure: it could reconstruct a large part of a plant. Use selected bounded references or explicit external placeholders.
- Private mapping file separated from the sharing bundle. Use fresh per-bundle public IDs to limit correlation across releases.
- Reparse and validate the candidate, scan for known original tokens/literals, and compare the intended structural invariants.
- For broader exports outside the authorized targeted sampler, manual inspection of the exact candidate and a release manifest listing included files and remaining disclosure.
- Do not call it risk-free or guarantee anonymization.

The existing structural publication helpers and aggregate exporter have their
own limited policies. The general relationship-preserving redaction workflow
above is not implemented. For research, Tyler can supply independently dummy
data with a small wrapper showing scope and order. Do not request a full
confidential export in assistant context.

## AI translation data profile

An AI provider adapter requires an explicit profile: allowed field types, allowed context radius, provider/runtime, retention policy, credential source, and whether calls may leave the approved network. Actual model suggestions are stored locally with provenance.

Prefer the least context that resolves a phrase: text, datatype, generic role, and a minimal approved surrounding example. Full routine or plant context is not automatically authorized. Anonymized names do not make all context nonconfidential.

Manual questionnaire review is still needed for ambiguous acronyms, equipment roles, and local terminology. Only approved translations enter the reusable glossary.

## Backups

Ignored inputs and checkpoints will not travel with ordinary Git clones. Use the plant's approved private backup method. A portable workspace export contains source snapshots, manifests, decision batches, schemas, and artifact checksums; it stays confidential. Test restoration without the original absolute paths.
