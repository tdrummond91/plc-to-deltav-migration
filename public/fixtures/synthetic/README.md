# Independently synthetic L5X fixture

## Current instruction condition-transfer demonstration

`condition_transfer_review_demo.L5X` extends the previous condition fixture
with 71 invented rungs (191 total). It exercises all 17 documented transfer
spellings, noncoil contexts, false-state explanations, data and signature gaps,
unknown ancestry, repeated reads around writes, branches and empty bypasses.
Sixty additional move occurrences exercise pagination. Markup-like source text
tests inert rendering. No private source was used to construct this fixture.
The [HTML demo](../../examples/engineering-review-demo.html) now uses review10
and includes Instruction conditions. Earlier fixtures remain unchanged.

## Historical condition demonstration

`condition_review_demo.L5X` independently extends the relationship demo with 28
invented rungs (120 total). Cases include nested series/parallel conditions,
empty bypasses, outputs within legs, shared guards, repeated reads after writes,
opaque block transfers, invalid signatures, identity gaps, comparison predicates,
first-scan flags and module-root context. These exercise the analyzer; they are
not validated controller logic or extracts from a plant export.

The HTML demo previously used review9 and added Conditional outputs.
Earlier independent fixtures remain unchanged.

## Historical relationship demonstration

`relationship_review_demo.L5X` independently extends the earlier rung demo with
20 invented rungs (92 total) and eight declarations. Cases cover exact aliases,
repeated CPT reads, self-read/write ordering, overwritten local producers,
whole-object/member barriers, branches, conditions, unknown effects, copy ranges,
invalid composed alias suffixes, distinct index spellings and operand-reuse versus
literal differences. These are analyzer cases, not validated controller logic.

The generated [HTML demo](../../examples/engineering-review-demo.html) uses
review8 and includes Address relationships. Existing fixture files are retained.

## Historical rung-analysis demonstration

[rung_analysis_review_demo.L5X](rung_analysis_review_demo.L5X) extends the
independently invented CPT access fixture with module input/output roots,
conditional outputs, branching outputs, empty bypasses, an unsupported block,
empty/unparsed rungs, ambiguous comments, missing metadata and weak PID/alarm/
equipment hints. All names, values and connections are invented. The
[current HTML demo](../../examples/engineering-review-demo.html) uses this fixture.
These deliberately mixed cases are parser examples, not controller-ready logic.
Earlier fixtures remain unchanged. See
[rung-analysis review](../../docs/reviews/RUNG_ANALYSIS_REVIEW.md).

## Historical CPT access demonstration

[cpt_access_review_demo.L5X](cpt_access_review_demo.L5X) extends the independently
invented extended-access fixture with an expression-only root, repeated reads
through its alias, a destination read within its own expression, and a constant
expression. The [current HTML demo](../../examples/engineering-review-demo.html)
previously used this fixture. No plant source or connections were read to construct it.
Earlier fixtures remain unchanged; these are parser cases, not controller-ready
logic. See [the CPT access contract](../../docs/reviews/CPT_ACCESS_REVIEW.md).

## Legacy calculation function demonstration

[calculation_function_review_demo.L5X](calculation_function_review_demo.L5X)
extends the invented calculation demo with all seven older function spellings,
mixed-case and nested calls, unsupported functions, wrong arity and first-error
cases. All names, values and connections are independently invented. It is not
an executable controller project. The earlier function HTML demo used this fixture;
all earlier fixture bytes and their historical validation remain intact.

## Calculation report demonstration

[calculation_review_demo.L5X](calculation_review_demo.L5X) extends the independently
invented PID member demonstration without changing that earlier fixture. It adds
CPT grouping, precedence, functions, repeated references, aliases, static and
dynamic subscripts, unresolved roots, unsupported syntax and invalid signatures.
Its deliberately invalid cases exercise evidence gaps; this is not a controller
project. No real export was read to invent these expressions. The generated
[HTML demonstration](../../examples/engineering-review-demo.html) includes this
fixture's calculation view. The original fixture hash below still applies only
to controller_demo.L5X.

This fixture was invented from generic L5X structure. It was not produced by renaming tags or preserving connections from a plant export. No confidential L5X or DeltaV export was read to construct it.

## Included cases

- Two programs with independently scoped LocalSignal tags and same-named MainRoutine routines.
- Three ladder routines containing nine rungs.
- Series contacts, parallel branches, nested branches, a timer, an alias, and an array operand.
- A local JMP/LBL pair and a JSR call to a helper routine.
- A user-defined structure and invented French descriptions with ambiguous shorthand.
- Two configured periodic tasks with different rates.
- One synthetic module envelope and one empty SFC envelope for inventory counts.

The module has no real hardware configuration. The SFC envelope contains no steps or transitions. This is a structural parser fixture, not a validated Studio 5000 project or executable control design.

## Files

