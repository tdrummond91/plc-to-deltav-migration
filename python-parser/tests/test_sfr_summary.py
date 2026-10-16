"""SFR publication summaries contain closed counts only, never source records."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import unittest
from unittest.mock import patch

from plc_workbench.sfr_summary import (
    SfrSummaryError, build_sfr_summary, render_sfr_summary, validate_sfr_summary,
)
from test_sfr_context import capture, chart, document, gap_document, program, step, tag


def summary(xml=None, schema_version=1, **kwargs):
    return build_sfr_summary(*capture(xml, schema_version=schema_version), **kwargs)


class SfrSummaryTests(unittest.TestCase):
    def test_schema_one_summary_bytes_are_frozen(self):
        rendered = render_sfr_summary(summary())
        self.assertEqual(hashlib.sha256(rendered.encode()).hexdigest(),
                         '0c4dfa604d09c8c0815984d15a2c36446fe42860d841aed6c3156126145fe619')

    def test_v2_summary_preserves_old_counts_and_contains_only_closed_gap_counts(self):
        old, newer = summary(gap_document()), summary(gap_document(), schema_version=2)
        self.assertEqual({key: newer['coverage'][key] for key in old['coverage']}, old['coverage'])
        c = newer['coverage']
        self.assertEqual((c['gap_contexts_total'], c['gap_candidate_links_total']), (1, 3))
        self.assertEqual(c['gap_candidate_links_by_kind'], {'same_content_root': 1, 'other_edit_exact': 1,
                                                          'peer_chart_exact': 1})
        text = render_sfr_summary(newer)
        self.assertLessEqual(len(text), 4096)
        self.assertEqual(json.loads(text), newer)
        for secret in ('Private', 'Container', 'Alias', 'Selected', 'target_id', 'step_ids', 'content_id'):
            self.assertNotIn(secret, text)
        self.assertEqual(newer['schema_version'], 2)
        self.assertEqual(newer['analyzer_version'], 'sfr-context-2')

    def test_v2_gap_population_and_candidate_counts_cannot_be_erased_or_invented(self):
        base = summary(gap_document(), schema_version=2)
        mutations = (
            lambda c: c.update(gap_contexts_total=0),
            lambda c: c['missing_matches_by_selector_kind'].update(named=0),
            lambda c: c['missing_matches_by_selector_kind'].update(named=0, initial=1),
            lambda c: c.update(gap_candidate_links_total=0),
            lambda c: c['gap_candidate_links_by_kind'].update(same_content_root=0),
            lambda c: c.update(gaps_with_candidates=0, gaps_with_no_candidates=1),
            lambda c: c.update(gap_peer_contents_total=0),
            lambda c: c['gap_peer_content_counts'].update(eligible=0),
            lambda c: c.update(gaps_with_excluded_peer_contents=1),
            lambda c: c.update(gap_peer_routines_without_content_total=1),
            lambda c: c.update(gaps_with_peer_routines_without_content=1),
        )
        for mutate in mutations:
            report = deepcopy(base); mutate(report['coverage'])
            with self.subTest(mutation=mutate), self.assertRaises(SfrSummaryError): validate_sfr_summary(report)

    def test_v2_peer_exclusions_and_empty_diagnostics_validate(self):
        body = f'<SFCContent>{step("Other")}</SFCContent>'
        charts = chart() + chart(body + '<EncodedData/>', name='Protected') + chart('', name='Missing')
        xml = document(program(text='SFR(PrivateChart,Other);', charts=charts, tags=tag() + tag('Other')))
        report = summary(xml, schema_version=2)
        self.assertEqual(report['coverage']['gap_peer_content_counts']['protected'], 1)
        self.assertEqual(report['coverage']['gap_peer_routines_without_content_total'], 1)
        validate_sfr_summary(report)
        for xml in (document(programs=''), document(), document(program(text='SFR(PrivateChart,0);'))):
            validate_sfr_summary(summary(xml, schema_version=2))

    def test_v2_cannot_be_downgraded_by_changing_version_constants_only(self):
        report = summary(gap_document(), schema_version=2)
        report.update(schema_version=1, analyzer_version='sfr-context-1', exporter_version='sfr-summary-1')
        with self.assertRaises(SfrSummaryError): validate_sfr_summary(report)
        report = summary()
        report.update(schema_version=2, analyzer_version='sfr-context-2', exporter_version='sfr-summary-2')
        with self.assertRaises(SfrSummaryError): validate_sfr_summary(report)

    def test_closed_report_is_small_and_never_exposes_names_or_identifiers(self):
        report = summary()
        text = render_sfr_summary(report)
        self.assertEqual(json.loads(text), report)
        self.assertLessEqual(len(text), 4096)
        self.assertEqual(text, render_sfr_summary(deepcopy(report)))
        for private in ('Private', 'snapshot', 'instruction_id', 'target_id', 'element_id', 'Operand', 'SFR('):
            self.assertNotIn(private, text)
        self.assertNotRegex(text, r'(?:routine_|instruction_|rung_)[0-9a-f]{64}')

    def test_supported_and_partial_populations_validate(self):
        cases = (document(programs=''), document(program(charts='')),
                 document(program(charts=chart() + chart())),
                 document(program(charts=chart('', language='RLL'))),
                 document(program(text='SFR(PrivateChart,0);')),
                 document(program(text='SFR(PrivateChart,1);')),
                 document(program(text='SFR(PrivateChart,Missing);')),
                 document(program(text='SFR(PrivateChart);')),
                 document(program(charts=chart('<EncodedData/>'))),
                 document(program(charts=chart(f'<SFCContent>{step(initial="other")}</SFCContent>'))))
        for xml in cases:
            with self.subTest(xml=xml): validate_sfr_summary(summary(xml))

    def test_mixed_edit_contents_conserve_matches_and_call_populations(self):
        body = (f'<SFCContent OnlineEditType="Original">{step()}</SFCContent>'
                f'<SFCContent OnlineEditType="PendingEdits">{step()}{step(identifier="2")}</SFCContent>')
        report = summary(document(program(text='SFR(PrivateChart,PrivateStep)SFR(PrivateChart,Missing);', charts=chart(body))))
        c = report['coverage']
        self.assertEqual((c['calls_total'], c['content_matches_total'], c['multiple_content_calls']), (2, 4, 2))
        self.assertEqual((c['matched_calls'], c['fully_matched_calls']), (1, 0))
        self.assertEqual(c['content_matches_by_status']['unique_candidate'], 1)
        self.assertEqual(c['content_matches_by_status']['ambiguous_candidate'], 1)
        self.assertEqual(c['content_matches_by_status']['selector_unresolved'], 2)
        validate_sfr_summary(report)

    def test_keys_fixed_constants_types_and_revision_are_strict(self):
        base = summary()
        mutations = (
            lambda r: r.update(raw_name='PrivateSecret'),
            lambda r: r.update(schema_version=True),
            lambda r: r.update(execution='analyzed'),
            lambda r: r.update(reset_effects='analyzed'),
            lambda r: r.update(edit_selection='Original'),
            lambda r: r.update(status='partial'),
            lambda r: r['coverage'].update(private_name='Secret'),
            lambda r: r['coverage']['steps_by_binding'].update(Secret=0),
            lambda r: r['coverage'].update(calls_total=True),
            lambda r: r['coverage'].update(calls_total=1.0),
            lambda r: r['coverage'].update(calls_total=-1),
            lambda r: r['coverage'].update(calls_total=250001),
            lambda r: r['tool_revision'].update(commit='PrivateSecret'),
        )
        for mutate in mutations:
            report = deepcopy(base); mutate(report)
            with self.subTest(mutation=mutate), self.assertRaises(SfrSummaryError): render_sfr_summary(report)

    def test_count_conservation_cannot_invent_or_erase_target_context(self):
        base = summary()
        mutations = (
            lambda c: c.update(calls_total=2), lambda c: c.update(source_rungs=0),
            lambda c: c.update(source_instructions=0), lambda c: c.update(source_operands=1),
            lambda c: c.update(source_sfc_routines=0), lambda c: c.update(source_sfc_contents=0),
            lambda c: c.update(source_sfc_steps=2), lambda c: c.update(steps_total=0),
            lambda c: c.update(content_matches_total=2), lambda c: c.update(matched_calls=0),
            lambda c: c.update(fully_matched_calls=0), lambda c: c.update(multiple_content_calls=1),
            lambda c: c['calls_by_signature'].update(classified=0, empty_argument=1),
            lambda c: c['calls_by_routine_status'].update(unique_candidate=0, missing_candidate=1),
            lambda c: c['calls_by_chart_status'].update(available=0, missing_content=1),
            lambda c: c['calls_by_selector_kind'].update(named=0, not_analyzed=1),
            lambda c: c['content_matches_by_status'].update(unique_candidate=0, ambiguous_candidate=1),
            lambda c: c['steps_by_binding'].update(root_bound=0),
            lambda c: c['initial_markers_by_kind'].update(false=0),
        )
        for mutate in mutations:
            report = deepcopy(base); mutate(report['coverage'])
            with self.subTest(mutation=mutate), self.assertRaises(SfrSummaryError): validate_sfr_summary(report)

    def test_revision_copy_and_result_authentication_are_preserved(self):
        revision = {'commit': 'f' * 40, 'worktree': 'clean'}
        report = summary(revision=revision)
        revision['worktree'] = 'modified'
        self.assertEqual(report['tool_revision']['worktree'], 'clean')
        parts = capture()
        with self.assertRaises(SfrSummaryError):
            build_sfr_summary(*parts[:-1], replace(parts[-1], calls=[]))

    def test_render_limit_and_boolean_counts_fail_without_source_leaks(self):
        report = summary()
        exact = len(render_sfr_summary(report))
        with patch('plc_workbench.sfr_summary.MAX_REPORT_BYTES', exact):
            self.assertEqual(len(render_sfr_summary(report)), exact)
        with patch('plc_workbench.sfr_summary.MAX_REPORT_BYTES', exact - 1):
            with self.assertRaises(SfrSummaryError) as error: render_sfr_summary(report)
            self.assertNotIn('Private', str(error.exception))
        report['coverage']['content_matches_by_status']['unique_candidate'] = True
        with self.assertRaises(SfrSummaryError): validate_sfr_summary(report)


if __name__ == '__main__':
    unittest.main()
