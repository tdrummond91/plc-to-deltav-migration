# Timers, counters and reset relationships

## Confirmed timer/counter return

Return `3547344` tested clean `a6840f4` with 1,338 application cases (two expected
Windows skips) and 139 helpers passing. All 485 selected occurrences have exact
qualified targets; all 48 resets match producer objects. The 436 objects comprise
433 timers and three counters, with one multiple-producer object. All have
stored data, and all 2,622 linked elements match their control's declared type.
Eighteen earlier summaries and the frozen examples are unchanged. All 42
historical reports validate. See the
[next sequence checkpoint](SFC_CONDITIONS_REVIEW.md) for remaining context.

## Confirmed return

Return `19ccaee` tested clean `5ae8b6d`: 1,295 application cases passed with two
expected Windows symlink skips, plus 139 helper cases. The private report saved
without a failure code. All 41 historical reports validate. Seventeen earlier
summaries are unchanged after removing only tool revision, including its nested
source-summary occurrence. The six diagnostic samples and eight-unit reservation
are unchanged.

Boolean output context accounts for all 4,163 OTE/OTL/OTU occurrences across
2,983 rungs. There are 2,978 qualified exact target addresses, including 110
module-output-root addresses; this does not establish 110 physical channels.
There are 1,126 addresses with multiple coil writers, 6,071 accepted predicate
reads and 315 addresses without a captured explicit RLL reader. That last group
is an investigation queue, not proof of unused code: external, indirect and
non-RLL consumers can still exist. Sixteen coil targets remain unbound.

No additional same-address noncoil writers or namespace-rejected uses were
observed in this bounded target population. These counts do not describe whole
root/member overlap or implicit effects. Rung-wide hints occur on 1,617 output
rungs and remain suggestions, not confirmed alarms or equipment identities.

## Analysis bundle

The next bundle connects timer, counter and reset occurrences with their control
addresses, incoming source conditions, explicit member uses and exported stored
data. The returned source census contains 390 TON, 44 RTO, three CTU and 48 RES
occurrences. Synthetic coverage also includes TOF and CTD.

The report must retain multiple producer/reset occurrences, aliases, separate
branches, exact array-element spellings and nested control paths. Matching an
address does not establish execution order, a runtime state, a validated member,
an effective duration or a process purpose. Missing producers, malformed
signatures, namespace conflicts and unresolved targets remain inspectable.

Stored PRE/ACC and status fields are source observations. Separate exported
representations remain separate; the report does not choose a live or effective
value. Timer/counter pseudo-operands are not used as a substitute for that stored
evidence. CONTROL reset targets and TIMER_T declarations remain distinguishable
from ordinary TIMER/COUNTER declarations. TOF incoming conditions must not be
labeled as proof that timing is active.

See the official [pseudo-operand initialization reference](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-03/contents-ditamap/pseudo-operand-initialization.html)
and [Logix RES reference](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-03/contents-ditamap/instruction-set/timer-and-counter-instructions/reset--res-.html).
Instruction documentation establishes field and instruction meaning, not the
behavior of a particular plant occurrence.

## Workflow and next checkpoint

From the work-machine repository folder on `feat/bounded-operand-example-pc`:

```bash
git pull
bash ./run-work-check.sh
git push
```

The runner tests, saves and commits validated feedback locally. Git transport
remains manual, the listener remains disabled, and no additional plant samples
or manual engineering review are requested by this bundle. Actual source and
the detailed report remain on the work machine.

After this return, the next planned broad bundle is sequence-transition text.
The Phase 1 objective remains investigation of all script-addressable source
questions before team review. The current planning estimate is 8-12 work-machine
runs from the Boolean-output checkpoint, subject to actual findings; it is not a
fixed commitment or an estimate for the editor, PCSD or FHX phases.

## Validation

Stateful objects1 retains bounded occurrence, object, address-use and stored-data
records with a 16 MiB / 250,000-record allowance. Its closed public summary is
limited to 4 KiB. Review18 reserves 248 MiB JSON and 280 MiB HTML; manifest21
still hashes sixteen artifacts because the new companion is embedded. Work35
retains the 80 KiB outer limit and the frozen sample request.
The conservative maximum-width work report is 74,330 bytes, below 81,920 bytes.

Thirty focused core/summary cases passed, including canonical tamper rejection,
resource boundaries, case-insensitive catalog recognition with literal address
identity, static bounds, namespaces, malformed signatures and stored-data gaps.
One hundred deterministic mixed invented programs passed core replay; independent
review added another sixty mixed programs. Thirteen new workflow cases and 236
affected existing cases passed, including targeted rechecks after updating
historical-version expectations. Eight independent development-only DOM cases
cover navigation, condition ancestry, all four paginated views, source-text
escaping, namespace/capture gaps, CONTROL and TIMER_T, and duplicate stored data.

An independent dense case with 600 controls, 600 resets, 12,000 member reads and
3,600 stored elements passed canonical and summary replay. It produced 5,226,735
private bytes and 3,084 public bytes, within the existing allowances. No
writer-by-consumer expansion is stored.

The independently invented [152-rung fixture](../../fixtures/synthetic/stateful_objects_demo.L5X)
and [offline report](../../examples/stateful-objects-demo.html) contain 90 selected
occurrences, 71 qualified groups, 136 address-use associations and 406 stored-data
links. The companion is 336,278 bytes and its revision-bound summary is 3,067
bytes. Five target gaps remain visible: two unresolved signatures, two unbound
addresses and one namespace conflict. These are deliberate diagnostics, not
controller-ready source.

Browser inspection confirmed group pagination of 50/21 records and occurrence
pagination of 50/40, including navigation from the last group. Search, type
display and evidence filters work. Duplicate presets remain separate source
observations. A foreign-namespace member stays unqualified and its existing
capture issue remains discoverable through the declaration's stored-data view.
Source navigation preserves literal script-like comment text, with no script
element in the report content or horizontal overflow. No report console errors
were observed; the only warnings originated in the browser extension.

Final verification passed with 1,338 selected application cases (two expected
Windows symlink skips), 139 helper cases and 176 development-only cases. This
covers 1,653 distinct cases across the application and helper suites; the
development guard's nested suite rerun is not counted again. The ignored
listener test was excluded before import.

The actual Bash launcher ran in an isolated repository with the invented
fixture and an unavailable remote. It saved a 44,756-byte work35 report, checked
all sixteen artifact hashes and made exactly one local feedback commit. No Git
network operation occurred. The frozen six examples and eight-unit reservation
replayed unchanged. No real confidential files were used.

All sixteen artifact bytes matched between that run, a fresh direct analysis
and the CLI report. The CLI returned the expected partial-analysis exit code
of 3, and its HTML matched the published synthetic demo exactly. Canonical
validation passed for the saved companions. Against the previous release,
all fifteen non-HTML artifacts stayed byte-identical and eight earlier embedded
companions were unchanged. All eighteen previous summaries matched after
normalizing only tool revision. The 41 historical feedback reports stayed
unchanged and valid; the added invented report also validated. Final runtime,
asset and test files matched
the tested snapshot. Independent review had no remaining required fixes.
