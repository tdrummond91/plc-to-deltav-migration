# Rack declarations and candidate diagnostics

Implemented 2026-10-14 on `feat/bounded-operand-example-pc`, after investigation
baseline `825afd0`. This remains Phase 1 source understanding. Work-machine
validation of this slice is confirmed by `9597f18`, testing clean `9d159e0`.
The preceding report `1195d40`, testing `112ee82`, had 99 unresolved aliases and 320 unresolved
operand occurrences, all `colon_root_not_declared`. It does not establish how
many correspond to rack declarations.

Returned result: 220 application cases (one skip) and 139 helpers passed. All
15 rack candidates are named; all 99 unresolved aliases and 319 alias-mediated
operand occurrences have unique candidates. One direct operand has no candidate.
Ordinary bindings are unchanged. See [UNMATCHED_OPERAND_REVIEW.md](UNMATCHED_OPERAND_REVIEW.md)
for exact reconciliation and the implemented one-address follow-up. The original
implementation/validation evidence below remains intact; its pending-run language
is superseded by this returned checkpoint.

## Behavior and boundary

The source reader now captures `RackConnection`, `InAliasTag` and `OutAliasTag`
in their exact supported module/communications/connection containers. Records
keep snapshot-bound IDs, XML locators, raw attributes and parent/scope links.
Names are optional. Ordinary connections, I/O symbols and tag/alias counts are
unchanged. Each modeled rack connection retains a backing-not-analyzed warning.
Unexpected text/children produce a diagnostic on the affected rack record;
unsupported contexts remain unmodeled evidence.

Candidate naming reuses the checked module topology. This initial slice accepts
attribute-free rack declarations with no unsupported content and an ICP first
edge, deriving only the individual `Location:Slot:I/O` root. Attributes, direct
Ethernet naming, unexpected content, incomplete/ambiguous parents or unsupported
ports stay unavailable with a fixed reason. It does not infer adapter members,
channel layouts, data types, runtime effects or a universal hardware-family map.
The official-format evidence and alternatives remain in
[RACK_IO_INVESTIGATION.md](RACK_IO_INVESTIGATION.md).

Rack candidates are separate from ordinary reference symbols. In particular,
they never turn an unresolved alias into a terminal `root_bound` symbol. The
private `rack_candidates` section compares only unresolved colon roots, using
the final failed alias target and its declaration scope when a chain is present.
Program lookup can see its controller; controller/AOI isolation is preserved.
Aliases, direct operand occurrences and alias-mediated operand occurrences are
three separate populations. Counts must not be added as distinct plant objects.

Match precedence is:

1. One visible exact named candidate: `unique_candidate`.
2. Multiple visible exact named candidates: `ambiguous_candidate`.
3. No visible named match, but visible unnamed declarations:
   `candidate_names_unavailable` (inconclusive, not evidence of a relationship).
4. No visible unnamed declaration, but an exact name in another scope:
   `outside_visible_scope`.
5. Otherwise: `no_candidate_match`.

Private rows preserve the missing root, scope and occurrence ID. A unique match
also preserves its candidate ID; other statuses do not copy lists of matching
IDs. `candidate_count` counts visible exact candidates, visible unnamed candidates
for the inconclusive status, or exact candidates elsewhere for the outside-scope
status. The implementation indexes candidates once and limits all retained new
evidence strings, including repeated IDs, to 8M characters. Existing topology,
operand and source limits still apply. Failures use fixed messages.

## Contracts and sharing

| Artifact | Current contract |
|---|---|
| Private inventory | schema 3, `source-inventory-3` |
| Private references | schema 3, `source-references-4` |
| Public source aggregate | schema 4, `aggregate-summary-4` |
| Public reference aggregate | schema 5, `reference-summary-5` |
| Work-check envelope | schema 2, `work-check-2` |
| Private reference-run manifest | schema 2; parser/analyzer metadata updated |

