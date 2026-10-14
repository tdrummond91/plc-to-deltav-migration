# Codex handoff: PLC analysis workbench

Current listener hold (2026-10-14): Tyler reported repeated endpoint-security
alerts involving bash.exe after the work-machine check of `1419af7`. The local
listener task is disabled and state is paused with no pending worker. Do not
restore automatic listener execution while that report is under investigation. The run
included listener Git/process-host regression tests in the application suite;
the specific detection is unverified and these changes do not prove its cause
resolved. Tyler is proceeding with a fresh clone and normal manual parser checks
using the local-only workflow below. Earlier restoration evidence is history.

Updated 2026-10-14. Current baseline: **Phase 1 source/reference tooling; local report commits automatic, pull/push manual**. Returned report `d247f87` confirms first-scan recognition with one system flag, 319 unresolved operands and a null sample. Both suites passed; other source/reference counts are stable. The next slice catalogs two-field ABS/LN/SQR calculation references. For the unchanged export, expect 28 additional catalogued instructions and 56 fewer unsupported-instruction slots if all use the documented signature. Read [calculation scope and evidence](docs/reviews/MATH_SIGNATURE_REVIEW.md), [work-machine procedure](docs/reviews/WORK_MACHINE_REFERENCES_RUN.md) and [command usage](../python-parser/README.md).

## Development-only listener files (2026-10-14)

Tyler requested that the work machine receive normal parser code without the
development feedback listener. `feedback-listener.sh`, `tools/feedback_listener/`
and `python-parser/tests/test_feedback_listener.py` are removed from tracking and
explicitly ignored. Their existing development-PC files are preserved locally;
the task remains disabled and paused. Fresh checkouts have no listener files,
and pulling this removal deletes the previously tracked copies on other PCs.
No parser or work-check command requires them. Listener documentation remains
as historical evidence; its source is retained in the pre-squash archive tag.

Do not re-add the local listener files to ordinary commits. A future maintained
listener should have its own development-tool repository or distribution path.
This removal neither restores the listener nor diagnoses the endpoint alert.

Validation used a clean export of the staged tree with no listener files: all
229 application/workflow tests (one existing Windows symlink skip) and 139 helper
tests passed, and the work-check entry point remained available. All 11 removed
files remain locally with unchanged Git-normalized contents. Independent review
found no remaining dependency or packaging blockers.

## Git baseline consolidation (2026-10-14)

Tyler requested one squash commit on `main` and retirement of the accumulated
topic branches. Documentation, decisions, reports and review evidence remain
intact. The primary feature's pre-squash history is retained by
`archive/phase1-before-squash-20261014` so reported tested SHAs remain retrievable.
The older divergent local summary branch was checked: its report is identical
and its review findings are already preserved in this baseline. Its exact two
extra commits are also backed up in the development checkout's local
`.git/branch-archive-20261014.bundle` before branch retirement.

Use `main` for the baseline on each computer. Future development starts from
current `main` on a new branch ending in `-pc`; do not merge a retired branch
back into the consolidated history. Manual work-machine checks accept `main`
and other named branches while retaining clean-tree and revision checks.
This Git cleanup does not mark Phase 1 complete or re-enable the listener.
The installed listener still targets the retired feature branch; any future
activation needs an explicitly selected new `-pc` target and updated local
configuration. Do not resume it against `main` or its old target.

Consolidation validation: 229 application/workflow tests passed (one existing
Windows symlink skip), excluding listener/Windows-host integration; all 139
helper tests and the synthetic fixture check with `l5x` passed. The 55 focused
work-check tests cover clean `main`, other named branches, dirty/detached
rejection and repeated local runs with an unreachable origin. Independent
review found no code blockers; no private input or listener execution was used.

## Current work-machine workflow (2026-10-14)

Work-machine recovery: its screenshot showed missing `.git/HEAD` and other
repository files. Tyler deleted the old checkout, then confirmed another old
folder contains the private inputs and is proceeding with a fresh clone. Keep
that backup intact; a fresh checkout needs its source selection supplied again.

Tyler clarified that running the script must automatically commit the report;
only fetching, pulling and pushing stay manual. The earlier removal of staging
and commits went beyond that requirement. The launcher uses the already checked
out clean named branch (including `main`) with no matching upstream required.
It saves and commits only the new validated feedback report under
`public/inspection/work-check-<run-id>.json`. Source selection remains in Git
metadata, and private logs/artifacts retain their `confidential/` locations.

Update code manually before a run. Review its feedback report, then run `git push`;
there is no manual copy, staging or commit step. The runner pins the tested
branch and revision, rejects unrelated changes, uses a report-only commit and
verifies its parent, changed path and validated report content in the working
file, index and commit. Failed test/analysis reports are also
committed locally. Git commit failure preserves the report for recovery.
Tyler additionally authorized one actual mystery operand, implemented below. Old reports
in Git-ignored `public/inspection/local/` are not picked up automatically.

Local report-commit validation: all 239 application/workflow tests passed (one
existing Windows symlink skip), excluding the ignored listener loader. Real
temporary-checkout CLI runs passed 152 selected application and 139 helper tests,
committed only the report and left a clean `main` with an unreachable origin.
Independent review found no remaining blockers; see the current
[runner review](docs/reviews/WORK_CHECK_RUNNER_REVIEW.md) for failure-case evidence.

Work-machine test execution uses explicit parser/helper module allowlists,
excluding listener, Windows process-host, Bash bootstrap and Git-fixture tests.
Full development unittest discovery remains available. Schema-1 reports remain
readable; schema 2 adds the bounded sample, schema 3 adds an unmatched-colon
fallback, schema 4 carries reference schema 6 with system-flag recognition,
and current schema 5 carries reference 7 with the ABS/LN/SQR signature catalog.
Consult the tested revision for historical suite scope
instead of treating reduced suite totals as a regression.

The confirmed timer report is `public/inspection/work-check-20261014T162634Z-2a7e40fe.json`,
returned in `1195d40`, testing clean `112ee82`. It validates, reports 177
application cases (one skip) and 139 helper cases with no failures/errors, and
records partial analysis with a private run saved. Its commit changes only the
report and has the tested revision as parent. Malformed-address/other_form counts
fall 868 to 0; non_data rises 0 to 868; unsupported-address falls 870 to 2.
The sample is null. All other source/reference counters are unchanged. This
confirms the predicted classification change without proving source byte identity.

The confirmed timer behavior recognizes trimmed `?` only in preset/accumulator
slots of valid three-argument TON/TOF/RTO instructions as `non_data` for root
lookup. Raw text is preserved; timer settings and effects remain unverified.
No repeat timer-only confirmation is needed.

The rack slice now captures RackConnection/InAliasTag/OutAliasTag separately,
derives conservative candidate roots and compares terminal missing roots under
existing scope/alias rules. Private references show candidates and occurrence
links; public summaries expose closed counts only. Unique matches do not become
ordinary terminal `root_bound` symbols because backing members are unexamined.
`candidate_names_unavailable` means matching is inconclusive, not that those
unnamed declarations correspond to the missing roots. Invented topology confirms
two candidate roots, one matching alias, two direct and one alias-mediated operand
matches, while ordinary bindings remain two bound and three unresolved operands.
Returned report `9597f18` now measures the real relationship: all 15 rack roots
are named, all 99 aliases and 319 alias-mediated occurrences have unique
candidates, and one direct occurrence has no candidate. No candidate names are
unavailable, ambiguous or outside scope. The report tested clean `9d159e0`, its
parent, passed 220 application cases (one skip) and 139 helpers, saved a private
run and changed only the feedback JSON. Ordinary source/reference counters are
unchanged; 26 XML elements across three paths are newly modeled and 11 warnings
now describe unknown backing instead of omitted declarations. The sample is null.

