# L5X engineering review, calculations and source structure

## Offline engineering review

`plc review` builds a self-contained, read-only report from source, reference,
access, Tag Data, PID, CPT calculation, SFC, rung, relationship and condition evidence. Open the
printed `review.html` path. The Engineering analysis view accounts for every
rung and captured block, groups candidate functions, explains uncertainty, and
shows structural branches and possible results. Search and combined filters
find families, unresolved blocks, empty bypasses and missing comments/metadata.
Address relationships separates exact member/index spellings, possible local
calculation links and operand-reuse patterns. Root-only access and opcode-shape
patterns remain separate views. Existing tag, PID, calculation and source views
provide deeper evidence links. Instruction conditions exposes incoming contexts for noncoil blocks, including
17 documented pass-through spellings. False evaluations can still change state;
condition transfer is separate from action/data validity. Conditional outputs links OTE/OTL/OTU records to
their incoming series/parallel condition graphs. Each source read stays a separate
occurrence; unknown transfers, binding gaps and malformed actions remain visible.
No PLC execution or final output value is inferred.

Binding context follows known-role binding gaps through captured alias chains,
scope-checked rack declarations and module evidence. Candidate logical addresses
group exact suffix spellings separately from confirmed address relationships.
Original bindings and guard statuses remain unchanged; physical I/O backing,
member validity and process purpose are still unconfirmed.

Instruction context links unknown-family blocks to candidate AOI declarations
within their controller, with parameter/body availability and source navigation.
Symbolic indexed access shows outer-root bindings and the individual reads that
select an array element. These companions retain existing unknown effects and
exact-address gaps. Call validity, element values and array bounds are unproven.

Candidate interpretations are unreviewed. Instruction roles, recognized
mnemonics, structural motifs, declaration references and weak name/comment
hints are separate. Internal Boolean outputs do not imply physical DOs; no
known local result does not prove dead code. CPT expression reads retain their
own population, node/span links and repeated occurrences.

The latest automated return (`48dcd22`) saved successfully and accounts for
4,163 coil outputs: 3,966 modeled guards, 196 with condition binding gaps and
one with an opaque transfer. There are 2,718 pass-through and 133 stored-state
transfers; 326 remain opaque. Earlier summaries remain unchanged, including
7,591 exact addresses and 1,489 operand-reuse patterns covering 4,286 rungs.
All 303 predicate binding gaps and 16 unbound coil targets now have unique
rack-candidate context: 319 uses across 94 candidate addresses and 11 roots.
Both additional dynamic writes now have bound outer roots and index reads. The
unknown block has a unique AOI declaration candidate, while one indexed operand
with an unknown role stays deferred. All six targeted rung examples replay unchanged.
SFR matched 139 of 140 calls to captured steps; its unmatched address occurs
in another chart in the same program. AOI body context has no recorded gaps.
PID connections account for all 46 controls and 322 slots, including 333 direct
member addresses. Every master slot is literal. Calculation paths now account
for 2,138 selected blocks, including 1,294 in branched rungs; two destinations
remain unresolved and one local reuse link is present. The next run measures
shared Boolean target uses, condition readers, declaration direction and authored
rung hints in the existing Conditional outputs view. No shutdown or physical
channel identity is inferred.
See [the current scope](../public/docs/reviews/OUTPUT_CONTEXT_REVIEW.md),
[the context contract](../public/docs/reviews/INSTRUCTION_CONTEXT_REVIEW.md)
and [sampling boundaries](../public/docs/reviews/TARGETED_RUNG_SAMPLES_REVIEW.md).
Continue the [Phase 1 analysis sequence](../public/docs/planning/PHASE_1_ENGINEERING_ANALYSIS.md)
before requesting team feedback. No manual engineering/UI review is needed now.
See [binding context scope and contracts](../public/docs/reviews/BINDING_CONTEXT_REVIEW.md).

```bash
uv run --project python-parser --locked plc review \
  "confidential/plc-code/A19CHL02-unencrypted.L5X" \
  --workspace "confidential/workspaces/review"
```

`--workspace` is required. Each invocation saves a new private run and prints
the HTML path. Exit 3 means usable partial output was saved. Review runs use
review16/manifest19 with sixteen hashed artifacts: snapshot.L5X, inventory.json, overview.txt,
references.json/txt, sfc-structure.json/txt, access.json, tag-data.json, pid.json, pid-members.json, calculations.json, rung-analysis.json, relationships.json, boolean-conditions.json and review.html. Existing plain
reference and standalone SFC workspaces retain manifest2 and manifest3.
All HTML and source-bearing artifacts are private and belong under
`confidential/`. Read [the function follow-up](../public/docs/reviews/CALCULATION_FUNCTION_REVIEW.md),
[the calculation review](../public/docs/reviews/CALCULATION_REVIEW.md),
[the PID member review](../public/docs/reviews/PID_MEMBER_REVIEW.md),
[the PID occurrence review](../public/docs/reviews/PID_EVIDENCE_REVIEW.md),
[the Tag Data review](../public/docs/reviews/TAG_DATA_REVIEW.md),
[the timer/copy checkpoint](../public/docs/reviews/TIMER_COPY_ACCESS_REVIEW.md)
and [the initial access-role checkpoint](../public/docs/reviews/ACCESS_ROLE_REVIEW.md).

