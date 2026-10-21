"""Offline engine checks; all language samples are independently invented."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from plc_workbench import local_translation_engine as engine


def fake_engine(outputs: list[str], finished: bool = True) -> engine.Engine:
    instance = engine.Engine.__new__(engine.Engine)
    instance._tokenizer = Mock()
    instance._tokenizer.encode.side_effect = lambda text, out_type: text.split()
    instance._tokenizer.decode.side_effect = lambda tokens: " ".join(tokens)
    instance._translator = Mock()
    instance._translator.translate_batch.return_value = [SimpleNamespace(hypotheses=[output.split() + (["</s>"] if finished else [])]) for output in outputs]
    return instance


def write_model_stub(root: Path) -> None:
    files = {}
    for name in engine.REQUIRED_FILES:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"synthetic-model-test")
        files[name] = {"size": target.stat().st_size, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
    (root / "installation.json").write_text(json.dumps({"package_sha256": engine.PACKAGE_SHA256, "files": files}), encoding="utf-8")


class TranslationEngineTests(unittest.TestCase):
    def test_missing_model_keeps_cache_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            result = engine.availability(Path(directory))
        self.assertFalse(result["available"])
        self.assertEqual(result["model_id"], engine.MODEL_ID)

    def test_availability_does_not_hash_weights_or_contact_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_model_stub(root)
            with patch.object(engine.importlib.util, "find_spec", return_value=object()), patch.object(engine.hashlib, "file_digest", side_effect=AssertionError("read weights")), patch("socket.socket.connect", side_effect=AssertionError("network")):
                self.assertTrue(engine.availability(root)["available"])
            with patch.object(engine.importlib.util, "find_spec", return_value=None):
                result = engine.availability(root)
                self.assertFalse(result["available"])
                self.assertEqual(result["model_id"], engine.MODEL_ID)

    def test_malformed_manifest_is_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for value in ([], {}, {"files": []}, {"files": {x: [] for x in engine.REQUIRED_FILES}, "package_sha256": engine.PACKAGE_SHA256}):
                (root / "installation.json").write_text(json.dumps(value), encoding="utf-8")
                self.assertFalse(engine.availability(root)["available"])

    def test_changed_model_bytes_fail_before_loading_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_model_stub(root)
            (root / "model/model.bin").write_bytes(b"modified-model-test!")
            with self.assertRaisesRegex(RuntimeError, "could not be opened"):
                engine.Engine(root)

    def test_mixed_comment_values_identifiers_and_units_survive(self):
        text = "Pump P101 en marche; arrêter P101 si la pression dépasse 150 kPa."
        expected = "Pump P101 on; stop P101 if pressure exceeds 150 kPa."
        instance = fake_engine([expected])
        self.assertEqual(instance.translate(text)["text"], expected)
        options = instance._translator.translate_batch.call_args.kwargs
        self.assertEqual(options["max_input_length"], 0)
        self.assertTrue(options["return_end_token"])

    def test_changed_or_added_tokens_withhold_candidate(self):
        for candidate in ("Stop P102 at 150 kPa.", "Stop P101 at 150 psi.", "Stop P101 at 15 kPa.", "Stop P101 at 150 kPa and 20 s."):
            result = fake_engine([candidate]).translate("Arrêter P101 à 150 kPa.")
            self.assertEqual(result["status"], "needs_review")
            self.assertEqual(result["text"], "")

    def test_explicit_simple_name_is_preserved(self):
        result = fake_engine(["Start the Main pump."]).translate("Démarrer la pompe Principal.", protected_tokens=["Principal"])
        self.assertEqual(result["status"], "needs_review")

    def test_negation_loss_in_either_language_is_withheld(self):
        for original in ("La pompe ne doit pas démarrer.", "Do not start la pompe."):
            self.assertEqual(fake_engine(["The pump must start."]).translate(original)["status"], "needs_review")
        self.assertEqual(fake_engine(["The pump must not start."]).translate("La pompe ne doit pas démarrer.")["status"], "translated")

    def test_negation_is_checked_per_sentence(self):
        result = fake_engine(["Pump must not start.", "Valve must open."]).translate("Pompe ne doit pas démarrer. Vanne ne doit pas ouvrir.")
        self.assertEqual(result["status"], "needs_review")

    def test_added_negation_is_withheld(self):
        result = fake_engine(["The pump must not start."]).translate("La pompe doit démarrer.")
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["text"], "")

    def test_ne_plus_negation_is_recognized_but_bare_plus_is_not(self):
        for original in ("La pompe ne démarre plus.", "La pompe n'est plus disponible."):
            result = fake_engine(["The pump is available."]).translate(original)
            self.assertEqual(result["status"], "needs_review")
        result = fake_engine(["The pump no longer starts."]).translate("La pompe ne démarre plus.")
        self.assertEqual(result["status"], "translated")
        result = fake_engine(["The pressure is higher."]).translate("La pression est plus élevée.")
        self.assertEqual(result["status"], "translated")
        result = fake_engine(["Sum plus offset."]).translate("Somme plus décalage.")
        self.assertEqual(result["status"], "translated")

    def test_long_sentence_and_text_are_not_truncated(self):
        instance = fake_engine([])
        for text in ("mot " * 141, "x" * (engine.MAX_TEXT_CHARS + 1)):
            self.assertEqual(instance.translate(text)["status"], "needs_review")
        instance._translator.translate_batch.assert_not_called()

    def test_paragraph_breaks_preserved_and_space_marker_removed(self):
        result = fake_engine(["High▁temperature.", "Stop the pump."]).translate("Température élevée.\n\nArrêter la pompe.")
        self.assertEqual(result["text"], "High temperature.\n\nStop the pump.")

    def test_incomplete_decode_is_withheld(self):
        result = fake_engine(["The pump must"], finished=False).translate("La pompe doit démarrer.")
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["text"], "")

    def test_runtime_error_does_not_leak_input_in_warning(self):
        instance = fake_engine([])
        instance._translator.translate_batch.side_effect = RuntimeError("SENSITIVE_SOURCE")
        result = instance.translate("SENSITIVE_SOURCE")
        self.assertNotIn("SENSITIVE_SOURCE", json.dumps(result))
        self.assertEqual(result["status"], "needs_review")


@unittest.skipUnless(engine.availability()["available"], "Optional offline translation model is not installed")
class InstalledTranslationTests(unittest.TestCase):
    def test_real_model_works_with_network_connections_forbidden(self):
        with patch("socket.socket.connect", side_effect=AssertionError("No network")), patch("socket.create_connection", side_effect=AssertionError("No network")):
            translator = engine.Engine()
            result = translator.translate("La pompe ne doit pas démarrer.")
            self.assertEqual(result["text"], "The pump must not start.")
            result = translator.translate("La pompe ne démarre plus.")
            self.assertEqual(result["status"], "translated")
            self.assertRegex(result["text"], r"no longer|not|doesn't")
            result = translator.translate("Pump P101 en marche; arrêter P101 si la pression dépasse 150 kPa.")
            self.assertEqual(result["status"], "translated")
            self.assertIn("stop P101", result["text"])
            self.assertIn("150 kPa", result["text"])
            result = translator.translate("La pression doit rester inférieure à 2,5 bar.")
            self.assertEqual(result["status"], "needs_review")
            self.assertEqual(result["text"], "")


if __name__ == "__main__":
    unittest.main()
