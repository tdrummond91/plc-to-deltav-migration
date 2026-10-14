"""Single-operand diagnostics from invented XML only; no process/network IO."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import unittest
from xml.sax.saxutils import quoteattr

from plc_workbench.diagnostic_sample import (
    DiagnosticSampleError, MAX_OPERAND_CHARS, build_diagnostic_sample, validate_diagnostic_sample,
)
from plc_workbench.reference_summary import build_reference_summary, render_reference_summary
from plc_workbench.references import ReferenceError, analyze_references
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes


def inventory(rungs: list[str], *, aliases: tuple[tuple[str, str], ...] = ()):
    tags = '<Tag Name="A" TagType="Base"/><Tag Name="Timer" TagType="Base"/>'
    tags += ''.join(f'<Tag Name={quoteattr(name)} TagType="Alias" AliasFor={quoteattr(target)}/>'
                    for name, target in aliases)
    tags += ('<Tag Name="PRIVATE_CONFIG_TAG" TagType="Base" DataType="REAL">'
             '<Data Format="L5K"><![CDATA[84739.125]]></Data></Tag>')
    ladder = ''.join(f'<Rung Number="{index + 700}" Type="N"><Comment>PRIVATE_COMMENT</Comment>'
                     f'<Text><![CDATA[{text}]]></Text></Rung>' for index, text in enumerate(rungs))
    source = (f'<RSLogix5000Content Owner="PRIVATE_OWNER"><Controller Name="PRIVATE_CONTROLLER">'
              f'<Tags>{tags}</Tags><Programs><Program Name="PRIVATE_PROGRAM"><Routines>'
              f'<Routine Name="PRIVATE_ROUTINE" Type="RLL"><RLLContent>{ladder}</RLLContent>'
              '</Routine></Routines></Program></Programs></Controller></RSLogix5000Content>')
    return analyze_snapshot(snapshot_from_bytes(source.encode("utf-8")))


def sample(raw_text: str = "?", *, opcode: str = "TON", argument_index: int = 1) -> dict:
    return {"kind": "direct_malformed_operand", "opcode": opcode,
            "argument_index": argument_index, "raw_text": raw_text}


class DiagnosticSampleTests(unittest.TestCase):
    def test_timer_placeholder_is_one_exact_operand_without_neighboring_context(self) -> None:
        source = inventory(["TON(Timer,?,654321)OTE(PRIVATE_NEIGHBOR);"])
        value = build_diagnostic_sample(source, analyze_references(source))
        self.assertEqual(value, sample())
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
        source = inventory(["ton(Timer,?,99);", "XIC(#Later);", "MOV(First?,Second?);"])
        references = analyze_references(source)
        source_before, references_before = source.to_dict(), references.to_dict()
        for _ in range(4):
            self.assertEqual(build_diagnostic_sample(source, references), sample())
        self.assertEqual(source.to_dict(), source_before)
        self.assertEqual(references.to_dict(), references_before)

    def test_selection_uses_argument_order_within_the_first_eligible_instruction(self) -> None:
        source = inventory(["MOV(First?,Second?);"])
        self.assertEqual(build_diagnostic_sample(source, analyze_references(source)),
                         sample("First?", opcode="MOV", argument_index=0))

    def test_overlong_or_nonprintable_operands_are_skipped_without_truncation(self) -> None:
        long_raw = "?" * (MAX_OPERAND_CHARS + 1)
        source = inventory([f"XIC({long_raw});", "XIC(Name?\tOther);", "XIC(Name?\nOther);",
                            "TON(Timer,?,0);"])
        references = analyze_references(source)
        self.assertEqual(sum(row["reason"] == "malformed_address" for row in references.operands), 4)
        self.assertEqual(build_diagnostic_sample(source, references), sample())
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
        source = inventory(["TON(Timer,?,0);", "XIC(Other?);"])
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


if __name__ == "__main__":
    unittest.main()
