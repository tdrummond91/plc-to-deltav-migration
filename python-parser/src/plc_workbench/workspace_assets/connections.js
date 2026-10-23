/* Read-only navigation over authenticated, exact-address source uses. */
(() => {
  "use strict";
  const SVG = "http://www.w3.org/2000/svg";
  const WIDTH = 1510;
  const X = [20, 310, 620, 960, 1250];
  const W = [240, 240, 280, 240, 240];
  let nextMap = 0;
  const element = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = String(text);
    if (className) node.className = className;
    return node;
  };
  function button(text, click, className = "") {
    const node = element("button", text, className);
    node.type = "button";
    node.addEventListener("click", click);
    return node;
  }
  function choice(label, values, value, change) {
    const wrapper = element("label", label);
    const select = element("select");
    values.forEach(([id, text]) => {
      const option = element("option", text);
      option.value = id;
      select.append(option);
    });
    select.value = value;
    select.addEventListener("change", () => change(select.value));
    wrapper.append(select);
    return wrapper;
  }
  function svgNode(tag, attributes) {
    const node = document.createElementNS(SVG, tag);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
    return node;
  }
  function rungLabel(rung) {
    return `Rung ${rung.number === undefined || rung.number === "" ? "(unnumbered)" : rung.number}`;
  }

  function render({ rungId, load, onFocus, openRung, chooseRung }) {
    const root = element("section", undefined, "connections");
    root.setAttribute("aria-label", "Rung connection explorer");
    const status = element("p", "Loading recorded connections…", "connection-status muted");
    status.setAttribute("role", "status");
    const body = element("div");
    root.append(status, body);
    const state = { id: rungId, scope: "all", direction: "both", signal: "", page: 1, endpointPage: 1, pageSize: 12, endpointPageSize: 8 };
    const history = [];
    let serial = 0;
    const markerId = `connection-arrow-${++nextMap}`;

    function change(patch) {
      Object.assign(state, { page: 1, endpointPage: 1 }, patch);
      refresh();
    }
    function focus(id) {
      if (id === state.id) return;
      history.push({ ...state });
      change({ id, signal: "" });
      onFocus?.(id);
    }
    function back() {
      if (!history.length) return;
      Object.assign(state, history.pop());
      onFocus?.(state.id);
      refresh();
    }
    async function refresh() {
      const request = ++serial;
      root.setAttribute("aria-busy", "true");
      status.textContent = "Loading recorded connections…";
      // Remove old controls so a pending response cannot navigate a stale focus.
      body.replaceChildren();
      try {
        const data = await load({ id: state.id, scope: state.scope, direction: state.direction,
          signal_id: state.signal, page: state.page, endpoint_page: state.endpointPage,
          page_size: state.pageSize, endpoint_page_size: state.endpointPageSize });
        if (request !== serial) return;
        if (!data.available) {
          status.textContent = data.notice || "Saved connection evidence is unavailable.";
          body.append(button("Retry", refresh));
          if (chooseRung) body.append(button("Choose another rung", chooseRung));
          return;
        }
        status.textContent = `${rungLabel(data.focus)} · ${data.focus.path || data.focus.id}`;
        draw(data);
      } catch (error) {
        if (request !== serial) return;
        status.textContent = "The connection map could not load. Your review changes are unaffected.";
        body.append(button("Retry", refresh));
        if (chooseRung) body.append(button("Choose another rung", chooseRung));
      } finally {
        if (request === serial) root.setAttribute("aria-busy", "false");
      }
    }
    function draw(data) {
      state.page = data.pagination.page;
      if (state.signal && data.signals.length) state.endpointPage = data.signals[0].endpoints.page;
      const toolbar = element("div", undefined, "connection-toolbar");
      const previous = button("← Back in trace", back);
      previous.disabled = !history.length;
      toolbar.append(previous, button("Open focused rung", () => openRung(state.id), "primary"),
        choice("Scope", [["all", "All captured routines"], ["routine", "Focused routine only"]], state.scope,
          scope => change({ scope, signal: "" })),
        choice("Connections", [["both", "Inputs and outputs"], ["inputs", "Inputs only"], ["outputs", "Outputs only"]],
          state.direction, direction => change({ direction, signal: "" })));
      if (state.signal) toolbar.append(button("Show all signals", () => change({ signal: "" })));
      body.append(toolbar, element("p", data.notice, "muted connection-explanation"));
      const guide = element("p", "Click a signal to expand its connections. Click any neighboring rung to trace from there. The focused rung stays in the center; arrows show recorded uses, not scan order or elapsed time.", "connection-guide");
      body.append(guide);
      coverage(data);

      if (!data.signals.length) {
        body.append(element("p", "No exact-address connections are recorded for this selection. Check the coverage notes and filters before treating a signal as unused.", "notice"));
        return;
      }
      const pager = element("div", undefined, "connection-pager");
      const pages = data.pagination;
      const prev = button("Previous signals", () => change({ page: state.page - 1 }));
      const next = button("Next signals", () => change({ page: state.page + 1 }));
      prev.disabled = pages.page <= 1;
      next.disabled = pages.page >= pages.pages;
      pager.append(prev, element("span", `${pages.total} signals · page ${pages.page} of ${Math.max(1, pages.pages)}`), next);
      pager.append(choice("Signals per page", [10, 12, 25, 50, 100].map(size => [String(size), String(size)]),
        String(state.pageSize), value => change({pageSize: Number(value)})));
      body.append(pager);
      const viewport = element("div", undefined, "connection-viewport");
      viewport.tabIndex = 0;
      viewport.setAttribute("aria-label", "Scrollable connection diagram");
      const sizer = element("div", undefined, "connection-sizer");
      const canvas = element("div", undefined, "connection-canvas");
      const wires = svgNode("svg", { width: WIDTH, "aria-hidden": "true", focusable: "false" });
      const defs = svgNode("defs", {});
      const marker = svgNode("marker", { id: markerId, viewBox: "0 0 10 10", refX: 9, refY: 5,
        markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" });
      marker.append(svgNode("path", { d: "M 0 0 L 10 5 L 0 10 z", class: "connection-arrow" }));
      defs.append(marker);
      wires.append(defs);
      canvas.append(wires);
      sizer.append(canvas);
      viewport.append(sizer);
      const headings = ["Upstream writers", "Signals read", "Focused rung", "Signals written", "Downstream readers"];
      headings.forEach((label, index) => place(element("h3", label, "connection-column"), index, 12, 42));
      function place(node, column, y, height) {
        Object.assign(node.style, { left: `${X[column]}px`, top: `${y}px`, width: `${W[column]}px`, height: `${height}px` });
        canvas.append(node);
        return { x: X[column], y, width: W[column], height };
      }
      function wire(from, to, kind) {
        const start = from.x + from.width, end = to.x;
        const y1 = from.y + from.height / 2, y2 = to.y + to.height / 2;
        const mid = (start + end) / 2;
        wires.append(svgNode("path", { d: `M ${start} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${end} ${y2}`,
          class: `connection-wire ${kind}`, "marker-end": `url(#${markerId})` }));
      }
      const inputSignals = data.signals.filter(signal => signal.input && state.direction !== "outputs");
      const outputSignals = data.signals.filter(signal => signal.output && state.direction !== "inputs");
      function lanes(signals, bucket) {
        let y = 70;
        return signals.map(signal => {
          const endpoints = state.signal ? signal[bucket] : signal[bucket].slice(0, 3);
          const height = Math.max(248, endpoints.length * 128);
          const lane = { signal, endpoints, y, height };
          y += height + 26;
          return lane;
        });
      }
      const left = lanes(inputSignals, "writers"), right = lanes(outputSignals, "readers");
      const endOf = items => items.length ? items.at(-1).y + items.at(-1).height : 320;
      const height = Math.max(endOf(left), endOf(right)) + 30;
      const center = element("article", undefined, "connection-card connection-focus");
      center.append(element("span", "YOU ARE HERE", "connection-eyebrow"), element("h3", rungLabel(data.focus)),
        element("p", data.focus.path || data.focus.id, "connection-path"),
        button("View rung flow", () => openRung(state.id)));
      const focusBox = place(center, 2, Math.max(80, height / 2 - 110), 220);
      function renderSide(items, isInput) {
        const bucket = isInput ? "writers" : "readers";
        items.forEach(({ signal, endpoints, y, height: laneHeight }) => {
          const card = element("article", undefined, "connection-card connection-signal");
          card.dataset.signalId = signal.id;
          const expand = button(signal.label, () => change({ signal: signal.id }), "connection-signal-name");
          expand.title = `Expand ${signal.target_path || signal.label}`;
          card.append(element("span", isInput ? "INPUT SIGNAL" : "OUTPUT SIGNAL", "connection-eyebrow"), expand,
            element("p", signal.target_path || signal.target_id, "connection-path"),
            element("p", `${signal.endpoints.totals.writers} other writer rungs · ${signal.endpoints.totals.readers} other reader rungs in scope`, "connection-count"));
          if (signal.counts.multiple_writers) card.append(element("strong", `${signal.counts.writer_instructions} writer instructions: value source is not unique`, "connection-warning"));
          const total = signal.endpoints.totals[bucket];
          if (total > endpoints.length) card.append(button(`Explore all ${total} ${bucket}`, () => change({ signal: signal.id })));
          const signalBox = place(card, isInput ? 1 : 3, y + laneHeight / 2 - 114, 228);
          wire(isInput ? signalBox : focusBox, isInput ? focusBox : signalBox, isInput ? "input" : "output");
          endpoints.forEach((endpoint, index) => {
            const other = button("", () => focus(endpoint.id), "connection-card connection-rung");
            other.dataset.rungId = endpoint.id;
            other.append(element("strong", rungLabel(endpoint)), element("span", endpoint.path || endpoint.id, "connection-path"),
              element("small", `${endpoint.use_count} recorded uses · click to trace`));
            const box = place(other, isInput ? 0 : 4, y + index * 128, 114);
            wire(isInput ? box : signalBox, isInput ? signalBox : box, isInput ? "input" : "output");
          });
          if (!endpoints.length) {
            const message = total ? `No ${bucket} on this page. ${total} are recorded in this scope; use the connected-rung pages below.`
              : `No other explicit ${isInput ? "writer" : "reader"} rung recorded in this scope. Check coverage and same-rung uses below.`;
            place(element("p", message, "connection-empty"), isInput ? 0 : 4, y + laneHeight / 2 - 70, 140);
          }
        });
      }
      renderSide(left, true);
      renderSide(right, false);
      wires.setAttribute("height", height);
      canvas.style.width = `${WIDTH}px`;
      canvas.style.height = `${height}px`;
      let zoom = 1;
      const zoomText = element("span", "100%");
      function scale(value) {
        zoom = Math.min(1.5, Math.max(0.35, value));
        canvas.style.transform = `scale(${zoom})`;
        sizer.style.width = `${WIDTH * zoom}px`;
        sizer.style.height = `${height * zoom}px`;
        zoomText.textContent = `${Math.round(zoom * 100)}%`;
      }
      const zoomControls = element("div", undefined, "connection-zoom");
      zoomControls.append(button("Zoom out", () => scale(zoom - .15)), zoomText,
        button("Zoom in", () => scale(zoom + .15)), button("Fit width", () => scale(Math.min(1, viewport.clientWidth / WIDTH))),
        button("100%", () => scale(1)));
      body.append(zoomControls, viewport);
      scale(1);
      // Fit after layout, but do not shrink below the readable zoom floor.
      requestAnimationFrame(() => { if (viewport.isConnected) scale(Math.max(.75, Math.min(1, viewport.clientWidth / WIDTH))); });
      details(data);
    }
    function coverage(data) {
      const details = element("details", undefined, "connection-coverage");
      details.append(element("summary", "Connection coverage and limits"));
      details.append(element("p", "Connections require the same captured tag identity and exact member/index suffix. Whole-tag writes, timer status members, PID/AOI side effects, copied ranges and runtime-selected indices may need additional review. An absent line is not proof that no relationship exists."));
      const focus = data.coverage.focus || {};
      const entries = Object.entries(focus).filter(([, value]) => Number(value) > 0);
      if (entries.length) {
        details.open = true;
        entries.forEach(([key, value]) => details.append(element("p", `${key.replaceAll("_", " ")}: ${value}`, "connection-warning")));
      }
      if (data.coverage.focus_parse_status && data.coverage.focus_parse_status !== "parsed")
        details.append(element("p", `Rung parse status: ${data.coverage.focus_parse_status}`, "connection-warning"));
      if (data.coverage.calculation_reads_available === false) {
        details.open = true;
        details.append(element("p", "This older saved run has no calculation-expression input connections. Analyze again to include them.", "connection-warning"));
      }
      body.append(details);
    }
    function details(data) {
      const section = element("section", undefined, "connection-details");
      section.append(element("h3", "Signal details and remaining connections"));
      data.signals.forEach(signal => {
        const item = element("details", undefined, "connection-signal-detail");
        item.open = Boolean(state.signal) || signal.unknown || signal.unknown_uses.length > 0;
        item.append(element("summary", `${signal.label} · focused rung: ${signal.focus_roles.join(" + ")}`));
        item.append(element("p", signal.target_path || signal.target_id, "connection-path"));
        item.append(button("Focus this signal", () => change({ signal: signal.id })));
        const same = signal.same_rung;
        item.append(element("p", `Inside this rung: ${same.reads} read uses, ${same.writes} write uses, ${same.unknown} uses with an unknown role. These are not claims of execution order.`));
        const outside = signal.outside_counts;
        if (outside.writers || outside.readers || outside.unknown_uses)
          item.append(element("p", `Outside this routine filter: ${outside.writers} writer rungs, ${outside.readers} reader rungs, ${outside.unknown_uses || 0} unknown-role rungs.`, "connection-warning"));
        if (signal.unknown) item.append(element("p", "This rung uses the address, but the input/output role is unresolved. No directed line is drawn for that use.", "connection-warning"));
        // Preserve discoverability even when the focus has an unknown role,
        // or another writer competes with an output of the focused rung.
        for (const [bucket, label] of [["writers", "Writer"], ["readers", "Reader"]]) {
          item.append(element("p", `${signal.endpoints.totals[bucket]} other ${bucket} in scope · ${signal[bucket].length} on this page`));
          signal[bucket].forEach(endpoint => item.append(button(
            `${label} · ${rungLabel(endpoint)} · ${endpoint.path || endpoint.id}`, () => focus(endpoint.id), "connection-evidence-endpoint")));
        }
        if (signal.counts.unknown_uses) item.append(element("p", `${signal.counts.unknown_uses} other rungs have unknown-role uses of this address.`));
        signal.unknown_uses.forEach(endpoint => item.append(button(`${rungLabel(endpoint)} · ${endpoint.path || endpoint.id} · unknown role`, () => focus(endpoint.id))));
        const endpointPage = signal.endpoints;
        if (endpointPage.pages > 1 || state.signal) {
          const nav = element("div", undefined, "connection-pager");
          const prev = button("Previous connected rungs", () => change({ signal: signal.id, endpointPage: endpointPage.page - 1 }));
          const next = button("Next connected rungs", () => change({ signal: signal.id, endpointPage: endpointPage.page + 1 }));
          prev.disabled = endpointPage.page <= 1;
          next.disabled = endpointPage.page >= endpointPage.pages;
          nav.append(prev, element("span", `Connections page ${endpointPage.page} of ${endpointPage.pages} · up to ${endpointPage.page_size} rungs per role`), next);
          nav.append(choice("Connected rungs per page", [8, 10, 25, 50, 100].map(size => [String(size), String(size)]),
            String(state.endpointPageSize), value => change({signal: signal.id, endpointPageSize: Number(value)})));
          item.append(nav);
        }
        section.append(item);
      });
      body.append(section);
    }
    refresh();
    return root;
  }
  window.PLCConnections = Object.freeze({ render });
})();