Current contracts: private inventory/reference schemas 3/4 with
`source-inventory-3` / `source-references-6`; public source/reference schemas 4/7;
work-check schema 5 and reference-run manifest schema 2. Historical public
reports still validate with exact original status vocabularies. Work schema 3
still requires reference 5 and work schema 4 requires reference 6. Read
[calculation review](docs/reviews/MATH_SIGNATURE_REVIEW.md)
for scope, version mapping, validation and the next report comparison.

Rack validation: 316 development application/workflow tests passed (one existing
symlink skip), including 43 new rack cases. The ignored listener loader was
excluded. Independent review found no remaining blockers after strengthening
mandatory warning and alias-mediated status reconciliation. Historical reports
remain readable. Final disposable-checkout workflow validation passed 220 selected
application cases (one skip) and 139 helpers, saved private synthetic artifacts,
made a report-only local commit and made no remote Git calls. See the rack review
for reproducible checks and exact scope.

Tyler's one actual mystery operand remains authorized: at most 128 printable
characters, a standard opcode and zero-based position, without rung/location IDs
or neighbors. Known timer placeholders are skipped. The rack slice does not
share individual rack names/relationships. The implemented follow-up retains one
sample total, choosing the first eligible malformed operand, then the first
unmatched direct colon operand only when no malformed sample qualifies. It
requires canonical direct no-candidate evidence and preserves exact raw text.
Schema 2 rejects the new kind; historical schema 3 requires reference schema 5.
See [follow-up review](docs/reviews/UNMATCHED_OPERAND_REVIEW.md).

Report `7f5db96`, testing clean `84dc393`, completes that one-address request:
`S:FS` at XIC argument 0. Its commit changes only the report, its tested revision
is its parent, 241 application cases (one skip) and 139 helpers passed, and a
private run was saved. All nested aggregate counts equal the preceding report
after excluding code revision; this does not establish source byte identity.

Rockwell identifies this as the First Scan flag. The implemented rule recognizes
only direct exact trimmed ASCII S:FS, ignoring case, in valid one-argument
XIC/XIO instructions. Raw evidence is preserved; no synthetic tag is created.
Aliases, other roles, suffixes and other S names retain their previous handling.
No runtime first-scan effects are modeled. Current reports reject it as a mystery
sample; historical returned samples remain readable. See the system-flag review
for official sources, boundary tests and final validation. Report `d247f87`,
testing clean `d64ee4d`, now confirms the exact predicted change: one system
flag, unresolved 320 to 319, direct rack comparisons 1 to 0, sample null, all
other source/reference counters unchanged. It passed 269 application cases
(one skip) and 139 helpers, saved a private run and changes only its report
with the tested revision as parent. No repeat flag-only run or mystery-address
request is needed. Partial analysis remains expected.

System-flag validation: 365 development application/workflow cases passed (one
existing symlink skip), excluding the ignored listener loader. Independent review
passed 99 focused cases with no blockers. Two actual disposable-checkout CLI
runs each passed 269 selected application cases (one skip) and 139 helpers,
preserved synthetic artifacts/rack counts, emitted one system flag and a null
sample, and made report-only local commits with no remote Git calls. All nine
stored work reports validate unchanged. Commands and evidence are in the
system-flag review.

The selected calculation slice adds only ABS/LN/SQR with two catalogued
source/destination slots using existing lexical root/literal rules. Source IDs,
raw operands, aliases and private field layout remain intact. Datatype, domain,
destination access, expression evaluation and runtime effects remain outside
this scope. Private text explicitly explains lexical destination literals.

Next compare the work-machine report against `d247f87`: if all 28 calculations
have the documented two-field signatures, catalogued instructions should rise
17,563 to 17,591 and unsupported instruction slots fall 653 to 597. Their newly
analyzed slots determine the actual root/literal/gap and alias-mediated rack
counts; do not predict those splits. Source counts and declarations should
remain stable. See the calculation review for primary evidence and validation.

Calculation validation: 382 development cases, OK with one existing symlink
skip; listener loader excluded. Independent review found no remaining blockers,
and its historical sample-contract coverage recommendation is retained. Two
actual synthetic CLI runs each passed 286 selected application cases (one skip)
and 139 helpers, saved the expected math delta and made only local report
commits with no remote Git calls. The second run confirms a newly saved report
does not break the historical fixture tests. All ten stored work reports remain
readable. Commands and final artifact evidence are in the calculation review.

Timer-fix validation: 273 application/workflow tests passed (one symlink skip),
with listener tests excluded. Two real temporary-checkout CLI runs each passed
177 selected application and 139 helper cases, validated null/remaining-gap
samples, preserved private raw slots and made report-only local commits. All six
stored work reports validate unchanged. Independent review confirmed no remaining
blockers. Details and reproducible commands are in the timer review above.

Historical sample validation: 259 application/workflow tests passed (one existing symlink
skip), with listener tests excluded. Two temporary-checkout CLI runs passed
166 selected application and 139 helper tests each, emitted the same one sample,
committed only their report, and preserved the source and prior outputs. All
five historical work-check reports still validate. Independent review found no
code blockers. That sample later returned in `349ee29`; the timer correction
was then confirmed by `1195d40` as recorded above.

Leave the development listener disabled and paused. Manual parser execution
remains under Tyler's control and is not gated on restoring the listener.

The checkpoints below retain prior implementation and validation evidence.
Earlier activation and automatic-publication instructions are superseded by
this current workflow and operational hold.

## Historical address-shape checkpoint (2026-10-13)

Historical listener restoration (subsequently reversed): the corrected scheduled task was enabled
and the listener was unpaused. Its first production poll after restoration ran at
00:14:29 America/Chicago, returned `LastTaskResult=0` and saved
`waiting_for_report` with no pending claim. Five-minute and logon checks were active.
Tyler's existing authorization covers automatic monitoring; the earlier hold for
terminal takeover is closed. Check live local status before interactive edits.

The historical hold followed terminal takeover after f18b34b. Disabling the task
stopped the interruption. Earlier foreground-window tests missed tab selection;
the corrected scheduled launch was subsequently verified at that boundary.

Root cause captured in scheduled testing: the uv virtual environment's
`pythonw.exe` is a console-subsystem redirector and opens Terminal before Python
code runs. The installer now verifies PE subsystem 2 and chooses the underlying
GUI Python executable. A repeated real scheduled worker had unchanged tabs and
selection with no window/focus events. `install.ps1 -UpdateLauncher` migrates only
the exact known old action while preserving the disabled task and paused state.

Listener maintenance: Tyler reported terminal interruptions from background work.
The replacement hosts the entire scheduled poll and ordinary descendants in a
private native ConPTY session and disables notifications only for the unattended
worker. It preserves exit codes, waits for attached descendants and records
local host diagnostics. The listener requires Windows 11 24H2+; parser/work-machine
support is unchanged. See [listener verification](docs/reviews/FEEDBACK_LISTENER.md).
Fresh validation: 274 application tests (273 passed, one existing symlink skip),
139 helper tests passed, independent review with no remaining blockers and a
successful real scheduled worker with passive Terminal-tab observation.
Global settings and parser contracts are unchanged. Inspect local listener status
before interactive edits. This validation preceded the report returned in
`b58af78` and the current operational hold.

