/* A viewport-sized view of captured source. Positions and arrows are not scan order. */
(() => {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const CARD_W = 250, CARD_H = 104, STEP_X = 390, STEP_Y = 180;
  const MAX_NODES = 80, MAX_EDGES = 320, LIST_SIZE = 25, CACHE_SIZE = 80;
  const el = (tag, text, cls = "") => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = String(text);
    node.className = cls;
    return node;
  };
  const svg = (tag, attrs = {}, text) => {
    const node = document.createElementNS(NS, tag);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, String(value)));
    if (text !== undefined) node.textContent = String(text);
    return node;
  };
  const btn = (text, fn, cls = "") => {
    const node = el("button", text, cls); node.type = "button";
    node.addEventListener("click", fn); return node;
  };
  const labeled = (text, control) => { const label = el("label", text); label.append(control); return label; };
  const clip = (text, n) => String(text || "").length > n ? String(text).slice(0, n - 1) + "…" : String(text || "");
  const rungName = item => `Rung ${item.number === "" || item.number == null ? "(unnumbered)" : item.number}`;
  const ids = values => (Array.isArray(values) ? values : []).map(value => typeof value === "string" ? value : value.id || value.rung_id).filter(Boolean);
  let serial = 0;

  function mount(root, options) {
    const prefix = `ladder-map-${++serial}`;
    let destroyed = false, generation = 0, linkGeneration = 0, detailGeneration = 0, selectionGeneration = 0;
    let runId = "", items = [], byId = new Map(), positions = new Map(), total = 0, selected = "";
    let columns = 1, listPage = 1, signalPage = 1, signalPages = 1, queryTimer, linkTimer, hoverTimer, frame;
    let transform = { x: 24, y: 24, scale: 1 }, drag = null, lastDragged = "", visible = [], signals = [];
    let linksKey = "", visibleKey = "", loadedKey = "", loadPromise = Promise.resolve(), fitted = false, pinned = false, resizeObserver;
    let connectionAvailable = null, connectionNotice = "", connectionCoverage = null;
    let detailSourceId = "", detailLoading = false;
    const cache = new Map(), pending = new Map();
    const filters = { query: "", routine: "", family: "", signal_id: "" };

    const toolbar = el("div", undefined, "ladder-map-toolbar");
    const search = el("input", undefined, "ladder-map-search");
    search.type = "search"; search.placeholder = "Find a tag, rung, comment or instruction";
    const routine = el("select", undefined, "ladder-map-routine");
    const family = el("select", undefined, "ladder-map-family");
    const direction = el("select", undefined, "ladder-map-direction");
    [["both", "All signals"], ["inputs", "Input signals"], ["outputs", "Output signals"]].forEach(([value, text]) => { const item = el("option", text); item.value = value; direction.append(item); });
    const status = el("p", "Open an analysis to see its captured ladder.", "ladder-map-status"); status.setAttribute("role", "status");
    const coverageStatus = el("p", undefined, "ladder-map-coverage"); coverageStatus.setAttribute("role", "status");
    const error = el("div", undefined, "ladder-map-error"); error.hidden = true; error.setAttribute("role", "alert");
    const filterNote = el("div", undefined, "ladder-map-filter-note");
    const stage = el("div", undefined, "ladder-map-stage");
    const canvas = svg("svg", { class: "ladder-map-canvas", role: "group", "aria-label": "Captured ladder map. Drag the background to pan; use the zoom controls or the rung list to navigate.", tabindex: "0" });
    const world = svg("g", { class: "ladder-map-world" });
    const edgeLayer = svg("g", { class: "ladder-map-edges", "aria-hidden": "true" });
    const signalLayer = svg("g", { class: "ladder-map-signals" });
    const nodeLayer = svg("g", { class: "ladder-map-nodes" });
    const defs = svg("defs");
    const marker = svg("marker", { id: `${prefix}-arrow`, viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 6, markerHeight: 6, orient: "auto-start-reverse" });
    marker.append(svg("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: "currentColor" })); defs.append(marker);
    world.append(edgeLayer, signalLayer, nodeLayer); canvas.append(defs, world);
    const zoomStatus = el("span", "100%", "ladder-map-zoom-status");
    const viewControls = el("div", undefined, "ladder-map-view-controls");
    const popSource = btn("Pop out selected source", () => options.popout?.(selected, "source"));
    const popConnections = btn("Pop out connections", () => options.popout?.(selected, "connections"));
    const inspectConnections = btn("Explore selected connections", () => options.connections?.(selected));
    popSource.disabled = popConnections.disabled = inspectConnections.disabled = true;
    viewControls.append(btn("Zoom in", () => zoomAt(1.4)), btn("Zoom out", () => zoomAt(1 / 1.4)), zoomStatus,
      btn("Fit all", fit), btn("Reset layout", () => { positions.clear(); fit(); }),
      btn("Pop out map", () => options.popout?.(selected, "map")), popSource, popConnections, inspectConnections);
    const detailBox = el("aside", undefined, "ladder-map-detail"); detailBox.hidden = true;
    detailBox.setAttribute("aria-label", "Rung and block information");
    const detailControls = el("div", undefined, "ladder-map-detail-controls");
    const pin = btn("Pin information", () => {
      setPinned(!pinned);
      if (pinned) {
        clearTimeout(hoverTimer);
        // Leaving a hovered card invalidates its display callback. Reattach to
        // the same cached/pending request when pinning the preview in flight.
        if (detailSourceId && detailLoading) queueDetail(detailSourceId, true);
      }
    });
    pin.setAttribute("aria-pressed", "false");
    pin.disabled = true;
    const closeInformation = btn("Close information", () => { setPinned(false); detailBox.hidden = true; detailSourceId = ""; detailLoading = false; pin.disabled = closeInformation.disabled = true; detailGeneration++; });
    closeInformation.disabled = true;
    detailControls.append(pin, closeInformation); viewControls.append(detailControls);
    const detailHint = el("p", "Pin information to follow its links. This preview lets clicks reach the map beneath it.", "ladder-map-detail-hint");
    const detailBody = el("div", undefined, "ladder-map-detail-body"); detailBox.append(detailHint, detailBody);
    stage.append(canvas, detailBox);
    const viewNote = el("p", undefined, "ladder-map-view-note");
    const legend = el("p", "Source-order layout, not execution order. Solid links show recorded writers/readers of the same address; dashed links have an unknown direction. These are possible connections, not live flow. Zoomed-out tiles summarize rungs; select a tile to zoom in. Dragging changes this view only.", "ladder-map-legend");
    const listToggle = el("details", undefined, "ladder-map-list-section");
    listToggle.append(el("summary", "Find and select rungs (keyboard-accessible list)"));
    const list = el("div", undefined, "ladder-map-list");
    const listNav = el("div", undefined, "ladder-map-pagination");
    const previous = btn("Previous rungs", () => { listPage--; renderList(); });
    const next = btn("Next rungs", () => { listPage++; renderList(); });
    const pageInput = el("input", undefined, "ladder-map-list-page"); pageInput.type = "number"; pageInput.min = "1"; pageInput.value = "1";
    const listStatus = el("span");
    pageInput.addEventListener("change", () => { listPage = Math.max(1, Math.min(Math.ceil(total / LIST_SIZE) || 1, Number(pageInput.value) || 1)); renderList(); });
    listNav.append(previous, labeled("Rung list page", pageInput), next, listStatus); listToggle.append(listNav, list);
    const signalSection = el("details", undefined, "ladder-map-signal-section");
    signalSection.append(el("summary", "Signals connected to the visible rungs"));
    const signalStatus = el("p", undefined, "ladder-map-signal-status"); signalStatus.setAttribute("role", "status");
    const signalList = el("div", undefined, "ladder-map-signal-list");
    const signalNav = el("div", undefined, "ladder-map-pagination");
    const prevSignals = btn("Previous signals", () => { signalPage--; queueLinks(true); });
    const nextSignals = btn("Next signals", () => { signalPage++; queueLinks(true); });
    signalNav.append(prevSignals, nextSignals); signalSection.append(signalStatus, signalNav, signalList);
    toolbar.append(labeled("Search all captured rungs", search), labeled("Routine", routine), labeled("Function family", family), labeled("Connections", direction));
    root.className += " ladder-map";
    root.replaceChildren(toolbar, filterNote, status, coverageStatus, error, viewControls, stage, viewNote, legend, signalSection, listToggle);

    function renderCoverage() {
      const parts = [];
      if (connectionAvailable === false) parts.push("Connection map unavailable for this saved analysis.");
      if (connectionNotice) parts.push(connectionNotice);
      if (connectionCoverage) {
        const fields = [["unparsed_rungs", "unparsed rungs"], ["unresolved_uses", "unresolved address uses"], ["unknown_roles", "uses with unknown read/write roles"], ["invalid_expanded_addresses", "addresses without a valid expanded identity"]];
        parts.push("Saved analysis coverage: " + fields.map(([key, label]) => `${Number.isFinite(connectionCoverage[key]) ? connectionCoverage[key].toLocaleString() : "not reported"} ${label}`).join("; ") + ".");
        const excluded = [["unqualified_rungs", "source-unqualified rungs in the analysis"], ["unqualified_uses", "source-unqualified address uses in the analysis"], ["unqualified_visible_rungs", "source-unqualified visible rungs"], ["unqualified_visible_uses", "source-unqualified visible address uses"], ["rejected_signal_count", "signals omitted from this connection view"]].filter(([key]) => Number.isFinite(connectionCoverage[key]));
        if (excluded.length) parts.push("Source verification: " + excluded.map(([key, label]) => `${connectionCoverage[key].toLocaleString()} ${label}`).join("; ") + ".");
        const unmodeled = [["calculation_reads_available", "calculation expression reads"], ["implicit_effects_available", "implicit instruction effects"], ["member_overlap_available", "overlap between whole structures/arrays and their members"]].filter(([key]) => connectionCoverage[key] === false).map(([, label]) => label);
        if (unmodeled.length) parts.push("Not modeled in these connections: " + unmodeled.join("; ") + ".");
      } else if (connectionAvailable !== false) parts.push("Connection coverage counts load when you zoom into individual rungs.");
      parts.push("Missing lines do not mean that a signal is unused or that rungs are independent.");
      coverageStatus.textContent = parts.join(" ");
    }
    function setPinned(value) {
      pinned = value; pin.textContent = pinned ? "Unpin information" : "Pin information";
      pin.setAttribute("aria-pressed", String(pinned));
      detailBox.className = `ladder-map-detail${pinned ? " is-pinned" : ""}`;
      detailHint.textContent = pinned ? "Pinned information. Follow its links, or unpin to click through to the map." : "Pin information to follow its links. This preview lets clicks reach the map beneath it.";
      detailBody.querySelectorAll("button").forEach(button => { button.disabled = !pinned; });
    }

    function isCurrent(token) { return !destroyed && generation === token && options.getState()?.active_run === runId; }
    function dimensions() { const rect = canvas.getBoundingClientRect(); return { width: Math.max(320, rect.width || 900), height: Math.max(240, rect.height || 600) }; }
    function position(item) {
      return positions.get(item.id) || { x: (item._index % columns) * STEP_X, y: Math.floor(item._index / columns) * STEP_Y };
    }
    function choiceValues(control, values, allLabel, value) {
      control.replaceChildren(); const all = el("option", allLabel); all.value = ""; control.append(all);
      (values || []).forEach(entry => { const option = el("option", `${entry.label || entry.id} (${entry.count ?? 0})`); option.value = entry.id; control.append(option); });
      control.value = value;
    }
    function changeFilter(name, value) { filters[name] = value; listPage = 1; signalPage = 1; fitted = false; return refresh(); }
    function drawSoon() { if (destroyed || frame) return; frame = requestAnimationFrame(() => { frame = null; draw(); }); }
    function fit() {
      const size = dimensions(); let maxX = Math.max(CARD_W, columns * STEP_X - (STEP_X - CARD_W));
      let maxY = Math.max(CARD_H, Math.ceil(Math.max(total, 1) / columns) * STEP_Y - (STEP_Y - CARD_H));
      let minX = 0, minY = 0;
      positions.forEach((point, id) => { if (!byId.has(id)) return; minX = Math.min(minX, point.x); minY = Math.min(minY, point.y); maxX = Math.max(maxX, point.x + CARD_W); maxY = Math.max(maxY, point.y + CARD_H); });
      const scale = Math.max(0.005, Math.min(1.2, (size.width - 48) / (maxX - minX), (size.height - 48) / (maxY - minY)));
      transform = { scale, x: (size.width - (maxX - minX) * scale) / 2 - minX * scale, y: (size.height - (maxY - minY) * scale) / 2 - minY * scale };
      fitted = true; drawSoon();
    }
    function zoomAt(factor, point) {
      const size = dimensions(), focus = point || { x: size.width / 2, y: size.height / 2 };
      const scale = Math.max(0.005, Math.min(3, transform.scale * factor)), ratio = scale / transform.scale;
      transform = { scale, x: focus.x - (focus.x - transform.x) * ratio, y: focus.y - (focus.y - transform.y) * ratio };
      drawSoon();
    }
    function localPoint(event) { const rect = canvas.getBoundingClientRect(); return { x: event.clientX - rect.left, y: event.clientY - rect.top }; }
    function bindNode(node, item) {
      node.addEventListener("click", event => { event.stopPropagation(); if (lastDragged === item.id) { lastDragged = ""; return; } select(item.id); });
      node.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); select(item.id); } });
      node.addEventListener("pointerdown", event => {
        if (event.button !== 0) return; event.stopPropagation(); const point = localPoint(event);
        drag = { kind: "node", id: item.id, start: point, point: position(item), moved: false };
        canvas.setPointerCapture?.(event.pointerId);
      });
      attachHover(node, item.id);
    }
    function draw() {
      if (destroyed) return;
      const size = dimensions(), scale = transform.scale;
      canvas.setAttribute("viewBox", `0 0 ${size.width} ${size.height}`);
      world.setAttribute("transform", `translate(${transform.x} ${transform.y}) scale(${scale})`);
      zoomStatus.textContent = `${Math.round(scale * 100)}%`;
      nodeLayer.replaceChildren();
      const inView = items.filter(item => { const p = position(item); return p.x * scale + transform.x < size.width + 40 && (p.x + CARD_W) * scale + transform.x > -40 && p.y * scale + transform.y < size.height + 40 && (p.y + CARD_H) * scale + transform.y > -40; });
      const clustered = scale < 0.38 || inView.length > MAX_NODES;
      visible = clustered ? [] : inView;
      if (clustered) {
        const buckets = new Map();
        inView.forEach(item => { const point = position(item), sx = point.x * scale + transform.x, sy = point.y * scale + transform.y;
          const key = `${Math.floor(sx / 90)}:${Math.floor(sy / 64)}`;
          if (!buckets.has(key)) buckets.set(key, []); buckets.get(key).push(item);
        });
        buckets.forEach((bucket, key) => {
          const first = position(bucket[0]); const node = svg("g", { class: "ladder-map-cluster", role: "button", tabindex: "0", "aria-label": `Zoom into ${bucket.length} rungs near ${rungName(bucket[0])}` });
          const width = 72 / scale, height = 44 / scale;
          const [cellX, cellY] = key.split(":").map(Number);
          const tile = { x: (cellX * 90 + 9 - transform.x) / scale, y: (cellY * 64 + 10 - transform.y) / scale };
          node.append(svg("rect", { x: tile.x, y: tile.y, width, height, rx: 6 / scale }), svg("text", { x: tile.x + width / 2, y: tile.y + height / 2, "font-size": 13 / scale, "text-anchor": "middle", "dominant-baseline": "middle" }, `${bucket.length} ${bucket.length === 1 ? "rung" : "rungs"}`));
          const expand = () => { const zoom = Math.min(3, Math.max(0.5, scale * 2.5)); transform = { scale: zoom, x: size.width / 2 - (first.x + CARD_W / 2) * zoom, y: size.height / 2 - (first.y + CARD_H / 2) * zoom }; drawSoon(); };
          node.addEventListener("pointerdown", event => event.stopPropagation());
          node.addEventListener("click", expand); node.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); expand(); } }); nodeLayer.append(node);
        });
        viewNote.textContent = `${inView.length.toLocaleString()} rungs in view, grouped into ${buckets.size} tiles. Zoom in to see individual rungs and address connections. Every rung is available through search and the list below.`;
      } else {
        visible.forEach(item => {
          const p = position(item), active = item.id === selected;
          const node = svg("g", { class: `ladder-map-node${active ? " is-selected" : ""}`, role: "button", tabindex: "0", "aria-label": `${rungName(item)}. ${item.routine_label || item.path}. ${(item.opcodes || []).join(", ")}`, "aria-pressed": String(active), "data-rung-id": item.id });
          node.append(svg("rect", { x: p.x, y: p.y, width: CARD_W, height: CARD_H, rx: 9 }));
          [[rungName(item), 22, "ladder-map-node-title"], [clip(item.routine_label || item.path, 34), 43, "ladder-map-node-routine"], [clip((item.opcodes || []).join(" · "), 38), 65, "ladder-map-node-opcodes"], [`${item.instruction_count} blocks · ${item.branch_count} branches${item.parse_status === "partial" ? " · partial" : ""}`, 87, "ladder-map-node-meta"]].forEach(([text, dy, cls]) => node.append(svg("text", { x: p.x + 12, y: p.y + dy, class: cls }, text)));
          bindNode(node, item); nodeLayer.append(node);
        });
        viewNote.textContent = `${visible.length} individual rungs in view of ${total.toLocaleString()} matches. Select a rung to inspect its complete branches, equations and source. Hover or focus for block information.`;
      }
      drawLinks(); queueLinks();
    }
    function center(item) { const size = dimensions(), p = position(item), scale = Math.max(0.8, transform.scale); transform = { scale, x: size.width / 2 - (p.x + CARD_W / 2) * scale, y: size.height / 2 - (p.y + CARD_H / 2) * scale }; drawSoon(); }
    async function select(id, reposition = false) {
      const token = ++selectionGeneration, current = generation;
      try {
        const accepted = await options.inspect(id);
        if (accepted === false || token !== selectionGeneration || !isCurrent(current)) return false;
        selected = id; popSource.disabled = popConnections.disabled = inspectConnections.disabled = false;
        if (reposition && byId.has(id)) center(byId.get(id)); else drawSoon();
        options.onSelection?.(id); queueDetail(id, true); renderList(); return true;
      } catch (cause) { if (token === selectionGeneration && isCurrent(current)) showError(cause, () => select(id, reposition)); return false; }
    }
    async function inspectSource(id) {
      const token = ++selectionGeneration, current = generation;
      try { return await options.inspect(id); }
      catch (cause) { if (token === selectionGeneration && isCurrent(current)) showError(cause, () => inspectSource(id)); return false; }
    }
    function renderList() {
      list.replaceChildren(); const pages = Math.max(1, Math.ceil(total / LIST_SIZE));
      listPage = Math.max(1, Math.min(listPage, pages)); pageInput.value = String(listPage); pageInput.max = String(pages);
      previous.disabled = listPage <= 1; next.disabled = listPage >= pages;
      listStatus.textContent = `Page ${listPage} of ${pages} · ${total.toLocaleString()} matching rungs`;
      const rows = items.slice((listPage - 1) * LIST_SIZE, listPage * LIST_SIZE);
      rows.forEach(item => {
        const row = btn(`${rungName(item)} · ${item.path}`, () => select(item.id, true), `ladder-map-list-row${item.id === selected ? " is-selected" : ""}`);
        row.title = item.comment_preview || ""; row.addEventListener("focus", () => queueDetail(item.id)); list.append(row);
      });
      if (!rows.length) list.append(el("p", total ? "Loading this page of the rung index…" : "No captured rungs match these filters."));
    }
    function showError(cause, retry) {
      if (destroyed) return; error.hidden = false;
      error.replaceChildren(el("p", cause?.message || String(cause)), btn("Retry", () => { error.hidden = true; retry(); }));
    }
    function filterSignal(signal) {
      // A signal drilldown promises its full fanout, including other routines.
      filters.query = ""; filters.routine = ""; filters.family = ""; search.value = "";
      filters.signal_id = signal.id; listPage = 1; fitted = false;
      filterNote.replaceChildren(el("span", `All recorded rungs connected to ${signal.label || signal.id}`), btn("Clear signal filter", () => changeFilter("signal_id", "")));
      refresh();
    }
    function drawLinks() {
      edgeLayer.replaceChildren(); signalLayer.replaceChildren();
      if (!visible.length) return;
      const current = new Set(visible.map(item => item.id)); let drawn = 0, available = 0;
      signals.forEach((signal, signalIndex) => {
        const endpoints = [...new Set([...ids(signal.readers), ...ids(signal.writers), ...ids(signal.unknown)])].filter(id => current.has(id));
        if (!endpoints.length) return;
        const points = endpoints.map(id => position(byId.get(id)));
        const p = { x: points.reduce((sum, point) => sum + point.x + CARD_W, 0) / points.length + 55,
          y: points.reduce((sum, point) => sum + point.y + CARD_H / 2, 0) / points.length + (signalIndex % 5 - 2) * 18 };
        [["writers", "writer"], ["readers", "reader"], ["unknown", "unknown"]].forEach(([field, cls]) => {
          ids(signal[field]).filter(id => current.has(id)).forEach(id => {
            available++; if (drawn >= MAX_EDGES) return; drawn++;
            const target = position(byId.get(id)), from = cls === "reader" ? p : { x: target.x + CARD_W, y: target.y + CARD_H / 2 }, to = cls === "reader" ? { x: target.x, y: target.y + CARD_H / 2 } : p;
            const attrs = { d: `M ${from.x} ${from.y} C ${(from.x + to.x) / 2} ${from.y}, ${(from.x + to.x) / 2} ${to.y}, ${to.x} ${to.y}`, class: `ladder-map-edge ${cls}` };
            if (cls !== "unknown") attrs["marker-end"] = `url(#${prefix}-arrow)`;
            edgeLayer.append(svg("path", attrs));
          });
        });
        const node = svg("g", { class: "ladder-map-signal", role: "button", tabindex: "0", "aria-label": `Show all rungs connected to ${signal.label || signal.id}` });
        node.append(svg("circle", { cx: p.x, cy: p.y, r: 6 }), svg("title", {}, signal.label || signal.id));
        node.addEventListener("pointerdown", event => event.stopPropagation());
        node.addEventListener("click", () => filterSignal(signal));
        node.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); filterSignal(signal); } }); signalLayer.append(node);
      });
      if (available > drawn) viewNote.textContent += ` Drawing ${drawn} of ${available} visible address links to keep the map responsive; the signal list below exposes every returned signal and its full rung filter.`;
    }
    function queueLinks(force = false) {
      const currentVisible = `${runId}|${visible.map(item => item.id).sort().join(",")}|${direction.value}`;
      if (currentVisible !== visibleKey) { signalPage = 1; visibleKey = currentVisible; }
      const key = `${runId}|${visible.map(item => item.id).sort().join(",")}|${direction.value}|${signalPage}`;
      if (!force && key === linksKey) return;
      clearTimeout(linkTimer); linksKey = key; const token = ++linkGeneration, current = generation;
      signals = []; signalList.replaceChildren(); edgeLayer.replaceChildren(); signalLayer.replaceChildren();
      if (!visible.length || connectionAvailable === false) { signalStatus.textContent = connectionAvailable === false ? "Connections are unavailable for this saved analysis; the captured rung index is still available." : "Zoom in to load connections for the visible rungs. No full-project diagram is downloaded."; prevSignals.disabled = nextSignals.disabled = true; return; }
      signalStatus.textContent = "Loading recorded signal connections…";
      linkTimer = setTimeout(async () => {
        const params = new URLSearchParams({ run_id: runId, ids: visible.map(item => item.id).join(","), page: String(signalPage), direction: direction.value || "both" });
        try {
          const response = await options.api(`/api/ladder-map/links?${params}`);
          if (!isCurrent(current) || token !== linkGeneration || response.run_id !== runId) return;
          if (typeof response.available === "boolean") connectionAvailable = response.available;
          if (response.notice) connectionNotice = response.notice;
          if (response.coverage) connectionCoverage = response.coverage;
          renderCoverage();
          signals = response.items || response.signals || []; signalPages = response.pages || 1;
          prevSignals.disabled = signalPage <= 1; nextSignals.disabled = signalPage >= signalPages;
          signalStatus.textContent = `${response.total ?? signals.length} signals · page ${signalPage} of ${signalPages}. ${response.notice || "Select a signal to see all its recorded rungs, including those outside this view."}`;
          signalList.replaceChildren();
          signals.forEach(signal => {
            const outside = signal.outside_counts || {}, totals = signal.totals || {};
            const row = el("div", undefined, "ladder-map-signal-row");
            row.append(btn(signal.label || signal.id, () => filterSignal(signal)), el("span", `${totals.writers ?? ids(signal.writers).length} writers · ${totals.readers ?? ids(signal.readers).length} readers · ${totals.unknown ?? ids(signal.unknown).length} unknown; outside view: ${outside.writers || 0} writers, ${outside.readers || 0} readers, ${outside.unknown || 0} unknown`)); signalList.append(row);
          });
          drawLinks();
        } catch (cause) { if (isCurrent(current) && token === linkGeneration) { signalStatus.textContent = "Connections could not be loaded."; signalList.replaceChildren(btn("Retry connections", () => queueLinks(true)), el("p", cause.message || String(cause))); } }
      }, 180);
    }
    async function detail(id) {
      const key = `${runId}:${id}`;
      if (cache.has(key)) { const result = cache.get(key); cache.delete(key); cache.set(key, result); return result; }
      if (pending.has(key)) return pending.get(key);
      const promise = options.api(`/api/ladder-map/detail?${new URLSearchParams({ run_id: runId, id })}`).then(result => {
        cache.set(key, result); while (cache.size > CACHE_SIZE) cache.delete(cache.keys().next().value); return result;
      }).finally(() => pending.delete(key)); pending.set(key, promise); return promise;
    }
    function queueDetail(id, immediate = false) {
      if (destroyed) return;
      clearTimeout(hoverTimer); if (pinned && !immediate) return;
      const token = ++detailGeneration, current = generation;
      const show = async () => {
        detailSourceId = id; detailLoading = true;
        detailBox.hidden = false; pin.disabled = closeInformation.disabled = false;
        detailBody.replaceChildren(el("p", "Loading captured block information…"));
        try {
          const response = await detail(id);
          if (!isCurrent(current) || token !== detailGeneration || response.run_id !== runId) return;
          detailLoading = false;
          renderDetail(response, id);
        } catch (cause) { if (isCurrent(current) && token === detailGeneration) { detailLoading = false; detailBody.replaceChildren(el("p", cause.message || String(cause)), btn("Retry information", () => queueDetail(id, true))); setPinned(pinned); } }
      };
      if (immediate) show(); else hoverTimer = setTimeout(show, 240);
    }
    function attachHover(node, id, fallbackText = "") {
      if (fallbackText) node.setAttribute("title", fallbackText);
      node.addEventListener("mouseenter", () => queueDetail(id));
      node.addEventListener("focus", () => queueDetail(id));
      node.addEventListener("mouseleave", () => { clearTimeout(hoverTimer); if (!pinned) detailGeneration++; });
      node.addEventListener("blur", () => { clearTimeout(hoverTimer); if (!pinned) detailGeneration++; });
    }
    function renderDetail(response, id) {
      const item = response.rung || response, known = byId.get(id);
      detailBody.replaceChildren(el("h3", item.title || item.label || (known ? rungName(known) : "Captured source")), el("p", item.path || known?.path || "", "muted"));
      if (item.description || item.comment) detailBody.append(el("p", item.description || item.comment));
      if (item.description_truncated) detailBody.append(el("p", "Description preview shortened; inspect the source for the complete text.", "muted"));
      if (item.attributes && Object.keys(item.attributes).length) detailBody.append(el("p", Object.entries(item.attributes).map(([key, value]) => `${key}: ${value}`).join(" · ")));
      const blocks = response.blocks || response.instructions || [];
      blocks.forEach(block => {
        const section = el("section", undefined, "ladder-map-block-info");
        section.append(el("h4", block.opcode || block.name || block.label || "Block"));
        [block.summary, block.help, block.description, block.family_label || block.family, block.identification, block.notice].filter(Boolean).forEach(text => section.append(el("p", typeof text === "object" ? JSON.stringify(text) : text)));
        if (block.id && block.id !== id) section.append(btn("Block details", () => queueDetail(block.id, true)));
        if (block.attributes && Object.keys(block.attributes).length) section.append(el("p", Object.entries(block.attributes).map(([key, value]) => `${key}: ${value}`).join(" · ")));
        const declarations = block.declarations || block.aoi_candidates || block.definitions || [];
        declarations.forEach(declaration => {
          const link = declaration.id || declaration.source_id;
          section.append(link ? btn(`Inspect ${declaration.name || declaration.label || declaration.path || "declaration"}`, () => inspectSource(link)) : el("p", declaration.name || declaration.label || "Declaration"));
          if (declaration.description) section.append(el("p", declaration.description));
          if (declaration.parameters?.length) {
            const table = el("table"), header = el("tr"); ["Parameter", "Type", "Use"].forEach(value => header.append(el("th", value))); table.append(header);
            declaration.parameters.forEach(parameter => { const row = el("tr"); [parameter.name || parameter.Name, parameter.datatype || parameter.data_type || parameter.DataType, parameter.usage || parameter.Usage || parameter.description].forEach(value => row.append(el("td", value || ""))); table.append(row); }); section.append(table);
          }
        });
        detailBody.append(section);
      });
      if (response.blocks_truncated) detailBody.append(el("p", `Showing ${blocks.length} of ${response.block_count} captured blocks. Inspect source to see every block.`, "muted"));
      if (response.parameters?.length) {
        const table = el("table"), header = el("tr"); ["Parameter", "Type", "Use / description"].forEach(value => header.append(el("th", value))); table.append(header);
        response.parameters.forEach(parameter => { const row = el("tr"), attributes = parameter.attributes || {};
          [parameter.name, attributes.DataType || attributes.datatype, [attributes.Usage || attributes.usage, parameter.description].filter(Boolean).join(" · ")].forEach(value => row.append(el("td", value || ""))); table.append(row);
        }); detailBody.append(table);
      }
      if (response.parameters_truncated) detailBody.append(el("p", `Showing ${response.parameters?.length || 0} of ${response.parameter_count} captured parameters. Inspect source to see all parameters.`, "muted"));
      (response.links || []).forEach(link => detailBody.append(btn(link.label || link.id, () => queueDetail(link.id, true))));
      (response.limitations || []).forEach(text => detailBody.append(el("p", text, "muted")));
      if (response.notice) detailBody.append(el("p", response.notice, "muted"));
      detailBody.append(btn(known ? "Inspect full rung" : "Inspect source", () => known ? select(id) : inspectSource(id)), btn("Pop out this source", () => options.popout?.(id, "source")));
      setPinned(pinned);
    }
    async function loadIndex(token) {
      let page = 1, pages = 1;
      try {
        do {
          const params = new URLSearchParams({ run_id: runId, page: String(page), ...filters });
          const result = await options.api(`/api/ladder-map?${params}`);
          if (!isCurrent(token)) return;
          if (result.run_id !== runId) throw new Error("The active analysis changed. Refresh the workspace project, then reload this map.");
          if (typeof result.connection_available === "boolean") connectionAvailable = result.connection_available;
          if (result.connection_notice) connectionNotice = result.connection_notice;
          if (result.coverage) connectionCoverage = result.coverage;
          renderCoverage();
          total = result.total || 0; pages = result.pages || 1; columns = Math.max(1, Math.ceil(Math.sqrt(total * STEP_Y / STEP_X)));
          (result.items || []).forEach(item => { if (!byId.has(item.id)) { const row = { ...item, _index: items.length }; items.push(row); byId.set(row.id, row); } });
          if (page === 1) { choiceValues(routine, result.routines, "All routines", filters.routine); choiceValues(family, result.families, "All function families", filters.family); }
          status.textContent = `${items.length.toLocaleString()} of ${total.toLocaleString()} matching rungs indexed${page < pages ? " — loading the remaining source index…" : "."} ${result.notice || ""}`;
          renderList(); if (!fitted) fit(); else drawSoon(); page++;
        } while (page <= pages && isCurrent(token));
      } catch (cause) { if (isCurrent(token)) { loadedKey = ""; status.textContent = `${items.length.toLocaleString()} of ${total.toLocaleString()} matching rungs indexed. Loading stopped.`; showError(cause, refresh); } }
    }
    function refresh() {
      const nextRun = options.getState()?.active_run || "";
      if (nextRun !== runId) {
        cache.clear(); positions.clear(); selected = ""; fitted = false;
        connectionAvailable = null; connectionNotice = ""; connectionCoverage = null;
        filters.signal_id = ""; filters.routine = ""; routine.value = "";
        setPinned(false);
        popSource.disabled = popConnections.disabled = inspectConnections.disabled = true;
      }
      const key = JSON.stringify([nextRun, filters]);
      if (key === loadedKey && !destroyed) { drawSoon(); return loadPromise; }
      loadedKey = key;
      const token = ++generation; linkGeneration++; detailGeneration++; selectionGeneration++;
      clearTimeout(queryTimer); clearTimeout(linkTimer); clearTimeout(hoverTimer); linksKey = "";
      runId = nextRun; items = []; byId = new Map(); total = 0; signals = []; visible = []; signalPage = 1;
      setPinned(false); detailBox.hidden = true; detailSourceId = ""; detailLoading = false; pin.disabled = closeInformation.disabled = true;
      error.hidden = true; nodeLayer.replaceChildren(); edgeLayer.replaceChildren(); signalLayer.replaceChildren(); signalList.replaceChildren();
      renderCoverage();
      if (!filters.signal_id) filterNote.replaceChildren();
      if (!runId) { choiceValues(routine, [], "All routines", ""); choiceValues(family, [], "All function families", ""); status.textContent = "Open an analysis to see its captured ladder."; renderList(); return Promise.resolve(); }
      status.textContent = "Loading the captured rung index…"; loadPromise = loadIndex(token); return loadPromise;
    }
    async function focus(id) {
      await loadPromise;
      if (!byId.has(id)) { Object.keys(filters).forEach(key => filters[key] = ""); search.value = ""; fitted = false; await refresh(); }
      if (!byId.has(id)) { showError(new Error("This source is not a captured rung in the active analysis."), refresh); return false; }
      return select(id, true);
    }
    search.addEventListener("input", () => { clearTimeout(queryTimer); queryTimer = setTimeout(() => changeFilter("query", search.value.trim()), 300); });
    search.addEventListener("keydown", event => { if (event.key === "Enter") { event.preventDefault(); clearTimeout(queryTimer); changeFilter("query", search.value.trim()); } });
    routine.addEventListener("change", () => changeFilter("routine", routine.value)); family.addEventListener("change", () => changeFilter("family", family.value));
    direction.addEventListener("change", () => { signalPage = 1; queueLinks(true); });
    canvas.addEventListener("wheel", event => { event.preventDefault(); zoomAt(Math.exp(-Math.max(-120, Math.min(120, event.deltaY)) * 0.003), localPoint(event)); }, { passive: false });
    canvas.addEventListener("pointerdown", event => { if (event.button !== 0) return; drag = { kind: "pan", start: localPoint(event), transform: { ...transform }, moved: false }; canvas.setPointerCapture?.(event.pointerId); });
    canvas.addEventListener("pointermove", event => {
      if (!drag) return; const point = localPoint(event), dx = point.x - drag.start.x, dy = point.y - drag.start.y;
      if (Math.abs(dx) + Math.abs(dy) > 4) drag.moved = true;
      if (drag.kind === "pan") { transform.x = drag.transform.x + dx; transform.y = drag.transform.y + dy; }
      else if (drag.moved) positions.set(drag.id, { x: drag.point.x + dx / transform.scale, y: drag.point.y + dy / transform.scale });
      drawSoon();
    });
    const endDrag = event => {
      if (drag?.kind === "node") { lastDragged = drag.id; if (!drag.moved && event.type !== "pointercancel") select(drag.id); }
      drag = null; if (canvas.hasPointerCapture?.(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
    };
    canvas.addEventListener("pointerup", endDrag); canvas.addEventListener("pointercancel", endDrag);
    canvas.addEventListener("keydown", event => {
      if (event.target !== canvas) return;
      const delta = { ArrowLeft: [60, 0], ArrowRight: [-60, 0], ArrowUp: [0, 60], ArrowDown: [0, -60] }[event.key];
      if (delta) { event.preventDefault(); transform.x += delta[0]; transform.y += delta[1]; drawSoon(); }
      else if (event.key === "+" || event.key === "=") { event.preventDefault(); zoomAt(1.4); }
      else if (event.key === "-") { event.preventDefault(); zoomAt(1 / 1.4); }
      else if (event.key === "Home") { event.preventDefault(); fit(); }
    });
    if (typeof ResizeObserver !== "undefined") { resizeObserver = new ResizeObserver(drawSoon); resizeObserver.observe(stage); }
    return { refresh, focus, attachHover, setRoutine: id => changeFilter("routine", id), destroy() { destroyed = true; generation++; linkGeneration++; detailGeneration++; clearTimeout(queryTimer); clearTimeout(linkTimer); clearTimeout(hoverTimer); if (frame) cancelAnimationFrame(frame); resizeObserver?.disconnect(); cache.clear(); pending.clear(); root.replaceChildren(); } };
  }
  window.PLCLadderMap = { mount };
})();
