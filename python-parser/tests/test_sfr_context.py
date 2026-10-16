"""Invented SFR calls preserve chart edits and uncertain target identities."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from plc_workbench.access import analyze_access
from plc_workbench.calculations import analyze_calculations
from plc_workbench.references import analyze_references
from plc_workbench.sfc_structure import analyze_sfc_structure
from plc_workbench.sfr_context import (
    SfrContextError, analyze_sfr_context, render_sfr_context_json, validate_sfr_context,
)
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes


def tag(name='PrivateStep', alias=None):
    attributes = f'TagType="Alias" AliasFor="{alias}"' if alias else 'TagType="Base" DataType="SFC_STEP"'
    return f'<Tag Name="{name}" {attributes}/>'


def step(operand='PrivateStep', initial='false', identifier='1', attributes=''):
    operand = '' if operand is None else f' Operand="{operand}"'
    initial = '' if initial is None else f' InitialStep="{initial}"'
    return f'<Step ID="{identifier}"{operand}{initial} {attributes}/>'


def chart(body=None, name='PrivateChart', language='SFC', attributes=''):
    if body is None:
        body = f'<SFCContent>{step()}</SFCContent>'
    return f'<Routine Name="{name}" Type="{language}" {attributes}>{body}</Routine>'


def routine(text='SFR(PrivateChart,PrivateStep);', name='PrivateRun'):
    return (f'<Routine Name="{name}" Type="RLL"><RLLContent><Rung Number="0" Type="N">'
            f'<Text><![CDATA[{text}]]></Text></Rung></RLLContent></Routine>')


def program(text='SFR(PrivateChart,PrivateStep);', charts=None, tags=None, name='PrivateProgram'):
    return (f'<Program Name="{name}"><Tags>{tag() if tags is None else tags}</Tags><Routines>'
            f'{routine(text)}{chart() if charts is None else charts}</Routines></Program>')


def document(programs=None, controller_tags='', extra='', attributes=''):
    return (f'<RSLogix5000Content {attributes}><Controller Name="PrivateController"><Tags>{controller_tags}</Tags>'
            f'<Programs>{program() if programs is None else programs}</Programs>{extra}'
            '</Controller></RSLogix5000Content>')


def capture(xml=None, access_version=4):
    snapshot = snapshot_from_bytes((document() if xml is None else xml).encode())
    inventory = analyze_snapshot(snapshot)
    references = analyze_references(inventory)
    calculations = analyze_calculations(snapshot, inventory, references)
    access = analyze_access(inventory, references, schema_version=access_version,
                            **({'snapshot': snapshot, 'calculations': calculations} if access_version == 4 else {}))
    sfc = analyze_sfc_structure(snapshot, inventory)
    parts = (snapshot, inventory, references, access, calculations, sfc)
    return (*parts, analyze_sfr_context(*parts))


class SfrContextTests(unittest.TestCase):
    def test_unique_candidate_uses_existing_ids_and_preserves_companions(self):
        parts = capture()
        before = [deepcopy(part.to_dict()) for part in parts[1:-1]]
        result = parts[-1]
        call, step_row = result.calls[0], result.steps[0]
        self.assertEqual((call['routine_status'], call['chart_status']), ('unique_candidate', 'available'))
        self.assertEqual(call['content_matches'][0]['target_step_id'], step_row['element_id'])
        self.assertEqual(call['content_matches'][0]['status'], 'unique_candidate')
        self.assertEqual(step_row['element_id'], parts[5].elements[0]['id'])
        self.assertEqual(result.status, 'complete')
        self.assertEqual((result.execution, result.reset_effects, result.edit_selection), ('not_analyzed',) * 3)
        validate_sfr_context(*parts)
        self.assertEqual(before, [part.to_dict() for part in parts[1:-1]])
        self.assertEqual(json.loads(render_sfr_context_json(result)), result.to_dict())

    def test_three_and_four_access_versions_produce_same_context(self):
        self.assertEqual(capture(access_version=3)[-1], capture(access_version=4)[-1])

    def test_empty_source_and_no_sfr_calls_are_valid(self):
        result = capture(document(programs=''))[-1]
        self.assertEqual((result.calls, result.steps, result.status), ([], [], 'complete'))
        result = capture(document(program(text='XIC(PrivateStep);')))[-1]
        self.assertEqual((len(result.calls), len(result.steps)), (0, 1))

    def test_casefold_routine_and_instruction_names_are_ascii_only(self):
        result = capture(document(program(text='sfr(privatechart,privatestep)SFR(PRIVATECHART,PRIVATEstep);')))[-1]
        self.assertEqual([c['routine_status'] for c in result.calls], ['unique_candidate'] * 2)
        self.assertNotEqual(result.calls[0]['instruction_id'], result.calls[1]['instruction_id'])
        result = capture(document(program(text='ſFR(PrivateChart,PrivateStep);')))[-1]
        self.assertEqual(result.calls, [])
        result = capture(document(program(text='SFR(PrıvateChart,PrivateStep);')))[-1]
        self.assertEqual(result.calls[0]['routine_status'], 'unsupported_name')

    def test_signature_failures_are_retained_without_target_inference(self):
        result = capture(document(program(text='SFR()SFR(PrivateChart)SFR(PrivateChart,PrivateStep,1)'
                                               'SFR(,PrivateStep)SFR(PrivateChart,);')))[-1]
        self.assertEqual([c['signature_status'] for c in result.calls],
                         ['argument_count_mismatch'] * 3 + ['empty_argument'] * 2)
        self.assertTrue(all(c['routine_status'] == c['selector_kind'] == 'not_analyzed' for c in result.calls))
        self.assertTrue(all(not c['content_matches'] for c in result.calls))

    def test_other_programs_and_controllers_cannot_supply_routine_candidates(self):
        other = program(text='XIC(PrivateStep);', name='OtherProgram')
        value = document(program(charts='') + other)
        self.assertEqual(capture(value)[-1].calls[0]['routine_status'], 'missing_candidate')
        value = document(program(charts='')).replace('</RSLogix5000Content>',
            f'<Controller Name="Other"><Programs>{program(text="XIC(PrivateStep);")}</Programs></Controller></RSLogix5000Content>')
        self.assertEqual(capture(value)[-1].calls[0]['routine_status'], 'missing_candidate')

    def test_duplicate_routine_name_is_ambiguous_before_language_filtering(self):
        value = document(program(charts=chart() + chart('', language='RLL')))
        row = capture(value)[-1].calls[0]
        self.assertEqual((row['routine_status'], row['routine_candidate_count']), ('ambiguous_candidate', 2))
        self.assertIsNone(row['target_routine_id'])
        self.assertEqual(row['content_matches'], [])

    def test_target_languages_missing_content_and_protection_remain_distinct(self):
        cases = ((chart('', language='RLL'), 'not_sfc'), (chart(''), 'missing_content'),
                 (chart('<EncodedData>PrivateEncoded</EncodedData>'), 'protected'),
                 (chart('<SFCContent/>' + '<EncryptedContent/>'), 'protected'),
                 (chart(attributes='SourceKey="PrivateKey"'), 'protected'),
                 (chart('<SFCContent/><Vendor/>'), 'unsupported_context'))
        for charts, status in cases:
            with self.subTest(status=status):
                row = capture(document(program(charts=charts)))[-1].calls[0]
                self.assertEqual(row['chart_status'], status)
                self.assertEqual(row['content_matches'], [])

    def test_qualified_dynamic_and_malformed_routine_selectors_stay_unsupported(self):
        for name in ('Program:Other.PrivateChart', 'PrivateChart[1]', '"PrivateChart"', 'x' * 65):
            with self.subTest(name=name):
                row = capture(document(program(text=f'SFR({name},PrivateStep);')))[-1].calls[0]
                self.assertEqual(row['routine_status'], 'unsupported_name')

    def test_step_operand_not_name_or_numeric_block_id_supplies_identity(self):
        body = '<SFCContent><Step ID="1" Name="PrivateStep" InitialStep="false"/></SFCContent>'
        result = capture(document(program(charts=chart(body))))[-1]
        self.assertEqual(result.steps[0]['binding_status'], 'missing_operand')
        self.assertEqual(result.calls[0]['content_matches'][0]['status'], 'incomplete_context')

    def test_alias_and_exact_expanded_static_suffix_match(self):
        tags = tag('Container') + tag('PrivateStep', 'Container.Member[0]') + tag('OtherAlias', 'Container.Member[0]')
        body = f'<SFCContent>{step("OtherAlias")}</SFCContent>'
        result = capture(document(program(tags=tags, charts=chart(body))))[-1]
        self.assertEqual(result.calls[0]['content_matches'][0]['status'], 'unique_candidate')
        self.assertEqual(result.steps[0]['suffix'], '.Member[0]')
        self.assertEqual(len(result.steps[0]['alias_chain']), 1)
        # Different member spellings/array representations remain distinct;
        # this slice does not normalize numeric indices or member casing.
        for suffix in ('.Member[00]', '.member[0]', '.Member[1]'):
            changed = tags.replace('Name="OtherAlias" TagType="Alias" AliasFor="Container.Member[0]"',
                                   f'Name="OtherAlias" TagType="Alias" AliasFor="Container{suffix}"')
            with self.subTest(suffix=suffix):
                result = capture(document(program(tags=changed, charts=chart(body))))[-1]
                self.assertEqual(result.calls[0]['content_matches'][0]['status'], 'missing_candidate')

    def test_scope_shadowing_and_root_alias_targets_keep_correct_identity(self):
        tags = tag() + tag('PrivateAlias', 'PrivateStep')
        body = f'<SFCContent>{step("PrivateAlias")}</SFCContent>'
        parts = capture(document(program(tags=tags, charts=chart(body)), controller_tags=tag()))
        row = parts[-1].steps[0]
        target = next(e for e in parts[1].entities if e.id == row['target_id'])
        self.assertEqual(next(e for e in parts[1].entities if e.id == target.scope_id).kind, 'program')
        self.assertEqual(parts[-1].calls[0]['content_matches'][0]['status'], 'unique_candidate')

    def test_duplicate_step_operands_are_ambiguous_not_filtered(self):
        body = f'<SFCContent>{step()}{step(identifier="2")}</SFCContent>'
        match = capture(document(program(charts=chart(body))))[-1].calls[0]['content_matches'][0]
        self.assertEqual((match['status'], match['candidate_count']), ('ambiguous_candidate', 2))
        self.assertEqual(len(match['candidate_step_ids']), 2)
        self.assertIsNone(match['target_step_id'])

    def test_bad_step_operand_blocks_false_unique_candidate(self):
        bad = (None, '', 'Missing', 'PrivateStep[Unknown]', '1')
        for operand in bad:
            with self.subTest(operand=operand):
                body = f'<SFCContent>{step()}{step(operand, identifier="2")}</SFCContent>'
                result = capture(document(program(charts=chart(body))))[-1]
                match = result.calls[0]['content_matches'][0]
                self.assertEqual((match['status'], match['candidate_count']), ('incomplete_context', 1))
                self.assertIsNone(match['target_step_id'])

    def test_unresolved_named_selectors_and_invalid_alias_composition_are_explicit(self):
        for operand in ('Missing', 'PrivateStep[Index]', '1', '00', '+0', '0.0'):
            with self.subTest(operand=operand):
                result = capture(document(program(text=f'SFR(PrivateChart,{operand});')))[-1]
                call = result.calls[0]
                self.assertEqual(call['selector_kind'], 'named')
                self.assertEqual(call['content_matches'][0]['status'], 'selector_unresolved')
        tags = tag() + tag('Alias', 'PrivateStep.0')
        result = capture(document(program(text='SFR(PrivateChart,Alias.Member);', tags=tags)))[-1]
        self.assertEqual(result.calls[0]['selector_binding_status'], 'invalid_identity')

    def test_alias_cycles_and_ambiguous_tag_declarations_are_explicit(self):
        for tags, status in ((tag('PrivateStep', 'PrivateStep'), 'alias_cycle'),
                             (tag() + tag(), 'ambiguous')):
            with self.subTest(status=status):
                result = capture(document(program(tags=tags)))[-1]
                self.assertEqual(result.steps[0]['binding_status'], status)
                self.assertEqual(result.calls[0]['selector_binding_status'], status)

    def test_initial_sentinel_uses_explicit_markers_and_never_import_normalizes(self):
        for initial, expected, count in (('true', 'unique_candidate', 1),
                                         ('false', 'missing_candidate', 0),
                                         ('TRUE', 'incomplete_context', 0),
                                         (None, 'incomplete_context', 0)):
            with self.subTest(initial=initial):
                body = f'<SFCContent>{step(initial=initial)}</SFCContent>'
                result = capture(document(program(text='SFR(PrivateChart, 0 );', charts=chart(body))))[-1]
                call, match = result.calls[0], result.calls[0]['content_matches'][0]
                self.assertEqual((call['selector_kind'], call['selector_binding_status']), ('initial', 'initial'))
                self.assertEqual((match['status'], match['candidate_count']), (expected, count))
        body = f'<SFCContent>{step(initial="true")}{step(initial="true", identifier="2")}</SFCContent>'
        result = capture(document(program(text='SFR(PrivateChart,0);', charts=chart(body))))[-1]
        self.assertEqual(result.calls[0]['content_matches'][0]['status'], 'ambiguous_candidate')
        body = f'<SFCContent>{step(initial="true")}{step(initial=None, identifier="2")}</SFCContent>'
        result = capture(document(program(text='SFR(PrivateChart,0);', charts=chart(body))))[-1]
        self.assertEqual(result.calls[0]['content_matches'][0]['status'], 'incomplete_context')

    def test_all_edit_contents_stay_separate_and_no_active_version_selected(self):
        body = (f'<SFCContent OnlineEditType="Original">{step()}</SFCContent>'
                f'<SFCContent OnlineEditType="PendingEdits">{step()}</SFCContent>'
                '<SFCContent OnlineEditType="TestEdits"/>')
        result = capture(document(program(charts=chart(body))))[-1]
        matches = result.calls[0]['content_matches']
        self.assertEqual([m['edit_kind'] for m in matches], ['Original', 'PendingEdits', 'TestEdits'])
        self.assertEqual([m['status'] for m in matches], ['unique_candidate', 'unique_candidate', 'missing_candidate'])
        self.assertNotEqual(matches[0]['target_step_id'], matches[1]['target_step_id'])
        self.assertEqual((result.coverage['matched_calls'], result.coverage['fully_matched_calls'],
                          result.coverage['multiple_content_calls']), (1, 0, 1))

    def test_foreign_routine_and_alias_contexts_never_prove_target(self):
        for body, chart_status in ((chart(attributes='x:Private="yes"'), 'unsupported_context'),):
            result = capture(document(program(charts=body), attributes='xmlns:x="urn:vendor"'))[-1]
            self.assertEqual(result.calls[0]['chart_status'], chart_status)
        charts = chart() + chart(attributes='x:Private="yes"')
        result = capture(document(program(charts=charts), attributes='xmlns:x="urn:vendor"'))[-1]
        self.assertEqual(result.calls[0]['routine_status'], 'ambiguous_candidate')
        tags = tag().replace('TagType=', 'x:TagType=')
        result = capture(document(program(tags=tags), attributes='xmlns:x="urn:vendor"'))[-1]
        self.assertEqual(result.steps[0]['binding_status'], 'unsupported_context')

    def test_foreign_nested_chart_elements_and_rung_text_stay_unsupported(self):
        body = f'<SFCContent>{step()}<x:Vendor><Step ID="2" Operand="PrivateStep"/></x:Vendor></SFCContent>'
        result = capture(document(program(charts=chart(body)), attributes='xmlns:x="urn:vendor"'))[-1]
        self.assertEqual(result.calls[0]['content_matches'][0]['status'], 'unsupported_context')
        xml = document(attributes='xmlns:x="urn:vendor"').replace('<Text>', '<x:Text>').replace('</Text>', '</x:Text>')
        result = capture(xml)[-1]
        self.assertEqual(result.calls[0]['routine_status'], 'unsupported_context')

    def test_common_root_namespace_remains_supported(self):
        result = capture(document(attributes='xmlns="urn:invented:l5x"'))[-1]
        self.assertEqual(result.calls[0]['content_matches'][0]['status'], 'unique_candidate')

    def test_aoi_calling_context_is_not_mistaken_for_program_scope(self):
        aoi = ('<AddOnInstructionDefinitions><AddOnInstructionDefinition Name="Toy">'
               f'<Routines>{routine()}{chart()}</Routines></AddOnInstructionDefinition></AddOnInstructionDefinitions>')
        result = capture(document(programs='', extra=aoi))[-1]
        self.assertEqual(result.calls[0]['routine_status'], 'unsupported_context')
        self.assertIsNone(result.calls[0]['program_id'])

    def test_canonical_companions_result_ids_counts_and_types_are_authenticated(self):
        parts = capture()
        for index, field, value in ((0, 'size_bytes', True), (1, 'status', 'invented'),
                                    (2, 'status', 'invented'), (3, 'status', 'invented'),
                                    (4, 'status', 'invented'), (5, 'status', 'invented')):
            mutated = list(parts[:-1]); mutated[index] = replace(mutated[index], **{field: value})
            with self.subTest(index=index), self.assertRaises(SfrContextError):
                analyze_sfr_context(*mutated)
        for field, value in (('schema_version', True), ('status', 'partial'), ('steps', [])):
            with self.subTest(field=field), self.assertRaises(SfrContextError):
                validate_sfr_context(*parts[:-1], replace(parts[-1], **{field: value}))
        calls = deepcopy(parts[-1].calls); calls[0]['content_matches'][0]['target_step_id'] = 'invented'
        with self.assertRaises(SfrContextError):
            validate_sfr_context(*parts[:-1], replace(parts[-1], calls=calls))

    def test_resource_errors_are_fixed_and_cyclic_renderer_fails_safely(self):
        for name, value in (('MAX_CONTEXT_BYTES', 10), ('MAX_RECORDS', 0)):
            with self.subTest(name=name), patch(f'plc_workbench.sfr_context.{name}', value):
                with self.assertRaises(SfrContextError) as error:
                    capture()
                self.assertNotIn('Private', str(error.exception))
        result = capture()[-1]
        cyclic = []; cyclic.append(cyclic)
        with self.assertRaises(SfrContextError):
            render_sfr_context_json(replace(result, calls=cyclic))
        exact = len(render_sfr_context_json(result))
        with patch('plc_workbench.sfr_context.MAX_CONTEXT_BYTES', exact):
            self.assertEqual(len(render_sfr_context_json(result)), exact)
        with patch('plc_workbench.sfr_context.MAX_CONTEXT_BYTES', exact - 1):
            with self.assertRaises(SfrContextError): render_sfr_context_json(result)

    def test_generated_demo_runs_without_duplicating_source_names(self):
        path = Path(__file__).resolve().parents[2] / 'public/fixtures/synthetic/stateful_sequence_demo.L5X'
        if not path.exists():
            self.skipTest('Companion synthetic report fixture has not been added yet.')
        result = capture(path.read_text(encoding='utf-8'))[-1]
        self.assertEqual(result.coverage['calls_total'], 8)
        self.assertEqual(result.coverage['source_sfc_routines'], 3)
        self.assertEqual(result.coverage['source_sfc_contents'], 4)


if __name__ == '__main__':
    unittest.main()
