# AOI body ownership and unmatched SFR target context

## Exact named parameter members (2026-10-19)

AOI body context2 adds source associations for explicit operand and expression
uses of an exact `.ParameterName` on a scalar declared AOI instance. The resolved
root's datatype must select one AOI in that root's controller, and the member must
select one Input or Output parameter. Program shadowing, caller aliases and
parameter-to-local-tag aliases retain their existing identities and suffixes.
The original access role stays unchanged; declared Usage does not rewrite it.
The parameter ID links to the existing declaration-owned body observations.
Repeated calls do not duplicate those observations or external member uses.
A captured call is not required to establish this named type/member association.

Whole-instance uses with an empty suffix remain outside the member population.
Arrays, indexed/nested members, InOut and system parameters, local tags exposed
as members, duplicate declarations or symbols, protected evidence and foreign
namespace dependencies do not produce a positive association. Unbound uses stay
in the existing binding coverage. Missing type/declaration evidence is not
replaced by a name-based guess. Matching a parameter name does not validate its
datatype, bounds, runtime invocation or resulting effects.

Separate per-declaration signatures preserve required, optional, system and
unclassified parameter IDs in source order. Per-call shape rows retain total,
trailing and empty field counts, plus a cardinality-only comparison when the
declaration signature is available. Equal counts do not establish positional
mapping or valid argument types. Optional hidden parameters do not generate
missing-argument findings. Exported EnableIn/EnableOut are identified separately;
their supplied attributes do not create ordinary required argument positions.

