"""Repository-helper compatibility alias for the installed shared grammar.

Inspection scripts can run directly from this repository without installation.
The application grammar has no dependency on these helpers. Alias the module
itself, rather than copying exports, so callers patching parser limits continue
to change the globals actually used by the parser.
"""
from pathlib import Path
import sys

_source_root = Path(__file__).resolve().parents[3] / "python-parser" / "src"
if str(_source_root) not in sys.path:
    sys.path.insert(0, str(_source_root))

from plc_workbench.ladder import syntax as _shared_syntax  # noqa: E402

sys.modules[__name__] = _shared_syntax
