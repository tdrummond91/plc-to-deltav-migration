# Normal-scan condition transfer

The [current control-transfer assessment](ROUTINE_CALL_SHAPE_REVIEW.md#current-control-transfer-assessment-2026-10-19)
records the completed local documentation investigation for JSR, SFR, SBR and
RET, the operations now explained in their existing report dossiers, and the
specific vendor/exporter evidence still needed. SBR has priority because it is
the sole remaining opaque coil-guard contributor. Source links and operation
notes do not supply an outgoing Boolean rule; condition schemas remain unchanged.

## C13 returned GSV marker remains unresolved (2026-10-19)

Return `a5ccae8`, tested clean `a58f3c0`, confirms the condition6 AOI proof now
models the single custom occurrence. The remaining 219 opaque transfers are
SFR 140, JSR 76, and one each GSV, SBR and RET. Four GSV signatures are modeled;
the fifth has `instance_syntax` with `question_mark: 1`. The sole opaque coil
guard still has SBR as its contributor; GSV contributes to none of those guards.

Rockwell's [Studio 5000 Routine Display help](https://www.rockwellautomation.com/en-ca/docs/studio-5000-logix-designer/37-00/contents-ditamap/studio-5000-logix-designer/ladder-editor/components-of-the-ladder-editor-routine-window/routine-display.html)
describes `?` as the marker showing where to enter an instruction operand.
Its [GSV/SSV reference](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-03/contents-ditamap/instruction-set/input-output-instructions/get-system-value--gsv--and-set-system-value--ssv-.html)
requires an instance name when the selected object needs one. The
[GSV/SSV argument-dialog reference](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-01/contents-ditamap/studio-5000-logix-designer/structured-text-editor/enter-structured-text-logic/argument-list-dialog-box-overview/argument-list-dialog-box---gsv-ssv-instruction.html)
likewise makes instance selection conditional on the object class. The
[Import/Export manual, 1756-RM014D, printed page 215](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf)
lists the four neutral-RLL fields but supplies no question-mark exception.
These references do not establish that an exported `?` is equivalent to an
omitted, unused instance field. The editor-marker description also does not
prove this particular exported instruction invalid.

The approved diagnostic and targeted samples contain no GSV instruction. The
public evidence therefore identifies the rejected instance form without
identifying its object class or attribute. Those fields remain in the private
source; their absence from public samples is not a source-capture failure.
Class and attribute evidence alone would still leave the neutral-text marker
interpretation unresolved under the reviewed references.

The GSV stays `opaque_transfer` with `signature_unresolved`,
`gsv_signature_status: instance_syntax` and `gsv_instance_gap_form: question_mark`.
No substitution, class guess or new transfer rule is applied. An admission
would require evidence that this neutral-text form is supported for the
applicable object and attribute, followed by a newly versioned rule. This
review adds no schema, public counter or source-sample request. Schemas1–6,
default behavior, frozen samples and the existing sample budget remain intact.
The existing synthetic rejected-instance regression explicitly checks `?`
and keeps its outgoing transfer opaque.

## Condition6 metadata and first-failure diagnostics (2026-10-19)

Return `908873f`, tested clean `3a4d997`, reports the same 220 opaque transfers:
the custom occurrence has `body_unqualified`, and one of five GSV occurrences
has `instance_syntax`. The approved `public/xml-value-profile.json` already
records direct `RevisionNote` and `AdditionalHelpText` children on the single
AOI definition. Condition5 rejects either child at its definition envelope,
before inspecting the arithmetic body. A routine `Description` was already
accepted and is not the identified omission. The profile is earlier structural
evidence, not proof that the latest private source has identical bytes or that
all later proof gates pass.

Rockwell's [Import/Export manual, 1756-RM014D, printed pages 96–99](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf)
identifies AdditionalHelpText as user-help metadata and RevisionNote as revision
information. Its XML structure explicitly includes AdditionalHelpText; its
RevisionNote description appears in the attributes table. The approved XML
profile supplies the observed leaf-element representation of RevisionNote.
Condition6 permits these two optional metadata elements alongside Description
only when each is unique, has no attributes or child elements, and passes the
existing full namespace and protection qualification. Metadata text is neither
copied into the proof nor published. Unknown elements, duplicated metadata and
nested or attributed extensions still fail closed. Routine Description receives
the same unique-leaf check. The entire scalar arithmetic and own-scope write
proof remains required; accepting metadata alone never establishes identity.

The private custom node adds `aoi_body_gap_reason`, null except when its status
is `body_unqualified`. The public `aoi_body_gap_reasons` map partitions that
status by the first failed body gate, in this order:

- `definition_content`: direct text or an unrecognized definition child.
- `metadata_shape`: duplicated, attributed or nested definition metadata.
- `container_cardinality`: Parameters/Routines are not unique, or LocalTags repeats.
- `scan_flag_syntax`: an optional-scan flag has a value outside true/false.
- `scan_enabled`: an optional-scan flag is true.
- `container_content`: a declaration/routine container has unexpected content.
- `routine_count`: the definition does not own exactly one routine.
- `routine_identity`: the routine is not named Logic and typed RLL.
- `routine_content`: the routine lacks a unique RLLContent or has other content,
  including malformed Description metadata.
- `content_shape`: RLLContent contains direct text or a non-Rung child.
- `rung_count`: no body rungs are retained, or inventory/raw-child counts differ.
- `rung_content`: a rung does not have the expected Text/Comment envelope.
- `rung_parse`: a structurally qualified body rung did not parse.
- `rung_type`: a parsed body rung is not ordinary Type N.

Earlier definition/call/instance/parameter qualification failures do not enter
this map. Instruction and binding failures remain in their existing status bins.
Repeated calls count separately; definition inspection remains cached. The sum
of the new body bins must equal `aoi_identity_statuses.body_unqualified`.
Optional-scan flag admission retains the prior lexical requirement; this change
does not infer behavior from an absent optional routine or broaden numeric flag
spellings.

The GSV rule is unchanged. Official [GSV/SSV examples](https://www.rockwellautomation.com/en-id/docs/studio-5000-logix-designer/37-00/contents-ditamap/instruction-set/input-output-instructions/gsv-ssv-programming-example.html)
show named objects, while singleton-object examples leave the instance blank.
These references do not establish that literal 0 or a question mark is an
equivalent neutral-RLL spelling. The returned first-failure status alone does
not reveal the rejected instance form, so neither spelling is newly admitted.
For GSV nodes only, `gsv_instance_gap_form` is null unless the existing first
failure is `instance_syntax`. The public `gsv_instance_gap_forms` partitions
that failure into `zero_literal` (exact stripped 0), `other_integer` (signed or
unsigned decimal digits, including other zero spellings), `question_mark`,
`quoted` (matching single/double outer quotes), `program_qualified` (ASCII
Program: prefix), and `other`, in that precedence order. These are lexical
observations, not instance validity or runtime meaning. No source token becomes
a public key. The bins sum exactly to `gsv_signature_statuses.instance_syntax`.

Schemas1–5 and default schema1 remain frozen. Condition6 uses the existing
32 MiB private, 250,000-record, 2,000,000-ID and 8 KiB public bounds. Its
conservative maximum-width public payload is 7,842 bytes. Tests cover every
new reason, metadata qualification and downstream write rejection, repeated
calls, GSV gate precedence and rejected forms, private canonical replay,
closed-summary conservation, exact serialization limits and frozen schema5
private/public hashes. This bundle requests no new source sample and makes no
sample-history or budget change.

## Condition5 bounded AOI identity proof (2026-10-19)

Return `883002a`, tested clean `7dcc4fa`, reduced opaque transfers from 326 to
220: SFR 140, JSR 76, and one each GSV, SBR, RET and withheld custom instruction.
The sole opaque coil guard has SBR as its contributor. Condition5 does not
change those built-in control-flow transfers. Rockwell's
[JSR/SBR/RET reference](https://www.rockwellautomation.com/en-sg/docs/studio-5000-logix-designer/37-00/contents-ditamap/instruction-set/program-control-instructions/jump-to-subroutine--jsr---subroutine--sbr---and-re.html)
documents call, parameter and return behavior without an explicit Logix SBR
outgoing Boolean rule. The
[SFR reference](https://www.rockwellautomation.com/en-gb/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/program-control-instructions/reset-sfc--sfr-.html)
describes reset and stored-action effects, not a general outgoing condition.
Rules from older controller families and the generic output rule are not
substituted for these control-flow instructions.

Rockwell's [Add-On Instructions manual, 1756-PM010N, printed pages 49-50](https://literature.rockwellautomation.com/idc/groups/literature/documents/pm/1756-pm010_-en-p.pdf)
states that EnableOut normally follows EnableIn, but AOI logic may override it.
False EnableIn forces EnableOut false even when an EnableInFalse routine runs.
Condition5 therefore proves identity only for an explicitly restricted source
body that cannot write either enable parameter. The proof establishes the local
normal-scan Boolean transfer subject to the existing fault, execution-completion,
asynchronous-change and scheduling exclusions. It does not prove values, outputs,
physical behavior or equivalence of the AOI's calculations.

Admission requires all of the following:

- A unique AOI name within the call's controller, without an AOI/UDT type-name
  collision; a namespace-qualified definition and complete descendants with no
  protection or encryption markers, including markers with false/empty values.
- A parsed ordinary rung in a program, with exactly one simple scalar instance
  argument. Its unaliased tag must bind uniquely and have the matching AOI type.
  Nested calls, members, array instances and non-program scopes are excluded.
- Unique EnableIn/Input and EnableOut/Output BOOL parameters, both hidden and
  optional. Every other parameter must be optional Input or Output. Parameters
  and local tags must have unique valid names and no aliases. Parameters use
  native scalar BOOL/SINT/INT/DINT/REAL; local tags additionally permit LINT.
  Native type-name shadowing is excluded. The Input/Output parameter list follows
  PM010N printed page 34 rather than assuming every native local type is valid.
- Exactly one routine, named Logic and typed RLL, with exactly one complete
  RLLContent. All body rungs must be ordinary and fully parsed. Optional scan
  routines, enabled optional-scan flags, foreign/unknown executable envelopes,
  protected regions, malformed bodies and omitted normal Logic are excluded.
- Every instruction must have an authenticated classified signature in the
  explicit ABS/ADD/CLR/CPT/DIV/LN/MOV/MUL/SQR/SUB catalogue. All data reads and
  writes, including expression leaves, must bind to native scalar parameters
  or locals in that definition, without aliases or suffixes. Numeric literals
  and the existing bounded CPT arithmetic grammar are allowed. No write may
  target EnableOut or EnableIn. Predicates, stateful operations, bulk operations,
  nested calls and unsupported instructions are excluded.

An authenticated exact write to EnableOut is reported as `explicit_override`,
including a classified write instruction outside the allowlist. This is source
write evidence, not proof that its rung executes or changes the runtime value.
The first blocking check supplies one diagnostic disposition; an earlier gap
can prevent a later write from being inspected. No absence-of-write claim is
made for failed proofs. The implementation uses snapshot, inventory, references
and access evidence already authenticated by conditions, without depending on
the downstream AOI or file-operation providers.

The private transfer node retains fixed proof fields: disposition, declaration,
instance, Logic routine and EnableOut IDs, plus checked instruction/write counts.
Definition inspection is cached once; repeated calls retain their own occurrence
and incoming graph edge without expanding the body. Proof records are bounded
before retention, and their IDs and bytes also enter the final graph budget.

The public summary adds `passthrough_opcodes.custom` and the fixed
`aoi_identity_statuses` map. Its categories are `modeled`, `explicit_override`,
`definition_unavailable`, `source_unqualified`, `protected`, `call_unqualified`,
`instance_unqualified`, `parameter_unqualified`, `body_unqualified`,
`instruction_unsupported` and `write_unqualified`. The last category includes a
read-binding gap that prevents the strict scalar-body proof. The population is
every parsed occurrence outside the ASCII public opcode vocabulary, including
calls for which no definition exists. `modeled` equals custom passes; all other
categories sum to `opaque_opcodes.withheld`. Unknown names never become keys.
Cross-summary checks subtract custom passes from the classified-access bound
and charge them against the source histogram's withheld population. Overlapping
opaque-guard contributor counts retain condition4 semantics.

Schema5 also explains every GSV occurrence with the fixed
`gsv_signature_statuses` map: `modeled`, `argument_count`, `empty_field`,
`class_token`, `instance_syntax`, `attribute_token`, `destination_syntax`, or
`namespace`. Qualification is checked first, followed by arity, nonempty required
fields and lexical class/instance/attribute/destination checks in that order.
The private GSV node retains the same disposition as `gsv_signature_status`.
These diagnostics explain the existing condition4 rule without extending it or
publishing names/values. Modeled counts equal GSV passes; every other category
sums to opaque GSV transfers. Namespace failures are bounded by source-qualified
gaps, and the remaining failures by unresolved signatures.

Schemas1-4 and default schema1 remain frozen. Schema5 retains the 32 MiB private,
250,000-record and 2,000,000-evidence-ID bounds, and the 8 KiB public limit.
Only the new summary5 uses one-space JSON indentation so even maximum-width
counts in all its closed maps fit that public limit.
Focused tests cover each admitted instruction, override writes, aliases, arrays,
scope/type/name ambiguity, foreign and protected source, incomplete/extra bodies,
unsupported instructions, repeated calls, private replay forgeries, closed
summary conservation, bounds and frozen condition4 hashes. No new source sample
or sample-budget change is required; the next normal work run can classify the
existing custom occurrence from the already available private source.

## Condition4 source investigation (2026-10-19)

Return `31cc08b`, report `work-check-20261019T110128Z-77859af2.json`,
contains 326 opaque transfers and one opaque coil guard. The source histogram
and condition3 partition reconcile these transfers exactly: SFR 140, JSR 76,
PID 46, MSG 27, MVM 16, SWPB 10, GSV five, one each AVE/FAL/RET/SBR/SQO,
and one withheld custom instruction. Every transfer has reason
`unsupported_condition_behavior`; none has a failed condition3 signature.
The existing public counts do not identify which opcode contributes to the
one opaque coil guard.

The earlier instruction-by-instruction investigation below omitted a relevant
general rule. Rockwell's [Logix 5000 Ladder Diagram programming manual,
1756-PM008J, printed pages 11-12](https://literature.rockwellautomation.com/idc/groups/literature/documents/pm/1756-pm008_-en-p.pdf)
defines output instructions by their action, copying or calculation behavior,
and states that their outgoing normal ladder condition equals the incoming
condition for both false and true evaluation. The following explicit built-in
catalogue combines that rule with each documented instruction's operation:

| Condition4 spelling | Documented output operation |
|---|---|
| MVM | [Copy selected source bits into a destination](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/move-logical-instructions/masked-move--mvm-.html) |
| SWPB | [Rearrange source bytes into a destination](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/move-logical-instructions/swap-byte--swpb-.html) |
| GSV | [Retrieve system data into a destination](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-03/contents-ditamap/instruction-set/input-output-instructions/get-system-value--gsv--and-set-system-value--ssv-.html) |
| MSG | [Request a message transfer](https://www.rockwellautomation.com/en-ie/docs/studio-5000-logix-designer/38-02/contents-ditamap/instruction-set/input-output-instructions/message--msg-.html) |
| PID | [Execute the PID calculation](https://www.rockwellautomation.com/en-se/docs/studio-5000-logix-designer/38-02/contents-ditamap/instruction-set/special-instructions/proportional-integral-derivative--pid-.html) |
| AVE | [Calculate an array average](https://www.rockwellautomation.com/en-za/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/array-file-misc-instructions/file-average-ave.html) |
| FAL | [Perform array calculations; its execution table also explicitly gives identity transfer](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-01/contents-ditamap/instruction-set/array-file-misc-instructions/file-arithmetic_logic-fal.html) |
| SQO | [Copy masked sequence data into a destination](https://www.rockwellautomation.com/en-sg/docs/factorytalk-design-studio/current/contents-ditamap/instructions/instruction-set/sequencer-instructions/sequencer-output--sqo-.html) |

These eight reviewed spellings are the complete extension. Access write roles
alone cannot admit an instruction. Calls, returns, SFR and custom AOI behavior
remain opaque. MSG completion, communication direction and payload effects are
separate from its outgoing ladder condition. All existing normal-scan, fault,
state, scheduling and runtime limitations continue to apply.

Admission requires a source-qualified rung and Text envelope: the namespace
must match the document root throughout the ancestry, with no namespaced
attributes in that chain. Unsupported source context retains an opaque node
with reason `source_unqualified`. Data declaration availability does not decide
an instruction's outgoing condition; no data binding or runtime value is
invented by this rule.

MVM/SWPB/GSV/MSG also require an existing classified access signature.
PID/AVE/FAL/SQO use independent source-only checks because file-operation
providers already consume conditions. Importing those providers into conditions
would introduce a dependency cycle. Their neutral-text slot ordering follows
the [Import/Export manual, instruction table](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf).
Checks retain address-shaped data fields, numeric immediate syntax where
applicable, the documented empty GSV instance slot, file LEN/POS pseudo-fields,
AVE dimensions 0-2, and FAL ALL/INC/positive numeric modes. FAL expressions use
the existing bounded arithmetic grammar. SWPB currently admits the documented
REVERSE/WORD/HIGHLOW textual modes. Other selector spellings remain gaps rather
than guessed aliases. Types, member validity, bounds, effective settings and
execution completion are not validated. Unsupported signatures retain
`signature_unresolved`.

The eight source populations total 107 occurrences. This is the maximum
potential reduction on the returned export, not a measured condition4 result:
source qualification and the conservative syntax checks must still run on the
work machine. No conclusion about the single opaque guard follows from this
upper bound.

Condition4 adds two fixed maps over the approved public opcode vocabulary plus
`withheld`: `opaque_opcodes` counts transfer occurrences, and
`opaque_guard_opcodes` counts coil guards whose incoming graph contains at least
one opaque occurrence of that opcode. Repeated occurrences of one opcode count
once per guard; different opcode contributions overlap. Thus the latter map's
sum can exceed the number of opaque guards. Fixed-size bitsets propagate these
categories once through the DAG; no descendant lists or expanded formulas are
created. Unsupported private opcode names never enter these maps. A malformed
coil's outgoing transfer is counted only in later guards, preserving the
existing incoming-guard rule.

Condition1-3 private output and public vocabularies remain unchanged. Condition4
retains the 32 MiB private bound and existing node/evidence limits. Its public
summary has a separate 8 KiB bound; older summaries retain 4 KiB. Cross-summary
classified-access bounds must subtract condition4 passes for PID/AVE/FAL/SQO,
which are independently signature-qualified and do not rewrite access4 roles.
No new rung sample is requested: six charged examples, eight reserved units,
and the forty-unit ceiling remain unchanged.

Focused validation covers all eight identity transfers with incoming predicates
and ONS state, malformed arities/fields/selectors/expressions, foreign source
namespaces and attributes, unresolved data and dynamic indices, overlapping
guard diagnostics, shared-prefix graph growth, forged replay, closed-summary
validation and private/public caps. Frozen pre-change hashes verify byte-identical
condition1-3 private and summary payloads on an invented mixed fixture. The
historical sections below describe their original version-specific catalogues.

## Returned work-machine evidence

Returned `b31392a` tested clean `78cf221`. All 889 application cases passed
(one expected Windows symlink skip), as did 139 helpers. The private run saved
successfully with partial analysis and no failure code. All nine preceding
summaries equal the prior successful `f7d91f0` return after removing only tool
revision fields. All 32 historical reports validate. This confirms a successful
save after the repair, without establishing the earlier failure's exact cause
or proving source byte identity. Pushed reports remain automated evidence.

The first condition1 return accounts for 4,606 rungs and 17,874 instructions:
32,570 graph nodes, 3,719 joins and 8,887 branch legs. All 4,163 coil actions
are recognized: 1,687 OTE, 1,174 OTL and 1,302 OTU. Incoming guards are modeled
for 3,920 outputs, have predicate binding gaps for 181, and contain opaque
transfers for 62. Targets comprise 4,147 exact addresses and 16 unbound slots.
There are 303 predicate occurrences with binding gaps and 3,177 opaque transfers.
The 2,348 outputs counted with branches have a completed ANY join in their
incoming guard; outputs inside a branch before its join are not counted there.

## New evidence and limits

Condition2 preserves an explicit `pass_through` node for each documented,
signature-classified instruction in the catalogue below. Each node retains its
instruction, operand occurrences and single incoming condition. It replaces
the previous opaque node without changing the number of nodes or duplicating
an instruction table. The report exposes these incoming contexts even when
the rung has no coil output.

The outgoing Boolean condition equals the incoming condition during documented
normal-scan LD evaluation. This does not establish that execution completes,
that a write occurs, or that an instruction has no effect on a false evaluation.
TON, RTO, CTU and OSF can change state on false evaluations. OSF's separate
output bit can pulse; that pulse is not its outgoing rung condition. Runtime
state, numerical results, faults, task/call reachability, MCR zones and
prescan/postscan remain outside this local model.

Data-operand binding gaps retain their independent access evidence. They do not
invalidate a documented identity transfer. Predicate binding gaps and earlier
opaque transfers still propagate through the new node. Repeated reads remain
distinct even when their address is identical; intervening writes and
asynchronous I/O may change later values. Branch legs and empty bypasses remain
ordered, without truth simplification or formula expansion.

## Explicit instruction catalogue and primary sources

Each linked Rockwell execution table explicitly sets rung-condition-out equal
to rung-condition-in for normal false and true evaluation. These are LD rules;
FBD enable semantics must not be substituted. Checked 2026-10-15.

| Supported spelling | Checked instruction execution reference |
|---|---|
| ABS | [Absolute value](https://www.rockwellautomation.com/en-gb/docs/studio-5000-logix-designer/38-03/contents-ditamap/instruction-set/compute-math-instructions/absolute-value--abs-.html) |
| ADD | [Add](https://www.rockwellautomation.com/en-hu/docs/studio-5000-logix-designer/37-00/contents-ditamap/instruction-set/compute-math-instructions/add--add-.html) |
| CLR | [Clear](https://www.rockwellautomation.com/en-il/docs/studio-5000-logix-designer/38-01/contents-ditamap/instruction-set/move-logical-instructions/clear--clr-.html) |
| COP, CPS | [Copy and synchronous copy](https://www.rockwellautomation.com/en-ca/docs/factorytalk-design-studio/current/contents-ditamap/instructions/instruction-set/array--file--misc-instructions/copy-cop-synch-copy-cps.html) |
| CPT | [Compute](https://www.rockwellautomation.com/en-za/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/compute-math-instructions/compute--cpt-.html) |
| CTU | [Count up](https://www.rockwellautomation.com/en-pl/docs/studio-5000-logix-designer/37-00/contents-ditamap/instruction-set/timer-and-counter-instructions/count-up--ctu-.html) |
| DIV | [Divide](https://www.rockwellautomation.com/en-gb/docs/studio-5000-logix-designer/38-03/contents-ditamap/instruction-set/compute-math-instructions/divide--div-.html) |
| LN | [Natural logarithm](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-03/contents-ditamap/instruction-set/advanced-math-instructions/ln.html) |
| MOV | [Move, including the documented rename to MOVE](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-01/contents-ditamap/instruction-set/move-logical-instructions/move--move-.html) |
| MUL | [Multiply](https://www.rockwellautomation.com/en-za/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/compute-math-instructions/multiply--mul-.html) |
| OSF | [One-shot falling](https://www.rockwellautomation.com/en-dk/docs/studio-5000-logix-designer/37-02/contents-ditamap/instruction-set/bit-instructions1/one-shot-falling--osf-1.html) |
| RES | [Reset](https://www.rockwellautomation.com/en-gb/docs/studio-5000-logix-designer/38-03/contents-ditamap/instruction-set/timer-and-counter-instructions/reset--res-.html) |
| RTO | [Retentive timer on](https://www.rockwellautomation.com/en-se/docs/factorytalk-design-studio/current/contents-ditamap/instructions/instruction-set/timer-and-counter-instructions/retentive-timer-on--rto-.html) |
| SQR | [Square root, including the documented rename to SQRT](https://www.rockwellautomation.com/en-pl/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/compute-math-instructions/square-root--sqrt-.html) |
| SUB | [Subtract](https://www.rockwellautomation.com/en-gb/docs/studio-5000-logix-designer/38-03/contents-ditamap/instruction-set/compute-math-instructions/subtract--sub-.html) |
| TON | [Timer on delay](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-01/contents-ditamap/instruction-set/timer-and-counter-instructions/timer-on-delay--ton-.html) |

Only these 17 spellings enter condition2. Modern MOVE/SQRT aliases are not
added to the frozen access4 catalogue. FAL's transfer is documented but its
operand signature is not classified by access4, so it remains outside this
catalogue. Invalid signatures of admitted opcodes remain opaque with reason
`signature_unresolved`. Other blocks retain `unsupported_condition_behavior`.

ONS remains opaque because its retained storage filters the outgoing condition
([ONS execution](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-01/contents-ditamap/instruction-set/bit-instructions1/one-shot--ons-1.html)).
OSR, TOF and CTD were not verified for this catalogue. Inspected AVE, GSV,
MSG, MVM, SQO, SWPB and PID tables did not establish the required two-state
transfer explicitly; no classification was inferred from their operand roles
or names. JSR/RET/SBR/SFR and other control flow remain deferred.

## Contracts and replay

Explicit/default condition1 replay remains available. New CLI/work runs select
condition2, with the same private dataclass fields and 32 MiB limit. Coverage
adds the fixed `pass_through` node kind and `passthrough_opcodes` map. The
instruction partition is predicates + passes + opaque transfers + recognized
coil actions. No names, IDs, expressions or values enter the public summary.

Condition summary2 remains bounded to 4 KiB. Review10/manifest13 saves the same
16 hashed artifacts, preserving the 14 precondition non-HTML artifacts.
Review10 uses 160 MiB JSON / 192 MiB HTML limits; all earlier contracts and
budgets remain frozen. Work26 requires condition summary2. Work24/25 still
require condition summary1. The pass, predicate and output opcode counts share
one source-histogram withheld allowance, and classified access counts bound
recognized condition instructions. Work26 retains the 48 KiB report envelope
and work25's closed save-failure categories.

## Next work-machine return

Validation completed before handoff:

- Full development and helper suites: 1,198 cases, passing with one expected
  Windows symlink skip. Listener tests were excluded before loading. Independent
  review separately ran 159 targeted cases and found no blocking issues.
- Two actual isolated Bash runs, explicit then remembered source, each passed
  907 application cases (one expected skip) and 139 helpers. Each saved a
  manifest13 run with all 16 hashes verified and committed exactly one new
  validated work26 report locally. Git tracing confirmed no network operations.
- Fresh CLI output and both launcher runs match across all 16 artifacts.
  Fourteen earlier non-HTML artifacts match the preceding implementation byte
  for byte. Nine earlier summaries match after revision normalization. Explicit
  condition1 output also matches the preceding implementation byte for byte.
  All 32 historical reports and both new synthetic reports validate. All 128
  runtime/test files match the final tested isolated snapshot.
- A large invented export with 4,606 rungs, 17,874 instructions, 1,863 branched
  rungs and 48,400 stored-data elements produces 21,162,621 condition bytes,
  137,920,434 combined JSON bytes and 138,087,343 HTML bytes within the retained
  budgets. Chrome loaded it, paged 6,624 instruction contexts and opened their
  graphs without report console errors or horizontal overflow.
- The 191-rung invented demonstration covers all 17 transfer spellings and
  retains 200 instruction contexts (156 passes, 44 opaque). Chrome verified
  timer context, separate operand evidence and inert markup-like source text.
  UI tests cover no-output rungs, legacy reports, pagination, shared DAGs,
  repeated reads/writes and bounded search with very long alias roots.

An initial complete run caught one older SFC integration assertion still
expecting manifest12. Its current-run expectation was updated to13 before the
passing reruns; no parser behavior was changed to satisfy that assertion.

Run the ordinary manual pull, script, manual push cycle. No engineering/team
review is needed yet. The return will measure the new pass-through population
and remaining opaque guards. Follow with the 303 predicate binding gaps and
16 unresolved targets, using already-approved aggregate/bounded evidence to
separate parser omissions from absent source declarations. These gaps and
control flow must not be hidden by declaring Phase 1 complete.
