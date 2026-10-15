# Exact-address relationships and operand-reuse patterns

## Confirmed automated result (2026-10-15)

Returned `f7d91f0` tests clean `ddd087c`: 821 application cases passed (one
expected skip) and 139 helpers. The source yields 7,591 exact address groups,
3,778 used across rungs and 1,453 with multiple writers. All 132 CPT reads are
indexed with no composed-suffix gaps. Operand-reuse patterns cover 4,286 rungs
in 1,489 groups; 320 rungs have exclusions (128 unknown instruction roles, 192
unresolved addresses). The narrow calculation rule found one local link while
excluding 13,053 branched instructions. All eight earlier summaries match after
revision normalization; all 30 historical reports validate. Continue with
[Boolean conditions](CONDITION_REVIEW.md); no team review is requested.

## Why this layer follows rung analysis

Returned `4a3406b` tests clean `938d72d`: 778 application cases passed with one
expected Windows skip, plus 139 helpers. All 4,606 rungs and 17,874 captured
blocks were accounted for. The run saved its private report successfully;
all seven previous summaries matched after tool_revision normalization, and
all 29 historical reports validated.

The first rung census found 2,743 series and 1,863 branched rungs, containing
3,719 branch groups and 8,887 legs. It grouped 4,332 rungs with recognized roles
or signatures, 208 partial and 66 unidentified rungs. That does not mean 4,332
rung purposes are confirmed. Of 82 unresolved block functions, 81 have known
mnemonics and one is uncatalogued. PID signatures are recognized separately from
their operand effects. There are still 505 unknown source operand roles and
321 ordinary binding gaps.

The 11,837 candidate occurrences overlap across families and evidence bases.
For example, 1,319 alarm candidates came from text hints; no explicit alarm
instruction was captured. These are not 1,319 verified alarms. There are 278
PID-declaration hints beyond direct PID signatures and 1,935 module-root
candidate occurrences. Source comments were captured on 1,169 rungs and absent
on 3,437; no ambiguous comments or missing rung numbers/types were reported.

The next analysis question is how these source occurrences relate. A root-only
access view cannot distinguish a structure's members or array elements. An
opcode-only pattern cannot distinguish `XIC(A)OTE(A)` from `XIC(A)OTE(B)`.
This layer makes those distinctions without inventing execution behavior.

## Exact-address evidence

Group admitted bound occurrences by their final declaration ID and exact
expanded suffix spelling. Alias spellings can converge on the same final
address; same-named declarations in different scopes remain different roots.
Keep ordinary read/write/read-write/unknown slots separate from individual CPT
expression reads. Repeated expression references remain separate occurrences.

The original resolver can concatenate individually valid alias suffixes into
an invalid combined form, such as a member following a terminal bit suffix.
Revalidate the composed static spelling before assigning an address identity;
retain rejected identities as gaps without changing earlier binding evidence.
Unbound/dynamic references remain in the existing access gap views.

This version deliberately keeps member case, subscript whitespace and leading
zero spellings unchanged. Different index groups do not prove different runtime
locations. A bound root or admitted suffix does not validate member existence,
array bounds, data type, copy range or whole-object/member overlap.

Show occurrence groups and participating rungs directly, without expanding
every writer/reader pair. An address with no captured explicit reader or writer
is an investigation lead; it is not proof of dead code, an uninitialized value,
or the absence of an HMI, communication, implicit or non-RLL use.

## Local calculation links and stronger patterns

Within an unbranched rung, eligible calculation/transfer blocks in one contiguous
segment can
link an earlier destination to a later read of the same admitted exact address.
Read all inputs before registering that instruction's destination, so a
self-read never becomes its own predecessor. Keep repeated CPT reads separate.

Unknown effects, unsupported signatures/expressions, unresolved operands,
control/stateful/range instructions and branch structure limit these links.
A write to another suffix of the same root invalidates an older local producer
candidate because overlap has not been established. The links record possible
source-order reuse, not guaranteed value propagation or a simulated scan.

Operand-reuse patterns supplement the original opcode/arity/branch patterns.
They retain address-variable and shared-root relationships, exact suffixes, roles,
literal/non-data spelling and CPT expression structure. Renamed addresses can share a pattern while same-opcode
rungs with different reuse or literals remain separate. Incomplete modeling
produces an explicit exclusion reason. Pattern equality does not establish
equivalent engineering purpose, types, side effects or behavior.

## Delivery and remaining work

The private relationship companion and report views are part of Phase 1.
Public work-machine output remains closed aggregate counts; source names,
addresses, links, templates and identities stay private. Git synchronization
remains manual and the launcher commits only its validated report locally.
The listener remains disabled.

