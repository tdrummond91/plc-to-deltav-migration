# Timer, reset and copy operand access

## Returned access baseline

Commit 7cd9201 returns
[work-check-20261015T045543Z-7f2b0763.json](../../inspection/work-check-20261015T045543Z-7f2b0763.json)
from clean 6642c5c. Its report-only commit has the tested revision as parent.
All 478 selected application cases (one existing Windows symlink skip) and 139
helper cases pass. The private run was saved, failure_code is null, and overall
status is partial. Strict work13/access-summary1 validation passes.

| Access1 population | Returned count |
|---|---:|
| Parsed instructions | 17,874 |
| Classified instructions | 16,952 |
| Unsupported instructions | 922 |
| Read operand slots | 15,595 |
| Write operand slots | 6,269 |
| Read/write operand slots | 152 |
| Non-data operand slots | 10 |
| Unknown operand slots | 2,557 |
| Root-linked slots | 20,286 |
| Indexed roots | 5,162 |
| Known roles with unusable bindings | 321 |
| Unparsed rungs | 0 |

This is about 94.8% instruction-role coverage, not migration completeness.
Reference12/source4 and SFC2 summaries are exactly equal to the preceding
1332543 feedback after removing only tool_revision. Aggregate equality does not
establish source byte identity. The new report confirms generation, not human
inspection of the HTML or PLC code. Tyler can defer engineering/UI review.

## Selected extension

The remaining unknown instructions include 390 TON, 44 RTO, 48 RES and 92 COP. They
already have reference signatures, so access can improve without changing root
bindings or source/reference/SFC contracts. This slice adds six spellings to the
initial 28: TON, TOF, RTO, RES, COP and CPS.

| Instruction | Explicit operand roles |
|---|---|
| TON / TOF / RTO | Timer structure: read_write; preset/accumulator fields: non_data initialization fields |
| RES | Structure: write to selected members |
| COP / CPS | Starting source: read; starting destination: write; length: read |

These are possible explicit roles. Timer units, valid configuration, initialized
member values, selected member extents, copied ranges, overlap, synchronization,
instruction execution and process behavior remain unimplemented. RES does not
claim that every member of the structure is overwritten. COP/CPS do not claim
that a single starting element is the whole affected range. Existing root
grouping remains an occurrence index, not a dependency graph.

## Timer pseudo-operands

