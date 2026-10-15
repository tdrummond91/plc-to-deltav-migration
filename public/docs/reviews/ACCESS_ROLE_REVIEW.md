# Explicit ladder operand access

## Current checkpoint and next run

The first operand-access layer is implemented. It identifies possible explicit
reads, writes and stored state that is both read and written for 28 existing
instruction spellings. The private report has a Tag access view with source
links and separate lists for unknown instruction roles and unresolved known
accesses. This remains Phase 1 source understanding.

Returned commit 1332543 contains
[work-check-20261015T041710Z-a3c2dc50.json](../../inspection/work-check-20261015T041710Z-a3c2dc50.json),
testing clean c36d10b: 439 application cases (one existing skip) and 139 helper
tests pass, private_run_saved is true, and no failure is recorded. Reference
and SFC summaries match the preceding report after normalizing tool_revision.
This verifies generation of the first HTML report; it does not establish that
the file was opened or reviewed by an engineer.

Tyler has not inspected the PLC source and does not need to do so before this
slice. Engineering and appearance review are deferred until useful and practical.
The next required input is another generated work-machine report:

```bash
git pull
bash ./run-work-check.sh
git push
```

Use the existing feat/bounded-operand-example-pc checkout. The runner remembers
the local input and prints the new private review.html path. It automatically
commits only the validated public feedback locally. Pull and push are manual.
Returning that feedback is sufficient; opening the HTML is optional for now.
Do not return the actual-unit HTML or access.json. The
[invented demonstration](../../examples/engineering-review-demo.html) is available
for learning the interface without knowing the actual PLC code.

## Meaning and limitations

Roles describe the potential use of explicit operand slots when an instruction
executes. They do not evaluate rung conditions, scan order, scheduling, implicit
status flags, member types, array bounds, byte ranges or runtime effects. No
dependency graph, alarm shutdown classification, priority, PID interpretation,
sequence interpretation or PCSD/FHX generation is introduced.

Root groups are occurrence indexes, not proven data dependencies. A read of
Motor.Ready and a write of Motor.Command can share a root while addressing
different members. Original operand IDs, source instruction/rung links and
resolved suffixes remain available for later overlap analysis. The implementation
does not build a Cartesian product of reads and writes. Candidate rack aliases
are not promoted to resolved roots.

Every parsed instruction is counted, even an unsupported zero-argument one.
Each existing operand gets a role and reason independently of binding success.
For example, MOV(A,12) has a known write slot but no writable root binding; it
appears in the unresolved-access list and makes access coverage partial. Literal
and recognized system-flag reads are valid unlinked reads. Unsupported instructions
may read or write data even when no operand has a usable binding. Absence from
the index never proves that a tag is unused or read-only.

Access status is partial exactly when at least one instruction is unclassified,
one rung is unparsed, or one known access slot has an unusable binding. A complete
access status means only complete captured explicit-role coverage under this
catalogue. Source/reference/SFC statuses remain separate and can still be partial.

## Initial catalogue

Operand order is the captured RLL argument order. Matching is ASCII case
insensitive; exact arity and nonempty arguments are required. An arity mismatch
or empty argument makes every operand of that instruction unknown.

| Instruction spellings | Roles in argument order |
|---|---|
| XIC, XIO | read |
| OTE, OTL, OTU, CLR | write |
| ONS | read_write |
| OSR, OSF | read_write, write |
| MOV | read, write |
| MVM | read, read, read_write |
| SWPB | read, non_data, write |
| ADD, SUB, MUL, DIV | read, read, write |
| ABS, LN, SQR | read, write |
| EQU, NEQ, LES, LEQ, GRT, GEQ | read, read |
| LIM | read, read, read |
| JMP, LBL | non_data |

MVM conservatively reads the destination because unmasked bits are retained;
individual masks are not evaluated. OTL/OTU retention on a false rung is not an
explicit read role. ONS and OSR/OSF storage state is both tested and updated.
The byte-order field in SWPB is a selector, not a data access. These distinctions
follow Rockwell's [MVM](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/move-logical-instructions/masked-move--mvm-.html),
[SWPB](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/move-logical-instructions/swap-byte--swpb-.html),
[ONS](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/bit-instructions1/one-shot--ons-1.html),
[OSR](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/bit-instructions1/one-shot-rising--osr-1.html),
[OSF](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/bit-instructions1/one-shot-falling--osf-1.html),
[OTL](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/bit-instructions1/output-latch--otl-1.html)
and [OTU](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/bit-instructions1/output-unlatch--otu-.html) descriptions.
Ordinary source/destination roles also follow the official
[move](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/move-logical-instructions/move--move-.html),
[math](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/compute-math-instructions.html)
and [comparison](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/compare-instructions.html) references.

