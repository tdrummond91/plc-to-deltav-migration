# Bounded source reuse during work checks

## Returned evidence

Return `0b5a9d9` tested clean `51202a8`: 1,448 application cases passed with
two expected Windows skips, plus 139 helpers. The private analysis saved.
All twenty earlier summaries and the SFC context coverage agree with the
previous return after revision normalization. The frozen six-example envelope
is unchanged; all 45 historical reports validate.

The first measured work run took 643,635 ms (10 minutes 44 seconds):

| Stage | Milliseconds | Approximate duration |
| --- | ---: | --- |
| Application tests | 217,884 | 3:38 |
| Helper tests | 313 | Less than one second |
| Analysis build | 129,098 | 2:09 |
| Private save | 161,724 | 2:42 |
| Summary build | 133,995 | 2:14 |
| Sample replay | 116 | Less than one second |

Private saving includes validation and report rendering, so its duration does
not establish a disk bottleneck. Repeated source analysis contributes to all
three expensive analysis stages. The source inventory reports 83,942 XML
elements, 6,307 tags and 4,606 rungs. No source byte-size estimate is inferred
from those counts.

All four unresolved SFC references have `colon_root_not_declared` failures.
They trace through two distinct terminal aliases and two unique lexical
rack-input candidates. These candidates do not establish qualified I/O
bindings; the four references remain unresolved. Further spelling samples
are unnecessary for this checkpoint.

## Reuse boundary

The work-check analysis invocation retains protected templates for its XML
nodes and canonical inventory. Every caller receives independent mutable
containers, including on the first request. Snapshot byte, hash, ID and size
checks run before inventory reuse. Cache keys include exact source bytes and
the applicable XML and rung-parser budgets. Policy changes cannot reuse an
earlier result under different limits. Only built-in immutable bytes are
eligible for reuse; subclasses and other accepted buffer inputs follow the
ordinary parser so custom equality cannot substitute a different source.

The scope has a 128 MiB retained-object budget. It prefers the smaller inventory
template when both cannot fit. Inputs that cannot be retained use the ordinary
parser; they are neither truncated nor rejected because the cache is full.
The ceiling applies to retained templates and keys, not total process memory
or transient parsing/copy allocations. XML/build exceptions are not cached;
valid partial inventories retain their existing failed-rung diagnostics under
the applicable parser policy. Scope exit, including exceptions, releases
retained objects; nested scopes restore their parent. There is no persistent
cache or cross-run reuse.

Derived models still undergo their canonical comparisons. Mutating an earlier
inventory cannot poison the protected copy or make a forged dependent model
pass validation. The normal CLI remains uncached as an independent comparison
path. The selected work-machine tests retain their normal validation behavior.

Work38, timing1, SFC context summary2, review20 and manifest23 remain unchanged.
The sixteen saved artifacts, frozen sample reservation, manual Git transport
and disabled listener retain their existing contracts. No new plant excerpts
are requested or exported.

## Performance evidence and next run

The implemented optimization was compared with frozen baseline `0b5a9d9`
using two invented inputs. The moderate case fell from 7.557 to 6.292 seconds;
the larger 1,026,408-byte case fell from 66.74 to 55.75 seconds, about 16.5%.
XML parses fell from 159 to one and canonical inventory builds from 77 to one.
Both analysis dictionaries, all sixteen artifact hashes and normalized
manifests matched. These are individual development-PC measurements, not a
prediction of the work-PC improvement. Existing timing fields will measure
the effect on the private source.

Run the ordinary commands from the repository on the work machine:

```bash
git pull
bash ./run-work-check.sh
git push
```

The script creates only its local feedback commit. Compare the next return's
analysis, save and summary timings, as well as all summaries and the frozen
samples. Application-test time can still dominate smaller sources. This
remains Phase 1. Manual engineering/team review is deferred.

The next semantic bundle should capture source-declared execution context:
task/program membership and scheduling metadata, main/fault entry candidates,
qualified routine-call context and incoming call conditions. The return has
76 JSR occurrences across 68 candidate edges, eleven calls with additional
argument fields, and one RLL routine without content. Existing graph evidence
leaves execution, call validation and parameter roles unanalyzed.

That context precedes equipment/alarm grouping: 1,453 exact addresses have
multiple writers, including 1,126 Boolean addresses with multiple coils.
The 1,319 alarm candidates do not establish shutdown consequences. Preserve
missing bodies, cross-task ordering and runtime behavior as explicit
uncertainty; source context is not a controller simulator. This follows
[roadmap milestone 3](../planning/ROADMAP.md) and the
[Phase 1 completion gate](../planning/PHASE_1_ENGINEERING_ANALYSIS.md).

## Verification

The 21 new reuse cases pass through the fresh production loader with process
creation and sockets blocked and the excluded workflow test module absent.
They cover mutable result isolation on misses and hits, forged snapshots,
changed XML/rung policies, alternate sources, capacity fallback, inventory
priority, rejection markers and nested/exception scope cleanup. A hostile
bytes-subclass equality probe exposed a cache-key bug during review; the
built-in-bytes guard fixes it, and the regression also checks mutable buffers
and preservation of the original cache entry. Independent review confirmed
the corrected behavior and found no remaining blockers.

The actual Bash launcher in an isolated invented checkout passed 1,469
application cases (two expected Windows skips) and 139 helpers. It saved the
private run, validated its work38 feedback and made exactly one local report
commit. Git tracing found no network operations. The 76 development workflow
cases passed, including canonical rejection of altered inventory before save
and scope release on failure. These suites cover 1,684 distinct cases; the
focused/guard reruns are not counted again. The ignored listener was excluded
before discovery. An earlier full run was stopped after the final key fix;
the final launcher run used the corrected frozen files.

All sixteen private artifact hashes were verified, and all sixteen files,
including review HTML, match baseline `0b5a9d9` byte for byte. Normalized
manifests and all 21 summaries match. Fresh direct analysis and the uncached
CLI produce the same artifacts; the CLI preserves partial-analysis exit code
3. Canonical review replay passed for two saved runs, all 45 historical reports
plus the new invented report validate, and existing example HTML remains exact
CLI output. Final runtime, assets and tests match the isolated verification
copy. The frozen sample reservation and historical report bytes are unchanged.
