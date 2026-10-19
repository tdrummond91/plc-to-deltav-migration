"""Bounded declaration wording attached to its exact captured signal uses.

These are lexical leads, not equipment classes or member descriptions. A root
declaration describes its root context even when a use has a member suffix.
Only the explicitly referenced alias and the terminal declaration are scanned;
an alias used by a reader does not become wording for an unrelated writer.
"""
from __future__ import annotations

from collections import defaultdict
import re
from typing import Any

from .access import AccessResult
from .models import InventoryResult, SourceSnapshot
from .rung_analysis import _HINTS
from .sfc_context import _qualified_source
from .source import _read_nodes

MAX_AUTHORED_FIELDS = 100_000
MAX_AUTHORED_USE_VISITS = 250_000
MAX_AUTHORED_CHARACTERS = 8_000_000
MAX_AUTHORED_ROWS = 100_000
MAX_AUTHORED_USE_IDS = 250_000
MAX_AUTHORED_BYTES = 8 * 1024 * 1024
AUTHORED_ADDRESS_BYTES = 128
AUTHORED_FIXED_BYTES = 2048
AUTHORED_CATEGORIES = frozenset({'alarm', 'equipment', 'sensor'})
AUTHORED_COUNT_MAPS = {
    'authored_scans_by_status': frozenset({'complete', 'truncated'}),
    'authored_field_scans_by_status': frozenset({'absent', 'no_match', 'matched', 'namespace_gap', 'ambiguous_text'}),
    'authored_evidence_by_relation': frozenset({'root_declaration', 'alias_declaration'}),
    'authored_evidence_by_field': frozenset({'name', 'description'}),
    'authored_evidence_by_qualification': frozenset({'qualified', 'namespace_gap'}),
    'authored_qualified_evidence_by_category': AUTHORED_CATEGORIES,
    'authored_unqualified_evidence_by_category': AUTHORED_CATEGORIES,
    'authored_outputs_by_category': AUTHORED_CATEGORIES,
}
AUTHORED_COVERAGE_KEYS = frozenset(AUTHORED_COUNT_MAPS) | frozenset({
    'authored_sources_total', 'authored_fields_scanned', 'authored_characters_scanned',
    'authored_use_visits', 'authored_evidence_total', 'authored_operand_links',
    'authored_expression_links', 'authored_description_gap_links',
    'authored_addresses_with_evidence', 'authored_addresses_with_description_gaps',
    'authored_addresses_with_unqualified_evidence', 'authored_outputs_with_evidence',
    'authored_outputs_with_unqualified_evidence',
})


