"""Run a console process in a private, headless Windows 11 24H2+ pseudoconsole.

ConPTY attaches descendants to a console without allocating a Terminal window or
tab. This host never attaches to the user's console or changes its configuration.
Only diagnostic terminal output is retained here; child-owned files and pipes
remain their normal, byte-preserving streams.

Lifecycle follows Microsoft's pseudoconsole example:
https://learn.microsoft.com/en-us/windows/console/creating-a-pseudoconsole-session
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from collections.abc import Callable
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import threading

MAX_OUTPUT_BYTES = 32 * 1024
_EXTENDED_STARTUPINFO_PRESENT = 0x00080000
_PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE = 0x00020016
_INFINITE = 0xFFFFFFFF


@dataclass(frozen=True)
class RunResult:
    exit_code: int
    output: bytes


class _Coord(ctypes.Structure):
    _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]


class _StartupInfo(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR), ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(wintypes.BYTE)),
        ("hStdInput", wintypes.HANDLE), ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class _StartupInfoEx(ctypes.Structure):
    _fields_ = [("StartupInfo", _StartupInfo), ("lpAttributeList", ctypes.c_void_p)]


class _ProcessInfo(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD),
    ]


def _kernel() -> ctypes.WinDLL:
    """Declare pointer-sized arguments explicitly; ctypes otherwise truncates."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    signatures = {
        "CreatePipe": ([ctypes.POINTER(wintypes.HANDLE), ctypes.POINTER(wintypes.HANDLE),
                        ctypes.c_void_p, wintypes.DWORD], wintypes.BOOL),
        "CreatePseudoConsole": ([_Coord, wintypes.HANDLE, wintypes.HANDLE, wintypes.DWORD,
                                 ctypes.POINTER(wintypes.HANDLE)], ctypes.c_long),
        "ClosePseudoConsole": ([wintypes.HANDLE], None),
        "ReleasePseudoConsole": ([wintypes.HANDLE], ctypes.c_long),
        "InitializeProcThreadAttributeList": ([ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                              ctypes.POINTER(ctypes.c_size_t)], wintypes.BOOL),
        "UpdateProcThreadAttribute": ([ctypes.c_void_p, wintypes.DWORD, ctypes.c_size_t,
                                       ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p,
                                       ctypes.c_void_p], wintypes.BOOL),
        "DeleteProcThreadAttributeList": ([ctypes.c_void_p], None),
        "CreateProcessW": ([wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
                            wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
                            ctypes.POINTER(_StartupInfoEx), ctypes.POINTER(_ProcessInfo)],
                           wintypes.BOOL),
        "ReadFile": ([wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                      ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p], wintypes.BOOL),
        "WaitForSingleObject": ([wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
        "GetExitCodeProcess": ([wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
        "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
    }
    for name, (arguments, result) in signatures.items():
        try:
            function = getattr(kernel, name)
        except AttributeError as error:
            raise OSError("This Windows version does not provide the pseudoconsole API") from error
        function.argtypes = arguments
        function.restype = result
    return kernel


def ensure_supported() -> None:
    """Fail before installation/launch when safe session lifecycle is unavailable."""
    if os.name != "nt":
        raise OSError("A Windows pseudoconsole requires Windows")
    _kernel()


def run(command: list[str], cwd: Path | None = None,
        on_error: Callable[[OSError], None] | None = None) -> RunResult:
    """Wait for child and attached descendants; return the child's exact exit code.

    The caller must launch a noninteractive command and let it finish. There is
    deliberately no timeout or forced termination of an active Git/worker run.
    Console output includes VT presentation sequences, not a binary data stream.
    The optional callback reports the first native lifecycle error immediately.
    A persistent error retains ownership for investigation instead of silently
    terminating active work. Callback failures never interrupt child ownership.
    """
    if os.name != "nt":
        raise OSError("A Windows pseudoconsole requires Windows")
    if not command or any(not isinstance(argument, str) or "\0" in argument for argument in command):
        raise ValueError("command must contain strings without NUL characters")
    if not command[0]:
        raise ValueError("command executable is required")

    kernel = _kernel()
    input_read, input_write = wintypes.HANDLE(), wintypes.HANDLE()
    output_read, output_write = wintypes.HANDLE(), wintypes.HANDLE()
    console = wintypes.HANDLE()
    process = _ProcessInfo()
    attributes = None
    attributes_initialized = False
    reader: threading.Thread | None = None
    captured = bytearray()
    read_errors: list[OSError] = []
    wait_errors: list[OSError] = []
    release_errors: list[OSError] = []
    child_finished = False
    error_lock = threading.Lock()
    error_notified = False

    def notify_error(error: OSError) -> None:
        nonlocal error_notified
        with error_lock:
            if error_notified:
                return
            error_notified = True
        if on_error is not None:
            try:
                on_error(error)
            except BaseException:
                # A reporting hook must not stop draining or release an active
                # child's console, even if it raises SystemExit in this thread.
                pass

    def checked(success: int) -> None:
        if not success:
            raise ctypes.WinError(ctypes.get_last_error())

    def close(handle: wintypes.HANDLE) -> None:
        if handle.value:
            kernel.CloseHandle(handle)
            handle.value = None

    def drain() -> None:
        buffer = ctypes.create_string_buffer(8192)
        count = wintypes.DWORD()
        while True:
            if not kernel.ReadFile(output_read, buffer, len(buffer), ctypes.byref(count), None):
                error = ctypes.get_last_error()
                if error in (109, 232):  # Broken pipe / pipe closing during teardown.
                    return
                if not read_errors:
                    read_errors.append(ctypes.WinError(error))
                    notify_error(read_errors[0])
                # Do not abandon an active producer or turn a transient read
                # failure into premature pseudoconsole teardown.
                threading.Event().wait(0.1)
                continue
            if not count.value:
                return
            remaining = MAX_OUTPUT_BYTES - len(captured)
            if remaining > 0:
                captured.extend(buffer.raw[:min(count.value, remaining)])
            # Always keep draining after the retention limit to avoid blocking
            # the child or ClosePseudoConsole on a full synchronous pipe.

    def wait_for_child() -> None:
        while kernel.WaitForSingleObject(process.hProcess, _INFINITE) != 0:
            if not wait_errors:
                wait_errors.append(ctypes.WinError(ctypes.get_last_error()))
                notify_error(wait_errors[0])
            # Never close a session containing in-flight Git/worker processes
            # merely because waiting failed. Preserve ownership and retry; an
            # error is reported only after the real process is known to exit.
            threading.Event().wait(0.1)

    try:
        checked(kernel.CreatePipe(ctypes.byref(input_read), ctypes.byref(input_write), None, 0))
        checked(kernel.CreatePipe(ctypes.byref(output_read), ctypes.byref(output_write), None, 0))
        reader = threading.Thread(target=drain, name="listener-conpty-output", daemon=True)
        reader.start()
        result = kernel.CreatePseudoConsole(_Coord(120, 30), input_read, output_write, 0,
                                            ctypes.byref(console))
        if result < 0:
            raise ctypes.WinError(result & 0xFFFFFFFF)

        size = ctypes.c_size_t()
        kernel.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
        if not size.value:
            raise ctypes.WinError(ctypes.get_last_error())
        attributes = ctypes.create_string_buffer(size.value)
        checked(kernel.InitializeProcThreadAttributeList(attributes, 1, 0, ctypes.byref(size)))
        attributes_initialized = True
        checked(kernel.UpdateProcThreadAttribute(
            attributes, 0, _PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE, console,
            ctypes.sizeof(console), None, None))
        startup = _StartupInfoEx()
        startup.StartupInfo.cb = ctypes.sizeof(startup)
        # Explicit NULL standard handles prevent Windows from duplicating a
        # redirected parent stream instead of connecting to the pseudoconsole.
        # https://github.com/microsoft/terminal/discussions/15814
        startup.StartupInfo.dwFlags = 0x00000100  # STARTF_USESTDHANDLES
        startup.lpAttributeList = ctypes.cast(attributes, ctypes.c_void_p)
        command_line = ctypes.create_unicode_buffer(subprocess.list2cmdline(command))
        checked(kernel.CreateProcessW(
            None, command_line, None, None, False, _EXTENDED_STARTUPINFO_PRESENT,
            None, str(cwd) if cwd is not None else None, ctypes.byref(startup), ctypes.byref(process)))

        # The pseudoconsole now owns its copies. Retaining either copy here
        # prevents normal broken-pipe detection during shutdown.
        close(input_read)
        close(output_write)
        kernel.CloseHandle(process.hThread)
        process.hThread = None
        wait_for_child()
        child_finished = True
        exit_code = wintypes.DWORD()
        checked(kernel.GetExitCodeProcess(process.hProcess, ctypes.byref(exit_code)))
    finally:
        if process.hProcess and not child_finished:
            wait_for_child()
        if process.hProcess:
            close(input_read)
            close(output_write)
            # Closing a console after only the direct child exits would send a
            # close event to surviving grandchildren. Windows 11 24H2's release
            # API lets the session end naturally when its last client exits.
            # https://learn.microsoft.com/en-us/windows/console/releasepseudoconsole
            while (result := kernel.ReleasePseudoConsole(console)) < 0:
                if not release_errors:
                    release_errors.append(ctypes.WinError(result & 0xFFFFFFFF))
                    notify_error(release_errors[0])
                threading.Event().wait(0.1)
            if reader is not None:
                reader.join()  # EOF proves every attached client disconnected.
        if attributes_initialized:
            kernel.DeleteProcThreadAttributeList(attributes)
        # Keep the input writer alive until all clients exit; early EOF can
        # close the session and terminate an attached client prematurely.
        if console.value:
            kernel.ClosePseudoConsole(console)
        close(input_read)
        close(output_write)
        close(input_write)
        if reader is not None and reader.ident is not None:
            reader.join()
        close(output_read)
        if process.hThread:
            kernel.CloseHandle(process.hThread)
        if process.hProcess:
            kernel.CloseHandle(process.hProcess)
    if read_errors:
        raise read_errors[0]
    if wait_errors:
        raise wait_errors[0]
    if release_errors:
        raise release_errors[0]
    return RunResult(exit_code.value, bytes(captured))
