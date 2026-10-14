"""Invented PE headers and real GUI interpreter selection, without launching UI."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import windows_launcher


def executable(subsystem: int, *, magic: int = 0x20B, characteristics: int = 2) -> bytes:
    """Build just the invented headers inspected by the launcher resolver."""
    data = bytearray(64 + 24 + 112)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 60, 64)
    data[64:68] = b"PE\0\0"
    struct.pack_into("<HH", data, 84, 112, characteristics)
    struct.pack_into("<H", data, 88, magic)
    struct.pack_into("<H", data, 88 + 68, subsystem)
    return bytes(data)


class WindowsLauncherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="plc-launcher-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.base = self.root / "base"
        self.fallback = self.root / "fallback"
        self.shim = self.root / "environment" / "Scripts" / "pythonw.exe"
        self.base.mkdir()
        self.fallback.mkdir()
        self.shim.parent.mkdir(parents=True)
        self.shim.write_bytes(executable(3))
        patches = [
            patch.object(sys, "base_prefix", str(self.base)),
            patch.object(sys, "_base_executable", str(self.fallback / "python.exe"), create=True),
            patch.object(sys, "executable", str(self.shim.with_name("python.exe"))),
        ]
        for mock in patches:
            mock.start()
            self.addCleanup(mock.stop)

    def test_gui_pe32_and_pe32_plus_headers_are_recognized(self) -> None:
        path = self.base / "pythonw.exe"
        for magic in (0x10B, 0x20B):
            with self.subTest(magic=magic):
                path.write_bytes(executable(2, magic=magic))
                self.assertEqual(windows_launcher.pe_subsystem(path), 2)

    def test_base_gui_is_selected_instead_of_environment_console_shim(self) -> None:
        selected = self.base / "pythonw.exe"
        selected.write_bytes(executable(2))
        (self.fallback / "pythonw.exe").write_bytes(executable(2))
        self.assertEqual(windows_launcher.pe_subsystem(self.shim), 3)
        self.assertEqual(windows_launcher.resolve_windowless_python(), selected.resolve())

    def test_console_candidate_falls_back_to_underlying_executable_directory(self) -> None:
        (self.base / "pythonw.exe").write_bytes(executable(3))
        selected = self.fallback / "pythonw.exe"
        selected.write_bytes(executable(2))
        self.assertEqual(windows_launcher.resolve_windowless_python(), selected.resolve())

    def test_missing_base_candidate_uses_fallback(self) -> None:
        selected = self.fallback / "pythonw.exe"
        selected.write_bytes(executable(2))
        self.assertEqual(windows_launcher.resolve_windowless_python(), selected.resolve())

    def test_malformed_candidate_uses_valid_fallback(self) -> None:
        (self.base / "pythonw.exe").write_bytes(b"not an executable")
        selected = self.fallback / "pythonw.exe"
        selected.write_bytes(executable(2))
        self.assertEqual(windows_launcher.resolve_windowless_python(), selected.resolve())

    def test_no_gui_candidate_fails_closed(self) -> None:
        (self.base / "pythonw.exe").write_bytes(executable(3))
        (self.fallback / "pythonw.exe").write_bytes(executable(3))
        with self.assertRaisesRegex(OSError, "No GUI-subsystem"):
            windows_launcher.resolve_windowless_python()
        with patch.object(sys, "_base_executable", None):
            with self.assertRaisesRegex(OSError, "No GUI-subsystem"):
                windows_launcher.resolve_windowless_python()

    def test_malformed_and_dll_headers_are_rejected(self) -> None:
        malformed = [b"", b"MZ", executable(2)[:100], executable(2, magic=0),
                     executable(2, characteristics=0), executable(2, characteristics=0x2002)]
        offset_outside = bytearray(executable(2))
        struct.pack_into("<I", offset_outside, 60, 0xFFFFFFFF)
        malformed.append(bytes(offset_outside))
        wrong_signature = bytearray(executable(2))
        wrong_signature[64:68] = b"NOPE"
        malformed.append(bytes(wrong_signature))
        oversized_header = bytearray(executable(2))
        struct.pack_into("<H", oversized_header, 84, 65535)
        malformed.append(bytes(oversized_header))
        for index, payload in enumerate(malformed):
            with self.subTest(index=index):
                path = self.base / "pythonw.exe"
                path.write_bytes(payload)
                with self.assertRaises(ValueError):
                    windows_launcher.pe_subsystem(path)

    def test_cli_prints_only_verified_path_or_clear_failure(self) -> None:
        selected = self.base / "pythonw.exe"
        selected.write_bytes(executable(2))
        output, error = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            self.assertEqual(windows_launcher.main(), 0)
        self.assertEqual(output.getvalue(), f"{selected.resolve()}\n")
        self.assertEqual(error.getvalue(), "")
        selected.write_bytes(executable(3))
        output, error = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            self.assertEqual(windows_launcher.main(), 1)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("No GUI-subsystem", error.getvalue())


@unittest.skipUnless(os.name == "nt", "Real Windows interpreter metadata")
class WindowsLauncherIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        candidates = [Path(sys.base_prefix) / "pythonw.exe"]
        base_executable = getattr(sys, "_base_executable", None)
        if base_executable:
            candidates.append(Path(base_executable).parent / "pythonw.exe")
        for candidate in candidates:
            try:
                if windows_launcher.pe_subsystem(candidate) == 2:
                    return
            except (OSError, ValueError):
                continue
        self.skipTest("A GUI Python interpreter is required only for the optional listener")

    def test_actual_selected_interpreter_is_gui_and_uses_base_installation(self) -> None:
        selected = windows_launcher.resolve_windowless_python()
        self.assertEqual(windows_launcher.pe_subsystem(selected), 2)
        possible = {Path(sys.base_prefix).resolve()}
        base_executable = getattr(sys, "_base_executable", None)
        if base_executable:
            possible.add(Path(base_executable).resolve().parent)
        self.assertIn(selected.parent, possible)

    def test_current_console_pythonw_shim_is_bypassed(self) -> None:
        shim = Path(sys.executable).with_name("pythonw.exe")
        if sys.prefix == sys.base_prefix or not shim.is_file() or windows_launcher.pe_subsystem(shim) != 3:
            self.skipTest("This interpreter does not use a console-subsystem pythonw shim")
        selected = windows_launcher.resolve_windowless_python()
        self.assertNotEqual(selected, shim.resolve())
        self.assertEqual(windows_launcher.pe_subsystem(shim), 3)
        self.assertEqual(windows_launcher.pe_subsystem(selected), 2)


if __name__ == "__main__":
    unittest.main()
