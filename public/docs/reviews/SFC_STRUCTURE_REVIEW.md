# SFC structural capture and bounded feedback

Implemented on `feat/bounded-operand-example-pc`, continuing Phase 1. The new
library and CLI expose SFC steps, transitions, action descriptors and diagram
links for investigation and later source-linked engineering records. They do
not interpret transition conditions, action qualifiers, timers or execution.

## Returned graph checkpoint

`2f37ae3` adds only
[work-check-20261015T012257Z-0878989d.json](../../inspection/work-check-20261015T012257Z-0878989d.json)
with tested clean `e17ceeb` as parent. Work10/reference12/source4 validates;
354 application cases (one Windows symlink skip) and 139 helpers pass. The graph
has 69 program routine nodes: 54 structurally parsed RLL, one partial RLL and
14 unmodeled SFC. All 76 JSR candidates link, forming 68 caller/target pairs;
three pairs repeat with eight extra occurrences. Three explicit main designations
match uniquely, 68 nodes participate, and one is isolated. No candidate cycles
or self pairs are observed. Earlier source/reference/candidate/metadata/shape,
alias/rack, flag and diagnostic counts are exactly unchanged. Partial, private
results saved and a null sample remain expected. Zero observed cycles does not
prove runtime behavior, particularly across unmodeled SFC bodies.

## Primary evidence and scope

[Rockwell RM014D, chapter 11](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf)
(printed pages 255-274) describes SFCContent, steps/actions, transitions, branches
and legs, subroutine/return and stop blocks, links and annotations. Online edits
can produce several SFCContent blocks in one routine. Therefore each content
block has its own captured identity and ID lookup; Original, PendingEdits and
TestEdits are retained separately. No active version is selected. Declared
numeric IDs are unsigned 32-bit values; raw spelling is preserved and decimal
leading zeros normalize for lookup. Directed links refer to diagram element IDs.

The approved minimized fixture demonstrates these wrappers and opaque ST lines,
but its randomized numeric IDs can create missing or ambiguous diagram links.
It establishes structural examples, not the real unit's topology. Coherent
invented fixtures establish link-resolution behavior; the next work-machine
report establishes real counts.

## Private model

SfcStructureResult is schema1 / sfc-structure-1, with scope sfc_structure_only
and semantic_analysis=not_implemented. It is separate from InventoryResult and
ReferenceResult, whose layouts and existing counts remain unchanged. The builder
validates snapshot identity and declaration ownership, then makes an additional
bounded XML pass over the same captured immutable bytes. It never rereads the
live input. Canonical replay checks every private field before saving or counting.

Private routine rows link source routine/scope IDs to content blocks and retain
protection markers, routine direct text and unknown immediate-child markers.
Content rows retain source location, raw attributes/direct text and edit-kind
classification. Every descendant within SFCContent retains source ID, parent,
location, XML name, contextual kind, attributes and direct text. Action bodies,
conditions, presets and limits preserve their ST text without parsing its meaning.
Unknown descendants remain unmodeled records. Unknown routine siblings are marked
as coverage gaps; their full payload remains in the immutable snapshot. Known
description and encryption metadata envelopes do not create that sibling gap.

ID lookup is local to each content block. Recognized flow objects, actions and
text boxes contribute block-ID evidence; other records with ID attributes also
participate conservatively in collision detection. Missing, invalid and duplicate
IDs remain explicit. Links resolve only when an endpoint names one eligible flow
object. Missing attributes, invalid IDs, absent targets, ambiguous targets and
unsupported target kinds are never guessed or connected across edit versions.
Snapshot IDs are provenance, not persistent engineering-object identities.

Bounds are 100,000 elements, 10,000 content blocks, 100,000 links, 8,000,000
retained string characters (including attribute names and metadata) and 65,536
characters per ID input, alongside the existing source-reader budgets. Fixed
errors expose no source-controlled details. Missing content, protection, unknown
content/edit kinds, unexpected text, ID gaps and unresolved endpoints make this
narrow capture partial. Complete means only that this structural slice had no
recorded gaps; it does not establish valid control logic or complete Phase 1.

## CLI and storage

```bash
uv run --project python-parser --locked plc sfc-structure \
  "confidential/plc-code/A19CHL02-unencrypted.L5X" --format text \
  --workspace "confidential/workspaces/sfc"

uv run --project python-parser --locked plc sfc-summary \
  "confidential/plc-code/A19CHL02-unencrypted.L5X" \
  --output "public/inspection/sfc-summary-001.json"
```

