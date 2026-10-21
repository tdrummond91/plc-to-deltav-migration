"""Private, repeatable English translations of immutable source wording.

This sidecar is a derived cache, not the project database or a reviewed decision.
Each database operation owns its connection; the model worker never shares the
workspace's SQLite connection. No networking or subprocesses run in this module.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
import hashlib
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any

from .local_translation_engine import DEFAULT_MODEL_DIR


CACHE_RULES_VERSION = "source-wording-v1"
WORKER_BATCH_TEXTS = 16
_REVIEW_WARNING = "Check the English wording against the original before using it."
_FAILED_WARNING = "This text could not be translated locally. The original is unchanged."
_UNAVAILABLE = "Local English translation is not ready. Install the local French-to-English model first."


def _availability(model_dir: Path) -> dict[str, Any]:
    # Installing or importing the editor must not require the optional model.
    from .local_translation_engine import availability
    return availability(model_dir)


def _engine(model_dir: Path) -> Any:
    from .local_translation_engine import Engine
    return Engine(model_dir)


class TranslationService:
    """Cache exact text and translate a deduplicated snapshot in one worker.

    ``start`` is idempotent for an active job and for already cached text. Failed
    text is cached too, so opening a pane cannot repeatedly retry a bad input;
    ``retry=True`` explicitly retries failures. A subsequent import can call
    ``start`` again after the active batch finishes. Reading mode is independent
    of preparing translations; changing to originals never cancels preparation.
    """

    def __init__(
        self,
        cache_path: Path,
        model_dir: Path | None = None,
        *,
        engine_factory: Callable[[Path], Any] = _engine,
        availability_provider: Callable[[Path], dict[str, Any]] = _availability,
    ) -> None:
        self.cache_path = Path(cache_path)
        self.model_dir = Path(model_dir) if model_dir is not None else DEFAULT_MODEL_DIR
        self._engine_factory = engine_factory
        self._availability_provider = availability_provider
        self._lock = threading.RLock()
        self._database_lock = threading.RLock()
        self._cancel = threading.Event()
        self._worker: threading.Thread | None = None
        self._closed = False
        self._started_at: float | None = None
        self._processing_seconds = 0.0
        self._progress: dict[str, Any] = {
            "state": "idle", "total": 0, "completed": 0, "cached": 0,
            "needs_review": 0, "failed": 0,
            "elapsed_seconds": 0.0, "remaining_seconds": None,
        }
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS translation_settings (
                    name TEXT PRIMARY KEY, value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS english_translations (
                    model_id TEXT NOT NULL,
                    rules_version TEXT NOT NULL,
                    source_hash TEXT NOT NULL,
                    source_text TEXT NOT NULL,
                    english_text TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('translated', 'needs_review')),
                    failed INTEGER NOT NULL CHECK(failed IN (0, 1)),
                    PRIMARY KEY(model_id, rules_version, source_hash, source_text)
                );
            """)
        self._enabled = self._setting("enabled") == "1"
        mode = self._setting("presentation_mode")
        self._mode = mode if mode in {"original", "english", "both"} else ("both" if self._enabled else "original")
        try:
            self._generation = max(0, int(self._setting("write_generation") or "0"))
        except ValueError:
            self._generation = 0

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.cache_path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _setting(self, name: str) -> str | None:
        with self._database_lock, self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM translation_settings WHERE name = ?", (name,),
            ).fetchone()
        return row[0] if row is not None else None

    def _set_setting(self, name: str, value: str) -> None:
        with self._database_lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO translation_settings(name, value) VALUES (?, ?) "
                "ON CONFLICT(name) DO UPDATE SET value=excluded.value", (name, value),
            )

    def _model(self) -> dict[str, Any]:
        try:
            value = self._availability_provider(self.model_dir)
            model_id = value.get("model_id")
            if not isinstance(model_id, str) or not model_id:
                raise ValueError("Missing model identity")
            return {
                "available": value.get("available") is True,
                "model_id": model_id,
                "message": value.get("message") if isinstance(value.get("message"), str) else _UNAVAILABLE,
            }
        except Exception:
            # Do not include exception text: a library may quote its input.
            return {"available": False, "model_id": "", "message": _UNAVAILABLE}

    def status(self) -> dict[str, Any]:
        model = self._model()
        with self._lock:
            result = {
                **model, **self._progress, "enabled": self._enabled,
                "presentation_mode": self._mode, "write_generation": self._generation,
                "cache_signature": [model["model_id"], CACHE_RULES_VERSION, self._generation],
            }
            if self._started_at is not None and self._progress["state"] == "running":
                result["elapsed_seconds"] = round(time.monotonic() - self._started_at, 3)
        return result

    def set_mode(self, mode: str) -> None:
        """Persist reading presentation independently of background preparation."""
        if not isinstance(mode, str) or mode not in {"original", "english", "both"}:
            raise ValueError("Translation mode must be original, english, or both")
        with self._lock:
            if not self._closed:
                self._set_setting("presentation_mode", mode)
                self._mode = mode

    def set_enabled(self, enabled: bool) -> None:
        if not isinstance(enabled, bool):
            raise TypeError("Translation preference must be true or false")
        with self._lock:
            if self._closed:
                return
            self._set_setting("enabled", "1" if enabled else "0")
            self._enabled = enabled
            self.set_mode("both" if enabled else "original")
            if not enabled:
                self._cancel.set()

    @staticmethod
    def _key(text: str, model_id: str) -> tuple[str, str, str, str]:
        return model_id, CACHE_RULES_VERSION, hashlib.sha256(text.encode("utf-8")).hexdigest(), text

    def _lookup(self, text: str, model_id: str) -> dict[str, Any] | None:
        if not model_id:
            return None
        with self._database_lock, self._connect() as connection:
            row = connection.execute(
                "SELECT english_text, status, failed FROM english_translations "
                "WHERE model_id=? AND rules_version=? AND source_hash=? AND source_text=?",
                self._key(text, model_id),
            ).fetchone()
        return self._entry(row, model_id)

    @staticmethod
    def _entry(row: sqlite3.Row | None, model_id: str) -> dict[str, Any] | None:
        if row is None:
            return None
        failed = bool(row["failed"])
        result = {
            "text": row["english_text"], "status": row["status"], "failed": failed,
            "model_id": model_id, "cached": True,
        }
        if row["status"] == "needs_review":
            result["warning"] = _FAILED_WARNING if failed else _REVIEW_WARNING
        return result

    def _cached_many(self, texts: tuple[str, ...], model_id: str) -> dict[str, dict[str, Any]]:
        if not texts or not model_id:
            return {}
        entries = {}
        # Thousands of comments and tag descriptions are common. Reuse one
        # connection for this initial scan instead of reopening SQLite per text.
        with self._database_lock, self._connect() as connection:
            for text in texts:
                row = connection.execute(
                    "SELECT english_text, status, failed FROM english_translations "
                    "WHERE model_id=? AND rules_version=? AND source_hash=? AND source_text=?",
                    self._key(text, model_id),
                ).fetchone()
                entry = self._entry(row, model_id)
                if entry is not None:
                    entries[text] = entry
        return entries

    def lookup(self, text: str) -> dict[str, Any] | None:
        if not isinstance(text, str) or not text.strip():
            return None
        return self._lookup(text, self._model()["model_id"])

    def lookup_many(self, texts: Iterable[str]) -> dict[str, dict[str, Any]]:
        """Read exact-wording matches using one short-lived cache connection."""
        unique = tuple(dict.fromkeys(text for text in texts if isinstance(text, str) and text.strip()))
        return self._cached_many(unique, self._model()["model_id"])

    def _save(self, source: str, model_id: str, result: dict[str, Any]) -> None:
        self._save_many([(source, result)], model_id)

    def _save_many(self, results: list[tuple[str, dict[str, Any]]], model_id: str) -> None:
        with self._database_lock, self._connect() as connection:
            connection.executemany(
                "INSERT INTO english_translations "
                "(model_id, rules_version, source_hash, source_text, english_text, status, failed) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(model_id, rules_version, source_hash, source_text) DO UPDATE SET "
                "english_text=excluded.english_text, status=excluded.status, failed=excluded.failed",
                [(*self._key(source, model_id), result["text"], result["status"], int(result["failed"]))
                 for source, result in results],
            )
            connection.execute(
                "INSERT INTO translation_settings(name, value) VALUES ('write_generation', '1') "
                "ON CONFLICT(name) DO UPDATE SET value=CAST(CAST(value AS INTEGER) + 1 AS TEXT)",
            )
            generation = int(connection.execute(
                "SELECT value FROM translation_settings WHERE name='write_generation'",
            ).fetchone()[0])
        with self._lock:
            self._generation = generation

    def start(self, texts: Iterable[str], *, retry: bool = False) -> dict[str, Any]:
        with self._lock:
            if self._closed or self._progress["state"] == "running":
                return self.status()
            # Immutable, exact wording: no whitespace/language normalization that
            # could merge different source evidence or alter addresses.
            unique = tuple(dict.fromkeys(text for text in texts if isinstance(text, str) and text.strip()))
            model = self._model()
            pending: list[str] = []
            cached = needs_review = failed = 0
            entries = self._cached_many(unique, model["model_id"])
            for source in unique:
                entry = entries.get(source)
                if entry is None or (retry and entry["failed"]):
                    pending.append(source)
                else:
                    cached += 1
                    needs_review += entry["status"] == "needs_review"
                    failed += entry["failed"]
            self._progress = {
                "state": "complete" if not pending else "idle",
                "total": len(unique), "completed": cached, "cached": cached,
                "needs_review": needs_review, "failed": failed,
                "elapsed_seconds": 0.0, "remaining_seconds": None,
            }
            self._started_at = None
            self._processing_seconds = 0.0
            if not pending:
                return self.status()
            if not model["available"]:
                self._progress.update(state="error", message=model["message"])
                return self.status()
            self._cancel.clear()
            self._started_at = time.monotonic()
            self._progress["state"] = "running"
            self._worker = threading.Thread(
                target=self._translate_batch,
                args=(tuple(pending), model["model_id"]),
                name="local-source-translation", daemon=True,
            )
            self._worker.start()
            return self.status()

    def _translate_batch(self, pending: tuple[str, ...], model_id: str) -> None:
        try:
            engine = self._engine_factory(self.model_dir)
            if engine.identity() != model_id:
                raise ValueError("The model changed before this batch started")
        except Exception:
            self._fail("Local translation could not start. Check the installed model and try again.")
            return
        batch_method = getattr(engine, "translate_many", None)
        # Compatibility with injected/older single-text engines. The production
        # engine packs 16 comments and commits the completed chunk atomically.
        chunk_size = WORKER_BATCH_TEXTS if callable(batch_method) else 1
        for offset in range(0, len(pending), chunk_size):
            if self._cancel.is_set():
                break
            sources = pending[offset:offset + chunk_size]
            began = time.monotonic()
            try:
                outputs = batch_method(sources) if callable(batch_method) else [engine.translate(sources[0])]
                if not isinstance(outputs, list) or len(outputs) != len(sources):
                    raise ValueError("Invalid local translation batch")
            except Exception:
                outputs = [None] * len(sources)
            results = [(source, self._validated_output(output)) for source, output in zip(sources, outputs)]
            try:
                self._save_many(results, model_id)
            except Exception:
                self._fail("The local translation cache could not be saved. Check that the project folder is writable.")
                return
            with self._lock:
                self._processing_seconds += time.monotonic() - began
                self._progress["completed"] += len(results)
                self._progress["needs_review"] += sum(result["status"] == "needs_review" for _, result in results)
                self._progress["failed"] += sum(result["failed"] for _, result in results)
                processed = self._progress["completed"] - self._progress["cached"]
                remaining = self._progress["total"] - self._progress["completed"]
                self._progress["remaining_seconds"] = round(self._processing_seconds / processed * remaining, 3)
        with self._lock:
            self._progress["state"] = "cancelled" if self._cancel.is_set() else "complete"
            if self._started_at is not None:
                self._progress["elapsed_seconds"] = round(time.monotonic() - self._started_at, 3)
            if self._cancel.is_set():
                self._progress["remaining_seconds"] = None

    @staticmethod
    def _validated_output(output: Any) -> dict[str, Any]:
        if isinstance(output, dict):
            english, state = output.get("text"), output.get("status")
            if isinstance(english, str) and state in {"translated", "needs_review"}:
                failed = not bool(english.strip())
                return {"text": english, "status": "needs_review" if failed else state, "failed": failed}
        return {"text": "", "status": "needs_review", "failed": True}

    def _fail(self, message: str) -> None:
        with self._lock:
            self._progress.update(state="error", message=message, remaining_seconds=None)
            if self._started_at is not None:
                self._progress["elapsed_seconds"] = round(time.monotonic() - self._started_at, 3)

    def close(self) -> None:
        """Stop after the active model call; completed text remains reusable."""
        with self._lock:
            self._closed = True
            self._cancel.set()
            worker = self._worker
        # A long native model call cannot be interrupted safely. A daemon may
        # finish that chunk after close; it opens its own short-lived database
        # connection and never touches the workspace store or starts another chunk.
        if worker is not None and worker is not threading.current_thread():
            worker.join(timeout=2)
