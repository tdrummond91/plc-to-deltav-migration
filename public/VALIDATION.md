# Artifact validation record

Prepared: 2026-10-08, planning revision 0.2.

## Current relationship checkpoint (2026-10-15)

See the [relationship validation record](docs/reviews/RELATIONSHIP_REVIEW.md)
for independent review, canonical artifact and summary comparisons, actual
isolated Bash runs, historical report replay, browser checks and scale evidence.
The latest real return `4a3406b` confirms the prior rung-analysis bundle with
778 application cases (one expected skip) and 139 helpers. Team review has not
started; the next run supplies automated relationship coverage.

## Historical rung-analysis checkpoint (2026-10-15)

The [rung-analysis validation record](docs/reviews/RUNG_ANALYSIS_REVIEW.md)
records the full development suite, independent review, final UI checks, two
actual isolated launcher runs, fourteen artifact hashes, legacy byte comparisons,
historical report replay and browser/scale checks. Work-machine pushes are
automated run results; team engineering feedback has not started. Follow the
[Phase 1 completion gate](docs/planning/PHASE_1_ENGINEERING_ANALYSIS.md) before
requesting that review.

## Completed checks

- Inspected the copied project's root and both ignore files read-only. Expected folders were present; no .git directory was present at that inspection.
- Constructed the small L5X independently, without reading a confidential source export.
- Checked XML token coverage, balanced element nesting, attribute syntax, root shape, and explicit element paths using a limited in-memory JavaScript inspection.
- Compared counts, scoped tag names, routine-language counts, instruction occurrences, and task schedules with the manually specified expected JSON.
- Verified the fixture SHA-256 against its origin record.
- Parsed supplied JSON examples.
- Checked local Markdown link targets and read back the generated artifacts.
- Searched public files for selected known private markers; none were found. This limited scan is not a comprehensive confidentiality guarantee.

Expected fixture counts: 1 controller, 1 mock module, 2 tasks, 2 programs, 1 user type, 15 tag definitions, 4 routines (3 RLL, 1 SFC), 9 rungs, 25 instruction occurrences.

## User-reported Python validation

On 2026-10-08, Tyler ran uv sync and then:

```bash
uv run python -B ../public/tools/check_fixture.py --with-l5x
```

His terminal reported:

```text
PASS: fixture hash, XML, counts, scopes, schedules and l5x tag access.
```

This confirms the delivered checker completed successfully in his environment. It does not establish full application parsing or vendor import compatibility. Codex inspected the supplied output; it did not independently run Python.

## Not performed

- Independent Python execution by Codex or broader application tests.
- General XML schema validation or Studio 5000 import validation.
- Application parser/renderer tests, analysis of real plant inputs, or GUI tests.
- PLC execution, safety/timing equivalence evaluation, or DeltaV validation.
- Byte-for-byte verification of Tyler's full project copy.
- Git initialization, staging, commits, remote fetches, or pushes.

The work-machine instructions permit only read-only project inspection and creation of handoff artifacts. All delivered Python commands are for Tyler to run. Static fixture checks are not evidence that the proposed modular application has been implemented or passes tests.

## Next evidence to record

The initial fixture check has passed as reported above. Next record the reviewed first-commit identifier and remote state after Tyler runs the Git steps. Then begin the small inventory/package milestone. Keep real-data errors and paths under confidential/.
