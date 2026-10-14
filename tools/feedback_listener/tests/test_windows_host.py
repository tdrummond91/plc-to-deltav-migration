"""Windows integration checks for real pseudoconsole ownership and teardown."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import windows_host


def native_host_supported() -> bool:
    try:
        windows_host.ensure_supported()
    except OSError:
        return False
    return True


@unittest.skipUnless(native_host_supported(), "Windows 11 24H2+ ConPTY integration")
class WindowsHostTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="plc-conpty-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.python = str(Path(sys.executable).with_name("python.exe"))

    def run_python(self, source: str) -> windows_host.RunResult:
        script = self.root / "child.py"
        script.write_text(source, encoding="utf-8")
        return windows_host.run([self.python, "-B", str(script)], cwd=self.root)

    def owned_console_hosts(self) -> set[int]:
        """Read process metadata only; identify hosts directly owned by this test."""
        class ProcessEntry(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                ("pid", wintypes.DWORD), ("heap", ctypes.c_size_t),
                ("module", wintypes.DWORD), ("threads", wintypes.DWORD),
                ("parent", wintypes.DWORD), ("priority", wintypes.LONG),
                ("flags", wintypes.DWORD), ("name", wintypes.WCHAR * 260),
            ]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
        kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
        snapshot = kernel.CreateToolhelp32Snapshot(2, 0)  # TH32CS_SNAPPROCESS
        self.assertNotEqual(snapshot, ctypes.c_void_p(-1).value)
        found: set[int] = set()
        try:
            entry = ProcessEntry()
            entry.dwSize = ctypes.sizeof(entry)
            present = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
            while present:
                if entry.parent == os.getpid() and entry.name.lower() in {"conhost.exe", "openconsole.exe"}:
                    found.add(entry.pid)
                present = kernel.Process32NextW(snapshot, ctypes.byref(entry))
        finally:
            kernel.CloseHandle(snapshot)
        return found

    def test_child_and_grandchild_share_an_invisible_console(self) -> None:
        probe = '''import ctypes, json, os
from ctypes import wintypes
kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.GetConsoleWindow.restype = wintypes.HWND
user = ctypes.WinDLL("user32", use_last_error=True)
user.IsWindowVisible.argtypes = [wintypes.HWND]
window = kernel.GetConsoleWindow()
processes = (wintypes.DWORD * 16)()
count = kernel.GetConsoleProcessList(processes, len(processes))
print(json.dumps({"window": window, "visible": bool(user.IsWindowVisible(window)),
                  "pid": os.getpid(), "console_pids": list(processes)[:count]}))
'''
        (self.root / "probe.py").write_text(probe, encoding="utf-8")
        result = self.run_python('''import json, subprocess, sys
from pathlib import Path
exec(Path("probe.py").read_text(), globals())
parent = subprocess.run([sys.executable, "probe.py"], capture_output=True, check=True)
Path("grandchild.json").write_bytes(parent.stdout)
''')
        self.assertEqual(result.exit_code, 0, result.output)
        grandchild = json.loads((self.root / "grandchild.json").read_text())
        self.assertFalse(grandchild["visible"])
        self.assertTrue(grandchild["window"])
        self.assertIn(grandchild["pid"], grandchild["console_pids"])
        self.assertGreaterEqual(len(grandchild["console_pids"]), 2)
        self.assertIn(str(grandchild["window"]).encode(), result.output)

    def test_grandchild_finishes_naturally_after_direct_child_exits(self) -> None:
        grandchild = self.root / "grandchild.py"
        grandchild.write_text('''import time
from pathlib import Path
time.sleep(0.4)
Path("grandchild-finished.txt").write_text("natural exit")
print("grandchild-finished")
''', encoding="utf-8")
        result = self.run_python('''import subprocess, sys
subprocess.Popen([sys.executable, "-B", "grandchild.py"])
raise SystemExit(17)
''')
        self.assertEqual(result.exit_code, 17)
        self.assertEqual((self.root / "grandchild-finished.txt").read_text(), "natural exit")
        self.assertIn(b"grandchild-finished", result.output)

    def test_redirected_binary_pipe_and_file_remain_exact(self) -> None:
        result = self.run_python('''import subprocess, sys
from pathlib import Path
code = "import sys; sys.stdout.buffer.write(bytes(range(256)) * 512)"
expected = bytes(range(256)) * 512
captured = subprocess.run([sys.executable, "-c", code], capture_output=True, check=True)
assert captured.stdout == expected
with Path("binary.bin").open("wb") as stream:
    subprocess.run([sys.executable, "-c", code], stdout=stream, check=True)
assert Path("binary.bin").read_bytes() == expected
print("binary-ok")
''')
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn(b"binary-ok", result.output)
        self.assertEqual((self.root / "binary.bin").read_bytes(), bytes(range(256)) * 512)

    def test_actual_nonzero_child_exit_is_preserved(self) -> None:
        result = self.run_python("raise SystemExit(37)\n")
        self.assertEqual(result.exit_code, 37)
        result = self.run_python("import ctypes; ctypes.WinDLL('kernel32').ExitProcess(ctypes.c_uint(0xA0123456))\n")
        self.assertEqual(result.exit_code, 0xA0123456)

    def test_large_terminal_output_drains_after_retention_limit(self) -> None:
        result = self.run_python('''import sys
from pathlib import Path
for index in range(12000):
    sys.stdout.write(f"{index:06d}:" + "x" * 100 + "\\n")
sys.stdout.flush()
Path("completed.txt").write_text("all output written")
''')
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(len(result.output), windows_host.MAX_OUTPUT_BYTES)
        self.assertEqual((self.root / "completed.txt").read_text(), "all output written")

    def test_argument_quoting_and_working_directory(self) -> None:
        arguments = ["contains spaces", 'embedded"quote', "trailing\\", ""]
        result = windows_host.run([self.python, "-c", "import json,os,sys; open('args.json','w').write(json.dumps(sys.argv[1:])); print(os.getcwd())", *arguments], cwd=self.root)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads((self.root / "args.json").read_text()), arguments)
        self.assertIn(str(self.root).encode(), result.output)

    def test_missing_executable_and_repeated_runs_release_handles(self) -> None:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        kernel.GetProcessHandleCount.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]

        def handles() -> int:
            count = wintypes.DWORD()
            self.assertTrue(kernel.GetProcessHandleCount(kernel.GetCurrentProcess(), ctypes.byref(count)))
            return count.value

        self.assertEqual(self.run_python("pass\n").exit_code, 0)  # Warm OS/Python lazy state.
        hosts_before = self.owned_console_hosts()
        before = handles()
        for _ in range(6):
            with self.assertRaises(OSError):
                windows_host.run([str(self.root / "does-not-exist.exe")])
            self.assertEqual(self.run_python("pass\n").exit_code, 0)
        self.assertLessEqual(handles(), before + 1)
        self.assertEqual(self.owned_console_hosts(), hosts_before)

    def test_pythonw_host_has_no_console_and_child_gets_private_console(self) -> None:
        # Exercise the scheduled entry point's GUI-subsystem interpreter.
        # pythonw itself never allocates a console, including on failure.
        host = self.root / "host.py"
        host.write_text(f'''import ctypes, json, sys
from ctypes import wintypes
from pathlib import Path
sys.path.insert(0, {str(Path(windows_host.__file__).parent)!r})
import windows_host
kernel = ctypes.WinDLL("kernel32")
kernel.GetConsoleWindow.restype = wintypes.HWND
assert not kernel.GetConsoleWindow()
result = windows_host.run([{self.python!r}, "-c", "print('gui-host-ok')"])
Path("host-result.json").write_text(json.dumps({{"exit_code": result.exit_code, "output": result.output.decode("utf-8")}}))
''', encoding="utf-8")
        from windows_launcher import resolve_windowless_python
        try:
            launcher = resolve_windowless_python()
        except OSError as error:
            self.skipTest(str(error))
        completed = subprocess.run([str(launcher), "-B", str(host)],
                                   cwd=self.root, capture_output=True, timeout=30)
        self.assertEqual(completed.returncode, 0)
        saved = json.loads((self.root / "host-result.json").read_text())
        self.assertEqual(saved["exit_code"], 0)
        self.assertIn("gui-host-ok", saved["output"])

    def test_repeated_wait_errors_notify_before_recovery_and_raise_after_exit(self) -> None:
        kernel = windows_host._kernel()
        wait = kernel.WaitForSingleObject
        attempts = 0
        notifications = []

        def fail_three_times(handle, milliseconds):
            nonlocal attempts
            attempts += 1
            if attempts <= 3:
                ctypes.set_last_error(6)
                return 0xFFFFFFFF
            return wait(handle, milliseconds)

        script = self.root / "child.py"
        script.write_text('''import time
from pathlib import Path
time.sleep(0.6)
Path("completed.txt").write_text("finished before error")
''', encoding="utf-8")

        def notify(error: OSError) -> None:
            notifications.append((error.winerror, attempts, (self.root / "completed.txt").exists()))

        with patch.object(kernel, "WaitForSingleObject", side_effect=fail_three_times), patch.object(
                windows_host, "_kernel", return_value=kernel):
            with self.assertRaises(OSError):
                windows_host.run([self.python, "-B", str(script)], cwd=self.root, on_error=notify)
        self.assertEqual(notifications, [(6, 1, False)])
        self.assertGreaterEqual(attempts, 4)
        self.assertEqual((self.root / "completed.txt").read_text(), "finished before error")

    def test_transient_read_error_keeps_draining_until_child_finishes(self) -> None:
        kernel = windows_host._kernel()
        read = kernel.ReadFile
        attempts = 0

        def fail_once(*arguments):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                ctypes.set_last_error(6)
                return False
            return read(*arguments)

        with patch.object(kernel, "ReadFile", side_effect=fail_once), patch.object(
                windows_host, "_kernel", return_value=kernel):
            with self.assertRaises(OSError):
                self.run_python('''import sys
from pathlib import Path
sys.stdout.write(("x" * 100 + "\\n") * 2000)
sys.stdout.flush()
Path("completed.txt").write_text("finished before error")
''')
        self.assertEqual((self.root / "completed.txt").read_text(), "finished before error")

    def test_reporting_callback_failure_does_not_interrupt_active_child(self) -> None:
        kernel = windows_host._kernel()
        wait = kernel.WaitForSingleObject
        attempts = 0
        notifications = []

        def fail_once(handle, milliseconds):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                ctypes.set_last_error(6)
                return 0xFFFFFFFF
            return wait(handle, milliseconds)

        def broken_callback(error: OSError) -> None:
            notifications.append(error.winerror)
            raise SystemExit("Reporter must not stop host")

        script = self.root / "child.py"
        script.write_text('''import time
from pathlib import Path
time.sleep(0.2)
Path("completed.txt").write_text("child survived callback")
''', encoding="utf-8")
        with patch.object(kernel, "WaitForSingleObject", side_effect=fail_once), patch.object(
                windows_host, "_kernel", return_value=kernel):
            with self.assertRaises(OSError):
                windows_host.run([self.python, "-B", str(script)], cwd=self.root, on_error=broken_callback)
        self.assertEqual(notifications, [6])
        self.assertEqual((self.root / "completed.txt").read_text(), "child survived callback")


@unittest.skipUnless(os.name == "nt", "Windows API capability check")
class WindowsHostCapabilityTests(unittest.TestCase):
    def test_unavailable_pseudoconsole_api_fails_before_launch(self) -> None:
        # Fake exports keep this fail-closed check runnable on older Windows.
        # Only the integration cases require the actual newer native API.
        for unavailable in ("CreatePseudoConsole", "ReleasePseudoConsole"):
            with self.subTest(unavailable=unavailable):
                calls = []

                class MissingPseudoConsole:
                    def __getattr__(self, name):
                        if name == unavailable:
                            raise AttributeError(name)

                        def export(*arguments):
                            calls.append(name)
                            return 0

                        return export

                with patch.object(ctypes, "WinDLL", return_value=MissingPseudoConsole()):
                    with self.assertRaisesRegex(OSError, "pseudoconsole API"):
                        windows_host.ensure_supported()
                    with self.assertRaisesRegex(OSError, "pseudoconsole API"):
                        windows_host.run([sys.executable, "-c", "pass"])
                self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