The automatic worker verified event b06e7dc and the selected report's exact blob,
validated it and the preceding report, and confirmed no suite/analysis failure.
The selected report tests clean 6585443; the preceding one tests clean ad2ec8b.
The module/I/O improvements and remaining 868 malformed-address occurrences
reconcile with the comparison below. These counts do not identify source syntax,
prove source byte identity or justify a grammar change.

The bounded follow-up adds `operands.malformed_address_shapes` to public reference
schema 3 (`reference-summary-3`, policy 2). Seven fixed counters partition only
operand occurrences with `unsupported_address` / `malformed_address`. Alias-target
failures are separated from direct operand spellings. The other counters observe
a leading hash (with or without a remainder accepted by the existing static
address recognizer), brackets, colon, dot, or other form, in documented precedence.
No names, values, lengths, source hashes or per-occurrence records are published.
Parsing and binding behavior, private inventory/references 2/2, source aggregate 3
and the work-check envelope 1 are unchanged. Reference aggregates 1/2 still validate
under their exact historical contracts. The listener itself is unchanged.

Fresh validation: 246 application tests (245 passed, one existing Windows symlink
skip), all 139 helper tests passed; independent review passed 37 focused tests
and found no remaining blockers. The real launcher also passed in a disposable
checkout/local remote with invented input, validated schema 1/3/3 aggregate,
private artifact hashes and independently verified report-only push. Full
evidence is in ADDRESS_SHAPE_REVIEW.md.
The requested schema-3 histogram has since returned in `b58af78`; its analysis
is the next parser task after the workflow changes. No rerun is needed merely to
obtain it.
Compare the same input's statuses/reasons and the histogram total with the prior
868 count; no improvement in binding counts is expected from this diagnostic.
Do not infer the new histogram from this earlier report. If its closed buckets
cannot support a bounded syntax investigation, record the specific work-machine
question and stop; never request private addresses, inventories or logs.
Phase 1 remains active; engineering classifications, corrections, PCSD/FHX,
services and deployment remain outside this slice.

## Historical module/I/O checkpoint (2026-10-13)

Tyler authorized implementing the next slice here after the two successful
work-machine reports. Do not ask for that authorization again or repeat this
implementation. Phase 1 now inventories module ports, ordinary connections and
input/output/configuration tag declarations. Scoped reference lookup can use
explicit module-tag names or names inferred conservatively from supported
ICP/Ethernet topology. Private records keep raw source and naming provenance
separate; unavailable names and unresolved/unsupported addresses have fixed
reasons. RackConnection mappings remain an explicit unsupported gap. This does
not validate members, types, instruction effects or engineering purpose.

Current private contracts are inventory schema 2 (`source-inventory-2`) and
reference schema 2 (`source-references-2`). New public output uses source schema 3
(`aggregate-summary-3`) and reference schema 2 (`reference-summary-2`), both with
policy 2. Public validation retains source schema 2 and reference schema 1 with
its schema-2 source; hybrid versions are rejected. The outer work-check schema 1
and private run manifests 1/2 are unchanged. See
[data contracts](docs/planning/DATA_CONTRACTS.md) for details.

The work-machine report returned in f91ae18:
[work-check-20261013T234851Z-b10d84dc.json](inspection/work-check-20261013T234851Z-b10d84dc.json).
It validates and records clean tested revision 6585443, 208 application tests
(207 passed, one skipped), all 139 helper tests passed, partial analysis without
a failure code and private_run_saved=true. All 252 module I/O declarations receive
names: 164 backplane-slot roots and 88 module-name roots. Bound aliases rise from
45 to 842; unresolved aliases fall from 896 to 99. Bound operands rise from
17,856 to 20,178; unresolved operands fall from 2,642 to 320. Shared source counts,
instruction histograms, routine types, ladder metrics and reference coverage are
unchanged. This verifies improved root lookup, not engineering semantics or
source byte identity. The detailed comparison is in MODULE_IO_REVIEW.md.

All remaining unresolved aliases/operands have colon_root_not_declared. Their
relationship to 11 unsupported rack connections is unproven. Unsupported-address
operands remain 870: 868 outside the current address grammar and two dynamic
indices. The next bounded parser candidate is aggregate address-shape evidence
for those 868 cases, with invented examples and a closed publication contract;
do not guess a fix from the label alone. No additional work-machine run is needed
to review this report. Do not request private inventories, addresses, reference
records or terminal logs here. PCSD, FHX, editor and engineering classification
remain later work.

Tyler has now explicitly authorized a listener to check for new work-machine
pushes and continue agreed development. Implementation fde4fc2 is installed, and
the scheduled launch check returned exit 0. The latest report above is selected
for the first follow-up, so Tyler does not need to rerun it to trigger development.
Live monitoring/worker state is local and must be checked with the status command;
consult [FEEDBACK_LISTENER.md](docs/reviews/FEEDBACK_LISTENER.md) for validation,
local activation and operating details. Before interactive edits on a development
PC where it is installed, inspect `bash ./feedback-listener.sh status` and pause
it; let a running worker finish before taking over. Do not pause the listener
from its own dedicated worker checkout. The work machine needs only its existing
run-work-check command.
The workflow should process each new work report once, serialize repository
work, ignore its own code pushes and stop for required questions, work-machine
investigation or a phase checkpoint needing Tyler's decision.

The current application suite includes the listener's Git integration tests:
232 tests run: 231 passed and one skipped, plus all 139 helper tests passed.
Source/reference output contracts are unchanged by the listener.

The checkpoints below preserve earlier evidence and chronology. Their previous
next-step statements do not override this current checkpoint.

## Returned automated checks (2026-10-13)

Two work-check reports arrived in ad2ec8b and f38d81e, testing clean revisions
0666542 and ad2ec8b respectively. Both pass validate_work_check_report. Each
reports 155 application tests run (154 passed, one skip), all 139 helper tests
passed, no test failures/errors, partial analysis, no analysis failure code and
private_run_saved=true. Both commits change only their new aggregate JSON report.

After excluding tool_revision, both nested reference summaries exactly match
reference-summary-20261013T203510Z.json: 4,606 rungs, 17,874 instructions and the
same symbol/alias/operand counts. This verifies repeatable aggregate results and
the work-machine test/report/push cycle. It does not establish source byte identity
or independently inspect the private saved files. No real export or private log
was accessed here, and no local test rerun was needed for this report review.

No additional work-machine run was needed to close this earlier checkpoint.
Tyler subsequently authorized the module/I/O slice recorded above. Phase 1 remains
active.

## Work-machine automation checkpoint (2026-10-13)

Tyler requested one script that pulls, tests, runs the current analysis and pushes
results including test outcomes. `bash ./run-work-check.sh SOURCE.L5X` records
the local source choice; later runs need only `bash ./run-work-check.sh`. The path
stays in Git metadata. The script uses `git pull --ff-only`, locked dependencies,
both test suites, one captured source snapshot, new private inventory/reference
files and one closed aggregate report. It automatically commits/pushes only the
new report, including failed test outcomes. Failed tests skip source analysis;
partial usable analysis counts as successful workflow completion.

No separate fetch step or manual report staging is required on the work machine.
Real source, private records and detailed logs stay under confidential/. Shared
reports include the tested commit, suite event counts and bounded code-only failed
test IDs, plus reference/structural aggregates when analysis succeeds. Branch/HEAD
or working-tree changes stop automatic publication/push; a rejected push preserves
the local report commit. Read the runner review for the exact schema and tests.

Validation: 155 application tests run, 154 passed and one existing Windows symlink
skip; all 139 helper tests passed. Independent review passed the 47 new tests
without remaining blockers after corrections. An actual temporary-remote workflow
also passed success, failed-test and malformed-source scenarios, verifying both
successful and failed results are committed/pushed without private text. The work-machine
run has now returned and is reviewed above.
The module/I/O parser extension was implemented after this runner checkpoint;
see the current section above.

