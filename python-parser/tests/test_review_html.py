"""Private HTML containment and offline boundaries, using invented source only."""
from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from plc_workbench.references import analyze_references
from plc_workbench.review import build_review_data
from plc_workbench.review_html import ReviewHtmlError, render_review_html
from plc_workbench.sfc_structure import analyze_sfc_structure
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes


def review_data(comment: str = 'Invented review note') -> dict:
    xml = ('<RSLogix5000Content><Controller Name="Invented"><Programs><Program Name="P">'
           '<Tags><Tag Name="A" TagType="Base" DataType="BOOL"/></Tags><Routines>'
           '<Routine Name="Main" Type="RLL"><RLLContent><Rung Number="0" Type="N">'
           '<Text><![CDATA[XIC(A)OTE(Missing);]]></Text><Comment><![CDATA[' + comment
           + ']]></Comment></Rung></RLLContent></Routine>'
           '<Routine Name="Sequence" Type="SFC"><SFCContent><Step ID="1"/>'
           '<TextBox ID="2"><Text><![CDATA[' + comment + ']]></Text></TextBox>'
           '<Attachment FromID="2" ToID="1"/></SFCContent></Routine>'
           '</Routines></Program></Programs></Controller></RSLogix5000Content>')
    snapshot = snapshot_from_bytes(xml.encode())
    inventory = analyze_snapshot(snapshot)
    return build_review_data(snapshot, inventory, analyze_references(inventory),
                             analyze_sfc_structure(snapshot, inventory))


class ParsedPage(HTMLParser):
    def __init__(self, page: str):
        super().__init__(convert_charrefs=False)
        self.starts: list[tuple[str, dict]] = []
        self.scripts: list[tuple[dict, str]] = []
        self.styles: list[str] = []
        self.active: tuple[str, dict, list[str]] | None = None
        self.feed(page)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.starts.append((tag, dict(attrs)))
        if tag in {'script', 'style'}:
            self.active = (tag, dict(attrs), [])

    def handle_data(self, data: str) -> None:
        if self.active:
            self.active[2].append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.active and self.active[0] == tag:
            text = ''.join(self.active[2])
            if tag == 'script':
                self.scripts.append((self.active[1], text))
            else:
                self.styles.append(text)
            self.active = None


