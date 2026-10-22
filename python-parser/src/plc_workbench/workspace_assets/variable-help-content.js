/* Read-only variable evidence. Captured values are neither live nor startup state. */
(() => {
  'use strict';
  const el = (tag, text, className = '') => {
    const node = document.createElement(tag); node.className = className;
    if (text !== undefined) node.textContent = String(text);
    return node;
  };
  const text = (value, fallback = 'Not captured') => typeof value === 'string' && value.trim() ? value : fallback;
  const readable = (value, labels = {}, fallback = 'Unresolved') => Object.hasOwn(labels, value)
    ? labels[value] : text(value, fallback).replaceAll('_', ' ');
  const identifier = value => typeof value === 'string' && value.length > 0 && value.length <= 240 && !/[\x00-\x20\x7f]/.test(value);
  function memberReference(value) {
    if (typeof value !== 'string') return null;
    try {
      const url = new URL(value);
      return url.protocol === 'https:' && ['www.rockwellautomation.com', 'rockwellautomation.com'].includes(url.hostname)
        && !url.username && !url.password && !url.port ? url.href : null;
    } catch { return null; }
  }
  function render(data) {
    const root = el('section', undefined, 'instruction-help-content variable-help-content');
    root.setAttribute('aria-label', 'Variable help');
    root.append(el('h2', text(data.variable, 'Variable')));
    if (data.notice) root.append(el('p', data.notice, 'instruction-help-caveat'));
    const declaration = data.declaration, member = data.member;
    const fields = el('dl', undefined, 'variable-help-fields');
    const field = (name, value) => fields.append(el('dt', name), el('dd', value));
    field('Binding', readable(data.binding?.status, {root_bound: 'Scoped tag found',
      unsupported_address: 'Only part of this address could be resolved', ambiguous: 'More than one matching declaration',
      missing_symbol: 'No matching declaration', alias_cycle: 'Alias references form a cycle'}));
    if (declaration) {
      field('Declared object', text(declaration.path, text(declaration.name)));
      const scope = readable(declaration.scope_kind, {controller: 'Controller-wide / global', program: 'Program', aoi: 'AOI'}, 'Scope unresolved');
      field('Scope', `${scope} · ${text(declaration.scope_path, text(declaration.scope_name, 'Path not captured'))}`);
      field('Declared type', text(declaration.datatype, 'Type unresolved'));
    } else field('Declaration', 'No verified declaration available');
    if (member) {
      field('Member', text(member.path, text(member.name)));
      field('Member type', text(member.datatype, 'Type unresolved'));
      if (member.units) field('Units', member.units);
    }
    root.append(fields);
    root.append(el('h3', 'Meaning'), el('p', text(member?.meaning,
      'No verified member meaning is available. A matching suffix alone does not establish its type or purpose.')));
    if (declaration?.description) root.append(el('p', declaration.description, 'variable-help-description'));
    if (declaration?.description_truncated || declaration?.path_truncated)
      root.append(el('p', 'The declaration description or path is shortened in this preview.', 'instruction-help-caveat'));
    if (member?.type_basis) root.append(el('p', `Type evidence: ${readable(member.type_basis, {
      root_declaration: 'declared tag type', captured_decorated_structure: 'structure type in saved data',
    })}`, 'instruction-help-caveat'));
    const reference = memberReference(member?.reference);
    if (reference) {
      const link = el('a', 'Member reference'); link.href = reference; link.target = '_blank'; link.rel = 'noopener noreferrer'; root.append(link);
    }
    if (data.binding?.alias_chain?.length) root.append(el('p', `Alias chain: ${data.binding.alias_chain.join(' → ')}`, 'instruction-help-caveat'));

    root.append(el('h3', 'Captured values'), el('p',
      'These are values stored in the exported file. They do not establish the live value, startup state, or a value assigned later by logic.', 'instruction-help-caveat'));
    const values = Array.isArray(data.captured_values) ? data.captured_values : [];
    if (!values.length) root.append(el('p', 'No unambiguous stored value is available for this address. Missing data does not mean zero.'));
    values.slice(0, 128).forEach(value => {
      const card = el('section', undefined, 'variable-help-value');
      const envelope = value.envelope === 'DefaultData' ? 'DefaultData · captured default alternative'
        : value.envelope === 'Data' ? 'Data · captured export value' : `${text(value.envelope, 'Unknown envelope')} · captured alternative`;
      card.append(el('strong', envelope), el('p', [value.path, value.datatype, value.format].filter(Boolean).join(' · '), 'instruction-help-caveat'));
      card.append(el('code', value.value_present === true ? String(value.value ?? '') : 'Value not captured'));
      if (value.value_truncated || value.path_truncated)
        card.append(el('p', 'This stored value or path is a shortened preview; it is not the complete captured entry.', 'instruction-help-caveat'));
      if (value.ambiguous) card.append(el('p', 'Ambiguous evidence: this entry is not selected as the effective value.', 'instruction-help-caveat'));
      if (value.status) card.append(el('p', `Evidence status: ${text(value.status, 'Unresolved').replaceAll('_', ' ')}`, 'instruction-help-caveat'));
      root.append(card);
    });
    if (data.captured_values_truncated || values.length > 128 || data.captured_values_total > values.length)
      root.append(el('p', `Showing ${Math.min(values.length, 128)} of ${data.captured_values_total ?? values.length} captured value entries.`, 'instruction-help-caveat'));
    const representations = Array.isArray(data.representations) ? data.representations : [];
    if (representations.length) {
      root.append(el('h3', 'Stored representations'), el('p', 'These formats and defaults remain separate evidence. Listing a representation does not interpret it or select an effective value.', 'instruction-help-caveat'));
      const list = el('ul'); representations.slice(0, 128).forEach(item => list.append(el('li',
        `${text(item.envelope, 'Unknown envelope')} · ${text(item.format, 'Unknown format')} · ${text(item.status, 'Interpretation unresolved').replaceAll('_', ' ')}`)));
      root.append(list);
      if (data.representations_truncated || representations.length > 128 || data.representations_total > representations.length)
        root.append(el('p', `Showing ${Math.min(representations.length, 128)} of ${data.representations_total ?? representations.length} representations.`, 'instruction-help-caveat'));
    }

    root.append(el('h3', 'Where it can be written'), el('p',
      'Captured write sites show possible assignments in this export. They do not establish execution order or which write reaches a read.', 'instruction-help-caveat'));
    const writers = Array.isArray(data.writers) ? data.writers : [];
    if (!writers.length) root.append(el('p', 'No verified write site is listed. This does not prove that the address is never changed.'));
    writers.slice(0, 128).forEach(writer => {
      const card = el('section', undefined, 'variable-help-writer');
      const label = text(writer.path, `Rung ${writer.rung_number ?? '?'} · ${text(writer.opcode, 'Instruction')}`);
      if (identifier(writer.instruction_id) && identifier(data.run_id)) {
        const link = el('a', label), url = new URL('/instruction-help.html', window.location.origin);
        url.searchParams.set('id', writer.instruction_id); url.searchParams.set('run_id', data.run_id);
        url.searchParams.set('theme', document.documentElement.dataset.theme === 'light' ? 'light' : 'dark');
        link.href = url.href; link.target = '_blank'; link.rel = 'noopener'; card.append(link);
      } else card.append(el('strong', label));
      const relation = {exact_address: 'Explicit write to this exact address',
        whole_control: 'Writes the containing structure; this member\'s effect is not established',
        possible_overlap: 'Possible overlapping write; exact member effect unresolved'}[writer.relation]
        || text(writer.relation, 'Relationship unresolved').replaceAll('_', ' ');
      card.append(el('p', `${relation} · ${text(writer.role, 'Role unresolved').replaceAll('_', ' ')}`, 'instruction-help-caveat'));
      if (writer.instruction_text) card.append(el('pre', writer.instruction_text));
      if (writer.instruction_text_truncated || writer.path_truncated)
        card.append(el('p', 'This write-site preview is shortened. Open its saved instruction for the complete captured arguments.', 'instruction-help-caveat'));
      root.append(card);
    });
    if (data.writers_truncated || writers.length > 128 || data.writers_total > writers.length)
      root.append(el('p', `Showing ${Math.min(writers.length, 128)} of ${data.writers_total ?? writers.length} write sites.`, 'instruction-help-caveat'));
    if (Array.isArray(data.limitations) && data.limitations.length) {
      root.append(el('h3', 'Limits of this evidence'));
      const list = el('ul'); data.limitations.slice(0, 128).forEach(item => list.append(el('li', item))); root.append(list);
    }
    return root;
  }
  window.PLCVariableHelpContent = Object.freeze({render});
})();
