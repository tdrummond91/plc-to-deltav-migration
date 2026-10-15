# Condition report save failure and diagnostics

## Returned evidence

Returned `e0b6b0c` tested clean `effa48f`. All 870 application cases passed,
with one expected Windows skip, and all 139 helpers passed. Analysis returned
`save_error`; every aggregate summary is null. All 31 historical reports validate.
This return supplies no condition coverage and is not engineering feedback.

The old runner reaches this stage after every analyzer has returned, but before
report preparation, publication and the saved-path console message finish.
Therefore the code does not identify the underlying failure, and its false
`private_run_saved` flag does not prove no finalized run exists: the flag was set
after printing. No private source or work-machine exception text was inspected.

## Bounded report allowance

Review9 adds a condition companion bounded to 32 MiB, while originally retaining
review3-8's combined 128 MiB JSON / 160 MiB HTML budgets. A previously admissible
report can therefore fail after adding conditions even when each companion
individually satisfies its limits.

Review9 now reserves that additional bounded companion allowance: 160 MiB JSON
and 192 MiB HTML. Review1-2 retain 64/80 MiB; review3-8 retain 128/160 MiB. The
condition artifact remains bounded to 32 MiB. No evidence is dropped or shortened
to fit, and report/manifest/condition schemas remain 9/12/1. This addresses a
reproducible size-budget problem; it is not confirmation of the private run's
cause. A normal work-machine rerun is needed to distinguish those outcomes.

## Safe failure categories

Work-check25 retains all work24 summary contracts and its 48 KiB envelope. Only
the closed failure vocabulary expands. Versions1-24 keep their old vocabulary.

| New failure code | Meaning |
|---|---|
| review_size_limit | Combined JSON, escaped payload or final HTML exceeded its versioned budget |
| review_validation_error | Canonical report construction or evidence validation was rejected |
| review_render_error | HTML rendering or bundled report resources failed |
| save_workspace_error | An explicit private workspace/path check was rejected |
| save_io_error | Saving encountered an operating-system filesystem error |

Unclassified save failures retain `save_error`. These codes contain no exception
messages, paths, source labels, values or traceback text. Only an exact internal
StorageError with a native-string allowlisted code can refine the save stage;
foreign exceptions and malformed codes cannot publish their attributes.
New save failures require passed tests, failed status, null summaries and an
unconfirmed save. A console failure after `save_run` returns now correctly keeps
`private_run_saved=True` and reports `unexpected_error`.

All validation/rendering still precedes run allocation. Files are created
exclusively, and the manifest is finalized last. Existing runs are not overwritten.
Git transport remains manual; the script commits only its new feedback locally.
The listener remains disabled.

## Validation

- Full development suite: 1,031 tests passed, with one expected Windows symlink
  skip. Listener tests were excluded before loading. Independent review found
  no blocking issues; all 19 new diagnostic and report/storage tests passed.
- Tests cover exact UTF-8 payload and final escaped HTML boundaries, unchanged
  earlier budgets, canonical validation versus rendering failures, malformed
  error-code objects, workspace rejection, filesystem failures without final
  manifests, and console failure after a completed save.
- Authentic invented size reproduction: 4,606 rungs, 17,874 instructions and
  48,400 stored-data elements. Review8 was 120,142,180 bytes and fit its original
  budget. Adding the bounded 20,041,879-byte condition artifact produced
  136,840,511 bytes of combined JSON: the original 128 MiB review9 budget rejected
  it. The new budget accepted it and generated 137,000,624 bytes of HTML. Chrome
  rendered the report, paged 5,625 output occurrences and opened individual
  condition details without horizontal overflow or report console errors.
  The browser automation's full snapshot hit its transport limit; scoped DOM
  observations and a screenshot verified the rendered page instead.
- Two actual isolated Bash launcher runs, using explicit then remembered invented
  source paths: 889 application cases and 139 helpers passed each time. Each run
  committed exactly one new validated work25 report locally. All sixteen private
  artifact hashes were verified; neither run performed any Git network operation.
- All sixteen artifact bytes match the preceding implementation on the same
  invented source, including HTML and conditions. Ten existing summaries match
  after revision normalization. The direct CLI and both runner outputs also match.
  All 31 historical reports plus both new synthetic reports validate unchanged.
  The 128 final runtime/test files match the tested isolated snapshot.

## Next work-machine return

Run the normal `git pull`, `bash ./run-work-check.sh`, and manual `git push`
workflow. A successful private run should return the missing condition summary;
otherwise the new fixed category will direct the next investigation. Do not
interpret this repair as new engineering classification coverage. Continue
Phase 1 automated analysis before requesting team review.
