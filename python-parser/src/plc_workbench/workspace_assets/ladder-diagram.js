/* Neutral, source-qualified ladder symbols. This is not a controller emulator. */
(() => {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const HEIGHT = 150, ANCHOR = 84, SERIES_GAP = 28, BUS_MARGIN = 30, LEG_GAP = 24;
  const PAD_X = 56, PAD_Y = 22;
  const LIMITS = Object.freeze({ instructions: 160, nodes: 1200, depth: 64, extent: 40000, argumentSlots: 128, text: 131072 });
  const SYMBOLS = Object.freeze({ XIC: "contact", XIO: "negated-contact", OTE: "coil", OTL: "latch-coil", OTU: "unlatch-coil" });
  const html = (tag, text, className = "") => {
    const node = document.createElement(tag); node.className = className;
    if (text !== undefined) node.textContent = String(text); return node;
  };
  const svg = (tag, attrs = {}, text) => {
    const node = document.createElementNS(NS, tag);
    Object.entries(attrs).forEach(([name, value]) => node.setAttribute(name, String(value)));
    if (text !== undefined) node.textContent = String(text); return node;
  };
  const button = (text, callback, className = "") => { const node = html("button", text, className); node.type = "button"; node.addEventListener("click", callback); return node; };
  const shortened = (value, limit) => String(value).length > limit ? String(value).slice(0, limit - 1) + "…" : String(value);
  const instructionText = instruction => `${instruction.opcode}(${instruction.arguments.join(",")})`;
  const kindOf = instruction => SYMBOLS[instruction.opcode.toUpperCase()] && instruction.arguments.length === 1 && instruction.arguments[0].trim() ? SYMBOLS[instruction.opcode.toUpperCase()] : "block";
  const dimensions = compact => compact
    ? { height: 108, anchor: 58, seriesGap: 22, busMargin: 30, legGap: 10, padX: PAD_X, padY: 10, compact: true }
    : { height: HEIGHT, anchor: ANCHOR, seriesGap: SERIES_GAP, busMargin: BUS_MARGIN, legGap: LEG_GAP, padX: PAD_X, padY: PAD_Y, compact: false };
  const inlineArguments = instruction => instruction.arguments.length === 2
    && instruction.arguments.every(argument => argument.trim() && argument.length <= 24)
    && instruction.arguments.join("").length <= 36;

  // Presentation of known operand roles only. These expressions are gated by
  // their incoming path and never evaluate source values or collapse branches.
  function blockPresentation(instruction) {
    const args = instruction.arguments, opcode = instruction.opcode.toUpperCase();
    const valid = count => args.length === count && args.every(value => value.trim());
    const value = (text, limit = 28) => ({kind: 'value', text, limit});
    const operation = text => ({kind: 'operator', text});
    const label = text => ({kind: 'label', text});
    const textOf = part => part.kind === 'value' ? shortened(part.text, part.limit) : part.text;
    const widthOf = row => row.reduce((sum, part) => sum + [...textOf(part)].reduce((width, char) => width + (char.codePointAt(0) > 255 ? 14 : 8), 0), 0);
    const result = (rows, note, mode) => ({rows, note, mode, width: Math.max(250, ...rows.map(row => widthOf(row) + 44))});
    const field = (name, slot) => [label(`${name}: `), value(args[slot])];
    // An operand with expression-like punctuation stays grouped as an opaque
    // source value. In particular, an indexed address is never algebraically split.
    const term = text => /^[A-Za-z_][A-Za-z\d_:.[\]]*$/.test(text) || /^[-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?$/.test(text)
      ? [value(text)] : [operation('('), value(text), operation(')')];
    const assignment = (destination, expression, note = 'Write when incoming path is TRUE') => {
      const head = [value(destination), operation(' ← ')], row = [...head, ...expression];
      return result(widthOf(row) <= 500 ? [row] : [head, expression], note, 'calculation');
    };
    const comparison = {EQU: '=', NEQ: '!=', LES: '<', LEQ: '<=', GRT: '>', GEQ: '>='}[opcode];
    if (comparison && valid(2)) return result([[...term(args[0]), operation(` ${comparison} `), ...term(args[1])]], 'Compare on the incoming path', 'comparison');
    if (['ADD', 'SUB', 'MUL', 'DIV'].includes(opcode) && valid(3))
      return assignment(args[2], [...term(args[0]), operation(` ${{ADD: '+', SUB: '−', MUL: '×', DIV: '/'}[opcode]} `), ...term(args[1])]);
    if (opcode === 'MOV' && valid(2)) return assignment(args[1], [value(args[0])]);
    if (opcode === 'CLR' && valid(1)) return assignment(args[0], [{kind: 'literal', text: '0'}]);
    if (['ABS', 'LN', 'SQR'].includes(opcode) && valid(2))
      return assignment(args[1], [operation(`${{ABS: 'abs', LN: 'ln', SQR: 'sqrt'}[opcode]}(`), value(args[0]), operation(')')]);
    if (opcode === 'CPT' && valid(2)) return assignment(args[0], [value(args[1], 60)], 'Captured expression · when enabled');
    if (['TON', 'TOF', 'RTO', 'CTU', 'CTD'].includes(opcode) && valid(3)) {
      const settings = [...field('Preset', 1), label(' · '), ...field('Accum', 2)];
      return result([field(['CTU', 'CTD'].includes(opcode) ? 'Counter' : 'Timer', 0),
        ...(widthOf(settings) <= 500 ? [settings] : [field('Preset', 1), field('Accum', 2)])], 'Captured operands · not live values', 'state');
    }
    if (opcode === 'ONS' && valid(1)) return result([field('Storage bit', 0)], 'One-shot path on rising condition', 'state');
    if (['OSR', 'OSF'].includes(opcode) && valid(2))
      return result([field('Storage bit', 0), field('Pulse output', 1)], opcode === 'OSR' ? 'Pulse on rising condition' : 'Pulse on falling condition', 'state');
    if (opcode === 'RES' && valid(1)) return result([[operation('Reset '), value(args[0])]], 'Reset selected state fields', 'state');
    if (opcode === 'PID' && valid(7)) return result([
      field('PID structure', 0), field('PV', 1), field('Tieback', 2), field('CV destination', 3),
      field('Master loop', 4), field('Hold input', 5), field('Hold value', 6),
    ], 'Captured parameters · not live control', 'state');
    return null;
  }

  function validate(source, options) {
    if (options.sourceQualified !== true || source?.source_qualified === false)
      throw new Error("The instruction structure has not been verified against this source snapshot.");
    if (source?.parse_status !== "parsed") throw new Error("The complete rung was not parsed successfully.");
    if (typeof source.text !== "string" || !source.structure || !Array.isArray(source.instructions))
      throw new Error("The original text, instruction list or branch structure is incomplete.");
    if (source.instructions.length > LIMITS.instructions)
      throw new Error(`This rung exceeds the ${LIMITS.instructions}-instruction drawing limit.`);
    const byId = new Map(); let textSize = 0;
    source.instructions.forEach(instruction => {
      if (!instruction || typeof instruction.id !== "string" || !instruction.id || byId.has(instruction.id)
          || typeof instruction.opcode !== "string" || !instruction.opcode || !Array.isArray(instruction.arguments)
          || instruction.arguments.some(argument => typeof argument !== "string"))
        throw new Error("A captured instruction is incomplete or has a repeated identifier.");
      if (instruction.arguments.length > LIMITS.argumentSlots)
        throw new Error("An instruction exceeds the drawing's argument-count limit.");
      textSize += instruction.opcode.length + instruction.arguments.reduce((sum, value) => sum + value.length, 0);
      if (textSize > LIMITS.text) throw new Error("The captured instruction labels exceed the drawing's text limit.");
      byId.set(instruction.id, instruction);
    });
    const stack = [{ tree: source.structure, depth: 0 }], seenNodes = new Set(), orderedIds = [];
    const referenced = new Set(); let count = 0;
    while (stack.length) {
      const { tree, depth } = stack.pop();
      if (!tree || typeof tree !== "object" || Array.isArray(tree) || seenNodes.has(tree))
        throw new Error("The captured structure contains an incomplete or repeated path.");
      if (++count > LIMITS.nodes || depth > LIMITS.depth) throw new Error("The rung exceeds the drawing's nesting or structure limit.");
      seenNodes.add(tree);
      if (tree.kind === "instruction") {
        if (!byId.has(tree.instruction_id) || referenced.has(tree.instruction_id))
          throw new Error("The branch structure has a missing or repeated instruction reference.");
        referenced.add(tree.instruction_id); orderedIds.push(tree.instruction_id);
      } else if (tree.kind === "sequence" || tree.kind === "branch") {
        const children = tree.kind === "sequence" ? tree.items : tree.legs;
        if (!Array.isArray(children) || (tree.kind === "branch" && (!children.length || children.some(child => child?.kind !== "sequence"))))
          throw new Error("A sequence or parallel branch has incomplete paths.");
        for (let index = children.length - 1; index >= 0; index--) stack.push({ tree: children[index], depth: depth + 1 });
      } else throw new Error("The captured rung uses an unsupported structure node.");
    }
    if (orderedIds.length !== source.instructions.length || orderedIds.some((id, index) => id !== source.instructions[index].id))
      throw new Error("The branch structure does not preserve the complete captured instruction order.");
    return byId;
  }

  const wire = (x1, y1, x2, y2, kind) => ({ x1, y1, x2, y2, kind });
  const empty = (width, height = HEIGHT) => ({ width, height, cards: [], wires: [], junctions: [], labels: [] });
  function merge(target, child, x, y) {
    child.cards.forEach(card => target.cards.push({ ...card, x: card.x + x, y: card.y + y }));
    child.wires.forEach(line => target.wires.push({ ...line, x1: line.x1 + x, x2: line.x2 + x, y1: line.y1 + y, y2: line.y2 + y }));
    child.junctions.forEach(point => target.junctions.push({ x: point.x + x, y: point.y + y }));
    child.labels.forEach(label => target.labels.push({ ...label, x: label.x + x, y: label.y + y }));
  }
  function layout(tree, byId, size) {
    if (tree.kind === "instruction") {
      const instruction = byId.get(tree.instruction_id), isBlock = kindOf(instruction) === "block";
      const presentation = isBlock ? blockPresentation(instruction) : null;
      const width = presentation?.width || (isBlock ? (size.compact && inlineArguments(instruction)
        ? Math.max(250, (instruction.arguments.join("").length + 10) * 12 + 44) : 250) : 170);
      const height = presentation ? Math.max(size.height, (size.compact ? 72 : 110) + presentation.rows.length * (size.compact ? 18 : 20)) : size.height;
      const result = empty(width, height); result.cards.push({ id: tree.instruction_id, x: 0, y: 0, width, height, presentation }); return result;
    }
    if (tree.kind === "sequence") {
      if (!tree.items.length) {
        const result = empty(120, size.height); result.wires.push(wire(0, size.anchor, 120, size.anchor, "bypass"));
        result.labels.push({ x: 60, y: size.anchor - 12, text: "Empty bypass", kind: "bypass" }); return result;
      }
      const children = tree.items.map(child => layout(child, byId, size));
      const result = empty(children.reduce((sum, child) => sum + child.width, 0) + size.seriesGap * (children.length - 1), Math.max(...children.map(child => child.height)));
      let x = 0;
      children.forEach((child, index) => {
        merge(result, child, x, 0); x += child.width;
        if (index < children.length - 1) { result.wires.push(wire(x, size.anchor, x + size.seriesGap, size.anchor, "series")); x += size.seriesGap; }
      }); return result;
    }
    const children = tree.legs.map(child => layout(child, byId, size));
    const width = Math.max(...children.map(child => child.width)) + size.busMargin * 2;
    const height = children.reduce((sum, child) => sum + child.height, 0) + size.legGap * (children.length - 1);
    const result = empty(width, height), left = size.busMargin / 2, right = width - size.busMargin / 2;
    let y = 0; const anchors = [];
    children.forEach((child, index) => {
      const anchor = y + size.anchor; anchors.push(anchor); merge(result, child, size.busMargin, y);
      result.wires.push(wire(left, anchor, size.busMargin, anchor, "branch-entry"), wire(size.busMargin + child.width, anchor, right, anchor, "branch-exit"));
      result.junctions.push({ x: left, y: anchor }, { x: right, y: anchor });
      result.labels.push({ x: left, y: y + (size.compact ? 9 : 13), text: `Path ${index + 1}`, kind: "path" }); y += child.height + size.legGap;
    });
    result.wires.push(wire(left, anchors[0], left, anchors[anchors.length - 1], "split"), wire(right, anchors[0], right, anchors[anchors.length - 1], "join"),
      wire(0, size.anchor, left, size.anchor, "branch-inlet"), wire(right, size.anchor, width, size.anchor, "branch-outlet"));
    return result;
  }

  function originalSource(source) {
    const details = html("details", undefined, "ladder-diagram-original");
    details.append(html("summary", "Original rung text (complete)"), html("pre", typeof source?.text === "string" ? source.text : "Original source text unavailable.")); return details;
  }
  function fallback(source, reason) {
    const root = html("section", undefined, "ladder-diagram-fallback"); root.setAttribute("role", "note");
    root.append(html("p", `${reason} The complete original text is shown instead; no partial ladder is drawn.`));
    const original = originalSource(source); original.open = true; root.append(original); return root;
  }
  function symbol(card, instruction, position, size, colors) {
    const kind = kindOf(instruction), x = card.width / 2, y = size.anchor;
    const group = svg("g", { class: "ladder-diagram-instruction", transform: `translate(${card.x} ${card.y})`, "data-instruction-id": instruction.id,
      "data-source-position": position, "data-symbol": kind, "data-width": card.width, "data-height": card.height,
      role: "button", tabindex: "0", "aria-label": `Instruction ${position}: ${instructionText(instruction)}. Open captured arguments and source details.` });
    const summary = window.PLCRungExplanation?.summary?.(instruction);
    group.append(svg("rect", { x: 0, y: 0, width: card.width, height: card.height, rx: 5, class: "ladder-diagram-hit-area" }));
    if (summary) group.setAttribute('aria-description', summary);
    const argumentText = (parent, argument, limit) => {
      if (colors) colors.append(parent, argument, {namespace: NS, tag: 'tspan', limit});
      else parent.append(svg('tspan', {}, limit ? shortened(argument, limit) : argument));
    };
    const line = (x1, y1, x2, y2, cls = "ladder-diagram-symbol-wire") => group.append(svg("line", { x1, y1, x2, y2, class: cls }));
    if (kind === "block") {
      line(0, y, 10, y); line(card.width - 10, y, card.width, y);
      group.append(svg("rect", { x: 10, y: size.compact ? 12 : 29, width: card.width - 20, height: card.height - (size.compact ? 28 : 50), rx: 3, class: "ladder-diagram-block" }),
        svg("text", { x: 22, y: size.compact ? 30 : 49, class: "ladder-diagram-opcode" }, shortened(instruction.opcode, 29)));
      if (card.presentation) {
        group.setAttribute('data-presentation', card.presentation.mode);
        card.presentation.rows.forEach((row, index) => {
          const text = svg('text', {x: 22, y: (size.compact ? 49 : 72) + index * (size.compact ? 18 : 20), class: 'ladder-diagram-expression'});
          row.forEach(part => {
            if (part.kind === 'value') argumentText(text, part.text, part.limit);
            else {
              const span = svg('tspan', {class: part.kind === 'label' ? 'ladder-diagram-slot' : 'ladder-diagram-operation'}, part.text);
              if (part.kind !== 'label') colors?.paint(span, part.text, part.kind);
              text.append(span);
            }
          });
          group.append(text);
        });
        group.append(svg('text', {x: 22, y: card.height - (size.compact ? 23 : 35), class: 'ladder-diagram-small'}, card.presentation.note));
      } else if (size.compact && inlineArguments(instruction)) {
        const text = svg("text", { x: 22, y: 58, class: "ladder-diagram-argument ladder-diagram-arguments-inline" });
        instruction.arguments.forEach((argument, index) => {
          text.append(svg('tspan', {class:'ladder-diagram-slot'}, `${index ? ' · ' : ''}${index + 1}: `));
          argumentText(text, argument);
        });
        group.append(text);
      } else instruction.arguments.slice(0, 2).forEach((argument, index) => {
        const text = svg("text", { x: 22, y: (size.compact ? 49 : 72) + index * (size.compact ? 18 : 20), class: "ladder-diagram-argument" });
        text.append(svg('tspan', {class:'ladder-diagram-slot'}, `${index + 1}: `));
        argumentText(text, argument || '(empty argument)', 29); group.append(text);
      });
      const note = instruction.arguments.length > 2 ? `+ ${instruction.arguments.length - 2} more arguments; select to read` : instruction.arguments.length === 0 ? "No captured arguments" : "Select for complete arguments";
      if (!card.presentation && (!size.compact || !inlineArguments(instruction))) group.append(svg("text", { x: 22, y: size.compact ? 85 : 115, class: "ladder-diagram-small" }, note));
    } else {
      const argument = instruction.arguments[0];
      const operand = svg("text", { x, y: size.compact ? 22 : 29, "text-anchor": "middle", class: "ladder-diagram-operand" });
      argumentText(operand, argument, 22); group.append(operand);
      if (argument.length > 22) group.append(svg("text", { x, y: size.compact ? 35 : 45, "text-anchor": "middle", class: "ladder-diagram-small" }, "Select for complete address"));
      if (kind === "contact" || kind === "negated-contact") {
        line(0, y, x - 12, y); line(x + 12, y, card.width, y);
        line(x - 12, y - 17, x - 12, y + 17, "ladder-diagram-contact"); line(x + 12, y - 17, x + 12, y + 17, "ladder-diagram-contact");
        if (kind === "negated-contact") line(x - 20, y + 21, x + 20, y - 21, "ladder-diagram-negation");
      } else {
        line(0, y, x - 22, y); line(x + 22, y, card.width, y);
        group.append(svg("path", { d: `M ${x - 7} ${y - 18} C ${x - 27} ${y - 12} ${x - 27} ${y + 12} ${x - 7} ${y + 18}`, class: "ladder-diagram-coil" }),
          svg("path", { d: `M ${x + 7} ${y - 18} C ${x + 27} ${y - 12} ${x + 27} ${y + 12} ${x + 7} ${y + 18}`, class: "ladder-diagram-coil" }));
        if (kind !== "coil") group.append(svg("text", { x, y: y + 5, "text-anchor": "middle", class: "ladder-diagram-coil-letter" }, kind === "latch-coil" ? "L" : "U"));
      }
      group.append(svg("text", { x, y: size.compact ? 94 : 120, "text-anchor": "middle", class: "ladder-diagram-opcode" }, instruction.opcode));
    }
    if (!size.compact) group.append(svg("text", { x: card.width - 10, y: card.height - 6, "text-anchor": "end", class: "ladder-diagram-source-order" }, `#${position}`)); return group;
  }

  function draw(source, byId, plan, options, size) {
    const colors = window.PLCSourceColors?.create(source.instructions);
    const root = html("section", undefined, `ladder-diagram${size.compact ? " is-compact" : ""}`); root.setAttribute("aria-label", "Source ladder drawing");
    if (!size.compact) root.append(html("p", `${plan.cards.length} captured instructions · all captured paths · neutral symbols, no live states`, "ladder-diagram-guide"));
    const controls = html("div", undefined, "ladder-diagram-controls");
    const viewport = html("div", undefined, "ladder-diagram-viewport"); viewport.tabIndex = 0;
    viewport.setAttribute("role", "region"); viewport.setAttribute("aria-label", "Ladder drawing. Scroll horizontally or vertically; use Zoom or Fit width to change scale.");
    const width = plan.width + size.padX * 2, height = plan.height + size.padY * 2;
    const canvas = svg("svg", { width, height, viewBox: `0 0 ${width} ${height}`, class: "ladder-diagram-canvas", role: "group", "aria-label": "Captured series and parallel paths" });
    const world = svg("g", { transform: `translate(${size.padX} ${size.padY})` });
    const lines = [wire(-30, size.anchor, 0, size.anchor, "rung-entry"), ...plan.wires, wire(plan.width, size.anchor, plan.width + 30, size.anchor, "rung-exit")];
    lines.forEach(line => world.append(svg("path", { d: `M ${line.x1} ${line.y1} L ${line.x2} ${line.y2}`, class: "ladder-diagram-wire", "data-wire": line.kind })));
    [-30, plan.width + 30].forEach(x => world.append(svg("line", { x1: x, x2: x, y1: 12, y2: plan.height - 8, class: "ladder-diagram-rail" })));
    plan.junctions.forEach(point => world.append(svg("circle", { cx: point.x, cy: point.y, r: 3, class: "ladder-diagram-junction" })));
    plan.labels.forEach(label => world.append(svg("text", { x: label.x, y: label.y, class: `ladder-diagram-path-label ${label.kind}`, "text-anchor": label.kind === "bypass" ? "middle" : "start" }, label.text)));
    const detail = html("section", undefined, "ladder-diagram-selected"); detail.hidden = true; detail.setAttribute("aria-label", "Selected instruction arguments");
    const error = html("p", undefined, "ladder-diagram-error"); error.hidden = true; error.setAttribute("role", "alert");
    const nodes = new Map(); let selectionRequest = 0;
    async function inspect(instruction) {
      const request = ++selectionRequest; error.hidden = true;
      try {
        const accepted = options.onInstruction ? await options.onInstruction(instruction) : true;
        if (accepted === false || request !== selectionRequest) return;
        nodes.forEach((node, id) => { node.setAttribute("class", `ladder-diagram-instruction${id === instruction.id ? " is-selected" : ""}`); node.setAttribute("aria-pressed", String(id === instruction.id)); });
        detail.hidden = false; detail.replaceChildren(html("h4", instruction.opcode));
        const summary = window.PLCRungExplanation?.summary?.(instruction);
        if (summary) detail.append(html('p', summary));
        detail.append(html("p", "Captured arguments in source order:"));
        const argumentsList = html("ol"); instruction.arguments.forEach(argument => {
          const row = html("li"), code = html("code");
          if (colors) colors.append(code, argument || '(empty argument)'); else code.textContent = argument || '(empty argument)';
          row.append(code); argumentsList.append(row);
        });
        detail.append(instruction.arguments.length ? argumentsList : html("p", "No captured arguments."));
        if (kindOf(instruction) === "block" && !blockPresentation(instruction)) detail.append(html("p", "Generic block presentation preserves the opcode and arguments. It does not infer the block's effects or rewrite an invalid operand count."));
      } catch (cause) {
        if (request !== selectionRequest) return; error.hidden = false;
        error.replaceChildren(html("span", cause?.message || String(cause)), button("Retry instruction", () => inspect(instruction)));
      }
    }
    const positions = new Map(source.instructions.map((instruction, index) => [instruction.id, index + 1]));
    plan.cards.forEach(card => {
      const instruction = byId.get(card.id), node = symbol(card, instruction, positions.get(card.id), size, colors);
      node.setAttribute("aria-pressed", "false"); node.addEventListener("click", () => inspect(instruction));
      node.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); inspect(instruction); } });
      window.PLCInstructionHelp?.attach?.(node, instruction, options.helpContext);
      nodes.set(card.id, node); world.append(node);
    });
    canvas.append(world); viewport.append(canvas);
    const baseZoom = size.compact ? 0.85 : 1;
    const zoomLabel = html("output", `${baseZoom * 100}%`, "ladder-diagram-zoom"); zoomLabel.setAttribute("aria-live", "polite");
    let zoom = baseZoom;
    const zoomOut = button("Zoom out", () => updateZoom(zoom - 0.15));
    const zoomIn = button("Zoom in", () => updateZoom(zoom + 0.15));
    function updateZoom(value) {
      zoom = Math.max(0.005, Math.min(2, value));
      canvas.setAttribute("width", width * zoom); canvas.setAttribute("height", height * zoom);
      canvas.style.width = `${width * zoom}px`; canvas.style.height = `${height * zoom}px`;
      zoomLabel.textContent = `${zoom < 0.1 ? Math.round(zoom * 1000) / 10 : Math.round(zoom * 100)}%`; zoomOut.disabled = zoom <= 0.005; zoomIn.disabled = zoom >= 2;
    }
    controls.append(zoomOut, zoomLabel, zoomIn, button("Reset zoom", () => updateZoom(baseZoom)), button("Fit width", () => updateZoom(((viewport.clientWidth || 900) - 20) / width)));
    viewport.addEventListener("keydown", event => {
      if (event.target !== viewport) return;
      if (event.key === "+" || event.key === "=") { event.preventDefault(); updateZoom(zoom + 0.15); }
      else if (event.key === "-") { event.preventDefault(); updateZoom(zoom - 0.15); }
      else if (event.key === "0") { event.preventDefault(); updateZoom(baseZoom); }
    });
    if (options.controlsTarget) options.controlsTarget.append(controls); else root.append(controls);
    root.append(viewport, error, detail, originalSource(source)); updateZoom(baseZoom); return root;
  }

  function render(source, options = {}) {
    try {
      const size = dimensions(options.compact === true), byId = validate(source, options), plan = layout(source.structure, byId, size);
      if (plan.width > LIMITS.extent || plan.height > LIMITS.extent) throw new Error("The complete rung exceeds the available drawing extent.");
      return draw(source, byId, plan, options, size);
    } catch (cause) { return fallback(source, cause instanceof Error ? cause.message : "The rung could not be drawn safely."); }
  }
  window.PLCLadderDiagram = Object.freeze({ render });
})();
