"""Run the shipped resizing controller against pointer, keyboard and storage events."""
from __future__ import annotations

import subprocess
import unittest

from test_workspace_ui import ASSETS, NODE


SCRIPT = (ASSETS / "reading-layout.js").read_text(encoding="utf-8")
DOM = r"""
const assert = require('node:assert/strict');
class Events {
  constructor() { this.events = new Map(); }
  addEventListener(name, callback) {
    if (!this.events.has(name)) this.events.set(name, new Set());
    this.events.get(name).add(callback);
  }
  removeEventListener(name, callback) { this.events.get(name)?.delete(callback); }
  fire(name, values = {}) {
    const event = {prevented: false, preventDefault() {this.prevented = true;}, ...values};
    for (const callback of this.events.get(name) || []) callback(event);
    return event;
  }
}
class Element extends Events {
  constructor(tag) {
    super(); this.tagName = tag; this.children = []; this.attributes = {};
    this.className = ''; this.value = ''; this.hidden = false; this.styleValues = {};
    this.style = {
      setProperty: (key, value) => {this.styleValues[key] = value;},
      removeProperty: key => {delete this.styleValues[key];},
    };
    this.classList = {
      contains: value => this.className.split(' ').includes(value),
      add: (...values) => {this.className = [...new Set([...this.className.split(' ').filter(Boolean), ...values])].join(' ');},
      remove: (...values) => {this.className = this.className.split(' ').filter(v => !values.includes(v)).join(' ');},
      toggle: (value, active) => {if (active) this.classList.add(value); else this.classList.remove(value);},
    };
    this.captured = null;
  }
  append(...children) {children.forEach(child => {child.parent = this; this.children.push(child);});}
  insertBefore(child, before) {child.parent = this; this.children.splice(this.children.indexOf(before), 0, child);}
  remove() {if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this);}
  setAttribute(name, value) {this.attributes[name] = String(value);}
  getAttribute(name) {return this.attributes[name];}
  focus() {this.focused = true;}
  setPointerCapture(id) {this.captured = id;}
  hasPointerCapture(id) {return this.captured === id;}
  releasePointerCapture(id) {if (this.captured === id) this.captured = null;}
  getBoundingClientRect() {return {left: 100, width};}
}
const document = {
  createElement: tag => new Element(tag),
  createTextNode: text => Object.assign(new Element('#text'), {textContent: text}),
};
const window = new Events();
let width = 1200;
const media = new Events(); media.matches = false;
window.matchMedia = query => {assert.equal(query, '(max-width: 1150px)'); return media;};
let observer = null;
window.ResizeObserver = class {
  constructor(callback) {this.callback = callback; this.disconnected = false; observer = this;}
  observe(element) {this.element = element;}
  disconnect() {this.disconnected = true;}
};
const storage = new Map(); const writes = [];
window.localStorage = {
  getItem: key => storage.get(key) || null,
  setItem: (key, value) => {storage.set(key, value); writes.push([key, value]);},
};
const key = 'plc-workspace-reading-layout-v1';
const grid = new Element('div'); grid.className = 'workspace-grid';
const inventory = new Element('section'); inventory.id = 'rung-inventory';
const detail = new Element('section'); detail.id = 'rung-detail';
grid.append(inventory, detail);
const settings = new Element('div');
const all = root => [root, ...root.children.flatMap(all)];
const separator = () => all(grid).find(node => node.getAttribute('role') === 'separator');
const size = () => all(settings).find(node => node.tagName === 'select');
const reset = () => all(settings).find(node => node.tagName === 'button');
const left = () => Number.parseFloat(grid.styleValues['--rung-inventory-width']);
const close = (actual, expected) => assert.ok(Math.abs(actual - expected) < 0.00001, `${actual} != ${expected}`);
const down = (id = 3) => separator().fire('pointerdown', {button: 0, isPrimary: true, pointerId: id, clientX: 100 + left() + 10});
const move = (x, id = 3) => separator().fire('pointermove', {pointerId: id, clientX: x});
"""


