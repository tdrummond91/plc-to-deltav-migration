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

from plc_workbench.access import analyze_access
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
    def test_version_specific_payload_and_html_limits_preserve_legacy_edges(self) -> None:
        from plc_workbench.tag_data import analyze_tag_data
        from test_review import fixture
        args = fixture(comment='PRIVATE_\u00e9')
        access = analyze_access(args[1], args[2])
        tag_data = analyze_tag_data(args[0], args[1])
        for version, kwargs in ((1, {}), (2, {'access': access}), (3, {'access': access, 'tag_data': tag_data})):
            data = build_review_data(*args, **kwargs)
            page = render_review_html(data)
            payload_size = len(json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
            html_size = len(page.encode('utf-8'))
            prefix = 'MAX_REVIEW_V3_' if version == 3 else 'MAX_REVIEW_'
            other = 'MAX_REVIEW_' if version == 3 else 'MAX_REVIEW_V3_'
            with self.subTest(version=version), \
                    patch(f'plc_workbench.review_html.{other}PAYLOAD_BYTES', 1), \
                    patch(f'plc_workbench.review_html.{other}HTML_BYTES', 1):
                with patch(f'plc_workbench.review_html.{prefix}PAYLOAD_BYTES', payload_size), \
                        patch(f'plc_workbench.review_html.{prefix}HTML_BYTES', html_size):
                    self.assertEqual(render_review_html(data), page)
                with patch(f'plc_workbench.review_html.{prefix}PAYLOAD_BYTES', payload_size - 1):
                    with self.assertRaisesRegex(ReviewHtmlError, 'size limit'):
                        render_review_html(data)
                with patch(f'plc_workbench.review_html.{prefix}HTML_BYTES', html_size - 1):
                    with self.assertRaisesRegex(ReviewHtmlError, 'size limit'):
                        render_review_html(data)

    def test_review3_escape_expansion_obeys_its_html_budget(self) -> None:
        from plc_workbench.tag_data import analyze_tag_data
        from test_review import fixture
        args = fixture(tags='<Tag Name="Values"><Data Format="String"><![CDATA[' + '<' * 10000 + ']]></Data></Tag>')
        data = build_review_data(*args, access=analyze_access(args[1], args[2]),
                                 tag_data=analyze_tag_data(args[0], args[1]))
        size = len(json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
        with patch('plc_workbench.review_html.MAX_REVIEW_V3_PAYLOAD_BYTES', size + 1), \
                patch('plc_workbench.review_html.MAX_REVIEW_V3_HTML_BYTES', size + 1):
            with self.assertRaisesRegex(ReviewHtmlError, 'size limit'):
                render_review_html(data)

    def test_tag_data_versions_and_markup_values_remain_inert(self) -> None:
        from plc_workbench.tag_data import analyze_tag_data
        from test_review import fixture
        marker = '</ScRiPt><img src="https://invalid.example/value">&\u2028é'
        args = fixture(tags='<Tag Name="Values"><Data Format="String"><![CDATA[' + marker + ']]></Data></Tag>')
        access = analyze_access(args[1], args[2])
        data = build_review_data(*args, access=access, tag_data=analyze_tag_data(args[0], args[1]))
        parsed = ParsedPage(render_review_html(data, debug=True))
        self.assertEqual(len(parsed.scripts), 2)
        payload = json.loads(parsed.scripts[0][1])
        self.assertEqual(payload, data)
        self.assertEqual(payload['tag_data']['contents'][0]['direct_text'], marker)
        self.assertNotIn('img', {tag for tag, _ in parsed.starts})
        for candidate in (dict(data, schema_version=2, report_version='engineering-review-2'),
                          dict(data, report_version='engineering-review-2'),
                          {k: v for k, v in data.items() if k != 'tag_data'},
                          {k: v for k, v in data.items() if k != 'access'},
                          dict(review_data(), tag_data=data['tag_data'])):
            with self.subTest(candidate=candidate['schema_version']), self.assertRaises(ReviewHtmlError):
                render_review_html(candidate)

    def test_access_versions_are_explicit_and_evidence_round_trips(self) -> None:
        from test_review import fixture
        args = fixture(('XIC(A)OTE(B);', 'MOV(B,12);', 'PID(A,B,A,B,A,B,A);'))
        access = analyze_access(args[1], args[2])
        data = build_review_data(*args, access=access)
        parsed = ParsedPage(render_review_html(data, debug=True))
        self.assertEqual(json.loads(parsed.scripts[0][1]), data)
        self.assertEqual(data['access']['coverage']['access_gap_operands'], 1)
        for candidate in (dict(data, schema_version=1), dict(data, report_version='engineering-review-1'),
                          {k:v for k,v in data.items() if k != 'access'},
                          dict(review_data(), access=access.to_dict())):
            with self.assertRaises(ReviewHtmlError):
                render_review_html(candidate)

    def test_markup_sentinel_cannot_escape_payload_and_unicode_round_trips(self) -> None:
        marker = '</ScRiPt><img src="https://invalid.example/secret" onerror="invented()">&\u2028\u2029é'
        data = review_data(marker)
        original = deepcopy(data)
        page = render_review_html(data, debug=True)
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

    def test_application_has_no_source_markup_sink_and_offline_help_has_no_run(self) -> None:
        parsed = ParsedPage(render_review_html(review_data()))
        script = parsed.scripts[1][1]
        for forbidden in ('innerHTML', 'outerHTML', 'insertAdjacentHTML', 'document.write',
                          'eval(', 'new Function', 'XMLHttpRequest', 'WebSocket',
                          'sendBeacon', 'location.href'):
            self.assertNotIn(forbidden, script)
        # The shared help controller also serves hosted reports. Its guarded
        # backend paths are unavailable in standalone reports; runtime tests
        # additionally assert no request or popup when interacting offline.
        self.assertIn('"runId":null', script)
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
