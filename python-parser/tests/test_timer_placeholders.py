"""Bounded timer-placeholder reference rules using invented in-memory sources."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import replace
import unittest

from plc_workbench.reference_summary import build_reference_summary, render_reference_summary
from plc_workbench.references import ReferenceError, _address, _literal, analyze_references, validate_references
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes


def inventory(text: str, *, aliases: str = ""):
    return analyze_snapshot(snapshot_from_bytes((
        '<RSLogix5000Content><Controller Name="SyntheticController"><Tags>'
        '<Tag Name="TimerRoot" TagType="Base" DataType="DINT"/>'
        '<Tag Name="Destination" TagType="Base"/>' + aliases + '</Tags>'
        '<Programs><Program Name="SyntheticProgram"><Routines><Routine Name="SyntheticRoutine" Type="RLL">'
        '<RLLContent><Rung Number="0" Type="N"><Text><![CDATA[' + text + ']]></Text></Rung></RLLContent>'
        '</Routine></Routines></Program></Programs></Controller></RSLogix5000Content>'
    ).encode("utf-8")))


class TimerPlaceholderTests(unittest.TestCase):
    def assert_non_data(self, operand: dict) -> None:
        self.assertEqual(operand["status"], "non_data")
        self.assertIsNone(operand["reason"])
        self.assertIsNone(operand["symbol_id"])
        self.assertIsNone(operand["target_id"])
        self.assertEqual(operand["suffix"], "")
        self.assertEqual(operand["alias_chain"], [])

    def test_six_timer_placeholder_slots_have_no_binding_or_inferred_value(self) -> None:
        source = inventory("TON(TimerRoot,?,?)TOF(TimerRoot,?,?)RTO(TimerRoot,?,?);")
        source_before = source.to_dict()
        result = analyze_references(source)
        for operand in result.operands:
            if operand["argument_index"] in {1, 2}:
                self.assertEqual(operand["raw_text"], "?")
                self.assert_non_data(operand)
            else:
                self.assertEqual(operand["status"], "root_bound")
                self.assertEqual(operand["raw_text"], "TimerRoot")
                self.assertEqual(operand["target_id"], result.symbols[0]["id"])
        self.assertEqual(Counter(row["status"] for row in result.operands), {"root_bound": 3, "non_data": 6})
        self.assertEqual(result.coverage["operands_total"], 9)
        self.assertEqual(result.coverage["instructions_catalogued"], 3)
        self.assertEqual(result.status, "complete")
        self.assertEqual(result.schema_version, 4)
        self.assertEqual(result.analyzer_version, "source-references-6")
        self.assertEqual(result.analysis_scope, "scoped_root_bindings")
        for field in ("semantic_analysis", "effect_analysis", "member_validation"):
            self.assertEqual(getattr(result, field), "not_implemented")
        self.assertEqual(source.to_dict(), source_before)
        validate_references(source, result)

    def test_placeholder_and_numeric_literal_slots_are_independent(self) -> None:
        source = inventory("TON(TimerRoot,?,0)TOF(TimerRoot,100,?)RTO(TimerRoot,?,32);")
        result = analyze_references(source)
        self.assertEqual([row["status"] for row in result.operands], [
            "root_bound", "non_data", "literal", "root_bound", "literal", "non_data",
            "root_bound", "non_data", "literal",
        ])
        self.assertEqual([row["raw_text"] for row in result.operands],
                         ["TimerRoot", "?", "0", "TimerRoot", "100", "?", "TimerRoot", "?", "32"])
        self.assertEqual(result.coverage["operands_total"], 9)

    def test_trimmed_placeholder_rule_keeps_supplied_operand_text_exactly(self) -> None:
        # This stage accepts captured inventory records. Exercise its trim
        # check independently of the syntax parser's whitespace normalization.
        source = inventory("ton(TimerRoot,?,?);")
        rung = source.rungs[0]
        instruction = replace(rung.instructions[0], arguments=("TimerRoot", "  ?  ", "\t?\n"))
        source = replace(source, rungs=[replace(rung, instructions=[instruction])])
        result = analyze_references(source)
        self.assertEqual([row["raw_text"] for row in result.operands], ["TimerRoot", "  ?  ", "\t?\n"])
        for operand in result.operands[1:]:
            self.assert_non_data(operand)
        validate_references(source, result)

    def test_timer_root_question_mark_remains_a_malformed_address(self) -> None:
        for opcode in ("TON", "TOF", "RTO"):
            with self.subTest(opcode=opcode):
                result = analyze_references(inventory(f"{opcode}(?,?,?);"))
                self.assertEqual(result.operands[0]["status"], "unsupported_address")
                self.assertEqual(result.operands[0]["reason"], "malformed_address")
                self.assertEqual(result.operands[0]["raw_text"], "?")
                for operand in result.operands[1:]:
                    self.assert_non_data(operand)
                self.assertEqual(result.status, "partial")

    def test_other_opcodes_and_timer_lookalikes_keep_existing_question_mark_rules(self) -> None:
        result = analyze_references(inventory(
            "XIC(?)MOV(?,Destination)RES(?)CPT(Destination,?)PRIVATE_TIMER(TimerRoot,?,?);"))
        self.assertEqual([row["status"] for row in result.operands], [
            "unsupported_address", "unsupported_address", "root_bound", "unsupported_address",
            "root_bound", "unsupported_expression", "unsupported_instruction", "unsupported_instruction",
            "unsupported_instruction",
        ])
        self.assertEqual(_address("?"), (None, "malformed_address"))
        self.assertFalse(_literal("?"))

    def test_wrong_timer_arity_precedes_placeholder_classification(self) -> None:
        for opcode in ("TON", "TOF", "RTO"):
            for arguments in ("TimerRoot,?", "TimerRoot,?,?,0", "?"):
                with self.subTest(opcode=opcode, arguments=arguments):
                    result = analyze_references(inventory(f"{opcode}({arguments});"))
                    self.assertTrue(result.operands)
                    self.assertTrue(all(row["status"] == "argument_count_mismatch" for row in result.operands))
                    self.assertEqual(result.coverage["instructions_catalogued"], 0)
                    self.assertEqual(result.status, "partial")

    def test_quoted_question_marks_stay_literals_and_other_malformed_forms_stay_gaps(self) -> None:
        result = analyze_references(inventory(
            "TON(TimerRoot,'?',\"?\")TOF(TimerRoot,??,Name?)RTO(TimerRoot, ,?);"))
        self.assertEqual([row["status"] for row in result.operands], [
            "root_bound", "literal", "literal", "root_bound", "unsupported_address", "unsupported_address",
            "root_bound", "empty", "non_data",
        ])
        self.assertEqual(result.operands[4]["reason"], "malformed_address")
        self.assertEqual(result.operands[5]["reason"], "malformed_address")

    def test_alias_targets_are_never_interpreted_as_timer_placeholders(self) -> None:
        aliases = ('<Tag Name="TimerAlias" TagType="Alias" AliasFor="TimerRoot"/>'
                   '<Tag Name="BadAlias" TagType="Alias" AliasFor="?"/>')
        source = inventory("TON(TimerAlias,?,0)TOF(TimerRoot,BadAlias,?);", aliases=aliases)
        result = analyze_references(source)
        root, placeholder, _literal_operand, _root, bad_alias, second_placeholder = result.operands
        self.assertEqual(root["status"], "root_bound")
        self.assertEqual(root["target_id"], result.symbols[0]["id"])
        self.assertEqual(len(root["alias_chain"]), 1)
        self.assert_non_data(placeholder)
        self.assert_non_data(second_placeholder)
        self.assertEqual((bad_alias["status"], bad_alias["reason"]), ("unsupported_address", "malformed_address"))
        self.assertEqual(bad_alias["raw_text"], "BadAlias")
        self.assertEqual(len(bad_alias["alias_chain"]), 1)
        alias = next(row for row in result.aliases if row["raw_target"] == "?")
        self.assertEqual((alias["status"], alias["reason"]), ("unsupported_address", "malformed_address"))

    def test_placeholder_binding_metadata_and_previous_version_fail_canonical_validation(self) -> None:
        source = inventory("TON(TimerRoot,?,?);")
        result = analyze_references(source)
        for mutation in ({"status": "unsupported_address", "reason": "malformed_address"},
                         {"status": "literal"}, {"target_id": result.symbols[0]["id"]},
                         {"suffix": ".PRE"}, {"raw_text": "0"}):
            with self.subTest(mutation=mutation):
                changed = deepcopy(result)
                changed.operands[1].update(mutation)
                with self.assertRaises(ReferenceError):
                    validate_references(source, changed)
        for previous in ("source-references-2", "source-references-3", "source-references-5"):
            with self.subTest(analyzer_version=previous), self.assertRaises(ReferenceError):
                validate_references(source, replace(result, analyzer_version=previous))

    def test_count_only_summary_counts_placeholder_slots_without_erasing_other_gaps(self) -> None:
        source = inventory("TON(TimerRoot,?,?)XIC(?);")
        summary = build_reference_summary(source, analyze_references(source))
        self.assertEqual(summary["operands"]["total"], 4)
        self.assertEqual(summary["operands"]["by_status"]["root_bound"], 1)
        self.assertEqual(summary["operands"]["by_status"]["non_data"], 2)
        self.assertEqual(summary["operands"]["by_status"]["unsupported_address"], 1)
        self.assertEqual(summary["operands"]["by_reason"]["unsupported_address"]["malformed_address"], 1)
        self.assertEqual(summary["status"], "partial")
        rendered = render_reference_summary(summary)
        for private_text in ("TimerRoot", "SyntheticController", source.snapshot["id"], "raw_text"):
            self.assertNotIn(private_text, rendered)


if __name__ == "__main__":
    unittest.main()
