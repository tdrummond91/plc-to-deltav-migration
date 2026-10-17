# Sequence transition expressions

## Confirmed return

Return `3547344` tested clean `a6840f4`: 1,338 application cases passed with two
expected Windows symlink skips, plus 139 helpers. The private report saved with
no failure code. All 42 historical feedback reports validate. All eighteen
earlier summaries are unchanged after removing only tool revision; the six
shared diagnostic examples and eight-unit reservation also remain unchanged.

The timer/counter bundle accounts for 485 occurrences across 441 rungs: 390 TON,
44 RTO, three CTU and 48 RES. All targets have qualified exact addresses. There
are 433 timer objects and three counter objects, with all 48 resets associated
with producers. One object has multiple producer occurrences. All 436 controls
have captured stored data; 2,622 linked elements have matching declared types.
There are 990 address-use associations, including 554 direct members. Incoming
conditions retain 43 binding gaps and nine stored-state dependencies. These are
source relationships, not selected runtime values or simulated timer behavior.

The sequence population is 14 charts, 145 steps and 155 transitions. Each
transition has a captured Condition and STContent; together they contain 329
lines and 5,390 characters. All 324 diagram links resolve structurally. This
export has no captured action bodies, presets or limit expressions. Structural
completeness does not establish the meaning or execution of the conditions.

## Analysis scope

The new companion investigates each captured transition condition, preserving
chart edit versions, original source lines, comments and expression offsets.
It records grouped operators and reference leaves without evaluating values.
Reference resolution uses program/controller scope and aliases, with namespace
qualification. Root binding does not validate a member, array range, operand
type or Boolean result. Unresolved references and unsupported text stay visible.

Source lines follow XML order. Line-number metadata cannot reorder the program.
Missing or conflicting condition wrappers, mixed text shapes, unsupported
syntax and resource limits remain explicit gaps. Rejected syntax does not
produce a guessed partial expression tree. Other SFC text bodies are counted
as outside this slice, and standalone ST routine analysis remains separate.

