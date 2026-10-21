"""Check local translation controls without changing source or engineering forms."""
from __future__ import annotations

import subprocess
import unittest

from test_workspace_ui import ASSETS, NODE


SCRIPT = (ASSETS / "translation.js").read_text(encoding="utf-8")
DOM = r"""
const assert = require('node:assert/strict');
class Element {
  constructor(tag) {
    this.tagName = tag; this.children = []; this.attributes = {}; this.events = {};
    this.hidden = false; this.checked = false; this.disabled = false;
    this.isConnected = true; this.value = ''; this.className = ''; this._text = '';
  }
  set textContent(value) {this._text = String(value); this.children = [];}
  get textContent() {return this._text + this.children.map(child => child.textContent).join('');}
  append(...children) {children.forEach(child => {child.parent = this; this.children.push(child);});}
  prepend(...children) {children.forEach(child => {child.parent = this;}); this.children.unshift(...children);}
  replaceChildren(...children) {this._text = ''; this.children = []; this.append(...children);}
  setAttribute(key, value) {this.attributes[key] = String(value);}
  addEventListener(name, callback) {this.events[name] = callback;}
  fire(name) {return this.events[name]?.({type: name});}
}
const document = {createElement: tag => new Element(tag)};
const window = {};
const blocked = () => {throw new Error('Translation must use the supplied same-origin API only');};
const fetch = blocked;
window.fetch = blocked; window.XMLHttpRequest = blocked; window.WebSocket = blocked;
Object.defineProperty(window, 'localStorage', {get: blocked});
Object.defineProperty(window, 'sessionStorage', {get: blocked});
let timerId = 0;
const timers = new Map();
const setTimeout = (callback, delay) => {const id = ++timerId; timers.set(id, {callback, delay}); return id;};
const clearTimeout = id => {timers.delete(id);};
const tick = async () => {for (let i = 0; i < 8; i++) await Promise.resolve();};
const nextTimer = async () => {
  assert.equal(timers.size, 1);
  const [id, timer] = timers.entries().next().value;
  assert.equal(timer.delay, 1200);
  timers.delete(id); await timer.callback(); await tick();
};
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => {resolve = yes; reject = no;});
  return {promise, resolve, reject};
};
const all = root => [root, ...root.children.flatMap(all)];
const byClass = (root, cls) => all(root).filter(node => node.className.split(' ').includes(cls));
const container = new Element('section');
const toggle = () => all(container).find(node => node.tagName === 'input');
const retry = () => all(container).find(node => node.tagName === 'button');
const status = () => byClass(container, 'translation-status')[0];
const state = (changes = {}) => ({
  enabled: false, available: true, state: 'idle', run_id: 'invented-run',
  total: 2, completed: 0, cached: 0, needs_review: 0, failed: 0, fields: {}, ...changes,
});
const source = (id = 'rung-one', comment = 'Fermer la vanne', description = 'Pompe de transfert') => ({
  run_id: 'invented-run', historical: false, source: {id, comment, description},
});
const translation = (comment = 'Close the valve', description = 'Transfer pump') => ({
  comment: {status: 'translated', text: comment}, description: {status: 'translated', text: description},
});
const calls = [];
let respond = async () => state();
const api = async (path, body) => {
  calls.push({path, body});
  assert.ok(path === '/api/translation' || path.startsWith('/api/translation?'));
  return respond(path, body);
};
"""


