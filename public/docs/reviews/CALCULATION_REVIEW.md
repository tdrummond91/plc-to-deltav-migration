# CPT calculation expression evidence

## Confirmed work-machine result (2026-10-15)

Returned `6d19d5e` tests clean `40df4d8`: 656 application cases (one expected
Windows symlink skip), 139 helpers and a saved private run. All 45 CPT signatures
and destinations are recognized/root-bound. Forty-three expressions parse into
456 nodes, including 122 reference leaves, all root-bound. Two expressions are
unsupported because of function names; all other syntax-error counters are zero.
Those two contribute no partial nodes or reference counts. This is syntax/root
evidence, not numeric, type, execution or engineering validation.

Six previous summaries match `564fa66` after removing only tool_revision.
All 25 historical feedback reports validate; the new report is 30,793 bytes.
Aggregate equality does not establish source byte identity. The next
[function follow-up](CALCULATION_FUNCTION_REVIEW.md) accepts documented older
spellings, which may explain the gaps; their actual names are not in this report.
The original implementation/validation record below remains historical.


## Purpose and current boundary

This Phase 1 companion exposes the structure inside CPT expressions that the
existing reference layer deliberately retains as unsupported expressions. The
original references and access roles remain unchanged. The new view records
grouping, operators, literal spellings and scoped reference leaves, with exact
source spans and separate records for repeated uses. It does not calculate
results, validate types/ranges or establish dependencies, execution effects,
controller compatibility or approved DeltaV mappings.

Returned `564fa66` confirms the preceding PID member slice: 46 distinct linked
structures, all 51 catalog fields exactly once, 2,300 scalar headers and 46 DATA
array headers matched, with no missing/duplicate/type/shape gaps. It passed 619
application cases (one existing Windows skip) and 139 helpers. Six earlier
summary populations remain equal after revision normalization; this does not
prove source byte identity. Numeric PID values and DATA contents remain raw
evidence. All 24 historical feedback reports validate.

## Grammar and source evidence

The grammar uses documented CPT precedence and left-to-right grouping at equal
precedence. Exponentiation precedes unary minus and NOT. Accepted forms include
numeric spellings, lexical addresses, grouping, unary and binary operators and
a fixed catalog of single-argument functions. The parser is bounded and never
evaluates source text. These choices follow the official
[Studio 5000 CPT reference](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/compute-math-instructions/compute--cpt-.html)
and [expression operator reference](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/compare-instructions/valid-operators.html).
Controller/version acceptance and legacy function aliases remain outside this
first grammar. Subscript expressions have a different grammar; dynamic array
addresses remain single unresolved leaves, without index-expression analysis.
Malformed address syntax rejects the entire expression. An unparenthesized
signed exponent is conservatively unsupported in this grammar; the explicitly
parenthesized form remains supported. Neither rule rewrites the source.

Two nonempty operands are required for a recognized signature. Unsupported or
incomplete expressions keep a fixed error category and source offset, but no
partial tree or leaf bindings. A parsed expression can still have unresolved
roots or an unbound destination. Literal destinations never become bound writes.
The inherited resolver follows program/controller and AOI lexical scopes,
aliases, cycles and static suffixes. A resolved root does not validate its member
path, array bounds, XML namespace semantics or runtime value.

Each occurrence links the original instruction, rung and operand IDs. Flat tree
nodes carry parent-child IDs and source character spans. Reference leaves carry
canonical resolver evidence; numeric leaves retain their original spelling.
Snapshot, inventory and references are authenticated before canonical replay.
Expressions are limited to 4,096 characters, 512 tokens and depth 64. Total
instruction/node/operand populations and the 16 MiB private evidence/JSON budget
are bounded. Unsupported syntax stays a visible gap.

## Report and workflow

Calculations has search, syntax filtering, a paged syntax outline and a separate
reference-use list. Repeated leaves remain separate, with spans, alias evidence
and declaration links. Rungs and declarations link back to their calculation
occurrences. Unsupported expressions display exact source and a fixed gap
explanation. The older report path has no Calculations section.

