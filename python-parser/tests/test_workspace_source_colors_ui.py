"""Exact source tokens, readable palettes, and bounded syntax-only coloring."""
from __future__ import annotations

import re
import subprocess
import unittest

from test_workspace_ui import ASSETS, NODE
from test_workspace_ladder_diagram_ui import DOM, COLOR_SCRIPT


@unittest.skipUnless(NODE, "Node is optional developer tooling")
class SourceColorsTests(unittest.TestCase):
    def run_js(self, checks: str) -> None:
        result = subprocess.run([NODE, "-"], input=DOM + COLOR_SCRIPT + checks,
                                capture_output=True, encoding="utf-8", timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_expression_symbols_constants_and_opaque_addresses_keep_exact_text(self) -> None:
        self.run_js(r"""
const raw='Array[Index[0] + 1].Member + ABS(Pressure) / -1.25e-3 AND Local:2:I.Data.0 + 16#FF';
const colors=window.PLCSourceColors.create([{arguments:[raw]}]),root=new Element('code');colors.append(root,raw);
assert.equal(root.textContent,raw);
assert.deepEqual(cls(root,'source-variable').map(n=>n.attributes['data-source-variable']),['Array[Index[0] + 1].Member','Pressure','Local:2:I.Data.0']);
assert.deepEqual(cls(root,'source-operator').map(n=>n.textContent),['+','ABS','/','-','AND','+']);
assert.deepEqual(cls(root,'source-literal').map(n=>n.textContent),['1.25e-3','16#FF']);
const repeated=new Element('mi');colors.paint(repeated,'Pressure');
assert.equal(repeated.attributes.class,cls(root,'source-variable')[1].attributes.class);
""")

    def test_hostile_text_is_never_interpreted_and_render_work_is_bounded(self) -> None:
        self.run_js(r"""
const colors=window.PLCSourceColors.create(),root=new Element('code');
const raw='"<img src=x onerror=bad()>" + A';colors.append(root,raw);
assert.equal(root.textContent,raw);assert.equal(all(root).some(n=>['img','script'].includes(n.tagName)),false);
assert.equal(cls(root,'source-literal')[0].textContent,'"<img src=x onerror=bad()>"');
const huge=new Element('code'),text='A + B '.repeat(5000);colors.append(huge,text);
assert.equal(huge.textContent,text);assert.ok(huge.children.length<=1025);
const invalid=new Element('code');colors.append(invalid,'Array[Unclosed + Value');
assert.equal(invalid.textContent,'Array[Unclosed + Value');
""")

    def test_paint_retains_layout_classes_and_literal_and_operation_roles(self) -> None:
        self.run_js(r"""
const colors=window.PLCSourceColors.create([{arguments:['A','B']}]),node=new Element('mi');
node.setAttribute('class','flow-opcode');colors.paint(node,'ADD','operator');
assert.equal(node.attributes.class,'flow-opcode source-token source-operator');
colors.paint(node,'A');assert.ok(node.attributes.class.includes('source-var-0'));
assert.equal(node.attributes.class.includes('source-operator'),false);
const number=new Element('mi');colors.paint(number,'-1.5');assert.ok(number.attributes.class.includes('source-literal'));
""")

    def test_each_theme_has_readable_variable_operator_and_literal_colors(self) -> None:
        css = (ASSETS / 'source-colors.css').read_text(encoding='utf-8')
        def luminance(hex_value: str) -> float:
            rgb = [int(hex_value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            values = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
            return sum(v * weight for v, weight in zip(values, (.2126, .7152, .0722)))
        blocks = css.split('}', 2)
        for theme, block, backgrounds in [('dark', blocks[0], ['#0d1118', '#1b2430', '#222d3a']),
                                           ('light', blocks[1], ['#f1f4f5', '#f9fafb', '#e7edef'])]:
            colors = re.findall(r'--source-(?:var-\d|operator|literal):\s*(#[\da-f]{6})', block)
            self.assertEqual(len(colors), 8)
            self.assertEqual(len(set(colors)), 8)
            for color in colors:
                for background in backgrounds:
                    a, b = sorted([luminance(color), luminance(background)])
                    self.assertGreaterEqual((b + .05) / (a + .05), 4.5, (theme, color, background))


if __name__ == '__main__':
    unittest.main()
