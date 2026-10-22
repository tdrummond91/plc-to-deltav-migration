/* Offline source explanation. No simulation, live state, or equipment inference. */
(() => {
  "use strict";
  const LIMITS = Object.freeze({ instructions: 180, nodes: 1200, depth: 48, argument: 4096, text: 64000 });
  const COMPARE = { EQU: "is equal to", NEQ: "is not equal to", LES: "is less than",
    LEQ: "is less than or equal to", GRT: "is greater than", GEQ: "is greater than or equal to" };
  const STATE = { TON: "On-delay timer", TOF: "Off-delay timer", RTO: "Retentive timer",
    CTU: "Count-up counter", CTD: "Count-down counter", ONS: "One-shot storage",
    OSR: "Rising-edge one-shot", OSF: "Falling-edge one-shot", RES: "Reset stored state" };
  const STATE_ARITY = { TON: 3, TOF: 3, RTO: 3, CTU: 3, CTD: 3, ONS: 1, OSR: 2, OSF: 2, RES: 1 };

  function el(tag, text, className = "") {
    const result = document.createElement(tag);
    result.className = className;
    if (text !== undefined) result.textContent = text;
    return result;
  }
  function original(source, reason) {
    const root = el("section", undefined, "rung-explanation rung-explanation-fallback");
    root.append(el("p", `${reason} Read the complete original text below; no partial explanation is presented.`, "warning-panel"));
    const details = el("details"); details.open = true;
    details.append(el("summary", "Complete original rung text"), el("pre", source?.text ?? "Source text unavailable."));
    root.append(details);
    return root;
  }
  function validate(source, options) {
    if (options.sourceQualified !== true)
      throw new Error("The source association has not been qualified for instruction explanations.");
    if (!Array.isArray(source?.instructions) || !source.structure || (source.parse_status && source.parse_status !== "parsed"))
      throw new Error("Complete parsed instruction and branch structure is unavailable.");
    if (source.instructions.length > LIMITS.instructions)
      throw new Error(`This rung exceeds the ${LIMITS.instructions}-instruction explanation limit.`);
    const byId = new Map(); let textSize = 0;
    source.instructions.forEach(instruction => {
      if (!instruction?.id || byId.has(instruction.id) || typeof instruction.opcode !== "string"
          || !Array.isArray(instruction.arguments) || instruction.arguments.length > 32)
        throw new Error("An instruction record is missing, repeated, or outside the display limits.");
      for (const argument of instruction.arguments) {
        if (typeof argument !== "string" || argument.length > LIMITS.argument)
          throw new Error("An instruction argument is outside the explanation limits.");
        textSize += argument.length;
      }
      if (textSize > LIMITS.text) throw new Error("The rung exceeds the explanation text limit.");
      byId.set(instruction.id, instruction);
    });
    const pending = [{ tree: source.structure, depth: 0 }], seen = new Set(), included = new Set();
    while (pending.length) {
      const { tree, depth } = pending.pop();
      if (!tree || typeof tree !== "object" || seen.has(tree))
        throw new Error("The captured branch structure is incomplete or repeated.");
      seen.add(tree);
      if (seen.size > LIMITS.nodes || depth > LIMITS.depth)
        throw new Error("The rung exceeds the explanation structure or nesting limit.");
      if (tree.kind === "instruction") {
        if (!byId.has(tree.instruction_id) || included.has(tree.instruction_id))
          throw new Error("A branch instruction reference is missing or repeated.");
        included.add(tree.instruction_id);
      } else if (tree.kind === "sequence" || tree.kind === "branch") {
        const children = tree.kind === "sequence" ? tree.items : tree.legs;
        if (!Array.isArray(children) || (tree.kind === "branch" && !children.length))
          throw new Error("A captured path has incomplete children.");
        children.forEach(child => pending.push({ tree: child, depth: depth + 1 }));
      } else throw new Error("An unsupported branch structure is present.");
    }
    if (included.size !== byId.size) throw new Error("Some instructions are absent from the captured paths.");
    return byId;
  }

  function facts(instruction) {
    const opcode = instruction.opcode.toUpperCase(), args = instruction.arguments;
    const valid = count => args.length === count && args.every(arg => arg.trim());
    const condition = text => ({ kind: "condition", label: "Condition", condition: text,
      text: `Test whether ${text}. The path is TRUE only when its incoming condition and this test are both TRUE; otherwise its result is FALSE.`, reads: args.map((_, index) => index), writes: [] });
    const action = (label, text, reads, writes) => ({ kind: "action", label, text, reads, writes });
    if ((opcode === "XIC" || opcode === "XIO") && valid(1))
      return condition(`${args[0]} is ${opcode === "XIC" ? "TRUE" : "FALSE"}`);
    if (COMPARE[opcode] && valid(2)) return condition(`${args[0]} ${COMPARE[opcode]} ${args[1]}`);
    if (opcode === "OTE" && valid(1)) return { ...action("Boolean output", `${args[0]} follows this instruction's incoming path result: TRUE or FALSE.`, [], [0]), output: "follow" };
    if ((opcode === "OTL" || opcode === "OTU") && valid(1))
      return { ...action(opcode === "OTL" ? "Latch Boolean output" : "Unlatch Boolean output",
        `When this path is TRUE, set ${args[0]} to ${opcode === "OTL" ? "TRUE" : "FALSE"}. When this path is FALSE, this instruction leaves the stored bit unchanged.`, [], [0]),
        output: opcode === "OTL" ? "latch" : "unlatch" };
    if (opcode === "MOV" && valid(2)) return action("Move value", `When enabled, copy ${args[0]} into ${args[1]}.`, [0], [1]);
    if (opcode === "CLR" && valid(1)) return action("Clear value", `When enabled, write zero to ${args[0]}.`, [], [0]);
    if (["ADD", "SUB", "MUL", "DIV"].includes(opcode) && valid(3)) {
      const expression = { ADD: `add ${args[0]} and ${args[1]}`, SUB: `subtract ${args[1]} from ${args[0]}`,
        MUL: `multiply ${args[0]} by ${args[1]}`, DIV: `divide ${args[0]} by ${args[1]}` }[opcode];
      return action("Calculate value", `When enabled, ${expression}; write the result to ${args[2]}.`, [0, 1], [2]);
    }
    if (opcode === "CPT" && valid(2))
      return { ...action("Calculate expression", `When enabled, evaluate the captured expression (${args[1]}) and write its result to ${args[0]}.`, [1], [0]), expressionSlot: 1 };
    if (["ABS", "LN", "SQR"].includes(opcode) && valid(2)) {
      const operation = { ABS: "absolute value", LN: "natural logarithm", SQR: "square root" }[opcode];
      return action("Calculate value", `When enabled, take the ${operation} of ${args[0]}; write the result to ${args[1]}.`, [0], [1]);
    }
    if (STATE[opcode] && valid(STATE_ARITY[opcode])) {
      const roles = opcode === "RES" ? { reads: [], writes: [0] }
        : { reads: [0], writes: [0, ...(["OSR", "OSF"].includes(opcode) ? [1] : [])] };
      return { kind: "state", label: STATE[opcode], ...roles,
        text: `${STATE[opcode]} uses stored state ${args[0]}. ${opcode === "RES" ? "Selected state fields can be reset; this is not a whole-object clear." : "Its behavior depends on stored state and execution history."} Timing, count changes, and downstream member values are not evaluated here.` };
    }
    if (opcode === "PID" && valid(7)) return { kind: "state", label: "PID control block", reads: [], writes: [],
      text: "A PID instruction is present with seven captured parameters. Its tuning, mode, control-variable effects, and assignment to DeltaV classes require separate review." };
    return { kind: "unknown", label: "Instruction effects unresolved", reads: [], writes: [],
      text: `The meaning and input/output effects of ${instruction.opcode} are not explained by this view. Keep its arguments and source position for review.` };
  }

  // A pure, bounded instruction tooltip shared by source renderers. It explains
  // this captured instruction only, never upstream paths or live controller state.
  function summary(instruction) {
    if (!instruction || typeof instruction.opcode !== 'string' || !instruction.opcode.trim()
        || instruction.opcode.length > 80 || !Array.isArray(instruction.arguments)
        || instruction.arguments.length > 32 || Array.from(instruction.arguments).some(argument =>
          typeof argument !== 'string' || argument.length > LIMITS.argument)
        || instruction.arguments.reduce((length, argument) => length + argument.length, 0) > LIMITS.text)
      return 'Instruction details unavailable: the captured record is incomplete or exceeds the summary limits.';
    const shortened = instruction.arguments.some(argument => argument.length > 120);
    const captured = {opcode: instruction.opcode, arguments: instruction.arguments.map(argument =>
      !argument.trim() ? '' : argument.length > 120 ? `${argument.slice(0, 117)}...` : argument)};
    const info = facts(captured);
    if (info.kind === 'unknown')
      return `${captured.opcode} · Unknown instruction effects. ${info.text} No input/output roles are inferred.`;
    const pieces = [`${captured.opcode} · ${info.label}. ${info.text}`];
    if (info.reads.length) pieces.push(`Inputs / values: ${info.reads.map(slot => captured.arguments[slot]).join(', ')}.`);
    if (info.writes.length) pieces.push(`Outputs / stored state: ${info.writes.map(slot => captured.arguments[slot]).join(', ')}.`);
    if (shortened) pieces.push('Argument previews shortened; inspect the complete captured arguments.');
    return pieces.join(' ');
  }

  // Preserve parentheses when combining known condition-only paths. Stateful or
  // opaque actions deliberately stop simplification of subsequent conditions.
  function join(parts, operator) {
    if (parts.some(part => part === null)) return null;
    const usable = parts.filter(part => part !== "");
    if (!usable.length) return "";
    const text = usable.length === 1 ? usable[0] : usable.map(part => `(${part})`).join(` ${operator} `);
    return text.length <= 2000 ? text : null;
  }
  function incomingText(condition) {
    return condition === null ? "Incoming result comes from preceding paths or stateful/unsupported instructions; inspect those steps."
      : condition === "" ? "This step receives the rung entry condition when the rung is evaluated."
        : `Incoming condition: ${condition}.`;
  }

  function render(source, options = {}) {
    let byId;
    try { byId = validate(source, options); } catch (error) { return original(source, error.message); }
    const root = el("section", undefined, "rung-explanation");
    root.setAttribute("aria-label", "Plain-language rung explanation");
    root.append(el("p", "Read Inputs, follow the numbered Logic paths, then check Outputs. TRUE means the Boolean value is true; FALSE means it is false. Conditions are local to their path. This describes source instructions when evaluated, without simulating the controller.", "rung-explanation-guide"));
    const inputSection = el("section", undefined, "rung-explanation-inputs"), logicSection = el("section", undefined, "rung-explanation-logic"), outputSection = el("section", undefined, "rung-explanation-outputs");
    inputSection.append(el("h4", "Inputs & constants"));
    logicSection.append(el("h4", "Logic paths — what this rung does"));
    outputSection.append(el("h4", "Outputs & stored state"));
    const inputRows = [], outputRows = [], positions = new Map(source.instructions.map((instruction, index) => [instruction.id, index + 1]));
    const evidence = new Map();
    (options.operands || []).forEach(operand => {
      if (operand && typeof operand.instruction_id === "string" && Number.isInteger(operand.argument_index)) {
        const key = `${operand.instruction_id}:${operand.argument_index}`;
        // Duplicate evidence is ambiguous rather than resolved by insertion order.
        evidence.set(key, evidence.has(key) ? null : operand);
      }
    });
    function operandNote(instruction, slot, description) {
      const captured = evidence.get(`${instruction.id}:${slot}`);
      if (!captured || captured.raw_text !== instruction.arguments[slot]) return `${description}; reference binding unavailable`;
      if (captured.status === "literal") return "Captured constant";
      if (captured.status === "root_bound") return `${description}; declaration root linked, member/type validity not established`;
      return `${description}; ${String(captured.status || "binding unknown").replaceAll("_", " ")}`;
    }
    function walk(tree, path, incoming) {
      if (tree.kind === "sequence") {
        const sequence = el("ol", undefined, "rung-explanation-sequence");
        let current = incoming, pure = true;
        if (!tree.items.length) sequence.append(el("li", "Empty path: passes the incoming condition through unchanged.", "rung-explanation-empty"));
        tree.items.forEach(item => {
          const result = walk(item, path, current);
          const row = el("li"); row.append(result.element); sequence.append(row);
          current = result.condition; pure = pure && result.pure;
        });
        return { element: sequence, condition: current, pure };
      }
      if (tree.kind === "branch") {
        const branch = el("section", undefined, "rung-explanation-branch");
        branch.append(el("strong", "Parallel paths"), el("p", "Each path starts at this split with the same incoming condition. Follow each path separately; actions stay on the path shown. The paths rejoin before the next step."));
        const results = tree.legs.map((leg, index) => {
          const label = `${path} / Path ${index + 1}`, result = walk(leg, label, incoming);
          const panel = el("section", undefined, "rung-explanation-path");
          panel.append(el("h5", label), result.element); branch.append(panel); return result;
        });
        const pure = results.every(result => result.pure);
        // An empty path carries its incoming result and must not disappear from OR.
        const combined = pure && results.some(result => result.condition === "") ? ""
          : pure ? join(results.map(result => result.condition), "OR") : null;
        branch.append(el("p", pure ? "Join: a TRUE result from any of these condition paths satisfies this branch."
          : "Join: actions or unresolved state are present. A single Boolean expression would omit their effects; continue using the separate paths.", "rung-explanation-join"));
        return { element: branch, condition: combined, pure };
      }
      const instruction = byId.get(tree.instruction_id), info = facts(instruction), number = positions.get(instruction.id);
      const step = el("article", undefined, `rung-explanation-step rung-explanation-${info.kind}`);
      step.dataset.instructionId = instruction.id;
      step.append(el("strong", `${number}. ${info.label} · ${instruction.opcode}`), el("p", info.text), el("p", incomingText(incoming), "rung-explanation-condition"));
      if (instruction.opcode.toUpperCase() === "CPT") {
        const occurrence = (options.calculations?.occurrences || []).find(item => item.id === instruction.id);
        step.append(el("p", occurrence?.syntax_status === "parsed"
          ? "Saved expression syntax is parsed. The Equations view shows its grouping; no numeric result is evaluated."
          : "Expression syntax is unavailable or unsupported. Read the captured expression; its internal inputs and operations remain unresolved.", "rung-explanation-condition"));
      }
      const raw = el("details"); raw.append(el("summary", "Captured arguments"), el("pre", `${instruction.opcode}(${instruction.arguments.join(", ")})`)); step.append(raw);
      info.reads.forEach(slot => inputRows.push([instruction.arguments[slot], `${number} · ${path}`,
        operandNote(instruction, slot, info.kind === "state" ? "Stored-state operand" : info.expressionSlot === slot ? "Captured expression; references are not expanded here" : "Input operand")]));
      info.writes.forEach(slot => {
        let effect = info.text;
        if (info.output === "follow" && incoming !== null && incoming !== "")
          effect = `TRUE when the rung-entry condition is TRUE AND (${incoming}); FALSE otherwise, when this instruction is evaluated.`;
        outputRows.push([instruction.arguments[slot], `${number} · ${path}`, effect]);
      });
      return { element: step, condition: info.kind === "condition" ? join([incoming, info.condition], "AND") : null,
        pure: info.kind === "condition" };
    }
    const explanation = walk(source.structure, "Main path", "");
    logicSection.append(explanation.element);
    function table(section, rows, headings, empty) {
      if (!rows.length) { section.append(el("p", empty)); return; }
      const table = el("table"), head = el("thead"), header = el("tr");
      headings.forEach(heading => header.append(el("th", heading))); head.append(header); table.append(head);
      const body = el("tbody"); rows.forEach(values => { const row = el("tr"); values.forEach(value => row.append(el("td", value))); body.append(row); });
      table.append(body); section.append(table);
    }
    table(inputSection, inputRows, ["Captured value / name", "Used at", "Evidence"], "No explicit inputs are identified by the supported rules. Check unresolved blocks and their arguments below.");
    table(outputSection, outputRows, ["Captured destination", "Written at", "Instruction rule"], "No explicit outputs are identified by the supported rules. This does not establish that the rung has no effects.");
    root.append(inputSection, logicSection, outputSection,
      el("p", "Names and comments do not establish alarm purpose, shutdown behavior, priority, physical I/O, or DeltaV class mapping. Stored state, other writers, execution conditions, and unsupported blocks need separate review.", "rung-explanation-boundary"));
    return root;
  }
  window.PLCRungExplanation = Object.freeze({ render, summary });
})();
