# Routine-instruction argument shapes

## Current control-transfer assessment (2026-10-19)

The local investigation is complete for this handoff: the reviewed primary
references establish the operations below, but do not settle the neutral-RLL
field convention or the missing outgoing Boolean rules. Those are specific
vendor/exporter evidence gaps, not questions for an engineer to classify by
judgment. The report now explains the documented operations beside the existing
source evidence. Another run of the unchanged work-PC script can validate the
new report presentation; it cannot establish an exporter convention or measure
an instruction's runtime condition. Historical investigation notes below remain
unchanged and describe the knowledge available at their dates.

The latest observed return is `a5ccae8`, tested clean `a58f3c0`, with
[work51 evidence](../../inspection/work-check-20261019T153207Z-5ce9d78c.json).
Its 219 opaque condition transfers comprise SFR 140, JSR 76, SBR 1, RET 1 and
the separately explained GSV marker. **SBR contributes to the sole opaque coil
guard.** That makes its normal-scan outgoing condition the first semantic
question to resolve. The other control instructions remain worth explaining
even though they contribute to none of the currently reported opaque coil guards.

### What is already available to the reviewer

| Population | Existing source evidence | Documented operation now explained in the dossier |
|---|---|---|
| JSR 76 | Each occurrence's incoming condition, ordered fields, program-local target candidate and exact content association. All 76 associate: 62 RLL and 14 SFC calls, referencing 66 distinct contents. | An enabled call invokes its specified routine; following a normal return, execution resumes after that JSR. The association does not prove that a normal return occurs. |
| SBR 1 | Its exact routine/content, incoming condition and single root-bound lexical field candidate. Eleven calls associate with this content, which also contains the RET. | SBR receives JSR input data and is placed first in the routine. The source field has not been assigned a parameter-destination role. |
| RET 1 | Its exact routine/content, incoming condition and zero captured fields. | Enabled RET ends the subroutine scan and returns any declared data. Zero fields do not make RET a no-op or a Boolean-false result. |
| SFR 140 | Routine/selector and per-content step evidence: all routines have unique candidates and available charts; 139 named selectors match, while one is missing in the requested chart and has a peer-chart diagnostic candidate. | Enabled SFR resets the specified chart to the selected step and stops/resets its stored actions. Selector 0 denotes the initial step; all 140 captured selectors are named. |

