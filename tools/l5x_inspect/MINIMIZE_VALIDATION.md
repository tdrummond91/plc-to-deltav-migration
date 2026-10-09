# Stage 5 validation

Validated 2026-10-09 in the task artifact directory.

## Unit tests

The combined suite passed: **118 tests in 0.116 seconds, OK**, exit code 0.
It contains the 94 unchanged Stage 1-4 tests and 24 new Stage 5 tests.

Tests use invented in-memory XML and mocked publication. They do not create
temporary files, caches or Git metadata. Python ran with -B using the existing
local project interpreter. CLI --help also completed with exit code 0.

Coverage includes technical-literal retention, dummy substitution, masked
datatypes/opcodes, whole-reference labels, rare late variants, consecutive run
ordering, sample limits/count equations, tall/wide rung selection, complete
selected rung subtrees, rung metric preservation, separate per-rung operands,
payload/ST/mixed-text handling, CDATA, omitted comments/PIs/namespaces, ordinal
provenance, repeatability, output hashing, fatal/no-publication paths,
same-input/output rejection, and program/AOI ladders.

## Full public skeleton audit

The read-only audit verified the actual public xml-skeleton.XML against
xml-structure-counts.json using the Stage 2 verifier:

- 83,942 elements; 213,876 attributes; 194 distinct paths; depth 14.
- 18,351 elements with CDATA.
- Zero nonblank attribute values and zero elements with nonblank text.
- Complete structure/count comparison succeeded after allowing removed text.

This upgrades Stage 2 from a user-reported successful run to an independently
inspected full blank skeleton. The confidential original was not opened.

## Approved public-sample integration

A separate read-only check built an in-memory demonstration from the 19 saved
sanitized Stage 4 examples plus a masked-opcode shape (20 input rungs).
With per-variant 1, the generator selected 16 rungs. The resulting in-memory XML
was reparsed by the Stage 4 inventory.

It retained the source report's maxima:
- branch depth 4;
- largest branch 49 legs;
- height 59 lanes;
- width 18 instruction boxes.

The masked instruction was retained once. The check passed with exit code 0.
No output files were written and no confidential input was opened. These inputs
reuse authorized public layouts; they are not independently invented layouts.

PowerShell emitted its known InitializeDefaultDrives startup warning before the
successful Python commands. It was not a Python failure.

## Validation boundaries

The generator has not been run by Codex against the confidential source. Real
retained counts, output size and field-policy coverage remain pending Tyler's
first local run and subsequent public-output inspection.

PASS checks structural output and accounting. It does not establish Studio
import validity, semantic/reference coherence, complete SFC/ST coverage,
execution equivalence or conversion correctness. Placeholder substitution
does not constitute a general confidentiality certification.

The two output files are individually atomic, not a single atomic transaction.
The report's output_sha256 identifies the generated XML; verify that pair after
any publication error before using a report left from an older attempt.

## Next check

Tyler copies only the new addition, runs the combined tests and the helper,
then returns the console summary. Inspect both public outputs before expanding
the replacement policy or changing sampling.