Private calculation schema1 is added to review6 after the existing PID member
companion. Manifest9 adds `calculations.json` as the thirteenth hashed artifact.
Omitting it preserves review5/manifest8. Work18 adds calculation summary1, with
fixed count-only keys, syntax-error categories, revision checks, tree identities
and cross-summary source/CPT capacities. Its cap is 3 KiB; the outer work report
retains 32 KiB. No source names, expressions, values or IDs enter this new summary.
Work1-17 and earlier optional paths remain strict. The work runner makes a
report-only local commit; all Git network operations remain manual and the
development listener remains disabled.

## Historical initial calculation measurement

On `feat/bounded-operand-example-pc`, from the repository root:

```bash
git pull
bash ./run-work-check.sh
git push
```

This measures syntax and leaf-reference coverage for the 45 previously counted
CPT instructions. Only generated feedback is required; manual source/UI review
remains optional. Partial status is expected while other interpretation gaps
remain. The HTML and all source-bearing artifacts stay under `confidential/`.
Editable corrections, PCSD and FHX remain later phases.

## Validation

The full development suite passed 752 cases in 92.887 seconds, with one existing
Windows symlink-capability skip. The ignored listener loader was excluded before
import. Independent review passed all 37 focused calculation/summary/workflow
cases and reproduced fixes for cyclic serializer fanout, impossible aggregate
token/depth counts and malformed subscript partial bindings. No blocking issues
remain. Signed-exponent and dynamic-index boundaries have explicit regressions.

Two final actual isolated Bash runs, explicit then remembered source, each
passed 656 application cases (one skip) and 139 helpers. Both produced
work18/review6/manifest9, thirteen verified hashes and one report-only local
commit. Git traces contain 31 commands per run and zero network verbs. Each
public report is 29,517 bytes. Fresh CLI generation exits 3 and matches all
thirteen artifacts byte for byte across both runs. Eleven previous evidence
files, including pid-members.json, match baseline `564fa66` on the same invented
input; six previous summaries match after removing only tool_revision. All 24
historical reports remain byte-identical and valid. All 100 runtime, asset and
test files in the final isolated checkout match this checkout. Source inputs,
previous runs and the real HEAD were preserved; temporary checkouts finish clean.

Fresh-process checks caught and fixed nondeterministic coverage dictionary
ordering in embedded report JSON. Runs with PYTHONHASHSEED 1 and 2 now produce
the same demonstration hash, and the final isolated CLI comparison confirms
artifact reproducibility. This last change affects ordering, not evidence.

Chrome checks cover calculation search/filtering, back-navigation state,
grouping and spans, repeated leaves, declaration/rung reverse links, dynamic
index gaps, and unsupported expressions without partial trees. A 61-reference,
121-node expression pages both tables correctly. Script-like expression text
remains inert, and legacy review5 has no Calculations section. No page JavaScript
errors occurred. The independently invented
[calculation fixture](../../fixtures/synthetic/calculation_review_demo.L5X) and
[HTML demonstration](../../examples/engineering-review-demo.html) include normal
and deliberately unsupported cases; all older fixture bytes remain unchanged.

The invented capacity input has 6,002 tag-data owners, 48,000 elements, 4,606
rungs and 60 CPT occurrences. The companion captures 360 syntax nodes and 180
reference occurrences. Analysis, canonical replay, summary and rendering took
74.76 seconds on this development PC; HTML is 56,661,286 bytes. Chrome supports
50/10 calculation paging and expression search on it. This is a synthetic
capacity check, not an actual-unit result or a performance guarantee.

The wheel build passed. All 40 packaged modules/assets match final source bytes,
and the extracted renderer reproduces the exact final HTML demonstration. The
QA tab and temporary loopback server are closed. Actual-unit CPT coverage is
the remaining run boundary; manual engineering/UI review remains optional.
