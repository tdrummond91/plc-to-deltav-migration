"""Standalone synthetic checks for invocation-scoped source template reuse."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, fields, is_dataclass, replace
import unittest
from unittest.mock import patch

from plc_workbench import source, source_reuse
from plc_workbench.ladder import syntax
from plc_workbench.source_reuse import source_reuse_scope


def snapshot(name: str = 'Demo'):
    return source.snapshot_from_bytes((
        '<RSLogix5000Content SoftwareRevision="35"><Controller Name="' + name + '">'
        '<Tags><Tag Name="Input" DataType="BOOL"><Description>Invented input</Description>'
        '</Tag></Tags><Programs><Program Name="Program"><Routines>'
        '<Routine Name="Main" Type="RLL"><RLLContent><Rung Number="0" Type="N">'
        '<Comment>Invented rung</Comment><Text><![CDATA['
        'XIC(Input)[XIC(A),XIO(B)]OTE(Output);'
        ']]></Text></Rung></RLLContent></Routine></Routines></Program></Programs>'
        '</Controller></RSLogix5000Content>'
    ).encode())


def mutable_ids(value: object) -> set[int]:
    """Find every reachable mutable descendant, including frozen-record fields."""
    result: set[int] = set()
    if isinstance(value, dict):
        result.add(id(value))
        for child in value.values():
            result.update(mutable_ids(child))
    elif isinstance(value, (list, tuple, set, frozenset)):
        if isinstance(value, (list, set)):
            result.add(id(value))
        for child in value:
            result.update(mutable_ids(child))
    elif is_dataclass(value):
        for item in fields(value):
            result.update(mutable_ids(getattr(value, item.name)))
    return result


class SourceReuseTests(unittest.TestCase):
    def test_inventory_and_xml_build_once_with_equal_independent_results(self) -> None:
        captured = snapshot()
        expected = source.analyze_snapshot(captured)
        with patch.object(source, '_parse_nodes', wraps=source._parse_nodes) as xml_build, \
                patch.object(source, '_build_inventory', wraps=source._build_inventory) as inventory_build:
            with source_reuse_scope():
                first = source.analyze_snapshot(captured)
                second = source.analyze_snapshot(captured)
                third = source.analyze_snapshot(captured)
                nodes = source._read_nodes(captured.data)
            self.assertEqual(xml_build.call_count, 1)
            self.assertEqual(inventory_build.call_count, 1)
        self.assertEqual(first, expected)
        self.assertEqual(second, expected)
        self.assertEqual(third, expected)
        self.assertFalse(mutable_ids(first) & mutable_ids(second))
        self.assertFalse(mutable_ids(second) & mutable_ids(third))
        self.assertEqual(nodes[0].name, 'RSLogix5000Content')

    def test_xml_miss_and_hit_mutations_do_not_reach_template(self) -> None:
        captured = snapshot()
        expected = [asdict(node) for node in source._read_nodes(captured.data)]
        with source_reuse_scope():
            for _ in range(2):
                nodes = source._read_nodes(captured.data)
                self.assertEqual([asdict(node) for node in nodes], expected)
                node = nodes[0]
                node.name = 'changed'
                node.attributes['changed'] = 'changed'
                node.expanded_attributes['changed'] = 'changed'
                node.children.clear()
                node.parts.append('changed')
                node.child_counts['changed'] = 999
                nodes.pop()
            final = source._read_nodes(captured.data)
            another = source._read_nodes(captured.data)
        self.assertEqual([asdict(node) for node in final], expected)
        self.assertFalse(mutable_ids(final) & mutable_ids(another))
        self.assertTrue(all(left is not right for left, right in zip(final, another)))

    def test_inventory_miss_and_hit_mutations_do_not_reach_template(self) -> None:
        captured = snapshot()
        expected = source.analyze_snapshot(captured).to_dict()
        with source_reuse_scope():
            for _ in range(2):
                result = source.analyze_snapshot(captured)
                self.assertEqual(result.to_dict(), expected)
                result.snapshot['id'] = 'changed'
                result.export_attributes.clear()
                result.entities[0].attributes.clear()
                result.rungs[0].metrics.clear()
                result.rungs[0].instructions.clear()
                result.rungs[0].structure.clear()
                result.counts.clear()
                result.routine_types.clear()
                result.instruction_counts.clear()
                result.coverage['rungs'].clear()
                result.diagnostics.append('changed')
                result.entities.clear()
                result.rungs.clear()
            self.assertEqual(source.analyze_snapshot(captured).to_dict(), expected)

    def test_every_snapshot_identity_field_is_checked_before_hit(self) -> None:
        captured = snapshot()
        invalid = [replace(captured, id='wrong'), replace(captured, sha256='0' * 64),
                   replace(captured, size_bytes=captured.size_bytes + 1),
                   replace(captured, data=snapshot('Other').data),
                   replace(captured, data=bytearray(captured.data))]
        with source_reuse_scope(), \
                patch.object(source, '_build_inventory', wraps=source._build_inventory) as build:
            expected = source.analyze_snapshot(captured)
            for changed in invalid:
                with self.subTest(changed=changed.id), self.assertRaises(source.SourceError):
                    source.analyze_snapshot(changed)
            self.assertEqual(source.analyze_snapshot(captured), expected)
            self.assertEqual(build.call_count, 1)

    def test_all_xml_limits_invalidate_xml_and_inventory(self) -> None:
        captured = snapshot()
        for name in ('MAX_SOURCE_BYTES', 'MAX_ELEMENTS', 'MAX_ATTRIBUTES',
                     'MAX_DEPTH', 'MAX_DIRECT_TEXT'):
            with self.subTest(limit=name), source_reuse_scope(), \
                    patch.object(source, '_parse_nodes', wraps=source._parse_nodes) as xml_build, \
                    patch.object(source, '_build_inventory', wraps=source._build_inventory) as inventory_build:
                expected = source.analyze_snapshot(captured)
                with patch.object(source, name, getattr(source, name) + 1):
                    self.assertEqual(source.analyze_snapshot(captured), expected)
                self.assertEqual(xml_build.call_count, 2)
                self.assertEqual(inventory_build.call_count, 2)

    def test_stricter_xml_limits_and_source_size_are_not_bypassed(self) -> None:
        captured = snapshot()
        with source_reuse_scope():
            source.analyze_snapshot(captured)
            for name, value in (('MAX_SOURCE_BYTES', len(captured.data) - 1),
                                ('MAX_ELEMENTS', 1), ('MAX_ATTRIBUTES', 0),
                                ('MAX_DEPTH', 1), ('MAX_DIRECT_TEXT', 1)):
                with self.subTest(limit=name), patch.object(source, name, value), \
                        self.assertRaises(source.SourceError):
                    source.analyze_snapshot(captured)
            self.assertEqual(source.analyze_snapshot(captured).status, 'complete')

    def test_all_rung_limits_invalidate_inventory_but_reuse_xml(self) -> None:
        captured = snapshot()
        for name in ('MAX_TEXT', 'MAX_DEPTH', 'MAX_NODES',
                     'MAX_BRANCH_LEGS', 'MAX_ARGUMENT_SLOTS'):
            with self.subTest(limit=name), source_reuse_scope(), \
                    patch.object(source, '_parse_nodes', wraps=source._parse_nodes) as xml_build, \
                    patch.object(source, '_build_inventory', wraps=source._build_inventory) as inventory_build:
                expected = source.analyze_snapshot(captured)
                with patch.object(syntax, name, getattr(syntax, name) + 1):
                    self.assertEqual(source.analyze_snapshot(captured), expected)
                self.assertEqual(xml_build.call_count, 1)
                self.assertEqual(inventory_build.call_count, 2)

    def test_stricter_rung_policy_preserves_failed_parse_result(self) -> None:
        captured = snapshot()
        with source_reuse_scope():
            self.assertEqual(source.analyze_snapshot(captured).status, 'complete')
            with patch.object(syntax, 'MAX_TEXT', 1):
                result = source.analyze_snapshot(captured)
                self.assertEqual(result.status, 'partial')
                self.assertEqual(result.rungs[0].parse_status, 'failed')
                self.assertEqual(source.analyze_snapshot(captured), result)
            self.assertEqual(source.analyze_snapshot(captured).status, 'complete')

    def test_expression_policy_is_also_part_of_inventory_key(self) -> None:
        captured = snapshot()
        with source_reuse_scope():
            before = source.analyze_snapshot(captured)
            with patch.object(syntax, 'EXPRESSION_OPCODES', frozenset({'XIC'})):
                after = source.analyze_snapshot(captured)
            self.assertEqual(before.rungs[0].metrics['expression_instruction_calls'], 0)
            self.assertEqual(after.rungs[0].metrics['expression_instruction_calls'], 2)

    def test_second_source_bypasses_without_displacing_pinned_source(self) -> None:
        first, second = snapshot(), snapshot('Other')
        with source_reuse_scope(), \
                patch.object(source, '_parse_nodes', wraps=source._parse_nodes) as xml_build, \
                patch.object(source, '_build_inventory', wraps=source._build_inventory) as inventory_build:
            expected = source.analyze_snapshot(first)
            different = source.analyze_snapshot(second)
            self.assertNotEqual(expected.snapshot, different.snapshot)
            self.assertEqual(source.analyze_snapshot(second), different)
            self.assertEqual(source.analyze_snapshot(first), expected)
            self.assertEqual(xml_build.call_count, 3)
            self.assertEqual(inventory_build.call_count, 3)

    def test_xml_failure_is_not_cached_or_pinned(self) -> None:
        captured = snapshot()
        nodes = source._read_nodes(captured.data)
        with source_reuse_scope(), patch.object(
                source, '_parse_nodes', side_effect=[source.SourceError('failed'), nodes]) as build:
            with self.assertRaises(source.SourceError):
                source._read_nodes(captured.data)
            state = source_reuse._ACTIVE.get()
            self.assertIsNone(state.data)
            self.assertFalse(state.entries)
            self.assertFalse(state.rejected)
            source._read_nodes(captured.data)
            source._read_nodes(captured.data)
            self.assertEqual(build.call_count, 2)

    def test_non_native_bytes_bypass_without_matching_or_displacing_normal_source(self) -> None:
        class HostileBytes(bytes):
            def __eq__(self, other: object) -> bool:
                return True

            def __ne__(self, other: object) -> bool:
                return False

        first, second = snapshot(), snapshot('Other')
        expected_other = source.analyze_snapshot(second)
        hostile = replace(second, data=HostileBytes(second.data))
        buffer = bytearray(second.data)
        with source_reuse_scope(), \
                patch.object(source, '_parse_nodes', wraps=source._parse_nodes) as xml_build, \
                patch.object(source, '_build_inventory', wraps=source._build_inventory) as inventory_build:
            expected_first = source.analyze_snapshot(first)
            for _ in range(2):
                result = source.analyze_snapshot(hostile)
                self.assertEqual(result, expected_other)
                self.assertNotEqual(result.snapshot, expected_first.snapshot)
            nodes_before = source._read_nodes(buffer)
            buffer[:] = buffer.replace(b'Other', b'Third')
            nodes_after = source._read_nodes(buffer)
            self.assertEqual(next(node for node in nodes_before if node.name == 'Controller')
                             .attributes['Name'], 'Other')
            self.assertEqual(next(node for node in nodes_after if node.name == 'Controller')
                             .attributes['Name'], 'Third')
            # Inventory's existing immutable-snapshot validation remains intact.
            with self.assertRaises(source.SourceError):
                source.analyze_snapshot(replace(second, data=buffer))
            self.assertEqual(source.analyze_snapshot(first), expected_first)
            self.assertEqual(xml_build.call_count, 5)
            self.assertEqual(inventory_build.call_count, 3)
            self.assertIs(source_reuse._ACTIVE.get().data, first.data)

    def test_inventory_failure_is_not_cached_or_pinned(self) -> None:
        captured = snapshot()
        expected = source.analyze_snapshot(captured)
        with source_reuse_scope(), patch.object(
                source, '_build_inventory', side_effect=[source.SourceError('failed'), expected]) as build:
            with self.assertRaises(source.SourceError):
                source.analyze_snapshot(captured)
            state = source_reuse._ACTIVE.get()
            self.assertIsNone(state.data)
            self.assertFalse(state.entries)
            self.assertFalse(state.rejected)
            self.assertEqual(source.analyze_snapshot(captured), expected)
            self.assertEqual(source.analyze_snapshot(captured), expected)
            self.assertEqual(build.call_count, 2)

    def test_no_scope_zero_and_tiny_budget_always_compute(self) -> None:
        captured = snapshot()
        with patch.object(source, '_parse_nodes', wraps=source._parse_nodes) as xml_build, \
                patch.object(source, '_build_inventory', wraps=source._build_inventory) as inventory_build:
            for _ in range(2):
                source.analyze_snapshot(captured)
            for budget in (0, 1, source_reuse._SCOPE_RESERVE_BYTES - 1):
                with source_reuse_scope(max_bytes=budget):
                    for _ in range(2):
                        source.analyze_snapshot(captured)
                    state = source_reuse._ACTIVE.get()
                    self.assertIsNone(state.data)
                    self.assertFalse(state.entries)
                    self.assertFalse(state.rejected)
            self.assertEqual(xml_build.call_count, 8)
            self.assertEqual(inventory_build.call_count, 8)

    def test_oversized_xml_keeps_only_bounded_marker_and_skips_repeat_sizing(self) -> None:
        captured = snapshot()
        budget = source_reuse._SCOPE_RESERVE_BYTES + 2048
        with source_reuse_scope(max_bytes=budget), \
                patch.object(source_reuse, '_graph_size', wraps=source_reuse._graph_size) as size:
            source._read_nodes(captured.data)
            calls = size.call_count
            source._read_nodes(captured.data)
            self.assertEqual(size.call_count, calls)
            state = source_reuse._ACTIVE.get()
            self.assertIsNone(state.data)
            self.assertFalse(state.entries)
            self.assertEqual(set(state.rejected), {'xml'})
            self.assertIsNotNone(state.size(state.data, state.entries, state.rejected))
            self.assertNotIn(captured.data, state.rejected['xml'])

    def test_inventory_priority_evicts_xml_and_xml_cannot_evict_inventory(self) -> None:
        captured = snapshot()
        with source_reuse_scope():
            source.analyze_snapshot(captured)
            state = source_reuse._ACTIVE.get()
            inventory_size = state.size(state.data, {'inventory': state.entries['inventory']}, {})
            combined_size = state.size(state.data, state.entries, {})
        self.assertGreater(combined_size, inventory_size + 512)
        budget = inventory_size + 512
        with source_reuse_scope(max_bytes=budget), \
                patch.object(source, '_build_inventory', wraps=source._build_inventory) as build:
            expected = source.analyze_snapshot(captured)
            state = source_reuse._ACTIVE.get()
            self.assertEqual(set(state.entries), {'inventory'})
            source._read_nodes(captured.data)
            self.assertEqual(set(state.entries), {'inventory'})
            self.assertEqual(source.analyze_snapshot(captured), expected)
            self.assertEqual(build.call_count, 1)
            self.assertIsNotNone(state.size(state.data, state.entries, state.rejected))

    def test_large_source_key_cannot_pin_bytes_when_no_entry_fits(self) -> None:
        captured = source.snapshot_from_bytes(
            b'<RSLogix5000Content><!--' + b' ' * 100_000 + b'--></RSLogix5000Content>')
        with source_reuse_scope(max_bytes=8192):
            source.analyze_snapshot(captured)
            state = source_reuse._ACTIVE.get()
            self.assertIsNone(state.data)
            self.assertFalse(state.entries)
            self.assertIsNotNone(state.size(state.data, state.entries, state.rejected))

    def test_separate_nested_and_exception_scopes_restore_and_clear(self) -> None:
        captured = snapshot()
        with patch.object(source, '_build_inventory', wraps=source._build_inventory) as build:
            with source_reuse_scope():
                source.analyze_snapshot(captured)
                outer = source_reuse._ACTIVE.get()
                with self.assertRaisesRegex(RuntimeError, 'synthetic'):
                    with source_reuse_scope():
                        source.analyze_snapshot(captured)
                        inner = source_reuse._ACTIVE.get()
                        raise RuntimeError('synthetic')
                self.assertIs(source_reuse._ACTIVE.get(), outer)
                self.assertIsNone(inner.data)
                self.assertFalse(inner.entries)
                source.analyze_snapshot(captured)
            self.assertIsNone(source_reuse._ACTIVE.get())
            self.assertIsNone(outer.data)
            self.assertFalse(outer.entries)
            self.assertFalse(outer.rejected)
            with source_reuse_scope():
                source.analyze_snapshot(captured)
            source.analyze_snapshot(captured)
            self.assertEqual(build.call_count, 4)

    def test_disabled_nested_scope_does_not_use_or_clear_parent(self) -> None:
        captured = snapshot()
        with source_reuse_scope(), \
                patch.object(source, '_build_inventory', wraps=source._build_inventory) as build:
            source.analyze_snapshot(captured)
            with source_reuse_scope(max_bytes=0):
                source.analyze_snapshot(captured)
                source.analyze_snapshot(captured)
            source.analyze_snapshot(captured)
            self.assertEqual(build.call_count, 3)

    def test_unknown_graph_types_fall_back_without_retaining_templates(self) -> None:
        class Unsupported:
            pass
        @dataclass(slots=True)
        class SlottedRecord:
            value: int = 1
        class ExtendedList(list):
            pass
        for build in (Unsupported, SlottedRecord, ExtendedList):
            with self.subTest(kind=build.__name__), source_reuse_scope():
                result = source_reuse._reuse_source('xml', b'synthetic', (), build, deepcopy)
                self.assertIsInstance(result, build)
                state = source_reuse._ACTIVE.get()
                self.assertIsNone(state.data)
                self.assertFalse(state.entries)

    def test_invalid_budgets_fail_before_changing_active_scope(self) -> None:
        with source_reuse_scope():
            outer = source_reuse._ACTIVE.get()
            for invalid in (-1, True, 1.0, None, source_reuse.MAX_REUSE_BYTES + 1):
                with self.subTest(budget=invalid), self.assertRaises(ValueError):
                    with source_reuse_scope(max_bytes=invalid):
                        self.fail('invalid budget entered')
                self.assertIs(source_reuse._ACTIVE.get(), outer)


if __name__ == '__main__':
    unittest.main()
