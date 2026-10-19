# PID instruction and stored-data evidence

## Confirmed PID return and next companion

Returned `28b5d1f` tests clean `1e9aaae`: 586 application cases (one skip),
139 helpers and a saved private run. Work16 validates; all 46 PID occurrences
link to 46 backing declarations, with 46 Decorated structures and 2,346 direct
member occurrences. There are no PID association gaps. Earlier summaries match
after revision normalization. All 23 stored work1-16 reports validate.
The [member companion](PID_MEMBER_REVIEW.md) is the next slice; no repeat
association-only work-machine run is needed. The original implementation and
validation checkpoint below is preserved.

## Confirmed stored-data return

Commit `a096cae` adds only
[work-check-20261015T110923Z-e950612e.json](../../inspection/work-check-20261015T110923Z-e950612e.json),
testing clean parent `7d0cbb1`. Its work15 report validates and records 546
application cases (one existing Windows symlink skip) and 139 helper cases,
with no failures or errors. The private run was saved, failure_code is null,
and overall status is partial. All 22 historical work1-15 reports validate.
Source/reference, SFC and access summaries match the preceding return exactly
after removing only tool_revision. This is aggregate continuity, not proof of
source byte identity or unchanged private artifact bytes.

| Stored-data population | Returned count |
|---|---:|
| Eligible declarations | 6,567 |
| Declarations with / without direct data | 5,624 / 943 |
| Data / DefaultData envelopes | 11,105 / 12 |
| Decorated / L5K / other envelopes | 5,597 / 5,493 / 27 |
| Descendant elements | 44,527 |
| Opaque / unmodeled elements | 27 / 0 |
| Unsupported-format issues | 5,520 |
| Other issue categories, including duplicates | 0 |

The 27 other envelopes do not establish 27 distinct formats or owners. L5K
cannot be called redundant with Decorated without owner-level overlap and value
comparison. At least 27 data-bearing owners lack a Decorated envelope: 5,597
envelopes cannot cover all 5,624 owners. Their identities and relevance to PID
storage are unknown here. Missing direct data supplies no zero, default or
inherited value. Zero shape gaps does not validate values, types or members.

## Scope of the PID slice

The separate PID companion joins captured ladder occurrences to their existing
operand bindings and stored-data IDs. It retains every ASCII PID spelling,
including malformed signatures. Exact seven-slot, nonempty signatures get
operand-function labels; all slots of an unsupported signature remain unknown.
Occurrence counts are distinct from backing-declaration counts and from a
count of engineered loops.

Rockwell's [PID instruction reference](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/special-instructions/proportional-integral-derivative--pid-.html)
establishes this order: PID structure, process variable, tieback, control
variable, master PID, inhold bit and inhold value. The setpoint belongs to the
stored SP member, rather than the third operand. The
[configuration guidance](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/special-instructions/proportional-integral-derivative--pid-/using-pid-instructions.html)
also identifies separate cascade configuration fields. This slice labels
operand functions but does not infer active cascade behavior from an explicit
master operand or a saved mode value.

Access2 remains unchanged. Its possible read/write classification is a separate
contract; labeling a PID slot does not assign an access role. No process
connectivity, dependency graph, execution timing, numeric conversion, effective
value, validated member address or approved DeltaV setting is produced.

Backing association requires a resolved first operand with an empty expanded
suffix and a captured declaration explicitly typed PID in the source namespace.
Declaration attributes are checked against the original namespace-aware XML.
The traversed alias/declaration and rung/scope paths also reject foreign
namespaces or qualified binding attributes such as Name, TagType and AliasFor.
Legacy root references stay intact; an unsupported binding path withholds PID
structure candidates while retaining navigation.
Any Dimensions attribute on the backing declaration remains an explicit
dimensions gap; the analyzer does
not coerce it into scalar evidence. Alias-to-root works; selecting a nested
member or array element is outside this slice. Gaps retain their operand and
declaration navigation.

All representations of an associated owner stay visible, including opaque
formats. Direct Decorated PID structures supply candidate IDs and direct member
IDs; duplicate candidates and members remain separate. No candidate is chosen
as effective. Missing data, opaque-only data and mixed representations have
separate coverage. Stored values are referenced from tag-data.json, not copied
into PID records. All identities belong to one immutable snapshot.

## Report and workflow

The private report adds **PID evidence** with search and storage-status filters.
Each occurrence links to its rung, operand bindings and source declarations.
The PV/PID/CV arrangement shows instruction positions only. A member table keeps
representation context alongside each saved value, including duplicates.
Object and rung pages link back to their PID occurrences. Existing stored-data
search remains available for member names and values.