The normal work-machine launcher also creates this report. Manually `git pull`,
run `bash ./run-work-check.sh` (supply the local L5X filename if needed), check
the generated feedback JSON, then manually `git push`. The runner
automatically commits only its validated feedback report; synchronization stays
manual. Current work33 adds calculation-path counts. It retains PID connections1, AOI body1 and SFR2,
condition3, custom-instruction/indexed-access summaries, the fixed
targeted-sample record and unchanged
binding-context summary1, relationship1, rung-analysis1,
access4, calculation2, PID member1, PID1, Tag Data1, reference12/source4 and SFC2.
Work32-33 permit 80 KiB for its additional fixed counters. Work28-31 permit
64 KiB; the targeted-evidence cap remains 16 KiB for all these versions. Work22-27
retain 48 KiB; work1-21 retain 32 KiB. New legacy single-operand samples are
disabled so they cannot rotate outside the targeted request's budget.
Work31-33 use compact JSON whitespace; earlier feedback formats are unchanged.
Work25 adds fixed save-failure categories. Review16 allows 216 MiB JSON / 248 MiB
HTML for calculation paths. Review15 retains 208 MiB JSON / 240 MiB
HTML, reserving 8 MiB for PID connections. Review14 retains 200 MiB JSON / 232 MiB
HTML, reserving 8 MiB for AOI body context. Review13 retains 192 MiB JSON / 224 MiB
HTML, reserving 8 MiB for SFR context. Review12 retains 184 MiB JSON / 216 MiB
HTML for custom-instruction and index context. Review11 retains 168 MiB JSON /
200 MiB HTML for the earlier binding context. Review9/10 retain
160 MiB JSON / 192 MiB HTML, and earlier versions retain their original budgets. See the
[save failure checkpoint](../public/docs/reviews/SAVE_FAILURE_REVIEW.md).
See [stored-state conditions and SFC targets](../public/docs/reviews/STATEFUL_SEQUENCE_REVIEW.md)
for that checkpoint's semantics and validation, and
[calculation paths](../public/docs/reviews/CALCULATION_PATHS_REVIEW.md) for current work.
Earlier work17 added count-only
PID member summary1 while preserving
PID1, Tag Data1/reference12/source4/SFC2/access2 summaries. Documented member
groups, type/shape checks and missing/duplicate catalog fields complement the
existing operand and storage links. Scalar values, array contents, flags and
effective configuration remain uninterpreted. Review4/manifest7 remains available
when the optional member companion is omitted.

Returned `28b5d1f` confirms all 46 PID occurrences linked to 46 distinct backing
declarations, with 2,346 direct member occurrences and no PID association gaps.
Its clean `1e9aaae` run passed 586 application cases (one skip) and 139 helpers;
prior summaries matched after revision normalization. This establishes capture
coverage, not 46 engineered loops or valid settings. Read the
[PID member review](../public/docs/reviews/PID_MEMBER_REVIEW.md) for current
scope and validation. That historical handoff measured PID member coverage;
the current handoff measures binding-gap context.

Historical Tag Data/work15 validation: 642 development cases passed with one
existing Windows symlink skip. Two isolated runs each passed 546 application
cases (one skip) and 139 helpers; ten artifact hashes and fresh CLI equivalence
verified. Eight legacy artifacts matched `122f230`; all 21 then-stored work1-14
reports validated. The returned work15 report at `a096cae` tested clean `7d0cbb1`
and is the unchanged baseline for the PID extension.

Historical access2/work14 validation was 592 development cases with one
existing symlink skip. Two actual isolated runs, explicit then remembered source,
each pass 496 application cases (one skip) and 139 helpers and create report-only
local commits without Git network calls. Nine artifact hashes and canonical
access2/review2 verify; fresh CLI artifacts match byte for byte. Seven legacy
artifacts match `7cd9201`, source/reference/SFC summaries match after revision
normalization, and all 20 historical work1-13 reports validate.

