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
            self.assertEqual(result["text"], "Arrêter P101 à 150 kPa.")
            self.assertTrue(result["failed"])

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
        self.assertEqual(result["text"], "La pompe doit démarrer.")

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
        self.assertEqual(result["text"], "La pompe doit démarrer.")

    def test_runtime_error_does_not_leak_input_in_warning(self):
        instance = fake_engine([])
        instance._translator.translate_batch.side_effect = RuntimeError("SENSITIVE_SOURCE")
        result = instance.translate("SENSITIVE_SOURCE")
        self.assertNotIn("SENSITIVE_SOURCE", result["warning"])
        self.assertEqual(result["text"], "SENSITIVE_SOURCE")
        self.assertEqual(result["status"], "needs_review")

    def test_many_packs_comments_and_preserves_each_paragraph(self):
        instance = fake_engine(["Pump running.", "Valve open.", "High pressure."])
        results = instance.translate_many(["Pompe en marche.\n\nVanne ouverte.", "Pression haute."])
        self.assertEqual([result["text"] for result in results], ["Pump running.\n\nValve open.", "High pressure."])
        self.assertEqual(instance._translator.translate_batch.call_count, 1)
        self.assertEqual(len(instance._translator.translate_batch.call_args.args[0]), 3)
        self.assertEqual(instance._translator.translate_batch.call_args.kwargs["max_batch_size"], 512)

    def test_many_bounded_to_32_comments_and_keeps_input_order(self):
        instance = fake_engine([])
        instance._translator.translate_batch.side_effect = lambda inputs, **_: [
            SimpleNamespace(hypotheses=[tokens + ["</s>"]]) for tokens in inputs
        ]
        sources = [f"P{index} running." for index in range(67)]
        results = instance.translate_many(iter(sources))
        self.assertEqual([result["text"] for result in results], sources)
        self.assertEqual([len(call.args[0]) for call in instance._translator.translate_batch.call_args_list], [32, 32, 3])

    def test_many_withholds_only_failed_comment_and_preserves_blank_input(self):
        instance = fake_engine(["Start P102.", "High pressure."])
        results = instance.translate_many(["Start P101.", "mot " * 141, "Pression haute.", " \n "])
        self.assertEqual([result["status"] for result in results], ["needs_review", "needs_review", "translated", "translated"])
        self.assertEqual(results[2]["text"], "High pressure.")
        self.assertEqual(results[3]["text"], " \n ")
        self.assertEqual(len(instance._translator.translate_batch.call_args.args[0]), 2)

    def test_many_incomplete_decode_does_not_hide_other_comments(self):
        instance = fake_engine([])
        instance._translator.translate_batch.return_value = [
            SimpleNamespace(hypotheses=[["Pump"]]),
            SimpleNamespace(hypotheses=[["Valve", "open.", "</s>"]]),
        ]
        results = instance.translate_many(["Pompe en marche.", "Vanne ouverte."])
        self.assertEqual(results[0]["status"], "needs_review")
        self.assertEqual(results[1]["text"], "Valve open.")

    def test_many_bad_batch_length_withholds_without_misaligned_wording(self):
        results = fake_engine(["Pump running."]).translate_many(["Pompe en marche.", "Vanne ouverte."])
        self.assertEqual([result["text"] for result in results], ["Pompe en marche.", "Vanne ouverte."])
        self.assertTrue(all(result["failed"] for result in results))

    def test_many_preserves_single_comment_guards(self):
        sources = ["The pump must not start.", "Start P101 at 150 kPa."]
        outputs = ["The pump must start.", "Start P101 at 15 kPa."]
        self.assertEqual(fake_engine(outputs).translate_many(sources), [fake_engine([output]).translate(source) for source, output in zip(sources, outputs)])

    def test_one_rejected_line_keeps_other_translated_lines_and_original_values(self):
        text = "Pompe en marche.\nPression maximale 2,5 bar.\nVanne ouverte."
        result = fake_engine(["Pump running.", "Maximum pressure 2.5 bar.", "Valve open."]).translate(text)
        self.assertEqual(result["text"], "Pump running.\nPression maximale 2,5 bar.\nValve open.")
        self.assertEqual(result["status"], "needs_review")
        self.assertTrue(result["partial"])
        self.assertFalse(result["failed"])
        self.assertEqual((result["translated_segments"], result["retained_segments"]), (2, 1))

    def test_partial_negation_and_explicit_identifier_guards_apply_per_segment(self):
        text = "Pompe en marche. Vanne ne doit pas ouvrir. Démarrer Principal."
        result = fake_engine(["Pump running.", "Valve must open.", "Start Main."]).translate(text, protected_tokens=["Principal"])
        self.assertEqual(result["text"], "Pump running. Vanne ne doit pas ouvrir. Démarrer Principal.")
        self.assertEqual((result["translated_segments"], result["retained_segments"]), (1, 2))

    def test_incomplete_decode_retains_only_its_original_line(self):
        instance = fake_engine([])
        instance._translator.translate_batch.return_value = [
            SimpleNamespace(hypotheses=[["Pump", "running.", "</s>"]]),
            SimpleNamespace(hypotheses=[["Valve", "must"]]),
        ]
        result = instance.translate("Pompe en marche.\nLa vanne doit ouvrir.")
        self.assertEqual(result["text"], "Pump running.\nLa vanne doit ouvrir.")
        self.assertTrue(result["partial"])

    def test_long_line_is_retained_without_preventing_other_lines(self):
        long_line = "mot " * (engine.MAX_SENTENCE_TOKENS + 1)
        instance = fake_engine(["Pump running.", "Valve open."])
        result = instance.translate("Pompe en marche.\n" + long_line + "\nVanne ouverte.")
        self.assertEqual(result["text"], "Pump running.\n" + long_line + "\nValve open.")
        self.assertEqual((result["translated_segments"], result["retained_segments"]), (2, 1))
        self.assertEqual(len(instance._translator.translate_batch.call_args.args[0]), 2)

    def test_whitespace_and_decorative_lines_survive_without_model_calls(self):
        text = "  Pompe en marche.  \r\n\t----------\r\tVanne ouverte.\t\n\n  123 >= 20  \n"
        instance = fake_engine(["Pump running.", "Valve open."])
        result = instance.translate(text)
        self.assertEqual(result["text"], "  Pump running.  \r\n\t----------\r\tValve open.\t\n\n  123 >= 20  \n")
        self.assertEqual((result["translated_segments"], result["retained_segments"]), (2, 0))
        self.assertEqual(len(instance._translator.translate_batch.call_args.args[0]), 2)
        decorative = fake_engine([])
        result = decorative.translate("\t----------------\r\n\r\n  1) 2)  ")
        self.assertEqual(result["text"], "\t----------------\r\n\r\n  1) 2)  ")
        self.assertEqual(result["status"], "translated")
        self.assertFalse(result["failed"])
        decorative._translator.translate_batch.assert_not_called()

    def test_segment_limit_retains_unattempted_tail_and_bounds_tokenization(self):
        instance = fake_engine(["Pump running."] * engine.MAX_SEGMENTS)
        source = "\n".join(["Pompe en marche."] * (engine.MAX_SEGMENTS + 2))
        result = instance.translate(source)
        self.assertEqual(result["text"], "\n".join(["Pump running."] * engine.MAX_SEGMENTS + ["Pompe en marche."] * 2))
        self.assertEqual(instance._tokenizer.encode.call_count, engine.MAX_SEGMENTS)
        self.assertEqual((result["translated_segments"], result["retained_segments"]), (engine.MAX_SEGMENTS, 2))

    def test_tokenizer_failure_retains_its_segment_and_keeps_later_alignment(self):
        instance = fake_engine(["Pump running.", "Valve open."])
        def encode(text, out_type):
            if text == "Autre note.":
                raise RuntimeError("private runtime details")
            return text.split()
        instance._tokenizer.encode.side_effect = encode
        result = instance.translate("Pompe en marche.\nAutre note.\nVanne ouverte.")
        self.assertEqual(result["text"], "Pump running.\nAutre note.\nValve open.")
        self.assertTrue(result["partial"])
        self.assertNotIn("private", result["warning"])

    def test_expanded_output_retains_one_original_instead_of_hiding_all_text(self):
        instance = fake_engine(["x" * (engine.MAX_TEXT_CHARS * 2 + 1), "Valve open."])
        result = instance.translate("Pompe en marche.\nVanne ouverte.")
        self.assertEqual(result["text"], "Pompe en marche.\nValve open.")
        self.assertTrue(result["partial"])


