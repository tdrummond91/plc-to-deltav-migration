# Phase 1 application map and L5X re-audit

Updated 2026-10-23. This record describes the read-only application projection;
it does not replace the earlier parsing evidence or approve a DeltaV design.

## Start here

After a manual pull on `feat/engineering-workspace-pc`, stop the running
workspace and reopen it with `bash ./open-workbench.sh`. Choose **Application
map** on Home or in Page. Existing imported analysis can supply this view;
there is no new database migration or required translation pass.

1. **Hardware route:** select a module. Check its controller, parent attachment,
   own ports and connection attributes. Open its input/output payload or registers.
2. **Registers & data:** search a tag/member, then inspect its declaration,
   datatype, direction, recorded reads/writes, raw values and exact source uses.
   Follow a parent register to distinguish a payload container from its members.
3. **Coverage:** inspect hardware, declarations/storage, logic/references and
   export/gaps. A readable map does not establish complete logic interpretation.

Application map is read only. Field I/O retains saved DeltaV names and packages;
Rungs and Classification & groups retain editable engineering decisions.
Patterns and Programs & routines remain separate views of the captured logic.

## Implemented evidence boundaries

| Information | What is shown and how it is qualified |
|---|---|
| Controller and hardware hierarchy | Actual enclosing controller name; Local self-parent is a root; child attachment resolves against the parent's port; missing/duplicate parents, ports and cycles remain unresolved. Configured ancestry is not a wiring survey. |
| Ports and connections | Captured attributes, source links, parent port versus own port, connection RPI, sizes, suffixes and ConnectionPath. Sizes remain configuration fields, not channel counts. |
| Declarations and scope | Base/Alias/Produced/Consumed, module input/output/configuration, AOI parameters/local tags, exact scope and unknown declaration kinds. ProduceInfo/ConsumeInfo attributes remain source facts. |
| Storage and containment | Root/member/array/bit records, qualified scalar array inheritance, static in-bounds declaration arrays, UDT member definitions and source provenance. Absent array elements are not manufactured. |
| Conflicts | Repeated member paths and conflicting declaration/captured datatypes stay explicit. No single effective value or datatype is selected from conflicting representations. |
| Access and calculations | Per-use roles and locations, alias versus assignment, exact CPT expression/destination and source/rung links. This is static evidence, not execution order or reaching-definition analysis. |
| Descriptions | Exact member/alias wording takes precedence over explicitly labeled backing/module fallback. Alternatives and conflicts remain inspectable. Rung prose is not copied to every operand. |
| Languages | Original wording remains intact. Existing local translation cache is consulted using full original text, even when a preview is shortened. Browsing does not start translation. |
| Physical classification | Qualified documented layouts remain separate from datatype, direction, access and unknown process meaning. A numeric input candidate is displayed separately from an unresolved physical channel. |
| Raw payloads | Containers and raw members stay visible, including diagnostics and configuration. Multiple data representations do not create duplicate registers. No new generic drive decoder is asserted. |

Module connection RPI uses microseconds; that statement is specific to the
module-connection attribute and is not applied to every attribute named RPI.
ConnectionPath and tag suffixes remain exact captured values. See Rockwell's
[Import/Export Reference Manual](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf),
publication 1756-RM014D, September 2025, module connection tables pp. 89–90.

## Representative-export re-audit

Fourteen public files were downloaded from two manufacturer-owned repositories,
pinned to the following commits. Only the exports were read; no downloaded
code was executed. Vendor files remain in an ignored local audit directory.
The repository tests contain independently invented data.

