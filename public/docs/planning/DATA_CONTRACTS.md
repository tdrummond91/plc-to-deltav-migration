# Data contracts, traceability, and checkpoints

Status: updated 2026-10-14. Private source inventory, derived root references and bounded aggregates have versioned contracts below; engineering/editable-review contracts remain proposals.

## Current basic calculation signature contracts (2026-10-14)

Private inventory remains schema 3 / source-inventory-3; private references
remain schema 4 with analyzer source-references-6. ABS/LN/SQR now have two
catalogued source/destination fields using the existing lexical lookup rules.
No private field layout changes. Public reference schema 7 / reference-summary-7
has the same fields/status vocabulary and source-schema-4 pairing as version 6,
with the updated analyzer constant. Version 6 is frozen as analyzer 5, including
its system-flag count bounds. All prior reference contracts remain readable.

Work schema 5 / work-check-5 requires reference 7 after successful analysis.
Work3/reference5 and work4/reference6 retain exact earlier pairings; work1/2
retain supported nested-reference handling. Known flags/timer placeholders stay
excluded from current mystery samples. Source aggregate 4, manifest 2, sharing
fields, sample bound, output paths and manual pull/push remain unchanged.
Lexical destination literals do not prove valid destination access, datatype,
math domain or execution effects. See [scope and validation](../reviews/MATH_SIGNATURE_REVIEW.md).

## First-scan system-flag contract checkpoint (2026-10-14)

Private inventory remains schema 3 / `source-inventory-3`. Private references
are schema 4 / `source-references-5`; public reference schema 6 /
`reference-summary-6` requires unchanged source schema 4. Reference-run manifests
remain schema 2 with current analyzer metadata. These versions supersede the
historical checkpoints below; rack and timer behavior is retained.

Only direct exact trimmed ASCII `S:FS`, ignoring letter case, in valid
one-argument XIC/XIO instructions receives operand status `system_flag`.
Raw evidence and source IDs remain unchanged. Its symbol/target IDs and reason
are null, with empty alias chain/suffix. Aliases, other roles and suffixes keep
their prior handling. This identifies the First Scan flag without simulating it.

Public `operands.by_status.system_flag` is a strict nonnegative count included
in total reconciliation and the completed operand-analysis statuses. It cannot
exceed catalogued instructions or named XIC + XIO + withheld occurrences.
Source schema 4 preserves opcode spelling, so lowercase contacts are withheld;
this public upper bound is conservative. Canonical private reanalysis proves
actual roles. Alias status keys do not change. Reference schemas 1 through 5
retain exact old status keys, rejecting even a zero `system_flag` field.
Reference 1 requires source 2; references 2/3/4 require source 3; 5/6 require 4.

At this checkpoint, work schema 4 / `work-check-4` requires reference 6 after successful
analysis. Historical work schema 3 still requires reference 5, including its
original S:FS mystery sample. Work schemas 1/2 retain their previous acceptance
of supported nested reference summaries; schema 2 remains malformed-kind only.
Current samples reject recognized XIC/XIO S:FS as unmatched even when another
direct operand remains unmatched. Selection, the single 128-character sample
bound, private output paths and local report commits are unchanged. Pull/push
remain manual. See [evidence and validation](../reviews/SYSTEM_FLAG_REVIEW.md).

## Rack candidate contract checkpoint (2026-10-14)

This slice introduced private inventory schema 3 / `source-inventory-3` and
private references schema 3 / `source-references-4`. Dedicated `module_rack_connection`,
`module_rack_input_alias` and `module_rack_output_alias` records preserve raw
attributes, XML locators, parent IDs and controller scope. They do not enter
ordinary symbols or tag/alias totals. Rack connection backing is always marked
not analyzed. Unexpected text/children produce a bounded diagnostic attached to
the exact record; raw content remains in the private snapshot.

