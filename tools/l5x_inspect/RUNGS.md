# Stage 4: rung structure inventory

This stage follows the reviewed Stage 3 profile. It reads the original local L5X
and produces `public/rung-structure.json`: coverage, instruction/branch counts,
shape groups, source locators and selected sanitized examples. It does not modify
the source or the application.

## Files and responsibilities

```text
tools/l5x_inspect/
  inspect_rungs.py        argument handling and console summary
  rungs/
    __init__.py
    syntax.py            pure parser, structural metrics, dummy forms
    inventory.py         XML reading, coverage, grouping and report publication
  tests/
    test_rung_syntax.py
    test_rung_inventory.py
```

The existing `summarize_xml.py` supplies XML preflight and atomic JSON output.
Prior helpers stay unchanged. The parser/metrics module has no file or CLI work,
so future views can reuse its results.

## Run

From the repository root:

```bash
uv run --project python-parser python -B tools/l5x_inspect/inspect_rungs.py --help

uv run --project python-parser python -B tools/l5x_inspect/inspect_rungs.py \
  "confidential/plc-code/YOUR_FILE.L5X"
```

Use the original export. The blank skeleton has no instruction text to analyze.
Default output is `public/rung-structure.json`. A successful or partial run
replaces that report; use `--output PATH` to retain another attempt.

`--top 5` selects up to five distinct shapes per ranking: tallest, widest, deepest,
and most frequent. This is the default. Supported values are 1 through 20.
The selected examples are deduplicated across rankings.

## What is counted

| Metric | Definition |
|---|---|
| instruction_calls | Outer ladder instruction calls; nested functions inside operands do not add calls |
| argument_slots | Comma-separated outer argument positions, including empty positions |
| nonempty_argument_fields | Nonblank outer arguments; no expression evaluation |
| expression_instruction_calls | CMP, CPT, FAL and FSC calls; not inner math operations |
| branch_groups | Square-bracket groups outside instruction argument lists |
| branch_legs | Sum of the legs in those groups; not expanded end-to-end paths |
| empty_branch_legs | Legs containing no instruction or nested branch |
| max_branch_depth | Maximum nesting of branch groups; unbranched is zero |
| max_legs_in_group | Largest number of legs in any one group |
| height_lanes | Instruction or empty sequence height 1; series takes max; a branch sums leg heights |
| width_instructions | Instruction width 1; series adds widths; a branch takes max leg width |

Height and width are normalized structural measures, not Studio 5000 pixels,
screen rows, text length, timing, or proof of behavioral complexity. Junction and
wire width is excluded. Separate branches in series do not multiply the height.

An invented example:

```text
[XIC(ARG_001),XIO(ARG_002)XIC(ARG_003)]OTE(ARG_004);

|--+--[XIC]----------+--(OTE)--|
|  +--[XIO]--[XIC]--+         |
```

This has 4 instructions, 1 branch group, 2 legs, depth 1, height 2 lanes,
and width 3 instruction boxes. The drawing above is explanatory; this helper
does not yet provide a general ASCII renderer.

Array brackets in `XIC(Array[3])` do not create a branch. Brackets and commas
inside quoted arguments or nested argument delimiters are also kept inside the
argument. All argument contents remain opaque to semantic analysis.

## Report navigation

- `coverage`: XML/ladder rung counts, parsed/unparsed counts, failure categories,
  empty-instruction rungs, ignored non-ladder Rung elements, and metadata findings.
- `instruction_counts`: counts from successfully parsed rungs only.
- `totals_for_parsed_rungs` and `maxima_for_parsed_rungs`: explicit metric scope.
- `patterns`: each ordered instruction/arity/branch shape, occurrence count and
  list of rung IDs.
- `rungs`: one record for every encountered ladder rung, including an ordinal
  XML locator, rung Number/Type, parse status and pattern ID or error.
- `rankings`: pattern IDs ordered by structural measures or frequency.
- `samples`: one sanitized representative per selected pattern, including a
  nested tree and neutral-text-shaped string.

A shape ignores argument values, argument reuse and inner expression structure.
For example, two CPT calls with different calculations may belong to the same
shape. Shape equality is not semantic equivalence or a conversion rule.

Ties use first source occurrence. Rankings choose distinct shapes so repeated
copies do not crowd out other examples. If any rungs are unparsed, rankings cannot
claim to include the largest unknown rung.

## Source information retained and removed

Retained intentionally: approved public instruction mnemonics, ordered branch
layout, instruction arity, numeric rung Number, approved rung Type, XML element
names, source-order locators, and counts.

Every nonempty whole argument becomes ARG_001, ARG_002, and so on. Identical
stripped argument text shares a label within that sample. Labels restart for the
next sample; they do not establish cross-rung tag identity. Constants, full tag
references, member/array expressions, quoted strings and calculations are all
replaced. Empty argument slots stay empty.

An instruction name outside the initial public list becomes UNLISTED_OP_0001,
etc., consistently within this run. This does not mean the instruction is invalid
or custom; the initial permission list is intentionally incomplete. Original
unlisted names never enter the report.

No raw source comments, program/routine/tag names, operand text, input filename,
input path, or source hash are exported. The original-to-placeholder association
exists only in local process memory in this slice. Ordinal XML locations support
back-reference to this input and its full skeleton; they are not stable IDs across
reordered exports.

The samples are structure examples, not importable Studio 5000 code or a complete
minimized L5X. They retain patterns as the user authorized. Review the public
report before sharing or committing it.

## Supported syntax and limits

The parser recognizes adjacent instruction calls, optional whitespace, balanced
argument delimiters, quoted argument text (including dollar escapes/doubled
quotes), nested square-bracket branches, empty branch legs, and a final semicolon.
It does not validate instruction arity, argument types, calculation syntax,
reference resolution, jumps, scan behavior, or operation safety.

The starting grammar and mnemonic/rung-type permissions were checked against
[Rockwell's Logix 5000 Import/Export Reference Manual](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf),
chapter 9. Actual-export coverage is established by the next local run, not by
those reference examples alone.

Limits: 2,000,000 text characters per rung, 20,000 instruction/branch nodes per
rung, 64 nested branch/argument levels, and the existing XML preflight limits.
Unsupported syntax produces an unparsed rung with an error code and zero-based
character offset. Raw snippets are never included in diagnostics.

## PASS, PARTIAL and fatal errors

- **PASS**: every encountered ladder rung was structurally parsed; this does not
  establish instruction semantics or controller import validity.
- **PARTIAL**: the JSON was written, with unparsed rungs identified. Measured
  totals exclude those rungs. A valid run returns exit code 2, so your prompt may
  show a failure symbol even though the diagnostic report was saved.
- **Error**: fatal XML/file/argument problem. Do not treat an older existing JSON
  as the result of this attempt.

For the unchanged source already inspected, coverage should find **4,606 ladder
rungs**. Parsed count, shape count and complexity maxima remain unknown until the
user runs this helper. Return the console summary and review the JSON. Resolve
any partial coverage before relying on maxima or building the minimized L5X.
