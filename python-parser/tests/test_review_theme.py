"""Theme behavior and readable semantic colors in the offline generated report."""
from __future__ import annotations

import json
import re
import subprocess
import unittest

from plc_workbench.review_html import render_review_html
from test_access_review_ui import _DOM, _NODE
from test_review_html import ParsedPage, review_data


_THEME_SETUP = r"""
document.documentElement = new Element('html');
const themeButton = new Element('button');
themeButton.id = 'theme-toggle';
themeButton.hidden = true;
page.append(themeButton);
const savedPreferences = new Map(Object.entries(input.preferences || {}));
const preferenceWrites = [];
const localPreferences = {
  getItem(key) {
    if(input.storage === 'read-denied') throw new Error('Storage denied');
    return savedPreferences.get(key) ?? null;
  },
  setItem(key, value) {
    if(input.storage === 'write-denied') throw new Error('Storage denied');
    savedPreferences.set(key, value); preferenceWrites.push([key, value]);
  }
};
if(input.storage === 'property-denied') {
  Object.defineProperty(window, 'localStorage', {get(){throw new Error('Storage denied');}});
} else if(input.storage !== 'absent') {
  window.localStorage = localPreferences;
}
const sourceBeforeTheme = JSON.stringify(input.data);
"""


@unittest.skipUnless(_NODE, 'Node is optional development tooling for UI behavior checks.')
class ReviewThemeUiTests(unittest.TestCase):
    def run_ui(self, checks: str, *, preferences: dict | None = None,
               storage: str = 'available') -> None:
        parsed = ParsedPage(render_review_html(review_data()))
        invocation = "vm.runInThisContext(input.script,{filename:'report.js'});"
        dom = _DOM.replace(invocation, _THEME_SETUP + '\n' + invocation)
        self.assertNotEqual(dom, _DOM)
        process = subprocess.run(
            [_NODE, '-e', dom], input=json.dumps({
                'data': json.loads(parsed.scripts[0][1]), 'script': parsed.scripts[1][1],
                'checks': checks, 'preferences': preferences, 'storage': storage,
            }), text=True, encoding='utf-8', capture_output=True, timeout=30, check=False,
        )
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)

    def test_default_toggle_round_trip_preserves_evidence_and_navigation(self) -> None:
        self.run_ui(r"""
        assert.equal(document.documentElement.dataset.theme,'dark');
        assert.equal(themeButton.hidden,false);
        assert.equal(themeButton.textContent,'Dark mode · Switch to light');
        assert.equal(themeButton.attributes['aria-label'],'Dark mode is on. Switch to light mode');
        assert.deepEqual(preferenceWrites,[]);
        navigate('guide');
        const guideBeforeTheme=content.textContent;
        themeButton.click();
        assert.equal(document.documentElement.dataset.theme,'light');
        assert.equal(themeButton.textContent,'Light mode · Switch to dark');
        assert.equal(themeButton.attributes['aria-label'],'Light mode is on. Switch to dark mode');
        assert.equal(content.textContent,guideBeforeTheme);
        assert.equal(savedPreferences.get('plc-workbench-theme'),'light');
        themeButton.click();
        assert.equal(document.documentElement.dataset.theme,'dark');
        assert.deepEqual(preferenceWrites,[['plc-workbench-theme','light'],['plc-workbench-theme','dark']]);
        assert.equal(JSON.stringify(input.data),sourceBeforeTheme);
        navigate('ladder');clickText(content,'Rung 0');
        assert.ok(content.textContent.includes('XIC(A)OTE(Missing);'));
        """)

    def test_saved_light_preference_is_restored_without_writing_on_load(self) -> None:
        self.run_ui(r"""
        assert.equal(document.documentElement.dataset.theme,'light');
        assert.equal(themeButton.textContent,'Light mode · Switch to dark');
        assert.deepEqual(preferenceWrites,[]);
        themeButton.click();
        assert.equal(savedPreferences.get('plc-workbench-theme'),'dark');
        """, preferences={'plc-workbench-theme': 'light'})

    def test_unrecognized_preference_falls_back_to_dark(self) -> None:
        for value in ('system', '', '<img src="invalid">'):
            with self.subTest(value=value):
                self.run_ui(r"""
                assert.equal(document.documentElement.dataset.theme,'dark');
                assert.equal(themeButton.textContent,'Dark mode · Switch to light');
                assert.deepEqual(preferenceWrites,[]);
                """, preferences={'plc-workbench-theme': value})

    def test_blocked_or_absent_storage_never_disables_toggle_or_report(self) -> None:
        for storage in ('read-denied', 'write-denied', 'property-denied', 'absent'):
            with self.subTest(storage=storage):
                self.run_ui(r"""
                assert.equal(document.documentElement.dataset.theme,'dark');
                themeButton.click();
                assert.equal(document.documentElement.dataset.theme,'light');
                themeButton.click();
                assert.equal(document.documentElement.dataset.theme,'dark');
                navigate('guide');
                assert.ok(content.textContent.includes('What this review is for'));
                assert.equal(JSON.stringify(input.data),sourceBeforeTheme);
                """, storage=storage)


class ReviewThemeHtmlTests(unittest.TestCase):
    def test_toggle_is_native_button_and_hidden_when_script_is_unavailable(self) -> None:
        parsed = ParsedPage(render_review_html(review_data()))
        buttons = [attrs for tag, attrs in parsed.starts
                   if tag == 'button' and attrs.get('id') == 'theme-toggle']
        self.assertEqual(len(buttons), 1)
        self.assertEqual(buttons[0]['type'], 'button')
        self.assertIn('hidden', buttons[0])
        self.assertNotIn('onclick', buttons[0])

    def test_semantic_text_colors_meet_normal_text_contrast_in_both_themes(self) -> None:
        css = ParsedPage(render_review_html(review_data())).styles[0]
        dark = re.search(r':root\{([^}]+)\}', css).group(1)
        light = re.search(r'@media screen\{:root\[data-theme="light"\]\{([^}]+)\}', css).group(1)

        def colors(rule: str) -> dict[str, str]:
            return dict(re.findall(r'--([\w-]+):(#\w+)', rule))

        def luminance(color: str) -> float:
            channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4
                      for c in channels]
            return sum(c * weight for c, weight in zip(linear, (.2126, .7152, .0722)))

        dark_colors, light_colors = colors(dark), colors(light)
        self.assertEqual(dark_colors.keys(), light_colors.keys())
        pairs = [('ink', 'canvas'), ('ink', 'paper'), ('ink', 'control'),
                 ('ink', 'violet-soft'), ('muted', 'paper'), ('muted', 'canvas'),
                 ('muted', 'raised'), ('muted', 'hover'), ('rail-ink', 'rail'),
                 ('rail-muted', 'rail'), ('nav-ink', 'nav-active'),
                 ('nav-ink', 'teal-soft'), ('teal', 'paper'), ('teal', 'teal-soft'),
                 ('amber', 'amber-soft'), ('red', 'red-soft'),
                 ('neutral-ink', 'neutral-soft'), ('violet', 'paper'),
                 ('violet', 'violet-soft'), ('source-ink', 'source'),
                 ('notice-ink', 'notice'), ('notice-strong', 'notice')]
        for mode, palette in (('dark', dark_colors), ('light', light_colors)):
            for foreground, background in pairs:
                with self.subTest(mode=mode, foreground=foreground, background=background):
                    levels = sorted((luminance(palette[foreground]), luminance(palette[background])))
                    self.assertGreaterEqual((levels[1] + .05) / (levels[0] + .05), 4.5)


if __name__ == '__main__':
    unittest.main()
