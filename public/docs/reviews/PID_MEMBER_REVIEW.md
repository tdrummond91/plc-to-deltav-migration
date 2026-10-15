# PID member evidence and documented setting groups

## Confirmed PID return

Returned commit `28b5d1f` adds only
[work-check-20261015T131431Z-51134c51.json](../../inspection/work-check-20261015T131431Z-51134c51.json),
testing clean `1e9aaae`. Its work16 report validates: 586 application cases
(one existing Windows symlink skip), 139 helpers, no failures or errors, a saved
private run and no failure code. Overall status remains partial. All 23 stored
work1-16 reports validate. Reference/source, SFC, access and Tag Data summaries
equal the preceding return after removing only tool_revision. This establishes
aggregate continuity, not source byte identity.

All 46 PID occurrences have recognized seven-slot signatures and link to 46
distinct backing declarations. Their 322 operands comprise 184 bound roots and
138 literals, with no signature, binding or storage gaps. The report counts 92
representations, 46 Decorated representations, 46 PID structures and 2,346 direct
member occurrences. Every PID occurrence has multiple representations and none
has multiple PID structures. The second representation's format is not identified
by this PID summary. These totals do not establish that every structure contains
the same members, that representations agree, or that there are 46 engineered
control loops. No further PID-association-only run is needed.

## Scope and evidence

The separate PID member companion describes direct stored members in the PID
structures already linked by PID1. It preserves that association layer exactly.
It deduplicates repeated instruction references to the same structure while
keeping different structures and representations separate. Each member points
back to its exact Tag Data element; saved values are not copied or selected.

The catalog uses the names and declared types in Rockwell's
[PID structure reference](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/pid-structure.html):
28 REAL scalar fields, CTL as DINT, 21 BOOL fields and the REAL DATA array.
The report organizes these into readable groups for setpoint, tuning, scaling,
limits, saved signals, mode/status flags and internal storage. These groups are
navigation aids, not DeltaV class assignments. Field names match ASCII case
insensitively, without trimming or Unicode case folding.

Scalar matching checks the captured member shape, declared type and presence of
a nonblank Value attribute. It does not parse or validate the number or flag.
For DATA, only the ArrayMember/REAL header with Dimensions="17" is recognized;
array contents remain unvalidated. Unknown names, qualified semantic attributes,
unsupported shapes, types and dimensions remain explicit gaps. Every linked
structure records catalog names not present and repeated catalog names.
An absent catalog entry is absent evidence, not a default or a declaration that
the source export is invalid. Duplicate records remain individually navigable.

There is no CTL bit unpacking, flag decoding, effective-value selection, numeric
conversion, alarm ranking, shutdown inference or runtime/cascade interpretation.
The official [PID instruction page](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/special-instructions/proportional-integral-derivative--pid-.html)
and structure page disagree on some explanatory details, including CA direction
labels and the minimum tieback spelling. This catalog uses MINTIE from the
structure table and neutral field labels; it does not resolve those disagreements
into bit meanings or percentage mappings. Tuning units depend on configuration
and are not inferred from one saved value.

## Report and contracts

The PID detail view shows member groups, readable labels, captured values,
shape/type status and exact source links with representation context. Missing
and duplicate catalog fields stay visible. Search includes documented member
names and labels. Older review4 reports retain their original raw member view.

Private PID member schema1 is a companion to unchanged PID1, Tag Data1,
access2, reference6, SFC2 and inventory3. Review5 adds pid_members; manifest8
adds pid-members.json as the twelfth hashed artifact. The optional API path
without the companion still produces review4/manifest7. Work17 adds the closed,
count-only pid_member_summary1 and retains prior summary versions. Work1-16,
review1-4 and manifest1-7 keep their contracts. Review5 retains the 128 MiB JSON
and 160 MiB HTML limits. Validation and rendering precede run allocation, with
manifest publication last.

Public member counts describe unique structures and direct members, unlike
PID1's counts repeated per instruction occurrence. Cross-summary checks bound
these populations by both PID1 and Tag Data evidence. Public member summaries
contain no names from the source, IDs, operands or values. The outer report's
separate allowance for one approved diagnostic operand remains unchanged.
The work runner makes a report-only local commit; all Git synchronization stays
manual and the development listener remains disabled.

## Next work-machine run

On `feat/bounded-operand-example-pc`, from the repository root:

```bash
git pull
bash ./run-work-check.sh
git push
```

This run measures documented member coverage and missing, duplicate, type or
shape gaps in the real export. Only generated feedback is required. Manual
engineering and appearance review remains optional; source-bearing reports
stay private. Partial status remains expected. Phase 1 source understanding
continues; editable corrections, PCSD and FHX are still later phases.

## Validation

The full development suite passed 715 cases in 78.860 seconds, with one existing
Windows symlink-capability skip. The ignored listener loader was excluded before
import. Final targeted checks cover 18 core/summary cases and 15 workflow cases.
Independent review reproduced and verified fixes for empty member populations
beside populated PID evidence, impossible catalog-group/DATA counts, and unique
owners exceeding linked occurrences. Repetition bounds now account for the
other represented owners. Canonical shared-owner, distinct-owner and mixed
repetition cases still pass. No review blockers remain.

Two actual isolated Bash launcher runs from the final implementation, explicit
then remembered source, each passed 619 application cases (one skip) and 139
helpers. Each produced work17/review5/manifest8 with twelve verified hashes and
one report-only local commit. Git traces contain 31 commands per run and zero
network verbs. Public reports are 27,543 bytes. Fresh CLI generation exits 3 and
matches all twelve artifacts byte for byte. Ten earlier evidence files, including
pid.json, match baseline `28b5d1f` on the same invented input; the five existing
summaries match after revision normalization. All 23 historical reports remain
unchanged and valid. All 95 runtime, asset and test files in the final isolated
checkout match this checkout. Source input, earlier runs and the real HEAD were
preserved; both temporary checkouts finish clean.

Chrome checks verify complete and incomplete catalogs, expected/stored type
hints, duplicate SP/sp records, missing types, empty values, unknown members and
DATA header gaps. Both mixed-case duplicate members remain visible; opening the
second reaches its DINT/20 source record. Back restores the member group filter.
Searching a documented label finds its occurrence and member. Fifty-row member
paging shows the 51st DATA record; its exact source opens all 17 invented child
records. The three SP records across two Decorated representations remain separate.
Saved script-like text is displayed inertly. Older review4 has its raw member
view without new catalog controls. No page JavaScript errors occurred.

The existing invented scale input has 6,002 tag-data owners, 48,000 data elements
and 4,606 rungs. Sixty PID occurrences share 40 structures: the new companion
correctly records 280 unique members instead of the 420 member occurrences in
PID1. Its 80 deliberately mistyped flags remain type gaps. Full analysis,
canonical replay, summary and rendering took 73.92 seconds on this development
PC; the final presentation is 56,448,757 bytes. Chrome opens it and supports PID
paging (50 then 10 records), search and grouped member detail. This is one
synthetic capacity check, not a performance guarantee or actual-unit validation.
The final presentation-only line break was rerendered without changing embedded
evidence. The independently invented [member demo](../../fixtures/synthetic/pid_member_review_demo.L5X)
and [HTML demo](../../examples/engineering-review-demo.html) include the full
catalog and deliberate gaps; older fixture bytes remain unchanged.

The wheel build passed; all 38 packaged modules/assets match final source
bytes. The extracted wheel renderer produces the exact final HTML demonstration.
All QA browser tabs and temporary loopback servers were closed. Actual-unit member coverage and work-PC file opening
remain to be checked; manual engineering/UI review remains optional.
