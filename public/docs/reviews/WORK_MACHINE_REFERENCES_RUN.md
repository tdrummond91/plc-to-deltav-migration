# Work-machine check: local results and manual publication

Current checkpoint (2026-10-16): **Sequence transition expressions**.
Return `3547344` tested clean `a6840f4`: 1,338 application cases passed (two
expected Windows skips), plus 139 helpers. All 485 timer/counter/reset targets
bind, all 48 resets match producers, and all 436 control objects have stored
data. Eighteen earlier summaries and the frozen six samples are unchanged;
all 42 historical feedback reports validate.

Review19/manifest22 adds source-linked transition expressions, comments and
reference bindings, with explicit unsupported and missing-condition cases.
Work36 returns closed counts while retaining sixteen saved artifacts.
See [scope and validation](SFC_CONDITIONS_REVIEW.md).

The next ordinary work-machine run measures coverage of 155 transition
conditions across 14 charts. No new plant samples or manual engineering/team
review are requested. Git transport stays manual and the listener stays
disabled. The returned syntax and binding gaps guide further sequence analysis.

## Historical timer/counter checkpoint

Historical checkpoint (2026-10-16): **Timers, counters and resets**.
Return `19ccaee` tested clean `5ae8b6d`: 1,295 application cases passed (two
expected Windows skips), plus 139 helpers. Boolean output context accounts for
all 4,163 coil occurrences and 2,978 qualified exact targets, with 6,071 predicate
reads. Multiple coil writers occur on 1,126 addresses; 315 have no captured
explicit RLL reader, which does not prove they are unused. Seventeen previous
summaries and the frozen six samples are unchanged; all 41 reports validate.

Review18/manifest21 adds timer/counter/reset control associations, incoming
source conditions, explicit member uses and exported stored-data context.
Work35 returns closed counts while retaining sixteen saved artifacts.
See [scope and validation](STATEFUL_OBJECTS_REVIEW.md).

The next ordinary work-machine run measures this bundle. No new plant samples
or manual engineering/team review are requested. Git transport stays manual and
the listener stays disabled. Sequence-transition text is the next planned broad
analysis bundle after returned evidence is checked.

## Historical Boolean-output checkpoint

Historical checkpoint (2026-10-16): **Boolean output context**.
Return `48dcd22` tested clean `2105ce3`: 1,254 application cases passed (two
expected Windows skips), plus 139 helpers. All 2,138 selected calculation blocks
are accounted for, including 1,294 in branched rungs; two destinations remain
unresolved. One possible local reuse link was found. All sixteen preceding
summaries and the frozen six examples are unchanged; all 40 reports validate.

Review17/manifest20 adds shared target-use evidence for the 4,163 coil
occurrences, declaration direction, competing writers, condition readers and
rung-scoped authored hints. The report follows actual condition-graph links,
without inferring execution, physical channels or shutdown behavior. Work34
returns closed counts while retaining sixteen saved artifacts.
See [scope and validation](OUTPUT_CONTEXT_REVIEW.md).

The next ordinary work-machine run measures these additions. No new plant
samples or manual engineering/team review are requested. Git transport stays
manual and the listener stays disabled.

## Historical calculation-path checkpoint

Historical checkpoint (2026-10-16): **Calculation inputs and destinations**.
Return `693e419` tested clean `f4f704d`: 1,216 application cases passed (two
expected Windows skips), plus 139 helpers. All 46 PID controls and 322 slots
are accounted for; 515 exact addresses include 333 referenced direct members.
All master operands are literals, so no explicit master-reference candidates
were found. Fifteen earlier summaries and the frozen six examples are unchanged;
all 39 historical reports validate.

Review16/manifest19 adds source-linked math/move records inside straight
segments and branch legs, with incoming conditions and possible local result
reuse. Forks, joins, unsupported blocks and stateful operations stop links.
Work33 returns closed counts while retaining the sixteen saved artifacts and
all earlier analysis semantics. See [scope and validation](CALCULATION_PATHS_REVIEW.md).

The next ordinary work-machine run measures these additions. No new plant
samples or manual engineering/team review are requested. Git transport stays
manual and the listener stays disabled.

## Historical PID connection checkpoint

Historical checkpoint (2026-10-16): **PID connections and observed member uses**.
Return `4018156` passed 1,183 application cases (two expected Windows skips) and
139 helpers. The AOI body has two rungs and three classified calculation blocks,
with no recorded context gaps. The single unmatched SFR address has one exact
candidate in another chart; its original missing match remains unchanged.
Thirteen earlier summaries and the frozen six-example record are unchanged;
all 38 historical reports validate.

Review15/manifest18 adds source-linked PID slot, member-use and master-reference
context while retaining sixteen artifacts. Work32 returns the closed connection
counts. Existing access4 and condition3 semantics remain unchanged.
See [scope, evidence and validation](PID_CONNECTIONS_REVIEW.md).

The next ordinary work-machine run measures these additions. No new source
samples or manual engineering/team review are needed. Git transport remains
manual, and the listener remains disabled.

