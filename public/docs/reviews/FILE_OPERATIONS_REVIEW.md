# File and array operation evidence

## Confirmed return and next scope

Return `f2165d5` tested clean `fb49ecf`: 1,532 application cases passed with
two expected Windows skips, plus 139 helpers. All 48 historical reports validate.
The 22 preceding summaries and the frozen six-example envelope are unchanged.
The private run saved successfully. Signal context accounts for 12,741 condition
operands, 5,064 exact signal addresses and 4,163 output occurrences. Its predicted
12,608 predicate slots plus 133 ONS storage slots match the returned counts.

Total run time was 709.736 seconds (11:50), up 63.194 seconds. Analysis, saving
and summary construction contributed most of that increase. One run does not
establish a performance trend.

The access catalogue still reports 128 unsupported instructions. Most already
have specialized evidence: 76 JSR calls, 46 PID occurrences, SBR/RET and one
declared custom instruction. AVE, FAL and SQO are three standard blocks whose
slots were still only recognized by mnemonic. This bundle covers those three
alongside COP/CPS, explaining the range context missing from scalar calculations.
The returned opcode and structural counts predict 95 operations and 294 slots:
92 COP and one each AVE, FAL and SQO. These are expectations for the next run,
not confirmed coverage of the new analyzer.

## Interpretation

| Instruction | Neutral-text slots | Evidence supplied |
|---|---|---|
| COP / CPS | source, destination, length | Starting addresses and length measured in destination elements |
| AVE | array, dimension, destination, control, length, position | Averaging region selector, destination and control association |
| FAL | control, length, position, mode, destination, expression | Iteration selector, expression tree and reference/index occurrences |
| SQO | array, mask, destination, control, length, position | Position-selected source, mask and destination read/write role |

The FAL destination precedes the expression in neutral text. LEN/POS are
pseudo-operands for control initialization, kept apart from ordinary runtime
reads. SQO preserves unmasked destination bits, so its destination is a possible
read/write. Modes, dimensions and pseudo-fields retain their authored spelling;
invalid forms stay visible.

FAL uses the existing bounded arithmetic parser. Unsupported expression syntax
produces a whole-expression gap. Symbolic indices preserve their root and the
inputs used to select an element, without manufacturing an exact element.
Namespace qualification includes source ancestry, aliases and declaration
dependencies. Rejected namespace evidence remains inspectable but cannot become
a qualified address association.

Control declarations and stored representations retain their separate source
links. Array starts, lengths and selectors do not establish bounds, overlapping
memory, live values, execution or physical outputs. No memory span is expanded,
and the Boolean transfer model remains unchanged. Existing access and rung
summaries remain available as the base catalogue; private reports link their
specialized file-operation evidence beside those older gaps.

## Contracts

File operations1 is an 8 MiB private companion embedded in review23. Review JSON
and HTML limits are 336 MiB and 368 MiB; manifest26 retains sixteen artifacts.
Work41 adds a closed summary within a 104 KiB envelope. Earlier contracts keep
their limits and meaning. Timing1 and the six-example/eight-unit reservation
remain unchanged. No additional source samples are requested.

## Validation

The actual Bash launcher passed 1,569 application cases (two expected Windows
skips) and 139 helpers in an isolated checkout containing only invented source.
It committed one validated feedback report locally, with zero Git network calls.
The 76 development workflow cases also passed. All 37 new production-selected
cases passed with process/socket creation blocked before import.

Independent review found and verified fixes for quadratic control-array data
matching, missing control/storage gaps in the report filter, and an aggregate
validator that admitted inconsistent operand roles. No review blockers remain.
Two DOM cases cover 50/15 pagination, opcode/gap filters, FAL destination and
expression order, symbolic index/source links, SQO preservation, stored data,
edit context, malformed expressions and namespace quarantine. Fourteen existing
rung-view cases passed after the base-catalogue wording change.

Browser inventory was empty in this session, so visual browser layout has not
been verified. The scoped local QA server was stopped. Automated DOM checks
establish navigation behavior, not a visual review.

Two saved runs passed canonical validation. All sixteen artifact bytes agree
between work-check, direct analysis and CLI. Fifteen older nonreview artifacts
are byte-identical to the preceding revision; all 23 preceding summaries agree
after tool revision normalization. All 48 historical reports remain unchanged;
49 reports validate including the isolated generated return. The final runtime
and test files match the tested checkout. The LF-normalized invented fixture
reproduces the committed HTML demo byte-for-byte through the CLI.

The conservative report reservation is 92,915 bytes, below 104 KiB. The frozen
six-example/eight-unit envelope replays unchanged. Local release evidence is in
`C:/Users/tyler/AppData/Local/Temp/plc-file-operations-final-94cmmdth`;
independent integration/guard evidence is in
`C:/Users/tyler/AppData/Local/Temp/plc-file-operation-integration-golsj3zo`.

## Next work-machine run

Use the ordinary manual pull/check/push workflow. The run will measure the
95 predicted operations, their slots, FAL expression/index gaps and stored
control coverage. Expected new source recognition is three instructions and
18 slots, subject to their actual forms and qualification. Earlier summaries
must remain unchanged after tool revision normalization.

This remains Phase 1. The next interpretation work should connect supported
Boolean patterns to precisely attributed alarm/equipment evidence. Rung-wide
alarm words cannot classify every coil on the rung. No manual engineering or
team review is required at this checkpoint.

## Primary references

- Rockwell [Logix 5000 Import/Export manual, neutral-text forms](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf), printed page 215 for FAL.
- Rockwell [neutral-text instruction table](https://www.rockwellautomation.com/en-se/docs/factorytalk-design-studio/current/contents-ditamap/code-editor-dsl-syntax/neutral-text-for-ladder-instructions.html).
- Rockwell [File Average](https://www.rockwellautomation.com/en-za/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/array-file-misc-instructions/file-average-ave.html).
- Rockwell [File Arithmetic and Logic](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-01/contents-ditamap/instruction-set/array-file-misc-instructions/file-arithmetic_logic-fal.html).
- Rockwell [Sequencer Output](https://www.rockwellautomation.com/en-sg/docs/factorytalk-design-studio/current/contents-ditamap/instructions/instruction-set/sequencer-instructions/sequencer-output--sqo-.html).
- Rockwell [pseudo-operand initialization](https://www.rockwellautomation.com/en-cz/docs/studio-5000-logix-designer/38-03/contents-ditamap/instruction-set/pseudo-operand-initialization.html).
