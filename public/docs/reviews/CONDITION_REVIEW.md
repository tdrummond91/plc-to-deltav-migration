# Boolean conditions and output actions

## Confirmed relationship return

Returned `f7d91f0` tests clean `ddd087c`: 821 application cases passed with one
expected Windows skip, plus 139 helpers. Private output was saved successfully.
All eight earlier summaries match after removing only tool_revision, and all
30 historical reports validate. These are automated results, not team feedback.

There are 7,591 admitted exact addresses: 3,660 have captured reads and writes,
2,703 have reads only, 1,182 writes only, and 46 unknown roles only. There are
3,778 addresses used across rungs and 1,453 with multiple captured writers.
All 132 CPT read occurrences were indexed; no composed-suffix identity gaps
were found. Different spellings remain separate identities, and these counts do
not establish channel validity, absence of external access or unused logic.

The stronger patterns group 4,286 rungs into 1,489 patterns. The remaining 320
rungs have explicit exclusions: 128 contain an instruction without modeled
operand roles and 192 have unresolved addresses. This does not supersede the
existing rung identification categories, which have a different scope.

Only one eligible local calculation link was found, a CPT input occurrence.
There were 830 eligible instructions, 3,991 other instructions acting as local
barriers and 13,053 instructions excluded because their rungs contain branches.
This motivates explicit series/parallel condition analysis; it does not mean the
plant has only one calculation chain or connection.

## Local condition graph

The new private companion follows the captured ladder tree in source order.
Each parsed rung begins with a rung-entry node. This represents the incoming
evaluation context, not a constant true value or proof that the routine runs.
Series conditions form ALL nodes. Parallel legs receive the same incoming node
and their resulting conditions form ANY nodes. Empty legs and shared nodes are
preserved without expanding all combinations of paths.

Recognized `XIC`, `XIO`, `EQU`, `NEQ`, `LES`, `LEQ`, `GRT`, `GEQ` and `LIM`
signatures contribute individual predicate occurrences. Their operands link to
the existing source/access/address evidence. No values are evaluated and no
type, member or array-bound validity is inferred. `LIM` remains its own source
predicate; wrapped bounds are not rewritten as an ordinary between comparison.
Binding gaps remain distinct from unmodeled instruction behavior.

Repeated reads are not merged by address or simplified away. Each predicate
belongs to a specific instruction occurrence. A write between reads, asynchronous
I/O or another execution context can change the observed value. The graph is an
explanation of local condition structure, not a simultaneous Boolean equation
over one immutable set of tag values.

Other blocks produce an explicit unknown transfer of their incoming condition.
They are not silently skipped or represented as an additional AND contact:
that would assume behavior which this analyzer has not modeled. An opaque leg
remains visible even beside an empty bypass. Its source and previously known
operand effects remain available in the other report views.

## Output actions

Each captured `OTE`, `OTL` or `OTU` has an output record, including malformed
signatures and unresolved targets. A supported output captures its incoming
condition and passes that condition onward under the documented normal-scan
instruction convention. Its target binding and guard quality are separate.

| Instruction | Incoming condition true | Incoming condition false |
|---|---|---|
| OTE | Set the bit | Clear the bit |
| OTL | Set the bit | Leave the bit unchanged by this instruction |
| OTU | Clear the bit | Leave the bit unchanged by this instruction |

These describe the individual instruction when evaluated normally. They do not
model prescan/postscan, task scheduling, routine calls, MCR zones, faults,
communications, other writers or final scan values. A module input/output
declaration supplies source context; it does not confirm a physical channel,
device, alarm, permissive or shutdown function.

## Reading the report

Conditional outputs provides searchable, paged output records, separate action
and condition-quality labels, and links to source rungs and exact addresses.
An output dossier shows each reachable condition node once. Short local labels
and child links preserve shared subgraphs instead of repeating a potentially
exponential expression. Rung and address dossiers link back to relevant outputs.
Unmodeled transfer nodes show exactly where the next analysis work is needed.

Readable reporting and reusable private records remain parallel outputs. The
public feedback contains fixed aggregate counts only. Git synchronization stays
manual, the script commits only its newly validated feedback report locally,
and the development listener remains disabled.

## Contracts and validation

