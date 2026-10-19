# Private engineering review report

## Grouped candidates and block evidence

Signal relationships now offers **Grouped source candidates**, with exact
condition/output pairs, five seed filters and source-field evidence. Engineering
analysis joins specialized PID, routine, file-operation and AOI context to the
original blocks while retaining base roles and unresolved effects. See
[scope and validation](SIGNAL_CANDIDATES_REVIEW.md) and the
[invented report](../../examples/signal-candidates-review-demo.html).

## Source trails

Signal relationships now includes Source trail starting points, with qualified wording and
module-root filters. Address dossiers offer upstream writer and downstream guard traces.
The report preserves contact polarity and source provenance, separates shared branches
from cycles, and stops at uncertainty or different source contents. See
SIGNAL_DEPENDENCIES_REVIEW.md for bounds and the invented demo.

## Current explicit alarm source view (2026-10-17)

**Alarm source evidence** separates typed declarations, tag-based conditions,
definition templates, messages, stored settings and source gaps. Search or
filter a group, then open a record for its original attributes and parent/child
links. Definition records are not expanded into operating alarms; numeric
settings and shutdown behavior remain unverified. See [scope and validation](ALARM_EVIDENCE_REVIEW.md)
and the [invented report](../../examples/alarm-evidence-review-demo.html).

## Historical conditional-output follow-up (2026-10-15)

Conditional outputs explains incoming conditions for OTE, OTL and OTU records,
including outputs inside branches and unresolved targets. A compact node table
shows ALL/ANY relationships, predicate occurrences, rung entry and explicit
unknown transfers. Node links preserve shared structure without expanding every
path. Guard quality, target identity and normal-scan action remain separate.

Rung and exact-address dossiers link to their outputs. Module declaration kinds
provide source context only. These records do not establish equipment, alarms,
shutdown effects, final values or execution schedules. Review9/manifest12 saves
sixteen artifacts; work24 adds a closed condition summary. The independent demo
contains 120 rungs. Continue automated Phase 1 analysis before team review.
See [scope and validation](CONDITION_REVIEW.md).

## Historical relationship follow-up (2026-10-15)

The Address relationships view separates exact suffixes beneath each root.
Open an address to inspect ordinary reads, writes, stateful uses, unknown roles,
CPT read occurrences and participating rungs. Rung, CPT and PID evidence links
navigate into these dossiers. Missing readers/writers are investigation leads;
implicit, external and non-RLL uses have not been excluded.

Possible local calculation links retain producer, read and write evidence within
eligible series segments. Operand-reuse patterns distinguish reused addresses,
same-root members, constants and CPT structure. Excluded rungs explain the gap;
no equality or link establishes runtime behavior. Review8/manifest11 saves fifteen
artifacts, including relationships.json. Work23 exports only count summaries.
The invented demo now has 92 rungs. Continue automated Phase 1 analysis; no team
engineering review is requested now. See [scope and validation](RELATIONSHIP_REVIEW.md).

## Historical rung-analysis follow-up (2026-10-15)

[Rung analysis](RUNG_ANALYSIS_REVIEW.md) adds the primary Engineering analysis
view: every rung, overlapping candidate families, evidence/gap filters,
ordered blocks and a readable branch outline. Candidates explain their source
links, rules and missing knowledge. Known functions, possible functions and
unclassified/empty rungs remain discoverable. Name/comment clues stay weak;
internal coils do not become physical outputs through naming alone.

This is the first broad interpretation layer, not the completion of Phase 1.
The work-machine returns have been automated results, not human feedback.
Continue the [automated analysis sequence](../planning/PHASE_1_ENGINEERING_ANALYSIS.md)
before team review. Review7/manifest10 saves fourteen hashed artifacts, adding
rung-analysis.json; work22 adds a closed count-only summary. The invented HTML
demo includes normal, ambiguous and deliberately unsupported cases.

## Historical CPT access follow-up (2026-10-15)

[CPT access](CPT_ACCESS_REVIEW.md) adds destination writes and separately counted
expression reads. Tag access includes expression-only roots, repeated reads,
exact source-span/node links and alias backlinks. Unsupported expressions and
unbound references remain explicit gaps. Current commands generate access4;
work21 adds summary4 while review6/manifest9 retains thirteen artifacts.
Returned `cbb2965` confirms the prior 175-instruction access extension with no
new binding gaps. The next run measures CPT integration. Manual engineering
and appearance review remains optional. The invented HTML demo is available.

