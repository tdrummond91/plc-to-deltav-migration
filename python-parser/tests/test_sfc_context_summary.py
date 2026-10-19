"""Closed summary conservation and source privacy for invented SFC context."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from plc_workbench.sfc_context_summary import (SfcContextSummaryError,
    build_sfc_context_summary, render_sfc_context_summary, validate_sfc_context_summary)
from test_sfc_context import capture, step, transition
from test_sfc_context import capture_xml, fixture
from test_rack_candidates import LOCAL, card, tag


class SfcContextSummaryTests(unittest.TestCase):
    def test_summary_round_trip_covers_parsed_missing_and_unsupported(self):
        for args in (capture(body=''), capture(body=step() + transition('State.X OR Missing'), rungs=('OTE(State.X);',)), capture(text='A := 1')):
            with self.subTest(status=args[-1].status):
                summary = build_sfc_context_summary(*args)
                self.assertEqual(summary, json.loads(render_sfc_context_summary(summary)))
                self.assertEqual(summary['coverage'], args[-1].coverage)

    def test_summary_contains_no_source_spelling_ids_paths_or_added_keys(self):
        summary = build_sfc_context_summary(*capture(text='UnsharedPlantName'))
        rendered = render_sfc_context_summary(summary)
        self.assertNotIn('UnsharedPlantName', rendered)
        self.assertNotIn('root_text', rendered)
        self.assertNotIn('snapshot', rendered)
        for location in (summary, summary['coverage'], summary['coverage']['gaps_by_kind']):
            location['source'] = 'DO_NOT_EXPORT'
            with self.assertRaises(SfcContextSummaryError):
                render_sfc_context_summary(summary)

            del location['source']

    def test_all_closed_counts_reject_bool_float_negative_and_excessive(self):
        summary = build_sfc_context_summary(*capture())
        for bad in (True, 1.0, -1, 10**12 + 1):
            for key in ('references_total', 'references_by_status'):
                changed = deepcopy(summary)
                if key == 'references_by_status':
                    changed['coverage'][key]['exact_address'] = bad
                else:
                    changed['coverage'][key] = bad
                with self.subTest(value=bad, key=key), self.assertRaises(SfcContextSummaryError):
                    validate_sfc_context_summary(changed)

    def test_conservation_rejects_source_mismatch_and_fabricated_associations(self):
        summary = build_sfc_context_summary(*capture(body=step() + transition('State.X OR Missing'), rungs=('OTE(State.X);',)))
        for key in ('references_total', 'source_references', 'addresses_total', 'step_links_total',
                    'gaps_total', 'gaps_with_lexical_steps', 'accepted_expression_uses',
                    'outside_scope_declarations', 'addresses_with_rll_readers', 'unqualified_step_links',
                    'references_with_multiple_steps'):
            changed = deepcopy(summary)
            changed['coverage'][key] += 100
            with self.subTest(key=key), self.assertRaises(SfcContextSummaryError):
                validate_sfc_context_summary(changed)

    def test_reference_roles_and_steps_are_conserved_independently(self):
        summary = build_sfc_context_summary(*capture(body=step() + transition('State.X'), rungs=('OTE(State.X);',)))
        for key, child in [('accepted_operands_by_role', 'write'), ('step_links_by_evidence', 'lexical_hint'),
                           ('step_links_by_relation', 'peer_chart'), ('step_links_by_match', 'exact'),
                           ('gaps_by_kind', 'root_missing')]:
            changed = deepcopy(summary)
            changed['coverage'][key][child] += 1
            with self.subTest(key=key), self.assertRaises(SfcContextSummaryError):
                validate_sfc_context_summary(changed)

    def test_revision_status_and_literal_types_are_strict(self):
        summary = build_sfc_context_summary(*capture(), revision={'commit': 'a' * 40, 'worktree': 'modified'})
        validate_sfc_context_summary(summary)
        mutations = [('schema_version', True), ('status', 'partial'), ('tool_revision', {'commit': None, 'worktree': 'clean'})]
        for key, value in mutations:
            changed = deepcopy(summary)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(SfcContextSummaryError):
                validate_sfc_context_summary(changed)

    def test_build_authenticates_context_and_output_caps_are_source_free(self):
        args = capture()
        args[-1].addresses[0]['suffix'] = '.FORGED'
        with self.assertRaises(SfcContextSummaryError):
            build_sfc_context_summary(*args)
        summary = build_sfc_context_summary(*capture())
        with patch('plc_workbench.sfc_context_summary.MAX_REPORT_BYTES', 1):
            with self.assertRaisesRegex(SfcContextSummaryError, '^SFC context summary validation failed; no summary was produced[.]$'):
                render_sfc_context_summary(summary)


class SfcGapDiagnosticSummaryTests(unittest.TestCase):
    def build(self, **kwargs):
        return build_sfc_context_summary(*capture(**kwargs), schema_version=2)

    def test_version_two_keeps_prior_coverage_and_authentication(self):
        args = capture(text='Missing OR Alias', tags=tag('Alias', 'OtherMissing'))
        old = build_sfc_context_summary(*args)
        current = build_sfc_context_summary(*args, schema_version=2)
        self.assertEqual(current['coverage'], old['coverage'])
        self.assertEqual(current['status'], old['status'])
        self.assertEqual(current['gap_diagnostics']['binding_reasons']['root_not_declared'], 2)
        self.assertEqual(current['gap_diagnostics']['alias_gap_references'], 1)
        self.assertEqual(current['gap_diagnostics']['alias_rack_matches']['not_applicable'], 1)
        self.assertEqual(json.loads(render_sfc_context_summary(current)), current)
        args[-1].gaps[0]['root_text'] = 'FORGED'
        with self.assertRaises(SfcContextSummaryError):
            build_sfc_context_summary(*args, schema_version=2)

    def test_shared_terminal_alias_and_rack_candidate_are_not_multiplied(self):
        summary = self.build(text='First OR Second OR First',
            tags=tag('First', 'Terminal') + tag('Second', 'Terminal') + tag('Terminal', 'Local:3:I.Data.0'),
            modules=LOCAL + card())
        d = summary['gap_diagnostics']
        self.assertEqual((d['alias_gap_references'], d['distinct_terminal_aliases']), (3, 1))
        self.assertEqual(d['alias_rack_matches']['unique_candidate'], 3)
        self.assertEqual(d['unique_rack_match_directions'], {'input': 3, 'output': 0})
        self.assertEqual(d['distinct_unique_rack_candidates'], 1)
        self.assertEqual(summary['coverage']['references_by_status']['binding_gap'], 3)
        self.assertEqual(summary['coverage']['references_by_status']['exact_address'], 0)

    def test_distinct_aliases_can_share_candidate_and_input_output_are_separate(self):
        summary = self.build(text='InputA OR InputB OR Output', modules=LOCAL + card(),
            tags=tag('InputA', 'Local:3:I.Data.0') + tag('InputB', 'Local:3:I.Data.1') + tag('Output', 'Local:3:O.Data.0'))
        d = summary['gap_diagnostics']
        self.assertEqual(d['distinct_terminal_aliases'], 3)
        self.assertEqual(d['distinct_unique_rack_candidates'], 2)
        self.assertEqual(d['unique_rack_match_directions'], {'input': 2, 'output': 1})

    def test_rack_missing_ambiguous_and_unavailable_stay_distinct(self):
        for modules, expected in ((LOCAL, 'no_candidate_match'),
                (LOCAL + card() + card('Duplicate'), 'ambiguous_candidate'),
                (LOCAL + card(port_type='Ethernet'), 'candidate_names_unavailable')):
            with self.subTest(expected=expected):
                d = self.build(text='Alias', tags=tag('Alias', 'Local:3:I.Data.0'), modules=modules)['gap_diagnostics']
                self.assertEqual(d['alias_rack_matches'][expected], 1)
                self.assertEqual(d['distinct_unique_rack_candidates'], 0)

    def test_program_shadow_does_not_change_controller_alias_lookup_scope(self):
        summary = self.build(text='Alias', modules=LOCAL + card(),
            tags=tag('Alias', 'Local:3:I.Data.0'), local=tag('Local:3:I'))
        self.assertEqual(summary['gap_diagnostics']['alias_rack_matches']['unique_candidate'], 1)
        self.assertEqual(summary['coverage']['references_by_status']['binding_gap'], 1)

    def test_rack_outside_controller_scope_never_becomes_visible(self):
        xml = fixture(text='Alias', tags=tag('Alias', 'Local:3:I.Data.0'))
        other = f'<Controller Name="Other"><Modules>{LOCAL + card()}</Modules></Controller>'
        args = capture_xml(xml.replace('</RSLogix5000Content>', other + '</RSLogix5000Content>'))
        summary = build_sfc_context_summary(*args, schema_version=2)
        self.assertEqual(summary['gap_diagnostics']['alias_rack_matches']['outside_visible_scope'], 1)
        self.assertEqual(summary['gap_diagnostics']['distinct_unique_rack_candidates'], 0)

    def test_unsupported_alias_and_cycle_retain_closed_reason_categories(self):
        cases = [('Dynamic', 'Array[A]', 'non_static_array_index'),
                 ('Qualified', 'Program:P.Tag', 'program_qualified_address'),
                 ('Empty', '', 'empty_address'), ('Cycle', 'Cycle', 'none')]
        for name, target, expected in cases:
            with self.subTest(expected=expected):
                d = self.build(text=name, tags=tag(name, target))['gap_diagnostics']
                self.assertEqual(d['binding_reasons'][expected], 1)
                self.assertEqual(d['alias_rack_matches']['not_applicable'], 1)

    def test_namespace_excluded_alias_does_not_promote_rack_hint(self):
        summary = self.build(text='Alias', modules=LOCAL + card(),
            tags='<Tag Name="Alias" TagType="Alias" AliasFor="Local:3:I.Data.0" x:Marker="foreign"/>')
        self.assertEqual(summary['coverage']['references_by_status']['namespace_gap'], 1)
        self.assertEqual(summary['gap_diagnostics']['alias_rack_matches']['not_applicable'], 1)

    def test_rack_counts_retain_legacy_lexical_policy_without_claiming_qualification(self):
        modules = LOCAL + card().replace('<Module Name="Card"', '<Module x:Marker="foreign" Name="Card"')
        summary = self.build(text='Alias', modules=modules, tags=tag('Alias', 'Local:3:I.Data.0'))
        self.assertEqual(summary['gap_diagnostics']['alias_rack_matches']['unique_candidate'], 1)
        self.assertEqual(summary['coverage']['references_by_status']['binding_gap'], 1)
        self.assertEqual(summary['coverage']['references_by_status']['exact_address'], 0)

    def test_empty_and_bound_only_sources_have_zero_diagnostics(self):
        for text in ('1', 'A'):
            d = self.build(text=text)['gap_diagnostics']
            self.assertFalse(any(v if type(v) is int else sum(v.values()) for v in d.values()))

    def test_numeric_types_and_conservation_are_strict(self):
        summary = self.build(text='Alias', tags=tag('Alias', 'Local:3:I.Data.0'), modules=LOCAL + card())
        changes = [lambda d: d.update(alias_gap_references=2),
                   lambda d: d.update(distinct_terminal_aliases=0),
                   lambda d: d.update(distinct_unique_rack_candidates=0),
                   lambda d: d['binding_reasons'].update(root_not_declared=1),
                   lambda d: d['alias_rack_matches'].update(no_record=1),
                   lambda d: d['unique_rack_match_directions'].update(output=1)]
        for change in changes:
            candidate = deepcopy(summary)
            change(candidate['gap_diagnostics'])
            with self.assertRaises(SfcContextSummaryError):
                validate_sfc_context_summary(candidate)
        for value in (True, 1.0, -1, 10**12 + 1):
            candidate = deepcopy(summary)
            candidate['gap_diagnostics']['distinct_terminal_aliases'] = value
            with self.assertRaises(SfcContextSummaryError):
                validate_sfc_context_summary(candidate)

    def test_versions_unknown_fields_and_source_text_are_closed(self):
        args = capture(text='SecretAlias', tags=tag('SecretAlias', 'SecretTarget'))
        summary = build_sfc_context_summary(*args, schema_version=2)
        rendered = render_sfc_context_summary(summary)
        self.assertNotIn('Secret', rendered)
        for version in (True, 0, 3):
            with self.assertRaises(SfcContextSummaryError):
                build_sfc_context_summary(*args, schema_version=version)
        for change in (lambda s: s.update(schema_version=1),
                       lambda s: s['gap_diagnostics'].update(raw='Secret'),
                       lambda s: s['gap_diagnostics']['binding_reasons'].update(Secret=1),
                       lambda s: s.pop('gap_diagnostics')):
            candidate = deepcopy(summary)
            change(candidate)
            with self.assertRaises(SfcContextSummaryError):
                validate_sfc_context_summary(candidate)


if __name__ == '__main__':
    unittest.main()
