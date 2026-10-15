# Static graph of declared JSR candidates

Implemented on `feat/bounded-operand-example-pc`, continuing Phase 1 source
understanding. This gives the reading/report path a routine-call map while
retaining snapshot-linked records for future engineering review.

## Returned metadata checkpoint

Commit `3431389` adds only
[work-check-20261015T005328Z-f9bff3e7.json](../../inspection/work-check-20261015T005328Z-f9bff3e7.json)
and has tested clean `5f91400` as parent. Work9/reference11/source4 validates;
335 application cases (one Windows symlink skip) and 139 helpers pass. All 76
unique JSR candidates belong to programs with an absent Type attribute; that
same bucket accounts for every unclassified target context. Call-weighted target
languages are RLL62 and SFC14. All earlier source/reference/candidate/shape,
alias/rack, flag and diagnostic counters are unchanged. Partial analysis,
private results saved and a null sample remain expected. This explains the
missing explicit-Normal context without establishing a missing-Type default.

## Scope and interpretation

The graph contains consistently owned program routine declarations, including
isolated declarations and non-RLL envelopes. Only parsed RLL JSRs with unique
program-local candidates create edges. Repeated calls between the same caller
and target collapse into one edge retaining their instruction evidence IDs.
Nonunique candidates stay outside the edge list with their evidence retained.
No tag namespace fallback, parameter interpretation or cross-program edge is
introduced. Existing binding, catalog and candidate counts remain unchanged.

Explicit MainRoutineName attributes are matched independently of Program.Type,
using program-local ASCII static identifiers and case-insensitive lookup.
Absent, empty, unsupported names, missing/ambiguous declarations and unique
matches remain separate. This records designation metadata, not a scheduled or
executed entry point. Names such as MainRoutine do not supply a designation.

Iterative strongly connected components identify candidate graph cycles,
including self edges. The implementation avoids recursive traversal and external
graph dependencies. A cycle describes declared call relationships; it does not
prove legal recursion, runtime execution, loop count or reachability. Conditional
ladder paths, disabled programs, tasks and parameter roles remain unmodeled.

Nodes retain observed rung dispositions and narrow structural body status.
Known RLL content errors or unparsed owned rungs mark structural gaps; a valid
empty RLLContent differs from missing content. A partly parsed routine can still
contribute edges from its parsed rungs. Non-RLL bodies stay language_unmodeled.
SFC nodes with zero observed outgoing edges must not be called execution leaves:
their body calls and transitions have not been parsed. Structural parsing also
does not establish instruction semantics or valid controller behavior.

## Contracts and publication

Private references advance to schema6 / source-references-9 with a required
routine_graph object. Nodes, grouped edges, explicit main-designation evidence,
excluded instruction IDs and cyclic components are snapshot-bound private data.
The graph uses existing source IDs; it does not create persistent engineering
identities. Canonical private validation reanalyzes the full result, including
the graph, before storage or public aggregation. New runs preserve previous
outputs. The existing references command and work runner save the graph in
references.json and present a labeled call map in references.txt.

Public reference12 / reference-summary-12 adds only fixed graph metadata and
closed counts: nodes by language/body status, programs/main-designation statuses,
linked/unlinked calls, grouped/repeated/self edges, candidate-cycle components,
nodes and edges, and participating/isolated nodes. It publishes no node names,
source IDs, edges, component memberships or designation strings. Counts
reconcile to existing candidate totals and source declarations; graph bounds
reject impossible aggregates. Analyzer9 records the new derivation, while all
earlier classification results remain intact.

Graph budgets are 100,000 nodes, 100,000 grouped edges, 250,000 call occurrences,
8,000,000 retained string-value characters and 65,536 characters per raw main
designation. Fixed errors include no source-controlled details. Edge bounds use
nonself directed pairs plus actual self pairs; cyclic nodes require RLL callers,
and cyclic edges obey the same directed-pair capacity. Unique/ambiguous main
matches consume disjoint program-owned declarations. Body counts fit source
dispositions, and target-language/distinct-target capacity fits graph nodes,
excluding AOI-only declarations. Partitions and bounds remain count checks, not
an attempt to reconstruct shared topology.

Reference11 is frozen as analyzer8 and rejects even an all-zero graph field.
Earlier reference fields and vocabularies remain unchanged. Work10 / work-check-10
requires reference12; work9/reference11 and earlier exact pairings stay readable.
Private inventory3, public source4 and reference-run manifest2 retain their
layouts. Sharing rules, output paths, local report commits and manual pull/push
remain unchanged. Only count reports are synchronized through the normal runner.

## Next real report

The next normal run should preserve every earlier counter, including 76 unique
calls, 66 distinct targets, 76 absent program-Type observations and RLL62/SFC14
target-language occurrences. Linked graph calls should be 76 and unlinked calls
zero. Grouped edges, callers, isolated nodes, main-designation matches, structural
body coverage and candidate-cycle counts remain unknown until the report returns.
Use these to focus later body/control-flow analysis. No repeated metadata-only
check is needed. Partial remains expected. See
[the normal run procedure](WORK_MACHINE_REFERENCES_RUN.md).

## Validation

Full development validation passes **450 cases with one existing Windows symlink
skip**; 199 related regression cases also pass. Fifteen new core graph cases
cover namespace/ownership, grouped evidence, isolated declarations, designation
states, missing versus empty bodies, partly parsed RLL, unmodeled/protected
envelopes, cycles, a 1,200-node traversal, exact resource budgets and canonical
tampering. Four additional public cases cover frozen reference11, privacy and
coherent invalid aggregates. Independent review passes 37 focused cases, rejects
its three reproduced impossible summaries after fixes, and checks 150 generated
mixed-language/multi-program summaries. SCC membership matches an independent
reachability oracle on 1,800 small graphs. No remaining blockers were found.

All 15 stored work reports validate unchanged. All 73 relative Markdown links in
changed documentation resolve and git diff --check passes.

The full development command excludes the ignored listener loader:

```bash
uv run --project python-parser --locked python -B - <<'PY'
from pathlib import Path
import sys, unittest
folder = Path.cwd() / 'python-parser/tests'
sys.path.insert(0, str(folder))
suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(p.stem)
    for p in sorted(folder.glob('test_*.py')) if p.stem != 'test_feedback_listener')
result = unittest.TextTestRunner().run(suite)
raise SystemExit(not result.wasSuccessful())
PY
```

All development fixtures are invented; no project confidential input or listener
is used.

An independent workflow agent runs the actual launcher twice from a final-byte
disposable clean checkout without remotes, using an explicit invented source
and then the remembered source. Each passes **354 application cases (one skip)
and 139 helpers**. Its graph has eight nodes, nine grouped edges, ten linked/two
unlinked call occurrences, one repeated pair and one self pair, two cyclic
components with three cyclic nodes/internal edges, seven participating nodes and
one isolated node. Absent-Type main designation resolves; missing/malformed RLL
remains partial and SFC remains unmodeled.

Work10/reference12/source4 reports and inventory3/reference6/manifest2/analyzer9
private artifacts verify. Direct CLI text/JSON return expected partial exit3;
JSON exactly equals saved canonical references, while text labels all nodes,
edges/provenance, main matches and cycles. Compared with clean baseline
`3431389` on the same fixture, inventory is identical and every prior private/
public field matches after excluding the new graph and version/revision metadata.
Both local report-only commits cite tested parents and leave clean checkouts.
Input, previous-run artifacts and manifest hashes are unchanged. Git traces
contain no fetch/pull/push, and all copied root code/test/config hashes match the
final tested bytes. Preliminary runs before strengthened public bounds are not
the final workflow evidence described here.
