# Rung analysis: structure and unreviewed function candidates

## Purpose and current scope

The work-machine pushes are automated test/analysis results. Tyler has not
provided engineering feedback. Continue the automated development sequence in
[Phase 1 engineering analysis](../planning/PHASE_1_ENGINEERING_ANALYSIS.md) before
asking him to present the report to the other team.

This first broad analysis layer combines existing evidence into one dossier per
rung and one entry per captured instruction. It adds candidate functions,
structural endpoints, branch/empty-path counts, source and expression accesses,
comment status, missing metadata and explicit gaps. Candidate categories overlap:
one rung can contain a calculation, reference an I/O declaration and have a weak
alarm hint. Counts are occurrences, not confirmed equipment or loop counts.

The report's Engineering analysis view groups rungs by how much of their block
evidence is understood, with family, structure and gap filters. Each rung links
its candidates to reasons, rule versions, missing evidence, ordered blocks and
a readable series/branch outline. Existing PID, calculation, tag and source
views remain available. The independently invented
[demo](../../examples/engineering-review-demo.html) includes deliberate errors
and ambiguous cases; it is not controller-ready logic.

## Evidence boundaries

- Supported operand signatures, recognized mnemonics, structural motifs,
  module-root references, declaration types and name/comment hints remain
  distinct evidence bases. Every candidate is `unreviewed`.
- A PID mnemonic with seven nonempty slots is a recognized signature. A linked
  PID declaration without that instruction is only a possible support relation.
  Neither establishes PV/SP/CV behavior, master/slave relationships or mode.
- A bounded Boolean motif requires only supported condition blocks and one
  final OTE/OTL/OTU on every structural path. Assign, latch and unlatch differ.
  It does not simulate execution or infer the commanded equipment.
- Ordered structural first/last blocks account for nullable branch legs. A
  trailing empty leg can leave an earlier block as a possible endpoint. No
  exponential path enumeration is performed.
- Exact known root/member suffixes distinguish candidate results. A shared root
  does not imply member overlap. State-changing/external/control instructions
  have a separate result group; no known local result is not proof of dead code.
- Module input/output declarations supply I/O context. An internal OTE alone
  does not establish a physical DO; channel type and direction of use still
  require further analysis.
- Whole-word English/French hints are weak clues. A pump, alarm or sensor name
  does not establish a device, shutdown effect or alarm rank. Ambiguous comments
  are retained as ambiguous, rather than treated as absent.
- Failed rungs remain represented without invented partial blocks. Unmodeled
  instruction effects and unresolved bindings remain visible.

## Contracts and publication

Private rung-analysis schema1 / `rung-analysis-1` requires authenticated
snapshot, inventory, references, access4 and calculation2. Canonical validation
replays the derivation, including ordering and evidence links. Snapshot-bound
candidate IDs are not durable correction identities across changed exports.
The companion has a 32 MiB serialized cap, bounded record/link counts and a
shared text-hint scan budget. It links existing evidence rather than copying
source comments or operand strings.

Optional review7 / manifest10 adds `rung-analysis.json` as the fourteenth hashed
artifact. Omitting the companion retains the prior review path. Existing
access4, calculation2 and other companion contracts remain unchanged.

Work22 adds a closed aggregate-only rung summary1: fixed vocabularies and counts
for coverage, structures, candidate families/bases, gaps and metadata. It exports
no rung text, names, comments, source IDs, paths, candidate IDs or reason text.
Cross-checks reconcile source/access/calculation populations. Work22 alone
allows 48 KiB for the complete public report; work1-21 retain 32 KiB. The rung
summary itself allows 4 KiB. Git pull/push remain manual; the launcher only
commits the generated public report locally. The listener remains disabled.

## Next automated evidence and remaining implementation

The next normal work-machine run measures this layer against the private export:
all 4,606 previously observed rungs, all 17,874 captured instructions, candidate
families, unresolved blocks, branch shape and metadata gaps. Those are expected
baseline populations, not an assumption that the source cannot change.

Return the generated aggregate report through the existing manual push flow.
No manual engineering or appearance review is requested at this checkpoint.
Continue afterward with exact operand relationships, stronger patterns,
cross-rung loops/equipment, alarm effects, sequence behavior, candidate dead ends
and relevant non-RLL code. Labeling every rung is not completion of Phase 1.

## Validation record

Completed on 2026-10-15:

- Full development suite: 898 tests passed with one expected Windows symlink
  skip. Final UI-only search/wording changes then passed all 25 related UI tests.
  An independent reviewer found no unresolved blockers after corrections to
  result-address counting, missing-data labels and aggregate consistency gates.
- Two actual isolated Bash launcher runs, explicit source then remembered source:
  each passed 778 application cases (one expected skip) and 139 helpers. Each
  committed only its new public report locally. Git traces contained 31 calls
  per run and no fetch, pull, push or transport operations. Public reports were
  34,207 bytes, within work22's 48 KiB cap.
- All fourteen private artifact hashes verified. Both runs and a separate CLI
  review produced identical artifact bytes. Canonical rung/review replay passed.
  The twelve older non-HTML artifacts matched baseline `f93f744` byte for byte;
  all seven previous aggregate summaries matched after tool_revision removal.
- All 28 historical reports remained unchanged and validated alongside the two
  new work22 reports. The final isolated snapshot matched all 114 runtime,
  asset and test files in the working tree.
- Browser checks covered combined filters, family grouping, source-label search,
  ambiguous/missing metadata, unparsed structure, empty branch paths, source
  links, literal destinations, I/O context, legacy navigation and escaped hostile
  source text. No application console errors or injected dialogs occurred.
- The current independently invented demonstration has 72 rungs, 87 captured
  blocks and 104 candidate occurrences. The HTML is 1,062,091 bytes. All earlier
  fixtures remain unchanged.
- An independently invented scale case with 4,606 rungs, 17,874 instructions,
  6,000 roots, 1,000 aliases and 1,000 CPTs/3,000 expression reads completed in
  52.8 seconds. Its rung companion was 26,046,935 bytes; review JSON was
  83,085,789 bytes and HTML 83,218,351 bytes, within existing caps. The browser
  loaded the report and handled grouping, paging and operand search. These are
  synthetic capacity checks, not measurements of the private export.

The final two-run/artifact verification used an isolated copy with no real
plant data. Documentation was updated afterward; runtime and test code was not.
