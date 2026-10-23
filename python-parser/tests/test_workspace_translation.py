"""Translation cache tests use invented wording and an injected local engine."""
from pathlib import Path
from contextlib import closing
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from plc_workbench.workspace_translation import TranslationService, WORKER_BATCH_TEXTS


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


class BatchEngine(FakeEngine):
    def translate_many(self, texts):
        self.calls.append(tuple(texts))
        if self.callback is not None:
            return self.callback(texts)
        return [{"text": f"English: {text}", "status": "translated"} for text in texts]


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
        self.assertFalse(result["partial"])
        self.assertIsNone(result["translated_segments"])
        self.assertIsNone(result["retained_segments"])
        self.assertNotIn("Private", result["warning"])
        service.start(["Marche pompe"], retry=True)
        self.assertEqual(len(self.calls), 1)

    def test_old_cache_schema_migrates_without_retranslating_successes(self):
        source, failed_source = "Pompe en marche", "Ancienne note manquante"
        with closing(sqlite3.connect(self.cache)) as connection:
            connection.executescript("""
                CREATE TABLE english_translations (
                    model_id TEXT NOT NULL, rules_version TEXT NOT NULL,
                    source_hash TEXT NOT NULL, source_text TEXT NOT NULL,
                    english_text TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('translated', 'needs_review')),
                    failed INTEGER NOT NULL CHECK(failed IN (0, 1)),
                    PRIMARY KEY(model_id, rules_version, source_hash, source_text)
                );
            """)
            connection.executemany("INSERT INTO english_translations VALUES (?, ?, ?, ?, ?, ?, ?)", [
                (*TranslationService._key(source, "test-fr-en-v1"), "Pump running", "translated", 0),
                (*TranslationService._key(failed_source, "test-fr-en-v1"), "", "needs_review", 1),
            ])
            connection.commit()
        service = self.service()
        state = service.start([source, failed_source])
        self.assertEqual((state["cached"], state["failed"], state["partial"]), (2, 1, 0))
        self.assertEqual(self.calls, [])
        entry = service.lookup(source)
        self.assertEqual(entry["text"], "Pump running")
        self.assertFalse(entry["partial"])
        self.assertIsNone(entry["translated_segments"])
        service.start([source, failed_source], retry=True)
        self.complete(service)
        self.assertEqual(self.calls, [failed_source])
        self.assertEqual(service.lookup(source)["text"], "Pump running")
        with closing(sqlite3.connect(self.cache)) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM english_translations").fetchone()[0], 2)

    def test_partial_composite_survives_restart_and_retries_only_explicitly(self):
        source = "Pompe en marche.\r\nPression maximale 2,5 bar."
        composite = "Pump running.\r\nPression maximale 2,5 bar."
        service = self.service(callback=lambda _: {
            "text": composite, "status": "needs_review", "failed": False, "partial": True,
            "translated_segments": 1, "retained_segments": 1,
        })
        service.start([source])
        state = self.complete(service)
        self.assertEqual((state["needs_review"], state["failed"], state["partial"]), (1, 0, 1))
        signature = state["cache_signature"]
        service.close()
        reopened = self.service(callback=lambda _: {
            "text": "Pump running.\r\nMaximum pressure 2,5 bar.", "status": "translated", "failed": False,
            "partial": False, "translated_segments": 2, "retained_segments": 0,
        })
        entry = reopened.lookup(source)
        self.assertEqual(entry["text"], composite)
        self.assertTrue(entry["partial"])
        self.assertEqual((entry["translated_segments"], entry["retained_segments"]), (1, 1))
        self.assertIn("original language", entry["warning"])
        cached = reopened.start([source])
        self.assertEqual((cached["cached"], cached["partial"], len(self.calls)), (1, 1, 1))
        self.assertEqual(cached["cache_signature"], signature)
        reopened.start([source], retry=True)
        state = self.complete(reopened)
        self.assertEqual((state["partial"], state["failed"], state["needs_review"], len(self.calls)), (0, 0, 0, 2))
        self.assertNotEqual(state["cache_signature"], signature)
        self.assertFalse(reopened.lookup(source)["partial"])

    def test_all_retained_nonempty_source_is_failed_and_can_be_retried(self):
        service = self.service(callback=lambda source: {
            "text": source, "status": "needs_review", "failed": True, "partial": False,
            "translated_segments": 0, "retained_segments": 2,
        })
        source = "Premiere note.\nDeuxieme note."
        service.start([source])
        state = self.complete(service)
        self.assertEqual((state["failed"], state["partial"]), (1, 0))
        self.assertEqual(service.lookup(source)["text"], source)
        self.assertTrue(service.lookup(source)["failed"])
        service.start([source])
        self.assertEqual(len(self.calls), 1)
        service.start([source], retry=True)
        self.complete(service)
        self.assertEqual(len(self.calls), 2)

    def test_interrupted_batch_is_saved_without_silently_repeating_inference(self):
        source = "Commentaire interrompu"
        service = self.service()
        # This is the durable state after a process exits during model inference.
        service._begin_attempt((source,), "test-fr-en-v1")
        self.assertIsNone(service.lookup(source))  # Still active, not a completed failure.
        service.close()
        reopened = self.service()
        state = reopened.start([source])
        self.assertEqual((state["state"], state["cached"], state["interrupted"]), ("complete", 1, 1))
        self.assertEqual((state["new_texts"], state["retry_texts"], state["cached_incomplete"]), (0, 0, 1))
        self.assertEqual(self.calls, [])
        entry = reopened.lookup(source)
        self.assertEqual(entry["text"], source)
        self.assertTrue(entry["interrupted"])
        self.assertIn("Retry incomplete", entry["warning"])
        reopened.start([source], retry=True)
        state = self.complete(reopened)
        self.assertEqual((state["retry_texts"], state["interrupted"], state["failed"]), (1, 0, 0))
        self.assertEqual(self.calls, [source])
        self.assertFalse(reopened.lookup(source)["interrupted"])

    def test_interrupted_retry_preserves_previous_partial_wording_and_model_partition(self):
        source, composite = "Pompe marche. Pression 2 bar.", "Pump running. Pression 2 bar."
        service = self.service(callback=lambda _: {
            "text": composite, "status": "needs_review", "translated_segments": 1, "retained_segments": 1,
        })
        service.start([source])
        self.complete(service)
        service._begin_attempt((source,), "test-fr-en-v1")
        service.close()
        reopened = self.service()
        state = reopened.start([source])
        self.assertEqual((state["partial"], state["interrupted"], state["cached"]), (1, 1, 1))
        self.assertEqual(reopened.lookup(source)["text"], composite)
        self.assertEqual(len(self.calls), 1)
        upgraded = self.service(model_id="test-fr-en-v2")
        self.assertIsNone(upgraded.lookup(source))
        upgraded.start([source])
        state = self.complete(upgraded)
        self.assertEqual((state["new_texts"], state["cached"], state["interrupted"]), (1, 0, 0))
        self.assertEqual(reopened.lookup(source)["text"], composite)

    def test_unchanged_output_is_saved_labeled_and_retried_only_by_choice(self):
        source = "Pump running"
        service = self.service(callback=lambda text: {"text": text, "status": "translated"})
        service.start([source])
        state = self.complete(service)
        self.assertEqual((state["unchanged"], state["failed"]), (1, 0))
        service.close()
        reopened = self.service()
        state = reopened.start([source])
        self.assertEqual((state["cached"], state["unchanged"], state["retry_texts"]), (1, 1, 0))
        self.assertTrue(reopened.lookup(source)["unchanged"])
        self.assertEqual(len(self.calls), 1)
        reopened.start([source], retry=True)
        state = self.complete(reopened)
        self.assertEqual((state["unchanged"], state["retry_texts"], len(self.calls)), (0, 1, 2))

    def test_failed_cache_write_leaves_recoverable_attempt_without_leaking_input(self):
        service = self.service()
        before = service.status()['cache_signature']
        with patch.object(service, "_save_many", side_effect=OSError("Private source details")):
            service.start(["Texte prive"])
            state = self.complete(service)
        self.assertEqual(state["state"], "error")
        self.assertNotIn("Private", state["message"])
        self.assertTrue(service.lookup("Texte prive")["interrupted"])
        self.assertNotEqual(service.status()['cache_signature'], before)
        service.close()
        reopened = self.service()
        self.assertEqual(reopened.start(["Texte prive"])["interrupted"], 1)
        self.assertEqual(self.calls, ["Texte prive"])

    def test_failed_explicit_retry_preserves_partial_text_and_records_attempt_outcome(self):
        source, saved = 'Pompe en marche. Pression haute.', 'Pump running. Pression haute.'
        fail = False

        def translate(_):
            if fail:
                raise RuntimeError('Private model failure')
            return {'text': saved, 'status': 'needs_review', 'translated_segments': 1, 'retained_segments': 1}

        service = self.service(callback=translate)
        service.start([source])
        self.complete(service)
        fail = True
        service.start([source], retry=True)
        state = self.complete(service)
        self.assertEqual((state['partial'], state['failed'], state['retry_failed']), (1, 0, 1))
        entry = service.lookup(source)
        self.assertEqual(entry['text'], saved)
        self.assertTrue(entry['partial'])
        self.assertTrue(entry['last_attempt_failed'])
        self.assertFalse(entry['failed'])  # Saved English remains usable in the view.
        self.assertIn('latest local retry failed', entry['warning'])
        service.close()
        reopened = self.service()
        state = reopened.start([source])
        self.assertEqual((state['cached'], state['retry_failed'], len(self.calls)), (1, 1, 2))
        self.assertEqual(reopened.lookup(source)['text'], saved)
        reopened.start([source], retry=True)
        state = self.complete(reopened)
        self.assertEqual((state['partial'], state['retry_failed']), (0, 0))
        self.assertFalse(reopened.lookup(source)['last_attempt_failed'])

    def test_attempt_start_and_interrupted_transition_each_invalidate_cached_views(self):
        service = self.service()
        source = 'Pompe en marche'
        service.start([source])
        self.complete(service)
        before = service.status()['cache_signature']
        service._begin_attempt((source,), 'test-fr-en-v1')
        active = service.status()['cache_signature']
        self.assertNotEqual(active, before)
        self.assertFalse(service.lookup(source)['interrupted'])
        service._fail('Saved test interruption')
        interrupted = service.status()['cache_signature']
        self.assertNotEqual(interrupted, active)
        self.assertTrue(service.lookup(source)['interrupted'])
        service.close()
        self.assertEqual(self.service().status()['cache_signature'], interrupted)

    def test_malformed_partial_metadata_does_not_certify_generic_candidate(self):
        result = TranslationService._validated_output({
            "text": "Candidate wording", "status": "needs_review", "partial": True,
            "translated_segments": True, "retained_segments": "one",
        })
        self.assertEqual(result["status"], "needs_review")
        self.assertFalse(result["partial"])
        self.assertIsNone(result["translated_segments"])
        self.assertIsNone(result["retained_segments"])

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
        self.assertEqual(tables, {"translation_settings", "english_translations", "english_translation_attempts"})

    def test_presentation_mode_is_persisted_separate_from_preparation(self):
        service = self.service()
        self.assertEqual(service.status()["presentation_mode"], "original")
        service.set_enabled(True)
        self.assertEqual(service.status()["presentation_mode"], "both")
        service.set_mode("original")
        self.assertTrue(service.status()["enabled"])
        reopened = self.service()
        self.assertEqual(reopened.status()["presentation_mode"], "original")
        self.assertTrue(reopened.status()["enabled"])
        service.set_mode("english")
        self.assertEqual(self.service().status()["presentation_mode"], "english")
        for invalid in ("French", "", None):
            with self.assertRaises(ValueError):
                service.set_mode(invalid)

    def test_existing_enabled_setting_migrates_to_both(self):
        service = self.service()
        service._set_setting("enabled", "1")
        self.assertEqual(self.service().status()["presentation_mode"], "both")

    def test_batched_worker_commits_once_per_chunk_and_signature_survives_restart(self):
        service = self.service(engine_factory=lambda _: BatchEngine(self.calls))
        texts = [f"Texte {index}" for index in range(WORKER_BATCH_TEXTS * 2 + 1)]
        before = service.status()["cache_signature"]
        with patch.object(service, "_save_many", wraps=service._save_many) as writes:
            service.start(texts)
            state = self.complete(service)
        self.assertEqual([len(batch) for batch in self.calls], [16, 16, 1])
        self.assertEqual(writes.call_count, 3)
        self.assertEqual((state["completed"], state["failed"], state["write_generation"]), (33, 0, 6))
        self.assertNotEqual(before, state["cache_signature"])
        self.assertEqual(self.service().status()["cache_signature"], state["cache_signature"])
        self.assertEqual(state["remaining_seconds"], 0)
        with patch.object(service, "_connect", wraps=service._connect) as connections:
            entries = service.lookup_many([*texts, texts[0], "Missing", " ", None])
        self.assertEqual(connections.call_count, 1)
        self.assertEqual(set(entries), set(texts))
        service.set_mode("english")
        self.assertEqual(service.status()["cache_signature"], state["cache_signature"])
        self.assertEqual(service.start(texts)["write_generation"], 6)

    def test_batch_visibility_change_does_not_cancel_and_estimate_requires_measurement(self):
        first = threading.Event()
        second = threading.Event()
        release_first = threading.Event()
        release_second = threading.Event()
        self.addCleanup(release_first.set)
        self.addCleanup(release_second.set)
        count = 0

        def translate(texts):
            nonlocal count
            count += 1
            (first if count == 1 else second).set()
            (release_first if count == 1 else release_second).wait(2)
            return [{"text": "English", "status": "translated"} for _ in texts]

        service = self.service(engine_factory=lambda _: BatchEngine(self.calls, callback=translate))
        service.set_enabled(True)
        service.start([f"Commentaire {index}" for index in range(17)])
        self.assertTrue(first.wait(1))
        self.assertIsNone(service.status()["remaining_seconds"])
        service.set_mode("original")
        release_first.set()
        self.assertTrue(second.wait(1))
        state = service.status()
        self.assertEqual(state["completed"], 16)
        self.assertIsNotNone(state["remaining_seconds"])
        self.assertEqual(state["state"], "running")
        release_second.set()
        self.assertEqual(self.complete(service)["completed"], 17)

    def test_cancel_saves_completed_chunk_without_starting_another(self):
        entered = threading.Event()
        release = threading.Event()
        self.addCleanup(release.set)

        def translate(texts):
            entered.set()
            release.wait(2)
            return [{"text": "English", "status": "translated"} for _ in texts]

        service = self.service(engine_factory=lambda _: BatchEngine(self.calls, callback=translate))
        service.start([f"Commentaire {index}" for index in range(17)])
        self.assertTrue(entered.wait(1))
        service.set_enabled(False)
        release.set()
        state = self.complete(service)
        self.assertEqual((state["state"], state["completed"], len(self.calls)), ("cancelled", 16, 1))
        self.assertIsNotNone(service.lookup("Commentaire 15"))
        self.assertIsNone(service.lookup("Commentaire 16"))
        self.assertIsNone(state["remaining_seconds"])

    def test_bad_batch_response_is_safe_and_cached_for_each_text(self):
        service = self.service(engine_factory=lambda _: BatchEngine(self.calls, callback=lambda _: []))
        service.start(["Secret invente", "Autre texte"])
        state = self.complete(service)
        self.assertEqual((state["completed"], state["failed"]), (2, 2))
        self.assertNotIn("Secret", str(state))
        self.assertEqual(service.lookup("Secret invente")["text"], "")


if __name__ == "__main__":
    unittest.main()
