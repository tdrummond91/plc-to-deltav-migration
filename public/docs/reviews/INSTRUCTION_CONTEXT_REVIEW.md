# Custom-instruction declarations and symbolic array selectors

## Returned evidence

Returned `51315bd` tested clean `bfd53e1`. All 991 application cases passed
(two expected Windows symlink skips), as did 139 helpers. The private run saved,
with partial analysis and no failure code. All eleven earlier summaries remain
identical after tool-revision normalization; all 35 historical reports validate.

The fixed request returned six distinct examples and reserved eight rung units
including the two earlier operand clues, against the 40-unit cap. All requested
cases were included. These examples clarify several next steps:

- The two dynamic destinations are indexed MOV writes. Each rung also updates
  the index in another branch. Comparisons and index updates are source evidence;
  they do not by themselves establish a bounded loop or a valid array element.
- The unknown block has a single argument; preceding
  branches write members of that argument. Its spelling and neighboring MOVs do
  not establish its declared identity, call validity or calendar behavior.
- The ONS example has two separate storage operands on alternative branches
  feeding a latch. A plain Boolean pass-through would lose the state dependence
  described in [Rockwell's ONS reference](https://www.rockwellautomation.com/en-ro/docs/studio-5000-logix-designer/37-00/contents-ditamap/instruction-set/bit-instructions1/one-shot--ons-1.html).
- The SFR example places the reset and unlatch in parallel branches. Control
  targets and sequence effects need separate analysis.
- The comparison/output example has several independent branch outputs and a
  data copy. Keeping each output's own incoming guard avoids merging their tests.

This implementation follows the two evidence gaps that can be investigated
using declarations and address syntax already present in the private snapshot.
The same six examples replay unchanged; this slice requests no new examples.

## Custom-instruction declaration context

The new companion relates unknown-family instruction occurrences to eligible
Add-On Instruction declarations in their own controller. It distinguishes a
unique declaration candidate, a missing declaration, ambiguous declarations and
unsupported source context. Parameter and body availability are source evidence,
with private links back to existing declarations and routines.

A candidate identifies a possible declaration; it does not validate the call's
arguments or infer parameter access, internal effects, output values or behavior.
Names are compared conservatively within controller ownership. Same-name tags,
routines, foreign controller declarations and unsupported extension contexts
cannot silently become a matching AOI. Existing unknown operand roles and opaque
condition transfers remain visible alongside the new declaration context.

## Symbolic indexed-access context

The second companion explains direct ordinary operands such as the invented
`MOV(Feed,Buffer[Cursor]);`. It records a possible write selected through
`Buffer[Cursor]`, independently resolved outer-root evidence, and an index read
of `Cursor`. Repeated references remain distinct occurrences. Program-local
resolution, aliases and unresolved index references retain their own evidence.

Selector text and source offsets remain private. The implementation does not
evaluate a selector, substitute a fabricated array element, establish array or
member validity, merge symbolic writes into exact-address identities, or infer
loop/range/scan behavior. Unsupported forms and deferred expression/alias cases
remain explicit. All existing binding gaps and earlier analysis records remain
unchanged; the new context explains them instead of erasing them.

## Contracts and workflow

Review12 embeds both bounded companions. Each is limited to 8 MiB; the combined
review permits 184 MiB JSON and 216 MiB HTML. Earlier review limits are unchanged.
Manifest15 still hashes sixteen artifacts, with no additional source snapshot
or raw-data export. Work29 adds two closed count summaries to the eleven existing
summaries and retains work28's 64 KiB public envelope and frozen sample request.
No names, expressions, source IDs or values enter the new summaries.

The usual work-machine sequence remains:

```bash
git pull
bash ./run-work-check.sh
git push
```

The runner commits only its own validated feedback report. Git transport remains
manual, and the listener remains disabled. No manual engineering/team review is
needed yet. The next return will establish whether the unknown block has a
matching declaration and whether the two dynamic destinations and their index
references can be explained by the new companions.

## Validation

- The full listener-excluded suite passed: 1,358 cases, with two expected Windows
  symlink skips. The new modules and workflow add 66 cases. Independent review
  included 77 additional synthetic probes; two summary-consistency gaps were
  corrected and rechecked before final QA.
- Two actual Bash launcher runs in an isolated checkout passed 1,057 application
  cases and 139 helpers each. The first selected an explicit invented input; the
  second reused its remembered path. Each made one report-only local commit,
  left a clean checkout and issued zero Git network commands.
- Both runs replayed the existing six-example record unchanged, even with the
  invented input. Both generated work29 reports validated within the unchanged
  64 KiB envelope. All 35 historical reports stayed byte-identical and valid.
- All fifteen earlier non-HTML artifacts were byte-identical to baseline
  `51315bd` on the same invented input. All eleven earlier aggregate summaries
  matched after revision normalization. Both new companions matched independent
  derivation from the snapshot, and all sixteen artifacts matched a separate
  CLI run, including canonical HTML rendering and manifest hashes.
- Chrome checks covered context search, call-to-declaration navigation, parameter
  and routine metadata, repeated index reads, unresolved selectors and source
  navigation. Literal script-like comments stayed text, and there were no page
  errors or horizontal overflow at the tested desktop viewport. A final link
  spacing adjustment passed eleven HTML checks; a fresh CLI rendering preserved
  the exact embedded payload and all fifteen non-HTML artifacts.

The [invented context report](../../examples/instruction-context-demo.html)
matches that final CLI rendering. Its fixture was independently constructed;
it contains no copied plant rung. The real source must still run on the work
machine before the new declaration and selector counts can be confirmed.
