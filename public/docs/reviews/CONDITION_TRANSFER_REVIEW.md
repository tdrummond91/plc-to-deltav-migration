# Normal-scan condition transfer

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
