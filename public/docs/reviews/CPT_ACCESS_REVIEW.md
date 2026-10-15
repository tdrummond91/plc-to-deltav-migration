# CPT calculation reads and destination writes

## Confirmed automated run result

Returned `f93f744` tests clean `ae97f10`. All 732 application cases pass with one
expected Windows skip, as do 139 helpers. All 45 CPT instructions now classify,
with 45 parsed containers and 132 bound expression reads across 72 roots. There
are 17,746 classified instructions, 128 unsupported instructions and 505 unknown
source slots. The 321 ordinary binding gaps remain unchanged; expression gaps
are zero. Six other summaries match after revision normalization, and all 28
historical reports validate. This is automated validation, not engineering
feedback or approval of rung purpose. The next work is explained in the
[Phase 1 analysis plan](../planning/PHASE_1_ENGINEERING_ANALYSIS.md).

## Confirmed starting point

Returned `cbb2965` tests clean `456786a`. All 695 application cases pass with
one expected Windows symlink skip, as do 139 helper cases. The access3 extension
classified all 175 projected instructions and 336 operand slots: three counters,
27 messages, five system-value reads and 140 named-step SFC resets. All 175 new
data operands bind to declared roots. There are no new binding gaps.

Classified instructions rose to 17,701 of 17,874, leaving 173 unsupported
instructions and 595 unknown source operand roles. The 321 known-role binding
gaps are unchanged. Six other summaries match the prior return after removing
only `tool_revision`; this is aggregate continuity, not source-byte identity.
All 27 historical work reports validate. The latest work20 report is 31,787 bytes.

The separate calculation2 analysis already parses all 45 CPT expressions into
592 nodes, retaining 132 root-bound reference occurrences and 45 bound
destinations. This slice connects those existing facts to the access report.
Projected work-machine gains are 45 classified instructions, 45 destination
writes, 45 expression containers and 132 separately traced reads. The expected
remaining totals are 128 unsupported instructions and 505 unknown source slots;
these remain projections until the next work-machine return.

## Contract and limits

