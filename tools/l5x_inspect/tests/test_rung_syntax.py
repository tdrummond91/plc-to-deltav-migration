"""Invented neutral text only; no plant code or filesystem writes."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rungs.syntax import (  # noqa: E402
    Instruction, OpcodeLabels, RungSyntaxError, measure,
    parse_rung, public_forms, render_sample,
)


class RungSyntaxTests(unittest.TestCase):
    def test_series_has_no_branches(self) -> None:
        metrics = measure(parse_rung("XIC(a)XIO(b)OTE(c);"))
        self.assertEqual(metrics["instruction_calls"], 3)
        self.assertEqual(metrics["branch_groups"], 0)
        self.assertEqual(metrics["height_lanes"], 1)
        self.assertEqual(metrics["width_instructions"], 3)
        self.assertEqual(metrics["max_branch_depth"], 0)

    def test_simple_parallel_metrics(self) -> None:
        metrics = measure(parse_rung("[XIC(a),XIC(b)XIO(c)]OTE(d);"))
        self.assertEqual(metrics["instruction_calls"], 4)
        self.assertEqual(metrics["branch_groups"], 1)
        self.assertEqual(metrics["branch_legs"], 2)
        self.assertEqual(metrics["height_lanes"], 2)
        self.assertEqual(metrics["width_instructions"], 3)
        self.assertEqual(metrics["max_branch_depth"], 1)

    def test_nested_branch_height_is_sum_width_is_longest_path(self) -> None:
        metrics = measure(parse_rung("[XIC(a)[XIO(b),XIC(c)],XIC(d)]OTE(e);"))
        self.assertEqual(metrics["instruction_calls"], 5)
        self.assertEqual(metrics["branch_groups"], 2)
        self.assertEqual(metrics["branch_legs"], 4)
        self.assertEqual(metrics["height_lanes"], 3)
        self.assertEqual(metrics["width_instructions"], 3)
        self.assertEqual(metrics["max_branch_depth"], 2)

    def test_separate_branch_heights_are_not_added(self) -> None:
        metrics = measure(parse_rung("[XIC(a),XIC(b)][XIC(c),XIC(d),XIC(e)]OTE(f);"))
        self.assertEqual(metrics["height_lanes"], 3)
        self.assertEqual(metrics["width_instructions"], 3)
        self.assertEqual(metrics["branch_legs"], 5)
        self.assertEqual(metrics["max_legs_in_group"], 3)

    def test_empty_bypass_legs_are_valid_structurally(self) -> None:
        metrics = measure(parse_rung("XIC(a)[,XIO(b),]OTE(c);"))
        self.assertEqual(metrics["branch_legs"], 3)
        self.assertEqual(metrics["empty_branch_legs"], 2)
        self.assertEqual(metrics["height_lanes"], 3)
        self.assertEqual(metrics["width_instructions"], 3)

    def test_array_brackets_and_commas_are_not_branches(self) -> None:
        tree = parse_rung("MOV(Array[1,2],Other[Index+1]);")
        self.assertEqual(len(tree.items[0].arguments), 2)
        self.assertEqual(measure(tree)["branch_groups"], 0)

    def test_nested_expression_calls_are_not_ladder_instructions(self) -> None:
        metrics = measure(parse_rung("CPT(out,(a + SIN(b)) / 2)CMP((a > b) AND (c < d));"))
        self.assertEqual(metrics["instruction_calls"], 2)
        self.assertEqual(metrics["expression_instruction_calls"], 2)
        self.assertEqual(metrics["argument_slots"], 3)

    def test_quoted_delimiters_and_semicolons_stay_in_argument(self) -> None:
        tree = parse_rung("MOV('private [,]; ()',dest);")
        self.assertEqual(len(tree.items[0].arguments), 2)
        self.assertEqual(measure(tree)["branch_groups"], 0)

    def test_dollar_escaped_quote_does_not_close_string(self) -> None:
        tree = parse_rung("MOV('a$'[,]b',dest);")
        self.assertEqual(len(tree.items[0].arguments), 2)

    def test_doubled_quote_does_not_split_argument(self) -> None:
        tree = parse_rung('MOV("a""[,]b",dest);')
        self.assertEqual(len(tree.items[0].arguments), 2)

    def test_empty_argument_slots_preserved(self) -> None:
        tree = parse_rung("GSV(Task,,Rate,out)NOP();")
        self.assertEqual(tree.items[0].arguments, ("Task", "", "Rate", "out"))
        self.assertEqual(tree.items[1].arguments, ())
        self.assertEqual(measure(tree)["argument_slots"], 4)
        self.assertEqual(measure(tree)["nonempty_argument_fields"], 3)

    def test_whitespace_and_empty_rung(self) -> None:
        self.assertEqual(measure(parse_rung(" \n ; \t"))["instruction_calls"], 0)
        self.assertEqual(measure(parse_rung(" XIC (a) \n OTE (b) ; "))["instruction_calls"], 2)

    def test_invalid_outer_syntax_fails_without_echoing_source(self) -> None:
        for value in ("PRIVATE(a)", "PRIVATE(a);PRIVATE(b);", "PRIVATE(a),OTE(b);",
                      "PRIVATE(a)];", "[PRIVATE(a)];", "[PRIVATE(a),OTE(b);",
                      "BST PRIVATE(a) BND;", "PRIVATE-a(x);"):
            with self.subTest(value=value):
                with self.assertRaises(RungSyntaxError) as caught:
                    parse_rung(value)
                self.assertNotIn("PRIVATE", str(caught.exception))

    def test_unbalanced_arguments_are_rejected(self) -> None:
        for value in ("XIC(a;", "XIC(Array[2));", "XIC('private);", "XIC({a]);",
                      "XIC(a;b);", "XIC((a);"):
            with self.subTest(value=value):
                with self.assertRaises(RungSyntaxError):
                    parse_rung(value)

    def test_limits_are_explicit(self) -> None:
        with patch("rungs.syntax.MAX_TEXT", 3):
            with self.assertRaises(RungSyntaxError) as caught:
                parse_rung("NOP();")
            self.assertEqual(caught.exception.code, "text_limit")
        with patch("rungs.syntax.MAX_NODES", 1):
            with self.assertRaises(RungSyntaxError):
                parse_rung("NOP()NOP();")
        with patch("rungs.syntax.MAX_DEPTH", 1):
            with self.assertRaises(RungSyntaxError):
                parse_rung("[[NOP(),NOP()],NOP()];")
            with self.assertRaises(RungSyntaxError):
                parse_rung("CMP((a));")

    def test_public_forms_replace_all_arguments_and_unknown_opcodes(self) -> None:
        import json
        labels = OpcodeLabels()
        tree = parse_rung("PRIVATE_OP(PRIVATE_TAG,123.5)[XIC(PRIVATE_TAG),XIO(999)]OTE(PRIVATE_OUT);")
        shape, sample, counts = public_forms(tree, labels)
        output = json.dumps({"shape": shape, "sample": sample, "counts": dict(counts)})
        self.assertNotIn("PRIVATE", output)
        self.assertNotIn("123.5", output)
        self.assertNotIn("999", output)
        self.assertEqual(counts["UNLISTED_OP_0001"], 1)
        self.assertEqual(sample["items"][0]["arguments"][0], "ARG_001")
        self.assertEqual(sample["items"][1]["legs"][0]["items"][0]["arguments"][0], "ARG_001")

    def test_unlisted_opcode_labels_are_consistent_and_distinct(self) -> None:
        labels = OpcodeLabels()
        self.assertEqual(labels.label("PrivateA"), labels.label("PrivateA"))
        self.assertNotEqual(labels.label("PrivateA"), labels.label("PrivateB"))
        self.assertEqual(labels.unknown_count, 2)
        self.assertEqual(labels.label("XIC"), "XIC")

    def test_shape_ignores_operands_but_keeps_opcode_arity_and_branch_order(self) -> None:
        labels = OpcodeLabels()
        def shape(text: str) -> dict:
            return public_forms(parse_rung(text), labels)[0]
        self.assertEqual(shape("[XIC(a),XIO(b)]OTE(c);"), shape("[XIC(x),XIO(y)]OTE(z);"))
        self.assertNotEqual(shape("[XIC(a),XIO(b)]OTE(c);"), shape("[XIO(a),XIC(b)]OTE(c);"))
        self.assertNotEqual(shape("GSV(a,,b,c);"), shape("GSV(a,b,,c);"))
        self.assertNotEqual(shape("XIC(a);"), shape("XIC(a,b);"))

    def test_sanitized_sample_round_trip_keeps_metrics_and_shape(self) -> None:
        labels = OpcodeLabels()
        source = parse_rung("XIC(a)[,CMP((x > 3) AND y),[XIO(a),XIC(b)]]OTE(out);")
        shape, sample, _counts = public_forms(source, labels)
        rebuilt = parse_rung(render_sample(sample))
        self.assertEqual(measure(source), measure(rebuilt))
        self.assertEqual(shape, public_forms(rebuilt, labels)[0])

    def test_instruction_repr_does_not_expose_operands(self) -> None:
        self.assertNotIn("SECRET", repr(Instruction("SECRET_OP", ("SECRET_TAG",))))


if __name__ == "__main__":
    unittest.main()
