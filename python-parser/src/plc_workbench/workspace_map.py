"""Small read-only ladder-map projections of saved source and analysis.

The overview deliberately carries no source text, operands or diagrams. Search
uses the complete captured text; detail is fetched explicitly and bounded. Map
connections belong to ConnectionIndex, which authenticates exact-address roles.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .project_store import ProjectError

PAGE_SIZE = 250
MAX_QUERY = 500
MAX_ID = 256
MAX_PATH = 1024
MAX_DETAIL_ITEMS = 64
FAMILY_LABELS = {
    'boolean_condition': 'Boolean conditions', 'boolean_output': 'Boolean results',
    'calculation': 'Calculations', 'timer_counter': 'Timers and counters',
    'data_transfer': 'Data transfer', 'communication_system': 'Communication and system',
    'sequence_control': 'Sequence control', 'control_flow': 'Program control',
    'pid_control': 'PID control', 'alarm': 'Alarms', 'unknown': 'Unidentified blocks',
    'unparsed': 'Unparsed source', 'empty': 'Empty rungs',
}


def query_text(query: dict, key: str, limit: int = MAX_ID) -> str:
    value = query.get(key, '')
    if type(value) is not str or len(value) > limit:
        raise ProjectError('Choose valid ladder-map filters.')
    return value


def page_number(query: dict) -> int:
    value = query.get('page', '1')
    if type(value) not in {str, int}:
        raise ProjectError('Choose a valid ladder-map page.')
    try:
        page = int(value)
    except (ValueError, TypeError):
        raise ProjectError('Choose a valid ladder-map page.') from None
    if not 1 <= page <= 1_000_000:
        raise ProjectError('Choose a valid ladder-map page.')
    return page


def family_filter(query: dict) -> str:
    """One validated source-family filter for map and ordinary rung browsing."""
    family = query_text(query, 'family', 80)
    if family and family not in FAMILY_LABELS:
        raise ProjectError('Choose a supported block family.')
    return family


def _short(value: Any, limit: int) -> str:
    return str(value if value is not None else '')[:limit]


class LadderMapIndex:
    def __init__(self, inventory: dict, analysis: dict, *, rung_ok: dict):
        self.rung_ok = rung_ok
        self.rungs = {row['id']: row for row in inventory.get('rungs', [])}
        self.sources = {row['id']: row for row in inventory.get('entities', [])}
        self.sources.update(self.rungs)
        self.parents = {row['id']: row.get('parent_id') for row in self.sources.values()}
        self.children: dict[str, list[dict]] = defaultdict(list)
        for row in inventory.get('entities', []):
            self.children[row.get('parent_id')].append(row)
        self.blocks = {row['id']: row for row in analysis.get('blocks', [])}
        self.paths: dict[str, str] = {}
        self.rows = []
        self.search = {}
        self.instructions = {}
        self._definitions: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
        for row in inventory.get('entities', []):
            if row.get('kind') in {'aoi', 'data_type'} and row.get('name'):
                self._definitions[(self.controller(row['id']), row['kind'], row['name'].casefold())].append(row)
        for ordinal, rung in enumerate(self.rungs.values()):
            instructions = rung.get('instructions', [])
            for instruction in instructions:
                self.sources[instruction['id']] = instruction
                self.parents[instruction['id']] = rung['id']
                self.instructions[instruction['id']] = rung['id']
            qualified = rung_ok.get(rung['id'], False)
            families = (sorted({self.block(instruction)['family'] for instruction in instructions})
                        if qualified else ['unknown'])
            if rung.get('parse_status') != 'parsed':
                families.append('unparsed')
            elif not instructions:
                families.append('empty')
            branches = 0
            pending = [rung.get('structure')]
            while pending:
                item = pending.pop()
                if isinstance(item, dict):
                    branches += item.get('kind') == 'branch'
                    pending.extend(item.get('items', item.get('legs', [])))
            path = self.path(rung['id'])
            number = rung.get('number') if rung.get('number') is not None else str(rung.get('ordinal', ordinal))
            row = {'id': rung['id'], 'number': _short(number, 128), 'path': path[:MAX_PATH],
                   'routine_id': rung.get('parent_id') or '',
                   'routine_label': self.path(rung.get('parent_id'))[:MAX_PATH] or '(Unassigned routine)',
                   'source_order': ordinal, 'comment_preview': _short(rung.get('comment'), 240),
                   'opcodes': list(dict.fromkeys(_short(item.get('opcode'), 128) for item in instructions))[:12],
                   'instruction_count': len(instructions), 'branch_count': branches,
                   'families': families, 'parse_status': rung.get('parse_status', 'unknown'),
                   'source_qualified': qualified}
            self.rows.append(row)
            self.search[rung['id']] = ' '.join((path, rung.get('text') or '', rung.get('comment') or '')).casefold()
        routines = Counter(row['routine_id'] for row in self.rows)
        self.routines = [{'id': identifier, 'label': self.path(identifier)[:MAX_PATH] or '(Unassigned routine)',
                          'count': count} for identifier, count in routines.items()]
        self.families = Counter(family for row in self.rows for family in row['families'])
        self.rows_by_id = {row['id']: row for row in self.rows}

    def family_choices(self) -> list[dict]:
        """Whole-analysis rung counts; a mixed rung can belong to several families."""
        return [{'id': identifier, 'label': FAMILY_LABELS[identifier], 'count': count}
                for identifier, count in sorted(self.families.items())]

    def path(self, identifier: str | None) -> str:
        if not identifier:
            return ''
        if identifier in self.paths:
            return self.paths[identifier]
        parts = []
        current = identifier
        seen = set()
        while current in self.sources and current not in seen and len(seen) < 160:
            seen.add(current)
            row = self.sources[current]
            if 'opcode' in row:
                parts.append(row['opcode'])
            elif 'instructions' in row:
                number = row.get('number') if row.get('number') is not None else row.get('ordinal', '?')
                parts.append(f'Rung {number}')
            else:
                parts.append(row.get('name') or row.get('kind', 'Unnamed'))
            current = self.parents.get(current)
        self.paths[identifier] = ' / '.join(reversed(parts))
        return self.paths[identifier]

    def controller(self, identifier: str) -> str:
        seen = set()
        while identifier in self.sources and identifier not in seen:
            seen.add(identifier)
            row = self.sources[identifier]
            if row.get('kind') == 'controller':
                return identifier
            identifier = self.parents.get(identifier)
        return ''

    def block(self, instruction: dict) -> dict:
        captured = self.blocks.get(instruction['id'], {})
        qualified = self.rung_ok.get(self.instructions.get(instruction['id']), False)
        matches = qualified and captured.get('opcode') == instruction.get('opcode')
        family = captured.get('family') if matches else 'unknown'
        if family not in FAMILY_LABELS:
            family = 'unknown'
        identification = captured.get('identification', 'unknown') if matches else 'unknown'
        return {'id': instruction['id'], 'opcode': _short(instruction.get('opcode'), 128),
                'family': family, 'identification': _short(identification, 80),
                'summary': f"{FAMILY_LABELS[family]}; {_short(identification, 80).replace('_', ' ')}."}

    def view(self, query: dict, *, signal_rungs: frozenset[str] | None = None) -> dict:
        routine = query_text(query, 'routine')
        family = family_filter(query)
        search = query_text(query, 'query', MAX_QUERY).casefold()
        page = page_number(query)
        if routine and routine not in {row['id'] for row in self.routines}:
            raise ProjectError('Choose a routine from the selected analysis.')
        items = [row for row in self.rows
                 if (not routine or row['routine_id'] == routine)
                 and (not family or family in row['families'])
                 and (not search or search in self.search[row['id']])
                 and (signal_rungs is None or row['id'] in signal_rungs)]
        pages = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = min(page, pages)
        return {'items': items[(page - 1) * PAGE_SIZE:page * PAGE_SIZE], 'total': len(items),
                'page': page, 'pages': pages, 'page_size': PAGE_SIZE,
                'routines': self.routines,
                'families': self.family_choices()}

    def detail(self, identifier: str, *, entity_ok: dict, rung_ok: dict) -> dict:
        if not identifier or len(identifier) > MAX_ID or identifier not in self.sources:
            raise ProjectError('Choose a captured source item from the selected analysis.')
        source = self.sources[identifier]
        kind = 'rung' if 'instructions' in source else 'instruction' if 'opcode' in source else source.get('kind', 'object')
        instructions = source.get('instructions', []) if kind == 'rung' else [source] if kind == 'instruction' else []
        attributes = list(source.get('attributes', {}).items())
        qualified = (rung_ok.get(identifier, False) if kind == 'rung' else
                     rung_ok.get(self.instructions.get(identifier), False) if kind == 'instruction'
                     else entity_ok.get(identifier, False))
        child_parameters = [row for row in self.children.get(identifier, [])
                            if row.get('kind') == 'aoi_parameter' and entity_ok.get(row['id'], False)] if qualified else []
        description = source.get('comment') if kind == 'rung' else source.get('description')
        result = {'id': identifier, 'title': self.path(identifier)[:MAX_PATH], 'kind': kind,
                  'description': _short(description, 2400),
                  'description_truncated': len(description or '') > 2400,
                  'attributes': {key[:128]: _short(value, 512) for key, value in attributes[:48]},
                  'attributes_truncated': len(attributes) > 48,
                  'blocks': [self.block(row) for row in instructions[:MAX_DETAIL_ITEMS]],
                  'block_count': len(instructions), 'blocks_truncated': len(instructions) > MAX_DETAIL_ITEMS,
                  'parameters': [{'id': row['id'], 'name': _short(row.get('name'), 128),
                                  'description': _short(row.get('description'), 512),
                                  'attributes': {key[:128]: _short(value, 512)
                                                 for key, value in list(row.get('attributes', {}).items())[:24]}}
                                 for row in child_parameters[:MAX_DETAIL_ITEMS]],
                  'parameter_count': len(child_parameters), 'parameters_truncated': len(child_parameters) > MAX_DETAIL_ITEMS,
                  'links': [], 'limitations': [], 'source_qualified': qualified}
        if not qualified:
            result['limitations'].append('Unsupported XML qualification prevents reliable type or instruction associations. Inspect the original source.')
            for block in result['blocks']:
                block.update(family='unknown', identification='unknown', summary='Source qualification is unsupported.')
        parent = self.parents.get(identifier)
        if parent in self.sources:
            result['links'].append({'id': parent, 'label': self.path(parent)[:MAX_PATH], 'kind': 'source_parent'})
        controller = self.controller(identifier)
        datatype = source.get('attributes', {}).get('DataType', '')
        lookups = [('data_type', datatype)] if datatype and qualified else []
        if kind == 'instruction' and qualified:
            lookups.append(('aoi', source.get('opcode', '')))
        for definition_kind, name in lookups:
            matches = self._definitions.get((controller, definition_kind, name.casefold()), [])
            if len(matches) == 1 and entity_ok.get(matches[0]['id'], False):
                row = matches[0]
                result['links'].append({'id': row['id'], 'label': self.path(row['id'])[:MAX_PATH],
                                        'kind': 'aoi_definition_candidate' if definition_kind == 'aoi' else 'declared_type'})
                if definition_kind == 'aoi':
                    result['limitations'].append('A same-controller AOI declaration matches this name. Its call binding and behavior are not confirmed by this map.')
            elif len(matches) > 1:
                result['limitations'].append('Multiple declarations match this name; no definition has been selected.')
            elif matches:
                result['limitations'].append('A matching declaration has unsupported XML qualification; no definition has been selected.')
        if kind == 'data_type':
            result['limitations'].append('Member details are available in the original source; the map does not infer a member layout.')
        if kind == 'rung' and source.get('parse_status') != 'parsed':
            result['limitations'].append('This rung is preserved without a complete parsed structure. Open the source to inspect it.')
        return result
