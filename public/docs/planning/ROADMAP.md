# Implementation roadmap and acceptance gates

Status: source inventory and bounded summary export implemented; later milestones remain proposals. Build small complete slices, each ending with a runnable command, a report, tests, and a handoff update. See [current implementation evidence](../reviews/SUMMARY_EXPORT_REVIEW.md).

## Confirmed product phases (2026-10-12)

This is a reusable tool for several units. The product phases below express
Tyler's workflow; they are not the earlier helper Stages 1-5 or the technical
Milestones 0-7 later in this document.

| Phase | Intended outcome |
|---|---|
| 1 - Understand L5X | Analyze rung patterns, loops, alarms, miscellaneous logic, I/O and other information useful for DeltaV mapping. Feed both user-readable scanning/analysis reports and editable engineering records from the parsed evidence. |
| 2 - Editable files | Provide records non-programmers can read and edit, with source links retained while organizing and moving engineering objects. A standalone editor is preferred; Excel remains an exchange/fallback candidate. |
| 3a - Target naming | Adapt names, descriptions and related fields to the desired DeltaV conventions while retaining the source values. |
| 3b - Correct interpretation | Correct classifications, unrecognized data and other extraction/interpretation mistakes. |
| 4 - PCSD and feedback | Build the Process Control Strategy Document and support plant test sheets; import corrections back into upstream engineering records and use them to improve parsing/analysis. Detailed PCSD content follows source understanding. |
| 5 - FHX in both workflows | Generate FHX using the team's class mappings and support reading FHX to produce PCSD. Target class contracts remain to be specified. |

Cross-cutting outputs include reports, unrecognized-rung queues, alarm shutdown
relationships versus warning-only behavior, and alarm rankings. Record evidence
and uncertainty rather than inferring these solely from names. The meaning of
loops and the ranking criteria should be refined with concrete examples.

Review can involve Tyler, Quebec and the development team in any chosen order.
Prefer sequential handoffs initially, with one active editor and revision-bound
packages. Recipients are selected per handoff; routing is separate from the
editing policy. Detect stale returned copies; concurrent editing is a later option.
Tyler handles the L5X-through-PCSD workflow and needs downstream corrections
returned to it. Rerunning any stage must preserve intended fixes. Source and
engineering objects can change or be split, combined, expanded or collapsed;
the tool needs explicit correspondence and unresolved-change review.

Two output paths must remain available from the L5X analysis: readable reports
for investigation, and editable engineering files for PCSD construction. A
report's display layout must not define the engineering record identity.

The prior MOD-to-DeltaV PCSD used Excel. Candidate content covers AI/AO/DI/DO,
selectors, PID flowcharts (PV/SP, master/slave and type), sequences/transitions,
alarms, external references, communication inputs/outputs, standalone Boolean
and floating-point calculations, valves and pumps. See ARCHITECTURE.md for the
discovery questions behind these categories. Source sequences and proposed
target sequences must remain distinguishable. Target modules, units and execution
locations require reviewed mapping rather than copying the source hierarchy.

The preferred editor provides object search, navigation through changes,
import/export and backups without requiring programming or an installed Python
environment. SQLite and executable packaging are proposals to evaluate when that
slice begins; do not build the full editor/database before the source model is
understood. Excel can remain useful for exchanges and generated test sheets.

Across computers, synchronize non-proprietary tools and reviewed development
artifacts. Actual exports and private analysis/review state remain local. Bounded
summary reports and stripped ladder examples can support development without
disclosing enough information to reconstruct the complete process.

The technical milestones below remain an earlier implementation proposal. Their
order and boundaries need reconciliation with these phases before selecting the
next slice. Current implemented baseline: the prototype, inspection helpers and
`plc inspect` source inventory and `plc summarize`, with 56 application tests and 139 helper tests
passing (one additional application test skipped for Windows symlink capability).
Initial Git setup is done. The first slice uses typed dataclasses and bounded
Expat parsing; it does not introduce Pydantic, SQLite or a GUI. The Milestone 1
command names below remain proposals; only `plc inspect` and `plc summarize` are implemented.

## Development and comparison workflow

- Keep each logical change on a focused conventional commit with its rationale,
  validation and limits recorded for the independent reviewing chat.
- Explain non-obvious logic and data contracts in code comments/docstrings; keep
  broader design decisions in the handoff and planning documents.