This slice uses existing reference-catalogue spellings; it does not add the
[newer mnemonic aliases](https://www.rockwellautomation.com/en-nl/docs/studio-5000-logix-designer/38-03/contents-ditamap/instruction-set/updated-instruction-mnemonics.html).
PID, CPT expressions, timers, RES, COP/CPS, routine arguments, AOIs and other
unlisted instructions remain explicit unknowns. SFC/ST execution remains outside
the scope. Later slices should add verified contracts rather than guess from
operand position or names.

## Contracts and implementation

- Private AccessResult schema1 / instruction-access-1 is separate from unchanged
  inventory3 and reference6/source-references-9. It has instruction, operand and
  root records plus closed coverage counters. Canonical replay rejects altered
  metadata, roles, targets, suffixes and group membership.
- Public access-summary-1 contains fixed metadata, revision and counts only;
  no names, IDs, suffixes, opcode histogram or topology. Validation checks exact
  keys/types, partitions, population capacities, status and feasible catalogue
  role combinations. It is embedded in work13; no new public CLI is added.
- Work13 requires access_summary on success and null on failure/not-run. Counts
  and revisions reconcile with the reference summary, including classified and
  non-data subset bounds. Historical work1 through12 remain strict/readable;
  public source4/reference12/SFC2 are unchanged.
- Optional access in build_review_data yields review2 / engineering-review-2,
  with analysis_scope source_evidence_with_operand_access. The default without
  access retains review1. Broad semantic/effect flags stay not_implemented.
- Access-enabled review storage uses manifest5 and nine hashed artifacts,
  including access.json and review.html. Validation/rendering precede run
  allocation; the final manifest publishes last. The earlier manifest1 through4
  paths remain available. CLI review and the work runner request the new variant.
- Limits: 250,000 instructions/operands, 32MiB private access JSON, 32KiB standalone
  access summary, 64MiB combined review model and 80MiB HTML. Existing work-report
  and publication boundaries continue to apply.

Core modules are access.py and access_summary.py. The HTML adds searchable root
groups, role-filtered occurrences, exact operand-to-rung navigation, known-role
binding gaps and unknown-instruction links. Read/write is a disjoint category,
not duplicated in the read and write counters. Legacy review1 renders without
the new section.

## Validation

The full tracked development suite passes 574 cases with one existing Windows
symlink-capability skip; the ignored listener loader is excluded. Independent
review passed all 35 focused access/workflow tests and JavaScript syntax, with
no remaining blockers. The audit prompted stricter public catalogue-capacity
checks and visible known-role binding gaps. Exhaustive small-count coverage
checks 12,460 role-count vectors, including parity cases.

Two actual work-runner invocations in an isolated temporary checkout, with an
explicit invented input then its remembered path, pass 478 selected application
cases (one skip) and 139 helpers on each run. Both runs produce manifest5 with
nine correctly hashed artifacts and canonical review2/access payloads. CLI review
produces byte-identical HTML. Seven legacy artifacts match baseline1332543
byte-for-byte; source/reference/SFC summaries match after revision normalization.
All 19 historical work reports (schemas1 through12) validate unchanged. Inputs
and prior runs remain intact, commits contain only the new public feedback and
record the tested revision as parent, and no Git fetch/pull/push occurs.

Chrome checks over a temporary loopback server verify masked destination
read/write filtering, exact argument/rung focus, literal-write gaps, unknown
zero-argument instructions and old review1 compatibility. A separately invented
4,606-rung/23,030-operand fixture produces 4,610 root groups and a 57,149,561-byte
HTML report in about 13.9 seconds on this PC. Search finds the last root and Back
preserves page2 of93 with 50-row pages. No page JavaScript errors were recorded.
This is synthetic scale evidence, not real-unit performance. The final footer
wording was subsequently verified by all eight HTML tests and the regenerated
demonstration in Chrome.

The built wheel includes exact access modules and embedded assets; its extracted
renderer reproduces the final demonstration byte-for-byte. Direct file opening
on the work PC and real-unit visual usability remain unverified. Browser
automation prohibits file:// navigation, so QA used loopback HTTP; no workaround
was attempted. Those optional user checks do not block further parser work.

## What follows

Use the next real-export aggregate to measure classified/unknown roles and
binding gaps before choosing the next bounded semantic slice. Then extend
instruction families or expression/member interpretation with synthetic tests
and primary instruction references. Equipment, loops, alarms and shutdown
relationships still require more source interpretation. Editable records,
correction continuity, PCSD and FHX remain later phases. No fixed iteration count
is justified before this new population evidence returns.
