"""Spawn a child process and terminate its WHOLE tree, with confirmation (ALIVE-PI-01B).

Killing only the direct child leaves Node descendants running. A run is therefore never reported
as cleanly cancelled until the tree is confirmed empty:

* POSIX: the child leads its own session/process group; the group is SIGKILLed and polled until
  no process remains in it.
* Windows: the child is placed in a Job Object (`KILL_ON_JOB_CLOSE`); terminating the job kills
  every descendant, including ones that outlived their parent, and the job's active-process count
  is read back to confirm it reached zero.

On Windows the child is assigned to the job just after it starts, so a descendant spawned in that
first instant would escape. Pi runs with tools and extensions disabled and spawns no children, so
the job is defense in depth there; the tests exercise the tree kill with a real grandchild.
"""

import asyncio
import contextlib
import os
import signal
import subprocess
import sys
import time

WINDOWS = sys.platform == "win32"

if WINDOWS:
    import ctypes
    from ctypes import wintypes

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _k32.CreateJobObjectW.restype = wintypes.HANDLE
    _k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _k32.AssignProcessToJobObject.restype = wintypes.BOOL
    _k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _k32.SetInformationJobObject.restype = wintypes.BOOL
    _k32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    _k32.QueryInformationJobObject.restype = wintypes.BOOL
    _k32.QueryInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.c_void_p,
    ]
    _k32.TerminateJobObject.restype = wintypes.BOOL
    _k32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    _k32.CloseHandle.restype = wintypes.BOOL
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]

    class _BasicLimits(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _IoCounters(ctypes.Structure):
        _fields_ = [(n, ctypes.c_uint64) for n in ("r", "w", "o", "rb", "wb", "ob")]

    class _ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BasicLimits),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    class _Accounting(ctypes.Structure):
        _fields_ = [
            ("TotalUserTime", ctypes.c_int64),
            ("TotalKernelTime", ctypes.c_int64),
            ("ThisPeriodTotalUserTime", ctypes.c_int64),
            ("ThisPeriodTotalKernelTime", ctypes.c_int64),
            ("TotalPageFaultCount", wintypes.DWORD),
            ("TotalProcesses", wintypes.DWORD),
            ("ActiveProcesses", wintypes.DWORD),
            ("TotalTerminatedProcesses", wintypes.DWORD),
        ]

    _JOB_KILL_ON_CLOSE = 0x2000
    _EXTENDED_LIMITS, _ACCOUNTING = 9, 1
    _PROCESS_SET_QUOTA_TERMINATE = 0x0100 | 0x0001


class ProcessTreeError(RuntimeError):
    pass


async def shielded(work):
    """Run `work` to completion even if the awaiting task is cancelled meanwhile.

    The cancel is not lost: it is re-raised once the work has finished. Cleanup must not be
    abortable by a second cancellation.
    """
    inner = asyncio.ensure_future(work)
    cancelled = False
    while not inner.done():
        try:
            await asyncio.shield(inner)
        except asyncio.CancelledError:
            cancelled = True
    result = inner.result()
    if cancelled:
        raise asyncio.CancelledError()
    return result


class ManagedProcess:
    """A child whose whole process tree can be terminated and the result confirmed."""

    def __init__(self, process, job=None):
        self.process = process
        self.job = job
        self.pid = process.pid
        self.stdin, self.stdout, self.stderr = process.stdin, process.stdout, process.stderr
        self._terminated = False

    @classmethod
    async def spawn(cls, argv, *, env, cwd, limit=4 * 1024 * 1024):
        kwargs = {}
        if WINDOWS:
            kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
            )
        else:
            kwargs["start_new_session"] = True
        process = await asyncio.create_subprocess_exec(
            *argv,
            cwd=cwd,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=limit,
            **kwargs,
        )
        job = None
        if WINDOWS:
            try:
                job = _create_job_for(process.pid)
            except BaseException:
                with contextlib.suppress(ProcessLookupError):
                    process.kill()
                raise
        return cls(process, job)

    @property
    def returncode(self):
        return self.process.returncode

    async def terminate_tree(self, *, grace=2.0, confirm_within=5.0):
        """Ask the child to exit, then kill the whole tree. Returns True only if confirmed empty."""
        if self._terminated:
            return await self._confirm(confirm_within)
        self._terminated = True
        with contextlib.suppress(Exception):
            if self.stdin and not self.stdin.is_closing():
                self.stdin.close()
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self.process.wait(), grace)
        # Even a child that exited on its own may have left descendants: always kill the tree.
        self._kill_tree()
        return await self._confirm(confirm_within)

    def _kill_tree(self):
        if WINDOWS:
            if self.job:
                _k32.TerminateJobObject(self.job, 1)
            with contextlib.suppress(ProcessLookupError):
                self.process.kill()
        else:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(self.pid, signal.SIGKILL)

    async def _confirm(self, within):
        deadline = time.monotonic() + within
        while time.monotonic() < deadline:
            if self.tree_is_empty():
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(self.process.wait(), 1)
                self._close_job()
                return True
            await asyncio.sleep(0.05)
        return False

    def tree_is_empty(self):
        if WINDOWS:
            if not self.job:
                return self.process.returncode is not None
            info = _Accounting()
            ok = _k32.QueryInformationJobObject(
                self.job, _ACCOUNTING, ctypes.byref(info), ctypes.sizeof(info), None
            )
            return bool(ok) and info.ActiveProcesses == 0
        try:
            os.killpg(self.pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        # A group that only holds zombies still answers; reap ours so it can disappear.
        if self.process.returncode is not None:
            return not _group_has_live_members(self.pid)
        return False

    def _close_job(self):
        if WINDOWS and self.job:
            _k32.CloseHandle(self.job)
            self.job = None


def _group_has_live_members(pgid):
    """POSIX: whether any non-zombie process remains in the group (zombies are not alive)."""
    try:
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            try:
                with open(f"/proc/{entry}/stat", encoding="utf-8") as handle:
                    fields = handle.read().rsplit(")", 1)[1].split()
            except (OSError, IndexError):
                continue
            state, group = fields[0], int(fields[2])
            if group == pgid and state != "Z":
                return True
    except OSError:
        return True  # cannot prove it empty; do not claim confirmation
    return False


def _create_job_for(pid):
    job = _k32.CreateJobObjectW(None, None)
    if not job:
        raise ProcessTreeError("cannot create a Job Object")
    limits = _ExtendedLimits()
    limits.BasicLimitInformation.LimitFlags = _JOB_KILL_ON_CLOSE
    if not _k32.SetInformationJobObject(
        job, _EXTENDED_LIMITS, ctypes.byref(limits), ctypes.sizeof(limits)
    ):
        _k32.CloseHandle(job)
        raise ProcessTreeError("cannot configure the Job Object")
    handle = _k32.OpenProcess(_PROCESS_SET_QUOTA_TERMINATE, False, pid)
    if not handle:
        _k32.CloseHandle(job)
        raise ProcessTreeError("cannot open the child process")
    try:
        if not _k32.AssignProcessToJobObject(job, handle):
            raise ProcessTreeError("cannot assign the child to the Job Object")
    except BaseException:
        _k32.CloseHandle(job)
        raise
    finally:
        _k32.CloseHandle(handle)
    return job