## Returned reference evidence (2026-10-13)

Tyler pushed public/inspection/reference-summary-20261013T203510Z.json in 7328809,
with clean code provenance at 294c839, and confirmed both work-machine test suites
passed. The reference aggregate validates. Its nested structural report exactly
matches summary-002 except for tool_revision; all 4,606 rungs remain accounted for.

17,563 of 17,874 instruction signatures are catalogued (98.26%). Of 24,583 operand
occurrences, 17,856 bind to declared roots and 2,517 are literals; 2,642 remain
unresolved, 870 have unsupported address syntax, 45 are unsupported expressions
and 653 occur in uncatalogued instructions. Aliases: 45 bound and 896 unresolved
out of 941. No ambiguity, cycles, depth limits or argument-count mismatches appear.
These are lexical-reference counts, not engineering interpretation percentages.

This evidence motivated the module/I/O declaration and fixed-reason slice now
implemented above. The public structural baseline includes 104 InputTag, 65
OutputTag and 83 ConfigTag elements omitted from the previous symbol model.
Their contribution to the unresolved totals remains unproven until the new run.
See the reference review for the earlier reconciliation and remaining limits.

## Preceding reference-analysis checkpoint (2026-10-13)

Tyler's corrected public/inspection/summary-002.json arrived in remote 3dd1b25.
It passes aggregate validation and matches the earlier readable baseline:
4,606/4,606 rungs parsed, 17,874 instructions, 6,307 tags, 941 tag aliases,
120 modules, 70 routines, one AOI and zero encoded regions. All ladder measures
match. Partial coverage reflects the already observed 14 SFC routines and one
RLL routine without content. The later reference run and suite confirmation are
recorded above.

Tyler then authorized continuing. The new branch starts at 3dd1b25 and preserves
the earlier review notes without resetting either history. `plc references`
adds private scoped declaration/alias/operand records from the captured inventory;
`plc reference-summary` publishes only fixed aggregate counts plus the structural
summary. Root binding does not validate members, access, effects or engineering
purpose. Unknown instructions, dynamic/qualified addresses, expressions and
missing module-tag declarations remain explicit gaps. Both publication paths
verify derived records against the source inventory before saving.

Implementation is b8d92bc. Validation: 107 application tests run, 106 passed,
one existing Windows symlink skip; all 139 helper tests passed. Independent review
passed all 48 reference tests after fixing record-integrity validation. Installed
CLI checks verified private storage, aggregate output, unchanged inputs and
no-overwrite behavior. The synthetic aggregate records clean b8d92bc provenance.

See the reference review for scope, primary documentation, independent review,
test evidence and resource bounds. The initial work-machine run has now returned
and is reviewed above. Use normal commits/pushes on feat/source-references-pc.
Engineering classification, editable corrections, GUI, PCSD and FHX remain later phases.

## First returned work-machine evidence (historical, 2026-10-13)

Tyler pushed public/inspection/summary-001.json in 61b9ca7. It reports a clean
028537d application revision, 6,000 tags, 111 modules, 70 encoded regions and
zero exposed routines/rungs/instructions. All 70 diagnostics are encoded_content
warnings. The aggregate passes a read-only v1-to-v2 schema compatibility check;
the original report remains unchanged and approved for sync.

The earlier public baseline had 6,307 tags, 120 modules, 70 routines, 4,606 rungs
and no EncodedData. Source equivalence is not established. The next action is to
confirm whether the same unchanged L5X or a different/new export was used, then
compare source availability on the work machine. Tyler may have sent the wrong
one and is checking; the cause is still unconfirmed. EncodedData counts do not prove
70 encrypted routines or identify their contents. No parser change was justified
from this aggregate alone. The corrected summary-002 above resolves the missing
readable-source evidence; the original report remains a separate comparison.

## Clarified sharing boundary (2026-10-13)

Tyler defines confidential material as information that permits rebuilding the
entire unit with data values, or more than 2% rung knowledge (D026). Aggregate
summary counts and technical codes expose no individual rung logic or process
values and are approved for repo sync. The previous private holding folder and
per-report sharing gate were unnecessary for these reports.

`plc summarize` now allows public/inspection/ output, records schema/policy v2
and `sharing_status=aggregate_sync_allowed`, and omits the review-before-sharing
warning. Its publisher validates and canonicalizes the bounded JSON before
writing. Raw `inspect` inventories and source exports retain their private
storage boundary. Future rung samples need separate coverage accounting; no
rung-sample allowance or whole-unit reconstruction capability was added here.

Validation: 59 application tests run, 58 passed, one existing Windows symlink
skip. Independent review passed all 25 summary tests with no remaining blocker.
Tyler's v1 work-machine report has now been returned and reviewed above; no
rerun was needed merely to adopt the clarified sharing policy. Earlier review-gate
statements below describe the superseded v1 policy, not a current approval
requirement.

## Summary export checkpoint (2026-10-12)

Tyler authorized building/testing the next slice and pushing it to GitHub for a
work-machine run. This branch starts at 79d865f and includes the source-inventory
commits. `plc summarize FILE [--output NEW.json]` reconstructs a fixed, bounded
aggregate schema from one captured source inventory. It includes component and
coverage counts, approved routine/instruction vocabulary, pooled withheld labels,
global ladder measurements and diagnostic counts. It excludes source identities,
hashes, names, paths, operands, layouts and per-occurrence records. Code revision
metadata refers to the application checkout, not the source export.

The summary is a local review candidate. Optional explicit output stays private
inside this checkout, uses atomic no-clobber publication and does not save an
L5X or raw inventory. Existing files remain untouched. Exit 3 means a usable
partial-coverage summary was produced; it does not imply a failed save.

Validation: 56 application tests passed plus one existing Windows symlink skip;
all 139 helper tests passed. Installed-command checks against both public fixtures
verified counts, unchanged inputs, no source hash in output, and preserved
existing reports. Independent review findings about OS-error disclosure and
impossible internal states were fixed and rechecked without remaining blockers.
Exact tested revision and command evidence are in SUMMARY_EXPORT_REVIEW.md.

Next action is Tyler's bounded work-machine run using the linked procedure.
Return only the locally reviewed summary JSON and test outcome. No real-export
run has occurred on this PC. Further symbol/alias analysis can follow the returned
evidence; PCSD/FHX and editor implementation remain deferred. Git log/status and
the branch's remote tip determine publication state; earlier no-push statements
below are historical checkpoints.

## Preceding source inventory checkpoint (2026-10-12)

The feature branch starts at 3cfdb57 on chore/project-scope-review-pc; source
implementation and validation are recorded at f9f61bc. The new
`plc inspect` captures input bytes once and produces JSON or readable reports
with scoped declarations, ordered rungs/instructions, source offsets, coverage
and diagnostics. Optional explicit private storage creates a new run with the
exact snapshot, complete reports and a manifest published last. Source IDs are
snapshot-specific; persistent engineering identities and review overlays remain
future work. The existing main.py prototype remains available.

Validation: 29 application tests passed, one Windows symlink test skipped, and
139 helper tests passed. The public minimized-fixture audit and synthetic fixture
checker passed. Installed CLI checks from an unrelated temporary working directory
parsed all 9 synthetic rungs (25 instructions) and all 276 minimized rungs
(1,904 instructions). Both correctly reported partial coverage for unsupported
routine content; the minimized fixture also includes an RLL routine without a
content block. These are public fixture results, not real-export validation.

