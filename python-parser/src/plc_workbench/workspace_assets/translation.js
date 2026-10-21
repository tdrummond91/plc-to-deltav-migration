/* Local derived wording. Original source and engineering forms stay untouched. */
(() => {
  "use strict";
  const modes = new Set(["original", "english", "both"]);
  const modeOf = (result) => modes.has(result?.presentation_mode) ? result.presentation_mode : "original";
  const el = (tag, text, cls) => {
    const n = document.createElement(tag);
    if (text !== undefined) n.textContent = text;
    if (cls) n.className = cls;
    return n;
  };

  function renderProse(root, original, entry, mode = "original") {
    root.replaceChildren();
    if (!root.className.split(" ").includes("translation-prose-root")) root.className += " translation-prose-root";
    if (!original) return;
    const source = el("div", original, "source-comment translation-original");
    if (!modes.has(mode) || mode === "original") {
      root.append(source);
      return;
    }
    const english = el("div", undefined, "translation-english");
    english.append(el("strong", "English translation · review wording"));
    if (entry?.status === "translated" && entry.text) {
      const text = el("div", entry.text, "source-comment");
      text.lang = "en";
      english.append(text);
    } else {
      english.append(el("p", entry?.warning || "English wording is not ready. Open Original wording to inspect the source.", "muted translation-gap"));
    }
    if (mode === "both") {
      const originalBlock = el("div", undefined, "translation-original-block");
      originalBlock.append(el("strong", "Original wording"), source);
      root.append(originalBlock, english);
    } else {
      const originalBlock = el("details", undefined, "translation-original-disclosure");
      originalBlock.append(el("summary", "Original wording"), source);
      root.append(english, originalBlock);
    }
  }

  function duration(seconds) {
    if (!Number.isFinite(seconds) || seconds < 0) return null;
    const total = Math.round(seconds);
    if (total < 60) return `${total}s`;
    const minutes = Math.floor(total / 60);
    return minutes < 60 ? `${minutes}m ${total % 60}s` : `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
  }

  function mount(container, api, onChange = () => {}) {
    const title = el("strong", "Source language");
    const label = el("label", "Display comments and descriptions");
    const mode = el("select", undefined, "translation-mode");
    for (const [value, text] of [["original", "Original"], ["english", "English"], ["both", "Both languages"]]) {
      const option = el("option", text); option.value = value; mode.append(option);
    }
    mode.value = "original";
    label.append(mode);
    const status = el("p", "Checking local translation setup…", "translation-status");
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    const coverage = el("p", "", "translation-coverage");
    coverage.hidden = true;
    const prepare = el("button", "Prepare all English", "translation-prepare");
    prepare.type = "button";
    prepare.disabled = true;
    const retry = el("button", "Retry missing translations", "translation-retry");
    retry.type = "button";
    retry.hidden = true;
    const retryStatus = el("button", "Retry status", "translation-retry-status");
    retryStatus.type = "button";
    retryStatus.hidden = true;
    const report = el("a", "Open analysis report", "translation-report");
    report.href = "/analysis?language=original";
    report.target = "_blank";
    report.rel = "noopener";
    const help = el("details");
    const coverageDetails = el("p", "", "translation-coverage-details");
    coverageDetails.hidden = true;
    help.append(el("summary", "How English analysis works"),
      coverageDetails,
      el("p", "Prepare all English translates every available comment and description in this imported L5X analysis on this PC. The first pass can take several minutes. You can keep reviewing or switch to Original while preparation continues. No full parser rerun is needed."),
      el("p", "English shows translated wording with the original available on demand. Both languages keeps them visible together. Names, addresses, logic, and saved review decisions stay as entered. Missing or uncertain translations are marked; they do not silently switch to French."),
      el("p", "Unchanged wording is translated once and reused from the local cache, including after later exports. New or changed wording is prepared separately. Review translations against their originals; abbreviations and mixed-language comments may need correction."),
      el("p", "First use: close the workspace and run this once from the repository in Git Bash. Setup downloads the translation software and French-to-English model. It does not send your comments anywhere."),
      el("code", "bash ./setup-translation.sh", "translation-command"),
      el("p", "Then reopen with bash ./open-workbench.sh. Your usual run-work-check.sh also opens this workspace. Translation runs locally without an internet connection after setup. The analysis report follows your selected language; reopen it to include newly prepared wording."));
    container.append(title, label, status, coverage, prepare, retry, retryStatus, report, help);
    let current = null, last = null, timer = null, serial = 0, stopped = false, configuring = false;
    let consecutiveErrors = 0;

    function paint(result) {
      const previous = last;
      last = result;
      consecutiveErrors = 0;
      retryStatus.hidden = true;
      mode.value = modeOf(result);
      const running = result.state === "running";
      prepare.disabled = configuring || running || !result.available || !result.run_id;
      retry.hidden = !result.available || running || !(result.failed || result.state === "error");
      const total = Number(result.total || 0), completed = Number(result.completed || 0);
      const remaining = Math.max(0, total - completed);
      const counts = `${completed} / ${total} unique texts`;
      const notes = [result.cached ? `${result.cached} reused` : "", remaining ? `${remaining} pending` : "",
        result.needs_review ? `${result.needs_review} need wording review` : "", result.failed ? `${result.failed} failed` : ""].filter(Boolean);
      const elapsed = duration(result.elapsed_seconds), eta = duration(result.remaining_seconds);
      const timing = [elapsed && `elapsed ${elapsed}`, running && (eta ? `about ${eta} remaining` : "estimating remaining time")].filter(Boolean);
      status.textContent = !result.available ? result.message || "Install the local translation model to prepare English."
        : running ? `Preparing English locally · ${counts}${notes.length ? " · " + notes.join(" · ") : ""}${timing.length ? " · " + timing.join(" · ") : ""}. You can keep reviewing.`
        : result.state === "error" ? result.message || "Translation stopped. Retry missing translations to continue."
        : result.state === "complete" ? `Prepared · ${counts}${notes.length ? " · " + notes.join(" · ") : ""}${elapsed ? " · elapsed " + elapsed : ""}.`
        : "Choose Prepare all English to translate this imported analysis once. Original wording is always retained.";
      const catalog = result.catalog_coverage;
      if (catalog && typeof catalog === "object") {
        const kinds = {comment: "comments", description: "descriptions", text_box: "text boxes", structured_text_comment: "separate code comments"};
        const parts = Object.entries(catalog.by_kind || {}).map(([key, count]) => `${count} ${kinds[key] || key.replaceAll("_", " ")}`);
        coverage.textContent = `${catalog.annotations || 0} source annotations · ${catalog.unique_texts || 0} unique texts.`;
        coverageDetails.textContent = parts.length ? "Coverage: " + parts.join(", ") + "." : "";
        if (Array.isArray(result.limitations) && result.limitations.length)
          coverageDetails.textContent += " " + result.limitations.join(" ");
      } else {
        coverage.textContent = typeof catalog === "string" ? catalog : "";
        coverageDetails.textContent = "";
      }
      coverage.hidden = !coverage.textContent;
      coverageDetails.hidden = !coverageDetails.textContent;
      const partial = remaining > 0 || Boolean(result.failed || result.needs_review);
      report.href = "/analysis?language=" + modeOf(result);
      report.textContent = modeOf(result) === "original" ? "Open original analysis report"
        : `Open ${modeOf(result) === "english" ? "English" : "both-language"} analysis report${partial ? " (wording gaps marked)" : ""}`;
      clearTimeout(timer);
      // Presentation is independent of preparation: Original never stops a job.
      timer = !stopped && running ? setTimeout(refresh, 1200) : null;
      if (previous && (modeOf(previous) !== modeOf(result) || previous.write_generation !== result.write_generation || previous.run_id !== result.run_id))
        onChange({ presentation_mode: modeOf(result), write_generation: result.write_generation, run_id: result.run_id });
    }
    function paintFields(result, selection) {
      for (const [key, output] of selection.outputs) {
        let value = result.fields?.[key];
        if (!value) value = {warning: !result.available ? result.message
          : result.state === "running" ? "This wording is queued while the whole source is prepared. It appears when the batch reaches this text; you can keep reviewing."
          : selection.historical ? "No saved English version for this earlier source. Open Original wording to inspect it."
          : "English wording is not ready. Open Original wording to inspect the source."};
        selection.entries.set(key, value);
        const signature = JSON.stringify([modeOf(result), value]);
        // Preserve expanded original disclosures during unrelated batch updates.
        if (selection.signatures.get(key) === signature) continue;
        selection.signatures.set(key, signature);
        renderProse(output, selection.source[key], value, modeOf(result));
      }
    }
    async function refresh() {
      if (stopped || configuring || !container.isConnected) { clearTimeout(timer); return; }
      clearTimeout(timer);
      const request = ++serial;
      const selection = current?.root.isConnected ? current : null;
      const query = new URLSearchParams();
      if (selection) {
        query.set("source_id", selection.id);
        if (selection.run) query.set("run_id", selection.run);
      }
      try {
        const result = await api("/api/translation" + (query.size ? "?" + query : ""));
        if (request !== serial || stopped || !container.isConnected) return;
        paint(result);
        if (selection && selection === current && selection.root.isConnected) paintFields(result, selection);
      } catch (error) {
        if (request !== serial || stopped || !container.isConnected) return;
        consecutiveErrors += 1;
        const autoRetry = consecutiveErrors <= 3;
        const recovery = autoRetry ? "Retrying status in 5 seconds." : "Use Retry status to reconnect.";
        status.textContent = "Translation status connection interrupted. " + error.message + " " + recovery;
        retryStatus.hidden = false;
        if (selection && selection === current && selection.root.isConnected && modeOf(last) !== "original") {
          for (const [key, output] of selection.outputs) {
            const saved = selection.entries.get(key);
            if (saved?.status === "translated" || saved?.status === "needs_review") continue;
            const warning = {warning: "Live translation status is interrupted; completion cannot be checked yet. " + recovery + " The original wording is still available."};
            selection.signatures.set(key, JSON.stringify([modeOf(last), warning]));
            renderProse(output, selection.source[key], warning, modeOf(last));
          }
        }
        clearTimeout(timer);
        timer = autoRetry ? setTimeout(refresh, 5000) : null;
      }
    }
    async function configure(prepareAll = false, retryMissing = false) {
      if (!last || configuring) { mode.value = modeOf(last); return; }
      configuring = true;
      mode.disabled = prepare.disabled = retry.disabled = true;
      const request = ++serial;
      clearTimeout(timer);
      try {
        const result = await api("/api/translation", { presentation_mode: mode.value, prepare: prepareAll, run_id: last.run_id, retry: retryMissing });
        if (stopped || request !== serial) return;
        paint(result);
      } catch (error) {
        if (stopped || request !== serial) return;
        mode.value = modeOf(last);
        status.textContent = error.message;
      } finally {
        configuring = false;
        mode.disabled = retry.disabled = false;
        prepare.disabled = !last?.available || !last?.run_id || last?.state === "running";
      }
      // A failed POST may still have reached the server. Re-read status rather
      // than repeating the mutation, and restore polling for any running job.
      if (!stopped && request === serial) await refresh();
    }
    mode.addEventListener("change", () => configure(mode.value !== "original"));
    prepare.addEventListener("click", () => configure(true));
    retry.addEventListener("click", () => configure(true, true));
    retryStatus.addEventListener("click", () => { consecutiveErrors = 0; return refresh(); });
    return {
      refresh,
      mode: () => modeOf(last),
      show(root, data) {
        const outputs = new Map();
        for (const key of ["comment", "description"]) {
          if (!data.source[key]) continue;
          const block = el("div", undefined, "translation-pair");
          const output = el("div", undefined, "translation-prose");
          block.append(el("strong", key === "comment" ? "Source comment" : "Source description"), output);
          root.append(block);
          renderProse(output, data.source[key], data.wording?.[key], modeOf(last));
          outputs.set(key, output);
        }
        current = { root, id: data.source.id, run: data.run_id, historical: data.historical, source: data.source, outputs, signatures: new Map(),
          entries: new Map(Object.entries(data.wording || {})) };
        refresh();
      },
      destroy() { stopped = true; ++serial; clearTimeout(timer); },
    };
  }
  window.PLCTranslation = { mount, renderProse };
})();