Private reference field `rack_candidates` contains `candidates` and `matches`.
Candidate rows have source_id, connection_id, module_id, scope_id, direction,
name, name_origin, reason and backing_status (`not_analyzed`). Names use checked
topology only for attribute-free, supported-content declarations with an ICP
first edge. No adapter backing member or runtime behavior is inferred.
Match groups are aliases, direct_operands and alias_operands; each row retains
source_id, terminal_root, lookup_scope_id, status, candidate_id and candidate_count.
The terminal failed alias target determines lookup scope. A unique candidate
does not change an unresolved binding into root_bound.

Match statuses are unique_candidate, ambiguous_candidate,
candidate_names_unavailable, outside_visible_scope and no_candidate_match.
Visible exact matches take priority, then visible unavailable names, then exact
names elsewhere. Unavailable names indicate inconclusive matching, not a proven
relationship. Only a unique match retains candidate_id. New private evidence is
bounded to 8M retained string characters, including repeated source links.

Public source schema 4 / `aggregate-summary-4` adds module_rack_connections,
module_rack_input_aliases and module_rack_output_aliases. The mandatory backing
warning count equals rack connections, with at least that many warning-severity
diagnostics. Public reference schema 5 / `reference-summary-5` requires source
schema 4 and adds the closed `rack_candidates` object:
analysis_scope=`rack_logical_root_candidates`, backing_mapping=`not_analyzed`,
declarations and matches. Declarations contain total, named, by_direction,
by_name_origin and unavailable_by_reason. Each match group contains total and
by_status. Declaration counts reconcile to source counts; alias matches equal
unresolved colon aliases; direct plus alias-mediated matches equal unresolved
colon operands. Every positive alias-mediated status requires that status among
aliases. No names, IDs, addresses or individual source relationships are shared.

Exact historical source schemas 2/3 and reference schemas 1/2/3/4 remain readable.
Reference 1 requires source 2; reference 2/3/4 require source 3; reference 5 requires
source 4. Current canonical private validation requires the current versions.
Work-check subsequently used schema 3 as described below; reference-run manifest stays schema 2 with updated
parser/analyzer metadata. The timer behavior described below is retained.
See [implementation, precedence and tests](../reviews/RACK_CANDIDATE_REVIEW.md).

## Historical work-machine feedback schema 3 (2026-10-14)

`l5x_work_machine_check` / `work-check-3` keeps the same top-level fields as schema
2 and requires reference aggregate 5 / source aggregate 4 after successful
analysis. `diagnostic_sample` remains null or one four-field object with at most
128 printable characters of exact raw_text, standard opcode and zero-based
argument_index. It accepts the original direct_malformed_operand kind and the
new direct_unmatched_colon_operand kind. The latter must be a recognized static
colon-root address with positive canonical direct no_candidate_match evidence.

Selection first scans for an eligible direct malformed occurrence, then considers
unmatched direct colon operands in source order. Overlong/nonprintable malformed
records do not block fallback. Aliases and candidate/ambiguous/inconclusive/
outside-scope matches never qualify. Repeated unchanged runs do not rotate
examples; no source IDs, neighboring logic or other source context are added.
The builder validates canonical private references and matches by occurrence ID.
Public validation checks partial analysis, positive direct-unmatched count and
observed opcode; it cannot independently prove a particular raw operand's source
identity from aggregate counts.

Historical schemas 1/2 remain readable under their original rules; schema 2
explicitly rejects the new kind. Private inventory/reference contracts and
count-only source/reference aggregates are unchanged by this update. See
[returned evidence, tests and limits](../reviews/UNMATCHED_OPERAND_REVIEW.md).

## Historical work-machine feedback schema 2 (2026-10-14)

The current contract above supersedes historical version numbers below.

`l5x_work_machine_check` / `work-check-2` adds required nullable
`diagnostic_sample` alongside the existing analysis/test envelope. A non-null
sample has exactly `kind=direct_malformed_operand`, standard `opcode`, zero-based
integer `argument_index`, and one exact printable `raw_text` operand of at most
128 characters. It is generated from validated direct-malformed references in
the captured snapshot; alias failures and non-address roles are excluded.
Failed/unrun analysis requires null. A sample must reconcile with a positive
direct-malformed count and an observed instruction opcode in reference schema 3/4/5.
Schemas 4/5 reject known timer placeholders as mystery samples; schema 3 retains
its original interpretation for historical feedback.

