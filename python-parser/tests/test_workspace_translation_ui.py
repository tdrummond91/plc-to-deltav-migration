"""Exercise whole-import English controls and safe local prose presentation."""
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
    this.hidden = false; this.disabled = false; this.open = false;
    this.isConnected = true; this.value = ''; this.className = ''; this._text = '';
  }
  set textContent(value) {this._text = String(value); this.children = [];}
  get textContent() {return this._text + this.children.map(child => child.textContent).join('');}
  append(...children) {children.forEach(child => {child.parent = this; this.children.push(child);});}
  replaceChildren(...children) {this._text = ''; this.children = []; this.append(...children);}
  setAttribute(key, value) {this.attributes[key] = String(value);}
  addEventListener(name, callback) {this.events[name] = callback;}
  fire(name) {return this.events[name]?.({type: name});}
}
const document = {createElement: tag => new Element(tag), createElementNS: (_ns, tag) => new Element(tag)};
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
const nextTimer = async (expectedDelay = 1200) => {
  assert.equal(timers.size, 1);
  const [id, timer] = timers.entries().next().value;
  assert.equal(timer.delay, expectedDelay);
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
const control = cls => byClass(container, cls)[0];
const language = (value, root = container) => byClass(root, value === 'both' ? 'translation-both' : 'translation-choice-' + value)[0];
const chooseMode = value => language(value).fire('click');
const mode = () => ({
  value: ['original', 'english', 'both'].find(value => language(value).attributes['aria-pressed'] === 'true'),
  disabled: ['original', 'english', 'both'].every(value => language(value).disabled),
});
const prepare = () => control('translation-prepare');
const retry = () => control('translation-retry');
const status = () => control('translation-status');
const report = () => control('translation-report');
const state = (changes = {}) => ({
  presentation_mode: 'original', enabled: false, available: true, state: 'idle',
  run_id: 'invented-run', total: 2, completed: 0, cached: 0, needs_review: 0, failed: 0,
  fields: {}, write_generation: 0, elapsed_seconds: 0, remaining_seconds: null, ...changes,
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

    def test_header_and_project_controls_share_pending_requests_and_saved_mode(self) -> None:
        self.run_js(r"""
const shortcuts = new Element('div');
const controller = window.PLCTranslation.mount(container, api, () => {}, shortcuts);
await controller.refresh();
assert.equal(calls.length, 1);
assert.equal(language('original', shortcuts).attributes['aria-pressed'], 'true');
const pending = deferred();
respond = (_path, body) => body ? pending.promise : state({presentation_mode: 'english'});
const change = language('english', shortcuts).fire('click');
assert.ok(['original','english'].every(value => language(value, shortcuts).disabled));
assert.equal(mode().disabled, true);
await chooseMode('original');
assert.equal(calls.filter(call => call.body).length, 1);
pending.resolve(state({presentation_mode: 'english'})); await change;
assert.equal(mode().value, 'english');
assert.equal(language('english', shortcuts).attributes['aria-pressed'], 'true');
assert.equal(language('original', shortcuts).attributes['aria-pressed'], 'false');
assert.equal(language('english', shortcuts).disabled, false);
respond = async () => state({presentation_mode: 'both'});
await chooseMode('both');
assert.equal(mode().value, 'both');
assert.ok(['original','english'].every(value => language(value, shortcuts).attributes['aria-pressed'] === 'true'));
respond = async () => state({presentation_mode: 'original'});
await language('original', shortcuts).fire('click');
assert.equal(mode().value, 'original');
assert.equal(language('english', shortcuts).attributes['aria-pressed'], 'false');
assert.equal(report().href, '/analysis?language=original');
assert.equal(timers.size, 0);
""")

    def test_original_comment_and_description_remain_plain_text(self) -> None:
        self.run_js(r"""
const controller = window.PLCTranslation.mount(container, api);
await controller.refresh();
const root = new Element('section');
const data = source('invented id & /?', '<script>fermer la vanne</script>', 'Pompe & moteur');
data.run_id = 'saved run & /?';
controller.show(root, data); await tick();
assert.equal(byClass(root, 'translation-pair').length, 2);
assert.ok(root.textContent.includes('Source comment'));
assert.ok(root.textContent.includes('Source description'));
assert.ok(root.textContent.includes(data.source.comment));
assert.ok(root.textContent.includes(data.source.description));
assert.equal(all(root).some(node => node.tagName === 'script'), false);
assert.equal(byClass(root, 'translation-english').length, 0);
assert.equal(mode().value, 'original');
const request = new URL(calls.at(-1).path, 'http://localhost');
assert.equal(request.searchParams.get('source_id'), data.source.id);
assert.equal(request.searchParams.get('run_id'), data.run_id);
assert.equal(calls.at(-1).body, undefined);
assert.ok(calls.every(call => !JSON.stringify(call).includes(data.source.comment)));
assert.equal(timers.size, 0);
""")

    def test_english_mode_hides_original_in_disclosure_and_preserves_unsaved_form(self) -> None:
        self.run_js(r"""
const changes = [];
const controller = window.PLCTranslation.mount(container, api, value => changes.push(value));
const root = new Element('section'), outer = new Element('section'), form = new Element('form');
const input = new Element('input'); input.value = 'Unsaved operator category';
form.append(input); outer.append(root, form);
controller.show(root, source()); await tick();
respond = async () => state({presentation_mode: 'english', enabled: true, state: 'complete', completed: 2, fields: translation()});
await chooseMode('english');
assert.deepEqual(calls.find(call => call.body).body,
  {presentation_mode: 'english', prepare: true, run_id: 'invented-run', retry: false});
assert.equal(byClass(root, 'translation-original-disclosure').length, 2);
assert.ok(byClass(root, 'translation-original-disclosure').every(node => !node.open));
assert.ok(byClass(root, 'translation-original-disclosure')[0].textContent.includes('Fermer la vanne'));
assert.ok(root.textContent.includes('Close the valve'));
assert.equal(all(root).filter(node => node.lang === 'en').length, 2);
assert.equal(form.children[0], input); assert.equal(input.value, 'Unsaved operator category');
assert.deepEqual(outer.children, [root, form]);
assert.equal(mode().disabled, false);
assert.equal(report().href, '/analysis?language=english');
assert.equal(changes.length, 1);
respond = async () => state({presentation_mode: 'both', enabled: true, state: 'complete', completed: 2, fields: translation()});
await chooseMode('both');
assert.equal(byClass(root, 'translation-original-disclosure').length, 0);
assert.equal(byClass(root, 'translation-original-block').length, 2);
assert.ok(root.textContent.includes('Fermer la vanne')); assert.ok(root.textContent.includes('Close the valve'));
assert.equal(report().href, '/analysis?language=both');
assert.equal(input.value, 'Unsaved operator category');
""")

    def test_switching_to_original_does_not_cancel_preparation_or_polling(self) -> None:
        self.run_js(r"""
respond = async () => state({presentation_mode: 'english', enabled: true, state: 'running'});
const controller = window.PLCTranslation.mount(container, api);
const root = new Element('section'); controller.show(root, source()); await tick();
respond = async () => state({presentation_mode: 'original', enabled: true, state: 'running', completed: 1});
await chooseMode('original');
assert.deepEqual(calls.find(call => call.body).body,
  {presentation_mode: 'original', prepare: false, run_id: 'invented-run', retry: false});
assert.equal(byClass(root, 'translation-english').length, 0);
assert.ok(root.textContent.includes('Fermer la vanne'));
assert.equal(timers.size, 1);
assert.ok(status().textContent.includes('Preparing English locally'));
assert.equal(report().href, '/analysis?language=original');
controller.destroy();
""")

    def test_both_language_toggle_returns_to_english_and_french_restores_source(self) -> None:
        self.run_js(r"""
let selected = 'both';
respond = async (_path, body) => {
  if (body) selected = body.presentation_mode;
  return state({presentation_mode: selected, enabled: true, state: 'running', fields: translation()});
};
const controller = window.PLCTranslation.mount(container, api);
const root = new Element('section'); controller.show(root, source()); await tick();
assert.equal(mode().value, 'both');
assert.equal(byClass(root, 'translation-original-block').length, 2);
await chooseMode('both');
assert.equal(controller.mode(), 'english');
assert.equal(byClass(root, 'translation-original-disclosure').length, 2);
await chooseMode('both');
assert.equal(controller.mode(), 'both');
await chooseMode('original');
assert.equal(controller.mode(), 'original');
assert.equal(byClass(root, 'translation-english').length, 0);
assert.ok(root.textContent.includes('Fermer la vanne'));
assert.equal(calls.filter(call => call.body).at(-1).body.prepare, false);
assert.equal(timers.size, 1);
assert.equal(report().textContent, 'Open French analysis report');
controller.destroy();
""")

    def test_prepare_all_can_run_while_view_remains_original(self) -> None:
        self.run_js(r"""
const controller = window.PLCTranslation.mount(container, api); await controller.refresh();
assert.equal(prepare().disabled, false);
respond = async () => state({enabled: true, state: 'running'});
await prepare().fire('click');
assert.deepEqual(calls.find(call => call.body).body,
  {presentation_mode: 'original', prepare: true, run_id: 'invented-run', retry: false});
assert.equal(mode().value, 'original'); assert.equal(prepare().disabled, true);
assert.equal(timers.size, 1);
assert.ok(container.textContent.includes('No full parser rerun is needed'));
assert.ok(container.textContent.includes('several minutes'));
controller.destroy();
""")

    def test_progress_reports_time_pending_gaps_and_cache_generations(self) -> None:
        self.run_js(r"""
let step = 0; const changes = [];
respond = async () => ++step === 1
  ? state({presentation_mode: 'english', enabled: true, state: 'running', elapsed_seconds: 65})
  : step === 2 ? state({presentation_mode: 'english', enabled: true, state: 'running', completed: 1,
      elapsed_seconds: 70, remaining_seconds: 80, write_generation: 1, fields: {comment: translation().comment}})
  : state({presentation_mode: 'english', enabled: true, state: 'complete', completed: 2, cached: 1,
      elapsed_seconds: 140, write_generation: 2, fields: translation()});
const controller = window.PLCTranslation.mount(container, api, value => changes.push(value));
const root = new Element('section'); controller.show(root, source()); await tick();
assert.match(status().textContent, /0 \/ 2 unique texts/);
assert.ok(status().textContent.includes('2 pending'));
assert.ok(status().textContent.includes('elapsed 1m 5s'));
assert.ok(status().textContent.includes('estimating remaining time'));
assert.ok(byClass(root,'translation-caption').some(note=>note.title.includes('This wording is queued while the whole source is prepared')));
assert.ok(report().textContent.includes('gaps marked'));
await nextTimer();
assert.ok(status().textContent.includes('about 1m 20s remaining'));
assert.ok(root.textContent.includes('Close the valve'));
await nextTimer();
assert.ok(status().textContent.includes('1 reused'));
assert.ok(root.textContent.includes('Transfer pump'));
assert.equal(timers.size, 0); assert.equal(changes.length, 2);
assert.equal(report().textContent, 'Open English analysis report');
await controller.refresh();
assert.equal(changes.length, 2);
""")

    def test_partial_and_review_required_wording_stays_visible_with_original_available(self) -> None:
        self.run_js(r"""
const root = new Element('section');
window.PLCTranslation.renderProse(root, 'Ne pas ouvrir', {status: 'needs_review', text: 'Ne pas ouvrir', warning: 'Compare uncertain wording.'}, 'english');
assert.ok(byClass(root, 'translation-caption')[0].textContent.includes('review required'));
assert.equal(byClass(root, 'translation-caption')[0].title, 'Compare uncertain wording.');
assert.ok(byClass(root, 'translation-english')[0].textContent.includes('Ne pas ouvrir'));
const original = byClass(root, 'translation-original-disclosure')[0];
assert.equal(original.open, false); assert.ok(original.textContent.includes('Ne pas ouvrir'));
window.PLCTranslation.renderProse(root, 'Pompe en marche\nNe pas ouvrir',
  {status:'needs_review',text:'Pump running\nNe pas ouvrir',partial:true,failed:false}, 'english');
assert.equal(byClass(root, 'source-comment')[0].textContent,'Pump running\nNe pas ouvrir');
assert.ok(byClass(root, 'translation-caption')[0].textContent.includes('English partial'));
assert.equal(all(root).some(node=>node.lang==='en'),false);
assert.ok(byClass(root,'translation-original-disclosure')[0].textContent.includes('Pompe en marche'));
window.PLCTranslation.renderProse(root, '<img src=x onerror=alert(1)>', {status: 'translated', text: '<script>alert(1)</script>'}, 'english');
assert.equal(all(root).some(node => ['img','script'].includes(node.tagName)), false);
assert.ok(root.textContent.includes('<script>alert(1)</script>'));
""")

    def test_unavailable_english_keeps_original_visible_without_extra_disclosure(self) -> None:
        self.run_js(r"""
const root=new Element('section');
for(const mode of ['english','both']) for(const entry of [null,{status:'needs_review',text:'',failed:true},{status:'needs_review',text:'Do not show this failed candidate',failed:true}]) {
  window.PLCTranslation.renderProse(root,'Original multiline\ncomment',entry,mode);
  assert.equal(byClass(root,'source-comment')[0].textContent,'Original multiline\ncomment');
  assert.equal(byClass(root,'source-comment').length,1);
  assert.equal(byClass(root,'translation-original-disclosure').length,0);
  assert.ok(byClass(root,'translation-caption')[0].textContent.includes('Original shown'));
}
""")

    def test_saved_incomplete_results_are_not_presented_as_pending_or_restarted(self) -> None:
        self.run_js(r"""
respond=async()=>state({enabled:true,presentation_mode:'english',state:'complete',total:6701,completed:6701,
  cached:6701,partial:678,failed:1,interrupted:1,unchanged:1,cached_incomplete:679,needs_review:679,new_texts:0,retry_texts:0});
const controller=window.PLCTranslation.mount(container,api); await controller.refresh();
assert.ok(status().textContent.includes('6701 reused from before this pass'));
assert.ok(status().textContent.includes('678 partial'));
assert.ok(status().textContent.includes('1 interrupted'));
assert.ok(status().textContent.includes('nothing will retry automatically'));
assert.ok(!status().textContent.includes('pending'));
assert.equal(retry().hidden,false); assert.equal(retry().textContent,'Retry incomplete translations');
assert.equal(timers.size,0); assert.ok(calls.every(call=>!call.body));
await controller.refresh(); assert.ok(calls.every(call=>!call.body));
""")

    def test_interrupted_attempt_and_unchanged_wording_have_explicit_saved_labels(self) -> None:
        self.run_js(r"""
const root=new Element('section');
window.PLCTranslation.renderProse(root,'Pompe en marche',{status:'needs_review',text:'Pompe en marche',failed:true,interrupted:true},'english');
assert.ok(root.textContent.includes('translation interrupted, retry manually'));
assert.equal(byClass(root,'source-comment')[0].textContent,'Pompe en marche');
window.PLCTranslation.renderProse(root,'Pompe\nPression',{status:'needs_review',text:'Pump\nPression',failed:false,partial:true,interrupted:true},'english');
assert.ok(root.textContent.includes('Saved wording · retry interrupted'));
assert.equal(byClass(root,'source-comment')[0].textContent,'Pump\nPression');
window.PLCTranslation.renderProse(root,'Pump running',{status:'translated',text:'Pump running',failed:false,unchanged:true},'english');
assert.ok(root.textContent.includes('Wording unchanged · saved locally'));
window.PLCTranslation.renderProse(root,'Pompe\nPression',{status:'needs_review',text:'Pump\nPression',failed:false,partial:true,last_attempt_failed:true},'english');
assert.ok(root.textContent.includes('Saved wording · latest retry failed'));
assert.equal(byClass(root,'source-comment')[0].textContent,'Pump\nPression');
""")

    def test_interrupted_generation_refreshes_views_and_failed_retry_stays_explicit(self) -> None:
        self.run_js(r"""
let generation=2;const changes=[];
respond=async()=>state({enabled:true,presentation_mode:'english',state:'complete',completed:2,write_generation:generation,retry_failed:1});
const controller=window.PLCTranslation.mount(container,api,value=>changes.push(value));await controller.refresh();
assert.ok(status().textContent.includes('retries failed; saved wording retained'));assert.equal(retry().hidden,false);
generation++;await controller.refresh();assert.equal(changes.length,1);
generation++;await controller.refresh();assert.equal(changes.length,2);
assert.equal(timers.size,0);
""")

    def test_completed_batch_missing_wording_does_not_claim_it_is_still_queued(self) -> None:
        self.run_js(r"""
respond = async () => state({presentation_mode: 'english', enabled: true, state: 'complete', completed: 2});
const controller = window.PLCTranslation.mount(container, api);
const root = new Element('section'); controller.show(root, source()); await tick();
assert.ok(root.textContent.includes('Original shown · English not ready'));
assert.ok(!root.textContent.includes('queued'));
assert.ok(!root.textContent.includes('background'));
assert.equal(timers.size, 0);
""")

    def test_original_disclosure_stays_open_during_unrelated_batch_updates(self) -> None:
        self.run_js(r"""
let generation = 1;
respond = async () => state({presentation_mode: 'english', enabled: true, state: 'running',
  fields: translation(), write_generation: generation++});
const controller = window.PLCTranslation.mount(container, api);
const root = new Element('section'); controller.show(root, source()); await tick();
const original = byClass(root, 'translation-original-disclosure')[0]; original.open = true;
await nextTimer();
assert.equal(byClass(root, 'translation-original-disclosure')[0], original);
assert.equal(original.open, true); controller.destroy();
""")

    def test_late_source_response_cannot_overwrite_new_selection(self) -> None:
        self.run_js(r"""
const old = deferred(), next = deferred();
respond = path => path.includes('rung-old') ? old.promise : next.promise;
const controller = window.PLCTranslation.mount(container, api);
const oldRoot = new Element('section'), nextRoot = new Element('section');
controller.show(oldRoot, source('rung-old')); controller.show(nextRoot, source('rung-new'));
next.resolve(state({presentation_mode: 'english', enabled: true, state: 'complete', completed: 2, fields: translation('New selection')}));
await tick(); const statusText = status().textContent;
old.resolve(state({presentation_mode: 'both', enabled: true, state: 'running', fields: translation('Stale selection')}));
await tick();
assert.ok(nextRoot.textContent.includes('New selection'));
assert.ok(!nextRoot.textContent.includes('Stale selection'));
assert.ok(!oldRoot.textContent.includes('Stale selection'));
assert.equal(status().textContent, statusText); assert.equal(mode().value, 'english');
assert.equal(timers.size, 0);
""")

    def test_detached_source_does_not_receive_late_translation(self) -> None:
        self.run_js(r"""
const request = deferred(); respond = () => request.promise;
const controller = window.PLCTranslation.mount(container, api);
const root = new Element('section'); controller.show(root, source());
root.isConnected = false;
request.resolve(state({presentation_mode: 'english', enabled: true, state: 'complete', fields: translation()})); await tick();
assert.ok(!root.textContent.includes('Close the valve'));
respond = async () => state(); await controller.refresh();
assert.equal(calls.at(-1).path, '/api/translation');
""")

    def test_missing_model_explains_setup_and_original_remains_accessible(self) -> None:
        self.run_js(r"""
respond = async () => state({presentation_mode: 'english', enabled: true, available: false, state: 'unavailable',
  message: 'Install the local French-to-English model.'});
const controller = window.PLCTranslation.mount(container, api);
const root = new Element('section'); controller.show(root, source()); await tick();
assert.equal(status().textContent, 'Install the local French-to-English model.');
assert.ok(byClass(root,'translation-caption').some(note=>note.title.includes('Install the local French-to-English model.')));
assert.ok(byClass(root, 'translation-original')[0].textContent.includes('Fermer la vanne'));
assert.ok(container.textContent.includes('bash ./setup-translation.sh'));
assert.ok(container.textContent.includes('without an internet connection after setup'));
assert.equal(prepare().disabled, true); assert.equal(mode().disabled, false);
assert.equal(timers.size, 0);
""")

    def test_failed_mode_change_restores_mode_without_losing_error_message(self) -> None:
        self.run_js(r"""
const controller = window.PLCTranslation.mount(container, api); await controller.refresh();
const request = deferred(); respond = () => request.promise;
const change = chooseMode('english');
assert.equal(mode().disabled, true); assert.equal(prepare().disabled, true);
request.reject(new Error('Local service temporarily unavailable')); await change;
assert.equal(mode().value, 'original'); assert.equal(mode().disabled, false);
assert.equal(prepare().disabled, false);
assert.ok(status().textContent.includes('Local service temporarily unavailable'));
respond = async () => state({presentation_mode: 'english', enabled: true, state: 'complete', completed: 2});
await chooseMode('english');
assert.equal(mode().value, 'english');
""")

    def test_retry_requests_missing_items_without_forcing_a_language_switch(self) -> None:
        self.run_js(r"""
respond = async () => state({enabled: true, state: 'complete', needs_review: 1, failed: 1});
const controller = window.PLCTranslation.mount(container, api); await controller.refresh();
assert.equal(retry().hidden, false);
respond = async () => state({enabled: true, state: 'running'});
await retry().fire('click');
assert.deepEqual(calls.find(call => call.body).body,
  {presentation_mode: 'original', prepare: true, run_id: 'invented-run', retry: true});
assert.equal(retry().hidden, true); assert.equal(timers.size, 1);
controller.destroy(); assert.equal(timers.size, 0);
""")

    def test_partial_wording_is_counted_and_can_be_retried(self) -> None:
        self.run_js(r"""
respond=async()=>state({enabled:true,presentation_mode:'english',state:'complete',completed:2,partial:1,needs_review:1,failed:0});
const controller=window.PLCTranslation.mount(container,api);await controller.refresh();
assert.equal(retry().hidden,false);assert.ok(status().textContent.includes('1 partial'));
respond=async()=>state({enabled:true,presentation_mode:'english',state:'running'});
await retry().fire('click');
assert.deepEqual(calls.find(call=>call.body).body,{presentation_mode:'english',prepare:true,run_id:'invented-run',retry:true});
controller.destroy();
""")

    def test_failed_configuration_rereads_applied_mode_and_resumes_running_poll(self) -> None:
        self.run_js(r"""
respond = async () => state({presentation_mode: 'english', enabled: true, state: 'running'});
const controller = window.PLCTranslation.mount(container, api);
const root = new Element('section'); controller.show(root, source()); await tick();
const start = calls.length;
respond = async (path, body) => {
  if (body) throw new Error('Response lost after preference was applied');
  return state({presentation_mode: 'original', enabled: true, state: 'running', completed: 1});
};
await chooseMode('original');
assert.equal(calls.slice(start).filter(call => call.body).length, 1);
assert.equal(calls.slice(start).filter(call => call.body === undefined).length, 1);
assert.equal(mode().value, 'original');
assert.equal(byClass(root, 'translation-english').length, 0);
assert.equal(timers.size, 1); assert.equal(prepare().disabled, true);
await nextTimer();
assert.equal(calls.slice(start).filter(call => call.body).length, 1);
assert.ok(status().textContent.includes('Preparing English locally'));
controller.destroy();
""")

    def test_failed_configuration_and_status_recover_without_repeating_post(self) -> None:
        self.run_js(r"""
respond = async () => state({presentation_mode: 'english', enabled: true, state: 'running',
  completed: 1, fields: {comment: translation().comment}});
const controller = window.PLCTranslation.mount(container, api);
const root = new Element('section'); controller.show(root, source()); await tick();
const start = calls.length;
respond = async () => {throw new Error('Server disconnected');};
await chooseMode('both');
assert.equal(calls.slice(start).filter(call => call.body).length, 1);
assert.equal(mode().value, 'english');
assert.ok(root.textContent.includes('Close the valve'));
assert.ok(byClass(root,'translation-caption').some(note=>note.title.includes('Live translation status is interrupted')));
assert.equal(timers.size, 1); assert.equal(control('translation-retry-status').hidden, false);
respond = async () => state({presentation_mode: 'english', enabled: true, state: 'complete', completed: 2, fields: translation()});
await nextTimer(5000);
assert.equal(calls.slice(start).filter(call => call.body).length, 1);
assert.equal(timers.size, 0); assert.equal(prepare().disabled, false);
assert.ok(root.textContent.includes('Transfer pump'));
""")

    def test_engine_error_allows_retry_but_missing_runtime_requires_setup(self) -> None:
        self.run_js(r"""
respond = async () => state({enabled: true, state: 'error', message: 'The local translation engine could not start.'});
const controller = window.PLCTranslation.mount(container, api); await controller.refresh();
assert.equal(retry().hidden, false);
assert.ok(status().textContent.includes('could not start'));
respond = async () => state({enabled: true, available: false, state: 'error', message: 'Install the local translation runtime.'});
await controller.refresh(); assert.equal(retry().hidden, true);
assert.ok(status().textContent.includes('Install the local translation runtime.'));
assert.equal(timers.size, 0);
""")

    def test_refresh_failure_marks_pending_wording_interrupted_then_recovers(self) -> None:
        self.run_js(r"""
respond = async () => state({presentation_mode: 'english', enabled: true, state: 'running'});
const controller = window.PLCTranslation.mount(container, api);
const root = new Element('section'); controller.show(root, source()); await tick();
respond = async () => {throw new Error('Local connection closed');};
await nextTimer();
assert.equal(timers.size, 1);
assert.ok(status().textContent.includes('Translation status connection interrupted. Local connection closed'));
assert.ok(status().textContent.includes('Retrying status in 5 seconds'));
assert.ok(byClass(root,'translation-caption').some(note=>note.title.includes('Live translation status is interrupted')));
assert.ok(!root.textContent.includes('This wording is queued'));
assert.ok(root.textContent.includes('Fermer la vanne'));
respond = async () => state({presentation_mode: 'english', enabled: true, state: 'complete', completed: 2, fields: translation()});
await nextTimer(5000); assert.ok(root.textContent.includes('Close the valve'));
assert.equal(timers.size, 0); assert.equal(control('translation-retry-status').hidden, true);
""")

    def test_recovery_is_bounded_preserves_completed_wording_and_offers_read_only_retry(self) -> None:
        self.run_js(r"""
respond = async () => state({presentation_mode: 'english', enabled: true, state: 'running',
  completed: 1, fields: {comment: translation().comment}});
const controller = window.PLCTranslation.mount(container, api);
const root = new Element('section'); controller.show(root, source()); await tick();
const english = byClass(root, 'translation-english')[0];
const original = byClass(root, 'translation-original-disclosure')[0]; original.open = true;
respond = async () => {throw new Error('Server disconnected');};
await nextTimer();
assert.equal(byClass(root, 'translation-english')[0], english);
assert.ok(english.textContent.includes('Close the valve')); assert.equal(original.open, true);
assert.ok(byClass(root, 'translation-english')[1].children.some(note=>note.title?.includes('status is interrupted')));
await nextTimer(5000); await nextTimer(5000); await nextTimer(5000);
assert.equal(timers.size, 0);
assert.ok(status().textContent.includes('Use Retry status to reconnect'));
assert.equal(control('translation-retry-status').hidden, false);
respond = async () => state({presentation_mode: 'english', enabled: true, state: 'complete', completed: 2, fields: translation()});
await control('translation-retry-status').fire('click');
assert.equal(control('translation-retry-status').hidden, true);
assert.ok(root.textContent.includes('Transfer pump'));
assert.ok(!root.textContent.includes('status is interrupted'));
assert.ok(calls.every(call => call.body === undefined)); assert.equal(timers.size, 0);
""")

    def test_detached_translation_controls_stop_recovery_requests(self) -> None:
        self.run_js(r"""
respond = async () => state({presentation_mode: 'english', enabled: true, state: 'running'});
const controller = window.PLCTranslation.mount(container, api);
const root = new Element('section'); controller.show(root, source()); await tick();
respond = async () => {throw new Error('Server disconnected');};
await nextTimer();
const count = calls.length; container.isConnected = false;
await nextTimer(5000);
assert.equal(calls.length, count); assert.equal(timers.size, 0);
await controller.refresh(); assert.equal(calls.length, count);
""")

    def test_destroy_cancels_delayed_recovery_and_retains_review_warning(self) -> None:
        self.run_js(r"""
respond = async () => state({presentation_mode: 'english', enabled: true, state: 'running',
  fields: {comment: {status: 'needs_review', warning: 'Check this abbreviation.'}}});
const controller = window.PLCTranslation.mount(container, api);
const root = new Element('section'); controller.show(root, source()); await tick();
respond = async () => {throw new Error('Server disconnected');}; await nextTimer();
assert.ok(byClass(root,'translation-caption').some(note=>note.title.includes('Check this abbreviation.')));
assert.equal(timers.size, 1); controller.destroy(); assert.equal(timers.size, 0);
""")

    def test_historical_missing_translation_and_warning_are_explicit(self) -> None:
        self.run_js(r"""
respond = async () => state({presentation_mode: 'english', enabled: true, state: 'complete', completed: 2, needs_review: 1,
  fields: {description: {status: 'needs_review', warning: 'Unrecognized abbreviation; compare the original.'}}});
const controller = window.PLCTranslation.mount(container, api);
const root = new Element('section'); const data = source(); data.historical = true; data.run_id = 'earlier-run';
controller.show(root, data); await tick();
assert.ok(byClass(root,'translation-caption').some(note=>note.title.includes('No saved English version for this earlier source')));
assert.ok(byClass(root,'translation-caption').some(note=>note.title.includes('Unrecognized abbreviation')));
assert.equal(byClass(root, 'translation-original-disclosure').length, 0);
assert.equal(byClass(root,'translation-original').length,2);
assert.ok(calls.at(-1).path.includes('run_id=earlier-run'));
assert.ok(report().textContent.includes('gaps marked'));
assert.equal(retry().hidden, true);
""")

    def test_run_change_notifies_once_and_unknown_mode_is_original(self) -> None:
        self.run_js(r"""
const changes = [];
const controller = window.PLCTranslation.mount(container, api, value => changes.push(value));
await controller.refresh();
respond = async () => state({presentation_mode: 'unexpected', run_id: 'new-run'});
await controller.refresh(); await controller.refresh();
assert.equal(changes.length, 1); assert.equal(controller.mode(), 'original');
assert.equal(changes[0].run_id, 'new-run');
assert.equal(report().href, '/analysis?language=original');
""")

    def test_catalog_coverage_and_exclusions_are_visible_without_claiming_complete_logic_translation(self) -> None:
        self.run_js(r"""
respond = async () => state({catalog_coverage: {annotations: 12, unique_texts: 8,
  by_kind: {description: 4, comment: 6, text_box: 2}},
  limitations: ['Stored values and executable code are not translated.', 'Extension notes excluded.']});
const controller = window.PLCTranslation.mount(container, api); await controller.refresh();
const coverage = control('translation-coverage');
assert.equal(coverage.hidden, false);
assert.ok(coverage.textContent.includes('12 source annotations'));
assert.ok(coverage.textContent.includes('8 unique texts'));
assert.ok(!coverage.textContent.includes('4 descriptions'));
const details = control('translation-coverage-details');
assert.ok(details.textContent.includes('4 descriptions'));
assert.ok(details.textContent.includes('2 text boxes'));
assert.ok(details.textContent.includes('Extension notes excluded.'));
assert.equal(details.parent.tagName, 'details'); assert.equal(details.parent.open, false);
""")

    def test_destroy_discards_pending_read_and_configuration_responses(self) -> None:
        self.run_js(r"""
const request = deferred(); respond = () => request.promise;
const controller = window.PLCTranslation.mount(container, api);
const root = new Element('section'); controller.show(root, source());
const oldStatus = status().textContent; controller.destroy();
request.resolve(state({presentation_mode: 'english', enabled: true, state: 'running', fields: translation()})); await tick();
assert.equal(status().textContent, oldStatus);
assert.ok(!root.textContent.includes('Close the valve')); assert.equal(timers.size, 0);
const nextContainer = new Element('section');
respond = async () => state();
const next = window.PLCTranslation.mount(nextContainer, api); await next.refresh();
const changeRequest = deferred(); respond = () => changeRequest.promise;
const change = language('english', nextContainer).fire('click'); const count = calls.length; next.destroy();
changeRequest.resolve(state({presentation_mode: 'english', enabled: true, state: 'running'})); await change;
assert.equal(calls.length, count); assert.equal(timers.size, 0);
""")

    def test_pending_poll_does_not_revert_new_mode(self) -> None:
        self.run_js(r"""
const controller = window.PLCTranslation.mount(container, api); await controller.refresh();
const pending = deferred(); respond = () => pending.promise;
const oldRead = controller.refresh();
respond = async () => state({presentation_mode: 'english', enabled: true, state: 'complete', completed: 2});
await chooseMode('english');
pending.resolve(state({presentation_mode: 'original'})); await oldRead;
assert.equal(mode().value, 'english'); assert.equal(report().href, '/analysis?language=english');
""")


if __name__ == "__main__":
    unittest.main()