This is the second development bundle in the
[Phase 1 analysis sequence](../planning/PHASE_1_ENGINEERING_ANALYSIS.md).
Cross-rung loop/equipment assembly, alarm effects, sequences, remaining block
semantics and non-RLL interpretation remain active development work. Team
feedback has not started and is not requested at this automated checkpoint.

## Reference context

Rockwell's [tag-reference syntax](https://www.rockwellautomation.com/en-ro/docs/studio-5000-logix-designer/38-00/contents-ditamap/studio-5000-logix-designer/ladder-editor/enter-logic/reference-a-tag-in-your-logic.html)
distinguishes structure members and array elements; its
[array indexing documentation](https://www.rockwellautomation.com/en-il/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/index-through-arrays.html)
describes dynamic subscripts. The
[move instruction reference](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-01/contents-ditamap/instruction-set/move-logical-instructions/move--move-.html)
provides source/destination and conditional-execution context. These references
do not establish the behavior of any particular source rung.

## Implementation contracts and validation

The companion is relationship schema1 / `relationship-analysis-1`, authenticated
against the immutable snapshot and canonical inventory/reference/access4,
calculation2 and rung-analysis1 evidence. Records are bounded before retention;
rendered private evidence is capped at 32 MiB. Public relationship summary1 has
closed count maps, no source text, and a 6 KiB cap. Review8/manifest11 adds the
fifteenth hashed artifact. Work23 adds that summary and reconciles populations
against existing companions. Work22/23 retain 48 KiB outer limits; work1-21
remain 32 KiB. Existing optional replay paths remain strict.

The independently invented 92-rung fixture includes aliases, invalid composed
suffixes, repeated expressions, self-read/write ordering, overwrite and overlap
barriers, branches, unknown effects, distinct index spellings and stronger-pattern
counterexamples. It yields 47 exact addresses, one identity gap, eight local links
across five rungs, and 47 patterns covering 54 rungs with 38 explicit skips.

Completed development validation:

- Full development suite: 951 cases passed with one expected Windows symlink
  skip. After the final UI correction, all 35 UI cases passed, including the
  additional long-name regression. Independent review reran 53 focused relationship
  cases and found no remaining blocking issues.
- Review fixed a display-text encoding issue and browser search amplification:
  one long declaration name repeated across thousands of suffix groups could
  multiply memory usage. Cached root previews are 120 characters and suffix
  previews 160 characters; the full spelling remains accessible as source evidence.
  Canonical long-name regression checks indexed size, labels, paging and search.
- Two actual isolated Bash launcher runs, explicit then remembered source, each
  passed 821 application cases (one skip) and 139 helpers. Each created one local
  report-only commit; Git traces contain 31 local commands and zero transport calls.
  No old reports or private runs were overwritten. Each public report is 36,744
  bytes, work23, within 48 KiB.
- Fifteen artifact hashes verified for both runs. Fresh CLI output matched all 15
  artifacts byte for byte. The generated public invented demo equals that saved
  canonical HTML. All 120 final runtime/assets/test files matched the tested
  isolated snapshot.
- Against baseline `4a3406b` on identical invented input, thirteen older non-HTML
  artifacts are byte-identical and all eight earlier summaries match after only
  tool_revision normalization. All 29 historical reports plus both new work23
  reports validate; historical report bytes remain unchanged.
- Browser checks verified exact-address dossiers, repeated CPT leaves and alias
  links, local link rows, invalid composition gaps, stronger pattern membership,
  source navigation, search and paging. Source markup rendered as text; no script
  errors appeared. Legacy access3 reports hide the optional relationship views.
- A separate invented scale case captured 4,606 rungs, 17,874 instructions, 6,000
  base declarations and 1,000 aliases. Relationship evidence is 11,047,425 bytes;
  review JSON 92,401,007 bytes; final HTML 92,549,485 bytes, all within their caps.
  Full construction took 69.3 seconds on this development PC. Chrome loaded the
  report and paged/searched its 7,000 exact addresses with source links intact.
- Changed Markdown local links and `git diff --check` pass. Actual proprietary
  source and ignored listener files were not read or run.

The next work-machine return should confirm the exact-address populations,
composed-suffix gaps, local-link coverage and pattern exclusion reasons on the
private export. Compare all eight earlier summaries after revision normalization.
Then continue source-addressable relationships, loop/equipment assembly and the
remaining block/non-RLL semantics. These synthetic checks do not supply plant
engineering approval or complete Phase 1.