- For a design question that needs delayed work-machine feedback, agree on one
  common baseline and up to three bounded alternatives. Use sibling branches
  such as `experiment/<topic>-a-pc`, `experiment/<topic>-b-pc` and
  `experiment/<topic>-c-pc` from that baseline. An experiment
  may branch from an existing feature branch; it need not start at main.
- Give each alternative the same test procedure, input selection and comparable
  report contract. Record the tested commit, baseline, tool/schema versions and
  options so results can be attributed even after branch tips move.
- Use separate private output locations for each trial. Provide a short results
  template, expected outcomes and a report path so Tyler can run all alternatives
  in one session. Treat a sanitized return report as a separately reviewed export.
- Keep production-input checks separate from synthetic checks. Minimized samples
  establish structural coverage, not complete source relationships or semantics.
- Compare the returned evidence, then integrate the chosen changes into the
  parent feature branch. Preserve useful negative results and do not merge every
  alternative wholesale. Creating experiments does not authorize pushes/merges.

## Milestone 0 — synthetic baseline and fresh Git

The user has moved real inputs into confidential/ and copied the working files to the new project name without the old .git or Python environment. The old project remains available. Do not repeat the copy or move the inputs.

First:
- review the independently invented fixture under public/fixtures/synthetic;
- run public/tools/check_fixture.py, then its --with-l5x check from the uv project;
- inspect the nine rung texts and the manually drawn parallel branch reference;
- record actual fixture check results in the handoff;
- apply root and nested ignore rules, keeping uv.lock tracked;
- initialize new local Git history and review the staged public/code baseline before committing;
- preserve the old project until the copy, input files, and rebuilt environment are verified.

Follow GIT_FRESH_START.md. No push has been performed. The new repository name and history do not prove code contents are free of confidential information; review them locally.

Acceptance: fixture checks pass on Tyler's machine, supported versus placeholder content is explicit, and the new tracked baseline contains reviewed code/public assets only. The supplied fixture includes an empty SFC envelope rather than claiming full SFC grammar coverage.

## Milestone 1 — package boundaries and JSON inventory

Implement only the small foundation:
- `main.py` compatibility wrapper;
- `src/plc_workbench/cli.py`, `services.py`, `models.py`;
- L5X reader adapter, inventory function, and initial run store;
- `plc ingest`, `plc overview`, and useful help;
- versioned source reference, diagnostic, coverage, and manifest models;
- canonical JSON inventory and records with no terminal parsing required.

Inventory all exported routine types and high-level components. Parse enough neutral instruction syntax to count JMP and other mnemonics accurately where possible. If that syntax work belongs in Milestone 2 for a construct, report a known subtotal with incomplete coverage rather than a guessed total.

Use the existing `l5x` package only through an adapter. Remove third-party argparse/pathlib dependencies on the authorized editing host. Keep the existing reader functions as adapters temporarily; do not preserve two competing data models.

Tests:
- tiny synthetic controller with RLL and SFC envelopes, scoped tags, modules, task scheduling;
- partial export, no-rung SFC, encoded routine, unknown element/attribute;
- duplicate routine names and alias/tag scope;
- --help without source file access;
- exact count definitions and complete coverage accounting;
- input bytes unchanged after processing;
- deterministic semantic report content across two runs;
- paths with spaces and output-root escape rejection.

Acceptance: a user can import one synthetic export, inspect a JSON summary, inspect every gap, and trace a record back to a source locator. No FHX generation.

## Milestone 2 — robust ladder parser and ASCII drawing

Develop a documented neutral-text grammar from official references and manually reviewed synthetic slices. Implement tokens, ordered syntax tree, source spans, and an ASCII renderer.

Synthetic cases:
- series contacts/coils and nested parallel branches;
- empty branch legs and output branches;
- multiple operands, array indices, nested expressions, and quoted escaped strings;
- timer/counter/arithmetic instructions and custom AOI calls;
- labels/jumps and syntax not covered by the original regex tokenizer;
- malformed branches, unmatched delimiters, unknown instructions, empty rungs;
- long labels, narrow terminal width, and unsupported-region fallback.

Use hand-constructed expected trees as the independent oracle, not only parser-to-printer round trips. Compare rendered diagrams with independently drawn expected connections. Property tests can later check parse/serialize/parse stability for the supported grammar.

Acceptance: exact source selection, accurate connections and order, understandable ASCII, explicit partial results, and trace links per instruction. A successful render does not prove runtime semantics.

## Milestone 3 — symbol resolution and execution context