The routine operations follow the
[Studio 5000 JSR/SBR/RET reference](https://www.rockwellautomation.com/en-sg/docs/studio-5000-logix-designer/37-00/contents-ditamap/instruction-set/program-control-instructions/jump-to-subroutine--jsr---subroutine--sbr---and-re.html).
The reset operation follows the
[Studio 5000 SFR reference](https://www.rockwellautomation.com/en-gb/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/program-control-instructions/reset-sfc--sfr-.html).
These are generic instruction operations, conditional on applicable normal
execution. The dossiers retain signature, source, target and incoming-condition
gaps; they do not calculate execution, parameter flow, active actions or final
values. The peer-chart SFR candidate is not substituted for the authored target.

This closes the missing explanation of source-understandable operations without
requiring a new execution model. Parameter transfers, path selection, return
timing and chart-state simulation are not computed by the current providers.
Computing them would need additional analysis; it is unnecessary merely to
present the documented operations and captured relationships. No condition
identity, access role, source association or public counter changes in this
documentation/report slice.

### SBR: the highest-priority missing rule

The precise unresolved issue is the outgoing Boolean condition of a legally
placed Logix SBR during normal entry, including any distinction between
preserving the incoming condition and establishing a true entry condition.
Those are hypotheses to distinguish, not interchangeable rules to choose from.
The reviewed combined execution table qualifies its false-input row as applying
to JSR and does not provide a separate SBR truth table. Copying input data and
continuing the routine does not itself specify that table. A captured incoming
condition also does not prove the routine is entered or that the placement is
valid. The SLC/MicroLogix statement that SBR evaluates true is not Logix proof.

The minimum useful vendor answer is a Logix/controller-version-specific rule
for SBR's normal outgoing condition and valid placement, including whether a
false incoming state is legal/reachable there. It must distinguish normal
execution from prescan/postscan. If the rule is restricted to first-instruction
routine entry, a parser implementation must authenticate that exact source
position and complete qualified content before applying it. It must not erase
the separate question of whether a caller executes. This rule could resolve the
reported coil guard; no plant value, equipment name or extra broad sample would
answer it. A controlled execution check can provide version-specific evidence
if vendor text is unavailable, but an offline export alone cannot prove the
Boolean result.

### JSR/SBR field grammar and RET continuation are separate questions

The observed JSR fields are 65 two-field forms with second field exactly `0`,
and eleven three-field forms with a nonzero ASCII-decimal second field. All 87
non-target JSR fields are lexical literals. A count-bearing layout would treat
the second field as metadata; the published neutral-RLL table instead lists
ordinary input/return fields after the routine name. Under that latter reading,
zero could be an input constant. Agreement with callee arities cannot establish
which convention the exporter used or prove call validity.

[1756-RM014D](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf)
has a concrete ladder example with a numeric second JSR field on printed page
210, but no accompanying callee interface that defines its meaning. Its RLL
table omits InputCount on page 215 and prefixes SBR with a routine-name field
on page 220. Its structured-text tables use InputCount and input-only SBR
on pages 294/299. Thus the sole bound SBR field is not yet proven to be either
that published routine-name position or an actual input destination. The current
[FactoryTalk neutral-ladder table](https://www.rockwellautomation.com/en-us/docs/factorytalk-design-studio/current/contents-ditamap/code-editor-dsl-syntax/neutral-text-for-ladder-instructions.html)
does not resolve the discrepancy for this Studio 5000 export. No ST or newer
FactoryTalk DSL convention is silently transferred into the RLL parser.

A minimal independently invented, verified Studio 5000 export can resolve this:
record known editor input/return counts of 0/0, 1/0, 2/1 and 0/1, using distinct
nonzero input constants and distinct return tags, together with each callee's
SBR/RET. Include the software build, import/export revision and controller
family/firmware; compare them with the existing private snapshot metadata or
explicitly document the supported version range. Export the editor-created
logic and verify a re-import. Hand-authored neutral text or another plant return
with the same field histogram supplies no independent serialization oracle.
This is a targeted tool experiment, not an additional proprietary sample request.

RET termination itself is documented and exposed now. The missing analysis is
which enabled return is reached and where that invocation resumes; an outgoing
Boolean false would incorrectly model subsequent instructions as scanned false,
while an identity would imply ordinary continuation through the RET. JSR's
normal-return statement likewise does not prove completion or return timing.
For the 14 SFC targets, qualified absence of SbrRet is captured; it is not an
execution model. [1756-PM006L, printed page 47](https://literature.rockwellautomation.com/idc/groups/literature/documents/pm/1756-pm006_-en-p.pdf)
describes both active-step and until-false-transition execution settings, which
affect return timing and parameter update points. The report therefore gives
the documented conditional continuation without selecting a runtime path.

### SFR and the general output rule

SFR's reset operation is known; the remaining semantic gap is its local
outgoing RLL condition, not the meaning of the two source fields. The reviewed
SFR execution table specifies the reset for true input and no action for false
input, but gives no outgoing-condition equation. A future admission needs an
applicable vendor statement that establishes that equation, including its
normal-completion scope. It does not need another histogram of the 140 calls.
The separate missing named target remains a source discrepancy for review; a
peer-chart match is neither a correction nor evidence that a reset succeeds.
The Logix reference expressly distinguishes its behavior from PLC-5's held-reset
behavior; that older behavior cannot supply the missing rule.

[1756-PM008J, printed pages 11–12](https://literature.rockwellautomation.com/idc/groups/literature/documents/pm/1756-pm008_-en-p.pdf)
provides the generic output-instruction identity rule. The action description
alone does not settle its application to each control-transfer boundary; RET
in particular changes continuation. The primary review did not find an explicit
Logix SBR truth table or an instruction-specific JSR/SFR outgoing equation that
would justify admitting these occurrences under the current condition contract.
This is a recorded evidence limit, not a claim that every vendor publication or
support article has been proved silent.

### Handoff conclusion

The available local records and targeted primary-document search are exhausted
for these narrowly stated gaps: RM014D language-specific tables and ladder
example; Studio 5000 37/38 instruction help and its execution tables; PM008J's
general rule; and PM006L's SFC interface/return settings. The independently
testable next inputs are the version-recorded exporter example for field grammar
and applicable vendor semantics or a separately controlled execution check for
outgoing conditions, prioritized SBR first. No additional plant capture is
requested, and frozen sample history/budget stay unchanged. The next unchanged
work-PC run verifies the software and new explanatory views only; it cannot
close those external evidence questions. All earlier schemas and transfer
classifications remain intact.

Date: 2026-10-14. Branch: `feat/bounded-operand-example-pc`.
Returned baseline: `08c2695`, testing clean `bdf09f1`.

## Returned evidence and the next question

[The returned bit report](../../inspection/work-check-20261014T205025Z-cc9c4184.json)
confirms all 26 MVM/SWPB instructions: catalogued increases 17,591 to 17,617,
unsupported instruction slots fall 597 to 519, root_bound increases by 52,
literals by 16 and non_data by ten. Its 296 application cases (one skip) and
139 helpers passed. The report-only commit has the tested revision as parent,
records clean code and a saved private run. Independent full comparison found
no unexpected changes. See [the confirmed bit review](BIT_OPERATION_REVIEW.md).

The next source-context question is how routine calls use their argument fields.
The public histogram contains JSR=76, SBR=1 and RET=1. All remain outside the
binding catalog. Understanding these instructions will prepare routine links
and eventually help distinguish conditional execution and sequence context.
It does not by itself identify process transitions or execution reachability.

## Why parameter roles are deferred

The actual [Logix Import/Export reference](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf),
Publication 1756-RM014D-EN-P, shows different language-specific layouts:

| Instruction | RLL neutral table | Structured-text table |
|---|---|---|
| JSR | Routine name, inputs, returns (printed page 215) | Routine name, InputCount, inputs, returns (page 294) |
| SBR | Routine name, inputs (page 220) | Inputs (page 299) |
| RET | Returns (page 220) | Returns (page 299) |

The [Studio 5000 routine-instruction help](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/program-control-instructions/jump-to-subroutine--jsr---subroutine--sbr---and-re.html)
describes optional parameters and their source/destination roles. Its generalized
form does not resolve the neutral-table differences. An independent explorer
opened the primary manual/help and identified this evidence gap. A second field
spelled zero cannot yet be claimed as a validated zero-input RLL signature.
Do not silently transfer the structured-text layout into the ladder parser.

Routine targets belong to the owning program according to the official
[task/program/routine guidance](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/studio-5000-logix-designer/controller-organizer/use-the-controller-organizer/use-tasks--programs--and-routines.html).
The inventory already preserves program/routine identities and attributes for
later scoped linking. This slice performs no target resolution and does not
put routine names into the tag-symbol namespace.

## Implemented observations

`routine_shapes.py` derives fixed counts from successful parsed RLL instruction
records. It recognizes only ASCII JSR/SBR/RET opcode spellings, ignoring case,
and emits no per-instruction rows or source strings. Public reference schema 9
adds `routine_instruction_shapes` with fixed metadata: analysis_scope is
parsed_rll_routine_instruction_fields; parameter_roles and target_resolution are
not_analyzed. `by_opcode` contains exactly JSR, SBR and RET.

Every group has total, argument_slots, noncanonical_spelling and by_arity.
Noncanonical spelling counts recognized mixed/lowercase opcodes that source
schema 4 pools into its withheld bucket. JSR bins are zero_fields, one_field,
two_fields_second_zero, two_fields_second_other, three_or_more_second_zero and
three_or_more_second_other. SBR/RET bins are zero_fields, one_field, two_fields
and three_or_more. The zero observation means the second argument, trimmed,
is exactly ASCII text `0`; `00`, `+0`, `0.0`, quoted zero and Unicode lookalikes
remain other. Empty second fields also belong to other. No parameter-count,
source/destination, datatype or call-validity meaning is assigned.

Closed validation requires strict nonnegative integers, exact keys/constants,
partition totals and arity/slot lower bounds (exact slots when no larger-arity
bucket is present). Each total equals its uppercase source opcode count plus
noncanonical_spelling; the combined spelling count cannot exceed the source
withheld pool. Call totals cannot exceed uncatalogued instruction coverage;
slots cannot exceed total operands or unsupported-instruction slots. These
checks prevent reusing the withheld pool independently for every opcode.

Private text receives the captured inventory through the CLI/storage render
path and prints the same observations, including zero-field SBR/RET calls that
operand rows alone cannot represent. The existing renderer API without an
inventory still works. Private reference JSON and its canonical result are
unchanged. No source file is reread for this diagnostic.

## Contracts and sharing

Public references are schema 9 / reference-summary-9, with analyzer
source-references-7 unchanged. Private references stay schema 4; source inventory
3, source aggregate 4 and manifest 2 retain their layouts. Work schema 7 /
work-check-7 requires reference 9. Work3/5, work4/6, work5/7 and work6/8 pairings
remain frozen, and work1/2 retain supported nested-reference handling.

Reference versions 1 through 8 retain exact fields and constants, rejecting even
an all-zero routine_instruction_shapes field. Version 8 and 9 share analyzer 7
because binding behavior did not change. Existing timer/flag/selector sample
rules, statuses and bounds are retained.

The additional field contains only fixed observational counts. It adds no routine
names, raw arguments, source/rung IDs, hashes, locations, neighboring logic or
relationships. The publication cap and single bounded mystery sample remain
unchanged. Private outputs stay local; report commits remain automatic and
pull/push manual. The listener stays disabled and untracked.

## Validation and next work-machine check

Synthetic coverage includes zero-field and larger-arity calls, exact zero versus
other spellings, empty slots, case/withheld accounting, failed-rung/ST exclusion,
unchanged bindings/catalog/private JSON, saved private text, public privacy,
strict types/fields/invariants and actual historical report compatibility.

Final development validation: **404 application/workflow cases**, OK with one
existing Windows symlink-capability skip; ignored listener loader excluded.
The core module passed ten new cases and the existing summary suite passed 76.
Independent review passed 68 focused cases, checked the actual CLI text boundary
and found no blockers. All twelve committed work reports validate unchanged.

The full development command, from the repository root, was:

```bash
uv run --project python-parser --locked python -B - <<'PY'
from pathlib import Path
import sys, unittest
folder = Path.cwd() / 'python-parser/tests'
sys.path.insert(0, str(folder))
loader = unittest.TestLoader()
suite = unittest.TestSuite(loader.loadTestsFromName(path.stem)
    for path in sorted(folder.glob('test_*.py'))
    if path.stem != 'test_feedback_listener')
result = unittest.TextTestRunner(verbosity=1).run(suite)
raise SystemExit(not result.wasSuccessful())
PY
```

An independent workflow agent used a disposable clean checkout with no remotes,
current tracked bytes and the new module/test. Its invented rack fixture adds
two routine calls (one lowercase), a zero-field SBR and zero-field RET. Total
instructions rise 5 to 9 while catalogue coverage stays 5; four new operand
slots remain unsupported_instruction. Every other operand, alias, rack, module
and symbol count is unchanged. Observations are JSR total2/slots4/noncanonical1,
with one two-field second-zero and one second-other; SBR/RET each total1/slots0/
zero_fields1. These facts assign no parameter or target semantics.

Actual commands were:

```bash
bash ./run-work-check.sh RoutineSynthetic.L5X
bash ./run-work-check.sh
uv run --project python-parser --locked plc references \
  confidential/plc-code/RoutineSynthetic.L5X --format text \
  --workspace confidential/workspaces/cli-routine
```

Both launchers exited 0, each passing **308 application cases (one skip) and
139 helpers** without failures/errors. Direct CLI returned the expected partial
exit 3. Public schemas are work7/reference9/source4; private inventory/reference/
manifest stay3/4/2 with analyzer7. Actual CLI and all three saved references.txt
reports include zero-field observations. Private JSON has its exact unchanged
structure and no new shape field. All fifteen artifact hashes across three
manifests verify; prior outputs and the input remain intact.

Disposable report-only commits `6a25336a4857` and `dc9b9ee41d9b` cite their clean
tested parents and leave a clean checkout. Git traces contain zero fetch/pull/
push commands. All 81 copied code/test/config files match final working bytes;
five Python test files were normalized to repository LF without semantic changes.
No project confidential input or listener execution was used.

All 58 relative Markdown links in changed documentation resolve, and
`git diff --check` passes. Historical report files remain untouched.

The next real report should preserve every existing binding, catalog, source,
alias/rack, flag/sample and diagnostic counter. It should add shape groups with
JSR=76, SBR=1 and RET=1 if the export is unchanged. Their field distributions
are unproven until the run. Inspect which JSR arities and second-zero spellings
dominate, and SBR/RET field counts, before choosing scoped routine links or a
further bounded export-format clarification. Shape agreement alone does not
prove parameter roles. No repeat bit/math-only check is needed.

## Returned work-machine confirmation (2026-10-14)

Commit `0a2610f` adds only
[work-check-20261014T212041Z-8cac2026.json](../../inspection/work-check-20261014T212041Z-8cac2026.json)
and has tested clean `9c56b50` as parent. The work7/reference9/source4 report
validates; all 308 application cases (one skip) and 139 helpers pass. JSR=76
and argument_slots=163: 65 two-field second-zero calls, 11 larger second-other
calls. Slot reconciliation proves those eleven have exactly three fields. SBR
has one occurrence with one field; RET has one with zero fields. Noncanonical
spelling counts are zero. All preceding source/reference/diagnostic counters
are identical. Analysis remains partial with private results saved and sample
null. Aggregate agreement does not prove source byte identity or parameter roles.

The next slice uses only the JSR first-field routine name shared by both official
layouts, deriving separate program-local declaration candidates. It leaves later
arguments and all tag/catalog counts unchanged. Read
[the candidate review](ROUTINE_TARGET_REVIEW.md) for the current contracts,
validation and next work-machine check. No repeat shape-only run is needed.

## Exact routine-content boundary observations (2026-10-19)

Execution-context schema 2 adds a source diagnostic to the existing program-local
JSR candidates. Each direct RLL content has one shared profile containing its
source location, exported attributes, parsed-rung counts and exact SBR/RET
occurrence links. Each call retains a separate association result. A unique
routine candidate with one qualified, complete RLL content can be associated;
missing or multiple contents, unsupported language, namespace, protection and
incomplete-source cases remain explicit. Multiple RET occurrences remain a
population; no return path or active edit is selected. Shared content profiles
avoid copying the same boundary population into every repeated call.

Every JSR/SBR/RET field keeps its existing occurrence and operand identities and
source position. JSR field zero is the routine target. Later JSR fields and all
SBR/RET fields receive only a lexical disposition: literal, empty, root-bound
candidate, unresolved, ambiguous, alias cycle/depth, unsupported address or
source-qualification gap. Program shadowing and alias declaration scope use the
existing resolver. A root candidate and suffix do not validate the suffix,
datatype, parameter direction or call signature, and they do not change the
original unsupported-instruction operand classification.

The closed public summary counts qualified content populations, call association
and boundary-presence profiles, lexical dispositions, and call field shapes
weighted by whether their exact target content contains SBR or RET. A separate
second-field spelling partition distinguishes absent, empty, exact ASCII zero,
other ASCII decimal and other text. This can distinguish calls whose source
targets contain boundaries from calls whose source targets do not. It cannot
establish an input count or pair fields across instructions.

The primary-source distinction above remains unresolved. The current
[neutral-ladder reference](https://www.rockwellautomation.com/en-us/docs/factorytalk-design-studio/current/contents-ditamap/code-editor-dsl-syntax/neutral-text-for-ladder-instructions.html)
still lists inputs and returns without the structured-text InputCount field.
The accessible [Studio 5000 version 37 help](https://www.rockwellautomation.com/en-sg/docs/studio-5000-logix-designer/37-00/contents-ditamap/instruction-set/program-control-instructions/jump-to-subroutine--jsr---subroutine--sbr---and-re.html)
labels InputCount in its structured-text syntax. These sources do not justify
importing that layout into captured RLL text. Parameter transfer, call validity,
types, outgoing rung conditions, invocation order and runtime effects remain
unmodeled. A future bounded export-format diagnostic may resolve the neutral
serialization convention; these counts alone cannot do so.

The opt-in API is `analyze_execution_context(..., schema_version=2)`; omitted
version and schema 1 retain their frozen canonical bytes and field sets.
Validation replays the supplied version against the captured source. The private
limit remains 16 MiB with at most 250,000 records and one million evidence links,
including the existing model. Links are reserved before copying, each retained
row replaces its temporary byte reservation, and final serialization enforces
the exact byte limit. The public summary remains 8 KiB and source-free, with
closed enums, strict integers, exact partitions and shared-population bounds.
The new bundle uses review 32 / manifest 35 / work 50; historical bundles retain
their existing versions. This adds source context and does not close R3.

Invented fixtures cover repeated calls, multiple returns and edit contents,
missing/malformed bodies, program scope and duplicates, qualified/protected
source, aliases and shadowing, field spelling, canonical replay mutations,
pre-retention link/byte limits, final exact byte limits and closed public
conservation. The legacy fixture remains 9,877 private bytes and 4,047 summary
bytes with the same SHA-256 digests as schema 1 before this change.

Focused validation passed 38 source-boundary, legacy execution and summary
cases. Seven new rendered-DOM checks cover call/content/boundary navigation,
lexical field links, generic message selectors, AOI and GSV condition evidence,
PID incoming context and the prior saved bundle. The 21 existing condition-DOM
checks and the legacy execution HTML boundary check also passed. The report
adds these details within existing dossiers, with no identifier-free navigation
groups; source positions still assign no transfer roles. Optional Node-based DOM
checks remain development tooling, outside the guarded work-machine registry.

## Returned source boundaries and SFC declarations (2026-10-19)

Return `908873f` adds the clean `3a4d997` work50 result
[work-check-20261019T140719Z-904afb98.json](../../inspection/work-check-20261019T140719Z-904afb98.json).
Its 164 observed fields reconcile as 163 JSR fields plus one SBR field and zero
RET fields. The JSR total is `65 * 2 + 11 * 3`: 76 routine targets and 87 literals.
The sole SBR field is a root-bound candidate. All eleven larger calls associate
with the single content containing SBR and RET. Another 51 calls associate with
51 different RLL contents without either boundary. These 62 calls therefore
reference 52 distinct associated contents. The remaining 14 calls target unique
SFC routines, which execution2 reports as unsupported language. The separately
validated SFC capture contains 14 complete contents and no Subroutine/Return
elements. These are source populations, not execution or reachability claims.

The current [import/export manual, 1756-RM014D](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf)
contains a concrete L5X ladder example on printed page 210:
`JSR(DayOfWeek,1,TestDateTime,Test_Result)`. This is primary evidence of a numeric
second field in RLL. It does not define that field or show the callee interface;
the neutral-text table on page 215 still omits an explicit count field. The
returned spelling partition does not reveal the values of the eleven nonzero
decimal fields. Neither the example nor matching source arities establishes the
calling convention. A small independently invented Studio 5000 export with known
editor input/return counts would resolve the exporter question more directly:
zero/zero, one/zero, two/one and zero/one, with distinguishable input literals.
A hand-authored fixture cannot prove the exporter convention. This remains a
parser/documentation question, not an engineering-only decision.

The same manual's printed pages 269–270 identify the SFC `SbrRet` element and
its comma-separated `In` and `Ret` attributes. The
[SFC programming manual, 1756-PM006L](https://literature.rockwellautomation.com/idc/groups/literature/documents/pm/1756-pm006_-en-p.pdf),
printed page 47, describes that element as the SFC parameter interface. This
supports capturing declared interface presence or absence without interpreting
the RLL fields.

Execution schema 3 adds that exact source join through the existing opt-in API,
`analyze_execution_context(..., schema_version=3)`. It derives canonical SFC
source records from the immutable snapshot and authenticated inventory; callers
do not supply a new dependency. A unique program-local routine target can
associate with one qualified, complete SFC content. Its profile is `sfc_absent`
or `sfc_declared`. Missing/multiple contents, multiple interface declarations,
namespace/protection gaps, incomplete structure and unsupported context remain
separate dispositions. No content edit or declaration is selected from competing
candidates. Unsupported source captured elsewhere cannot establish absence.

Private content rows retain their language, canonical SFC content link and exact
declaration links. Each declaration is retained once, with its canonical SFC
element link, source locator, raw attributes and separate missing/empty/nonempty
`In` and `Ret` observations. Text is not split into transfers, resolved to tags or
checked against JSR fields. Repeated calls share content and declaration evidence.
The browser labels SFC boundaries explicitly and links both the exact chart
content and each declaration; existing RLL dossiers retain their presentation.

The public summary adds closed content/target-language partitions and declaration
populations. It conserves links and records, rejects qualified contents with
multiple interfaces, and requires enough distinct contents for mutually
exclusive associated profiles. Program-only execution populations can be bounded
by the SFC capture but cannot generally equal it: SFC capture also includes
AOI-owned routines. Schema 1 and 2 keep their frozen fields and canonical bytes;
signal-context replay authenticates schema 3, and execution/signal inputs accept
condition versions 3–6 without changing condition semantics.

Limits remain 16 MiB private JSON, 250,000 records, one million evidence links
and 8 KiB public summary. Link reservations precede retained lists and final
serialization checks exact bytes. A conservative maximum-width public rendering
with every count at its six-digit capacity and full revision metadata is 8,136
bytes. The representative schema2 fixture stays 14,843 private bytes and 6,432
public bytes with its frozen SHA-256 values. No historical sample changes.

For unchanged source populations, execution3 should report 68 content rows
(54 RLL and 14 SFC), 76 associated calls, 66 distinct associated contents,
14 `sfc_absent` call profiles, zero SFC declarations and zero unsupported-language
call results. These are expected next-return counts, not an observed plant run.
RLL field dispositions and SBR/RET occurrences should remain unchanged. The
new bundle uses review33 / manifest36 / work51 and adds no raw sample request.

Focused validation passed 76 execution, closed-summary, signal-replay and DOM
cases, including 16 new source/summary regressions and two new SFC navigation
checks. An initial DOM assertion expected an empty table where the renderer
correctly supplies an empty state; it was corrected before the passing run.
Independent summary review also prompted explicit regressions for duplicate
interfaces reported as qualified and incompatible profiles sharing too few
qualified contents. The optional Node checks remain outside guarded work-machine
tests. No full-suite result is claimed here.

Outgoing rung-condition behavior remains separate. The
[ladder programming manual, 1756-PM008J](https://literature.rockwellautomation.com/idc/groups/literature/documents/pm/1756-pm008_-en-p.pdf)
gives a general output-instruction rule on printed page 12; it does not itself
classify these control-transfer instructions or resolve their exceptions. Current
Studio 5000 JSR/SBR/RET and SFR execution tables do not state an explicit outgoing
Boolean equation for each instruction. No SLC/MicroLogix SBR rule, PLC-5 SFR
behavior, structured-text signature or observed count agreement is imported as
Logix RLL proof. Parameter mapping, control-flow propagation and R3 remain open.
