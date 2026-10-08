# Codex handoff — PLC analysis workbench

Planning revision: 0.2, 2026-10-08.
State: planning and independently synthetic fixture prepared. No application refactor, package installation, repository edits, Git updates, or plant-data processing was performed for this handoff.

## Goal and user instructions

Build an iterative tool for investigating Allen-Bradley L5X exports. It needs a useful CLI now and reusable services for a future GUI. Eventually it may help convert selected logic to DeltaV FHX, but the target transformation design has not been selected.

The user wants exact, bounded changes and an explanation whenever new syntax or tools are introduced. Avoid large shell-editing scripts when a clear replacement block is sufficient. Show named objects and traceable connections in diagrams.

Read the current host's AGENTS instructions first. The work machine is read-only for Codex, except for designated temporary handoff artifacts. On an editing-capable host, implement the selected slice directly and run its checks. Do not reinterpret the work profile as permission to write or execute tests in the live repository.

Read these documents in order:
1. `docs/planning/DECISIONS.md` and `docs/planning/L5X_STRUCTURE.md`
2. `docs/planning/ARCHITECTURE.md`
3. `docs/planning/DATA_CONTRACTS.md`
4. `docs/planning/ROADMAP.md`
5. `docs/planning/CONFIDENTIALITY.md`
6. `docs/planning/CLI_AND_REVIEW.md`

## Current prototype

The inspected project has:
- Root `confidential/plc-code/` containing user-maintained L5X exports.
- The existing DeltaV reference folder is also beneath `confidential/` (preserve its name).
- `python-parser/main.py`, `pyproject.toml`, `uv.lock`, and an empty Python README.
- The user moved both input folders during planning and now has a root ignore file containing `confidential/`.
- The new project copy contains confidential/, public/, python-parser/, and .gitignore. No .git directory was present when this copy was inspected.
- The user completed the copy to the new project name after a Windows rename failed; the original remains available. No byte-for-byte comparison was performed by Codex.
- This handoff supplies a root README, a root handoff pointer, and canonical public documentation.

The current script mixes:
- XML inventory and name search;
- basic ladder tokenization and branch indentation;
- `l5x.Project` tag access;
- argparse argument handling and printing.

Preserve the successful behaviors while extracting modules. Inspect the current file before changing it; the user has edited it repeatedly. The earlier branch formatter is a prototype, not a validated ladder grammar or renderer.

The dependency file lists Python >=3.12 plus third-party `argparse`, `pathlib`, and `l5x`. The first two are in the Python standard library and should be removed from dependencies during the authorized packaging slice. Preserve `uv.lock` and update it using uv as part of that slice. The inspected nested python-parser/.gitignore ignores uv.lock; remove that rule using the supplied replacement before the fresh baseline. Avoid importing the L5X file at module import time.

## Confirmed decisions

- Ladder is the first detailed analysis target.
- The main inventory must still count SFC and other routine types, tags by scope, tasks, I/O modules, rungs, and JMP/other instructions where parsed.
- Machine-readable JSON drives reports and future GUI views.
- All real inputs and derived results belong beneath root `confidential/`.
- `public/` contains only independently synthetic fixtures, portable docs, examples, and generic support tools; application code remains in python-parser/.
- Create and check the independently synthetic L5X before extracting the application modules.
- Use fresh Git history in the new project copy and link a new empty GitHub repository after local review.
- AI-assisted French interpretation is desired, including Quebec shorthand. Suggestions require evidence, an uncertainty estimate if available, an explicit unresolved state, and a bilingual human review record.
- Every processing stage accounts for what it parsed, preserved without understanding, deliberately excluded, and failed to process.
- Every derived result must trace back to source occurrences.
- Checkpoints and reviewer round trips must survive interruptions and later software versions.
- No PLC runtime changes, downloads, or FHX conversion implementation are part of the first milestones.

## Current first slice and next implementation

