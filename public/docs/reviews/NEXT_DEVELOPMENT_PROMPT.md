Read public/CODEX_HANDOFF.md and
public/docs/reviews/STAGE_5_CODE_REVIEW.md.

Use public/fixtures/minimized_review/controller_demo.L5X as the
current structural example. Its companion minimized-report.json
provides coverage and source mappings.

Run the existing tests first:
uv run --project python-parser python -B -m unittest discover \
  -s tools/l5x_inspect/tests -v

Expected baseline: 130 passing tests.

Summarize the current architecture, implemented capabilities,
limitations, and propose the next bounded development milestone.
Wait for agreement before implementing that milestone.

Keep parsing and analysis reusable by both CLI and a future GUI.
Preserve source mappings and account for unsupported content.
Do not access confidential/ or begin DeltaV conversion.
