"""Include the local listener's Git integration tests in the work-check suite."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


def load_tests(loader: unittest.TestLoader, _tests: unittest.TestSuite,
               _pattern: str | None) -> unittest.TestSuite:
    path = Path(__file__).resolve().parents[2] / 'tools/feedback_listener/tests/test_listener.py'
    specification = importlib.util.spec_from_file_location('test_feedback_listener_cases', path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return loader.loadTestsFromModule(module)
