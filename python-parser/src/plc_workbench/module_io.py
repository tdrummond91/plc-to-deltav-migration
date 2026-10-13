"""Conservative, private names inferred from module declaration topology.

The inventory remains raw evidence. These names are a separate interpretation of
the module/port and connection attributes described in 1756-RM014 chapter 4 and
the Location:Slot:Type address convention in 1756-RM094 chapter 10. Only ICP
backplanes and directly attached Ethernet modules are supported. This does not
validate members, channel types, values, rack-optimized mappings, or behavior.
"""
from __future__ import annotations

from collections import defaultdict
from functools import cache
import re

from .models import EntityRecord, InventoryResult

MODULE_IO_KINDS = ('module_input_tag', 'module_output_tag', 'module_config_tag')
NAME_ORIGINS = ('explicit_name', 'module_name', 'backplane_slot', 'unavailable')
NAME_REASONS = (
    'invalid_explicit_name', 'missing_module_context', 'ambiguous_module_context',
    'missing_connection_context', 'ambiguous_connection_context', 'invalid_suffix',
    'missing_upstream_port', 'ambiguous_upstream_port', 'invalid_upstream_port',
    'missing_parent_module', 'ambiguous_parent_module', 'missing_parent_port',
    'ambiguous_parent_port', 'port_type_mismatch', 'unsupported_port_type',
    'invalid_module_name', 'invalid_slot', 'topology_cycle', 'topology_depth_limit',
    'name_length_limit',
)
MAX_TOPOLOGY_DEPTH = 64
# Match the reference address limit without importing the resolver (a cycle).
MAX_IO_NAME_LENGTH = 65_536
MAX_EXPANDED_NAME_CHARS = 8_000_000
_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
_EXPLICIT_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*(?::[A-Za-z0-9_]+)+')
_DECIMAL = re.compile(r'0|[1-9][0-9]*')
_SUFFIX = {kind: letter for kind, letter in zip(MODULE_IO_KINDS, ('I', 'O', 'C'))}


def _unavailable(reason: str) -> dict[str, str | None]:
    return {'name': None, 'name_origin': 'unavailable', 'reason': reason}


class ModuleIOError(ValueError):
    """A fixed resource-limit error with no source text."""


