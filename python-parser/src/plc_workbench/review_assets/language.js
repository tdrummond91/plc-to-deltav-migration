/* Offline reading overlay. Never rewrites evidence, identifiers or PLC logic. */
(() => {
  'use strict';
  function create(data) {
    let overlay = null;
    try {
      const raw = document.getElementById('review-language-data');
      if (raw) overlay = JSON.parse(raw.textContent);
      if (!overlay || overlay.snapshot_id !== data.snapshot.id || !Array.isArray(overlay.translations)) overlay = null;
    } catch (_) { overlay = null; }
    const rows = new Map((overlay?.translations || []).map(row => [row.original, row]));
    let mode = ['original', 'english', 'both'].includes(overlay?.language) ? overlay.language : 'original';
    const node = (tag, text, cls) => {
      const element = document.createElement(tag);
      if (text !== undefined) element.textContent = text;
      if (cls) element.className = cls;
      return element;
    };
    const english = original => {
      const row = rows.get(original);
      return ['translated', 'needs_review'].includes(row?.status) && typeof row.text === 'string' && row.text.trim() ? row.text : null;
    };
    function prose(original, compact = false) {
      const text = original ?? 'No text captured.';
      if (!overlay || mode === 'original' || !original) return node(compact ? 'div' : 'pre', compact && text.length > 180 ? text.slice(0, 179) + '…' : text, compact ? 'snippet' : 'source-text note');
      const result = node('div', undefined, 'translated-source');
      const translated = english(original);
      const shown = translated || original, row = rows.get(original);
      result.append(node(compact ? 'div' : 'pre', compact && shown.length > 180 ? shown.slice(0, 179) + '…' : shown, compact ? 'snippet' : 'source-text note'));
      result.append(node('div', !translated ? 'Original shown · English unavailable'
        : row.partial === true ? 'English partial · untranslated portions kept in original wording'
        : row.status === 'needs_review' ? 'English wording · review required' : 'English · review wording', 'row-note'));
      if (!translated) return result;
      const source = mode === 'both' ? node('div') : node('details', undefined, 'technical');
      source.append(node(mode === 'both' ? 'strong' : 'summary', 'Original source wording'),
                    node('pre', original, 'source-text note'));
      result.append(source);
      return result;
    }
    function preview(original, fallback = '') {
      if (!original) return fallback;
      if (!overlay || mode === 'original') return original;
      const translated = english(original);
      if (!translated) return original + ' · Original shown; English unavailable';
      const shown = translated + (rows.get(original)?.partial === true ? ' · Partial English; original portions retained' : '');
      return mode === 'both' ? shown + ' · Original: ' + original : shown;
    }
    function mount(target, changed) {
      if (!target || !overlay) return;
      const label = node('label', 'Source wording ', 'filter-wrap');
      const picker = node('select'); picker.setAttribute('aria-label', 'Report source language');
      for (const [value, text] of [['original', 'Original'], ['english', 'English'], ['both', 'Both']]) {
        const option = node('option', text); option.value = value; picker.append(option);
      }
      picker.value = mode;
      picker.addEventListener('change', () => {
        if (!['original', 'english', 'both'].includes(picker.value)) return;
        mode = picker.value; changed();
      });
      label.append(picker); target.append(label);
    }
    return {enabled: Boolean(overlay), prose, preview, english, mount,
            entries: overlay?.entries || [], coverage: overlay?.coverage || {}, limitations: overlay?.limitations || [],
            search: original => [original || '', english(original) || ''].join(' ')};
  }
  window.PLCReviewLanguage = {create};
})();