| Source | Commit | Files / useful variation |
|---|---|---|
| [Rockwell Logix CI/CD examples](https://github.com/RockwellAutomation/ra-logix-cicd/tree/de14d4ac87d5295b2380cce441ed581d1930947f/1-production-files/L5Xs) | `de14d4ac87d5295b2380cce441ed581d1930947f` | DelayedSum_AOI, ExampleForCICD_L85E, WetBulbTemperature: controller and AOI exports, ladder/ST, scalar/structured/default values. |
| [Rockwell version-control fixtures](https://github.com/RockwellAutomation/ra-logix-designer-vcs-custom-tools/tree/923a9675a53637515c8a5088ff7eed41a9b3eb82/e2e_tests/fixtures) | `923a9675a53637515c8a5088ff7eed41a9b3eb82` | Eleven files: minimal controller, HTTP-client dependency variants, direct/indirect AOI dependencies, ST and ST online edits, dependency export options. |

All fourteen pass through source inventory, references, calculations, access,
rung/relationship analysis, authenticated variable/field-I/O indexes and the
application projection without an exception. Each was checked for meaningful
coverage rather than treating construction success as complete interpretation.
The retained local manifest records source URLs, byte counts and SHA-256 hashes.

These files primarily test software/AOI export variations. They are **not** a
representative sample of installed physical I/O or drive profiles. Invented
tests separately cover local/remote module routes, non-default I/O suffixes,
SINT payloads, connection diagnostics, four supported physical member layouts,
aliases, produced/consumed tags, malformed namespaces, conflicts and paging.

The re-audit found and corrected duplicate-member ambiguity, declaration/data
type conflicts, missing declaration-only array/UDT typing, unknown TagType
promotion and timer placeholders being counted as unresolved data references.
Independent UI checks also caught a mismatch between actual provenance fields
and the initial display contract; the UI suite now renders a real backend result.

## Explicit remaining limits

- ST/FBD bodies, online edit semantics and protected regions are retained and
  reported as unsupported/unprocessed where applicable; they are not converted
  into ladder access paths. Visible parameters inside EncodedData are not treated
  as ordinary unprotected declarations. Noncanonical AddOnInstruction wrappers
  in several public fixtures remain unmodeled and appear in inventory coverage.
- Copy ranges and AOI side effects are not expanded into invented per-member
  dataflow. Dynamic indexes and runtime-selected addresses remain unresolved.
  The public DelayedSum AOI also contains `GT`; its access semantics are currently
  unsupported and counted as unknown rather than treated as a known comparison.
- The app map does not decode a general byte payload into process parameters.
  ABB's [FENA manual](https://library.e.abb.com/public/d6a31af1808043ba8ef53980031041ea/EN_FENA01_11_21_UM_E_A4.pdf)
  documents assemblies 101/151 on printed pp. 209–211. Selecting and decoding a
  vendor profile still needs qualified identity/configuration and explicit raw
  containment. Configurable parameter identities, units and scaling are not
  inferred from numeric storage or a similar device name.
- Source comments and exact calculations are exposed for review. Equipment-name
  discrepancies and suspicious scale factors are not automatically reconciled
  or rewritten. No general comment-to-equipment conflict detector is added.
- No database schema, immutable analysis artifact or bounded work-return format
  changed. No automatic pull, push, listener, or external translation was added.

The next work-PC check is an **existing-source walkthrough** of these three tabs.
Use the normal `bash ./run-work-check.sh` only if a fresh analysis is wanted.
Private plant validation remains necessary; public and invented fixtures cannot
approve actual field wiring, process behavior or DeltaV class allocation.

## Validation record

- 770 workspace, project-store and related review tests passed in the broader run.
- 193 focused regression tests passed after the integration fixes; subsequent
  UDT description refinements passed the application backend/API checks.
- An independent review reproduced the ambiguity, type, array, UDT description
  and dimension defects, then verified their fixes with no remaining blockers.
- The final public-export pass opened every projected register detail and checked
  its captured source ID. An existing invented saved signal/package project was
  opened through the new API with its stored review state unchanged.
- Browser checks used invented data: Home/Page order, configured parent route,
  raw register detail, exact CPT uses, source-rung navigation, returning to the
  map, grouped coverage, sticky header and document-width bounds. Screenshot
  capture timed out; visual appearance still needs the work-PC walkthrough.
