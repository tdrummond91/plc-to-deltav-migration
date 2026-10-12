Read public/CODEX_HANDOFF.md and
public/docs/reviews/STAGE_5_CODE_REVIEW.md.

Then read the 2026-10-12 scope in public/docs/planning/DECISIONS.md,
ROADMAP.md, ARCHITECTURE.md and DATA_CONTRACTS.md. The five product phases
are distinct from the completed helper stages and earlier technical milestones.
PCSD means Process Control Strategy Document. The current priority is L5X
understanding that feeds both reading/scanning reports and editable engineering
records. Detailed PCSD design follows source discovery. Editor/storage/packaging
choices remain proposals; do not treat them as implemented capabilities.

Use public/fixtures/minimized_review/controller_demo.L5X as the
current structural example. Its companion minimized-report.json
provides coverage and source mappings.

For implementation/review involving helper behavior, run the existing tests:
uv run --project python-parser python -B -m unittest discover \
  -s tools/l5x_inspect/tests -v

Expected baseline: 130 passing tests.
This baseline and the minimized_review public audit passed locally on 2026-10-12.
For documentation-only changes, review the diff and links; do not describe an old
test run as fresh execution.

Summarize the current architecture, implemented capabilities,
limitations, and propose the next bounded development milestone.
Wait for agreement before implementing that milestone.

Keep parsing and analysis reusable by both CLI and a future GUI.
Preserve source mappings and account for unsupported content.
Do not access confidential/ or begin DeltaV conversion.

Tyler uses a second ChatGPT chat for independent review. For each change, record:

- the baseline and tested commit, affected files and concrete behavior;
- rationale and alternatives, distinguishing user decisions from proposals;
- exact validation commands/results and remaining limitations;
- unresolved evidence and a bounded next step.

Use useful code comments/docstrings and focused conventional commits on branches
ending in -pc for this machine. Do not publish proprietary data in review notes.
Slow work-machine feedback may call for up to three experiment branches from a
common parent, using the same test/report contract. Label each result with its
tested revision and keep outputs separate. Choose experiments deliberately;
do not create three alternatives for every change.

Pay particular attention to decision survival across reruns, source-to-target
identity, partial coverage, and source-derived versus engineer-designed strategy.
The minimized fixture is a structural sample; use independently coherent
synthetic inputs to validate relationships it no longer preserves.