Tyler authorized this one actual operand to investigate otherwise unidentified
syntax. No rung/source identifiers, surrounding logic or other values are added.
Source/reference summaries remain count-only at current schemas 4/5. Work-check schema 1
still validates under its exact original keys and cannot contain a sample. The
publication limit remains 32 KiB. See the [review and limits](../reviews/BOUNDED_OPERAND_SAMPLE_REVIEW.md).

## Timer recognition update (2026-10-14)

This checkpoint records the timer slice before the rack contract above. Its
recognition rules remain current; its version numbers are historical.

Private reference schema remains 2; the current analyzer is `source-references-3`.
For valid three-argument TON/TOF/RTO signatures, exact trimmed `?` in slots 1/2
is `non_data` for address lookup. Raw text and occurrence links remain intact.
This supplies no timer value and validates no configuration, datatype or effect.
Other roles and alias targets retain their prior handling. The ordinary address
grammar is unchanged. Current canonical validation requires the new analyzer;
this is not an editable import/migration path for saved private runs.

Public reference schema 4 / `reference-summary-4` records `source-references-3`
with the same fields as schema 3. Private manifest schema 2, source aggregate
schema 3 and work-check schema 2 remain unchanged. Public readers accept exact
reference schemas 1/2/3/4, including their original analyzer constants, and
work-check schemas 1/2. Non-null work samples require reference schema 3 or 4.
No sample field is added to count-only reference summaries. See
[the timer evidence and validation](../reviews/TIMER_PLACEHOLDER_REVIEW.md).

The following v2/v3 sections preserve their original behavior and provenance;
this update supersedes their statements about the current analyzer/exporter.

## Implemented root-reference analysis v2 (2026-10-13)

`references.ReferenceResult` has schema 2, analyzer `source-references-2` and
analysis_scope `scoped_root_bindings`. It consumes the typed source-inventory-2
result without modifying it. Private records include the snapshot identity,
symbols, alias resolutions, operand occurrences, coverage and status. Semantic,
instruction-effect and member validation fields remain `not_implemented`.

Symbols retain declaration IDs, owning scopes, `name_origin` and `name_reason`.
Alongside ordinary tags and AOI declarations, module_input_tag, module_output_tag
and module_config_tag records participate in root lookup. Module names may be
explicit or inferred from supported ICP/Ethernet topology; origins are
`explicit_name`, `module_name`, `backplane_slot` or `unavailable`. Missing,
ambiguous, unsupported or cyclic topology leaves the name unavailable with a
fixed reason. No value or Data child supplies a missing name. Raw inventory
records are not modified by this interpretation. Alias records are limited to
ordinary Tag aliases and AOI declarations with AliasFor.

Each operand ID hashes the
snapshot, instruction ID and zero-based argument index. Its record preserves the
raw argument, rung/instruction/scope IDs, direct symbol ID, terminal target ID,
alias-chain IDs and accumulated member/index suffix. Repeated uses remain separate.
Alias records include unused aliases; target lookup follows each alias's scope.
These are snapshot evidence links, not persistent engineering/review identities.

Operand dispositions are root_bound, unresolved, ambiguous, alias_cycle,
alias_depth_limit, unsupported_address, unsupported_expression, literal, non_data,
unsupported_instruction, argument_count_mismatch and empty. Aliases use the first
six applicable resolution dispositions (excluding unsupported_expression).
Root binding proves declaration lookup only; no member, array-bound, type or
access validation is claimed. Coverage distinguishes parsed source rungs and
instructions with catalogued signatures. Even a zero-argument unknown instruction
prevents complete status. Unsupported source content also propagates partial.

