/* Local project editor. Source values enter the DOM only through textContent. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  let token = document.querySelector('meta[name="workspace-token"]').content;
  const statusNames = {
    unreviewed: "Not reviewed",
    needs_review: "Needs review",
    confirmed: "Confirmed",
  };
  const state = {
    project: null,
    view: "rungs",
    page: 1,
    objectPage: 1,
    routine: "",
    selected: new Set(),
    source: null,
    detailTarget: "rung-detail",
    dirty: false,
    saving: false,
    listSerial: 0,
    detailSerial: 0,
    refreshSerial: 0,
    connectionRung: null,
  };
  const node = (tag, text, className) => {
    const n = document.createElement(tag);
    if (text !== undefined && text !== null) n.textContent = String(text);
    if (className) n.className = className;
    return n;
  };
  const button = (text, callback, className) => {
    const n = node("button", text, className);
    n.type = "button";
    n.addEventListener("click", callback);
    return n;
  };
  const link = (text, id, view = "ladder") => {
    const n = node("a", text);
    n.href =
      "/analysis?language=" + translations.mode() + "#view=" +
      encodeURIComponent(view) +
      (id ? "&source=" + encodeURIComponent(id) : "");
    n.target = "_blank";
    n.rel = "noopener";
    return n;
  };
  const field = (labelText, input) => {
    const n = node("label", labelText);
    n.append(input);
    return n;
  };
  const input = (value = "", placeholder = "") => {
    const n = node("input");
    n.type = "text";
    n.value = value;
    n.placeholder = placeholder;
    return n;
  };
  const select = (choices, value = "") => {
    const n = node("select");
    choices.forEach(([id, label]) => {
      const opt = node("option", label);
      opt.value = id;
      n.append(opt);
    });
    n.value = value;
    return n;
  };
  const clear = (n) => n.replaceChildren();
  const labelOf = (item) =>
    item.path || item.name || item.label || item.id || "Unnamed source";
  const categories = () => state.project?.categories || [];
  const groups = () => state.project?.groups || [];
  const categoryName = (id) =>
    categories().find((c) => c.id === id)?.name || id;
  const chip = (label, cls = "") => node("span", label, "chip " + cls);
  function notify(message, error = false) {
    $("notice").textContent = message;
    $("notice").className = "notice" + (error ? " error" : "");
    $("notice").hidden = false;
  }
  function discard() {
    if (state.saving) {
      notify("Wait for the current change to finish saving.");
      return false;
    }
    if (!state.dirty) return true;
    if (
      !window.confirm(
        "You have unsaved review changes. Discard them and continue?",
      )
    )
      return false;
    state.dirty = false;
    return true;
  }
  function debounce(fn) {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), 250);
    };
  }
  async function api(path, body) {
    const options = { credentials: "same-origin", cache: "no-store" };
    if (body !== undefined) {
      options.method = "POST";
      options.headers = {
        "Content-Type": "application/json",
        "X-Workspace-Token": token,
      };
      options.body = JSON.stringify(body);
    }
    const response = await fetch(path, options);
    let result;
    try {
      result = await response.json();
    } catch {
      throw new Error(
        "The workspace returned an unreadable response. Keep this page open and check the local server.",
      );
    }
    if (!response.ok) {
      const error = new Error(result.error || "Request failed.");
      error.status = response.status;
      throw error;
    }
    return result;
  }
  async function run(action) {
    try {
      return await action();
    } catch (error) {
      notify(
        error.status === 409
          ? "This project changed in another window. Your unsaved form is still here. Reload the page after copying any changes you need to keep. " +
              error.message
          : error.message,
        true,
      );
      return null;
    }
  }
  async function refresh() {
    state.project = await api("/api/state");
    renderProject();
    translations?.refresh();
  }
  async function mutate(
    command,
    expectedRevision = modalRevision ?? state.project.revision,
  ) {
    state.saving = true;
    try {
      const result = await api("/api/mutate", {
        expected_revision: expectedRevision,
        command,
        author: $("reviewer-name").value.trim() || "Local reviewer",
      });
      state.dirty = false;
      await refresh();
      return result;
    } finally {
      state.saving = false;
    }
  }
  function renderProject() {
    const p = state.project,
      s = p.source || {};
    const hasSource = Boolean(p.active_run);
    const snapshot =
      typeof s.snapshot === "string"
        ? s.snapshot
        : s.snapshot?.id || s.snapshot?.sha256 || "";
    $("source-name").textContent = hasSource
      ? s.name || "Imported source"
      : "No source selected";
    $("source-count").textContent = hasSource
      ? `${Number(s.rung_count || 0).toLocaleString()} rungs · ${Number(s.instruction_count || 0).toLocaleString()} instructions`
      : "Choose your finalized analysis run to begin.";
    $("source-snapshot").textContent = snapshot
      ? "Snapshot " + snapshot.slice(0, 18)
      : "";
    $("source-snapshot").title = snapshot;
    $("rung-badge").textContent = hasSource
      ? Number(s.rung_count || 0).toLocaleString()
      : "";
    $("revision").textContent = "Project revision " + p.revision;
    $("backup").disabled = !hasSource;
    $("undo").disabled = !(p.history || []).length;
    const selected = $("category-filter").value;
    $("category-filter").replaceChildren(node("option", "All categories"));
    $("category-filter").firstChild.value = "";
    categories().forEach((c) => {
      const o = node("option", c.name);
      o.value = c.id;
      $("category-filter").append(o);
    });
    $("category-filter").value = selected;
    renderRoutines();
    renderGroups();
    if (state.view === "groups") classificationBrowser.refresh();
    if (state.view === "map") ladderMap.refresh();
    renderChanges();
    renderGuide();
  }
  function renderRoutines() {
    const root = $("routine-tree");
    clear(root);
    const query = $("routine-search").value.toLowerCase();
    const buckets = new Map();
    (state.project.routines || [])
      .filter((r) => (r.path || r.name || "").toLowerCase().includes(query))
      .forEach((r) => {
        const parts = (r.path || r.name || "").split(" / ");
        const parent =
          parts.length > 1 ? parts.slice(0, -1).join(" / ") : "Source routines";
        if (!buckets.has(parent)) buckets.set(parent, []);
        buckets.get(parent).push(r);
      });
    buckets.forEach((routines, parent) => {
      const details = node("details");
      details.open = true;
      details.append(node("summary", parent));
      routines.forEach((r) => {
        const b = button(
          "",
          () => {
            if (!discard()) return;
            state.routine = r.id;
            state.page = 1;
            if (state.view === "map") {
              renderRoutines();
              run(() => ladderMap.setRoutine(r.id));
              return;
            }
            switchView("rungs", true);
            renderRoutines();
            run(loadRungs);
          },
          state.routine === r.id ? "active" : "",
        );
        b.append(
          node("span", r.name || labelOf(r)),
          node("span", Number(r.count || 0).toLocaleString()),
        );
        details.append(b);
        if (!r.count)
          details.append(
            link(
              "Open routine source ↗",
              r.id,
              r.type === "SFC" || r.kind === "SFC" ? "sfc" : "objects",
            ),
          );
      });
      root.append(details);
    });
    if (!buckets.size)
      root.append(
        node(
          "p",
          query ? "No matching routines." : "Routines appear after import.",
          "muted",
        ),
      );
  }
  function switchView(view, skipCheck = false) {
    if (!skipCheck && !discard()) return false;
    if (view === "connections" && state.source?.source?.instructions)
      state.connectionRung = state.source.source.id;
    if (view !== state.view) {
      // Hidden forms must not outlive the source revision that populated them.
      state.source = null;
      state.detailSerial += 1;
      ["rung-detail", "object-detail", "map-detail"].forEach((id) => {
        const panel = $(id);
        if (!panel) return;
        clear(panel);
        panel.inert = false;
        panel.removeAttribute("aria-busy");
        panel.append(
          node(
            "div",
            "Select a source record to inspect its evidence and saved review.",
            "empty",
          ),
        );
      });
    }
    state.view = view;
    document
      .querySelectorAll(".view")
      .forEach((n) => (n.hidden = n.id !== "view-" + view));
    document.querySelectorAll("#navigation button").forEach((n) => {
      if (n.dataset.view === view) n.setAttribute("aria-current", "page");
      else n.removeAttribute("aria-current");
    });
    if (view === "rungs") run(loadRungs);
    if (view === "objects") run(loadObjects);
    if (view === "groups") {
      renderGroups();
      classificationBrowser.refresh();
    }
    if (view === "changes") renderChanges();
    if (view === "connections") renderConnections();
    if (view === "map") run(() => ladderMap.refresh());
    return true;
  }

  function popupWorkspace(id = '', view = 'map') {
    if (!['map', 'source', 'connections'].includes(view)) return;
    if (typeof id !== 'string' || id.length > 256 || /[\x00-\x1f\x7f]/.test(id)) return;
    if (view !== 'map' && !id) {
      notify('Select a source record first.');
      return;
    }
    const target = view === 'source' ? (/^(rung|instruction)_/.test(id) ? 'rungs' : 'objects') : view;
    const url = '/?panel=' + (view === 'source' ? 'source' : 'workspace')
      + '#view=' + target + (id ? '&source=' + encodeURIComponent(id) : '');
    // A direct user gesture opens an independent same-origin window. No source
    // text or credentials are placed in the URL, only canonical evidence IDs.
    const opened = window.open(url, '_blank', 'popup,width=1400,height=900');
    if (opened) {
      opened.opener = null;
    } else {
      notify('The browser blocked the window. Open this view in a new tab instead.');
      const fallback = node('a', 'Open selected view in a new tab');
      fallback.href = url; fallback.target = '_blank'; fallback.rel = 'noopener';
      $('notice').append(fallback);
    }
  }

  async function refreshProjectWindow() {
    if (!discard()) return;
    const request = state.refreshSerial = (state.refreshSerial || 0) + 1;
    const previousProject = state.project, previousSource = state.source;
    const detailSerial = state.detailSerial;
    const selected = state.source?.source?.id;
    const runId = state.project?.active_run;
    const view = state.view;
    const project = await api('/api/state');
    // A slow request must not replace edits or navigation made after it began.
    // Keep the old project revision too, so a retained form cannot save as fresh.
    if (request !== state.refreshSerial) return;
    if (state.dirty || state.saving || state.detailSerial !== detailSerial
        || state.source !== previousSource || state.project !== previousProject
        || state.view !== view) {
      notify('Your current edits or selection were kept. Use Refresh saved data again when ready.');
      return;
    }
    state.project = project;
    renderProject();
    translations?.refresh();
    if (runId !== state.project.active_run) {
      state.connectionRung = null;
      state.selected.clear();
      state.source = null;
      state.view = '';
      switchView(view, true);
      notify('The active analysis changed. Select a source from the current map or list.');
    } else if (selected) {
      await openSource(selected, state.detailTarget, true);
    } else if (view === 'connections') renderConnections();
    else if (view === 'rungs') await loadRungs();
    else if (view === 'objects') await loadObjects();
  }
  function renderSelection() {
    const count = state.selected.size;
    $("bulk-bar").hidden = count === 0;
    $("selection-count").textContent =
      count + " source" + (count === 1 ? "" : "s") + " selected";
  }
  function pagination(target, result, callback) {
    clear(target);
    const total = Number(result.total || 0),
      size = Number(result.page_size || 50),
      page = Number(result.page || 1),
      pages = Math.max(1, Math.ceil(total / size));
    const prev = button("← Previous", () => callback(page - 1)),
      next = button("Next →", () => callback(page + 1));
    prev.disabled = page <= 1;
    next.disabled = page >= pages;
    target.append(prev, node("span", `Page ${page} of ${pages}`), next);
  }
  async function loadRungs() {
    const serial = ++state.listSerial;
    const detailSerial = state.detailSerial;
    const params = new URLSearchParams({
      query: $("rung-search").value,
      routine: state.routine,
      category: $("category-filter").value,
      status: $("status-filter").value,
      page: String(state.page),
    });
    const result = await api("/api/rungs?" + params);
    if (serial !== state.listSerial || state.view !== "rungs") return;
    const root = $("rung-list");
    clear(root);
    const total = Number(result.total || 0),
      page = Number(result.page || 1),
      size = Number(result.page_size || 50);
    $("rung-results").replaceChildren(
      node(
        "strong",
        total
          ? `${(page - 1) * size + 1}–${Math.min(page * size, total)} of ${total.toLocaleString()} matching rungs`
          : "No matching rungs",
      ),
    );
    if (result.items?.length) {
      const check = node("input");
      check.type = "checkbox";
      check.setAttribute("aria-label", "Select all rungs on this page");
      check.checked = result.items.every((r) => state.selected.has(r.id));
      check.addEventListener("change", () => {
        result.items.forEach((r) =>
          check.checked
            ? state.selected.add(r.id)
            : state.selected.delete(r.id),
        );
        renderSelection();
        run(loadRungs);
      });
      $("rung-results").prepend(check);
    }
    const routine = (state.project.routines || []).find(
      (r) => r.id === state.routine,
    );
    $("rung-context").textContent = routine
      ? labelOf(routine) +
        " · Clear filters or choose All to see every captured rung."
      : "All captured rungs are available here. Filters and page controls change what is shown; the imported source remains complete.";
    (result.items || []).forEach((r) => {
      const row = node(
        "div",
        null,
        "list-row" + (state.source?.source?.id === r.id ? " selected" : ""),
      );
      const check = node("input");
      check.type = "checkbox";
      check.checked = state.selected.has(r.id);
      check.setAttribute(
        "aria-label",
        "Select rung " + (r.number ?? "unnumbered") + " " + r.path,
      );
      check.addEventListener("change", () => {
        check.checked ? state.selected.add(r.id) : state.selected.delete(r.id);
        renderSelection();
      });
      const body = node("div", null, "list-body");
      body.append(
        button(
          "Rung " + (r.number ?? "unnumbered"),
          () => run(() => openSource(r.id, "rung-detail")),
          "list-title",
        ),
        node("div", r.path, "list-path"),
      );
      body.append(renderRungPreview(r));
      body.append(button("Open rung & connections →", () => run(() => openSource(r.id, "rung-detail")), "text-button rung-open"));
      if (r.comment) {
        const prose = node("div", null, "source-preview");
        window.PLCTranslation.renderProse(prose, r.comment, r.wording?.comment, result.presentation_mode);
        body.append(prose);
      }
      const badges = node("div", null, "chips");
      badges.append(
        chip(
          statusNames[r.review?.status] || "Not reviewed",
          r.review?.status === "confirmed" ? "reviewed" : "",
        ),
      );
      (r.review?.category_ids || []).forEach((c) =>
        badges.append(chip(categoryName(c), "reviewed")),
      );
      if (!r.review?.category_ids?.length)
        (r.proposals || [])
          .slice(0, 4)
          .forEach((c) =>
            badges.append(
              chip(
                typeof c === "string" ? c : c.label || c.category || c.kind,
                "proposed",
              ),
            ),
          );
      if (r.parse_status !== "parsed")
        badges.append(chip(r.parse_status || "Source gap", "warning"));
      body.append(badges);
      row.append(check, body);
      root.append(row);
    });
    if (!total)
      root.append(
        node(
          "p",
          state.project.active_run
            ? "No results. Clear the filters or choose another routine."
            : "Choose analysis run above to import your source.",
          "empty",
        ),
      );
    pagination($("rung-pagination"), result, (page) => {
      state.page = page;
      run(loadRungs);
    });
    renderSelection();
    // Only fill an untouched empty pane. An explicit/deep-linked selection or
    // unsaved form always wins over a slower inventory request.
    if (!state.source && !state.dirty && !state.saving && !$("rung-detail").inert &&
        detailSerial === state.detailSerial && result.items?.length)
      await openSource(result.items[0].id, "rung-detail", true);
  }
  function renderRungPreview(row) {
    const root = node("div", null, "rung-preview");
    const preview = row.preview || {};
    const occurrences = new Map((preview.calculations?.occurrences || []).map((item) => [item.id, item]));
    const nodes = new Map((preview.calculations?.nodes || []).map((item) => [item.id, item]));
    (preview.instructions || []).forEach((inst) => {
      const card = node("div", null, "rung-preview-expression");
      card.append(node("span", inst.opcode, "eyebrow"), instructionEquation(inst, occurrences.get(inst.id), nodes).math);
      root.append(card);
    });
    if (!preview.instructions?.length)
      root.append(node("p", "Source structure needs inspection. Open the rung for its complete text.", "muted"));
    const extra = Math.max(0, (preview.instruction_count || 0) - (preview.instructions?.length || 0));
    const context = [];
    if (extra) context.push(`${extra} more instruction${extra === 1 ? "" : "s"}`);
    if (preview.branch_count) context.push(`${preview.branch_count} parallel branch${preview.branch_count === 1 ? "" : "es"} · open flow to follow paths`);
    if (context.length) root.append(node("p", context.join(" · "), "preview-context"));
    return root;
  }
  function openConnections(rungId) {
    if (!discard()) return;
    state.connectionRung = rungId;
    switchView("connections", true);
  }
  function renderConnections() {
    const root = $("connection-map");
    clear(root);
    if (!state.connectionRung) {
      root.append(node("p", "Open a rung, then choose Explore inputs & outputs to start a connection map."),
        button("Choose a rung", () => switchView("rungs")));
      return;
    }
    root.append(window.PLCConnections.render({
      rungId: state.connectionRung,
      load: (parameters) => api("/api/connections?" + new URLSearchParams(parameters)),
      onFocus: (id) => { state.connectionRung = id; },
      chooseRung: () => switchView("rungs"),
      openRung: (id) => {
        if (!discard()) return;
        switchView("rungs", true);
        run(() => openSource(id, "rung-detail", true));
      },
    }));
  }
  async function loadObjects() {
    const serial = ++state.listSerial;
    const result = await api(
      "/api/objects?" +
        new URLSearchParams({
          query: $("object-search").value,
          kind: $("object-kind").value,
          page: String(state.objectPage),
        }),
    );
    if (serial !== state.listSerial) return;
    clear($("object-list"));
    $("object-results").textContent =
      Number(result.total || 0).toLocaleString() + " matching source objects";
    (result.items || []).forEach((o) => {
      const row = node("div", null, "list-row");
      const body = node("div", null, "list-body");
      body.append(
        button(
          o.name || o.kind || "Unnamed object",
          () => run(() => openSource(o.id, "object-detail")),
          "list-title",
        ),
        node("div", o.path, "list-path"),
        chip(o.kind),
      );
      if (o.description) {
        const prose = node(o.description_is_code ? "pre" : "div", null, "source-preview");
        if (o.description_is_code) prose.textContent = o.description;
        else window.PLCTranslation.renderProse(prose, o.description, o.wording?.description, result.presentation_mode);
        body.append(prose);
      }
      row.append(body);
      $("object-list").append(row);
    });
    if (!result.total)
      $("object-list").append(
        node("p", "No matching source objects.", "empty"),
      );
    pagination($("object-pagination"), result, (page) => {
      state.objectPage = page;
      run(loadObjects);
    });
  }
  async function openSource(id, target = "rung-detail", skipCheck = false) {
    if (!skipCheck && !discard()) return;
    const serial = ++state.detailSerial;
    const panel = $(target);
    panel.inert = true;
    panel.setAttribute("aria-busy", "true");
    try {
      const result = await api("/api/source?id=" + encodeURIComponent(id));
      if (serial !== state.detailSerial) return;
      if (state.dirty) {
        notify(
          "Your current form has unsaved changes. It was kept instead of replacing it with the requested source.",
        );
        return;
      }
      state.source = result;
      state.detailTarget = target;
      renderDetail(result, panel);
      if (window.innerWidth <= 1150) panel.scrollIntoView({ block: "start" });
      if (state.view === "rungs") run(loadRungs);
    } finally {
      if (serial === state.detailSerial) {
        panel.inert = false;
        panel.removeAttribute("aria-busy");
      }
    }
  }
  function section(root, title, description) {
    const n = node("section", null, "detail-section");
    n.append(node("h3", title));
    if (description) n.append(node("p", description));
    root.append(n);
    return n;
  }
  function human(value) {
    const text = String(value || "").replaceAll("_", " ");
    return text ? text[0].toUpperCase() + text.slice(1) : "Not specified";
  }
  function familyName(category) {
    // These labels deliberately match the existing analysis report vocabulary.
    return (
      {
        pid_control: "PID / control",
        calculation: "Calculations",
        boolean_output: "Boolean outputs",
        timer_counter: "Timers / counters",
        data_transfer: "Data transfers",
        communication_system: "Communications / system",
        sequence_control: "Sequence control",
        control_flow: "Program control flow",
        io_input: "I/O inputs",
        io_output: "I/O outputs",
        alarm: "Possible alarms",
        equipment: "Possible equipment",
        sensor: "Possible sensors",
        miscellaneous: "Miscellaneous logic",
      }[category] || human(category)
    );
  }
  function proposalReason(proposal) {
    if (proposal.basis === "instruction_signature")
      return (
        "Supported " +
        familyName(proposal.category).toLowerCase() +
        " instruction signature."
      );
    if (proposal.basis === "known_mnemonic")
      return "The instruction name suggests this function; its operand effects remain unresolved.";
    if (proposal.basis === "module_root")
      return "A source reference resolves to an exported module root. Read and write roles remain separate.";
    if (proposal.basis === "declaration_type")
      return "A referenced declaration has a PID data type. This suggests loop-related logic; it does not establish PID execution.";
    if (proposal.basis === "text_hint")
      return "A word in a declaration name, description, or rung comment suggests this family. This is a text hint, not proof of behavior.";
    return (
      {
        conditional_boolean_assign:
          "Condition blocks lead to one final Boolean assignment.",
        conditional_boolean_latch:
          "Condition blocks lead to one final Boolean latch.",
        conditional_boolean_unlatch:
          "Condition blocks lead to one final Boolean unlatch.",
        boolean_assign: "One Boolean assignment block.",
        boolean_latch: "One Boolean latch block.",
        boolean_unlatch: "One Boolean unlatch block.",
        no_supported_function_candidate:
          "No modeled function candidate is available for these blocks yet.",
      }[proposal.reason] || human(proposal.reason)
    );
  }
  function missingEvidence(code) {
    return (
      {
        engineering_purpose_unconfirmed: "Engineering purpose is unconfirmed.",
        instruction_effects_not_analyzed:
          "Instruction effects have not been analyzed.",
        execution_not_simulated: "Execution has not been simulated.",
        channel_type_not_verified: "Channel type has not been verified.",
        name_or_comment_is_not_behavior:
          "A name or comment alone does not establish behavior.",
        pid_execution_not_established:
          "PID execution has not been established.",
      }[code] || human(code)
    );
  }
  function renderProposal(root, proposal, evidence) {
    const card = node("div", null, "instruction-row");
    card.append(
      node("strong", familyName(proposal.category)),
      node("p", proposalReason(proposal)),
    );
    if (proposal.missing_evidence?.length) {
      const list = node("ul");
      proposal.missing_evidence.forEach((code) =>
        list.append(node("li", missingEvidence(code))),
      );
      card.append(list);
    }
    if (proposal.evidence_ids?.length) {
      const links = node("details");
      links.append(
        node(
          "summary",
          "Supporting source evidence (" + proposal.evidence_ids.length + ")",
        ),
      );
      const list = node("div", null, "link-row");
      proposal.evidence_ids.forEach((id, index) =>
        list.append(
          link(evidence.get(id) || "Source evidence " + (index + 1), id),
        ),
      );
      links.append(list);
      card.append(links);
    }
    const technical = node("details");
    technical.append(
      node("summary", "Technical identifiers"),
      node("pre", JSON.stringify(proposal, null, 2)),
    );
    card.append(technical);
    root.append(card);
  }
  function renderDetail(data, root) {
    clear(root);
    const s = data.source || {},
      kind = data.kind || s.kind || "rung",
      isRung =
        Object.prototype.hasOwnProperty.call(s, "text") &&
        Array.isArray(s.instructions);
    const header = node("div", null, "detail-header");
    const title = node("div");
    title.append(
      node("span", "ORIGINAL SOURCE", "eyebrow"),
      node(
        "h2",
        isRung
          ? "Rung " + (s.number ?? "unnumbered")
          : s.name || s.opcode || kind,
      ),
      node("p", data.path || s.locator || s.id, "detail-path"),
    );
    header.append(
      title,
      link(
        "Full analysis ↗",
        s.id,
        isRung || kind === "instruction" ? "ladder" : "objects",
      ),
      button('Pop out source', () => popupWorkspace(s.id, 'source')),
    );
    root.append(header);
    root.append(
      button(
        "Back to source list",
        () =>
          $(
            state.detailTarget === 'map-detail' ? 'ladder-map' : state.detailTarget === "object-detail"
              ? "object-list"
              : "rung-list",
          ).scrollIntoView({ block: "center" }),
        "mobile-return",
      ),
    );
    if (data.review?.needs_revalidation)
      root.append(
        node(
          "div",
          "This decision needs revalidation against the current analysis. Review the original evidence before confirming.",
          "warning-panel",
        ),
      );
    if (s.comment || s.description) {
      const comment = section(root, "Source comment / description");
      translations.show(comment, data);
    }
    const summary = node("div", null, "chips");
    [
      ...new Set(
        (data.proposals || []).map((p) =>
          typeof p === "string" ? p : p.category,
        ),
      ),
    ].forEach((category) =>
      summary.append(chip("Proposed: " + familyName(category), "proposed")),
    );
    root.append(summary);
    if (isRung) {
      root.append(button("Explore inputs & outputs →", () => openConnections(s.id), "primary"));
      root.append(button('Pop out connections', () => popupWorkspace(s.id, 'connections')));
      renderRungLogic(root, s, data.calculations || {});
    }
    const editor = section(
      root,
      "Your engineering review",
      "Choose categories and save your decision using the source above. Engineering properties are optional structured fields.",
    );
    renderEditor(editor, s.id, data.review || {}, data.revision);
    if (isRung) {
      const instructions = node("details", null, "detail-section");
      instructions.append(
        node(
          "summary",
          "Every instruction & operand (" +
            s.instructions.length +
            " instructions)",
        ),
      );
      renderInstructions(instructions, s.instructions, data.operands || []);
      root.append(instructions);
    } else {
      const original = section(root, "Original properties");
      renderValues(original, s.attributes || s);
      if (s.arguments) renderInstructions(root, [s], data.operands || []);
    }
    const proposals = node("details", null, "detail-section");
    proposals.append(
      node("summary", "Why the parser proposed these categories"),
      node(
        "p",
        "Analysis proposals remain separate from your saved engineering review.",
      ),
    );
    root.append(proposals);
    const evidenceLabels = new Map([[s.id, "This source"]]);
    (s.instructions || []).forEach((i) =>
      evidenceLabels.set(
        i.id,
        i.opcode + "(" + (i.arguments || []).join(", ") + ")",
      ),
    );
    (data.operands || []).forEach((o) =>
      evidenceLabels.set(o.id, o.raw_text || o.text || "Operand evidence"),
    );
    if (!data.proposals?.length)
      proposals.append(
        node(
          "p",
          "No classification proposal is available for this source. You can categorize it below.",
        ),
      );
    else
      data.proposals.forEach((p) => {
        if (typeof p === "string") proposals.append(chip(p, "proposed"));
        else renderProposal(proposals, p, evidenceLabels);
      });
    const ruleProposals = section(
      root,
      "Project rule proposals",
      "Reusable rules suggest categories from a matching source pattern. Different arguments can still mean different engineering behavior.",
    );
    if (!(data.rule_proposals || []).length) {
      ruleProposals.append(
        node("p", "No enabled project rule matches this source."),
      );
    }
    (data.rule_proposals || []).forEach((rule) => {
      const row = node("div", null, "instruction-row");
      row.append(node("strong", rule.name));
      (rule.category_ids || []).forEach((id) =>
        row.append(chip(categoryName(id), "proposed")),
      );
      ruleProposals.append(row);
    });
    const related = section(root, "Linked source & groups");
    const links = node("div", null, "link-row");
    (data.related || []).forEach((r) =>
      links.append(link(r.label || r.id, r.id, r.view || "objects")),
    );
    (data.group_ids || []).forEach((id) => {
      const g = groups().find((g) => g.id === id);
      links.append(
        button(g?.name || id, () => {
          if (discard()) {
            switchView("groups", true);
            groupEditor(g);
          }
        }),
      );
    });
    related.append(
      links,
      button("Add this source to a group", () => groupPicker([s.id])),
    );
    if (!links.childNodes.length)
      related.prepend(node("p", "No linked engineering group yet."));
  }
  function renderValues(root, values) {
    const list = node("dl", null, "evidence-values");
    Object.entries(values || {})
      .filter(
        ([key]) =>
          ![
            "id",
            "locator",
            "structure",
            "instructions",
            "arguments",
            "text",
            "comment",
            "description",
          ].includes(key),
      )
      .forEach(([key, value]) => {
        list.append(
          node("dt", key.replaceAll("_", " ")),
          node(
            "dd",
            typeof value === "object" ? JSON.stringify(value, null, 2) : value,
          ),
        );
      });
    root.append(list);
  }
  function renderRungLogic(root, source, calculations) {
    const area = section(root, "Rung logic",
      "Follow the connected path from left to right. Parallel paths split and rejoin where shown. EN is the condition arriving at an instruction; ← stores a value. This shows source structure, not live state or an elapsed-time scale.");
    const tabs = node("div", null, "logic-tabs");
    tabs.setAttribute("role", "tablist");
    tabs.setAttribute("aria-label", "Rung display");
    const byId = new Map(source.instructions.map((i) => [i.id, i]));
    const occurrences = new Map((calculations.occurrences || []).map((c) => [c.id, c]));
    const nodes = new Map((calculations.nodes || []).map((n) => [n.id, n]));
    const panels = [], controls = [];
    const names = ["Rung flow", "Equations", "Branch structure", "Original text"];
    const activate = (index) => {
      panels.forEach((panel, i) => { panel.hidden = i !== index; });
      controls.forEach((control, i) => {
        control.setAttribute("aria-selected", String(i === index));
        control.tabIndex = i === index ? 0 : -1;
      });
    };
    names.forEach((name, index) => {
      const panel = node("div", null, "logic-panel");
      panel.id = `logic-${source.id}-${index}`;
      panel.setAttribute("role", "tabpanel");
      panel.tabIndex = 0;
      const control = button(name, () => activate(index));
      control.id = panel.id + "-tab";
      control.setAttribute("role", "tab");
      control.setAttribute("aria-controls", panel.id);
      panel.setAttribute("aria-labelledby", control.id);
      control.addEventListener("keydown", (event) => {
        const next = event.key === "ArrowRight" ? (index + 1) % names.length
          : event.key === "ArrowLeft" ? (index + names.length - 1) % names.length
          : event.key === "Home" ? 0 : event.key === "End" ? names.length - 1 : null;
        if (next !== null) { event.preventDefault(); activate(next); controls[next].focus(); }
      });
      panels.push(panel); controls.push(control); tabs.append(control);
    });
    area.append(tabs, ...panels);
    activate(0);
    if (calculations.status === "unavailable")
      area.prepend(node("p", "Saved expression structure could not be verified. CPT instructions retain their original expressions.", "warning-panel"));
    if (source.structure) {
      const positions = new Map(source.instructions.map((i, index) => [i.id, index + 1]));
      panels[0].append(window.PLCRungFlow.render(source, {
        instruction: (inst) => {
          const card = node("div", null, "flow-instruction");
          const equation = instructionEquation(inst, occurrences.get(inst.id), nodes);
          card.title = equation.label;
          if (state.view === 'map') ladderMap.attachHover?.(card, inst.id, equation.label);
          card.append(node("strong", `${positions.get(inst.id)} · ${inst.opcode}`, "flow-opcode"),
            node("span", equation.label, "flow-kind"));
          const display = node("div", null, "equation-display");
          display.append(equation.math);
          card.append(display, link("Instruction evidence ↗", inst.id));
          return card;
        },
        onInstruction: inst => popupWorkspace(inst.id, 'source'),
      }), button("Select individual instructions to group", () => activate(2), "text-button"));
      panels[1].append(renderEquationTree(source.structure, byId, occurrences, nodes, positions));
      const chosen = new Set();
      const scroll = node("div", null, "structure-scroll");
      scroll.append(renderStructure(source.structure, byId, chosen));
      panels[2].append(node("p", "Boxes and parallel paths preserve the captured structure. Select individual instructions here to group them."), scroll,
        button("Group checked instructions", () => {
          if (!chosen.size) { notify("Check one or more instruction boxes first."); return; }
          groupPicker([...chosen]);
        }));
    } else {
      panels[0].append(node("p", "A complete parsed structure is unavailable. Inspect the captured source below.", "warning-panel"), node("pre", source.text ?? "Source text unavailable."));
      panels[1].append(node("p", "No complete equation structure is available. Use Original text."));
      panels[2].append(node("p", "No complete branch structure is available. Use Original text."));
    }
    panels[3].append(node("pre", source.text ?? "Source text unavailable."));
  }
  function mathNode(tag, ...children) {
    const element = document.createElementNS("http://www.w3.org/1998/Math/MathML", tag);
    children.forEach((child) => element.append(typeof child === "string" ? document.createTextNode(child) : child));
    return element;
  }
  function mathAtom(text) {
    // Keep full source names, including underscores and array indices, literal.
    const element = mathNode("mi", String(text));
    element.setAttribute("mathvariant", "normal");
    return element;
  }
  function mathFence(child, left = "(", right = ")") {
    return mathNode("mrow", mathNode("mo", left), child, mathNode("mo", right));
  }
  function mathExpression(root, nodes, instructionId) {
    const seen = new Set();
    function visit(id, depth = 0, enclosed = false) {
      const current = nodes.get(id);
      if (!current || current.instruction_id !== instructionId || seen.has(id) || depth > 64 || seen.size >= 512)
        throw new Error("Incomplete expression structure");
      seen.add(id);
      const children = current.child_ids || [];
      const arity = { literal: 0, reference: 0, group: 1, unary: 1, binary: 2, function: 1 }[current.kind];
      if (arity === undefined || children.length !== arity) throw new Error("Unsupported expression node");
      const terms = children.map((child) => visit(child, depth + 1, current.kind === "group"));
      if (current.kind === "reference") return mathAtom(current.raw_text);
      if (current.kind === "literal") return mathNode("mn", current.raw_text);
      if (current.kind === "group") return mathFence(terms[0]);
      const op = current.operator;
      if (current.kind === "unary") {
        if (!["-", "NOT"].includes(op)) throw new Error("Unsupported unary operator");
        return mathNode("mrow", mathNode("mo", op === "-" ? "−" : op), terms[0]);
      }
      if (current.kind === "function") {
        if (["SQR", "SQRT"].includes(op)) return mathNode("msqrt", terms[0]);
        if (op === "ABS") return mathFence(terms[0], "|", "|");
        return mathNode("mrow", mathAtom(op), mathFence(terms[0]));
      }
      if (op === "/") return mathNode("mfrac", ...terms);
      if (op === "**") {
        // Fenced bases preserve Logix left-associative powers and signed bases.
        const left = nodes.get(children[0]);
        const base = ["binary", "unary"].includes(left.kind) ? mathFence(terms[0]) : terms[0];
        return mathNode("msup", base, terms[1]);
      }
      if (!["+", "-", "*", "MOD", "AND", "OR", "XOR"].includes(op))
        throw new Error("Unsupported binary operator");
      const expression = mathNode("mrow", terms[0], mathNode("mo", ({ "-": "−", "*": "×" })[op] || op), terms[1]);
      // Explicit grouping avoids changing precedence when a subtree is nested.
      return depth && !enclosed ? mathFence(expression) : expression;
    }
    return visit(root);
  }
  function instructionEquation(inst, occurrence, nodes) {
    const args = inst.arguments || [], opcode = inst.opcode.toUpperCase();
    const assign = (destination, expression) => mathNode("mrow", mathAtom(destination), mathNode("mo", "←"), expression);
    const call = () => mathNode("mrow", mathAtom(inst.opcode), mathFence(mathNode("mrow", ...args.flatMap((arg, i) =>
      [...(i ? [mathNode("mo", ",")] : []), mathNode("mtext", arg)]))));
    let expression, label = "Instruction", fallback = false;
    const valid = (count) => args.length === count && args.every((arg) => typeof arg === "string" && arg.trim());
    if (opcode === "CPT") {
      if (valid(2) && occurrence?.syntax_status === "parsed") {
        try { expression = assign(args[0], mathExpression(occurrence.root_node_id, nodes, inst.id)); }
        catch { fallback = true; }
      } else fallback = true;
      label = fallback ? "Original expression · typesetting unavailable" : "Calculation";
    } else if (["ADD", "SUB", "MUL", "DIV"].includes(opcode) && valid(3)) {
      const left = mathAtom(args[0]), right = mathAtom(args[1]);
      expression = assign(args[2], opcode === "DIV" ? mathNode("mfrac", left, right)
        : mathNode("mrow", left, mathNode("mo", { ADD: "+", SUB: "−", MUL: "×" }[opcode]), right));
      label = "Calculation";
    } else if (["ABS", "LN", "SQR", "SQRT"].includes(opcode) && valid(2)) {
      const value = mathAtom(args[0]);
      expression = assign(args[1], opcode === "ABS" ? mathFence(value, "|", "|")
        : opcode === "LN" ? mathNode("mrow", mathAtom("LN"), mathFence(value)) : mathNode("msqrt", value));
      label = "Calculation";
    } else if (["EQU", "NEQ", "LES", "LEQ", "GRT", "GEQ"].includes(opcode) && valid(2)) {
      expression = mathNode("mrow", mathAtom(args[0]), mathNode("mo", { EQU: "=", NEQ: "≠", LES: "<", LEQ: "≤", GRT: ">", GEQ: "≥" }[opcode]), mathAtom(args[1]));
      label = "Comparison";
    } else if (opcode === "MOV" && valid(2)) {
      expression = assign(args[1], mathAtom(args[0])); label = "Move value";
    } else if (opcode === "CLR" && valid(1)) {
      expression = assign(args[0], mathNode("mn", "0")); label = "Clear value";
    } else if (["XIC", "XIO"].includes(opcode) && valid(1)) {
      const condition = opcode === "XIC" ? mathAtom(args[0])
        : mathNode("mrow", mathNode("mo", "¬"), mathAtom(args[0]));
      expression = mathNode("mrow", mathAtom("EN"), mathNode("mo", "∧"), condition);
      label = opcode === "XIC" ? "Pass when the bit is true" : "Pass when the bit is false";
    } else if (opcode === "OTE" && valid(1)) {
      expression = assign(args[0], mathAtom("EN")); label = "Output follows the incoming condition";
    } else if (["OTL", "OTU"].includes(opcode) && valid(1)) {
      expression = mathNode("mrow", mathAtom("EN"), mathNode("mo", "⇒"),
        mathAtom(opcode === "OTL" ? "SET" : "RESET"), mathFence(mathAtom(args[0])));
      label = opcode === "OTL" ? "Latch when enabled" : "Unlatch when enabled";
    } else if (["TON", "TOF", "RTO", "ONS", "OSR", "OSF", "CTU", "CTD"].includes(opcode)) {
      label = { TON: "On-delay timer", TOF: "Off-delay timer", RTO: "Retentive timer",
        ONS: "One-shot storage", OSR: "Rising-edge one-shot", OSF: "Falling-edge one-shot",
        CTU: "Count up", CTD: "Count down" }[opcode];
    }
    const math = mathNode("math", expression || call());
    math.setAttribute("display", "block");
    math.setAttribute("aria-label", `${inst.opcode}(${args.join(", ")})`);
    return { math, label, fallback };
  }
  function renderEquationTree(tree, byId, occurrences, nodes, positions, depth = 0) {
    if (!tree || depth > 140) return node("p", "Structure display limit reached. Use Original text.", "warning-panel");
    if (tree.kind === "sequence") {
      const sequence = node("div", null, "equation-sequence");
      if (!tree.items?.length) sequence.append(node("p", "Empty branch path", "empty-leg"));
      (tree.items || []).forEach((item) => sequence.append(renderEquationTree(item, byId, occurrences, nodes, positions, depth + 1)));
      return sequence;
    }
    if (tree.kind === "branch") {
      const branch = node("div", null, "equation-branch");
      branch.append(node("span", "PARALLEL PATHS", "equation-branch-label"));
      (tree.legs || []).forEach((leg, index) => {
        const path = node("div", null, "equation-path");
        path.append(node("strong", "Path " + (index + 1)), renderEquationTree(leg, byId, occurrences, nodes, positions, depth + 1));
        branch.append(path);
      });
      return branch;
    }
    const inst = tree.kind === "instruction" && byId.get(tree.instruction_id);
    if (!inst) return node("p", "Instruction structure unavailable. Use Original text.", "warning-panel");
    const row = node("div", null, "equation-row"), heading = node("div", null, "equation-heading");
    const rendered = instructionEquation(inst, occurrences.get(inst.id), nodes);
    heading.append(node("strong", `${positions.get(inst.id)} · ${inst.opcode}`), node("span", rendered.label), link("Evidence ↗", inst.id));
    const display = node("div", null, "equation-display");
    display.append(rendered.math);
    row.append(heading, display);
    return row;
  }
  function renderStructure(tree, byId, chosen, depth = 0) {
    if (depth > 140)
      return node(
        "div",
        "Structure depth exceeds display limit. Use full text.",
        "unknown-node",
      );
    if (tree.kind === "sequence") {
      const sequence = node("div", null, "sequence");
      if (!tree.items?.length)
        sequence.append(node("span", "Empty branch path", "empty-leg"));
      else
        tree.items.forEach((item) =>
          sequence.append(renderStructure(item, byId, chosen, depth + 1)),
        );
      return sequence;
    }
    if (tree.kind === "branch") {
      const branch = node("div", null, "branch");
      branch.setAttribute("aria-label", "Parallel source branch");
      (tree.legs || []).forEach((leg) =>
        branch.append(renderStructure(leg, byId, chosen, depth + 1)),
      );
      return branch;
    }
    if (tree.kind === "instruction") {
      const inst = byId.get(tree.instruction_id);
      if (!inst)
        return node(
          "div",
          "Instruction evidence unavailable: " + tree.instruction_id,
          "unknown-node",
        );
      const box = node("div", null, "instruction-box");
      box.append(node("strong", inst.opcode));
      (inst.arguments || []).forEach((arg, index) =>
        box.append(node("span", index + 1 + ": " + arg, "argument mono")),
      );
      const check = node("input");
      check.type = "checkbox";
      check.addEventListener("change", () =>
        check.checked ? chosen.add(inst.id) : chosen.delete(inst.id),
      );
      const label = field("Select fragment", check);
      box.append(label, link("Instruction evidence ↗", inst.id));
      return box;
    }
    return node(
      "div",
      "Unrecognized structure node: " + (tree.kind || "unknown"),
      "unknown-node",
    );
  }
  function renderInstructions(root, instructions, operands) {
    const area = section(
      root,
      "Every instruction & operand",
      "Argument order and text are retained. Evidence links open the full analysis in a separate tab.",
    );
    const list = node("div", null, "instruction-list");
    instructions.forEach((inst, index) => {
      const card = node("div", null, "instruction-row");
      const header = node("header");
      header.append(
        node("strong", index + 1 + ". " + inst.opcode),
        link("Evidence ↗", inst.id),
      );
      card.append(header);
      const args = node("ol");
      (inst.arguments || []).forEach((value, position) => {
        const row = node("li");
        const operand = operands.find(
          (o) =>
            o.instruction_id === inst.id &&
            (o.position === position || o.argument_index === position),
        );
        row.append(node("span", value));
        if (operand?.id) {
          row.append(
            document.createTextNode(" · "),
            link("Binding evidence ↗", operand.id),
          );
        }
        (operand?.target_ids || []).forEach((id) =>
          row.append(
            document.createTextNode(" · "),
            link("Source tag ↗", id, "objects"),
          ),
        );
        args.append(row);
      });
      card.append(
        args,
        button(
          "Review this instruction",
          () => run(() => openSource(inst.id, state.detailTarget)),
          "text-button",
        ),
      );
      list.append(card);
    });
    area.append(list);
  }
  function categoryPicker(selected = []) {
    const container = node("div", null, "category-options");
    categories().forEach((c) => {
      const check = node("input");
      check.type = "checkbox";
      check.value = c.id;
      check.checked = selected.includes(c.id);
      const label = field(c.name, check);
      label.className = "check-label";
      container.append(label);
    });
    if (!categories().length)
      container.append(node("p", "Create a category with Manage categories."));
    return {
      element: container,
      values: () =>
        [...container.querySelectorAll("input:checked")].map((n) => n.value),
    };
  }
  function renderEditor(
    root,
    id,
    review,
    sourceRevision = state.project.revision,
  ) {
    // A later global refresh must never make an old form appear current.
    const renderedRevision = sourceRevision;
    const form = node("form", null, "review-form");
    const picker = categoryPicker(review.category_ids || []);
    form.append(node("h4", "Reviewed categories"), picker.element);
    const status = select(
      Object.entries(statusNames),
      review.status || "unreviewed",
    );
    form.append(field("Review status", status));
    const properties = node("details");
    properties.append(
      node(
        "summary",
        "Engineering properties (" +
          Object.keys(review.fields || {}).length +
          " saved)",
      ),
      node(
        "p",
        "Use these fields for engineering names, purpose, equations, connections, alarm behavior, or your own properties. Original source facts are not overwritten.",
      ),
    );
    const fields = node("div");
    const standard = [
      "Name",
      "Description",
      "Purpose",
      "Equation",
      "PV",
      "SP",
      "Output",
      "Alarm behavior",
      "Target class",
    ];
    const keys = Object.keys(review.fields || {});
    const fieldNames = [...new Set([...keys, ...standard])];
    fieldNames.forEach((key) =>
      addProperty(fields, key, review.fields?.[key] ?? ""),
    );
    properties.append(
      fields,
      button("Add a property", () => {
        addProperty(fields, "", "");
        markDirty();
      }),
    );
    form.append(properties);
    const saveRow = node("div", null, "save-row");
    const save = node("button", "Save review", "primary");
    save.type = "submit";
    const saveState = node("span", "Saved in project", "save-state");
    saveRow.append(
      save,
      saveState,
      button("Add to group", () => groupPicker([id])),
    );
    form.append(saveRow);
    function markDirty() {
      state.dirty = true;
      saveState.textContent = "Unsaved changes";
    }
    form.addEventListener("input", markDirty);
    form.addEventListener("change", markDirty);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const values = Object.create(null);
      let error = "";
      fields.querySelectorAll(".field-row").forEach((row) => {
        const key = row.querySelector("input").value.trim(),
          value = row.querySelector("textarea").value;
        if (!key && value) error = "Give every filled property a name.";
        if (key && value) {
          if (Object.hasOwn(values, key))
            error = "Property names must be unique: " + key;
          values[key] = value;
        }
      });
      if (error) {
        notify(error, true);
        return;
      }
      const controls = [
        ...form.querySelectorAll("button, input, select, textarea"),
      ];
      controls.forEach((control) => (control.disabled = true));
      const result = await run(async () => {
        await mutate(
          {
            op: "review",
            source_ids: [id],
            category_ids: picker.values(),
            status: status.value,
            fields: values,
          },
          renderedRevision,
        );
        notify(
          "Review saved. Original source and parser proposals are unchanged.",
        );
        await openSource(id, state.detailTarget, true);
        if (state.view === "rungs") await loadRungs();
      });
      if (result === null)
        controls.forEach((control) => (control.disabled = false));
    });
    root.append(form);
    if (state.source?.source?.structure)
      root.append(
        button(
          "Create a reusable category rule from this pattern",
          () => ruleDialog(id),
          "text-button",
        ),
      );
  }
  function addProperty(container, key, value) {
    const row = node("div", null, "field-row");
    const keyInput = input(key, "Property name");
    keyInput.setAttribute("aria-label", "Property name");
    const valueInput = node("textarea");
    valueInput.value = String(value ?? "");
    valueInput.rows = 1;
    valueInput.setAttribute("aria-label", (key || "Property") + " value");
    const remove = button("×", () => {
      row.remove();
      state.dirty = true;
      container
        .closest("form")
        ?.dispatchEvent(new Event("input", { bubbles: true }));
    });
    remove.setAttribute("aria-label", "Remove " + (key || "property"));
    row.append(keyInput, valueInput, remove);
    container.append(row);
  }
  let modalSave = null,
    modalDirty = false,
    modalBusy = false,
    modalRevision = null;
  function modal(title, build, onSave, saveLabel = "Save") {
    $("dialog-title").textContent = title;
    clear($("dialog-body"));
    $("dialog-error").hidden = true;
    $("dialog-save").textContent = saveLabel;
    $("dialog-save").hidden = !onSave;
    $("dialog-save").disabled = false;
    $("dialog-cancel").textContent = onSave ? "Cancel" : "Close";
    modalSave = onSave;
    modalDirty = false;
    modalRevision = state.project.revision;
    build($("dialog-body"));
    $("dialog").showModal();
  }
  function closeModal() {
    if (state.saving || modalBusy) {
      notify("Wait for the current operation to finish.");
      return;
    }
    if (
      modalDirty &&
      !window.confirm("Discard the unsaved changes in this dialog?")
    )
      return;
    $("dialog").close();
    modalDirty = false;
    modalRevision = null;
  }
  function bulkReview() {
    if (!discard()) return;
    let picker, status, replace;
    modal(
      "Update " + state.selected.size + " selected sources",
      (body) => {
        body.append(
          node(
            "p",
            "Only the options you enable are changed. Individual engineering properties are preserved.",
          ),
        );
        replace = node("input");
        replace.type = "checkbox";
        body.append(
          field(
            "Replace reviewed categories on every selected source",
            replace,
          ),
        );
        picker = categoryPicker();
        body.append(picker.element);
        status = select([
          ["", "Keep each status"],
          ...Object.entries(statusNames),
        ]);
        body.append(field("Review status", status));
      },
      async () => {
        const command = { op: "review", source_ids: [...state.selected] };
        if (replace.checked) command.category_ids = picker.values();
        if (status.value) command.status = status.value;
        if (!replace.checked && !status.value)
          throw new Error("Choose a category replacement or status change.");
        await mutate(command);
        await loadRungs();
        if (state.source)
          await openSource(state.source.source.id, state.detailTarget, true);
        notify(
          "Saved changes to " + state.selected.size + " selected sources.",
        );
      },
    );
  }
  function categoryManager() {
    if (!discard()) return;
    modal(
      "Manage category names",
      (body) => {
        body.append(
          node(
            "p",
            "Categories are project labels. Renaming one updates its label everywhere; existing memberships keep their identities.",
          ),
        );
        categories().forEach((c) => {
          const row = node("div", null, "category-edit"),
            name = input(c.name);
          name.setAttribute("aria-label", "Category name");
          const save = button("Rename", () =>
            run(async () => {
              if (!name.value.trim())
                throw new Error("Category name cannot be empty.");
              await mutate({
                op: "category",
                id: c.id,
                name: name.value.trim(),
              });
              modalRevision = state.project.revision;
              if (state.source)
                await openSource(
                  state.source.source.id,
                  state.detailTarget,
                  true,
                );
              notify("Category renamed.");
              save.disabled = true;
              modalDirty = false;
            }),
          );
          name.addEventListener("input", () => (save.disabled = false));
          row.append(name, save);
          body.append(row);
        });
        const row = node("div", null, "category-edit"),
          name = input("", "New category name");
        name.setAttribute("aria-label", "New category name");
        row.append(
          name,
          button("Create", () =>
            run(async () => {
              if (!name.value.trim()) throw new Error("Enter a category name.");
              await mutate({ op: "category", name: name.value.trim() });
              if (state.source)
                await openSource(
                  state.source.source.id,
                  state.detailTarget,
                  true,
                );
              modalDirty = false;
              $("dialog").close();
              categoryManager();
            }),
          ),
        );
        body.append(row);
      },
      null,
    );
  }
  function groupPicker(memberIds) {
    if (!discard()) return;
    let groupSelect, name;
    modal(
      "Add source membership",
      (body) => {
        body.append(
          node(
            "p",
            memberIds.length +
              " source records will be added. Existing memberships stay in place; a source can belong to several groups.",
          ),
        );
        groupSelect = select([
          ["", "Create a new group"],
          ...groups().map((g) => [g.id, g.name]),
        ]);
        name = input("", "For example: transfer pump permissives");
        body.append(
          field("Engineering group", groupSelect),
          field("New group name", name),
        );
        groupSelect.addEventListener(
          "change",
          () => (name.disabled = Boolean(groupSelect.value)),
        );
      },
      async () => {
        const old = groups().find((g) => g.id === groupSelect.value);
        if (!old && !name.value.trim()) throw new Error("Enter a group name.");
        const command = {
          op: "group",
          name: old?.name || name.value.trim(),
          member_ids: [...new Set([...(old?.member_ids || []), ...memberIds])],
        };
        if (old) command.id = old.id;
        await mutate(command);
        if (state.source)
          await openSource(state.source.source.id, state.detailTarget, true);
        notify("Group membership saved.");
      },
    );
  }
  function renderGroups() {
    const root = $("group-list");
    clear(root);
    groups().forEach((g) => {
      const card = node("article", null, "card");
      card.append(
        node("h2", g.name),
        node("p", (g.member_ids || []).length + " linked source records"),
      );
      const labels = new Map((state.project.classification_categories || []).map(c => [c.id, c.label || c.name || c.id]));
      const classifications = node("div", null, "classification-chips");
      (g.function_categories || []).forEach(id => classifications.append(chip(labels.get(id) || id)));
      classifications.append(chip(window.PLCClassification.migrationLabel(g.migration_status || "unreviewed"), "classification-decision"));
      card.append(classifications);
      if (g.migration_note) card.append(node("p", g.migration_note));
      if (g.needs_revalidation) card.append(node("p", "Source evidence changed. Recheck the saved classification and migration decision. This group remains in scope until reviewed.", "warning-panel"));
      if (g.unresolved_member_ids?.length)
        card.append(
          node(
            "p",
            g.unresolved_member_ids.length +
              " older-source memberships need correspondence.",
            "warning-panel",
          ),
        );
      const disclosure = node("details"), members = node("div", null, "members");
      const controls = node("div", null, "pagination");
      disclosure.append(node("summary", "Linked source records"), members, controls);
      const sourceMembers = g.members || g.member_ids || [];
      let memberPage = 0, built = false;
      function paintMembers() {
        clear(members); clear(controls);
        const start = memberPage * 50, end = Math.min(start + 50, sourceMembers.length);
        sourceMembers.slice(start, end).forEach(m => {
          const id = typeof m === "string" ? m : m.id;
          members.append(button(typeof m === "string" ? m : m.path || m.label || id, () => run(async () => {
            if (!discard()) return;
            const view = typeof m !== "string" && m.kind === "rung" ? "rungs" : "objects";
            switchView(view, true);
            await openSource(id, view === "rungs" ? "rung-detail" : "object-detail", true);
          })));
        });
        const previous = button("Previous members", () => {memberPage -= 1; paintMembers();});
        const next = button("Next members", () => {memberPage += 1; paintMembers();});
        previous.disabled = memberPage === 0; next.disabled = end >= sourceMembers.length;
        controls.append(previous, node("span", sourceMembers.length ? `${start + 1}–${end} of ${sourceMembers.length}` : "No members"), next);
      }
      disclosure.addEventListener("toggle", () => {
        if (disclosure.open && !built) {built = true; paintMembers();}
      });
      card.append(disclosure);
      const actions = node("div", null, "actions");
      actions.append(button("Edit categories, migration & members", () => groupEditor(g)));
      card.append(actions);
      root.append(card);
    });
    if (!groups().length)
      root.append(
        node(
          "div",
          "Create a group from selected rungs or checked instruction fragments. Groups capture your engineering interpretation without changing the source.",
          "card",
        ),
      );
    renderRules(root);
  }
  function groupEditor(group = {}) {
    if (!discard()) return;
    let name, classificationFields;
    const members = new Set(group.member_ids || []);
    modal(
      group.id ? "Edit engineering group" : "New engineering group",
      (body) => {
        name = input(group.name || "", "Group name");
        classificationFields = window.PLCClassification.groupFields(group, state.project.classification_categories || []);
        body.append(
          field("Name", name),
          classificationFields.element,
          node(
            "p",
            "Remove memberships below, or add source records through the Rungs and Tags views. Removing membership does not delete source evidence.",
          ),
        );
        const container = node("div"), pages = node("div", null, "pagination");
        const memberLabels = new Map((group.members || []).map(m => [m.id, m.path || m.label || m.id]));
        let page = 0;
        function paint() {
          clear(container); clear(pages);
          page = Math.min(page, Math.max(0, Math.ceil(members.size / 50) - 1));
          const start = page * 50, end = Math.min(start + 50, members.size);
          [...members].slice(start, end).forEach((id) => {
            const row = node("div", null, "member-row");
            row.append(
              node("span", memberLabels.get(id) || id),
              button("Remove", () => {
                members.delete(id);
                modalDirty = true;
                paint();
              }),
            );
            container.append(row);
          });
          const previous = button("Previous members", () => {page -= 1; paint();});
          const next = button("Next members", () => {page += 1; paint();});
          previous.disabled = page === 0; next.disabled = end >= members.size;
          pages.append(previous, node("span", members.size ? `${start + 1}–${end} of ${members.size}` : "No members"), next);
          if (!members.size)
            container.append(
              node(
                "p",
                "No members yet. Save the group, then select source records to add.",
              ),
            );
        }
        paint();
        body.append(container, pages);
      },
      async () => {
        if (!name.value.trim()) throw new Error("Enter a group name.");
        const command = {
          op: "group",
          name: name.value.trim(),
          member_ids: [...members],
          ...classificationFields.values(),
        };
        if (group.id) command.id = group.id;
        await mutate(command);
        notify("Engineering group saved.");
      },
    );
  }
  function renderRules(root) {
    const area = node("article", null, "card");
    area.append(
      node("h2", "Project category rules"),
      node(
        "p",
        "A rule proposes categories for the same opcode and branch pattern. Arguments and process conditions may differ. Matching a rule never confirms a rung.",
      ),
    );
    const rules = state.project.rules || [];
    rules.forEach((rule) => {
      const row = node("div", null, "instruction-row");
      row.append(
        node("strong", rule.name),
        node("p", (rule.category_ids || []).map(categoryName).join(", ")),
        chip(
          rule.enabled ? "Enabled" : "Disabled",
          rule.enabled ? "reviewed" : "",
        ),
        button("Edit rule", () => editRule(rule)),
        button(rule.enabled ? "Disable rule" : "Enable rule", () =>
          run(async () => {
            if (!discard()) return;
            await mutate({
              op: "rule",
              id: rule.id,
              name: rule.name,
              source_id: rule.source_id,
              category_ids: rule.category_ids,
              enabled: !rule.enabled,
            });
            notify("Rule updated. Reviewed classifications were preserved.");
          }),
        ),
      );
      area.append(row);
    });
    if (!rules.length)
      area.append(
        node(
          "p",
          "Open a rung and use Create a reusable category rule after checking its pattern.",
        ),
      );
    root.append(area);
  }
  function editRule(rule) {
    if (!discard()) return;
    let name, picker, enabled;
    modal(
      "Edit project category rule",
      (body) => {
        name = input(rule.name);
        picker = categoryPicker(rule.category_ids || []);
        enabled = node("input");
        enabled.type = "checkbox";
        enabled.checked = Boolean(rule.enabled);
        body.append(
          field("Rule name", name),
          node(
            "p",
            "This rule uses the saved example's opcode and branch pattern. Change the proposed categories here; existing reviewed decisions remain separate and affected decisions may need revalidation.",
          ),
          picker.element,
          field("Enable this rule", enabled),
        );
      },
      async () => {
        if (!name.value.trim()) throw new Error("Enter a rule name.");
        if (!picker.values().length)
          throw new Error("Choose at least one proposed category.");
        await mutate({
          op: "rule",
          id: rule.id,
          name: name.value.trim(),
          source_id: rule.source_id,
          category_ids: picker.values(),
          enabled: enabled.checked,
        });
        notify(
          "Project rule updated. Check Changes & reconciliation for decisions requiring revalidation.",
        );
      },
    );
  }
  async function ruleDialog(sourceId) {
    if (!discard()) return;
    await run(async () => {
      const matches = await api(
        "/api/rule-matches?source_id=" + encodeURIComponent(sourceId),
      );
      let name, picker;
      modal(
        "Create a reusable category rule",
        (body) => {
          body.append(
            node(
              "p",
              "This rule matches the exact opcode and branch pattern, ignoring argument values. It proposes categories without approving sources. Saved categories and properties stay intact; matching saved reviews are marked for revalidation.",
            ),
          );
          name = input("", "Descriptive rule name");
          picker = categoryPicker(state.source?.review?.category_ids || []);
          body.append(
            field("Rule name", name),
            picker.element,
            node(
              "h3",
              Number(matches.total || 0).toLocaleString() +
                " matching rungs in the current source",
            ),
          );
          const list = node("div", null, "member-results");
          (matches.items || []).forEach((m) => {
            const card = node("div", null, "instruction-row");
            card.append(link(m.path || m.id, m.id), node("pre", m.text || ""));
            list.append(card);
          });
          body.append(list);
        },
        async () => {
          if (!name.value.trim()) throw new Error("Enter a rule name.");
          if (!picker.values().length)
            throw new Error("Choose at least one proposed category.");
          await mutate({
            op: "rule",
            name: name.value.trim(),
            source_id: sourceId,
            category_ids: picker.values(),
            enabled: true,
          });
          notify(
            "Project category rule saved. Matches remain proposals; affected saved reviews need revalidation.",
          );
          await openSource(sourceId, state.detailTarget, true);
        },
      );
    });
  }
  function renderChanges() {
    const root = $("reconciliation");
    clear(root);
    const pending = state.project.pending_reviews || [];
    if (pending.length) {
      const banner = node("div", null, "warning-panel");
      banner.append(
        node("h2", pending.length + " saved decisions need reconciliation"),
        node(
          "p",
          "A changed export gets new source identities. Prior decisions remain in history. Compare the old source with a proposed replacement before explicitly copying a decision.",
        ),
      );
      pending.forEach((p) => {
        const card = node("div", null, "instruction-row");
        card.append(
          node("strong", p.path || p.source_id),
          node(
            "p",
            (
              p.revalidation_reasons ||
              p.review?.revalidation_reasons ||
              []
            ).join(", ") || "Older or changed source evidence",
          ),
          button(
            p.review?.active
              ? "Review current evidence"
              : "Compare & reconnect",
            () => {
              if (p.review?.active) {
                if (!discard()) return;
                switchView("rungs", true);
                run(() => openSource(p.source_id, "rung-detail", true));
              } else rebindDialog(p);
            },
          ),
        );
        banner.append(card);
      });
      root.append(banner);
    } else
      root.append(
        node("p", "No pending source correspondence is reported.", "card"),
      );
    const history = $("history");
    clear(history);
    (state.project.history || [])
      .slice()
      .sort((a, b) => Number(b.revision) - Number(a.revision))
      .forEach((h) => {
        const row = node("div", null, "history-row");
        row.append(
          node(
            "time",
            h.created_utc || h.created_at || h.timestamp || h.at || "",
          ),
        );
        const body = node("div");
        body.append(
          node(
            "strong",
            h.summary ||
              h.description ||
              h.operation ||
              h.op ||
              "Project change",
          ),
          node(
            "p",
            "Revision " +
              (h.revision ?? h.id ?? "") +
              (h.author ? " · " + h.author : ""),
          ),
        );
        const detail = node("details");
        detail.append(
          node("summary", "Change details"),
          node("pre", JSON.stringify(h, null, 2)),
        );
        body.append(detail);
        row.append(body);
        history.append(row);
      });
    if (!(state.project.history || []).length)
      history.append(node("p", "Your saved changes will appear here.", "card"));
  }
  function rebindDialog(old) {
    if (!discard()) return;
    let selected = "",
      query,
      sourceType;
    modal(
      "Compare and reconnect saved decision",
      (body) => {
        body.append(
          node("h3", "Previous source"),
          node("p", old.path || old.source_id),
          node("pre", JSON.stringify(old.review || {}, null, 2)),
          node(
            "p",
            "Choose the corresponding current source. This copies the prior decision as Needs review and retains its history. It does not prove equivalence.",
          ),
        );
        const previous = node(
          "div",
          "Loading previous source evidence…",
          "instruction-row",
        );
        body.append(previous);
        run(async () => {
          if (!old.run_id) {
            previous.textContent =
              "Previous source run is unavailable. Do not infer correspondence from an identifier alone.";
            return;
          }
          const evidence = await api(
            "/api/source?" +
              new URLSearchParams({ id: old.source_id, run_id: old.run_id }),
          );
          clear(previous);
          previous.append(
            node("h3", "Original source retained with this decision"),
            node("p", evidence.path),
          );
          const source = evidence.source || {};
          if (source.comment || source.description) {
            const prose = node("div", null, "translation-pair");
            const key = source.comment ? "comment" : "description";
            previous.append(prose);
            window.PLCTranslation.renderProse(prose, source[key], null, translations.mode());
            if (translations.mode() !== "original") {
              run(async () => {
                const wording = await api("/api/translation?" + new URLSearchParams({source_id: old.source_id, run_id: old.run_id}));
                if (prose.isConnected) window.PLCTranslation.renderProse(prose, source[key], wording.fields?.[key], wording.presentation_mode);
              });
            }
          }
          previous.append(
            node(
              "pre",
              source.text ??
                JSON.stringify(source.attributes || source, null, 2),
            ),
          );
          if (source.structure) {
            const scroll = node("div", null, "structure-scroll");
            const structure = renderStructure(
              source.structure,
              new Map((source.instructions || []).map((i) => [i.id, i])),
              new Set(),
            );
            // Historical evidence is read-only; active-source links would point
            // at the wrong snapshot, and fragment checks cannot be edited here.
            structure
              .querySelectorAll("a, label")
              .forEach((control) => control.remove());
            scroll.append(structure);
            previous.append(scroll);
          }
        });
        query = input("", "Search the current source");
        sourceType = select([
          ["rungs", "Rungs"],
          ["objects", "Tags and source objects"],
          ["instructions", "Individual instructions"],
        ]);
        body.append(
          field("Replacement type", sourceType),
          field("Find replacement source", query),
        );
        const results = node("div", null, "member-results");
        body.append(results);
        const search = debounce(() =>
          run(async () => {
            const parameters = new URLSearchParams({
              query: query.value,
              page: "1",
            });
            if (sourceType.value === "instructions")
              parameters.set("kind", "instruction");
            const found = await api(
              (sourceType.value === "rungs" ? "/api/rungs?" : "/api/objects?") +
                parameters,
            );
            clear(results);
            results.append(
              node("p", found.total + " matches; refine the search if needed."),
            );
            (found.items || []).forEach((r) => {
              const row = node("div", null, "instruction-row"),
                radio = node("input");
              radio.type = "radio";
              radio.name = "replacement";
              radio.value = r.id;
              radio.checked = selected === r.id;
              radio.addEventListener("change", () => (selected = r.id));
              row.append(
                field(r.path, radio),
                node("pre", r.text || (r.description_is_code ? r.description : "") || ""),
                link(
                  "Inspect full evidence ↗",
                  r.id,
                  sourceType.value === "objects" ? "objects" : "ladder",
                ),
              );
              if (r.comment || (r.description && !r.description_is_code)) {
                const key = r.comment ? "comment" : "description";
                const prose = node("div", null, "source-preview");
                window.PLCTranslation.renderProse(prose, r[key], r.wording?.[key], found.presentation_mode);
                row.append(prose);
              }
              results.append(row);
            });
          }),
        );
        query.addEventListener("input", search);
        sourceType.addEventListener("change", () => {
          selected = "";
          search();
        });
        search();
      },
      async () => {
        if (!selected)
          throw new Error(
            "Select a current source after comparing the evidence.",
          );
        await mutate({
          op: "rebind",
          from_id: old.source_id || old.id,
          to_id: selected,
        });
        notify("Prior decision copied and marked Needs review.");
      },
    );
  }
  function renderGuide() {
    const root = $("guide-content");
    clear(root);
    root.className = "guide";
    const steps = [
      [
        "source",
        "Confirm the source",
        "Check the source name and rung count in the sidebar. Choose analysis run if this is not the export you intend to review.",
        "Choose analysis run",
        importDialog,
      ],
      [
        "inspect",
        "Inspect one complete rung",
        "Open Rungs. Select a program and routine, then a rung title. Drag the divider to give the source pane more width. Equation text starts at 75%; adjust it above the list. Rung flow connects instructions from left to right, with parallel paths that split and rejoin. Equations shows formatted calculations; Original text preserves the exact source. Comment language in the sidebar adds local English wording alongside the original after one-time setup.",
        "Open rungs",
        () => switchView("rungs"),
      ],
      [
        "map",
        "Explore the whole ladder",
        "Open Ladder map. Count tiles cover every captured rung; click one to zoom in, or search and filter by routine or function. Drag the background to pan and drag a rung to arrange this view. Select a rung for its complete branches and equations; hover or focus for block information. Click a signal to find all its recorded rungs. Drag the divider to resize the inspector, or use Map only. Pop out map, selected source or connections into separate windows for other monitors. Save before switching, then use Refresh saved data in other windows to load your changes.",
        "Open ladder map",
        () => switchView("map"),
      ],
      [
        "trace",
        "Follow inputs and outputs",
        "From a rung, select Explore inputs & outputs. The connection map shows upstream writer rungs and downstream readers through their shared signals. Click a signal to expand its fan-out, or a neighboring rung to keep tracing. Back in trace retraces your steps. Check multiple-writer warnings and coverage notes before interpreting an absent connection.",
        "Open connection map",
        () => switchView("connections"),
      ],
      [
        "categorize",
        "Save a classification",
        "Under Your engineering review, select one or more categories. Set Needs review while uncertain or Confirmed when checked. Save review writes to the project database.",
        "Manage categories",
        categoryManager,
      ],
      [
        "group",
        "Describe the engineering object",
        "Add a whole rung or selected instruction fragments to an engineering group. Several rungs can form one object; one rung can contribute to several groups.",
        "Open groups",
        () => switchView("groups"),
      ],
      [
        "verify",
        "Check persistence and history",
        "Save, select another rung, and return. Your reviewed categories and properties should remain. Changes & reconciliation shows what changed and offers undo.",
        "View changes",
        () => switchView("changes"),
      ],
      [
        "rerun",
        "Reuse and reconcile",
        "Import a new finalized analysis run. Unchanged-source decisions stay separate from new proposals. For changed exports, reconnect prior decisions explicitly and recheck them.",
        "Choose analysis run",
        importDialog,
      ],
    ];
    let progress = {};
    try {
      progress = JSON.parse(
        localStorage.getItem("plc-workspace-guide-v1") || "{}",
      );
    } catch {}
    steps.forEach(([id, title, description, action, callback], index) => {
      const card = node("article", null, "guide-step"),
        check = node("input");
      check.type = "checkbox";
      check.id = "guide-" + id;
      check.checked = progress[id] === true;
      check.addEventListener("change", () => {
        progress[id] = check.checked;
        try {
          localStorage.setItem(
            "plc-workspace-guide-v1",
            JSON.stringify(progress),
          );
        } catch {
          notify(
            "Guide checkmarks cannot be stored in this browser. Engineering edits still save to the project database.",
          );
        }
      });
      const body = node("div"),
        label = node("label", index + 1 + ". " + title);
      label.htmlFor = check.id;
      body.append(label, node("p", description), button(action, callback));
      card.append(check, body);
      root.append(card);
    });
    root.append(
      node(
        "p",
        "These checkmarks track your learning in this browser. They do not approve engineering data. Back up project creates a recoverable copy of the project database; keep original source exports and analysis runs with your private project.",
      ),
    );
  }
  async function importDialog() {
    if (!discard()) return;
    await run(async () => {
      const result = await api("/api/runs");
      let chosen, path;
      modal(
        "Choose your analysis run",
        (body) => {
          body.append(
            node(
              "p",
              "Select a finalized private analysis run containing source inventory and review data. Import reads that saved result; it does not pull from Git or upload source data.",
            ),
          );
          chosen = select([
            ["", "Choose a run…"],
            ...(result.items || []).map((r) => [r.path, r.label || r.path]),
          ]);
          path = input("", "Or enter a local finalized run directory");
          body.append(
            field("Available local runs", chosen),
            field("Run directory", path),
          );
          chosen.addEventListener("change", () => (path.value = chosen.value));
          body.append(
            node(
              "p",
              "Existing review decisions are retained. A changed source snapshot requires explicit correspondence before previous decisions can apply.",
            ),
          );
        },
        async () => {
          if (!path.value.trim())
            throw new Error("Choose a run or enter its local directory.");
          await api("/api/import", {
            path: path.value.trim(),
            expected_revision: modalRevision,
          });
          state.dirty = false;
          state.source = null;
          state.connectionRung = null;
          clear($("connection-map"));
          state.selected.clear();
          state.routine = "";
          state.page = 1;
          state.objectPage = 1;
          [
            "rung-search",
            "category-filter",
            "status-filter",
            "object-search",
            "object-kind",
            "routine-search",
          ].forEach((id) => ($(id).value = ""));
          await refresh();
          clear($("rung-detail"));
          $("rung-detail").append(
            node(
              "div",
              "Source imported. Choose a rung to inspect its evidence and saved review.",
              "empty",
            ),
          );
          clear($("object-detail"));
          $("object-detail").append(
            node(
              "div",
              "Select a source object from the imported run.",
              "empty",
            ),
          );
          switchView("rungs", true);
          notify(
            "Analysis imported. Verify the source name and total rung count in the sidebar.",
          );
        },
        "Import analysis",
      );
    });
  }
  $("dialog-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!modalSave) return;
    modalBusy = true;
    const controls = [
      ...$("dialog").querySelectorAll("button, input, select, textarea"),
    ];
    controls.forEach((control) => (control.disabled = true));
    $("dialog-error").hidden = true;
    try {
      await modalSave();
      modalDirty = false;
      modalRevision = null;
      $("dialog").close();
    } catch (error) {
      $("dialog-error").textContent = error.message;
      $("dialog-error").hidden = false;
    } finally {
      modalBusy = false;
      controls.forEach((control) => (control.disabled = false));
    }
  });
  $("dialog-body").addEventListener("input", () => (modalDirty = true));
  $("dialog-body").addEventListener("change", () => (modalDirty = true));
  $("dialog-close").addEventListener("click", closeModal);
  $("dialog-cancel").addEventListener("click", closeModal);
  $("dialog").addEventListener("cancel", (event) => {
    event.preventDefault();
    closeModal();
  });
  document
    .querySelectorAll("#navigation button")
    .forEach((n) =>
      n.addEventListener("click", () => switchView(n.dataset.view)),
    );
  $("rung-search").addEventListener(
    "input",
    debounce(() => {
      state.page = 1;
      run(loadRungs);
    }),
  );
  ["category-filter", "status-filter"].forEach((id) =>
    $(id).addEventListener("change", () => {
      state.page = 1;
      run(loadRungs);
    }),
  );
  $("routine-search").addEventListener("input", renderRoutines);
  $("all-routines").addEventListener("click", () => {
    if (!discard()) return;
    state.routine = "";
    state.page = 1;
    if (state.view === 'map') {
      renderRoutines();
      run(() => ladderMap.setRoutine(''));
      return;
    }
    renderRoutines();
    switchView("rungs", true);
  });
  $("clear-filters").addEventListener("click", () => {
    $("rung-search").value = "";
    $("category-filter").value = "";
    $("status-filter").value = "";
    state.routine = "";
    state.page = 1;
    renderRoutines();
    run(loadRungs);
  });
  ["object-search", "object-kind"].forEach((id) =>
    $(id).addEventListener(
      "input",
      debounce(() => {
        state.objectPage = 1;
        run(loadObjects);
      }),
    ),
  );
  $("clear-selection").addEventListener("click", () => {
    state.selected.clear();
    renderSelection();
    run(loadRungs);
  });
  $("bulk-review").addEventListener("click", bulkReview);
  $("bulk-group").addEventListener("click", () =>
    groupPicker([...state.selected]),
  );
  $("new-group").addEventListener("click", () => groupEditor());
  $("categories").addEventListener("click", categoryManager);
  $("import").addEventListener("click", importDialog);
  $("backup").addEventListener("click", () =>
    run(async () => {
      if (
        state.dirty &&
        !window.confirm(
          "Your unsaved form is not included in a database backup. Back up the saved project now?",
        )
      )
        return;
      const result = await api("/api/backup", {});
      notify("Backup created: " + result.path);
    }),
  );
  $("restore").addEventListener("click", () =>
    run(async () => {
      if (!discard()) return;
      const backups = await api("/api/backups");
      let chosen;
      modal(
        "Restore a project backup",
        (body) => {
          body.append(
            node(
              "p",
              "Restoring creates a new project database from the selected backup and opens that restored project. Your current project and the backup remain unchanged. Future launches reopen the restored project.",
            ),
          );
          chosen = select([
            ["", "Choose a backup…"],
            ...(backups.items || []).map((backup) => [
              backup.name,
              backup.name +
                " · " +
                Math.ceil(backup.size_bytes / 1024).toLocaleString() +
                " KB",
            ]),
          ]);
          body.append(field("Available backups", chosen));
          if (!(backups.items || []).length)
            body.append(
              node(
                "p",
                "No backup is available here. Use Back up project to create one first.",
              ),
            );
        },
        async () => {
          if (!chosen.value) throw new Error("Choose a backup to restore.");
          const restored = await api("/api/restore", {
            name: chosen.value,
            expected_revision: modalRevision,
          });
          if (typeof restored.workspace_token === "string")
            token = restored.workspace_token;
          state.dirty = false;
          state.source = null;
          state.connectionRung = null;
          clear($("connection-map"));
          state.selected.clear();
          state.routine = "";
          state.page = 1;
          state.objectPage = 1;
          [
            "rung-search",
            "category-filter",
            "status-filter",
            "object-search",
            "object-kind",
            "routine-search",
          ].forEach((id) => ($(id).value = ""));
          await refresh();
          clear($("rung-detail"));
          $("rung-detail").append(
            node(
              "div",
              "Backup restored into a new project. Open a source record to verify its saved review.",
              "empty",
            ),
          );
          clear($("object-detail"));
          $("object-detail").append(
            node(
              "div",
              "Select a source object from the restored project.",
              "empty",
            ),
          );
          switchView("rungs", true);
          notify(
            "Backup restored. The previous project remains intact. Current project: " +
              state.project.project_path,
          );
        },
        "Restore into new project",
      );
    }),
  );
  $("undo").addEventListener("click", () =>
    run(async () => {
      if (!discard()) return;
      if (
        !window.confirm(
          "Undo the latest project change? Its history will remain recorded.",
        )
      )
        return;
      await mutate({ op: "undo" });
      notify("Latest project change undone.");
      if (state.source)
        await openSource(state.source.source.id, state.detailTarget, true);
    }),
  );
  function theme(value) {
    document.documentElement.dataset.theme = value;
    $("theme").textContent = value === "dark" ? "Light theme" : "Dark theme";
    $("theme").setAttribute(
      "aria-label",
      "Switch to " + (value === "dark" ? "light" : "dark") + " theme",
    );
    try {
      localStorage.setItem("plc-workspace-theme-v1", value);
    } catch {}
  }
  try {
    $("reviewer-name").value =
      localStorage.getItem("plc-workspace-reviewer-v1") || "";
  } catch {}
  $("reviewer-name").addEventListener("change", () => {
    try {
      localStorage.setItem(
        "plc-workspace-reviewer-v1",
        $("reviewer-name").value.trim(),
      );
    } catch {}
  });
  $("theme").addEventListener("click", () =>
    theme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"),
  );
  $("stop").addEventListener("click", () => {
    if (!discard()) return;
    modal(
      "Close the local workspace",
      (body) =>
        body.append(
          node(
            "p",
            "Saved reviews remain in the project database. This stops the local server; run bash ./open-workbench.sh to reopen saved work without another analysis.",
          ),
        ),
      async () => {
        await api("/api/stop", {});
        document
          .querySelectorAll("button, input, select, textarea")
          .forEach((control) => (control.disabled = true));
        notify(
          "Workspace closed. Your saved project is safe. Run the workspace launcher to reopen it.",
        );
      },
      "Close workspace",
    );
  });
  try {
    theme(
      localStorage.getItem("plc-workspace-theme-v1") === "light"
        ? "light"
        : "dark",
    );
  } catch {
    theme("dark");
  }
  window.addEventListener("beforeunload", (event) => {
    if (state.dirty || modalDirty || state.saving) {
      event.preventDefault();
      event.returnValue = "";
    }
  });
  // Accepted statuses are intentionally narrower than source parse dispositions.
  $("status-filter").replaceChildren(
    ...[["", "All statuses"], ...Object.entries(statusNames)].map(
      ([id, label]) => {
        const n = node("option", label);
        n.value = id;
        return n;
      },
    ),
  );
  function requestedLocation() {
    const fragment = window.location.hash.slice(1);
    if (!fragment) return { view: "rungs", source: "" };
    if (fragment.length > 2048) return null;
    const parameters = new URLSearchParams(fragment);
    if (
      [...parameters.keys()].some((key) => !["view", "source"].includes(key)) ||
      parameters.getAll("view").length !== 1 ||
      parameters.getAll("source").length > 1
    )
      return null;
    const view = parameters.get("view");
    const source = parameters.get("source") || "";
    if (
      !["rungs", "objects", "map", "connections", "groups", "changes", "guide"].includes(view) ||
      source.length > 256 ||
      /[\x00-\x1f\x7f]/.test(source)
    )
      return null;
    if (source && !["rungs", "objects", "map", "connections"].includes(view)) return null;
    return { view, source };
  }
  function translationChanged() {
    // Refresh only list wording. The selected detail's translation module owns
    // its prose; rebuilding the detail would destroy unsaved review fields.
    if (!state.project) return;
    if (state.view === "rungs") run(loadRungs);
    if (state.view === "objects") run(loadObjects);
  }
  async function openLocation(skipCheck = false) {
    const location = requestedLocation();
    if (!location || !switchView(location.view, skipCheck)) return;
    if (location.view === 'map') {
      if (location.source) await ladderMap.focus(location.source);
      return;
    }
    if (location.view === 'connections') {
      if (location.source) state.connectionRung = location.source;
      renderConnections();
      return;
    }
    if (location.source)
      await openSource(
        location.source,
        location.view === "objects" ? "object-detail" : "rung-detail",
        true,
      );
  }
  window.addEventListener("hashchange", () => run(() => openLocation()));
  window.PLCReadingLayout.mount(document.querySelector("#view-rungs .workspace-grid"), $("rung-reading-settings"));
  window.PLCReadingLayout.mount($('map-layout'), $('map-reading-settings'), {
    storageKey: 'plc-workspace-map-layout-v1', defaultRatio: 0.6,
    leftLabel: 'Ladder map', rightLabel: 'selected source', minLeft: 380,
  });
  $('map-inspector-toggle').addEventListener('click', () => {
    const mapOnly = $('map-layout').classList.toggle('map-only');
    $('map-inspector-toggle').setAttribute('aria-pressed', String(mapOnly));
    $('map-inspector-toggle').textContent = mapOnly ? 'Map + inspector' : 'Map only';
  });
  $('refresh-project').addEventListener('click', () => run(refreshProjectWindow));
  const panelMode = new URLSearchParams(window.location.search).get('panel');
  if (panelMode === 'source' || panelMode === 'workspace') {
    document.body.classList.add('workspace-popout');
    if (panelMode === 'source') document.body.classList.add('source-popout');
    $('stop').hidden = true;
    const note = node('p', 'This window shares the same saved project. After saving elsewhere, use Refresh saved data here. Close this window with the browser window controls.', 'popout-note');
    document.querySelector('.topbar').after(note);
  }
  const ladderMap = window.PLCLadderMap.mount($('ladder-map'), {
    api,
    getState: () => state.project,
    inspect: async id => {
      if (!discard()) return false;
      await openSource(id, 'map-detail', true);
      return state.source?.source?.id === id;
    },
    popout: popupWorkspace,
    connections: openConnections,
  });
  const translations = window.PLCTranslation.mount($("translation-controls"), api, translationChanged);
  const classificationBrowser = window.PLCClassification.mount($("classification-browser"), {
    api,
    getState: () => state.project,
    reportLink: link,
    openSource: (id, kind) => run(async () => {
      if (!discard()) return;
      const view = kind === "rung" ? "rungs" : "objects";
      switchView(view, true);
      await openSource(id, view === "rungs" ? "rung-detail" : "object-detail", true);
    }),
    editGroup: (id, needsRevalidation) => {
      const group = groups().find(item => item.id === id);
      if (group) groupEditor(needsRevalidation ? {...group, needs_revalidation: true} : group);
      else notify("This saved group changed. Refresh the project before editing it.", true);
    },
    adopt: async (proposal, runId) => {
      if (!discard()) return;
      state.saving = true;
      let result;
      try {
        result = await api("/api/classification/adopt", {
          proposal_id: proposal.id, run_id: runId,
          expected_revision: state.project.revision,
          author: $("reviewer-name").value.trim() || "Local reviewer",
        });
        state.project = result;
        renderProject();
      } finally {state.saving = false;}
      const group = groups().find(item => item.id === result.selected_group_id || item.proposal_id === proposal.id);
      if (group) groupEditor(group);
      notify("Detected group saved. Adjust its categories, migration decision, or members here.");
    },
  });
  run(async () => {
    await refresh();
    await openLocation(true);
    if (state.project.startup_notice) notify(state.project.startup_notice, true);
    else if (!state.project.active_run)
      notify(
        "Start by choosing your finalized analysis run. No demonstration data is loaded.",
      );
  });
})();