Independent code review found and prompted fixes for declaration context,
unrecognized executable XML, ambiguous descriptions/comments and canonical
snapshot identity. The shared grammar now limits total branch legs and argument
slots and records instruction spans. Standalone inspection helpers import that
same grammar from python-parser/src; copy the full branch across machines rather
than only the old tools folder. No confidential files were read or remote
branches pushed. Use git log/status for the exact local commit state.

No work-machine run is required to continue development. A bounded public-summary
export is the recommended next slice before asking Tyler to return new private
inventory results. After that, scoped symbols/aliases and references can build on
this foundation. GUI/database decisions, editable review data, PCSD and FHX are
still deferred. Detailed evidence, limits and next-step rationale are in the
implementation review linked above.

## Confirmed scope and preceding documentation checkpoint (2026-10-12)

Tyler confirmed a reusable migration tool for several units. The five product
phases and workflow are recorded in docs/planning/ROADMAP.md and decisions D013-D025.
L5X analysis has two parallel outputs: information/scanning reports for source
understanding, and editable engineering files used to organize objects and build
the PCSD. Both need links to the same source evidence. PCSD feedback, class-based
FHX generation and FHX-to-PCSD are explicitly in the long-term scope.

Review is sequential initially, but participant order is not fixed. Tyler,
Quebec and the development team are participants, not hardcoded workflow stages.
Choose the recipient at each handoff and keep the policy adaptable. Approved
corrections must survive reruns. Changed, expanded, collapsed, split or combined
objects require reconciliation rather than losing prior decisions.

PCSD means Process Control Strategy Document. The earlier MOD-to-DeltaV workflow
used Excel, which was accessible to users but difficult to organize and version.
The PCSD supports generating plant test sheets for a DeltaV unit and simulation.
Candidate content includes I/O, selectors, PID relationships/flowcharts,
sequences/transitions, alarms, communications, external references, Boolean and
floating-point calculations, valves and pumps. Source understanding comes first;
the final PCSD content/schema is not settled. L5X sequences may require explicit
engineering design, and source grouping is not automatically target unit/module
or execution-location grouping.

Tyler prefers a standalone editor with search, useful navigation, change review,
import/export and backups, while retaining Excel if it proves useful. Design
deployment for non-programmers without a separately installed Python runtime.
SQLite as a local project store and PyInstaller-style Windows packaging are
recommendations to evaluate, not installed components or confirmed selections.
Tyler prefers sequential review initially: one active editor, followed by a
revision-bound handoff to the next reviewer. Validate returned changes against
their base revision and flag stale copies. Shared live editing and concurrent
copy reconciliation are later options, not initial requirements. Keep the
one-active-editor policy separate from participant identity and routing.

Only non-proprietary code/tools and reviewed development artifacts travel through
Git. Real L5X files and private engineering state stay local. Tyler may supply
bounded summary reports and stripped dummy ladder examples for development;
these should not enable reconstruction of the complete process.

On this editing PC, origin was fetched and main matched origin/main at bafc410.
Created local branch chore/project-scope-review-pc as requested. Scope was
recorded in 3ade905 and sequential-review preference in e8a1ede; subsequent
clarifications are separate documentation commits. Use git log/status for the
current commit/push state. All 130 helper tests passed, and the read-only
minimized_review audit passed (7,303 source links, 276 rung records, 194 paths,
431 variants). No confidential source was read. Changes in this scope discussion
are documentation only. Future PC development branches must end in -pc.

Scope-document validation: reviewed the changed requirements/proposals, checked
the referenced local review entry point, and passed git diff --check. The helper
test/audit results above are from the initial repository inspection in this
session; documentation changes did not trigger a repeated test run.

After Tyler requested code/fixture examination and invited subagents, independent
validation, parser review and design-readiness review checked the unchanged
implementation again. Fresh results: 130 tests passed (0.077 seconds), the
minimized_review public audit passed, and the synthetic fixture checker passed
including l5x tag access. No stable-input blocker was established within the
documented outer-syntax/metrics contract. Allocation limits, sanitized-opcode
round-trip assumptions and changing-input protection need explicit treatment
as the reader evolves. Exact probes, commands and limitations are recorded in
docs/reviews/NEXT_DEVELOPMENT_PROMPT.md.

At this preceding documentation checkpoint, the recommended next slice was one private snapshot-bound source inventory,
selected-rung evidence and gap reporting, with JSON/readable views over shared
records. Current scrubbed fixtures validate structural breadth but not source
relationships: the minimized sample retains 276/4,606 rungs and 161/554 shapes,
with per-rung ARG identities. Use coherent independent synthetic cases for future
reference tracing. This review does not select the GUI, database or final PCSD
schema. Implementation followed in the source-inventory checkpoint above.

A separate ChatGPT chat will review the work. Keep focused conventional commits,
decision rationale, useful code comments and reproducible validation notes. Read
docs/reviews/NEXT_DEVELOPMENT_PROMPT.md (relative to public/) for the review entry
point. When work-machine turnaround is slow, Tyler may test up to three sibling
experiment branches from a common baseline and return their comparable results.
This is a workflow option, not a request to create three branches immediately.

The sections below retain the earlier work-machine evidence and chronology.
Their pending Git/checkpoint statements describe those earlier sessions, not
this PC's current state. The five product phases are distinct from helper
Stages 1-5 and the earlier technical implementation milestones.

Tyler wants one small helper at a time: provide code, let him run it, inspect the
result, then implement the next piece. Do not jump directly to a complete dummy
generator or migration framework.

## Historical inspection status (2026-10-09)

- Stage 1: Tyler reported 19 tests passed and supplied the counts JSON. Its nested
  counts reconcile with 83,942 elements, 213,876 attributes, 194 paths and depth 14.
  Codex did not read the original confidential input.
- Stage 2: Tyler reported "no errors". Codex has now independently audited the
  complete public skeleton against Stage 1: all structure/counts match, all
  attribute values and direct text are blank, and CDATA counts reconcile.
- Stage 3: Tyler supplied 58 passing tests and a successful real-input run:
  194 paths, 213,876 attribute values, 70 routines. Codex read the generated public
  JSON and reconciled value accounting and source totals with Stage 1. The original
  confidential export was not read.
- All work by Codex remains in task handoff artifacts. No repository/Git writes.

## Reviewed Stage 3 findings

The report accounts for all 213,876 attribute values: 90,414 approved technical
literal observations plus 123,462 withheld observations. Per-field occurrence,
unique-value and missing-attribute counts reconcile. Source totals match Stage 1.

Routine types: 56 RLL and 14 SFC. Exactly one reported Routine has no child
elements: global routine ordinal 68, located at
/RSLogix5000Content[1]/Controller[1]/Programs[1]/Program[2]/Routines[1]/Routine[1].
Its declared Type is RLL. This explains the 70-record/69-content-block gap.
The empty element is observed; intentionality is not established.

Tag kinds across controller/program scopes: 5,364 Base, 941 Alias, 2 Produced.
Declared Tag datatypes include 2,993 BOOL, 1,536 REAL, 434 TIMER, 129 DINT,
39 INT, 27 MESSAGE, 7 SINT, 4 CONTROL and 3 COUNTER observations.
194 Tag DataType observations remain withheld (177 controller, 17 program);
do not label them all as custom or infer the actual names.

Across Data and DefaultData elements: 5,597 Decorated, 5,511 L5K and 27 Message
formats. These are representation counts, not separate tag counts.
Task types are 1 CONTINUOUS and 2 PERIODIC; actual scan rates remain withheld.

## Stage 4: rung inventory implemented and reviewed

