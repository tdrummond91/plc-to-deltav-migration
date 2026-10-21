"""Review persistence and import integrity using only invented source exports."""

from __future__ import annotations

import hashlib
import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench.access import analyze_access
from plc_workbench.calculations import analyze_calculations
from plc_workbench.project_store import ProjectError, ProjectStore, rung_pattern
from plc_workbench.references import analyze_references
from plc_workbench.rung_analysis import analyze_rungs
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.storage import save_run


def invented_run(root: Path, *, text: str = "XIC(Input)OTE(Output);", proposal: str = "boolean_output", extra: bool = True) -> Path:
    source = (f'<RSLogix5000Content><Controller Name="Invented"><Programs><Program Name="P">'
              '<Routines><Routine Name="Logic" Type="RLL"><RLLContent>'
              f'<Rung Number="0" Type="N"><Comment>Invented only</Comment><Text><![CDATA[{text}]]></Text></Rung>'
              '</RLLContent></Routine></Routines></Program></Programs></Controller></RSLogix5000Content>').encode()
    snapshot = snapshot_from_bytes(source)
    inventory = analyze_snapshot(snapshot)
    run = save_run(root, snapshot, inventory)
    if extra:
        references = analyze_references(inventory)
        calculations = analyze_calculations(snapshot, inventory, references)
        access = analyze_access(inventory, references, schema_version=4, snapshot=snapshot, calculations=calculations)
        analysis = analyze_rungs(snapshot, inventory, references, access, calculations).to_dict()
        analysis["candidates"][0]["category"] = proposal
        attach(run, "rung-analysis.json", json.dumps(analysis).encode())
        attach(run, "references.json", json.dumps(references.to_dict()).encode())
        attach(run, "review.html", b"<!doctype html><title>Invented report</title>")
    return run