## Historical AOI body checkpoint

Historical checkpoint (2026-10-16): **AOI body ownership and unmatched SFR context**.
Return `871b700` passed 1,128 application cases (two expected Windows skips) and
139 helpers. All 133 ONS occurrences now have stored-state transfers; opaque
coil guards fell from 59 to one. SFR target matching resolved 139 of 140 calls.
Twelve earlier summaries and the frozen six-example record remain unchanged;
all 37 historical reports validate.

Review14/manifest17 adds AOI body and instance relationships plus SFR gap
context, still with sixteen artifacts. Work31 returns their closed counts.
See [scope, evidence and validation](AOI_BODY_REVIEW.md).

The next ordinary work-machine run measures these additions. No new source
samples or manual engineering/team review are needed. Git transport remains
manual, and the listener remains disabled.

## Historical stored-state checkpoint

Historical checkpoint (2026-10-15): **stored-state conditions and SFC reset targets**.
Return `5215baa` passed 1,057 application cases (two expected Windows skips) and
139 helpers, saved its private run and preserved all eleven earlier summaries.
The unknown call has one matching AOI declaration; both dynamic write roots and
their index reads bind. One unknown-role indexed operand remains deferred.
All 36 historical reports validate and the six samples replay unchanged.

Condition3 explains ONS storage dependence without selecting runtime values.
SFR context links reset calls to program-local chart and step candidates while
retaining edit revisions and unresolved matches. Review13/manifest16 retains
sixteen artifacts; work30 returns the new SFR counts and updated condition counts.
See [scope, evidence and validation](STATEFUL_SEQUENCE_REVIEW.md).

The next ordinary work-machine run measures these changes; no new rung samples
or manual engineering/team review are needed. Git transport remains manual and
the listener remains disabled. AOI body/instance mapping is a recorded follow-up.

## Historical instruction-context checkpoint

Historical checkpoint (2026-10-15): **custom declarations and symbolic array selectors**.
The targeted return `51315bd` passed 991 application cases (two expected Windows
skips) and 139 helpers and saved its private run. All six samples were included;
all eleven prior summaries were unchanged. No additional sampling is requested.

The next normal `git pull`, `bash ./run-work-check.sh`, `git push` cycle produces
work29: two new aggregate context summaries plus the identical frozen sample
record. The private review12 contains declaration candidates and symbolic selector
details; manifest15 keeps sixteen hashed artifacts. Git transport remains manual,
and the script still commits only its validated feedback report. No manual
engineering/team review is needed yet. See [scope and validation](INSTRUCTION_CONTEXT_REVIEW.md).

## Historical targeted-sample checkpoint

Historical checkpoint (2026-10-15): **fixed targeted diagnostic rung examples**.
Tyler confirmed the 2% limit counts new informative examples separately from
older scrubbed structural catalogs. Small evidence-driven pulls are authorized;
no per-case approval gate is needed within that boundary.

Work28 adds a maximum six-rung request for two dynamic indexes, an unknown
instruction, ONS/SFR condition gaps and a branched comparison/output pattern.
Per-rung substitutions remove plant names and literal values. One bounded
unknown mnemonic is an intentional diagnostic clue. Public history plus an
ignored local reservation freeze the whole request across retries and changed
exports; historical replay is explicitly marked. The old rotating operand
sampler is disabled in work28. Earlier contracts remain readable.

Returned `aed0fc4` tested clean `a12ada1`: 945 application cases passed (one
expected skip), plus 139 helpers; the private run saved and all ten prior summaries
were unchanged. All 303 predicate gaps and 16 unbound outputs have unique rack
context, with two dynamic-index writes remaining. All 34 older reports validate.
The next normal work-machine run collects targeted examples; no manual engineering
or UI review is needed. See [selection, accounting and validation](TARGETED_RUNG_SAMPLES_REVIEW.md).
Git transport stays manual and the listener stays disabled.

## Historical binding-context checkpoint

Historical checkpoint (2026-10-15): **binding gaps and logical rack context**.
Returned `248b12a` tested clean `ef4ba8d`: 907 application cases passed (one
expected skip), plus 139 helpers, with a saved private run. Nine earlier summaries
are unchanged. Condition2 explains 2,718 instruction transfers; 459 remain opaque.
Coil guards comprise 3,923 modeled, 181 with predicate gaps and 59 opaque.
There remain 303 gap-bearing predicates and 16 unbound coil targets.

Review11 adds a bounded binding-context index linking unresolved occurrences to
source, alias chains, existing rack candidates and separate logical-address groups.
All existing bindings and condition statuses remain unchanged; physical backing
and member validity remain unverified. Manifest14 still has sixteen artifacts.
Work27 adds a count-only context summary. See [scope and validation](BINDING_CONTEXT_REVIEW.md).

The next normal work-machine run measures those per-occurrence associations.
Continue Phase 1 automated analysis; no engineering/team review is requested yet.
Git transport remains manual and the listener remains disabled.