## Historical extended access follow-up (2026-10-15)

[Extended access](EXTENDED_ACCESS_REVIEW.md) adds counter and message controls,
system-value operands and SFC-reset targets. The report distinguishes original
reference findings from access-owned bindings and adds declaration reverse links
for newly recognized operands. Message payloads, system transfer ranges and
SFC execution remain outside this layer. Returned `760448e` confirms 45/45 CPT
syntax trees and 132/132 reference uses root-bound. Work20 measures the new
access3 coverage; review6/manifest9 still saves thirteen artifacts.
Manual engineering and appearance review remains optional.

## Historical calculation function follow-up (2026-10-15)

The [function extension](CALCULATION_FUNCTION_REVIEW.md) adds documented older
CPT spellings and a Function coverage panel. Counts include fully parsed
expressions only; unsupported-function counts describe the first rejection.
Returned `6d19d5e` confirms 43/45 expressions parsed with 122 bound reference
occurrences; two unidentified unsupported functions remain. Review6/manifest9
still saves thirteen artifacts, now with calculation2; work19 adds summary2.
Manual engineering and appearance review remains optional.

## Initial calculation follow-up (2026-10-15)

The [CPT calculation extension](CALCULATION_REVIEW.md) adds expression search,
syntax grouping, source spans and repeated reference occurrences with links to
rungs and declarations. Unsupported expressions keep their exact source and a
fixed gap reason without a partial tree. Review6/manifest9 saves thirteen hashed
artifacts; work18 adds closed count-only calculation feedback. Returned
`564fa66` confirms all PID catalog headers; numeric values remain unvalidated.
Engineering and appearance review remains optional.

## Historical PID member follow-up (2026-10-15)

The [PID member extension](PID_MEMBER_REVIEW.md) adds documented setting groups,
name/type/shape checks and missing/duplicate catalog entries to PID detail.
Review5/manifest8 saves twelve hashed artifacts; work17 adds count-only member
feedback. Returned `28b5d1f` confirms the preceding PID association slice.
Engineering and appearance review remains optional; saved values do not establish
runtime modes or approved settings.

## PID occurrence follow-up (2026-10-15)

The [PID evidence extension](PID_EVIDENCE_REVIEW.md) adds operand-function labels,
PV/PID/CV positions and links to stored representations and member evidence.
At that checkpoint, review4/manifest7 runs have eleven artifacts and work16 count-only
feedback. Returned `a096cae` confirms the preceding stored-data capture; manual
source and appearance review remains optional. No active loop/cascade behavior
or effective configuration is inferred.

## Stored tag data follow-up (2026-10-15)

The [stored tag data extension](TAG_DATA_REVIEW.md) adds searchable saved member
values, representation and element details, and declaration-to-ladder links.
At that checkpoint, runs used review3/manifest6 with ten artifacts and work15 count-only
feedback. Stored data stays private; no effective configuration is inferred.
Returned `122f230` confirms the preceding timer/reset/copy run. Manual source
and appearance review remains optional.

## Timer/reset/copy follow-up (2026-10-15)

The [timer/reset/copy access extension](TIMER_COPY_ACCESS_REVIEW.md) adds timer
initialization labels and coverage counters. Current runs use nested access2
and work14 while keeping review2/manifest5 outer layouts. Returned 7cd9201
confirmed the preceding access1 run. The report remains available for optional
later source and appearance review; no manual inspection blocks parser work.

## Initial access follow-up (2026-10-14)

The returned 1332543 work report confirms the first HTML generation: 439 selected
application cases (one skip), 139 helpers and a saved private run from clean
c36d10b. The next slice adds explicit operand reads/writes for 28 instruction
spellings, a searchable Tag access view and visible unknown/unresolved access
queues. Current CLI/work runs use review2, manifest5 with nine artifacts and
public work13; earlier review1/manifest4 contracts remain available.
See [access scope, validation and current next step](ACCESS_ROLE_REVIEW.md).

