# Stage 3 validation

Date: 2026-10-09.

The combined suite completed with **58 tests passed**: 19 structure-count tests,
16 full-skeleton tests, and 23 value-profile tests. Tests used invented XML in
memory and mocked filesystem publication. Python ran with -B; no repository
files, Git state, confidential inputs, or caches were written by Codex.

The profile tests cover:
- per-path occurrence, exact distinct-string, missing-attribute and withheld counts;
- lexical type versus same-element declared PLC datatype;
- keeping inherited datatype resolution explicitly unimplemented;
- technical value permissions and private/custom value omission;
- private names, descriptions, dates, constants, code and comments not entering JSON;
- empty CDATA, direct versus descendant text, and container whitespace;
- low-cardinality heuristics not authorizing value disclosure;
- routine locators, missing/unknown types, content gaps and mismatches;
- SFC transition ST content not being counted as a standalone ST routine;
- documented special Data formats;
- namespaces, DTD/malformed input, memory limits, and no output on parse failure.

Original source not read by Codex. Actual Stage 3 execution, report inspection,
real filesystem writes, and the observed 70-routine/69-content-block explanation
remain pending Tyler's local run.

Stage 2 status: Tyler reported "no errors" on 2026-10-09. The exact PASS output and
full skeleton have not been supplied for inspection; no independent visual review
or source-count audit is claimed.

The existing Stage 1 and Stage 2 Python files and their tests are unchanged in
this handoff. Only the new profiler/tests and documentation need copying.
