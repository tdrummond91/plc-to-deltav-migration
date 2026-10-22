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
import hashlib
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


def _refreshed_report_policy(data: bytes) -> str:
    """Use the trusted renderer's hashed policy, never imported HTML policy."""
    match = re.search(rb'<meta http-equiv="Content-Security-Policy" content="([^"]+)">', data[:4096])
    policy = match.group(1).decode('ascii') if match else ''
    digest = r"'sha256-[A-Za-z0-9+/]{43}='"
    if re.fullmatch(r"default-src 'none'; script-src " + digest + r"; style-src " + digest
            + r"; connect-src 'self'; img-src 'none'; font-src 'none'; object-src 'none'; "
              r"frame-src 'none'; base-uri 'none'; form-action 'none'", policy) is None:
        raise ProjectError('The refreshed report is missing its trusted display policy.')
    return ("sandbox allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox; "
            + policy + "; frame-ancestors 'none'")


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
        self._report_cache: tuple[Any, bytes] = (None, b'')
        self._calculation_cache: tuple[str | None | object, dict] = (_UNLOADED, {})
        self._connection_cache: tuple[str | None | object, Any] = (_UNLOADED, None)
        self._ladder_map_cache: tuple[Any, Any] = (_UNLOADED, None)
        self._map_qualification_cache: tuple[Any, Any] = (_UNLOADED, None)
        self._variable_cache: dict[str, Any] = {}
        self._translation_service: Any = None
        self._translation_run: str | None = None
        self._translation_catalog_cache: tuple[Any, dict] = (_UNLOADED, {})
        self._translation_history: tuple[Any, dict] = (_UNLOADED, {})
        self._classification_cache: tuple[Any, dict] = (_UNLOADED, {})
        self.startup_notice = ''

    def close(self) -> None:
        if self._translation_service is not None:
            self._translation_service.close()
        self.store.close()

    def _translator(self) -> Any:
        from .workspace_translation import TranslationService
        if self._translation_service is None:
            self._translation_service = TranslationService(self.project.with_suffix('.translations.sqlite'))
        return self._translation_service

    def annotation_catalog(self) -> dict:
        """Inventory prose from the saved XML once; never reparse translated XML."""
        from .translation_catalog import collect_annotations
        from .workspace_report import read_report_data
        self._load(self.store.state())
        if not self._run:
            raise ProjectError('Import a completed source analysis first.')
        if self._translation_catalog_cache[0] != self._run:
            # Advanced condition evidence is embedded in the inert saved report;
            # it has no separate sfc-conditions.json artifact. Validate it against
            # the captured inventory before accepting any comment spans.
            data = read_report_data(self.store.artifact('review.html'), self._inventory)
            catalog = collect_annotations(self.store.artifact('snapshot.L5X'), self._inventory,
                                          data['sfc'], data.get('sfc_conditions'))
            self._translation_catalog_cache = (self._run, catalog)
        return self._translation_catalog_cache[1]

    def _translation_texts(self) -> list[str]:
        return [entry['original'] for entry in self.annotation_catalog()['entries']]

    def translation(self, source_id: str = '', run_id: str | None = None) -> dict:
        """Read local derived wording without writing source or review revisions."""
        service = self._translator()
        state = self.store.state()
        self._load(state)
        active = self._run
        status = service.status()
        if (status['enabled'] and status['available'] and active
                and active != self._translation_run and status['state'] != 'running'):
            status = service.start(self._translation_texts())
            self._translation_run = active
        result = dict(status, run_id=active, fields={})
        if self._translation_catalog_cache[0] == active:
            catalog = self._translation_catalog_cache[1]
            result['catalog_coverage'] = catalog['coverage']
            result['limitations'] = catalog['limitations']
        if source_id:
            # Polling prose must not reload historical analysis/calculation maps.
            sources = self._sources
            if run_id and run_id != active:
                if self._translation_history[0] != run_id:
                    inventory = self.store.inventory(run_id)
                    rows = inventory.get('entities', []) + inventory.get('rungs', [])
                    rows.extend(instruction for rung in inventory.get('rungs', [])
                                for instruction in rung.get('instructions', []))
                    self._translation_history = (run_id, {row['id']: row for row in rows})
                sources = self._translation_history[1]
            if source_id not in sources:
                raise ProjectError('This source record is not present in the selected analysis.')
            source = sources[source_id]
            fields = {key: source[key] for key in ('comment', 'description')
                      if isinstance(source.get(key), str) and source[key].strip()}
            entries = service.lookup_many(fields.values())
            result['fields'] = {key: entries.get(value) for key, value in fields.items()}
        return result

    def configure_translation(self, payload: dict) -> dict:
        modern = 'presentation_mode' in payload
        if (type(payload.get('retry', False)) is not bool
                or (modern and (payload['presentation_mode'] not in ('original', 'english', 'both')
                                or type(payload.get('prepare', False)) is not bool))
                or (not modern and type(payload.get('enabled')) is not bool)):
            raise ProjectError('Choose whether English translations are enabled.')
        state = self.store.state()
        if payload.get('run_id') != state.get('active_run'):
            raise RevisionConflict('The selected source changed. Reload before starting translations.')
        service = self._translator()
        if modern:
            if payload.get('prepare'):
                service.set_enabled(True)
                self._translation_run = None
            service.set_mode(payload['presentation_mode'])
        else:
            service.set_enabled(payload['enabled'])
            self._translation_run = None
        if ((modern and payload.get('prepare')) or payload.get('retry')) and service.status()['enabled']:
            self._load(state)
            if service.status()['state'] != 'running' and self._run:
                service.start(self._translation_texts(), retry=payload.get('retry', False))
                self._translation_run = self._run
        return self.translation()

    def _wording(self, records: list[dict], field: str) -> tuple[str, dict]:
        service = self._translator()
        mode = service.status()['presentation_mode']
        return mode, service.lookup_many(row[field] for row in records
                                        if isinstance(row.get(field), str) and row[field].strip())

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

    def _routine_descriptor(self, routine: dict, count: int) -> dict:
        """Program or AOI scope metadata without loading any rung diagrams."""
        current = routine.get('parent_id')
        visited: set[str] = set()
        program = scope = None
        while current in self._sources and current not in visited:
            visited.add(current)
            source = self._sources[current]
            if scope is None and source.get('kind') in {'program', 'aoi'}:
                scope = source
            if source.get('kind') == 'program':
                program = source
                break
            current = source.get('parent_id')
        return {'id': routine['id'], 'source_id': routine['id'],
                'name': routine.get('name') or 'Unnamed', 'path': self.path(routine['id']),
                'count': count, 'type': routine.get('attributes', {}).get('Type', ''),
                'program_id': program['id'] if program else '',
                'program_name': (program.get('name') or 'Unnamed') if program else '',
                'program_path': self.path(program['id']) if program else '',
                'scope_id': scope['id'] if scope else '',
                'scope_name': (scope.get('name') or 'Unnamed') if scope else '',
                'scope_path': self.path(scope['id']) if scope else '',
                'scope_kind': scope.get('kind', '') if scope else ''}

    def state(self) -> dict:
        from .workspace_classification import CATEGORY_DEFINITIONS
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
            self._routine_descriptor(row, routine_counts[row['id']])
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
        current_proposals = ({row['id']: row for row in self._classification_cache[1].get('groups', [])}
                             if self._classification_cache[0] == state['active_run'] else {})
        for group in state.get('groups', []):
            proposed = current_proposals.get(group.get('proposal_id'))
            if (group.get('proposal_id') and self._classification_cache[0] == state['active_run']
                    and (not proposed or group.get('proposal_signature') != self._classification_signature(proposed))):
                group['needs_revalidation'] = True
                group['revalidation_reasons'] = sorted(set(group.get('revalidation_reasons', [])
                                                           + ['classification_evidence_changed']))
            group['members'] = [{'id': identifier, 'path': self.path(identifier) or self._historical_labels.get(identifier, 'Earlier source · ' + identifier),
                                 'kind': 'rung' if identifier in self._rung_for else self._sources.get(identifier, {}).get('kind', 'object')}
                                for identifier in group.get('member_ids', [])]
        state["project_path"] = str(self.project)
        state['startup_notice'] = self.startup_notice
        state['classification_categories'] = CATEGORY_DEFINITIONS
        return state

    def _classifications(self) -> dict:
        """Project saved evidence once per run; browsing never changes reviews."""
        from .workspace_classification import build_classification
        from .workspace_report import read_report_data
        self._load(self.store.state())
        if not self._run:
            raise ProjectError('Import a completed source analysis first.')
        if self._classification_cache[0] != self._run:
            report = read_report_data(self.store.artifact('review.html'), self._inventory)
            result = build_classification(self._inventory, self.store.analysis(), report,
                                          source=self.store.artifact('snapshot.L5X'))
            self._classification_cache = (self._run, result)
        return self._classification_cache[1]

    @staticmethod
    def _classification_signature(proposal: dict) -> str:
        # Covers advanced providers embedded only in review.html, which the
        # older project-wide JSON-artifact proposal digest does not include.
        return hashlib.sha256(json.dumps(proposal, sort_keys=True, ensure_ascii=False,
                                         allow_nan=False).encode('utf-8')).hexdigest()

    def mutate(self, command: dict, expected_revision: int, author: str = 'Reviewer') -> dict:
        if isinstance(command, dict) and command.get('op') == 'group' and command.get('id'):
            existing = next((group for group in self.store.state()['groups']
                             if group['id'] == command['id']), None)
            if existing and existing.get('proposal_id') and 'migration_status' in command:
                proposal = next((row for row in self._classifications()['groups']
                                 if row['id'] == existing['proposal_id']), None)
                if proposal is not None:
                    command = dict(command, proposal_signature=self._classification_signature(proposal))
        self.store.mutate(command, expected_revision, author=author)
        return self.state()

    def classification(self, query: dict) -> dict:
        from .project_store import MIGRATION_STATUSES
        state = self.state()
        definitions = state['classification_categories']
        if not state['active_run']:
            return dict(self._page([], query), pages=1, categories=definitions,
                        coverage={}, limitations=[], run_id=None)
        projection = self._classifications()
        category = query.get('category', '')
        migration = query.get('migration', '')
        if category and category not in {row['id'] for row in definitions}:
            raise ProjectError('Choose an available function classification.')
        if migration and migration not in MIGRATION_STATUSES | {'in_scope'}:
            raise ProjectError('Choose an available migration filter.')
        saved = {group['proposal_id']: group for group in state['groups'] if group.get('proposal_id')}
        search = query.get('query', '').casefold()
        rows = []
        for proposed in projection['groups']:
            adopted = saved.get(proposed['id'])
            limited_scope = bool(adopted and not set(proposed['member_ids']).issubset(adopted['member_ids']))
            functions = adopted.get('function_categories', proposed['category_ids']) if adopted and not limited_scope else proposed['category_ids']
            disposition = adopted.get('migration_status', 'unreviewed') if adopted else 'unreviewed'
            stale = bool(adopted and (adopted.get('needs_revalidation')
                         or adopted.get('proposal_signature') != self._classification_signature(proposed)))
            if stale or limited_scope:
                disposition = 'investigate'
            if category and category not in functions:
                continue
            if migration == 'in_scope' and disposition == 'exclude':
                continue
            if migration and migration != 'in_scope' and migration != disposition:
                continue
            name = adopted['name'] if adopted and not limited_scope else proposed['name']
            if search and search not in ' '.join([name, proposed.get('reason', ''),
                    self.path(proposed.get('anchor_id', '')), ' '.join(functions),
                    adopted.get('migration_note', '') if adopted else '',
                    json.dumps(proposed.get('parameters', []), ensure_ascii=False)]).casefold():
                continue
            rows.append(dict(proposed, name=name,
                             saved_group_id=adopted['id'] if adopted else None,
                             migration_scope_limited=limited_scope,
                             saved_member_count=len(adopted['member_ids']) if adopted else 0,
                             needs_revalidation=stale,
                             effective_category_ids=functions, effective_migration_status=disposition))
        result = self._page(rows, query)
        result.update(pages=max(1, (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE),
                      categories=definitions, coverage=projection['coverage'],
                      limitations=projection['limitations'], run_id=state['active_run'])
        # Human labels are resolved only for the visible page; canonical IDs stay
        # available for opening every member without flattening its source.
        for row in result['items']:
            row['members'] = [{'id': member, 'label': self.path(member)} for member in row['member_ids']]
            row['source_labels'] = {member['id']: member['label'] for member in row['members']}
        return result

    def adopt_classification(self, payload: dict) -> dict:
        state = self.state()
        if payload.get('run_id') != state['active_run'] or payload.get('expected_revision') != state['revision']:
            raise RevisionConflict('The project or analysis changed. Refresh the classification before saving it.')
        if type(payload.get('expected_revision')) is not int:
            raise ProjectError('A current project revision is required.')
        identifier = payload.get('proposal_id')
        if not isinstance(identifier, str):
            raise ProjectError('Choose a source classification to edit.')
        proposal = next((row for row in self._classifications()['groups'] if row['id'] == identifier), None)
        if proposal is None:
            raise ProjectError('This source classification is not present in the active analysis.')
        existing = next((group for group in state['groups'] if group.get('proposal_id') == identifier), None)
        if existing is None:
            self.store.mutate({'op': 'group', 'name': proposal['name'][:160],
                               'member_ids': proposal['member_ids'], 'function_categories': proposal['category_ids'],
                               'migration_status': 'unreviewed', 'proposal_id': identifier,
                               'proposal_signature': self._classification_signature(proposal)},
                              state['revision'], author=payload.get('author', 'Reviewer'))
            state = self.state()
            existing = next(group for group in state['groups'] if group.get('proposal_id') == identifier)
        state['selected_group_id'] = existing['id']
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
        from .workspace_map import family_filter
        state = self.state()
        family = family_filter(query)
        # Share the map's source qualification and saved block evidence. Review
        # categories remain independent: changing them cannot relabel a block.
        metadata = self._ladder_map({})[0] if self._run else None
        mode, wording = self._wording(self._rungs, 'comment')
        reviews = state.get("reviews", {})
        memberships: dict[str, list[str]] = defaultdict(list)
        for group in state.get("groups", []):
            for identifier in group.get("member_ids", []):
                memberships[identifier].append(group["id"])
        rows = []
        search = query.get("query", "").casefold()
        for rung in self._rungs:
            identifier = rung["id"]
            source_family = metadata.rows_by_id[identifier] if metadata is not None else {}
            if family and family not in source_family.get('families', []):
                continue
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
                                                  wording.get(rung.get('comment'), {}).get('text', ''),
                                                  " ".join(proposals), " ".join(review.get("fields", {}).values())]).casefold():
                continue
            rows.append({"id": identifier, "number": rung.get("number"), "path": path,
                         "text": rung.get("text"), "comment": rung.get("comment"),
                         "parse_status": rung.get("parse_status"), "proposals": proposals,
                         "review": review, "groups": memberships[identifier],
                         "families": source_family.get('families', []),
                         "source_qualified": source_family.get('source_qualified', False),
                         "rule_proposals": self.rule_proposals(identifier, state)})
        result = self._page(rows, query)
        result['presentation_mode'] = mode
        result['families'] = metadata.family_choices() if metadata is not None else []
        for row in result['items']:
            row['wording'] = {'comment': wording.get(row.get('comment'))}
            source = self._sources[row['id']]
            instructions = source.get('instructions', [])
            preview = instructions[:2]
            pending = [source.get('structure')]
            branches = 0
            while pending:
                current = pending.pop()
                if isinstance(current, dict):
                    branches += current.get('kind') == 'branch'
                    pending.extend(current.get('items', current.get('legs', [])))
            row['preview'] = {
                'instructions': preview, 'instruction_count': len(instructions),
                'branch_count': branches,
                'calculations': self._calculation_detail([item['id'] for item in preview]),
            }
        return result

    def routine_ladder(self, query: dict) -> dict:
        """Page full saved source for one routine; never rerun analysis or reports.

        Qualification controls diagram eligibility, not source visibility. Even
        unsupported containers keep every captured rung and its original text.
        """
        state = self.store.state()
        self._load(state)
        identifier, selected = query.get('routine', ''), query.get('run_id', '')
        if (any(type(value) is not str or len(value) > 256 for value in (identifier, selected))
                or not identifier):
            raise ProjectError('Choose a captured routine from the selected analysis.')
        if selected and selected != self._run:
            raise RevisionConflict('The source analysis changed. Reload Programs & routines.')
        if not self._run:
            raise ProjectError('Import a completed analysis to browse its programs and routines.')
        routine = self._sources.get(identifier)
        if routine is None or routine.get('kind') != 'routine':
            raise ProjectError('Choose a captured routine from the selected analysis.')
        requested_page = query.get('page', '1')
        if type(requested_page) not in {int, str}:
            raise ProjectError('Choose a valid routine page.')
        try:
            page = int(requested_page)
        except (ValueError, TypeError):
            raise ProjectError('Choose a valid routine page.') from None
        if not 1 <= page <= 1_000_000:
            raise ProjectError('Choose a valid routine page.')

        rungs = [row for row in self._rungs if row.get('parent_id') == identifier]
        page_size = 20
        pages = max(1, (len(rungs) + page_size - 1) // page_size)
        page = min(page, pages)
        visible = rungs[(page - 1) * page_size:page * page_size]
        mode, wording = self._wording(visible, 'comment')
        entities_ok, rungs_ok, _ = self._map_qualification()
        descriptor = self._routine_descriptor(routine, len(rungs))
        descriptor['source_qualified'] = entities_ok.get(identifier, False)
        available = descriptor['source_qualified'] and descriptor['type'] == 'RLL'
        if not descriptor['source_qualified']:
            notice = ('This routine has unsupported source qualification. Captured rungs remain available '
                      'as original text; a qualified ladder diagram cannot be established.')
        elif descriptor['type'] != 'RLL':
            notice = (f"This routine is exported as {descriptor['type'] or 'an unspecified routine type'}, "
                      'rather than RLL ladder logic. Open its source record for context. '
                      'Any captured rungs remain available as original text.')
        elif not rungs:
            notice = ('This RLL routine has no captured ladder rungs. This does not establish that '
                      'protected or omitted source logic is empty. Open its source record for context.')
        else:
            notice = ('Rungs follow their captured export order. Diagrams show source structure, '
                      'not live Boolean values or controller execution timing.')
        items = [dict(row, path=self.path(row['id']),
                      source_qualified=bool(available and rungs_ok.get(row['id'], False)),
                      wording={'comment': wording.get(row.get('comment'))}) for row in visible]
        return {'routine': descriptor, 'items': items, 'total': len(rungs),
                'captured_rung_count': len(rungs), 'page': page, 'pages': pages, 'page_size': page_size,
                'run_id': self._run, 'revision': state['revision'], 'presentation_mode': mode,
                'available': available, 'notice': notice}

    def _connection_index(self) -> Any:
        """One authenticated saved-evidence index shared by map and rung views."""
        from .workspace_connections import ConnectionIndex, ConnectionError as EvidenceError, MAX_ARTIFACT_BYTES
        if not self._run:
            return None
        if self._connection_cache[0] != self._run:
            def unique_object(pairs: list[tuple[str, Any]]) -> dict:
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError('Repeated evidence field.')
                    result[key] = value
                return result

            def companion(name: str) -> dict:
                raw = self.store.artifact(name, self._run)
                if len(raw) > MAX_ARTIFACT_BYTES:
                    raise ValueError('Connection evidence exceeds its limit.')
                return json.loads(raw, object_pairs_hook=unique_object)

            try:
                artifacts = [companion(name) for name in (
                    'references.json', 'access.json', 'relationships.json')]
                try:
                    calculations = companion('calculations.json')
                except ProjectError:
                    calculations = None  # Older access schemas can expose explicit operands only.
                index = ConnectionIndex(self._inventory, *artifacts, calculations)
            except (ProjectError, EvidenceError, ValueError, TypeError, KeyError, RecursionError, OverflowError):
                index = None
            self._connection_cache = (self._run, index)
        return self._connection_cache[1]

    @staticmethod
    def _connection_notice(index: Any) -> str:
        if index is None:
            return ('Connection evidence is missing or could not be verified in this saved run. '
                    'Original rungs remain available; this does not mean there are no connections.')
        from .workspace_connections import _NOTICE
        return _NOTICE

    def connections(self, query: dict) -> dict:
        """Return a paged, immutable neighborhood of exact source-address uses."""
        from .workspace_connections import ConnectionError as EvidenceError
        self.state()
        if not self._run:
            return {'available': False, 'notice': 'Import a completed analysis to explore connections.'}
        index = self._connection_index()
        if index is None:
            return {'available': False, 'notice': self._connection_notice(index)}
        try:
            page, endpoint_page = int(query.get('page', '1')), int(query.get('endpoint_page', '1'))
            identifier = query.get('id', '')
            rung_id = self._rung_for.get(identifier, identifier)
            return index.view(rung_id, scope=query.get('scope', 'all'),
                              signal_id=query.get('signal_id', ''), direction=query.get('direction', 'both'),
                              page=page, endpoint_page=endpoint_page)
        except (EvidenceError, ValueError, TypeError) as exc:
            raise ProjectError('Choose a captured rung and valid connection filters.') from exc

    def _map_qualification(self) -> tuple[dict, dict, Any]:
        from .workspace_classification import _qualify_source
        if self._map_qualification_cache[0] != self._run:
            self._map_qualification_cache = (self._run, _qualify_source(
                self.store.artifact('snapshot.L5X', self._run), self._inventory))
        return self._map_qualification_cache[1]

    def variable(self, query: dict) -> dict:
        """Inspect one immutable run without switching the active workspace."""
        from .workspace_variables import (
            MAX_ARTIFACT_BYTES, VariableError, VariableIndex, unavailable, validate_query,
        )
        run_id, instruction_id, variable = (query.get(key) for key in ('run_id', 'instruction_id', 'variable'))
        try:
            validate_query(run_id, instruction_id, variable)
        except VariableError as exc:
            raise ProjectError(str(exc)) from None
        state = self.store.state()
        # Validate the requested run even when an unavailable index is cached.
        # Historical calls never mutate _run, loaded source lists, or selection.
        self.store._run(run_id)
        if run_id not in self._variable_cache:
            inventory = self.store.inventory(run_id)
            def companion(name: str, *, optional: bool = False) -> dict | None:
                try:
                    raw = self.store.artifact(name, run_id)
                except ProjectError:
                    if optional:
                        return None
                    raise
                if len(raw) > MAX_ARTIFACT_BYTES:
                    raise ValueError('Variable companion exceeds its limit.')
                def unique(pairs: list[tuple[str, Any]]) -> dict:
                    result = {}
                    for key, value in pairs:
                        if key in result:
                            raise ValueError('Repeated evidence field.')
                        result[key] = value
                    return result
                return json.loads(raw, object_pairs_hook=unique)
            try:
                index = VariableIndex(self.store.artifact('snapshot.L5X', run_id), inventory,
                    companion('references.json'), companion('access.json', optional=True),
                    companion('tag-data.json', optional=True), companion('calculations.json', optional=True))
            except (ProjectError, VariableError, ValueError, TypeError, KeyError, RecursionError, OverflowError):
                index = None
            # Two immutable indexes cover active and historical popup use without
            # retaining every imported project snapshot in memory.
            while len(self._variable_cache) >= 2:
                self._variable_cache.pop(next(iter(self._variable_cache)))
            self._variable_cache[run_id] = index
        index = self._variable_cache[run_id]
        try:
            result = (index.view(instruction_id, variable) if index is not None else
                      unavailable('Saved variable evidence is missing or could not be verified. Original source remains available.'))
        except VariableError as exc:
            raise ProjectError(str(exc)) from None
        return {**result, 'run_id': run_id, 'instruction_id': instruction_id, 'variable': variable,
                'historical': run_id != state.get('active_run')}

    def _map_connection_index(self) -> Any:
        index = self._connection_index()
        if index is not None:
            entities, rungs, _ = self._map_qualification()
            index.qualify_map(entities, rungs)
        return index

    def _ladder_map(self, query: dict) -> tuple[Any, dict]:
        from .workspace_map import LadderMapIndex, query_text
        state = self.store.state()
        self._load(state)
        selected = query_text(query, 'run_id')
        if selected and selected != self._run:
            raise RevisionConflict('The source analysis changed. Reload the ladder map.')
        if not self._run:
            raise ProjectError('Import a completed analysis to explore the ladder map.')
        if self._ladder_map_cache[0] != self._run:
            _, rungs, _ = self._map_qualification()
            self._ladder_map_cache = (self._run, LadderMapIndex(
                self._inventory, self.store.analysis(self._run), rung_ok=rungs))
        return self._ladder_map_cache[1], state

    def ladder_map(self, query: dict) -> dict:
        from .workspace_connections import ConnectionError as EvidenceError
        from .workspace_map import query_text
        metadata, state = self._ladder_map(query)
        index = self._map_connection_index()
        selected_signal = query_text(query, 'signal_id')
        signal_rungs = None
        if selected_signal:
            if index is None:
                raise ProjectError('Connections are unavailable; clear the signal filter to browse all source rungs.')
            try:
                signal_rungs = index.signal_rungs(selected_signal)
            except EvidenceError as exc:
                raise ProjectError(str(exc)) from exc
        return dict(metadata.view(query, signal_rungs=signal_rungs), run_id=self._run,
                    revision=state['revision'], connection_available=index is not None,
                    connection_notice=index.map_notice() if index is not None else self._connection_notice(index))

    def ladder_map_links(self, query: dict) -> dict:
        from .workspace_connections import ConnectionError as EvidenceError
        from .workspace_map import MAX_ID, page_number, query_text
        metadata, state = self._ladder_map(query)
        selection = query_text(query, 'ids', 80 * (MAX_ID + 1))
        identifiers = selection.split(',') if selection else []
        direction = query_text(query, 'direction', 16) or 'both'
        page = page_number(query)
        if (len(identifiers) > 80 or len(set(identifiers)) != len(identifiers)
                or any(len(identifier) > MAX_ID or identifier not in metadata.rungs for identifier in identifiers)
                or direction not in {'both', 'inputs', 'outputs'}):
            raise ProjectError('Choose at most 80 captured rungs and a valid connection direction.')
        index = self._map_connection_index()
        if index is None:
            return {'available': False, 'notice': self._connection_notice(index), 'signals': [],
                    'total': 0, 'page': 1, 'pages': 1, 'page_size': 80, 'omitted_signals': 0,
                    'run_id': self._run, 'revision': state['revision']}
        try:
            result = index.map_links(identifiers, direction=direction, page=page)
        except EvidenceError as exc:
            raise ProjectError(str(exc)) from exc
        return dict(result, run_id=self._run, revision=state['revision'])

    def ladder_map_detail(self, query: dict) -> dict:
        from .workspace_map import query_text
        metadata, state = self._ladder_map(query)
        identifier = query_text(query, 'id')
        if identifier not in metadata.sources:
            raise ProjectError('Choose a captured source item from the selected analysis.')
        entities, rungs, _ = self._map_qualification()
        return dict(metadata.detail(identifier, entity_ok=entities, rung_ok=rungs),
                    run_id=self._run, revision=state['revision'])

    def objects(self, query: dict) -> dict:
        self.state()
        mode, wording = self._wording(self._objects, 'description')
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
            code = source.get('kind') == 'instruction'
            entry = None if code else wording.get(source.get('description'))
            if search and search not in (path + " " + (source.get("description") or "")
                                        + ' ' + (entry or {}).get('text', '')).casefold():
                continue
            items.append({"id": source["id"], "kind": source.get("kind"), "name": source.get("name"),
                          "path": path, "description": source.get("description"),
                          'description_is_code': code, 'wording': {'description': entry}})
        return dict(self._page(items, query), presentation_mode=mode)

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
        source_qualified = False
        if kind in {"rung", "instruction"}:
            _, qualified_rungs, _ = self._map_qualification()
            source_qualified = qualified_rungs.get(rung_id or identifier, False)
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
                "source_qualified": source_qualified,
                "proposals": self._proposals.get(rung_id or identifier, []),
                "review": state.get("reviews", {}).get(identifier, {}), "operands": operands,
                "calculations": self._calculation_detail(instruction_ids if rung_id else []),
                "rule_proposals": self.rule_proposals(rung_id or identifier, state),
                "related": list({row["id"]: row for row in related}.values()),
                "group_ids": [g["id"] for g in state.get("groups", []) if identifier in g.get("member_ids", [])]}

    def _calculation_detail(self, instruction_ids: list[str]) -> dict:
        """Expose saved expression syntax only after matching its captured source.

        Validation reuses the existing bounded CPT grammar for the selected
        instructions. It never evaluates expressions, rebinds addresses, reruns
        L5X analysis, or writes project records. Optional old/corrupt evidence
        cannot prevent reviewing the original source.
        """
        from .calculations import (
            CALCULATION_CONSTANTS, CALCULATION_V1_CONSTANTS, ERROR_CODES,
            FUNCTIONS, FUNCTIONS_V1, MAX_CALCULATION_BYTES, CalculationResult,
            _Parser, _Unsupported, render_calculation_json,
        )
        from .project_store import _decode
        from .tag_data import _strict_match

        empty = {"status": "absent", "occurrences": [], "nodes": []}
        unavailable = {"status": "unavailable", "occurrences": [], "nodes": [],
                       "message": "Saved calculation evidence could not be verified. Original source remains available."}
        if not instruction_ids:
            return empty
        if self._calculation_cache[0] != self._run:
            try:
                data = self.store.artifact("calculations.json", self._run)
            except ProjectError:
                self._calculation_cache = (self._run, empty)
            else:
                try:
                    if len(data) > MAX_CALCULATION_BYTES:
                        raise ValueError
                    payload = _decode(data)
                    result = CalculationResult(**payload)
                    # Reuse the publisher's container, depth and size limits.
                    render_calculation_json(result)
                    constants = CALCULATION_V1_CONSTANTS if result.schema_version == 1 else CALCULATION_CONSTANTS
                    if (type(result.schema_version) is not int or result.schema_version not in {1, 2}
                            or any(payload.get(key) != value for key, value in constants.items())
                            or not _strict_match(self._inventory.get("snapshot"), result.snapshot)
                            or result.status not in {"partial", "complete"}
                            or not isinstance(result.occurrences, list) or not isinstance(result.nodes, list)):
                        raise ValueError
                    occurrences, nodes = {}, defaultdict(list)
                    for row in result.occurrences:
                        if (not isinstance(row, dict) or not isinstance(row.get("id"), str)
                                or row["id"] in occurrences or row["id"] not in self._rung_for
                                or self._sources[row["id"]].get("opcode", "").upper() != "CPT"
                                or row.get("rung_id") != self._rung_for[row["id"]]):
                            raise ValueError
                        occurrences[row["id"]] = row
                    seen = set()
                    for node in result.nodes:
                        if (not isinstance(node, dict) or not isinstance(node.get("id"), str)
                                or node["id"] in seen or not isinstance(node.get("instruction_id"), str)
                                or node["instruction_id"] not in occurrences):
                            raise ValueError
                        seen.add(node["id"])
                        nodes[node["instruction_id"]].append(node)
                    self._calculation_cache = (self._run, {
                        "status": "available", "occurrences": occurrences, "nodes": nodes,
                        "schema_version": result.schema_version,
                    })
                except (ProjectError, TypeError, ValueError, KeyError, RecursionError, OverflowError):
                    self._calculation_cache = (self._run, unavailable)
        evidence = self._calculation_cache[1]
        if evidence["status"] != "available":
            return dict(evidence)
        occurrences, nodes = [], []
        try:
            for identifier in instruction_ids:
                if self._sources[identifier].get("opcode", "").upper() != "CPT":
                    continue
                row = evidence["occurrences"].get(identifier)
                if row is None:
                    raise ValueError
                expected_keys = {"id", "rung_id", "destination_operand_id", "expression_operand_id",
                                 "signature_status", "syntax_status", "error_code", "error_offset",
                                 "root_node_id", "node_ids"}
                if row.keys() != expected_keys:
                    raise ValueError
                arguments = self._sources[identifier]["arguments"]
                signature = ("argument_count_mismatch" if len(arguments) != 2 else
                             "empty_argument" if any(not arg.strip() for arg in arguments) else "recognized")
                operand_ids = {operand["argument_index"]: operand["id"] for operand in self._operands[identifier]}
                if (row["signature_status"] != signature
                        or row["destination_operand_id"] != operand_ids.get(0)
                        or row["expression_operand_id"] != operand_ids.get(1)):
                    raise ValueError
                saved_nodes = evidence["nodes"].get(identifier, [])
                if signature != "recognized":
                    if (row["syntax_status"] != "signature_unresolved" or row["error_code"] is not None
                            or row["error_offset"] is not None or row["root_node_id"] is not None
                            or row["node_ids"] != [] or saved_nodes):
                        raise ValueError
                elif row["syntax_status"] == "unsupported":
                    if (row["error_code"] not in ERROR_CODES or type(row["error_offset"]) is not int
                            or not 0 <= row["error_offset"] <= len(arguments[1])
                            or row["root_node_id"] is not None or row["node_ids"] != [] or saved_nodes):
                        raise ValueError
                elif row["syntax_status"] == "parsed":
                    functions = FUNCTIONS_V1 if evidence["schema_version"] == 1 else FUNCTIONS
                    parser = _Parser(arguments[1], identifier, str(self._inventory["snapshot"]["id"]), functions)
                    root = parser.parse()
                    syntax_nodes = [{key: value for key, value in node.items() if key != "binding"}
                                    for node in saved_nodes]
                    expected_nodes = [{key: value for key, value in node.items() if key != "binding"}
                                      for node in parser.nodes]
                    if (row["error_code"] is not None or row["error_offset"] is not None
                            or row["root_node_id"] != root
                            or row["node_ids"] != [node["id"] for node in parser.nodes]
                            or not _strict_match(expected_nodes, syntax_nodes)):
                        raise ValueError
                    nodes.extend(syntax_nodes)
                else:
                    raise ValueError
                occurrences.append(dict(row))
        except (TypeError, ValueError, KeyError, RecursionError, OverflowError, _Unsupported):
            return unavailable
        return {"status": "available", "occurrences": occurrences, "nodes": nodes}

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

    def report(self, language: str | None = None) -> bytes:
        from .workspace_report import refresh_report
        state = self.state()
        active = state.get('active_run')
        if not active:
            raise ProjectError('Import a completed source analysis first.')
        service = self._translator()
        status = service.status()
        mode = language or status['presentation_mode']
        if mode not in ('original', 'english', 'both'):
            raise ProjectError('Choose Original, English or Both for the analysis language.')
        signature = (active, mode, tuple(status['cache_signature']))
        if self._report_cache[0] != signature:
            # Keep local language switching usable even when the report opens
            # in Original mode. The overlay never replaces captured evidence.
            catalog = self.annotation_catalog()
            translations = service.lookup_many(entry['original'] for entry in catalog['entries'])
            rendered = refresh_report(self.store.artifact('review.html'), self._inventory,
                                      translations=translations, language=mode, catalog=catalog,
                                      run_id=self._run, rung_qualification=self._map_qualification()[1])
            self._report_cache = (signature, rendered)
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
        if self._translation_service is not None:
            self._translation_service.close()
        self._translation_service = None
        self._translation_run = None
        self._translation_catalog_cache = (_UNLOADED, {})
        self._translation_history = (_UNLOADED, {})
        self._classification_cache = (_UNLOADED, {})
        self.store, self.project = restored, destination
        self._run = _UNLOADED
        self._report_cache = (None, b'')
        self._calculation_cache = (_UNLOADED, {})
        self._connection_cache = (_UNLOADED, None)
        self._ladder_map_cache = (_UNLOADED, None)
        self._map_qualification_cache = (_UNLOADED, None)
        self._variable_cache = {}
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

    def _send(self, status: int, data: bytes, content_type: str, *, report: bool = False,
              trusted_report: bool = False) -> None:
        # Only /analysis supplies this flag after refresh_report has discarded
        # imported executable HTML and generated this installation's scripts.
        trusted_policy = _refreshed_report_policy(data) if trusted_report else None
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "SAMEORIGIN")
            if trusted_policy is not None:
                self.send_header('Content-Security-Policy', trusted_policy)
            elif report:
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
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, TimeoutError):
            # A closed browser/tab can abort either headers or body (including
            # Windows error 10053). There is no usable connection for a second
            # error response. Catch only transport failures here: storage errors
            # must still reach the route's controlled project-error response.
            self.close_connection = True

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
            elif url.path == '/api/routine-ladder':
                self._json(200, workspace.routine_ladder(query))
            elif url.path == "/api/connections":
                self._json(200, workspace.connections(query))
            elif url.path == '/api/variable':
                self._json(200, workspace.variable(query))
            elif url.path == '/api/ladder-map':
                self._json(200, workspace.ladder_map(query))
            elif url.path == '/api/ladder-map/links':
                self._json(200, workspace.ladder_map_links(query))
            elif url.path == '/api/ladder-map/detail':
                self._json(200, workspace.ladder_map_detail(query))
            elif url.path == "/api/objects":
                self._json(200, workspace.objects(query))
            elif url.path == '/api/classification':
                self._json(200, workspace.classification(query))
            elif url.path == "/api/source":
                self._json(200, workspace.source(query.get("id", ""), query.get("run_id")))
            elif url.path == "/api/translation":
                self._json(200, workspace.translation(query.get('source_id', ''), query.get('run_id')))
            elif url.path == "/api/runs":
                self._json(200, workspace.available_runs())
            elif url.path == "/api/backups":
                self._json(200, workspace.backups())
            elif url.path == "/api/rule-matches":
                self._json(200, workspace.rule_matches(query.get("source_id", "")))
            elif url.path == "/analysis":
                self._send(200, workspace.report(query.get('language')), "text/html; charset=utf-8",
                           report=True, trusted_report=True)
            elif url.path in ("/", "/index.html", "/workspace.js", "/workspace.css",
                              "/source-colors.js", "/source-colors.css",
                              "/instruction-help.html", "/instruction-help.js", "/instruction-help.css", "/instruction-help-content.js",
                              "/variable-help-content.js",
                              "/rung-flow.js", "/rung-flow.css", "/rung-explanation.js", "/rung-explanation.css",
                              "/routine-browser.js", "/routine-browser.css", "/ladder-diagram.js", "/ladder-diagram.css",
                              "/connections.js", "/connections.css",
                              "/reading-layout.js", "/reading-layout.css", "/translation.js", "/translation.css",
                              '/classification.js', '/classification.css', '/ladder-map.js', '/ladder-map.css'):
                name = "index.html" if url.path in ("/", "/index.html") else url.path[1:]
                data = (ASSETS / name).read_bytes()
                if name == "index.html":
                    data = data.replace(b"__WORKSPACE_TOKEN__", self.server.token.encode("ascii"))
                content_type = 'text/javascript' if name.endswith('.js') else 'text/css' if name.endswith('.css') else 'text/html'
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
            try:
                request_body = self.rfile.read(length)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, TimeoutError):
                self.close_connection = True
                return
            payload = json.loads(request_body)
            if not isinstance(payload, dict):
                raise ProjectError("Expected a workspace operation.")
            route = urlsplit(self.path).path
            if route == "/api/mutate":
                result = workspace.mutate(payload.get("command", {}), payload.get("expected_revision"),
                                          author=payload.get("author", "Reviewer"))
            elif route == "/api/import":
                result = workspace.import_run(payload.get("path", ""), payload.get("expected_revision"))
            elif route == '/api/translation':
                result = workspace.configure_translation(payload)
            elif route == '/api/classification/adopt':
                result = workspace.adopt_classification(payload)
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
                    print("Open Choose analysis run to select your saved run. Stop with Stop workspace or Ctrl+C.", flush=True)
                else:
                    print("Your analysis is loaded. Stop with Stop workspace or Ctrl+C.", flush=True)
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