Tyler has not inspected the source yet. Manual source/engineering/appearance
review is optional and deferred; it is not a gate to further parser work.
Returning the next generated aggregate is sufficient. The review suggestions
below are available when Tyler is ready to explore the source. Actual-unit HTML
remains private; the invented demonstration is safe for interface discussion.

## Purpose and scope

This is the first organized review package following the
[project-state assessment](PROJECT_STATE_REVIEW.md). It brings the existing
snapshot inventory, references, SFC structure, syntax groups and findings into
one private HTML document. The report is a read-only source explorer. Persistent
engineering edits, runtime effects, equipment classifications and PCSD/FHX
generation remain later work. Possible explicit operand roles are now available
as described above. Dedicated routine-call candidate/graph navigation
is also a follow-up; this interface shows routine declarations and source context.

The report is available for eventual navigation, source correspondence, missing
information, bug and appearance review. That review can wait.
There is no need to install Python or run a server just to open the resulting
HTML, although generating it currently uses the existing parser environment.

## Commands and saved output

The ordinary work-machine command now also saves review.html:

```bash
git pull
bash ./run-work-check.sh
```

The script prints `Private review report:` followed by its complete path. Open
that file in a browser. It is inside the new private run under
confidential/workspaces/work-check/. The script still automatically commits only
its validated public feedback JSON locally; review that JSON and run `git push`
manually when ready. It does not open a browser, start a server or contact a
remote Git repository automatically.

To generate a private report directly without running/committing test feedback:

```bash
uv run --project python-parser --locked plc review \
  "confidential/plc-code/A19CHL02-unencrypted.L5X" \
  --workspace "confidential/workspaces/review"
```

The workspace is required. Each invocation saves a new run; existing input and
run files remain intact. Exit3 means a usable report with partial underlying
coverage, not a failed HTML export. All styling, scripts and evidence are embedded
in review.html, so the file can be opened offline without its neighboring files.
**The actual-unit HTML contains private names, values and logic and stays local.**
Its data boundary is different from the small public feedback JSON.

## Optional review when ready

- Overview: source populations, underlying coverage and navigation into records.
- Objects: locate a named source object, inspect its scope/description/attributes
  and follow its recorded operand occurrences back to rungs.
- Ladder: inspect original rung text, comments, instruction operands and binding
  status. The displayed source is not a graphical ladder simulator.
- SFC: distinguish routine/content edit versions; inspect steps, conditions,
  opaque ST, authored notes, flow links and separate annotation attachments.
- Patterns: inspect groups of exact ordered opcode/arity/branch shapes and their
  rung occurrences. Matching shapes omit operands and do not prove equivalent
  behavior or the same engineering role.
- Findings: follow source, reference and SFC gaps to the available evidence;
  source diagnostics without IDs retain their XML locator.
- Tag access: inspect possible reads, writes, stored state and unknown roles;
  follow each occurrence or binding gap to its exact operand and rung. Shared
  roots do not prove member overlap or execution dependencies.

When familiar with the source, a first local review can use a tag, a repeated rung pattern and
one SFC note. Verify their names/context, links and findings against your source.
Check whether search, filtering, pagination and Back let you investigate without
losing your place. Note unreadable text, clipped controls, awkward column widths
and any missing context. Record desired interpretation fixes separately from
layout/navigation bugs; this version does not persist edited classifications.
Describe issues or share approved bounded examples instead of sending the full
private HTML. The independently invented demo can be used freely for appearance
feedback.

Open [the invented demonstration](../../examples/engineering-review-demo.html)
locally in a browser to review the layout immediately. It is generated solely
from the synthetic fixture below; its private badge demonstrates how real
reports are labeled. The full HTML from a real unit must remain on the work PC.

## Original review1 contracts (retained)

Private review schema1 / engineering-review-1 contains the captured snapshot
identity, original inventory/reference/SFC payloads, syntax pattern occurrences,
findings and statistics. It has no stable engineering-object identity or accepted
correction overlay. Canonical replay validates supplied evidence against the same
immutable bytes; it does not reread the live input. Compact JSON is limited to
64MiB, findings to 500,000 and pattern groups to 100,000. HTML has its own 80MiB
limit. Model errors contain no source text.