@unittest.skipUnless(NODE, "Node is optional developer tooling")
class WorkspaceTranslationUiTests(unittest.TestCase):
    def run_js(self, checks: str) -> None:
        code = DOM + SCRIPT + "\n(async () => {\n" + checks + "\n})()"
        code += ".then(() => process.stdout.write('TRANSLATION_TEST_COMPLETE\\n'))"
        code += ".catch(error => {console.error(error); process.exitCode = 1;});"
        result = subprocess.run(
            [NODE, "-"], input=code, capture_output=True, encoding="utf-8", timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("TRANSLATION_TEST_COMPLETE", result.stdout)

    def test_original_comment_and_description_remain_visible_and_are_plain_text(self) -> None:
        self.run_js(r"""
const controller = window.PLCTranslation.mount(container, api);
await controller.refresh();
const root = new Element('section');
const data = source('invented id & /?', '<script>fermer la vanne</script>', 'Pompe & moteur');
data.run_id = 'saved run & /?';
controller.show(root, data); await tick();
assert.equal(byClass(root, 'translation-pair').length, 2);
assert.ok(root.textContent.includes('Original comment'));
assert.ok(root.textContent.includes('Original description'));
assert.ok(root.textContent.includes(data.source.comment));
assert.ok(root.textContent.includes(data.source.description));
assert.equal(all(root).some(node => node.tagName === 'script'), false);
assert.ok(byClass(root, 'translation-english').every(node => node.hidden));
assert.equal(toggle().checked, false);
const request = new URL(calls.at(-1).path, 'http://localhost');
assert.equal(request.searchParams.get('source_id'), data.source.id);
assert.equal(request.searchParams.get('run_id'), data.run_id);
assert.equal(calls.at(-1).body, undefined);
assert.ok(calls.every(call => !JSON.stringify(call).includes(data.source.comment)));
assert.equal(timers.size, 0);
""")

    def test_enable_shows_english_alongside_original_without_touching_review_form(self) -> None:
        self.run_js(r"""
const controller = window.PLCTranslation.mount(container, api);
const root = new Element('section');
const outer = new Element('section'); const form = new Element('form');
const input = new Element('input'); input.value = 'Unsaved operator category';
form.append(input); outer.append(root, form);
controller.show(root, source()); await tick();
respond = async () => state({enabled: true, state: 'complete', completed: 2, fields: translation()});
toggle().checked = true; await toggle().fire('change');
const update = calls.find(call => call.body);
assert.deepEqual(update, {path: '/api/translation', body: {enabled: true, run_id: 'invented-run', retry: false}});
assert.ok(root.textContent.includes('Fermer la vanne'));
assert.ok(root.textContent.includes('Pompe de transfert'));
assert.ok(root.textContent.includes('Close the valve'));
assert.ok(root.textContent.includes('Transfer pump'));
assert.ok(byClass(root, 'translation-english').every(node => !node.hidden));
assert.equal(all(root).filter(node => node.lang === 'en').length, 2);
assert.equal(form.children[0], input); assert.equal(input.value, 'Unsaved operator category');
assert.deepEqual(outer.children, [root, form]);
assert.equal(toggle().disabled, false); assert.equal(retry().disabled, false);
respond = async () => state();
toggle().checked = false; await toggle().fire('change');
assert.ok(byClass(root, 'translation-english').every(node => node.hidden));
assert.ok(root.textContent.includes('Fermer la vanne'));
assert.equal(input.value, 'Unsaved operator category');
""")

    def test_late_source_response_cannot_overwrite_new_selection_or_status(self) -> None:
        self.run_js(r"""
const old = deferred(), next = deferred();
respond = path => path.includes('rung-old') ? old.promise : next.promise;
const controller = window.PLCTranslation.mount(container, api);
const oldRoot = new Element('section'), nextRoot = new Element('section');
controller.show(oldRoot, source('rung-old'));
controller.show(nextRoot, source('rung-new'));
next.resolve(state({enabled: true, state: 'complete', completed: 2, fields: translation('New selection')}));
await tick();
const statusText = status().textContent;
old.resolve(state({enabled: true, state: 'running', completed: 0, fields: translation('Stale selection')}));
await tick();
assert.ok(nextRoot.textContent.includes('New selection'));
assert.ok(!nextRoot.textContent.includes('Stale selection'));
assert.ok(!oldRoot.textContent.includes('Stale selection'));
assert.equal(status().textContent, statusText);
assert.equal(timers.size, 0);
""")

    def test_detached_source_does_not_receive_late_translation(self) -> None:
        self.run_js(r"""
const request = deferred(); respond = () => request.promise;
const controller = window.PLCTranslation.mount(container, api);
const root = new Element('section'); controller.show(root, source());
root.isConnected = false;
request.resolve(state({enabled: true, state: 'complete', fields: translation()})); await tick();
assert.ok(!root.textContent.includes('Close the valve'));
respond = async () => state(); await controller.refresh();
assert.equal(calls.at(-1).path, '/api/translation');
""")

    def test_progress_poll_updates_selected_fields_then_stops_at_completion(self) -> None:
        self.run_js(r"""
let step = 0;
respond = async () => ++step === 1
  ? state({enabled: true, state: 'running'})
  : step === 2 ? state({enabled: true, state: 'running', completed: 1, fields: {comment: translation().comment}})
  : state({enabled: true, state: 'complete', completed: 2, cached: 1, fields: translation()});
const controller = window.PLCTranslation.mount(container, api);
const root = new Element('section'); controller.show(root, source()); await tick();
assert.match(status().textContent, /0 \/ 2 unique texts/);
assert.ok(root.textContent.includes('Waiting for this text'));
await nextTimer();
assert.match(status().textContent, /1 \/ 2 unique texts/);
assert.ok(root.textContent.includes('Close the valve'));
assert.ok(root.textContent.includes('Waiting for this text'));
await nextTimer();
assert.match(status().textContent, /2 \/ 2 unique texts/);
assert.ok(status().textContent.includes('1 reused'));
assert.ok(root.textContent.includes('Transfer pump'));
assert.equal(timers.size, 0); assert.equal(calls.length, 3);
""")

    def test_missing_model_explains_local_setup_and_preserves_originals(self) -> None:
        self.run_js(r"""
respond = async () => state({enabled: true, available: false, state: 'unavailable', message: 'Install the local French-to-English model.'});
const controller = window.PLCTranslation.mount(container, api);
const root = new Element('section'); controller.show(root, source()); await tick();
assert.equal(status().textContent, 'Install the local French-to-English model.');
assert.ok(root.textContent.includes('Fermer la vanne'));
assert.ok(root.textContent.includes('Install the local French-to-English model.'));
assert.ok(container.textContent.includes('bash ./setup-translation.sh'));
assert.ok(container.textContent.includes('bash ./open-workbench.sh'));
assert.ok(container.textContent.includes('downloads the translation software'));
assert.ok(container.textContent.includes('without an internet connection after setup'));
assert.equal(timers.size, 0); assert.equal(toggle().disabled, false);
""")

    def test_failed_enable_restores_toggle_and_reenables_controls_for_retry(self) -> None:
        self.run_js(r"""
const controller = window.PLCTranslation.mount(container, api); await controller.refresh();
const request = deferred(); respond = () => request.promise;
toggle().checked = true; const change = toggle().fire('change');
assert.equal(toggle().disabled, true); assert.equal(retry().disabled, true);
request.reject(new Error('Local service temporarily unavailable')); await change;
assert.equal(toggle().checked, false);
assert.equal(toggle().disabled, false); assert.equal(retry().disabled, false);
assert.ok(status().textContent.includes('Local service temporarily unavailable'));
respond = async () => state({enabled: true, state: 'complete', completed: 2});
toggle().checked = true; await toggle().fire('change');
assert.equal(toggle().checked, true); assert.equal(toggle().disabled, false);
assert.equal(timers.size, 0);
""")

    def test_retry_requests_only_missing_translations_for_current_run(self) -> None:
        self.run_js(r"""
respond = async () => state({enabled: true, state: 'complete', needs_review: 1, failed: 1});
const controller = window.PLCTranslation.mount(container, api); await controller.refresh();
assert.equal(retry().hidden, false);
respond = async () => state({enabled: true, state: 'running'});
await retry().fire('click');
const update = calls.find(call => call.body);
assert.deepEqual(update.body, {enabled: true, run_id: 'invented-run', retry: true});
assert.equal(retry().hidden, true); assert.equal(retry().disabled, false);
assert.equal(timers.size, 1);
controller.destroy(); assert.equal(timers.size, 0);
""")

    def test_engine_start_failure_allows_retry_but_missing_runtime_requires_setup(self) -> None:
        self.run_js(r"""
respond = async () => state({enabled: true, available: true, state: 'error', failed: 0,
  message: 'The local translation engine could not start.'});
const controller = window.PLCTranslation.mount(container, api); await controller.refresh();
assert.equal(retry().hidden, false);
assert.ok(status().textContent.includes('could not start'));
respond = async () => state({enabled: true, state: 'running'});
await retry().fire('click');
assert.deepEqual(calls.find(call => call.body).body,
  {enabled: true, run_id: 'invented-run', retry: true});
assert.equal(retry().hidden, true);
respond = async () => state({enabled: true, available: false, state: 'error', failed: 0,
  message: 'Install the local translation runtime.'});
await controller.refresh();
assert.equal(retry().hidden, true);
assert.ok(status().textContent.includes('Install the local translation runtime.'));
assert.ok(container.textContent.includes('bash ./setup-translation.sh'));
assert.equal(timers.size, 0);
""")

    def test_refresh_error_stops_poll_and_keeps_original_and_recovery_available(self) -> None:
        self.run_js(r"""
respond = async () => state({enabled: true, state: 'running'});
const controller = window.PLCTranslation.mount(container, api);
const root = new Element('section'); controller.show(root, source()); await tick();
respond = async () => {throw new Error('Local connection closed');};
await nextTimer();
assert.equal(timers.size, 0);
assert.ok(status().textContent.includes('Translation unavailable. Local connection closed'));
assert.ok(root.textContent.includes('Fermer la vanne'));
assert.equal(toggle().disabled, false);
respond = async () => state({enabled: true, state: 'complete', completed: 2, fields: translation()});
await controller.refresh();
assert.ok(root.textContent.includes('Close the valve'));
""")

    def test_historical_missing_translation_and_review_warnings_are_explicit(self) -> None:
        self.run_js(r"""
respond = async () => state({enabled: true, state: 'complete', needs_review: 1,
  fields: {description: {status: 'needs_review', warning: 'Unrecognized abbreviation; compare the original.'}}});
const controller = window.PLCTranslation.mount(container, api);
const root = new Element('section'); const data = source(); data.historical = true; data.run_id = 'earlier-run';
controller.show(root, data); await tick();
assert.ok(root.textContent.includes('No saved English version for this earlier source'));
assert.ok(root.textContent.includes('Unrecognized abbreviation; compare the original.'));
assert.ok(root.textContent.includes('Pompe de transfert'));
assert.ok(calls.at(-1).path.includes('run_id=earlier-run'));
assert.equal(retry().hidden, true);
""")

    def test_destroy_discards_pending_read_response_and_poll(self) -> None:
        self.run_js(r"""
const request = deferred(); respond = () => request.promise;
const controller = window.PLCTranslation.mount(container, api);
const root = new Element('section'); controller.show(root, source());
const oldStatus = status().textContent; controller.destroy();
request.resolve(state({enabled: true, state: 'running', fields: translation()})); await tick();
assert.equal(status().textContent, oldStatus);
assert.ok(!root.textContent.includes('Close the valve'));
assert.equal(timers.size, 0);
""")

    def test_destroy_discards_pending_enable_response_without_an_extra_request(self) -> None:
        self.run_js(r"""
const controller = window.PLCTranslation.mount(container, api); await controller.refresh();
const request = deferred(); respond = () => request.promise;
toggle().checked = true; const change = toggle().fire('change');
const count = calls.length, oldStatus = status().textContent;
controller.destroy();
request.resolve(state({enabled: true, state: 'running'})); await change;
assert.equal(calls.length, count);
assert.equal(status().textContent, oldStatus);
assert.equal(timers.size, 0);
""")


if __name__ == "__main__":
    unittest.main()