@unittest.skipUnless(NODE, "Node is optional developer tooling")
class WorkspaceReadingLayoutTests(unittest.TestCase):
    def run_js(self, checks: str) -> None:
        result = subprocess.run(
            [NODE, "-"], input=DOM + SCRIPT + "\n" + checks,
            capture_output=True, encoding="utf-8", timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_defaults_are_accessible_equation_only_and_mount_is_idempotent(self) -> None:
        self.run_js(r"""
const first = window.PLCReadingLayout.mount(grid, settings);
assert.equal(grid.children.length, 3);
assert.deepEqual(grid.children, [inventory, separator(), detail]);
close(left(), 1180 / 3);
assert.equal(grid.styleValues['--rung-equation-scale'], '0.75');
assert.equal(size().value, '75');
assert.equal(separator().tabIndex, 0);
assert.equal(separator().attributes['aria-orientation'], 'vertical');
assert.equal(separator().attributes['aria-controls'], 'rung-inventory rung-detail');
assert.match(separator().attributes['aria-valuetext'], /Rung inventory \d+ pixels; selected source \d+ pixels/);
assert.equal(window.PLCReadingLayout.mount(grid, settings), first);
assert.equal(grid.children.length, 3);
assert.equal(settings.children.length, 1);
assert.equal(writes.length, 0);
assert.equal(inventory.styleValues['font-size'], undefined);
assert.equal(detail.styleValues['font-size'], undefined);
""")

    def test_map_split_has_independent_preferences_and_labels(self) -> None:
        self.run_js(r"""
storage.set(key, JSON.stringify({version:1,ratio:.3,scale:125}));
const mapKey='plc-workspace-map-layout-v1';
window.PLCReadingLayout.mount(grid,settings,{storageKey:mapKey,defaultRatio:.6,leftLabel:'Ladder map',rightLabel:'selected source',minLeft:380});
close(left(),1180*.6);assert.equal(size().value,'75');
assert.equal(separator().attributes['aria-label'],'Resize ladder map and selected source panes');
separator().fire('keydown',{key:'Home'});close(left(),380);
assert.equal(JSON.parse(storage.get(key)).ratio,.3);assert.equal(JSON.parse(storage.get(key)).scale,125);
assert.ok(storage.has(mapKey));reset().fire('click');close(left(),1180*.6);
""")

    def test_drag_captures_pointer_preserves_grab_offset_and_clamps_both_panes(self) -> None:
        self.run_js(r"""
window.PLCReadingLayout.mount(grid, settings);
const start = left(); const event = down();
assert.equal(event.prevented, true);
assert.equal(separator().captured, 3);
assert.equal(separator().focused, true);
move(100 + start + 10); close(left(), start);
move(650); close(left(), 540);
move(5000); assert.equal(left(), 820); assert.equal(1180 - left(), 360);
move(-5000); close(left(), 240);
separator().fire('pointerup', {pointerId: 3});
assert.equal(separator().captured, null);
assert.equal(grid.classList.contains('rung-reading-dragging'), false);
assert.equal(writes.length, 1);
close(JSON.parse(storage.get(key)).ratio, 240 / 1180);
move(900); close(left(), 240);
""")

    def test_nonprimary_and_foreign_pointer_events_do_not_change_layout(self) -> None:
        self.run_js(r"""
window.PLCReadingLayout.mount(grid, settings);
const original = left();
separator().fire('pointerdown', {button: 2, pointerId: 3, clientX: 300});
move(900); close(left(), original);
separator().fire('pointerdown', {button: 0, isPrimary: false, pointerId: 3, clientX: 300});
move(900); close(left(), original);
down(); move(900, 9); close(left(), original);
separator().fire('pointerup', {pointerId: 9});
assert.equal(separator().captured, 3);
move(800); assert.equal(left(), 690);
separator().fire('pointercancel', {pointerId: 3});
assert.equal(separator().captured, null);
move(500); assert.equal(left(), 690);
""")

    def test_keyboard_and_double_click_resize_without_replacing_equation_preference(self) -> None:
        self.run_js(r"""
window.PLCReadingLayout.mount(grid, settings);
size().value = '50'; size().fire('change');
const original = left();
assert.equal(separator().fire('keydown', {key: 'ArrowRight'}).prevented, true);
close(left(), original + 10);
separator().fire('keydown', {key: 'ArrowLeft', shiftKey: true}); close(left(), original - 40);
separator().fire('keydown', {key: 'Home'}); close(left(), 240);
separator().fire('keydown', {key: 'End'}); assert.equal(left(), 820);
assert.equal(separator().fire('keydown', {key: 'Tab'}).prevented, false);
assert.equal(left(), 820);
separator().fire('dblclick'); close(left(), original);
assert.equal(size().value, '50');
assert.equal(JSON.parse(storage.get(key)).scale, 50);
""")

    def test_resize_clamps_display_but_keeps_saved_ratio_and_releases_mobile_drag(self) -> None:
        self.run_js(r"""
storage.set(key, JSON.stringify({version: 1, ratio: 0.7, scale: 100}));
window.PLCReadingLayout.mount(grid, settings);
width = 1400; observer.callback(); close(left(), 966);
width = 800; observer.callback(); close(left(), 420);
assert.equal(JSON.parse(storage.get(key)).ratio, 0.7);
width = 1400; window.fire('resize'); close(left(), 966);
down(); assert.equal(separator().captured, 3);
media.matches = true; media.fire('change');
assert.equal(separator().captured, null);
assert.equal(separator().hidden, true);
assert.equal(separator().tabIndex, -1);
assert.equal(grid.classList.contains('rung-reading-stacked'), true);
move(300); close(left(), 966);
separator().fire('keydown', {key: 'Home'}); close(left(), 966);
media.matches = false; media.fire('change');
assert.equal(separator().hidden, false);
close(left(), 966);
assert.equal(JSON.parse(storage.get(key)).ratio, 0.7);
""")

    def test_hidden_or_too_narrow_grid_stacks_and_recovers_on_resize_observation(self) -> None:
        self.run_js(r"""
width = 0; window.PLCReadingLayout.mount(grid, settings);
assert.equal(separator().hidden, true);
width = 619; observer.callback(); assert.equal(separator().hidden, true);
width = 620; observer.callback(); assert.equal(separator().hidden, false);
assert.equal(left(), 240);
assert.equal(separator().attributes['aria-valuemin'], '40');
assert.equal(separator().attributes['aria-valuemax'], '40');
separator().fire('keydown', {key: 'End'}); assert.equal(left(), 240);
width = 1200; observer.callback(); close(left(), 472);
""")

    def test_bad_saved_values_fall_back_without_poisoning_geometry(self) -> None:
        self.run_js(r"""
for (const saved of [null, 'malformed', '[]', '{}',
  JSON.stringify({version: 9, ratio: 0.6, scale: 125}),
  JSON.stringify({version: 1, ratio: 0, scale: 300}),
  JSON.stringify({version: 1, ratio: 1, scale: '50'}),
  JSON.stringify({version: 1, ratio: '0.5', scale: null}),
  '{"version":1,"ratio":1e400,"scale":75}']) {
  if (saved === null) storage.delete(key); else storage.set(key, saved);
  const controller = window.PLCReadingLayout.mount(grid, settings);
  close(left(), 1180 / 3);
  assert.equal(size().value, '75');
  assert.ok(Number.isFinite(left()));
  controller.destroy();
}
""")

    def test_valid_preferences_restore_independently_and_only_settings_are_stored(self) -> None:
        self.run_js(r"""
storage.set(key, JSON.stringify({version: 1, ratio: 0.5, scale: 125}));
window.PLCReadingLayout.mount(grid, settings);
close(left(), 590); assert.equal(size().value, '125');
for (const value of [50, 75, 100, 125]) {
  size().value = String(value); size().fire('change');
  assert.equal(grid.styleValues['--rung-equation-scale'], String(value / 100));
  assert.equal(JSON.parse(storage.get(key)).scale, value);
  close(left(), 590);
}
const savedCount = writes.length;
size().value = '100000'; size().fire('change');
assert.equal(writes.length, savedCount);
assert.equal(grid.styleValues['--rung-equation-scale'], '1.25');
assert.ok(writes.every(([name, text]) => name === key
  && Object.keys(JSON.parse(text)).sort().join(',') === 'ratio,scale,version'));
reset().fire('click'); close(left(), 1180 / 3);
assert.equal(size().value, '75');
assert.equal(JSON.parse(storage.get(key)).scale, 75);
""")

    def test_unavailable_storage_does_not_block_reading_or_resizing(self) -> None:
        self.run_js(r"""
Object.defineProperty(window, 'localStorage', {get() {throw new Error('Blocked storage');}});
const controller = window.PLCReadingLayout.mount(grid, settings);
separator().fire('keydown', {key: 'End'}); assert.equal(left(), 820);
size().value = '100'; size().fire('change');
assert.equal(grid.styleValues['--rung-equation-scale'], '1');
controller.reset(); close(left(), 1180 / 3);
controller.destroy();
""")

    def test_capture_failure_and_loss_leave_controller_usable(self) -> None:
        self.run_js(r"""
window.PLCReadingLayout.mount(grid, settings);
const capture = separator().setPointerCapture;
separator().setPointerCapture = () => {throw new Error('Pointer no longer active');};
down(); assert.equal(grid.classList.contains('rung-reading-dragging'), false);
separator().setPointerCapture = capture;
down(); move(700); assert.equal(left(), 590);
separator().fire('lostpointercapture', {pointerId: 3});
assert.equal(grid.classList.contains('rung-reading-dragging'), false);
move(800); assert.equal(left(), 590);
separator().fire('keydown', {key: 'ArrowRight'}); assert.equal(left(), 600);
""")

    def test_destroy_cleans_up_only_its_own_elements_and_listeners(self) -> None:
        self.run_js(r"""
const extra = new Element('span'); settings.append(extra);
const controller = window.PLCReadingLayout.mount(grid, settings);
const oldObserver = observer; down(); controller.destroy(); controller.destroy();
assert.deepEqual(grid.children, [inventory, detail]);
assert.deepEqual(settings.children, [extra]);
assert.equal(grid.className, 'workspace-grid');
assert.deepEqual(grid.styleValues, {});
assert.equal(oldObserver.disconnected, true);
assert.equal(window.events.get('resize').size, 0);
assert.equal(media.events.get('change').size, 0);
window.fire('resize'); oldObserver.callback(); assert.deepEqual(grid.styleValues, {});
assert.ok(window.PLCReadingLayout.mount(grid, settings));
assert.equal(grid.children.length, 3);
""")

    def test_resize_event_fallback_works_without_resize_observer(self) -> None:
        self.run_js(r"""
window.ResizeObserver = undefined;
window.PLCReadingLayout.mount(grid, settings);
width = 1000; window.fire('resize'); close(left(), 980 / 3);
assert.equal(observer, null);
""")


if __name__ == "__main__":
    unittest.main()
