/* This preference stays in this browser. Report evidence is never stored here. */
(() => {
  'use strict';
  const root = document.documentElement;
  const button = document.getElementById('theme-toggle');
  if (!root || !button) return;
  const storageKey = 'plc-workbench-theme';
  let mode = 'dark';
  try {
    const saved = window.localStorage.getItem(storageKey);
    if (saved === 'light' || saved === 'dark') mode = saved;
  } catch (_) {
    // Local file storage can be unavailable; switching still works for this page.
  }
  function apply() {
    const current = mode === 'dark' ? 'Dark' : 'Light';
    const target = mode === 'dark' ? 'light' : 'dark';
    root.dataset.theme = mode;
    button.textContent = `${current} mode · Switch to ${target}`;
    button.setAttribute('aria-label', `${current} mode is on. Switch to ${target} mode`);
  }
  apply();
  button.hidden = false;
  button.addEventListener('click', () => {
    mode = mode === 'dark' ? 'light' : 'dark';
    apply();
    try {
      window.localStorage.setItem(storageKey, mode);
    } catch (_) {
      // The visible theme remains usable even when persistence is blocked.
    }
  });
})();
