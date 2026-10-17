# Work-check timing and sequence alias diagnostics

## Returned evidence

Return `d9df280` tested clean `0ee009a`: 1,426 application cases passed with two
expected Windows skips, plus 139 helper cases. The private analysis saved.
All twenty preceding summaries agree after revision normalization, all 44
historical reports validate and the frozen six-example envelope is identical.

Of 271 sequence reference occurrences, 267 have qualified exact-address
context and four have alias-chain binding gaps. The 167 distinct addresses
include 93 with captured ladder uses. The 39 bound step candidates comprise
32 same-content and seven peer-chart relationships. The gaps have no Boolean
spelling, outside-scope declaration or lexical-step hints. These are source
relationships, not proof of runtime sequence behavior.

## Why measure runtime

The user reported a longer work check. Earlier reports contain no elapsed
durations, so they cannot distinguish test cost from analysis or saving cost.
Each run executes the selected tests and analysis pipeline again; the previous
bundle did not contain a one-time migration or setup stage.

Read-only profiling on the public invented SFC context fixture confirmed
repeated canonical validation: one `_analyze` call invoked `analyze_snapshot`
77 times, `analyze_references` 118 times, `analyze_conditions` 27 times and
`analyze_relationships` 33 times. Initial companion construction, private
review saving and summary publication each authenticate their dependencies.
The small-fixture profiled run took 5.232 seconds, including profiler overhead
and excluding tests. This is evidence of repeated work, not a work-PC duration
or a production speed estimate.

Work38 records monotonic elapsed milliseconds for six fixed phases:

| Phase | Includes |
| --- | --- |
| Application tests | Selected parser tests and their runner process |
| Helper tests | Selected helper tests and their runner process |
| Analysis build | Source capture, inventory and derived analysis companions |
| Private save | Validation, report rendering, artifact writes and manifest |
| Summary build | Closed public summaries and their validation |
| Sample replay | Existing durable sample reservation; selection only under the unchanged policy |

Completion times print in the console and are included in the public report.
An attempted failing phase retains its duration; an unattempted phase is null.
Total elapsed time begins at Python workflow entry and stops before feedback
rendering, publication and the local Git commit. It excludes the earlier `uv`
bootstrap. Each duration is an integer between zero and 31 days in milliseconds;
the nonoverlapping phase sum cannot exceed total elapsed time. Only fixed
labels and numbers are published, with no source paths or user-defined labels.

Validation safeguards remain in place. A later optimization should use measured
work-PC costs and preserve forged-input and mutation rejection. Global caching
of mutable result objects is not an acceptable shortcut.

## Alias diagnostics

SFC context summary2 preserves the original coverage and adds closed counts for
binding reasons, alias-gap occurrences, distinct terminal aliases and existing
rack-match evidence. Counting distinct terminal aliases distinguishes repeated
uses of one failed alias from separate failing declarations.

Rack hints are reused from the authenticated reference model, keyed by the
original alias declaration. A hint is counted only when the failing terminal
root and declaration lookup scope agree. Missing, ambiguous, unavailable and
outside-scope candidates remain separate. Unique candidates have direction
counts and a distinct-candidate count; repeated references do not imply new
physical channels.

These are the existing lexical rack hints. Module/port namespace provenance is
not requalified here, so even a unique hint is not qualified I/O evidence. It
does not resolve the alias, validate its member suffix, establish a backing
mapping or prove a runtime value. Namespace-excluded alias references are not
eligible for rack matching. No source strings, names or additional examples
are exported.

## Contracts and next run

Work38 adds timing1 and requires SFC context summary2. Its outer cap remains
80 KiB. The new summary cap is 5 KiB; historical summary1 retains its 4 KiB cap
and work37 remains readable. Private context1, review20, manifest23 and the
sixteen private artifacts are unchanged. Historical notes remain available.

On the work machine, run the usual commands from the repository:

```bash
git pull
bash ./run-work-check.sh
git push
```

The script creates only its local feedback commit. The listener remains
disabled; no fetch, pull or push was added to the script. No new source samples
or manual engineering/team review are requested. The next return should tell
us which phase takes the time and whether the four alias gaps have existing
rack hints or another failure reason. Phase 1 interpretation continues from
that evidence before correction workflows, PCSD or FHX generation.

## Verification

The focused summary suite passed 19 cases (twelve new); eleven timing cases
passed. An independent reviewer found no blockers and additionally rejected
three forged canonical dependencies: rack terminal root, candidate direction
and SFC binding identity. Synthetic cases cover shared terminal aliases,
distinct input/output candidates, scope shadowing, outside-controller hints,
namespace exclusions, unsupported addresses, cycles and closed count schemas.
The mocked publication/commit timing assertion remains development-only. The
ten selected timing cases load through the production allowlist without
importing the excluded Git workflow test module.

The conservative maximum-width work38 probe is 80,204 bytes under 81,920;
summary2 is 4,134 bytes under 5,120. No private source strings are added to the
shared report.

The actual Bash launcher passed 1,448 selected application cases (two expected
Windows skips) and 139 helpers, then saved its private analysis and one local
feedback commit. Git tracing recorded no network operations. The measured
synthetic run spent 363.937 seconds on application tests, 0.510 on helper tests,
0.348 on analysis construction, 0.558 on private saving, 0.417 on summaries and
0.184 on sample replay. Total elapsed time through report assembly was 366.126
seconds. The tiny invented source is not a performance proxy for the work L5X.

The final report was 49,114 bytes. All sixteen manifest hashes were checked;
all sixteen artifacts, including HTML, matched the previous code byte for byte.
Manifest metadata agreed apart from run ID and creation time. Fresh direct
analysis and the CLI produced the same artifacts; the CLI retained its expected
partial-analysis exit code 3. Twenty prior summaries and context1 coverage were
unchanged after revision normalization, and all 44 historical reports plus the
new invented report validated. Existing example HTML remained exact CLI output.

The 74 final development cases passed. The additional process/socket guard
passed over both selected suites before one mocked workflow test was relocated
out of the work-machine selection; the final selection is a subset of that
passing guard run. The relocated assertion passed in the development suite, and
the ten remaining timing tests independently passed through the production
loader in a fresh process. This covers 1,662 distinct cases, counting the guard
once and not counting its nested selected tests again. Independent review found
no remaining blockers. The final runtime, assets and test files match the
isolated verification copy; the listener was excluded before discovery.