def attach(run: Path, name: str, data: bytes) -> None:
    (run / name).write_bytes(data)
    manifest = json.loads((run / "manifest.json").read_text())
    manifest["artifacts"][name] = {"size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


class ProjectStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run_dir = invented_run(self.root / "runs")
        self.store = ProjectStore(self.root / "project.sqlite")
        self.addCleanup(self.store.close)
        self.store.import_run(self.run_dir)
        self.rung_id = self.store.inventory()["rungs"][0]["id"]
        self.instruction_id = self.store.inventory()["rungs"][0]["instructions"][0]["id"]

    def change(self, command: dict) -> dict:
        return self.store.mutate(command, self.store.state()["revision"])

    def review(self, **changes) -> dict:
        return self.change({"op": "review", "source_ids": [self.rung_id], "category_ids": ["category-pid"], "status": "confirmed", "fields": {"DeltaV name": "INVENTED_LOOP"}, **changes})

    def test_import_retains_every_artifact_and_does_not_touch_run(self) -> None:
        before = {p.name: p.read_bytes() for p in self.run_dir.iterdir()}
        state = self.store.state()
        self.assertEqual(state["revision"], 1)
        self.assertEqual(len(self.store.inventory()["rungs"]), 1)
        for name, data in before.items():
            self.assertEqual(self.store.artifact(name), data)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.run_dir.iterdir()})
        self.assertIn("parser-boolean_output", {c["id"] for c in state["categories"]})

    def test_saved_review_persists_after_reopen_and_source_remains_immutable(self) -> None:
        original = self.store.inventory()
        result = self.review()
        with ProjectStore(self.store.path) as reopened:
            self.assertEqual(reopened.state(), result)
            self.assertEqual(reopened.inventory(), original)
        self.assertEqual(result["reviews"][self.rung_id]["fields"]["DeltaV name"], "INVENTED_LOOP")

    def test_returned_inventory_cannot_change_cached_evidence(self) -> None:
        inventory = self.store.inventory()
        inventory["rungs"].clear()
        self.assertEqual(len(self.store.inventory()["rungs"]), 1)

    def test_identical_import_is_noop_and_same_source_rerun_preserves_decisions(self) -> None:
        reviewed = self.review()
        self.assertEqual(self.store.import_run(self.run_dir), reviewed)
        rerun = invented_run(self.root / "runs")
        result = self.store.import_run(rerun)
        review = result["reviews"][self.rung_id]
        self.assertEqual(review["status"], "confirmed")
        self.assertFalse(review["needs_revalidation"])
        self.assertEqual(result["revision"], reviewed["revision"] + 1)
        self.assertEqual(review["fields"], reviewed["reviews"][self.rung_id]["fields"])

    def test_changed_proposals_keep_overrides_and_require_revalidation(self) -> None:
        self.review()
        rerun = invented_run(self.root / "runs", proposal="pid_control")
        result = self.store.import_run(rerun)
        review = result["reviews"][self.rung_id]
        self.assertEqual(review["category_ids"], ["category-pid"])
        self.assertEqual(review["fields"]["DeltaV name"], "INVENTED_LOOP")
        self.assertEqual(review["status"], "needs_review")
        self.assertTrue(review["needs_revalidation"])
        self.assertIn("parser_evidence_changed", review["revalidation_reasons"])
        confirmed = self.review()["reviews"][self.rung_id]
        self.assertFalse(confirmed["needs_revalidation"])

    def test_reimporting_retained_historical_run_does_not_claim_activation(self) -> None:
        self.review()
        newer_run = invented_run(self.root / "runs", text="XIO(Input)OTE(Output);")
        current = self.store.import_run(newer_run)
        with self.assertRaisesRegex(ProjectError, "earlier analysis is already retained"):
            self.store.import_run(self.run_dir, expected_revision=current["revision"])
        self.assertEqual(self.store.state(), current)
        self.assertEqual(self.store.import_run(newer_run), current)

    def test_changed_snapshot_keeps_old_reviews_and_group_memberships(self) -> None:
        self.review()
        grouped = self.change({"op": "group", "name": "Invented pump", "member_ids": [self.rung_id, self.instruction_id]})
        group_id = grouped["groups"][0]["id"]
        new_run = invented_run(self.root / "runs", text="XIO(Input)OTE(Output);")
        result = self.store.import_run(new_run)
        old = result["reviews"][self.rung_id]
        self.assertFalse(old["active"])
        self.assertIn("source_changed_requires_correspondence", old["revalidation_reasons"])
        self.assertEqual(result["groups"][0]["id"], group_id)
        self.assertEqual(set(result["groups"][0]["unresolved_member_ids"]), {self.rung_id, self.instruction_id})
        new_id = self.store.inventory()["rungs"][0]["id"]
        self.assertNotIn(new_id, result["reviews"])
        rebound = self.change({"op": "rebind", "from_id": self.rung_id, "to_id": new_id})
        self.assertIn(self.rung_id, rebound["reviews"])
        self.assertEqual(rebound["reviews"][new_id]["previous_source_id"], self.rung_id)
        self.assertEqual(rebound["reviews"][new_id]["status"], "needs_review")
        self.assertIn(new_id, rebound["groups"][0]["member_ids"])
        self.assertIn(self.rung_id, rebound["groups"][0]["member_ids"])

    def test_rebinding_never_overwrites_existing_review(self) -> None:
        self.review()
        self.review(source_ids=[self.instruction_id])
        before = self.store.state()
        with self.assertRaises(ProjectError):
            self.change({"op": "rebind", "from_id": self.rung_id, "to_id": self.instruction_id})
        self.assertEqual(self.store.state(), before)

    def test_stale_revision_rejected_atomically_across_connections(self) -> None:
        with ProjectStore(self.store.path) as other:
            base = other.state()["revision"]
            self.review()
            current = self.store.state()
            with self.assertRaisesRegex(ProjectError, "changed"):
                other.mutate({"op": "category", "name": "Stale category"}, base)
            with self.assertRaisesRegex(ProjectError, "changed"):
                other.import_run(self.run_dir, expected_revision=base)
        self.assertEqual(self.store.state(), current)

    def test_batch_validation_rolls_back_every_record(self) -> None:
        before = self.store.state()
        with self.assertRaises(ProjectError):
            self.review(source_ids=[self.rung_id, "missing-source"])
        self.assertEqual(self.store.state(), before)

    def test_custom_categories_and_many_to_many_groups_keep_stable_ids(self) -> None:
        first = self.change({"op": "category", "name": "Nested timers"})
        category = next(c for c in first["categories"] if c["name"] == "Nested timers")
        renamed = self.change({"op": "category", "id": category["id"], "name": "State timers"})
        self.assertIn({"id": category["id"], "name": "State timers"}, renamed["categories"])
        entity_id = self.store.inventory()["entities"][0]["id"]
        self.review(source_ids=[self.rung_id, self.instruction_id, entity_id], category_ids=[category["id"]])
        self.change({"op": "group", "name": "First", "member_ids": [self.rung_id, self.instruction_id]})
        state = self.change({"op": "group", "name": "Second", "member_ids": [self.rung_id, entity_id]})
        self.assertEqual(len(state["groups"]), 2)
        self.assertTrue(all(self.rung_id in group["member_ids"] for group in state["groups"]))

    def test_undo_adds_history_and_restores_prior_review(self) -> None:
        first = self.review()
        changed = self.review(status="needs_review", fields={"DeltaV name": "NEW_NAME"})
        undone = self.change({"op": "undo"})
        self.assertEqual(undone["reviews"], first["reviews"])
        self.assertEqual(undone["revision"], changed["revision"] + 1)
        self.assertEqual(undone["history"][0]["operation"], "undo")
        self.assertEqual(undone["history"][1]["undone_revision"], undone["revision"])
        self.assertEqual(self.change({"op": "undo"})["reviews"], {})
        with self.assertRaisesRegex(ProjectError, "no edits"):
            self.change({"op": "undo"})

    def test_function_and_migration_decisions_survive_membership_edits_backup_and_undo(self) -> None:
        before = self.store.artifact('snapshot.L5X')
        first = self.change({'op': 'group', 'name': 'Invented calculation', 'member_ids': [self.rung_id],
                             'function_categories': ['dc', 'alarm'], 'migration_status': 'replace',
                             'migration_note': 'Keep behavior using the target alarm class.'})
        group = first['groups'][0]
        edited = self.change({'op': 'group', 'id': group['id'], 'name': group['name'],
                              'member_ids': [self.rung_id, self.instruction_id]})['groups'][0]
        for field in ('function_categories', 'migration_status', 'migration_note'):
            self.assertEqual(edited[field], group[field])
        backup = self.store.backup(self.root / 'backups' / 'classified.sqlite')
        with ProjectStore(backup) as reopened:
            self.assertEqual(reopened.state()['groups'], [edited])
            self.assertEqual(reopened.artifact('snapshot.L5X'), before)
        undone = self.change({'op': 'undo'})['groups'][0]
        self.assertEqual(undone['member_ids'], [self.rung_id])
        self.assertEqual(undone['migration_status'], 'replace')

    def test_invalid_function_or_migration_metadata_does_not_write(self) -> None:
        before = self.store.state()
        for extra in ({'function_categories': ['fictional']}, {'migration_status': 'silently_drop'},
                      {'migration_status': []}, {'migration_note': 'x' * 4001},
                      {'proposal_id': 'invented', 'proposal_signature': 'wrong'}):
            with self.subTest(extra=extra), self.assertRaises(ProjectError):
                self.change({'op': 'group', 'name': 'Invalid', 'member_ids': [self.rung_id], **extra})
            self.assertEqual(self.store.state(), before)

    def test_undo_does_not_remove_imported_evidence(self) -> None:
        self.review()
        self.store.import_run(invented_run(self.root / "runs"))
        with self.assertRaisesRegex(ProjectError, "latest source import"):
            self.change({"op": "undo"})
        self.assertEqual(len(self.store.state()["runs"]), 2)

    def test_portable_backup_restores_every_artifact_and_review(self) -> None:
        reviewed = self.review()
        destination = self.store.backup(self.root / "backups" / "project.sqlite")
        # The backup needs no original run directory or adjacent JSON files.
        with ProjectStore(destination) as restored:
            self.assertEqual(restored.state(), reviewed)
            self.assertEqual(restored.artifact("snapshot.L5X"), (self.run_dir / "snapshot.L5X").read_bytes())
            self.assertEqual(restored.artifact("review.html"), (self.run_dir / "review.html").read_bytes())
        with self.assertRaises(ProjectError):
            self.store.backup(destination)
        with self.assertRaises(ProjectError):
            self.store.backup(self.store.path)

    def test_tampered_artifact_or_missing_manifest_never_imports(self) -> None:
        before = self.store.state()
        for target in ("inventory.json", "review.html", "snapshot.L5X"):
            run = invented_run(self.root / "runs")
            (run / target).write_bytes(b"tampered")
            with self.assertRaises(ProjectError):
                self.store.import_run(run)
            self.assertEqual(self.store.state(), before)
        run = invented_run(self.root / "runs")
        (run / "manifest.json").rename(run / ".manifest.pending")
        with self.assertRaises(ProjectError):
            self.store.import_run(run)

    def test_manifest_traversal_unknown_schema_and_limit_rejected(self) -> None:
        for mode in ("traversal", "schema", "limit"):
            run = invented_run(self.root / "runs")
            path = run / "manifest.json"
            manifest = json.loads(path.read_text())
            if mode == "traversal":
                manifest["artifacts"]["../escape"] = {"size_bytes": 0, "sha256": "0" * 64}
            elif mode == "schema":
                manifest["schema_version"] = 999
            else:
                manifest["artifacts"]["review.html"]["size_bytes"] = 2**40
            path.write_text(json.dumps(manifest))
            with self.assertRaises(ProjectError):
                self.store.import_run(run)

    def test_forged_snapshot_and_duplicate_inventory_ids_rejected(self) -> None:
        for mode in ("snapshot", "duplicate"):
            run = invented_run(self.root / "runs")
            inventory = json.loads((run / "inventory.json").read_text())
            if mode == "snapshot":
                inventory["snapshot"]["id"] = "sha256:" + "0" * 64
            else:
                inventory["rungs"].append(inventory["rungs"][0])
            attach(run, "inventory.json", json.dumps(inventory).encode())
            with self.assertRaises(ProjectError):
                self.store.import_run(run)

    def test_project_and_backup_inside_checkout_require_confidential(self) -> None:
        checkout = Path(__file__).resolve().parents[2]
        with self.assertRaises(ProjectError):
            ProjectStore(checkout / "public" / "must-not-exist.sqlite")
        with self.assertRaises(ProjectError):
            self.store.backup(checkout / "public" / "must-not-exist.sqlite")

    def test_invalid_commands_are_safe_errors_and_make_no_changes(self) -> None:
        invalid = [
            {"op": []}, {"op": "review", "source_ids": []},
            {"op": "review", "source_ids": [self.rung_id], "status": []},
            {"op": "review", "source_ids": [self.rung_id], "fields": {"Name": 42}},
            {"op": "review", "source_ids": [self.rung_id], "category_ids": ["missing"]},
            {"op": "category", "name": ""}, {"op": "category", "id": ["bad"], "name": "Name"},
            {"op": "group", "name": "Group", "member_ids": ["missing"]},
        ]
        before = self.store.state()
        for command in invalid:
            with self.subTest(command=command), self.assertRaises(ProjectError):
                self.change(command)
            self.assertEqual(self.store.state(), before)

    def test_unrelated_database_is_not_modified(self) -> None:
        path = self.root / "unrelated.sqlite"
        with closing(sqlite3.connect(path)) as database:
            database.execute("CREATE TABLE unrelated (value TEXT)")
            database.commit()
        before = path.read_bytes()
        with self.assertRaises(ProjectError):
            ProjectStore(path)
        self.assertEqual(path.read_bytes(), before)

    def test_inventory_only_run_reports_missing_analysis_honestly(self) -> None:
        self.store.import_run(invented_run(self.root / "runs", extra=False))
        self.assertEqual(self.store.analysis(), {})
        with self.assertRaises(ProjectError):
            self.store.artifact("review.html")

    def test_bounded_read_rejects_oversized_artifacts(self) -> None:
        run = invented_run(self.root / "runs")
        with patch("plc_workbench.project_store.MAX_ARTIFACT_BYTES", 1):
            with self.assertRaises(ProjectError):
                self.store.import_run(run)

    def test_partial_bulk_review_preserves_per_source_properties(self) -> None:
        self.review()
        self.review(source_ids=[self.instruction_id], fields={"DeltaV name": "SECOND"}, category_ids=["category-timer"])
        result = self.change({"op": "review", "source_ids": [self.rung_id, self.instruction_id], "status": "needs_review"})
        self.assertEqual(result["reviews"][self.rung_id]["fields"], {"DeltaV name": "INVENTED_LOOP"})
        self.assertEqual(result["reviews"][self.instruction_id]["fields"], {"DeltaV name": "SECOND"})
        self.assertEqual(result["reviews"][self.instruction_id]["category_ids"], ["category-timer"])
        result = self.change({"op": "review", "source_ids": [self.rung_id, self.instruction_id], "category_ids": []})
        self.assertEqual(result["reviews"][self.rung_id]["category_ids"], [])
        self.assertEqual(result["reviews"][self.instruction_id]["fields"], {"DeltaV name": "SECOND"})
        with self.assertRaises(ProjectError):
            self.change({"op": "review", "source_ids": [self.rung_id]})

    def test_category_only_change_does_not_reaffirm_stale_evidence(self) -> None:
        self.review()
        self.store.import_run(invented_run(self.root / "runs", proposal="timer"))
        state = self.change({"op": "review", "source_ids": [self.rung_id], "category_ids": ["category-timer"]})
        self.assertTrue(state["reviews"][self.rung_id]["needs_revalidation"])
        self.assertEqual(state["reviews"][self.rung_id]["status"], "needs_review")

    def test_rule_proposes_without_changing_source_or_manual_categories(self) -> None:
        self.review()
        original = self.store.inventory()
        result = self.change({"op": "rule", "name": "Simple Boolean", "source_id": self.rung_id, "category_ids": ["category-miscellaneous"], "enabled": True})
        rule = result["rules"][0]
        self.assertEqual(rule["pattern"], {"kind": "sequence", "items": [{"kind": "instruction", "opcode": "XIC"}, {"kind": "instruction", "opcode": "OTE"}]})
        self.assertEqual(result["reviews"][self.rung_id]["category_ids"], ["category-pid"])
        self.assertEqual(result["reviews"][self.rung_id]["status"], "needs_review")
        self.assertEqual(self.store.inventory(), original)
        reverted = self.change({"op": "undo"})
        self.assertEqual(reverted["rules"], [])
        self.assertEqual(reverted["reviews"][self.rung_id]["status"], "confirmed")

    def test_rule_signature_preserves_branch_structure_and_ignores_operands(self) -> None:
        one = self.store.inventory()["rungs"][0]
        other_run = invented_run(self.root / "runs", text="XIC(Other)OTE(Another);")
        other = json.loads((other_run / "inventory.json").read_text())["rungs"][0]
        branch_run = invented_run(self.root / "runs", text="[XIC(Input),]OTE(Output);")
        branched = json.loads((branch_run / "inventory.json").read_text())["rungs"][0]
        self.assertEqual(rung_pattern(one), rung_pattern(other))
        self.assertNotEqual(rung_pattern(one), rung_pattern(branched))

    def test_rule_can_be_disabled_after_example_source_changes(self) -> None:
        state = self.change({"op": "rule", "name": "Example", "source_id": self.rung_id, "category_ids": ["category-pid"]})
        rule_id = state["rules"][0]["id"]
        self.store.import_run(invented_run(self.root / "runs", text="XIO(Input)OTE(Output);"))
        result = self.change({"op": "rule", "id": rule_id, "enabled": False})
        self.assertFalse(result["rules"][0]["enabled"])

    def test_matching_hashes_do_not_admit_invalid_consumed_records(self) -> None:
        mutations = [
            ("inventory.json", lambda data: data["entities"][0].update(attributes=[])),
            ("inventory.json", lambda data: data["entities"][0].update(name={})),
            ("inventory.json", lambda data: data["entities"][0].update(id=" leading-space")),
            ("inventory.json", lambda data: data["entities"][0].update(parent_id=data["entities"][0]["id"])),
            ("inventory.json", lambda data: data["rungs"][0].update(text=[])),
            ("inventory.json", lambda data: data["rungs"][0].update(parent_id="missing")),
            ("inventory.json", lambda data: data["rungs"][0]["instructions"][0].update(arguments={})),
            ("inventory.json", lambda data: data["rungs"][0]["instructions"][0].update(opcode="")),
            ("inventory.json", lambda data: data["rungs"][0]["instructions"][0].update(end=10**9)),
            ("inventory.json", lambda data: data["rungs"][0]["structure"]["items"][0].update(instruction_id="missing")),
            ("inventory.json", lambda data: data["rungs"][0]["structure"]["items"].clear()),
            ("rung-analysis.json", lambda data: data["candidates"][0].pop("rung_id")),
            ("rung-analysis.json", lambda data: data["candidates"][0].update(rung_id="missing")),
            ("rung-analysis.json", lambda data: data["candidates"][0].update(category=[])),
            ("rung-analysis.json", lambda data: data["candidates"][0].update(missing_evidence=None)),
            ("rung-analysis.json", lambda data: data["rungs"].clear()),
            ("rung-analysis.json", lambda data: data["blocks"][0].update(rung_id="missing")),
            ("references.json", lambda data: data["snapshot"].update(id="different")),
            ("references.json", lambda data: data["operands"].clear()),
            ("references.json", lambda data: data["operands"][0].update(instruction_id="missing")),
            ("references.json", lambda data: data["operands"][0].update(rung_id="missing")),
            ("references.json", lambda data: data["operands"][0].update(target_id=[])),
            ("references.json", lambda data: data["operands"][0].update(argument_index=True)),
            ("references.json", lambda data: data["operands"][0].update(raw_text="DifferentArgument")),
        ]
        before = self.store.state()
        for artifact, mutate in mutations:
            with self.subTest(artifact=artifact, mutation=mutate):
                run = invented_run(self.root / "runs")
                data = json.loads((run / artifact).read_text())
                mutate(data)
                attach(run, artifact, json.dumps(data).encode())
                with self.assertRaises(ProjectError):
                    self.store.import_run(run)
                self.assertEqual(self.store.state(), before)

    def test_invalid_import_then_repaired_same_identifier_has_no_poisoned_cache(self) -> None:
        run = invented_run(self.root / "runs")
        original = (run / "rung-analysis.json").read_bytes()
        broken = json.loads(original)
        broken["candidates"][0].pop("rung_id")
        attach(run, "rung-analysis.json", json.dumps(broken).encode())
        with self.assertRaises(ProjectError):
            self.store.import_run(run)
        attach(run, "rung-analysis.json", original)
        state = self.store.import_run(run)
        self.assertEqual(len(state["runs"]), 2)
        self.assertIn("rung_id", self.store.analysis()["candidates"][0])

    def test_unrelated_version_one_database_and_incomplete_project_are_unchanged(self) -> None:
        for application in (0, 0x504C4357):
            path = self.root / f"unrelated-{application}.sqlite"
            with closing(sqlite3.connect(path)) as database:
                database.execute("CREATE TABLE unrelated (value TEXT)")
                database.execute("PRAGMA user_version=1")
                database.execute(f"PRAGMA application_id={application}")
                database.commit()
            before = path.read_bytes()
            with self.assertRaises(ProjectError):
                ProjectStore(path)
            self.assertEqual(path.read_bytes(), before)

    def test_missing_names_and_unparsed_source_remain_reviewable(self) -> None:
        run = invented_run(self.root / "runs", text="XIC(", extra=False)
        inventory = json.loads((run / "inventory.json").read_text())
        inventory["entities"][0]["name"] = None
        attach(run, "inventory.json", json.dumps(inventory).encode())
        self.store.import_run(run)
        self.assertIsNone(self.store.inventory()["entities"][0]["name"])
        self.assertEqual(self.store.inventory()["rungs"][0]["parse_status"], "failed")

    def test_nonfinite_saved_json_rejected_before_import(self) -> None:
        run = invented_run(self.root / "runs")
        inventory = json.loads((run / "inventory.json").read_text())
        inventory["extra"] = float("nan")
        attach(run, "inventory.json", json.dumps(inventory).encode())
        with self.assertRaises(ProjectError):
            self.store.import_run(run)


if __name__ == "__main__":
    unittest.main()
