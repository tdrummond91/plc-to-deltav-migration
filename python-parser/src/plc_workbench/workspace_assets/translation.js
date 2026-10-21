/* Local derived wording. Original source and engineering forms stay untouched. */
(() => {
  "use strict";
  function mount(container, api) {
    const el = (tag, text, cls) => {
      const n = document.createElement(tag);
      if (text !== undefined) n.textContent = text;
      if (cls) n.className = cls;
      return n;
    };
    const title = el("strong", "Comment language");
    const label = el("label", "Show English alongside original");
    const toggle = el("input");
    toggle.type = "checkbox";
    label.prepend(toggle);
    const status = el("p", "Checking local translation setup…", "translation-status");
    status.setAttribute("role", "status");
    const retry = el("button", "Retry missing translations");
    retry.type = "button";
    retry.hidden = true;
    const help = el("details");
    help.append(el("summary", "How local translation works"),
      el("p", "Enable once to translate the imported comments and descriptions on this PC. Unchanged text reuses the local cache, including after a new analysis. Review the wording against the original; abbreviations and mixed-language phrases may need correction."),
      el("p", "First use: close the workspace and run this once from the repository in Git Bash. Setup downloads the translation software and French-to-English model. It does not send your comments anywhere."),
      el("code", "bash ./setup-translation.sh", "translation-command"),
      el("p", "Then reopen with bash ./open-workbench.sh. Your usual run-work-check.sh also opens this workspace. Translation runs locally without an internet connection after setup. The static analysis report keeps original wording."));
    container.append(title, label, status, retry, help);
    let current = null, last = null, timer = null, serial = 0, stopped = false;

    function paint(result) {
      last = result;
      toggle.checked = result.enabled;
      retry.hidden = !result.enabled || !result.available || result.state === "running" || !(result.failed || result.state === "error");
      const count = `${result.completed || 0} / ${result.total || 0} unique texts`;
      status.textContent = !result.enabled ? "Original wording. Enable English to prepare translations for this source."
        : !result.available ? result.message
        : result.state === "running" ? `Translating locally · ${count}. You can keep reviewing.`
        : result.state === "error" ? result.message || "Translation stopped. Original text remains available."
        : result.state === "complete" ? `Ready · ${count} · ${result.cached || 0} reused${result.needs_review ? ` · ${result.needs_review} need wording review` : ""}.`
        : "English enabled. New comments will be translated locally.";
      clearTimeout(timer);
      timer = !stopped && result.enabled && result.state === "running"
        ? setTimeout(refresh, 1200) : null;
    }
    function paintFields(result, selection) {
      for (const [key, output] of selection.outputs) {
        output.hidden = !result.enabled;
        if (!result.enabled) continue;
        output.replaceChildren(el("strong", "English translation · review wording"));
        const value = result.fields?.[key];
        if (value?.status === "translated" && value.text) {
          const text = el("div", value.text, "source-comment");
          text.lang = "en";
          output.append(text);
        } else {
          output.append(el("p", value?.warning || (!result.available ? result.message
            : result.state === "running" ? "Waiting for this text. Translation continues in the background."
            : selection.historical ? "No saved English version for this earlier source. The original is shown above."
            : "An English version is not ready. The original is shown above."), "muted"));
        }
      }
    }
    async function refresh() {
      const request = ++serial;
      const selection = current?.root.isConnected ? current : null;
      const query = new URLSearchParams();
      if (selection) {
        query.set("source_id", selection.id);
        if (selection.run) query.set("run_id", selection.run);
      }
      try {
        const result = await api("/api/translation" + (query.size ? "?" + query : ""));
        if (request !== serial || stopped) return;
        paint(result);
        if (selection && selection === current && selection.root.isConnected) paintFields(result, selection);
      } catch (error) {
        if (request !== serial || stopped) return;
        status.textContent = "Translation unavailable. " + error.message;
        clearTimeout(timer);
      }
    }
    async function configure(retryMissing = false) {
      if (!last) { toggle.checked = false; return; }
      toggle.disabled = retry.disabled = true;
      ++serial;
      clearTimeout(timer);
      try {
        const result = await api("/api/translation", { enabled: toggle.checked, run_id: last.run_id, retry: retryMissing });
        if (stopped) return;
        paint(result);
        await refresh();
      } catch (error) {
        if (stopped) return;
        toggle.checked = last.enabled;
        status.textContent = error.message;
      } finally { toggle.disabled = retry.disabled = false; }
    }
    toggle.addEventListener("change", () => configure());
    retry.addEventListener("click", () => configure(true));
    return {
      refresh,
      show(root, data) {
        const outputs = new Map();
        for (const key of ["comment", "description"]) {
          if (!data.source[key]) continue;
          const block = el("div", undefined, "translation-pair");
          const original = el("div", data.source[key], "source-comment");
          const output = el("div", undefined, "translation-english");
          output.hidden = true;
          block.append(el("strong", key === "comment" ? "Original comment" : "Original description"), original, output);
          root.append(block);
          outputs.set(key, output);
        }
        current = { root, id: data.source.id, run: data.run_id, historical: data.historical, outputs };
        refresh();
      },
      destroy() { stopped = true; ++serial; clearTimeout(timer); },
    };
  }
  window.PLCTranslation = { mount };
})();