The helper is ready as a task handoff. It adds:
- `tools/l5x_inspect/inspect_rungs.py`: arguments and console summary.
- `tools/l5x_inspect/rungs/syntax.py`: pure neutral-text structure parser,
  measurements and sanitized representations.
- `tools/l5x_inspect/rungs/inventory.py`: XML reading, coverage, grouping,
  ranked samples and JSON publication.
- Two test modules plus RUNGS.md and RUNG_VALIDATION.md.

The 58 unchanged earlier tests and 36 new tests passed together (94 total).
CLI help passed. Tests used invented in-memory inputs and mocked writes.
Tyler has now copied the helper, passed all 94 tests locally, and run the actual
export successfully. Codex reviewed the generated public report; see below.

Default output: `public/rung-structure.json`, schema_version 1, parser_version 1.
Coverage accounts for every encountered ladder rung as parsed or unparsed, and
separately counts ignored non-ladder Rung elements. Program and AOI ladders are
included. The actual report accounts for all 4,606 ladder rungs as parsed.

The JSON provides per-rung ordinal locators, numeric Number, approved Type,
metrics, pattern IDs and diagnostic codes; pattern records link back to rung IDs.
It counts instruction calls, argument positions, expression-bearing instruction
calls (CMP/CPT/FAL/FSC only), branch groups/legs, depth, normalized height and
normalized width. Inner expressions remain opaque. Height counts parallel lanes;
width counts instruction boxes and excludes wiring. These are structural measures,
not Studio pixels, execution timing or proof of behavioral complexity.

Shapes preserve ordered instruction labels, arity, empty argument positions and
branch topology. Operand values, reuse and inner expression structure do not
define shape identity. Select up to five distinct shapes per ranking by default:
tallest, widest, deepest and most frequent. The sample list is deduplicated across
rankings; tied scores use first source occurrence.

Samples retain the authorized instruction/branch layout with every nonempty
whole argument replaced by ARG placeholders. Identical stripped arguments share
a label only within a sample. Unlisted instruction names become run-local
UNLISTED_OP labels; this is not a declaration that they are custom or invalid.
No raw comments, identifiers, operands, source filename/path or source hash
enter the report. Private mappings are not persisted in this slice.

PASS means all encountered ladder rungs were structurally parsed. PARTIAL means
a report was still saved, with unparsed locators and error codes; valid runs
return exit code 2 in this case. Measured totals and rankings cover only parsed
rungs. No partial instruction counts are guessed from failed rungs.

Keep the original source local. Ladder branching is parsed from Rung/Text, not
the XML Branch elements belonging to SFC. Syntactic samples do not establish
semantic equivalence or Studio import validity. The complete minimized dummy L5X
and general ASCII renderer remain later slices.

## Reviewed Stage 4 findings

Tyler ran all 94 tests successfully in 0.037 seconds, then ran the helper on
the actual local export. The console reported PASS. Codex subsequently read
public/rung-structure.json and independently recalculated its shape metrics,
weighted totals, rankings and occurrence links from the saved public trees.
The confidential source was not opened by Codex.

- 4,606/4,606 ladder rungs parsed; 0 unparsed; 0 metadata findings.
- 4,604 program rungs and 2 AOI rungs; totals agree with earlier stages.
- 554 distinct ordered structural shapes; every rung links to exactly one.
- 17,874 instruction calls; 24,583 argument positions, all nonempty.
- 3,719 branch groups; 8,887 branch legs; no empty branch legs.
- Maximum nesting depth 4, height 59 lanes, width 18 instruction boxes.
- 46 expression-bearing calls: 45 CPT plus 1 FAL. Inner mathematical operators
  are not counted.
- 19 selected samples after deduplicating the four top-five rankings.
- All sample operands were checked as ARG placeholders; rendered sample text
  matches its saved tree and shape. This is an output-format check, not a
  comparison against original confidential values or a general secrecy proof.

The tallest example is pattern_00038, rung_000237, original rung Number 5.
It has 94 calls, 6 branch groups, 64 total legs, and depth 2. Its outer branch
has 49 legs; five nested three-leg branches add ten lanes: 49 + 5*(3-1) = 59.
Its normalized width is 3 instruction boxes.
The widest example is pattern_00420, rung_003215, Number 33: width 18,
height 6, depth 2, 25 instructions.

The most frequent shape, pattern_00048, occurs 999 times:
XIO(ARG_001)OTU(ARG_002);. Equal shapes do not prove equal behavior.

UNLISTED_OP_0001 occurs exactly once, in pattern_00007 / rung_000007:
ordinal locator
/RSLogix5000Content[1]/Controller[1]/Programs[1]/Program[1]/Routines[1]/Routine[1]/RLLContent[1]/Rung[5],
Number 4. Its structure parsed successfully. Its original mnemonic remains
unknown and masked; do not infer that it is custom or invalid. It is outside
the 19 ranked sample selections; retain a sanitized representative for this
case in the next dummy fixture.

Source totals still match Stages 1 and 3: 83,942 elements, 213,876 attributes,
194 paths, depth 14. All 554 shape metrics, 4,606 occurrence links, weighted
instruction/branch totals, four rankings and 19 sample/tree links reconciled.
No new parser correction is indicated by this report review.
This verifies report consistency, not instruction semantics or Studio validity.

## Stage 5: first minimized fixture generated and reviewed

The handoff adds minimize_l5x.py, dummy/model.py, dummy/selection.py and
dummy/build.py under tools/l5x_inspect/, plus test_minimize_l5x.py, MINIMIZE.md
and MINIMIZE_VALIDATION.md. Earlier helpers and the application are unchanged.

The helper opens the original export read-only and recomputes its rung inventory.
It requires complete rung parsing and no rung metadata findings. It sanitizes
values, selects representative XML, writes a structural L5X example and a
companion report. No dependency installation is needed.

Default outputs:
- public/fixtures/minimized/controller_demo.L5X
- public/fixtures/minimized/minimized-report.json

The initial policy-1 --per-variant 5 sampled consecutive equivalent local runs.
The reviewed policy-2 handoff counts first N occurrences per variant under each
retained parent, including interleaved variants. Mandatory
anchors retain the first occurrence of every global local variant, the ranked
ladder examples, every instruction label (including masked ones), and all needed
ancestors. Selected ladder Rung subtrees are retained completely. Retained
siblings stay in source order. The cap is not a global five-per-element limit.

Variant identity includes path, attribute names/categories, approved technical
values or masked datatype identity, collapsed ordered child-name runs, source
direct-text/CDATAness and text action. It is not full subtree or behavior
equivalence. Publication checks all source paths and variant IDs are represented
and verifies emitted element/attribute counts.

Stage 3 approved technical literals and numeric rung Number/approved Type remain.
Other identifiers, datatypes, descriptions and scalars receive invented values.
Whole recognized identifier/reference strings share run-local DUMMY_ID labels;
other datatypes share DUMMY_TYPE labels. Ladder ARG labels are separate per rung.
No scope/member/reference resolution is claimed. Private replacement dictionaries
exist only in process memory; every retained element has public source/output
ordinal XML locators for back-reference.

Serialized non-ladder text, ST lines and mixed direct text receive explicit
placeholders and are reported. Original comments/PIs are omitted and counted.
Task/SFC links, array dimensions/indices and member references are not repaired
for semantic coherence. Output is for structural parser development; controller
import/operation has not been validated.

The coverage JSON records source/retained/omitted elements, attributes and text
values by path, selection reasons, replacement action counts, unsupported retained
payloads, rung records and source/output occurrence links. output_sha256 hashes
the generated XML only. XML and report are individually atomic, with XML written
first and report second; they are not one atomic two-file transaction.