The [AOI programming manual, PM010N](https://literature.rockwellautomation.com/idc/groups/literature/documents/pm/1756-pm010_-en-p.pdf)
describes required arguments, visibility and access to Input/Output instance
members on printed pages 27-29; page 35 describes parameter display order. The
[import/export manual, RM014D](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf)
describes the system parameters on printed page 101. These facts support the
named association and signature observations above. They do not establish a
general neutral-RLL positional serialization rule.

The JSR/SBR/RET neutral-RLL layout question recorded in
[ROUTINE_CALL_SHAPE_REVIEW.md](ROUTINE_CALL_SHAPE_REVIEW.md) remains unresolved.
A future closed diagnostic could report each call's lexical field bindings and
its target routine's SBR/RET boundary populations, partitioned by exact content
container. Input-count partitioning and position-to-position associations need
primary syntax evidence before implementation; invented examples are not that
evidence. Neither this companion nor such a diagnostic selects a return path or
projects called-body effects into callers.

Schema1 remains the default and preserves its rendered private and summary
bytes. Explicit `schema_version=2` adds `member_contexts`, `parameter_signatures`
and `call_shapes`; canonical replay uses the supplied version. Schema1 private
output retains its 8 MiB cap; schema2 has a 16 MiB cap, with link reservation
before collection and versioned bounds during derivation, native-container
inspection, serialization and replay. The larger schema2 allowance follows an
invented 4,606-rung capacity probe with 4,605 calls to one shared instance and
9,210 external member uses that exceeded the earlier 8 MiB bound. Link-byte
reservations accumulate while a row is built and are replaced by that row's
actual retained bytes; completed rows and the cumulative 250,000-link limit
remain charged. This avoids charging each link again after its row is retained.
The identical probe passes under the normal 16 MiB limit: canonical private
output is 14,536,368 bytes, retaining all 4,605 calls and call-shape records,
9,210 matched member contexts, two parameters, one instance root and one body
rung/instruction. Its 4,569-byte summary passes source replay and rendering.
The earlier permanent reservation accounting charged 17,380,580 bytes for that
same evidence, including link bytes already charged in completed rows.

Summary2 has an 8 KiB cap and closed status/count partitions; summary1 retains
its 4 KiB cap. The final focused AOI context, summary, member and workflow suite
passes 72 tests, including frozen schema1 bytes, versioned limits, pending
reservation replacement, cumulative links and exact serialization boundaries.
The suite covers exact roles and IDs, expressions, repeated
calls, aliases, scope, metadata gaps, protection, arrays, forged evidence,
resource bounds and frozen schema1 bytes. Pipeline/report integration is a
separate part of the current bundle; these focused checks do not claim a new
work-machine return or close the Phase 1 gates.

## Confirmed work-machine return

Return `4018156` tested clean `4b04e28`: 1,183 application cases and 139 helpers
passed, with two expected Windows skips and a saved private run. All 38 historical
reports validate; thirteen earlier summaries and the six-example reservation
are unchanged. The AOI body has two parsed rungs, three classified calculation
instructions and nine expression reads, with no recorded body/symbol context
gaps. Its instance has a matching declared root type. The unmatched SFR address
has one exact candidate in another chart of the same program, with all thirteen
peer contents eligible. The original missing match is preserved.

The next implementation is [PID connections and member uses](PID_CONNECTIONS_REVIEW.md).
The earlier scope and validation below are retained as checkpoint evidence.

## Returned evidence

Return `871b700` tested clean `60d5683`. All 1,128 application cases and 139
helper cases passed, with two expected Windows symlink skips. The private run
saved without a failure code. All 37 historical work reports validate, twelve
earlier aggregate summaries are unchanged after revision normalization, and the
six-example diagnostic record replays exactly. Its reservation remains eight
units; this checkpoint requests no additional samples.

All 133 ONS instructions now have stored-state transfers, with no storage-binding
gaps. Opaque transfers dropped from 459 to 326. Of 4,163 coil guards, 3,966 are
modeled, 196 retain binding gaps and one remains opaque. The 58 guards containing
ONS ancestry were previously opaque: 43 are now modeled and fifteen reveal
existing predicate-binding gaps. The increase from 181 to 196 gap-bearing guards
does not mean fifteen new unresolved addresses appeared. There are still 303
gap-bearing predicates and sixteen unbound output targets.

All 140 SFR calls have unique program-local routine candidates and available
chart contents. Exactly 139 match a captured step; one has no matching step in
its selected content. All 145 captured steps have bound operands. The fourteen
charts each have one content version, and all initial-step markers are explicit.
This identifies a concrete source relationship to investigate, without proving
which reset executes or whether the source requires correction.

## AOI body and instance context

The earlier unknown-family call has a unique AOI declaration candidate. The new
companion connects declarations to their already-captured routines, rungs,
instructions and access records. These bodies already contribute to global
source totals; linking them does not count them again or copy their source into
every call.

Parameters and local tags retain separate indexes for the written symbol and
the resolved alias target. One occurrence can appear in both indexes, but
aggregate populations count it once. Declared parameter Usage is distinct from
the observed operand role. Symbols with no selected explicit observations are
not labeled unused: unsupported instructions, dynamic indexes, other languages
and implicit effects can leave gaps in that observation model.

Rockwell identifies the first AOI field as its instance tag in the
[official instruction guidance](https://www.rockwellautomation.com/en-in/docs/studio-5000-logix-designer/38-00/contents-ditamap/studio-5000-logix-designer/add-on-instructions/using-an-add-on-instruction.html).
The companion resolves that field separately when the declaration is unique.
It distinguishes root binding, address shape and declared root datatype
comparison. A member suffix cannot inherit the root's datatype as proof of its
own type. An array spelling does not establish bounds, dimensional validity or
a valid scalar instance. Hidden or optional parameters do not imply missing
positional arguments.

Logic, Prescan and other routine names establish ownership only. This slice
does not simulate the body, assign its engineering purpose, infer scheduling,
validate positional parameter passing or project internal reads/writes onto
caller data. Existing custom-instruction context and access records stay intact.

## SFR gap diagnostics

SFR context2 retains the original target and match result. For a named,
root-bound selector with a missing match, it records bounded related evidence:
the same root with a different suffix in the selected content; the exact address
in another edit of the selected routine; and the exact address in other eligible
charts in the same program. These are diagnostic links, not replacement targets.

Protected, unsupported and incomplete peer contents remain excluded from
positive comparisons and are counted explicitly. No matches in the eligible
set do not establish absence from all source or runtime contexts. Original,
pending and test edits remain separate; no active edit is chosen. Schema1
defaults and earlier match semantics are preserved.

## Contracts and next work-machine run

Review14 embeds the bounded 8 MiB AOI body companion alongside SFR context2.
Its JSON/HTML caps are 200/232 MiB; earlier caps remain unchanged. Manifest17
still hashes sixteen artifacts. Work31 adds the closed AOI body summary and
updates SFR summary2 inside the unchanged 64 KiB envelope. Detailed names,
addresses and source links stay in the private HTML report.
Only work31 uses compact JSON whitespace to leave room for all bounded summaries
and the reserved diagnostic record. Earlier report rendering remains unchanged;
the private HTML interface remains the readable review surface.

From the repository root on the work machine:

```bash
git pull
bash ./run-work-check.sh
git push
```

The script commits its validated aggregate report locally. Git transport remains
manual, and the listener stays disabled. No new source samples or manual team
review are requested. The next returned counts will show the AOI body's observed
accesses and the available diagnostic context for the unmatched SFR call.

## Validation

- The full application/helper suite passed 1,483 cases with two expected Windows
  symlink skips. Listener tests were excluded before loading. An independent
  reviewer also exercised ownership, scope, malformed records and peer-content
  exclusions, with no remaining blockers.
- Two actual Bash launcher runs in an isolated synthetic repository each passed
  1,182 application cases and 139 helper cases. The second reused the remembered
  source path. Each saved all sixteen hashed artifacts and made exactly one
  local report commit. Git traces showed no network operations. The six-example
  record and eight-unit reservation replayed unchanged.
- Cross-process artifact comparison found an unordered SFR coverage-key mapping.
  The final fix sorts those keys; all 48 focused SFR tests passed, including a new
  insertion-order regression. An independent reviewer verified identical bytes
  across seven hash seeds for seven payloads, including actual review HTML.
  The full suite and launcher runs above preceded this final ordering-only fix.
- After that fix, two fresh analysis processes and the CLI produced identical
  bytes for all sixteen saved artifacts. Fifteen earlier non-HTML artifacts were
  byte-identical to baseline `871b700`; thirteen earlier summaries were equal
  after revision normalization. All 37 historical reports remained unchanged,
  and all 39 reports in the isolated repository validated.
- Both isolated work reports were 36,188 bytes. Envelope tests include large
  reserved samples and maximum permitted independent count widths under the
  unchanged 65,536-byte limit. Earlier report rendering is unchanged.
- The invented HTML example was checked in a browser: body and operand
  pagination, direct versus resolved alias indexes, unobserved-symbol wording,
  first-field instance context, SFR candidate links and peer exclusions. Source
  markup rendered as plain text, with no injected script, console error or
  horizontal overflow. The final example matches the corrected CLI output.

All private paths used for this validation were isolated temporary synthetic
workspaces. No real local plant files or ignored listener files were read.