Initial access1 validation is historical: 574 development cases passed with one
existing symlink skip. Two final synthetic launcher runs each passed 478 application cases (one
skip) and 139 helpers, with nine artifact hashes and canonical access/review
evidence verified and CLI HTML identical. Seven legacy artifacts are byte-identical
to baseline `1332543` on the same invented input; source/reference/SFC summaries
match after revision normalization. All 19 then-stored work1-12 reports validated.
Returned `7cd9201` confirms initial access1 on clean `6642c5c`, passing 478
application cases (one skip) and 139 helpers. It classified 16,952 of 17,874
instructions, retained 922 unsupported instructions and counted 321 access
binding gaps; reference/source and SFC summaries match the preceding `1332543`
report after revision normalization. Historical work14 requires access summary2
and private access2; frozen work13 retains access summary1. Reference12/source4/SFC2 and
private inventory3/reference6/SFC2 retain their contracts. See
[the work-machine procedure](../public/docs/reviews/WORK_MACHINE_REFERENCES_RUN.md).

## Explicit operand access

The independent access analyzer consumes validated inventory/reference evidence
and preserves existing instruction and operand identities. Its supported
catalogue labels `read`, `write`, `read_write` and `non_data`; unsupported
instructions and wrong/empty signatures retain `unknown` roles. TON/TOF/RTO
require three nonempty fields and accept only `?` or recognized integer literal forms
in their two preset/accumulator pseudo-operands. Accepted timer storage is
read-write and both pseudo-operands are non-data; an unsupported pseudo form
leaves the whole instruction unknown. RES storage is a possible write.
COP/CPS provide source-read/destination-write/length-read roles without expanding
copy extents or validating types, bounds, overlap or execution.

Access3 adds CTU/CTD counter read/write with the same pseudo-field grammar,
MSG control read/write, GSV destination write, SSV source read and SFR explicit
step possible write. Exact trimmed SFR target `0` is an initial-step selector.
The three GSV/SSV selectors and SFR routine names are non-data. Their data slots
use separately attributed root bindings without changing original reference
records. GSV/SSV may have an empty instance field; other required slots must be
present and nonempty. Message payloads, system transfer ranges, SFC execution
and step membership remain unmodeled. CPT, PID, AOI, JSR and ST effects are not
inferred by this access layer.

Only canonical `root_bound` occurrences enter the disjoint resolved-root groups.
Read-write storage remains one occurrence, OTL/OTU are explicit writes, and MVM
conservatively includes a destination read because unmasked bits are retained.
No mask evaluation, member validation or source-to-destination dependency edges
are added. A literal destination can retain a declared write role while remaining
unbound; it is an access gap and never supplies bound write evidence.

`access.json` is private schema3 (`instruction-access-3`). Its coverage accounts
for all parsed instructions, operands by role/binding, linked/unlinked occurrences,
indexed roots, unparsed rungs and known-role binding gaps. Separate timer and
counter pseudo-field counts retain their populations. Fixed extended-family
counts and fresh-bound counts reconcile access additions with unchanged original
references. Each private operand includes its binding origin and original
reference status; the report shows these scopes separately.

`analysis.access_summary` schema3 in work20 publishes only fixed metadata,
status, revision and counts. It contains no names, IDs, values or source-defined
keys. Frozen work13 retains summary1; work14-19 retain summary2. Explicit private
access2 replay reproduces earlier evidence. A shared withheld-opcode allowance
covers case variants without treating pooled spellings as known family members.
The source/reference contracts and standalone `references` output are unchanged.
See [EXTENDED_ACCESS_REVIEW.md](../public/docs/reviews/EXTENDED_ACCESS_REVIEW.md)
for the current contract and [TIMER_COPY_ACCESS_REVIEW.md](../public/docs/reviews/TIMER_COPY_ACCESS_REVIEW.md)
for the preserved earlier checkpoint.

## Source inventory

`plc inspect` provides the underlying read-only source inventory. It captures one local L5X as
immutable in-memory bytes, inventories source envelopes and scoped tags, and
reports each rung's preserved text, outer syntax, instruction arguments, offsets
and structural coverage. JSON and readable text use the same inventory records.

All `inspect` outputs are **private**: they can contain names, comments, raw ladder logic,
source hashes and identifiers. This command is not a scrubber. Keep real inputs
and outputs in approved private storage; do not put them in `public/` or Git.
The existing `tools/l5x_inspect/` publication helpers remain a separate workflow.

## SFC structural evidence

```bash
uv run --project python-parser --locked plc sfc-structure \
  "confidential/plc-code/A19CHL02-unencrypted.L5X" --format text \
  --workspace "confidential/workspaces/sfc"
uv run --project python-parser --locked plc sfc-summary \
  "confidential/plc-code/A19CHL02-unencrypted.L5X" \
  --output "public/inspection/sfc-summary-001.json"
```