Validation completed:
- 118 combined tests passed (94 unchanged plus 24 new), 0.116 seconds.
- CLI help passed.
- Full actual public skeleton verified: 83,942 elements, 213,876 attributes,
  194 paths, depth 14, 18,351 CDATA-bearing elements, all values/text blank.
- An in-memory integration using the 19 approved public rung examples plus the
  masked-opcode shape passed. From 20 inputs it selected 16 with per-variant 1
  and preserved depth 4, 49-leg maximum, 59-lane height and width 18.
- No confidential export was opened and no repository/Git writes occurred.

Actual Stage 5 run and public-output review are complete.

Tyler passed all 118 tests locally (0.057 seconds), committed the helpers and
earlier reviewed public reports as 6c50244, and successfully pushed main to
origin/main. The push created the remote branch and set tracking. The new
minimized files were generated afterward; no subsequent commit/push was reported.

The real-input generator reported:
- 44,545 of 83,942 elements retained; 39,397 omitted.
- 194 of 194 XML paths and 431 of 431 local variants represented.
- 2,397 of 4,606 ladder rungs retained, covering 458 of 554 source shapes.
- All 42 encountered instruction labels represented, including the masked one.
- 4,171 opaque payload replacements, 107 ST-line replacements and 12 mixed-text
  replacements among retained elements.
- Generated XML 4,078,792 bytes; companion report 14,379,883 bytes.

Codex read the two public files and ran a read-only audit, without opening the
confidential original. The generated XML hash matches its report. Every one of
44,545 output/source occurrence links was verified against the full blank
skeleton, including unchanged element names and attribute-name sets. All 194
per-path source/retained/omitted counts reconcile with the earlier reports and
actual output. All 2,397 rung source records, metadata, shapes and metrics match
the Stage 4 report. All 19 ranked source examples and 42 instruction labels remain.
Maxima remain depth 4, 49 direct legs, 59 lanes and width 18. All 108,252 output
attributes were checked against the stated public/dummy value categories, with
zero findings. All 13,131 nonblank direct text fields, including whole ladder
operands, passed their replacement-policy checks.

These checks verify output structure, provenance and stated replacement policies;
they do not establish instruction semantics, coherent runtime references, Studio
import validity or a general confidentiality certification. Public source/output
ordinal locators apply to this source ordering only.

## Stage 5 review corrections: installed and verified by user

The independent review confirmed two issues. See
public/docs/reviews/STAGE_5_CODE_REVIEW.md and
public/inspection/stage_5_corrections.json for original file/line evidence.

1. The sampler reset its quota between consecutive variant runs. It now counts
   the first N occurrences of each variant across each retained parent.
   Mandatory anchors and their ancestors, full selected rung subtrees, global
   path/local-variant coverage, ranked examples, instruction representatives,
   source ordering and occurrence mappings are retained.
2. Skeleton publication checked counts/text but could accept nonblank attributes.
   parse_structure now has an opt-in require_blank_attributes gate, enabled when
   create_skeleton verifies its completed output. A failing gate prevents
   publication without printing the unexpected value.

The new minimized report uses schema_version 2 and policy_version 2.
selection.per_parent_variant_limit replaces per_consecutive_variant_run.
Other report schemas are unchanged. Variant identity itself is unchanged;
retained parents may lose entire later child-name runs when redundant examples
are omitted. The full blank skeleton remains the authority for complete nesting.

Twelve new tests were run against the unchanged helpers first: four expected
failures established the two quota cases, version contract and skeleton gate.
After the bounded correction, all 130 tests passed in 0.182 seconds. Existing
count, parser, sanitizer and publication tests also passed. Tests use memory
and mocks, with Python -B; no workspace writes or confidential reads occurred.

The existing policy-1 public pair was freshly audited: 44,545 links, 2,397 rung
records/shapes/metrics, 194 paths, 431 variant IDs, all 19 source ranked samples,
42 instruction labels, counts, source order, full retained rung descendants and
replacement policies reconciled. The actual public skeleton also passed strict
blank-attribute verification; no existing retained attribute value was found.

A separate in-memory re-minimization of the existing public fixture retained
7,303 of 44,545 elements and 276 of 2,397 rungs. It preserved 194 paths, 431
variants, 19 rankings selected for that public input, all 42 instruction labels
and maxima depth 4 / direct legs 49 / height 59 / width 18. Every retained source
link and rung tree was checked. These are public-fixture integration counts;
that check did not regenerate the original confidential source. The subsequent
user-run original-source results are recorded below; keep the two evidence
sources distinct.

The handoff files are under the task outputs/l5x-inspect-stage-5-fixes directory.
Tyler has installed them; both pre/post-install verification checks passed.
Codex did not install files in the repository. COPY_AND_RUN.md contains bounded
backup/copy commands. verify_handoff.py checks all destination code/document
hashes before replacement and detects skipped/changed files after installation.
It handles line-ending differences only, not other edits. The package also
contains unchanged helper snapshots for task-local tests; copy only the paths
listed in install-files.txt, never the whole snapshot.

## Policy-2 original-source run and public review: complete

Tyler supplied the completed install/test/generation/audit output. Both checks
verified 13 handoff files and 12 dependencies. All 130 tests passed in 0.061
seconds. The original-source run produced public/fixtures/minimized_review.
Codex read that public JSON and generated XML bytes, confirmed schema/policy 2,
reconciled the report summary and independently verified its generated-file hash.
Codex did not open the confidential original or repeat the production run.

Actual original-source coverage:
- 7,303 of 83,942 elements retained; 76,639 omitted.
- 194/194 XML paths and 431/431 local variants represented.
- 276 of 4,606 rungs retained, representing 161 of 554 ladder shapes.
- All 19 ranked source examples and 42 instruction labels preserved.
- Maxima unchanged: branch depth 4, direct legs 49, height 59, width 18.
- 204 opaque payload, 78 ST-line and 11 mixed-text replacements retained.
- Output: 18,539 attributes; 1,493 nonblank text-bearing elements;
  1,016 CDATA-bearing elements; XML depth 14.
- XML 714,140 bytes; JSON 2,854,812 bytes.

The user's public checker returned PASS: generated XML hash matches; all 7,303
occurrence links and 276 rung shape/metric pairs verified; all required path,
variant, ranked-example and instruction-label coverage accounted; zero attribute
policy findings; all 1,493 nonblank text fields passed policy checks.
These are user-run checker results plus Codex's direct public-report/hash review.

The previously oversized parent/variant group fell from 614 retained rungs to 7.
Codex inspected their recorded source locators and mandatory selection reasons:
first five ordinary examples plus one CTU and one RES instruction representative.
The two extra examples are intentional quota exceptions, not counter resets.

The fixture is representative, not complete ladder-pattern coverage. The full
rung-structure.json retains all 554 shape records and all 4,606 rung occurrences.
Keep the policy-1 minimized folder as a comparison until a separate cleanup is
chosen. No helper code changed after the 130-test review checkpoint.

See public/inspection/stage_5_run_review.json for the portable result record.

## Next bounded step: documentation checkpoint and Git review

Copy the updated handoff and stage_5_run_review.json from the task
outputs/l5x-inspect-stage-5-run-review directory. Then Tyler should fetch origin
and return git status and ahead/behind evidence before commit/push instructions.
No new commit/push is reported. The earlier successful main push is the last
confirmed remote event; Codex has not fetched or modified Git.

