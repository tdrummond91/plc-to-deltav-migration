/* Offline orientation: fixed learning checkpoints only, never engineering records. */
(() => {
  "use strict";
  const PROGRESS_KEY = "plc-workbench-learning-v2";
  const LEGACY_PROGRESS_KEY = "plc-workbench-learning-v1";
  const THEME_KEY = "plc-workbench-theme";
  const KIND = "plc-learning-progress";
  const CORE = ["orient", "navigate", "interpret", "respond"];
  const TOPICS = [
    "rungs",
    "io",
    "loops",
    "calculations",
    "sequences",
    "alarms",
    "connections",
  ];
  const IDS = [...CORE, ...TOPICS];
  const MAX_BYTES = 8192;
  const byId = (id) => document.getElementById(id);
  const checks = Array.from(document.querySelectorAll("[data-check]"));
  const status = byId("storage-status");
  const transfer = byId("transfer-status");
  const next = byId("next-action");
  let completed = new Set();
  const pendingChanges = new Map();

  function parseProgress(text) {
    if (typeof text !== "string" || text.length > MAX_BYTES)
      throw new Error("size");
    const value = JSON.parse(text);
    if (
      !value ||
      Array.isArray(value) ||
      typeof value !== "object" ||
      Object.keys(value).sort().join(",") !== "completed,kind,version" ||
      value.kind !== KIND ||
      ![1, 2].includes(value.version) ||
      !Array.isArray(value.completed) ||
      value.completed.length > IDS.length ||
      value.completed.some(
        (id) => typeof id !== "string" || !IDS.includes(id),
      ) ||
      new Set(value.completed).size !== value.completed.length
    )
      throw new Error("format");
    // Previous core tasks described a read-only report. They cannot attest
    // that the user has now saved and reopened an engineering decision.
    return value.version === 1
      ? value.completed.filter((id) => TOPICS.includes(id))
      : value.completed;
  }

  function payload() {
    return {
      kind: KIND,
      version: 2,
      completed: IDS.filter((id) => completed.has(id)),
    };
  }

  function refreshFromStorage() {
    // Another open copy may have saved a different checkpoint since our last action.
    try {
      const saved = localStorage.getItem(PROGRESS_KEY);
      if (saved !== null) completed = new Set(parseProgress(saved));
    } catch {
      /* Preserve this visit's working checks when storage is unavailable. */
    }
    for (const [id, checked] of pendingChanges) {
      if (checked) completed.add(id);
      else completed.delete(id);
    }
  }

  function save() {
    try {
      localStorage.setItem(PROGRESS_KEY, JSON.stringify(payload()));
      pendingChanges.clear();
      status.textContent =
        "Saved in this browser. Export a backup to keep it or move it to another computer.";
    } catch {
      status.textContent =
        "This browser cannot save progress here. Your checks work for this visit; use Export progress before closing.";
    }
  }

  function render() {
    for (const input of checks)
      input.checked = completed.has(input.dataset.check);
    const count = CORE.filter((id) => completed.has(id)).length;
    byId("core-count").textContent = String(count);
    byId("core-progress").value = count;
    byId("topic-count").textContent =
      `${TOPICS.filter((id) => completed.has(id)).length} / ${TOPICS.length} explored`;
    const remaining = CORE.find((id) => !completed.has(id));
    const actions = {
      orient: ["Go to step 1 — confirm your source →", "#first-look"],
      navigate: ["Go to step 2 — inspect a complete rung →", "#practice"],
      interpret: ["Go to step 3 — save a decision →", "#interpret"],
      respond: ["Go to step 4 — reopen and back up →", "#respond"],
    };
    const [label, href] = actions[remaining] || [
      "Walkthrough complete — explore a subject →",
      "#subjects",
    ];
    next.textContent = label;
    next.setAttribute("href", href);
  }

  try {
    const saved =
      localStorage.getItem(PROGRESS_KEY) ??
      localStorage.getItem(LEGACY_PROGRESS_KEY);
    if (saved !== null) completed = new Set(parseProgress(saved));
    status.textContent =
      "Progress stays in this browser. Export a backup to keep it or move it to another computer.";
  } catch {
    status.textContent =
      "Saved progress is unavailable. Use Export progress to keep this visit’s checks.";
  }
  render();
  for (const input of checks)
    input.addEventListener("change", () => {
      const checked = input.checked;
      refreshFromStorage();
      if (checked) completed.add(input.dataset.check);
      else completed.delete(input.dataset.check);
      pendingChanges.set(input.dataset.check, checked);
      render();
      save();
    });

  const exportButton = byId("export-progress");
  exportButton.disabled = false;
  exportButton.addEventListener("click", () => {
    let url;
    let link;
    try {
      refreshFromStorage();
      render();
      url = URL.createObjectURL(
        new Blob([JSON.stringify(payload(), null, 2) + "\n"], {
          type: "application/json",
        }),
      );
      link = document.createElement("a");
      link.href = url;
      link.download = "workbench-learning-progress.json";
      document.body.append(link);
      link.click();
      transfer.textContent =
        "Progress download requested. Keep the JSON file to restore your checks on another computer.";
    } catch {
      transfer.textContent =
        "The download could not start. Your checks are still shown here; try another browser or keep a copy of the checklist.";
    } finally {
      if (link) link.remove();
      if (url) setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
  });

  const importInput = byId("import-progress");
  importInput.disabled = false;
  importInput.addEventListener("change", async () => {
    const file = importInput.files && importInput.files[0];
    if (!file) return;
    try {
      if (file.size > MAX_BYTES) throw new Error("size");
      const restored = parseProgress(await file.text());
      refreshFromStorage();
      completed = new Set([...completed, ...restored]);
      for (const id of restored) pendingChanges.set(id, true);
      render();
      save();
      transfer.textContent =
        "Progress imported. Previously completed checks were kept.";
    } catch {
      transfer.textContent =
        "Choose a valid workbench learning-progress JSON file (up to 8 KB). Your current checks were not changed.";
    } finally {
      importInput.value = "";
    }
  });

  const toggle = byId("theme-toggle");
  let theme = "dark";
  try {
    if (localStorage.getItem(THEME_KEY) === "light") theme = "light";
  } catch {
    /* Keep the offline default. */
  }
  function renderTheme() {
    document.documentElement.dataset.theme = theme;
    toggle.textContent =
      theme === "dark" ? "Switch to light" : "Switch to dark";
  }
  renderTheme();
  toggle.disabled = false;
  toggle.addEventListener("click", () => {
    theme = theme === "dark" ? "light" : "dark";
    renderTheme();
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      /* Switching still works for this visit. */
    }
  });
})();