The first command emits private text or JSON; it returns exit3 for partial SFC
capture and exit0 for complete SFC capture. The aggregate command emits bounded
counts. Neither command infers runtime behavior or runs Git synchronization.
The ordinary inspect/reference commands keep their existing behavior.

save_run accepts optional SFC evidence, validating it before allocating a run.
It adds sfc-structure.json and sfc-structure.txt. New SFC-only runs have manifest3
source_sfc_structure_run with five artifacts; combined reference/SFC runs have
manifest3 source_reference_sfc_structure_run with seven artifacts. Existing
inventory-only/reference-only calls retain exact manifest1/2 layouts. The new
manifest records SFC versions/scope and combined partial status; artifact hashes,
exclusive creation, atomic finalization and append-only output remain intact.

## Public and work contracts

SFC summary schema1 / sfc-structure-summary-1 uses sharing policy2 and report kind
l5x_sfc_structure_review_summary. It contains standard code revision, source SFC
routine count, status and fixed counters for routine/content coverage, edit
versions, element kinds, ID quality/duplicates, links/endpoints, opaque ST line
length and issue codes. Names, values, snapshot/source IDs, attributes, ST text,
graph edges and unknown XML labels stay private. Partitions, issue counts and
endpoint capacities reconcile, including nonflow-target capacity and bounds on
which kinds can produce unexpected-text issues. The publisher revalidates the
schema and keeps the 32-KiB/no-overwrite/path rules.

Work11 / work-check-11 adds analysis.sfc_structure_summary beside the unchanged
reference12/source4 summary. It checks the same tested revision and SFC routine
population, combines analysis status, and requires null SFC summary on failed or
not-run analysis. sfc_structure_error is accepted only in the new envelope.
Work10 and earlier envelopes remain frozen/readable. Inventory3, reference6,
source-inventory-3/source-references-9 and public source4/reference12 stay exact.
The normal work runner captures once, saves combined manifest3 private results,
commits only the bounded feedback report locally, and never fetches/pulls/pushes.
Its parser test allowlist includes only invented process/network-free SFC tests;
real CLI revision collection is mocked in those tests.

## Next real report

Every existing source/reference/graph count should remain unchanged. Expect 14
source SFC routines in the new summary for the same export. Content/edit-version,
step/transition/action/branch, ID and link-resolution counts remain unknown until
the report returns. Review those counts and extraction gaps before adding ST
semantics, action calls, process transitions or target sequence mapping. Overall
partial remains expected. See [the normal procedure](WORK_MACHINE_REFERENCES_RUN.md).

## Validation

Full development validation passes **495 cases with one existing Windows symlink
skip**, excluding the ignored listener loader. New coverage comprises 17 SFC
core cases, 11 aggregate cases, 11 CLI/storage cases, five work-envelope cases
and one publisher case. The 104 related workflow/reference regressions pass.
Independent review passes 53 focused cases after fixes for attribute-name budget
bypass, impossible unsupported endpoints, opaque-text issue capacities and
outside-content coverage gaps. All three reproduced counterexamples now reject;
unknown routine siblings produce partial status. All 16 historical work reports
validate unchanged. No remaining blockers were found. All 78 relative Markdown links in changed
documentation resolve, and git diff --check passes.

The full suite command is:

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

An independent workflow agent runs the actual launcher twice from final copied
bytes in a disposable clean checkout without remotes: explicit invented source,
then remembered source. Each passes **399 application cases (one skip) and 139
helpers**. Its one SFC routine has two separate edit contents, 23 elements, ten
valid block IDs, five links (four resolved/one missing target), nine resolved/one
missing endpoints, two opaque ST lines with 41 characters and one issue. Repeated
numeric IDs across edits create no duplicate groups or cross-version targets.

Reports use work11 with SFC summary1 and unchanged reference12/source4. Inventory3,
reference6/analyzer9 remain exact; combined manifest3 has seven hashed artifacts.
SFC CLI JSON/text equal saved artifacts; count stdout and published summaries
match with revision accounted separately. Raw names, ST and IDs are absent from
shared feedback. Plain reference CLI retains manifest2/five artifacts; standalone
SFC uses manifest3/five artifacts. Compared with baseline `2f37ae3` on the same
fixture, inventory/private references are identical and reference summaries
differ only in code revision. Both local report-only commits cite tested parents
and leave clean checkouts. Source, previous runs and all artifact hashes remain
intact; Git traces contain no fetch/pull/push. Root code/test/config hashes match
the final tested bytes. Parser allowlist tests pass with subprocess/socket
creation prohibited; standalone CLI revision collection is mocked for those tests.

Development uses invented fixtures and approved public reports; project
confidential files and the disabled listener are not used here.
