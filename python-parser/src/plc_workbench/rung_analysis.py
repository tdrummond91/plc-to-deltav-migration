"""Snapshot-bound rung structure and explainable, unreviewed function candidates.

This is a structural interpretation of source evidence, not PLC execution, a
dependency graph, dead-code analysis, or a confirmed engineering purpose. Source
slots and CPT reference occurrences remain different populations throughout.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
import hashlib
from io import StringIO
import json
import re
from typing import Any

from .access import AccessResult, OPERAND_ROLES_V4, validate_access
from .calculations import CalculationResult
from .models import InventoryResult, SourceSnapshot
from .references import ReferenceResult, _strict_record_match

MAX_RUNG_ANALYSIS_BYTES = 32 * 1024 * 1024
MAX_RECORDS = 250_000
MAX_EVIDENCE_IDS = 2_000_000
MAX_HINT_CHARACTERS = 8_000_000
STRUCTURES = frozenset({'unparsed', 'empty', 'series', 'branched'})
IDENTIFICATIONS = frozenset({'identified', 'partial', 'unidentified', 'empty', 'unparsed'})
COMMENT_STATUSES = frozenset({'present', 'absent', 'ambiguous'})
RESULT_KINDS = frozenset({'single_known_result', 'multiple_known_results', 'no_known_result', 'stateful_or_external'})
BLOCK_IDENTIFICATIONS = frozenset({'roles_known', 'signature_known', 'known_mnemonic', 'unknown'})
BLOCK_FAMILIES = frozenset({'boolean_condition', 'boolean_output', 'calculation', 'timer_counter',
                          'data_transfer', 'communication_system', 'sequence_control', 'control_flow',
                          'pid_control', 'alarm', 'unknown'})
CANDIDATE_CATEGORIES = frozenset({'pid_control', 'calculation', 'boolean_output', 'timer_counter',
                                'data_transfer', 'communication_system', 'sequence_control', 'control_flow',
                                'io_input', 'io_output', 'alarm', 'equipment', 'sensor', 'miscellaneous'})
CANDIDATE_BASES = frozenset({'instruction_signature', 'known_mnemonic', 'structural_pattern',
                           'module_root', 'declaration_type', 'text_hint'})
RUNG_CONSTANTS = {
    'schema_version': 1, 'analyzer_version': 'rung-analysis-1',
    'analysis_scope': 'rll_structure_and_candidates', 'execution_analysis': 'not_implemented',
    'engineering_review': 'unreviewed',
}
COUNT_MAPS = {
    'structures': STRUCTURES, 'identification': IDENTIFICATIONS, 'comments': COMMENT_STATUSES,
    'results': RESULT_KINDS, 'block_identification': BLOCK_IDENTIFICATIONS,
    'block_families': BLOCK_FAMILIES, 'candidate_categories': CANDIDATE_CATEGORIES,
    'candidate_bases': CANDIDATE_BASES,
}
COVERAGE_KEYS = frozenset(COUNT_MAPS) | {
    'source_rungs', 'source_instructions', 'source_operands', 'expression_uses', 'candidates_total',
    'unknown_blocks', 'access_gap_operands', 'expression_gap_uses', 'unknown_role_operands',
    'branches', 'branch_legs', 'empty_legs', 'missing_number', 'missing_type',
}
_CONDITIONS = frozenset('XIC XIO EQU NEQ LES LEQ GRT GEQ LIM'.split())
_OUTPUTS = frozenset({'OTE', 'OTL', 'OTU'})
_FAMILIES = {
    **dict.fromkeys(_CONDITIONS, 'boolean_condition'),
    **dict.fromkeys(_OUTPUTS | {'ONS', 'OSR', 'OSF'}, 'boolean_output'),
    **dict.fromkeys('ADD SUB MUL DIV ABS LN SQR CPT AVE FAL'.split(), 'calculation'),
    **dict.fromkeys('TON TOF RTO RES CTU CTD'.split(), 'timer_counter'),
    **dict.fromkeys('MOV MVM SWPB CLR COP CPS'.split(), 'data_transfer'),
    **dict.fromkeys('MSG GSV SSV'.split(), 'communication_system'),
    **dict.fromkeys('SFR SQO'.split(), 'sequence_control'),
    **dict.fromkeys('JMP LBL JSR SBR RET'.split(), 'control_flow'),
    'PID': 'pid_control',
    **dict.fromkeys('ALMA ALMD ASO'.split(), 'alarm'),
}
_MNEMONIC_ONLY = frozenset('JSR SBR RET AVE FAL SQO ALMA ALMD ASO'.split())
_HINTS = {
    'alarm': frozenset({'alarm', 'alarms', 'alarme', 'alarmes', 'warning', 'trip', 'shutdown'}),
    'equipment': frozenset({'pump', 'pumps', 'pompe', 'pompes', 'valve', 'valves', 'vanne', 'vannes', 'motor', 'moteur'}),
    'sensor': frozenset({'sensor', 'sensors', 'capteur', 'capteurs', 'transmitter', 'transmetteur', 'sonde'}),
    'pid_control': frozenset({'pid', 'regulator', 'regulateur', 'régulateur'}),
}


class RungAnalysisError(ValueError):
    """Source-free analysis or validation rejection."""


def _invalid() -> None:
    raise RungAnalysisError('Rung analysis does not match the source evidence.')


def _limit() -> None:
    raise RungAnalysisError('Rung analysis exceeds its evidence limits.')


@dataclass(frozen=True)
class RungAnalysisResult:
    snapshot: dict[str, str | int]
    status: str
    rungs: list[dict[str, Any]]
    blocks: list[dict[str, Any]]
    candidates: list[dict[str, Any]]
    coverage: dict[str, Any]
    schema_version: int = 1
    analyzer_version: str = 'rung-analysis-1'
    analysis_scope: str = 'rll_structure_and_candidates'
    execution_analysis: str = 'not_implemented'
    engineering_review: str = 'unreviewed'

    def to_dict(self) -> dict[str, Any]:
        render_rung_analysis_json(self)
        return deepcopy(vars(self))


def _frontiers(tree: dict[str, Any]) -> tuple[list[str], list[str], bool, int, int, int]:
    """Fold ordered possible structural terminals without enumerating paths.

    A nullable suffix retains the preceding terminals. Each instruction occurs
    once in the AST, so child frontiers are disjoint and need no pairwise graph.
    Nesting is already bounded by the authenticated source parser.
    """
    kind = tree['kind']
    if kind == 'instruction':
        return [tree['instruction_id']], [tree['instruction_id']], False, 0, 0, 0
    first: list[str] = []
    last: list[str] = []
    branches = legs = empty = 0
    if kind == 'branch':
        nullable = False
        branches, legs = 1, len(tree['legs'])
        for child in tree['legs']:
            a, z, n, b, l, e = _frontiers(child)
            first.extend(a)
            last.extend(z)
            nullable = nullable or n
            branches, legs, empty = branches + b, legs + l, empty + e + int(not child['items'])
        return first, last, nullable, branches, legs, empty
    nullable = True
    for child in tree['items']:
        a, z, n, b, l, e = _frontiers(child)
        if nullable:
            first.extend(a)
        if n:
            last.extend(z)
        else:
            last = z
        nullable = nullable and n
        branches, legs, empty = branches + b, legs + l, empty + e
    return first, last, nullable, branches, legs, empty


def _access_gap(operand: dict[str, Any]) -> bool:
    return (operand['role'] == 'read' and operand['binding_status'] not in {'root_bound', 'literal', 'system_flag'}
            or operand['role'] in {'write', 'read_write'} and operand['binding_status'] != 'root_bound')


def _derive(inventory: InventoryResult, access: AccessResult) -> RungAnalysisResult:
    if (len(inventory.rungs) > MAX_RECORDS or len(access.instructions) > MAX_RECORDS
            or len(access.operands) > MAX_RECORDS or len(access.expression_uses) > MAX_RECORDS):
        _limit()
    instructions = {row['id']: row for row in access.instructions}
    operands = {row['id']: row for row in access.operands}
    expressions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for use in access.expression_uses:
        expressions[use['instruction_id']].append(use)
    entities = {entity.id: entity for entity in inventory.entities}
    ambiguous_comments = {d.source_id for d in inventory.diagnostics
                          if d.code == 'descriptive_text_ambiguous' and d.message.startswith('Comment ')}
    coverage = {key: dict.fromkeys(sorted(values), 0) for key, values in COUNT_MAPS.items()}
    coverage.update(dict.fromkeys(sorted(COVERAGE_KEYS - COUNT_MAPS.keys()), 0))
    coverage.update(source_rungs=len(inventory.rungs), source_instructions=len(access.instructions),
                    source_operands=len(access.operands), expression_uses=len(access.expression_uses),
                    unknown_role_operands=access.coverage['operands_by_role']['unknown'])
    rung_rows: list[dict[str, Any]] = []
    blocks: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    retained = evidence_count = hint_characters = 0
    hint_cache: dict[str, set[str]] = {}

    def charge(record: dict[str, Any]) -> None:
        nonlocal retained, evidence_count
        # Charge before retaining each bounded record, including repeated ID
        # links. No source string or expanded alias suffix is copied here.
        stack = [record]
        while stack:
            item = stack.pop()
            if type(item) is dict:
                retained += sum(len(k) + 8 for k in item)
                stack.extend(item.values())
            elif type(item) is list:
                evidence_count += len(item)
                stack.extend(item)
            elif type(item) is str:
                retained += len(item) + 6
            else:
                retained += 8
            if retained > MAX_RUNG_ANALYSIS_BYTES or evidence_count > MAX_EVIDENCE_IDS:
                _limit()

    def hints(identifier: str, texts: tuple[str | None, ...]) -> set[str]:
        nonlocal hint_characters
        if identifier not in hint_cache:
            matched: set[str] = set()
            for text in texts:
                if not text:
                    continue
                hint_characters += len(text)
                if hint_characters > MAX_HINT_CHARACTERS:
                    _limit()
                # Whole lexical words only: e.g. 'pumpkin' does not mean pump.
                for token in re.finditer(r'[^\W\d_]+', text.casefold(), re.UNICODE):
                    for category, words in _HINTS.items():
                        if token.group() in words:
                            matched.add(category)
            hint_cache[identifier] = matched
        return hint_cache[identifier]

    for rung in inventory.rungs:
        local_blocks: list[dict[str, Any]] = []
        local_operands: list[dict[str, Any]] = []
        local_uses: list[dict[str, Any]] = []
        candidate_ids: list[str] = []
        grouped: dict[tuple[str, str], list[str]] = defaultdict(list)

        def candidate(category: str, basis: str, rule: str, ids: list[str], reason: str,
                      missing: list[str]) -> None:
            if len(candidates) >= MAX_RECORDS:
                _limit()
            identifier = 'rung-candidate:' + hashlib.sha256(f'{rung.id}|{rule}'.encode()).hexdigest()
            record = {'id': identifier, 'rung_id': rung.id, 'category': category, 'basis': basis,
                      'rule_id': rule, 'rule_version': 1, 'evidence_ids': ids,
                      'reason': reason, 'missing_evidence': missing, 'review_status': 'unreviewed'}
            charge(record)
            candidates.append(record)
            candidate_ids.append(identifier)
            coverage['candidate_categories'][category] += 1
            coverage['candidate_bases'][basis] += 1

        for instruction in rung.instructions:
            source = instructions[instruction.id]
            opcode = instruction.opcode.upper()
            family = _FAMILIES.get(opcode, 'unknown')
            identification = 'roles_known' if source['status'] == 'classified' else 'unknown'
            if opcode == 'PID' and len(instruction.arguments) == 7 and all(a.strip() for a in instruction.arguments):
                identification = 'signature_known'
            elif opcode in _MNEMONIC_ONLY:
                identification = 'known_mnemonic'
            uses = expressions[instruction.id]
            record = {'id': instruction.id, 'rung_id': rung.id, 'opcode': instruction.opcode,
                      'family': family, 'identification': identification, 'access_status': source['status'],
                      'operand_ids': list(source['operand_ids']), 'expression_use_ids': [u['id'] for u in uses]}
            charge(record)
            blocks.append(record)
            local_blocks.append(record)
            local_operands.extend(operands[i] for i in source['operand_ids'])
            local_uses.extend(uses)
            coverage['block_identification'][identification] += 1
            coverage['block_families'][family] += 1
            if identification != 'unknown' and family not in {'boolean_condition', 'unknown'}:
                basis = 'known_mnemonic' if identification == 'known_mnemonic' else 'instruction_signature'
                grouped[(family, basis)].append(instruction.id)
        for (family, basis), ids in sorted(grouped.items()):
            missing = ['engineering_purpose_unconfirmed']
            if basis == 'known_mnemonic' or family == 'pid_control':
                missing.append('instruction_effects_not_analyzed')
            candidate(family, basis, f'{family}_{basis}', ids, f'{family}_{basis}', missing)
        parsed = rung.parse_status == 'parsed'
        first, last, nullable, branches, legs, empty = _frontiers(rung.structure) if parsed else ([], [], False, 0, 0, 0)
        structure = ('unparsed' if not parsed else 'branched' if branches else 'series' if local_blocks else 'empty')
        unknown = [b['id'] for b in local_blocks if b['identification'] in {'unknown', 'known_mnemonic'}]
        gaps = [o['id'] for o in local_operands if _access_gap(o)]
        expression_gaps = [u['id'] for u in local_uses if u['binding_status'] != 'root_bound']
        syntax_gap = any(o['role'] == 'expression_read' and o['binding_status'] == 'unsupported_expression'
                         for o in local_operands)
        identification = ('unparsed' if not parsed else 'empty' if not local_blocks else
                          'unidentified' if len(unknown) == len(local_blocks) else
                          'partial' if unknown or gaps or expression_gaps or syntax_gap else 'identified')
        comment = 'ambiguous' if rung.id in ambiguous_comments else 'present' if rung.comment and rung.comment.strip() else 'absent'
        missing_metadata = [name for name in ('number', 'type') if not getattr(rung, name)]
        role_ids = {role: [] for role in sorted(OPERAND_ROLES_V4)}
        for operand in local_operands:
            role_ids[operand['role']].append(operand['id'])
        results = [o for o in local_operands if o['role'] in {'write', 'read_write'}]
        # Exact static suffixes only. Distinct members of one root remain
        # distinct; no range overlap, alias equivalence beyond canonical root,
        # data propagation, or definitely-executed output is asserted.
        # An unresolved destination is still a potential write operand, but it
        # cannot contribute a known address or a distinct address count.
        result_addresses = {(o['target_id'], o['suffix']) for o in results
                            if o['binding_status'] == 'root_bound'}
        stateful = (any(o['role'] == 'read_write' for o in results)
                    or any(b['identification'] in {'roles_known', 'signature_known'} and
                           (b['family'] in {'pid_control', 'communication_system', 'control_flow', 'sequence_control', 'alarm'}
                            or b['opcode'].upper() in {'OTL', 'OTU'}) for b in local_blocks))
        result_kind = ('stateful_or_external' if stateful else 'multiple_known_results' if len(result_addresses) > 1
                       else 'single_known_result' if result_addresses else 'no_known_result')
        outputs = [b for b in local_blocks if b['opcode'].upper() in _OUTPUTS]
        if (len(outputs) == 1 and last == [outputs[0]['id']] and not nullable
                and all(b['identification'] == 'roles_known' and b['opcode'].upper() in _CONDITIONS | _OUTPUTS
                        for b in local_blocks)):
            effect = {'OTE': 'assign', 'OTL': 'latch', 'OTU': 'unlatch'}[outputs[0]['opcode'].upper()]
            candidate('boolean_output', 'structural_pattern', f'boolean_{effect}',
                      [b['id'] for b in local_blocks], f'conditional_boolean_{effect}' if len(local_blocks) > 1 else f'boolean_{effect}',
                      ['execution_not_simulated', 'engineering_purpose_unconfirmed'])
        io: dict[str, list[str]] = defaultdict(list)
        seen_io: dict[str, set[str]] = defaultdict(set)
        pid_type_ids: list[str] = []
        text_sources: dict[str, tuple[str | None, ...]] = {rung.id: (rung.comment,) if comment == 'present' else ()}
        for row in (*local_operands, *local_uses):
            for identifier in (row['symbol_id'], row['target_id']):
                entity = entities.get(identifier)
                if entity is not None:
                    text_sources[entity.id] = (entity.name, entity.description)
            entity = entities.get(row['target_id'])
            if entity is not None and entity.attributes.get('DataType') == 'PID':
                pid_type_ids.append(row['id'])
            if entity is not None and entity.kind in {'module_input_tag', 'module_output_tag'}:
                category = 'io_input' if entity.kind == 'module_input_tag' else 'io_output'
                if row['id'] not in seen_io[category]:
                    io[category].append(row['id'])
                    seen_io[category].add(row['id'])
        for category, ids in sorted(io.items()):
            candidate(category, 'module_root', f'{category}_module_root', ids, 'declared_module_root_reference',
                      ['channel_type_not_verified', 'engineering_purpose_unconfirmed'])
        if pid_type_ids and not any(b['identification'] == 'signature_known' for b in local_blocks):
            candidate('pid_control', 'declaration_type', 'pid_declared_structure', pid_type_ids,
                      'declared_pid_structure_reference',
                      ['pid_execution_not_established', 'engineering_purpose_unconfirmed'])
        text_groups: dict[str, list[str]] = defaultdict(list)
        for identifier, texts in text_sources.items():
            for category in sorted(hints(identifier, texts)):
                text_groups[category].append(identifier)
        for category, ids in sorted(text_groups.items()):
            candidate(category, 'text_hint', f'{category}_text_hint', ids, 'whole_word_name_or_comment_hint',
                      ['name_or_comment_is_not_behavior', 'engineering_purpose_unconfirmed'])
        if local_blocks and not candidate_ids:
            candidate('miscellaneous', 'structural_pattern', 'unassigned_rung_function',
                      [b['id'] for b in local_blocks], 'no_supported_function_candidate', ['engineering_purpose_unconfirmed'])
        record = {'id': rung.id, 'structure': structure, 'identification': identification, 'comment_status': comment,
                  'missing_metadata': missing_metadata, 'block_ids': [b['id'] for b in local_blocks],
                  'first_block_ids': first, 'last_block_ids': last, 'nullable': nullable,
                  'branch_count': branches, 'branch_legs': legs, 'empty_legs': empty,
                  'operand_ids_by_role': role_ids, 'expression_use_ids': [u['id'] for u in local_uses],
                  'access_gap_operand_ids': gaps, 'expression_gap_use_ids': expression_gaps,
                  'unknown_block_ids': unknown, 'result_kind': result_kind,
                  'result_operand_ids': [o['id'] for o in results], 'candidate_ids': candidate_ids}
        charge(record)
        rung_rows.append(record)
        for group, value in (('structures', structure), ('identification', identification), ('comments', comment), ('results', result_kind)):
            coverage[group][value] += 1
        for key, count in (('unknown_blocks', len(unknown)), ('access_gap_operands', len(gaps)),
                           ('expression_gap_uses', len(expression_gaps)), ('branches', branches), ('branch_legs', legs),
                           ('empty_legs', empty), ('missing_number', int('number' in missing_metadata)),
                           ('missing_type', int('type' in missing_metadata))):
            coverage[key] += count
    coverage['candidates_total'] = len(candidates)
    partial = any(coverage['identification'][s] for s in ('partial', 'unidentified', 'unparsed'))
    return RungAnalysisResult(dict(inventory.snapshot), 'partial' if partial else 'complete',
                              rung_rows, blocks, candidates, coverage)


def analyze_rungs(snapshot: SourceSnapshot, inventory: InventoryResult, references: ReferenceResult,
                  access: AccessResult, calculations: CalculationResult) -> RungAnalysisResult:
    """Authenticate all inputs before deriving one record per source rung/block."""
    try:
        if type(access) is not AccessResult or type(access.schema_version) is not int or access.schema_version != 4:
            _invalid()
        validate_access(inventory, references, access, snapshot=snapshot, calculations=calculations)
        result = _derive(inventory, access)
        render_rung_analysis_json(result)
        return result
    except RungAnalysisError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def validate_rung_analysis(snapshot: SourceSnapshot, inventory: InventoryResult, references: ReferenceResult,
                           access: AccessResult, calculations: CalculationResult, result: RungAnalysisResult) -> None:
    """Reject any deviation from a fresh derivation, including reordering."""
    try:
        if type(result) is not RungAnalysisResult:
            _invalid()
        expected = analyze_rungs(snapshot, inventory, references, access, calculations)
        if not _strict_record_match(vars(expected), vars(result)):
            _invalid()
    except RungAnalysisError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError):
        _invalid()


def render_rung_analysis_json(result: RungAnalysisResult) -> str:
    """Render bounded native records; source authentication is separate."""
    try:
        if type(result) is not RungAnalysisResult or vars(result).keys() != set(RungAnalysisResult.__dataclass_fields__):
            _invalid()
        data = vars(result)
        stack = [iter((data,))]
        exhausted = object()
        budget = MAX_RUNG_ANALYSIS_BYTES
        while stack:
            item = next(stack[-1], exhausted)
            if item is exhausted:
                stack.pop()
                continue
            budget -= 1
            if budget < 0 or len(stack) > 12:
                _limit()
            if type(item) is dict:
                if any(type(k) is not str for k in item):
                    _invalid()
                budget -= sum(map(len, item))
                stack.append(iter(item.values()))
            elif type(item) is list:
                if len(item) > MAX_RECORDS:
                    _limit()
                stack.append(iter(item))
            elif type(item) is str:
                budget -= len(item)
            elif type(item) not in {int, bool, type(None)}:
                _invalid()
            if budget < 0:
                _limit()
        output, size = StringIO(), 0
        for chunk in json.JSONEncoder(ensure_ascii=True, sort_keys=True, indent=2).iterencode(data):
            size += len(chunk)
            if size + 1 > MAX_RUNG_ANALYSIS_BYTES:
                _limit()
            output.write(chunk)
        output.write('\n')
        return output.getvalue()
    except RungAnalysisError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()
