/* Source-linked proposals and reviewed migration decisions. No source rewriting. */
(() => {
  "use strict";
  const MIGRATION = [
    ["unreviewed", "Not reviewed"],
    ["retain", "Retain this function"],
    ["replace", "Replace with a DeltaV implementation"],
    ["exclude", "Exclude from migration"],
    ["investigate", "Investigate before deciding"],
  ];
  const element = (tag, text, className = "") => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = String(text);
    node.className = className;
    return node;
  };
  const button = (text, callback, className = "") => {
    const node = element("button", text, className);
    node.type = "button";
    node.addEventListener("click", callback);
    return node;
  };
  const label = (text, control) => {
    const node = element("label", text);
    node.append(control);
    return node;
  };
  const choices = (items, value = "") => {
    const node = element("select");
    items.forEach(([id, text]) => {
      const option = element("option", text);
      option.value = id;
      node.append(option);
    });
    node.value = value;
    return node;
  };
  const paragraphs = (root, value, className = "") => {
    (Array.isArray(value) ? value : [value]).filter(Boolean).forEach(text => {
      // Unknown structured evidence stays readable without becoming HTML.
      root.append(element("p", typeof text === "object" ? JSON.stringify(text) : text, className));
    });
  };
  const migrationLabel = id => MIGRATION.find(([value]) => value === id)?.[1] || id;
  const migrationHint = value => ({
    retain: "This proposal identifies a function to account for in the migration. Confirm how your DeltaV classes should implement it.",
    platform_detail: "This includes controller-specific implementation details. Check which behavior DeltaV must preserve before excluding anything.",
    investigate: "Inspect the linked source and unresolved evidence before choosing a migration decision.",
  })[value] || value;

  function groupFields(group, categories) {
    const root = element("div", undefined, "classification-editor");
    if (group.needs_revalidation) root.append(element("p", "This group's source evidence changed. Check its members and migration decision before saving; previous decisions remain visible for comparison.", "warning-panel"));
    const selected = new Set(group.function_categories || []);
    const fieldset = element("fieldset", undefined, "classification-category-picker");
    fieldset.append(element("legend", "Function categories (choose all that apply)"));
    const known = new Set();
    categories.forEach(category => {
      known.add(category.id);
      const control = element("input");
      control.type = "checkbox";
      control.checked = selected.has(category.id);
      control.addEventListener("change", () => {
        if (control.checked) selected.add(category.id);
        else selected.delete(category.id);
      });
      const wrapper = label(category.label || category.name || category.id, control);
      wrapper.title = category.description || "";
      fieldset.append(wrapper);
    });
    // Preserve older/custom categories even if this app version has no label.
    selected.forEach(id => {
      if (known.has(id)) return;
      const control = element("input");
      control.type = "checkbox";
      control.checked = true;
      control.addEventListener("change", () => control.checked ? selected.add(id) : selected.delete(id));
      fieldset.append(label(id, control));
    });
    const migration = choices(MIGRATION, group.migration_status || "unreviewed");
    migration.className = "classification-migration-edit";
    const note = element("textarea");
    note.value = group.migration_note || "";
    note.rows = 3;
    note.placeholder = "Explain what to retain, replace, exclude, or investigate.";
    note.className = "classification-note-edit";
    root.append(fieldset,
      element("p", "DC is a discrete calculation with a true/false result. AC is an analogue calculation with a floating point result. One group may need several functions or multiple DeltaV classes."),
      label("Migration decision", migration), label("Reason / migration notes", note),
      element("p", "Excluding a group removes it from the migration selection only. Its source evidence and saved review stay available. Allen-Bradley-specific logic may still express behavior that DeltaV must preserve.", "classification-help"));
    return {element: root, values: () => ({
      function_categories: [...selected], migration_status: migration.value,
      migration_note: note.value.trim(),
    })};
  }

  function mount(root, options) {
    const filters = element("div", undefined, "filters classification-filters");
    const search = element("input");
    search.type = "search";
    search.placeholder = "Name, address, or reason for classification…";
    const category = choices([["", "All function categories"]]);
    const migration = choices([["", "All migration decisions"], ["in_scope", "Hide reviewed exclusions"], ...MIGRATION]);
    search.className = "classification-search";
    category.className = "classification-category-filter";
    migration.className = "classification-migration-filter";
    filters.append(label("Search detected groups", search), label("Function", category), label("Migration decision", migration));
    const status = element("p", "Open this view to load detected groups.", "classification-status");
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    const description = element("p", "");
    description.className = "classification-filter-description";
    const limits = element("details", undefined, "classification-limitations");
    const coverage = element("p", undefined, "classification-coverage");
    const list = element("div", undefined, "classification-list");
    const pages = element("div", undefined, "pagination classification-pagination");
    const intro = element("div", undefined, "classification-intro");
    intro.append(element("h2", "Detected function groups"),
      element("p", "These proposals are ready to browse without creating groups by hand. A shared address links source uses; it does not prove they form one piece of equipment or one DeltaV module. Review the evidence before adopting a proposal."),
      element("p", "Unknown and uncertain items stay visible. Use migration decisions to separate retained functions, replacements, and reviewed exclusions."));
    root.replaceChildren(intro, filters, description, status, coverage, limits, list, pages);
    let page = 1, serial = 0, timer, data = null, busy = false;

    function reset() {page = 1; return refresh();}
    search.addEventListener("input", () => {clearTimeout(timer); timer = setTimeout(reset, 250);});
    category.addEventListener("change", reset);
    migration.addEventListener("change", reset);
    filters.append(button("Clear filters", () => {
      clearTimeout(timer); search.value = ""; category.value = ""; migration.value = ""; return reset();
    }));

    function sourceButton(text, id, kind = "object") {
      const control = button(text, () => options.openSource(id, kind), "text-button");
      control.title = id;
      return control;
    }
    function card(item, registry) {
      const article = element("article", undefined, "classification-card");
      const heading = element("div", undefined, "classification-card-heading");
      heading.append(element("h3", item.name || "Unnamed source association"));
      const chips = element("div", undefined, "classification-chips");
      const categoryIds = item.effective_category_ids ?? item.category_ids ?? [];
      categoryIds.forEach(id => chips.append(element("span", registry.get(id)?.label || id, "chip")));
      if (!categoryIds.length) chips.append(element("span", "Unclassified", "chip"));
      const decision = item.effective_migration_status || "unreviewed";
      chips.append(element("span", migrationLabel(decision), "chip classification-decision"));
      heading.append(chips); article.append(heading);
      if (item.needs_revalidation) article.append(element("p", "Source evidence changed. Recheck the saved classification and migration decision; this item remains in scope until reviewed.", "warning-panel"));
      if (item.migration_scope_limited) article.append(element("p", `Your saved group contains ${item.saved_member_count} source records and leaves out part of this detected proposal. Its categories and migration decision apply to the saved members only. This larger proposal remains in scope for investigation.`, "warning-panel"));
      paragraphs(article, item.reason, "classification-reason");
      if (item.migration_hint) {
        const hint = element("div", undefined, "classification-hint");
        hint.append(element("strong", "Migration consideration"));
        paragraphs(hint, migrationHint(item.migration_hint)); article.append(hint);
      }
      const members = item.member_ids || [], rungs = item.rung_ids || [];
      const rungSet = new Set(rungs), sourceIds = [...new Set([...rungs, ...members])];
      const sourceLabels = item.source_labels || Object.fromEntries((item.members || []).map(member => [member.id, member.label]));
      article.append(element("p", `${members.length} linked source records · ${rungs.length} rungs`, "classification-member-count"));
      const details = element("details", undefined, "classification-evidence");
      details.append(element("summary", "Evidence, parameters & source links"));
      let evidenceBuilt = false;
      function buildEvidence() {
        if (!details.open || evidenceBuilt) return;
        evidenceBuilt = true;
        if (item.basis) {
          details.append(element("h4", "Why these records are associated")); paragraphs(details, item.basis);
        }
        if (item.limitations?.length) {
          details.append(element("h4", "What still needs checking")); paragraphs(details, item.limitations, "classification-gap");
        }
        const parameters = item.parameters || [];
        if (parameters.length) {
          details.append(element("h4", "Captured parameters"), element("p", "Values below are source evidence. Changing a migration decision does not rewrite these values."));
          const table = element("table", undefined, "classification-parameters");
          const head = element("thead"), row = element("tr");
          ["Parameter", "Captured value", "Source"].forEach(text => row.append(element("th", text)));
          head.append(row); table.append(head);
          const body = element("tbody");
          parameters.forEach(parameter => {
            const row = element("tr");
            const value = parameter.value === undefined ? "Not captured" : typeof parameter.value === "object" ? JSON.stringify(parameter.value) : String(parameter.value);
            row.append(element("td", parameter.name || "Unnamed parameter"), element("td", value, "mono"));
            const source = element("td");
            if (parameter.source_id) source.append(sourceButton("Open source", parameter.source_id));
            else source.textContent = "See linked source";
            row.append(source); body.append(row);
          });
          table.append(body); details.append(table);
        } else details.append(element("p", "No parameter values are captured in this proposal. Open its source records to inspect the declaration and logic."));
        details.append(element("h4", "Linked source records"));
        const links = element("div", undefined, "classification-source-links");
        const controls = element("div", undefined, "pagination classification-source-pagination");
        let sourcePage = 0;
        function paintSources() {
          links.replaceChildren(); controls.replaceChildren();
          const start = sourcePage * 50, end = Math.min(start + 50, sourceIds.length);
          sourceIds.slice(start, end).forEach(id => links.append(sourceButton(
            sourceLabels[id] || `${rungSet.has(id) ? "Rung" : "Source"} ${id}`, id, rungSet.has(id) ? "rung" : "object")));
          const previous = button("← Previous source links", () => {sourcePage -= 1; paintSources();});
          const next = button("Next source links →", () => {sourcePage += 1; paintSources();});
          previous.disabled = sourcePage === 0; next.disabled = end >= sourceIds.length;
          controls.append(previous, element("span", sourceIds.length ? `${start + 1}–${end} of ${sourceIds.length} source records` : "No source links captured"), next);
        }
        paintSources(); details.append(links, controls);
      }
      details.addEventListener("toggle", buildEvidence);
      article.append(details);
      const actions = element("div", undefined, "actions");
      const anchor = item.anchor_id || rungs[0] || members[0];
      if (anchor) actions.append(sourceButton("Inspect source", anchor, rungSet.has(anchor) ? "rung" : "object"));
      if (anchor && options.reportLink) actions.append(options.reportLink("Open analysis evidence ↗", anchor,
        rungSet.has(anchor) ? "ladder" : "objects"));
      const save = button(item.saved_group_id ? "Edit saved group" : "Adopt & edit group", async () => {
        if (busy) return;
        if (item.saved_group_id) {options.editGroup(item.saved_group_id, item.needs_revalidation); return;}
        busy = true; save.disabled = true;
        try {
          await options.adopt(item, data.run_id);
          await refresh();
        } catch (error) {
          status.textContent = error.message;
          status.className = "classification-status warning-panel";
        } finally {busy = false; save.disabled = false;}
      }, item.saved_group_id ? "" : "primary");
      actions.append(save); article.append(actions);
      return article;
    }
    async function refresh() {
      const request = ++serial;
      const project = options.getState();
      list.replaceChildren(); pages.replaceChildren(); limits.replaceChildren(); coverage.textContent = "";
      if (!project?.active_run) {
        root.removeAttribute("aria-busy");
        limits.hidden = true;
        description.textContent = "";
        status.textContent = "Choose an analysis run to see detected function groups.";
        return;
      }
      root.setAttribute("aria-busy", "true");
      status.className = "classification-status";
      status.textContent = "Reading classifications from the imported source…";
      const query = new URLSearchParams({category: category.value, migration: migration.value, query: search.value, page: String(page)});
      try {
        const result = await options.api("/api/classification?" + query);
        if (request !== serial) return;
        data = result; page = Number(result.page || 1);
        const selected = category.value;
        category.replaceChildren();
        [["", "All function categories"], ...(result.categories || []).map(item => [item.id, item.label || item.name || item.id])].forEach(([id, text]) => {
          const option = element("option", text); option.value = id; category.append(option);
        });
        category.value = selected;
        const registry = new Map((result.categories || []).map(item => [item.id, item]));
        description.textContent = registry.get(category.value)?.description || "A source association can have multiple function categories. Filtered results include your saved category and migration decisions.";
        const total = Number(result.total || 0), pagesCount = Math.max(1, Number(result.pages || Math.ceil(total / (result.page_size || 25))));
        status.textContent = `${total.toLocaleString()} detected groups match · page ${page} of ${pagesCount}`;
        const counts = result.coverage || {};
        if (Number.isFinite(counts.source_rungs) && Number.isFinite(counts.represented_rungs)) {
          coverage.textContent = `${counts.represented_rungs.toLocaleString()} of ${counts.source_rungs.toLocaleString()} source rungs link to proposals. A link does not mean every function is classified.`;
          if (counts.unrepresented_rungs) coverage.textContent += ` ${counts.unrepresented_rungs.toLocaleString()} rungs still have no proposal; they remain available in Rungs.`;
          if (counts.truncated) coverage.textContent += " Display limits were reached; coverage is partial.";
        }
        if (result.limitations?.length) {
          limits.append(element("summary", "Classification boundaries & unresolved evidence")); paragraphs(limits, result.limitations);
        }
        limits.hidden = !result.limitations?.length;
        (result.items || []).forEach(item => list.append(card(item, registry)));
        if (!result.items?.length) list.append(element("p", "No detected groups match these filters. Clear filters to include unreviewed and uncertain items.", "empty"));
        const previous = button("← Previous", () => {page -= 1; return refresh();});
        const next = button("Next →", () => {page += 1; return refresh();});
        previous.disabled = page <= 1; next.disabled = page >= pagesCount;
        pages.append(previous, element("span", `Page ${page} of ${pagesCount}`), next);
      } catch (error) {
        if (request !== serial) return;
        status.textContent = error.message || "Classifications could not be loaded.";
        status.className = "classification-status warning-panel";
        list.append(button("Retry classifications", refresh));
      } finally {
        if (request === serial) root.removeAttribute("aria-busy");
      }
    }
    return {refresh, destroy: () => {serial += 1; clearTimeout(timer);}};
  }
  window.PLCClassification = {mount, groupFields, migrationLabel};
})();