## Historical condition-transfer checkpoint

Historical checkpoint (2026-10-15): **normal-scan instruction condition transfer**.
Returned `b31392a` tested clean `78cf221`: 889 application cases passed (one
expected skip), plus 139 helpers, and the private report saved successfully.
All nine preceding summaries are unchanged after tool revision normalization.
The first condition return accounts for all 4,163 coils: 3,920 modeled incoming
guards, 181 with predicate binding gaps and 62 with opaque transfers; 16 targets
remain unbound. This confirms recovery, without proving the earlier failure's cause.

Condition2 preserves incoming context through 17 documented, signature-classified
instruction spellings, including math, move, timer, counter and reset blocks.
The report also exposes noncoil instruction contexts without requiring a downstream
coil. Normal-scan condition transfer does not simulate effects or execution.
Review10/manifest13 retains sixteen artifacts; work26 returns condition summary2.
Earlier replay stays frozen. See [scope, sources and validation](CONDITION_TRANSFER_REVIEW.md).

Continue Phase 1 automated analysis after the next normal work-machine return;
no team review is requested. Git transport stays manual and the listener remains disabled.

## Historical save repair checkpoint

Historical checkpoint (2026-10-15): **condition report save repair**.
Returned `e0b6b0c` tested clean `effa48f`: 870 application cases passed (one
expected skip), plus 139 helpers, but returned `save_error` and no analysis
summaries. The private failure cause remains unconfirmed. Review9 now reserves
its additional bounded condition payload (160 MiB JSON / 192 MiB HTML);
review1-8 budgets remain unchanged. Work25 adds five fixed save-failure categories
without sharing exception text. A console failure after a completed save now
retains the correct saved-run flag. See [evidence and validation](SAVE_FAILURE_REVIEW.md).

The next normal work-machine run should supply condition counts or a precise
failure category. Continue Phase 1 analysis after that return; no team review
is requested. Git transport stays manual and the listener remains disabled.

## Historical condition implementation checkpoint

Historical checkpoint (2026-10-15): **Boolean conditions and output actions**
adds compact local condition graphs for series and parallel rungs, individual
predicate occurrences, and incoming-condition records for OTE/OTL/OTU. Unknown
block behavior remains explicit. Ordinary output, latch and unlatch actions stay
distinct; no PLC execution, final value or equipment/alarm purpose is inferred.

Returned `f7d91f0` tests clean `ddd087c`: 821 application cases passed (one
expected Windows skip), plus 139 helpers. There are 7,591 exact addresses,
3,778 used across rungs and 1,453 with multiple captured writers. Stronger
patterns cover 4,286 rungs in 1,489 groups; 320 rungs retain explicit exclusions.
No composed-suffix gaps were found. The narrow local calculation analysis found
one link; 13,053 instructions were excluded because their rungs contain branches.
All eight preceding summaries match after tool_revision normalization, and all
30 historical reports validate. Pushed results are automated, not team feedback.

Review9/manifest12 adds boolean-conditions.json as the sixteenth hashed artifact.
Work24 adds closed condition summary1. Work22-24 retain 48 KiB outer envelopes;
work1-21 retain 32 KiB. Earlier companions and optional replay remain intact.
The next normal work-machine run measures local condition/output coverage.
Continue source-addressable Phase 1 analysis before asking for team review.
Git synchronization stays manual; the launcher commits only its new validated
feedback report locally, and the listener remains disabled.

See [condition scope and validation](CONDITION_REVIEW.md).

## Historical relationship implementation checkpoint

Historical checkpoint (2026-10-15): **exact-address relationships and operand-reuse patterns**
adds exact expanded suffix identities, separate source/expression read occurrences,
possible local calculation links and stronger rung groups. Existing root-only
access and opcode-shape views remain available. Source-order links do not establish
runtime data flow, and pattern equality does not confirm engineering equivalence.

Returned `4a3406b` tests clean `938d72d`: 778 application cases passed (one
expected Windows skip), plus 139 helpers. All 4,606 rungs and 17,874 blocks were
accounted for; 1,863 rungs contain branches. The rung layer found 82 blocks with
unresolved operand behavior and 11,837 overlapping function candidates. The 1,319
alarm candidates are text hints, not verified alarms. Seven preceding summaries
match after tool_revision normalization; all 29 historical reports validate.

Review8/manifest11 adds relationships.json as the fifteenth hashed artifact.
Work23 adds closed relationship summary1; work22 and work23 allow 48 KiB outer
reports, while work1-21 retain 32 KiB. Earlier companions and optional replay
paths remain intact. The next normal work-machine run measures this relationship
layer on the private export. Pushed results are automated evidence, not human
feedback. Continue script-addressable Phase 1 analysis before team review.
Git synchronization stays manual; the launcher commits only its new validated
feedback report locally, and the listener stays disabled.

See [relationship scope and validation](RELATIONSHIP_REVIEW.md).

## Historical rung-analysis implementation checkpoint

