"""English presentation preserves source payload and remains completely offline."""
from copy import deepcopy
import json
import re
import subprocess
import unittest

from plc_workbench.project_store import ProjectError
from plc_workbench.review_html import render_review_html
from plc_workbench.workspace_report import refresh_report
from test_access_review_ui import _NODE
from test_cpt_access_review_ui import DOM
from test_review_html import ParsedPage, review_data


class WorkspaceReportLanguageTests(unittest.TestCase):
    def setUp(self):
        self.original = 'Retour de la pompe'
        self.data = review_data(self.original)
        self.rung = self.data['inventory']['rungs'][0]
        self.translations = {self.original: {'text': 'Pump feedback', 'status': 'translated', 'failed': False}}
        self.catalog = {
            'snapshot_id': self.data['snapshot']['id'],
            'entries': [{'id': 'annotation_invented', 'owner_id': self.rung['id'],
                         'locator': self.rung['locator'] + '/Comment[1]', 'kind': 'comment', 'original': self.original}],
            'coverage': {'annotations': 1, 'unique_texts': 1},
            'limitations': ['Executable text and names remain original.'],
        }

    def rendered(self, **overrides):
        options = {'translations': self.translations, 'language': 'english', 'catalog': self.catalog, **overrides}
        html = refresh_report(render_review_html(self.data).encode(), self.data['inventory'], **options).decode()
        overlay = json.loads(re.search(r'<div id="review-language-data" hidden>(.*?)</div>', html).group(1))
        return html, ParsedPage(html), overlay

    def test_translation_separate_from_exact_evidence_with_source_bound_allowlist(self):
        source = deepcopy(self.data)
        translations = {**self.translations,
                        'XIC(A)OTE(Missing);': {'text': 'Pretend new code', 'status': 'translated'},
                        'unrelated': {'text': 'Unrelated input', 'status': 'translated'}}
        _, parsed, overlay = self.rendered(translations=translations)
        original = ParsedPage(render_review_html(self.data))
        self.assertEqual(parsed.scripts[0][1], original.scripts[0][1])
        self.assertEqual(len(parsed.scripts), 2)
        self.assertEqual(overlay['translations'], [{'original': self.original, 'text': 'Pump feedback', 'status': 'translated'}])
        self.assertEqual(source, self.data)
        self.assertNotIn('Pump feedback', parsed.scripts[1][1])
        self.assertIn("connect-src 'none'", html_policy(parsed))

    def test_source_injection_and_malformed_overlays_are_controlled(self):
        hostile = '</div><script>alert("no")</script>&text __APP__ __LANGUAGE__ __PAYLOAD__'
        html, parsed, overlay = self.rendered(translations={self.original: {'text': hostile, 'status': 'translated'}})
        self.assertEqual(len(parsed.scripts), 2)
        self.assertNotIn(hostile, html)
        self.assertEqual(overlay['translations'][0]['text'], hostile)
        for options in ({'language': 'unknown'}, {'catalog': {'snapshot_id': 'other', 'entries': []}}, {'translations': []}):
            with self.assertRaises(ProjectError):
                self.rendered(**options)

    def test_literal_template_slots_in_source_remain_exact(self):
        data = review_data('__LANGUAGE__ __APP__ __PAYLOAD__')
        original = render_review_html(data)
        rendered = refresh_report(original.encode(), data['inventory'], language='english')
        self.assertEqual(ParsedPage(original).scripts[0][1], ParsedPage(rendered.decode()).scripts[0][1])

    @unittest.skipUnless(_NODE, 'Node is optional development UI tooling.')
    def test_full_report_switches_language_searches_both_and_keeps_code(self):
        self.run_ui(r'''
        const before=JSON.stringify(input.data);
        const picker=document.getElementById('report-language').querySelector('select');
        assert.equal(picker.value,'english');
        navigate('ladder'); clickText(content,'Rung 0');
        assert.ok(content.textContent.includes('XIC(A)OTE(Missing);'));
        assert.ok(content.textContent.includes('Pump feedback'));
        const source=content.querySelectorAll('details').find(d=>d.textContent.includes('Original source wording'));
        assert.ok(source.textContent.includes('Retour de la pompe'));
        picker.value='original';picker.events.change();
        assert.ok(!content.textContent.includes('Pump feedback'));
        assert.ok(content.textContent.includes('Retour de la pompe'));
        picker.value='both';picker.events.change();
        assert.ok(content.textContent.includes('Pump feedback'));
        assert.ok(content.textContent.includes('Retour de la pompe'));
        navigate('sfc');clickText(content,'Sequence');
        assert.ok(content.textContent.includes('Pump feedback'));
        assert.ok(content.textContent.includes('Retour de la pompe'));
        navigate('annotations');
        assert.ok(content.textContent.includes('Executable text and names remain original.'));
        const query=document.getElementById('review-search');
        query.value='feedback';query.events.input();
        assert.equal(rows(tableNamed('Source comments and descriptions')).length,1);
        query.value='Retour';query.events.input();
        assert.equal(rows(tableNamed('Source comments and descriptions')).length,1);
        tableNamed('Source comments and descriptions').querySelector('button').click();
        assert.ok(heading.textContent.includes('Rung 0'));
        assert.equal(JSON.stringify(input.data),before);
        ''')

    @unittest.skipUnless(_NODE, 'Node is optional development UI tooling.')
    def test_missing_english_is_explicit_and_original_is_collapsed(self):
        self.run_ui(r'''
        navigate('ladder');clickText(content,'Rung 0');
        assert.ok(content.textContent.includes('English wording is not available for this note.'));
        assert.ok(content.querySelectorAll('details').some(d=>d.textContent.includes('Retour de la pompe')));
        assert.ok(!content.querySelectorAll('pre').some(d=>d.textContent.includes('Discard this result')));
        ''', translations={self.original: {'text': 'Discard this result', 'status': 'needs_review', 'failed': True}})

    @unittest.skipUnless(_NODE, 'Node is optional development UI tooling.')
    def test_original_report_switches_to_english_without_requests_or_cache_entries(self):
        self.run_ui(r'''
        const picker=document.getElementById('report-language').querySelector('select');
        assert.equal(picker.value,'original');
        navigate('ladder');clickText(content,'Rung 0');
        assert.ok(content.textContent.includes('Retour de la pompe'));
        picker.value='english';picker.events.change();
        assert.ok(content.textContent.includes('English wording is not available for this note.'));
        navigate('annotations');
        assert.ok(content.textContent.includes('English available0'));
        ''', language='original', translations={})

    def run_ui(self, checks, **options):
        _, parsed, overlay = self.rendered(**options)
        setup = """
        for(const id of ['review-language-data','report-language']){const n=new Element('div');n.id=id;page.append(n);}
        document.getElementById('review-language-data').textContent=JSON.stringify(input.overlay);
        global.fetch=()=>{throw new Error('Network access is forbidden');};
        """
        script = DOM.replace("vm.runInThisContext(input.script,{filename:'report.js'});",
                             setup + "vm.runInThisContext(input.script,{filename:'report.js'});")
        result = subprocess.run([_NODE, '-e', script], input=json.dumps({
            'data': json.loads(parsed.scripts[0][1]), 'overlay': overlay,
            'script': parsed.scripts[1][1], 'checks': checks,
        }), text=True, encoding='utf-8', capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


def html_policy(parsed):
    return next(attributes['content'] for tag, attributes in parsed.starts
                if tag == 'meta' and attributes.get('http-equiv') == 'Content-Security-Policy')


if __name__ == '__main__':
    unittest.main()
