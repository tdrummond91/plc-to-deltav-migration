"""Invented fixed byte footprints do not depend on saved runtime values."""
from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import patch

from plc_workbench.workspace_usage_ranges import UsageRangeResolver
from plc_workbench.workspace_variables import VariableIndex
from test_workspace_field_io import field_inputs, module
from test_workspace_variables import wire


def array_data(datatype: str = 'DINT', dimensions: str = '8', indices=(0, 1, 2, 3, 4, 5, 6, 7)) -> str:
    elements = ''.join(f'<Element Index="[{index}]" Value="0"/>' for index in indices)
    return (f'<ArrayMember Name="Data" DataType="{datatype}" Dimensions="{dimensions}">{elements}</ArrayMember>'
            '<DataValueMember Name="Fault" DataType="DINT" Value="0"/>')


def setup(text: str, *, source_type: str = 'DINT', destination_type: str = 'DINT',
          data: str | None = None, extra_tags: str = '', card_extra: str = ''):
    cards = module('ArrayCard', 1, 'INVENTED', data=data or array_data(source_type), extra=card_extra)
    captured = field_inputs((text,), modules=cards, extra_tags=(
        f'<Tag Name="Buffer" DataType="{destination_type}" Dimensions="8"/>' + extra_tags))
    values = wire(captured)
    base = VariableIndex(*values)
    return UsageRangeResolver(base), values


def descriptor(resolver: UsageRangeResolver, slot: int = 0) -> dict:
    ref = next(ref for ref in resolver.base._references.operands if ref['argument_index'] == slot)
    rung = resolver.base._rungs[ref['rung_id']]
    binding = resolver.base._resolve(ref['raw_text'].strip(), rung.scope_id)
    return resolver.resolve(ref, binding)


def matched(resolver: UsageRangeResolver, span: dict, suffix: str) -> dict:
    return resolver.match(span, {'root_id': span['root_id'], 'suffix': suffix})