Alias and operand records also carry `reason`. It is non-null only for
`unresolved` or `unsupported_address`, including a terminal alias failure.
Unresolved reasons are `invalid_scope`, `root_not_declared`,
`colon_root_not_declared` and `aoi_alias_target_not_local`. Unsupported-address
reasons are `empty_address`, `address_length_limit`, `program_qualified_address`,
`backslash_qualified_address`, `non_static_array_index`, `malformed_address` and
`expanded_suffix_limit`. A colon-shaped missing root is a syntax observation,
not proof of an I/O defect or invalid source. Dynamic-index recognition is
bounded lexical analysis; no expression is evaluated.

Reference runs add references.json/references.txt to the existing private run and
use manifest schema 2, artifact_kind source_reference_run. The manifest is still
published last, includes all artifact hashes and records the analyzer version.
Ordinary source-inventory runs retain their existing schema-1 manifest.

`reference_summary` reconstructs only fixed aggregate fields: symbol kinds,
alias/operand disposition and reason counts, module naming counts, coverage and
the structural schema-3 report as source_summary. Its report_kind is
l5x_reference_review_summary, schema 3, policy 2 and exporter reference-summary-3.
Each aliases/operands `by_reason` group includes the complete fixed unresolved
and unsupported-address vocabularies; each reason total must equal the matching
status count. `module_io` contains `total`, `named`, `by_name_origin` and
`unavailable_by_reason`. Origins reconcile with total module I/O declarations;
named plus unavailable equals total, and unavailable reason counts reconcile.
The reason vocabulary comes from module_io.NAME_REASONS, never source labels.
Code provenance occurs only in the
nested source_summary.tool_revision. Private snapshot/occurrence reconciliation
happens in memory, including canonical reanalysis of names and bindings.
Closed-key/type/count validation runs again at publication;
private records, arbitrary labels, added fields and source identities are rejected.
The whole report is capped at 32 KiB and approved for sync under D026.

Reference aggregate schema 3 adds only `operands.malformed_address_shapes`.
The fixed zero-filled keys, in classification precedence, are
`alias_target_failure`, `leading_hash_static_address`, `leading_hash_other`,
`contains_brackets`, `contains_colon`, `contains_dot`, `other_form`.
Only occurrences with final status `unsupported_address` and reason
`malformed_address` enter this partition. A nonempty verified alias chain uses
the alias bucket, avoiding a claim about the caller's spelling. For a direct
leading hash, removing exactly one hash and passing the remainder to the existing
static-address recognizer selects the static/other bucket. Bracket means either
square-bracket character. The remaining tests inspect colon, then dot, then fall
back to other. The counters are mutually exclusive occurrences, not distinct
strings or evidence of valid syntax, dimensions, types or engineering purpose.
Their sum must equal the malformed-address reason count. A positive alias-target
bucket requires at least one malformed-address alias. No source-dependent keys,
examples, lengths, hashes, ordering or occurrence links are emitted.
Private reference schema/analyzer remain 2/source-references-2.

Public validation also accepts the previous reference schema 1 with its nested
source schema 2 and reference schema 2 with source schema 3 (without shape fields).
New reference schema 3 also requires source schema 3; mixed version fields or
nested versions are rejected. Historical work-check schema 1 and current schema 2
accept all three supported nested reference versions; a non-null schema-2 sample
additionally requires reference schema 3 as described above. This is aggregate read compatibility,
not an editable-data import or private-run migration.

See [module/I/O review](../reviews/MODULE_IO_REVIEW.md) and the
[preceding reference review](../reviews/SOURCE_REFERENCES_REVIEW.md) for scope,
resource bounds, primary documentation and test evidence.

## Implemented aggregate summary v3 (2026-10-13)

`plc_workbench.summary` builds and validates report_kind
`l5x_aggregate_review_summary`, schema_version 3, policy_version 2 and
exporter_version `aggregate-summary-3`. The builder accepts source-inventory-2.
Its closed field vocabulary includes component counts, coverage dispositions,
approved routine types, approved instruction totals, global ladder totals/maxima,
diagnostic counts and fixed analysis limitations. Unlisted labels use pooled
`withheld` counts, never stable unknown IDs. Missing routine Type is distinguished
from a present but unlisted value. XML coverage includes only aggregate element/
distinct-path counts, not path strings. Source identities and raw fields are absent.
New count fields are `module_ports`, `module_connections`, `module_input_tags`,
`module_output_tags` and `module_config_tags`; the diagnostic vocabulary now
includes `module_rack_connection_not_analyzed`. Ordinary tag totals are unchanged
in meaning. The validator also accepts the exact previous schema-2 contract;
schema versions cannot be mixed with another version's fields or metadata.

