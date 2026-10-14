"""Include the local listener's Git integration tests in the work-check suite."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


def load_tests(loader: unittest.TestLoader, _tests: unittest.TestSuite,
               _pattern: str | None) -> unittest.TestSuite:
    directory = Path(__file__).resolve().parents[2] / 'tools/feedback_listener/tests'
    suite = unittest.TestSuite()
    for path in sorted(directory.glob('test_*.py')):
        name = f'test_feedback_listener_{path.stem}'
        specification = importlib.util.spec_from_file_location(name, path)
        assert specification is not None and specification.loader is not None
        module = importlib.util.module_from_spec(specification)
        sys.modules[specification.name] = module
        specification.loader.exec_module(module)
        suite.addTests(loader.loadTestsFromModule(module))
    return suite