The independently invented [PID demonstration](../../fixtures/synthetic/pid_review_demo.L5X)
adds aliases, repeated storage use, alternate/duplicate representations, an
explicit master operand, absent and opaque-only data, a nested-member gap and
a deliberately invalid signature. It is not controller-ready logic. Historical
fixtures remain unchanged. The generated
[HTML demonstration](../../examples/engineering-review-demo.html) uses this input.

Private PID schema1 / pid-evidence-1 and count-only pid-summary1 are companions
to unchanged source3/reference6/SFC2/access2/tag-data1 contracts. Work16 requires
the PID summary beside the existing summaries. Review4/manifest7 adds pid.json
as the eleventh hashed artifact. Legacy work1-15, review1-3 and manifest1-6
contracts remain available. Review4 retains the review3 128 MiB payload / 160
MiB HTML caps; review1/2 retain 64/80 MiB. Validation and rendering finish before
run allocation, and the manifest publishes last.

The public PID summary contains closed counts and fixed metadata, with no PID
names, operands, values or record IDs. The outer work report retains its existing
separate allowance for one approved diagnostic operand sample. The runner commits only its validated feedback
report locally. Git synchronization remains manual; the listener stays disabled.
Private PID evidence and serialized JSON each have a 16 MiB bound. The input
scope is limited to 250,000 total parsed source instructions and 250,000 reference
operands, including non-PID instructions. The public PID summary is capped at 8 KiB;
the complete work report retains its 32 KiB cap. Canonical replay rejects altered
or foreign evidence, and public counters reconcile with source/reference and
Tag Data capacities while allowing repeated occurrences of the same backing data.

## Original work-machine run (now returned)

On `feat/bounded-operand-example-pc`, from the repository root:

```bash
git pull
bash ./run-work-check.sh
git push
```

Only generated feedback is required. Manual engineering/UI review remains
optional and does not gate parser development. Keep actual-unit HTML and all
source-bearing JSON private. Partial status remains expected.

The return will measure the 46 previously captured PID instruction occurrences:
recognized signatures, root/suffix/type gaps, distinct backing owners and
stored-data association. It will not establish 46 independent loops. Those
counts will determine whether targeted format decoding or member selection is
needed before deeper loop interpretation. Existing summaries should stay
unchanged for the same export, except revision metadata.

## Validation

The full development suite passes 682 cases in 76.268 seconds, with one existing
Windows symlink-capability skip. The ignored listener loader was excluded before
import. The 40 PID cases include 28 core/summary and 12 workflow tests. Independent
review reproduced and verified fixes for qualified alias attributes creating
ordinary storage links and for transplanted public PID counts exceeding the
accompanying Tag Data evidence. No outstanding review blockers remain.

Two actual isolated Bash launcher runs, explicit then remembered source, each
pass 586 application cases (one skip) and 139 helpers. Each saves work16/review4/
manifest7, verifies eleven artifact hashes and makes one report-only local
commit. Git traces contain 31 commands per run and no network verbs. Fresh CLI
generation exits 3 and matches all eleven artifacts byte for byte. Canonical
review4/PID1 validates. Nine legacy artifacts, including tag-data.json, match
baseline `a096cae` byte for byte on the same invented input. Reference (including
source), SFC, access and Tag Data summaries match after revision normalization.
All 22 historical reports remain unchanged and valid. Public reports are 25,722
bytes. Source input, previous runs and the real checkout HEAD remain intact.

Chrome checks verify the PV/PID/CV display, the seven operand labels, explicit
master reference, aliases, missing and opaque-only data, suffix gaps and search
filters. A malformed six-slot occurrence has six unclassified slots and no
operand diagram. Three saved SP values across two representations remain
separate; the duplicate 35 value links to its exact third Data representation
and the Back button restores the PID page. Rung and declaration links return to
their PID occurrences. An HTML-like saved value remains inert text, without
script execution. Older review3 opens with stored-data navigation and no PID
section. No page JavaScript errors occurred. The packaged wheel contains the
36 final modules/assets and renders the exact final demonstration bytes.

A separate invented scale input has 6,002 data owners, 48,000 stored-data
elements and 4,606 rungs. Its 60 PID occurrences share 40 backing declarations;
unused PID declarations do not manufacture instruction occurrences. The
3,420,554-byte XML produces 56,316,012-byte HTML in 55.85 seconds, including
canonical replay, summary construction and rendering on this development PC.
Chrome opens it and supports PID search, detail navigation and 50-row paging
(51 DOM rows including the header, then 11 on the final page). This is one
bounded capacity check, not a universal performance guarantee. Actual-unit PID association coverage is now confirmed above; work-PC file
opening remains unverified. All QA browser tabs and
temporary loopback servers have been closed.
