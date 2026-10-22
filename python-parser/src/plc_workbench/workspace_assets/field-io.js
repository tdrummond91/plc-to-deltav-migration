/* Captured module inventory and source uses. Engineering groups stay explicit. */
(() => {
  'use strict';
  const PAGE_SIZE = 24, USE_SIZE = 12;
  const types = {di: 'DI · digital input', do: 'DO · digital output', ai: 'AI · analogue input', ao: 'AO · analogue output', unknown: 'Unresolved field type'};
  const moduleTypes = {di: types.di, do: types.do, ai: types.ai, ao: types.ao,
    mixed: 'Mixed field I/O', non_field: 'Controller / network', unknown: 'Unclassified'};
  const moduleRoles = {field_io: 'Field I/O', controller: 'Controller', communication: 'Communication / network', unknown: 'Unresolved module role'};
  const typeReasons = {
    exact_vendor_catalog: 'Exact vendor and catalog recognized',
    source_unqualified: 'Source declaration could not be verified',
    missing_catalog: 'Catalog number is missing',
    unsupported_vendor: 'Vendor is not supported by the catalog lookup',
    user_defined_catalog: 'User-defined catalog needs review',
    unsupported_catalog: 'Catalog is not yet in the supported lookup',
  };
  const human = value => String(value ?? '').replaceAll('_', ' ');
  const el = (tag, text, cls = '') => {
    const result = document.createElement(tag); result.className = cls;
    if (text !== undefined && text !== null) result.textContent = String(text);
    return result;
  };
  const button = (text, action, cls = '') => {
    const result = el('button', text, cls); result.type = 'button';
    result.addEventListener('click', action); return result;
  };
  const field = (label, control) => {
    control.setAttribute('aria-label', label);
    const result = el('label', label); result.append(control); return result;
  };
  function choices(entries, cls) {
    const result = el('select', undefined, cls);
    entries.forEach(([value, label]) => { const item = el('option', label); item.value = value; result.append(item); });
    return result;
  }
  function facts(entries) {
    const result = el('dl', undefined, 'field-io-facts');
    entries.forEach(([label, value]) => {
      result.append(el('dt', label), el('dd', value === null || value === undefined || value === '' ? 'Not captured' : value));
    });
    return result;
  }
  function upstreamLabel(value) {
    if (value === null || value === undefined || value === '') return 'Not captured';
    const text = String(value).trim().toLowerCase();
    if (text === 'true' || text === '1') return 'Yes';
    if (text === 'false' || text === '0') return 'No';
    return `Unresolved (${String(value)})`;
  }
  function validPage(value, limit) {
    return value && Array.isArray(value.items) && value.items.length <= limit
      && Number.isInteger(value.total) && value.total >= 0
      && Number.isInteger(value.page) && value.page >= 1
      && Number.isInteger(value.pages) && value.pages >= value.page
      && value.page_size === limit;
  }
  function mount(root, options) {
    const filters = el('form', undefined, 'filters field-io-filters');
    const search = el('input', undefined, 'field-io-search');
    search.type = 'search'; search.maxLength = 256; search.placeholder = 'Name, catalog, address, alias or original description…';
    const type = choices([['', 'All module types'], ...Object.entries(moduleTypes)], 'field-io-type');
    const direction = choices([['', 'All captured directions'], ['input', 'Input data'], ['output', 'Output data'], ['configuration', 'Configuration data']], 'field-io-direction');
    const find = el('button', 'Search'); find.type = 'submit';
    const reset = button('Clear filters', () => { search.value = ''; type.value = ''; direction.value = ''; return changeFilters(); });
    filters.append(field('Find field I/O', search), field('Module field type', type), field('Captured data direction', direction), find, reset);
    const status = el('p', undefined, 'field-io-status'); status.setAttribute('role', 'status');
    const totals = el('div', undefined, 'field-io-type-totals');
    totals.setAttribute('aria-label', 'Module types across the entire captured source');
    const selection = el('div', undefined, 'field-io-selection');
    const count = el('span');
    const group = button('Add whole modules to group', () => {
      if (!ensureCurrent() || !selected.size) return;
      return options.addToGroup([...selected.keys()]);
    });
    const clearSelection = button('Clear module selection', () => { selected.clear(); paintSelection(); paintCards(lastDirectory); });
    selection.append(count, group, clearSelection,
      el('small', 'Grouping adds complete module declarations. It does not save individual channel selections.', 'muted'));
    const layout = el('div', undefined, 'field-io-layout');
    const directory = el('section', undefined, 'field-io-directory');
    directory.setAttribute('aria-label', 'Captured module cards');
    const pager = el('div', undefined, 'pagination field-io-module-pages');
    const cards = el('div', undefined, 'field-io-cards'); directory.append(pager, cards);
    const detail = el('section', undefined, 'field-io-detail panel');
    detail.setAttribute('aria-label', 'Selected module and captured addresses');
    layout.append(directory, detail);
    const help = el('details', undefined, 'field-io-help');
    help.append(el('summary', 'What this page establishes'),
      el('p', 'Cards represent captured module declarations. DI, DO, AI and AO require a recognized catalog; an address receives a field type only when its documented member layout supports it. Other addresses remain unresolved. BOOL or REAL alone does not identify physical I/O.'),
      el('p', 'Input and output labels describe captured module data direction. Status, configuration and feedback members are not automatically field points. Linked rungs show recorded source uses, not physical wiring, live values or confirmed device connections.'),
      el('p', 'Search matches captured names, catalogs, addresses, aliases and original descriptions. English translations change the displayed wording; they do not replace the source search terms.'),
      el('p', 'Descriptions follow the header language setting and retain original wording when English is unavailable. Select whole module cards to add their declarations to an existing engineering group or create a new group. Use Classification & groups to edit the saved grouping.'));
    const glossary = el('details', undefined, 'field-io-glossary');
    glossary.append(el('summary', 'Field I/O glossary'), facts([
      ['DI', 'Digital input: an on/off field signal, such as a switch contact.'],
      ['DO', 'Digital output: an on/off command to field equipment.'],
      ['AI', 'Analogue input: a measured numeric signal, such as pressure or level.'],
      ['AO', 'Analogue output: a variable numeric command to field equipment.'],
      ['Mixed I/O card', 'One module supports more than one field type. It appears in each matching type filter.'],
      ['Controller / network', 'A recognized controller or communication module, separated from field I/O cards.'],
      ['Channel', 'An individual I/O path on a module. A source member index alone does not prove the wired terminal.'],
      ['Address', 'A captured tag or member reference. Several source records can describe the same physical signal.'],
      ['Alias', 'An exported name that refers to another source address.'],
      ['Catalog function', 'A description derived from manufacturer documentation for the recognized catalog.'],
      ['Source description', 'Wording captured in this L5X export, with cached English shown when selected.'],
    ]));
    help.append(glossary);
    root.append(filters, totals, status, selection, help, layout);
    let key = '', runId = '', active = false, directorySerial = 0, detailSerial = 0;
    let page = 1, signalPage = 1, moduleId = '', lastDirectory = null, directoryMode = 'original';
    let applied = {query: '', field_type: '', direction: ''};
    const selected = new Map();
    const projectKey = () => {
      const project = options.getState() || {};
      return JSON.stringify([project.project_path || '', project.active_run || '']);
    };
    const current = expected => active && key === expected && projectKey() === expected;
    function ensureCurrent() {
      if (!active) return false;
      if (projectKey() === key && runId) return true;
      refresh(); return false;
    }
    function request(extra = {}) {
      return '/api/field-io?' + new URLSearchParams({run_id: runId, ...applied, page: String(page), ...extra});
    }
    function checkResult(result, expectedRun, selectedId = '') {
      if (result?.run_id !== expectedRun || typeof result.available !== 'boolean'
          || !validPage(result.modules, PAGE_SIZE) || !validPage(result.addresses, PAGE_SIZE)
          || (selectedId && result.available && result.selected_module?.id !== selectedId))
        throw new Error('This field I/O response does not match the selected source. Use Refresh saved data in Project tools.');
      const module = result.selected_module;
      if (module && ['ports', 'roots', 'rack_aliases'].some(name => !Array.isArray(module[name]) || module[name].length > PAGE_SIZE))
        throw new Error('The module source preview exceeded its expected bounds.');
      if (result.addresses.items.some(row => !Array.isArray(row.aliases) || row.aliases.length > 8
          || !Array.isArray(row.uses) || row.uses.length > USE_SIZE
          || !Number.isInteger(row.uses_total) || row.uses_total < 0
          || !Number.isInteger(row.use_page) || row.use_page < 1
          || !Number.isInteger(row.use_pages) || row.use_pages < row.use_page))
        throw new Error('The address source-use preview exceeded its expected bounds.');
    }
    function paintSelection() {
      count.textContent = `${selected.size} whole module${selected.size === 1 ? '' : 's'} selected`;
      group.disabled = clearSelection.disabled = !selected.size;
    }
    function paintTotals(coverage) {
      totals.replaceChildren();
      if (coverage?.module_type_counts_scope !== 'all_captured_modules') return;
      const counts = coverage.modules_by_field_type, filterCounts = coverage.modules_by_filter;
      const validCounts = value => value && Object.keys(moduleTypes).every(name => Number.isInteger(value[name]) && value[name] >= 0);
      if (!validCounts(counts) || !validCounts(filterCounts)) return;
      const recognized = counts.di + counts.do + counts.ai + counts.ao + counts.mixed;
      const total = recognized + counts.non_field + counts.unknown;
      totals.append(el('p', `${total.toLocaleString()} captured module record${total === 1 ? '' : 's'} · ${recognized.toLocaleString()} recognized field I/O card${recognized === 1 ? '' : 's'} · ${counts.non_field.toLocaleString()} controller/network record${counts.non_field === 1 ? '' : 's'} · ${counts.unknown.toLocaleString()} unclassified module record${counts.unknown === 1 ? '' : 's'}.`, 'field-io-count-summary'));
      totals.append(el('p', 'Module catalog coverage across the complete source · counts describe module declarations, not field-point addresses or wired channels.', 'muted'));
      Object.entries(moduleTypes).forEach(([value, label]) => {
        const amount = filterCounts[value];
        const quantity = ['unknown', 'non_field'].includes(value) ? `module record${amount === 1 ? '' : 's'}` : amount === 1 ? 'card' : 'cards';
        const choose = button(`${label} · ${amount.toLocaleString()} ${quantity}`, () => { type.value = value; return changeFilters(); }, 'field-io-type-tile');
        choose.setAttribute('aria-pressed', String(type.value === value)); totals.append(choose);
      });
      if (counts.mixed) totals.append(el('p', 'Mixed cards appear in every matching DI, DO, AI or AO filter. These filter counts overlap; the module total above counts each record once.', 'muted'));
      const roles = coverage.modules_by_role;
      if (roles && ['controller', 'communication'].every(role => Number.isInteger(roles[role]) && roles[role] >= 0))
        totals.append(el('p', `Recognized infrastructure: ${roles.controller.toLocaleString()} controller record${roles.controller === 1 ? '' : 's'} · ${roles.communication.toLocaleString()} communication/network record${roles.communication === 1 ? '' : 's'}.`, 'muted'));
      if (Number.isInteger(coverage.point_mapped_addresses) && coverage.point_mapped_addresses >= 0)
        totals.append(el('p', `Separate address coverage: ${coverage.point_mapped_addresses.toLocaleString()} documented field-point addresses across the captured source. These are address records, not a count of distinct wired points.`, 'muted'));
      if (counts.unknown) {
        totals.append(el('p', 'Catalog coverage is incomplete. Unclassified module records can include unsupported I/O or infrastructure catalogs. A zero recognized AI or AO card count does not establish that analogue I/O is absent. Open an unclassified record to inspect its catalog and classification reason.', 'field-io-coverage-note'));
        const reasons = coverage.modules_by_field_type_reason;
        const unresolved = Object.keys(typeReasons).filter(reason => reason !== 'exact_vendor_catalog');
        if (reasons && unresolved.every(reason => Number.isInteger(reasons[reason]) && reasons[reason] >= 0)
            && unresolved.reduce((sum, reason) => sum + reasons[reason], 0) === counts.unknown) {
          const breakdown = el('details', undefined, 'field-io-reason-counts');
          breakdown.append(el('summary', 'Why module records are unclassified'));
          const list = el('ul');
          unresolved.filter(reason => reasons[reason] > 0).forEach(reason => {
            list.append(el('li', `${typeReasons[reason]} · ${reasons[reason].toLocaleString()} module record${reasons[reason] === 1 ? '' : 's'}`));
          });
          breakdown.append(list); totals.append(breakdown);
        }
      }
    }
    function placeholder() {
      detail.replaceChildren(el('h2', 'Choose a module'), el('p', 'Open a card to inspect its captured addresses, aliases and recorded rung uses.'));
    }
    function sourceButton(label, id, kind = 'object') {
      const expected = key;
      return button(label, () => {
        if (!current(expected)) { ensureCurrent(); return; }
        return options.openSource(id, kind);
      }, 'text-link');
    }
    function sourceReportLink(label, view, ownerId = '') {
      const expected = key;
      const link = el('a', label, 'text-link');
      link.href = '/analysis#view=' + encodeURIComponent(view)
        + (ownerId ? '&source=' + encodeURIComponent(ownerId) : '');
      link.target = '_blank'; link.rel = 'noopener';
      const guard = event => {
        if (!current(expected)) { event.preventDefault(); ensureCurrent(); }
      };
      link.addEventListener('click', guard);
      link.addEventListener('auxclick', guard);
      return link;
    }
    function paging(target, result, label, load) {
      const previous = button('Previous ' + label, () => { if (ensureCurrent()) return load(result.page - 1); });
      const next = button('Next ' + label, () => { if (ensureCurrent()) return load(result.page + 1); });
      previous.disabled = result.page <= 1; next.disabled = result.page >= result.pages;
      target.replaceChildren(previous, el('span', `${result.total.toLocaleString()} ${label} · page ${result.page} of ${result.pages}`), next);
      target.hidden = result.pages <= 1;
    }
    function paintCards(result) {
      cards.replaceChildren();
      if (!result) return;
      const expected = key;
      result.items.forEach(module => {
        const card = el('article', undefined, 'field-io-card' + (module.id === moduleId ? ' is-current' : ''));
        const title = button(module.name || 'Unnamed module', () => {
          if (!current(expected)) { ensureCurrent(); return; }
          moduleId = module.id; signalPage = 1; paintCards(lastDirectory); return loadDetail();
        }, 'field-io-card-open');
        title.setAttribute('aria-pressed', String(module.id === moduleId));
        const pick = el('input', undefined, 'field-io-module-check'); pick.type = 'checkbox';
        pick.checked = selected.has(module.id);
        pick.disabled = module.grouping_scope !== 'module_declaration'
          || module.group_member_ids?.length !== 1 || module.group_member_ids[0] !== module.id;
        pick.addEventListener('change', () => {
          if (!current(expected)) { ensureCurrent(); return; }
          if (pick.disabled) return;
          if (pick.checked) selected.set(module.id, module.name || module.id); else selected.delete(module.id);
          paintSelection();
        });
        const heading = el('div', undefined, 'field-io-card-heading');
        heading.append(title, field('Select whole module', pick));
        card.append(heading, el('span', moduleTypes[module.field_type] || moduleTypes.unknown, 'chip'),
          facts([['Controller', module.controller?.name], ['Parent / rack', module.parent_module_name],
            ['Slot', module.slot], ['Catalog', module.catalog_number],
            ['Data directions', (module.directions || []).map(human).join(' · ') || 'Unresolved']]));
        if (module.field_type === 'unknown')
          card.append(el('p', typeReasons[module.field_type_reason] || 'Catalog classification is unresolved', 'field-io-classification-reason'));
        catalogFunction(card, module);
        description(card, module, directoryMode, true);
        if (Number.isInteger(module.point_mapped_address_count))
          card.append(el('strong', `${module.point_mapped_address_count} documented field-point address${module.point_mapped_address_count === 1 ? '' : 'es'}`, 'field-io-point-count'));
        card.append(el('small', `${module.address_count || 0} captured addresses · ${module.rung_count || 0} linked rungs`, 'muted'));
        cards.append(card);
      });
      if (!result.items.length) cards.append(el('p', 'No module cards match these filters.', 'empty'));
    }
    async function loadDirectory() {
      if (!ensureCurrent()) return;
      const expected = key, expectedRun = runId, serial = ++directorySerial;
      status.textContent = 'Loading captured module cards…'; directory.setAttribute('aria-busy', 'true');
      lastDirectory = null; cards.replaceChildren(); pager.replaceChildren();
      try {
        const result = await options.api(request());
        if (!current(expected) || serial !== directorySerial) return;
        checkResult(result, expectedRun);
        lastDirectory = result.modules; page = result.modules.page; directoryMode = result.presentation_mode || 'original';
        paintTotals(result.coverage);
        status.textContent = result.available ? `${result.modules.total.toLocaleString()} module cards match the filters. Descriptions follow the selected source language.`
          : result.notice || 'Module evidence is unavailable for this analysis.';
        paintCards(lastDirectory);
        paging(pager, lastDirectory, 'modules', next => { page = next; return loadDirectory(); });
      } catch (error) {
        if (!current(expected) || serial !== directorySerial) return;
        status.textContent = error.message || 'The module cards could not be loaded.';
        cards.replaceChildren(button('Retry module cards', loadDirectory));
      } finally {
        if (current(expected) && serial === directorySerial) directory.removeAttribute('aria-busy');
      }
    }
    function catalogFunction(parent, module, full = false) {
      const block = el('section', undefined, 'field-io-catalog-function');
      block.append(el('strong', 'Catalog function'), el('p', module.catalog_description || 'No manufacturer description is available for this catalog yet.'));
      if (module.catalog_family) block.append(el('small', 'Catalog family: ' + module.catalog_family, 'muted'));
      block.append(el('small', module.catalog_description
        ? 'Manufacturer documentation; separate from the L5X source wording.'
        : 'Catalog metadata is separate from the L5X source wording.', 'muted'));
      if (full) {
        const capacity = module.catalog_capacity;
        if (capacity && ['di', 'do', 'ai', 'ao'].some(kind => Number.isInteger(capacity[kind]) && capacity[kind] > 0)) {
          const heading = module.catalog_capacity_basis === 'maximum_configuration_dependent'
            ? 'Documented maximum capacity (configuration dependent)' : 'Documented catalog capacity';
          block.append(el('strong', heading), facts(['di', 'do', 'ai', 'ao']
            .filter(kind => Number.isInteger(capacity[kind]) && capacity[kind] > 0)
            .map(kind => [types[kind], capacity[kind]])),
          el('small', 'Catalog capacity does not establish the active configuration or the number of wired points.', 'muted'));
        }
        if (typeof module.catalog_reference === 'string') {
          try {
            const url = new URL(module.catalog_reference);
            if (url.protocol === 'https:' && ['rockwellautomation.com', 'www.rockwellautomation.com', 'literature.rockwellautomation.com', 'configurator.rockwellautomation.com'].includes(url.hostname) && !url.username && !url.password && !url.port) {
              const reference = el('a', 'Catalog reference' + (module.catalog_publication ? ' · ' + module.catalog_publication : '')
                + (module.catalog_reference_page ? ' · p. ' + module.catalog_reference_page : '') + ' ↗');
              reference.href = url.href; reference.target = '_blank'; reference.rel = 'noopener noreferrer'; block.append(reference);
            }
          } catch { /* Source text is not treated as an external link. */ }
        }
      }
      parent.append(block);
    }
    function description(parent, record, mode, compact = false) {
      const notes = record.source_annotations;
      if (Array.isArray(notes) && notes.length) {
        const section = el(compact ? 'details' : 'section', undefined, 'field-io-source-annotations');
        section.append(el(compact ? 'summary' : 'h4', 'Source comments and descriptions'));
        notes.slice(0, 8).forEach(note => {
          const entry = el('article', undefined, 'field-io-source-note');
          const label = note.kind === 'member_comment' ? 'Member comment' : note.kind === 'source_description' ? 'Source description' : 'Captured source note';
          const basis = note.via === 'alias' ? 'Via alias' + (note.owner_name ? ': ' + note.owner_name : '')
            : note.via === 'backing_declaration' ? 'Backing tag' : note.via === 'module' ? 'Module declaration' : '';
          const provenance = [label, basis,
            note.language ? 'Recorded language: ' + note.language : '', note.suffix || ''].filter(Boolean);
          entry.append(el('strong', provenance.join(' · ')));
          const prose = el('div', undefined, 'field-io-description');
          if (window.PLCTranslation?.renderProse) window.PLCTranslation.renderProse(prose, note.text, note.wording, mode);
          else prose.textContent = note.text || 'No note text captured';
          entry.append(prose);
          if (note.owner_id) entry.append(sourceReportLink('Open note source' + (note.owner_name ? ': ' + note.owner_name : ''), 'objects', note.owner_id));
          if (note.text_truncated || note.wording?.text_truncated) entry.append(el('small', 'Source note preview shortened; use Open note source to read its complete wording in a separate window.', 'muted'));
          section.append(entry);
        });
        if (record.source_annotations_truncated || notes.length > 8) {
          const total = Number.isInteger(record.source_annotations_total) ? ` of ${record.source_annotations_total}` : '';
          section.append(el('p', `Showing ${Math.min(notes.length, 8)}${total} source comments and descriptions. Browse all source comments to find the additional wording in a separate window.`, 'muted'),
            sourceReportLink('Browse all source comments', 'annotations'));
        }
        parent.append(section); return;
      }
      const backing = record.description_basis === 'backing_declaration';
      parent.append(el('strong', backing ? 'Backing tag description' : 'Source description', 'field-io-description-label'));
      const prose = el('div', undefined, 'field-io-description');
      if (record.description && window.PLCTranslation?.renderProse)
        window.PLCTranslation.renderProse(prose, record.description, record.wording?.description, mode);
      else prose.textContent = record.description || (backing ? 'No backing tag description captured' : 'No source description captured');
      parent.append(prose);
      if (record.description_truncated || record.wording?.description?.text_truncated)
        parent.append(el('small', 'Description preview shortened; open the source for complete wording.', 'muted'));
    }
    function renderUses(target, address, generation) {
      target.replaceChildren();
      const expected = key, expectedModule = moduleId, expectedSignalPage = signalPage;
      if (!Array.isArray(address.uses) || address.uses.length > USE_SIZE) throw new Error('The source-use page exceeded its expected bounds.');
      const list = el('ul', undefined, 'field-io-use-list');
      address.uses.forEach(use => {
        const item = el('li');
        item.append(sourceButton(`${use.opcode || 'Instruction'} · rung ${use.rung_number ?? '?'} · ${human(use.role) || 'recorded use'}`, use.rung_id, 'rung'),
          el('span', use.path || 'Source path not captured', 'muted'), el('code', use.variable || address.address));
        if (use.path_truncated || use.variable_truncated) item.append(el('small', 'Source-use preview shortened; open the rung for complete source.', 'muted'));
        list.append(item);
      });
      if (!address.uses.length) list.append(el('li', 'No captured rung uses for this address.'));
      const pages = el('div', undefined, 'pagination field-io-use-pages');
      target.append(list, pages);
      let serial = 0;
      const load = async next => {
        if (!current(expected) || detailSerial !== generation || moduleId !== expectedModule) { ensureCurrent(); return; }
        const requestSerial = ++serial;
        target.setAttribute('aria-busy', 'true');
        try {
          const result = await options.api(request({module_id: expectedModule, signal_page: String(expectedSignalPage), address_id: address.id, use_page: String(next)}));
          if (!current(expected) || detailSerial !== generation || serial !== requestSerial || moduleId !== expectedModule) return;
          checkResult(result, runId, expectedModule);
          const row = result.addresses.items.find(item => item.id === address.id);
          if (!row) throw new Error('This address is no longer on the selected page. Reload the module.');
          renderUses(target, row, generation);
        } catch (error) {
          if (!current(expected) || detailSerial !== generation || serial !== requestSerial) return;
          pages.replaceChildren(el('p', error.message || 'The rung uses could not be loaded.'), button('Retry rung uses', () => load(next)));
        } finally {
          if (current(expected) && detailSerial === generation && serial === requestSerial) target.removeAttribute('aria-busy');
        }
      };
      paging(pages, {total: address.uses_total, page: address.use_page, pages: address.use_pages}, 'rung uses', load);
    }
    function renderAddress(address, generation, mode) {
      const item = el('article', undefined, 'field-io-address');
      item.append(el('h3', address.address || address.root_name || 'Unresolved address'),
        facts([['Field type', types[address.field_type] || types.unknown], ['Point evidence', human(address.point_status) || 'Unresolved'],
          ['Data direction', human(address.direction) || 'Unresolved'], ['Member channel index', address.channel], ['Captured datatype', address.datatype]]));
      if (address.configuration_status === 'input_mode_unresolved')
        item.append(el('p', 'The input mode is unresolved. This member index does not establish the wired channel or terminal.', 'muted'));
      description(item, address, mode);
      item.append(sourceButton('Open backing declaration', address.root_id));
      if (address.aliases?.length) {
        const aliases = el('details', undefined, 'field-io-aliases');
        aliases.append(el('summary', `Source aliases (${address.aliases_total})`));
        address.aliases.forEach(alias => {
          const entry = el('div'); entry.append(sourceButton(alias.name || alias.id, alias.id), el('small', alias.path, 'muted'));
          description(entry, alias, mode); aliases.append(entry);
        });
        if (address.aliases_truncated) aliases.append(el('p', 'Additional aliases are outside this preview. Inspect the backing declaration for source context.', 'muted'));
        item.append(aliases);
      }
      const uses = el('details', undefined, 'field-io-uses'), body = el('div');
      uses.append(el('summary', `Captured rung uses (${address.uses_total})`), body);
      renderUses(body, address, generation); item.append(uses);
      return item;
    }
    function renderModule(result, generation) {
      detail.replaceChildren();
      const module = result.selected_module;
      if (!result.available || !module) { detail.append(el('p', result.notice || 'Module details are unavailable.')); return; }
      detail.append(el('h2', module.name || 'Unnamed module'), el('p', module.path, 'muted'),
        el('span', moduleTypes[module.field_type] || moduleTypes.unknown, 'chip'),
        facts([['Controller', module.controller?.path || module.controller?.name], ['Catalog', module.catalog_number],
          ['Parent / rack', module.parent_module_name], ['Slot', module.slot], ['Location evidence', human(module.location_status)],
          ['Module role', moduleRoles[module.module_role] || moduleRoles.unknown],
          ['Supported field types', Array.isArray(module.field_types) && module.field_types.length ? module.field_types.map(kind => types[kind] || human(kind)).join(' · ') : 'None identified'],
          ['Type evidence', human(module.field_type_basis)], ['Classification reason', typeReasons[module.field_type_reason] || 'Not provided by this analysis'],
          ...(Number.isInteger(module.point_count) && module.point_count >= 0
            ? [[module.point_count_basis === 'maximum_configuration_dependent' ? 'Maximum capacity (configuration dependent)' : 'Documented rated capacity', module.point_count]] : [])]));
      catalogFunction(detail, module, true);
      description(detail, module, result.presentation_mode || 'original');
      detail.append(sourceButton('Open module source', module.id));
      const sourceInfo = el('details', undefined, 'field-io-module-source');
      sourceInfo.append(el('summary', 'Captured module connections and declarations'));
      ['ports', 'roots', 'rack_aliases'].forEach(name => {
        const rows = module[name] || [];
        sourceInfo.append(el('h3', `${human(name)} (${module[name + '_total'] ?? rows.length})`));
        rows.forEach(row => {
          const item = el('div', undefined, 'field-io-source-row');
          if (name === 'ports') item.append(facts([['Port', row.port_id], ['Type', row.type], ['Address', row.address], ['Upstream', upstreamLabel(row.upstream)]]));
          else {
            item.append(sourceButton(row.name || row.alias_for || row.id, row.id),
              el('p', name === 'roots' ? `${human(row.direction) || 'Unresolved direction'} · ${row.datatype || 'Unspecified datatype'} · ${human(row.name_origin)}`
                : `Backing unresolved · ${row.alias_for || 'Target not captured'}`, 'muted'));
            description(item, row, result.presentation_mode || 'original');
          }
          sourceInfo.append(item);
        });
        if (module[name + '_truncated']) sourceInfo.append(el('p', 'This source preview is limited to 24 records.', 'muted'));
      });
      detail.append(sourceInfo, el('h3', 'Identified field addresses'));
      const pages = el('div', undefined, 'pagination field-io-address-pages');
      paging(pages, result.addresses, 'addresses', next => { signalPage = next; return loadDetail(); }); detail.append(pages);
      const mapped = result.addresses.items.filter(address => address.point_status === 'documented_member_layout'
        && ['di', 'do', 'ai', 'ao'].includes(address.field_type) && address.channel !== null);
      const other = result.addresses.items.filter(address => !mapped.includes(address));
      const totalPoints = Number.isInteger(module.point_mapped_address_count)
        ? ` Module total: ${module.point_mapped_address_count} matched address${module.point_mapped_address_count === 1 ? '' : 'es'}. These are source records, not a count of distinct wired points.` : '';
      detail.append(el('p', `${mapped.length} documented field-point address${mapped.length === 1 ? '' : 'es'} on this page.${totalPoints} Address paging covers both sections below; documented field addresses appear first.`, 'muted'));
      const points = el('section', undefined, 'field-io-points');
      points.setAttribute('aria-label', 'Identified field addresses on this address page');
      mapped.forEach(address => points.append(renderAddress(address, generation, result.presentation_mode || 'original')));
      if (!mapped.length) points.append(el('p', result.addresses.total
        ? 'No documented field-point addresses on this address page. Other pages and the unresolved addresses below may contain further evidence.'
        : 'No captured field addresses are available for this module. Its declaration remains available.', 'empty'));
      detail.append(points);
      if (other.length) {
        const remaining = el('details', undefined, 'field-io-other-addresses');
        remaining.append(el('summary', `Other captured addresses and status (${other.length} on this page)`),
          el('p', 'Roots, diagnostics, configuration, feedback and unresolved members stay available here. Their presence does not establish a physical field point.', 'muted'));
        other.forEach(address => remaining.append(renderAddress(address, generation, result.presentation_mode || 'original')));
        detail.append(remaining);
      }
      if (result.limitations?.length) {
        const limits = el('details', undefined, 'field-io-limitations'); limits.append(el('summary', 'Evidence limits'));
        result.limitations.forEach(text => limits.append(el('p', text))); detail.append(limits);
      }
    }
    async function loadDetail() {
      if (!ensureCurrent() || !moduleId) return;
      const expected = key, expectedRun = runId, expectedModule = moduleId, serial = ++detailSerial;
      detail.setAttribute('aria-busy', 'true'); detail.replaceChildren(el('p', 'Loading module addresses…'));
      try {
        const result = await options.api(request({module_id: expectedModule, signal_page: String(signalPage)}));
        if (!current(expected) || serial !== detailSerial || moduleId !== expectedModule) return;
        checkResult(result, expectedRun, expectedModule); signalPage = result.addresses.page;
        renderModule(result, serial);
      } catch (error) {
        if (!current(expected) || serial !== detailSerial || moduleId !== expectedModule) return;
        detail.replaceChildren(el('p', error.message || 'The module details could not be loaded.', 'warning-panel'), button('Retry module details', loadDetail));
      } finally {
        if (current(expected) && serial === detailSerial) detail.removeAttribute('aria-busy');
      }
    }
    function changeFilters() {
      if (!ensureCurrent()) return;
      applied = {query: search.value.trim().slice(0, 256), field_type: type.value, direction: direction.value};
      page = signalPage = 1; moduleId = ''; ++detailSerial; detail.removeAttribute('aria-busy'); placeholder();
      return loadDirectory();
    }
    async function refresh() {
      active = true;
      const next = projectKey(), project = options.getState() || {};
      if (next !== key) {
        key = next; runId = project.active_run || ''; page = signalPage = 1; moduleId = ''; ++directorySerial; ++detailSerial;
        selected.clear(); lastDirectory = null; applied = {query: '', field_type: '', direction: ''};
        search.value = ''; type.value = ''; direction.value = ''; cards.replaceChildren(); pager.replaceChildren(); totals.replaceChildren(); placeholder();
        directory.removeAttribute('aria-busy'); detail.removeAttribute('aria-busy'); paintSelection();
      }
      if (!runId) { status.textContent = 'Choose an analysis under Project tools to browse its captured field I/O.'; return; }
      await Promise.all([loadDirectory(), moduleId ? loadDetail() : Promise.resolve()]);
    }
    function deactivate() { active = false; ++directorySerial; ++detailSerial; }
    filters.addEventListener('submit', event => { event.preventDefault(); return changeFilters(); });
    [type, direction].forEach(control => control.addEventListener('change', changeFilters));
    paintSelection(); placeholder();
    return {refresh, deactivate};
  }
  window.PLCFieldIO = Object.freeze({mount});
})();
