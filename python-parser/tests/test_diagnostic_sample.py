"""Single-operand diagnostics from invented XML only; no process/network IO."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch
from xml.sax.saxutils import quoteattr

from plc_workbench.diagnostic_sample import (
    DiagnosticSampleError, MAX_OPERAND_CHARS, build_diagnostic_sample, validate_diagnostic_sample,
    UNMATCHED_COLON_SAMPLE_KIND,
)
from plc_workbench.reference_summary import build_reference_summary, render_reference_summary
from plc_workbench.references import ReferenceError, analyze_references, validate_references
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes


def inventory(rungs: list[str], *, aliases: tuple[tuple[str, str], ...] = (),
              modules: str = '', extra: str = '', other_controllers: str = ''):
    tags = '<Tag Name="A" TagType="Base"/><Tag Name="Timer" TagType="Base"/>'
    tags += ''.join(f'<Tag Name={quoteattr(name)} TagType="Alias" AliasFor={quoteattr(target)}/>'
                    for name, target in aliases)
    tags += ('<Tag Name="PRIVATE_CONFIG_TAG" TagType="Base" DataType="REAL">'
             '<Data Format="L5K"><![CDATA[84739.125]]></Data></Tag>')
    ladder = ''.join(f'<Rung Number="{index + 700}" Type="N"><Comment>PRIVATE_COMMENT</Comment>'
                     f'<Text><![CDATA[{text}]]></Text></Rung>' for index, text in enumerate(rungs))
    source = (f'<RSLogix5000Content Owner="PRIVATE_OWNER"><Controller Name="PRIVATE_CONTROLLER">'
              f'<Modules>{modules}</Modules><Tags>{tags}</Tags><Programs><Program Name="PRIVATE_PROGRAM"><Routines>'
              f'<Routine Name="PRIVATE_ROUTINE" Type="RLL"><RLLContent>{ladder}</RLLContent>'
              f'</Routine></Routines></Program></Programs>{extra}</Controller>'
              f'{other_controllers}</RSLogix5000Content>')
    return analyze_snapshot(snapshot_from_bytes(source.encode("utf-8")))


def sample(raw_text: str = "?", *, opcode: str = "TON", argument_index: int = 1) -> dict:
    return {"kind": "direct_malformed_operand", "opcode": opcode,
            "argument_index": argument_index, "raw_text": raw_text}


def colon_sample(raw_text: str = 'Unknown:3:I.Data.2', *, opcode: str = 'XIC',
                 argument_index: int = 0) -> dict:
    return {'kind': UNMATCHED_COLON_SAMPLE_KIND, 'opcode': opcode,
            'argument_index': argument_index, 'raw_text': raw_text}


def rack_modules(*, aliases: int = 1, parent: str = 'Local') -> str:
    return ('<Module Name="Local" ParentModule="Local" ParentModPortId="1"><Ports>'
            '<Port Id="1" Type="ICP" Address="0" Upstream="false"/></Ports></Module>'
            f'<Module Name="Card" ParentModule="{parent}" ParentModPortId="1"><Ports>'
            '<Port Id="1" Type="ICP" Address="3" Upstream="true"/></Ports><Communications>'
            '<Connections><RackConnection>' + '<InAliasTag/>' * aliases +
            '</RackConnection></Connections></Communications></Module>')


class DiagnosticSampleTests(unittest.TestCase):
    def test_known_timer_placeholders_are_skipped_but_historical_samples_validate(self) -> None:
        source = inventory(["TON(Timer,?,?);", "TOF(Timer,?,?);", "RTO(Timer,?,?);"])
        self.assertIsNone(build_diagnostic_sample(source, analyze_references(source)))
        validate_diagnostic_sample(sample())
        source = inventory(["TON(Timer,?,?);", "XIC(Next?);"])
        self.assertEqual(build_diagnostic_sample(source, analyze_references(source)),
                         sample("Next?", opcode="XIC", argument_index=0))

    def test_malformed_operand_is_one_exact_operand_without_neighboring_context(self) -> None:
        source = inventory(["TON(Timer,Preset?,654321)OTE(PRIVATE_NEIGHBOR);"])
        value = build_diagnostic_sample(source, analyze_references(source))
        self.assertEqual(value, sample("Preset?"))
        validate_diagnostic_sample(value)
        rendered = json.dumps(value)
        for excluded in ("Timer", "654321", "PRIVATE_", "84739.125", source.snapshot["id"],
                         source.rungs[0].id, source.rungs[0].locator):
            self.assertNotIn(excluded, rendered)
        self.assertEqual(set(value), {"kind", "opcode", "argument_index", "raw_text"})

    def test_names_numbers_and_spaces_inside_one_malformed_operand_are_retained(self) -> None:
        for raw in ("Pump_12[-7]", "Pump_12 + 37.5", "Array[?,2]", "Unit_12..PV", "?Name_123"):
            with self.subTest(raw=raw):
                source = inventory([f"MOV({raw},A);"])
                value = build_diagnostic_sample(source, analyze_references(source))
                self.assertEqual(value, sample(raw, opcode="MOV", argument_index=0))

    def test_first_eligible_operand_is_stable_across_repeated_runs(self) -> None:
        source = inventory(["ton(Timer,Preset?,99);", "XIC(#Later);", "MOV(First?,Second?);"])
        references = analyze_references(source)
        source_before, references_before = source.to_dict(), references.to_dict()
        for _ in range(4):
            self.assertEqual(build_diagnostic_sample(source, references), sample("Preset?"))
        self.assertEqual(source.to_dict(), source_before)
        self.assertEqual(references.to_dict(), references_before)

    def test_selection_uses_argument_order_within_the_first_eligible_instruction(self) -> None:
        source = inventory(["MOV(First?,Second?);"])
        self.assertEqual(build_diagnostic_sample(source, analyze_references(source)),
                         sample("First?", opcode="MOV", argument_index=0))

    def test_overlong_or_nonprintable_operands_are_skipped_without_truncation(self) -> None:
        long_raw = "?" * (MAX_OPERAND_CHARS + 1)
        source = inventory([f"XIC({long_raw});", "XIC(Name?\tOther);", "XIC(Name?\nOther);",
                            "TON(Timer,Preset?,0);"])
        references = analyze_references(source)
        self.assertEqual(sum(row["reason"] == "malformed_address" for row in references.operands), 4)
        self.assertEqual(build_diagnostic_sample(source, references), sample("Preset?"))
        no_bounded = inventory([f"XIC({long_raw});", "XIC(Name?\tOther);"])
        self.assertIsNone(build_diagnostic_sample(no_bounded, analyze_references(no_bounded)))

    def test_exact_character_limit_is_accepted_and_preserved(self) -> None:
        raw = "?" * MAX_OPERAND_CHARS
        source = inventory([f"XIC({raw});"])
        self.assertEqual(build_diagnostic_sample(source, analyze_references(source)),
                         sample(raw, opcode="XIC", argument_index=0))

    def test_other_reference_gaps_literals_labels_and_alias_targets_are_excluded(self) -> None:
        source = inventory([
            "XIC(Alias);", "CPT(A,Unknown? + 7);", "JMP(Label?);", "LBL(Label?);",
            "PRIVATE_UNKNOWN(?);", "XIC(?,A);", "MOV('?',A);", "MOV(42,A);", "XIC(Missing);",
            "XIC(A[Index]);", "XIC(Program:Other.A);", r"XIC(\Remote.A);", "MOV( ,A);", "XIC(A);",
        ], aliases=(("Alias", "?"),))
        references = analyze_references(source)
        self.assertTrue(any(row["reason"] == "malformed_address" and row["alias_chain"]
                            for row in references.operands))
        self.assertIsNone(build_diagnostic_sample(source, references))

    def test_cpt_destination_slot_can_be_sampled_but_expression_slot_cannot(self) -> None:
        source = inventory(["CPT(Dest?,PrivateValue + 8);"])
        self.assertEqual(build_diagnostic_sample(source, analyze_references(source)),
                         sample("Dest?", opcode="CPT", argument_index=0))

    def test_no_operands_returns_null_and_null_validates(self) -> None:
        source = inventory(["NOP();"])
        self.assertIsNone(build_diagnostic_sample(source, analyze_references(source)))
        validate_diagnostic_sample(None)

    def test_validator_rejects_wrong_shapes_metadata_and_nonmalformed_text(self) -> None:
        bad_values = [[], [sample()], {}, "?", True, sample() | {"rung_id": "PRIVATE_SENTINEL"},
                      sample() | {"kind": "alias_target"}, sample() | {"opcode": "ton"},
                      sample() | {"opcode": "PRIVATE_OPCODE"}, sample() | {"opcode": []}]
        bad_values.extend(sample(argument_index=index) for index in (-1, 3, True, "1", 1.0))
        bad_values.extend(sample(opcode=opcode, argument_index=0) for opcode in ("JMP", "LBL"))
        bad_values.append(sample(opcode="CPT", argument_index=1))
        bad_values.extend(sample(raw) for raw in ("", "   ", "A", "A[1]", "A[Index]", "Program:Other.A",
                                                    r"\Remote.A", "12", " 12 ", "'?'", '"?"',
                                                    "?" * 129, "?\tOther", "?\nOther", "?\0Other"))
        bad_values.append(sample() | {"raw_text": 42})
        for value in bad_values:
            with self.subTest(value=value), self.assertRaises(DiagnosticSampleError) as raised:
                validate_diagnostic_sample(value)
            self.assertNotIn("PRIVATE_SENTINEL", str(raised.exception))

    def test_validator_rejects_extra_operand_or_rung_injection(self) -> None:
        for raw in ("?,Other?", "?)OTE(Neighbor", "?);XIC(Neighbor", "?[", "?;Other", "?){Other}"):
            with self.subTest(raw=raw), self.assertRaises(DiagnosticSampleError):
                validate_diagnostic_sample(sample(raw))

    def test_forged_reference_records_are_rejected_before_selection(self) -> None:
        source = inventory(["TON(Timer,Preset?,0);", "XIC(Other?);"])
        original = analyze_references(source)
        mutations = [
            lambda value: value.operands[1].update(raw_text="PRIVATE_FORGED?"),
            lambda value: value.operands[1].update(argument_index=True),
            lambda value: value.operands[1].update(status="literal"),
            lambda value: value.operands[1].update(reason=None),
            lambda value: value.operands[1].update(alias_chain=["PRIVATE_ALIAS"]),
            lambda value: value.operands.reverse(),
            lambda value: value.coverage.update(operands_total=0),
        ]
        for mutate in mutations:
            value = deepcopy(original)
            mutate(value)
            with self.subTest(mutation=mutate), self.assertRaises(ReferenceError) as raised:
                build_diagnostic_sample(source, value)
            self.assertNotIn("PRIVATE_", str(raised.exception))
        with self.assertRaises(ReferenceError):
            build_diagnostic_sample(source, replace(original, snapshot={"id": "PRIVATE_OTHER"}))

    def test_alias_failure_cannot_be_forged_into_a_direct_sample(self) -> None:
        source = inventory(["XIC(Alias);"], aliases=(("Alias", "?"),))
        references = analyze_references(source)
        references.operands[0]["alias_chain"] = []
        with self.assertRaises(ReferenceError):
            build_diagnostic_sample(source, references)

    def test_count_only_reference_summary_is_unchanged_by_sampling(self) -> None:
        source = inventory(["MOV(PrivateOperand_12?,A);"])
        references = analyze_references(source)
        before = render_reference_summary(build_reference_summary(source, references))
        value = build_diagnostic_sample(source, references)
        self.assertEqual(value["raw_text"], "PrivateOperand_12?")
        after = render_reference_summary(build_reference_summary(source, references))
        self.assertEqual(before, after)
        self.assertNotIn("PrivateOperand_12", after)
        self.assertNotIn("diagnostic_sample", after)


class UnmatchedColonDiagnosticTests(unittest.TestCase):
    def test_fallback_keeps_one_actual_operand_and_validates_evidence_once(self) -> None:
        source = inventory(['XIC(Unknown:3:I.Data.2)OTE(PRIVATE_NEIGHBOR);'])
        references = analyze_references(source)
        source_before, references_before = source.to_dict(), references.to_dict()
        with patch('plc_workbench.diagnostic_sample.validate_references', wraps=validate_references) as validate:
            value = build_diagnostic_sample(source, references)
        validate.assert_called_once_with(source, references)
        self.assertEqual(value, colon_sample())
        self.assertEqual(set(value), {'kind', 'opcode', 'argument_index', 'raw_text'})
        for excluded in ('PRIVATE_', source.snapshot['id'], source.rungs[0].id, 'candidate_id'):
            self.assertNotIn(excluded, json.dumps(value))
        self.assertEqual(source.to_dict(), source_before)
        self.assertEqual(references.to_dict(), references_before)

    def test_malformed_priority_applies_across_the_entire_operand_population(self) -> None:
        long_malformed = '?' * (MAX_OPERAND_CHARS + 1)
        cases = [
            (['XIC(Unknown:I);', 'XIC(Later?);'], sample('Later?', opcode='XIC', argument_index=0)),
            ([f'XIC({long_malformed});', 'XIC(Unknown:I);'], colon_sample('Unknown:I')),
            ([f'XIC({long_malformed});', 'XIC(Unknown:I);', 'XIC(Later?);'],
             sample('Later?', opcode='XIC', argument_index=0)),
        ]
        for rungs, expected in cases:
            with self.subTest(rungs=rungs):
                source = inventory(rungs)
                self.assertEqual(build_diagnostic_sample(source, analyze_references(source)), expected)

    def test_fallback_uses_stable_instruction_and_argument_order(self) -> None:
        source = inventory(['MOV(First:I,Second:O);', 'XIC(Third:I);'])
        references = analyze_references(source)
        before = references.to_dict()
        for _ in range(3):
            self.assertEqual(build_diagnostic_sample(source, references),
                             colon_sample('First:I', opcode='MOV'))
        self.assertEqual(references.to_dict(), before)

    def test_rack_unique_ambiguous_unavailable_and_outside_statuses_are_excluded(self) -> None:
        cases = [
            (rack_modules(), '', 'unique_candidate'),
            (rack_modules(aliases=2), '', 'ambiguous_candidate'),
            (rack_modules(parent='Absent'), '', 'candidate_names_unavailable'),
            ('', '<Controller Name="Elsewhere"><Modules>' + rack_modules() + '</Modules></Controller>',
             'outside_visible_scope'),
        ]
        for modules, other, expected in cases:
            with self.subTest(status=expected):
                source = inventory(['XIC(Local:3:I);'], modules=modules, other_controllers=other)
                references = analyze_references(source)
                self.assertEqual(references.rack_candidates['matches']['direct_operands'][0]['status'], expected)
                self.assertIsNone(build_diagnostic_sample(source, references))

    def test_skips_matched_rack_operand_and_samples_later_unmatched_operand(self) -> None:
        source = inventory(['XIC(Local:3:I)XIC(Unmatched:7:O);'], modules=rack_modules())
        self.assertEqual(build_diagnostic_sample(source, analyze_references(source)),
                         colon_sample('Unmatched:7:O'))

    def test_aoi_scope_restriction_is_not_misreported_as_an_unmatched_candidate(self) -> None:
        aoi = ('<AddOnInstructionDefinitions><AddOnInstructionDefinition Name="Isolated">'
               '<Routines><Routine Name="Main" Type="RLL"><RLLContent><Rung Type="N">'
               '<Text><![CDATA[XIC(Local:3:I);]]></Text></Rung></RLLContent></Routine></Routines>'
               '</AddOnInstructionDefinition></AddOnInstructionDefinitions>')
        source = inventory([], modules=rack_modules(), extra=aoi)
        references = analyze_references(source)
        self.assertEqual(references.rack_candidates['matches']['direct_operands'][0]['status'],
                         'outside_visible_scope')
        self.assertIsNone(build_diagnostic_sample(source, references))

    def test_alias_targets_and_noncolon_or_nonstatic_gaps_are_excluded(self) -> None:
        source = inventory([
            'XIC(Alias);', 'XIC(Missing);', 'XIC(Unknown:I.Data[Index]);',
            'XIC(Program:Other.A);', r'XIC(\Remote.A);', 'MOV("Unknown:I",A);',
            'JMP(Unknown:I);', 'CPT(A,Unknown:I + 1);', 'PRIVATE_UNKNOWN(Unknown:I);',
        ], aliases=(('Alias', 'Unknown:I.Data.2'),))
        references = analyze_references(source)
        self.assertEqual(references.rack_candidates['matches']['alias_operands'][0]['status'],
                         'no_candidate_match')
        self.assertIsNone(build_diagnostic_sample(source, references))

    def test_exact_bound_and_static_address_text_are_preserved_without_truncation(self) -> None:
        longest = 'M' * (MAX_OPERAND_CHARS - 2) + ':I'
        for raw in (longest, 'MixedCase_12:I.Data[1, 2].7'):
            with self.subTest(raw=raw):
                source = inventory([f'XIC({raw});'])
                self.assertEqual(build_diagnostic_sample(source, analyze_references(source)), colon_sample(raw))
        source = inventory([f'XIC(M{longest});', 'XIC(Unknown:I.Data[1,\t2]);', 'XIC(Last:I);'])
        self.assertEqual(build_diagnostic_sample(source, analyze_references(source)), colon_sample('Last:I'))

    def test_standalone_validator_requires_colon_root_and_static_lexical_address(self) -> None:
        validate_diagnostic_sample(colon_sample())
        validate_diagnostic_sample(colon_sample(' Known:I.Data[1, 2].7 '))
        for raw in ('?', 'PlainName', 'PlainName.Member', 'PlainName[2]', 'Unknown:I.Data[Index]',
                    'Program:Other.A', 'Missing:I..Data', r'\Missing:I', 'Missing:I,Other:I',
                    'Missing:I);XIC(Other', '"Missing:I"', '42', '', ' ', 'M' * 127 + ':I',
                    'Missing:I.Data[1,\t2]', 'Missing:I\n', 'Missing:I\0', True):
            with self.subTest(raw=raw), self.assertRaises(DiagnosticSampleError):
                validate_diagnostic_sample(colon_sample(raw))
        for change in ({'kind': []}, {'candidate_id': 'PRIVATE_ID'}, {'argument_index': True},
                       {'opcode': 'PRIVATE_OPCODE'}, {'raw_text': {'PRIVATE': 'value'}}):
            with self.subTest(change=change), self.assertRaises(DiagnosticSampleError) as caught:
                validate_diagnostic_sample(colon_sample() | change)
            self.assertNotIn('PRIVATE', str(caught.exception))

    def test_forged_rack_records_cannot_enable_or_redirect_fallback(self) -> None:
        source = inventory(['XIC(Local:3:I)XIC(Unknown:I);'], modules=rack_modules())
        original = analyze_references(source)
        for mutate in (
            lambda r: r.rack_candidates['matches']['direct_operands'][0].update(
                status='no_candidate_match', candidate_id=None, candidate_count=0),
            lambda r: r.rack_candidates['matches']['direct_operands'].pop(),
            lambda r: r.rack_candidates['matches']['direct_operands'][1].update(source_id=r.operands[0]['id']),
            lambda r: r.rack_candidates['candidates'][0].update(name='PRIVATE_FORGED:I'),
        ):
            value = deepcopy(original)
            mutate(value)
            with self.subTest(mutation=mutate), self.assertRaises(ReferenceError) as caught:
                build_diagnostic_sample(source, value)
            self.assertNotIn('PRIVATE', str(caught.exception))

    def test_fallback_does_not_add_identifiers_to_the_count_only_summary(self) -> None:
        source = inventory(['XIC(UnmatchedPrivate_12:I.Data.2);'])
        references = analyze_references(source)
        before = render_reference_summary(build_reference_summary(source, references))
        self.assertEqual(build_diagnostic_sample(source, references),
                         colon_sample('UnmatchedPrivate_12:I.Data.2'))
        self.assertEqual(render_reference_summary(build_reference_summary(source, references)), before)
        self.assertNotIn('UnmatchedPrivate_12', before)
        self.assertNotIn('diagnostic_sample', before)


if __name__ == "__main__":
    unittest.main()
