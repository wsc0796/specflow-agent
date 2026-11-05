"""Windows process-instance evidence for the synchronous in-process adapter."""

import ctypes
import os
from ctypes import wintypes


def _kernel():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.GetProcessTimes.restype = wintypes.BOOL
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    return kernel


def current_process_identity():
    if os.name != "nt":
        # This build does not claim verified cross-restart process evidence on
        # another platform. Current-thread completion is still observable.
        return {"pid": os.getpid(), "creation_time": None, "platform": os.name}
    kernel = _kernel()
    handle = kernel.OpenProcess(0x1000 | 0x00100000, False, os.getpid())
    if not handle:
        raise RuntimeError("Cannot bind the review adapter to its Windows process instance")
    try:
        times = [wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *[ctypes.byref(value) for value in times]):
            raise RuntimeError("Cannot read Windows process creation identity")
        created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        return {"pid": os.getpid(), "creation_time": created, "platform": "nt"}
    finally:
        kernel.CloseHandle(handle)


def original_process_exited(instance):
    if os.name != "nt" or instance.get("platform") != "nt" or not instance.get("creation_time"):
        return False
    kernel = _kernel()
    handle = kernel.OpenProcess(0x1000 | 0x00100000, False, instance["pid"])
    if not handle:
        return ctypes.get_last_error() == 87  # No such process; access denied is not proof.
    try:
        times = [wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *[ctypes.byref(value) for value in times]):
            return False
        created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        return created != instance["creation_time"] or kernel.WaitForSingleObject(handle, 0) == 0
    finally:
        kernel.CloseHandle(handle)
