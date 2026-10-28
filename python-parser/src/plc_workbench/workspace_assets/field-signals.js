/* Individual source signals and explicit, revision-bound engineering packages. */
(() => {
  'use strict';
  const TYPES = {di: 'DI', do: 'DO', ai: 'AI', ao: 'AO', unknown: 'Unclassified'};
  const PAGE_SIZES = [10, 50, 100, 200, 500];
  const ROLES = {scaling: 'Scaling', alarm: 'Alarm', reference: 'Reference', logic: 'Logic'};
  const USAGE = {referenced: 'Used in logic', possible_indirect: 'Indirect reference',
    not_found: 'No references found', unknown: 'Not checked'};
  const USAGE_ROLES = {read: 'Read', write: 'Write', read_write: 'Read/write', unknown: 'Role unknown'};
  const USAGE_GAPS = {missing_access: 'Saved read/write roles are unavailable', unparsed_rungs: 'Some rungs were not parsed',
    missing_logic: 'No ladder routines were captured in this source', partial_export: 'Source is a partial controller export',
    unsupported_routines: 'Some routine languages are unsupported', protected_logic: 'Some logic is protected',
    incomplete_routines: 'Some routine content is incomplete', opaque_expressions: 'Some expressions were not analyzed',
    unscanned_index_expressions: 'References inside some array index expressions have not been scanned',
    unsupported_instructions: 'Read/write roles are not classified for some instructions', unqualified_source: 'Some source could not be qualified',
    unresolved_references: 'Some source names could not be resolved', usage_index_limit: 'The usage scan reached its limits'};
  const REFERENCE_REASONS = {aggregate_parent: 'A containing word or structure is referenced',
    aggregate_child: 'A member below this address is referenced', range_unresolved: 'The copy or fill range has not been resolved to individual members',
    dynamic_index: 'A variable index selects the member; its value is determined at runtime', equivalent_static_index: 'Equivalent numeric array index spelling'};
  const count = value => Number.isInteger(value) && value >= 0 ? value : 0;
  const usageOf = row => row.usage && Object.hasOwn(USAGE, row.usage.status) ? row.usage
    : {status: 'unknown', coverage_complete: false};
  const referenceCounts = (references, rungs, kind) =>
    `${count(references)} ${kind} reference${count(references) === 1 ? '' : 's'} · ${count(rungs)} rung${count(rungs) === 1 ? '' : 's'}`;
  const wording = value => typeof value === 'string' && value.trim() ? value : '';
  const indirectDetail = usage => wording(usage.detail)
    || wording(usage.possible_uses?.[0]?.explanation)
    || REFERENCE_REASONS[usage.possible_uses?.[0]?.reason]
    || 'Open the source reference for target-resolution details.';
  const usageCount = usage => {
    if (usage.status === 'referenced') {
      const parts = [];
      if (count(usage.direct_count) || !count(usage.resolved_count)) parts.push(referenceCounts(usage.direct_count, usage.direct_rung_count, 'exact'));
      if (count(usage.resolved_count)) parts.push(referenceCounts(usage.resolved_count, usage.resolved_rung_count, 'resolved'));
      return parts.join('; ');
    }
    return usage.status === 'possible_indirect' ? referenceCounts(usage.possible_count, usage.possible_rung_count, 'indirect')
      : usage.status === 'not_found' ? 'Within scanned source' : 'Reference scan unavailable';
  };
  const MAPPING = {exact_catalog_direction_member_and_captured_profile_type: 'Catalog, data direction, member layout and captured datatype match the documented profile.',
    captured_member_layout_requires_review: 'The module type is recognized, but this member layout still needs review.',
    qualified_floating_channel_requires_review: 'A floating-point payload and input/output direction are captured. They suggest a numeric signal; its physical channel mapping remains unresolved.',
    captured_member_and_catalog_require_review: 'The member layout and module catalog both need review.'};
  const el = (tag, text, cls = '') => {
    const item = document.createElement(tag); item.className = cls;
    if (text !== undefined && text !== null) item.textContent = String(text);
    return item;
  };
  const button = (label, action, cls = '') => {
    const item = el('button', label, cls); item.type = 'button'; item.addEventListener('click', action); return item;
  };
  const field = (label, input) => {
    const item = el('label', label); input.setAttribute('aria-label', label); item.append(input); return item;
  };
  const select = (entries, value, cls = '') => {
    const item = el('select', undefined, cls);
    entries.forEach(([id, label]) => { const option = el('option', label); option.value = id; item.append(option); });
    item.value = value; return item;
  };
  const input = (value, cls, multiline = false) => {
    const item = el(multiline ? 'textarea' : 'input', undefined, cls); item.value = value || ''; return item;
  };
  const pageValid = (page, limit) => page && Array.isArray(page.items) && page.items.length <= limit
    && Number.isInteger(page.total) && page.total >= 0 && Number.isInteger(page.page) && page.page > 0
    && Number.isInteger(page.pages) && page.pages >= page.page && page.page_size === limit;
  const sameBinding = (left, right) => left && right && ['run_id', 'snapshot_id', 'root_id', 'suffix', 'address_id', 'evidence_signature']
    .every(key => left[key] === right[key]);
  const sameEvidence = (left, right) => left && right && ['snapshot_id', 'root_id', 'suffix', 'address_id', 'evidence_signature']
    .every(key => left[key] === right[key]);
  const preferredNote = row => row.preferred_annotation || row.source_annotations?.find(note => note.id === row.description_selection?.preferred_annotation_id);
  const textOf = row => preferredNote(row)?.text || (row.description_selection ? row.description : row.source_annotations?.[0]?.text || row.description) || '';
  const wordingOf = row => preferredNote(row)?.wording || row.wording?.description;
  const descriptionNotice = row => row.description_selection?.conflict ? 'Conflicting source wording · review alternatives' : '';
  const labelOf = row => row.aliases?.[0]?.name || row.address || row.id;
  const proposedName = row => row.suggested_target_name ?? row.aliases?.[0]?.name ?? row.source_metadata?.base_name ?? '';
  const controllerOf = row => {
    const source = row.hardware || {}, controller = source.controller || {};
    const name = controller.name || source.controller_name || 'Controller not captured';
    return {id: controller.id || source.controller_id || name, name};
  };

  function mount(root, options) {
    const filters = el('form', undefined, 'filters field-signals-filters');
    const query = input('', 'field-signals-query'); query.type = 'search'; query.maxLength = 256;
    const type = select([['', 'All types'], ...Object.entries(TYPES)], '', 'field-signals-type');
    const section = select([['all', 'Signals and candidates'], ['signals', 'Documented signals'], ['candidates', 'Mapping candidates']], 'all', 'field-signals-section');
    const usage = select([['', 'All usage'], ...Object.entries(USAGE)], '', 'field-signals-usage-filter');
    const hideEmpty = el('input', undefined, 'field-signals-hide-empty'); hideEmpty.type = 'checkbox';
    const pageSize = select(PAGE_SIZES.map(size => [String(size), String(size)]), '50', 'field-signals-page-size');
    const submit = el('button', 'Search'); submit.type = 'submit';
    filters.append(field('Find alias, address, DeltaV name, package or source wording', query), field('Physical type / candidate', type),
      field('Evidence', section), field('Logic usage', usage), field('Hide empty unreferenced rows', hideEmpty), submit);
    const referenceScan = el('details', undefined, 'field-signals-reference-scan');
    referenceScan.setAttribute('aria-label', 'Reference scan'); referenceScan.setAttribute('tabindex', '-1'); referenceScan.hidden = true;
    const status = el('p', undefined, 'field-signals-status'); status.setAttribute('role', 'status');
    const draftsNotice = el('div', undefined, 'field-signals-drafts');
    const layout = el('div', undefined, 'field-signals-layout');
    const directory = el('section', undefined, 'field-signals-directory');
    const tableWrap = el('div', undefined, 'field-signals-controller-list'), pager = el('div', undefined, 'pagination');
    const footer = el('div', undefined, 'field-signals-footer'), filterSummary = el('small', undefined, 'field-signals-filter-summary muted');
    const audit = button('Download I/O audit', downloadAudit, 'field-signals-audit');
    audit.title = 'Download inventory, usage and description counts for this analysis; no source names or logic.';
    footer.append(field('Signals per page', pageSize), pager, audit, filterSummary);
    const controllerTools = el('div', undefined, 'field-signals-controller-tools');
    const detail = el('section', undefined, 'field-signals-detail'); detail.setAttribute('aria-label', 'Selected field signal and engineering package');
    directory.append(controllerTools, tableWrap, footer); layout.append(directory, detail);
    root.replaceChildren(filters, referenceScan, status, draftsNotice, layout);
    const drafts = new Map();
    const controllerStates = new Map(); let controllerPanels = [], controllersExpanded = true;
    let active = true, key = '', runId = '', listSerial = 0, detailSerial = 0, page = 1, selectedId = '', selectedDraft = null, detailPageSize = 10;
    let applied = {query: '', field_type: '', section: 'all', usage: '', hide_empty: '0', page_size: '50'}, saving = false, auditing = false, hardware = null, hardwareTimer = null, suppressHardwareFocus = false;
    const state = () => options.getState() || {};
    const identity = () => JSON.stringify([state().project_path || '', state().active_run || '']);
    const current = expected => active && key === expected && identity() === expected;
    const draftKey = (id, context = key) => JSON.stringify([context, id]);
    const dirty = draft => Boolean(draft && (draft.signalDirty || [...draft.packages.values()].some(item => item.dirty)));
    const hasUnsavedChanges = () => [...drafts.values()].some(dirty);
    const message = (text, error = false) => { status.textContent = text; status.className = 'field-signals-status' + (error ? ' is-error' : ''); };
    const changed = () => { paintDrafts(); options.onDirtyChange?.(hasUnsavedChanges()); };
    function requireCurrent(expected) {
      if (current(expected)) return true;
      message('The project or analysis changed. Your edits are retained; reopen this source in its original analysis before saving.', true);
      return false;
    }
    function url(extra = {}) {
      return '/api/field-signals?' + new URLSearchParams({run_id: runId, ...applied, page: String(page), ...extra});
    }
    async function downloadAudit() {
      if (auditing || !runId || !requireCurrent(key)) return;
      const expected = key, expectedRun = runId;
      auditing = true; audit.disabled = true;
      try {
        const result = await options.api('/api/field-signals-audit?' + new URLSearchParams({run_id: expectedRun}));
        if (!current(expected)) return;
        if (!result || result.run_id !== expectedRun) throw new Error('The audit does not match this analysis. Refresh and try again.');
        if (!result.audit || result.audit.schema_version !== 1) throw new Error('This I/O audit format is unavailable. Refresh and try again.');
        // Run/revision are request guards, never part of the count-only file.
        const blob = new Blob([JSON.stringify(result.audit, null, 2) + '\n'], {type: 'application/json'});
        const address = URL.createObjectURL(blob), link = el('a');
        link.href = address; link.download = 'field-io-audit.json';
        try { document.body.append(link); link.click(); }
        finally { link.remove(); setTimeout(() => URL.revokeObjectURL(address), 1000); }
        message('I/O audit downloaded. It contains counts, with no source names or logic.');
      } catch (error) {
        if (current(expected)) message(error.message || 'The I/O audit could not be downloaded.', true);
      } finally { auditing = false; audit.disabled = !active || !runId; }
    }
    function checkResult(result, expectedRun, expectedPageSize) {
      if (!result || result.run_id !== expectedRun || !Number.isInteger(result.revision) || result.revision < 0 || !pageValid(result.signals, expectedPageSize))
        throw new Error('Signal evidence did not match the requested analysis or page bounds. Reload the list.');
    }
    function sourceLink(label, ownerId, view = 'objects', expected = key) {
      const link = el('a', label); link.href = ownerId
        ? '/?panel=source&run_id=' + encodeURIComponent(runId) + '#view=' + (view === 'ladder' ? 'rungs' : 'objects') + '&source=' + encodeURIComponent(ownerId)
        : '/#view=objects';
      link.target = '_blank'; link.rel = 'noopener';
      const guard = event => { if (!requireCurrent(expected)) event.preventDefault(); };
      link.addEventListener('click', guard); link.addEventListener('auxclick', guard); return link;
    }
    function prose(target, original, wording, mode) {
      if (typeof original !== 'string' || !original.trim()) {
        target.textContent = 'No source description captured';
        target.className += ' field-signals-description-missing'; return;
      }
      if (window.PLCTranslation?.renderProse) window.PLCTranslation.renderProse(target, original, wording, mode);
      else target.textContent = original;
    }
    function paintDrafts() {
      draftsNotice.replaceChildren();
      const pending = [...drafts.values()].filter(dirty);
      if (!pending.length) return;
      const list = el('details'); list.append(el('summary', `${pending.length} signal draft${pending.length === 1 ? '' : 's'} with unsaved edits`));
      pending.forEach(draft => {
        const row = el('div', undefined, 'field-signals-draft-row');
        const restore = button(labelOf(draft.row), () => {
          if (!requireCurrent(draft.context)) return;
          selectedId = draft.row.id; selectedDraft = draft; paintEditor(draft); revealEditor();
        });
        row.append(restore, el('span', draft.context === key ? 'Current analysis' : 'Retained from another project or analysis', 'muted'));
        if (draft.context !== key) {
          const retained = el('pre', JSON.stringify({target_name: draft.target_name, description: draft.description, field_type: draft.field_type,
            packages: [...draft.packages.values()].filter(item => item.dirty).map(item => ({name: item.name, member_ids: [...item.members], signal_ids: [...item.signals], member_roles: item.roles}))}, null, 2));
          const copy = el('details'); copy.append(el('summary', 'Read retained edits'), retained); row.append(copy);
        }
        list.append(row);
      });
      draftsNotice.append(list);
    }
    function closeHardware() {
      clearTimeout(hardwareTimer); hardwareTimer = null;
      if (hardware) { hardware.anchor.setAttribute('aria-expanded', 'false'); hardware.panel.remove(); hardware = null; }
    }
    function hardwareButton(row) {
      const expected = key, info = button('', () => {
        if (hardware?.anchor === info) { hardware.pinned = !hardware.pinned; if (!hardware.pinned) closeHardware(); }
        else show(true);
      }, 'field-signals-hardware-info');
      const symbol = el('span', 'i', 'field-signals-info-symbol'); symbol.setAttribute('aria-hidden', 'true'); info.append(symbol);
      info.setAttribute('aria-label', 'Hardware information for ' + labelOf(row));
      info.setAttribute('aria-expanded', 'false'); info.setAttribute('aria-haspopup', 'dialog');
      const leave = () => { clearTimeout(hardwareTimer); hardwareTimer = setTimeout(() => { if (!hardware?.pinned) closeHardware(); }, 180); };
      function show(pinned = false) {
        if (!requireCurrent(expected)) return;
        clearTimeout(hardwareTimer);
        if (hardware?.anchor === info) { if (pinned) hardware.pinned = true; return; }
        closeHardware();
        const panel = el('aside', undefined, 'field-signals-hardware-popover'); panel.setAttribute('role', 'dialog');
        panel.setAttribute('aria-label', 'Captured hardware information');
        const source = row.hardware || {}, facts = el('dl');
        [['Module', source.name || source.module_name], ['Controller', source.controller?.name || source.controller_name],
          ['Catalog', source.catalog_number], ['Rack / parent', source.parent_module_name], ['Slot', source.slot],
          ['Source address', row.address], ['Data direction', row.direction]].forEach(([label, value]) => {
          facts.append(el('dt', label), el('dd', value ?? 'Not captured'));
        });
        panel.append(el('strong', 'Hardware information'), button('Close hardware information', closeHardware, 'text-link'), facts);
        if (source.id) panel.append(sourceLink('Open module source', source.id, 'objects', expected));
        if (source.controller?.id) panel.append(sourceLink('Open controller source', source.controller.id, 'objects', expected));
        if (source.catalog_description) panel.append(el('p', source.catalog_description), el('small', 'Manufacturer catalog wording; separate from the source description.', 'muted'));
        panel.append(el('small', 'Source address and module evidence do not establish physical wiring or live values.', 'muted'));
        panel.addEventListener('pointerenter', () => clearTimeout(hardwareTimer)); panel.addEventListener('pointerleave', leave);
        panel.addEventListener('focusin', () => { clearTimeout(hardwareTimer); if (hardware) hardware.pinned = true; });
        document.body.append(panel); info.setAttribute('aria-expanded', 'true'); hardware = {anchor: info, panel, pinned};
        const box = info.getBoundingClientRect(), width = Math.min(380, Math.max(160, window.innerWidth - 24));
        panel.style.width = width + 'px'; panel.style.left = Math.max(12, Math.min(box.left, window.innerWidth - width - 12)) + 'px';
        panel.style.maxHeight = Math.max(100, window.innerHeight - 32) + 'px';
        const height = panel.getBoundingClientRect().height;
        panel.style.top = Math.max(12, Math.min(box.bottom + 8, window.innerHeight - height - 12)) + 'px';
      }
      info.addEventListener('pointerenter', () => show()); info.addEventListener('pointerleave', leave);
      info.addEventListener('focus', () => { if (!suppressHardwareFocus) show(); });
      info.addEventListener('blur', event => { if (!hardware?.panel.contains(event.relatedTarget)) leave(); });
      return info;
    }
    document.addEventListener('pointerdown', event => {
      if (hardware && !hardware.panel.contains(event.target) && !hardware.anchor.contains(event.target)) closeHardware();
    });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && hardware) {
        const anchor = hardware.anchor; closeHardware(); suppressHardwareFocus = true;
        try { anchor.focus({preventScroll: true}); } finally { suppressHardwareFocus = false; }
        event.preventDefault();
      }
    });
    window.addEventListener('resize', closeHardware);
    function pageControls(target, result, label, action) {
      const previous = button('Previous ' + label, () => action(result.page - 1)); previous.disabled = result.page <= 1;
      const next = button('Next ' + label, () => action(result.page + 1)); next.disabled = result.page >= result.pages;
      target.replaceChildren(previous, el('span', `${result.total} ${label} · page ${result.page} of ${result.pages}`), next);
      target.hidden = result.pages <= 1;
    }
    function paintReferenceScan(result) {
      referenceScan.hidden = false;
      const scan = result?.coverage?.reference_scan;
      const hasCounts = scan && ['rungs_total', 'rungs_scanned', 'rungs_not_scanned'].every(name => Number.isInteger(scan[name]) && scan[name] >= 0);
      const available = scan?.available === true;
      const heading = el('summary');
      heading.append(el('strong', 'Reference scan'), el('span', hasCounts
        ? `${scan.rungs_scanned} / ${scan.rungs_total} rungs scanned${scan.rungs_not_scanned ? `; ${scan.rungs_not_scanned} not scanned` : ''}${!available ? ' · not available' : scan.complete !== true ? ' · source omissions' : ' · complete'}`
        : 'Scan details unavailable', 'muted'));
      referenceScan.replaceChildren(heading);
      if (!available) referenceScan.append(el('p', 'Reference scan unavailable. Addresses without reference evidence are shown as Not checked.', 'field-signals-usage-gap'));
      else if (scan.complete !== true) referenceScan.append(el('p', 'Some source is outside this reference scan. Found references remain valid.', 'field-signals-usage-gap'));
      referenceScan.append(el('p', 'No references found applies to the scanned source. Read/write roles and physical channel types are separate findings.', 'muted'));
      function explanations(reasons, heading) {
        if (!Array.isArray(reasons) || !reasons.length) return;
        const list = el('ul');
        [...new Set(reasons)].slice(0, 16).forEach(reason => list.append(el('li', USAGE_GAPS[reason] || 'Additional source evidence could not be interpreted')));
        referenceScan.append(el('strong', heading), list);
      }
      explanations(scan?.gap_reasons, 'Source outside the scan');
      explanations(scan?.role_gap_reasons, 'Instruction and name details');
    }
    function signalTable(rows, result, expected) {
      const table = el('table', undefined, 'field-signals-table'), head = el('thead'), header = el('tr');
      ['Field type / channel', 'Source alias / address', 'Source description', 'Logic usage', 'DeltaV name', 'Package status', 'Info'].forEach(label => header.append(el('th', label)));
      head.append(header); const body = el('tbody');
      rows.forEach(row => {
        const tr = el('tr'); if (row.id === selectedId) tr.className = 'is-current';
        const mapped = row.mapping_status === 'documented_member_layout';
        const typeLabel = mapped ? TYPES[row.field_type] || TYPES.unknown
          : row.direction === 'input' ? 'Input' : row.direction === 'output' ? 'Output' : TYPES.unknown;
        const candidates = (row.candidate_field_types || []).map(value => TYPES[value]).filter(Boolean).join(' / ');
        const numeric = row.suggested_type_basis === 'qualified_floating_channel_and_direction' || row.mapping_reason === 'qualified_floating_channel_requires_review';
        const detailLabel = mapped ? 'Source-mapped' : numeric ? 'Numeric ' + (row.direction === 'output' ? 'output' : row.direction === 'input' ? 'input' : 'signal') + ' type candidate'
          : candidates ? candidates + ' type candidate' : 'Channel type not classified';
        const category = el('td'); category.append(el('strong', typeLabel), el('small', detailLabel, 'muted'));
        const source = el('td'); source.append(button(labelOf(row), async () => { if (requireCurrent(expected)) { await openRow(row); revealEditor(); } }, 'field-signals-open'));
        if (labelOf(row) !== row.address) source.append(el('code', row.address));
        if (row.aliases_total > 1) source.append(el('small', row.aliases_total + ' captured aliases', 'muted'));
        const description = el('td', undefined, 'field-signals-source-description'), wording = el('div', undefined, 'field-signals-wording-preview');
        const context = row.description_origin?.specific !== true && row.use_context?.description ? row.use_context : null;
        if (context) {
          prose(wording, context.description, context.wording?.description || context.wording, result.presentation_mode);
          description.append(wording, sourceLink('From result ' + (context.result_name || 'tag'), context.result_id, 'objects', expected));
        } else {
          prose(wording, textOf(row), wordingOf(row), result.presentation_mode); description.append(wording);
          if (row.description_origin?.specific === false && row.description_origin.kind !== 'missing')
            description.append(el('small', row.description_origin.label, 'field-signals-description-origin muted'));
        }
        if (descriptionNotice(row)) description.append(el('small', descriptionNotice(row), 'field-signals-description-conflict'));
        const use = usageOf(row), usageCell = el('td', undefined, 'field-signals-usage-cell');
        const usageButton = button(USAGE[use.status], async () => {
          if (requireCurrent(expected)) { await openRow(row); revealEditor(); }
        }, 'field-signals-usage-open usage-' + use.status);
        usageButton.setAttribute('aria-label', USAGE[use.status] + ' for ' + labelOf(row) + '. Open source references.');
        usageCell.append(usageButton);
        if (use.status === 'possible_indirect') {
          const explanation = el('small', indirectDetail(use), 'field-signals-usage-detail');
          explanation.title = indirectDetail(use); usageCell.append(explanation);
        }
        usageCell.append(el('small', usageCount(use), 'muted'));
        const saved = row.saved_signal, names = el('td', undefined, 'field-signals-name');
        names.append(el('span', (saved ? saved.target_name : proposedName(row)) || 'Not assigned'));
        if (!saved && proposedName(row)) names.append(el('small', 'Proposed · unreviewed', 'muted'));
        const packageIds = row.packages || (saved ? (state().groups || []).filter(group => group.signal_ids?.includes(saved.id)) : []);
        const statusLabel = !saved ? 'Not saved' : saved.needs_revalidation ? 'Needs review' : packageIds.length ? `${packageIds.length} package${packageIds.length === 1 ? '' : 's'}` : 'Saved · no package';
        const info = el('td'); info.append(hardwareButton(row));
        tr.append(category, source, description, usageCell, names, el('td', statusLabel), info); body.append(tr);
      });
      table.append(head, body); return table;
    }
    function setControllers(expanded) {
      closeHardware(); controllersExpanded = expanded;
      controllerStates.forEach((_, id) => controllerStates.set(id, expanded));
      controllerPanels.forEach(({panel, id}) => { panel.open = expanded; controllerStates.set(id, expanded); });
    }
    controllerTools.append(button('Expand all', () => setControllers(true)), button('Collapse all', () => setControllers(false)),
      el('span', 'Controllers on this page · search, type and usage filters apply to every page', 'muted'));
    function paintList(result) {
      closeHardware(); paintReferenceScan(result); tableWrap.replaceChildren(); controllerPanels = [];
      controllerTools.hidden = result.available === false;
      footer.hidden = result.available === false;
      const filtering = result.filtering;
      filterSummary.textContent = filtering?.hide_empty ? `${count(filtering.hidden_empty_count)} empty unreferenced rows hidden`
        + (count(filtering.preserved_empty_count) ? `; ${count(filtering.preserved_empty_count)} saved row${count(filtering.preserved_empty_count) === 1 ? '' : 's'} retained` : '') : '';
      filterSummary.hidden = !filterSummary.textContent;
      if (result.available === false) {
        pager.replaceChildren();
        tableWrap.append(el('p', 'The field signal list could not be loaded. This does not mean the analysis has no I/O. Your saved names and packages are retained; rungs and the full source report remain available.', 'warning-panel'));
        return;
      }
      const expected = key, groups = new Map();
      result.signals.items.forEach(row => {
        const controller = controllerOf(row);
        if (!groups.has(controller.id)) groups.set(controller.id, {...controller, rows: []});
        groups.get(controller.id).rows.push(row);
      });
      groups.forEach(group => {
        const panel = el('details', undefined, 'field-signals-controller'), heading = el('summary');
        const total = (result.controller_counts || []).find(item => (item.controller_id || item.id) === group.id)?.total;
        const count = Number.isInteger(total) ? `${group.rows.length} shown · ${total} matching signals` : `${group.rows.length} signals on this page`;
        heading.append(el('strong', group.name), el('span', count, 'muted'));
        panel.open = controllerStates.get(group.id) ?? controllersExpanded;
        panel.addEventListener('toggle', () => { controllerStates.set(group.id, panel.open); if (!panel.open) closeHardware(); });
        const wrap = el('div', undefined, 'field-signals-table-wrap'); wrap.append(signalTable(group.rows, result, expected));
        panel.append(heading, wrap); tableWrap.append(panel); controllerPanels.push({panel, id: group.id});
      });
      if (!result.signals.items.length) tableWrap.append(el('p', 'No individual signals match these filters. Try a different type, evidence or usage filter.'));
      pageControls(pager, result.signals, 'signals', next => { if (!requireCurrent(expected)) return; page = next; return loadList(); });
    }
    async function loadList() {
      const expected = key, expectedRun = runId, expectedPageSize = Number(applied.page_size), serial = ++listSerial;
      message('Loading individual field signals…'); directory.setAttribute('aria-busy', 'true');
      try {
        const result = await options.api(url());
        if (!current(expected) || serial !== listSerial) return;
        checkResult(result, expectedRun, expectedPageSize); page = result.signals.page; paintList(result);
        message(result.available === false ? result.notice || 'Signal evidence is unavailable.'
          : `${result.signals.total} matching field signals`, result.available === false);
      } catch (error) {
        if (!current(expected) || serial !== listSerial) return;
        message(error.message || 'The signal list could not be loaded.', true);
        tableWrap.replaceChildren(button('Retry signals', loadList));
      } finally { if (current(expected) && serial === listSerial) directory.removeAttribute('aria-busy'); }
    }
    function newDraft(row, payload) {
      const saved = row.saved_signal;
      const original = {target_name: saved ? saved.target_name : proposedName(row), description: saved?.description || '', field_type: saved?.field_type || row.suggested_field_type || row.field_type || 'unknown'};
      return {context: key, row: {...row}, payload, revision: payload.revision, id: saved?.id || '', original,
        target_name: original.target_name, description: original.description, field_type: original.field_type,
        signalDirty: false, packages: new Map(), packageId: '', message: '', sourceLabels: new Map()};
    }
    async function openRow(row, coordinates = {}) {
      const expected = key, expectedRun = runId, expectedPageSize = Number(applied.page_size), serial = ++detailSerial;
      selectedId = row.id; closeHardware();
      const retained = drafts.get(draftKey(row.id));
      if (retained && !Object.keys(coordinates).length) { selectedDraft = retained; paintEditor(retained); return; }
      detail.setAttribute('aria-busy', 'true');
      if (!retained) detail.replaceChildren(el('p', 'Loading source uses and related rung candidates…'));
      try {
        const priorPages = retained ? {rung_page: String(retained.row.direct_rungs?.page || 1), related_page: String(retained.row.related_rungs?.page || 1),
          use_page: String(retained.row.direct_uses?.page || 1)} : {};
        const expectedDetailSize = Number(coordinates.detail_page_size || retained?.detailPageSize || detailPageSize);
        const payload = await options.api(url({signal_id: row.id, ...priorPages, detail_page_size: String(expectedDetailSize), ...coordinates}));
        if (!current(expected) || serial !== detailSerial || selectedId !== row.id) return;
        checkResult(payload, expectedRun, expectedPageSize);
        if (payload.selected_signal?.id !== row.id) throw new Error('The selected signal did not match this source address.');
        const found = payload.selected_signal;
        for (const name of ['direct_uses', 'direct_rungs', 'related_rungs']) if (found[name] && !pageValid(found[name], expectedDetailSize))
          throw new Error('The related rung page exceeded its source bounds.');
        const draft = retained || newDraft(found, payload);
        draft.detailPageSize = expectedDetailSize; detailPageSize = expectedDetailSize;
        if (retained) { draft.row = {...found, saved_signal: retained.row.saved_signal}; draft.payload = payload; }
        for (const name of ['direct_rungs', 'related_rungs']) for (const rung of found[name]?.items || [])
          draft.sourceLabels.set(rung.rung_id || rung.id, {label: rung.path || `Rung ${rung.number ?? '?'}`, kind: 'rung'});
        drafts.set(draftKey(row.id), draft); selectedDraft = draft; paintEditor(draft);
      } catch (error) {
        if (!current(expected) || serial !== detailSerial) return;
        message(error.message || 'Signal details could not be loaded.', true);
        if (!retained) detail.replaceChildren(el('p', error.message), button('Retry signal details', () => openRow(row, coordinates)));
      } finally { if (current(expected) && serial === detailSerial) detail.removeAttribute('aria-busy'); }
    }
    function saveError(draft, error) {
      if (error.status === 409) draft.conflict = true;
      draft.message = (error.status === 409 ? 'The project changed. Your edits are retained; review the current project before retrying. ' : '')
        + (error.message || 'The change could not be saved.');
      if (selectedDraft === draft) paintEditor(draft); changed();
    }
    function advanceRevision(draft, from, to) {
      if (draft.revision === from) draft.revision = to;
      draft.packages.forEach(item => { if (item.revision === from) item.revision = to; });
    }
    async function reviewLatest(draft) {
      if (!requireCurrent(draft.context)) return;
      const serial = (draft.latestSerial || 0) + 1; draft.latestSerial = serial;
      try {
        const latest = await options.api('/api/state');
        if (!current(draft.context) || draft.latestSerial !== serial) return;
        if (JSON.stringify([latest.project_path || '', latest.active_run || '']) !== draft.context)
          throw new Error('The server project or analysis changed. These edits cannot be rebased onto that source.');
        if (!Number.isInteger(latest.revision)) throw new Error('The current project revision could not be verified.');
        const saved = (latest.signals || []).find(signal => signal.id === draft.id);
        if (draft.id && !saved)
          throw new Error('This saved signal no longer exists. Your edits remain available for reference.');
        if (saved && !sameBinding(saved.binding, draft.row.saved_signal?.binding)) {
          draft.latestReview = null;
          throw new Error('This signal was reconnected to different source evidence. Your edits are retained; reopen its current source before changing the saved signal.');
        }
        const item = draft.packages.get(draft.packageId);
        if (item?.id && !(latest.groups || []).some(group => group.id === item.id))
          throw new Error('This package no longer exists. Choose another package before applying these selections.');
        draft.latestReview = latest; if (selectedDraft === draft) paintEditor(draft);
      } catch (error) { saveError(draft, error); }
    }
    function useLatest(draft) {
      const latest = draft.latestReview;
      if (!latest || !requireCurrent(draft.context)) return;
      const saved = (latest.signals || []).find(signal => signal.id === draft.id);
      if (saved) {
        for (const name of ['target_name', 'description', 'field_type']) {
          if (draft[name] === draft.original[name]) draft[name] = saved[name];
        }
        draft.original = {target_name: saved.target_name, description: saved.description, field_type: saved.field_type};
        draft.signalDirty = Object.keys(draft.original).some(name => draft[name] !== draft.original[name]);
        draft.row.saved_signal = saved;
      }
      const item = draft.packages.get(draft.packageId), group = (latest.groups || []).find(group => group.id === item?.id);
      if (item) {
        if (group) {
          const merge = (live, before, desired) => {
            const result = new Set(live);
            before.forEach(id => { if (!desired.has(id)) result.delete(id); });
            desired.forEach(id => { if (!before.includes(id)) result.add(id); });
            return result;
          };
          item.members = merge(group.member_ids || [], item.original.member_ids, item.members);
          item.signals = merge(group.signal_ids || [], item.original.signal_ids, item.signals);
          const roles = {...group.member_roles};
          new Set([...Object.keys(item.original.member_roles), ...Object.keys(item.roles)]).forEach(id => {
            if (item.roles[id] !== item.original.member_roles[id]) { if (item.roles[id]) roles[id] = item.roles[id]; else delete roles[id]; }
          });
          Object.keys(roles).forEach(id => { if (!item.members.has(id)) delete roles[id]; }); item.roles = roles;
          if (item.name === item.original.name) item.name = group.name;
          item.original = {name: group.name, member_ids: [...group.member_ids || []], signal_ids: [...group.signal_ids || []], member_roles: {...group.member_roles}};
        }
        item.revision = latest.revision;
      }
      draft.revision = latest.revision; draft.conflict = false; draft.latestReview = null;
      draft.message = 'Latest saved version reviewed. Your explicit edits are retained; save when ready.';
      paintEditor(draft); changed();
    }
    function paintConflict(draft) {
      if (!draft.conflict) return;
      const section = el('section', undefined, 'warning-panel');
      section.append(el('strong', 'Review a newer saved version before retrying'),
        el('p', 'Your unsaved values and selections are retained. A newer revision is never accepted automatically.'),
        button('Review latest saved version', () => reviewLatest(draft)));
      if (draft.latestReview) {
        const saved = (draft.latestReview.signals || []).find(signal => signal.id === draft.id);
        const item = draft.packages.get(draft.packageId), group = (draft.latestReview.groups || []).find(group => group.id === item?.id);
        section.append(el('p', 'Latest saved project revision: ' + draft.latestReview.revision));
        if (saved) section.append(el('pre', JSON.stringify({target_name: saved.target_name, description: saved.description, field_type: saved.field_type}, null, 2)));
        if (group) section.append(el('p', `Package “${group.name}”: ${group.member_ids.length} source members, ${(group.signal_ids || []).length} signals.`));
        section.append(el('p', 'Using this revision preserves other saved memberships and applies only your additions, explicit removals and changed roles.'),
          button('Use latest revision for these edits', () => useLatest(draft)));
      }
      detail.append(section);
    }
    async function rebind(draft, id) {
      if (saving || !requireCurrent(draft.context) || !draft.row.binding) return;
      const expectedRevision = draft.revision; saving = true; paintEditor(draft);
      try {
        const result = await options.mutate({op: 'signal_rebind', id, binding: {...draft.row.binding}}, expectedRevision);
        const saved = (result?.signals || state().signals || []).find(signal => signal.id === id);
        if (!saved || !sameBinding(saved.binding, draft.row.binding)) throw new Error('The save response did not confirm this source correspondence.');
        draft.id = id; draft.row.saved_signal = saved;
        if (!draft.signalDirty) for (const field of ['target_name', 'description', 'field_type']) draft[field] = saved[field];
        draft.original = {target_name: saved.target_name, description: saved.description, field_type: saved.field_type};
        advanceRevision(draft, expectedRevision, result?.revision ?? state().revision);
        draft.message = 'Source correspondence saved. Review the selected source, then confirm its signal mapping.';
      } catch (error) { saveError(draft, error); }
      finally { saving = false; if (selectedDraft === draft) paintEditor(draft); changed(); }
    }
    function paintCorrespondence(draft) {
      const signals = new Map((state().signals || []).map(signal => [signal.id, signal]));
      if (draft.row.saved_signal) signals.set(draft.row.saved_signal.id, draft.row.saved_signal);
      const eligible = [...signals.values()].filter(signal => (!signal.active || signal.needs_revalidation || signal.id === draft.id)
        && (!draft.id || signal.id === draft.id) && !sameEvidence(signal.binding, draft.row.binding));
      if (!eligible.length) return;
      const section = el('details', undefined, 'field-signals-correspondence'); section.append(el('summary', 'Needs correspondence · retained signals'));
      section.append(el('p', 'Choose a saved signal only if this source replaces its previous address. Its identity, history and package memberships are retained. This is an explicit mapping change.'));
      const search = input('', 'field-signals-retained-search'), choices = select([['', 'Choose a retained signal…']], '', 'field-signals-retained-choice');
      const verified = el('input', undefined, 'field-signals-rebind-verified'); verified.type = 'checkbox';
      const apply = button('Reconnect retained signal to this source', () => { if (verified.checked && choices.value) return rebind(draft, choices.value); });
      apply.disabled = true;
      const paint = () => {
        const matching = eligible.filter(signal => [signal.target_name, signal.description, signal.binding.address_id].join(' ').toLocaleLowerCase().includes(search.value.toLocaleLowerCase()));
        choices.replaceChildren(); [['', 'Choose a retained signal…'], ...matching.slice(0, 50).map(signal => [signal.id, signal.target_name || signal.binding.address_id])]
          .forEach(([id, label]) => { const option = el('option', label); option.value = id; choices.append(option); });
        choices.value = ''; verified.checked = false; apply.disabled = true;
        count.textContent = `${Math.min(matching.length, 50)} of ${matching.length} matching retained signals. Search to narrow the list.`;
      };
      const count = el('p', undefined, 'muted');
      search.addEventListener('input', paint); choices.addEventListener('change', () => { verified.checked = false; apply.disabled = true; });
      verified.addEventListener('change', () => { apply.disabled = !verified.checked || !choices.value || saving || !current(draft.context); });
      section.append(field('Find a retained signal', search), count, field('Saved signal to reconnect', choices),
        field('I checked that this source replaces the selected signal’s previous binding', verified), apply);
      paint(); detail.append(section);
    }
    async function saveSignal(draft, confirm = false) {
      if (saving || !requireCurrent(draft.context)) return;
      if (!draft.id && !draft.row.binding) { saveError(draft, new Error('This source address has no verified binding.')); return; }
      const command = {op: 'signal', target_name: draft.target_name, description: draft.description, field_type: draft.field_type};
      if (draft.id) command.id = draft.id; else command.binding = {...draft.row.binding};
      if (confirm) command.confirm = true;
      const expectedRevision = draft.revision;
      saving = true; paintEditor(draft);
      try {
        const result = await options.mutate(command, expectedRevision);
        const saved = (result?.signals || state().signals || []).find(item => draft.id ? item.id === draft.id : sameBinding(item.binding, draft.row.binding));
        if (!saved) throw new Error('The save response did not identify this signal. Your edits remain available.');
        draft.id = saved.id; draft.row.saved_signal = saved; draft.signalDirty = false;
        for (const field of ['target_name', 'description', 'field_type']) draft[field] = saved[field];
        advanceRevision(draft, expectedRevision, result?.revision ?? state().revision);
        draft.original = {target_name: saved.target_name, description: saved.description, field_type: saved.field_type};
        draft.conflict = false; draft.latestReview = null;
        draft.message = confirm ? 'Signal mapping confirmed.' : 'Signal saved. Original source wording and addresses are unchanged.';
      } catch (error) { saveError(draft, error); }
      finally { saving = false; if (selectedDraft === draft) paintEditor(draft); changed(); }
    }
    function getPackage(draft, id) {
      if (draft.packages.has(id)) return draft.packages.get(id);
      const original = id === '__new' ? {} : (state().groups || []).find(group => group.id === id);
      if (!original) return null;
      const item = {id: original.id || '', name: original.name || '', members: new Set(original.member_ids || []),
        signals: new Set(original.signal_ids || []), roles: {...original.member_roles}, revision: state().revision, dirty: false, page: 1,
        original: {name: original.name || '', member_ids: [...original.member_ids || []], signal_ids: [...original.signal_ids || []], member_roles: {...original.member_roles}}};
      draft.packages.set(id, item); return item;
    }
    async function savePackage(draft, item) {
      if (saving || !requireCurrent(draft.context)) return;
      if (!item.name.trim()) { draft.message = 'Enter a package name.'; paintEditor(draft); return; }
      const command = {op: 'group', name: item.name.trim(), member_ids: [...item.members], signal_ids: [...item.signals], member_roles: {...item.roles}};
      if (item.id) command.id = item.id;
      const beforeIds = new Set((state().groups || []).map(group => group.id)), expectedRevision = item.revision;
      saving = true; paintEditor(draft);
      try {
        const result = await options.mutate(command, expectedRevision);
        const saved = (result?.groups || state().groups || []).find(group => item.id ? group.id === item.id
          : !beforeIds.has(group.id) && group.name === command.name && group.signal_ids?.length === command.signal_ids.length
            && command.signal_ids.every(id => group.signal_ids.includes(id)) && group.member_ids?.length === command.member_ids.length
            && command.member_ids.every(id => group.member_ids.includes(id)));
        if (!saved) throw new Error('The save response did not identify this package. Your selections remain available.');
        item.id = saved.id; item.dirty = false;
        advanceRevision(draft, expectedRevision, result?.revision ?? state().revision);
        item.original = {name: item.name, member_ids: [...item.members], signal_ids: [...item.signals], member_roles: {...item.roles}};
        draft.packages.delete(draft.packageId); draft.packageId = saved.id; draft.packages.set(saved.id, item);
        draft.conflict = false; draft.latestReview = null;
        draft.message = 'Package saved. Only the memberships you chose were changed.';
      } catch (error) { saveError(draft, error); }
      finally { saving = false; if (selectedDraft === draft) paintEditor(draft); changed(); }
    }
    function paintMembers(target, draft, item) {
      const records = [...item.members].map(id => ({id, kind: 'source'})).concat([...item.signals].map(id => ({id, kind: 'signal'})));
      const size = item.pageSize || 10, pages = Math.max(1, Math.ceil(records.length / size)); item.page = Math.min(item.page, pages);
      const selector = select(PAGE_SIZES.map(size => [String(size), String(size)]), String(size), 'field-signals-members-page-size');
      selector.disabled = saving || !current(draft.context);
      selector.addEventListener('change', () => {
        if (!PAGE_SIZES.includes(Number(selector.value)) || !requireCurrent(draft.context)) return;
        item.pageSize = Number(selector.value); item.page = 1; paintEditor(draft);
      });
      const list = el('div', undefined, 'field-signals-members');
      records.slice((item.page - 1) * size, item.page * size).forEach(record => {
        const row = el('div', undefined, 'field-signals-member'), checkbox = el('input'); checkbox.type = 'checkbox'; checkbox.checked = true;
        checkbox.disabled = saving || !current(draft.context);
        const saved = record.kind === 'signal' ? (state().signals || []).find(signal => signal.id === record.id) : null;
        const member = (state().groups || []).find(group => group.id === item.id)?.members?.find(member => member.id === record.id);
        const source = draft.sourceLabels.get(record.id) || {label: member?.path || member?.label || 'Retained source record', kind: member?.kind};
        row.append(field(record.kind === 'signal' ? 'Signal: ' + (saved?.target_name || saved?.description || 'Unnamed saved signal') : 'Source member: ' + source.label, checkbox));
        if (record.kind === 'source') row.append(sourceLink(source.kind === 'rung' ? 'Open rung source' : 'Open source record', record.id, source.kind === 'rung' ? 'ladder' : 'objects', draft.context));
        checkbox.addEventListener('change', () => {
          if (!requireCurrent(draft.context)) return;
          if (!checkbox.checked) { (record.kind === 'signal' ? item.signals : item.members).delete(record.id); delete item.roles[record.id]; item.dirty = true; changed(); paintEditor(draft); }
        });
        if (record.kind === 'source') {
          const role = select([['', 'No assigned role'], ...Object.entries(ROLES)], item.roles[record.id] || ''); role.disabled = saving || !current(draft.context);
          role.addEventListener('change', () => { if (role.value) item.roles[record.id] = role.value; else delete item.roles[record.id]; item.dirty = true; changed(); paintEditor(draft); });
          row.append(field('Package role', role));
        }
        list.append(row);
      });
      const pagesElement = el('div', undefined, 'pagination');
      pageControls(pagesElement, {page: item.page, pages, total: records.length}, 'package members', next => { item.page = next; paintEditor(draft); });
      target.append(el('p', 'Existing source members and signals stay in this package. Uncheck a member only when you intend to remove it.', 'muted'), field('Package members per page', selector), list, pagesElement);
    }
    function paintCandidates(target, draft, item, name, heading, parameter) {
      const page = draft.row[name]; if (!page) return;
      const section = el('section', undefined, 'field-signals-candidates'); section.append(el('h4', heading));
      if (page.available === false) section.append(el('p', 'Related-rung evidence is unavailable for this saved analysis.', 'warning-panel'));
      if (page.total_is_lower_bound || page.traversal?.truncated)
        section.append(el('p', 'This is a bounded, one-step search. Some source rungs or high-fan-out addresses were not expanded; the displayed total is a minimum.', 'warning-panel'));
      page.items.forEach(candidate => {
        const id = candidate.rung_id || candidate.id, row = el('article', undefined, 'field-signals-candidate');
        const checkbox = el('input', undefined, 'field-signals-candidate-check'); checkbox.type = 'checkbox'; checkbox.checked = Boolean(item?.members.has(id)); checkbox.disabled = !item || saving || !current(draft.context);
        const label = candidate.path || `Rung ${candidate.number ?? '?'}`;
        const reason = candidate.association_reason === 'shared_address_with_direct_use_rung' ? 'Shares an exact source address with a rung that uses this signal.'
          : candidate.association_reason === 'direct_exact_address_use' ? 'Direct use of this exact source address.'
          : 'Captured source association; review its role before including it.';
        row.append(field('Include ' + label, checkbox), el('p', reason, 'muted'));
        if (candidate.role_notice) row.append(el('small', candidate.role_notice, 'muted'));
        const role = select(Object.entries(ROLES), item?.roles[id] || (ROLES[candidate.candidate_role] ? candidate.candidate_role : 'logic'));
        role.disabled = !item || saving || !current(draft.context);
        checkbox.addEventListener('change', () => {
          if (!item || !requireCurrent(draft.context)) return;
          if (checkbox.checked) { item.members.add(id); item.roles[id] = role.value; } else { item.members.delete(id); delete item.roles[id]; }
          item.dirty = true; changed(); paintEditor(draft);
        });
        role.addEventListener('change', () => { if (item?.members.has(id)) { item.roles[id] = role.value; item.dirty = true; changed(); paintEditor(draft); } });
        row.append(field('Proposed package role', role), sourceLink('Open rung source', id, 'ladder', draft.context));
        (candidate.associations || []).slice(0, 4).forEach(association => row.append(el('code', 'Related through ' + association.address)));
        if (candidate.associations_truncated) row.append(el('small', 'Additional shared-address paths are outside this preview.', 'muted'));
        section.append(row);
      });
      if (!page.items.length) section.append(el('p', 'No captured candidates on this page.'));
      const controls = el('div', undefined, 'pagination');
      pageControls(controls, page, 'rung candidates', next => {
        if (requireCurrent(draft.context)) return openRow(draft.row, {[parameter]: String(next)});
      });
      section.append(controls); target.append(section);
    }
    function paintUsage(draft) {
      const row = draft.row, usage = usageOf(row), section = el('section', undefined, 'field-signals-usage-summary');
      const indexSources = new Map(); let indexSourcesTruncated = false;
      section.append(el('h4', 'Logic usage'), el('strong', USAGE[usage.status], 'usage-' + usage.status),
        el('p', usageCount(usage), 'field-signals-usage-count'),
        el('p', usage.status === 'referenced' ? 'This source address is used by the references listed below.'
          : usage.status === 'possible_indirect' ? indirectDetail(usage)
          : usage.status === 'not_found' ? 'No references to this address were found in the scanned source.'
          : 'The reference scan could not determine usage for this address.'));
      const roles = Object.entries(USAGE_ROLES).filter(([key]) => count(usage.roles?.[key]) > 0);
      if (roles.length) section.append(el('p', roles.map(([key, label]) => `${label}: ${count(usage.roles[key])}`).join(' · '), 'field-signals-usage-roles'));
      section.append(button('View reference scan scope', () => {
        if (!requireCurrent(draft.context)) return;
        referenceScan.open = true; referenceScan.scrollIntoView?.({block: 'start', behavior: 'smooth'}); referenceScan.focus({preventScroll: true});
      }, 'text-link'));
      function references(title, rows, kind = 'exact') {
        const list = el('details', undefined, 'field-signals-usage-references'); list.open = true;
        list.append(el('summary', title));
        rows.forEach(use => {
          const entry = el('article', undefined, 'field-signals-usage-reference');
          entry.append(el('strong', [use.opcode || 'Instruction', USAGE_ROLES[use.role] || 'Role unknown'].join(' · ')));
          if (use.variable) entry.append(el('code', use.variable));
          if (use.path) entry.append(el('small', use.path, 'muted'));
          const explanation = wording(use.explanation) || REFERENCE_REASONS[use.reason];
          if (explanation || kind !== 'exact') entry.append(el('p', explanation
            || (kind === 'resolved' ? 'This source reference statically includes the address.'
              : 'Target-resolution details were not saved for this reference.'), 'field-signals-reference-explanation muted'));
          if (use.instruction_id) entry.append(sourceLink('Open instruction source', use.instruction_id, 'ladder', draft.context));
          if (use.rung_id) entry.append(sourceLink('Open rung source', use.rung_id, 'ladder', draft.context));
          const indices = Array.isArray(use.index_sources) ? use.index_sources : [];
          indexSourcesTruncated ||= Boolean(use.index_sources_truncated) || indices.length > 12;
          indices.slice(0, 12).forEach(source => {
            if (!source || typeof source !== 'object' || (!wording(source.instruction_id) && !wording(source.rung_id))) return;
            indexSources.set(JSON.stringify([source.variable, source.instruction_id, source.rung_id, source.role]), source);
          });
          list.append(entry);
        });
        section.append(list);
      }
      const exact = row.direct_uses;
      if (exact?.items?.length) references('Exact source references', exact.items);
      if (exact?.pages > 1) {
        const controls = el('div', undefined, 'pagination');
        pageControls(controls, exact, 'exact references', next => {
          if (requireCurrent(draft.context)) return openRow(row, {use_page: String(next)});
        }); section.append(controls);
      }
      const resolved = Array.isArray(usage.resolved_uses) ? usage.resolved_uses.slice(0, 12) : [];
      if (resolved.length) references('Resolved source references', resolved, 'resolved');
      if (usage.resolved_uses_truncated || count(usage.resolved_count) > resolved.length)
        section.append(el('small', `Showing ${resolved.length} of ${count(usage.resolved_count)} resolved references; the preview is bounded.`, 'muted'));
      const possible = Array.isArray(usage.possible_uses) ? usage.possible_uses.slice(0, 12) : [];
      if (possible.length) references('References needing target resolution', possible, 'indirect');
      if (usage.possible_uses_truncated || count(usage.possible_count) > possible.length)
        section.append(el('small', `Showing ${possible.length} of ${count(usage.possible_count)} indirect references; the preview is bounded.`, 'muted'));
      if (indexSources.size) {
        const sources = el('div', undefined, 'field-signals-index-sources'); sources.append(el('strong', 'Array index sources'));
        [...indexSources.values()].slice(0, 3).forEach(source => {
          const action = ['write', 'read_write'].includes(source.role) ? 'written' : 'accessed';
          const label = `Index ${wording(source.variable) || 'value'} ${action} by ${wording(source.opcode) || 'instruction'}`
            + (wording(source.path) ? ' · ' + source.path : '');
          sources.append(sourceLink(label, wording(source.instruction_id) || source.rung_id, 'ladder', draft.context));
        });
        if (indexSources.size > 3 || indexSourcesTruncated)
          sources.append(el('small', `Showing ${Math.min(3, indexSources.size)} of ${indexSources.size} index source reference${indexSources.size === 1 ? '' : 's'} in these previews.`
            + (indexSourcesTruncated ? ' Additional index sources are outside this preview.' : ''), 'muted'));
        section.append(sources);
      } else if (indexSourcesTruncated) section.append(el('small', 'Index source references are outside the retained preview.', 'muted'));
      detail.append(section);
    }
    function paintEditor(draft) {
      const row = draft.row, controlsDisabled = saving || !current(draft.context);
      detail.replaceChildren(el('h3', labelOf(row)), el('code', row.address));
      if (draft.message) detail.append(el('p', draft.message, 'field-signals-editor-status'));
      if (!current(draft.context)) detail.append(el('p', 'These edits belong to a different project or analysis. They remain available for reference, but cannot be saved into the current source.', 'warning-panel'));
      paintUsage(draft);
      const source = el('details', undefined, 'field-signals-source'); source.append(el('summary', 'Original source wording and evidence'));
      if (row.rack_mapping?.logical_address) {
        source.append(el('p', 'Source address ' + row.rack_mapping.logical_address
          + ' → backing address ' + row.address, 'field-signals-rack-mapping'));
      }
      if (row.description_origin?.label) source.append(el('p', row.description_origin.label, 'field-signals-description-origin muted'));
      const metadata = row.source_metadata || {}, facts = el('dl', undefined, 'field-signals-source-facts');
      [['Tag type', metadata.tag_type], ['Alias for', metadata.alias_for], ['Base name', metadata.base_name],
        ['Data type', metadata.data_type], ['Radix', metadata.radix], ['External access', metadata.external_access]].forEach(([label, value]) => {
        if (value !== undefined && value !== null && value !== '') facts.append(el('dt', label), el('dd', value));
      });
      if (facts.children.length) source.append(facts);
      if (row.description_selection) {
        const selection = row.description_selection, preferred = el('article'), wording = el('div');
        preferred.append(el('strong', 'Preferred source wording')); prose(wording, textOf(row), wordingOf(row), draft.payload.presentation_mode);
        preferred.append(wording, el('small', 'Selection: ' + (selection.basis || 'Not captured').replaceAll('_', ' ') + ' · ' + (selection.status || 'unknown').replaceAll('_', ' '), 'muted'));
        if (descriptionNotice(row)) preferred.append(el('p', descriptionNotice(row) + '. Source alternatives remain unchanged.', 'field-signals-description-conflict'));
        source.append(preferred);
        const choices = selection.candidates || [];
        if (choices.length) {
          const alternatives = el('details'); alternatives.append(el('summary', 'Description selection evidence'));
          choices.forEach(candidate => {
            const entry = el('p', [candidate.kind, candidate.basis, candidate.owner_name].filter(Boolean).map(value => String(value).replaceAll('_', ' ')).join(' · ') || 'Source wording candidate');
            if (candidate.owner_id) entry.append(sourceLink('Open candidate source', candidate.owner_id, 'objects', draft.context)); alternatives.append(entry);
          });
          if (selection.candidates_truncated || selection.candidate_count > choices.length) alternatives.append(el('small', `Showing ${choices.length} of ${selection.candidate_count} description candidates.`, 'muted'));
          source.append(alternatives);
        }
      }
      const notes = row.source_annotations || [];
      if (notes.length) notes.slice(0, 8).forEach(note => {
        const entry = el('article'), text = el('div');
        entry.append(el('strong', (note.kind === 'member_comment' ? 'Member comment' : 'Source description') + (note.via === 'alias' ? ' · alias ' + (note.owner_name || '') : '')));
        prose(text, note.text, note.wording, draft.payload.presentation_mode); entry.append(text);
        if (note.owner_id) entry.append(sourceLink('Open complete source wording', note.owner_id, 'objects', draft.context)); source.append(entry);
      });
      else { const text = el('p'); prose(text, row.description, row.wording?.description, draft.payload.presentation_mode); source.append(text); }
      if (row.source_annotations_truncated) source.append(sourceLink('Browse all source comments', '', 'annotations', draft.context));
      if (row.aliases?.length) {
        const aliases = el('div', undefined, 'field-signals-aliases'); aliases.append(el('strong', 'Captured member aliases'));
        row.aliases.slice(0, 8).forEach(alias => {
          const entry = el('div'); entry.append(sourceLink(alias.name || 'Unnamed alias', alias.id, 'objects', draft.context)); aliases.append(entry);
        });
        if (row.aliases_truncated) aliases.append(el('small', `Showing ${Math.min(row.aliases.length, 8)} of ${row.aliases_total} captured aliases.`, 'muted'));
        source.append(aliases);
      }
      source.append(el('p', MAPPING[row.mapping_reason] || (row.mapping_status === 'documented_member_layout' ? 'Documented source member layout.' : 'Field mapping requires review.')));
      detail.append(source);
      if (row.use_context?.description) {
        const context = row.use_context, panel = el('section', undefined, 'field-signals-use-context'), description = el('p');
        panel.append(sourceLink('From result ' + (context.result_name || 'tag'), context.result_id, 'objects', draft.context));
        prose(description, context.description, context.wording?.description || context.wording, draft.payload.presentation_mode); panel.append(description);
        if (context.rung_id) panel.append(sourceLink('Open result rung', context.rung_id, 'ladder', draft.context));
        detail.append(panel);
      }
      const signalForm = el('div', undefined, 'field-signals-edit-form');
      const name = input(draft.target_name, 'field-signals-target-name'), description = input(draft.description, 'field-signals-description', true);
      name.maxLength = 160; description.maxLength = 4000;
      const type = select(Object.entries(TYPES), draft.field_type, 'field-signals-reviewed-type');
      [[name, 'target_name'], [description, 'description'], [type, 'field_type']].forEach(([control, property]) => {
        control.disabled = controlsDisabled;
        control.addEventListener(property === 'field_type' ? 'change' : 'input', () => { draft[property] = control.value; draft.signalDirty = true; changed(); });
      });
      const save = button('Save signal', () => saveSignal(draft)); save.disabled = controlsDisabled;
      signalForm.append(field('DeltaV name', name), field('Engineering description', description), field('Reviewed field type', type), save);
      if (draft.id && row.saved_signal?.needs_revalidation) {
        const bindingChanged = !sameEvidence(row.saved_signal.binding, row.binding);
        const confirm = button('Confirm signal mapping', () => saveSignal(draft, true)); confirm.disabled = controlsDisabled || bindingChanged;
        signalForm.append(el('p', bindingChanged ? 'The saved binding differs from this source evidence. Reconnect the retained signal below before confirming its mapping.'
          : 'The saved source mapping needs review. Confirm only after checking this source and any changed evidence.', 'warning-panel'), confirm);
      }
      detail.append(signalForm);
      paintConflict(draft); paintCorrespondence(draft);
      const packageSection = el('section', undefined, 'field-signals-package'); packageSection.append(el('h3', 'Engineering package'));
      const chooser = select([['', 'Choose a package…'], ['__new', 'Create a new package'], ...(state().groups || []).map(group => [group.id, group.name])], draft.packageId, 'field-signals-package-choice');
      chooser.disabled = controlsDisabled || !draft.id;
      chooser.addEventListener('change', () => { draft.packageId = chooser.value; if (draft.packageId) getPackage(draft, draft.packageId); paintEditor(draft); });
      packageSection.append(field('Package', chooser));
      if (!draft.id) packageSection.append(el('p', 'Save this signal first, then choose the package and logic it belongs to.', 'muted'));
      const item = draft.packageId ? getPackage(draft, draft.packageId) : null;
      if (item) {
        const packageName = input(item.name, 'field-signals-package-name'); packageName.maxLength = 160; packageName.disabled = controlsDisabled;
        packageName.addEventListener('input', () => { item.name = packageName.value; item.dirty = true; changed(); });
        const include = el('input', undefined, 'field-signals-include-signal'); include.type = 'checkbox'; include.checked = item.signals.has(draft.id); include.disabled = controlsDisabled;
        include.addEventListener('change', () => { if (include.checked) item.signals.add(draft.id); else item.signals.delete(draft.id); item.dirty = true; changed(); paintEditor(draft); });
        packageSection.append(field('Package name', packageName), field('Include this signal in the package', include));
        paintMembers(packageSection, draft, item);
        const save = button('Save package', () => savePackage(draft, item)); save.disabled = controlsDisabled;
        packageSection.append(save);
      }
      const candidateSize = select(PAGE_SIZES.map(size => [String(size), String(size)]), String(draft.detailPageSize || detailPageSize), 'field-signals-detail-page-size');
      candidateSize.disabled = controlsDisabled;
      candidateSize.addEventListener('change', () => {
        if (!PAGE_SIZES.includes(Number(candidateSize.value)) || !requireCurrent(draft.context)) return;
        return openRow(draft.row, {detail_page_size: candidateSize.value, rung_page: '1', related_page: '1', use_page: '1'});
      });
      packageSection.append(field('Rungs per candidate section', candidateSize));
      paintCandidates(packageSection, draft, item, 'direct_rungs', 'Rungs using this signal', 'rung_page');
      paintCandidates(packageSection, draft, item, 'related_rungs', 'Related logic candidates', 'related_page');
      detail.append(packageSection);
      const limits = draft.row.limitations || draft.payload.limitations;
      if (Array.isArray(limits) && limits.length) { const notes = el('details'); notes.append(el('summary', 'Evidence limits')); limits.forEach(text => notes.append(el('p', text))); detail.append(notes); }
    }
    function revealEditor() {
      if (window.innerWidth <= 1500) detail.scrollIntoView?.({block: 'start', behavior: 'smooth'});
    }
    async function refresh() {
      active = true;
      const next = identity(), changedContext = next !== key;
      if (changedContext) {
        ++listSerial; ++detailSerial; closeHardware(); key = next; runId = state().active_run || ''; page = 1; selectedId = '';
        tableWrap.replaceChildren(); pager.replaceChildren(); referenceScan.replaceChildren(); referenceScan.open = false; referenceScan.hidden = true;
        controllerStates.clear(); controllerPanels = [];
        if (selectedDraft && dirty(selectedDraft)) paintEditor(selectedDraft);
        else { selectedDraft = null; detail.replaceChildren(el('p', 'Choose an individual signal to edit its DeltaV name, description and package.')); }
      }
      paintDrafts();
      audit.disabled = auditing || !runId;
      if (!runId) { message('Choose an analysis under Project tools to browse individual field signals.'); return; }
      const tasks = [loadList()];
      if (!saving && selectedDraft && current(selectedDraft.context) && !dirty(selectedDraft)) {
        const row = selectedDraft.row; drafts.delete(draftKey(row.id)); tasks.push(openRow(row));
      }
      await Promise.all(tasks);
    }
    function deactivate() { active = false; ++listSerial; ++detailSerial; closeHardware(); }
    function discardDrafts() {
      if (saving) return;
      drafts.clear(); selectedDraft = null; selectedId = ''; detail.replaceChildren(el('p', 'Choose an individual signal to edit.')); changed();
    }
    function changeFilters() {
      if (!requireCurrent(key)) return;
      applied = {query: query.value.trim().slice(0, 256), field_type: type.value, section: section.value,
        usage: usage.value, hide_empty: hideEmpty.checked ? '1' : '0', page_size: pageSize.value}; page = 1; return loadList();
    }
    filters.addEventListener('submit', event => { event.preventDefault(); return changeFilters(); });
    type.addEventListener('change', changeFilters); section.addEventListener('change', changeFilters); usage.addEventListener('change', changeFilters);
    hideEmpty.addEventListener('change', changeFilters);
    pageSize.addEventListener('change', () => {
      if (!PAGE_SIZES.includes(Number(pageSize.value)) || !requireCurrent(key)) return;
      applied = {...applied, page_size: pageSize.value}; page = 1; return loadList();
    });
    detail.append(el('p', 'Choose an individual signal to edit its DeltaV name, description and package.'));
    return {refresh, deactivate, setActive: value => value ? refresh() : deactivate(), hasUnsavedChanges, discardDrafts,
      openSignal: async id => { if (identity() !== key || !active) await refresh(); if (requireCurrent(key)) { await openRow({id}); revealEditor(); } }};
  }
  window.PLCFieldSignals = {mount};
})();
