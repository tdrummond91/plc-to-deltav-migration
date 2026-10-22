"""Optional, strictly offline French-to-English reading aid.

The public Argos/OPUS model is run directly through CTranslate2. No model hub,
package manager, sentence-segmentation downloader, or network client is imported
here. Installation is a separate, explicit command in ``setup_translation``.
Translations are derived reading aids, never source facts or review decisions.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import islice
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
MAX_BATCH_TEXTS = 32

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


def _unsafe(reason: str, original: str = "") -> dict:
    return {"text": original, "status": "needs_review", "warning": reason,
            "partial": False, "translated_segments": 0, "retained_segments": 1,
            "failed": True}


@dataclass
class _Prepared:
    original: str
    pieces: list[str]
    # Preserve formatting around each independently translated sentence/line.
    segments: list[tuple[int, str, str, str]]
    tokens: list[list[str]]
    total_segments: int


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
        return self.translate_many([text], protected_tokens=protected_tokens)[0]

    def translate_many(self, texts: Iterable[str], protected_tokens: Iterable[str] = ()) -> list[dict]:
        """Pack independent comments into bounded inference batches.

        Rejected or unattempted sentences stay exactly as captured, while safe
        sentences remain readable in English. No incomplete model output is used.
        """
        results: list[dict] = []
        sources = iter(texts)
        extra = tuple(protected_tokens)
        while group := tuple(islice(sources, MAX_BATCH_TEXTS)):
            prepared = [self._prepare(text) for text in group]
            tokenized = [tokens for item in prepared if isinstance(item, _Prepared) for tokens in item.tokens]
            if tokenized:
                try:
                    batches = self._translator.translate_batch(
                        tokenized, beam_size=4, length_penalty=0.2, replace_unknowns=True,
                        max_batch_size=512, batch_type="tokens", max_input_length=0,
                        max_decoding_length=256, return_end_token=True,
                    )
                    if len(batches) != len(tokenized):
                        raise ValueError("Incomplete local translation batch")
                except Exception:
                    batches = None
            else:
                batches = []
            offset = 0
            for item in prepared:
                if isinstance(item, dict):
                    results.append(item)
                    continue
                results.append(self._finish(item, None if batches is None else batches[offset:offset + len(item.tokens)], extra))
                offset += len(item.tokens)
        return results

    def _prepare(self, text: str) -> dict | _Prepared:
        if not isinstance(text, str) or len(text) > MAX_TEXT_CHARS:
            return _unsafe("This comment is too long for the local reading aid; review the original wording.", text if isinstance(text, str) else "")
        # Split only at paragraph and sentence boundaries. Never truncate or split
        # an overlong sentence into unrelated fragments to force it through. The
        # exact separator is retained, including CRLF and whitespace-only lines.
        pieces = re.split(r"(\r\n|\r|\n|(?<=[.!?;])[^\S\r\n]+(?=[A-ZÀ-ÖØ-Þ]))", text)
        segments, tokenized = [], []
        total = 0
        for index in range(0, len(pieces), 2):
            part = pieces[index]
            core = part.strip()
            # Decorative rules, list punctuation and numbers require no model.
            if not re.search(r"[^\W\d_]", core, re.UNICODE):
                continue
            total += 1
            if total > MAX_SEGMENTS:
                continue
            prefix = part[:len(part) - len(part.lstrip())]
            suffix = part[len(part.rstrip()):]
            try:
                tokens = self._tokenizer.encode(core, out_type=str)
                if not tokens or len(tokens) > MAX_SENTENCE_TOKENS:
                    continue
            except Exception:
                continue
            segments.append((index, prefix, core, suffix))
            tokenized.append(tokens)
        return _Prepared(text, pieces, segments, tokenized, total)

    def _finish(self, prepared: _Prepared, batches: list | None, extra: tuple[str, ...]) -> dict:
        pieces = prepared.pieces.copy()
        accepted = 0
        size = len(prepared.original)
        # A malformed batch cannot safely be aligned to its source segments.
        aligned = batches is not None and len(batches) == len(prepared.segments)
        for (index, prefix, original, suffix), batch in zip(prepared.segments, batches if aligned else []):
            try:
                hypothesis = batch.hypotheses[0]
                if not hypothesis or hypothesis[-1] != "</s>":
                    continue
                # Normalize SentencePiece spaces without touching real tag underscores.
                candidate = self._tokenizer.decode(hypothesis[:-1]).replace("▁", " ").strip()
                if not candidate or any(character in candidate for character in "\r\n"):
                    continue
                if token_fingerprint(original, extra) != token_fingerprint(candidate, extra):
                    continue
                original_negative = bool(_FRENCH_NEGATION.search(original) or _ENGLISH_NEGATION.search(original))
                candidate_negative = bool(_ENGLISH_NEGATION.search(candidate))
                if original_negative != candidate_negative:
                    continue
                replacement = prefix + candidate + suffix
                next_size = size - len(pieces[index]) + len(replacement)
                if next_size > MAX_TEXT_CHARS * 2:
                    continue
                pieces[index] = replacement
                size = next_size
                accepted += 1
            except Exception:
                # Library failures never replace source text or expose raw exceptions.
                continue
        retained = prepared.total_segments - accepted
        return {"text": "".join(pieces), "status": "needs_review" if retained else "translated",
                "partial": bool(accepted and retained), "translated_segments": accepted,
                "retained_segments": retained, "failed": bool(retained and not accepted),
                "warning": "Some wording remains in its original language. Review it against the source." if retained
                else "Reading aid only. Confirm equipment terminology and control meaning against the original."}