Condition schema 1 (`condition-analysis-1`) adds `boolean-conditions.json` to
review 9 / manifest 12: sixteen hashed private artifacts. Work-check 24 adds
condition summary 1, a closed count-only contract capped at 4 KiB. Work22-24
allow a 48 KiB outer report; work1-21 retain their 32 KiB caps. The private
condition document is bounded to 32 MiB, 250,000 records and two million linked
IDs. Review JSON/HTML retain their 128/160 MiB bounds. Earlier optional report
versions remain available and their prior artifacts are unchanged.

Completed development validation:

- Full development suite: 1,012 tests passed, including one expected Windows
  symlink skip. Listener tests were excluded before loading.
- Independent review: no blocking findings; 60 condition core, summary,
  workflow and UI tests passed. An additional independent oracle checked 105
  invented sources across 630 graph evaluations, including a non-AND opaque
  transfer, nested branches, empty bypasses and repeated reads around writes.
- Two actual isolated Bash launcher runs, first with an explicit invented input
  and then with the remembered path: 870 application tests and 139 helpers passed
  each time. Both saved private output, committed exactly one new validated
  public report and preserved previous runs. Git traces contained 31 local
  commands per run and zero network operations. The outer reports were 39,017
  bytes, below the 48 KiB limit.
- Verified all sixteen manifest hashes, canonical review/condition records,
  byte-identical artifacts across both runs and the direct CLI, and unchanged
  earlier reports. All thirty historical reports plus the two synthetic returns
  validate. Fourteen earlier non-HTML artifacts match the preceding implementation
  byte for byte; all nine prior summaries match after revision normalization.
- The 120-rung invented demo includes 52 coil occurrences and 356 condition
  nodes. Chrome checks covered search, pagination, nested joins, unknown transfers
  beside empty bypasses, node operands, back navigation and legacy absence of
  conditional-output navigation. The delivered HTML matches its generated demo.
- Dense synthetic scale: 4,606 rungs, 17,874 instructions, 7,000 exact addresses,
  5,625 output occurrences and 22,480 condition nodes. Conditions occupied
  20,041,878 bytes; review JSON 109,099,337 bytes and HTML 109,259,450 bytes.
  Generation completed in about 91 seconds locally. Chrome loaded the full
  report, paged the 5,625 outputs and opened an individual guard without document
  horizontal overflow. These timings and sizes describe invented inputs, not
  the private plant export.

The next normal work-machine run is needed to measure real condition coverage.
The previous source census contains 1,687 OTE, 1,174 OTL and 1,302 OTU
occurrences (4,163 total); the new summary must account for them and distinguish
modeled guards, binding gaps, opaque transfers and unresolved output targets.
An overall partial result remains expected while broader semantics are unfinished.

## Next analysis work

Continue the [Phase 1 completion gate](../planning/PHASE_1_ENGINEERING_ANALYSIS.md).
This layer supplies local condition structure for later loop, equipment, alarm
and sequence analysis. Remaining transfer semantics, cross-rung relationships,
AOIs and non-RLL content are development work, not questions prematurely handed
to engineers. No manual or team review is requested at this checkpoint.

## Primary reference context

Rockwell's [ladder programming manual](https://literature.rockwellautomation.com/idc/groups/literature/documents/pm/1756-pm008_-en-p.pdf)
describes condition/action structure and the possibility of asynchronous I/O
changes between reads. Its [branch documentation](https://www.rockwellautomation.com/en-us/docs/factorytalk-design-studio/current/contents-ditamap/using-the-software/ladder-editor/add-a-ld-branch-to-a-routine.html)
describes parallel alternatives. The [XIC reference](https://www.rockwellautomation.com/en-hu/docs/studio-5000-logix-designer/37-00/contents-ditamap/instruction-set/bit-instructions1/examine-if-closed--xic-1.html)
and [general instruction manual](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm003_-en-p.pdf)
provide instruction context. The action distinctions above follow the
[OTE](https://www.rockwellautomation.com/en-us/docs/factorytalk-design-studio/current/contents-ditamap/instructions/instruction-set/bit-instructions/output-energize--ote-.html),
[OTL](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/bit-instructions1/output-latch--otl-1.html)
and [OTU](https://www.rockwellautomation.com/en-gb/docs/studio-5000-logix-designer/38-03/contents-ditamap/instruction-set/bit-instructions1/output-unlatch--otu-.html)
execution tables. These references do not establish any particular plant rung's
purpose or approve its migration.