| File | Purpose |
|---|---|
| [controller_demo.L5X](controller_demo.L5X) | Small UTF-8 input |
| [origin.json](origin.json) | Synthetic declaration and exact-file SHA-256 |
| [expected_inventory.json](expected_inventory.json) | Manually specified counts, scopes, and intended findings |
| [rung_1.expected.txt](rung_1.expected.txt) | Manually drawn branch connectivity |
| [Fixture checker](../../tools/check_fixture.py) | Standard-library read-only sanity checks |

Expected totals: 15 tag definitions, 4 routines (3 RLL and 1 SFC), 9 rungs, 25 instruction occurrences. Structure members and array elements do not count as additional tag definitions. An alias counts as one tag definition. The empty SFC contributes one routine and zero RLL rungs.

## User-run checks

From the repository's python-parser directory:

```bash
uv run python -B ../public/tools/check_fixture.py
uv run python -B ../public/tools/check_fixture.py --with-l5x
```

The first command uses standard-library XML parsing and compares the fixture to expected counts and SHA-256. The second also checks the installed l5x package's tag access. The --with-l5x option is a boolean switch: argparse action="store_true" sets it to True when present and False when omitted. Python -B disables bytecode cache writes; uv can still manage its environment normally when you run it.

Checks exit with 0 on success and 1 on failure. Tyler ran the --with-l5x check on 2026-10-08 and supplied terminal output reporting PASS for the hash, XML, counts, scopes, schedules, and l5x tag access. Codex did not execute Python independently.

Changing fixture bytes deliberately requires reviewing the origin hash and expected results. Do not derive expectations from the parser being tested; preserve independently reviewed expected behavior.

## Boundaries

This is one small positive fixture. Add separate examples for malformed XML, encoded routines, unsupported instructions, partial exports, AOIs, real SFC syntax, and control-flow edge cases as those milestones begin.

The existing prototype may fail or partially render some cases; record those gaps. Passing the checker only verifies the fixture's internal contract, not the prototype's parser, a future GUI, or runtime behavior.

The supplied root .gitattributes keeps text fixtures in LF format across Git checkouts so their exact-file hashes remain portable.

## Module I/O example

[module_io_demo.L5X](module_io_demo.L5X) is a separate, independently invented
fixture. The original fixture's origin hash and checker apply only to
controller_demo.L5X. This new example is not a validated Studio 5000 project.

Expected structural counts: four modules, five ports, two connections, two each
of InputTag/OutputTag/ConfigTag, three ordinary tags, two aliases, two rungs and
five instructions. All six I/O declarations deliberately omit Name. Three names
come from the local backplane slot and three from a direct Ethernet module;
the latter uses connection-specific I1/O1 suffixes. One alias and six operand
occurrences bind. One alias and one operand stay unresolved with
colon_root_not_declared. Reference status is partial; structure status is complete.

```bash
uv run --project python-parser plc references public/fixtures/synthetic/module_io_demo.L5X
```

The [aggregate example](../../examples/module-reference-summary.synthetic.json)
contains only counts. Its revision is deliberately unavailable, so it is not
presented as an actual work-machine run. Neither example contains plant data.

## Engineering review demonstrations

[engineering_review_demo.L5X](engineering_review_demo.L5X) contains invented
ladder/SFC evidence for report navigation. The separate
[tag_data_review_demo.L5X](tag_data_review_demo.L5X) extends that demonstration
with illustrative PID/timer members, an array, string text, duplicate Data
representations and an unsupported vendor format. Its values and connections
are independently invented, and neither file is controller-ready logic.

The new [pid_review_demo.L5X](pid_review_demo.L5X) adds seven PID occurrences,
including one deliberately invalid signature. It distinguishes the Tieback
operand from the saved SP member. Cases include alias reuse, an explicit master
operand, duplicate representations/members, missing and opaque-only data, and
a nested-member association gap. All values and relationships are invented.

The [PID member demonstration](pid_member_review_demo.L5X) adds a complete
51-entry catalog example and a separate incomplete structure with a mixed-case
duplicate, wrong/missing types, empty value, unknown member and unexpected DATA
dimensions. Its nine PID occurrences include the earlier association gaps.
All values remain invented, including deliberately nonnumeric saved text.
The earlier PID member HTML demonstration used pid_member_review_demo.L5X;
its cases are retained in the current CPT access fixture. The original fixtures and their existing origin/hash
contracts remain unchanged. See the [PID checkpoint](../../docs/reviews/PID_EVIDENCE_REVIEW.md)
and [stored-data checkpoint](../../docs/reviews/TAG_DATA_REVIEW.md) for scope and validation.

## Extended operand access demonstration

`extended_access_review_demo.L5X` independently extends the invented calculation
example with CTU/CTD, MSG, GSV/SSV and SFR examples. It includes alias-backed
controls, a blank system instance, selector/tag name collisions, the initial-step
zero sentinel, unresolved/dynamic addresses and deliberately malformed forms.
It is not controller-ready logic. The generated
[offline demonstration](../../examples/engineering-review-demo.html) shows
original reference findings separately from access-owned bindings.
