"""Review regressions: invented inputs, memory buffers, and mocked publication only."""
from __future__ import annotations

from contextlib import ExitStack
from hashlib import sha256
from io import BytesIO, StringIO
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dummy.build import build_fixture, create_fixture
from summarize_xml import StructureError
from write_skeleton import create_skeleton


def fixture(body: str, **kwargs) -> tuple[str, dict]:
    return build_fixture(BytesIO(f"<Root>{body}</Root>".encode()), **kwargs)


class ReviewRegressionTests(unittest.TestCase):
    def test_interleaved_variants_share_one_parent_quota(self) -> None:
        xml, report = fixture('<Items>' + '<Item A="1"/><Item B="2"/>' * 10 + '</Items>', per_variant=2)
        self.assertEqual(len(ET.fromstring(xml).findall('.//Item')), 4)
        links = [r for r in report['occurrence_map'] if '/Item[' in r['source_locator']]
        self.assertEqual([r['source_locator'].rsplit('/', 1)[-1] for r in links],
                         ['Item[1]', 'Item[2]', 'Item[3]', 'Item[4]'])

    def test_quota_is_independent_for_each_retained_parent(self) -> None:
        group = '<Group>' + '<Item A="1"/><Item B="2"/>' * 8 + '</Group>'
        xml, _ = fixture(group * 2, per_variant=2)
        groups = ET.fromstring(xml).findall('Group')
        self.assertEqual([len(g) for g in groups], [4, 4])

    def test_late_ancestor_and_rare_descendant_survive_small_quota(self) -> None:
        common = '<Group><Items><Item/></Items></Group>'
        late = '<Group><Items><Item/><Item><Rare/></Item></Items></Group>'
        xml, report = fixture(common * 10 + late, per_variant=1)
        self.assertIsNotNone(ET.fromstring(xml).find('.//Rare'))
        rare = next(r for r in report['occurrence_map'] if r['source_locator'].endswith('/Rare[1]'))
        self.assertIn('/Group[11]/', rare['source_locator'])
        self.assertIn('/Group[2]/', rare['dummy_locator'])
        self.assertEqual(report['coverage']['source_paths'], report['coverage']['retained_paths'])
        self.assertEqual(report['selection']['local_variants'], report['selection']['retained_local_variants'])

    def test_mandatory_examples_do_not_refill_ordinary_quota(self) -> None:
        body = '<Group><Item/></Group>' * 8 + '<Group><Item/><Rare/></Group>'
        xml, report = fixture(body, per_variant=2)
        self.assertEqual(len(ET.fromstring(xml).findall('Group')), 3)
        retained = [r['source_locator'] for r in report['occurrence_map'] if r['dummy_locator'].count('/') == 2]
        self.assertEqual(retained, ['/Root[1]/Group[1]', '/Root[1]/Group[2]', '/Root[1]/Group[9]'])

    def test_complete_rung_keeps_repeated_descendants_above_quota(self) -> None:
        body = '<RLLContent><Rung Number="0" Type="N">' + '<Comment>invented</Comment>' * 12
        body += '<Text><![CDATA[XIC(A)OTE(B);]]></Text></Rung></RLLContent>'
        xml, _ = fixture(body, per_variant=1)
        self.assertEqual(len(ET.fromstring(xml).findall('.//Rung/Comment')), 12)

    def test_sampling_report_identifies_changed_policy(self) -> None:
        _, report = fixture('<Item/>')
        self.assertEqual(report['schema_version'], 2)
        self.assertEqual(report['policy_version'], 2)
        self.assertEqual(report['selection']['per_parent_variant_limit'], 5)
        self.assertNotIn('per_consecutive_variant_run', report['selection'])

    def test_output_accounting_and_mapping_cover_retained_nodes(self) -> None:
        xml, report = fixture('<Items>' + '<Item A="12">text</Item><Item B="false"/>' * 12 + '</Items>', per_variant=2)
        root = ET.fromstring(xml)
        links = report['occurrence_map']
        self.assertEqual(len(links), len(list(root.iter())))
        self.assertEqual(len({r['source_locator'] for r in links}), len(links))
        self.assertEqual(len({r['dummy_locator'] for r in links}), len(links))
        for row in report['paths']:
            for kind in ('elements', 'attributes', 'text_values'):
                self.assertEqual(row[f'source_{kind}'], row[f'retained_{kind}'] + row[f'omitted_{kind}'])
        self.assertEqual(sum(report['attribute_actions'].values()), sum(len(e.attrib) for e in root.iter()))
        self.assertEqual(report['output_sha256'], sha256(xml.encode()).hexdigest())

    def test_first_publication_failure_does_not_attempt_report(self) -> None:
        with patch('pathlib.Path.open', return_value=BytesIO(b'<Root/>')), \
             patch('dummy.build._write_atomic', side_effect=OSError('invented failure')) as publish:
            with self.assertRaises(OSError):
                create_fixture(Path('invented.L5X'), Path('invented-output'))
        self.assertEqual(publish.call_count, 1)
        self.assertEqual(publish.call_args.args[0].name, 'controller_demo.L5X')

    def test_second_publication_failure_leaves_detectable_mismatched_pair(self) -> None:
        old_xml, old_report = fixture('<Old/>')
        disk = {'controller_demo.L5X': old_xml, 'minimized-report.json': json.dumps(old_report)}
        def publish(path: Path, content: str) -> None:
            if path.name == 'minimized-report.json':
                raise OSError('invented failure')
            disk[path.name] = content
        with patch('pathlib.Path.open', return_value=BytesIO(b'<Root><New/></Root>')), \
             patch('dummy.build._write_atomic', side_effect=publish):
            with self.assertRaises(OSError):
                create_fixture(Path('invented.L5X'), Path('invented-output'))
        self.assertNotEqual(sha256(disk['controller_demo.L5X'].encode()).hexdigest(),
                            json.loads(disk['minimized-report.json'])['output_sha256'])

    def test_input_hardlink_collision_rejected_before_read(self) -> None:
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.samefile', return_value=True), \
             patch('pathlib.Path.open') as opened, patch('dummy.build._write_atomic') as publish:
            with self.assertRaises(StructureError):
                create_fixture(Path('invented.L5X'), Path('invented-output'))
        opened.assert_not_called()
        publish.assert_not_called()

    def test_output_alias_collision_rejected_before_read(self) -> None:
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.samefile', side_effect=[False, False, True]), \
             patch('pathlib.Path.open') as opened, patch('dummy.build._write_atomic') as publish:
            with self.assertRaises(StructureError):
                create_fixture(Path('invented.L5X'), Path('invented-output'))
        opened.assert_not_called()
        publish.assert_not_called()

    def test_skeleton_publication_rejects_nonblank_attribute(self) -> None:
        class OpenBuffer(StringIO):
            name = 'mock-skeleton.tmp'
            def close(self) -> None:
                pass
        buffer = OpenBuffer()
        def opened(path: Path, *_args, **_kwargs) -> BytesIO:
            if path.name == 'invented.L5X':
                return BytesIO(b'<Root Name="invented source"/>')
            return BytesIO(b'<Root Name="UNEXPECTED_RETAINED_VALUE"/>')
        with ExitStack() as stack:
            stack.enter_context(patch('pathlib.Path.open', opened))
            stack.enter_context(patch('pathlib.Path.mkdir'))
            stack.enter_context(patch('pathlib.Path.exists', lambda p: p.name == 'mock-skeleton.tmp'))
            cleanup = stack.enter_context(patch('pathlib.Path.unlink'))
            stack.enter_context(patch('write_skeleton.tempfile.NamedTemporaryFile', return_value=buffer))
            publish = stack.enter_context(patch('write_skeleton.os.replace'))
            with self.assertRaises(StructureError) as caught:
                create_skeleton(Path('invented.L5X'), Path('invented.XML'))
            self.assertNotIn('UNEXPECTED_RETAINED_VALUE', str(caught.exception))
            publish.assert_not_called()
            cleanup.assert_called_once()


if __name__ == '__main__':
    unittest.main()