The public fixture, expected inventory, branch reference, origin manifest, and read-only Python checker are supplied under public/fixtures/synthetic and public/tools. Run the checker and inspect its results before modifying parser behavior. Then implement Milestone 1 from ROADMAP within the current host authorization:
- establish `src/plc_workbench/` and a thin CLI;
- implement input snapshot identity and a versioned JSON inventory;
- include a clear coverage report, source locators, routine-language counts, and unknowns;
- provide `--help` and synthetic fixtures;
- keep all output in `confidential/workspaces/<case_id>/artifacts/<run_id>/`.

Milestone 0 creates the synthetic baseline and verifies the fresh repository. The user has completed the confidential layout and the new project copy; do not move those inputs again. Follow docs/planning/GIT_FRESH_START.md. Read the latest root and nested ignore files before applying replacements.

Do not pre-create a large plugin framework or empty module tree. Add files as the corresponding milestone is implemented.

## Boundaries that must survive implementation

1. Domain records do not contain XML Element objects, l5x package objects, GUI widgets, or open file handles.
2. Analysis returns typed results; it does not print or access the network.
3. Readers own source parsing. Services orchestrate work. Presenters own CLI, JSON report views, ASCII, and later workbooks/GUI.
4. Original exports remain immutable. Translations and classifications are overlays.
5. A source hierarchy is not an execution graph. Preserve scan order and cross-references.
6. Unsupported content is explicit and recoverable from the preserved original.
7. Pattern grouping is not proof of behavioral equivalence.
8. A rule confidence score is not automatically a statistical probability.
9. Forward and reverse traceability use explicit many-to-many links, not reversed dictionaries.
10. Public tests and documentation contain only independently synthetic data.
11. Do not load confidential payloads into assistant context by default. Use local helpers to produce bounded, reviewed structural or independently synthetic examples. Never send real code to external services without a configured, user-approved data scope.

## Validation status

- Planning decisions checked against the user's requests.
- Repository layout, ignore file, dependency file, and prototype source inspected read-only.
- Original confidential exports were not read for this planning task.
- The new copy was inspected read-only and had no .git directory. New Git initialization, staging, commits, and remote linkage remain user actions. Old history and any remote were not audited.
- Tyler ran uv sync and uv run python -B ../public/tools/check_fixture.py --with-l5x on 2026-10-08. His terminal reported PASS for fixture hash, XML, counts, scopes, schedules, and l5x tag access. This is user-reported execution evidence; Codex did not execute the command. See VALIDATION.md.
- No application tests or Studio 5000/DeltaV runtime checks were executed.
- Handoff JSON and document links are checked separately; that does not validate the proposed application.

## How to update this handoff

After each implementation slice, replace the status below with:
- completed slice and code changes;
- commands executed and actual test results;
- fixture/schema/rule versions;
- unresolved findings and known unsupported syntax;
- new decisions and next bounded slice.

Keep plant names, actual tags, source paths, exported code, raw error payloads, and confidential hashes out of this file. Put private run details in `confidential/`.

### Progress ledger

| Slice | State | Evidence |
|---|---|---|
| Planning | Draft ready for discussion | Architecture, contracts, CLI proposal, roadmap, confidentiality plan |
| Confidential layout / fresh repository | User copied to new project; Git setup pending | No .git in inspected new copy; ignore replacements supplied |
| Synthetic fixture | User-run Python check passed, including l5x tag access | Terminal output supplied 2026-10-08; Studio 5000 import remains unverified |
| Package extraction / inventory | Not implemented | Existing prototype remains |
| Parser / renderer / graphs | Not implemented | Contracts and synthetic test cases proposed |
| AI translation / reviewer import | Not implemented | Provider and data policy not selected |
| DeltaV mapping / output | Deferred | Target semantics not designed |

## Unresolved choices

- Approved AI provider/runtime and precisely what private context it may receive.
- Which reviewer workbook layout is easiest for the Quebec team.
- Which secondary routine language is next after the initial ladder slice.
- Rules for grouping multiple controller exports into a case and confirming remote endpoints.
- DeltaV library/version, module classes, target execution behavior, and acceptance tests; all deferred until source analysis is dependable.