def add_authored_evidence(snapshot: SourceSnapshot, inventory: InventoryResult,
        access: AccessResult, outputs: list[dict[str, Any]], addresses: list[dict[str, Any]],
        coverage: dict[str, Any]) -> None:
    """Add source-qualified, occurrence-linked wording without copying raw text.

Each unique declaration field is tokenized once. Work and retention are charged
before expansion; exhaustion leaves a deterministic prefix and explicit scan
status. Duplicate/nested descriptions are gaps, never selected text.
    """
    coverage.update({key: dict.fromkeys(sorted(values), 0) for key, values in AUTHORED_COUNT_MAPS.items()})
    coverage.update(dict.fromkeys(sorted(AUTHORED_COVERAGE_KEYS - AUTHORED_COUNT_MAPS.keys()), 0))
    nodes = _read_nodes(snapshot.data)
    xml = {node.locator: node for node in nodes}
    qualified, _, _ = _qualified_source(snapshot, inventory)
    entities = {entity.id: entity for entity in inventory.entities}
    operands = {row['id']: row for row in access.operands}
    expressions = {row['id']: row for row in access.expression_uses}
    output_by_operand = {row['target_operand_id']: row['id'] for row in outputs
        if row['target_status'] == 'exact_address'}
    output_matches: dict[str, set[str]] = defaultdict(set)
    output_categories: dict[str, set[str]] = defaultdict(set)
    fields: dict[tuple[str, str], tuple[str, str, tuple[str, ...], tuple[str, ...]]] = {}
    source_ids: set[str] = set()
    retained_bytes = retained_ids = 0
    halted = False

    def reserve(amount: int, *, ids: int = 0) -> bool:
        nonlocal retained_bytes, retained_ids, halted
        if retained_bytes + amount > MAX_AUTHORED_BYTES or retained_ids + ids > MAX_AUTHORED_USE_IDS:
            halted = True
            return False
        retained_bytes += amount
        retained_ids += ids
        return True

    def scan(entity_id: str, field: str):
        nonlocal halted
        key = (entity_id, field)
        if key in fields:
            return fields[key]
        if coverage['authored_fields_scanned'] >= MAX_AUTHORED_FIELDS:
            halted = True
            return None
        entity = entities[entity_id]
        node = xml[entity.locator]
        okay = qualified[entity.locator]
        text = entity.name if field == 'name' else entity.description
        ambiguous = False
        if field == 'description':
            descriptions = [nodes[index] for index in node.children if nodes[index].name == 'Description']
            ambiguous = bool(descriptions) and (len(descriptions) != 1 or bool(descriptions[0].children))
            if len(descriptions) == 1:
                okay = okay and qualified[descriptions[0].locator]
        characters = len(text) if text else 0
        if coverage['authored_characters_scanned'] + characters > MAX_AUTHORED_CHARACTERS:
            halted = True
            return None
        coverage['authored_fields_scanned'] += 1
        coverage['authored_characters_scanned'] += characters
        source_ids.add(entity_id)
        terms: set[str] = set()
        categories: set[str] = set()
        # Keep the existing whole-word catalog and lexical boundaries exactly.
        # No camel-case splitting, abbreviation expansion or synonym inference.
        if text and not ambiguous:
            for token in re.finditer(r'[^\W\d_]+', text.casefold(), re.UNICODE):
                for category in AUTHORED_CATEGORIES:
                    if token.group() in _HINTS[category]:
                        terms.add(token.group())
                        categories.add(category)
        status = ('ambiguous_text' if ambiguous else 'absent' if not text else
            'namespace_gap' if not okay else 'matched' if categories else 'no_match')
        coverage['authored_field_scans_by_status'][status] += 1
        result = (status, 'qualified' if okay else 'namespace_gap', tuple(sorted(categories)), tuple(sorted(terms)))
        fields[key] = result
        return result

    # The fixed wrappers remain present even for truncated scans. Reserve their
    # allowance before evidence so an otherwise full evidence budget cannot
    # unexpectedly consume the complete artifact's remaining space.
    reserve(AUTHORED_FIXED_BYTES + AUTHORED_ADDRESS_BYTES * len(addresses))
    for address in addresses:
        evidence: list[dict[str, Any]] = []
        gaps: list[str] = []
        address.update(authored_evidence=evidence, authored_description_gap_ids=gaps,
            authored_scan_status='truncated' if halted else 'complete')
        if not halted:
            # Root context applies only to the accepted occurrences in this
            # address. Explicit alias context retains its own subset of uses.
            groups: dict[str, dict[str, list[str]]] = {
                address['target_id']: {'operand_ids': [], 'expression_use_ids': []}}
            sources = ((field, identifiers, operands if field == 'operand_ids' else expressions)
                for field, identifiers in (
                    *((('operand_ids', address[f'{role}_operand_ids']) for role in ('read', 'write', 'read_write', 'unknown'))),
                    ('expression_use_ids', address['expression_use_ids'])))
            for field, identifiers, lookup in sources:
                for identifier in identifiers:
                    if coverage['authored_use_visits'] >= MAX_AUTHORED_USE_VISITS:
                        halted = True
                        break
                    coverage['authored_use_visits'] += 1
                    groups[address['target_id']][field].append(identifier)
                    symbol_id = lookup[identifier]['symbol_id']
                    if symbol_id != address['target_id']:
                        groups.setdefault(symbol_id, {'operand_ids': [], 'expression_use_ids': []})[field].append(identifier)
                if halted:
                    break
            # If the work budget stops midway, do not pretend this address was
            # fully scanned. Its captured prefix can still provide useful leads.
            for entity_id, uses in groups.items():
                if halted:
                    break
                relation = 'root_declaration' if entity_id == address['target_id'] else 'alias_declaration'
                for field in ('name', 'description'):
                    scanned = scan(entity_id, field)
                    if scanned is None:
                        break
                    status, qualification, categories, terms = scanned
                    if status == 'ambiguous_text' or field == 'description' and status == 'namespace_gap' and not categories:
                        if reserve(len(entity_id.encode('utf-8')) + 24, ids=1):
                            gaps.append(entity_id)
                            coverage['authored_description_gap_links'] += 1
                        else:
                            break
                    if not categories:
                        continue
                    if coverage['authored_evidence_total'] >= MAX_AUTHORED_ROWS:
                        halted = True
                        break
                    # Conservative header allowance includes the closed term
                    # catalog and pretty-JSON nesting; charge before retaining.
                    if not reserve(1024 + len(entity_id.encode('utf-8'))):
                        break
                    row = {'entity_id': entity_id, 'relation': relation, 'field': field,
                        'scope': 'declaration_root_context', 'qualification': qualification,
                        'categories': list(categories), 'terms': list(terms),
                        'operand_ids': [], 'expression_use_ids': []}
                    for use_field, count_key in (('operand_ids', 'authored_operand_links'),
                            ('expression_use_ids', 'authored_expression_links')):
                        for identifier in uses[use_field]:
                            if not reserve(len(identifier.encode('utf-8')) + 32, ids=1):
                                break
                            row[use_field].append(identifier)
                            coverage[count_key] += 1
                            output_id = output_by_operand.get(identifier) if use_field == 'operand_ids' else None
                            if output_id is not None:
                                output_matches[qualification].add(output_id)
                                if qualification == 'qualified':
                                    for category in categories:
                                        output_categories[category].add(output_id)
                        if halted:
                            break
                    if row['operand_ids'] or row['expression_use_ids']:
                        evidence.append(row)
                        coverage['authored_evidence_total'] += 1
                        coverage['authored_evidence_by_relation'][relation] += 1
                        coverage['authored_evidence_by_field'][field] += 1
                        coverage['authored_evidence_by_qualification'][qualification] += 1
                        category_key = ('authored_qualified_evidence_by_category' if qualification == 'qualified'
                            else 'authored_unqualified_evidence_by_category')
                        for category in categories:
                            coverage[category_key][category] += 1
                    if halted:
                        break
            address['authored_scan_status'] = 'truncated' if halted else 'complete'
        coverage['authored_scans_by_status'][address['authored_scan_status']] += 1
        coverage['authored_addresses_with_evidence'] += int(bool(evidence))
        coverage['authored_addresses_with_description_gaps'] += int(bool(gaps))
        coverage['authored_addresses_with_unqualified_evidence'] += int(any(
            row['qualification'] == 'namespace_gap' for row in evidence))
    coverage['authored_sources_total'] = len(source_ids)
    coverage['authored_outputs_with_evidence'] = len(output_matches['qualified'])
    coverage['authored_outputs_with_unqualified_evidence'] = len(output_matches['namespace_gap'])
    coverage['authored_outputs_by_category'].update({key: len(output_categories[key]) for key in AUTHORED_CATEGORIES})
