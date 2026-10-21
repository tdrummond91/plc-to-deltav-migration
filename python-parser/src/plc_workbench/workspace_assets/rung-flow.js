/* Source-position diagrams. Wires describe ladder structure, not live power flow. */
(() => {
  "use strict";

  const SVG = "http://www.w3.org/2000/svg";
  const CARD_WIDTH = 330;
  const CARD_HEIGHT = 186;
  const SERIES_GAP = 50;
  const BUS_MARGIN = 48;
  const LEG_GAP = 30;
  const LEG_LABEL_HEIGHT = 26;
  const PADDING_X = 78;
  const PADDING_Y = 48;
  const LIMITS = Object.freeze({ depth: 128, nodes: 1200, instructions: 180, extent: 50000 });

  function element(tag, className, text) {
    const result = document.createElement(tag);
    if (className) result.className = className;
    if (text !== undefined) result.textContent = text;
    return result;
  }

  function svgElement(tag, attributes = {}) {
    const result = document.createElementNS(SVG, tag);
    Object.entries(attributes).forEach(([key, value]) => result.setAttribute(key, String(value)));
    return result;
  }

  function wire(x1, y1, x2, y2, kind) {
    return { x1, y1, x2, y2, kind };
  }

  function emptyLayout(width, height) {
    return { width, height, cards: [], wires: [], labels: [], junctions: [] };
  }

  function translate(target, child, x, y) {
    child.cards.forEach((card) => target.cards.push({ ...card, x: card.x + x, y: card.y + y }));
    child.wires.forEach((line) => target.wires.push({
      ...line, x1: line.x1 + x, y1: line.y1 + y, x2: line.x2 + x, y2: line.y2 + y,
    }));
    child.labels.forEach((label) => target.labels.push({ ...label, x: label.x + x, y: label.y + y }));
    child.junctions.forEach((point) => target.junctions.push({ x: point.x + x, y: point.y + y }));
  }

  function validate(source) {
    if (!source?.structure || !Array.isArray(source.instructions))
      throw new Error("Complete instruction and branch structure is unavailable.");
    if (source.instructions.length > LIMITS.instructions)
      throw new Error(`This rung exceeds the ${LIMITS.instructions}-instruction diagram limit.`);
    const byId = new Map();
    source.instructions.forEach((instruction) => {
      if (!instruction?.id || byId.has(instruction.id))
        throw new Error("Instruction identifiers are missing or repeated.");
      byId.set(instruction.id, instruction);
    });
    const pending = [{ tree: source.structure, depth: 0 }];
    const seen = new Set();
    const included = new Set();
    let count = 0;
    while (pending.length) {
      const { tree, depth } = pending.pop();
      if (!tree || typeof tree !== "object" || seen.has(tree))
        throw new Error("The captured branch structure is incomplete or repeated.");
      if (++count > LIMITS.nodes || depth > LIMITS.depth)
        throw new Error("The rung exceeds the diagram's structure or nesting limit.");
      seen.add(tree);
      if (tree.kind === "instruction") {
        if (!byId.has(tree.instruction_id) || included.has(tree.instruction_id))
          throw new Error("The branch structure has a missing or repeated instruction reference.");
        included.add(tree.instruction_id);
      } else if (tree.kind === "sequence" || tree.kind === "branch") {
        const children = tree.kind === "sequence" ? tree.items : tree.legs;
        if (!Array.isArray(children) || (tree.kind === "branch" && !children.length))
          throw new Error("A captured sequence or branch has incomplete children.");
        children.forEach((child) => pending.push({ tree: child, depth: depth + 1 }));
      } else {
        throw new Error(`Unrecognized structure node: ${String(tree.kind || "unknown")}.`);
      }
    }
    if (included.size !== byId.size)
      throw new Error("Some captured instructions are absent from the branch structure.");
    return byId;
  }

  function layout(tree) {
    if (tree.kind === "instruction") {
      const result = emptyLayout(CARD_WIDTH, CARD_HEIGHT);
      result.cards.push({ instructionId: tree.instruction_id, x: 0, y: 0 });
      return result;
    }
    if (tree.kind === "sequence") {
      if (!tree.items.length) {
        const result = emptyLayout(190, 78);
        result.wires.push(wire(0, 39, 190, 39, "bypass"));
        result.labels.push({ x: 95, y: 24, text: "Empty path · bypass", kind: "bypass" });
        return result;
      }
      const children = tree.items.map(layout);
      const width = children.reduce((sum, child) => sum + child.width, 0)
        + SERIES_GAP * (children.length - 1);
      const height = Math.max(...children.map((child) => child.height));
      const result = emptyLayout(width, height);
      let x = 0;
      children.forEach((child, index) => {
        translate(result, child, x, (height - child.height) / 2);
        x += child.width;
        if (index < children.length - 1) {
          result.wires.push(wire(x, height / 2, x + SERIES_GAP, height / 2, "series"));
          x += SERIES_GAP;
        }
      });
      return result;
    }
    const children = tree.legs.map(layout);
    const width = Math.max(...children.map((child) => child.width)) + BUS_MARGIN * 2;
    const height = children.reduce((sum, child) => sum + child.height + LEG_LABEL_HEIGHT, 0)
      + LEG_GAP * (children.length - 1);
    const result = emptyLayout(width, height);
    const leftBus = BUS_MARGIN / 2;
    const rightBus = width - leftBus;
    const anchors = [];
    let y = 0;
    children.forEach((child, index) => {
      result.labels.push({ x: BUS_MARGIN, y: y + 17, text: `Path ${index + 1}`, kind: "path" });
      y += LEG_LABEL_HEIGHT;
      const anchor = y + child.height / 2;
      anchors.push(anchor);
      translate(result, child, BUS_MARGIN, y);
      result.wires.push(wire(leftBus, anchor, BUS_MARGIN, anchor, "branch-entry"));
      result.wires.push(wire(BUS_MARGIN + child.width, anchor, rightBus, anchor, "branch-exit"));
      result.junctions.push({ x: leftBus, y: anchor }, { x: rightBus, y: anchor });
      y += child.height + LEG_GAP;
    });
    const first = Math.min(height / 2, anchors[0]);
    const last = Math.max(height / 2, anchors[anchors.length - 1]);
    result.wires.push(wire(leftBus, first, leftBus, last, "split"));
    result.wires.push(wire(rightBus, first, rightBus, last, "join"));
    result.wires.push(wire(0, height / 2, leftBus, height / 2, "branch-inlet"));
    result.wires.push(wire(rightBus, height / 2, width, height / 2, "branch-outlet"));
    result.junctions.push({ x: leftBus, y: height / 2 }, { x: rightBus, y: height / 2 });
    return result;
  }

  function originalSource(source, reason) {
    const fallback = element("div", "rung-flow-fallback");
    fallback.setAttribute("role", "note");
    fallback.append(element("p", "warning-panel", `${reason} The diagram is unavailable; no partial connections are shown.`));
    const details = element("details", "rung-flow-source");
    details.open = true;
    details.append(element("summary", null, "Original rung text"));
    details.append(element("pre", null, source?.text ?? "Source text unavailable."));
    fallback.append(details);
    return fallback;
  }

  function defaultInstruction(instruction) {
    const content = element("div", "rung-flow-default");
    content.append(element("strong", null, instruction.opcode || "Instruction"));
    content.append(element("pre", null, (instruction.arguments || []).join(", ")));
    return content;
  }

  function draw(source, byId, plan, options) {
    const root = element("section", "rung-flow");
    root.setAttribute("aria-label", "Connected rung structure");
    root.append(element("p", "rung-flow-guide",
      "Follow left to right. Wires split into parallel source paths and rejoin. This shows source progression, not elapsed time or live execution."));
    const controls = element("div", "rung-flow-controls");
    const viewport = element("div", "rung-flow-viewport");
    viewport.tabIndex = 0;
    viewport.setAttribute("role", "region");
    viewport.setAttribute("aria-label", "Rung diagram. Scroll to explore; use the zoom controls to change scale.");
    const scaled = element("div", "rung-flow-scaled");
    const canvas = element("div", "rung-flow-canvas");
    const width = plan.width + PADDING_X * 2;
    const height = plan.height + PADDING_Y * 2;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    const svg = svgElement("svg", { width, height, viewBox: `0 0 ${width} ${height}`, "aria-hidden": "true" });
    svg.classList.add("rung-flow-wires");
    const group = svgElement("g", { transform: `translate(${PADDING_X} ${PADDING_Y})` });
    const lines = [
      wire(-50, plan.height / 2, 0, plan.height / 2, "rung-entry"),
      ...plan.wires,
      wire(plan.width, plan.height / 2, plan.width + 50, plan.height / 2, "rung-exit"),
    ];
    lines.forEach((line) => {
      group.append(svgElement("path", {
        d: `M ${line.x1} ${line.y1} L ${line.x2} ${line.y2}`,
        "data-wire": line.kind,
      }));
      if (line.y1 === line.y2 && line.x2 - line.x1 >= 36) {
        const middle = (line.x1 + line.x2) / 2;
        group.append(svgElement("polyline", {
          points: `${middle - 4},${line.y1 - 4} ${middle + 1},${line.y1} ${middle - 4},${line.y1 + 4}`,
          "data-direction": "source-progression",
        }));
      }
    });
    plan.junctions.forEach((point) => group.append(svgElement("circle", { cx: point.x, cy: point.y, r: 4 })));
    [-50, plan.width + 50].forEach((x) => group.append(svgElement("line", {
      x1: x, x2: x, y1: plan.height / 2 - 24, y2: plan.height / 2 + 24,
    })));
    svg.append(group);
    canvas.append(svg);
    const labels = [
      { x: -65, y: plan.height / 2 - 29, text: "Entry", kind: "endpoint" },
      ...plan.labels,
      { x: plan.width + 34, y: plan.height / 2 - 29, text: "Exit", kind: "endpoint" },
    ];
    labels.forEach((label) => {
      const text = element("span", `rung-flow-label rung-flow-${label.kind}`, label.text);
      text.style.left = `${label.x + PADDING_X}px`;
      text.style.top = `${label.y + PADDING_Y - 17}px`;
      canvas.append(text);
    });
    const positions = new Map(source.instructions.map((instruction, index) => [instruction.id, index + 1]));
    plan.cards.forEach((card) => {
      const instruction = byId.get(card.instructionId);
      const wrapper = element("article", "rung-flow-card");
      wrapper.dataset.instructionId = instruction.id;
      wrapper.style.left = `${card.x + PADDING_X}px`;
      wrapper.style.top = `${card.y + PADDING_Y}px`;
      wrapper.style.width = `${CARD_WIDTH}px`;
      wrapper.style.height = `${CARD_HEIGHT}px`;
      wrapper.setAttribute("aria-label", `Instruction ${positions.get(instruction.id)}: ${instruction.opcode}`);
      const content = element("div", "rung-flow-card-content");
      content.append((options.instruction || defaultInstruction)(instruction));
      wrapper.append(content);
      if (options.onInstruction) {
        const inspect = element("button", "rung-flow-inspect", "Inspect instruction");
        inspect.type = "button";
        inspect.addEventListener("click", () => options.onInstruction(instruction));
        wrapper.append(inspect);
      }
      canvas.append(wrapper);
    });
    const zoomLabel = element("output", "rung-flow-zoom");
    zoomLabel.setAttribute("aria-live", "polite");
    let zoom = 1;
    const updateZoom = (value) => {
      zoom = Math.max(0.25, Math.min(2, Math.round(value * 100) / 100));
      canvas.style.transform = `scale(${zoom})`;
      scaled.style.width = `${width * zoom}px`;
      scaled.style.height = `${height * zoom}px`;
      zoomLabel.textContent = `${Math.round(zoom * 100)}%`;
      zoomOut.disabled = zoom <= 0.25;
      zoomIn.disabled = zoom >= 2;
    };
    const zoomButton = (text, callback) => {
      const control = element("button", null, text);
      control.type = "button";
      control.addEventListener("click", callback);
      return control;
    };
    const zoomOut = zoomButton("Zoom out", () => updateZoom(zoom - 0.25));
    const zoomIn = zoomButton("Zoom in", () => updateZoom(zoom + 0.25));
    const reset = zoomButton("Reset zoom", () => updateZoom(1));
    controls.append(zoomOut, zoomLabel, zoomIn, reset,
      element("span", "rung-flow-count", `${plan.cards.length} instructions · all captured paths`));
    scaled.append(canvas);
    viewport.append(scaled);
    root.append(controls, viewport);
    updateZoom(1);
    return root;
  }

  function render(source, options = {}) {
    try {
      const byId = validate(source);
      const plan = layout(source.structure);
      if (plan.width > LIMITS.extent || plan.height > LIMITS.extent)
        throw new Error("This rung exceeds the diagram's available canvas size.");
      return draw(source, byId, plan, options);
    } catch (error) {
      return originalSource(source, error instanceof Error ? error.message : "The rung diagram could not be constructed.");
    }
  }

  window.PLCRungFlow = Object.freeze({ render });
})();