Historical checkpoint (2026-10-15): **rung structure and function candidates**
brings existing source/access evidence into a complete rung census, ordered block
dossiers, branch outlines and overlapping candidate families. Interpretations
remain unreviewed, with reasons and missing evidence. Supported roles, recognized
mnemonics, declaration links and weak text hints stay distinguishable.

Returned `f93f744` tests clean `ae97f10`: 732 application cases passed (one
expected Windows skip), plus 139 helpers. All 45 CPTs were classified and all
132 expression reads bound across 72 roots. There are 17,746 classified
instructions, 128 unsupported instructions, 505 unknown source operand roles
and 321 unchanged ordinary binding gaps. Six other summaries match after only
tool_revision normalization; all 28 historical reports validate.

Review7/manifest10 adds rung-analysis.json as the fourteenth artifact. Work22
adds a fixed-count rung summary1 and a 48 KiB outer cap only for this version;
older report caps/contracts stay unchanged. Access4/calculation2 remain intact.
The next work-machine run supplies automated coverage for this broader layer.
Pushed results are not human feedback. Continue resolving script-addressable
relationships, loops, alarms and sequence questions before team review; no
manual review is requested now. Git synchronization stays manual and the
listener stays disabled. See [Rung analysis](RUNG_ANALYSIS_REVIEW.md) and the
[Phase 1 completion gate](../planning/PHASE_1_ENGINEERING_ANALYSIS.md).

## Historical CPT access implementation checkpoint

Historical checkpoint (2026-10-15): **CPT calculation access** connects the existing
expression trees to possible destination writes and individual tag reads.
Returned `cbb2965` tests clean `456786a`: all 175 newly supported instructions
and 336 operand slots were classified, and all 175 new data operands bound.
There are 17,701 classified instructions, 173 unsupported instructions, 595
unknown source operand roles and 321 unchanged binding gaps. All 695 application
cases passed (one expected Windows skip), as did 139 helpers. Six other summaries
match after removing only tool_revision; all 27 historical reports validate.

Current commands explicitly build access4 from authenticated calculation2
records. Expression reads remain separate from source operand counts, and repeat
occurrences retain their node/span links. Work21 requires access summary4 and
calculation summary2; work1-20 and explicit access2/3 replay remain frozen.
Review6/manifest9 still saves thirteen artifacts. The next work-machine run
checks the projected 45 CPT classifications and 132 expression reads. Only
bounded generated feedback is required; engineering/UI review remains optional.
Git synchronization stays manual and the listener stays disabled. See
[CPT access](CPT_ACCESS_REVIEW.md).

## Historical extended access implementation checkpoint

Historical checkpoint (2026-10-15): **extended explicit operand access** adds
counter controls, message controls, system-value operands and SFC-reset targets.
Returned `760448e` tests clean `36c0ff4`: all 45 CPT expressions now parse into
592 nodes, with 132 captured reference uses and all 45 destinations root-bound.
Four retained function calls use `SQR`; all expression-error counters are zero.
All 668 application cases passed (one expected Windows skip), as did 139 helpers.
Six earlier summaries match after removing only tool_revision. This establishes
syntax/root coverage for this export, not engineering validity or source-byte
identity. All 26 historical feedback reports validate.

Access3 owns the new bindings separately from unchanged reference6 evidence;
explicit access2 replay remains available. Work20 requires access summary3,
while work1-19 retain their exact contracts. Review6/manifest9 still saves
thirteen artifacts with actual nested versions. The next work-machine run
measures the new instruction families and binding gaps. Only generated feedback
is required; engineering/UI review remains optional. Git synchronization stays
manual and the listener stays disabled. See [Extended operand access](EXTENDED_ACCESS_REVIEW.md).

## Historical PID member implementation checkpoint

Historical checkpoint (2026-10-15): **documented PID member evidence** organizes
linked stored fields into readable groups, checks captured names/types/shapes,
and exposes absent and duplicate catalog entries without selecting effective
values. Returned `28b5d1f` confirms all 46 PID instruction occurrences linked to
46 distinct declarations, with 2,346 direct member occurrences and no PID
association gaps. It passed 586 application cases (one skip) and 139 helpers;
previous summaries stayed equal after revision normalization.

Current review5/manifest8 adds `pid-members.json` as the twelfth hashed artifact.
Work17 adds count-only `analysis.pid_member_summary` schema1 beside unchanged
PID1, Tag Data1, access2, SFC2 and reference12/source4 summaries. Older optional
paths and work1-16 remain strict. The next work-machine run measures member
coverage and gaps; only generated feedback is needed. Manual engineering/UI
review remains optional. Git synchronization stays manual and the listener
remains disabled. See [PID member review](PID_MEMBER_REVIEW.md) for scope and validation.

## Historical PID occurrence checkpoint

Historical checkpoint (2026-10-15): **PID occurrence evidence** links parsed PID
instructions and their seven named operand functions to retained references and
conservatively eligible stored PID structures. Repeated occurrences, aliases,
representations and duplicate members remain separate evidence. No active
cascade, runtime mode, effective value or distinct control-loop count is inferred.
The previously observed 46 PID instructions are source occurrences.