Strict nonnegative integer checks and cross-field accounting run before rendering
or publication. Complete reports cannot hide unknown-severity diagnostics or
unsupported executable coverage. Known parser measurement bounds are enforced.
Serialized UTF-8 JSON is capped at 32 KiB; report cardinality does not grow with
distinct unknown labels. `sharing_status=aggregate_sync_allowed` records Tyler's
authorization to sync these aggregates. They contain no individual rung logic
or process values. His boundary is unit reconstruction with data values, or more
than 2% rung knowledge; this summary has no rung samples. V1 reports remain usable
as historical feedback under that clarification without rerunning the source;
they are not directly accepted by the current validator. No editable-import
compatibility is claimed.

`tool_revision` contains this code checkout's 40-hex Git commit plus `clean`,
`modified` or `unavailable`. Unavailable requires a null commit. Modified checks
tracked/untracked application sources and build/dependency metadata, not plant
data. There is no source digest or caller-supplied revision option. An exported
summary alone cannot identify which private L5X revision was used; retain that
association locally if needed. This tradeoff deliberately limits cross-report
source correlation. Never use the code commit as a source identity.

Only the final `.json` is the published candidate. Exclusive hard-link publication
avoids clobbering existing files. Temporary `.pending` files can remain after an
interruption/cleanup failure and are not shareable results. See the
[work-machine procedure](../reviews/WORK_MACHINE_SUMMARY_RUN.md).

## Implemented source inventory v2

`python-parser/src/plc_workbench/models.py` defines typed source records serialized
by `InventoryResult.to_dict()`. The full report has schema_version 2,
parser_version `source-inventory-2`, analysis_scope `source_structure_only` and
semantic_analysis `not_implemented`. Top-level fields include snapshot metadata,
export attributes, entities, rungs, diagnostics, counts, routine_types,
instruction_counts, coverage and status. This is a private source format,
separate from the sanitized helpers' schemas. External JSON Schema validation
and editable import are not implemented.

Snapshot identity is `sha256:<digest>` of the exact captured bytes. Entity/rung/
instruction IDs hash that identity, kind and occurrence locator. Names are not
keys. Parent/scope links refer to source entity IDs; rung instruction structures
refer to their instruction IDs. Offsets are zero-based, end-exclusive Python
character offsets into decoded rung text, not file-byte offsets. Attributes and
operands are source evidence with no reference or instruction-effect validation.

Module records now include five additional entity kinds: module_port,
module_connection, module_input_tag, module_output_tag and module_config_tag.
Ports and configuration tags link to the module; input/output tags link to their
ordinary connection, which links to the module. All inherit controller scope.
Only the supported Module/Ports and Module/Communications paths create these
records. Similar vendor-extension element names do not become declarations.
Absent Name attributes stay absent; topology-based names belong only to derived
references. RackConnection remains preserved in the snapshot with the explicit
`module_rack_connection_not_analyzed` diagnostic. Its aliases are not ordinary
connection tag records. These new counts do not inflate total_tag_definitions
or tag_aliases.

Coverage accounts for each encountered rung as parsed, failed, unsupported or
excluded; each inventoried routine is parsed, failed or unsupported. Instruction
totals cover parsed RLL rungs only, with an explicit completeness flag. Familiar
element names outside supported containers are preserved without becoming
declarations. Unknown executable XML makes routine coverage incomplete. Generic
unmodeled paths remain counted and original bytes remain available in the snapshot.
`complete` means this structural slice completed, never engineering completeness.

