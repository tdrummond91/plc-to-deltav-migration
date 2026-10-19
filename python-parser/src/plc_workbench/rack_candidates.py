"""Private, bounded rack-root candidates that never change reference bindings.

An individual rack alias can suggest a Location:Slot:I/O root when its checked
module topology supports that name. This is separate from an ordinary symbol:
the adapter backing tag, member mapping, data type and runtime effects remain
unverified. Missing-root comparisons are observations, not resolved references.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from .models import InventoryResult
from . import module_io


RACK_NAME_ORIGINS = ('backplane_slot', 'unavailable')
RACK_NAME_REASONS = module_io.NAME_REASONS + (
    'unsupported_rack_attributes', 'unsupported_rack_port_type', 'unsupported_rack_content',
)
RACK_MATCH_STATUSES = (
    'unique_candidate', 'ambiguous_candidate', 'candidate_names_unavailable',
    'outside_visible_scope', 'no_candidate_match',
)
MAX_EXPANDED_EVIDENCE_CHARS = 8_000_000
_DIRECTIONS = {
    'module_rack_input_alias': ('input', 'I'),
    'module_rack_output_alias': ('output', 'O'),
}


class RackCandidateError(ValueError):
    """A fixed failure that never embeds private source evidence."""


def build_rack_candidates(
    inventory: InventoryResult,
    aliases: list[dict[str, Any]],
    operands: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare canonical unresolved roots with separate rack-name candidates.

    Call after ordinary reference analysis, with its canonical record lists.
    No input is changed and this function does no file or network IO. Aliases
    and direct/alias-mediated operands remain distinct occurrence populations.
    ``candidate_count`` counts exact matching candidates for named statuses,
    visible unnamed candidates for the uncertainty status, and zero otherwise.
    """
    # Local import avoids a cycle when references builds these diagnostics.
    from .references import _address

    entities, _, _, location = module_io._module_naming_context(inventory)
    unsupported_content = {finding.source_id for finding in inventory.diagnostics
                           if finding.code == 'module_rack_content_not_analyzed'}
    candidates: list[dict[str, Any]] = []
    expanded_characters = 0

    def reserve(length: int) -> None:
        nonlocal expanded_characters
        expanded_characters += length
        if expanded_characters > MAX_EXPANDED_EVIDENCE_CHARS:
            raise RackCandidateError('Rack candidate analysis exceeds the expanded-evidence limit.')

    for alias in inventory.entities:
        if alias.kind not in _DIRECTIONS:
            continue
        direction, suffix = _DIRECTIONS[alias.kind]
        connection = entities.get(alias.parent_id or '')
        module = (entities.get(connection.parent_id or '')
                  if connection is not None and connection.kind == 'module_rack_connection' else None)
        name = None
        origin = 'unavailable'
        if connection is None or connection.kind != 'module_rack_connection':
            reason = 'missing_connection_context'
        elif module is None or module.kind != 'module' or alias.scope_id != module.scope_id:
            reason = 'missing_module_context'
        elif connection.scope_id != module.scope_id:
            reason = 'missing_connection_context'
        elif alias.attributes or connection.attributes:
            # No explicit-name/target/suffix interpretation in this slice.
            reason = 'unsupported_rack_attributes'
        elif alias.id in unsupported_content or connection.id in unsupported_content:
            reason = 'unsupported_rack_content'
        else:
            prefix, derived_origin, reason = location(module.id)
            if reason is None and derived_origin != 'backplane_slot':
                reason = 'unsupported_rack_port_type'
            if reason is None:
                assert prefix is not None
                length = len(prefix) + 1 + len(suffix)
                if length > module_io.MAX_IO_NAME_LENGTH:
                    reason = 'name_length_limit'
                else:
                    reserve(length)
                    name = f'{prefix}:{suffix}'
                    origin = 'backplane_slot'
        row = {
            'source_id': alias.id,
            'connection_id': connection.id if connection is not None and connection.kind == 'module_rack_connection' else None,
            'module_id': module.id if module is not None and module.kind == 'module' else None,
            'scope_id': alias.scope_id,
            'direction': direction,
            'name': name,
            'name_origin': origin,
            'reason': reason,
            'backing_status': 'not_analyzed',
        }
        # Name allocation is reserved above; account for retained source links
        # and fixed metadata as well, including repeated connection/scope IDs.
        reserve(sum(len(value) for key, value in row.items()
                    if key != 'name' and isinstance(value, str)))
        candidates.append(row)

    # Index once; do not retain per-occurrence candidate lists or search all
    # candidates for each caller of the same missing root.
    by_scope: dict[tuple[str | None, str], list[str]] = defaultdict(list)
    named_totals: dict[str, int] = defaultdict(int)
    unavailable: dict[str | None, int] = defaultdict(int)
    for candidate in candidates:
        if candidate['name'] is None:
            unavailable[candidate['scope_id']] += 1
        else:
            key = candidate['name'].lower()
            by_scope[candidate['scope_id'], key].append(candidate['source_id'])
            named_totals[key] += 1

    def visible_scopes(scope_id: str | None) -> tuple[str, ...]:
        scope = entities.get(scope_id or '')
        if scope is None or scope.kind not in {'program', 'controller', 'aoi'}:
            return ()
        if scope.kind == 'program':
            controller = entities.get(scope.scope_id or '')
            if controller is not None and controller.kind == 'controller':
                return scope.id, controller.id
        return (scope.id,)

    def terminal(record: dict[str, Any], *, is_alias: bool) -> tuple[str, str | None]:
        raw = record['raw_target'] if is_alias else record['raw_text']
        scope_id = record['scope_id']
        if record['alias_chain']:
            last = entities.get(record['alias_chain'][-1])
            if last is None:
                raise RackCandidateError('Rack candidate evidence is inconsistent.')
            raw = last.attributes.get('AliasFor', '')
            scope_id = last.scope_id
        parsed, _ = _address(raw)
        if parsed is None or ':' not in parsed[0]:
            raise RackCandidateError('Rack candidate evidence is inconsistent.')
        return parsed[0], scope_id

    matches: dict[str, list[dict[str, Any]]] = {
        'aliases': [], 'direct_operands': [], 'alias_operands': [],
    }
    for records, is_alias in ((aliases, True), (operands, False)):
        for record in records:
            if record['status'] != 'unresolved' or record['reason'] != 'colon_root_not_declared':
                continue
            root, scope_id = terminal(record, is_alias=is_alias)
            reserve(len(root))
            scopes = visible_scopes(scope_id)
            key = root.lower()
            count = sum(len(by_scope.get((scope, key), ())) for scope in scopes)
            candidate_id = None
            if count:
                status = 'unique_candidate' if count == 1 else 'ambiguous_candidate'
                if count == 1:
                    candidate_id = next(by_scope[scope, key][0] for scope in scopes
                                        if (scope, key) in by_scope)
            else:
                count = sum(unavailable.get(scope, 0) for scope in scopes)
                if count:
                    status = 'candidate_names_unavailable'
                else:
                    count = named_totals.get(key, 0)
                    status = 'outside_visible_scope' if count else 'no_candidate_match'
            group = ('aliases' if is_alias else
                     'alias_operands' if record['alias_chain'] else 'direct_operands')
            row = {
                'source_id': record['source_id'] if is_alias else record['id'],
                'terminal_root': root,
                'lookup_scope_id': scope_id,
                'status': status,
                'candidate_id': candidate_id,
                'candidate_count': count,
            }
            reserve(sum(len(value) for field, value in row.items()
                        if field != 'terminal_root' and isinstance(value, str)))
            matches[group].append(row)
    return {'candidates': candidates, 'matches': matches}