`sfc-structure` emits private step/transition/action descriptors, edit-version
content blocks, raw attributes/opaque ST and conservative diagram links. TextBox
notes preserve direct text and immediate Text-child fragments independently;
annotation attachments have separate typed endpoints and do not become flow
edges or automatic engineering descriptions. Numeric
IDs resolve only within a content block; missing, invalid and duplicate IDs
remain gaps. All edit versions stay separate. This uses another bounded XML pass
over the same captured bytes, keeping existing inventory/reference results exact.
Private text/JSON can be saved in an append-only workspace. Exit0/3 describes
complete/partial structural capture, not complete Phase 1 or valid execution.

`sfc-summary` publishes only closed counts and code revision under schema2/policy2.
It contains no raw descriptors, values, source IDs or topology. The ordinary
source/reference commands keep their existing contracts. Optional SFC storage
adds sfc-structure.json/txt and manifest3; ordinary source/reference-only runs
retain manifest1/2. See [the annotation review](../public/docs/reviews/SFC_ANNOTATION_REVIEW.md) and [the SFC review](../public/docs/reviews/SFC_STRUCTURE_REVIEW.md).

## Scoped tag and alias references

`plc references` analyzes the captured source inventory without rereading the
file. It binds supported whole operands to declared tag roots, follows aliases
in each alias's declaring scope, and retains each occurrence with its rung and
instruction IDs. Program locals shadow controller tags; AOI definitions use only
their own parameters/local tags. Case-insensitive collisions are ambiguous.

```bash
uv run --project python-parser plc references public/fixtures/synthetic/controller_demo.L5X
uv run --project python-parser plc references "confidential/plc-code/unit.L5X" \
  --format json --workspace "confidential/workspaces/reference-check"
```

`root_bound` means the declared root and any alias chain were found. It does not
prove valid members, array dimensions/bounds, access permissions, instruction
types, read/write direction or engineering meaning. Static member/index suffixes
are retained as evidence. Expressions, dynamic indexing, cross-program qualified
addresses, uncatalogued instructions and malformed argument lists remain explicit
gaps. Routine labels in JMP/LBL are accounted as non-data; call/sequence/system
instruction roles are not guessed. Module InputTag/OutputTag/ConfigTag declarations
now participate in root lookup. Explicit names or conservative ICP/Ethernet
module/port topology supply the name; private symbols retain `name_origin` and
`name_reason`. Missing or ambiguous topology leaves an unnamed declaration.
RackConnection declarations are inventoried separately; backing mappings remain
unverified. Private rack candidates compare missing logical roots without
changing ordinary bindings. These gaps
do not establish that the source project has an invalid tag.

Private inventory schema 3 (`source-inventory-3`) includes module ports, ordinary
connections, input/output/configuration tags and dedicated rack declarations
without changing ordinary tag/alias totals. Reference schema 6 (`source-references-9`) includes the three ordinary I/O
symbol kinds and a fixed `reason` on unresolved/unsupported-address bindings.
Reasons distinguish missing declared roots, qualified or dynamic addresses and
other bounded syntax gaps; they do not claim to identify every gap's engineering
cause. Raw declarations remain separate from inferred names.

Analyzer `source-references-9` retains recognition of exact trimmed `?` only in the preset
and accumulator slots (1/2) of valid three-argument TON/TOF/RTO instructions.
These are `non_data` for root lookup; original text is preserved. No timer values,
types, configuration or effects are validated. Root slots, aliases and other
instructions keep their existing gap handling. See [the timer review](../public/docs/reviews/TIMER_PLACEHOLDER_REVIEW.md).

Direct exact trimmed ASCII `S:FS`, ignoring letter case, in valid one-argument
XIC/XIO instructions is recognized as `system_flag`. It is the First Scan flag,
with no declared-tag link. Raw evidence is preserved; aliases, suffixes, other
instructions and other `S:` names keep their existing handling. This does not
model initialization effects or when the flag is true. See
[the system-flag review](../public/docs/reviews/SYSTEM_FLAG_REVIEW.md).

Valid two-field ABS/LN/SQR instructions now reuse the existing root/literal
lookup for source and destination arguments. These lexical classifications do
not validate types, math domains, destination access or runtime behavior;
recognized destination literals retain the existing catalog policy. Expressions,
dynamic indices and wrong arity remain gaps. See
[the calculation review](../public/docs/reviews/MATH_SIGNATURE_REVIEW.md).

MVM/SWPB now have three catalogued fields. MVM source/mask/destination and SWPB
source/destination use existing lexical lookup. SWPB's middle order-mode field
is `non_data` by position, with its raw value retained and no mode-value or byte
ordering validation. It cannot become an address sample, even if it resembles a
tag or malformed address. Wrong arity and empty fields retain their gap handling.
See [the bit-operation review](../public/docs/reviews/BIT_OPERATION_REVIEW.md).