Saved runs contain snapshot.L5X, inventory.json, overview.txt and a v1 manifest
with artifact hashes/sizes. Publish the manifest last and never reuse a prior
run directory. Incomplete directories have no final manifest and must not be
treated as checkpoints. The initial manifest does not store an original file
name/path or parent-run lineage. See [usage](../../../python-parser/README.md)
and [review evidence](../reviews/SOURCE_INVENTORY_REVIEW.md).

The identity/checkpoint proposals below describe later additions; they do not
change the implemented v2 fields implicitly.

## Evidence, interpretation, decision

Keep three layers:
1. Source facts: literal names, expressions, attributes, values, configured schedules, and source locations.
2. Derived findings: parsed structure, reference resolution, classification suggestions, pattern memberships, and translation proposals.
3. Reviewer decisions: accepted/corrected/rejected/deferred interpretations and future target mappings.

An accepted decision is evidence of a review, not evidence that the parser recovered every source construct. Keep parser coverage and human review status independently visible.

## Identity and source references

Use IDs rather than names as joins:
- `snapshot_id`: content identity of the original file bytes plus source-format discriminator. Keep original name/path in the private source manifest.
- `entity_id`: deterministic within a snapshot, derived from snapshot ID, entity kind, and a unique structural locator including scope and ordinal.
- `occurrence_id`: identifies a particular occurrence or multi-node region in one snapshot.
- `pattern_id`: versioned canonical pattern representation and normalization policy.
- `run_id`: unique execution record, with parent runs and input/result digests.
- `decision_id`: immutable human decision, referencing the original finding and its revision.
- `translation_id`: one source-text/context translation record, not an English-string key.

Use a stored source reference on every extracted object: snapshot ID, entity ID, structural path, source ordinal, and raw-payload reference. Tokenized instructions additionally have offsets within the preserved rung text. Source line/column is optional and must be explicitly unavailable if not measured.

Rung Number alone is not stable: inserting a rung may renumber subsequent rungs. A routine name alone is not unique across programs. A hash of rung text alone merges identical occurrences. Use scoped locations and source ordinals to disambiguate.

Across different exports, do not silently reuse entity IDs. Store a correspondence proposal with old ID, new ID, match method, evidence, ambiguity, and review decision. Confirmed correspondences support continuity; unmatched or ambiguous records remain visible.

## Engineering objects and correction survival

Add a persistent engineering-object identity distinct from snapshot-bound source
entity IDs. One equipment object or sequence can refer to multiple source rungs;
one rung can contribute to several engineering objects. Names, spreadsheet row
numbers, UI folders and target unit assignments are attributes, not identity.

Proposed correction records distinguish:

- extraction/classification defects that may justify a reusable rule/code fix;
- object-specific reviewed facts and interpretations;
- target design decisions such as names, grouping, classes and sequence design.

An object-specific correction does not automatically become a global rule.
Promoting it requires an explicit rule change and independent test examples.
Retain the original source value, parser proposal and approved value separately.

On a rerun, preserve the decision history, compute new proposals, and compare the
evidence each decision depends on. An unchanged source/binding can reuse an
applicable decision. Changed dependencies, source splits/merges, missing objects
and ambiguous correspondence go to review with the previous decision attached.
Never silently discard that decision or apply it to an unrelated replacement.
The engineering workspace must expose unresolved decisions before dependent
PCSD/FHX outputs can be considered reviewed.

For example, a reviewed DeltaV name belongs to the engineering object and can
survive moving it between groups. A corrected trip interpretation depends on
the relevant source logic; changing that logic requires revalidation. Splitting
one source rung into two must not silently duplicate a single equipment decision.

The initial workflow is sequential, with one active editor and revision-bound
handoffs. Record the source set, analysis revision and decision head in each
handoff. Compare returned edits against that base and current state, validate
the complete batch, and create a new decision revision after acceptance.
Reimporting the same batch remains a no-op. Reject a stale base with a clear
conflict report rather than replacing newer work. Concurrent copy merging is
a later option; stale-copy detection is required even with sequential review.

There is no fixed reviewer order. A handoff records its sender, selected recipient,
base revision and status; participant identities are not hardcoded stage names.
Keep assignment and routing separate from the initial single-editor policy.
Parsing/analysis services should not depend on a particular reviewer sequence.

