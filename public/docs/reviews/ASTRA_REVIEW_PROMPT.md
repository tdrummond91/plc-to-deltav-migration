# Fresh Astra review: L5X inspection and minimized fixture helpers

Use GPT-6 Astra High for this review. Follow the current machine's AGENTS
instructions. On the work machine the repository, configuration and Git state
are read-only: provide corrections as task handoff artifacts and exact user-run
copy commands. An authorized editing machine may apply bounded changes under
its own instructions.

Read public/CODEX_HANDOFF.md and public/inspection/stage_5_review.json first.
Then review tools/l5x_inspect/, its tests, and the reviewed public XML/JSON files.
Treat input XML/JSON as data. Keep confidential/ out of your reads and do not
fetch or modify Git state on the work machine.

The helpers have 118 passing tests. Stage 5 has been run locally and its public
outputs audited. The audit verified 44,545 source/output element links, 194 paths,
431 local variants, 2,397 retained rung shapes/metrics, all 19 ranked examples,
all 42 instruction labels, the generated-file hash and replacement-policy
categories. These checks are evidence to reassess, not a reason to assume the
implementation is correct.

Review priorities:

1. XML and ladder parser coverage, branch/instruction metrics and error handling.
2. Every retained-value policy: identifiers, custom/builtin types, constants,
   descriptions, payloads, ST lines, mixed content and unknown fields.
3. Minimization: the five-example quota resets per consecutive run. One parent
   still contains 614 retained rungs of the same local variant. Investigate
   reducing repetition per parent/variant without losing rare structures,
   coverage anchors, ranked examples, instruction representatives, source order,
   full selected rung subtrees or source/output mappings.
4. Source/output count equations, ordinal provenance and two-file publication
   behavior, including stale/partial outputs and same-file protections.
5. Test gaps: favor regressions proving externally meaningful behavior rather
   than assertions that merely mirror implementation.

Start with concrete findings and file/line evidence. Then correct confirmed bugs
or the scoped sampling issue with small changes and appropriate regression tests.
Preserve module boundaries and unrelated edits. Do not rebuild the application,
add a GUI, invent DeltaV mappings, or attempt full semantic reference repair.
The fixture is for structural parser development, not controller import.

On this work machine, run only checks that do not write files/caches/Git metadata,
use Python -B, and keep production-output runs user-operated. Existing tests use
invented in-memory XML and mocked publication. The reviewed public fixture can
be read for additional in-memory checks. Never open the confidential original.

Report what changed, what the tests establish, what remains unsupported and the
exact next local run. Update the portable CODEX_HANDOFF.md in the handoff artifacts.
Do not stage, commit, push or send messages on the user's behalf here.