Generated references, array dimensions/indices, sampled SFC graphs and opaque/ST
payload placeholders remain outside semantic validity. Two output files are
individually atomic, not a transaction. GUI, translation and DeltaV conversion
remain deferred. Next development scope should be chosen after this checkpoint;
do not start another broad implementation automatically.

## Stage 3 report contract

The report includes source_totals, coverage, policies, routine_coverage and paths.
Every path row has an element count and per-attribute/direct-text statistics:
occurrences, distinct parsed strings, lexical-type counts, approved technical
literal counts, withheld counts, invented examples, and missing-attribute counts.

Lexical types are syntax categories. Integer 0 is not proof of BOOL or DINT.
Same-element DataType context is reported separately for Value/ForceValue or
direct text; parent inheritance and tag/reference resolution are not implemented.
Date-like shapes are not calendar validation. Distinct strings are kept only in
local process memory and are never dumped, hashed into the report, or sent online.

An explicit limited permission list allows common builtin types, routine types,
task types, TagType, Radix, ExternalAccess and selected documented Data formats.
Unrecognized values stay withheld but counted. Do not label all withheld types
as custom: some may be valid builtin types outside the initial list.
A small repeated value set is only a heuristic, never permission to emit values.
Actual descriptions, identifiers, constants and source logic remain absent;
examples are independently invented placeholders.

Routine records use ordinal XML locators, not names. Direct children establish
content coverage; STContent inside an SFC transition condition does not establish
an ST routine. Missing/multiple/mismatched blocks and protection markers are
review findings, not proof of an invalid PLC project. Ordinal locators apply only
to this source ordering, not as stable IDs across future reordered exports.

Opaque payloads are not decoded. Stage 4 now implements outer ladder syntax and
structural dimensions. Semantic analysis, persistent mappings, translation and
GUI logic remain separate future work.

## Findings from the Stage 1 JSON

There are 3 programs, 3 tasks, 120 Module records, 1 AOI definition,
70 Routine records, 4,606 ladder Rung elements, and 6,307 Tag elements
(6,261 controller plus 46 program). InputTag/OutputTag/ConfigTag, AOI Parameter
and AOI LocalTag records are different element types and excluded from Tag counts.

55 RLLContent blocks comprise 54 program blocks plus one AOI block.
14 SFCContent blocks contain 14 Branch elements and 34 Leg elements.
The 155 STContent blocks are under SFC transition Conditions.
No EncodedData element is present in this particular report. DataTypes exists
without child definitions; this alone does not exclude custom type references.

Resolved by Stage 3: one RLL Routine has no child elements. See the reviewed
findings above for its ordinal XML location.

Different Data representations and scopes must stay distinct. Profile Format
values before interpreting payloads; a Data count is not a tag count.

## Required eventual outputs

| Output | State |
|---|---|
| Nested counts JSON | User-run report inspected; totals reconciled |
| Full blank XML skeleton | Complete public skeleton independently verified against Stage 1 |
| Type/value profile | User run and public JSON reviewed; accounting reconciled |
| Minimized dummy L5X | Policy-2 original-source run and public audit passed; 276 sampled rungs with required coverage |

Full skeleton: preserve every element, repeated instance, sibling order and
attribute name; blank all values, including Number, Type and DataType.
The later dummy L5X may retain approved technical values.

Tyler permits retaining sampled rung instruction and branch layouts, rung Number
and Type, with tag names and constants replaced. Include tallest/widest branch
examples and branch/expression-call counts. Stage 4 implements the first pass;
actual-input coverage and the saved public report have now been reviewed. Define metrics against observed
neutral syntax; do not infer ladder branching from SFC Branch elements or the
blank XML skeleton. Keep real reverse mappings in confidential/.


## Layout and machine boundaries

- `python-parser/`: current application prototype; do not refactor in this slice.
- `tools/l5x_inspect/`: standalone auxiliary inspection helpers.
- `public/`: portable documentation, invented fixtures, and reviewed structural
  reports/examples approved for sharing.
- `confidential/`: source exports, private derived data, mappings, logs, reviewer
  workbooks, and checkpoints. Inputs are under `confidential/plc-code/`.
- Root `.gitignore` excludes `confidential/` and Python environments/caches.
  Preserve the current ignore files; no replacement is needed for this slice.

Read the current machine's AGENTS instructions first. On the work machine, Codex
may only create handoff artifacts in its designated task artifact directory.
Repository files, configuration, Git metadata, and remote state are read-only.
Provide exact Git Bash commands for Tyler to run; do not execute them or request
permission to bypass that boundary. On an authorized editing machine, make the
selected changes directly within that machine's instructions.

Tyler created the renamed project copy, initialized Git on main, and configured
origin. Do not rerun git init, discard history, or add origin again. Current
working-tree/staging status and remote freshness were not verified for these
handoffs; a read-only Git status attempt was denied by the environment. Preserve
local changes and inspect status before staging. Fetch/check remote state must be
user-run before recommending a push; do not use force push to resolve rejection.

The old independently invented fixture passed Tyler's checker including l5x tag
access. That verifies the toy's internal checks, not coverage of his real export,
nor Studio 5000 import validity. Use it as a limited test fixture, not as authority
for the source schema.

## Broader direction retained

The future application should have a thin argument/UI layer and reusable parsing,
analysis, and reporting services. Ladder is the first detailed target. Inventory
must still count SFC and other routine types, tags by scope, tasks, modules, rungs,
and instructions such as JMP where their text can be parsed.

JSON should drive overview reports and a future GUI. Navigate from broad counts
and pattern groups down to concrete occurrences. Keep explicit links to source
locations and support many-to-many mappings; one classification can span rungs,
and one rung can have multiple classifications. Patterns alone do not establish
behavioral equivalence. Preserve scan order, jumps, timing/task context, and
inter-controller relationships during later execution-graph analysis.

Each stage must account for parsed content, preserved unknowns, deliberately
ignored content, and errors. Immutable original inputs, versioned checkpoints,
and review overlays must support resume, back-reference, and Excel export/import
round trips without silently overwriting prior decisions.

French/Quebec shorthand interpretation should eventually support AI suggestions,
uncertainty, unresolved items, and bilingual human review. Provider and data scope
are unresolved. A confidence score is not automatically a calibrated probability.
Keep a reversible glossary/mapping; do not alter the original source text.

DeltaV FHX conversion is deferred. Target library/version, mapping semantics,
execution behavior, acceptance tests, and the conversion design are not chosen.
No PLC download or runtime change is part of this work.

Earlier planning remains under `public/docs/planning/`: ARCHITECTURE, DATA_CONTRACTS,
CLI_AND_REVIEW, L5X_STRUCTURE, ROADMAP, CONFIDENTIALITY, and DECISIONS. Treat it as
a proposal subject to actual-structure findings and the staged sequence above.

## Progress and handoff maintenance

Stages 3 and 4 results are recorded above. Stage 4 user tests and source run
succeeded, and Codex inspected the generated public report. The first minimized
L5X generator has now passed the user run and public-output audit. The code
checkpoint was pushed; generated outputs have no reported subsequent push.
Fresh review corrections are installed by Tyler. Policy-2 original-source
generation and the public checker passed; Codex reviewed the generated public
report/hash and mandatory exceptions. Documentation checkpoint and user-run Git
review are next; no new commit/push has been reported.
Keep user-reported runs distinct from inspected output and semantic validation.

After each slice, update:
- implemented behavior and schema/script versions;
- actual commands run, results, and limits of those results;
- unresolved structures and unsupported syntax;
- agreed next bounded step.

Keep real tag names, plant paths, raw ladder text, confidential hashes, and private
diagnostics out of this public document.
