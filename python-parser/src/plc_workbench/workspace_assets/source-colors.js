/* Reading colors only: exact spelling is retained, with no inferred dataflow. */
(() => {
  'use strict';
  const WORD_OPERATORS = new Set(['AND', 'OR', 'XOR', 'NOT', 'MOD']);
  const NUMBER = /(?:16#[\da-f_]+|8#[0-7_]+|2#[01_]+|(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)/iy;
  const NAME = /[A-Za-z_][A-Za-z\d_:]*/y;
  const MEMBER = /\.(?:[A-Za-z_][A-Za-z\d_]*|\d+)/y;
  function tokens(value) {
    const text = String(value), result = [];
    let offset = 0;
    const add = (end, kind) => { result.push({text: text.slice(offset, end), kind}); offset = end; };
    while (offset < text.length && result.length < 1024) {
      const char = text[offset];
      if (/\s/.test(char)) {
        let end = offset + 1; while (end < text.length && /\s/.test(text[end])) end++;
        add(end, 'plain'); continue;
      }
      if (char === '"' || char === "'") {
        let end = offset + 1;
        while (end < text.length) {
          if (text[end] === '\\' || text[end] === '$') { end = Math.min(end + 2, text.length); continue; }
          if (text[end++] === char) break;
        }
        add(end, 'literal'); continue;
      }
      NUMBER.lastIndex = NAME.lastIndex = offset;
      const number = NUMBER.exec(text);
      if (number) { add(NUMBER.lastIndex, 'literal'); continue; }
      const name = NAME.exec(text);
      if (name) {
        let end = NAME.lastIndex;
        // Treat member paths and balanced subscripts as one opaque address. This
        // is a label highlighter, not a second expression/address parser.
        while (end < text.length) {
          MEMBER.lastIndex = end;
          if (MEMBER.exec(text)) { end = MEMBER.lastIndex; continue; }
          if (text[end] !== '[') break;
          let depth = 1; end++;
          while (end < text.length && depth) { if (text[end] === '[') depth++; if (text[end] === ']') depth--; end++; }
        }
        const word = text.slice(offset, end), upper = word.toUpperCase();
        add(end, WORD_OPERATORS.has(upper) || /^\s*\(/.test(text.slice(end)) ? 'operator'
          : ['TRUE', 'FALSE'].includes(upper) ? 'literal' : 'variable');
        continue;
      }
      add(offset + 1, /[+\-−×÷*/^%=<>!&|~]/.test(char) ? 'operator' : 'plain');
    }
    // Unusually large labels still keep their entire source without unbounded DOM.
    if (offset < text.length) result.push({text: text.slice(offset), kind: 'plain'});
    return result;
  }
  function create(instructions = []) {
    const colors = new Map();
    const color = value => {
      if (!colors.has(value)) colors.set(value, colors.size % 6);
      return colors.get(value);
    };
    instructions.forEach(inst => (inst.arguments || []).forEach(argument => {
      tokens(argument).forEach(token => { if (token.kind === 'variable') color(token.text); });
    }));
    function paint(element, value, kind) {
      const text = String(value).trim();
      if (!kind) {
        const parts = tokens(text);
        kind = parts.length === 1 ? parts[0].kind : parts.length === 2 && /^[+-]$/.test(parts[0].text)
          && parts[1].kind === 'literal' && /^(?:\d|\.\d)/.test(parts[1].text) ? 'literal' : 'variable';
      }
      const previous = element.getAttribute?.('class') || (typeof element.className === 'string' ? element.className : '');
      const classes = previous.split(/\s+/).filter(name => name && !/^source-(?:token|variable|var-\d|operator|literal|plain)$/.test(name));
      element.setAttribute('class', [...classes, 'source-token', `source-${kind}`, ...(kind === 'variable' ? [`source-var-${color(text)}`] : [])].join(' '));
      if (kind === 'variable') element.setAttribute('data-source-variable', text);
      return element;
    }
    function append(parent, value, options = {}) {
      const text = String(value), shortened = Number.isInteger(options.limit) && options.limit > 0 && text.length > options.limit;
      let remaining = shortened ? options.limit - 1 : text.length;
      for (const token of tokens(text)) {
        if (!remaining) break;
        const child = options.namespace ? document.createElementNS(options.namespace, options.tag || 'tspan') : document.createElement(options.tag || 'span');
        child.textContent = token.text.slice(0, remaining); paint(child, token.text, token.kind);
        parent.append(child); remaining -= child.textContent.length;
      }
      if (shortened) {
        const tail = options.namespace ? document.createElementNS(options.namespace, options.tag || 'tspan') : document.createElement(options.tag || 'span');
        tail.textContent = '…'; paint(tail, '', 'plain'); parent.append(tail);
      }
      return parent;
    }
    return Object.freeze({paint, append});
  }
  window.PLCSourceColors = Object.freeze({create});
})();
