# Confidential data, synthetic examples, and Git

Status: workflow proposal. The user has already moved the input folders under root `confidential/`. The user has copied files into a new project directory without .git; initialization is pending. Old repository history has not been audited.

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

All actual exports, working datasets, tag lists, glossary mappings, AI prompts/responses, checkpoints, reviewer spreadsheets, logs, and reports remain inside `confidential/`. This includes pseudonymized candidates until explicitly reviewed for sharing.

The application resolves the workspace's real path and refuses outputs outside it, including through symlinks or `..`. Shared synthetic examples use a separate explicit development path and are never generated automatically from production data.

## Git ignore proposal

Keep the user's single plant-data boundary:
```gitignore
confidential/
```

The supplied `.gitignore.proposed` adds ordinary Python caches, virtual environments, build artifacts, and local credential files. Those entries are software hygiene, not additional plant-data locations. It intentionally does not ignore all JSON/CSV/XML because schemas and independently synthetic fixtures must remain trackable.

The root and nested ignore files both apply. The current python-parser/.gitignore contains uv.lock; replace that rule before the fresh baseline. Keep uv.lock, source code, tests, generic rules, and synthetic documentation tracked.

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

Do not put actual tag names, plant descriptions, IPs, source paths, credentials, schedules, export fragments, equipment topology, or private hashes in these areas. Tests that use real exports run locally under the confidential workspace and never upload their reports to CI.

A future local pre-commit/publish checker should flag:
- files under confidential even if force-added;
- real-data exports or workbooks outside approved synthetic paths;
- hardcoded private paths/names in source or docs;
- credentials, addresses, opaque encoded payloads, and oversized unexpected artifacts;
- fixture files without a declared synthetic origin.

This is a review aid, not proof of confidentiality. Git ignore is not encryption, an access-control boundary, an AI-tool access policy, or a backup strategy.

## Sharing modes

1. Schema-only inventory: element/attribute names, ordering, value kinds, and bounded shape examples. Omit literal values and counts unless needed and explicitly approved.
2. Tag-only sample: tags can still reveal the process. Use invented identifiers and minimal synthetic descriptions unless the actual naming pattern is approved for disclosure.
3. Pseudonymized structural slice: replace names consistently within a bounded sample, preserve only requested relationships, and keep the reverse mapping private.
4. Independently synthetic fixture: construct a small example from the grammar rather than exporting plant structure. Preferred for public tests and AI assistance.

Removing names alone does not hide plant logic. Branch topology, task rates, timer values, scaling, AOI bodies, module inventories, communications, and comments can reveal design. A structural example is useful but still needs a human sharing decision.

## Redaction helper requirements

- An allowlist of fields and a maximum slice size.
- Token-aware identifier replacement across declarations, aliases, operand references, array members, AOI bindings, and selected interlinks.
- Preserve syntax validity and within-sample equality relationships without exposing original identifiers.
- Substitute typed dummy values and invented descriptions; remove real addresses, credentials, serials, comments, owner/export metadata, and hidden raw/decorated duplicate data.
- Default to removing unsupported/opaque/encoded sections, with a private omission report.
- No automatic full dependency closure: it could reconstruct a large part of a plant. Use selected bounded references or explicit external placeholders.
- Private mapping file separated from the sharing bundle. Use fresh per-bundle public IDs to limit correlation across releases.
- Reparse and validate the candidate, scan for known original tokens/literals, and compare the intended structural invariants.
- Manual inspection of the exact candidate and a release manifest listing included files and remaining disclosure.
- Do not call it risk-free or guarantee anonymization.

No redaction implementation exists yet. For initial research, Tyler can supply independently dummy data with a small wrapper showing scope and order. Do not request a full confidential export in assistant context.

## AI translation data profile

An AI provider adapter requires an explicit profile: allowed field types, allowed context radius, provider/runtime, retention policy, credential source, and whether calls may leave the approved network. Actual model suggestions are stored locally with provenance.

Prefer the least context that resolves a phrase: text, datatype, generic role, and a minimal approved surrounding example. Full routine or plant context is not automatically authorized. Anonymized names do not make all context nonconfidential.

Manual questionnaire review is still needed for ambiguous acronyms, equipment roles, and local terminology. Only approved translations enter the reusable glossary.

## Backups

Ignored inputs and checkpoints will not travel with ordinary Git clones. Use the plant's approved private backup method. A portable workspace export contains source snapshots, manifests, decision batches, schemas, and artifact checksums; it stays confidential. Test restoration without the original absolute paths.
