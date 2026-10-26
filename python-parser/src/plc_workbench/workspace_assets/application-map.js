/* Read-only configured hardware, declarations, payload members and recorded logic uses. */
(() => {
  'use strict';
  const SIZES = [10, 50, 100, 200, 500];
  const TABS = [['hardware', 'Hardware route'], ['registers', 'Registers & data'], ['coverage', 'Coverage']];
  const TYPES = {di: 'DI', do: 'DO', ai: 'AI', ao: 'AO', unknown: 'Unresolved'};
  const friendly = value => String(value ?? '').replaceAll('_', ' ');
  const text = value => value === undefined || value === null || value === '' ? 'Not captured' :
    Array.isArray(value) ? value.map(text).join(', ') || 'None recorded' : typeof value === 'object' ? JSON.stringify(value) : String(value);
  const el = (tag, value, cls = '') => {
    const node = document.createElement(tag); node.className = cls;
    if (value !== undefined && value !== null) node.textContent = String(value);
    return node;
  };
  const button = (label, action, cls = '') => {
    const node = el('button', label, cls); node.type = 'button'; node.addEventListener('click', action); return node;
  };
  const field = (label, control) => {
    const node = el('label', label); control.setAttribute('aria-label', label); node.append(control); return node;
  };
  const choice = (entries, value, cls) => {
    const node = el('select', undefined, cls);
    entries.forEach(([id, label]) => { const option = el('option', label); option.value = String(id); node.append(option); });
    node.value = String(value); return node;
  };
  const validPage = (page, size) => page && Array.isArray(page.items) && page.items.length <= size &&
    Number.isInteger(page.total) && page.total >= 0 && Number.isInteger(page.page) && page.page > 0 &&
    Number.isInteger(page.pages) && page.pages >= page.page && page.page_size === size;

  function mount(root, options) {
    let live = true, serial = 0, identity = '', runId = '', revision = -1, currentState = {}, data = null, revealSelection = false;
    const view = {tab: 'hardware', page: 1, module_page: 1, use_page: 1, page_size: 50,
      query: '', direction: '', datatype: '', declaration_kind: '', member_kind: '', logic_role: '', module_id: '', register_id: ''};
    const heading = el('div', undefined, 'application-intro');
    heading.append(el('h2', 'Application & register map'), el('span', 'Read only', 'application-readonly'),
      el('p', 'Follow configured hardware routes, inspect declarations and raw payloads, then trace their captured logic uses. Physical channels, numeric storage and logical roles are shown separately.'));
    const tabs = el('nav', undefined, 'application-tabs'); tabs.setAttribute('aria-label', 'Application map sections');
    const tabButtons = TABS.map(([id, label]) => {
      const item = button(label, () => { view.tab = id; render(); }); item.setAttribute('aria-pressed', id === view.tab ? 'true' : 'false'); tabs.append(item); return [id, item];
    });
    const filters = el('form', undefined, 'filters application-filters');
    const query = el('input', undefined, 'application-query'); query.type = 'search'; query.maxLength = 256;
    const direction = choice([['', 'All directions'], ['input', 'Input'], ['output', 'Output'], ['configuration', 'Configuration'], ['internal', 'Internal']], '', 'application-direction');
    const datatype = el('input', undefined, 'application-datatype'); datatype.maxLength = 80; datatype.placeholder = 'e.g. SINT, REAL, TIMER';
    const declaration = choice([['', 'All declarations'], ...['base', 'alias', 'produced', 'consumed', 'module_input', 'module_output', 'module_configuration', 'aoi_parameter', 'aoi_local', 'unknown'].map(value => [value, friendly(value)])], '', 'application-declaration');
    const member = choice([['', 'All records'], ['declaration', 'Declarations'], ['container', 'Containers / arrays'], ['scalar', 'Scalar members'], ['bit', 'Bit references']], '', 'application-member');
    const role = choice([['', 'All logic access'], ['read', 'Read'], ['write', 'Write'], ['read_write', 'Read and write'], ['unknown', 'Unknown'], ['unused', 'No recorded use']], '', 'application-role');
    const size = choice(SIZES.map(value => [value, value]), view.page_size, 'application-page-size');
    const submit = el('button', 'Search'); submit.type = 'submit';
    const reset = button('Clear filters', () => {
      [query, datatype, direction, declaration, member, role].forEach(control => { control.value = ''; });
      Object.assign(view, {module_id: '', register_id: ''}); return applyFilters();
    });
    const registerControls = el('div', undefined, 'application-register-filters');
    registerControls.append(field('Direction', direction), field('Declared datatype', datatype), field('Declaration kind', declaration), field('Record kind', member), field('Logic access', role));
    filters.append(field('Find name, address, description or catalog', query), registerControls, field('Rows per page', size), submit, reset);
    const status = el('p', undefined, 'application-status'); status.setAttribute('role', 'status');
    const scope = el('div', undefined, 'application-scope');
    const body = el('div', undefined, 'application-body');
    root.replaceChildren(heading, tabs, filters, scope, status, body);
    const getState = () => options.getState?.() || currentState;
    const keyOf = state => JSON.stringify([state.project_path || '', state.active_run || '']);
    const current = expected => live && identity === expected && keyOf(getState()) === expected;
    const notice = (message, error = false) => { status.textContent = message; status.className = 'application-status' + (error ? ' is-error' : ''); };
    function sourceButton(label, id, kind = 'source') {
      const expected = identity, item = button(label, () => {
        if (!current(expected)) { notice('The active analysis changed. Reload this page before opening its source.', true); return; }
        if (kind === 'rung') options.onRung?.(id); else options.onSource?.(id);
      }, 'application-source-link');
      item.disabled = !id; return item;
    }
    function applyFilters() {
      Object.assign(view, {query: query.value.trim(), direction: direction.value, datatype: datatype.value.trim(),
        declaration_kind: declaration.value, member_kind: member.value, logic_role: role.value, page_size: Number(size.value), page: 1, module_page: 1, use_page: 1, register_id: ''});
      return refresh();
    }
    filters.addEventListener('submit', event => { event.preventDefault(); applyFilters(); });
    [direction, declaration, member, role, size].forEach(control => control.addEventListener('change', applyFilters));
    function facts(entries, cls = '') {
      const node = el('dl', undefined, 'application-facts ' + cls);
      entries.forEach(([label, value]) => node.append(el('dt', label), el('dd', text(value)))); return node;
    }
    function description(row, tag = 'p') {
      const node = el(tag, undefined, 'application-description');
      if (!row.description) node.textContent = 'No source wording captured';
      else if (window.PLCTranslation?.renderProse) window.PLCTranslation.renderProse(node, row.description, row.wording?.description, data?.presentation_mode);
      else node.textContent = row.description || 'No source wording captured'; return node;
    }
    function referenceLink(label, value) {
      try {
        const address = new URL(value); if (!['https:', 'http:'].includes(address.protocol)) return null;
        const link = el('a', label, 'application-reference'); link.href = address.href; link.target = '_blank'; link.rel = 'noopener noreferrer'; return link;
      } catch { return null; }
    }
    function objectDetails(label, value, open = false) {
      const panel = el('details', undefined, 'application-evidence'); panel.open = open; panel.append(el('summary', label));
      if (value === undefined || value === null || (Array.isArray(value) && !value.length)) panel.append(el('p', 'Not captured in this analysis.', 'muted'));
      else if (Array.isArray(value)) value.forEach((item, index) => panel.append(typeof item === 'object' && item !== null ? facts(Object.entries(item).map(([key, entry]) => [friendly(key), entry])) : el('p', text(item))));
      else if (typeof value === 'object') panel.append(facts(Object.entries(value).map(([key, entry]) => [friendly(key), entry])));
      else panel.append(el('p', text(value)));
      return panel;
    }
    function pager(page, parameter, label) {
      const node = el('div', undefined, 'pagination application-pagination');
      const previous = button('Previous ' + label, () => { view[parameter] = page.page - 1; return refresh(); }); previous.disabled = page.page <= 1;
      const next = button('Next ' + label, () => { view[parameter] = page.page + 1; return refresh(); }); next.disabled = page.page >= page.pages;
      node.append(previous, el('span', `${page.total} ${label} · page ${page.page} of ${page.pages}`), next); return node;
    }
    function chooseModule(id, showHardware = true) {
      Object.assign(view, {module_id: id || '', register_id: '', page: 1, module_page: 1, use_page: 1});
      if (showHardware) { view.tab = 'hardware'; revealSelection = Boolean(id); } return refresh();
    }
    function chooseRegister(id) {
      Object.assign(view, {register_id: id, use_page: 1, tab: 'registers'}); revealSelection = true; return refresh();
    }
    function route(module) {
      const section = el('section', undefined, 'application-route'); section.append(el('h3', 'Configured route'));
      const metadata = module.route || {}, nodes = metadata.modules || (metadata.module_ids || []).map(id => data.modules.items.find(item => item.id === id) || {id, name: id});
      const chain = el('div', undefined, 'application-route-chain'); chain.setAttribute('aria-label', 'Configured parent-module ancestry');
      const unique = nodes.filter((item, index) => index === 0 || item.id !== nodes[index - 1].id);
      unique.forEach((item, index) => {
        if (index) chain.append(el('span', '→', 'application-route-arrow'));
        const node = button(item.name || item.id, () => chooseModule(item.id), 'application-route-node');
        if (item.id === module.id) node.setAttribute('aria-current', 'true'); chain.append(node);
      });
      if (!unique.length) chain.append(el('span', 'Ancestry is not captured.', 'muted'));
      section.append(chain, el('p', 'Route status: ' + friendly(metadata.status || 'unknown') + '. This is configured ancestry, not verified field wiring.', 'muted'));
      const attachment = module.attachment || {};
      section.append(facts([['Parent module', module.parent_name], ['Parent attachment', attachment.status], ['Parent port', attachment.parent_port_id],
        ['Parent port type', attachment.parent_port_type], ['Parent port address', attachment.parent_port_address]]));
      if (module.parent_id && module.parent_id !== module.id) section.append(button('Inspect parent module', () => chooseModule(module.parent_id), 'application-source-link'));
      return section;
    }
    function moduleDetail(module) {
      const panel = el('section', undefined, 'application-detail'); panel.setAttribute('aria-label', 'Selected hardware module');
      const tools = el('div', undefined, 'application-detail-heading');
      tools.append(el('h3', module.name || 'Unnamed module'), sourceButton('Open module source', module.id)); panel.append(tools);
      panel.append(facts([['Controller', module.controller?.name], ['Catalog number', module.catalog_number], ['Vendor', module.vendor], ['Module role', module.module_role]]), description(module));
      if (module.catalog_description) panel.append(el('p', 'Manufacturer catalog wording: ' + module.catalog_description, 'muted'));
      const catalog = referenceLink('Open manufacturer catalog reference', module.catalog_reference); if (catalog) panel.append(catalog);
      panel.append(route(module));
      const ports = el('details', undefined, 'application-evidence'); ports.open = true; ports.append(el('summary', 'Ports · configured addresses and direction'));
      (module.ports || []).forEach(port => {
        const entry = el('article', undefined, 'application-port'); entry.append(el('h4', `Port ${port.port_id ?? port.Id ?? '?'} · ${port.type || port.Type || 'Type not captured'}`),
          facts([['Address', port.address ?? port.Address], ['Upstream', port.upstream ?? port.Upstream], ['Source qualification', port.qualified ? 'Qualified' : 'Not established']]));
        if (port.id) entry.append(sourceButton('Open port source', port.id)); ports.append(entry);
      });
      if (!(module.ports || []).length) ports.append(el('p', 'No port configuration was captured.', 'muted')); panel.append(ports);
      const connections = el('details', undefined, 'application-evidence'); connections.open = true;
      connections.append(el('summary', `Connections · ${(module.connections || []).length} captured`));
      (module.connections || []).forEach((connection, index) => {
        const row = el('article', undefined, 'application-connection'), attributes = facts(Object.entries(connection.attributes || {}).map(([label, value]) => [label, value]));
        Object.keys(connection.attributes || {}).forEach((key, position) => {
          const help = connection.attribute_help?.[key]; if (help?.meaning) attributes.children[position * 2].title = help.meaning;
        });
        row.append(el('h4', connection.name || connection.attributes?.Name || `Connection ${index + 1}`), attributes);
        if (connection.source_id) row.append(sourceButton('Open connection source', connection.source_id));
        (connection.input_root_ids || []).forEach((id, ordinal) => row.append(sourceButton('Open input payload ' + (ordinal + 1), id)));
        (connection.output_root_ids || []).forEach((id, ordinal) => row.append(sourceButton('Open output payload ' + (ordinal + 1), id)));
        if (connection.attribute_help) row.append(objectDetails('Connection attribute meanings', connection.attribute_help));
        row.append(el('p', 'Connection attributes are the captured configuration. Byte sizes and assembly instances do not establish a physical channel count.', 'muted'));
        connections.append(row);
      });
      if (!(module.connections || []).length) connections.append(el('p', 'No connection record was captured for this module.', 'muted'));
      panel.append(connections, objectDetails('Captured module attributes', module.attributes),
        button('Inspect this module’s registers', () => { view.tab = 'registers'; return refresh(); }, 'primary'));
      return panel;
    }
    function hardware() {
      const layout = el('div', undefined, 'application-layout'), directory = el('section', undefined, 'application-directory');
      directory.append(el('h3', 'Configured modules'), pager(data.modules, 'module_page', 'modules'));
      const groups = new Map();
      data.modules.items.forEach(module => {
        const controller = module.controller || {}, id = controller.id || controller.name || 'unresolved';
        if (!groups.has(id)) groups.set(id, {name: controller.name || 'Controller not captured', rows: []}); groups.get(id).rows.push(module);
      });
      groups.forEach(group => {
        const section = el('details', undefined, 'application-controller'); section.open = true; section.append(el('summary', group.name));
        group.rows.forEach(module => {
          const row = el('article', undefined, 'application-module' + (view.module_id === module.id ? ' is-selected' : ''));
          row.append(button(module.name || 'Unnamed module', () => chooseModule(module.id), 'application-module-name'), el('span', module.catalog_number || 'Catalog not captured', 'application-module-catalog'),
            el('p', 'Parent: ' + (module.parent_name || 'Not captured'), 'muted'));
          if (module.description) row.append(description(module));
          section.append(row);
        }); directory.append(section);
      });
      if (!data.modules.items.length) directory.append(el('p', 'No configured modules match this selection. Registers and logic may still exist in this export.', 'notice'));
      layout.append(directory);
      if (data.selected_module) {
        const detail = moduleDetail(data.selected_module); layout.append(detail);
        if (revealSelection && window.innerWidth <= 850) setTimeout(() => { if (live && detail.isConnected !== false) detail.scrollIntoView?.({block: 'start'}); }, 0);
      }
      else layout.append(el('p', 'Select a module to follow its configured route, inspect ports and connections, and open its registers.', 'application-empty-detail'));
      body.append(layout);
    }
    function dimension(label, value, state, provenance) {
      const card = el('div', undefined, 'application-dimension');
      card.append(el('dt', label), el('dd', text(value)));
      if (state) card.append(el('small', 'Evidence: ' + friendly(typeof state === 'object' ? state.status || state.basis || text(state) : state), 'muted'));
      if (provenance) card.append(objectDetails('Source / basis', provenance)); return card;
    }
    function registerDetail(row) {
      const panel = el('section', undefined, 'application-detail application-register-detail'); panel.setAttribute('aria-label', 'Selected register evidence');
      const heading = el('div', undefined, 'application-detail-heading'); heading.append(el('h3', row.address || row.name || 'Unnamed register'), sourceButton('Open source', row.source_id)); panel.append(heading);
      panel.append(el('p', row.path || row.scope?.path || 'Source path not captured', 'application-path'));
      const states = row.states || {}, provenance = row.provenance || {}, dimensions = el('dl', undefined, 'application-dimensions');
      [['Declaration kind', row.declaration_kind, 'declaration_kind'], ['Declared datatype', row.declared_datatype || row.datatype, 'datatype'], ['Data direction', row.io_direction, 'io_direction'],
        ['Logic access', row.logic_access?.roles?.join(', ') || (row.logic_access?.uses_total ? 'Not classified' : 'No recorded use'), 'logic_access'],
        ['Logical meaning', row.logical_meaning?.label || row.logical_meaning?.value || 'Unresolved', 'logical_meaning'],
        ['Physical classification', TYPES[row.physical?.field_type] || 'Unresolved', 'physical'],
        ['Transport', row.transport?.label || row.transport?.value || (typeof row.transport === 'string' ? row.transport : 'Unresolved'), 'transport'],
        ['External access', row.external_access, 'external_access']].forEach(([label, value, key]) => {
          const stateKey = {declaration_kind: 'declaration', io_direction: 'direction'}[key] || key;
          const basis = provenance[key] || (provenance[key + '_source_ids']?.length ? {source_ids: provenance[key + '_source_ids']} : null) ||
            (row[key]?.basis ? {basis: row[key].basis} : null);
          const status = row.metadata_conflicts?.[key] ? 'source_conflict' : states[stateKey] || row[key]?.status;
          dimensions.append(dimension(label, value, status, basis));
        });
      panel.append(dimensions, facts([['Storage record', row.member_kind], ['Radix', row.radix], ['Alias target', row.alias_target], ['Physical channel', row.physical?.channel], ['Source scope', row.scope?.name]]));
      if (row.metadata_conflicts && Object.keys(row.metadata_conflicts).length) {
        const conflict = el('section', undefined, 'warning-panel application-metadata-conflict');
        conflict.append(el('strong', 'Conflicting source metadata'), el('p', 'The declaration and captured data disagree. Both are retained; the effective storage interpretation remains unresolved.'), objectDetails('Compare declaration and captured values', row.metadata_conflicts, true)); panel.append(conflict);
      }
      const physicalReference = referenceLink('Open channel profile reference', row.physical?.reference); if (physicalReference) panel.append(physicalReference);
      if (row.parent_register_id) panel.append(button('Inspect containing register / array', () => chooseRegister(row.parent_register_id), 'application-parent-register'));
      if (row.alias_binding?.register_id) panel.append(button('Inspect alias target storage', () => chooseRegister(row.alias_binding.register_id), 'application-source-link'));
      if (row.module_id) panel.append(button('Inspect associated hardware route', () => chooseModule(row.module_id), 'application-source-link'));
      panel.append(el('p', 'Aliases name existing storage. Recorded writes change values. A scalar byte, word or bit reference does not by itself establish a wired channel.', 'muted'));
      const descriptions = el('details', undefined, 'application-evidence application-descriptions'); descriptions.open = true;
      descriptions.append(el('summary', 'Descriptions and comments'));
      const selection = row.description_selection || {};
      if (row.description) descriptions.append(description(row));
      descriptions.append(facts([['Selection basis', selection.basis], ['Selection status', selection.status]]));
      if (selection.conflict) descriptions.append(el('p', 'Conflicting source wording is preserved below. The preferred text is a display choice, not a resolved engineering decision.', 'warning-panel'));
      if (selection.candidates?.length) {
        const candidates = el('details', undefined, 'application-evidence'); candidates.append(el('summary', 'Description precedence and origin'));
        selection.candidates.forEach(candidate => {
          const item = el('article', undefined, 'application-annotation'); item.append(facts(Object.entries(candidate).filter(([key]) => !key.endsWith('_id') && key !== 'id').map(([key, value]) => [friendly(key), value])));
          if (candidate.owner_id) item.append(sourceButton('Open description candidate source', candidate.owner_id)); candidates.append(item);
        });
        if (selection.candidate_count > selection.candidates.length) candidates.append(el('p', `Showing ${selection.candidates.length} of ${selection.candidate_count} candidates; the remaining wording is available in source.`, 'muted'));
        descriptions.append(candidates);
      }
      (row.source_annotations || []).forEach(note => {
        const entry = el('article', undefined, 'application-annotation'); entry.append(el('strong', friendly(note.kind || 'Source wording') + (note.owner_name ? ' · ' + note.owner_name : '')));
        const wording = el('p');
        if (window.PLCTranslation?.renderProse) window.PLCTranslation.renderProse(wording, note.text, note.wording, data.presentation_mode); else wording.textContent = note.text || '';
        entry.append(wording); if (note.owner_id) entry.append(sourceButton('Open wording source', note.owner_id)); descriptions.append(entry);
      });
      if (row.source_annotations_truncated) descriptions.append(el('p', 'Additional wording remains in the complete source.', 'muted'));
      if (!row.description && !(row.source_annotations || []).length) descriptions.append(el('p', 'No description or comment was captured for this record.', 'muted'));
      panel.append(descriptions);
      const aliases = el('details', undefined, 'application-evidence'); aliases.append(el('summary', `Aliases · ${row.aliases_total || (row.aliases || []).length}`));
      (row.aliases || []).forEach(alias => { const item = el('p'); item.append(sourceButton(alias.name || alias.id, alias.id), el('span', ' → ' + (alias.alias_for || row.address || '') + (alias.status ? ' · ' + friendly(alias.status) : ''))); aliases.append(item); });
      if (row.aliases_total > (row.aliases || []).length) aliases.append(el('p', 'This preview is bounded. Open source to inspect all declarations.', 'muted'));
      panel.append(aliases, objectDetails('Exported values (not live readings)', row.values), objectDetails('Captured data representations', row.representations),
        objectDetails('Declaration attributes', row.attributes), objectDetails('Communication settings / produced-consumed relationships', row.communications),
        objectDetails('Source qualification and provenance', {states: row.states, provenance: row.provenance}));
      if (row.datatype_definition) {
        const definition = el('details', undefined, 'application-evidence'); definition.append(el('summary', 'Datatype definition · ' + (row.datatype_definition.name || row.datatype || 'Unnamed')));
        if (row.datatype_definition.source_id) definition.append(sourceButton('Open datatype source', row.datatype_definition.source_id));
        (row.datatype_definition.members || []).forEach(member => {
          const item = el('article', undefined, 'application-annotation'); item.append(el('strong', member.name || 'Unnamed member'), facts(Object.entries(member.attributes || {})));
          if (member.status) item.append(el('small', 'Evidence: ' + friendly(member.status), 'muted')); definition.append(item);
        });
        if (row.datatype_definition.members_truncated) definition.append(el('p', `Showing ${(row.datatype_definition.members || []).length} of ${row.datatype_definition.members_total} declared members. Open datatype source for the complete definition.`, 'muted'));
        panel.append(definition);
      }
      [['values', 'captured values'], ['representations', 'representations'], ['communications', 'communication records']].forEach(([key, label]) => {
        if (row[key + '_truncated']) panel.append(el('p', `This detail shows ${(row[key] || []).length} of ${row[key + '_total']} ${label}. Open the source for the complete captured record.`, 'muted'));
      });
      const uses = el('section', undefined, 'application-uses'); uses.append(el('h3', 'Recorded logic uses'));
      if (row.uses && validPage(row.uses, view.page_size)) {
        uses.append(pager(row.uses, 'use_page', 'uses'));
        row.uses.items.forEach(use => {
          const card = el('article', undefined, 'application-use');
          const header = el('div', undefined, 'application-use-heading'); header.append(el('strong', `${use.opcode || 'Instruction'} · ${friendly(use.role || 'unknown access')}`));
          if (use.rung_id) header.append(sourceButton(`Open rung ${use.rung_number ?? ''}`.trim(), use.rung_id, 'rung'));
          card.append(header, el('p', use.path || 'Source path not captured', 'application-path'));
          if (use.operand) card.append(facts([['Operand', use.operand]]));
          if (use.destination) card.append(facts([['Calculation destination', use.destination]]));
          if (use.expression) card.append(el('pre', use.expression, 'application-expression'));
          if (use.exact_instruction) card.append(el('code', use.exact_instruction, 'application-exact-instruction'));
          uses.append(card);
        });
        if (!row.uses.total) uses.append(el('p', 'No recorded exact-address use. Indirect, protected or unsupported logic may still use this storage; see Coverage.', 'muted'));
      } else uses.append(el('p', 'Use evidence was not returned for this record.', 'muted'));
      panel.append(uses); return panel;
    }
    function registers() {
      const layout = el('div', undefined, 'application-layout application-register-layout'), directory = el('section', undefined, 'application-directory');
      directory.append(el('p', 'Declarations, containers and members remain distinct. An input payload may contain measurements, status bytes, diagnostics and configuration echoes.', 'application-guide'), pager(data.registers, 'page', 'records'));
      const wrap = el('div', undefined, 'application-table-wrap'), table = el('table', undefined, 'application-table'), head = el('thead'), header = el('tr');
      ['Address / declaration', 'Datatype / storage', 'Direction / logic access', 'Physical channel', 'Source description'].forEach(label => header.append(el('th', label))); head.append(header);
      const rows = el('tbody');
      data.registers.items.forEach(row => {
        const tr = el('tr', undefined, view.register_id === row.id ? 'is-selected' : ''), name = el('td');
        name.append(button(row.address || row.name || 'Unnamed record', () => chooseRegister(row.id), 'application-register-name'), el('small', row.scope?.name || 'Scope not captured', 'muted'));
        const datatypeCell = el('td'); datatypeCell.append(el('strong', row.datatype || 'Unresolved'), el('small', friendly(row.member_kind || 'unknown record kind'), 'muted'));
        if (row.metadata_conflicts && Object.keys(row.metadata_conflicts).length) datatypeCell.append(el('small', 'Source metadata conflict', 'application-conflict'));
        const access = el('td'); access.append(el('span', friendly(row.io_direction || 'unknown direction')), el('small', (row.logic_access?.roles || []).map(friendly).join(', ') || 'No recorded use', 'muted'));
        const physical = el('td'); physical.append(el('span', TYPES[row.physical?.field_type] || 'Unresolved'), el('small', friendly(row.physical?.status || 'not established'), 'muted'));
        const wording = description(row, 'td');
        const basis = row.description_selection?.basis;
        if (row.description && basis && !basis.startsWith('exact_')) wording.append(el('small',
          !row.suffix && basis === 'backing_description' ? 'Declaration description' : friendly(basis) + ' (fallback)', 'muted'));
        if (row.description_selection?.conflict) wording.append(el('small', 'Conflicting source wording', 'application-conflict'));
        tr.append(name, datatypeCell, access, physical, wording); rows.append(tr);
      });
      table.append(head, rows); wrap.append(table); directory.append(wrap);
      if (!data.registers.items.length) directory.append(el('p', 'No records match these filters. Clear filters or inspect Coverage to see what was captured.', 'notice'));
      layout.append(directory);
      if (data.selected_register) {
        const detail = registerDetail(data.selected_register); layout.append(detail);
        if (revealSelection && window.innerWidth <= 1300) setTimeout(() => { if (live && detail.isConnected !== false) detail.scrollIntoView?.({block: 'start'}); }, 0);
      }
      else layout.append(el('p', 'Select a declaration or member to inspect its independent evidence, source wording, aliases, values and logic uses.', 'application-empty-detail'));
      body.append(layout);
    }
    function coverage() {
      const panel = el('section', undefined, 'application-coverage'); panel.append(el('h3', 'Captured application coverage'),
        el('p', 'These counts describe the saved export and available parser evidence. Missing source sections, protected logic and unresolved references remain explicit; a complete inventory is not proof of functional equivalence.'));
      const summary = data.coverage || {};
      const shown = new Set(), totals = el('div', undefined, 'application-coverage-totals');
      [['modules_total', 'Configured modules'], ['source_declarations', 'Source declarations'], ['raw_payload_members', 'Payload members'], ['vendor_documented_channels', 'Documented channel records']].forEach(([key, label]) => {
        if (summary[key] !== undefined) { const card = el('div'); card.append(el('strong', summary[key]), el('span', label)); totals.append(card); shown.add(key); }
      });
      if (totals.children.length) panel.append(totals);
      const groups = [
        ['Hardware routes & physical evidence', ['routes_by_status', 'vendor_decoded_payloads', 'communication_details']],
        ['Declarations & storage', ['registers_total', 'registers_by_declaration_kind', 'registers_by_direction', 'registers_by_member_kind', 'registers_by_datatype', 'datatype_definitions', 'captured_values']],
        ['Logic & references', ['routine_types', 'routine_languages', 'reference_operands_by_status', 'copy_range_instructions_not_expanded', 'instructions_with_unknown_access', 'aoi_calls_not_expanded', 'unresolved_reference_examples', 'unresolved_reference_examples_truncated']],
        ['Export completeness & unresolved records', ['export_attributes', 'source_inventory_coverage', 'representations_total', 'representations_by_format', 'encoded_regions', 'inventory_diagnostics', 'tag_data_coverage', 'gaps', 'unresolved', 'has_tag_data', 'has_instruction_access', 'totals_scope']],
      ];
      function addEntries(target, entries) {
        entries.forEach(([key, value]) => {
          shown.add(key);
          if (typeof value === 'object' && value !== null) target.append(objectDetails(friendly(key), value,
            !['source_inventory_coverage', 'tag_data_coverage', 'export_attributes'].includes(key)));
          else target.append(facts([[friendly(key), value]]));
        });
      }
      groups.forEach(([label, keys]) => {
        const entries = keys.filter(key => summary[key] !== undefined).map(key => [key, summary[key]]); if (!entries.length) return;
        const section = el('details', undefined, 'application-coverage-group'); section.open = true; section.append(el('summary', label));
        if (keys.includes('source_inventory_coverage')) section.append(el('p',
          'Source inventory describes the initial XML capture. Its unmodeled paths can be handled by later tag-data or access analysis; inspect those results separately. Retained unsupported formats still have explicit gaps.', 'muted'));
        addEntries(section, entries); panel.append(section);
      });
      const remaining = Object.entries(summary).filter(([key]) => !shown.has(key));
      if (remaining.length) { const section = el('details', undefined, 'application-coverage-group'); section.append(el('summary', 'Additional captured coverage')); addEntries(section, remaining); panel.append(section); }
      const limits = el('section', undefined, 'application-limitations'); limits.append(el('h3', 'Interpretation and limits'));
      const list = el('ul'); (data.limitations || []).forEach(item => list.append(el('li', typeof item === 'string' ? item : text(item)))); limits.append(list); panel.append(limits); body.append(panel);
    }
    function render() {
      tabButtons.forEach(([id, node]) => node.setAttribute('aria-pressed', String(view.tab === id)));
      registerControls.hidden = view.tab !== 'registers'; filters.hidden = view.tab === 'coverage'; scope.replaceChildren(); body.replaceChildren();
      if (view.module_id) {
        scope.append(el('span', 'Module scope: ' + (data?.selected_module?.name || view.module_id)), button('Show all modules and registers', () => chooseModule('', false)));
      }
      if (!data) return;
      if (!data.available) {
        const panel = el('section', undefined, 'notice');
        panel.append(el('h3', data.reason === 'application_capacity' ? 'Application map display limit' : 'Application evidence unavailable'),
          el('p', data.notice || 'Application evidence is unavailable for this saved analysis.'));
        body.append(panel); return;
      }
      if (view.tab === 'hardware') hardware(); else if (view.tab === 'registers') registers(); else coverage();
      revealSelection = false;
    }
    async function refresh() {
      if (!live) return;
      const expected = identity, expectedRun = runId, request = ++serial;
      if (!expectedRun) { data = null; body.replaceChildren(); notice('Choose an analysis run to inspect its captured application.'); return; }
      const params = {...view, run_id: expectedRun}; delete params.tab;
      notice('Loading captured application evidence…'); root.setAttribute('aria-busy', 'true');
      try {
        const result = await options.api('/api/application?' + new URLSearchParams(params));
        if (request !== serial || !current(expected)) return;
        if (!result || result.run_id !== expectedRun || (result.available && (!validPage(result.modules, view.page_size) || !validPage(result.registers, view.page_size))))
          throw new Error('Application evidence did not match the requested analysis or page bounds. Reload the page.');
        data = result;
        if (result.modules) view.module_page = result.modules.page;
        if (result.registers) view.page = result.registers.page;
        render(); notice(result.available ? `${result.modules.total} configured modules · ${result.registers.total} matching declarations and members. Source data is read only.` : result.notice || 'Application evidence is unavailable.', !result.available);
      } catch (error) {
        if (request !== serial || !current(expected)) return;
        data = null; body.replaceChildren(button('Retry application map', refresh)); notice(error.message || 'Application evidence could not load.', true);
      } finally { if (request === serial && current(expected)) root.removeAttribute('aria-busy'); }
    }
    function update(state = getState()) {
      const reactivated = !live; currentState = state; live = true;
      const next = keyOf(state), changed = next !== identity, newRevision = state.revision ?? -1;
      if (changed) {
        identity = next; runId = state.active_run || ''; data = null; serial++;
        Object.assign(view, {page: 1, module_page: 1, use_page: 1, module_id: '', register_id: ''});
        body.replaceChildren();
      }
      if (reactivated || changed || newRevision !== revision || !data) { revision = newRevision; return refresh(); }
      render(); return Promise.resolve();
    }
    return {update, refresh, wordingChanged: refresh,
      deactivate() { live = false; serial++; root.removeAttribute('aria-busy'); },
      destroy() { live = false; serial++; root.replaceChildren(); }};
  }
  window.PLCApplicationMap = Object.freeze({mount});
})();
