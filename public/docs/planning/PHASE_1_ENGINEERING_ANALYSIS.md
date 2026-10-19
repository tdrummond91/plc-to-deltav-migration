# Phase 1: automated engineering understanding before team review

Confirmed by Tyler on 2026-10-15: the work-machine pushes so far contain
**automated run results**, not engineering feedback or approved classifications.
Continue improving the analysis until the script has extracted and explained
everything it can establish from the available export. Team review follows that
work; it is not a prerequisite for each parser extension.

## What the reports must explain

Every exported rung must be accounted for, including unparsed rungs, and every
captured block must either have an explained role or an explicit unknown.
Reports must organize patterns, loops/PIDs, alarms, digital outputs, sensors,
I/O, calculations, equipment and miscellaneous logic into useful groups.
They must expose comments, missing identifiers, unclear connections, possible
dead ends and the distinction between single and multiple structural paths.

Rung purpose and engineering object identity require more than an opcode count.
Show the evidence supporting each proposed function, its inputs and outputs,
related rungs, and the remaining uncertainty. A rung can serve several purposes;
do not force it into one mutually exclusive equipment or function category.
Uncertain records belong in higher-level groups such as possible PID support,
possible alarm-related logic or output logic with an unresolved destination.
They must remain discoverable beside the better-understood examples.

Readable reports and reusable machine-readable records are parallel outputs.
Human classifications later become a separate correction layer. Generated
proposals, source evidence and approved decisions must remain distinguishable.

## Evidence levels

| Level | Meaning | Example |
|---|---|---|
| Source fact | Directly retained source, declaration or documented instruction identity | A PID instruction and its seven captured arguments; a module output declaration |
| Supported analysis | A bounded rule explains the captured structure and references | Series conditions leading to one supported Boolean write |
| Candidate interpretation | Evidence suggests a purpose but does not establish it | PID structure references without a PID instruction in that rung |
| Authored hint | A name or comment supplies a weak clue | A valve, pump or alarm word without enough supporting behavior |
| Unresolved | The script lacks a needed rule, source content or distinguishable relationship | Unknown block, indirect address or missing declaration |

No percentage confidence should imply statistical calibration that does not
exist. Every candidate needs a rule/version, evidence links and an explanation.
Recognizing a block family does not validate every argument, runtime effect or
engineering purpose. A root binding does not validate its member or channel.

## Development sequence

1. **Rung dossiers and initial candidates.** Account for every rung/block,
   distinguish series/branched/empty/unparsed structure, retain structural
   endpoints and empty bypasses, explain supported functions and expose unknowns.
   Group source comments and identifier gaps beside their candidate context.
2. **Relationships and stronger patterns.** Distinguish operand reuse from mere
   opcode shape; follow exact member/index references, local calculation chains,
   conditional outputs and I/O-backed endpoints. Keep unknown effects visible.
3. **Loops, equipment and interfaces.** Assemble candidate objects spanning
   rungs: PV/SP/CV relationships, selectors, master/slave evidence, sensors,
   valves/pumps, commands/feedback and communication references. Extend source
   capture when required evidence is present but not yet extracted.
4. **Alarms, sequences and incomplete paths.** Trace triggers, resets, delays,
   effects and ranking evidence; investigate consumers/writers/callers and
   candidate dead ends. Account for relevant SFC/ST bodies, AOIs and external
   definitions rather than treating an RLL-only result as whole-unit coverage.
5. **Consolidation before team review.** Resolve remaining script-addressable
   gaps, check group consistency and report readability, and consolidate the
   residual questions that require information outside the available source.

These are coherent development bundles, not one work-machine run per bullet or
per opcode. Continue locally while useful work is possible. Request a normal
work-machine run when new private-source evidence is necessary to validate the
bundle or choose the next analysis rule. Do not require manual source reading
or team feedback at those automated validation boundaries.

The first rung-analysis implementation is the start of this sequence. It is not
completion of Phase 1, even if every rung receives a family label.

## Completion gate for presenting the report

- Every relevant source region, rung and block is accounted for; omitted,
  protected or unsupported content is explicitly located.
- Pattern and candidate groups are meaningful, traceable and readable; source
  facts, inferred purposes and authored hints remain distinguishable.
- Available-source questions that the script can resolve have been investigated,
  including relationships across rungs and relevant non-RLL code.
- Residual unknowns explain the competing interpretations, work already done and
  information still missing. A missing implementation is not mislabeled as a
  question only an engineer can answer.
- Reports are tested for counting, navigation, grouping and representative large
  inputs. Automated tests establish implementation behavior; they do not stand
  in for the team's eventual engineering confirmation.

Then Tyler can present the reports to the other team. Corrections should identify
whether a reusable rule is wrong, an individual object needs an exception, or a
target-design choice is being made. Source changes and split/merged groupings
must be reconciled instead of silently reusing snapshot-bound identities.

## Structural and semantic boundaries

A single ladder path is a structural observation. An instruction may still be
conditional, change state or transfer control. A visible write identifies a
possible destination, not a guarantee of execution or a physical output.
Likewise, no known local result is a useful investigation group, not proof of
dead or unreachable code. Empty branch legs can be valid bypasses.

The existing syntax patterns compare opcode, arity and branch shape. They do not
compare operands, thresholds, aliases or behavior. Preserve that view as evidence
and add stronger relationship-based patterns separately.

Primary references supporting the initial family/structure vocabulary include
Rockwell's [Ladder Diagram programming manual](https://literature.rockwellautomation.com/idc/groups/literature/documents/pm/1756-pm008_-en-p.pdf),
[Output Latch reference](https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/bit-instructions1/output-latch--otl-1.html)
and [Alarm Instructions reference](https://www.rockwellautomation.com/en-ca/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/alarm-instructions.html).
These describe instruction families; they do not establish the purpose of any
particular plant rung.