Each parsed RLL JSR now has a separate private `routine_targets` occurrence,
including zero-field calls. Its static first field matches only declared routines
in the caller program, independently of tag lookup. Unique candidates retain
snapshot IDs and explicit self/main/fault context; other_routine requires a
Normal program. AOI callers and unsupported names stay explicit, and non-RLL
target envelopes remain candidates. Parameter roles, valid calls and phase-state
names are not inferred. All JSR/SBR/RET operand classifications and catalog counts
are unchanged. See [the candidate review](../public/docs/reviews/ROUTINE_TARGET_REVIEW.md).

The private `rack_candidates` section lists supported individual rack roots and
compares unresolved colon roots in three populations: aliases, direct operands
and alias-mediated operands. Exact candidates remain separate from normal
bindings. Unavailable candidate names mean matching is inconclusive; a candidate
match does not establish the backing adapter/member layout. Public summaries
publish only fixed counts. See [rack contracts and tests](../public/docs/reviews/RACK_CANDIDATE_REVIEW.md).

Both text and JSON reports are private. The workspace option creates a NEW run
containing the existing snapshot/inventory/overview, plus `references.json` and
`references.txt`. Its schema-2 `source_reference_run` manifest records artifact
hashes, versions, limits of analysis and combined partial status. The existing
`inspect` run manifest remains schema 1. Old runs and inputs are never overwritten.

For portable feedback, run:

```bash
uv run --project python-parser plc reference-summary "confidential/plc-code/unit.L5X" \
  --output "public/inspection/reference-summary-001.json"
```

This approved aggregate includes fixed symbol-kind, alias/operand status and
reason counts, module naming origins/unavailable reasons, analysis coverage and
a nested schema-4 `source_summary`, plus closed rack-candidate counts. Code provenance is
`source_summary.tool_revision`. It contains no names, values, source identities
or individual reference links. Its report kind is `l5x_reference_review_summary`,
schema 12, policy 2, exporter `reference-summary-12`, analyzer `source-references-9`.
`operands.by_status.system_flag` counts recognized first-scan contact operands
separately from ordinary bindings, literals and non-data roles.
`routine_instruction_shapes` observes JSR/SBR/RET argument counts, with fixed
arity buckets and exact second-zero text observations for JSR. These counts
assign no parameter roles or routine targets; the binding catalog is unchanged.
Case-normalized observations reconcile against source opcode/withheld counts.
Private text reports include the same observations, including zero-field calls;
private reference JSON now includes separate canonical candidate occurrences. See
[the routine-shape review](../public/docs/reviews/ROUTINE_CALL_SHAPE_REVIEW.md).
The separate public `routine_targets` object contains only fixed metadata, total,
closed status/context counts and distinct-target count. It publishes no routine
names or occurrence IDs. The shape profile's target_resolution=not_analyzed
describes that profile only; candidate lookup and parameter interpretation remain
separate. Reference9 stays frozen as analyzer7 and rejects the new field.
`routine_target_metadata` observes program-Type provenance and target-language
declarations for unique candidates, plus program-Type counts restricted to
not_analyzed contexts. Missing, empty, known exact enums and unknown explicit
values stay distinct; no omitted-Type default is assigned. Counts are weighted
by calls, not distinct targets. Private text includes the same counts when
inventory is supplied. Private JSON/schema6/analyzer9 now also contains the
separate static graph; existing metadata and candidate results are unchanged.
Reference10 is frozen and rejects this new metadata field. See
[the metadata review](../public/docs/reviews/ROUTINE_METADATA_REVIEW.md).
Private `routine_graph` records program-local routine nodes, grouped candidate
JSR calls with instruction links, observed body coverage, explicit main
designations and candidate cycles. Text presents a labeled map; JSON retains
canonical source IDs. SFC bodies remain unmodeled, and this static graph does
not establish execution, scheduling, valid recursion or parameter roles. Public
`routine_graph` contains only fixed counts, with no topology, names or IDs.
Reference11 stays frozen as analyzer8 and rejects the graph field. See
[the graph review](../public/docs/reviews/ROUTINE_GRAPH_REVIEW.md).
`operands.malformed_address_shapes` partitions only malformed-address occurrences
into seven fixed observational buckets, including a separate alias-target bucket.
The diagnostic does not change address recognition or binding. See the
[address-shape contract](../public/docs/reviews/ADDRESS_SHAPE_REVIEW.md).
The validator also accepts reference schema 1/source schema 2 and reference
schemas 2/3/4 with source schema 3, and references 5/6/7/8/9/10/11/12 with source 4. Historical
status vocabularies remain exact; mixed version combinations are rejected.
The publisher accepts only the source, reference and work-check aggregate schemas and validates again
before writing. New filename, location, 32-KiB limit and no-overwrite rules apply.

