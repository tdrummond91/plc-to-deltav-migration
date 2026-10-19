# Explicit alarm source evidence

## Returned evidence

Return `0c1e6d3` tested clean `1462800`: 1,627 application cases passed with
two expected Windows skips, plus 139 helpers. All 51 historical reports validate.
All 23 non-signal summaries and 55 preceding signal coverage fields are unchanged
after revision normalization. The six-example/eight-reserved-unit envelope is
identical; no diagnostic sample was added.

Authored wording produced 1,073 qualified field-to-address associations across
1,072 addresses, linked to 873 output occurrences. The output category counts
are 88 alarm, 790 equipment and 16 sensor; categories overlap. There are 1,072
description rows and one name row, split into 824 root and 249 alias associations.
All 5,064 address scans completed with no truncation or description gaps.
These remain wording associations, not verified equipment or alarm populations.

Total work-check time was 791.508 seconds, up 31.350 seconds (4.12%); application
tests account for 23.840 seconds of the increase. One comparison does not
establish a performance trend. Existing unresolved bindings and condition
limitations remain visible; this return did not resolve them.

There are no ALMA, ALMD or ASO occurrences in the parsed RLL population. That
does not establish the absence of alarms: fourteen SFC routines and one missing
routine body are outside that instruction count, and the previous summaries
did not count explicit tag-based alarm XML. This increment measures that gap.

## Source evidence and interpretation

Alarm evidence1 is a separate companion. It captures exact declared
ALARM_ANALOG/ALARM_DIGITAL types, their stored-data links, tag-based conditions,
datatype/member definition templates, and alarm configuration trees. Source
attributes, messages, language labels, direct text, parent relationships and
locations remain private and retain their original spelling. The summary
contains only closed count fields.

The structural basis is Rockwell's [Logix 5000 Import/Export Reference Manual,
1756-RM014D-EN-P](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf),
September 2025, chapters 6 and 7. The implementation captures these source
forms without applying defaults, interpreting numeric settings, resolving
relative inputs, expanding templates into instances or mapping priorities.
Instruction access signatures and the existing rung and signal analyses are
unchanged. No alarm execution, process trip, shutdown relationship or live
value is inferred.

Declaration, condition, template, configuration and message counts are separate
populations and must not be added into an operating alarm count. A zero result
does not rule out conventional Boolean alarm logic or external HMI definitions.
Known alarm anchors in unfamiliar placements, foreign namespace attributes,
duplicate forms and unsupported descendants retain explicit source gaps.

## Contracts and report

The companion is canonically replayed against its source snapshot, inventory
and tag data. Capture bounds 50,000 retained rows, 100,000 declaration links
and 500,000 scanned XML nodes, with 8 MiB private JSON and an 8 KiB closed
summary cap. Exceeding a bound raises a fixed source-free error; a bounded
failure is never reported as a complete absence. The maximum-width work44
probe is 97,920 bytes, below the unchanged 106,496-byte outer cap. Review26 embeds it alongside unchanged signal3 and file operations1;
manifest29 retains sixteen artifacts. Work44 adds its closed summary. Earlier
schema versions and reusable API defaults retain their prior behavior.

The report adds **Alarm source evidence** with separate filters for declarations,
conditions, templates, messages, stored settings and unresolved source evidence.
Search and fifty-row paging lead to individual records, source declarations,
stored representations and parent/child XML. All source text uses text nodes.
The [invented report](../../examples/alarm-evidence-review-demo.html) exercises
these paths without plant data.

## Verification

Independent review found and closed a work-report entity-count mismatch for
scheduled programs, missing message identities, an omitted HMICommand settings
filter entry and unpaged stored-representation links. Missing/blank language
identities remain source gaps; Message Type is required only in supported
analog, tag-based condition and definition contexts. Digital messages may omit
it. Missing declaration identities quarantine their linked source trees.

All 45 new production cases passed with process and socket creation blocked
before project imports. All 76 development workflow cases passed. Three DOM
cases passed, including filters, fifty-row paging, source/parent navigation,
template separation, empty populations and literal markup-like messages.

Chrome verified declaration paging of 50/12, all 25 source-gap records,
multilingual child messages, settings grouping and unchanged relative/numeric
spellings. Browser errors were empty, and the layout was visually inspected.
The browser check caught whitespace-only XML indentation hiding attribute
previews; the final renderer uses attribute previews in that case, with a new
DOM assertion and fresh CLI regeneration. Raw source text is unchanged. The
browser tab and temporary loopback server were closed.

The invented capacity case contains 4,606 rungs and 5,000 tag declarations,
including 500 detailed analog alarm declarations. It captures 500 containers
and 3,000 elements without gaps, producing 2,832,100 bytes of private JSON and
2,267 bytes of closed summary. Canonical replay and summary validation pass.
The demo contains 62 typed declarations, 68 containers and 469 elements,
including 25 deliberately gapped records; its alarm JSON is 432,188 bytes.
These are size checks, not plant timing predictions.

The isolated actual Bash launcher passed 1,672 application cases (two expected
Windows skips) and 139 helpers. It saved review26/manifest29 with all sixteen
artifact hashes verified, replayed the unchanged six-example/eight-unit
reservation, and made exactly one local report commit with zero Git network
calls. Two fresh saved analyses passed canonical replay; the CLI reproduced
their sixteen artifacts. All fifteen preceding non-review artifact bytes and
all 24 preceding closed summaries match the baseline. Signal3 is unchanged.
All 51 historical work reports remain byte-identical and validate alongside
the new isolated report.

All 234 backend/test files match the full-run snapshot. The later one-line
attribute-preview correction and its DOM assertion were verified separately:
three final alarm DOM cases and eight prior signal/file-operation DOM cases
passed, and a fresh CLI run reproduces the committed invented HTML byte for
byte. Both isolated verification repositories finish clean. No private source
or listener state was read or changed.

## Next work-machine return

Run the ordinary manual pull/check/push sequence. The next return measures
explicit declaration and configuration populations and source gaps. No new
plant example or manual team review is requested. Git transport remains manual
and the listener remains disabled.

This remains Phase 1. After checking these counts, continue with evidence-backed
equipment relationships, remaining source gaps and report consolidation before
requesting engineering feedback or starting editable PCSD delivery.
