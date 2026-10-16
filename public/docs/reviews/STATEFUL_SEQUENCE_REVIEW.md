# Stored-state conditions and SFC reset targets

## Returned evidence

Return `5215baa` tested clean `7263af0`: 1,057 application cases passed with two
expected Windows symlink skips, plus 139 helper cases. The private run saved,
analysis remained partial and no failure code was recorded. All eleven summaries
preceding the instruction-context addition were unchanged after normalizing
tool revision. All 36 historical work-check reports validate.

The single unknown block has a unique controller-owned AOI declaration candidate:
six parameters (four Input, two Output), all marked nonrequired and invisible,
and one RLL routine with no observed protection or encoded regions. This confirms
declaration context, not call validity or the instruction's engineering purpose.
Both dynamic write roots and their two index-read occurrences are bound. One
additional indexed operand remains explicitly deferred because its role is unknown.
The same six sampled rungs replayed unchanged; the cumulative reservation stays
eight units and this checkpoint requests no new samples.

## ONS conditions

Condition3 models ONS as a separate stored-state transfer. At a normal evaluation,
its outgoing condition depends on the incoming condition and the storage value
immediately before that instruction occurrence. Symbolically:

```text
outgoing = incoming AND NOT storage_before_this_occurrence
storage_after_this_occurrence = incoming
```

The parser records this dependency; it does not execute the equations or select
a storage value. Repeated ONS occurrences and shared storage remain distinct.
An intervening write, a different caller or a prior execution can change that
storage; it must not be equated to an earlier scan's input. Prescan initialization
also differs from ordinary evaluation. These rules follow the
[Rockwell ONS reference](https://www.rockwellautomation.com/en-ro/docs/studio-5000-logix-designer/37-00/contents-ditamap/instruction-set/bit-instructions1/one-shot--ons-1.html)
and its execution flow chart.

The presence of a stored-state condition propagates through the local graph and
is visible on downstream outputs and instruction contexts. This is structural
ancestry: an alternative bypass can make that storage unnecessary to the final
condition, and Boolean simplification is not performed. Existing opaque behavior and
binding gaps still propagate. A literal, missing declaration or unresolved
storage address remains a storage-binding gap; a malformed signature remains
opaque. This does not establish BOOL member validity or runtime safety.

Condition1/2 remain available with their original bytes and defaults. Existing
OSF pass-through behavior is unchanged; its output pulse is separate from the
outgoing rung condition. OSR and other unimplemented transfers remain explicit.

The returned census contains 133 ONS occurrences and 459 opaque transfers.
The next run should replace those 133 ONS opaque nodes with state-dependent
nodes. How many of the 59 opaque coil guards become explained must be measured.

## SFC reset target context

The separate SFR context connects reset occurrences to program-scoped routine
candidates and chart-step evidence. It preserves missing, ambiguous, unsupported
and wrong-language outcomes. SFC step identity comes from its `Operand` field;
initial-step selection uses explicit `InitialStep` metadata. Original, pending
and test edit contents remain separate candidates. No active revision is chosen.

The [SFR reference](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/program-control-instructions/reset-sfc--sfr-.html)
describes resetting a chart to a named step, or its initial step when the target
is zero, and stopping its stored actions. The
[L5X import/export reference](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf)
documents the SFC step attributes and edit contents. These references establish
the meaning of captured fields, not the execution of any particular reset.

SFR remains opaque in the condition model. Target links do not establish
outgoing rung conditions, complete transition logic, active steps, action
execution or scan ordering. The current census contains 140 named-step SFR
occurrences whose target relationships can now be investigated locally.

## Contracts and workflow

Review13 embeds the new 8 MiB SFR context and uses condition3. Its JSON/HTML caps
are 192/224 MiB; historical caps are unchanged. Manifest16 still hashes sixteen
artifacts. Work30 adds a closed SFR count summary, updates condition counts and
retains the 64 KiB outer envelope. Detailed names, values and source links remain
in the private report. The fixed diagnostic request retains condition2 selection
semantics for initial selection and replays an existing reservation unchanged.

On the work machine, run from the repository root:

```bash
git pull
bash ./run-work-check.sh
git push
```

The runner commits only its own validated feedback locally. Git transport remains
manual; the listener remains disabled. Manual engineering/team review is deferred
while script-addressable gaps remain.

## Next AOI follow-up

AOI routine bodies are already part of the source inventory and global rung
totals. A later slice should expose declaration-to-body ownership, parameter and
local-tag observed accesses, and caller instance identity without double-counting
those rungs or copying the body into each call. Declared Usage must remain
distinct from actual body access; optional hidden parameters do not imply
missing positional call arguments. See Rockwell's
[instance and member guidance](https://www.rockwellautomation.com/en-in/docs/studio-5000-logix-designer/38-00/contents-ditamap/studio-5000-logix-designer/add-on-instructions/using-an-add-on-instruction.html)
and [AOI programming manual](https://literature.rockwellautomation.com/idc/groups/literature/documents/pm/1756-pm010_-en-p.pdf).
Positional call validation, internal execution and global effects need their own
rules; they must not be inferred from a unique declaration match.

## Validation

The full developer/helper suite passed 1,429 cases with two expected Windows
symlink skips. Listener tests were excluded before module loading. Independent
review found no remaining blockers after tightening stored-state wording; its
700 randomized condition comparisons and sixteen separate SFR probes passed.
The selected work-machine suites also passed under the subprocess/socket guard.

Two actual Bash launcher runs in an isolated repository used only the invented
[fixture](../../fixtures/synthetic/stateful_sequence_demo.L5X), first by explicit
path and then by its remembered local path. Each passed 1,128 application cases
(two skips) and 139 helper cases, saved a private report and committed exactly
one validated aggregate report locally. Git traces recorded no network calls.
Both runs replayed the existing six-example reservation byte-for-byte in content,
with total reserved rungs remaining eight. They did not request new examples.

All sixteen saved artifact hashes matched. A separate CLI run produced the same
sixteen artifacts. Against the previous checkpoint on this invented fixture,
fourteen older non-HTML artifacts were byte-identical, twelve older aggregate
summaries were unchanged after revision normalization, and the embedded binding,
custom-instruction and indexed-access contexts were unchanged. Condition3 and
the review intentionally changed. All 36 historical work reports remained
unchanged and validated alongside the two new synthetic reports.

The [invented report](../../examples/stateful-sequence-demo.html) matches the
verified CLI HTML byte-for-byte. Browser checks covered ONS filtering and
50-row pagination, symbolic storage conditions, SFR target navigation, separate
Original/PendingEdits candidates and navigation to the matching step/content.
Source-comment markup remained literal text, with no injected content script,
horizontal page overflow or browser console errors in the checked views.

The real source still needs the next work-machine run. Synthetic results do not
confirm how many real ONS guards or SFR targets will resolve.