@unittest.skipUnless(engine.availability()["available"], "Optional offline translation model is not installed")
class InstalledTranslationTests(unittest.TestCase):
    def test_real_packed_outputs_match_serial_with_network_forbidden(self):
        samples = [
            "La pompe ne doit pas démarrer.",
            "La pression est trop élevée. Vérifier le capteur.",
            "Pump P101 en marche; arrêter P101 si la pression dépasse 150 kPa.",
            "La vanne est ouverte.\n\nLa pompe est disponible.",
        ]
        with patch("socket.socket.connect", side_effect=AssertionError("No network")), patch("socket.create_connection", side_effect=AssertionError("No network")):
            translator = engine.Engine()
            self.assertEqual(translator.translate_many(samples), [translator.translate(text) for text in samples])

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
            self.assertEqual(result["text"], "La pression doit rester inférieure à 2,5 bar.")

    def test_real_multiline_partial_keeps_safe_english_and_exact_original_formatting(self):
        with patch("socket.socket.connect", side_effect=AssertionError("No network")), patch("socket.create_connection", side_effect=AssertionError("No network")):
            result = engine.Engine().translate("  La pompe ne doit pas démarrer.\r\n-----\r\nLa pression doit rester inférieure à 2,5 bar.  ")
        self.assertEqual(result["text"], "  The pump must not start.\r\n-----\r\nLa pression doit rester inférieure à 2,5 bar.  ")
        self.assertTrue(result["partial"])
        self.assertEqual((result["translated_segments"], result["retained_segments"]), (1, 1))


if __name__ == "__main__":
    unittest.main()