Current review4/manifest7 saves eleven hashed private artifacts, adding `pid.json`
beside unchanged Tag Data1/access2/reference6/SFC2/inventory3 evidence. Work16 adds
closed count-only `analysis.pid_summary` schema1 and keeps Tag Data1/access2/SFC2/
reference12/source4 summaries. Review1-3, manifest1-6 and work1-15 keep their exact
contracts; review4 retains review3's 128 MiB JSON and 160 MiB HTML limits.
See [PID evidence review](PID_EVIDENCE_REVIEW.md) for scope, validation and
remaining limits. The next ordinary work-machine run measures PID evidence;
only generated aggregate feedback is needed. Engineering/UI review remains
optional later. Manual pull/run/push and private artifact storage still apply.

## Historical Tag Data checkpoint

Historical checkpoint (2026-10-15): **stored Tag Data evidence** is a separate
capture layer beside the unchanged source/reference/SFC/access contracts.
Review3/manifest6 adds `tag-data.json` as the tenth hashed private artifact;
work15 adds a count-only tag-data summary1. Missing Data remains absent evidence.
Stored text and attributes do not establish effective values, initialization,
runtime state, member validity or approved settings. Read the
[Tag Data review](TAG_DATA_REVIEW.md) for scope and complete validation results.
All 642 development cases pass with one existing Windows symlink skip.
Two actual isolated runs, explicit then remembered source, each pass 546
application cases (one existing symlink skip) and 139 helpers, with report-only
local commits and no Git network calls. All ten hashes and canonical review3/
Tag Data schema1 verify; fresh CLI artifacts are identical. Eight legacy artifacts
match `122f230` byte for byte, source/reference/SFC/access summaries match after
revision normalization, and all 21 historical work1-14 reports validate.

Returned `122f230` confirms timer/reset/copy access2 on clean `bdcc101`: 496
application cases (one skip), 139 helpers, 17,526 classified instructions of
17,874, 348 unsupported instructions, 931 unknown operand roles and 321 binding
gaps. All 434 timers have 868 placeholder initialization fields. Source/reference
and SFC summaries equal `7cd9201` after revision normalization; aggregate equality
does not prove source byte identity. The next normal work-machine run measures
Tag Data capture. Only generated aggregate feedback is needed; engineering/UI
review remains deferred and does not gate parser work. Manual pull/run/push
and private artifact storage continue as described below.

## Historical timer/reset/copy checkpoint

The next run measures **Phase 1 timer/reset/copy operand access, extending the
catalogue to 34 supported mnemonic spellings**. It saves private access evidence and adds count-only access
coverage to the generated feedback. Roles describe potential explicit uses,
not execution effects or dependencies. Root groups do not prove overlap between
member/index suffixes. Timer pseudo-operands retain only placeholder/integer
classification; timing, initialization and copy ranges remain unmodeled.
Read [TIMER_COPY_ACCESS_REVIEW.md](TIMER_COPY_ACCESS_REVIEW.md) and the initial
[ACCESS_ROLE_REVIEW.md](ACCESS_ROLE_REVIEW.md) for
capabilities and limits; the evidence checkpoints below remain historical.

Returned `7cd9201` confirms initial access1: 478 application cases (one skip),
139 helpers, clean tested `6642c5c` and a saved private run. It classified 16,952
of 17,874 instructions, retained 922 unsupported instructions and counted 321
access binding gaps. Reference/source and SFC summaries match the preceding
`1332543` report after revision normalization. Tyler has not
inspected the source/report and explicitly deferred engineering and UI review.
Only the next generated aggregate feedback is needed for this access slice;
familiar-tag, SFC and appearance checks are optional later and do not gate parser work.

In Git Bash at the repository root on `feat/bounded-operand-example-pc`:

```bash
git pull
bash ./run-work-check.sh
# If this checkout has no remembered source, use instead:
# bash ./run-work-check.sh A19CHL02-unencrypted.L5X
```

The runner prints the private `review.html` path for optional later inspection.
After checking the new generated feedback JSON, run `git push` manually. The
script commits that report locally; no manual staging or commit is needed.
Keep the HTML and engineering artifacts private.

Historical extension validation: 592 development cases pass (one existing symlink
skip). Two actual isolated runs, explicit then remembered source, each pass 496
application cases (one skip) and 139 helpers. Both make report-only local commits
without Git network calls, preserve earlier runs, verify nine artifact hashes
and canonical access2/review2, and match fresh CLI artifacts byte for byte.
Seven legacy artifacts match `7cd9201`; source/reference/SFC summaries match
after revision normalization. All 20 historical work1-13 reports validate.