class ReviewHtmlTests(unittest.TestCase):
    def test_markup_sentinel_cannot_escape_payload_and_unicode_round_trips(self) -> None:
        marker = '</ScRiPt><img src="https://invalid.example/secret" onerror="invented()">&\u2028\u2029é'
        data = review_data(marker)
        original = deepcopy(data)
        page = render_review_html(data)
        parsed = ParsedPage(page)
        self.assertEqual(len(parsed.scripts), 2)
        attrs, payload = parsed.scripts[0]
        self.assertEqual(attrs, {'type': 'application/json', 'id': 'review-data'})
        self.assertEqual(json.loads(payload), data)
        self.assertEqual(data, original)
        self.assertNotIn('<', payload)
        self.assertNotIn('>', payload)
        self.assertNotIn('&', payload)
        self.assertNotIn('\u2028', payload)
        self.assertNotIn('\u2029', payload)
        self.assertNotIn('img', {tag for tag, _ in parsed.starts})
        self.assertEqual(json.loads(payload)['inventory']['rungs'][0]['comment'], marker)

    def test_offline_assets_are_embedded_and_exact_hashes_match_restrictive_policy(self) -> None:
        parsed = ParsedPage(render_review_html(review_data()))
        policy = next(attrs['content'] for tag, attrs in parsed.starts
                      if tag == 'meta' and attrs.get('http-equiv') == 'Content-Security-Policy')
        for directive in ('default-src', 'connect-src', 'img-src', 'font-src', 'object-src',
                          'frame-src', 'base-uri', 'form-action'):
            self.assertIn(f"{directive} 'none'", policy)
        self.assertNotIn('unsafe-inline', policy)
        for text in (parsed.scripts[1][1], parsed.styles[0]):
            digest = base64.b64encode(hashlib.sha256(text.encode()).digest()).decode()
            self.assertIn(f"'sha256-{digest}'", policy)
        self.assertFalse(any('src' in attrs for _, attrs in parsed.starts))
        self.assertFalse(any(tag in {'link', 'iframe', 'object', 'form'} for tag, _ in parsed.starts))
        self.assertEqual([attrs['href'] for _, attrs in parsed.starts if 'href' in attrs], ['#main'])

    def test_application_has_no_source_markup_or_network_execution_sink(self) -> None:
        parsed = ParsedPage(render_review_html(review_data()))
        script = parsed.scripts[1][1]
        for forbidden in ('innerHTML', 'outerHTML', 'insertAdjacentHTML', 'document.write',
                          'eval(', 'new Function', 'fetch(', 'XMLHttpRequest', 'WebSocket',
                          'sendBeacon', 'location.href', 'window.open'):
            self.assertNotIn(forbidden, script)
        self.assertIn('textContent', script)
        self.assertIn('PAGE_SIZE = 50', script)
        self.assertIn('aria-label', script)
        for view in ('overview', 'objects', 'ladder', 'sfc', 'patterns', 'findings'):
            self.assertIn(view + ':', script)

    def test_private_payload_retains_aliases_text_and_typed_relationships(self) -> None:
        data = review_data()
        payload = json.loads(ParsedPage(render_review_html(data)).scripts[0][1])
        self.assertEqual(payload['sfc']['annotations'], data['sfc']['annotations'])
        self.assertEqual(len(payload['sfc']['annotations']), 1)
        self.assertEqual(payload['sfc']['links'], [])
        self.assertEqual(payload['references']['operands'], data['references']['operands'])
        self.assertEqual(payload['findings'], data['findings'])
        self.assertTrue(payload['patterns'])

    def test_source_and_expansion_limits_fail_with_source_free_messages(self) -> None:
        data = review_data('PRIVATE_SENTINEL')
        with patch('plc_workbench.review_html.MAX_REVIEW_PAYLOAD_BYTES', 100):
            with self.assertRaisesRegex(ReviewHtmlError, 'size limit') as caught:
                render_review_html(data)
        self.assertNotIn('PRIVATE_SENTINEL', str(caught.exception))
        # The original JSON fits; HTML escaping expands many '<' characters.
        data['inventory']['rungs'][0]['comment'] = '<' * 10_000
        size = len(json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode())
        with (patch('plc_workbench.review_html.MAX_REVIEW_PAYLOAD_BYTES', size + 1),
              patch('plc_workbench.review_html.MAX_REVIEW_HTML_BYTES', size + 1)):
            with self.assertRaisesRegex(ReviewHtmlError, 'size limit'):
                render_review_html(data)

    def test_invalid_payload_and_missing_assets_do_not_leak_input_or_paths(self) -> None:
        for value in (None, [], {'schema_version': 1}, {**review_data(), 'schema_version': True}):
            with self.subTest(value=type(value)):
                with self.assertRaises(ReviewHtmlError):
                    render_review_html(value)
        data = review_data()
        data['private'] = object()
        with self.assertRaisesRegex(ReviewHtmlError, 'could not be rendered'):
            render_review_html(data)
        data['private'] = data
        with self.assertRaisesRegex(ReviewHtmlError, 'could not be rendered'):
            render_review_html(data)
        with patch.object(Path, 'read_text', side_effect=OSError('PRIVATE_DIRECTORY')):
            with self.assertRaises(ReviewHtmlError) as caught:
                render_review_html(review_data())
            self.assertNotIn('PRIVATE_DIRECTORY', str(caught.exception))

    def test_render_is_deterministic_without_timestamps_or_external_state(self) -> None:
        data = review_data()
        self.assertEqual(render_review_html(data), render_review_html(deepcopy(data)))


if __name__ == '__main__':
    unittest.main()
