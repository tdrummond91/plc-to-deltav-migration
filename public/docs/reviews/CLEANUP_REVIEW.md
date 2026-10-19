# C15 maintainability and review confirmation

## Scope

After C14 passed, Tyler requested one code/folder cleanup and one further
work-machine run before official review. This maintenance pass retains the
verified analysis baseline: work53, review35, manifest38, all private artifact
paths, current commands and the frozen sample budget. It introduces no new
source interpretation rule and does not restart the completed R3/R4 analysis
investigations.

Current entrypoints now explain what to run, where reports live and where to
find code. Complete earlier entrypoint documents are preserved under
`public/docs/history/2026-10-19-pre-cleanup/`, with an index and preservation
manifest. Detailed review notes, source fixtures and feedback reports stay at
their existing paths. Historical checkpoints remain available without being
mixed into the current run instructions.

The code cleanup places work-report size and serialization policy in the leaf
`plc_workbench/contracts/work_reports.py` module. The workflow, publisher and
sample-history reader share that policy. Existing work-check constants and
helper entrypoints remain compatible, including patched-cap behavior in tests.
Closed validators, per-version raw-byte limits, canonical rendering, no-clobber
publication and fail-closed sample history retain their behavior.

The **Unresolved analysis** binding description now separates original binding
evidence from qualified rack source correspondence. The two current invented
demonstration reports are refreshed with unchanged embedded evidence. Physical
wiring and runtime behavior remain unproven by source identity.

## Local validation

The focused contract/publication/history selection passes 46 cases with one
expected Windows symlink skip, with subprocess and socket creation denied.
The nine new cases cover version-era caps, patched compatibility aliases,
finite serialization versions, strict publication discriminators, raw padding
and pre-parse error ordering. The audited work-PC selection includes them.

All 61 published work reports, covering schemas 1-53, pass their original raw
size limits, closed validation and byte-exact canonical replay. Nineteen
development UI cases pass for residual navigation, rack groups and control
interpretation. Both refreshed demos retain identical embedded evidence; their
changes are the corrected sentence and its script-integrity hash.

All six archived entrypoints reconstruct the original working-copy bytes and
match the pre-cleanup Git revision after newline normalization. Only the 315
relative Markdown destinations were rebased; prose and code examples are
preserved. CLI command/help checks match the new current instructions.
All 630 local links and heading anchors across the 22 changed/new Markdown
files resolve. The retained standalone prototype is explicitly labeled so it
is distinguishable from the supported package entrypoint.

Sixty additional development workflow/driver cases pass under process/socket
denial. Eight temporary-local-Git fixtures also pass with their intended process
support. An initial development harness incorrectly denied those eight Git
setups; rerunning that exact class with local Git enabled resolved all eight
without a product change. These development fixtures are outside the audited
work-PC parser selection.

Independent production review found no blocking issue. The complete audited
selection passes 2,112 application cases (two expected Windows symlink skips)
and 139 helper cases, with zero failures or errors. Subprocess and socket
creation were denied throughout both suites; no external calls occurred.

## Verified C15 work-machine return

Return `d53e1ee` contains
[`work-check-20261019T185822Z-acde7c64.json`](../../inspection/work-check-20261019T185822Z-acde7c64.json),
testing cleanup commit `4c5386c50e7e441fa1df4c21182c1fe5c445031b` with a clean
worktree. Both suites passed: 2,112 application cases with two expected skips,
139 helpers, zero failures/errors. The private run saved with no failure code.
The returned report is 88,955 bytes within the work53 limit of 144 KiB.

Post-return audit validated all 62 historical reports, covering schemas 1-53,
against their own raw-byte limits and closed validators, then reproduced every
report's canonical bytes exactly. The current history reader accepts the full
history and returns the same established frozen record. Process and socket
creation were denied during this audit.

All **29 analysis summary families** equal the accepted C14 return `adc5475`
after excluding only `tool_revision` fields. The complete targeted-sample and
diagnostic envelopes also match, with six charged examples, eight reserved
units and cap forty. No new plant example was released.

Grouping remains 55,230 memberships / 7,580 groups, including 1,029
rack-qualified memberships. Signal/SFC assembly exclusions remain zero, scans
remain complete, and two dynamic calculation destinations plus one dynamic
file address retain their explicit exclusions. Analysis remains `partial` and
engineering decisions `unreviewed`; the existing source/vendor/runtime questions
are unchanged. This is successful maintenance validation.

| Phase | C14 milliseconds | C15 milliseconds |
|---|---:|---:|
| Application tests | 1,565,147 | 423,888 |
| Helper tests | 378 | 352 |
| Analysis build | 215,113 | 213,556 |
| Private save | 240,197 | 237,555 |
| Summary build | 211,942 | 210,255 |
| Sample replay | 196 | 205 |
| Total | 2,233,553 | 1,086,389 |

C15 took 18m 06.389s, compared with C14's 37m 13.553s. Application tests account
for 1,141,259 ms of the 1,147,164 ms reduction; the other phases together account
for 5,905 ms. These timings do not isolate machine load or another cause, so
the reduction is not attributed to the cleanup. No timing rerun is needed.

## Next action

C15 is complete. No further unchanged-source work-PC run is planned before
official review. Open the existing private report from this run for
readability/appearance checks and official engineering review using the
[reading guide](REPORT_REVIEW_GUIDE.md). Missing source, vendor/exporter
semantics and runtime/engineering questions remain in the
[C14 readiness assessment](PHASE_1_READINESS_REVIEW.md).

The full private report was generated on the work PC; this return provides
bounded validation and aggregate evidence, not a new visual inspection of that
private HTML. Tyler's walkthrough confirms its usability on the actual source.
This closeout changes documentation only and does not require rebuilding it.