## Trace links

A trace link contains:
- source ID(s) and target ID(s);
- relation type, direction, transformation ID/version;
- run and decision IDs;
- mapping details, including omitted or split fields;
- evidence and loss/uncertainty notes.

Relationships are many-to-many. One source tag may map to several target parameters; several source instructions may map to one target object. Reverse navigation queries the same link table. It must never assume the inverse of a dictionary is unique.

Original text and canonicalized text are separate fields. Record a normalization map when canonical tokens merge, split, or replace source tokens. Preserve units, sign, scale, raw literal spelling, and operand role where known.

## Persisted formats

Use UTF-8 JSON for manifests and small structured reports; JSONL for large record collections. JSONL is one JSON object per line, suitable for streaming and later indexing.

Required persisted information:

- versioned JSON/JSONL data;
- immutable original source bytes;
- immutable decision batches;
- human-readable reports regenerated from those records.

Use validated models and generated schemas. Refuse unknown major schema versions; explicit migrations create a new copy with migration provenance. Keep timestamps separate from semantic payloads so deterministic results can be compared without clock noise.

The earlier proposal made JSON/JSONL files canonical and SQLite a later index.
The standalone editor preference reopens that choice. Evaluate SQLite as the
canonical private project store, with explicit versioned history and JSON/JSONL
exchange/report snapshots. Select one authoritative writable store before
implementing editor persistence. JSON contracts are still required for inspection,
review exchange and synthetic regression artifacts; existing helper reports do
not need migration for this planning update.

Backup/restore is separate from review history. A portable private backup must
cover the selected store, immutable source files, decision history, required
attachments and schema/tool versions. Use a consistent database backup mechanism
if SQLite is selected; test restoration with relative links on a fresh workspace.
Define backup destination and retention before relying on it. Restoring an older
backup must not silently replace newer reviewed work.

Avoid pickle for long-lived state. It ties restoration to Python objects and can execute code when loaded.

## Inventory contract

`inventory.json` should provide:
- schema and report versions, case/source/run IDs;
- source software/schema revisions, partial/full context;
- counts of controllers, I/O modules, tasks, scheduled and unscheduled programs;
- routines by language and protection/readability state;
- rungs by routine, source type, and parse status;
- tag declarations by controller/program/AOI scope, aliases, and exported tag kind;
- datatype definitions, referenced built-ins, member counts, and unresolved types;
- AOI definition counts and separate call-site counts;
- instruction counts, including JMP, LBL, JSR, timer, and PID families;
- SFC structure counts where available, with explicit unimplemented metrics;
- unresolved reference counts, unknown constructs, and coverage links;
- artifact paths relative to the run directory for drill-down.

Every metric includes a unit and completeness indicator. For example, `jmp_instructions` counts recognized JMP instructions in the analyzed population, not strings matching JMP in comments. For unreadable or unparsed rungs, total JMP count is unknown; provide a known subtotal and incomplete coverage.

Verbose rendering exposes per-object detail from the same data. A GUI should not need to parse console output.

## Stage accounting

Every stage emits:
- `manifest.json`: inputs, versions, options, parent run(s), status, artifact hashes;
- result JSON/JSONL appropriate to the stage;
- `coverage.json`: totals by unit/population and disposition;
- `coverage_details.jsonl`: per-unit disposition and source reference;
- `ignored.jsonl`: explicit exclusions with reason and policy/rule;
- `errors.jsonl`: structured diagnostics, severity, source reference, remedy;
- `logs/events.jsonl`: operational events;
- concise human report summarizing successes, gaps, and next review work.

Within each declared population, dispositions are mutually exclusive:

```text
encountered = parsed + preserved_unsupported + excluded + failed
```

A stage may have different populations (rungs, instructions, XML attributes). Do not add them together into a meaningless coverage percentage. Track unknown attributes as well as unknown elements. A parsed routine envelope does not mean its instructions have been analyzed.

