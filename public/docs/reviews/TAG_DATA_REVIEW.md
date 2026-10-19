# Stored tag data evidence

Confirmed return: `a096cae` validates work15 from clean `7d0cbb1`, with 546
application cases (one skip), 139 helpers and a saved private run. All 22
historical work reports validate. Data capture retained 44,527 elements with
zero shape/namespace/duplicate issues; 5,493 L5K and 27 other envelopes remain
uninterpreted. Prior summaries are unchanged after revision normalization.
The next slice is [PID occurrence evidence](PID_EVIDENCE_REVIEW.md); its guide
records the coverage limits and current run instructions. The original
stored-data implementation checkpoint below is preserved.

## Confirmed timer/reset/copy return

Returned commit `122f230` contains only
[work-check-20261015T094840Z-c2673e7a.json](../../inspection/work-check-20261015T094840Z-c2673e7a.json),
testing its clean parent `bdcc101`. All 496 application cases (one existing
Windows symlink skip) and 139 helper cases pass. Work14/access2 validation
passes, the private run was saved, and no analysis failure was reported.

Every conditional timer/reset/copy count predicted in
[the preceding review](TIMER_COPY_ACCESS_REVIEW.md) is confirmed:

| Population | Returned count |
|---|---:|
| Classified instruction roles | 17,526 of 17,874 |
| Unsupported instructions | 348 |
| Unknown operand roles | 931 |
| Classified timer instructions | 434 |
| Timer initialization placeholders | 868 |
| Timer integer initialization fields | 0 |
| Known roles with unusable bindings | 321 |

Reference/source and SFC summaries exactly match `7cd9201` after removing only
tool revision metadata. Root-linked operands remain 20,286 and indexed roots
remain 5,162. All 21 stored work reports validate. Aggregate equality does not
prove source byte identity. The 98.05% figure describes instruction operand
roles, not Phase 1 completion or migration equivalence. Engineering/UI review
remains deferred; this return confirms generation and automated validation.

## Why stored data comes next

All observed timer preset/accumulator pseudo-fields are placeholders. Their
saved backing members are a separate part of the export. The unit also has 46 PID instructions
and 83 module configuration tags. Reading their stored data is useful groundwork
for loop, alarm and I/O interpretation; another small opcode catalogue increment
would not expose those settings.

Rockwell's [Import/Export reference, 1756-RM014D](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf)
describes the Data representations on printed pages 42-46 and AOI DefaultData
on pages 101 and 109. Decorated data represents scalar values, structures and
arrays; it can be absent from an export. The parser captures that evidence
without deciding which representation is effective or validating values.

## Capture contract

The separate `TagDataResult` consumes the immutable snapshot and canonical
inventory. Eligible declarations are tags, AOI parameters/local tags and module
configuration/input/output tags. Each owner is recorded even when it has no
direct Data or DefaultData child. Missing data means absent in this export;
it supplies no zero, default, inherited value or error by itself.

Each direct Data/DefaultData envelope is independent. Attributes and parsed
direct text remain private. Descendant elements are stored once in a flat list
with parent, owner and envelope IDs. Original XML spelling remains in the
snapshot; parsed XML attributes/text are not claimed byte-identical to it.
Element locations can be reconstructed from parent links and sibling ordinals.
No validated runtime member address is manufactured.

Namespace metadata is retained. Data in a namespace different from its document
or owner remains unmodeled, and a namespaced attribute cannot impersonate an
ordinary Format, Name or Value attribute. The shared XML reader gains internal
expanded-name metadata only; inventory and reference contracts do not change.

Known Decorated element shapes are recognized conservatively. Unknown shapes
and unsupported formats retain their evidence and capture issues. String text
is opaque and is not decoded. L5K/Raw/unknown representations are not converted
to equivalent Decorated values. Multiple representations and duplicate members,
array indices or payload roots remain separate; no winner is selected.

Value conversion, numeric/type validation, array bounds, member validity,
configuration approval, live state, initialization effects and effective value
selection are outside this slice. A captured PID member does not establish a
valid loop, cascade relationship, alarm priority or DeltaV setting. Private
records still belong to one source snapshot and are not persistent correction
identities.

## Report and workflow