Source aggregates add three rack declaration counts. Reference aggregates add
only closed `rack_candidates` counts: declaration direction, name origins,
unavailable reasons and match statuses for the three populations. There are no
names, source IDs, lookup roots, topology or per-occurrence links in that section.
Private JSON/text retain those details for work-machine review. The existing
separate one-operand work-check sample has not expanded.

All counters use bounded integers, reject booleans/unknown keys and reconcile
with source declarations and unresolved-reference denominators. The mandatory
backing warning count equals captured rack connections; warning severity cannot
be relabeled to manufacture a complete result. Each positive alias-mediated
match status also requires that status among alias records. Canonical
reanalyzing of the captured inventory rejects forged private candidate records
before aggregation or saving. Exact historical source schemas 2/3 and reference
schemas 1/2/3/4 remain readable; mixed contracts are rejected. New private records
are not an editable-import format or a migration of old private runs.

## Validation and next evidence

The invented rack fixture now captures one rack connection and two rack aliases.
Both candidate roots are named; its one unresolved alias, two direct operands
and one alias-mediated operand each have a unique candidate. Ordinary bindings
remain two bound and three unresolved operands, with one unresolved alias.
Ordinary module counts and original source bytes are preserved; status remains
partial because backing relationships have not been analyzed.

Automated coverage exercises XML context/content, duplicates, scope isolation,
terminal alias scope, collisions with ordinary declarations, incomplete topology,
unsupported attributes/ports, budgets, strict aggregation, privacy under renaming,
private persistence, historical reports and timer-sample compatibility.

Final local validation after review fixes: 316 application/workflow tests passed
with one existing Windows symlink-capability skip, excluding the ignored listener
loader. The 43 new rack tests run without process/network fixtures. Independent
review verified the two additional aggregate invariants above and found no
remaining blockers; its final focused run passed 76 tests. All seven stored
work-check reports and nine standalone historical source summaries remain valid.
Whitespace and local documentation-link checks passed.

Actual workflow validation used a disposable synthetic-only Git checkout with
an unreachable origin. Explicit-source and remembered-source runs both succeeded;
after all review fixes, a refreshed final-code run passed 220 selected application
cases (one skip) and all 139 helpers. Invocation was the checkout's actual
`python -B -m plc_workbench.work_check`, first with the invented fixture path and
then without a source argument. Git Trace2 showed only local operations, with no
fetch/pull/push/clone/ls-remote attempts. Each run committed only its new report,
whose tested revision was the commit's parent, and left a clean checkout.
Saved snapshots, private artifact hashes, prior reports and source bytes were
verified. Final temporary tested commit was
`0bac9dbaa46b7dc01bc933dd4fba0afc9bd7050e`; its report-only commit was
`7d422b02863469a08d4f0606171a42e47d036aab`. These are disposable validation commits,
not remote project revisions. Final Python source/tests matched the development
files byte-for-byte. No plant input, listener or scheduled task was used.

Reproduce the full development suite from the repository root without importing
the optional ignored listener tests:

```bash
uv run --project python-parser --locked python -B - <<'PY'
from pathlib import Path
import sys, unittest
folder = Path.cwd() / 'python-parser/tests'
sys.path.insert(0, str(folder))
loader = unittest.TestLoader()
suite = unittest.TestSuite(loader.loadTestsFromName(p.stem)
    for p in sorted(folder.glob('test_*.py')) if p.stem != 'test_feedback_listener')
result = unittest.TextTestRunner(verbosity=1).run(suite)
raise SystemExit(not result.wasSuccessful())
PY
```

The next work-machine run measures whether the real missing roots have supported
rack candidates. Compare the three match populations and unavailable reasons,
while expecting the ordinary 99/320 unresolved totals to remain unchanged for
an unchanged export. Do not predict all of them will match. Return only the
automatically committed work-check report using the manual push procedure in
[WORK_MACHINE_REFERENCES_RUN.md](WORK_MACHINE_REFERENCES_RUN.md). This does not
require another timer-only confirmation. Continue development from those counts;
request a bounded example only if they leave a specific ambiguity unresolved.
