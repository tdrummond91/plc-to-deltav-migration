"""Numbered navigation stays in natural order across page boundaries."""
from __future__ import annotations

import unittest

from plc_workbench.workspace_application import ApplicationIndex
from plc_workbench.workspace_field_signals import FieldSignalIndex
from plc_workbench.workspace_sorting import natural_key
from test_workspace_field_io import build, field_inputs, module, query


class WorkspaceNaturalOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.channels = [2, 8, 9, 10, 11]
        leaves = ''.join(f'<DataValueMember Name="Ch{i}Data" DataType="REAL" '
                         'Radix="Float" Value="0.0"/>' for i in (11, 2, 10, 9, 8))
        modules = ''.join(module(f'Card{i}', i, 'INVENTED', data=leaves) for i in range(26, 0, -1))
        cls.captured = field_inputs(('MOV(Local:8:I.Ch11Data,InternalReal);',
                                    'MOV(Local:8:I.Ch2Data,InternalReal);'), modules=modules)
        cls.io = build(cls.captured)
        cls.signals = FieldSignalIndex(cls.io)
        cls.app = ApplicationIndex(cls.io)

    def test_card_names_sort_before_module_pagination(self) -> None:
        pages = [self.io.view(query(query='Card', page=page))['modules'] for page in (1, 2)]
        self.assertEqual([len(page['items']) for page in pages], [24, 2])
        self.assertEqual([row['name'] for page in pages for row in page['items']],
                         [f'Card{i}' for i in range(1, 27)])
        pages = [self.app.view({'run_id': 'invented-run', 'query': 'Card',
                              'page_size': 10, 'module_page': page})['modules'] for page in (1, 2, 3)]
        self.assertEqual([row['name'] for page in pages for row in page['items']],
                         [f'Card{i}' for i in range(1, 27)])

    def test_signal_order_is_global_and_keeps_bindings_and_source_order(self) -> None:
        source_order = [rung.id for rung in self.captured[1].rungs]
        all_rows = self.signals.view({'run_id': 'invented-run', 'field_type': 'ai',
                                     'page_size': 500})['signals']['items']
        small_rows = [row for page in range(1, 14)
                      for row in self.signals.view({'run_id': 'invented-run', 'field_type': 'ai',
                                                   'page_size': 10, 'page': page})['signals']['items']]
        expected = [f'Local:{slot}:I.Ch{channel}Data' for slot in range(1, 27) for channel in self.channels]
        self.assertEqual([row['address'] for row in all_rows], expected)
        self.assertEqual([row['id'] for row in small_rows], [row['id'] for row in all_rows])
        self.assertEqual(len({row['id'] for row in small_rows}), 130)
        self.assertTrue(all(row['binding'] == self.signals.anchor(row['id']) for row in small_rows))
        self.assertEqual(list(self.io.base._rungs), source_order)

    def test_address_members_sort_naturally_in_both_readonly_views(self) -> None:
        card = next(row for row in self.io.modules.values() if row['name'] == 'Card8')
        rows = self.io.view(query(module_id=card['id']))['addresses']['items']
        expected = [f'Local:8:I.Ch{i}Data' for i in self.channels]
        self.assertEqual([row['address'] for row in rows if row['direction'] == 'input' and row['suffix']], expected)
        rows = self.app.view({'run_id': 'invented-run', 'query': 'Local:8:I.Ch'})['registers']['items']
        self.assertEqual([row['address'] for row in rows], expected)

    def test_multiple_numbers_case_and_padding_keep_distinct_names(self) -> None:
        names = ['R10:2:I.Ch8Data', 'r9:10:I.Ch2Data', 'R9:2:I.Ch11Data', 'R9:2:I.Ch9Data']
        self.assertEqual(sorted(names, key=natural_key),
                         ['R9:2:I.Ch9Data', 'R9:2:I.Ch11Data', 'r9:10:I.Ch2Data', 'R10:2:I.Ch8Data'])
        # Padding is a stable tie-break, never an identity normalization.
        self.assertEqual(sorted(['Point8', 'Point10', 'Point08', 'Point9'], key=natural_key),
                         ['Point08', 'Point8', 'Point9', 'Point10'])


if __name__ == '__main__':
    unittest.main()
