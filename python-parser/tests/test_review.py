"""Invented evidence exercises the private review model without IO or processes."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from plc_workbench.access import analyze_access
from plc_workbench.references import analyze_references
from plc_workbench.review import (
    ReviewError, build_review_data, render_review_json, validate_review_data,
)
from plc_workbench.sfc_structure import analyze_sfc_structure
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes


def fixture(texts: tuple[str, ...] = ('XIC(A)OTE(B);',), *, tags: str = '',
            sfc: str = '', extra_routines: str = '', comment: str = ''):
    rungs = ''.join(f'<Rung Number="{i}" Type="N"><Text><![CDATA[{text}]]></Text>'
                    f'<Comment><![CDATA[{comment}]]></Comment></Rung>'
                    for i, text in enumerate(texts))
    raw = ('<RSLogix5000Content><Controller Name="Demo"><Programs><Program Name="P">'
           '<Tags><Tag Name="A" TagType="Base" DataType="BOOL"/>'
           '<Tag Name="B" TagType="Base" DataType="BOOL"/>' + tags + '</Tags><Routines>'
           '<Routine Name="Main" Type="RLL"><RLLContent>' + rungs + '</RLLContent></Routine>'
           + extra_routines + (f'<Routine Name="Sequence" Type="SFC">{sfc}</Routine>' if sfc else '')
           + '</Routines></Program></Programs></Controller></RSLogix5000Content>')
    snapshot = snapshot_from_bytes(raw.encode('utf-8'))
    inventory = analyze_snapshot(snapshot)
    references = analyze_references(inventory)
    structure = analyze_sfc_structure(snapshot, inventory)
    return snapshot, inventory, references, structure


class ReviewTests(unittest.TestCase):
    def test_access_review_keeps_original_evidence_and_legacy_default_exact(self) -> None:
        args = fixture(('XIC(A)OTE(B);', 'MOV(B,A);'))
        original = build_review_data(*args)
        access = analyze_access(args[1], args[2])
        enriched = build_review_data(*args, access=access)
        self.assertEqual(enriched['schema_version'], 2)
        self.assertEqual(enriched['report_version'], 'engineering-review-2')
        self.assertEqual(enriched['access'], access.to_dict())
        for field in ('inventory', 'references', 'sfc', 'patterns', 'findings', 'statistics'):
            self.assertEqual(enriched[field], original[field])
        self.assertNotIn('access', original)
        self.assertEqual(build_review_data(*args), original)
        validate_review_data(*args, enriched, access=access)
        with self.assertRaises(ReviewError):
            validate_review_data(*args, enriched)

    def test_access_is_replayed_and_forged_roles_roots_or_metadata_are_rejected(self) -> None:
        args = fixture(('XIC(A)OTE(B);',))
        access = analyze_access(args[1], args[2])
        forged = deepcopy(access)
        forged.operands[0]['role'] = 'write'
        cycle: list = []
        cycle.append(cycle)
        for candidate in (forged, replace(access, roots=[]),
                          replace(access, schema_version=True),
                          replace(access, operands=cycle), True):
            with self.subTest(candidate=type(candidate)), self.assertRaises(ReviewError):
                build_review_data(*args, access=candidate)
        data = build_review_data(*args, access=access)
        data['access']['operands'][0]['role'] = 'write'
        with self.assertRaises(ReviewError):
            validate_review_data(*args, data, access=access)

    def test_invalid_destination_role_makes_enriched_review_partial(self) -> None:
        args = fixture(('MOV(A,12);',))
        access = analyze_access(args[1], args[2])
        self.assertEqual(access.status, 'partial')
        data = build_review_data(*args, access=access)
        self.assertEqual(data['status'], 'partial')
        destination = data['access']['operands'][1]
        self.assertEqual((destination['role'], destination['binding_status']), ('write', 'literal'))
        self.assertIsNone(destination['target_id'])
        self.assertEqual(data['access']['coverage']['access_gap_operands'], 1)

    def test_exact_pattern_groups_ignore_values_but_preserve_order_branches_case_arity(self) -> None:
        args = fixture(('XIC(A)OTE(B);', 'XIC(B)OTE(A);', 'OTE(B)XIC(A);',
                        '[XIC(A),XIO(B)]OTE(B);', '[XIO(B),XIC(A)]OTE(B);',
                        'xic(A)OTE(B);', 'XIC(A,B)OTE(B);'))
        data = build_review_data(*args)
        self.assertEqual(data['statistics']['parsed_rungs'], 7)
        self.assertEqual(data['statistics']['pattern_groups'], 6)
        self.assertEqual(data['statistics']['repeated_pattern_groups'], 1)
        first = data['patterns'][0]
        self.assertEqual(first['rung_ids'], [rung.id for rung in args[1].rungs[:2]])
        self.assertEqual(first['count'], 2)
        self.assertEqual(json.loads(first['shape']),
                         ['sequence', [['instruction', 'XIC', 1], ['instruction', 'OTE', 1]]])
        self.assertEqual(first['opcode_summary'], [{'opcode': 'OTE', 'arity': 1, 'count': 1},
                                                   {'opcode': 'XIC', 'arity': 1, 'count': 1}])
        self.assertEqual(data['effect_analysis'], 'not_implemented')
        self.assertEqual(data['semantic_analysis'], 'not_implemented')

    def test_failed_rungs_remain_findings_and_unknown_opcodes_remain_syntax(self) -> None:
        args = fixture(('Mystery(A);', 'Mystery();', 'XIC(A)'))
        data = build_review_data(*args)
        failed = args[1].rungs[2]
        self.assertEqual(data['statistics']['parsed_rungs'], 2)
        self.assertEqual({rid for p in data['patterns'] for rid in p['rung_ids']},
                         {args[1].rungs[0].id, args[1].rungs[1].id})
        self.assertTrue(any(f['origin'] == 'source' and f['source_id'] == failed.id
                            for f in data['findings']))
        self.assertIn('unsupported_instruction', {f['code'] for f in data['findings']})
        self.assertIn('no_operand_evidence', {f['code'] for f in data['findings']})
        self.assertEqual(data['status'], 'partial')

    def test_supported_literal_non_data_and_system_flags_are_not_operand_gaps(self) -> None:
        data = build_review_data(*fixture(('MOV(12,A)JMP(Label)XIC(S:FS)TON(A,?,?);',)))
        self.assertEqual([f for f in data['findings'] if f['origin'] == 'operand'], [])
        self.assertEqual({row['status'] for row in data['references']['operands']},
                         {'root_bound', 'literal', 'non_data', 'system_flag'})

    def test_findings_preserve_source_context_and_sfc_attachments_without_flow_claims(self) -> None:
        args = fixture(('XIC(Missing)JSR(Child,0)JSR(Absent,0);',),
                       tags='<Tag Name="BrokenAlias" TagType="Alias" AliasFor="Missing"/>',
                       extra_routines='<Routine Name="Child" Type="RLL"><RLLContent/></Routine>',
                       sfc='<SFCContent><Step ID="1"/><TextBox ID="2"><Text>Note</Text></TextBox>'
                       '<Attachment FromID="2" ToID="1"/><DirectedLink FromID="1" ToID="99"/>'
                       '</SFCContent>')
        data = build_review_data(*args)
        origins = {f['origin'] for f in data['findings']}
        self.assertEqual(origins, {'source', 'operand', 'alias', 'routine_target', 'sfc'})
        codes = {f['code'] for f in data['findings']}
        self.assertIn('missing_candidate', codes)
        self.assertIn('target_context_not_analyzed', codes)
        self.assertIn('link_endpoint_unresolved', codes)
        self.assertEqual(data['statistics']['sfc_annotations'], 1)
        self.assertEqual(data['statistics']['sfc_links'], 1)
        ids = {e.id for e in args[1].entities} | {r.id for r in args[1].rungs}
        ids.update(i.id for r in args[1].rungs for i in r.instructions)
        ids.update(row['id'] for row in args[2].operands)
        ids.update(row['id'] for row in args[3].contents + args[3].elements)
        for row in data['findings']:
            if row['source_id'] is not None:
                self.assertIn(row['source_id'], ids)
            self.assertLessEqual(set(row['related_ids']), ids)
        self.assertEqual(len({f['id'] for f in data['findings']}), len(data['findings']))

    def test_private_markup_and_unicode_retained_and_json_round_trip_is_canonical(self) -> None:
        marker = '</script><img src=x onerror="invented()">\u2028\u2029\u00e9'
        args = fixture(comment=marker, sfc='<SFCContent><TextBox ID="1"><Text><![CDATA['
                       + marker + ']]></Text></TextBox></SFCContent>')
        data = build_review_data(*args)
        self.assertEqual(data['inventory']['rungs'][0]['comment'], marker)
        self.assertEqual(data['sfc']['elements'][1]['direct_text'], marker)
        decoded = json.loads(render_review_json(data))
        self.assertEqual(decoded, data)
        validate_review_data(*args, decoded)
        self.assertNotIn('data', data['snapshot'])

    def test_orphan_diagnostic_retains_exact_locator_without_inventing_source_id(self) -> None:
        snapshot = snapshot_from_bytes(b'<RSLogix5000Content><Vendor><Tag Name="Orphan"/>'
                                       b'</Vendor></RSLogix5000Content>')
        inventory = analyze_snapshot(snapshot)
        references = analyze_references(inventory)
        sfc = analyze_sfc_structure(snapshot, inventory)
        data = build_review_data(snapshot, inventory, references, sfc)
        orphan = next(row for row in data['findings']
                      if row['code'] == 'declaration_context_not_analyzed')
        original = next(row for row in inventory.diagnostics if row.code == orphan['code'])
        self.assertIsNone(orphan['source_id'])
        self.assertEqual(orphan['related_ids'], [])
        self.assertEqual(orphan['locator'], original.locator)
        self.assertEqual(orphan['locator'], '/RSLogix5000Content[1]/Vendor[1]/Tag[1]')
        self.assertTrue(all('locator' in row for row in data['findings']))
        derived = build_review_data(*fixture(('XIC(Missing);',),
            tags='<Tag Name="Alias" TagType="Alias" AliasFor="Missing"/>'))
        alias = next(row for row in derived['findings'] if row['origin'] == 'alias')
        alias_entity = next(row for row in derived['inventory']['entities']
                            if row['id'] == alias['source_id'])
        self.assertEqual(alias['locator'], alias_entity['locator'])
        operand = next(row for row in derived['findings'] if row['origin'] == 'operand')
        self.assertIsNone(operand['locator'])

    def test_canonical_replay_rejects_input_tampering_cycles_and_mixed_snapshots(self) -> None:
        snapshot, inventory, references, sfc = fixture(sfc='<SFCContent><Step ID="1"/></SFCContent>')
        altered = replace(inventory, rungs=[replace(inventory.rungs[0], comment='PRIVATE_TAMPER')])
        wrong_refs = replace(references, operands=[])
        wrong_sfc = replace(sfc, elements=[])
        cycle: list = []
        cycle.append(cycle)
        for changed in (
            (snapshot, altered, references, sfc),
            (snapshot, inventory, wrong_refs, sfc),
            (snapshot, inventory, references, wrong_sfc),
            (snapshot, inventory, replace(references, operands=cycle), sfc),
            (replace(snapshot, size_bytes=True), inventory, references, sfc),
            (snapshot_from_bytes(snapshot.data + b' '), inventory, references, sfc),
        ):
            with self.subTest(case=changed[0].size_bytes), self.assertRaises(ReviewError) as caught:
                build_review_data(*changed)
            self.assertNotIn('PRIVATE_TAMPER', str(caught.exception))

    def test_canonical_payload_validation_rejects_all_fields_extra_keys_and_boolean_counts(self) -> None:
        args = fixture()
        canonical = build_review_data(*args)
        for field in canonical:
            candidate = deepcopy(canonical)
            candidate[field] = None
            with self.subTest(field=field), self.assertRaises(ReviewError):
                validate_review_data(*args, candidate)
        for candidate in (dict(canonical, unexpected='PRIVATE_EXTRA'),
                          dict(canonical, schema_version=True)):
            with self.assertRaises(ReviewError):
                validate_review_data(*args, candidate)
        candidate = deepcopy(canonical)
        candidate['statistics']['rungs'] = True
        with self.assertRaises(ReviewError):
            validate_review_data(*args, candidate)
        candidate = deepcopy(canonical)
        candidate['inventory'] = candidate
        with self.assertRaises(ReviewError):
            validate_review_data(*args, candidate)

    def test_exact_utf8_budget_and_independent_row_limits(self) -> None:
        args = fixture(('XIC(PRIVATE_UNKNOWN);',), comment='\u00e9' * 3)
        data = build_review_data(*args)
        exact = len(render_review_json(data).encode('utf-8'))
        with patch('plc_workbench.review.MAX_REVIEW_BYTES', exact):
            self.assertEqual(build_review_data(*args), data)
            self.assertEqual(len(render_review_json(data).encode('utf-8')), exact)
        with patch('plc_workbench.review.MAX_REVIEW_BYTES', exact - 1):
            with self.assertRaises(ReviewError):
                build_review_data(*args)
            with self.assertRaises(ReviewError):
                render_review_json(data)
        for limit in ('MAX_REVIEW_FINDINGS', 'MAX_REVIEW_PATTERNS'):
            with patch(f'plc_workbench.review.{limit}', 0), self.assertRaises(ReviewError) as caught:
                build_review_data(*args)
            self.assertNotIn('PRIVATE_UNKNOWN', str(caught.exception))

    def test_immutable_capture_no_filesystem_read_and_deterministic_snapshot_scoped_ids(self) -> None:
        args = fixture()
        before = (args[1].to_dict(), args[2].to_dict(), args[3].to_dict())
        with patch.object(Path, 'open', side_effect=AssertionError('Unexpected filesystem access')):
            first = build_review_data(*args)
            self.assertEqual(first, build_review_data(*args))
        self.assertEqual(before, (args[1].to_dict(), args[2].to_dict(), args[3].to_dict()))
        changed = fixture(comment='Other captured bytes')
        other = build_review_data(*changed)
        self.assertEqual(first['patterns'][0]['shape'], other['patterns'][0]['shape'])
        self.assertNotEqual(first['patterns'][0]['id'], other['patterns'][0]['id'])


if __name__ == '__main__':
    unittest.main()
