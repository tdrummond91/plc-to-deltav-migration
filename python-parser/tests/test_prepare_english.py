"""Saved-source English preparation uses invented L5X and a local fake engine."""
from contextlib import redirect_stdout
from copy import deepcopy
from html import unescape
from io import StringIO
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench import prepare_english
from plc_workbench.project_store import ProjectError
from plc_workbench.references import analyze_references
from plc_workbench.sfc_structure import analyze_sfc_structure
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.storage import save_run
from plc_workbench.workspace import Workspace
from plc_workbench.workspace_translation import TranslationService
from test_workspace_translation import FakeEngine


def saved_prose_analysis(runs: Path, controller: str = "InventedTranslation") -> Path:
    source = f'''<RSLogix5000Content><Controller Name="{controller}">
    <Description>Controle de demonstration</Description><Tags>
    <Tag Name="Input" TagType="Base" DataType="BOOL"><Description>Niveau bas</Description></Tag>
    <Tag Name="Output" TagType="Base" DataType="BOOL"><Description>Pompe de demonstration</Description></Tag>
    </Tags><Programs><Program Name="Programme"><Routines><Routine Name="Main" Type="RLL">
    <RLLContent><Rung Number="0"><Comment>Arreter la pompe</Comment><Text>XIC(Input)OTE(Output);</Text></Rung>
    <Rung Number="1"><Comment>Commande de vanne</Comment><Text>XIO(Input)OTL(Output);</Text></Rung>
    </RLLContent></Routine></Routines></Program></Programs></Controller></RSLogix5000Content>'''
    snapshot = snapshot_from_bytes(source.encode("utf-8"))
    inventory = analyze_snapshot(snapshot)
    return save_run(runs, snapshot, inventory, references=analyze_references(inventory),
                    sfc_structure=analyze_sfc_structure(snapshot, inventory), include_review=True)


def report_overlay(report: bytes) -> dict:
    match = re.search(r'<div id="review-language-data" hidden>(.*?)</div>', report.decode("utf-8"), re.S)
    if match is None:
        raise AssertionError("The report is missing its language overlay")
    return json.loads(unescape(match.group(1)))


class PrepareEnglishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.fixture.cleanup)
        cls.runs = Path(cls.fixture.name) / "runs"
        cls.saved_run = saved_prose_analysis(cls.runs)
        cls.other_run = saved_prose_analysis(cls.runs, controller="ChangedInventedTranslation")

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name) / "project.sqlite"
        self.calls = []
        self.available = True
        self.callback = None
        self.engine_factory = lambda _: FakeEngine(self.calls, callback=self.callback)
        self.factory = patch("plc_workbench.workspace_translation.TranslationService", lambda path: TranslationService(
            path, engine_factory=lambda model: self.engine_factory(model),
            availability_provider=lambda _: {"available": self.available, "model_id": "test-fr-en-v1", "message": "Install local model"},
        ))
        self.factory.start()
        self.addCleanup(self.factory.stop)
        self.workspace = Workspace(self.project, self.runs)
        self.addCleanup(self.workspace.close)
        self.workspace.import_run(str(self.saved_run), 0)

    def prepare(self):
        with redirect_stdout(StringIO()):
            return prepare_english.prepare(self.workspace)

    def test_full_export_reuses_cache_and_preserves_source_and_review_revision(self):
        rung = self.workspace.rungs({})["items"][0]
        state = self.workspace.store.mutate({"op": "review", "source_ids": [rung["id"]],
            "status": "confirmed", "fields": {"description": "Human approved wording"}},
            expected_revision=self.workspace.store.state()["revision"])
        canonical = {name: self.workspace.store.artifact(name) for name in ("snapshot.L5X", "inventory.json", "review.html")}
        result, destination = self.prepare()
        self.assertEqual((result["state"], result["completed"], result["total"]), ("complete", 5, 5))
        self.assertEqual(self.workspace.store.state(), state)
        for name, original in canonical.items():
            self.assertEqual(self.workspace.store.artifact(name), original)
        exported = json.loads((destination / "source-wording.json").read_text(encoding="utf-8"))
        self.assertEqual(exported["run_id"], state["active_run"])
        self.assertEqual(exported["translations"]["Arreter la pompe"]["text"], "English: Arreter la pompe")
        self.assertEqual(report_overlay((destination / "review-english.html").read_bytes())["language"], "english")
        self.assertEqual(json.loads((destination / "complete.json").read_text())["status"], "complete")
        self.assertEqual(self.workspace.translation()["presentation_mode"], "english")
        first_files = {path.name: path.read_bytes() for path in destination.iterdir()}
        repeated, second = self.prepare()
        self.assertNotEqual(destination, second)
        self.assertEqual((repeated["cached"], len(self.calls)), (5, 5))
        self.assertEqual({path.name: path.read_bytes() for path in destination.iterdir()}, first_files)

    def test_missing_model_does_not_create_completed_export(self):
        self.available = False
        status, destination = self.prepare()
        self.assertIsNone(destination)
        self.assertNotEqual(status["state"], "complete")
        self.assertEqual(self.calls, [])
        self.assertFalse((self.project.parent / "english-analysis").exists())

    def test_model_start_failure_does_not_create_completed_export(self):
        def unavailable(_):
            raise RuntimeError("Sensitive installation details")
        self.engine_factory = unavailable
        status, destination = self.prepare()
        self.assertEqual(status["state"], "error")
        self.assertIsNone(destination)
        self.assertNotIn("Sensitive", str(status))
        self.assertFalse((self.project.parent / "english-analysis").exists())

    def test_withheld_wording_exports_partial_and_cli_returns_partial_status(self):
        self.callback = lambda text: ({"text": "", "status": "needs_review"}
            if text == "Arreter la pompe" else {"text": "English: " + text, "status": "translated"})
        result, destination = self.prepare()
        self.assertEqual((result["failed"], result["needs_review"]), (1, 1))
        completion = json.loads((destination / "complete.json").read_text())
        self.assertEqual(completion["status"], "partial")
        overlay = report_overlay((destination / "review-english.html").read_bytes())
        withheld = next(row for row in overlay["translations"] if row["original"] == "Arreter la pompe")
        self.assertEqual((withheld["status"], withheld["text"]), ("unavailable", ""))
        with patch.object(prepare_english, "_startup_project", return_value=(self.project, None)), redirect_stdout(StringIO()):
            self.assertEqual(prepare_english.main(["--project", str(self.project)]), 3)

    def test_report_failure_never_creates_completion_record(self):
        with patch.object(self.workspace, "report", side_effect=ProjectError("Report could not render")):
            with self.assertRaisesRegex(ProjectError, "Report could not render"):
                self.prepare()
        self.assertFalse((self.project.parent / "english-analysis").exists())
        self.assertEqual(self.workspace.translation()["completed"], 5)

    def test_cli_missing_model_returns_error_without_success_message(self):
        self.available = False
        output = StringIO()
        with patch.object(prepare_english, "_startup_project", return_value=(self.project, None)), redirect_stdout(output):
            code = prepare_english.main(["--project", str(self.project)])
        self.assertEqual(code, 1)
        self.assertNotIn("English report:", output.getvalue())
        self.assertFalse((self.project.parent / "english-analysis").exists())

    def test_active_run_change_during_export_never_marks_mixed_export_complete(self):
        original_write = Path.write_bytes

        def write_then_change_source(path, data):
            count = original_write(path, data)
            if path.name == "review-english.html":
                self.workspace.import_run(str(self.other_run), self.workspace.store.state()["revision"])
            return count

        with patch.object(Path, "write_bytes", new=write_then_change_source):
            with self.assertRaisesRegex(ProjectError, "active analysis changed"):
                self.prepare()
        export_root = self.project.parent / "english-analysis"
        self.assertEqual(len(list(export_root.glob("*/source-wording.json"))), 1)
        self.assertEqual(len(list(export_root.glob("*/review-english.html"))), 1)
        self.assertEqual(list(export_root.glob("*/complete.json")), [])

    def test_known_namespace_gap_is_partial_even_when_all_eligible_texts_translate(self):
        original_catalog = Workspace.annotation_catalog

        def catalog_with_gap(workspace):
            catalog = deepcopy(original_catalog(workspace))
            catalog["coverage"]["namespace_exclusions"] = 1
            catalog["limitations"].append("An invented unsupported namespace annotation remains original.")
            return catalog

        with patch.object(Workspace, "annotation_catalog", new=catalog_with_gap):
            status, destination = self.prepare()
            self.assertEqual((status["failed"], status["needs_review"], status["coverage_gaps"]), (0, 0, 1))
            completion = json.loads((destination / "complete.json").read_text())
            self.assertEqual(completion["status"], "partial")
            self.assertEqual(completion["coverage"]["namespace_exclusions"], 1)
            self.assertIn("unsupported namespace", completion["limitations"][-1])
            output = StringIO()
            with patch.object(prepare_english, "_startup_project", return_value=(self.project, None)), redirect_stdout(output):
                self.assertEqual(prepare_english.main(["--project", str(self.project)]), 3)
            self.assertIn("1 unsupported source notes were excluded", output.getvalue())

    def test_redirected_export_directory_is_rejected_before_writing(self):
        redirected = self.project.parent / "redirected-destination"
        redirected.mkdir()
        export_root = self.project.parent / "english-analysis"
        try:
            export_root.symlink_to(redirected, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Directory symlinks are not available to this Windows account")
        try:
            with self.assertRaisesRegex(ProjectError, "without redirected paths"):
                self.prepare()
            self.assertEqual(list(redirected.iterdir()), [])
        finally:
            export_root.unlink()


if __name__ == "__main__":
    unittest.main()
