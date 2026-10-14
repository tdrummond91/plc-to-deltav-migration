"""Locate a real GUI Python executable, rejecting console-subsystem shims.

Some virtual environments name their console redirector ``pythonw.exe``. The
filename alone therefore cannot establish that Task Scheduler will launch it
without a Terminal window. Use the underlying interpreter's GUI binary instead;
the listener and its host use only the standard library.
"""
from __future__ import annotations

import os
from pathlib import Path
import struct
import sys

WINDOWS_GUI_SUBSYSTEM = 2


def pe_subsystem(path: Path) -> int:
    """Read the PE subsystem after checking its DOS, COFF and optional headers.

    This checks the relevant header structure, not executable authenticity.
    Layout: https://learn.microsoft.com/en-us/windows/win32/debug/pe-format
    """
    def invalid() -> ValueError:
        return ValueError("Invalid Windows executable header")

    with path.open("rb") as stream:
        size = os.fstat(stream.fileno()).st_size
        dos = stream.read(64)
        if len(dos) != 64 or dos[:2] != b"MZ":
            raise invalid()
        offset = struct.unpack_from("<I", dos, 60)[0]
        if offset < 64 or offset + 24 > size:
            raise invalid()
        stream.seek(offset)
        header = stream.read(24)
        if len(header) != 24 or header[:4] != b"PE\0\0":
            raise invalid()
        optional_size, characteristics = struct.unpack_from("<HH", header, 20)
        if not characteristics & 0x0002 or characteristics & 0x2000:
            raise invalid()  # Executable image required; a DLL is not a launcher.
        if optional_size < 96 or offset + 24 + optional_size > size:
            raise invalid()
        optional = stream.read(optional_size)
        if len(optional) != optional_size:
            raise invalid()
        magic = struct.unpack_from("<H", optional)[0]
        minimum = {0x10B: 96, 0x20B: 112}.get(magic)
        if minimum is None or len(optional) < minimum:
            raise invalid()
        return struct.unpack_from("<H", optional, 68)[0]


def resolve_windowless_python() -> Path:
    """Find the GUI interpreter underlying this environment, or fail closed."""
    candidates = [Path(sys.base_prefix) / "pythonw.exe"]
    base_executable = getattr(sys, "_base_executable", None)
    if base_executable:
        candidates.append(Path(base_executable).parent / "pythonw.exe")
    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=True)
            if resolved in seen:
                continue
            seen.add(resolved)
            if pe_subsystem(resolved) == WINDOWS_GUI_SUBSYSTEM:
                return resolved
        except (OSError, ValueError):
            continue
    raise OSError(
        "No GUI-subsystem pythonw.exe was found for this interpreter. "
        "Install Python with its windowed interpreter; a console shim is not safe for the listener."
    )


def main() -> int:
    try:
        print(resolve_windowless_python())
    except OSError as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
