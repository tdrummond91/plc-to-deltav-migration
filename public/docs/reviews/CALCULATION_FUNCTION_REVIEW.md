# Legacy CPT function spellings and bounded diagnostics

## Confirmed return (2026-10-15)

Returned `760448e` tests clean `36c0ff4`. All 668 application cases passed with
one expected Windows skip, and all 139 helpers passed. The private run was saved.
All 45 CPT expressions parse into 592 nodes with 132 reference occurrences,
all root-bound; all 45 destinations bind. Four retained function nodes use SQR.
All expression-error and unsupported-function counters are zero. Six prior
summaries match after removing only tool_revision; source-byte identity and
engineering meaning are not established. All 26 historical reports validate.
The report is 31,380 bytes. The next slice is
[extended operand access](EXTENDED_ACCESS_REVIEW.md); no calculation-only rerun
is needed. The implementation-time hypotheses and evidence below are historical.

## Historical returned evidence and next question

Returned `6d19d5e` tests clean `40df4d8`. All 656 application cases passed with
one expected Windows skip; all 139 helpers passed. The private run was saved.
All 45 CPT occurrences have recognized signatures and bound destination roots.
Forty-three expressions parsed into 456 syntax nodes, including 122 reference
occurrences, all root-bound. Two expressions stopped at unsupported function
names. Their names are absent from the count-only feedback, so the cause is not
yet established. They contribute no partial tree or leaf evidence.

The six prior summaries remain equal after removing only tool_revision; this
does not prove byte-identical source. All 25 historical work reports validate.
The latest report is 30,793 bytes, under the existing 32 KiB cap.

## Change and documented basis

The parser now also accepts ACS, ASN, ATN, FRD, SQR, TOD and TRN as single-argument
CPT function spellings. The official
[Logix Designer release notes](https://compatibility.rockwellautomation.com/GeneratedReleaseNote.aspx?v1=66820)
map these older mnemonics to ACOS, ASIN, ATAN, BCD_TO, SQRT, TO_BCD and TRUNC,
respectively. Rockwell's [CPT expression reference](https://www.rockwellautomation.com/en-ie/docs/factorytalk-design-studio/current/contents-ditamap/instructions/instruction-set/compute-math-instructions/compute--cpt-.html)
also lists the older spellings in its function-precedence group. Recognition
does not establish compatibility with a particular controller or firmware.

The private AST retains the source spelling in uppercase, as before; exact case
and whitespace remain in the original expression and source spans. No operator
is rewritten to a newer spelling. Precedence, resource limits, numeric text,
scope/alias binding and whole-expression rejection are unchanged. No expressions
are evaluated, and types, values, dependencies and execution remain unvalidated.
ATAN2 remains outside this deliberately single-argument function grammar.

Older spellings could explain the two reported gaps. That is a hypothesis until
the next work-machine result; this change does not report them as resolved.

## Contracts and report

Calculation2 / calculation-evidence-2 adds two coverage maps to the existing
occurrence/node layout. `functions_by_spelling` has 22 fixed uppercase catalog
keys and counts only function nodes in fully parsed expressions. Its total must
equal the retained function-node count. A failed expression contributes zero
partial function counts even if a supported call appears before its error.

`unsupported_functions` has only atan2 and other keys. It counts the first
unsupported function reached in each expression with that error; its sum equals
the unsupported_function error count. It is not a census of all function text
in rejected expressions. Unknown/private names never become public keys or
values. Lexical, syntax and resource-limit errors do not add a function bucket.

The optional Function coverage panel explains those count populations. The
original calculation1 grammar and byte-stable evidence remain available through
explicit schema_version=1 analysis and version-selected canonical replay.
Calculation-summary1 stays strict; calculation-summary2 includes the new maps.
Work19 requires summary2 and frozen work18 requires summary1. Review6 and
manifest9 remain unchanged, retain thirteen artifacts, and record the actual
nested calculation schema/analyzer. Older optional paths still work.

The 3 KiB summary and 32 KiB work-report caps remain unchanged. Work checks still
make only a report commit locally; pulling and pushing are manual and the
development listener remains disabled. Source-bearing artifacts remain private.

## Historical work-machine run

On `feat/bounded-operand-example-pc`, from the repository root:

```bash
git pull
bash ./run-work-check.sh
git push
```

This tests the older spellings against the two outstanding function gaps and
returns fixed function counts. Only generated feedback is required. Manual
engineering/UI review is optional; Phase 1 continues. Editable corrections,
PCSD and FHX remain later phases.

## Validation

The full development suite passed 764 cases in 74.362 seconds, with one expected
Windows symlink-capability skip. The ignored listener loader was excluded before
import. The independent reviewer passed 49 calculation/core/summary/workflow
tests and compared frozen schema1 against the committed implementation across
29 additional cases. Nested and mixed-case aliases, rejection ordering,
resource limits, dynamic indices and radix literals produced no unhandled
failures or review blockers. Schema1 private and summary byte regressions also
pass. Historical work18 cannot accept calculation-summary2 by transplantation.

Two actual isolated Bash runs, explicit then remembered source, each passed
668 application cases (one skip) and 139 helpers. Both produced work19 with
review6/manifest9 and calculation2, thirteen verified artifact hashes and one
report-only local commit. No Git network commands occurred. Their public
reports are 30,104 bytes. Fresh CLI generation exits 3 and matches all thirteen
artifacts byte for byte. Eleven older evidence files and six revision-normalized
summaries match baseline `6d19d5e` on the same invented input. Explicit current
calculation1 replay reproduces baseline calculations.json byte for byte. All 25
historical reports remain unchanged; both new reports validate. All 100 runtime,
asset and test files in the isolated checkout match the final working files.
Source inputs, earlier runs and the real HEAD were preserved; both temporary
checkouts finish clean. A regression also embeds the new counters into the latest
actual report envelope and verifies it remains within 32 KiB.

Chrome verifies the new function table, fixed first-error counts, mixed-case
source display, separate SQR/SQRT grouping, repeated leaf spans and searches.
An unsupported sibling leaves no partial syntax or leaf evidence. Explicit
calculation1 reports retain their original unsupported result and omit the new
function panel. Script-like text remains inert; no page JavaScript errors occur.
The new independently invented
[function fixture](../../fixtures/synthetic/calculation_function_review_demo.L5X)
has 23 CPT occurrences, with all seven older spellings and deliberate failures.
The [HTML demonstration](../../examples/engineering-review-demo.html) is 599,384
bytes. Older fixture bytes remain unchanged. The prior large-input capacity
check remains historical; this catalog/count extension did not require another
large synthetic run.

The wheel build passes; all 40 packaged modules/assets match source bytes, and
the extracted renderer reproduces the exact final demonstration HTML. The QA
tab and temporary loopback server are closed. The next actual-unit run is still
needed to determine whether the two unsupported functions use these spellings.