def derive_module_io_names(inventory: InventoryResult) -> dict[str, dict[str, str | None]]:
    """Return one fixed-shape name/provenance row for every module I/O record.

    Explicit names need no topology guess. Derived names require a unique module
    and parent port in the same controller. Every ancestor link is checked, with
    a bounded walk and a special case for the documented self-parent Local root.
    Duplicate resulting tag names are deliberately retained for the reference
    resolver to mark ambiguous; no declaration wins because it occurred first.
    """
    entities = {entity.id: entity for entity in inventory.entities}
    by_module_name: dict[tuple[str | None, str], list[EntityRecord]] = defaultdict(list)
    ports: dict[str, list[EntityRecord]] = defaultdict(list)
    ports_by_id: dict[tuple[str, str | None], list[EntityRecord]] = defaultdict(list)
    connection_names: dict[tuple[str, str], int] = defaultdict(int)
    connection_ids: dict[tuple[str, str], int] = defaultdict(int)
    for entity in inventory.entities:
        if entity.kind == 'module' and entity.name:
            by_module_name[(entity.scope_id, entity.name.lower())].append(entity)
        elif entity.kind == 'module_port' and entity.parent_id is not None:
            ports[entity.parent_id].append(entity)
            ports_by_id[(entity.parent_id, entity.attributes.get('Id'))].append(entity)
        elif entity.kind == 'module_connection' and entity.parent_id is not None:
            if entity.name is not None:
                connection_names[(entity.parent_id, entity.name.lower())] += 1
            if 'Id' in entity.attributes:
                connection_ids[(entity.parent_id, entity.attributes['Id'])] += 1

    def valid_module(module: EntityRecord, controller_id: str | None) -> str | None:
        if (controller_id is None or module.scope_id != controller_id
                or entities.get(controller_id) is None
                or entities[controller_id].kind != 'controller'
                or module.parent_id != controller_id):
            return 'missing_module_context'
        if module.name and len(module.name) > MAX_IO_NAME_LENGTH:
            return 'name_length_limit'
        if (not module.name or not _NAME.fullmatch(module.name)
                or module.name.lower() == 'program'):
            return 'invalid_module_name'
        if len(by_module_name[(controller_id, module.name.lower())]) != 1:
            return 'ambiguous_module_context'
        return None

    @cache
    def parent_link(module_id: str, controller_id: str) -> tuple[
            EntityRecord | None, EntityRecord | None, str | None]:
        """Return the unique parent and child's upstream port, or fixed reason."""
        module = entities[module_id]
        parent_name = module.attributes.get('ParentModule')
        if parent_name is None and module.name and module.name.lower() == 'local':
            parent_name = module.name
        if not parent_name:
            return None, None, 'missing_parent_module'
        candidates = by_module_name.get((controller_id, parent_name.lower()), [])
        if not candidates:
            return None, None, 'missing_parent_module'
        if len(candidates) != 1:
            return None, None, 'ambiguous_parent_module'
        parent = candidates[0]
        reason = valid_module(parent, controller_id)
        if reason:
            return None, None, reason
        # Real exports use ParentModPortId. Also recognize the ID spelling in
        # the import/export manual, but conflicting spellings are not evidence.
        parent_ids = {module.attributes[key] for key in ('ParentModPortId', 'ParentModPortID')
                      if key in module.attributes}
        if len(parent_ids) != 1:
            return None, None, 'missing_parent_port' if not parent_ids else 'ambiguous_parent_port'
        parent_id = next(iter(parent_ids))
        if not _DECIMAL.fullmatch(parent_id):
            return None, None, 'missing_parent_port'
        selected = ports_by_id.get((parent.id, parent_id), [])
        if not selected:
            return None, None, 'missing_parent_port'
        if len(selected) != 1:
            return None, None, 'ambiguous_parent_port'
        parent_port = selected[0]
        if parent_port.scope_id != controller_id:
            return None, None, 'missing_parent_port'
        # The local controller's module is its own chassis anchor, not an edge
        # to traverse forever. Do not extend that exception to arbitrary names.
        if parent.id == module.id:
            if (module.name.lower() == 'local'
                    and parent_port.attributes.get('Type') == 'ICP'
                    and parent_port.attributes.get('Upstream') in {'false', '0'}):
                return parent, None, None
            return None, None, 'topology_cycle'
        module_ports = ports[module.id]
        if any(port.attributes.get('Upstream') not in {'true', 'false', '0', '1'}
               for port in module_ports):
            return None, None, 'invalid_upstream_port'
        upstream = [port for port in module_ports
                    if port.attributes.get('Upstream') in {'true', '1'}]
        if not upstream:
            return None, None, 'missing_upstream_port'
        if len(upstream) != 1:
            return None, None, 'ambiguous_upstream_port'
        port = upstream[0]
        port_id = port.attributes.get('Id', '')
        if (not _DECIMAL.fullmatch(port_id) or port.scope_id != controller_id
                or len(ports_by_id[(module.id, port_id)]) != 1):
            return None, None, 'invalid_upstream_port'
        if parent_port.attributes.get('Upstream') not in {'false', '0'}:
            return None, None, 'invalid_upstream_port'
        port_type = port.attributes.get('Type')
        if port_type != parent_port.attributes.get('Type'):
            return None, None, 'port_type_mismatch'
        if port_type not in {'ICP', 'Ethernet'}:
            return None, None, 'unsupported_port_type'
        if port_type == 'ICP' and not _DECIMAL.fullmatch(port.attributes.get('Address', '')):
            return None, None, 'invalid_slot'
        if port_type == 'Ethernet' and not port.attributes.get('Address'):
            return None, None, 'invalid_upstream_port'
        return parent, port, None

    @cache
    def location(module_id: str) -> tuple[str | None, str | None, str | None]:
        module = entities[module_id]
        controller_id = module.scope_id
        reason = valid_module(module, controller_id)
        if reason:
            return None, None, reason
        assert controller_id is not None
        seen: set[str] = set()
        current = module
        prefix = origin = None
        for _ in range(MAX_TOPOLOGY_DEPTH):
            if current.id in seen:
                return None, None, 'topology_cycle'
            seen.add(current.id)
            parent, port, reason = parent_link(current.id, controller_id)
            if reason:
                return None, None, reason
            assert parent is not None
            if parent.id == current.id:
                # A root ConfigTag can exist, but no child slot or direct
                # Ethernet edge supports inventing its tag name in this slice.
                if prefix is None:
                    return None, None, 'missing_upstream_port'
                return prefix, origin, None
            assert port is not None
            if current.id == module.id:
                if port.attributes['Type'] == 'ICP':
                    if len(parent.name) + 1 + len(port.attributes['Address']) > MAX_IO_NAME_LENGTH:
                        return None, None, 'name_length_limit'
                    prefix = f"{parent.name}:{port.attributes['Address']}"
                    origin = 'backplane_slot'
                else:
                    prefix = module.name
                    origin = 'module_name'
            current = parent
        return None, None, 'topology_depth_limit'

    rows: dict[str, dict[str, str | None]] = {}
    expanded_characters = 0

    def reserve_name(length: int) -> None:
        nonlocal expanded_characters
        expanded_characters += length
        if expanded_characters > MAX_EXPANDED_NAME_CHARS:
            raise ModuleIOError('Module I/O names exceed the expanded-character limit.')

    for io in inventory.entities:
        if io.kind not in MODULE_IO_KINDS:
            continue
        if io.name is not None:
            if len(io.name) > MAX_IO_NAME_LENGTH:
                rows[io.id] = _unavailable('name_length_limit')
                continue
            reserve_name(len(io.name))
            rows[io.id] = ({'name': io.name, 'name_origin': 'explicit_name', 'reason': None}
                           if (_EXPLICIT_NAME.fullmatch(io.name)
                               and not io.name.lower().startswith('program:'))
                           else _unavailable('invalid_explicit_name'))
            continue
        parent = entities.get(io.parent_id or '')
        connection = None
        if io.kind != 'module_config_tag':
            if parent is None or parent.kind != 'module_connection':
                rows[io.id] = _unavailable('missing_connection_context')
                continue
            connection = parent
            parent = entities.get(connection.parent_id or '')
        if parent is None or parent.kind != 'module' or io.scope_id != parent.scope_id:
            rows[io.id] = _unavailable('missing_module_context')
            continue
        if connection is not None:
            if connection.scope_id != parent.scope_id:
                rows[io.id] = _unavailable('missing_connection_context')
                continue
            if ((connection.name is not None
                 and connection_names[(parent.id, connection.name.lower())] > 1)
                    or ('Id' in connection.attributes
                        and connection_ids[(parent.id, connection.attributes['Id'])] > 1)):
                rows[io.id] = _unavailable('ambiguous_connection_context')
                continue
        suffix = _SUFFIX[io.kind]
        if connection is not None:
            attribute = 'InputTagSuffix' if io.kind == 'module_input_tag' else 'OutputTagSuffix'
            suffix = connection.attributes.get(attribute, suffix)
            if len(suffix) > MAX_IO_NAME_LENGTH:
                rows[io.id] = _unavailable('name_length_limit')
                continue
            if not re.fullmatch(rf'{_SUFFIX[io.kind]}[A-Za-z0-9_]*', suffix):
                rows[io.id] = _unavailable('invalid_suffix')
                continue
        prefix, origin, reason = location(parent.id)
        if reason is None:
            length = len(prefix) + 1 + len(suffix)
            if length > MAX_IO_NAME_LENGTH:
                reason = 'name_length_limit'
            else:
                # Reserve before joining: a compact XML declaration can repeat
                # one long module/adapter prefix across thousands of I/O rows.
                reserve_name(length)
        rows[io.id] = (_unavailable(reason) if reason else
                       {'name': f'{prefix}:{suffix}', 'name_origin': origin, 'reason': None})
    return rows
