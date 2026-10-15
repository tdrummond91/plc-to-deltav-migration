# Independently synthetic L5X fixture

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
The [HTML demonstration](../../examples/engineering-review-demo.html) now uses
pid_member_review_demo.L5X. The original fixtures and their existing origin/hash
contracts remain unchanged. See the [PID checkpoint](../../docs/reviews/PID_EVIDENCE_REVIEW.md)
and [stored-data checkpoint](../../docs/reviews/TAG_DATA_REVIEW.md) for scope and validation.
