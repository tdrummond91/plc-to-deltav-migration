"""Source-bound, read-only equation evidence for the local engineering editor."""
from __future__ import annotations

from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from plc_workbench.workspace import Workspace
from test_workspace import running_workspace, saved_analysis


class WorkspaceEquationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.captures = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.captures.cleanup)
        cls.runs = Path(cls.captures.name) / "runs"
        cls.first = saved_analysis(cls.runs, first_texts=(
            "XIC(Input)CPT(Output,(Input+2)/(3-1))CPT(Output,SQRT(Input**2));",
            "CPT(Output,Input*17);", "CPT(Output,ATAN2(Input,2));",
            "CPT(Output);",
        ))
        cls.later = saved_analysis(cls.runs, first_texts=("CPT(Output,Input+99);",))
        cls.inventory = json.loads((cls.first / "inventory.json").read_text(encoding="utf-8"))
        cls.calculations = json.loads((cls.first / "calculations.json").read_text(encoding="utf-8"))

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name) / "project.sqlite"
        self.workspace = Workspace(self.project, self.runs)
        self.addCleanup(self.workspace.close)
        state = self.workspace.import_run(str(self.first), 0)
        self.run_id = state["active_run"]

    def replace_calculations(self, payload: dict | bytes | None) -> None:
        """Simulate damaged local optional evidence without changing source capture."""
        connection = self.workspace.store.connection
        if payload is None:
            connection.execute("DELETE FROM artifacts WHERE run_id=? AND name='calculations.json'", (self.run_id,))
        else:
            data = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
            connection.execute("UPDATE artifacts SET data=? WHERE run_id=? AND name='calculations.json'", (data, self.run_id))
        connection.commit()

    def test_rung_and_instruction_selection_only_return_their_saved_syntax(self) -> None:
        rung = self.inventory["rungs"][0]
        state_before = self.workspace.store.state()
        writes_before = self.workspace.store.connection.total_changes
        detail = self.workspace.source(rung["id"])
        selected = detail["calculations"]
        instructions = rung["instructions"][1:]
        self.assertEqual(selected["status"], "available")
        self.assertEqual([row["id"] for row in selected["occurrences"]], [row["id"] for row in instructions])
        self.assertEqual({node["instruction_id"] for node in selected["nodes"]}, {row["id"] for row in instructions})
        for node in selected["nodes"]:
            self.assertNotIn("binding", node)
            saved = next(row for row in self.calculations["nodes"] if row["id"] == node["id"])
            self.assertEqual(node, {key: value for key, value in saved.items() if key != "binding"})
        instruction_detail = self.workspace.source(instructions[0]["id"])["calculations"]
        self.assertEqual([row["id"] for row in instruction_detail["occurrences"]], [instructions[0]["id"]])
        self.assertEqual({node["instruction_id"] for node in instruction_detail["nodes"]}, {instructions[0]["id"]})
        self.assertEqual(self.workspace.store.state(), state_before)
        self.assertEqual(self.workspace.store.connection.total_changes, writes_before)

    def test_non_calculation_and_object_selections_have_no_expression_nodes(self) -> None:
        rung = self.inventory["rungs"][0]
        for identifier in (rung["instructions"][0]["id"], self.inventory["entities"][0]["id"]):
            with self.subTest(identifier=identifier):
                evidence = self.workspace.source(identifier)["calculations"]
                self.assertEqual(evidence["occurrences"], [])
                self.assertEqual(evidence["nodes"], [])

    def test_unsupported_and_unresolved_signatures_keep_explicit_raw_fallback(self) -> None:
        for index, expected in ((2, "unsupported"), (3, "signature_unresolved")):
            with self.subTest(status=expected):
                rung = self.inventory["rungs"][index]
                detail = self.workspace.source(rung["id"])
                evidence = detail["calculations"]
                self.assertEqual(evidence["status"], "available")
                self.assertEqual(evidence["occurrences"][0]["syntax_status"], expected)
                self.assertEqual(evidence["nodes"], [])
                self.assertEqual(detail["source"]["text"], rung["text"])

    def test_missing_optional_calculations_remain_compatible(self) -> None:
        self.replace_calculations(None)
        detail = self.workspace.source(self.inventory["rungs"][0]["id"])
        self.assertEqual(detail["calculations"], {"status": "absent", "occurrences": [], "nodes": []})
        self.assertEqual(detail["source"], self.inventory["rungs"][0])

    def test_historical_source_uses_its_own_evidence_then_restores_active_source(self) -> None:
        later = self.workspace.import_run(str(self.later), self.workspace.store.state()["revision"])
        later_inventory = self.workspace.store.inventory()
        old = self.workspace.source(self.inventory["rungs"][0]["id"], self.run_id)
        self.assertTrue(old["historical"])
        self.assertEqual(old["run_id"], self.run_id)
        self.assertEqual(len(old["calculations"]["occurrences"]), 2)
        active = self.workspace.source(later_inventory["rungs"][0]["id"])
        self.assertFalse(active["historical"])
        self.assertEqual(active["run_id"], later["active_run"])
        self.assertEqual(len(active["calculations"]["occurrences"]), 1)
        self.assertIn("99", [node["raw_text"] for node in active["calculations"]["nodes"]])
        self.assertEqual(self.workspace.state()["source"]["snapshot"], later_inventory["snapshot"])

    def test_foreign_snapshot_or_invalid_json_falls_back_without_hiding_source(self) -> None:
        payload = deepcopy(self.calculations)
        payload["snapshot"]["id"] = "foreign-private-snapshot"
        for value in (payload, b'{broken-private-data', b'[]'):
            with self.subTest(value=type(value).__name__):
                self.replace_calculations(value)
                # Reopen to exercise a fresh cache after external local damage.
                with self.fresh_workspace() as workspace:
                    detail = workspace.source(self.inventory["rungs"][0]["id"])
                    self.assertEqual(detail["calculations"]["status"], "unavailable")
                    self.assertEqual(detail["calculations"]["nodes"], [])
                    self.assertNotIn("private", detail["calculations"]["message"])
                    self.assertEqual(detail["source"], self.inventory["rungs"][0])

    def fresh_workspace(self):
        return closing(Workspace(self.project, self.runs))

    def test_changed_operators_cycles_foreign_nodes_and_raw_spans_are_rejected(self) -> None:
        def changed_operator(payload: dict) -> None:
            next(node for node in payload["nodes"] if node["operator"] == "/")["operator"] = "+"

        def cycle(payload: dict) -> None:
            node = next(node for node in payload["nodes"] if node["operator"] == "/")
            node["child_ids"][0] = node["id"]

        def foreign_child(payload: dict) -> None:
            row = payload["occurrences"][0]
            node = next(node for node in payload["nodes"] if node["id"] == row["root_node_id"])
            node["child_ids"][0] = payload["occurrences"][2]["root_node_id"]

        def changed_leaf(payload: dict) -> None:
            payload["nodes"][0]["raw_text"] = "UnrelatedPlantTag"

        def changed_occurrence_link(payload: dict) -> None:
            payload["occurrences"][0]["expression_operand_id"] = "other-expression"

        def boolean_span(payload: dict) -> None:
            payload["nodes"][0]["start"] = True

        for mutation in (changed_operator, cycle, foreign_child, changed_leaf, changed_occurrence_link, boolean_span):
            with self.subTest(mutation=mutation.__name__):
                payload = deepcopy(self.calculations)
                mutation(payload)
                self.replace_calculations(payload)
                with self.fresh_workspace() as workspace:
                    detail = workspace.source(self.inventory["rungs"][0]["id"])
                    self.assertEqual(detail["calculations"]["status"], "unavailable")
                    self.assertEqual(detail["calculations"]["occurrences"], [])
                    self.assertEqual(detail["calculations"]["nodes"], [])
                    self.assertEqual(detail["source"]["text"], self.inventory["rungs"][0]["text"])

    def test_artifact_size_limit_falls_back_without_parsing_payload(self) -> None:
        with patch("plc_workbench.calculations.MAX_CALCULATION_BYTES", 8):
            evidence = self.workspace.source(self.inventory["rungs"][0]["id"])["calculations"]
        self.assertEqual(evidence["status"], "unavailable")

    def test_real_source_api_contains_filtered_equation_evidence(self) -> None:
        with running_workspace(self.project, self.runs) as client:
            identifier = self.inventory["rungs"][1]["instructions"][0]["id"]
            detail = client.get("/api/source?" + urlencode({"id": identifier}))
            self.assertEqual(detail["calculations"]["status"], "available")
            self.assertEqual([row["id"] for row in detail["calculations"]["occurrences"]], [identifier])
            self.assertEqual({row["instruction_id"] for row in detail["calculations"]["nodes"]}, {identifier})


if __name__ == "__main__":
    unittest.main()
