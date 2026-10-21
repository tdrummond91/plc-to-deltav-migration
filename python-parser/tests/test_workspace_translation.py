"""Translation cache tests use invented wording and an injected local engine."""
from pathlib import Path
from contextlib import closing
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from plc_workbench.workspace_translation import TranslationService


class FakeEngine:
    def __init__(self, calls, *, model_id="test-fr-en-v1", callback=None):
        self.calls = calls
        self.model_id = model_id
        self.callback = callback

    def identity(self):
        return self.model_id

    def translate(self, text):
        self.calls.append(text)
        if self.callback is not None:
            return self.callback(text)
        return {"text": f"English: {text}", "status": "translated"}


class TranslationServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.cache = Path(self.directory.name) / "project.translations.sqlite"
        self.calls = []
        self.services = []
        self.addCleanup(self.close_services)

    def close_services(self):
        for service in self.services:
            service.close()

    def service(self, *, model_id="test-fr-en-v1", available=True, callback=None, engine_factory=None, availability_provider=None):
        service = TranslationService(
            self.cache,
            Path(self.directory.name) / "model",
            engine_factory=engine_factory or (lambda _: FakeEngine(self.calls, model_id=model_id, callback=callback)),
            availability_provider=availability_provider or (lambda _: {
                "available": available, "model_id": model_id,
                "message": "Ready" if available else "Install the local model",
            }),
        )
        self.services.append(service)
        return service

    def complete(self, service):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            state = service.status()
            if state["state"] != "running":
                return state
            time.sleep(0.005)
        self.fail("Local test translation worker did not finish")

    def test_deduplicate_exact_text_and_reuse_after_restart(self):
        service = self.service()
        service.set_enabled(True)
        service.start(["Pompe en marche", "Pompe en marche", "Pression haute", "", " "])
        state = self.complete(service)
        self.assertEqual(state["state"], "complete")
        self.assertEqual((state["total"], state["completed"], state["cached"]), (2, 2, 0))
        self.assertEqual(self.calls, ["Pompe en marche", "Pression haute"])
        service.close()
        reopened = self.service()
        self.assertTrue(reopened.status()["enabled"])
        result = reopened.lookup("Pompe en marche")
        self.assertEqual(result["text"], "English: Pompe en marche")
        self.assertTrue(result["cached"])
        state = reopened.start(["Pompe en marche", "Pression haute"])
        self.assertEqual((state["completed"], state["cached"]), (2, 2))
        self.assertEqual(len(self.calls), 2)

    def test_changed_text_whitespace_or_model_has_distinct_cache_entry(self):
        service = self.service()
        service.start(["Marche"])
        self.complete(service)
        service.start(["Marche", " Marche", "Arret"])
        state = self.complete(service)
        self.assertEqual(state["cached"], 1)
        self.assertEqual(len(self.calls), 3)
        other_model = self.service(model_id="test-fr-en-v2")
        self.assertIsNone(other_model.lookup("Marche"))
        other_model.start(["Marche"])
        self.complete(other_model)
        self.assertEqual(len(self.calls), 4)
        self.assertEqual(service.lookup("Marche")["model_id"], "test-fr-en-v1")

    def test_rules_version_invalidates_without_deleting_old_translation(self):
        service = self.service()
        service.start(["Alarme"])
        self.complete(service)
        with patch("plc_workbench.workspace_translation.CACHE_RULES_VERSION", "future-v2"):
            self.assertIsNone(service.lookup("Alarme"))
            service.start(["Alarme"])
            self.complete(service)
        self.assertEqual(len(self.calls), 2)
        self.assertIsNotNone(service.lookup("Alarme"))

    def test_failed_text_is_safe_cached_and_retried_only_explicitly(self):
        failed = True

        def translate(text):
            if failed:
                raise RuntimeError(f"Sensitive input: {text}")
            return {"text": "Pump running", "status": "translated"}

        service = self.service(callback=translate)
        service.start(["Texte prive invente"])
        state = self.complete(service)
        self.assertEqual((state["failed"], state["needs_review"]), (1, 1))
        self.assertNotIn("Texte prive", str(state))
        result = service.lookup("Texte prive invente")
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["text"], "")
        self.assertNotIn("Texte prive", result["warning"])
        service.start(["Texte prive invente"])
        self.assertEqual(len(self.calls), 1)
        failed = False
        service.start(["Texte prive invente"], retry=True)
        state = self.complete(service)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(state["failed"], 0)
        self.assertEqual(service.lookup("Texte prive invente")["text"], "Pump running")

    def test_needs_review_candidate_retained_and_does_not_retry_as_failure(self):
        service = self.service(callback=lambda _: {
            "text": "Pump enabled", "status": "needs_review", "warning": "Private arbitrary engine output",
        })
        service.start(["Marche pompe"])
        state = self.complete(service)
        self.assertEqual((state["failed"], state["needs_review"]), (0, 1))
        result = service.lookup("Marche pompe")
        self.assertEqual(result["text"], "Pump enabled")
        self.assertNotIn("Private", result["warning"])
        service.start(["Marche pompe"], retry=True)
        self.assertEqual(len(self.calls), 1)

    def test_missing_model_still_reads_cache_without_starting_engine(self):
        service = self.service()
        service.start(["Arret pompe"])
        self.complete(service)
        service.close()
        missing = self.service(available=False, engine_factory=lambda _: self.fail("Engine must not load"))
        self.assertEqual(missing.lookup("Arret pompe")["text"], "English: Arret pompe")
        self.assertEqual(missing.start(["Arret pompe"])["state"], "complete")
        state = missing.start(["Nouveau texte"])
        self.assertEqual(state["state"], "error")
        self.assertEqual(state["message"], "Install the local model")
        self.assertIsNone(missing.lookup("Nouveau texte"))

    def test_large_cached_batch_uses_one_connection_for_the_cache_scan(self):
        service = self.service()
        texts = tuple(f"Commentaire invente {index}" for index in range(100))
        # Populate via the service so the test checks the real key/row contract.
        service.start(texts)
        self.complete(service)
        with patch.object(service, "_connect", wraps=service._connect) as connections:
            state = service.start(texts)
        self.assertEqual(state["cached"], len(texts))
        self.assertEqual(connections.call_count, 1)
        self.assertEqual(len(self.calls), len(texts))

    def test_engine_identity_mismatch_does_not_pollute_cache(self):
        service = self.service(engine_factory=lambda _: FakeEngine(self.calls, model_id="wrong-model"))
        service.start(["Marche"])
        state = self.complete(service)
        self.assertEqual(state["state"], "error")
        self.assertEqual(self.calls, [])
        self.assertIsNone(service.lookup("Marche"))

    def test_active_batch_does_not_block_queries_or_accept_mutated_list(self):
        entered = threading.Event()
        release = threading.Event()
        self.addCleanup(release.set)

        def translate(text):
            entered.set()
            if not release.wait(2):
                raise RuntimeError("Test worker timed out")
            return {"text": "Translated", "status": "translated"}

        service = self.service(callback=translate)
        inputs = ["Premier", "Deuxieme"]
        service.start(inputs)
        self.assertTrue(entered.wait(1))
        inputs.append("Not in the snapshot")
        self.assertEqual(service.status()["total"], 2)
        self.assertIsNone(service.lookup("Premier"))
        self.assertEqual(service.start(["Another job"])["total"], 2)
        release.set()
        self.complete(service)
        self.assertEqual(self.calls, ["Premier", "Deuxieme"])

    def test_disable_stops_after_current_item_and_completed_cache_survives(self):
        entered = threading.Event()
        release = threading.Event()
        self.addCleanup(release.set)

        def translate(text):
            entered.set()
            release.wait(2)
            return {"text": "Translated", "status": "translated"}

        service = self.service(callback=translate)
        service.set_enabled(True)
        service.start(["Premier", "Deuxieme"])
        self.assertTrue(entered.wait(1))
        service.set_enabled(False)
        self.assertEqual(service.status()["state"], "running")
        release.set()
        state = self.complete(service)
        self.assertEqual(state["state"], "cancelled")
        self.assertEqual(state["completed"], 1)
        self.assertIsNotNone(service.lookup("Premier"))
        self.assertIsNone(service.lookup("Deuxieme"))
        self.assertFalse(self.service().status()["enabled"])
        service.set_enabled(True)
        service.start(["Premier", "Deuxieme"])
        state = self.complete(service)
        self.assertEqual((state["completed"], state["cached"]), (2, 1))

    def test_no_network_or_subprocess_is_required(self):
        with patch("socket.socket", side_effect=AssertionError("No network")), patch(
            "subprocess.Popen", side_effect=AssertionError("No subprocess"),
        ):
            service = self.service()
            service.start(["Pression basse"])
            self.assertEqual(self.complete(service)["state"], "complete")
            self.assertIsNotNone(service.lookup("Pression basse"))

    def test_bad_availability_and_engine_response_fail_without_input_leak(self):
        broken = self.service(availability_provider=lambda _: (_ for _ in ()).throw(RuntimeError("secret")))
        self.assertNotIn("secret", str(broken.status()))
        self.assertFalse(broken.status()["available"])
        service = self.service(callback=lambda _: {"text": 5, "status": "translated"})
        service.start(["Marche"])
        self.assertEqual(self.complete(service)["failed"], 1)
        self.assertEqual(service.lookup("Marche")["status"], "needs_review")

    def test_empty_batch_and_closed_service_do_not_start_a_worker(self):
        service = self.service()
        self.assertEqual(service.start([])["state"], "complete")
        service.close()
        service.start(["Marche"])
        self.assertEqual(self.calls, [])

    def test_only_sidecar_tables_are_written(self):
        service = self.service()
        service.start(["Marche"])
        self.complete(service)
        with closing(sqlite3.connect(self.cache)) as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(tables, {"translation_settings", "english_translations"})


if __name__ == "__main__":
    unittest.main()