- Parsed: enough information recovered for the stage's stated contract.
- Preserved unsupported: raw evidence retained; analysis unavailable.
- Excluded: intentional omission under a named policy, with source location.
- Failed: attempted processing did not meet the contract.

Do not mark unsupported syntax as successfully converted. Empty diagnostics files are still written, so a consumer can distinguish no errors from no report. Fatal XML corruption reports a document-level failure rather than fabricated component totals.

## Run lifecycle and reproducibility

Each write creates a unique run directory beneath the confidential workspace. Suggested statuses:
`running -> complete | partial | failed | cancelled`.

Write pending files, validate and hash them, then atomically publish the final manifest. An interrupted run cannot appear complete. A single workspace writer uses a lock; readers use complete manifests. Never silently resume from an incomplete artifact.

A finalized manifest includes:
- original source digests and input snapshot IDs;
- parent run IDs and decision-head ID;
- application version and code revision; dirty code flag and local source digest if uncommitted;
- Python/dependency lock versions;
- parser/catalog/rules/glossary/prompt/model/provider versions;
- options and parameters;
- input/output artifact hashes and dispositions;
- timestamps, status, and duration.

Deterministic stages with identical semantic inputs should produce identical semantic outputs. AI proposals record request/response provenance and are replayed from the stored result for reproducibility; rerunning an AI call is a new run even with the same prompt.

## Review checkpoints and rollback

Create an immutable decision batch for each imported review or GUI save. It references:
- source snapshot and base analysis run;
- expected previous decision-head ID;
- the proposals and original-value digests being reviewed;
- reviewer identity/time, changes, comments, and approval state.

Validate the whole batch before applying. Importing the same batch twice has no effect. A stale base, concurrent change, duplicate ID, or conflicting decision creates a conflict report and leaves the head unchanged.

Undo selects an earlier checkpoint or creates a compensating decision batch. It does not erase evidence. A review branch can explore a different mapping without overwriting another branch.

Git records software history and synthetic expectations. It does not back up ignored `confidential/` data. The private workspace needs its own approved backup and a restore test.

## Translation record

Include:
- exact source text and locale (`fr-CA` where applicable);
- source references and relevant context;
- proposed English, alternatives, uncertain tokens, and reason for abstention;
- model/provider, prompt/glossary version, input digest, response provenance;
- estimated confidence percent (0–100 or null);
- confidence basis (`model_estimate`, `rule_score`, `calibrated`, or unavailable);
- status: proposed / unresolved / approved / corrected / rejected / deferred;
- final reviewer-approved English and reviewer comment.

A percentage is not a measured success probability unless calibrated against reviewed cases. Do not manufacture one when the model/provider supplies none.

Reversibility comes from retaining original text and linked records. English-to-French back-reference may yield several originals; report those candidates rather than arbitrarily choosing one. Applying a future rename is a token-aware, scope-aware transformation with a preview, collision check, and separate decision; never a global text replacement.

## Classification and pattern records

A finding carries one or more labels, evidence entity IDs, subject scope, rule version, score basis, rationale, and review state.

A pattern definition carries an ordered abstract structure, placeholder roles, normalization version, and required/optional context. Occurrences hold exact source entities, placeholder bindings, boundary connections, task context, and match status. Displayed counts are computed from valid occurrences, not maintained independently.

Links from reports and a future GUI resolve these IDs within the selected run. Avoid embedding absolute workstation paths in transferable links.

## Tests for the contracts

- Two same-named routines in different programs never collide.
- Two identical rungs in one routine retain separate occurrence IDs.
- Source whitespace changes produce a new byte snapshot but may retain a matching structural fingerprint.
- Rung insertion generates correspondence proposals, not automatic approval transfer.
- Serialization/load retains required fields, unknown-source references, and Unicode.
- Coverage arithmetic holds for success, exclusions, unsupported content, and failures.
- Reviewer batch replay is idempotent; stale/tampered/conflicting batches are rejected.
- Cancelled or interrupted runs are never selected as complete checkpoints.
- A private workspace copied to a new approved machine can resolve relative artifact links.

These are acceptance requirements, not tests executed by this planning handoff.