The private HTML adds **Stored tag data**. Search matches declaration names,
member attributes, saved value spelling and direct text. Open a representation
or member for its complete evidence, then follow the declaration to its ladder
occurrences. Object pages list their data representations and explicitly show
absence. Search indexes individual records; tables paginate rather than
rendering a complete data tree at once. Data-view declaration-name search uses
a bounded preview; full names remain searchable in Objects and visible on the
declaration page. Member context previews are bounded hierarchies, not validated
addresses.

The [invented demonstration](../../examples/engineering-review-demo.html) is
generated from [tag_data_review_demo.L5X](../../fixtures/synthetic/tag_data_review_demo.L5X).
It includes illustrative PID/timer members, arrays, string text, duplicates and
an opaque vendor format. It is not controller-ready logic. The original
engineering_review_demo.L5X fixture remains unchanged.

Current versions are private tag-data1, public tag-data-summary1, review3,
manifest6 and work15. Combined runs have ten artifacts, adding `tag-data.json`.
Source3/reference6/access2/SFC2 and source-summary4/reference-summary12/
access-summary2/SFC-summary2 remain unchanged. Legacy review/storage calls
without tag data retain their prior versions. Historical work1-14 contracts
remain strict.

Public feedback contains closed counts, fixed metadata and revision information.
It includes no stored values, member names, source IDs or data-type histogram.
Owner and XML populations reconcile with existing source evidence. Canonical
replay rejects forged private evidence before report/save/publication. Source
and tag-data evidence limits remain bounded. Legacy review1/2 keep their
64 MiB payload / 80 MiB HTML caps; review3 allows 128 MiB / 160 MiB for the
additional data companion. The larger limits are version-specific and checked
before allocating a saved run. Nothing is silently truncated. The runner makes
only the generated feedback commit locally; pull and push remain manual.

## Next work-machine run

On `feat/bounded-operand-example-pc`, from the repository root:

```bash
git pull
bash ./run-work-check.sh
git push
```

Only generated public feedback is required. No manual source/report review is
needed yet. Keep the actual-unit HTML, tag-data.json and other engineering
artifacts private. Overall partial status remains expected.

The return will establish actual Data/DefaultData format coverage and retained
shape gaps. No unit-level stored-data counts are predicted without evidence.
Existing source/reference/access/SFC counts should remain unchanged for the
same export. These results will guide the next interpretation bundle.

## Validation

The full tracked development suite passes 642 cases with one existing Windows
symlink-capability skip. The ignored listener loader is excluded. Independent
review passes the 30 new core/summary cases, integration and budget-boundary
cases, and 231 small invented format/shape/namespace combinations. Review found
and corrected recognition of multiple structured payloads inside one array
element; such a shape now remains unmodeled. No review blockers remain.

Two actual isolated work-script runs, explicit then remembered source, each
pass 546 application cases (one skip) and 139 helpers. Each makes exactly one
report-only local commit with no Git network commands. All ten artifact hashes,
canonical review3/access2/tag-data1 and fresh CLI output verify. CLI artifacts
are byte-identical to both runs. Eight legacy artifacts, including access.json,
match baseline `122f230` byte for byte. Source/reference/SFC/access summaries
match after removing only tool revision metadata. All 21 historical work1-14
reports validate unchanged. The generated public reports are 22,825 bytes,
below the existing 32 KiB cap. Source input and previous runs remain intact.

Chrome checks on invented inputs verify member/value search, timer PRE value
to declaration to TON rung navigation, alternate representation numbering,
duplicate values and array indices, nested member context, missing data and
opaque HTML-like text remaining inert. Legacy review2 renders with the current
assets without a stored-data section. No page JavaScript errors occurred. The
packaged wheel contains the final modules/assets and renders the exact demo
bytes. Temporary QA tabs and loopback servers are closed.

A separate invented scale fixture has 6,000 tag owners, 42,000 data elements
and 4,606 rungs. Its 3,881,892-byte XML produces 91,482,529-byte HTML in 39.31
seconds including canonical replay, aggregate construction and rendering on
this development PC. Chrome loading, opening Stored tag data and searching
the last tag took about 3.3 seconds through automation. Paging shows only 50
data rows at a time. This fixture exceeded the previous combined report cap,
which motivated the version-specific limits above. These measurements are
one test result, not a universal capacity or timing guarantee; browser memory
can exceed file size. Boundary tests cover exact UTF-8 and escaped/final HTML
limits and failure before run allocation. No real unit data was used. Direct
work-PC file opening and engineering usability remain unverified optional
checks; the next aggregate run is still required.