Pattern IDs and finding IDs are snapshot-scoped. The shape representation keeps
exact opcode spelling, argument count and ordered series/parallel structure;
operand names, values and reuse are excluded deliberately. Parsed unknown
opcodes remain eligible for syntax grouping. Supported literal/non-data/system
flag slots do not become unresolved findings. An informational no-operand record
does not claim a zero-argument instruction is unsupported.

`save_run(..., include_review=True)` requires inventory, references and SFC
evidence. It builds the report before allocating the destination and adds an
eighth artifact to optional manifest4, artifact_kind
source_reference_sfc_review_run. The manifest records review schema/version and
the HTML hash/size. A write failure cannot publish a final manifest. Defaults and
ordinary inventory/reference/SFC commands retain manifests1/2/3 and their exact
artifact layouts.

The first delivery retained public work12/reference12/source4/SFC2. Work13 now
adds access coverage while the other three contracts remain unchanged. The tested revision and
private-run success identify report-capable runs; HTML contents, source IDs and
individual findings are not added to public feedback. Earlier stored reports
remain readable. The existing listener stays disabled and excluded from tracking.

## Browser boundary

The report uses embedded assets and fixed application code. Source values are
JSON-escaped at the HTML boundary and displayed as text rather than interpreted
as markup. A hash-based Content Security Policy disallows external network
content and connections. Lists are paginated, source identifiers are retained
for drill-down, and display previews must not discard the original evidence.
No active content is generated from an authored source note.

To bound memory, ancestor-path previews/search cover at most eight ancestor
segments and 80 characters per segment. Full object names and attributes remain
available in their own records. A descendant search can miss a very long
ancestor-name suffix outside that preview; search the ancestor object directly.

## Demonstration source

[engineering_review_demo.L5X](../../fixtures/synthetic/engineering_review_demo.L5X)
is independently invented for this interface. It contains 12 rungs, ordinary and
unresolved references, repeated shapes, a PID signature and CPT expression, and
two SFC content versions with direct/child notes and a deliberately unresolved
attachment. It is not controller-ready logic or a reference process design.
The existing canonical synthetic fixture remains unchanged.

## Original review1 development validation

- Full tracked application/development suite: 535 cases pass, with one existing
  Windows symlink-capability skip; the ignored listener loader is excluded.
- The final label polish also passes all seven HTML tests and JavaScript syntax
  validation. Independent model/UI/workflow review has no remaining blockers.
- Two actual work-runner invocations in a fresh temporary checkout, first with
  an explicit invented input and then its remembered path: 439 selected
  application cases (one skip) and 139 helper tests pass on each run.
- Those invocations produce manifest4 with eight correctly hashed artifacts.
  Standalone plc review returns a usable partial exit3, prints the path and
  produces byte-identical HTML. Ordinary reference and SFC commands retain
  their manifest2 and manifest3 layouts. Inputs and earlier runs are unchanged.
- Report-only local commits have the tested revision as parent and leave clean
  trees. No Git fetch, pull or push occurs. The embedded HTML evidence matches
  the saved JSON. Baseline 9cd65a4 inventory, references, SFC and public summaries
  remain exact after normalizing the standard revision field.
- All 18 historical public work reports validate unchanged. The built wheel
  contains exact copies of both embedded report assets; its extracted renderer
  generates byte-identical demonstration HTML.

Chrome browser checks over a temporary loopback server confirm object-search
results and occurrence links, correct rung/operand focus after navigation,
separate SFC edit versions and empty sections, syntax-pattern and finding
drill-down, empty search results, and the final overview layout. A source comment
containing a script-closing tag, image markup and event-handler text remains
literal text with no image, dialog or page JavaScript error.

A separate independently generated scale fixture has 4,606 rungs, 6,417 objects,
23,030 operands, 14 SFC routines and 280 attachments. Its HTML is about 35.6MB;
snapshot analysis plus report generation took about 10.8 seconds on this PC.
The browser opens it and successfully searches the final rung, pages through
50-row results and returns from a detail to page2 of93. This is a synthetic scale
check, not a measurement of the real export or the work machine.

Direct file:// navigation is blocked by the browser automation URL policy, so
browser QA used loopback HTTP. The generated HTML has no external resource or
network dependency, but opening the file directly under work-PC browser policy
and real-export visual usability remain unverified. They can be checked when
Tyler is ready and do not block continued parser work. Current access validation
is recorded in the follow-up linked above.