Initial access1 validation is historical: 574 development cases passed (one existing symlink skip).
Two final synthetic launcher runs each pass 478 application cases (one skip)
and 139 helpers. Manifest hashes, canonical review/access evidence and identical
CLI HTML verify; seven legacy artifacts remain byte-identical to baseline
`1332543` on the same invented input, and source/reference/SFC summaries match
after revision normalization. All 19 historical work1-12 reports validate.
At that checkpoint, overall `partial` remained expected. Work14 carried access summary2 beside unchanged reference12/
source4/SFC2. Review2 runs used manifest5 with nine hashed artifacts, including
private access2 in `access.json` and `review.html`; frozen work13 retains access
summary1. Legacy reference/SFC runs
retain manifest2/3, and historical review1/manifest4 runs remain readable.

Use **main** for the consolidated baseline. The current Phase 1 work is on
**feat/bounded-operand-example-pc**. Pull that branch manually, then run the script. This remains Phase 1:
source inventory, module I/O declarations, declared roots/aliases and supported explicit operand uses. Engineering classifications,
editable corrections, PCSD and FHX generation are still later work.

Confirmed timer evidence: `1195d40` tested `112ee82`, passed 177 application
cases (one skip) and 139 helpers, and confirms malformed addresses 868 to 0,
non-data 0 to 868, and unsupported addresses 870 to 2. Other source/reference
counters are unchanged; the diagnostic sample is null. See
[TIMER_PLACEHOLDER_REVIEW.md](TIMER_PLACEHOLDER_REVIEW.md) for results and limits.
Rack evidence: `9597f18` tested `9d159e0`, passed 220 application cases
(one skip) and 139 helpers. All 15 rack roots are named; all 99 unresolved aliases
and 319 alias-mediated occurrences have unique candidates. One direct operand
has no candidate. Ordinary bindings remain unchanged; backing maps are unverified.

The address report: `7f5db96` tested `84dc393`, passed 241 application cases
(one skip) and 139 helpers, and supplied `S:FS` at XIC argument 0. Other aggregate
counts equal the preceding rack report. This is the built-in First Scan flag.
First-scan evidence: `d247f87` tested `d64ee4d`, passed 269 application cases
(one skip) and 139 helpers. It confirms one `system_flag`, unresolved operands
320 to 319, direct rack comparisons 1 to 0 and sample null. Other counters stay
unchanged. No repeat flag-only run is needed; see [the confirmed review](SYSTEM_FLAG_REVIEW.md).

Calculation evidence: `4244cf5` tested `a6a2a71`, passed 286 application cases (one
skip) and 139 helpers, and confirms all 28 ABS/LN/SQR instructions plus 56 bound
arguments. Catalogued rises 17,563 to 17,591, root_bound 20,178 to 20,234 and
unsupported instruction slots fall 653 to 597; other counters are unchanged.
No repeat math-only check is needed; see [the confirmed review](MATH_SIGNATURE_REVIEW.md).

Bit-operation evidence: `08c2695` tested `bdf09f1`, passed 296 application cases (one
skip) and 139 helpers, and confirms all 26 MVM/SWPB signatures. Their 78 fields
split into 52 bound roots, 16 literals and ten selectors; other counters stay
unchanged. No repeat bit-only check is needed; see [the confirmed review](BIT_OPERATION_REVIEW.md).

Shape evidence: `0a2610f` tested `9c56b50`, passed 308 application cases (one
skip) and 139 helpers. JSR has 76 occurrences/163fields: 65 two-field second-zero
and 11 three-field second-other calls. SBR has one field; RET has none. Every
earlier counter is unchanged. A second field spelled zero does not establish
its parameter role. See [the confirmed shape review](ROUTINE_CALL_SHAPE_REVIEW.md).

Candidate evidence: `7e15843` tested `3598710`, passed 325 application cases (one
skip) and 139 helpers. All 76 JSRs have unique declared candidates covering
66 distinct targets; all contexts remain not_analyzed. Earlier counters remain
unchanged. See [the confirmed candidate review](ROUTINE_TARGET_REVIEW.md).

Metadata evidence: `3431389` tests clean `5f91400`, passing 335 application cases
(one skip) and 139 helpers. All 76 program-Type observations are absent; targets
are RLL62/SFC14 by call occurrence. Every earlier counter remains unchanged.
See [the confirmed metadata review](ROUTINE_METADATA_REVIEW.md).

Latest evidence: `2f37ae3` tests clean `e17ceeb`, passing 354 application cases
(one skip) and 139 helpers. The graph has 69 nodes, 68 pairs and 76 linked calls, with three repeated pairs,
eight extra occurrences, three matched mains, one isolated node and no observed
cycles. Earlier counters are stable.
See [the confirmed graph review](ROUTINE_GRAPH_REVIEW.md).

Returned SFC evidence: `42e0188` tests clean `4b00f5a`, passing 399 application
cases (one skip) and 139 helpers. All 14 contents have absent edit-kind attributes;
145 steps, 155 transitions, 324 links and all 648 endpoints resolve. There are
280 text boxes, 213 attachments and 280 unknown elements; ST is 329 lines/5,390
characters. Every earlier reference count stays unchanged.