class UsageRangeTests(unittest.TestCase):
    def test_fill_reads_one_source_element_even_when_filling_several_destination_elements(self) -> None:
        resolver, _ = setup('FLL(Local:1:I.Data[1],Buffer[0],4);', destination_type='INT')
        span = descriptor(resolver, 0)
        self.assertEqual(span['status'], 'resolved')
        self.assertEqual(span['role'], 'read')
        self.assertEqual(span['byte_count'], 4)
        self.assertEqual(matched(resolver, span, '.Data[1]')['status'], 'included')
        self.assertEqual(matched(resolver, span, '.Data[1].31')['status'], 'included')
        self.assertEqual(matched(resolver, span, '.Data[2]')['status'], 'excluded')
        self.assertIn('One source value', span['explanation'])

    def test_cop_cps_fixed_nonzero_array_starts_exclude_siblings_and_preserve_source(self) -> None:
        for opcode in ('COP', 'CPS'):
            with self.subTest(opcode=opcode):
                resolver, inputs = setup(f'{opcode}(Local:1:I.Data[2],Buffer[3],2);')
                before = deepcopy(inputs)
                budget = resolver._budget
                span = descriptor(resolver)
                self.assertEqual(span['status'], 'resolved')
                self.assertEqual((span['length'], span['byte_count'], span['start_byte'], span['end_byte']), (2, 8, 8, 16))
                self.assertEqual(span['role'], 'read')
                for index in range(8):
                    self.assertEqual(matched(resolver, span, f'.Data[{index}]')['status'],
                                     'included' if index in {2, 3} else 'excluded')
                self.assertEqual(matched(resolver, span, '.Fault')['status'], 'excluded')
                self.assertEqual(matched(resolver, span, '.Data[02]')['status'], 'included')
                self.assertIn('8 bytes', matched(resolver, span, '.Data[2]')['explanation'])
                self.assertEqual(resolver.scalar_type(span['root_id'], '.Data[2]'), 'DINT')
                self.assertEqual(resolver._budget, budget)
                self.assertEqual(inputs, before)

    def test_copy_length_uses_destination_width_and_can_touch_partial_source_elements(self) -> None:
        resolver, _ = setup('COP(Local:1:I.Data[0],Buffer[0],2);', source_type='SINT')
        span = descriptor(resolver)
        self.assertEqual(span['byte_count'], 8)
        self.assertEqual(span['element_bytes'], 1)
        self.assertTrue(all(matched(resolver, span, f'.Data[{index}]')['status'] == 'included' for index in range(8)))
        resolver, _ = setup('COP(Local:1:I.Data[0],Buffer[0],1);', destination_type='INT')
        span = descriptor(resolver)
        self.assertEqual(span['byte_count'], 2)
        self.assertEqual(matched(resolver, span, '.Data[0]')['status'], 'included')
        self.assertEqual(matched(resolver, span, '.Data[1]')['status'], 'excluded')
        for bit in (0, 7, 8, 15):
            self.assertEqual(matched(resolver, span, f'.Data[0].{bit}')['status'], 'included')
        for bit in (16, 31):
            self.assertEqual(matched(resolver, span, f'.Data[0].{bit}')['status'], 'excluded')

    def test_fll_constant_range_and_zero_length(self) -> None:
        for length in ('2', '16#2', '+2'):
            with self.subTest(length=length):
                resolver, _ = setup(f'FLL(0,Local:1:I.Data[2],{length});')
                span = descriptor(resolver, 1)
                self.assertEqual(span['status'], 'resolved')
                self.assertEqual(span['role'], 'write')
                self.assertEqual(matched(resolver, span, '.Data[3]')['status'], 'included')
                self.assertEqual(matched(resolver, span, '.Data[4]')['status'], 'excluded')
        resolver, _ = setup('FLL(0,Local:1:I.Data[2],0);')
        span = descriptor(resolver, 1)
        self.assertEqual((span['status'], span['byte_count']), ('resolved', 0))
        self.assertEqual(matched(resolver, span, '.Data[2]')['reason'], 'zero_length')

    def test_saved_length_value_is_never_a_runtime_constant(self) -> None:
        tags = '<Tag Name="Length" DataType="DINT"><Data Format="Decorated"><DataValue DataType="DINT" Value="2"/></Data></Tag>'
        resolver, _ = setup('COP(Local:1:I.Data[0],Buffer[0],Length);', extra_tags=tags)
        span = descriptor(resolver)
        self.assertEqual(span['status'], 'unresolved')
        self.assertEqual(span['reason'], 'variable_length')
        self.assertIn('runtime length', span['explanation'])
        for text in ('-1', '1.0', '2147483648'):
            resolver, _ = setup(f'COP(Local:1:I.Data[0],Buffer[0],{text});')
            self.assertEqual(descriptor(resolver)['reason'], 'variable_length')

    def test_overrun_never_clamps_to_a_member_or_excludes_same_root_siblings(self) -> None:
        texts = ('COP(Local:1:I.Data[7],Buffer[0],2);',
                 'COP(Local:1:I.Data[0],Buffer[7],2);',
                 'FLL(0,Local:1:I.Data[7],2);',
                 'FLL(0,Local:1:I.Fault,2);')
        for text in texts:
            with self.subTest(text=text):
                resolver, _ = setup(text)
                span = descriptor(resolver, 1 if text.startswith('FLL') else 0)
                self.assertEqual((span['status'], span['reason']), ('unresolved', 'member_boundary'))
                self.assertEqual(matched(resolver, span, '.Fault')['status'], 'unresolved')
                self.assertEqual(resolver.match(span, {'root_id': 'different', 'suffix': '.Fault'})['status'], 'excluded')

    def test_declared_dimensions_handle_sparse_decorated_elements(self) -> None:
        resolver, _ = setup('COP(Local:1:I.Data[4],Buffer[0],2);', data=array_data(indices=(0, 5)))
        span = descriptor(resolver)
        self.assertEqual(span['status'], 'resolved')
        self.assertEqual(matched(resolver, span, '.Data[4]')['status'], 'included')
        self.assertEqual(matched(resolver, span, '.Data[5]')['status'], 'included')
        self.assertEqual(matched(resolver, span, '.Data[6]')['status'], 'excluded')
        resolver, _ = setup('COP(Local:1:I.Data[4],Buffer[0],2);', data=array_data(indices=()))
        span = descriptor(resolver)
        self.assertEqual(span['status'], 'resolved')
        self.assertEqual(matched(resolver, span, '.Data[5]')['status'], 'included')

    def test_aliases_are_scoped_and_resolved_before_computing_the_span(self) -> None:
        tags = '<Tag Name="Start" TagType="Alias" AliasFor="Local:1:I.Data[2]"/>'
        resolver, _ = setup('COP(Start,Buffer[0],2);', extra_tags=tags)
        span = descriptor(resolver)
        self.assertEqual((span['status'], span['start_byte']), ('resolved', 8))
        self.assertEqual(matched(resolver, span, '.Data[3]')['status'], 'included')

    def test_unqualified_conflicting_and_unknown_storage_does_not_produce_ranges(self) -> None:
        resolver, _ = setup('COP(Local:1:I.Data[0],Buffer[0],1);',
            card_extra='xmlns:x="urn:other" x:Flag="foreign"')
        self.assertEqual(descriptor(resolver)['reason'], 'unqualified_operand')
        data = array_data().replace('Index="[0]" Value="0"', 'Index="[0]" DataType="REAL" Value="0"')
        resolver, _ = setup('COP(Local:1:I.Data[0],Buffer[0],1);', data=data)
        self.assertEqual(descriptor(resolver)['reason'], 'ambiguous_layout')
        for datatype in ('BOOL', 'InventedUDT'):
            resolver, _ = setup('COP(Local:1:I.Data[0],Buffer[0],1);', data=array_data(datatype))
            self.assertEqual(descriptor(resolver)['status'], 'unresolved')
        resolver, _ = setup('COP(Local:1:I.Data[0],Buffer[0],1);', data=array_data(dimensions='2,4'))
        self.assertEqual(descriptor(resolver)['reason'], 'unsupported_layout')

    def test_supported_declaration_cannot_survive_conflicting_unsupported_decorated_type(self) -> None:
        for datatype in ('REAL', 'BOOL', 'InventedUDT'):
            with self.subTest(datatype=datatype):
                tags = ('<Tag Name="Conflicting" DataType="DINT"><Data Format="Decorated">'
                        f'<DataValue DataType="{datatype}" Value="0"/></Data></Tag>')
                resolver, _ = setup('COP(Conflicting,Buffer[0],1);', extra_tags=tags)
                span = descriptor(resolver)
                self.assertEqual((span['status'], span['reason']), ('unresolved', 'ambiguous_layout'))
                self.assertIn('Conflicting', span['explanation'])
                self.assertIsNone(resolver.scalar_type(span['root_id'], ''))

    def test_duplicate_and_foreign_decorated_layouts_are_not_selected(self) -> None:
        for data in (array_data() + array_data(),
                     array_data().replace('<ArrayMember ', '<ArrayMember xmlns:x="urn:other" x:Flag="foreign" ')):
            with self.subTest(data=data[:60]):
                resolver, _ = setup('COP(Local:1:I.Data[0],Buffer[0],1);', data=data)
                self.assertEqual(descriptor(resolver)['reason'], 'ambiguous_layout')

    def test_fill_requires_a_numeric_scalar_source_and_explains_unsupported_layouts(self) -> None:
        resolver, _ = setup('FLL(UnknownSource,Local:1:I.Data[2],2);',
            extra_tags='<Tag Name="UnknownSource" DataType="InventedUDT"/>')
        span = descriptor(resolver, 1)
        self.assertEqual(span['reason'], 'unsupported_layout')
        self.assertIn('UnknownSource', span['explanation'])
        resolver, _ = setup('FLL(InternalReal,Local:1:I.Data[2],2);')
        self.assertEqual(descriptor(resolver, 1)['status'], 'resolved')

    def test_bad_literal_index_missing_layout_and_dynamic_start_remain_explicit(self) -> None:
        resolver, _ = setup('COP(Local:1:I.Data[8],Buffer[0],1);')
        self.assertEqual(descriptor(resolver)['reason'], 'invalid_index')
        resolver, _ = setup('COP(Local:1:I.Missing[0],Buffer[0],1);')
        self.assertEqual(descriptor(resolver)['reason'], 'missing_layout')
        resolver, _ = setup('COP(Local:1:I.Data[Index],Buffer[0],1);', extra_tags='<Tag Name="Index" DataType="DINT"/>')
        self.assertEqual(descriptor(resolver)['reason'], 'unqualified_operand')
        resolver, _ = setup('COP(Local:1:I.Data,Buffer[0],1);')
        self.assertEqual(descriptor(resolver)['reason'], 'array_element_required')

    def test_scalar_destinations_and_primitive_member_types_are_available(self) -> None:
        resolver, _ = setup('FLL(0,Local:1:I.Fault,1);')
        span = descriptor(resolver, 1)
        self.assertEqual(span['status'], 'resolved')
        self.assertEqual(matched(resolver, span, '.Fault.3')['status'], 'included')
        self.assertEqual(matched(resolver, span, '.Data[0]')['status'], 'excluded')
        self.assertEqual(resolver.scalar_type(span['root_id'], '.Fault'), 'DINT')
        self.assertIsNone(resolver.scalar_type(span['root_id'], '.Data'))

    def test_limits_fail_closed_and_return_detached_descriptors(self) -> None:
        with patch('plc_workbench.workspace_usage_ranges.MAX_LAYOUT_BYTES', 1):
            resolver, _ = setup('COP(Local:1:I.Data[0],Buffer[0],1);')
        self.assertEqual(resolver._budget, 0)
        self.assertEqual(descriptor(resolver)['reason'], 'metadata_limit')
        resolver, _ = setup('COP(Local:1:I.Data[0],Buffer[0],1);')
        first = descriptor(resolver)
        first['start_byte'] = 100
        self.assertEqual(descriptor(resolver)['start_byte'], 0)


if __name__ == '__main__':
    unittest.main()
