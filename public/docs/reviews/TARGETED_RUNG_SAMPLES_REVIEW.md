# Targeted real-rung diagnostic examples

## Authorization and returned evidence

Tyler confirmed that the 2% boundary counts **new informative examples**,
separately from the older scrubbed structural catalogs. Small source-derived
pulls are authorized when parser findings are unclear. Do not ask for approval
for each such diagnostic case. This does not authorize full routines, dependency
closure, connected plant reconstruction or unrestricted source exports.

Returned `aed0fc4` tested clean `a12ada1`: 945 application cases passed with
one expected Windows skip, plus 139 helpers, and the private run saved. All ten
earlier summaries were unchanged. Binding context links all 303 predicate gaps
and 16 unbound coil targets to unique rack candidates: 319 uses, 94 candidate
addresses and 11 roots. Two further write operands use dynamic indexes. The
source still contains 459 opaque instruction transfers and one unknown block.
These counts select questions; they do not reveal the individual implementations.

## Fixed first request

Request `rung-cases-1` has six slots:

| Case | Selection evidence |
|---|---|
| `dynamic_index_1`, `dynamic_index_2` | First two ordinary-operand dynamic-index gaps (expression leaves excluded) |
| `unknown_block_1` | First block whose family is unknown |
| `opaque_ons_1` | First ONS occurrence with opaque condition transfer |
| `opaque_sfr_1` | First SFR occurrence with opaque condition transfer |
| `branched_output_1` | First branched rung with a comparison and a recognized coil |

Select in canonical source order, before checking the sample's size or lexical
support. An oversized or unsupported first case is withheld rather than replaced
with successive source rungs. Multiple cases on one rung share one sample and
one budget charge. Each sample contains only that rung, never its neighbors or
transitive dependencies. Missing cases are explicit.

The sample retains instruction/argument order, nested branches and local lexical
relationships. Plant roots, members, bit selectors and literal values become
per-rung placeholders. Dynamic-index operators and repeated references remain
visible. Placeholder maps restart for each rung: they do not form a cross-rung
tag dictionary. Lexical equality does not prove alias equivalence or runtime
identity. Samples are explanatory representations, not executable controller code.

Known publication-catalog instruction names remain visible. At most one unknown
instruction mnemonic, bounded to 64 identifier characters, may be retained as
an intentional diagnostic clue; its rung uses `UNLISTED_OP_1`. No raw argument,
description, location, source ID/hash, tag declaration, stored value or module
configuration accompanies it. Unsupported lexical forms withhold the case with
a fixed reason; they never fall back to raw text.

Bounds apply before and after conversion: six distinct rungs, 8,192 raw
characters per rung, 24 instructions, four branch levels, 16 branch legs,
128 lexical tokens, 2,048 sanitized text characters and a 16 KiB record.
Canonical source evidence is authenticated before selection. Closed public
validation reparses the sanitized form and checks structure, vocabulary,
placeholder/literal metadata, case references and budget conservation.

## Accounting and reruns

The first request reserves two rung units conservatively for the historical
single-operand clues (`?` and `S:FS`). The total allowed charge is the smaller
of 40 units and `floor(source_rungs / 50)`. New samples consume one unit each,
even though their names and values are removed. New capacity is
`max(0, allowed_charge - 2)`: a source below 100 rungs retains the two historical
reservations even though they exceed that source's cap, and releases no new
samples. On the 4,606-rung source, this
request can charge at most eight units including the two earlier clues: about
0.174%. That measures the agreed new-information budget, not all historical
structural disclosure or a mathematical guarantee of anonymity.

Work28 stops the older rotating single-operand selector and requires its
`diagnostic_sample` field to be null. Historical work1-27 samples remain readable.
There is one current request, with no automatic advancement to another batch.
A future explicit request must carry forward the existing reserved count and
retain earlier request contracts; changing an export must not reset its budget.

Before a new record can enter a work report, the runner saves an atomic,
non-overwriting reservation under
`confidential/work-check-samples/rung-cases-1.json`. This contains only the same
bounded public-safe record, not a reverse mapping or additional plant data.
Published work reports provide the portable copy for another computer or clone.
Existing reservations and published records must agree. A repeated request
reuses the identical record, even if source bytes or ordering have changed;
the envelope labels it historical replay rather than fresh evidence.

A failed report publication or commit therefore cannot silently select more
examples on retry. Invalid, contradictory or oversized history withholds sampling
while ordinary parser analysis still runs. A selection error that released no
record permits another attempt; a history error without a surviving reservation
cannot silently start a fresh request. Keep published reports and the local
reservation when archiving work. Deleting every published copy and the private
reservation destroys this accounting evidence; the implementation cannot prove
the history of manually erased data. These are single-owner workflow safeguards,
not an adversarial audit log.

## Publication contract and next run

Work28 adds a separate `targeted_samples` envelope. It distinguishes selection,
historical replay, unavailable evidence and analysis not run. Only work28 permits
a 64 KiB outer report; work22-27 retain 48 KiB and earlier versions retain 32 KiB.
All eleven current analysis summaries and all sixteen saved private artifacts
retain their existing contracts and contents. Review11/manifest14 are unchanged.

Run the usual work-machine sequence from the repository:

```bash
git pull
bash ./run-work-check.sh
git push
```

The script commits only its validated feedback report locally. Git transport
remains manual, and the listener remains disabled. No manual engineering or UI
review is requested yet. The next returned samples will determine which parser
rules or interpretation limits to investigate next.

## Validation

- Independent review ran all 46 new targeted core/history/workflow tests:
  passed, with one expected Windows symlink skip. Review findings on numeric bit
  selectors, expression-gap accounting and selection-error retries were fixed.
- The actual Bash launcher ran twice in an isolated checkout against the invented
  400-rung fixture. Each run passed 991 application cases (two expected Windows
  symlink skips) and 139 helpers, saved the private analysis, and committed only
  its own 44,727-byte feedback report. Git traces showed no network operations.
- All six synthetic cases were selected once, charged six new units plus two
  prior units, and replayed identically on the second run. The local reservation
  matched the published record. Invented plant identifiers and numeric values
  were absent; the intentional unknown mnemonic remained the sole name clue.
- All sixteen private artifacts, including `review.html`, were byte-identical
  to baseline `10f96a8`, between both runs, and through the separate review CLI.
  All eleven summaries matched after revision normalization. Canonical replay
  validated both new runs and all 34 unchanged historical reports.
- The isolated runtime/assets/test snapshot matched all 139 corresponding final
  working-tree files. Neither the real source directory nor ignored listener
  files were read. Synthetic work28 reports remain in temporary QA checkouts;
  they must not be copied into the production history and consume its request.

Broader discovery ran 1,292 cases with two expected Windows symlink skips. It
had already loaded an old single-operand expectation before that test was
updated, so the same stale assertion failed directly and inside the guarded
suite-loader check. Both affected tests passed on a fresh final-file rerun;
the guard also verified that selected tests cannot launch processes or sockets.
The two actual launcher runs above used the final files and passed throughout.
