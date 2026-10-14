# One remaining unmatched direct address

Date: 2026-10-14. Branch: `feat/bounded-operand-example-pc`.
Returned baseline: `9597f18`, testing clean `9d159e0`.

## Confirmed rack result

[The returned report](../../inspection/work-check-20261014T175611Z-c63b79cc.json)
validates. Its commit adds only that report, and its parent equals the reported
tested revision. All 220 selected application cases (one skip) and 139 helpers
passed, with no failures/errors. Analysis is partial and its private run was
saved. The diagnostic sample is null because the prior selector accepts only
malformed operands, and none remain.

The reader captured 11 rack connections, 11 input aliases and four output
aliases. All 15 candidate roots received backplane-slot names, with no unavailable
names. The three missing-root populations are:

| Population | Total | Unique candidate | No candidate |
|---|---:|---:|---:|
| Alias declarations | 99 | 99 | 0 |
| Alias-mediated operand occurrences | 319 | 319 | 0 |
| Direct operand occurrences | 1 | 0 | 1 |

There are no ambiguous, outside-scope or inconclusive matches. These are separate
populations, not distinct equipment counts. The result supports the rack logical
declaration hypothesis for the 99 aliases and their 319 uses; it does not prove
adapter backing members, data types, channel layouts or runtime effects.
Existing ordinary root bindings remain unchanged.

All shared source/reference fields match the preceding report except versions,
code revision, new rack counts, 26 newly modeled XML elements across three paths,
and replacement of 11 unsupported-rack warnings by 11 backing-not-analyzed
warnings. Aggregate equality does not establish source byte identity.

## Follow-up implementation

The next slice targets only the single direct address without a candidate.
Tyler already authorized one actual mystery-address occurrence; no expansion to
full rungs, neighboring operands or other source metadata is needed.

Work-check schema 3 / `work-check-3` retains one nullable `diagnostic_sample`
object with exactly kind, opcode, argument_index and raw_text. The new kind is
`direct_unmatched_colon_operand`. Its exact source text must be one recognized
static colon-root address of at most 128 printable characters. The standard
opcode and zero-based argument slot use the same restrictions as before.

The selector first validates the current inventory/reference pair, including
rack candidate records. It still selects the first eligible direct malformed
operand before considering any fallback. If none qualifies, it selects the
first direct unresolved colon operand whose canonical rack lookup is
`no_candidate_match`, joined by occurrence ID. It copies the operand's raw text,
not its extracted terminal root. It excludes aliases, dynamic indices,
non-colon roots, candidate matches and inconclusive/outside-scope results.
Overlong/nonprintable operands are skipped without truncation. Repeated unchanged
runs do not rotate examples. There is one sample total, not one per category.

Schema 3 requires reference aggregate 5 / source aggregate 4 for successful
analysis. Public validation requires partial analysis, an observed sampled opcode
and a positive direct no-candidate count for the new kind. It checks syntax and
aggregate consistency; actual occurrence provenance comes from canonical private
validation during generation. It does not invent missing hardware or label the
source invalid. Historical work-check schemas 1/2 remain readable, and schema 2
explicitly rejects the new sample kind. The original malformed-kind rules remain.

Private parser/reference contracts, count-only source/reference aggregates,
root binding behavior and private artifact layouts are unchanged. The runner
still commits only its validated report locally, with manual pull/push. The
listener stays disabled and untracked.

## Verification and next action

Tests cover malformed priority even when an unmatched address occurs first,
ineligible-malformed fallback, exact raw text, 128/129-character boundaries,
nonprintable text, alias and every nonmatching rack-status exclusion, forged
private records, count-only summary invariance, current/historical report rules,
failed analysis, no-overwrite publication and captured-once private persistence.
All eight stored work-check reports remain valid and unchanged.

Independent review passed 67 focused tests and found no remaining blockers.
The full development suite passed 337 cases with one existing Windows symlink
skip; the ignored listener loader was excluded before import. Use the full-suite
command recorded in [the rack review](RACK_CANDIDATE_REVIEW.md) to reproduce it.

Two actual CLI runs in a disposable synthetic checkout (explicit source, then
remembered source) each passed 241 selected application cases with one skip and
all 139 helpers. The invented rack fixture gained one `XIC` occurrence of
`MysteryRack:7:I.Data[2].3`; both runs emitted exactly that operand with kind
direct_unmatched_colon_operand and argument index 0. The original five operand
outcomes stayed unchanged. Each run used `python -B -m plc_workbench.work_check`,
saved matching private snapshot/artifacts, committed only its new validated
report, and left a clean checkout. The report's tested revision equaled the
commit parent. Prior source, reports and private synthetic outputs were preserved.
Git Trace2 recorded no remote verbs with an unreachable origin. Copied final
Python files matched the development files byte-for-byte. No plant input or
listener was used. These tests establish workflow behavior, not the remaining
plant address's spelling or engineering meaning.

The next work-machine run should supply the one remaining direct address if it
fits the unchanged sample bounds. For an unchanged export, reference counts and
rack match counts should stay identical; only the work envelope version and
sample can change. Review and manually push the automatically committed report.
Investigate the returned spelling before changing grammar or declaring a binding.
No repeat timer or rack-candidate confirmation is needed.