Exit 3 means useful partial results were produced. Reference analysis can be
partial even when the structural inventory is complete. Exit 0 means this bounded
root-binding scope completed; it never means all engineering behavior is understood.
See [validation and exact scope](../public/docs/reviews/MODULE_IO_REVIEW.md)
and [work-machine steps](../public/docs/reviews/WORK_MACHINE_REFERENCES_RUN.md).

## Bounded summary for feedback

`plc summarize` applies a separate aggregate publication policy to the captured
inventory. It contains approved count fields, routine-language and instruction
totals, diagnostic counts and global ladder measurements. Unknown source labels
are pooled into fixed withheld buckets. No source hashes, names, operands, XML
paths, rung IDs or layouts are included. Tyler has approved these aggregates for
repository sync: they expose no individual rung logic or process values. His
confidentiality boundary is unit reconstruction with data values, or more than
2% rung knowledge. This command exports no rung samples and does not assess
that threshold for other artifacts.

```bash
uv run --project python-parser plc summarize "public/fixtures/synthetic/controller_demo.L5X"
uv run --project python-parser plc summarize "confidential/plc-code/unit.L5X" \
  --output "public/inspection/source-summary-001.json"
```

Without `--output`, stdout is JSON. An explicit output creates a new UTF-8 JSON
file and prints a fixed save notice to stderr. Existing files/symlinks are never
overwritten. Output inside this checkout may be beneath public/inspection/ or
confidential/. The publisher independently validates and canonicalizes the JSON
before writing, so this path is not a general private-data copy mechanism.
Publication uses a temporary sibling plus an atomic no-clobber hard link; an
unsupported filesystem fails without publishing the candidate. Normal local
NTFS storage is covered by the tests; network-share support is not assumed.
If temporary-file cleanup fails, a `.plc-summary-*.pending` file may remain.
Only the requested final `.json` is the published candidate; a pending file is
never a report to share.

New summaries use schema 4, policy 2 and exporter `aggregate-summary-4`, built from
the source-inventory-3 contract. Counts include module ports, ordinary
connections, input/output/configuration tags and dedicated rack declarations.
The validator retains source aggregate schemas 2/3 and rejects mixed version fields.
A complete validated report is capped at 32 KiB.
All counts are strict nonnegative integers and reconcile across groups. Output
cardinality does not grow with unrecognized source labels. The code revision
comes from this application's checkout, with a clean/modified/unavailable flag;
it is not a source-data fingerprint. Modified includes tracked or untracked
application sources/build metadata; docs and plant inputs are excluded. The
command never accesses a network for revision collection.

Policy 2 records `sharing_status=aggregate_sync_allowed` without a review warning.
Existing v1 aggregate reports remain suitable for sync under Tyler's
clarification; they do not require a fresh source run. Their old status string
records the previous policy. They remain historical feedback rather than a
directly accepted input to the current validator.

Exit codes match `inspect`: 0 structural completion, 3 partial coverage with a
usable candidate, 1 failure, 2 usage. Parsed syntax is not understood engineering
purpose. See [the work-machine procedure](../public/docs/reviews/WORK_MACHINE_SUMMARY_RUN.md)
for checkout, testing, generation and the exact artifact to return.

## Local work-machine feedback

The development listener remains disabled and paused. Its files and test loader
are ignored local development tools and are not included in normal checkouts.
Manual parser checks are independent of that service. Update or clone the code manually, then
run from the repository root in Git Bash:

```bash
bash ./run-work-check.sh YOUR_READABLE_EXPORT.L5X
# Later runs in this checkout remember the source path:
bash ./run-work-check.sh
```

The launcher uses the code already checked out on a
clean named branch, including `main`. It automatically stages and commits only
the new feedback report, never fetches, pulls or pushes, and does not require
an upstream branch. A configured Git author identity is required for the local
commit. Code updates are a separate manual
action. The first run accepts a source filename/path; later runs reuse the
selection saved in this checkout's Git metadata.

The application and helper checks use explicit module allowlists in fresh
processes. Work-machine checks exclude listener, Windows process-host, Bash
bootstrap and Git-fixture tests. The development command below excludes the
ignored listener loader; its test totals must not be compared as if it had the
same scope as the work-machine checks.

Successful tests enable source, reference, SFC, access and Tag Data analysis
from one captured snapshot and a new private workspace. The feedback includes test counts, bounded
code-only failing test IDs, the tested commit and count-only reference/SFC/access/Tag Data summaries.
Work-check schema 15 retains `diagnostic_sample`: one actual direct malformed
operand, or a direct unresolved colon operand with no rack candidate when no
eligible malformed sample exists. It retains at most 128 printable characters,
a standard instruction and zero-based argument position; otherwise it is null.
Tyler authorized one mystery-address example; no rung, source location or
neighboring logic is included. Selection is stable, excludes alias targets and
inconclusive/candidate matches, and never truncates source text. Schema 2 rejects
the `direct_unmatched_colon_operand` kind. Current reports reject recognized
XIC/XIO `S:FS` as an unmatched sample, and SWPB order-mode slots as either kind.
See the
[follow-up review](../public/docs/reviews/UNMATCHED_OPERAND_REVIEW.md).
It is saved to `public/inspection/work-check-<run-id>.json` and committed locally.
Failed tests also produce a committed report and skip source analysis. Useful
partial analysis exits 0; test or analysis failure exits 1 after committing the
report. Preflight, save or commit failures stop without claiming completion.

