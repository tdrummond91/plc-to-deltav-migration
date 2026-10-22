/* Local, read-only instruction help. Windows keep an explicit saved-run identity. */
(() => {
  'use strict';
  let getContext = () => ({}), panel = null, active = null, pending = null;
  let showTimer, hideTimer, suppressFocus = false, pointerPressed = null;
  const attached = new WeakMap();
  const el = (tag, text, className = '') => {
    const node = document.createElement(tag); node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const validId = value => typeof value === 'string' && value.length > 0 && value.length <= 240
    && !/[\x00-\x20\x7f]/.test(value);
  const validVariable = value => typeof value === 'string' && value.trim().length > 0 && value.length <= 4096 && !/[\x00-\x1f\x7f]/.test(value);
  const variableCache = new Map(), variableJobs = new Map(), variableQueue = [];
  let variableRequests = 0;
  const messageFor = error => error?.name === 'AbortError'
    ? 'The workspace took too long to respond. Check that it is running, then retry.'
    : error?.message || 'Saved variable evidence could not be loaded.';
  async function readJson(url) {
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(url, {cache: 'no-store', credentials: 'same-origin', signal: controller.signal});
      if (!response.ok) throw new Error('The saved evidence could not be loaded. Check that this project and analysis are still available.');
      return await response.json();
    } finally { clearTimeout(timeout); }
  }
  function freezeEvidence(value, depth = 0) {
    if (depth > 20) throw new Error('Saved variable evidence exceeds its display limits.');
    if (value && typeof value === 'object') {
      Object.values(value).forEach(child => freezeEvidence(child, depth + 1)); Object.freeze(value);
    }
    return value;
  }
  function drainVariableQueue() {
    while (variableRequests < 4 && variableQueue.length) {
      const job = variableQueue.shift(); variableRequests++;
      (async () => {
        try {
          const params = new URLSearchParams({run_id: job.runId, instruction_id: job.instructionId, variable: job.variable});
          const data = await readJson(`/api/variable?${params}`);
          if (!data || data.run_id !== job.runId || data.instruction_id !== job.instructionId || data.variable !== job.variable)
            throw new Error('This evidence does not match the requested variable and saved analysis. Reopen help from the source.');
          if (JSON.stringify(data).length > 1024 * 1024 || typeof data.available !== 'boolean'
              || ['captured_values', 'writers', 'limitations', 'representations'].some(key => data[key] !== undefined && (!Array.isArray(data[key]) || data[key].length > 256)))
            throw new Error('Saved variable evidence exceeds its display limits.');
          freezeEvidence(data);
          variableCache.set(job.key, data);
          while (variableCache.size > 96) variableCache.delete(variableCache.keys().next().value);
          job.resolve(data);
        } catch (error) { job.reject(error); }
        finally { variableJobs.delete(job.key); variableRequests--; drainVariableQueue(); }
      })();
    }
  }
  function loadVariable(instruction, variable, context = contextFor()) {
    const runId = context?.runId, instructionId = instruction?.id;
    if (!validId(runId) || !validId(instructionId) || !validVariable(variable))
      return Promise.reject(new Error('Variable help needs its captured instruction, address and saved analysis.'));
    const key = JSON.stringify([runId, instructionId, variable]);
    if (variableCache.has(key)) {
      const data = variableCache.get(key); variableCache.delete(key); variableCache.set(key, data); return Promise.resolve(data);
    }
    if (variableJobs.has(key)) return variableJobs.get(key).promise;
    if (variableJobs.size >= 96) return Promise.reject(new Error('Variable details are busy. Wait for the current requests, then retry.'));
    const job = {key, runId, instructionId, variable};
    job.promise = new Promise((resolve, reject) => { job.resolve = resolve; job.reject = reject; });
    variableJobs.set(key, job); variableQueue.push(job); drainVariableQueue(); return job.promise;
  }
  function contextFor(context) {
    const value = context || getContext() || {};
    return Object.freeze({runId: value.runId});
  }
  function helpUrl(instruction, context, variable = null) {
    if (!validId(instruction?.id) || !validId(context?.runId)) return null;
    const url = new URL('/instruction-help.html', window.location.origin);
    url.searchParams.set('id', instruction.id);
    url.searchParams.set('run_id', context.runId);
    if (variable !== null) {
      if (!validVariable(variable)) return null;
      url.searchParams.set('variable', variable);
    }
    url.searchParams.set('theme', document.documentElement.dataset.theme === 'light' ? 'light' : 'dark');
    return url.href;
  }
  function close(restoreFocus = false) {
    clearTimeout(showTimer); clearTimeout(hideTimer); pending = null;
    const previous = active; active = null;
    if (previous) previous.anchor.setAttribute('aria-expanded', 'false');
    if (panel) { panel.remove(); panel = null; }
    if (restoreFocus && previous?.anchor.isConnected) {
      suppressFocus = true; previous.anchor.focus({preventScroll: true}); suppressFocus = false;
    }
  }
  function place() {
    if (!active || !panel) return;
    const anchor = active.anchor;
    if (!anchor.isConnected || !anchor.getClientRects().length) { close(); return; }
    const rect = anchor.getBoundingClientRect();
    const margin = 12, gap = 10, width = window.innerWidth, height = window.innerHeight;
    if (rect.bottom < 0 || rect.top > height || rect.right < 0 || rect.left > width) { close(); return; }
    panel.style.maxHeight = `${Math.max(60, height - margin * 2)}px`;
    let box = panel.getBoundingClientRect();
    let left = rect.right + gap, top = rect.top;
    if (left + box.width > width - margin) {
      if (rect.left - gap - box.width >= margin) left = rect.left - gap - box.width;
      else {
        // Use the larger vertical gap and scroll inside it. Clamping a full-height
        // card above the block could otherwise cover the very target being clicked.
        const below = height - rect.bottom - gap - margin, above = rect.top - gap - margin;
        const useBelow = below >= above;
        panel.style.maxHeight = `${Math.max(60, useBelow ? below : above)}px`;
        box = panel.getBoundingClientRect();
        left = rect.left; top = useBelow ? rect.bottom + gap : rect.top - gap - box.height;
      }
    }
    panel.style.left = `${Math.max(margin, Math.min(left, width - box.width - margin))}px`;
    panel.style.top = `${Math.max(margin, Math.min(top, height - box.height - margin))}px`;
  }
  function deferClose() {
    clearTimeout(hideTimer);
    hideTimer = setTimeout(() => close(), 350);
  }
  function renderVariable(record, body) {
    if (!validId(record.context?.runId)) {
      body.replaceChildren(el('h2', record.variable), el('p',
        'Saved variable values and write sites are available when you open this report through the workspace.',
        'instruction-help-status'));
      return;
    }
    body.replaceChildren(el('p', `Loading saved evidence for ${record.variable}…`, 'instruction-help-status'));
    const expectedPanel = panel;
    loadVariable(record.instruction, record.variable, record.context).then(data => {
      if (active !== record || panel !== expectedPanel || !body.isConnected) return;
      if (!window.PLCVariableHelpContent) throw new Error('Variable help assets are unavailable. Refresh this workspace page.');
      body.replaceChildren(window.PLCVariableHelpContent.render(data)); place();
    }).catch(error => {
      if (active !== record || panel !== expectedPanel || !body.isConnected) return;
      const status = el('p', messageFor(error)); status.setAttribute('role', 'status');
      const retry = el('button', 'Retry variable help'); retry.type = 'button';
      retry.addEventListener('click', () => renderVariable(record, body)); body.replaceChildren(status, retry); place();
    });
  }
  function show(record, focus = false) {
    clearTimeout(showTimer); clearTimeout(hideTimer); pending = null;
    if (!record.anchor.isConnected || !record.anchor.getClientRects().length) return;
    if (active !== record || !panel) {
      close(); active = record;
      panel = el('section', undefined, 'instruction-help-panel');
      panel.id = 'instruction-hover-help'; panel.setAttribute('role', 'dialog');
      const subject = record.variable ? 'Variable help' : 'Instruction help';
      panel.setAttribute('aria-modal', 'false'); panel.setAttribute('aria-label', subject);
      const bar = el('div', undefined, 'instruction-help-toolbar');
      bar.append(el('span', `${subject} · Read only`, 'eyebrow'));
      const openButton = el('button', 'Open help window ↗'); openButton.type = 'button';
      openButton.addEventListener('click', () => open(record.instruction, record.context, record.variable));
      openButton.disabled = !helpUrl(record.instruction, record.context, record.variable);
      const closeButton = el('button', '×'); closeButton.type = 'button';
      closeButton.setAttribute('aria-label', record.variable ? 'Close variable help' : 'Close instruction help');
      closeButton.addEventListener('click', () => close(panel?.contains(document.activeElement)));
      bar.append(openButton, closeButton);
      const body = el('div', undefined, 'instruction-help-body');
      if (!record.variable) body.append(window.PLCInstructionHelpContent.render(record.instruction));
      panel.append(bar, body, el('p', 'Hover a variable for its saved values and writers, or a block for operation help. Ctrl-click (⌘-click on Mac) keeps that help in a separate window. F1 opens the focused item; Ctrl+Enter opens a window.', 'instruction-help-hint'));
      panel.addEventListener('pointerenter', () => clearTimeout(hideTimer));
      panel.addEventListener('pointerleave', event => {
        if (!record.anchor.contains(event.relatedTarget) && !panel.contains(document.activeElement)) deferClose();
      });
      panel.addEventListener('focusin', () => clearTimeout(hideTimer));
      panel.addEventListener('focusout', event => {
        if (!panel.contains(event.relatedTarget) && !record.anchor.contains(event.relatedTarget)) deferClose();
      });
      // Help for retained evidence inside a native dialog must share its top
      // layer; a body-level panel would be inert behind that dialog.
      (record.anchor.closest('dialog[open]') || document.body).append(panel);
      record.anchor.setAttribute('aria-expanded', 'true');
      if (record.variable) renderVariable(record, body);
    }
    place();
    if (focus && panel) panel.querySelector('button:not(:disabled)')?.focus({preventScroll: true});
  }
  function open(instruction, context = contextFor(), variable = null) {
    const url = helpUrl(instruction, context, variable);
    if (!url) return false;
    // _blank deliberately creates an independent window each time, even for the same block.
    const popup = window.open(url, '_blank', 'popup,width=620,height=780,resizable=yes,scrollbars=yes');
    if (popup) { popup.opener = null; return true; }
    if (panel) {
      const old = panel.querySelector('.instruction-help-blocked'); old?.remove();
      const notice = el('p', 'The browser blocked the help window. ', 'instruction-help-blocked');
      notice.setAttribute('role', 'status');
      const link = el('a', 'Open help in a new tab'); link.href = url; link.target = '_blank'; link.rel = 'noopener';
      notice.append(link); panel.append(notice); place();
    }
    return false;
  }
  function attach(anchor, instruction, context) {
    if (!anchor || attached.has(anchor) || !window.PLCInstructionHelpContent?.valid(instruction)) return;
    // Copy the bounded record: neither future UI state nor a changed source object can retarget this help.
    const captured = Object.freeze({id: instruction.id, opcode: instruction.opcode,
      arguments: Object.freeze([...instruction.arguments])});
    const record = {anchor, instruction: captured, context: contextFor(context)};
    attached.set(anchor, record);
    const members = new WeakMap();
    const subjectFor = target => {
      const token = target?.closest?.('[data-source-variable]');
      if (!token || !anchor.contains(token)) return record;
      const variable = token.getAttribute('data-source-variable');
      if (!validVariable(variable)) return record;
      if (!members.has(token)) {
        members.set(token, {anchor: token, instruction: captured, context: record.context, variable});
        if (!token.hasAttribute('tabindex')) token.setAttribute('tabindex', '0');
        token.setAttribute('aria-haspopup', 'dialog'); token.setAttribute('aria-expanded', 'false');
        token.setAttribute('aria-controls', 'instruction-hover-help');
        token.setAttribute('aria-keyshortcuts', 'F1 Control+Enter Meta+Enter');
        token.classList.add('has-variable-help');
      }
      return members.get(token);
    };
    anchor.querySelectorAll('[data-source-variable]').forEach(subjectFor);
    anchor.removeAttribute('title');
    anchor.querySelectorAll('title, [title]').forEach(node => {
      if (node.tagName.toLowerCase() === 'title') node.remove(); else node.removeAttribute('title');
    });
    if (!anchor.hasAttribute('tabindex')) anchor.setAttribute('tabindex', '0');
    anchor.setAttribute('aria-haspopup', 'dialog'); anchor.setAttribute('aria-expanded', 'false');
    anchor.setAttribute('aria-controls', 'instruction-hover-help');
    anchor.setAttribute('aria-keyshortcuts', 'F1 Control+Enter Meta+Enter');
    anchor.classList.add('has-instruction-help');
    const schedule = selected => {
      clearTimeout(hideTimer);
      if (active === selected) { clearTimeout(showTimer); pending = null; return; }
      if (pending === selected) return;
      clearTimeout(showTimer); pending = selected;
      showTimer = setTimeout(() => { if (pending === selected) show(selected); }, 240);
    };
    // pointerenter does not bubble from SVG tspans. Delegated pointerover keeps
    // member help ahead of its surrounding instruction, using the full token.
    anchor.addEventListener('pointerenter', event => {
      if (!pending || !anchor.contains(pending.anchor)) schedule(subjectFor(event.target));
    });
    anchor.addEventListener('pointerover', event => schedule(subjectFor(event.target)));
    anchor.addEventListener('pointerout', event => {
      if (anchor.contains(event.relatedTarget)) schedule(subjectFor(event.relatedTarget));
    });
    anchor.addEventListener('pointerleave', event => {
      if (pending && anchor.contains(pending.anchor)) { clearTimeout(showTimer); pending = null; }
      if (active && anchor.contains(active.anchor) && !panel?.contains(event.relatedTarget) && !active.anchor.contains(document.activeElement)) deferClose();
    });
    anchor.addEventListener('pointerdown', () => {
      // Focus follows pointerdown, before click. Do not insert a panel under an
      // in-progress click; the completed Ctrl-click opens help synchronously.
      pointerPressed = record; clearTimeout(showTimer); pending = null;
    }, true);
    anchor.addEventListener('focusin', event => { if (!suppressFocus && pointerPressed !== record) show(subjectFor(event.target)); });
    anchor.addEventListener('focusout', event => {
      if (active && anchor.contains(active.anchor) && !panel?.contains(event.relatedTarget) && !anchor.contains(event.relatedTarget)) deferClose();
    });
    anchor.addEventListener('click', event => {
      if (!event.ctrlKey && !event.metaKey) return;
      event.preventDefault(); event.stopImmediatePropagation();
      const selected = subjectFor(event.target); show(selected); open(captured, selected.context, selected.variable);
    }, true);
    anchor.addEventListener('keydown', event => {
      if (event.key === 'F1' || (event.key === 'Enter' && (event.ctrlKey || event.metaKey))) {
        event.preventDefault(); event.stopImmediatePropagation();
        const selected = subjectFor(event.target); show(selected, event.key === 'F1');
        if (event.key === 'Enter') open(captured, selected.context, selected.variable);
      }
    }, true);
  }
  document.addEventListener('pointerdown', event => {
    if (active && !active.anchor.contains(event.target) && !panel?.contains(event.target)) close();
    else if (pending && !pending.anchor.contains(event.target)) close();
  }, true);
  document.addEventListener('pointerup', () => { pointerPressed = null; }, true);
  document.addEventListener('pointercancel', () => { pointerPressed = null; }, true);
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && active) {
      event.preventDefault(); event.stopImmediatePropagation(); close(panel?.contains(document.activeElement));
    }
  }, true);
  document.addEventListener('scroll', event => {
    if (panel?.contains(event.target)) return;
    if (panel?.contains(document.activeElement)) place(); else close();
  }, true);
  window.addEventListener('resize', place);
  window.addEventListener('blur', () => { pointerPressed = null; });
  new MutationObserver(() => {
    if (active && (!active.anchor.isConnected || !active.anchor.getClientRects().length)) close();
    if (pending && !pending.anchor.isConnected) { clearTimeout(showTimer); pending = null; }
  }).observe(document.body, {childList: true, subtree: true, attributes: true, attributeFilter: ['hidden', 'open']});

  async function loadWindow(root) {
    const query = new URLSearchParams(window.location.search);
    document.documentElement.dataset.theme = query.get('theme') === 'light' ? 'light' : 'dark';
    const id = query.get('id'), runId = query.get('run_id'), variable = query.get('variable');
    const status = el('p', variable === null ? 'Opening saved instruction…' : 'Opening saved variable evidence…'); status.setAttribute('role', 'status'); root.replaceChildren(status);
    try {
      if (!validId(id) || !validId(runId)) throw new Error('This help link is missing its instruction or saved analysis. Open help from a block in the workspace.');
      if (variable !== null) {
        const data = await loadVariable({id}, variable, {runId});
        if (!window.PLCVariableHelpContent) throw new Error('Variable help assets are unavailable. Refresh this page.');
        document.title = `${variable} · Variable help · PLC Workbench`;
        root.setAttribute('aria-label', 'Saved variable help');
        const heading = document.getElementById('instruction-help-window-title');
        if (heading) heading.textContent = 'PLC Workbench · Variable help';
        root.replaceChildren(el('p', `Saved analysis: ${runId}${data.historical ? ' · Earlier analysis' : ''}`, 'instruction-help-provenance'),
          window.PLCVariableHelpContent.render(data));
        return;
      }
      const params = new URLSearchParams({id, run_id: runId});
      const data = await readJson(`/api/source?${params}`);
      if (data.run_id !== runId || data.kind !== 'instruction' || data.source?.id !== id
          || !window.PLCInstructionHelpContent.valid(data.source))
        throw new Error('This saved record does not match the requested instruction. Reopen help from the workspace.');
      document.title = `${data.source.opcode} · Instruction help · PLC Workbench`;
      const path = el('p', data.path || id, 'instruction-help-path');
      const source = el('p', `Saved analysis: ${runId}${data.historical ? ' · Earlier analysis' : ''}`, 'instruction-help-provenance');
      root.replaceChildren(path, source, window.PLCInstructionHelpContent.render(data.source));
    } catch (error) {
      status.textContent = messageFor(error);
      const retry = el('button', 'Retry'); retry.type = 'button'; retry.addEventListener('click', () => loadWindow(root)); root.append(retry);
    }
  }
  window.PLCInstructionHelp = Object.freeze({attach, close, open, loadVariable,
    configure(options = {}) { close(); getContext = typeof options.getContext === 'function' ? options.getContext : () => ({}); }});
  const root = document.getElementById('instruction-help-window');
  if (root) loadWindow(root);
})();