Add scoped symbol tables, aliases, instruction operand roles, read/write indexes, task/program order, JSR/SBR/RET and JMP/LBL edges, and AOI definition/call relationships.

Handle dynamic addressing and unknown effects conservatively. Add multiple-controller snapshots as separate sources; external endpoints remain unresolved unless matched by evidence.

Tests: local/controller name collisions, alias cycles, multiple writers, conditional calls, backward jumps, task boundaries, produced/consumed tags, missing peers, and unknown AOIs.

Acceptance: any tag or rung can show references and relevant control-flow context; unresolved relationships are counted and inspectable.

## Milestone 4 — review checkpoint infrastructure and AI translation

Build generic review records and immutable decision batches before relying on them for classifications or mappings. Implement XLSX export/validate/import with source/run binding and atomic application.

Add the translation-provider interface and a fake provider for tests. Select the real provider and permitted context with Tyler before enabling it. Start with a small internally reviewed set of Quebec French descriptions and acronyms. Keep all actual prompts/responses private.

Tests: Unicode and accents, ambiguous abbreviations, untranslatable text, repeated source phrase in different context, multiple French originals with one English translation, blank versus cleared decisions, malformed AI output, provider timeout, and no implicit acceptance.

Workbook tests: reordered rows, duplicates, missing rows, stale base, modified original fields, invalid confidence, formulas, and reimport. Test a restore on a fresh private workspace copy.

Acceptance: a person can approve/correct/defer translations and recover the exact originals and review history. Confidence estimates are labeled with their basis.

## Milestone 5 — explainable classification and local patterns

Start with a small rule catalog: instruction family, approved tag role, and explicit naming hints. Allow multiple labels and abstention. Distinguish suggested, approved, corrected, and rejected classifications.

Add ordered structural and typed rung patterns with generic placeholders and occurrence bindings. Treat repeated use of the same operand distinctly from two different operands. Include pattern counts and a drill-down report.

Tests: isomorphic synthetic examples, deliberate nonmatches, branch-order differences, contact inversion, timer mode/preset differences, identical names in different scopes, and overlapping matches.

Acceptance: a reviewer can see why two occurrences match, which details were abstracted away, and their exact source bindings. No claim of functional equivalence.

## Milestone 6 — cross-rung motifs and richer analysis

Use validated dependency/control-flow graphs to propose motifs spanning rungs. Include boundary inputs/outputs, scheduling context, loops, stateful instructions, and unresolved communications.

Extend SFC/FBD/ST analysis according to inventory value and reviewed examples. Preserve language boundaries and cross-calls. Profile before choosing a graph library or SQLite index.

Acceptance: cross-rung groups explain their inclusion and boundaries; uncertain execution relationships remain explicit.

## Milestone 7 — GUI as another client

Pick a GUI only after services and result schemas have proven useful. Start with:
- hierarchy browser;
- patterns and occurrences;
- source/ASCII detail;
- findings and coverage;
- translation/review forms;
- checkpoint selection and comparison.

The GUI saves through the same decision services as workbook import. Test cancellation, stale edits, progress, and rendering large result sets. Do not duplicate parsing in UI callbacks.

## Later gate — PCSD feedback, target semantics and FHX

Design conversion separately after enough source examples and reviewed classifications exist. Define supported source behavior, approved target library/version, many-to-many mappings, information loss, and engineering acceptance scenarios.

Define the PCSD import/export contract and preservation of downstream corrections
before generation. Add class-aware FHX reading as well as writing so supported
FHX data can produce PCSD through the same reviewed engineering representation.
Keep imported target facts traceable to their FHX source; do not conflate them
with facts extracted from an L5X snapshot.

Do not emit deployable FHX merely because a pattern matches. Static source analysis and synthetic unit tests are not target-system validation.

## Definition of done for every slice

- One user-facing workflow works end-to-end with synthetic data.
- Report says what was handled, preserved unsupported, excluded, and failed.
- Source trace links resolve.
- Checkpoint format and schema versions are recorded.
- Applicable unit/integration tests pass on an authorized execution host.
- Existing baseline behavior is compared using independently frozen inputs.
- No real data enters tracked fixtures, docs, logs, or CI.
- README/help, decision log, and CODEX_HANDOFF are updated.
- Validation boundaries are explicit: static, synthetic, actual-file, GUI, and runtime evidence are separate.

Only create modules and dependencies needed for the selected slice. Do not implement all planned layers in one refactor.
