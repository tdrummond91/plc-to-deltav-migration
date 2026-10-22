/* Local reading preferences only: never stores source text or review decisions. */
(function () {
  "use strict";

  const STORAGE_KEY = "plc-workspace-reading-layout-v1";
  const DEFAULT_RATIO = 1 / 3;
  const DEFAULT_SCALE = 75;
  const SCALES = [50, 75, 100, 125];
  const DIVIDER_WIDTH = 20;
  const MIN_INVENTORY = 240;
  const MIN_DETAIL = 360;
  const mounted = new WeakMap();

  function preferences(storageKey = STORAGE_KEY, defaultRatio = DEFAULT_RATIO) {
    try {
      const saved = JSON.parse(window.localStorage.getItem(storageKey));
      if (saved && saved.version === 1) {
        return {
          ratio: typeof saved.ratio === "number" && Number.isFinite(saved.ratio)
            && saved.ratio > 0 && saved.ratio < 1 ? saved.ratio : defaultRatio,
          scale: SCALES.includes(saved.scale) ? saved.scale : DEFAULT_SCALE,
        };
      }
    } catch (_) {
      // Browser privacy settings may disable storage. Reading still works.
    }
    return { ratio: defaultRatio, scale: DEFAULT_SCALE };
  }

  function mount(grid, settingsContainer, options = {}) {
    if (!grid || !settingsContainer) return null;
    if (mounted.has(grid)) return mounted.get(grid);
    const panels = Array.from(grid.children);
    if (panels.length !== 2) return null;
    const [inventory, detail] = panels;
    const storageKey = options.storageKey || STORAGE_KEY;
    const defaultRatio = options.defaultRatio || DEFAULT_RATIO;
    const leftLabel = options.leftLabel || 'Rung inventory';
    const rightLabel = options.rightLabel || 'selected source';
    const minLeft = options.minLeft || MIN_INVENTORY;
    const minRight = options.minRight || MIN_DETAIL;
    const saved = preferences(storageKey, defaultRatio);
    let ratio = saved.ratio;
    let scale = saved.scale;
    let drag = null;
    let stacked = true;
    let destroyed = false;
    const compact = window.matchMedia("(max-width: 1150px)");

    const divider = document.createElement("div");
    divider.className = "rung-pane-divider";
    divider.tabIndex = 0;
    divider.setAttribute("role", "separator");
    divider.setAttribute("aria-orientation", "vertical");
    divider.setAttribute("aria-label", `Resize ${leftLabel.toLowerCase()} and ${rightLabel.toLowerCase()} panes`);
    divider.title = "Drag to resize. Use arrow keys for small changes, Shift + arrows for larger changes, Home or End for the limits. Double-click to reset the split.";
    if (inventory.id && detail.id) {
      divider.setAttribute("aria-controls", `${inventory.id} ${detail.id}`);
    } else if (detail.id) {
      divider.setAttribute("aria-controls", detail.id);
    }
    grid.insertBefore(divider, detail);
    grid.classList.add("rung-reading-layout");

    const controls = document.createElement("div");
    controls.className = "rung-reading-controls";
    const label = document.createElement("label");
    label.append(document.createTextNode("Equation text "));
    const size = document.createElement("select");
    size.setAttribute("aria-label", "Equation text size");
    for (const value of SCALES) {
      const option = document.createElement("option");
      option.value = String(value);
      option.textContent = `${value}%`;
      size.append(option);
    }
    label.append(size);
    const resetButton = document.createElement("button");
    resetButton.type = "button";
    resetButton.textContent = "Reset layout";
    const hint = document.createElement("span");
    hint.className = "rung-reading-hint";
    hint.textContent = "Drag the divider to give either pane more space.";
    controls.append(label, resetButton, hint);
    settingsContainer.append(controls);

    function save() {
      try {
        window.localStorage.setItem(storageKey, JSON.stringify({ version: 1, ratio, scale }));
      } catch (_) {
        // The current layout remains usable when persistence is unavailable.
      }
    }

    function bounds() {
      const box = grid.getBoundingClientRect();
      const available = Math.max(0, box.width - DIVIDER_WIDTH);
      return { box, available, min: minLeft, max: available - minRight };
    }

    function stopDrag(event, persist = false) {
      if (!drag || (event && event.pointerId !== drag.id)) return;
      const pointerId = drag.id;
      drag = null;
      grid.classList.remove("rung-reading-dragging");
      try {
        if (divider.hasPointerCapture(pointerId)) divider.releasePointerCapture(pointerId);
      } catch (_) {
        // Pointer cancellation can release capture before the event arrives.
      }
      if (persist) save();
    }

    function paint() {
      if (destroyed) return;
      const { available, min, max } = bounds();
      stacked = compact.matches || available < minLeft + minRight;
      grid.classList.toggle("rung-reading-stacked", stacked);
      divider.hidden = stacked;
      divider.tabIndex = stacked ? -1 : 0;
      if (stacked) {
        stopDrag(null, true);
        hint.textContent = "Widen the window to resize the two panes side by side.";
        return;
      }
      hint.textContent = "Drag the divider to give either pane more space.";
      // Clamp the displayed width, not the saved ratio: temporary narrow windows
      // must not distort the user's preferred split when the window grows again.
      const left = Math.max(min, Math.min(max, ratio * available));
      grid.style.setProperty("--rung-inventory-width", `${left}px`);
      divider.setAttribute("aria-valuemin", String(Math.round(100 * min / available)));
      divider.setAttribute("aria-valuemax", String(Math.round(100 * max / available)));
      divider.setAttribute("aria-valuenow", String(Math.round(100 * left / available)));
      divider.setAttribute("aria-valuetext", `${leftLabel} ${Math.round(left)} pixels; ${rightLabel} ${Math.round(available - left)} pixels`);
    }

    function changeWidth(left) {
      const { available, min, max } = bounds();
      if (stacked || available < minLeft + minRight) return;
      ratio = Math.max(min, Math.min(max, left)) / available;
      paint();
    }

    function applyScale() {
      size.value = String(scale);
      grid.style.setProperty("--rung-equation-scale", String(scale / 100));
    }

    function reset() {
      stopDrag(null);
      ratio = defaultRatio;
      scale = DEFAULT_SCALE;
      applyScale();
      paint();
      save();
    }

    divider.addEventListener("pointerdown", (event) => {
      if (event.button !== 0 || event.isPrimary === false || stacked || drag) return;
      event.preventDefault();
      divider.focus();
      const { box, available, min, max } = bounds();
      const left = Math.max(min, Math.min(max, ratio * available));
      drag = { id: event.pointerId, offset: event.clientX - box.left - left };
      try {
        divider.setPointerCapture(event.pointerId);
      } catch (_) {
        drag = null;
        return;
      }
      grid.classList.add("rung-reading-dragging");
    });
    divider.addEventListener("pointermove", (event) => {
      if (!drag || event.pointerId !== drag.id) return;
      event.preventDefault();
      changeWidth(event.clientX - bounds().box.left - drag.offset);
    });
    divider.addEventListener("pointerup", (event) => stopDrag(event, true));
    divider.addEventListener("pointercancel", (event) => stopDrag(event, true));
    divider.addEventListener("lostpointercapture", (event) => stopDrag(event, true));
    divider.addEventListener("dblclick", () => {
      stopDrag(null);
      ratio = defaultRatio;
      paint();
      save();
    });
    divider.addEventListener("keydown", (event) => {
      if (stacked || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const { available, min, max } = bounds();
      const left = Math.max(min, Math.min(max, ratio * available));
      const increment = event.shiftKey ? 50 : 10;
      changeWidth(event.key === "Home" ? min : event.key === "End" ? max
        : left + (event.key === "ArrowRight" ? increment : -increment));
      save();
    });
    size.addEventListener("change", () => {
      const next = Number(size.value);
      if (!SCALES.includes(next)) return;
      scale = next;
      applyScale();
      save();
    });
    resetButton.addEventListener("click", reset);

    // ResizeObserver also handles leaving a hidden tab or changing sidebar size.
    const observer = typeof window.ResizeObserver === "function"
      ? new window.ResizeObserver(paint) : null;
    observer?.observe(grid);
    window.addEventListener("resize", paint);
    compact.addEventListener("change", paint);
    applyScale();
    paint();
    const api = {
      reset,
      destroy() {
        if (destroyed) return;
        destroyed = true;
        stopDrag(null);
        observer?.disconnect();
        window.removeEventListener("resize", paint);
        compact.removeEventListener("change", paint);
        divider.remove();
        controls.remove();
        grid.classList.remove("rung-reading-layout", "rung-reading-stacked");
        grid.style.removeProperty("--rung-inventory-width");
        grid.style.removeProperty("--rung-equation-scale");
        mounted.delete(grid);
      },
    };
    mounted.set(grid, api);
    return api;
  }

  window.PLCReadingLayout = Object.freeze({ mount });
})();