The outer report is schema16 and carries unchanged reference12/source4 plus
`analysis.sfc_structure_summary` (SFC schema2), `analysis.access_summary`
(access schema2), `analysis.tag_data_summary` (Tag Data schema1) and
`analysis.pid_summary` (PID schema1) when analysis succeeds. Failed or skipped
analysis leaves these summaries null. Frozen work15 retains Tag Data1 without PID; work14
retains access summary2 without Tag Data; frozen work13 requires access summary1. Historical
work12 retains SFC2 without access, and work11 requires frozen SFC1.
Historical schema-1/2/3/4/5/6/7/8/9/10/11/12/13/14/15 reports remain readable;
schemas 3/4/5/6/7/8/9 require references 5/6/7/8/9/10/11 respectively. The tested
SHA identifies the implementation and therefore its suite scope; historical
reports may include the broader development suites. The result returned in
`46467af` validated the local report-commit workflow. The later report in `349ee29`
returned `?` at TON argument 1. Report `1195d40` then tested `112ee82` and
confirmed malformed occurrences fall 868 to zero while non-data rises by 868,
with unchanged root bindings. Both suites passed; no repeat run is needed for
this fix. Known placeholders are skipped when choosing a remaining mystery sample.

Report `9597f18` confirmed 15 named rack roots, matching all 99 unresolved aliases
and 319 alias-mediated operands. Report `7f5db96` identified the one unmatched
direct operand as `S:FS` in XIC. Report `d247f87`, testing clean `d64ee4d`, confirms
its recognition: system_flag=1, unresolved operands 320 to 319, direct rack
comparisons 1 to 0 and a null sample. All 269 application cases (one skip) and
139 helpers passed. Other source/reference counters stayed unchanged. No repeat
flag-only check is needed. Partial remains expected. Logical candidate matches
do not validate backing I/O maps or promote ordinary bindings.

Report `4244cf5`, testing clean `a6a2a71`, confirms all 28 ABS/LN/SQR signatures
and all 56 arguments bound to roots. Catalogued instructions rise 17,563 to
17,591, root_bound rises 20,178 to 20,234 and unsupported instruction slots fall
653 to 597. All 286 application cases (one skip) and 139 helpers passed; other
counters are unchanged. No repeat calculation-only run is needed.

Report `08c2695`, testing clean `bdf09f1`, confirms all 26 MVM/SWPB signatures.
Their 78 slots became 52 bound roots, 16 literals and ten selectors. Catalogued
instructions rise to 17,617 and unsupported instruction slots fall to 519.
All 296 application cases (one skip) and 139 helpers passed; other counters
are unchanged. No repeat bit-operation-only check is needed.

Report `0a2610f`, testing clean `9c56b50`, confirms 76 JSRs/163fields: 65
two-field second-zero and 11 three-field second-other calls. SBR has one field;
RET has none. All 308 application cases (one skip) and 139 helpers passed;
earlier counters are unchanged. No parameter role follows from these shapes.

Report `7e15843`, testing clean `3598710`, confirms 76 unique candidates,
66 distinct targets and all contexts not_analyzed. All 325 application cases
(one skip) and 139 helpers pass; earlier counts are unchanged. A unique
declaration candidate does not prove a valid call or parameter role.

Report `3431389`, testing clean `5f91400`, confirms all 76 program-Type
observations are absent, with target-language occurrences RLL62/SFC14. All 335
application cases (one skip) and 139 helpers pass; earlier counts are unchanged.

Report `2f37ae3`, testing clean `e17ceeb`, confirms 69 graph nodes, 68 pairs,
76 linked calls, three repeats/eight extras, three unique mains, one isolated
node and no observed cycles. All 354 application cases (one skip) and 139 helpers
pass; earlier counts are unchanged.

Returned `90923ab` confirms SFC2 structural capture is complete for this export:
280 recognized child-text boxes and 213 attachments with all 426 endpoints
resolved. SFC issues fall from 280 to zero; all earlier reference, flow-link,
ID and ST counts remain unchanged. The report passes 416 application cases
(one skip) and 139 helpers. That checkpoint saved private sfc-structure.json/txt
under combined manifest3 (seven artifacts); current review4 runs use manifest7
with eleven artifacts, adding access JSON, Tag Data JSON, PID JSON and HTML. Overall partial remains expected: runtime SFC logic,
ST semantics and engineering classifications remain unimplemented. No repeat
annotation-only work run is needed. See the [project-state assessment](../public/docs/reviews/PROJECT_STATE_REVIEW.md).

