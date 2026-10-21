"""Optional, strictly offline French-to-English reading aid.

The public Argos/OPUS model is run directly through CTranslate2. No model hub,
package manager, sentence-segmentation downloader, or network client is imported
here. Installation is a separate, explicit command in ``setup_translation``.
Translations are derived reading aids, never source facts or review decisions.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re
from typing import Iterable

PACKAGE_URL = "https://argos-net.com/v1/translate-fr_en-1_9.argosmodel"
PACKAGE_SHA256 = "3b3052fee6bb1e8e8e632a26a723eb2a2c7710dfe73ba61ffd9b83e85d4f14c1"
RULE_VERSION = "reading-aid-v2"
MODEL_ID = f"argos-fr-en-1.9:{PACKAGE_SHA256}:ct2-4.8.3:spm-0.2.2:{RULE_VERSION}"
DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[3] / "confidential" / "translation" / "fr-en"
REQUIRED_FILES = (
    "metadata.json", "README.md", "sentencepiece.model", "model/config.json",
    "model/model.bin", "model/shared_vocabulary.json",
)
MAX_TEXT_CHARS = 16_000
MAX_SENTENCE_TOKENS = 140
MAX_SEGMENTS = 128

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:(?:[.:][A-Za-z0-9_]+)|(?:\[[0-9]+\]))*")
_NUMBER = re.compile(r"(?<![\w])[-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?(?![\w])")
_UNIT = re.compile(r"(?<![\w])(?:°[CF]|kPa|MPa|psi|bar|mA|mV|Hz|rpm|kg|mm|cm|m³|m3|L/min|l/min|m/s|ms|min|sec|s|h|V|A)(?![\w])|%")
_COMPARATOR = re.compile(r"<=|>=|!=|==|[<>≤≥=]")
_ACRONYMS = frozenset({"PID", "PV", "SP", "CV", "AI", "AO", "DI", "DO", "DC", "TON", "TOF", "RTO", "PLC", "HMI", "VFD"})
_FRENCH_NEGATION = re.compile(
    r"\b(?:pas|jamais|aucun(?:e)?|sans|rien|non)\b"
    r"|(?:\bne\b|\bn['’])[^.!?;\n]*?\bplus\b",
    re.IGNORECASE,
)
_ENGLISH_NEGATION = re.compile(r"\b(?:not|no|never|without|neither|nor|unable|cannot)\b|n['’]t\b|\bnon[-\s]", re.IGNORECASE)


def _manifest(model_dir: Path) -> dict:
    path = model_dir / "installation.json"
    if model_dir.is_symlink() or (model_dir / "model").is_symlink() or path.is_symlink() or path.stat().st_size > 32_768:
        raise ValueError("Invalid model installation metadata")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(manifest, dict) or not isinstance(manifest.get("files"), dict)
            or manifest.get("package_sha256") != PACKAGE_SHA256
            or set(manifest.get("files", {})) != set(REQUIRED_FILES)):
        raise ValueError("Unexpected model installation")
    for name in REQUIRED_FILES:
        entry = manifest["files"][name]
        file = model_dir / name
        if (not isinstance(entry, dict) or file.is_symlink() or not file.is_file() or file.stat().st_size != entry.get("size")
                or not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("sha256", "")))):
            raise ValueError("Incomplete model installation")
    return manifest


def availability(model_dir: Path = DEFAULT_MODEL_DIR) -> dict:
    """Cheap readiness check; the stable identity also makes old caches readable."""
    result = {"available": False, "model_id": MODEL_ID, "message": "Run bash ./setup-translation.sh once, then reopen the workbench."}
    try:
        _manifest(Path(model_dir))
    except (OSError, ValueError, TypeError, KeyError):
        return result
    try:
        if any(importlib.util.find_spec(name) is None for name in ("ctranslate2", "sentencepiece")):
            result["message"] = "The model is installed. Run bash ./setup-translation.sh to install the optional local translation packages."
            return result
    except (ImportError, ValueError):
        return result
    result.update(available=True, message="French-to-English translation is available entirely on this computer.")
    return result


def token_fingerprint(text: str, extra: Iterable[str] = ()) -> Counter[str]:
    """Literal checks catch changed identifiers/values; they cannot prove meaning."""
    values = [m.group(0) for m in _WORD.finditer(text)
              if any(c.isdigit() or c in "_:.[" for c in m.group(0)) or m.group(0) in _ACRONYMS]
    values.extend(m.group(0) for pattern in (_NUMBER, _UNIT, _COMPARATOR) for m in pattern.finditer(text))
    for token in extra:
        if isinstance(token, str) and token and token in text:
            values.extend([token] * text.count(token))
    return Counter(values)


def _unsafe(reason: str) -> dict:
    return {"text": "", "status": "needs_review", "warning": reason}


class Engine:
    """One CPU model instance; construct inside the translation worker thread."""

    def __init__(self, model_dir: Path = DEFAULT_MODEL_DIR):
        model_dir = Path(model_dir)
        try:
            manifest = _manifest(model_dir)
            for name, entry in manifest["files"].items():
                with (model_dir / name).open("rb") as source:
                    if hashlib.file_digest(source, "sha256").hexdigest() != entry["sha256"]:
                        raise ValueError("Model content changed")
            import ctranslate2
            import sentencepiece
            self._tokenizer = sentencepiece.SentencePieceProcessor(model_file=str(model_dir / "sentencepiece.model"))
            self._translator = ctranslate2.Translator(
                str(model_dir / "model"), device="cpu", compute_type="int8",
                inter_threads=1, intra_threads=2,
            )
        except Exception:
            # Underlying exceptions can expose paths; source text is never logged.
            raise RuntimeError("The local translation model could not be opened. Run bash ./setup-translation.sh and reopen the workbench.") from None

    def identity(self) -> str:
        return MODEL_ID

    def translate(self, text: str, protected_tokens: Iterable[str] = ()) -> dict:
        if not isinstance(text, str) or len(text) > MAX_TEXT_CHARS:
            return _unsafe("This comment is too long for the local reading aid; review the original wording.")
        if not text.strip():
            return {"text": text, "status": "translated"}
        # Split only at paragraph and sentence boundaries. Never truncate or split
        # an overlong sentence into unrelated fragments to force it through.
        pieces = re.split(r"(\n+|(?<=[.!?;])\s+(?=[A-ZÀ-ÖØ-Þ]))", text)
        segments = [part for index, part in enumerate(pieces) if index % 2 == 0 and part.strip()]
        if len(segments) > MAX_SEGMENTS:
            return _unsafe("This comment contains too many sections for the local reading aid.")
        try:
            tokenized = [self._tokenizer.encode(part, out_type=str) for part in segments]
            if any(len(tokens) > MAX_SENTENCE_TOKENS for tokens in tokenized):
                return _unsafe("A sentence exceeds the local model's reading limit. Review the original; nothing was truncated.")
            batches = self._translator.translate_batch(
                tokenized, beam_size=4, length_penalty=0.2, replace_unknowns=True,
                max_batch_size=512, batch_type="tokens", max_input_length=0,
                max_decoding_length=256, return_end_token=True,
            )
            if len(batches) != len(segments) or any(not batch.hypotheses[0] or batch.hypotheses[0][-1] != "</s>" for batch in batches):
                return _unsafe("The local model did not finish this comment. Review the original; partial wording was withheld.")
            # The source tokenizer does not know every target-language piece.
            # Argos also normalizes residual SentencePiece space markers. Keep
            # real underscores intact because they can be part of PLC names.
            translated_segments = [self._tokenizer.decode(batch.hypotheses[0][:-1]).replace("▁", " ").strip() for batch in batches]
            extra = tuple(protected_tokens)
            for original, candidate in zip(segments, translated_segments):
                if token_fingerprint(original, extra) != token_fingerprint(candidate, extra):
                    return _unsafe("The translation changed a value, unit, address, or identifier, so it was withheld. Review the original wording.")
                original_negative = bool(_FRENCH_NEGATION.search(original) or _ENGLISH_NEGATION.search(original))
                candidate_negative = bool(_ENGLISH_NEGATION.search(candidate))
                if original_negative != candidate_negative:
                    return _unsafe("The translation may have added or removed a negative condition, so it was withheld. Review the original wording.")
            translated = iter(translated_segments)
            english = "".join(next(translated) if i % 2 == 0 and part.strip() else part for i, part in enumerate(pieces))
            if not english.strip() or len(english) > MAX_TEXT_CHARS * 2:
                return _unsafe("The local model did not return usable wording. Review the original.")
            return {"text": english, "status": "translated", "warning": "Reading aid only. Confirm equipment terminology and control meaning against the original."}
        except Exception:
            return _unsafe("The local model could not translate this comment. Review the original wording.")
