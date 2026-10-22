/* Lazy routine directory. Source order and diagrams are read-only. */
(() => {
  'use strict';
  const DIRECTORY_SIZE = 50;
  const el = (tag, text, cls = '') => {
    const node = document.createElement(tag); node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const button = (text, action) => {
    const node = el('button', text); node.type = 'button';
    node.addEventListener('click', action); return node;
  };
  const field = (text, control) => {
    control.setAttribute('aria-label', text);
    const label = el('label', text); label.append(control); return label;
  };
  function mount(root, options) {
    const filters = el('div', undefined, 'filters routine-directory-filters');
    const query = el('input', undefined, 'routine-directory-search');
    query.type = 'search'; query.placeholder = 'Routine, program or source path…'; query.maxLength = 1000;
    const program = el('select', undefined, 'routine-directory-program');
    const type = el('select', undefined, 'routine-directory-type');
    const reset = button('Clear routine filters', () => {
      query.value = ''; program.value = ''; type.value = ''; page = 1; renderDirectory();
    });
    filters.append(field('Find a routine', query), field('Program / AOI scope', program), field('Routine type', type), reset);
    const status = el('p', undefined, 'routine-directory-status'); status.setAttribute('role', 'status');
    const list = el('div', undefined, 'routine-directory-list');
    const pager = el('div', undefined, 'pagination routine-directory-pagination');
    const help = el('details', undefined, 'routine-directory-help');
    help.append(el('summary', 'How to read these ladders'),
      el('p', 'Expand one routine at a time. Ladder pages contain up to 20 rungs; other source types stay available through their source link. Contacts test a bit, coils write a bit, and boxes retain other instructions and their arguments. Parallel paths split and rejoin as captured. Neutral lines do not show live controller states.', 'muted'));
    root.append(filters, status, help, pager, list);
    let key = '', runId = '', active = false, serial = 0, page = 1, routines = [], opened = null;
    const projectKey = () => {
      const state = options.getState() || {};
      return JSON.stringify([state.project_path || '', state.active_run || '']);
    };
    const scope = routine => routine.scope_id || routine.program_id || routine.program_path || '(unassigned)';
    const scopeLabel = routine => routine.scope_path || routine.program_path || routine.program_name || '(Unassigned scope)';
    const routineType = routine => routine.type || 'Unspecified';
    function choices(control, entries, all) {
      const before = control.value; control.replaceChildren();
      const first = el('option', all); first.value = ''; control.append(first);
      entries.forEach(([id, label]) => { const option = el('option', label); option.value = id; control.append(option); });
      control.value = entries.some(([id]) => id === before) ? before : '';
    }
    function closeCurrent() {
      serial++;
      if (!opened) return;
      const old = opened; opened = null;
      old.details.open = false; old.body.replaceChildren();
    }
    function renderDirectory() {
      closeCurrent(); list.replaceChildren();
      const text = query.value.trim().toLocaleLowerCase();
      const matches = routines.filter(routine => (!program.value || scope(routine) === program.value)
        && (!type.value || routineType(routine) === type.value)
        && (!text || [routine.name, routine.path, scopeLabel(routine)].join(' ').toLocaleLowerCase().includes(text)));
      const pages = Math.max(1, Math.ceil(matches.length / DIRECTORY_SIZE));
      page = Math.max(1, Math.min(page, pages));
      status.textContent = runId ? `${matches.length.toLocaleString()} of ${routines.length.toLocaleString()} routines match. Page ${page} of ${pages}.`
        : 'Choose an analysis under Project tools to browse its programs and routines.';
      const previous = button('Previous routines', () => { page--; renderDirectory(); }); previous.disabled = page <= 1;
      const next = button('Next routines', () => { page++; renderDirectory(); }); next.disabled = page >= pages;
      const jump = el('input', undefined, 'routine-directory-page');
      jump.type = 'number'; jump.min = '1'; jump.max = String(pages); jump.value = String(page);
      jump.addEventListener('change', () => {
        const value = Number(jump.value);
        if (Number.isInteger(value) && value >= 1 && value <= pages) { page = value; renderDirectory(); }
        else jump.value = String(page);
      });
      pager.replaceChildren(previous, field('Directory page', jump), next);
      pager.hidden = pages <= 1;
      matches.slice((page - 1) * DIRECTORY_SIZE, page * DIRECTORY_SIZE).forEach(routine => {
        const details = el('details', undefined, 'routine-directory-entry'); details.dataset.routineId = routine.id;
        const summary = el('summary');
        summary.setAttribute('aria-label', `${routine.path || routine.name || routine.id}, ${routineType(routine)}, ${routine.count || 0} captured rungs`);
        summary.append(el('strong', routine.name || routine.id), el('span', routine.path || scopeLabel(routine), 'routine-directory-path'),
          el('span', `${routineType(routine)} · ${routine.count || 0} captured rungs`, 'chip'));
        const body = el('div', undefined, 'routine-directory-body'); details.append(summary, body);
        details.addEventListener('toggle', () => {
          if (!details.open) { if (opened?.details === details) closeCurrent(); return; }
          if (opened?.details === details || !active) return;
          closeCurrent();
          // Closing the preceding entry does not close this newly opened row.
          details.open = true;
          opened = {routine, details, body, page: 1, requestedPage: 1, payload: null, comments: new Map(), loading: false};
          load(opened, 1);
        });
        list.append(details);
      });
      if (!matches.length) list.append(el('p', runId ? 'No routines match these filters.' : 'No analysis is selected.', 'empty'));
    }
    function paintComment(target, rung, mode) {
      if (!rung.comment) { target.replaceChildren(el('p', 'No rung comment captured.', 'muted')); return; }
      window.PLCTranslation.renderProse(target, rung.comment, rung.wording?.comment, mode);
    }
    async function load(entry, rungPage, wordingOnly = false) {
      if (!active || opened !== entry || projectKey() !== key) return;
      const generation = ++serial, expectedRun = runId, expectedKey = key;
      entry.loading = true;
      entry.requestedPage = rungPage;
      entry.error?.remove(); entry.error = null;
      if (!wordingOnly) {
        entry.payload = null; entry.comments.clear();
        entry.body.replaceChildren(el('p', `Loading rung page ${rungPage}…`, 'routine-loading'));
      }
      const current = () => active && opened === entry && entry.details.open && generation === serial
        && key === expectedKey && projectKey() === expectedKey;
      try {
        const result = await options.api('/api/routine-ladder?' + new URLSearchParams({routine: entry.routine.id, page: String(rungPage), run_id: expectedRun}));
        if (!current()) return;
        if (result.run_id !== expectedRun || result.routine?.id !== entry.routine.id)
          throw new Error('The source changed while this routine was loading. Use Refresh saved data in Project tools.');
        entry.page = result.page; entry.loading = false;
        if (wordingOnly && entry.payload) {
          result.items.forEach(rung => { const target = entry.comments.get(rung.id); if (target) paintComment(target, rung, result.presentation_mode); });
          entry.payload = result; return;
        }
        entry.payload = result; entry.comments.clear(); entry.body.replaceChildren();
        const actions = el('div', undefined, 'routine-actions');
        actions.append(options.reportLink('Open routine source ↗', entry.routine.id, result.routine.type === 'SFC' ? 'sfc' : 'objects'),
          button('Review routine rungs', () => options.review(entry.routine.id)));
        entry.body.append(actions);
        if (result.notice && (!result.available || !result.total)) entry.body.append(el('p', result.notice, 'muted'));
        if (!result.total) { entry.body.append(el('p', 'No captured ladder rungs in this routine. Use Open routine source to inspect its available content.', 'empty')); return; }
        const paging = () => {
          const controls = el('div', undefined, 'pagination routine-rung-pagination');
          const previous = button('Previous rung page', () => load(entry, entry.page - 1)); previous.disabled = result.page <= 1;
          const next = button('Next rung page', () => load(entry, entry.page + 1)); next.disabled = result.page >= result.pages;
          const start = (result.page - 1) * result.page_size + 1, end = start + result.items.length - 1;
          controls.append(previous, el('span', `${start}–${end} of ${result.total} rungs · page ${result.page} of ${result.pages}`), next);
          controls.hidden = result.pages <= 1;
          return controls;
        };
        entry.body.append(paging());
        result.items.forEach(rung => {
          const card = el('section', undefined, 'routine-rung'); card.dataset.sourceId = rung.id;
          const heading = el('div', undefined, 'routine-rung-heading');
          heading.append(el('h2', `Rung ${rung.number ?? '?'}`), button('Open rung review', () => options.review(entry.routine.id, rung.id)));
          const comment = el('div', undefined, 'routine-rung-comment'); entry.comments.set(rung.id, comment);
          paintComment(comment, rung, result.presentation_mode);
          card.append(heading, comment, window.PLCLadderDiagram.render(rung, {
            sourceQualified: rung.source_qualified === true,
            onInstruction: instruction => {
              if (projectKey() !== expectedKey) throw new Error('The active analysis changed. Refresh this routine before inspecting its instructions.');
              return options.inspect(instruction);
            },
          }));
          entry.body.append(card);
        });
        entry.body.append(paging());
      } catch (error) {
        if (!current()) return;
        entry.loading = false;
        if (!wordingOnly) entry.body.replaceChildren();
        entry.error = el('div', undefined, 'routine-page-error');
        entry.error.setAttribute('role', 'alert');
        entry.error.append(el('p', error.message || 'This routine could not be loaded.', 'warning-panel'),
          button('Retry routine page', () => load(entry, rungPage, wordingOnly)));
        entry.body.append(entry.error);
      }
    }
    function refresh() {
      active = true;
      const state = options.getState() || {}, nextKey = projectKey();
      if (nextKey !== key) {
        key = nextKey; runId = state.active_run || ''; page = 1;
        routines = state.routines || [];
        query.value = ''; program.value = ''; type.value = '';
        const scopes = new Map(routines.map(routine => [scope(routine), scopeLabel(routine)]));
        choices(program, [...scopes].sort((a,b) => a[1].localeCompare(b[1])), 'All programs / AOIs');
        choices(type, [...new Set(routines.map(routineType))].sort().map(value => [value,value]), 'All routine types');
        renderDirectory();
      } else if (opened?.loading) load(opened, opened.requestedPage, opened.payload?.page === opened.requestedPage);
    }
    function deactivate() { active = false; serial++; }
    function wordingChanged() {
      if (active && opened) {
        const target = opened.loading ? opened.requestedPage : opened.page;
        load(opened, target, opened.payload?.page === target);
      }
    }
    [program, type].forEach(control => control.addEventListener('change', () => { page = 1; renderDirectory(); }));
    query.addEventListener('input', () => { page = 1; renderDirectory(); });
    return {refresh, deactivate, wordingChanged};
  }
  window.PLCRoutineBrowser = Object.freeze({mount});
})();
