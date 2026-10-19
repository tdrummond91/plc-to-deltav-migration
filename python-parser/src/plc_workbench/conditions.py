"""Bounded, source-relative Boolean conditions for selected normal-scan coils.

The graph preserves evaluation entry, instruction occurrences, branch leg order,
and opaque transfers. It neither simulates a scan nor establishes physical I/O,
alarm purpose, member types, initialization, or process behavior.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
from io import StringIO
from itertools import chain
import json
import re
from typing import Any

from .access import AccessResult, _timer_pseudo_kind
from .calculations import CalculationResult, FUNCTIONS, _Parser, _Unsupported as ExpressionUnsupported
from .ladder.syntax import PUBLIC_OPCODES
from .models import InventoryResult, SourceSnapshot
from .references import MAX_ADDRESS_LENGTH, ReferenceResult, _address, _NUMBER, _Resolver, _strict_record_match
from .relationships import RelationshipResult, validate_relationships
from .rung_analysis import RungAnalysisResult
from .source import _read_nodes

MAX_CONDITION_BYTES = 32 * 1024 * 1024
MAX_RECORDS = 250_000
MAX_EVIDENCE_IDS = 2_000_000
PREDICATE_OPCODES = frozenset('XIC XIO EQU NEQ LES LEQ GRT GEQ LIM'.split())
OUTPUT_ACTIONS = {'OTE': 'assign_condition', 'OTL': 'set_if_true', 'OTU': 'clear_if_true'}
# Instruction-specific normal-scan LD execution tables, cited in
# CONDITION_TRANSFER_REVIEW.md. Operand access alone is never sufficient to
# admit an opcode. Stateful effects and faults are outside this transfer model.
PASSTHROUGH_OPCODES = frozenset('ABS ADD CLR COP CPS CPT CTU DIV LN MOV MUL OSF RES RTO SQR SUB TON'.split())
STATEFUL_OPCODES = frozenset({'ONS'})
# Separate sets preserve the exact condition1-3 catalogues. These built-in
# output instructions use the documented PM008 normal-scan output rule; they
# are never inferred from access roles or applied to control flow or AOIs.
REVIEWED_PASSTHROUGH_OPCODES = frozenset('MVM SWPB GSV MSG PID AVE FAL SQO'.split())
SOURCE_SIGNATURE_OPCODES = frozenset('PID AVE FAL SQO'.split())
OPAQUE_OPCODES = PUBLIC_OPCODES | {'withheld'}
AOI_BODY_OPCODES = frozenset('ABS ADD CLR CPT DIV LN MOV MUL SQR SUB'.split())
AOI_IDENTITY_STATUSES = frozenset({
    'modeled', 'explicit_override', 'definition_unavailable', 'source_unqualified',
    'protected', 'call_unqualified', 'instance_unqualified', 'parameter_unqualified',
    'body_unqualified', 'instruction_unsupported', 'write_unqualified',
})
GSV_SIGNATURE_STATUSES = frozenset({'modeled', 'argument_count', 'empty_field', 'class_token',
    'instance_syntax', 'attribute_token', 'destination_syntax', 'namespace'})
AOI_BODY_GAP_REASONS = frozenset({
    'definition_content', 'metadata_shape', 'container_cardinality', 'scan_enabled',
    'scan_flag_syntax', 'container_content', 'routine_count', 'routine_identity',
    'routine_content', 'content_shape', 'rung_count', 'rung_parse', 'rung_type', 'rung_content',
})
GSV_INSTANCE_GAP_FORMS = frozenset({'zero_literal', 'other_integer', 'question_mark',
                                    'quoted', 'program_qualified', 'other'})
CONDITION_CONSTANTS = {
    'schema_version': 1, 'analyzer_version': 'condition-analysis-1',
    'analysis_scope': 'local_rung_boolean_conditions', 'execution_analysis': 'not_implemented',
    'engineering_review': 'unreviewed', 'evaluation_scope': 'normal_scan_only',
}
COUNT_MAPS = {
    'node_kinds': frozenset({'entry', 'predicate', 'all', 'any', 'opaque_transfer'}),
    'output_opcodes': frozenset(OUTPUT_ACTIONS), 'predicate_opcodes': PREDICATE_OPCODES,
    'guard_statuses': frozenset({'modeled', 'binding_gaps', 'opaque'}),
    'action_statuses': frozenset({'recognized', 'unresolved'}),
    'target_statuses': frozenset({'exact_address', 'identity_gap', 'unbound', 'signature_unresolved'}),
    'rung_statuses': frozenset({'parsed', 'unparsed'}),
    'opaque_reasons': frozenset({'unsupported_condition_behavior', 'signature_unresolved'}),
}
COVERAGE_KEYS = frozenset(COUNT_MAPS) | {
    'source_rungs', 'source_instructions', 'source_operands', 'expression_uses',
    'nodes_total', 'outputs_total', 'rungs_with_outputs', 'output_addresses',
    'branch_joins', 'branch_legs', 'binding_gap_predicates', 'outputs_with_branches',
}


def condition_constants(schema_version: int) -> dict[str, Any]:
    if type(schema_version) is not int or schema_version not in (1, 2, 3, 4, 5, 6):
        _invalid()
    return {**CONDITION_CONSTANTS, 'schema_version': schema_version,
            'analyzer_version': f'condition-analysis-{schema_version}'}


def count_maps(schema_version: int) -> dict[str, frozenset[str]]:
    condition_constants(schema_version)
    if schema_version == 1:
        return dict(COUNT_MAPS)
    maps = {**COUNT_MAPS, 'node_kinds': COUNT_MAPS['node_kinds'] | {'pass_through'},
            'passthrough_opcodes': PASSTHROUGH_OPCODES}
    if schema_version >= 3:
        maps['node_kinds'] = maps['node_kinds'] | {'stateful_transfer'}
        maps['stateful_opcodes'] = STATEFUL_OPCODES
    if schema_version >= 4:
        maps['passthrough_opcodes'] = PASSTHROUGH_OPCODES | REVIEWED_PASSTHROUGH_OPCODES
        maps['opaque_reasons'] = maps['opaque_reasons'] | {'source_unqualified'}
        maps['opaque_opcodes'] = OPAQUE_OPCODES
        maps['opaque_guard_opcodes'] = OPAQUE_OPCODES
    if schema_version >= 5:
        maps['passthrough_opcodes'] = maps['passthrough_opcodes'] | {'custom'}
        maps['aoi_identity_statuses'] = AOI_IDENTITY_STATUSES
        maps['gsv_signature_statuses'] = GSV_SIGNATURE_STATUSES
    if schema_version >= 6:
        maps['aoi_body_gap_reasons'] = AOI_BODY_GAP_REASONS
        maps['gsv_instance_gap_forms'] = GSV_INSTANCE_GAP_FORMS
    return maps


def coverage_keys(schema_version: int) -> frozenset[str]:
    return frozenset(COVERAGE_KEYS | count_maps(schema_version).keys()
                     | ({'binding_gap_stateful', 'outputs_with_stateful_conditions'}
                        if schema_version >= 3 else set()))


def _reviewed_signature(opcode: str, arguments: tuple[str, ...] | list[str]) -> bool:
    """Recognize source syntax, without resolving data or validating types.

    File/PID providers consume conditions, so this small recognizer must not
    import those providers. Their documented neutral-text ordering is retained.
    Unsupported selectors and FAL expression grammar remain explicit gaps.
    """
    arity = {'MVM': 3, 'SWPB': 3, 'GSV': 4, 'MSG': 1, 'PID': 7,
             'AVE': 6, 'FAL': 6, 'SQO': 6}[opcode]
    if len(arguments) != arity:
        return False
    values = [value.strip() for value in arguments]
    if any(not value and not (opcode == 'GSV' and index == 1)
           for index, value in enumerate(values)):
        return False

    def address(value: str) -> bool:
        parsed, reason = _address(value)
        return parsed is not None or reason == 'non_static_array_index'

    def value(text: str) -> bool:
        return len(text) <= MAX_ADDRESS_LENGTH and (bool(_NUMBER.fullmatch(text)) or address(text))

    if opcode == 'MVM':
        return value(values[0]) and value(values[1]) and address(values[2])
    if opcode == 'SWPB':
        return (address(values[0]) and address(values[2]) and values[1].isascii()
                and values[1].upper() in {'REVERSE', 'WORD', 'HIGHLOW'})
    if opcode == 'GSV':
        return (all(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', values[index])
                    for index in (0, 2))
                and (not values[1] or address(values[1])) and address(values[3]))
    if opcode == 'MSG':
        return address(values[0])
    if opcode == 'PID':
        return (all(address(values[index]) for index in (0, 1, 3))
                and all(value(values[index]) for index in (2, 4, 5, 6)))
    if opcode in {'AVE', 'SQO'}:
        return (all(address(values[index]) for index in (0, 2, 3))
                and (values[1] in {'0', '1', '2'} if opcode == 'AVE' else value(values[1]))
                and all(_timer_pseudo_kind(values[index]) is not None for index in (4, 5)))
    mode = values[3]
    if not (address(values[0]) and address(values[4])
            and all(_timer_pseudo_kind(values[index]) is not None for index in (1, 2))
            and ((mode.isascii() and mode.upper() in {'ALL', 'INC'})
                 or (re.fullmatch(r'[0-9]{1,10}', mode) and 1 <= int(mode) <= 2147483647))):
        return False
    try:
        _Parser(values[5], '', '', FUNCTIONS).parse()
    except ExpressionUnsupported:
        return False
    return True


def _qualified_rungs(snapshot: SourceSnapshot, inventory: InventoryResult) -> dict[str, bool]:
    """Require ordinary source ancestry and an unconfounded Text envelope."""
    nodes = _read_nodes(snapshot.data)
    namespace = nodes[0].expanded_name.rsplit('}', 1)[0] if '}' in nodes[0].expanded_name else None
    supported: list[bool] = []
    by_locator = {}
    for index, node in enumerate(nodes):
        current = node.expanded_name.rsplit('}', 1)[0] if '}' in node.expanded_name else None
        supported.append(current == namespace and all('}' not in key for key in node.expanded_attributes)
                         and (node.parent is None or supported[node.parent]))
        by_locator[node.locator] = index
    qualified = {}
    for rung in inventory.rungs:
        index = by_locator[rung.locator]
        texts = [child for child in nodes[index].children if nodes[child].name == 'Text']
        qualified[rung.id] = (supported[index] and len(texts) == 1
                              and supported[texts[0]] and not nodes[texts[0]].children)
    return qualified


def _gsv_signature_status(arguments: tuple[str, ...], qualified: bool) -> str:
    """Explain the existing syntax rule without exposing fields or widening it."""
    if not qualified:
        return 'namespace'
    if len(arguments) != 4:
        return 'argument_count'
    values = [value.strip() for value in arguments]
    if any(not values[index] for index in (0, 2, 3)):
        return 'empty_field'
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', values[0]):
        return 'class_token'
    if values[1]:
        parsed, reason = _address(values[1])
        if parsed is None and reason != 'non_static_array_index':
            return 'instance_syntax'
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', values[2]):
        return 'attribute_token'
    parsed, reason = _address(values[3])
    if parsed is None and reason != 'non_static_array_index':
        return 'destination_syntax'
    return 'modeled'


def _gsv_instance_gap_form(value: str) -> str:
    """Partition rejected instance syntax without retaining its source value."""
    value = value.strip()
    if value == '0':
        return 'zero_literal'
    if re.fullmatch(r'[+-]?[0-9]+', value):
        return 'other_integer'
    if value == '?':
        return 'question_mark'
    if len(value) >= 2 and value[0] in {'"', "'"} and value[-1] == value[0]:
        return 'quoted'
    if value.isascii() and value.lower().startswith('program:'):
        return 'program_qualified'
    return 'other'


def _aoi_identity_proofs(snapshot: SourceSnapshot, inventory: InventoryResult,
                         access: AccessResult, *, schema_version: int = 5) -> dict[str, dict[str, Any]]:
    """Prove a narrow AOI cannot override its default normal-scan EnableOut.

    This is deliberately independent of downstream AOI providers. Authenticated
    access roles check an explicit arithmetic catalogue; roles never admit an
    arbitrary instruction. Each definition is inspected once, without expanding
    calls or retaining body text, descendants, or per-call body evidence lists.
    """
    if max(len(inventory.entities), len(inventory.rungs), len(access.instructions),
           len(access.operands), len(access.expression_uses)) > MAX_RECORDS:
        _limit()
    nodes = _read_nodes(snapshot.data)
    namespace = nodes[0].expanded_name.rsplit('}', 1)[0] if '}' in nodes[0].expanded_name else None
    qualified, protected = [], []
    protection = {'Protected', 'IsProtected', 'SourceProtected', 'SourceKey', 'SourceKeyName',
                  'ProtectionType', 'Encrypted', 'EncryptionInfo', 'IsEncrypted'}
    for node in nodes:
        current = node.expanded_name.rsplit('}', 1)[0] if '}' in node.expanded_name else None
        qualified.append(current == namespace and all('}' not in key for key in node.expanded_attributes)
                         and (node.parent is None or qualified[node.parent]))
        protected.append(node.name in {'EncodedData', 'EncryptedContent', 'EncryptedAOIContent', 'EncryptionInfo'}
                         or bool(protection.intersection(node.attributes))
                         or (node.parent is not None and protected[node.parent]))
    # Descendant qualification prevents a supported-looking wrapper from hiding
    # foreign or protected logic. The original ancestry flags stay available.
    subtree_qualified, subtree_protected = qualified.copy(), protected.copy()
    for index in range(len(nodes) - 1, -1, -1):
        parent = nodes[index].parent
        if parent is not None:
            subtree_qualified[parent] &= subtree_qualified[index]
            subtree_protected[parent] |= subtree_protected[index]
    locations = {node.locator: index for index, node in enumerate(nodes)}
    entities = {entity.id: entity for entity in inventory.entities}
    owners, types, symbols, routines, body_rungs = {}, {}, {}, {}, {}
    for entity in inventory.entities:
        parent = entities.get(entity.parent_id)
        owners[entity.id] = entity.id if entity.kind == 'controller' else owners.get(parent.id) if parent else None
        if entity.kind in {'aoi', 'data_type'} and entity.name:
            types.setdefault((owners[entity.id], entity.name.lower()), []).append(entity)
        if entity.kind in {'aoi_parameter', 'aoi_local_tag'}:
            symbols.setdefault(entity.scope_id, []).append(entity)
        if entity.kind == 'routine':
            routines.setdefault(entity.scope_id, []).append(entity)
    for rung in inventory.rungs:
        body_rungs.setdefault(rung.parent_id, []).append(rung)
    instructions = {row['id']: row for row in access.instructions}
    operands = {row['id']: row for row in access.operands}
    expression_uses = {}
    for row in access.expression_uses:
        expression_uses.setdefault(row['instruction_id'], []).append(row)
    resolver = _Resolver(inventory)
    name_pattern = re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,39}')
    native = {'BOOL', 'SINT', 'INT', 'DINT', 'LINT', 'REAL'}

    def scalar(entity: Any) -> bool:
        return (entity.attributes.get('Dimensions', '') in {'', '0'}
                and 'AliasFor' not in entity.attributes
                and entity.attributes.get('TagType', 'Base') == 'Base')

    def envelope(index: int, allowed: set[str], required: dict[str, int]) -> bool:
        node = nodes[index]
        return (not node.text.strip() and all(nodes[child].name in allowed for child in node.children)
                and all(sum(nodes[child].name == name for child in node.children) == count
                        for name, count in required.items()))

    def source_status(index: int) -> str | None:
        return ('source_unqualified' if not subtree_qualified[index] else
                'protected' if subtree_protected[index] else None)

    def rung_envelope(rung: Any) -> bool:
        index = locations[rung.locator]
        texts = [child for child in nodes[index].children if nodes[child].name == 'Text']
        return (envelope(index, {'Text', 'Comment'}, {'Text': 1})
                and len(texts) == 1 and not nodes[texts[0]].children)

    def rung_qualified(rung: Any) -> bool:
        return rung.parse_status == 'parsed' and rung.type == 'N' and rung_envelope(rung)

    def inspect_definition(definition: Any) -> dict[str, Any]:
        proof = {'aoi_identity_status': 'parameter_unqualified', 'aoi_declaration_id': definition.id,
                 'aoi_logic_id': None, 'aoi_enableout_id': None,
                 'aoi_checked_instructions': 0, 'aoi_checked_writes': 0}
        if schema_version >= 6:
            proof['aoi_body_gap_reason'] = None
        index = locations[definition.locator]
        status = source_status(index)
        if status:
            return {**proof, 'aoi_identity_status': status}
        declared = symbols.get(definition.id, [])
        by_name = {}
        for symbol in declared:
            symbol_index = locations[symbol.locator]
            container = nodes[symbol_index].parent
            if (not symbol.name or not name_pattern.fullmatch(symbol.name)
                    or symbol.name.lower() in by_name or not scalar(symbol)
                    or symbol.attributes.get('DataType') not in native
                    or types.get((owners[definition.id], symbol.attributes['DataType'].lower()))
                    or container is None or nodes[container].parent != index
                    or nodes[container].name != ('Parameters' if symbol.kind == 'aoi_parameter' else 'LocalTags')
                    or not envelope(symbol_index, {'Description', 'DefaultData', 'Data'}, {})):
                return proof
            by_name[symbol.name.lower()] = symbol
            if symbol.kind == 'aoi_parameter':
                if (symbol.attributes.get('DataType') == 'LINT'
                        or symbol.attributes.get('Usage') not in {'Input', 'Output'}
                        or symbol.attributes.get('Required') != 'false'
                        or symbol.attributes.get('Visible') not in {'true', 'false'}):
                    return proof
        for name, usage in (('enablein', 'Input'), ('enableout', 'Output')):
            symbol = by_name.get(name)
            if (symbol is None or symbol.kind != 'aoi_parameter'
                    or symbol.attributes.get('DataType') != 'BOOL'
                    or symbol.attributes.get('Usage') != usage
                    or symbol.attributes.get('Visible') != 'false'):
                return proof
        proof['aoi_enableout_id'] = by_name['enableout'].id
        proof['aoi_identity_status'] = 'body_unqualified'
        own_routines = routines.get(definition.id, [])
        if schema_version >= 6:
            def gap(reason: str) -> dict[str, Any]:
                return {**proof, 'aoi_body_gap_reason': reason}

            metadata = {'Description', 'RevisionNote', 'AdditionalHelpText'}
            children = nodes[index].children
            if not envelope(index, metadata | {'Parameters', 'LocalTags', 'Routines'}, {}):
                return gap('definition_content')
            # Text metadata cannot conceal a body, alternate representation or
            # an attributed extension. The namespace/protection walk ran first.
            if (any(sum(nodes[c].name == name for c in children) > 1 for name in metadata)
                    or any(nodes[c].attributes or nodes[c].children for c in children
                           if nodes[c].name in metadata)):
                return gap('metadata_shape')
            if (not envelope(index, metadata | {'Parameters', 'LocalTags', 'Routines'},
                             {'Parameters': 1, 'Routines': 1})
                    or sum(nodes[c].name == 'LocalTags' for c in children) > 1):
                return gap('container_cardinality')
            flags = [definition.attributes.get(key, 'false')
                     for key in ('ExecutePrescan', 'ExecutePostscan', 'ExecuteEnableInFalse')]
            if any(value not in {'true', 'false'} for value in flags):
                return gap('scan_flag_syntax')
            if any(value == 'true' for value in flags):
                return gap('scan_enabled')
        elif (not envelope(index, {'Description', 'Parameters', 'LocalTags', 'Routines'},
                         {'Parameters': 1, 'Routines': 1})
                or sum(nodes[child].name == 'LocalTags' for child in nodes[index].children) > 1
                or any(definition.attributes.get(key, 'false') != 'false'
                       for key in ('ExecutePrescan', 'ExecutePostscan', 'ExecuteEnableInFalse'))
                or len(own_routines) != 1):
            return proof
        # Require exact container membership as well as inventory ownership;
        # otherwise an ignored child could conceal another declaration/body.
        for child in nodes[index].children:
            node = nodes[child]
            expected = {'Parameters': 'Parameter', 'LocalTags': 'LocalTag', 'Routines': 'Routine'}.get(node.name)
            if expected and not envelope(child, {expected}, {}):
                return gap('container_content') if schema_version >= 6 else proof
        if schema_version >= 6 and len(own_routines) != 1:
            return gap('routine_count')
        routine = own_routines[0]
        routine_index = locations[routine.locator]
        if schema_version >= 6:
            if routine.name != 'Logic' or routine.attributes.get('Type') != 'RLL':
                return gap('routine_identity')
            descriptions = [nodes[c] for c in nodes[routine_index].children if nodes[c].name == 'Description']
            if (not envelope(routine_index, {'Description', 'RLLContent'}, {'RLLContent': 1})
                    or len(descriptions) > 1 or any(n.attributes or n.children for n in descriptions)):
                return gap('routine_content')
        elif (routine.name != 'Logic' or routine.attributes.get('Type') != 'RLL'
                or not envelope(routine_index, {'Description', 'RLLContent'}, {'RLLContent': 1})):
            return proof
        proof['aoi_logic_id'] = routine.id
        content = next(child for child in nodes[routine_index].children if nodes[child].name == 'RLLContent')
        rungs = body_rungs.get(routine.id, [])
        if schema_version >= 6:
            if not envelope(content, {'Rung'}, {}):
                return gap('content_shape')
            if not rungs or len(rungs) != len(nodes[content].children):
                return gap('rung_count')
            if any(not rung_envelope(rung) for rung in rungs):
                return gap('rung_content')
            if any(rung.parse_status != 'parsed' for rung in rungs):
                return gap('rung_parse')
            if any(rung.type != 'N' for rung in rungs):
                return gap('rung_type')
        elif (not envelope(content, {'Rung'}, {}) or not rungs
                or len(rungs) != len(nodes[content].children)
                or any(not rung_qualified(rung) for rung in rungs)):
            return proof
        allowed_symbols = {symbol.id for symbol in declared}

        def own_binding(row: dict[str, Any]) -> bool:
            return (row['binding_status'] == 'root_bound' and not row['suffix'] and not row['alias_chain']
                    and row['symbol_id'] == row['target_id'] and row['target_id'] in allowed_symbols)

        for rung in rungs:
            for source in rung.instructions:
                record = instructions[source.id]
                slots = [operands[identifier] for identifier in record['operand_ids']]
                # A classified, exact EnableOut destination is explicit override
                # evidence even when its opcode is outside the identity allowlist.
                if any(slot['role'] in {'write', 'read_write'} and own_binding(slot)
                       and slot['target_id'] == by_name['enableout'].id for slot in slots):
                    return {**proof, 'aoi_identity_status': 'explicit_override'}
                if (not source.opcode.isascii() or source.opcode.upper() not in AOI_BODY_OPCODES
                        or record['status'] != 'classified'):
                    return {**proof, 'aoi_identity_status': 'instruction_unsupported'}
                for slot in slots:
                    if slot['role'] == 'write':
                        if not own_binding(slot) or slot['target_id'] == by_name['enablein'].id:
                            return {**proof, 'aoi_identity_status': 'write_unqualified'}
                        proof['aoi_checked_writes'] += 1
                    elif slot['role'] == 'read':
                        if slot['binding_status'] != 'literal' and not own_binding(slot):
                            return {**proof, 'aoi_identity_status': 'write_unqualified'}
                    elif slot['role'] != 'expression_read' or slot['binding_status'] != 'parsed_expression':
                        return {**proof, 'aoi_identity_status': 'write_unqualified'}
                if any(not own_binding(row) for row in expression_uses.get(source.id, [])):
                    return {**proof, 'aoi_identity_status': 'write_unqualified'}
                proof['aoi_checked_instructions'] += 1
        return {**proof, 'aoi_identity_status': 'modeled'}

    definitions, proofs, budget = {}, {}, _Budget()
    for rung in inventory.rungs:
        for source in rung.instructions:
            if source.opcode.isascii() and source.opcode.upper() in PUBLIC_OPCODES:
                continue
            if len(proofs) >= MAX_RECORDS:
                _limit()
            proof = {'aoi_identity_status': 'definition_unavailable', 'aoi_declaration_id': None,
                     'aoi_instance_id': None, 'aoi_logic_id': None, 'aoi_enableout_id': None,
                     'aoi_checked_instructions': 0, 'aoi_checked_writes': 0}
            if schema_version >= 6:
                proof['aoi_body_gap_reason'] = None
            candidates = types.get((owners.get(rung.scope_id), source.opcode.lower()), [])
            if (len(candidates) == 1 and candidates[0].kind == 'aoi'
                    and candidates[0].name and name_pattern.fullmatch(candidates[0].name)):
                definition = candidates[0]
                proof['aoi_declaration_id'] = definition.id
                status = source_status(locations[rung.locator])
                if status:
                    proof['aoi_identity_status'] = status
                elif (not name_pattern.fullmatch(source.opcode) or not rung_qualified(rung)
                      or len(source.arguments) != 1 or not name_pattern.fullmatch(source.arguments[0].strip())
                      or entities.get(rung.scope_id) is None or entities[rung.scope_id].kind != 'program'):
                    proof['aoi_identity_status'] = 'call_unqualified'
                else:
                    binding = resolver.resolve(source.arguments[0].strip(), rung.scope_id)
                    instance = entities.get(binding['target_id'])
                    if (binding['status'] != 'root_bound' or binding['suffix'] or binding['alias_chain']
                            or binding['symbol_id'] != binding['target_id'] or instance is None
                            or instance.kind != 'tag' or not scalar(instance)
                            or not name_pattern.fullmatch(instance.attributes.get('DataType', ''))
                            or instance.attributes.get('DataType', '').lower() != definition.name.lower()
                            or source_status(locations[instance.locator])):
                        proof['aoi_identity_status'] = 'instance_unqualified'
                    else:
                        proof['aoi_instance_id'] = instance.id
                        if definition.id not in definitions:
                            definitions[definition.id] = inspect_definition(definition)
                        proof.update(definitions[definition.id])
            budget.record({'instruction_id': source.id, **proof})
            proofs[source.id] = proof
    return proofs


class ConditionError(ValueError):
    """Source-free validation or resource rejection."""


def _invalid() -> None:
    raise ConditionError('Condition evidence does not match the source evidence.')


def _limit() -> None:
    raise ConditionError('Condition evidence exceeds its evidence limits.')


@dataclass(frozen=True)
class ConditionResult:
    snapshot: dict[str, str | int]
    status: str
    nodes: list[dict[str, Any]]
    outputs: list[dict[str, Any]]
    rungs: list[dict[str, Any]]
    coverage: dict[str, Any]
    schema_version: int = 1
    analyzer_version: str = 'condition-analysis-1'
    analysis_scope: str = 'local_rung_boolean_conditions'
    execution_analysis: str = 'not_implemented'
    engineering_review: str = 'unreviewed'
    evaluation_scope: str = 'normal_scan_only'

    def to_dict(self) -> dict[str, Any]:
        render_conditions_json(self)
        return deepcopy(vars(self))


class _Budget:
    def __init__(self) -> None:
        self.bytes = self.ids = 0

    def record(self, record: dict[str, Any]) -> None:
        self.bytes += len(json.dumps(record, ensure_ascii=True, separators=(',', ':'))) + 1
        self.ids += sum(len(value) if type(value) is list else int(value is not None)
                        for key, value in record.items()
                        if key == 'id' or key.endswith('_id') or key.endswith('_ids'))
        if self.bytes > MAX_CONDITION_BYTES or self.ids > MAX_EVIDENCE_IDS:
            _limit()


def _identifier(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode('utf-8'))
        digest.update(b'\0')
    return prefix + digest.hexdigest()


def _derive(inventory: InventoryResult, access: AccessResult,
            relationships: RelationshipResult, *, schema_version: int = 1,
            qualified_rungs: dict[str, bool] | None = None,
            aoi_proofs: dict[str, dict[str, Any]] | None = None) -> ConditionResult:
    constants = condition_constants(schema_version)
    if max(len(inventory.rungs), len(access.instructions), len(access.operands),
           len(access.expression_uses)) > MAX_RECORDS:
        _limit()
    instructions = {row['id']: row for row in access.instructions}
    operands = {row['id']: row for row in access.operands}
    source_instructions = {row.id: row for rung in inventory.rungs for row in rung.instructions}
    addresses = {identifier: address['id'] for address in relationships.addresses
                 for role in ('read', 'write', 'read_write', 'unknown')
                 for identifier in address[f'{role}_operand_ids']}
    identity_gaps = {row['id'] for row in relationships.identity_gaps if row['kind'] == 'operand'}
    maps = count_maps(schema_version)
    coverage = {key: dict.fromkeys(sorted(vocabulary), 0) for key, vocabulary in maps.items()}
    coverage.update(dict.fromkeys(sorted(coverage_keys(schema_version) - maps.keys()), 0))
    coverage.update(source_rungs=len(inventory.rungs), source_instructions=len(access.instructions),
                    source_operands=len(access.operands), expression_uses=len(access.expression_uses))
    nodes: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    rungs: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    # Fixed-size bitsets propagate diagnostic categories through the DAG once.
    # No descendant walks, formula expansion, or source-controlled map keys.
    opaque_buckets = sorted(OPAQUE_OPCODES) if schema_version >= 4 else []
    opaque_bits = {opcode: 1 << index for index, opcode in enumerate(opaque_buckets)}
    opaque_masks: dict[str, int] = {}
    target_addresses: set[str] = set()
    budget = _Budget()

    def node(rung_id: str, kind: str, child_ids: list[str], *, instruction_id: str | None = None,
             operand_ids: list[str] | None = None, reason: str | None = None,
             binding_gap: bool = False, aoi_proof: dict[str, Any] | None = None,
             gsv_status: str | None = None, gsv_gap_form: str | None = None) -> str:
        if len(nodes) >= MAX_RECORDS:
            _limit()
        identifier = _identifier('condition_node_', inventory.snapshot['id'], rung_id, str(len(nodes)), kind)
        row = {'id': identifier, 'rung_id': rung_id, 'kind': kind, 'instruction_id': instruction_id,
               'child_ids': child_ids, 'operand_ids': list(operand_ids or []), 'reason': reason,
               'has_opaque': kind == 'opaque_transfer' or any(by_id[c]['has_opaque'] for c in child_ids),
               'has_binding_gap': binding_gap or any(by_id[c]['has_binding_gap'] for c in child_ids),
               'has_branch': kind == 'any' or any(by_id[c]['has_branch'] for c in child_ids)}
        if schema_version >= 3:
            row['has_stateful'] = kind == 'stateful_transfer' or any(by_id[c]['has_stateful'] for c in child_ids)
        if schema_version >= 4:
            mask = 0
            for child in child_ids:
                mask |= opaque_masks[child]
            if kind == 'opaque_transfer':
                raw = source_instructions[instruction_id].opcode
                bucket = raw.upper() if raw.isascii() and raw.upper() in PUBLIC_OPCODES else 'withheld'
                mask |= opaque_bits[bucket]
                coverage['opaque_opcodes'][bucket] += 1
            opaque_masks[identifier] = mask
        if aoi_proof is not None:
            row.update(aoi_proof)
        if gsv_status is not None:
            row['gsv_signature_status'] = gsv_status
            if schema_version >= 6:
                row['gsv_instance_gap_form'] = gsv_gap_form
        budget.record(row)
        nodes.append(row)
        by_id[identifier] = row
        coverage['node_kinds'][kind] += 1
        if kind == 'opaque_transfer':
            coverage['opaque_reasons'][reason] += 1
        if kind == 'any':
            coverage['branch_joins'] += 1
            coverage['branch_legs'] += len(child_ids)
        return identifier

    def instruction(rung_id: str, instruction_id: str, incoming: str, output_ids: list[str]) -> str:
        record = instructions[instruction_id]
        opcode = source_instructions[instruction_id].opcode.upper()
        operand_ids = record['operand_ids']
        classified = record['status'] == 'classified'
        if schema_version >= 5 and aoi_proofs is not None and instruction_id in aoi_proofs:
            proof = aoi_proofs[instruction_id]
            status = proof['aoi_identity_status']
            coverage['aoi_identity_statuses'][status] += 1
            if schema_version >= 6 and status == 'body_unqualified':
                coverage['aoi_body_gap_reasons'][proof['aoi_body_gap_reason']] += 1
            modeled = status == 'modeled'
            if modeled:
                coverage['passthrough_opcodes']['custom'] += 1
            return node(rung_id, 'pass_through' if modeled else 'opaque_transfer', [incoming],
                        instruction_id=instruction_id, operand_ids=operand_ids, aoi_proof=proof,
                        reason='source_proven_aoi_identity' if modeled else 'unsupported_condition_behavior')
        if opcode in PREDICATE_OPCODES and classified:
            gap = any(identifier not in addresses and operands[identifier]['binding_status'] not in {'literal', 'system_flag'}
                      for identifier in operand_ids)
            predicate = node(rung_id, 'predicate', [], instruction_id=instruction_id,
                             operand_ids=operand_ids, binding_gap=gap)
            coverage['predicate_opcodes'][opcode] += 1
            coverage['binding_gap_predicates'] += int(gap)
            return node(rung_id, 'all', [incoming, predicate])
        if opcode in OUTPUT_ACTIONS:
            if len(outputs) >= MAX_RECORDS:
                _limit()
            target = operand_ids[0] if classified else None
            address = addresses.get(target)
            target_status = ('signature_unresolved' if not classified else 'exact_address' if address
                             else 'identity_gap' if target in identity_gaps else 'unbound')
            guard = by_id[incoming]
            guard_status = 'opaque' if guard['has_opaque'] else 'binding_gaps' if guard['has_binding_gap'] else 'modeled'
            identifier = _identifier('condition_output_', inventory.snapshot['id'], instruction_id)
            row = {'id': identifier, 'instruction_id': instruction_id, 'rung_id': rung_id,
                   'opcode': opcode, 'action': OUTPUT_ACTIONS[opcode] if classified else 'unresolved',
                   'guard_id': incoming, 'guard_status': guard_status, 'target_operand_id': target,
                   'target_address_id': address, 'target_status': target_status}
            if schema_version >= 3:
                row['has_stateful'] = guard['has_stateful']
                coverage['outputs_with_stateful_conditions'] += int(row['has_stateful'])
            if schema_version >= 4:
                mask = opaque_masks[incoming]
                while mask:
                    bit = mask & -mask
                    coverage['opaque_guard_opcodes'][opaque_buckets[bit.bit_length() - 1]] += 1
                    mask ^= bit
            budget.record(row)
            outputs.append(row)
            output_ids.append(identifier)
            coverage['output_opcodes'][opcode] += 1
            coverage['guard_statuses'][guard_status] += 1
            coverage['action_statuses']['recognized' if classified else 'unresolved'] += 1
            coverage['target_statuses'][target_status] += 1
            # Count guards containing a completed ANY join, not every coil
            # located inside a branch leg before that leg rejoins its peers.
            coverage['outputs_with_branches'] += int(guard['has_branch'])
            if address:
                target_addresses.add(address)
            # These three catalogued normal-scan coil instructions pass the
            # incoming condition through. Their destination actions differ.
            if classified:
                return incoming
        if schema_version >= 3 and opcode in STATEFUL_OPCODES and classified:
            # ONS filters its incoming condition using the storage value read
            # at this occurrence: outgoing = incoming AND NOT storage-before.
            # Normal evaluation assigns storage-after = incoming. We record
            # that symbolic rule, not values, a prior scan, or an inferred state
            # chain between occurrences that happen to share a storage address.
            # Unlike a predicate constant, a literal/system flag cannot supply
            # an exact retained-storage address. Type/member validity is still
            # outside this local condition model.
            gap = operand_ids[0] not in addresses
            coverage['stateful_opcodes'][opcode] += 1
            coverage['binding_gap_stateful'] += int(gap)
            return node(rung_id, 'stateful_transfer', [incoming], instruction_id=instruction_id,
                        operand_ids=operand_ids, reason='documented_normal_scan_stored_state',
                        binding_gap=gap)
        if schema_version >= 2 and opcode in PASSTHROUGH_OPCODES and classified:
            coverage['passthrough_opcodes'][opcode] += 1
            # Keep the occurrence even though the Boolean transfer is identity.
            # Data binding gaps do not change that documented transfer. These
            # slots still retain their independent access/binding evidence.
            return node(rung_id, 'pass_through', [incoming], instruction_id=instruction_id,
                        operand_ids=operand_ids, reason='documented_normal_scan_passthrough')
        if schema_version >= 4 and opcode in REVIEWED_PASSTHROUGH_OPCODES:
            source = source_instructions[instruction_id]
            gsv_status = gsv_gap_form = None
            if schema_version >= 5 and opcode == 'GSV':
                gsv_status = _gsv_signature_status(source.arguments, bool(qualified_rungs and qualified_rungs[rung_id]))
                coverage['gsv_signature_statuses'][gsv_status] += 1
                if schema_version >= 6 and gsv_status == 'instance_syntax':
                    gsv_gap_form = _gsv_instance_gap_form(source.arguments[1])
                    coverage['gsv_instance_gap_forms'][gsv_gap_form] += 1
            if not qualified_rungs or not qualified_rungs[rung_id]:
                reason = 'source_unqualified'
            elif (not source.opcode.isascii()
                  or (opcode not in SOURCE_SIGNATURE_OPCODES and not classified)
                  or not _reviewed_signature(opcode, source.arguments)):
                reason = 'signature_unresolved'
            else:
                coverage['passthrough_opcodes'][opcode] += 1
                return node(rung_id, 'pass_through', [incoming], instruction_id=instruction_id,
                            operand_ids=operand_ids, reason='documented_normal_scan_passthrough',
                            gsv_status=gsv_status, gsv_gap_form=gsv_gap_form)
            return node(rung_id, 'opaque_transfer', [incoming], instruction_id=instruction_id,
                        operand_ids=operand_ids, reason=reason, gsv_status=gsv_status, gsv_gap_form=gsv_gap_form)
        reason = ('signature_unresolved' if opcode in PREDICATE_OPCODES or opcode in OUTPUT_ACTIONS
                  or (schema_version >= 2 and opcode in PASSTHROUGH_OPCODES)
                  or (schema_version >= 3 and opcode in STATEFUL_OPCODES)
                  else 'unsupported_condition_behavior')
        return node(rung_id, 'opaque_transfer', [incoming], instruction_id=instruction_id,
                    operand_ids=operand_ids, reason=reason)

    for rung in inventory.rungs:
        parsed = rung.parse_status == 'parsed'
        output_ids: list[str] = []
        entry = node(rung.id, 'entry', []) if parsed else None
        exit_id = entry
        if parsed:
            # Explicit continuations avoid recursive calls, expanded Boolean
            # formulas, descendant lists, and repeated prefix copying.
            stack: list[tuple[Any, ...]] = [('visit', rung.structure, entry)]
            values: list[str] = []
            while stack:
                task = stack.pop()
                event = task[0]
                if event == 'visit':
                    tree, incoming = task[1:]
                    if tree['kind'] == 'instruction':
                        values.append(instruction(rung.id, tree['instruction_id'], incoming, output_ids))
                    elif tree['kind'] == 'sequence':
                        stack.append(('sequence', tree['items'], 0, incoming))
                    else:
                        legs = tree['legs']
                        stack.append(('join', len(legs)))
                        stack.extend(('visit', leg, incoming) for leg in reversed(legs))
                elif event == 'sequence':
                    items, index, incoming = task[1:]
                    if index == len(items):
                        values.append(incoming)
                    else:
                        stack.append(('next', items, index + 1))
                        stack.append(('visit', items[index], incoming))
                elif event == 'next':
                    stack.append(('sequence', task[1], task[2], values.pop()))
                else:
                    count = task[1]
                    children = values[-count:] if count else []
                    if count:
                        del values[-count:]
                    values.append(node(rung.id, 'any', children))
            exit_id = values.pop()
        row = {'id': rung.id, 'status': 'parsed' if parsed else 'unparsed',
               'entry_id': entry, 'exit_id': exit_id, 'output_ids': output_ids}
        budget.record(row)
        rungs.append(row)
        coverage['rung_statuses'][row['status']] += 1
        coverage['rungs_with_outputs'] += int(bool(output_ids))
    coverage.update(nodes_total=len(nodes), outputs_total=len(outputs), output_addresses=len(target_addresses))
    partial = bool(coverage['rung_statuses']['unparsed'] or coverage['node_kinds']['opaque_transfer']
                   or coverage['binding_gap_predicates']
                   or coverage.get('binding_gap_stateful', 0)
                   or len(outputs) != coverage['target_statuses']['exact_address'])
    return ConditionResult(deepcopy(inventory.snapshot), 'partial' if partial else 'complete',
                           nodes, outputs, rungs, coverage, **constants)


def analyze_conditions(snapshot: SourceSnapshot, inventory: InventoryResult, references: ReferenceResult,
                       access: AccessResult, calculations: CalculationResult,
                       rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
                       *, schema_version: int = 1) -> ConditionResult:
    """Authenticate every prior companion before deriving bounded conditions."""
    try:
        validate_relationships(snapshot, inventory, references, access, calculations, rung_analysis, relationships)
        condition_constants(schema_version)
        result = _derive(inventory, access, relationships, schema_version=schema_version,
                         qualified_rungs=_qualified_rungs(snapshot, inventory) if schema_version >= 4 else None,
                         aoi_proofs=_aoi_identity_proofs(snapshot, inventory, access, schema_version=schema_version)
                         if schema_version >= 5 else None)
        render_conditions_json(result)
        return result
    except ConditionError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def validate_conditions(snapshot: SourceSnapshot, inventory: InventoryResult, references: ReferenceResult,
                        access: AccessResult, calculations: CalculationResult,
                        rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
                        result: ConditionResult) -> None:
    try:
        if type(result) is not ConditionResult:
            _invalid()
        render_conditions_json(result)
        expected = analyze_conditions(snapshot, inventory, references, access, calculations, rung_analysis,
                                      relationships, schema_version=result.schema_version)
        if not _strict_record_match(vars(expected), vars(result)):
            _invalid()
    except ConditionError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_conditions_json(result: ConditionResult) -> str:
    """Serialize only bounded native containers; authentication is separate."""
    try:
        if type(result) is not ConditionResult or vars(result).keys() != set(ConditionResult.__dataclass_fields__):
            _invalid()
        payload = vars(result)
        remaining = MAX_CONDITION_BYTES
        frames: list[tuple[Any, int | None]] = [(iter((payload,)), None)]
        active: set[int] = set()
        while frames:
            try:
                value = next(frames[-1][0])
            except StopIteration:
                _, identifier = frames.pop()
                if identifier is not None:
                    active.remove(identifier)
                continue
            remaining -= 1
            if type(value) is str:
                remaining -= len(value)
            elif type(value) in {dict, list}:
                if len(value) > MAX_RECORDS or id(value) in active or len(frames) > 12:
                    _limit()
                if type(value) is dict and any(type(key) is not str for key in value):
                    _invalid()
                active.add(id(value))
                children = chain(value.keys(), value.values()) if type(value) is dict else value
                frames.append((iter(children), id(value)))
            elif type(value) not in {int, bool, type(None)}:
                _invalid()
            if remaining < 0:
                _limit()
        output, size = StringIO(), 0
        for chunk in json.JSONEncoder(ensure_ascii=True, sort_keys=True, indent=2).iterencode(payload):
            size += len(chunk)
            if size + 1 > MAX_CONDITION_BYTES:
                _limit()
            output.write(chunk)
        return output.getvalue() + '\n'
    except ConditionError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()