Review the local feedback report before sharing, then run `git push` when ready.
There is no manual copy, staging or commit step. Older reports in
`public/inspection/local/` remain ignored and are not included automatically.
Raw logs, full results, source and older outputs stay under `confidential/` and
must not be included. Read the [work-machine procedure](../public/docs/reviews/WORK_MACHINE_REFERENCES_RUN.md)
for output locations and the [implementation review](../public/docs/reviews/WORK_CHECK_RUNNER_REVIEW.md)
for the bounded report contract. This runs the implemented Phase 1 tools; it does
not generate engineering classifications, PCSD or FHX.

## Run individual commands from Git Bash

From the repository root, with Python 3.12+ and `uv` available:

```bash
uv run --project python-parser plc inspect --help
uv run --project python-parser plc inspect "public/fixtures/synthetic/controller_demo.L5X"
uv run --project python-parser plc inspect "confidential/plc-code/unit.L5X" \
  --format json --workspace "confidential/workspaces/demo"
```

The first run installs the local package and dependencies. End users will
eventually receive a standalone app; executable packaging is not implemented in
this slice. `uv run --project python-parser python -m plc_workbench` is an
equivalent entry point. The original `main.py` prototype remains available.

Without `--workspace`, the command writes only the requested report to stdout.
`--format text` is the default; `--format json` returns the full inventory. Both
use UTF-8 to preserve multilingual source text, including when redirected. Save
paths go to stderr so redirected JSON stays machine-readable. To inspect one
rung, copy its exact `id` from the inventory's `rungs` list:

```bash
uv run --project python-parser plc inspect "confidential/plc-code/unit.L5X" \
  --rung-id "EXACT_ID_FROM_THE_SAME_SNAPSHOT" --format json
```

IDs identify occurrences within one byte snapshot. Changing the source creates
new IDs; they are not persistent review-object IDs. Unknown or ambiguous IDs
fail before any workspace is created. The selected JSON view includes one
`rung`, its direct diagnostics and the report's snapshot/status metadata.

## Private saved runs

An explicit workspace creates a fresh `run-<UTC timestamp>-<random id>/`:

- `snapshot.L5X`: the exact bytes analyzed, copied without changing the input.
- `inventory.json`: the complete private inventory, even when `--rung-id` selects
  a narrower stdout view.
- `overview.txt`: the complete readable overview and gap list.
- `manifest.json`: snapshot identity, parser/schema versions, coverage status,
  artifact byte counts and SHA-256 hashes.

Existing runs are never reused or overwritten. Files are exclusively created
and flushed before the final manifest is atomically published. Readers must
ignore runs without `manifest.json`; an interrupted/failed run may leave files
and `.manifest.pending` but does not become a successful checkpoint. A saved
`partial` run is a finished inventory with explicitly incomplete coverage.
These checks do not promise durability against every power-loss/filesystem case.

Destinations inside this development checkout must resolve beneath
`confidential/`. Other explicit private locations are supported, including paths
with spaces. Resolved workspace/run containment checks reject symlink escapes
and artifact collisions. This is a local, single-owner workspace; it is not a
security boundary against concurrent hostile filesystem modification. A
packaged installation without a checkout relies on the user-selected private
destination. Shell redirection is outside the command's destination checks.

Git does not back up ignored private workspaces. Retain the whole run directory
in an approved backup location to preserve relative artifact links. This slice
does not implement editable records, correction overlays, handoffs or backups.

## Coverage and exit status

| Exit | Meaning |
| --- | --- |
| 0 | Structural report completed within this reader's scope |
| 1 | Read, validation, selection or save failure |
| 2 | Invalid command-line arguments |
| 3 | Report produced with partial structural coverage |

Parsed syntax does not establish engineering purpose. SFC/other unsupported
content and opaque regions are preserved in the snapshot and reported as gaps.
The separate `references` command adds bounded root binding; `inspect` remains
structural. Alarm shutdown analysis, PID relationships, equipment/sequence
classification, PCSD and FHX generation are not implemented.
Instruction subtotals cover only parsed rungs; inspect coverage before using
them as source-wide totals. The synthetic fixture includes unsupported SFC and
therefore intentionally returns exit 3.

## Tests

Run from the repository root:

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
uv run --project python-parser --locked python -B -m unittest discover -s tools/l5x_inspect/tests -v
```

Tests use invented data or the reviewed public fixtures. The private workspace
tests use temporary directories; no proprietary source is required.
Do not use broad application discovery on a development checkout that retains
the ignored listener test loader. The explicit command above leaves it excluded.
