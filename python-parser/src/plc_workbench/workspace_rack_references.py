"""Recover qualified rack source paths without replaying the analysis pipeline.

The shared variable index has already authenticated inventory, references and
decorated data against the source. Reuse the rack-layout analyzer's bounded
source checks, then apply the same EN2T/Slot and alias rules as rack_backing_context.
These are source correspondences, not terminal wiring or runtime assertions.
"""
from __future__ import annotations

from collections import defaultdict
import json
import re

from .rack_backing_summary import _derive as _rack_shapes
from .references import _address, MAX_ADDRESS_LENGTH
from .source import snapshot_from_bytes
from .workspace_variables import VariableIndex

MAX_INDEX_BYTES = 8 * 1024 * 1024
_SUFFIX = re.compile(r'\.(Data|Fault)(?:\.([0-9]+))?', re.ASCII | re.IGNORECASE)


class RackReferenceError(ValueError):
    """Fixed source-free error for invalid or excessive recovery evidence."""

    def __init__(self, message: str, *, actual: int | None = None, limit: int | None = None) -> None:
        super().__init__(message)
        self.actual, self.limit = actual, limit


class RackReferenceIndex:
    """One immutable, cached-run rack projection; never accepts a saved overlay."""

    def __init__(self, base: VariableIndex) -> None:
        if type(base) is not VariableIndex:
            raise RackReferenceError('Choose authenticated variable evidence for rack references.')
        self.base = base
        self.roots: dict[str, dict] = {}
        self._names: dict[tuple[str | None, str], list[str]] = defaultdict(list)
        self._aliases: dict[tuple[str, str], bool] = {}
        self._budget = 0
        candidates = base._references.rack_candidates['candidates']
        if not candidates or base._data_evidence is None:
            return
        for candidate in candidates:
            if candidate['name']:
                key = candidate['scope_id'], candidate['name'].casefold()
                self._retain((key, candidate['source_id']))
                self._names[key].append(candidate['source_id'])
        elements = {row['id']: row for row in base._data_evidence.elements}
        children: dict[str, list[dict]] = defaultdict(list)
        for row in elements.values():
            children[row['parent_id']].append(row)

        def root(candidate: dict, disposition: str, family: str, metadata: dict) -> None:
            if (disposition != 'slot_array_shape_observed_mapping_unchecked'
                    or family != 'rockwell_1756_en2t'
                    or metadata['header_consistency'] != 'series_direction_consistent'
                    or len(self._names[candidate['scope_id'], candidate['name'].casefold()]) != 1):
                return
            evidence = metadata['evidence']
            owner = base._entities[evidence['backing_tag_id']]
            binding = base._resolve(evidence['backing_name'], owner.scope_id)
            if (binding['status'] != 'root_bound' or binding['target_id'] != owner.id
                    or binding['symbol_id'] != owner.id or binding['alias_chain'] or binding['suffix']
                    or not base._entity_ok.get(owner.id)):
                return
            structure = children[evidence['selected_element']['id']][0]
            fields = {field['attributes'].get('Name', '').casefold(): field
                      for field in children[structure['id']]}
            value = {'candidate_id': candidate['source_id'], 'module_id': candidate['module_id'],
                'logical_root': candidate['name'], 'direction': candidate['direction'],
                'backing_tag_id': owner.id, 'backing_name': evidence['backing_name'],
                'backing_prefix': f".{elements[evidence['array_element_id']]['attributes']['Name']}[{evidence['slot']}]",
                'datatype': structure['attributes']['DataType'],
                'data_member_id': fields['data']['id'],
                'fault_member_id': fields['fault']['id'] if candidate['direction'] == 'input' else None}
            self._retain(value)
            self.roots[candidate['source_id']] = value

        # _rack_shapes checks topology, protected/foreign source, duplicate
        # representations, slot bounds and all required native DINT fields.
        _rack_shapes(snapshot_from_bytes(base._source), base._captured,
                     base._references, base._data_evidence, schema_version=2, evidence_sink=root)

    def _retain(self, value: object) -> None:
        self._budget += len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
        if self._budget > MAX_INDEX_BYTES:
            raise RackReferenceError('Rack reference evidence exceeds its retained-data limit.',
                                     actual=self._budget, limit=MAX_INDEX_BYTES)

    def _candidate(self, binding: dict, raw: str, scope_id: str | None) -> str | None:
        if binding.get('status') != 'unresolved' or binding.get('reason') != 'colon_root_not_declared':
            return None
        if binding['alias_chain']:
            alias = self.base._entities[binding['alias_chain'][-1]]
            raw, scope_id = alias.attributes.get('AliasFor', ''), alias.scope_id
        parsed, _ = _address(raw)
        if parsed is None:
            return None
        scope = self.base._entities.get(scope_id)
        visible = [scope_id]
        if scope is not None and scope.kind == 'program':
            visible.append(scope.scope_id)
        candidates = [identifier for visible_scope in visible
                      for identifier in self._names.get((visible_scope, parsed[0].casefold()), ())]
        return candidates[0] if len(candidates) == 1 and candidates[0] in self.roots else None

    def _datatype(self, root: dict, suffix: str) -> str | None:
        if len(root['backing_name']) + len(root['backing_prefix']) + len(suffix) > MAX_ADDRESS_LENGTH:
            return None
        if not suffix:
            return root['datatype']
        match = _SUFFIX.fullmatch(suffix)
        if match is None or match[1].casefold() == 'fault' and root['fault_member_id'] is None:
            return None
        bit = match[2]
        if bit is not None:
            if len(bit.lstrip('0')) > 2 or int(bit.lstrip('0') or '0') > 31:
                return None
            return 'BOOL'
        return 'DINT'

    def resolve(self, binding: dict, raw: str, scope_id: str | None) -> dict | None:
        candidate_id = self._candidate(binding, raw, scope_id)
        if candidate_id is None:
            return None
        root = self.roots[candidate_id]
        datatype = self._datatype(root, binding['suffix'])
        if datatype is None:
            return None
        for alias_id in binding['alias_chain']:
            key = alias_id, candidate_id
            if key not in self._aliases:
                alias = self.base._entities[alias_id]
                okay = bool(self.base._entity_ok.get(alias_id)) and alias.attributes.get('Dimensions', '0') == '0'
                if okay and alias.attributes.get('DataType') is not None:
                    own = self.base._resolve(alias.name or '', alias.scope_id)
                    okay = (self._candidate(own, alias.name or '', alias.scope_id) == candidate_id
                            and self._datatype(root, own['suffix']) == alias.attributes['DataType'])
                self._retain((key, okay))
                self._aliases[key] = okay
            if not self._aliases[key]:
                return None
        suffix = root['backing_prefix'] + binding['suffix']
        return {'target_id': root['backing_tag_id'], 'suffix': suffix, 'datatype': datatype,
                'rack_mapping': {'basis': 'qualified_rack_slot_source_correspondence',
                    'candidate_id': candidate_id, 'module_id': root['module_id'],
                    'logical_address': root['logical_root'] + binding['suffix'],
                    'logical_suffix': binding['suffix'], 'backing_tag_id': root['backing_tag_id'],
                    'backing_suffix': suffix}}

    def binding(self, raw: str, scope_id: str | None) -> dict:
        """Return a detached source binding overlay for qualified consumers.

        Alias metadata is checked by resolve before replacing the unresolved
        target; its original alias chain/symbol remain available for source
        qualification. Historical reference/access records are never changed.
        """
        original = self.base._resolve(raw, scope_id)
        recovered = self.resolve(original, raw, scope_id)
        if recovered is None:
            return original
        return dict(original, status='root_bound', reason=None,
                    symbol_id=original['symbol_id'] or recovered['target_id'],
                    target_id=recovered['target_id'], suffix=recovered['suffix'],
                    basis='qualified_rack_slot_source_correspondence')
