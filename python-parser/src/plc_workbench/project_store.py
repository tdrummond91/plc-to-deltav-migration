"""Private engineering projects with immutable evidence and revisioned decisions.

Source IDs belong to an export snapshot. Reviews and engineering groups are
stored separately from parser artifacts; importing an export never rewrites a
review onto a similarly named rung. Explicit correspondence is required.
"""

from __future__ import annotations

from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterator
from uuid import uuid4

from .storage import StorageError, _workspace_path


MAX_ARTIFACT_BYTES = 512 * 1024 * 1024
MAX_RUN_BYTES = 1024 * 1024 * 1024
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_ARTIFACTS = 256
MAX_MEMBERS = 100_000
MAX_SIGNALS = 100_000
MAX_SIGNAL_BINDINGS = 1_000
_SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_SCHEMA_VERSION = 2
_APPLICATION_ID = 0x504C4357  # ASCII PLCW; distinguishes this file from other SQLite applications.
_EDIT_TABLES = ("categories", "groups", "reviews", "rules", "signals")
MIGRATION_STATUSES = frozenset({'unreviewed', 'retain', 'replace', 'exclude', 'investigate'})
SIGNAL_FIELD_TYPES = frozenset({'di', 'do', 'ai', 'ao', 'unknown'})
MEMBER_ROLES = frozenset({'scaling', 'alarm', 'reference', 'logic'})
_SIGNAL_BINDING_KEYS = frozenset({'run_id', 'snapshot_id', 'root_id', 'suffix', 'address_id', 'evidence_signature'})
_TABLE_COLUMNS = {
    "project": {"singleton", "revision", "active_run"},
    "runs": {"id", "snapshot_id", "fingerprint", "proposal_digest", "manifest", "imported_utc"},
    "artifacts": {"run_id", "name", "data"},
    "history": {"revision", "operation", "author", "created_utc", "command",
                "before_patch", "after_patch", "undone_revision"},
    **{table: {"id", "record"} for table in _EDIT_TABLES},
}
_DEFAULT_CATEGORIES = (
    ("pid", "PID / control loop"), ("alarm", "Alarm / protective logic"),
    ("io", "I/O / signal handling"), ("calculation", "Calculation"),
    ("sequence", "Sequence / state logic"), ("timer", "Timer / counter"),
    ("equipment", "Equipment control"), ("communication", "Communication"),
    ("miscellaneous", "Miscellaneous logic"), ("unknown", "Needs identification"),
)


class ProjectError(ValueError):
    """Concise error suitable for the private workspace interface."""