[Rockwell's CPT documentation](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/compute-math-instructions/compute--cpt-.html)
describes evaluating an expression and storing its result in the destination
when enabled. Access4 records the possible destination write and expression
reads. It does not evaluate the expression, establish execution or infer a
dependency/effect graph, numeric correctness, valid types or member overlap.

An exact two-slot, nonempty CPT has a `write` destination and an
`expression_read` container. A wholly parsed expression contributes one read use
for every reference node, in lexical source order. Repeated references stay
separate, including repeated aliases to one root. Each use retains its canonical
calculation-node ID, source span, rung, operand and instruction links, binding
status and alias/suffix evidence. Literal-only expressions contribute zero tag
reads. No synthetic source operands are invented and no raw expression text is
copied into the access-use records.

The whole expression is never treated as one tag address. Unsupported expression
syntax retains its known container role and explicit syntax gap, with zero
partial reads. A parsed expression can still contain unresolved/unsupported
address leaves. Malformed instruction signatures retain unknown roles. Dynamic
subscripts remain opaque address gaps; no index dependencies are extracted.

Access4 requires the immutable snapshot and canonically replayed calculation2
companion. Its separate `expression_uses` and `expression_roots` collections do
not alter the older source-operand or root-group populations. The existing
default access3 API and explicit access2 replay retain their byte contracts.
Legacy renderers reject populated new fields rather than silently dropping them.

The private access limit stays 32 MiB. Expression uses have their own 250,000
record limit; suffix and alias expansion shares the incremental 8M-character
retention budget with ordinary operands. Access summary4 adds closed counts for
CPTs, expression parsing, read bindings, expression roots and binding gaps.
Work21 requires access summary4 and calculation summary2 and reconciles their
counts. Earlier work1-20 and summary1-3 contracts remain frozen.

Review6/manifest9 retains thirteen hashed artifacts. Current commands request
access4 explicitly after calculation2. Other evidence companions and their
versions remain unchanged. The work runner continues to make only a local
report commit. Pull/push remain manual, and the listener remains disabled.

## Report navigation

Tag access shows **Expression reads** separately from ordinary operand reads,
writes and read/writes. Tags used only within expressions now appear there.
Count links show each occurrence, source span, rung and declaration, including
aliases and repeated uses. Calculation detail remains the canonical syntax view.
Unsupported syntax and unbound reads remain explicit gaps. Historical access2/3
reports keep their earlier columns.

[cpt_access_review_demo.L5X](../../fixtures/synthetic/cpt_access_review_demo.L5X)
extends the independently invented demonstration with an expression-only root,
two uses of its alias, a destination also read in the same expression and a
constant-only expression. Prior fixtures stay unchanged. The
[HTML demonstration](../../examples/engineering-review-demo.html) is generated
from this fixture. No plant source was read to build it.

## Validation

Independent review found and fixed two work21 aggregate defects: PID and CPT
could share one withheld-opcode occurrence, and destination/extended bindings
could claim impossible read/write allocations. Work21 now shares the source
allowance and checks both lower and upper role-allocation bounds after reserving
CPT slots and bound destinations. Work1-20 stay frozen. Regression cases cover
recognized and malformed PID signatures, GSV/SFR writes, unbound destinations,
legacy writes and mixed extended roles. The reviewer independently confirmed
all reproductions reject and checked the allocation formula against all 27,000
small three-role allocation states. Final independent review has no open issues.

Browser checks on the invented fixture verified expression-only roots, three
reads of one root including two repeated aliases, distinct spans `[0, 15)` and
`[18, 33)`, navigation to the selected calculation node, separate destination
writes, explicit unsupported syntax/binding gaps and historical access3 columns.
An adversarial `</script><img ...>` expression rendered as text with zero image
nodes, dialogs or application JavaScript errors. Six new Node DOM cases also
cover aliases, same-root read/write uses, constants, pagination and legacy paths.
The rebuilt demo has 59 rungs and 26 CPT occurrences, including two deliberately
invalid signatures. Its 24 recognized CPT containers include 17 parsed and
seven unsupported expressions; 29 read uses include 27 bound and two gaps.

A separate invented scale check used 4,606 rungs, 17,874 instructions, 6,000 base
roots, 1,000 aliases and 1,000 CPTs. All 3,000 expression reads bound; the full
authenticated review and HTML rendered successfully in 50.18 seconds on this PC.
Access JSON was 31,985,244 bytes, below the 32 MiB limit by 1,569,188 bytes.
Review JSON was 61,933,364 bytes; HTML was 62,046,429 bytes. This measures build
performance, not browser responsiveness or a guarantee for every larger export.

Two final isolated runs of the actual Bash launcher (explicit source, then
remembered source) each passed 732 application cases with one expected Windows
symlink skip and all 139 helpers. Each made exactly one local report-only commit;
31 traced Git calls per run included no network operation. Existing runs and
reports remained byte-identical and both isolated checkouts stayed clean.
Feedback was 31,181 bytes. A conservative projection from the latest returned
plant aggregates, allowing as many expression roots as reference occurrences,
validates at 32,352 bytes, inside the unchanged 32 KiB cap.

All thirteen manifest hashes, canonical review6/access4/calculation2 content and
standalone CLI artifact equality verified. The CLI returned its expected partial
exit code 3. Eleven unchanged artifacts match baseline `cbb2965` byte for byte;
explicit access3 replay also matches its baseline bytes. Tests pin access2/3
private and summary hashes. All six other summaries match after revision
normalization. All 27 historical reports plus both new synthetic reports
validate, with historical bytes unchanged. All 108 final runtime, asset and test
files match the verified isolated checkout.

The final full development suite passed all 839 cases in 95.60 seconds, with
one expected Windows symlink skip and no failures or errors. Listener tests
remain excluded. `git diff --check` passes.

## Next work-machine handoff

On `feat/bounded-operand-example-pc`, manually pull, run
`bash ./run-work-check.sh`, then manually push its local report commit. Supply
the local L5X filename only if the checkout has no remembered source. Return
only the generated bounded feedback. Engineering, source and appearance review
can wait until Tyler is ready; it does not gate the next parser slice.

This remains Phase 1. PID access semantics, other unsupported instructions,
engineering classifications, corrections, PCSD and FHX remain later work.
