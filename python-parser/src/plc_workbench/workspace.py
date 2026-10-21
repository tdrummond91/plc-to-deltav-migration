"""Local, explicitly launched editor for immutable analysis and reviewed decisions.

The browser never receives a filesystem server. Only named application assets,
verified imported artifacts and project operations are available on loopback.
No Git/network synchronization or background polling is performed.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import socket
import sqlite3
import threading
from typing import Any
from urllib.parse import parse_qs, urlsplit
import webbrowser

from .project_store import ProjectError, ProjectStore, RevisionConflict, rung_pattern
from .storage import StorageError, _workspace_path

ASSETS = Path(__file__).with_name("workspace_assets")
PAGE_SIZE = 50
MAX_REQUEST_BYTES = 2 * 1024 * 1024
_UNLOADED = object()


def _json(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


class Workspace:
    """Browser projection; the store remains the only writable authority."""

    def __init__(self, project: Path, runs: Path):
        self.project = _workspace_path(project)
        self.runs_path = _workspace_path(runs)
        self.store = ProjectStore(self.project)
        self._run: str | None | object = _UNLOADED
        self._inventory: dict = {}
        self._sources: dict = {}
        self._paths: dict[str, str] = {}
        self._proposals: dict[str, list] = defaultdict(list)
        self._operands: dict[str, list] = defaultdict(list)
        self._rungs: list = []
        self._objects: list = []
        self._rung_for: dict[str, str] = {}
        self._patterns: dict[str, dict | None] = {}
        self._historical_labels: dict[str, str] = {}
        self._report_cache: tuple[str | None, bytes] = (None, b'')
        self.startup_notice = ''

    def close(self) -> None:
        self.store.close()

    def _load(self, state: dict) -> None:
        active = state.get("active_run")
        # Accept the store's stable run ID; do not infer identity from a filename.
        if isinstance(active, dict):
            active = active.get("id")
        if active == self._run:
            return
        self._run = _UNLOADED
        self._inventory = self.store.inventory(active) if active else {}
        self._rungs = self._inventory.get("rungs", [])
        self._objects = self._inventory.get("entities", [])
        self._sources = {row["id"]: row for row in self._objects + self._rungs}
        self._paths = {}
        self._rung_for = {}
        self._patterns = {rung['id']: rung_pattern(rung) for rung in self._rungs}
        for rung in self._rungs:
            self._rung_for[rung["id"]] = rung["id"]
            for instruction in rung.get("instructions", []):
                self._sources[instruction["id"]] = instruction
                self._rung_for[instruction["id"]] = rung["id"]
        self._proposals = defaultdict(list)
        for candidate in self.store.analysis(active).get("candidates", []) if active else []:
            self._proposals[candidate["rung_id"]].append(candidate)
        self._operands = defaultdict(list)
        if active:
            try:
                references = json.loads(self.store.artifact("references.json", active))
            except (ProjectError, KeyError):
                references = {}
            for operand in references.get("operands", []):
                self._operands[operand.get("instruction_id", "")].append(operand)
        # Publish the cache identity only after every imported dependency loads.
        self._run = active

    def path(self, identifier: str) -> str:
        if identifier in self._paths:
            return self._paths[identifier]
        current = identifier
        parts: list[str] = []
        seen: set[str] = set()
        while current and current in self._sources and current not in seen:
            seen.add(current)
            source = self._sources[current]
            if "opcode" in source:
                parts.append(source["opcode"])
                current = self._rung_for.get(current, "")
            elif "number" in source:
                parts.append(f"Rung {source.get('number') or source.get('ordinal', '?')}")
                current = source.get("parent_id", "")
            else:
                parts.append(source.get("name") or source.get("kind", "Unnamed"))
                current = source.get("parent_id", "")
        result = " / ".join(reversed(parts))
        self._paths[identifier] = result
        return result

    def state(self) -> dict:
        state = self.store.state()
        self._load(state)
        snapshot = self._inventory.get("snapshot", {})
        controllers = [o.get("name") or "Unnamed" for o in self._objects if o.get("kind") == "controller"]
        routine_counts = Counter(row.get("parent_id") for row in self._rungs)
        state["source"] = {
            "name": ", ".join(controllers) or "No source imported",
            "snapshot": snapshot,
            "rung_count": len(self._rungs),
            "instruction_count": sum(len(r.get("instructions", [])) for r in self._rungs),
            "object_count": len(self._objects),
        }
        state["routines"] = [
            {"id": row["id"], "name": row.get("name", "Unnamed"), "path": self.path(row["id"]),
             "count": routine_counts[row["id"]], "type": row.get("attributes", {}).get("Type", "")}
            for row in self._objects if row.get("kind") == "routine"
        ]
        state["counts"] = {"rungs": len(self._rungs), "objects": len(self._objects),
                           "reviewed": sum(r.get("active", True) and r.get("status") == "confirmed"
                                           and not r.get("needs_revalidation", False)
                                           for r in state.get("reviews", {}).values()),
                           "source_coverage": self._inventory.get("coverage", {}),
                           "source_status": self._inventory.get("status", "not_loaded")}
        snapshots = {run['snapshot_id']: run['id'] for run in state.get('runs', [])}
        state["pending_reviews"] = [
            {"source_id": identifier, "path": self.path(identifier) or review.get("source_path") or identifier,
             "review": review, "run_id": snapshots.get(review.get("snapshot_id"))}
            for identifier, review in state.get("reviews", {}).items()
            if (not review.get("active", True) and not review.get("correspondence_to"))
            or (review.get("active", True) and review.get("needs_revalidation", False))
        ]
        missing_runs = {row['run_id'] for row in state['pending_reviews']
                        if row['source_id'] not in self._sources and row['source_id'] not in self._historical_labels}
        for run_id in missing_runs - {None}:
            self._retain_labels(self.store.inventory(run_id))
        for row in state['pending_reviews']:
            row['path'] = self._historical_labels.get(row['source_id'], row['path'])
        for group in state.get('groups', []):
            group['members'] = [{'id': identifier, 'path': self.path(identifier) or self._historical_labels.get(identifier, 'Earlier source · ' + identifier)}
                                for identifier in group.get('member_ids', [])]
        state["project_path"] = str(self.project)
        state['startup_notice'] = self.startup_notice
        return state

    def _retain_labels(self, inventory: dict) -> None:
        records = {row['id']: row for row in inventory.get('entities', []) + inventory.get('rungs', [])}
        for rung in inventory.get('rungs', []):
            records.update({i['id']: dict(i, parent_id=rung['id']) for i in rung.get('instructions', [])})
        for identifier in records:
            parts, seen = [], set()
            current = identifier
            while current in records and current not in seen:
                seen.add(current)
                row = records[current]
                label = (f"Rung {row.get('number') or row.get('ordinal', '?')}" if 'number' in row
                         else row.get('name') or row.get('opcode') or row.get('kind', 'Unnamed'))
                parts.append(label)
                current = row.get('parent_id')
            self._historical_labels[identifier] = ' / '.join(reversed(parts))

    @staticmethod
    def _page(items: list, query: dict) -> dict:
        try:
            page = max(1, int(query.get("page", "1")))
        except (ValueError, TypeError):
            raise ProjectError("Page must be a positive number.") from None
        page = min(page, max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE))
        return {"items": items[(page - 1) * PAGE_SIZE:page * PAGE_SIZE], "total": len(items),
                "page": page, "page_size": PAGE_SIZE}

    def rungs(self, query: dict) -> dict:
        state = self.state()
        reviews = state.get("reviews", {})
        memberships: dict[str, list[str]] = defaultdict(list)
        for group in state.get("groups", []):
            for identifier in group.get("member_ids", []):
                memberships[identifier].append(group["id"])
        rows = []
        search = query.get("query", "").casefold()
        for rung in self._rungs:
            identifier = rung["id"]
            review = reviews.get(identifier, {})
            proposals = sorted({c["category"] for c in self._proposals[identifier]})
            path = self.path(identifier)
            if query.get("routine") and rung.get("parent_id") != query["routine"]:
                continue
            if query.get("category") and query["category"] not in review.get("category_ids", []):
                continue
            if query.get("status") and review.get("status", "unreviewed") != query["status"]:
                continue
            if query.get("group") and query["group"] not in memberships[identifier]:
                continue
            if search and search not in " ".join([path, rung.get("text") or "", rung.get("comment") or "",
                                                  " ".join(proposals), " ".join(review.get("fields", {}).values())]).casefold():
                continue
            rows.append({"id": identifier, "number": rung.get("number"), "path": path,
                         "text": rung.get("text"), "comment": rung.get("comment"),
                         "parse_status": rung.get("parse_status"), "proposals": proposals,
                         "review": review, "groups": memberships[identifier],
                         "rule_proposals": self.rule_proposals(identifier, state)})
        return self._page(rows, query)

    def objects(self, query: dict) -> dict:
        self.state()
        search = query.get("query", "").casefold()
        items = []
        sources = self._objects
        if query.get('kind') == 'instruction':
            sources = [dict(instruction, kind='instruction', name=instruction['opcode'],
                            description=rung.get('text', '')[instruction.get('start', 0):instruction.get('end', 0)])
                       for rung in self._rungs for instruction in rung.get('instructions', [])]
        for source in sources:
            path = self.path(source["id"])
            if query.get("kind") and query["kind"] != source.get("kind"):
                continue
            if search and search not in (path + " " + (source.get("description") or "")).casefold():
                continue
            items.append({"id": source["id"], "kind": source.get("kind"), "name": source.get("name"),
                          "path": path, "description": source.get("description")})
        return self._page(items, query)

    def source(self, identifier: str, run_id: str | None = None) -> dict:
        state = self.store.state()
        active = state.get('active_run')
        self._load(dict(state, active_run=run_id or active))
        try:
            result = self._source_detail(identifier, state)
            result['historical'] = bool(run_id and run_id != active)
            result['run_id'] = run_id or active
            result['revision'] = state['revision']
            return result
        finally:
            self._load(state)

    def _source_detail(self, identifier: str, state: dict) -> dict:
        if identifier not in self._sources:
            raise ProjectError("This source record is not present in the selected analysis.")
        source = self._sources[identifier]
        rung_id = self._rung_for.get(identifier)
        kind = "rung" if "instructions" in source else "instruction" if "opcode" in source else source.get("kind", "object")
        related = []
        parent = rung_id if kind == "instruction" else source.get("parent_id")
        if parent and parent != identifier and parent in self._sources:
            related.append({"id": parent, "label": self.path(parent)})
        operands = []
        instruction_ids = [i["id"] for i in source.get("instructions", [])] if kind == "rung" else [identifier]
        for instruction_id in instruction_ids:
            for operand in self._operands[instruction_id]:
                targets = list(dict.fromkeys(operand.get(key) for key in ("target_id", "root_id", "resolved_id", "symbol_id")
                           if operand.get(key) in self._sources))
                operands.append(dict(operand, target_ids=targets))
                for target in targets:
                    related.append({"id": target, "label": self.path(target)})
        return {"source": source, "path": self.path(identifier), "kind": kind,
                "proposals": self._proposals.get(rung_id or identifier, []),
                "review": state.get("reviews", {}).get(identifier, {}), "operands": operands,
                "rule_proposals": self.rule_proposals(rung_id or identifier, state),
                "related": list({row["id"]: row for row in related}.values()),
                "group_ids": [g["id"] for g in state.get("groups", []) if identifier in g.get("member_ids", [])]}

    def rule_proposals(self, identifier: str, state: dict) -> list:
        pattern = self._patterns.get(identifier)
        return [{"rule_id": rule["id"], "name": rule["name"], "category_ids": rule["category_ids"]}
                for rule in state.get("rules", [])
                if pattern is not None and rule.get("enabled") and rule.get("pattern") == pattern]

    def rule_matches(self, identifier: str) -> dict:
        self.state()
        pattern = self._patterns.get(identifier)
        if pattern is None:
            raise ProjectError("Choose a parsed rung with a captured branch structure.")
        matches = [{"id": r["id"], "path": self.path(r["id"]), "text": r.get("text")}
                   for r in self._rungs if self._patterns[r["id"]] == pattern]
        return {"items": matches, "total": len(matches), "pattern": pattern}

    def available_runs(self) -> dict:
        items = []
        if self.runs_path.is_dir():
            for path in sorted(self.runs_path.iterdir(), reverse=True):
                if path.is_symlink() or not path.is_dir() or not (path / "manifest.json").is_file():
                    continue
                items.append({"path": str(path), "label": path.name})
        return {"items": items}

    def report(self) -> bytes:
        from .workspace_report import refresh_report
        state = self.state()
        active = state.get('active_run')
        if not active:
            raise ProjectError('Import a completed source analysis first.')
        if self._report_cache[0] != active:
            rendered = refresh_report(self.store.artifact('review.html'), self._inventory)
            self._report_cache = (active, rendered)
        return self._report_cache[1]

    def import_run(self, raw_path: str, expected_revision: int) -> dict:
        if type(expected_revision) is not int:
            raise ProjectError("Reload the workspace before importing; an expected project revision is required.")
        path = Path(raw_path).expanduser().resolve()
        if path.parent != self.runs_path or path.is_symlink():
            raise ProjectError("Choose a completed run from the configured private runs folder.")
        self.store.import_run(path, expected_revision=expected_revision)
        return self.state()

    def backup(self) -> dict:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        destination = self.project.parent / "backups" / f"{self.project.stem}-{stamp}.sqlite"
        self.store.backup(destination)
        return {"path": str(destination)}

    def backups(self) -> dict:
        folder = self.project.parent / 'backups'
        return {'items': [{'name': p.name, 'path': str(p), 'size_bytes': p.stat().st_size}
                          for p in sorted(folder.glob('*.sqlite'), reverse=True)
                          if p.is_file() and not p.is_symlink()]}

    def restore(self, name: str, expected_revision: int) -> dict:
        if type(expected_revision) is not int or expected_revision != self.store.state()['revision']:
            raise RevisionConflict('The project changed since this page was loaded. Reload before restoring.')
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*\.sqlite', name):
            raise ProjectError('Choose a backup from the saved project backups list.')
        backup = self.project.parent / 'backups' / name
        if not backup.is_file() or backup.is_symlink():
            raise ProjectError('That backup is no longer available.')
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        destination = self.project.parent / f'restored-{stamp}.sqlite'
        with ProjectStore(backup) as saved:
            saved.backup(destination)
        restored = ProjectStore(destination)
        # A tiny local pointer makes the next normal launch reopen this restored
        # project. Both the original database and the selected backup survive.
        pointer = self.project.parent / 'last-project.json'
        pending = pointer.with_name(f'.last-project-{secrets.token_hex(8)}.tmp')
        try:
            with pending.open('xb') as stream:
                stream.write(_json({'filename': destination.name}))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(pending, pointer)
        except OSError:
            restored.close()
            raise ProjectError('The restored copy was created, but could not be selected for reopening.') from None
        self.store.close()
        self.store, self.project = restored, destination
        self._run = _UNLOADED
        self._report_cache = (None, b'')
        self._historical_labels = {}
        return self.state()


class WorkspaceServer(HTTPServer):
    # Windows SO_REUSEADDR can permit two listeners on one port. Exclusive
    # ownership must be established before an automatic import changes a project.
    allow_reuse_address = os.name != 'nt'

    def __init__(self, address: tuple[str, int], workspace: Workspace):
        self.workspace = workspace
        self.token = secrets.token_urlsafe(32)
        super().__init__(address, WorkspaceHandler)

    def server_bind(self) -> None:
        if os.name == 'nt' and hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    @property
    def origin(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}"

    def get_request(self) -> tuple:
        connection, address = super().get_request()
        connection.settimeout(10)
        return connection, address


class WorkspaceHandler(BaseHTTPRequestHandler):
    server: WorkspaceServer
    server_version = "PLCWorkbench"

    def log_message(self, format: str, *args: Any) -> None:
        # Paths and query text may contain private engineering names.
        return

    def _send(self, status: int, data: bytes, content_type: str, *, report: bool = False) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        if report:
            # Imported HTML is evidence, not trusted application code. Even a
            # self-consistent altered manifest must not grant it editor access.
            # Opaque-origin sandbox preserves its self-contained script while
            # blocking access to the project API, opener and local storage.
            self.send_header("Content-Security-Policy", "sandbox allow-scripts; default-src 'none'; "
                             "script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; "
                             "connect-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        else:
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; "
                             "connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'self'")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, status: int, value: Any) -> None:
        self._send(status, _json(value), "application/json; charset=utf-8")

    def _allowed(self, *, write: bool = False) -> bool:
        def reject(message: str) -> bool:
            # Drain a bounded rejected POST so Windows can deliver the JSON
            # response instead of resetting the socket with unread input.
            if write:
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if 0 < length <= MAX_REQUEST_BYTES:
                        self.rfile.read(length)
                except (ValueError, OSError):
                    pass
            self._json(403, {'error': message})
            return False

        if self.headers.get("Host") != urlsplit(self.server.origin).netloc:
            return reject("Open this workspace using its local 127.0.0.1 address.")
        origin = self.headers.get("Origin")
        if origin is not None and origin != self.server.origin:
            return reject("Requests must originate in this workspace.")
        top_navigation = (not write and self.headers.get('Sec-Fetch-Mode') == 'navigate'
                          and urlsplit(self.path).path in ('/', '/index.html', '/analysis'))
        if self.headers.get("Sec-Fetch-Site") == "cross-site" and not top_navigation:
            return reject("Cross-site access is not allowed.")
        if write:
            token = self.headers.get("X-Workspace-Token", "")
            if not token.isascii() or not secrets.compare_digest(token, self.server.token):
                return reject("Reopen the workspace page before saving.")
        return True

    def do_GET(self) -> None:
        if not self._allowed():
            return
        url = urlsplit(self.path)
        query = {key: values[-1] for key, values in parse_qs(url.query).items()}
        workspace = self.server.workspace
        try:
            if url.path == "/api/state":
                self._json(200, workspace.state())
            elif url.path == "/api/rungs":
                self._json(200, workspace.rungs(query))
            elif url.path == "/api/objects":
                self._json(200, workspace.objects(query))
            elif url.path == "/api/source":
                self._json(200, workspace.source(query.get("id", ""), query.get("run_id")))
            elif url.path == "/api/runs":
                self._json(200, workspace.available_runs())
            elif url.path == "/api/backups":
                self._json(200, workspace.backups())
            elif url.path == "/api/rule-matches":
                self._json(200, workspace.rule_matches(query.get("source_id", "")))
            elif url.path == "/analysis":
                self._send(200, workspace.report(), "text/html; charset=utf-8", report=True)
            elif url.path in ("/", "/index.html", "/workspace.js", "/workspace.css"):
                name = "index.html" if url.path in ("/", "/index.html") else url.path[1:]
                data = (ASSETS / name).read_bytes()
                if name == "index.html":
                    data = data.replace(b"__WORKSPACE_TOKEN__", self.server.token.encode("ascii"))
                content_type = {"index.html": "text/html", "workspace.js": "text/javascript", "workspace.css": "text/css"}[name]
                self._send(200, data, content_type + "; charset=utf-8")
            else:
                self._json(404, {"error": "Page not found."})
        except (ProjectError, StorageError) as exc:
            self._json(400, {"error": str(exc)})
        except (OSError, ValueError, KeyError, sqlite3.Error):
            self._json(500, {"error": "Could not read the project. Close the workspace and check its saved files."})

    def do_POST(self) -> None:
        if not self._allowed(write=True):
            return
        workspace = self.server.workspace
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_REQUEST_BYTES:
                self._json(413, {"error": "The requested change is too large or empty."})
                return
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                self._json(415, {"error": "Changes must use the workspace's JSON form."})
                return
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ProjectError("Expected a workspace operation.")
            route = urlsplit(self.path).path
            if route == "/api/mutate":
                workspace.store.mutate(payload.get("command", {}), payload.get("expected_revision"),
                                       author=payload.get("author", "Reviewer"))
                result = workspace.state()
            elif route == "/api/import":
                result = workspace.import_run(payload.get("path", ""), payload.get("expected_revision"))
            elif route == "/api/backup":
                result = workspace.backup()
            elif route == '/api/restore':
                result = workspace.restore(payload.get('name'), payload.get('expected_revision'))
                # A revision number identifies a state within one database.
                # Retire every other tab's write session when changing projects.
                self.server.token = secrets.token_urlsafe(32)
                result['workspace_token'] = self.server.token
            elif route == "/api/stop":
                result = {"stopped": True}
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            else:
                self._json(404, {"error": "Operation not found."})
                return
            self._json(200, result)
        except (ProjectError, StorageError) as exc:
            message = str(exc)
            status = 409 if isinstance(exc, RevisionConflict) else 400
            self._json(status, {"error": message})
        except (ValueError, TypeError, KeyError, RecursionError):
            self._json(400, {"error": "Invalid workspace operation. Reload the page and try again."})
        except (OSError, sqlite3.Error):
            self._json(500, {"error": "Could not save the project. Check disk space and access, then retry."})


def _startup_project(explicit: Path | None, *, automatic_import: bool) -> tuple[Path, str]:
    """Resolve the selected project before opening or creating any database.

    Manual startup can explain a fallback and let the reviewer choose a backup.
    An automatic import must never send new analysis to that unintended fallback.
    """
    if explicit is not None:
        return explicit, ''
    default = Path('confidential/projects/engineering.sqlite')
    pointer = default.parent / 'last-project.json'
    if not pointer.exists() and not pointer.is_symlink():
        return default, ''
    try:
        if pointer.is_file() and not pointer.is_symlink() and pointer.stat().st_size <= 1024:
            filename = json.loads(pointer.read_text(encoding='utf-8')).get('filename')
            if isinstance(filename, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*\.sqlite', filename):
                candidate = default.parent / filename
                if candidate.is_file() and not candidate.is_symlink():
                    return candidate, ''
    except (OSError, ValueError, AttributeError):
        pass
    if automatic_import:
        raise ProjectError(
            'The previously selected project is missing or its selection file is invalid. '
            'No analysis was imported and no fallback project was created. '
            'Open the workspace manually to select or restore the intended project, '
            'then choose the already completed run under Import analysis. No analysis rerun is needed.'
        )
    return default, (
        'The previously selected project could not be found. '
        'The default project is open; earlier project files have not been replaced.'
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Open the local editable engineering workspace. No Git operations.")
    parser.add_argument("--project", type=Path, help="Explicit project; otherwise reopen the last selected local project.")
    parser.add_argument("--runs", type=Path, default=Path("confidential/workspaces/work-check"))
    parser.add_argument("--import-run", type=Path,
                        help="Import this completed run into the selected project before opening the editor.")
    parser.add_argument("--port", type=int, default=8745)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")
    try:
        project, startup_notice = _startup_project(args.project, automatic_import=args.import_run is not None)
        with_workspace = Workspace(project, args.runs)
        with_workspace.startup_notice = startup_notice
        try:
            server = WorkspaceServer(("127.0.0.1", args.port), with_workspace)
            try:
                # Binding first avoids changing the project if another editor
                # already occupies the requested port. Import remains atomic.
                if args.import_run is not None:
                    loaded = with_workspace.import_run(
                        str(args.import_run), with_workspace.store.state()['revision']
                    )
                    startup_notice = (
                        f"Analysis ready: {loaded['source']['name']} - "
                        f"{loaded['source']['rung_count']:,} captured rungs. "
                        'Saved review corrections are retained; changed evidence is flagged for review.'
                    )
                    with_workspace.startup_notice = startup_notice
                print(f"Engineering workspace: {server.origin}", flush=True)
                if args.import_run is None:
                    print("Open Import analysis to choose your saved run. Stop with Close workspace or Ctrl+C.", flush=True)
                else:
                    print("Your analysis is loaded. Stop with Close workspace or Ctrl+C.", flush=True)
                if startup_notice:
                    print(startup_notice, flush=True)
                if not args.no_browser:
                    webbrowser.open(server.origin)
                try:
                    server.serve_forever(poll_interval=0.2)
                except KeyboardInterrupt:
                    pass
            finally:
                server.server_close()
        finally:
            with_workspace.close()
        return 0
    except (ProjectError, StorageError) as exc:
        print(f"Workspace: {exc}")
        return 1
    except OSError:
        print(f"Could not open the workspace. Check folder access; port {args.port} may already be in use.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