class RevisionConflict(ProjectError):
    """The caller's revision no longer matches the project's saved head."""


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _decode(data: bytes | str) -> dict[str, Any]:
    def reject_constant(_: str) -> None:
        raise ValueError("Non-finite JSON number")

    try:
        value = json.loads(data, parse_constant=reject_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ProjectError("A saved artifact is not valid JSON.") from exc
    if not isinstance(value, dict):
        raise ProjectError("A saved artifact must contain a JSON object.")
    return value


def _text(value: Any, label: str, limit: int = 160, *, empty: bool = False) -> str:
    if (not isinstance(value, str) or len(value) > limit
            or (not empty and not value.strip()) or any(ord(c) < 32 and c not in "\n\t" for c in value)):
        raise ProjectError(f"{label} must be readable text of at most {limit} characters.")
    return value.strip()


def _ids(value: Any, label: str, *, allow_empty: bool = True) -> list[str]:
    if (not isinstance(value, list) or len(value) > MAX_MEMBERS
            or (not allow_empty and not value)):
        raise ProjectError(f"{label} must be a bounded list of identifiers.")
    result = [_text(item, label, 256) for item in value]
    if len(result) != len(set(result)):
        raise ProjectError(f"{label} contains duplicate identifiers.")
    return result


def _private_path(path: Path) -> Path:
    try:
        return _workspace_path(Path(path))
    except (StorageError, OSError, ValueError) as exc:
        raise ProjectError("Project files inside the checkout must stay beneath confidential/.") from exc


def _read_bounded(path: Path, limit: int) -> bytes:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
            raise ProjectError("A saved artifact is missing, linked, or exceeds its size limit.")
        with path.open("rb") as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ProjectError("A saved artifact exceeds its size limit.")
        return data
    except OSError as exc:
        raise ProjectError("Could not read the completed saved run.") from exc


def _source_ids(inventory: dict[str, Any]) -> set[str]:
    """Admit captured entities, rungs and instructions, never arbitrary IDs."""
    result: set[str] = set()
    for collection in ("entities", "rungs"):
        rows = inventory.get(collection)
        if not isinstance(rows, list):
            raise ProjectError("Inventory is missing its complete source records.")
        for row in rows:
            if not isinstance(row, dict):
                raise ProjectError("Inventory contains an invalid source record.")
            identifier = _text(row.get("id"), "Source identifier", 256)
            if identifier != row["id"] or any(character.isspace() for character in identifier):
                raise ProjectError("Inventory contains an invalid source identifier.")
            if identifier in result:
                raise ProjectError("Inventory contains duplicate source identifiers.")
            result.add(identifier)
            if collection == "rungs":
                instructions = row.get("instructions", [])
                if not isinstance(instructions, list):
                    raise ProjectError("Inventory contains invalid instruction records.")
                for instruction in instructions:
                    if not isinstance(instruction, dict):
                        raise ProjectError("Inventory contains invalid instruction records.")
                    identifier = _text(instruction.get("id"), "Instruction identifier", 256)
                    if identifier != instruction["id"] or any(character.isspace() for character in identifier):
                        raise ProjectError("Inventory contains an invalid instruction identifier.")
                    if identifier in result:
                        raise ProjectError("Inventory contains duplicate source identifiers.")
                    result.add(identifier)
    return result


def _invalid_records() -> None:
    raise ProjectError("Saved evidence has invalid records or source links; regenerate the run.")


def _rows(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    rows = payload.get(key)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        _invalid_records()
    return rows


def _string_fields(row: dict[str, Any], keys: tuple[str, ...], *, nullable: bool = False) -> None:
    for key in keys:
        value = row.get(key)
        if not isinstance(value, str) and not (nullable and value is None):
            _invalid_records()


def _link(value: Any, identifiers: set[str], *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if not isinstance(value, str) or value not in identifiers:
        _invalid_records()


def _validate_structure(rung: dict[str, Any]) -> None:
    instructions = rung["instructions"]
    expected = [instruction["id"] for instruction in instructions]
    structure = rung.get("structure")
    if rung["parse_status"] != "parsed":
        if structure is not None or instructions:
            _invalid_records()
        return
    if not isinstance(rung.get("text"), str):
        _invalid_records()
    visited: list[str] = []
    stack = [(structure, 0)]
    while stack:
        node, depth = stack.pop()
        if not isinstance(node, dict) or depth > 256:
            _invalid_records()
        kind = node.get("kind")
        if kind == "instruction":
            if set(node) != {"kind", "instruction_id"}:
                _invalid_records()
            visited.append(node["instruction_id"])
        elif kind in ("sequence", "branch"):
            key = "items" if kind == "sequence" else "legs"
            children = node.get(key)
            if set(node) != {"kind", key} or not isinstance(children, list):
                _invalid_records()
            if kind == "branch" and (len(children) < 2 or any(
                    not isinstance(child, dict) or child.get("kind") != "sequence" for child in children)):
                _invalid_records()
            stack.extend((child, depth + 1) for child in reversed(children))
        else:
            _invalid_records()
    if not isinstance(structure, dict) or structure.get("kind") != "sequence" or visited != expected:
        _invalid_records()


def _validate_inventory(inventory: dict[str, Any]) -> tuple[set[str], dict[str, str]]:
    """Validate shapes and joins used by the editor, without rerunning analysis.

    Matching digests establish artifact consistency, not independent verification
    that every saved interpretation is true of the original controller source.
    The original source and original JSON remain unmodified evidence.
    """
    _source_ids(inventory)
    entities = _rows(inventory, "entities")
    rungs = _rows(inventory, "rungs")
    entity_ids = {row["id"] for row in entities}
    rung_ids = {row["id"] for row in rungs}
    if (inventory.get("status") not in ("complete", "partial")
            or not isinstance(inventory.get("coverage"), dict)):
        _invalid_records()
    parents = {}
    for row in entities:
        _string_fields(row, ("kind", "locator"))
        _string_fields(row, ("name", "description"), nullable=True)
        attributes = row.get("attributes")
        if not isinstance(attributes, dict) or any(
                not isinstance(key, str) or not isinstance(value, str) for key, value in attributes.items()):
            _invalid_records()
        for key in ("parent_id", "scope_id"):
            _link(row.get(key), entity_ids, nullable=True)
        parents[row["id"]] = row.get("parent_id")
    # A malformed cycle would otherwise create misleading truncated source paths.
    completed: set[str] = set()
    for identifier in parents:
        chain: set[str] = set()
        current = identifier
        while current is not None and current not in completed:
            if current in chain:
                _invalid_records()
            chain.add(current)
            current = parents[current]
        completed.update(chain)
    instruction_rungs: dict[str, str] = {}
    for rung in rungs:
        _string_fields(rung, ("locator", "parse_status"))
        _string_fields(rung, ("text", "comment", "number", "type"), nullable=True)
        if (type(rung.get("ordinal")) is not int or rung["ordinal"] < 0
                or rung["parse_status"] not in ("parsed", "failed", "preserved_unsupported")):
            _invalid_records()
        for key in ("parent_id", "scope_id"):
            _link(rung.get(key), entity_ids, nullable=True)
        previous_end = 0
        for instruction in _rows(rung, "instructions"):
            _string_fields(instruction, ("opcode",))
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", instruction["opcode"]):
                _invalid_records()
            arguments = instruction.get("arguments")
            start, end = instruction.get("start"), instruction.get("end")
            if (not isinstance(arguments, list) or any(not isinstance(arg, str) for arg in arguments)
                    or type(start) is not int or type(end) is not int
                    or not isinstance(rung.get("text"), str)
                    or not previous_end <= start < end <= len(rung["text"])):
                _invalid_records()
            previous_end = end
            instruction_rungs[instruction["id"]] = rung["id"]
        _validate_structure(rung)
    return rung_ids, instruction_rungs


def _validate_analysis(analysis: dict[str, Any], inventory: dict[str, Any],
                       rung_ids: set[str], instruction_rungs: dict[str, str]) -> None:
    if analysis.get("snapshot") != inventory["snapshot"]:
        raise ProjectError("Rung analysis belongs to a different source snapshot.")
    rows = _rows(analysis, "rungs")
    if (len(rows) != len(rung_ids) or any(not isinstance(row.get("id"), str) for row in rows)
            or {row["id"] for row in rows} != rung_ids):
        _invalid_records()
    blocks = _rows(analysis, "blocks")
    if (len(blocks) != len(instruction_rungs)
            or any(not isinstance(row.get("id"), str) for row in blocks)
            or {row["id"] for row in blocks} != set(instruction_rungs)):
        _invalid_records()
    for block in blocks:
        if block.get("rung_id") != instruction_rungs[block["id"]]:
            _invalid_records()
    seen: set[str] = set()
    for candidate in _rows(analysis, "candidates"):
        _string_fields(candidate, ("id", "category", "basis", "rule_id", "reason"))
        _link(candidate.get("rung_id"), rung_ids)
        if (candidate["id"] in seen
                or not re.fullmatch(r"[a-z_]{1,100}", candidate["category"])):
            _invalid_records()
        seen.add(candidate["id"])
        for key in ("evidence_ids", "missing_evidence"):
            values = candidate.get(key)
            if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
                _invalid_records()


def _validate_references(references: dict[str, Any], inventory: dict[str, Any],
                         instruction_rungs: dict[str, str]) -> None:
    if references.get("snapshot") != inventory["snapshot"]:
        raise ProjectError("Reference evidence belongs to a different source snapshot.")
    entity_ids = {entity["id"] for entity in inventory["entities"]}
    instructions = {instruction["id"]: instruction for rung in inventory["rungs"]
                    for instruction in rung["instructions"]}
    instruction_ids = set(instructions)
    seen: set[str] = set()
    positions: set[tuple[str, int]] = set()
    for operand in _rows(references, "operands"):
        _string_fields(operand, ("id", "raw_text", "status"))
        instruction_id = operand.get("instruction_id")
        _link(instruction_id, instruction_ids)
        index = operand.get("argument_index")
        arguments = instructions[instruction_id]["arguments"]
        if (operand["id"] in seen or operand.get("rung_id") != instruction_rungs[instruction_id]
                or type(index) is not int or not 0 <= index < len(arguments)
                or operand["raw_text"] != arguments[index]
                or (instruction_id, index) in positions):
            _invalid_records()
        seen.add(operand["id"])
        positions.add((instruction_id, index))
        for key in ("target_id", "root_id", "resolved_id", "symbol_id", "scope_id"):
            _link(operand.get(key), entity_ids, nullable=True)
    expected = {(identifier, index) for identifier, instruction in instructions.items()
                for index in range(len(instruction["arguments"]))}
    if positions != expected:
        _invalid_records()


def rung_pattern(rung: dict[str, Any]) -> dict[str, Any] | None:
    """Structural rule signature: preserve branches/opcodes, exclude operands.

    This supports classification proposals, never behavioral equivalence. Two
    rungs with the same shape can still control entirely different equipment.
    """
    instructions = {item["id"]: item.get("opcode") for item in rung.get("instructions", [])}

    def visit(node: Any, depth: int = 0) -> dict[str, Any]:
        if not isinstance(node, dict) or depth > 256:
            raise ValueError
        kind = node.get("kind")
        if kind == "instruction":
            opcode = instructions.get(node.get("instruction_id"))
            if not isinstance(opcode, str) or not opcode:
                raise ValueError
            return {"kind": kind, "opcode": opcode}
        key = {"sequence": "items", "branch": "legs"}.get(kind)
        if key is None or not isinstance(node.get(key), list):
            raise ValueError
        return {"kind": kind, key: [visit(child, depth + 1) for child in node[key]]}

    try:
        return visit(rung.get("structure"))
    except (ValueError, KeyError, TypeError, RecursionError):
        return None


def _load_run(run_dir: Path) -> tuple[dict[str, Any], dict[str, bytes], str, str]:
    """Validate the publisher's final manifest and every declared artifact."""
    path = Path(run_dir).expanduser()
    if path.is_symlink():
        raise ProjectError("Select a completed run directory, not a symbolic link.")
    path = path.resolve()
    manifest_bytes = _read_bounded(path / "manifest.json", MAX_MANIFEST_BYTES)
    manifest = _decode(manifest_bytes)
    if (type(manifest.get("schema_version")) is not int
            or not 1 <= manifest["schema_version"] <= 38
            or manifest.get("status") not in ("complete", "partial")):
        raise ProjectError("The saved run manifest is incomplete or uses an unsupported schema.")
    _text(manifest.get("run_id"), "Run identifier", 256)
    records = manifest.get("artifacts")
    if (not isinstance(records, dict) or not 2 <= len(records) <= MAX_ARTIFACTS
            or not {"inventory.json", "snapshot.L5X"}.issubset(records)):
        raise ProjectError("The completed run must include inventory and captured source artifacts.")
    artifacts: dict[str, bytes] = {"manifest.json": manifest_bytes}
    total = len(manifest_bytes)
    for name, expected in records.items():
        if (not isinstance(name, str) or not _SAFE_NAME.fullmatch(name) or name == "manifest.json"
                or not isinstance(expected, dict) or type(expected.get("size_bytes")) is not int
                or not 0 <= expected["size_bytes"] <= MAX_ARTIFACT_BYTES
                or not isinstance(expected.get("sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", expected["sha256"])):
            raise ProjectError("A manifest artifact entry is invalid.")
        total += expected["size_bytes"]
        if total > MAX_RUN_BYTES:
            raise ProjectError("The saved run exceeds the project import size limit.")
        data = _read_bounded(path / name, expected["size_bytes"])
        if len(data) != expected["size_bytes"] or hashlib.sha256(data).hexdigest() != expected["sha256"]:
            raise ProjectError("A saved artifact does not match its manifest; regenerate the run.")
        artifacts[name] = data
    inventory = _decode(artifacts["inventory.json"])
    source = artifacts["snapshot.L5X"]
    digest = hashlib.sha256(source).hexdigest()
    snapshot = {"id": f"sha256:{digest}", "sha256": digest, "size_bytes": len(source)}
    if manifest.get("snapshot") != snapshot or inventory.get("snapshot") != snapshot:
        raise ProjectError("Source bytes and inventory do not match the saved snapshot.")
    rung_ids, instruction_rungs = _validate_inventory(inventory)
    if "rung-analysis.json" in artifacts:
        _validate_analysis(_decode(artifacts["rung-analysis.json"]), inventory, rung_ids, instruction_rungs)
    if "references.json" in artifacts:
        _validate_references(_decode(artifacts["references.json"]), inventory, instruction_rungs)
    # Report HTML contains rendering choices; JSON artifacts contain evidence.
    # Conservatively invalidate approvals if any captured analysis dependency
    # changes. This intentionally favors review over silently trusting old facts.
    evidence = {name: details["sha256"] for name, details in records.items() if name.endswith(".json")}
    proposal_digest = hashlib.sha256(_json(evidence).encode()).hexdigest()
    fingerprint = hashlib.sha256(manifest_bytes).hexdigest()
    return manifest, artifacts, fingerprint, proposal_digest


class ProjectStore:
    """One portable SQLite file; original saved-run directories remain untouched."""

    def __init__(self, path: Path) -> None:
        self.path = _private_path(path)
        self._cache: dict[tuple[str, str], dict[str, Any]] = {}
        self._source_id_cache: dict[str, set[str]] = {}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA foreign_keys=ON")
            self._initialize()
        except (OSError, sqlite3.Error, ProjectError) as exc:
            if hasattr(self, "connection"):
                self.connection.close()
            if isinstance(exc, ProjectError):
                raise
            raise ProjectError("Could not open the private project database.") from exc

    def _initialize(self) -> None:
        version = self.connection.execute("PRAGMA user_version").fetchone()[0]
        application = self.connection.execute("PRAGMA application_id").fetchone()[0]
        if version not in (0, 1, _SCHEMA_VERSION):
            raise ProjectError("This project uses an unsupported database schema.")
        existing = self.connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        if version == 0 and (existing or application not in (0, _APPLICATION_ID)):
            raise ProjectError("The selected file is not an engineering project database.")
        if version:
            expected_tables = {table: columns for table, columns in _TABLE_COLUMNS.items()
                               if version != 1 or table != 'signals'}
            if application != _APPLICATION_ID or {row[0] for row in existing} != set(expected_tables):
                raise ProjectError("The selected file is not a recognized engineering project database.")
            for table, columns in expected_tables.items():
                actual = self.connection.execute(f"PRAGMA table_info({table})").fetchall()
                if {row[1] for row in actual} != columns:
                    raise ProjectError("The project database schema is incomplete or unsupported.")
            head = self.connection.execute("SELECT singleton,revision,active_run FROM project").fetchall()
            if (len(head) != 1 or head[0][0] != 1 or type(head[0][1]) is not int
                    or head[0][1] < 0):
                raise ProjectError("The project database has an invalid revision record.")
            if version == 1:
                # Add engineering records without rewriting evidence, decisions,
                # revision numbers or old history patches. Restore migrates a
                # working copy, never the original backup.
                with self._transaction():
                    self.connection.execute('CREATE TABLE signals (id TEXT PRIMARY KEY, record TEXT NOT NULL)')
                    self.connection.execute(f'PRAGMA user_version={_SCHEMA_VERSION}')
            return
        with self._transaction():
            self.connection.execute(
                "CREATE TABLE project (singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
                "revision INTEGER NOT NULL, active_run TEXT)"
            )
            self.connection.execute("INSERT OR IGNORE INTO project VALUES (1,0,NULL)")
            self.connection.execute(
                "CREATE TABLE runs (id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL, "
                "fingerprint TEXT NOT NULL UNIQUE, proposal_digest TEXT NOT NULL, "
                "manifest TEXT NOT NULL, imported_utc TEXT NOT NULL)"
            )
            self.connection.execute(
                "CREATE TABLE artifacts (run_id TEXT NOT NULL REFERENCES runs(id), "
                "name TEXT NOT NULL, data BLOB NOT NULL, PRIMARY KEY(run_id,name))"
            )
            for table in _EDIT_TABLES:
                self.connection.execute(f"CREATE TABLE {table} (id TEXT PRIMARY KEY, record TEXT NOT NULL)")
            self.connection.execute(
                "CREATE TABLE history (revision INTEGER PRIMARY KEY, operation TEXT NOT NULL, "
                "author TEXT NOT NULL, created_utc TEXT NOT NULL, command TEXT NOT NULL, "
                "before_patch TEXT NOT NULL, after_patch TEXT NOT NULL, undone_revision INTEGER)"
            )
            self.connection.execute(f"PRAGMA user_version={_SCHEMA_VERSION}")
            self.connection.execute(f"PRAGMA application_id={_APPLICATION_ID}")

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            yield
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> ProjectStore:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _head(self) -> sqlite3.Row:
        return self.connection.execute("SELECT revision,active_run FROM project WHERE singleton=1").fetchone()

    def _expect(self, revision: int | None) -> None:
        if revision is not None and (type(revision) is not int or revision != self._head()["revision"]):
            raise RevisionConflict("The project changed since this page was loaded. Reload before saving.")

    def _records(self, table: str) -> dict[str, dict[str, Any]]:
        rows = self.connection.execute(f"SELECT id,record FROM {table}")
        return {row["id"]: json.loads(row["record"]) for row in rows}

    def _editable(self) -> dict[str, Any]:
        return {
            **{table: self._records(table) for table in _EDIT_TABLES},
            "active_run": self._head()["active_run"],
        }

    def _put(self, table: str, identifier: str, record: dict[str, Any]) -> None:
        self.connection.execute(
            f"INSERT INTO {table}(id,record) VALUES (?,?) "
            "ON CONFLICT(id) DO UPDATE SET record=excluded.record",
            (identifier, _json(record)),
        )

    def _record_history(self, operation: str, command: dict[str, Any], before: dict[str, Any], author: str) -> int:
        after = self._editable()
        prior_patch: dict[str, Any] = {}
        next_patch: dict[str, Any] = {}
        for table in _EDIT_TABLES:
            changed = {
                key for key in before[table].keys() | after[table].keys()
                if before[table].get(key) != after[table].get(key)
            }
            if changed:
                prior_patch[table] = {key: before[table].get(key) for key in changed}
                next_patch[table] = {key: after[table].get(key) for key in changed}
        if before["active_run"] != after["active_run"]:
            prior_patch["active_run"] = before["active_run"]
            next_patch["active_run"] = after["active_run"]
        revision = self._head()["revision"] + 1
        self.connection.execute(
            "INSERT INTO history VALUES (?,?,?,?,?,?,?,NULL)",
            (revision, operation, author, datetime.now(timezone.utc).isoformat(),
             _json(command), _json(prior_patch), _json(next_patch)),
        )
        self.connection.execute("UPDATE project SET revision=? WHERE singleton=1", (revision,))
        return revision

    def _run(self, run_id: str | None = None) -> sqlite3.Row:
        selected = run_id or self._head()["active_run"]
        row = self.connection.execute("SELECT * FROM runs WHERE id=?", (selected,)).fetchone()
        if row is None:
            raise ProjectError("Import a completed saved run before reviewing source records.")
        return row

    def _active_ids(self) -> set[str]:
        identifier = self._run()["id"]
        if identifier not in self._source_id_cache:
            key = (identifier, "inventory.json")
            if key not in self._cache:
                self._cache[key] = _decode(self.artifact("inventory.json", identifier))
            self._source_id_cache[identifier] = _source_ids(self._cache[key])
        return self._source_id_cache[identifier]

    def artifact(self, name: str, run_id: str | None = None) -> bytes:
        row = self.connection.execute(
            "SELECT data FROM artifacts WHERE run_id=? AND name=?", (self._run(run_id)["id"], name)
        ).fetchone()
        if row is None:
            raise ProjectError("The selected run does not contain that artifact.")
        return bytes(row["data"])

    def _artifact_json(self, name: str, run_id: str | None = None) -> dict[str, Any]:
        identifier = self._run(run_id)["id"]
        key = (identifier, name)
        if key not in self._cache:
            self._cache[key] = _decode(self.artifact(name, identifier))
        # Callers must not be able to alter the stored evidence through a cache.
        return json.loads(_json(self._cache[key]))

    def inventory(self, run_id: str | None = None) -> dict[str, Any]:
        return self._artifact_json("inventory.json", run_id)

    def analysis(self, run_id: str | None = None) -> dict[str, Any]:
        identifier = self._run(run_id)["id"]
        exists = self.connection.execute(
            "SELECT 1 FROM artifacts WHERE run_id=? AND name='rung-analysis.json'", (identifier,)
        ).fetchone()
        if exists is None:
            return {}
        return self._artifact_json("rung-analysis.json", identifier)

    def state(self) -> dict[str, Any]:
        head = self._head()
        active_ids = self._active_ids() if head["active_run"] else set()
        active_snapshot = self._run()['snapshot_id'] if head['active_run'] else None
        reviews = self._records("reviews")
        for identifier, review in reviews.items():
            review["active"] = identifier in active_ids
        signals = self._records('signals')
        for signal in signals.values():
            signal['active'] = (signal['binding']['snapshot_id'] == active_snapshot
                                and signal['binding']['root_id'] in active_ids)
        groups = list(self._records("groups").values())
        for group in groups:
            group.setdefault('signal_ids', [])
            group.setdefault('member_roles', {})
            group["unresolved_member_ids"] = [identifier for identifier in group["member_ids"]
                                              if identifier not in active_ids
                                              and not reviews.get(identifier, {}).get("correspondence_to")]
            group['unresolved_signal_ids'] = [identifier for identifier in group['signal_ids']
                                               if not signals.get(identifier, {}).get('active', False)]
        runs = []
        for row in self.connection.execute("SELECT * FROM runs ORDER BY imported_utc,id"):
            manifest = json.loads(row["manifest"])
            runs.append({
                "id": row["id"], "snapshot_id": row["snapshot_id"],
                "imported_utc": row["imported_utc"], "status": manifest["status"],
                "parser_version": manifest.get("parser_version"), "source_run_id": manifest["run_id"],
            })
        history = [dict(row) for row in self.connection.execute(
            "SELECT revision,operation,author,created_utc,undone_revision "
            "FROM history ORDER BY revision DESC LIMIT 200"
        )]
        return {
            "schema_version": _SCHEMA_VERSION, "revision": head["revision"],
            "active_run": head["active_run"], "runs": runs,
            "categories": list(self._records("categories").values()),
            "groups": groups, "reviews": reviews,
            "signals": list(signals.values()),
            "rules": list(self._records("rules").values()), "history": history,
        }

    def import_run(self, run_dir: Path, expected_revision: int | None = None) -> dict[str, Any]:
        manifest, artifacts, fingerprint, proposal_digest = _load_run(run_dir)
        with self._transaction():
            self._expect(expected_revision)
            prior = self.connection.execute("SELECT id FROM runs WHERE fingerprint=?", (fingerprint,)).fetchone()
            if prior is not None:
                if prior["id"] != self._head()["active_run"]:
                    raise ProjectError(
                        "This earlier analysis is already retained in the project. "
                        "Open its historical evidence or restore a backup to a separate project; "
                        "the active analysis was not changed."
                    )
                return self.state()
            before = self._editable()
            old_run = self._run() if before["active_run"] else None
            identifier = manifest["run_id"]
            if self.connection.execute("SELECT 1 FROM runs WHERE id=?", (identifier,)).fetchone():
                raise ProjectError("This run identifier was already imported with different content.")
            snapshot_id = manifest["snapshot"]["id"]
            self.connection.execute(
                "INSERT INTO runs VALUES (?,?,?,?,?,?)",
                (identifier, snapshot_id, fingerprint, proposal_digest,
                 _json(manifest), datetime.now(timezone.utc).isoformat()),
            )
            self.connection.executemany(
                "INSERT INTO artifacts VALUES (?,?,?)",
                [(identifier, name, data) for name, data in artifacts.items()],
            )
            self.connection.execute("UPDATE project SET active_run=? WHERE singleton=1", (identifier,))
            analysis = _decode(artifacts["rung-analysis.json"]) if "rung-analysis.json" in artifacts else {}
            self._seed_categories(analysis)
            revision = self._head()["revision"] + 1
            active_ids = _source_ids(_decode(artifacts["inventory.json"]))
            for source_id, original in before["reviews"].items():
                review = dict(original)
                reason = None
                if review["snapshot_id"] != snapshot_id or source_id not in active_ids:
                    reason = "source_changed_requires_correspondence"
                elif review["proposal_digest"] != proposal_digest:
                    reason = "parser_evidence_changed"
                if reason:
                    review.update(
                        status="needs_review", needs_revalidation=True, revision=revision,
                        revalidation_reasons=sorted(set(review.get("revalidation_reasons", []) + [reason])),
                    )
                    self._put("reviews", source_id, review)
            for signal_id, original in before['signals'].items():
                reason = None
                if (original['binding']['snapshot_id'] != snapshot_id
                        or original['binding']['root_id'] not in active_ids):
                    reason = 'source_changed_requires_correspondence'
                elif original['proposal_digest'] != proposal_digest:
                    reason = 'parser_evidence_changed'
                if reason:
                    self._put('signals', signal_id, dict(original, needs_revalidation=True,
                        revision=revision, revalidation_reasons=sorted(set(
                            original.get('revalidation_reasons', []) + [reason]))))
            # Keep human group decisions, but do not let a prior exclusion hide
            # newly changed source/proposals without another look.
            for group_id, original in before['groups'].items():
                if not original.get('proposal_id'):
                    continue
                reasons = set(original.get('revalidation_reasons', []))
                if original.get('snapshot_id') != snapshot_id:
                    reasons.add('source_changed_requires_correspondence')
                elif original.get('proposal_digest') != proposal_digest:
                    reasons.add('parser_evidence_changed')
                if reasons:
                    self._put('groups', group_id, dict(original, needs_revalidation=True,
                              revalidation_reasons=sorted(reasons), revision=revision))
            self._record_history(
                "import", {"run_id": identifier, "previous_run": old_run["id"] if old_run else None},
                before, "Import",
            )
        return self.state()

    def _seed_categories(self, analysis: dict[str, Any]) -> None:
        existing = self._records("categories")
        for identifier, name in _DEFAULT_CATEGORIES:
            key = f"category-{identifier}"
            if key not in existing:
                self._put("categories", key, {"id": key, "name": name})
        for candidate in analysis.get("candidates", []):
            category = candidate.get("category") if isinstance(candidate, dict) else None
            if isinstance(category, str) and re.fullmatch(r"[a-z_]{1,100}", category):
                key = f"parser-{category}"
                if key not in existing:
                    self._put("categories", key, {"id": key, "name": category.replace("_", " ").capitalize()})

    def mutate(self, command: dict[str, Any], expected_revision: int, author: str = "Reviewer") -> dict[str, Any]:
        if not isinstance(command, dict):
            raise ProjectError("A workspace change must be an object.")
        if type(expected_revision) is not int:
            raise ProjectError("A workspace change requires its current project revision.")
        author = _text(author, "Reviewer", 120)
        operation = command.get("op")
        if operation not in ("review", "category", "group", "undo", "rebind", "rule", "signal", "signal_rebind"):
            raise ProjectError("This workspace change is not supported.")
        # Resolve structural anchors before the write transaction. The workspace
        # independently verifies the selected address/signature against its
        # authenticated field projection; neither path trusts browser labels.
        binding = None
        if operation == 'signal_rebind' or operation == 'signal' and 'id' not in command:
            binding = self._signal_binding(command.get('binding'))
        with self._transaction():
            self._expect(expected_revision)
            before = self._editable()
            if operation == "review":
                self._review(command)
            elif operation == "category":
                self._category(command)
            elif operation == "group":
                self._group(command)
            elif operation == "rebind":
                self._rebind(command)
            elif operation == "rule":
                self._rule(command)
            elif operation == 'signal':
                self._signal(command, binding)
            elif operation == 'signal_rebind':
                self._signal_rebind(command, binding)
            else:
                self._undo()
            self._record_history(operation, command, before, author)
        return self.state()

    def _review(self, command: dict[str, Any]) -> None:
        source_ids = _ids(command.get("source_ids"), "Source records", allow_empty=False)
        active_ids = self._active_ids()
        if any(identifier not in active_ids for identifier in source_ids):
            raise ProjectError("Select source records from the active run.")
        if not {"category_ids", "status", "fields"}.intersection(command):
            raise ProjectError("Choose at least one review property to change.")
        categories = _ids(command["category_ids"], "Categories") if "category_ids" in command else None
        known_categories = self._records("categories")
        if categories is not None and any(identifier not in known_categories for identifier in categories):
            raise ProjectError("Select existing categories or create a category first.")
        status = command.get("status")
        if "status" in command and status not in ("unreviewed", "needs_review", "confirmed"):
            raise ProjectError("Choose an available review status.")
        fields = None
        if "fields" in command:
            supplied = command["fields"]
            if not isinstance(supplied, dict) or len(supplied) > 64:
                raise ProjectError("Properties must be a map of at most 64 named values.")
            fields = {
                _text(key, "Property name", 80): _text(value, "Property value", 4000, empty=True)
                for key, value in supplied.items()
            }
            if len(fields) != len(supplied):
                raise ProjectError("Property names must remain distinct after whitespace is removed.")
        run = self._run()
        previous = self._records("reviews")
        for identifier in source_ids:
            old = previous.get(identifier, {})
            # Changing categories alone must not silently confirm a stale review.
            reaffirmed = status is not None
            review = {
                "source_id": identifier, "snapshot_id": run["snapshot_id"],
                "category_ids": categories if categories is not None else old.get("category_ids", []),
                "status": status if status is not None else old.get("status", "needs_review"),
                "fields": fields if fields is not None else old.get("fields", {}),
                "revision": self._head()["revision"] + 1,
                "needs_revalidation": False if reaffirmed else old.get("needs_revalidation", False),
                "revalidation_reasons": [] if reaffirmed else old.get("revalidation_reasons", []),
                "proposal_digest": run["proposal_digest"] if reaffirmed
                else old.get("proposal_digest", run["proposal_digest"]),
            }
            if "previous_source_id" in old:
                review["previous_source_id"] = old["previous_source_id"]
            self._put("reviews", identifier, review)

    def _category(self, command: dict[str, Any]) -> None:
        existing = self._records("categories")
        identifier = (_text(command["id"], "Category identifier", 256)
                      if command.get("id") else f"category-{uuid4().hex}")
        if command.get("id") and identifier not in existing:
            raise ProjectError("The category no longer exists. Reload before editing it.")
        name = _text(command.get("name"), "Category name", 120)
        if any(row["id"] != identifier and row["name"].casefold() == name.casefold() for row in existing.values()):
            raise ProjectError("A category with that name already exists.")
        self._put("categories", identifier, {"id": identifier, "name": name})

    def _signal_binding(self, supplied: Any) -> dict[str, str]:
        """Check a source-qualified selection's immutable structural anchor.

        Field classification and selection provenance are checked by the
        workspace projection before mutation. This independent store boundary
        rejects another run/root, dynamic suffixes and invented address hashes.
        """
        from .references import _ADDRESS
        if not isinstance(supplied, dict) or set(supplied) != _SIGNAL_BINDING_KEYS:
            raise ProjectError('A signal requires its complete captured address binding.')
        binding = {}
        for key in _SIGNAL_BINDING_KEYS:
            value = _text(supplied[key], 'Signal source binding', 4096 if key == 'suffix' else 256)
            if value != supplied[key]:
                raise ProjectError('Signal source binding text must retain its exact identity.')
            binding[key] = value
        run = self._run(binding['run_id'])
        if (run['id'] != self._head()['active_run'] or binding['snapshot_id'] != run['snapshot_id']):
            raise ProjectError('Select a signal from the active source analysis.')
        inventory = self.inventory(run['id'])
        root = next((row for row in inventory['entities'] if row['id'] == binding['root_id']), None)
        if root is None or root['kind'] not in {'module_input_tag', 'module_output_tag', 'module_config_tag'}:
            raise ProjectError('A field signal must retain a captured module backing declaration.')
        suffix = binding['suffix']
        if not suffix.startswith(('.', '[')) or _ADDRESS.fullmatch('A' + suffix) is None:
            raise ProjectError('A field signal requires an exact static member address.')
        normalized = re.sub(r'\.[A-Za-z_][A-Za-z0-9_]*', lambda match: match.group().lower(), suffix)
        expected = 'field_address_' + hashlib.sha256((root['id'] + '\0' + normalized).encode()).hexdigest()
        if binding['address_id'] != expected or not re.fullmatch(r'[0-9a-f]{64}', binding['evidence_signature']):
            raise ProjectError('Signal address identity or evidence signature is invalid.')
        return binding

    def _signal_collision(self, identifier: str, binding: dict[str, str]) -> None:
        for other_id, signal in self._records('signals').items():
            other = signal['binding']
            if (other_id != identifier and other['snapshot_id'] == binding['snapshot_id']
                    and other['address_id'] == binding['address_id']):
                raise ProjectError('This captured signal already has an engineering record; edit that record instead.')

    def _signal(self, command: dict[str, Any], binding: dict[str, str] | None) -> None:
        allowed = {'op', 'id', 'binding', 'target_name', 'description', 'field_type', 'confirm'}
        if set(command) - allowed:
            raise ProjectError('This signal change contains unsupported fields.')
        existing = self._records('signals')
        identifier = _text(command['id'], 'Signal identifier', 256) if 'id' in command else f'signal-{uuid4().hex}'
        old = existing.get(identifier)
        if 'id' in command and old is None:
            raise ProjectError('The engineering signal no longer exists. Reload before editing it.')
        if old is not None and 'binding' in command:
            raise ProjectError('Use explicit signal correspondence to change a source binding.')
        if old is None and (binding is None or len(existing) >= MAX_SIGNALS):
            raise ProjectError('The signal selection is missing or the project signal limit was reached.')
        if old is not None and not {'target_name', 'description', 'field_type', 'confirm'}.intersection(command):
            raise ProjectError('Choose at least one signal property to change.')
        if 'confirm' in command and type(command['confirm']) is not bool:
            raise ProjectError('Signal confirmation must be an explicit true or false value.')
        record = dict(old) if old else {
            'id': identifier, 'binding': binding, 'binding_history': [], 'target_name': '',
            'description': '', 'field_type': 'unknown', 'proposal_digest': self._run()['proposal_digest'],
            'needs_revalidation': False, 'revalidation_reasons': [],
        }
        for key, limit in (('target_name', 160), ('description', 4000)):
            if key in command:
                record[key] = _text(command[key], 'Signal ' + key.replace('_', ' '), limit, empty=True)
        if 'field_type' in command:
            value = command['field_type']
            if not isinstance(value, str) or value not in SIGNAL_FIELD_TYPES:
                raise ProjectError('Choose an available reviewed signal field type.')
            record['field_type'] = value
        self._signal_collision(identifier, record['binding'])
        if command.get('confirm'):
            run = self._run()
            if (record['binding']['snapshot_id'] != run['snapshot_id']
                    or record['binding']['root_id'] not in self._active_ids()):
                raise ProjectError('Reconnect this signal to the current source before confirming it.')
            # The workspace also requires the current projected signature to
            # match. A same-snapshot rerun can then reaffirm changed analysis.
            record.update(needs_revalidation=False, revalidation_reasons=[], proposal_digest=run['proposal_digest'])
        record['revision'] = self._head()['revision'] + 1
        self._put('signals', identifier, record)

    def _signal_rebind(self, command: dict[str, Any], binding: dict[str, str] | None) -> None:
        if set(command) != {'op', 'id', 'binding'} or binding is None:
            raise ProjectError('Signal correspondence requires an existing signal and a complete new binding.')
        identifier = _text(command['id'], 'Signal identifier', 256)
        original = self._records('signals').get(identifier)
        if original is None:
            raise ProjectError('Choose a retained engineering signal for correspondence.')
        if original['binding'] == binding:
            raise ProjectError('The signal is already bound to this exact source evidence.')
        self._signal_collision(identifier, binding)
        history = list(original['binding_history'])
        if len(history) >= MAX_SIGNAL_BINDINGS:
            raise ProjectError('The signal correspondence history limit was reached.')
        revision = self._head()['revision'] + 1
        history.append({'binding': original['binding'], 'proposal_digest': original['proposal_digest'],
                        'revision': original['revision'], 'replaced_revision': revision})
        self._put('signals', identifier, dict(original, binding=binding, binding_history=history,
            proposal_digest=self._run()['proposal_digest'], revision=revision, needs_revalidation=True,
            revalidation_reasons=['explicit_correspondence_requires_review']))

    def _group(self, command: dict[str, Any]) -> None:
        from .workspace_classification import CATEGORY_DEFINITIONS
        existing = self._records("groups")
        identifier = _text(command["id"], "Group identifier", 256) if command.get("id") else f"group-{uuid4().hex}"
        if command.get("id") and identifier not in existing:
            raise ProjectError("The engineering group no longer exists. Reload before editing it.")
        name = _text(command.get("name"), "Group name", 160)
        members = _ids(command.get("member_ids", []), "Group members")
        active_ids = self._active_ids()
        old = existing.get(identifier, {})
        previous = old.get("member_ids", [])
        # Existing old-snapshot memberships remain editable/visible, but cannot
        # be invented by submitting an arbitrary source identifier.
        if any(member not in active_ids and member not in previous for member in members):
            raise ProjectError("Group members must belong to this run or the group's retained evidence.")
        signal_ids = _ids(command.get('signal_ids', old.get('signal_ids', [])), 'Engineering signals')
        known_signals = self._records('signals')
        if any(signal_id not in known_signals for signal_id in signal_ids):
            raise ProjectError('Group signals must be retained engineering signal records.')
        supplied_roles = command.get('member_roles')
        if 'member_roles' in command:
            if (not isinstance(supplied_roles, dict) or not set(supplied_roles).issubset(set(members))
                    or any(not isinstance(role, str) or role not in MEMBER_ROLES for role in supplied_roles.values())):
                raise ProjectError('Member roles must assign scaling, alarm, reference or logic to existing source members.')
            roles = dict(supplied_roles)
        else:
            roles = {member: role for member, role in old.get('member_roles', {}).items() if member in members}
        functions = _ids(command.get('function_categories', old.get('function_categories', [])), 'Function categories')
        if not set(functions).issubset({row['id'] for row in CATEGORY_DEFINITIONS}):
            raise ProjectError('Choose one of the available engineering function categories.')
        migration = command.get('migration_status', old.get('migration_status', 'unreviewed'))
        if not isinstance(migration, str) or migration not in MIGRATION_STATUSES:
            raise ProjectError('Choose an available migration disposition.')
        note = _text(command.get('migration_note', old.get('migration_note', '')),
                     'Migration note', 4000, empty=True)
        proposal = old.get('proposal_id')
        if 'proposal_id' in command:
            supplied = _text(command['proposal_id'], 'Source proposal', 256)
            if proposal is not None and supplied != proposal:
                raise ProjectError('The source proposal for an existing group cannot be changed.')
            proposal = supplied
        record = {
            "id": identifier, "name": name, "member_ids": members,
            'signal_ids': signal_ids, 'member_roles': roles,
            'function_categories': functions, 'migration_status': migration, 'migration_note': note,
            "revision": self._head()["revision"] + 1,
        }
        if proposal:
            record['proposal_id'] = proposal
            signature = command.get('proposal_signature', old.get('proposal_signature'))
            if signature is not None:
                if not isinstance(signature, str) or not re.fullmatch(r'[0-9a-f]{64}', signature):
                    raise ProjectError('The source group evidence signature is invalid.')
                record['proposal_signature'] = signature
            run = self._run()
            reaffirmed = 'migration_status' in command and all(member in active_ids for member in members)
            record.update(
                snapshot_id=run['snapshot_id'] if reaffirmed else old.get('snapshot_id', run['snapshot_id']),
                proposal_digest=run['proposal_digest'] if reaffirmed else old.get('proposal_digest', run['proposal_digest']),
                needs_revalidation=False if reaffirmed else old.get('needs_revalidation', False),
                revalidation_reasons=[] if reaffirmed else old.get('revalidation_reasons', []),
            )
        self._put("groups", identifier, record)

    def _rebind(self, command: dict[str, Any]) -> None:
        from_id = _text(command.get("from_id"), "Previous source", 256)
        to_id = _text(command.get("to_id"), "Current source", 256)
        reviews = self._records("reviews")
        if from_id not in reviews or to_id not in self._active_ids() or from_id == to_id:
            raise ProjectError("Choose a retained review and a different current source record.")
        if to_id in reviews:
            raise ProjectError("The destination already has a review; it cannot be overwritten by correspondence.")
        review = dict(reviews[from_id])
        review.pop("correspondence_to", None)
        run = self._run()
        review.update(
            source_id=to_id, snapshot_id=run["snapshot_id"], status="needs_review", needs_revalidation=True,
            revalidation_reasons=["explicit_correspondence_requires_review"], previous_source_id=from_id,
            proposal_digest=run["proposal_digest"], revision=self._head()["revision"] + 1,
        )
        self._put("reviews", to_id, review)
        previous = reviews[from_id]
        previous["correspondence_to"] = list(dict.fromkeys(previous.get("correspondence_to", []) + [to_id]))
        self._put("reviews", from_id, previous)
        for group in self._records("groups").values():
            if from_id in group["member_ids"] and to_id not in group["member_ids"]:
                group["member_ids"].append(to_id)
                roles = group.get('member_roles', {})
                if from_id in roles and to_id not in roles:
                    group['member_roles'] = {**roles, to_id: roles[from_id]}
                group["revision"] = self._head()["revision"] + 1
                self._put("groups", group["id"], group)

    def _rule(self, command: dict[str, Any]) -> None:
        existing = self._records("rules")
        identifier = _text(command["id"], "Rule identifier", 256) if command.get("id") else f"rule-{uuid4().hex}"
        if command.get("id") and identifier not in existing:
            raise ProjectError("The classification rule no longer exists. Reload before editing it.")
        previous = existing.get(identifier)
        enabled = command.get("enabled", True)
        if type(enabled) is not bool:
            raise ProjectError("Rule enabled must be true or false.")
        name = _text(command.get("name", previous["name"] if previous else None), "Rule name", 160)
        source_id = _text(
            command.get("source_id", previous["source_id"] if previous else None), "Rule example source", 256
        )
        categories = _ids(
            command.get("category_ids", previous["category_ids"] if previous else []),
            "Rule categories", allow_empty=False,
        )
        known_categories = self._records("categories")
        if any(category not in known_categories for category in categories):
            raise ProjectError("Select existing categories for the rule.")
        rungs = self.inventory()["rungs"]
        source = next((rung for rung in rungs if rung["id"] == source_id), None)
        if source is None and previous and source_id == previous["source_id"]:
            pattern = previous["pattern"]
            snapshot_id = previous["snapshot_id"]
        elif source is None:
            raise ProjectError("Select a captured rung as the classification rule example.")
        else:
            pattern = rung_pattern(source)
            snapshot_id = self._run()["snapshot_id"]
            if pattern is None or not source.get("instructions"):
                raise ProjectError("This rung has no complete parsed instruction structure for a rule.")
        revision = self._head()["revision"] + 1
        rule = {
            "id": identifier, "name": name, "source_id": source_id, "snapshot_id": snapshot_id,
            "category_ids": categories, "enabled": enabled, "pattern": pattern, "revision": revision,
        }
        self._put("rules", identifier, rule)
        affected_patterns = [pattern] + ([previous["pattern"]] if previous else [])
        affected = {rung["id"] for rung in rungs if rung_pattern(rung) in affected_patterns}
        for source_id, review in self._records("reviews").items():
            if source_id in affected:
                review.update(
                    status="needs_review", needs_revalidation=True, revision=revision,
                    revalidation_reasons=sorted(set(
                        review.get("revalidation_reasons", []) + ["classification_rule_changed"]
                    )),
                )
                self._put("reviews", source_id, review)

    def _undo(self) -> None:
        row = self.connection.execute(
            "SELECT revision,before_patch FROM history "
            "WHERE operation NOT IN ('import','undo') AND undone_revision IS NULL "
            "AND revision > (SELECT COALESCE(MAX(revision),0) FROM history WHERE operation='import') "
            "ORDER BY revision DESC LIMIT 1"
        ).fetchone()
        if row is None:
            raise ProjectError("There are no edits to undo since the latest source import.")
        patch = json.loads(row["before_patch"])
        for table in _EDIT_TABLES:
            for identifier, record in patch.get(table, {}).items():
                if record is None:
                    self.connection.execute(f"DELETE FROM {table} WHERE id=?", (identifier,))
                else:
                    self._put(table, identifier, record)
        self.connection.execute(
            "UPDATE history SET undone_revision=? WHERE revision=?",
            (self._head()["revision"] + 1, row["revision"]),
        )

    def backup(self, destination: Path) -> Path:
        target = _private_path(destination)
        if target == self.path:
            raise ProjectError("Choose a new backup filename; the active project cannot be replaced.")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            # Reserve the destination without replacing an existing backup.
            with target.open("xb"):
                pass
        except OSError as exc:
            raise ProjectError("Choose a new writable backup filename; existing files are never replaced.") from exc
        try:
            with closing(sqlite3.connect(target)) as backup:
                self.connection.backup(backup)
                if backup.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ProjectError("The backup did not pass its integrity check.")
        except (OSError, sqlite3.Error) as exc:
            raise ProjectError("Could not complete the project backup. Keep the active project.") from exc
        return target