Latest annotation evidence: `90923ab` tests clean `f8411bc`, passing 416
application cases (one skip) and 139 helpers. All 280 boxes have recognized
Text children, all 213 attachments/426 endpoints resolve, and SFC structural
status is complete with zero issues. Previous reference/flow/ID/ST counts stay
unchanged. Overall partial remains expected because engineering interpretation
is incomplete. No repeat annotation-only run is needed; the access-role
checkpoint above is now ready for the next run. See [the confirmed annotation
review](SFC_ANNOTATION_REVIEW.md) and [project state](PROJECT_STATE_REVIEW.md).

## Manual runs

The development listener remains disabled and paused. Its files are excluded
from the tracked project; normal manual parser checks do not require them.
Update or clone the code manually, then
open Git Bash in the repository root on `main` or a chosen development branch:

```bash
bash ./run-work-check.sh YOUR_READABLE_EXPORT.L5X
# Later runs in this checkout remember the source path:
bash ./run-work-check.sh
```

The first run accepts the readable export's local filename or path. A fresh
clone has no remembered source selection, so supply it again on that first run.

A bare filename is looked up under `confidential/plc-code/`. An explicit relative
or absolute path also works; quote paths with spaces. The selected path is shown
locally and saved in this checkout's Git metadata, outside tracked files. The
script never embeds it in the shared report. Use the readable export that produced
summary-002 and the returned reference summary: 4,606 rungs, 17,874 instructions,
6,307 tags, 120 modules and no encoded regions.

The script uses the code already checked out and locked Python dependencies. It
runs explicit parser/helper test allowlists in separate processes, analyzes the
saved source and automatically stages and commits only its new validated
feedback report. It never fetches, pulls or pushes. Passing a different
filename/path replaces the machine-local source
selection for future runs.

Git, Git Bash and uv must already be available. The checkout must be clean and
on a named branch (including `main`); an upstream and GitHub authentication are not required
by the runner. A configured Git author identity is needed for the local commit.
Local changes stop the script without discarding anything.
Dependency setup may still use uv's configured package sources.

The work-machine test lists exclude listener, Windows process-host, Bash
bootstrap and Git-fixture tests. Full unittest discovery remains the development
check. New reports use schema 15 and their tested SHA identifies which suite
implementation ran; older reports can therefore have a broader test scope.

## What it produces

| Location | Contents |
|---|---|
| `public/inspection/work-check-<run-id>.json` | Automatically committed feedback: tested revision, suite results, reference/structural/access/Tag Data counts, and at most one actual mystery operand with instruction/argument position |
| `confidential/work-checks/<run-id>/` | Local test logs and structured results; analysis exception details if needed |
| `confidential/workspaces/work-check/<new-run>/` | Local snapshot.L5X, inventory.json, overview.txt, references.json, references.txt, sfc-structure.json, sfc-structure.txt, access.json, tag-data.json, review.html and manifest.json |
| Git metadata `plc-work-check.json` | Local remembered source path; not committed or pushed |

For optional later inspection, `review.html` is the organized offline report. It includes private
source evidence and bundled assets, and opens without a server. For a separate
new run, use `uv run --project python-parser --locked plc review FILE
--workspace confidential/workspaces/review`; `--workspace` is required. The
command prints the HTML path, and exit 3 means usable partial output.

Open `overview.txt` for the source overview and `references.txt` for declarations,
alias chains, operand occurrences and rack candidate lookups. Their JSON counterparts preserve structured
records and source links for later analysis. Open sfc-structure.txt for SFC edit
blocks, descriptors, opaque ST and scoped links; its JSON preserves canonical
records. `access.json` schema2 records possible explicit operand roles and resolved-root
groups; it does not assert runtime effects, dependencies or member overlap.
Combined review work runs use review4/manifest7 with eleven hashed artifacts.
`tag-data.json` schema1 preserves stored Data/DefaultData evidence without choosing
effective values or validating settings. `pid.json` schema1 links PID occurrences
to existing operand and stored-structure evidence with explicit gaps. Work16
retains `analysis.tag_data_summary` schema1 and adds `analysis.pid_summary` schema1
with fixed counts and no stored names, values, IDs, relationships or Format spellings.
Access summary2 retains accepted timer counts and fixed placeholder/integer pseudo-operand
counts; these contain no raw timer values or operand text. The timer capacity
bound includes published TON/TOF/RTO counts plus pooled `withheld` spellings so
lowercase source instructions remain supported. That bound does not prove that
every pooled instruction is a timer.
Plain reference runs retain manifest2 and standalone SFC runs retain manifest3.
Every run gets new output locations;
the original source and previous runs are preserved.

