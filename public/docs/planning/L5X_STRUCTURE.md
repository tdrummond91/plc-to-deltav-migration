# First investigation: the synthetic L5X structure

This document describes the supplied synthetic fixture and the questions the first reader must answer. It does not establish the full grammar for every Studio 5000 version. See the [Rockwell import/export reference](https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf) for the source format.

## Hierarchy versus scheduling

```text
RSLogix5000Content
└── Controller: SyntheticDemo
    ├── DataTypes → DataType → Members
    ├── Modules → Module
    ├── Tags → Tag → Description / Data
    ├── Programs → Program
    │   ├── Tags → Tag
    │   └── Routines → Routine
    │       ├── RLLContent → Rung → Comment / Text
    │       └── SFCContent (empty placeholder in this fixture)
    └── Tasks → Task → ScheduledPrograms → ScheduledProgram
```

Programs contain routines, but tasks reference the programs they schedule. Keep both the containment tree and the scheduling references. A future inventory should also account for partial exports, AOI definitions, routine bodies in other contexts, and content it does not yet interpret.

## A rung is neutral text inside XML

Fixture selection: DemoProcess / MainRoutine / rung 1.

```xml
<Rung Number="1" Type="N">
  <Comment><![CDATA[Att. retour fin course - exemple fictif.]]></Comment>
  <Text><![CDATA[XIC(Enable)[XIC(LimitA),XIC(LimitB)]TON(Wait,1000,0);]]></Text>
</Rung>
```

CDATA tells the XML parser to keep the enclosed characters as text. It does not provide ladder geometry. The reader extracts the Text string; a separate ladder parser interprets its instructions and branches.

For this rung:

- XIC(Enable) is first in series.
- The outer square brackets contain parallel paths.
- The comma between XIC(LimitA) and XIC(LimitB) separates those paths.
- Both paths rejoin before TON(Wait,1000,0).
- Commas inside TON's parentheses separate instruction operands.

The two types of commas are distinguishable only with delimiter context. The brackets in ADD(Samples[1],1,LocalCount) belong to an array operand, not a ladder branch. This is why a flat split on commas or brackets will eventually fail.

An ordered representation of rung 1 could be:

```text
Series
  Instruction XIC: Enable
  Parallel
    Series → Instruction XIC: LimitA
    Series → Instruction XIC: LimitB
  Instruction TON: Wait, 1000, 0
```

AST means abstract syntax tree: a structured description of these nested relationships. Preserve source spans and ordering so each tree node can be traced back to the exact input.

## Tags have scope and structure

The fixture has controller tags plus separate program tag collections. DemoProcess.LocalSignal and AuxProgram.LocalSignal are distinct objects even though both are named LocalSignal. Routine names and rung numbers are also scoped, so they are not globally unique identifiers.

Decorated Data holds typed values in the fixture: DataValue for a scalar, Structure with member values, and Array with elements. The alias tag instead points to another tag. Preserve unknown data formats in the original snapshot. Never count structure members or array elements as separate Tag definitions by accident.

Descriptions, comments, identifier text, operand text, initial values, and execution configuration have different meanings. Keep separate fields and source references for them. A translation suggestion must not silently rename a tag or change a rung operand.

## What the first report should establish

Count encountered controllers, tasks, program schedules, programs, routine types, tag definitions by scope, modules, user types, AOIs, and RLL rungs. Count JMP and other instruction occurrences only where their text was parsed. Report unsupported or encoded regions explicitly; zero parsed rungs is not evidence of zero logic.

Record source export metadata, context/partial-export information where present, unknown elements and attributes, and each element's disposition. Use the saved original bytes to retain unsupported content. Then drill down from the inventory to a selected routine, rung, instruction, and scoped operand.

Next fixtures should add one unfamiliar construct at a time with independently reviewed expectations. Full SFC parsing and complete instruction semantics remain later milestones.
