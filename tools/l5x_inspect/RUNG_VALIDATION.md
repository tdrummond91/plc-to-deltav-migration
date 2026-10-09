# Stage 4 validation

Validated 2026-10-09 in the task artifact directory.

## Checks performed

The combined suite passed: **94 tests in 0.074 seconds, OK**, exit code 0.
This comprises 58 unchanged Stage 1-3 tests and 36 new Stage 4 tests
(20 syntax tests and 16 inventory tests).

Command run against the handoff copy with the existing local Python interpreter:

```text
python.exe -B -m unittest discover -s tools/l5x_inspect/tests -p test_*.py -v
```

The CLI `inspect_rungs.py --help` also completed with exit code 0 and displayed
the input, output and sample-limit arguments. PowerShell emitted a startup
InitializeDefaultDrives warning before the successful Python commands; it was
not a Python test failure.

Tests use invented in-memory XML/rung strings and mocked output operations.
No confidential export was opened, no repository file was changed, no dependency
was installed, and no Git operation was performed.

## Coverage

- Series, parallel and nested branches; sequential branch groups; empty legs.
- Array indices, nested argument delimiters, quoted commas/brackets, escaped
  quotes, empty argument positions and terminal semicolons.
- Explicit syntax/resource-limit failures without raw source snippets.
- Structural height/width/depth, instruction counts and expression-call counts.
- Pattern grouping, tied rankings, sample selection and occurrence links.
- Known instruction labels, masked unlisted names, operand replacement and
  removal of test identifiers/constants from serialized reports.
- Program and AOI ladders, ignored SFC/ST content, source count reconciliation.
- Missing/multiple/nested Text elements and complete versus partial coverage.
- Same-input/output rejection, fatal errors without publication, and partial
  reports published through the existing output helper.

## Limits of this evidence

The actual Stage 4 input has not been run by Codex. Its 4,606 ladder rungs are
known from prior structural reports; their new parse coverage, instruction
counts, shape counts and maxima remain pending Tyler's run.

These tests do not establish Studio 5000 import validity, instruction semantics,
execution equivalence, general ASCII rendering or DeltaV conversion correctness.
Whole operands are opaque and replaced; their expression trees are not analyzed.

## Next validation

Copy the additions using COPY_AND_RUN.md. Run all tests, inspect CLI help, and
then run inspect_rungs.py against the original local export.

Review coverage first. If PARTIAL is printed, the saved JSON contains the
unparsed rung locations and error categories. Resolve those findings before
treating the ranked examples as complete or implementing the minimized L5X.