Rockwell documents transitions as either BOOL expressions or subroutine calls
whose result can be supplied through EOT. A parsed condition alone therefore
cannot establish a chart's execution or transition priority. See the official
[SFC programming manual](https://literature.rockwellautomation.com/idc/groups/literature/documents/pm/1756-pm006_-en-p.pdf)
and [structured-text syntax](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/structured-text-syntax.html).
Operator interpretation follows the
[structured-text programming manual](https://literature.rockwellautomation.com/idc/groups/literature/documents/pm/1756-pm007_-en-p.pdf).
The implemented grammar and exclusions are recorded with the validation below.

The grammar covers numeric literals, exact static addresses, groups, unary
operators, arithmetic, comparisons, equality, AND/&, XOR, OR and the documented
one-argument math function catalogue, including historical spellings. It uses
Logix's separate unary-minus and NOT priorities, separate relational and
equality priorities, and left-to-right evaluation at equal precedence. It
preserves an optional single final semicolon without accepting trailing
statements. See the official
[order-of-execution table](https://www.rockwellautomation.com/en-no/docs/studio-5000-logix-designer/38-03/contents-ditamap/instruction-set/structured-text-attributes/determine-the-order-of-execution.html).

The three documented comment forms retain source spans. Nested comments,
strings, dynamic subscripts, constructs, assignments and unknown functions
remain explicit gaps. JSR is identified as an instruction-call form requiring
further routine/EOT analysis. TRUE/FALSE spellings are resolved as identifiers
instead of being replaced with assumed Boolean values. This grammar describes
source evidence, not controller compilation or numeric validity.

## Workflow and next checkpoint

On the work machine, in the repository folder on `feat/bounded-operand-example-pc`:

```bash
git pull
bash ./run-work-check.sh
git push
```

The runner tests, saves the private report and commits bounded feedback locally.
Git transport stays manual and the listener stays disabled. This bundle requests
no new plant examples and does not require manual engineering review.

The returned counts will show how much transition text is understood, which
references bind, and which unsupported forms need the next analysis pass.
Further sequence relationship work and broader equipment/loop/alarm context
remain Phase 1 work. Team review follows investigation of the remaining
script-addressable questions; a parsed expression is not a finished process
classification or an approved DeltaV mapping.

## Contracts and validation

SFC conditions1 is a bounded private companion with a closed 4 KiB summary.
Review19/manifest22 embeds it while retaining sixteen saved artifacts. Work36
retains the 80 KiB outer report allowance and frozen diagnostic sample request.
The new companion has a 16 MiB allowance, within 264 MiB JSON / 296 MiB HTML
review limits. Earlier companion semantics and historical report readers stay
unchanged.

The independently invented
[diagnostic fixture](../../fixtures/synthetic/sfc_conditions_demo.L5X) exercises
comments, grouped expressions, aliases, unsupported text, metadata gaps, edit
versions and pagination. It includes deliberately invalid source and is not
controller-ready code.

The parser bounds each expression to 65,536 characters, 2,048 tokens and depth
64, with eight million retained expression characters across the companion.
These limits produce explicit gaps or bounded fatal rejections rather than
unbounded recursion. The conservative maximum-width summary is 3,143 bytes;
the whole work36 report is 76,554 bytes, below its 81,920-byte limit.

Thirty-six focused core/summary tests and twelve new workflow cases passed.
The 276 affected existing cases passed, including targeted rechecks after
updating historical-version expectations. Eight
independent DOM cases passed. Independent review also checked fifteen expected
precedence trees, twenty-three rejected edge cases, nine canonical tamper
rejections, four closed-summary rejections and five malformed XML/namespace
cases. A repeated-exponent numeric-token defect, generic JSR classification
and blank compound-node source selection were corrected before final checks.
No outstanding review fixes remain.

The synthetic demonstration has 83 transitions in two separate chart edit
contents: 70 have modeled syntax, three have reference-binding gaps and ten
have unsupported or missing conditions. Its 563 nodes contain 202 reference
occurrences, 198 root-bound. Five comments and two transitions with line-number
metadata gaps remain inspectable. One action-body line remains explicitly
outside this transition-only slice. The private companion is 585,613 bytes;
the [offline report](../../examples/sfc-conditions-demo.html) is 1,118,220 bytes.

An independent dense case with 400 transitions, 6,800 expression nodes,
3,600 alias-member references and 400 comments passed canonical and summary
replay in 3.41 seconds. It produced 7,989,678 private bytes and 2,430 summary
bytes, within their respective allowances.

Browser checks verified the overview entry, search, 50/33 transition pagination,
the last-page detail, fourteen unresolved-evidence rows, separate Original and
PendingEdits conditions, multiline comments, compound-node source spans and
navigation to exact source lines. Script-like comment text remained literal,
with no script elements in report content or horizontal overflow. No report
console errors were observed; the only warnings came from the browser extension.
All relative links in the ten changed Markdown files resolve.

Final verification passed: 1,386 selected application cases with two expected
Windows symlink skips, 139 helper cases and 184 development-only cases. This
covers 1,709 distinct cases; the development guard's nested rerun of selected
suites is not counted again. The ignored listener test was excluded before
import.

The actual Bash launcher ran in an isolated repository against the invented
fixture, with an unavailable remote. It saved a 46,349-byte work36 report,
verified all sixteen artifact hashes and made exactly one local feedback
commit. No Git network operation occurred. The six frozen examples and
eight-unit reservation replayed unchanged. No real confidential files were used.

All sixteen artifact bytes matched across the launcher run, a fresh direct
analysis and the CLI. The CLI returned the expected partial-analysis exit code
3, and its HTML exactly matched the published synthetic demo. Canonical replay
passed for every saved companion. Against the previous release, all fifteen
non-HTML artifacts stayed byte-identical and nine earlier embedded companions
were unchanged. Nineteen previous summaries matched after normalizing only
tool revision. All 42 historical feedback reports stayed unchanged and valid;
the invented report also validated. The 189 final runtime, asset and test files
matched the tested snapshot, and both isolated repositories remained clean.
