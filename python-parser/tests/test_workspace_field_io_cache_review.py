"""The shared field-I/O/variable cache releases evidence from older runs."""
from __future__ import annotations

import gc
from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest
import weakref

from plc_workbench.workspace import Workspace
from test_workspace_field_io import field_inputs, module
from test_workspace_map_api import save_map_inputs


class FieldIOCacheReviewTests(unittest.TestCase):
    def test_three_run_eviction_releases_both_projection_and_authenticated_base(self):
        # LIFO cleanup closes SQLite before removing its Windows directory,
        # including when an assertion fails midway through historical reads.
        with ExitStack() as cleanup:
            folder = cleanup.enter_context(tempfile.TemporaryDirectory())
            root = Path(folder)
            runs = root / 'runs'
            sources = [field_inputs(modules=module(f'InventedCard{i}', 1, '1756-IB16'))
                       for i in range(3)]
            saved = [save_map_inputs(runs, source) for source in sources]
            workspace = Workspace(root / 'project.sqlite', runs)
            cleanup.callback(workspace.close)
            identifiers = []
            for path in saved:
                state = workspace.import_run(str(path), workspace.store.state()['revision'])
                identifier = state['active_run']
                identifiers.append(identifier)
                self.assertTrue(workspace.field_io({'run_id': identifier})['available'])
                if len(identifiers) == 1:
                    first_base = weakref.ref(workspace._variable_cache[identifier])
                    first_projection = weakref.ref(workspace._field_io_cache[identifier])
            gc.collect()
            self.assertIsNone(first_base())
            self.assertIsNone(first_projection())
            self.assertNotIn(identifiers[0], workspace._variable_cache)
            self.assertNotIn(identifiers[0], workspace._field_io_cache)

            # Reopening historical variable help may evict another run, but it
            # must neither strand a field projection nor switch the active run.
            before = workspace.store.state()
            changes = workspace.store.connection.total_changes
            for index in (0, 1, 2, 0):
                identifier = identifiers[index]
                instruction = sources[index][1].rungs[0].instructions[0]
                workspace.variable({'run_id': identifier, 'instruction_id': instruction.id,
                                    'variable': 'InputAlias'})
                self.assertTrue(workspace.field_io({'run_id': identifier})['available'])
                self.assertLessEqual(len(workspace._variable_cache), 2)
                self.assertLessEqual(len(workspace._field_io_cache), 2)
                self.assertLessEqual(set(workspace._field_io_cache), set(workspace._variable_cache))
                self.assertIs(workspace._field_io_cache[identifier].base,
                              workspace._variable_cache[identifier])
            self.assertEqual(workspace.store.state(), before)
            self.assertEqual(workspace.store.connection.total_changes, changes)


if __name__ == '__main__':
    unittest.main()