The public report includes at most one actual operand in `diagnostic_sample`,
with its standard opcode and zero-based argument position. The operand can
contain a real name/value; Tyler authorized this bounded example to investigate
unknown syntax. It is limited to 128 printable characters, with no full rung,
source filename/hash, routine, neighboring logic or individual reference links.
The first eligible malformed operand has priority; otherwise a direct unresolved
colon operand with no rack candidate can be selected. Aliases and inconclusive
or matched rack lookups are excluded. Recognized first-scan flags and SWPB
order-mode selector slots do not qualify.
Repeated unchanged runs select the same
eligible example. Null means no eligible
example was available or analysis did not succeed. The reference aggregate
is at `analysis.reference_summary`, with the structural summary nested beneath
`source_summary`. Separate SFC counts are at `analysis.sfc_structure_summary`;
count-only access coverage is at `analysis.access_summary`, and stored-data
capture counts are at `analysis.tag_data_summary`. These sections contain no
names, source IDs, values or individual relationships.
The top-level `tool_revision` identifies the tested code commit;
the automatically created report commit is intentionally different.

`analysis.reference_summary.rack_candidates` is the new comparison section.
It counts named/unavailable rack declarations and match statuses separately for
aliases, direct operands and alias-mediated operands. `unique_candidate` is a
possible logical declaration with unexamined backing; `candidate_names_unavailable`
is inconclusive. Do not expect `root_bound` to increase in this diagnostic slice.

## Manual review and publication

Review the saved feedback report, then publish the already committed result:

```bash
git push
```

No manual copy, staging or commit step is needed. Older reports saved by the
previous runner under `public/inspection/local/` remain ignored and are not
included automatically. The private log folder, workspace and source export
are never included in the report commit. The runner does not contact a remote.

## Reading completion and failures

`Check status: partial` is expected for the current source and exits successfully.
Known SFC/empty-routine gaps and unsupported reference forms remain visible. Partial
means usable results with gaps, not a failed save. A complete result also refers
only to the implemented analysis scope, not all process behavior.

If either suite fails, both suites are still attempted, source analysis is skipped,
and the test-results report is committed locally. The script exits 1 after reporting
that failure. Analysis failures also produce a failed report with a fixed reason
code and a local report commit; detailed diagnostics remain local. Setup/source-selection errors occur
before the check and do not produce a test-results report. Changes to the branch,
commit or tracked/untracked files during the run stop normal completion.

If staging or committing fails, the report remains on disk and the script exits
1 without pushing. The local `git.log` contains the Git error (for example,
missing author identity). Resolve that error before retrying; the retained
uncommitted report must be handled before another run can pass the clean-tree
check. The runner never clears or silently commits unrelated changes.

A local save does not send anything to the development PC. A report becomes
available there only after manual publication. No copied terminal output,
manual test summary or proprietary source is needed. The listener remains
disabled; do not assume it will process a newly published result automatically.

Interpret the reference counters as follows:

- `root_bound`: a declared root/alias chain was found; members, dimensions,
  access rules and instruction effects are not validated.
- `unresolved`: no applicable declaration was found. Missing module-tag modeling
  for unsupported topologies or partial export context can cause this; it does
  not prove a source typo. Fixed `by_reason` counts explain the supported cases;
  `colon_root_not_declared` only describes address syntax, not proven I/O intent.
- `ambiguous`: multiple declarations matched the same case-insensitive name.
- `unsupported_instruction`, `unsupported_expression`, `unsupported_address`:
  private evidence was retained but this slice did not interpret it.
- `alias_cycle`, `alias_depth_limit`: alias traversal could not complete.
- `literal`: recognized literal values, without tag links.
- `system_flag`: exact direct `S:FS` in a valid XIC/XIO contact, without tag links
  or a runtime model of first-scan behavior.
- `non_data`: labels and recognized timer placeholders, without tag links. A
  timer placeholder supplies no value and does not validate timer configuration.
  SWPB order-mode slots are also non-data by role; their mode value is unvalidated.

Manual commands remain available in the [Python README](../../../python-parser/README.md).
See [runner implementation and validation](WORK_CHECK_RUNNER_REVIEW.md) for the
automated workflow's contract and test evidence.

The module/I/O update adds `module_io` naming/provenance counts and fixed reason
counts under both `aliases` and `operands`. Source module ports, connections and
input/output/config declarations are counted separately from ordinary tags.
Actual names, topology and per-reference detail remain in the private reports.
See [module/I/O review](MODULE_IO_REVIEW.md) for comparison targets and
[listener operation](FEEDBACK_LISTENER.md) for its local status controls.

The report returned in `349ee29` supplied `?` at TON argument 1. Report `1195d40`
now confirms schema-4 timer-slot recognition: malformed occurrences fall 868 to
zero while non-data rises by 868. Only two dynamic-index unsupported addresses
remain. That historical check used outer schema 2. See [timer review](TIMER_PLACEHOLDER_REVIEW.md)
for the complete comparison and remaining Phase 1 gaps.
These seven closed counters partition the malformed-address operand total;
they do not change parsing or binding. Alias-target failures have their own
bucket, and direct spellings are grouped by fixed precedence. Those counters
contain no actual addresses, values or individual relationships; the separate
authorized operand sample is the explicit exception in schema 2. The current histogram sum is zero; later
changes should be compared with the confirmed `1195d40` baseline. See [address-shape review](ADDRESS_SHAPE_REVIEW.md).
