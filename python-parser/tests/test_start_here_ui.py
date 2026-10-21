"""Offline orientation contracts against the actual page and JavaScript asset.

Node is optional development tooling. The small DOM covers interactions and
storage failures; it does not replace a browser check of the page's appearance.
All progress fixtures contain fixed learning checkpoints, not engineering data.
"""
from __future__ import annotations

from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from urllib.parse import unquote, urlsplit


_ROOT = Path(__file__).resolve().parents[2]
_NODE = shutil.which('node')
_CHECKPOINTS = (
    'orient', 'navigate', 'interpret', 'respond', 'rungs', 'io', 'loops',
    'calculations', 'sequences', 'alarms', 'connections',
)


class StartHerePage(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.starts: list[tuple[str, dict[str, str | None]]] = []
        self.labels: list[dict] = []
        self.active_label: dict | None = None
        self.feed((_ROOT / 'START-HERE.html').read_text(encoding='utf-8'))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        self.starts.append((tag, attributes))
        if tag == 'label':
            self.active_label = {'starts': [], 'text': []}
        if self.active_label is not None:
            self.active_label['starts'].append((tag, attributes))

    def handle_data(self, data: str) -> None:
        if self.active_label is not None:
            self.active_label['text'].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == 'label' and self.active_label is not None:
            self.labels.append(self.active_label)
            self.active_label = None


_DOM = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {Blob} = require('node:buffer');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const PROGRESS_KEY = 'plc-workbench-learning-v1';
const THEME_KEY = 'plc-workbench-theme';
const progress = completed => JSON.stringify({kind:'plc-learning-progress', version:1, completed});

function createPage({stored={}, memory=new Map(Object.entries(stored)), mode='normal'}={}) {
  class Element {
    constructor(tag, attrs={}) {
      this.tagName=tag.toUpperCase(); this.attributes={...attrs}; this.events={};
      this.dataset={}; this.textContent=''; this.checked=false; this.value='';
      this.disabled=Object.hasOwn(attrs,'disabled'); this.children=[];
      for(const [name,value] of Object.entries(attrs)) {
        if(name.startsWith('data-')) this.dataset[name.slice(5)]=value;
      }
      this.id=attrs.id;
    }
    setAttribute(name,value) { this.attributes[name]=String(value); }
    addEventListener(name,callback) { this.events[name]=callback; }
    append(child) { this.children.push(child); child.parent=this; }
    remove() { if(this.parent) this.parent.children=this.parent.children.filter(child=>child!==this); }
    click() { assert.notEqual(this.disabled,true); if(this.tagName==='A') downloads.push(this); return this.events.click?.(); }
  }
  const elements=input.nodes.map(([tag,attrs])=>new Element(tag,attrs));
  const get=id=>{const element=elements.find(item=>item.id===id); assert.ok(element,'Missing page element: '+id); return element;};
  const checks=elements.filter(element=>Object.hasOwn(element.dataset,'check'));
  const body=new Element('body');
  const document={body, documentElement:new Element('html'), getElementById:get,
    querySelectorAll:selector=>{assert.equal(selector,'[data-check]'); return checks;},
    createElement:tag=>new Element(tag)};
  const downloads=[], blobs=[], revoked=[], timers=[];
  const context={document, Blob, URL:{
    createObjectURL:blob=>{blobs.push(blob); return 'blob:learning-'+blobs.length;},
    revokeObjectURL:url=>revoked.push(url)},
    setTimeout:callback=>timers.push(callback)};
  const storage={
    getItem:key=>{if(mode==='read-denied') throw new Error('storage read denied'); return memory.has(key)?memory.get(key):null;},
    setItem:(key,value)=>{if(mode==='write-denied') throw new Error('storage write denied'); memory.set(key,value);}
  };
  if(mode==='getter-denied') Object.defineProperty(context,'localStorage',{get(){throw new Error('storage getter denied');}});
  else if(mode!=='absent') context.localStorage=storage;
  vm.runInNewContext(input.script,context,{filename:'public/start-here/start-here.js'});
  return {get, memory, document, downloads, blobs, revoked,
    check(id,checked=true) {
      const element=checks.find(item=>item.dataset.check===id);
      assert.ok(element,'Missing checkpoint: '+id); element.checked=checked; element.events.change();
    },
    completed:()=>checks.filter(element=>element.checked).map(element=>element.dataset.check),
    saved:()=>JSON.parse(memory.get(PROGRESS_KEY)),
    async importText(text,{size=Buffer.byteLength(text,'utf8'),readError=false}={}) {
      const element=get('import-progress'); let reads=0;
      element.files=[{size,text:async()=>{reads++; if(readError) throw new Error('file read denied'); return text;}}];
      element.value='selected-progress.json'; await element.events.change();
      assert.equal(element.value,'','Import must allow selecting the same file again'); return reads;
    },
    async exported() {
      get('export-progress').click(); assert.ok(blobs.length,'Export must request a file');
      return JSON.parse(await blobs[blobs.length-1].text());
    },
    flushTimers:()=>{for(const callback of timers.splice(0)) callback();}
  };
}
const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
new AsyncFunction('assert','createPage','progress','PROGRESS_KEY','THEME_KEY','input',input.checks)(
  assert,createPage,progress,PROGRESS_KEY,THEME_KEY,input
).catch(error=>{console.error(error); process.exitCode=1;});
"""


class StartHerePageTests(unittest.TestCase):
    def test_all_links_and_resources_resolve_locally_and_anchor_ids_are_unique(self) -> None:
        page = StartHerePage()
        ids = [attrs['id'] for _, attrs in page.starts if 'id' in attrs]
        self.assertEqual(len(ids), len(set(ids)))
        resources = 0
        for tag, attrs in page.starts:
            for attribute in ('href', 'src'):
                if attribute not in attrs:
                    continue
                link = urlsplit(attrs[attribute])
                with self.subTest(tag=tag, link=attrs[attribute]):
                    self.assertFalse(link.scheme or link.netloc, 'Orientation must work offline')
                    if link.path:
                        target = (_ROOT / unquote(link.path)).resolve()
                        self.assertTrue(target.is_relative_to(_ROOT))
                        self.assertTrue(target.is_file(), f'Missing local resource: {target}')
                        self.assertNotIn('confidential', target.relative_to(_ROOT).parts)
                    elif link.fragment:
                        self.assertIn(unquote(link.fragment), ids)
                    if tag in {'script', 'link'}:
                        resources += 1
        self.assertGreaterEqual(resources, 2)
        self.assertFalse(any(tag in {'form', 'iframe', 'embed', 'textarea'} for tag, _ in page.starts))

    def test_learning_checkpoints_have_unique_fixed_ids_and_explanatory_labels(self) -> None:
        page = StartHerePage()
        checkpoints = [(tag, attrs) for tag, attrs in page.starts if 'data-check' in attrs]
        self.assertCountEqual([attrs['data-check'] for _, attrs in checkpoints], _CHECKPOINTS)
        for tag, attrs in checkpoints:
            with self.subTest(checkpoint=attrs['data-check']):
                self.assertEqual(tag, 'input')
                self.assertEqual(attrs.get('type'), 'checkbox')
                labels = [label for label in page.labels if (tag, attrs) in label['starts']]
                self.assertEqual(len(labels), 1)
                label = labels[0]
                self.assertIn('strong', [name for name, _ in label['starts']])
                self.assertIn('small', [name for name, _ in label['starts']])
                self.assertGreater(len(' '.join(label['text']).split()), 8)


@unittest.skipUnless(_NODE, 'Node is optional development tooling for UI checks.')
class StartHereUiTests(unittest.TestCase):
    def run_ui(self, checks: str) -> None:
        page = StartHerePage()
        scripts = [attrs['src'] for tag, attrs in page.starts if tag == 'script' and attrs.get('src')]
        self.assertEqual(len(scripts), 1)
        result = subprocess.run(
            [_NODE, '-e', _DOM], input=json.dumps({
                'nodes': page.starts, 'checkpoints': _CHECKPOINTS,
                'script': (_ROOT / scripts[0]).read_text(encoding='utf-8'), 'checks': checks,
            }), text=True, encoding='utf-8', capture_output=True, timeout=30, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_fresh_progress_and_next_action_follow_core_skills_not_optional_topics(self) -> None:
        self.run_ui(r"""
        const page=createPage();
        assert.deepEqual(page.completed(),[]);
        assert.equal(page.get('core-count').textContent,'0');
        assert.equal(page.get('core-progress').value,0);
        assert.equal(page.get('topic-count').textContent,'0 / 7 explored');
        assert.equal(page.get('next-action').attributes.href,'#first-look');
        page.check('loops');
        assert.equal(page.get('topic-count').textContent,'1 / 7 explored');
        assert.equal(page.get('core-count').textContent,'0');
        assert.equal(page.get('next-action').attributes.href,'#first-look');
        for(const [id,href] of [['orient','#practice'],['navigate','#interpret'],
          ['interpret','#respond'],['respond','#your-report']]) {
          page.check(id); assert.equal(page.get('next-action').attributes.href,href);
        }
        assert.equal(page.get('core-count').textContent,'4');
        assert.equal(page.get('core-progress').value,4);
        assert.match(page.get('next-action').textContent,/Ready to review one real item/);
        """)

    def test_check_and_uncheck_persist_and_reload_without_losing_optional_progress(self) -> None:
        self.run_ui(r"""
        let page=createPage({stored:{[PROGRESS_KEY]:progress(['orient','navigate','rungs'])}});
        assert.deepEqual(page.completed(),['orient','navigate','rungs']);
        assert.equal(page.get('core-count').textContent,'2');
        assert.equal(page.get('next-action').attributes.href,'#interpret');
        page.check('orient',false); page.check('alarms');
        assert.deepEqual(page.saved().completed,['navigate','rungs','alarms']);
        page=createPage({memory:page.memory});
        assert.deepEqual(page.completed(),['navigate','rungs','alarms']);
        assert.equal(page.get('core-count').textContent,'1');
        assert.equal(page.get('topic-count').textContent,'2 / 7 explored');
        assert.equal(page.get('next-action').attributes.href,'#first-look');
        """)

    def test_two_tabs_keep_latest_saved_checks_during_changes_import_and_export(self) -> None:
        self.run_ui(r"""
        const memory=new Map();
        const first=createPage({memory}), second=createPage({memory});
        first.check('orient');
        second.check('navigate');
        assert.deepEqual(second.saved().completed,['orient','navigate']);
        first.check('orient',false);
        assert.deepEqual(first.saved().completed,['navigate']);
        second.check('loops');
        assert.deepEqual(second.saved().completed,['navigate','loops']);
        assert.deepEqual((await first.exported()).completed,['navigate','loops']);
        second.check('alarms');
        await first.importText(progress(['respond']));
        assert.deepEqual(first.saved().completed,['navigate','respond','loops','alarms']);
        """)

    def test_valid_import_merges_completed_skills_and_empty_import_keeps_them(self) -> None:
        self.run_ui(r"""
        const page=createPage(); page.check('orient'); page.check('alarms');
        await page.importText(progress(['loops','navigate','orient']));
        assert.deepEqual(page.completed(),['orient','navigate','loops','alarms']);
        assert.deepEqual(page.saved().completed,page.completed());
        assert.equal(page.get('core-count').textContent,'2');
        assert.equal(page.get('topic-count').textContent,'2 / 7 explored');
        assert.match(page.get('transfer-status').textContent,/Previously completed checks were kept/);
        await page.importText(progress([]));
        assert.deepEqual(page.completed(),['orient','navigate','loops','alarms']);
        const saved=page.memory.get(PROGRESS_KEY);
        page.get('import-progress').files=[];
        await page.get('import-progress').events.change();
        assert.equal(page.memory.get(PROGRESS_KEY),saved);
        """)

    def test_malformed_or_unrecognized_imports_leave_current_progress_unchanged(self) -> None:
        self.run_ui(r"""
        const page=createPage(); page.check('orient'); page.check('loops');
        const before=page.memory.get(PROGRESS_KEY);
        const invalid=['{','null','[]',progress(['unknown']),progress(['orient','orient']),
          progress([null]),progress(['navigate','unknown']),
          JSON.stringify({kind:'other',version:1,completed:['navigate']}),
          JSON.stringify({kind:'plc-learning-progress',version:2,completed:['navigate']}),
          JSON.stringify({kind:'plc-learning-progress',version:1,completed:'navigate'}),
          JSON.stringify({kind:'plc-learning-progress',version:1,completed:['navigate'],notes:'Invented note'})];
        for(const value of invalid) {
          await page.importText(value);
          assert.deepEqual(page.completed(),['orient','loops']);
          assert.equal(page.memory.get(PROGRESS_KEY),before);
          assert.match(page.get('transfer-status').textContent,/current checks were not changed/);
        }
        """)

    def test_import_size_boundary_and_file_read_errors_preserve_existing_checks(self) -> None:
        self.run_ui(r"""
        const page=createPage(); page.check('orient');
        assert.equal(await page.importText(progress(['navigate']),{size:8193}),0);
        assert.deepEqual(page.completed(),['orient']);
        await page.importText(progress(['navigate']).padEnd(8193,' '),{size:8192});
        assert.deepEqual(page.completed(),['orient']);
        await page.importText(progress(['navigate']),{readError:true});
        assert.deepEqual(page.completed(),['orient']);
        assert.deepEqual(page.saved().completed,['orient']);
        await page.importText(progress(['navigate']).padEnd(8192,' '));
        assert.deepEqual(page.completed(),['orient','navigate']);
        assert.match(page.get('transfer-status').textContent,/Progress imported/);
        """)

    def test_export_contains_only_fixed_checkpoint_choices_and_releases_download_resources(self) -> None:
        self.run_ui(r"""
        const page=createPage();
        await page.importText(progress([...input.checkpoints].reverse()));
        const exported=await page.exported();
        assert.deepEqual(Object.keys(exported).sort(),['completed','kind','version']);
        assert.equal(exported.kind,'plc-learning-progress');
        assert.equal(exported.version,1);
        assert.deepEqual(exported.completed,input.checkpoints);
        assert.equal(page.blobs[0].type,'application/json');
        assert.equal(page.downloads[0].download,'workbench-learning-progress.json');
        assert.equal(page.document.body.children.length,0);
        page.flushTimers();
        assert.deepEqual(page.revoked,[page.downloads[0].href]);
        assert.match(page.get('transfer-status').textContent,/Progress download requested/);
        """)

    def test_storage_absent_or_denied_does_not_break_checks_theme_or_export(self) -> None:
        self.run_ui(r"""
        for(const mode of ['absent','read-denied','write-denied','getter-denied']) {
          const page=createPage({mode});
          assert.equal(page.get('export-progress').disabled,false,mode);
          assert.equal(page.get('import-progress').disabled,false,mode);
          assert.equal(page.get('theme-toggle').disabled,false,mode);
          page.check('orient'); page.check('rungs');
          page.get('theme-toggle').click();
          assert.equal(page.document.documentElement.dataset.theme,'light',mode);
          assert.deepEqual((await page.exported()).completed,['orient','rungs'],mode);
          await page.importText(progress(['navigate']));
          assert.deepEqual(page.completed(),['orient','navigate','rungs'],mode);
          if(mode!=='read-denied') assert.match(page.get('storage-status').textContent,/cannot save progress/);
        }
        """)

    def test_readable_but_unwritable_saved_progress_keeps_unsaved_checks_and_unchecks(self) -> None:
        self.run_ui(r"""
        const page=createPage({mode:'write-denied',stored:{[PROGRESS_KEY]:progress(['orient'])}});
        page.check('navigate'); page.check('interpret');
        assert.deepEqual(page.completed(),['orient','navigate','interpret']);
        assert.deepEqual((await page.exported()).completed,['orient','navigate','interpret']);
        page.check('orient',false);
        assert.deepEqual((await page.exported()).completed,['navigate','interpret']);
        assert.deepEqual(page.completed(),['navigate','interpret']);
        await page.importText(progress(['respond']));
        assert.deepEqual((await page.exported()).completed,['navigate','interpret','respond']);
        assert.deepEqual(page.saved().completed,['orient']);
        assert.match(page.get('storage-status').textContent,/cannot save progress/);
        """)

    def test_malformed_saved_progress_recovers_when_a_skill_is_checked(self) -> None:
        self.run_ui(r"""
        for(const saved of ['{',progress(['unknown']),' '.repeat(8193)]) {
          const page=createPage({stored:{[PROGRESS_KEY]:saved}});
          assert.deepEqual(page.completed(),[]);
          assert.match(page.get('storage-status').textContent,/Saved progress is unavailable/);
          page.check('navigate');
          assert.deepEqual(page.saved().completed,['navigate']);
          assert.deepEqual(createPage({memory:page.memory}).completed(),['navigate']);
        }
        """)

    def test_existing_light_preference_restores_and_theme_change_keeps_progress(self) -> None:
        self.run_ui(r"""
        const page=createPage({stored:{[THEME_KEY]:'light',[PROGRESS_KEY]:progress(['orient'])}});
        assert.equal(page.document.documentElement.dataset.theme,'light');
        assert.equal(page.get('theme-toggle').textContent,'Switch to dark');
        page.get('theme-toggle').click();
        assert.equal(page.document.documentElement.dataset.theme,'dark');
        assert.equal(page.memory.get(THEME_KEY),'dark');
        assert.deepEqual(page.saved().completed,['orient']);
        const restored=createPage({memory:page.memory});
        assert.equal(restored.document.documentElement.dataset.theme,'dark');
        assert.deepEqual(restored.completed(),['orient']);
        """)


if __name__ == '__main__':
    unittest.main()