Rockwell documents the timer preset/accumulator fields as pseudo-operands tied
to the backing structure. They initialize members at download; they are not
separate runtime data sources. During execution, the timer uses and updates its
structure. See [pseudo-operand initialization](https://www.rockwellautomation.com/en-gb/docs/studio-5000-logix-designer/38-00/contents-ditamap/pseudo-operand-initialization.html),
[TON](https://www.rockwellautomation.com/en-gb/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/timer-and-counter-instructions/timer-on-delay--ton-.html),
[TOF](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-01/contents-ditamap/instruction-set/timer-and-counter-instructions/timer-off-delay--tof-.html)
and [RTO](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-01/contents-ditamap/instruction-set/timer-and-counter-instructions/retentive-timer-on--rto-.html).
The selected-member reset role follows [RES](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/timer-and-counter-instructions/reset--res-.html).
Source/destination/length roles follow Rockwell's
[COP/CPS operand reference](https://www.rockwellautomation.com/en-ca/docs/factorytalk-design-studio/current/contents-ditamap/instructions/instruction-set/array--file--misc-instructions/copy-cop-synch-copy-cps.html).

The access classifier requires exactly three nonempty timer operands. Both
pseudo fields must be either a trimmed question mark or a signed ASCII integer
in decimal or radix2/8/16 form. Radix digit separators follow the existing
reference grammar. This is lexical recognition only: numeric ranges, types,
timer units and initialization validity are not checked. A question mark
supplies no value; it must not become zero, a default or a valid setting.

Quoted strings, fractional/exponent forms, typed time literals, expressions,
tag names and malformed numeric forms remain unsupported in those slots.
If either field has such a form, the entire instruction has unknown roles and
status unsupported_operand_form. Wrong arity and empty fields retain their
separate statuses. All original operand text, reference bindings and source
links remain unchanged, including bound-looking pseudo fields in rejected
instructions. CTU/CTD remain unknown because their root reference signatures
are not implemented; this slice does not silently invent counter bindings.

The report labels recognized pseudo fields as initialization fields, explains
their limits beside the rung evidence and shows aggregate placeholder/integer
counts. They are excluded from runtime read/write root groups. A timer root
with an unusable binding still has a known read_write role and an access gap;
a recognized signature does not make the source valid controller code.

## Version and publication boundaries

- Private access2 / instruction-access-2 adds explicit unimplemented
  initialization_analysis and range_analysis flags, the unsupported_operand_form
  status, and timer counters. Review2 and manifest5 retain their outer layouts
  and record the nested access version. Nine private artifacts are saved.
- Access-summary2 / access-summary-2 exposes the same closed counts/metadata
  plus timer_instructions and timer_pseudo_operands_by_kind, partitioned into
  placeholder and integer_literal. Only classified timers contribute; their
  pseudo counts sum to twice their instruction count. No values, names,
  source identifiers, opcode histogram or relationships are published.
- Exact catalogue feasibility subtracts each classified timer's one read_write
  and two non_data slots before checking the original signature capacities.
  RES and COP/CPS already fit those remaining aggregate shapes. Invalid timer
  forms contribute exactly three unknown slots, separately from arbitrary
  unsupported instructions and arity mismatches.
- Work14 requires access2; historical work13 requires frozen access1. New timer
  counts are bounded by published TON/TOF/RTO plus the pooled withheld population,
  because source4 pools lowercase mnemonic spellings. That is a capacity bound,
  not a claim about the withheld instructions. Placeholder/non-data and
  integer/literal reference populations also reconcile. Historical access1 keys, vocabularies,
  constants and validation remain strict. Source inventory3, references6/analyzer9,
  source-summary4, reference-summary12 and SFC2 are unchanged.
- Existing size limits, canonical validation, immutable runs, manifest-last
  publication and report-only local commits remain. The work runner never
  fetches, pulls or pushes. The ignored listener stays disabled.

## Next work-machine run

On feat/bounded-operand-example-pc, from the repository root:

```bash
git pull
bash ./run-work-check.sh
git push
```

Only the generated public feedback is needed. The private HTML is available for
optional later exploration; no source or interface inspection is required now.
Do not send the actual-unit HTML/access.json. The
[invented demo](../../examples/engineering-review-demo.html) shows the interface
without needing plant knowledge.

For an unchanged export with the expected signatures, classified instructions
should rise by 574 to 17,526, unknown instructions fall to 348, read slots rise
to 15,779, write slots to 6,409, read_write slots to 586, non_data slots to 878 and
unknown slots fall to 931. Expected timer counts are 434 and 868 placeholders.
These are conditional expectations, not observed results. Source/reference/SFC
counts, total operands and root-linked population should remain unchanged.
Newly classified unbound accesses can change the gap count. Other unknowns and
bindings keep overall status partial; Phase1 engineering interpretation remains
incomplete. Use the returned populations to choose the next bounded slice.

## Validation

The full tracked development suite passes 592 cases with one existing Windows
symlink-capability skip. The ignored listener loader is excluded. Independent
review passes 32 core/summary cases and 20 workflow cases; there are no remaining
code blockers. Existing reference regressions pass unchanged. JavaScript syntax
and diff whitespace checks pass.

The audit strengthened two envelope checks: classified and rejected-form timers
together consume the published/pool timer capacity; classified and rejected-form
instructions also consume the reference-catalogued capacity. Tests distinguish
these checks from independently valid nested summaries and preserve lowercase
timer recognition without changing source-summary4.

Chrome QA on invented data verifies classified timer totals and pseudo-field
partitions, the separate read_write timer-root occurrences, source/rung links,
initialization labels and explanation, whole-instruction unknown fallback for
a tag-like pseudo field, unresolved timer roots and a copy length's read role.
An old access1 payload renders with current assets without new timer counters;
the current invented demo shows access2. No page JavaScript errors occurred.
The packaged wheel contains exact modules/assets and its extracted renderer
matches the final demonstration bytes. Temporary QA tabs and loopback servers
are closed; no QA listener remains. Direct work-PC file opening and engineering
usability remain optional, unverified user checks.

Two actual isolated work-script runs, using explicit and remembered source
selection, each pass 496 application cases (one existing Windows symlink skip)
and 139 helper cases. Each creates one report-only local commit; no Git network
commands run. All nine artifact hashes, canonical review2/access2 validation and
byte-identical fresh CLI artifacts verify. The source and prior run remain
intact. Seven legacy artifacts match baseline 7cd9201 byte for byte; normalized
source/reference/SFC summaries also match. All 20 historical work reports
validate. These checks use invented data and do not replace the next actual-unit
work-machine run.
