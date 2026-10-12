# Data contracts, traceability, and checkpoints

Status: proposed contracts, updated 2026-10-12. Final schemas are to be implemented and versioned in a selected development slice.

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
