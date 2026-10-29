"""Spawn a child process and terminate its WHOLE tree, with confirmation (ALIVE-PI-01B).

Killing only the direct child leaves Node descendants running. A run is therefore never reported
as cleanly cancelled until the tree is confirmed empty:

* Windows: the child is created SUSPENDED, placed in a Job Object (`KILL_ON_JOB_CLOSE`) and only
  then resumed, so it can never run (or fork) outside the job. Terminating the job kills every
  descendant, including ones that outlived their parent, and the job's active-process count is
  read back to confirm it reached zero.
* POSIX: a process group is NOT containment: a descendant can call setsid()/setpgid() and leave it.
  Membership is therefore the union of (a) the group and session, (b) every descendant by parent
  pid, and (c) every process whose environment carries this run's unique tag (which also finds a
  detached grandchild whose parent has already exited). Cleanup freezes the members with SIGSTOP
  until the set stops growing (a stopped process cannot fork), SIGKILLs them, then polls until no
  live member remains. "Confirmed" means exactly that, and no more.

Limit (stated, not hidden): without cgroups or a PID namespace, a descendant that BOTH is orphaned
before cleanup and scrubs its own environment cannot be found. This is process hygiene for a
child that is not trying to escape; it is not an OS sandbox.
"""

import asyncio
import contextlib
import os
import signal
import subprocess
import sys
import time
import uuid

WINDOWS = sys.platform == "win32"
TAG_ENV = "ALIVE_PI_RUN_TAG"

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
    _PROCESS_SUSPEND_RESUME = 0x0800
    _CREATE_SUSPENDED = 0x00000004
    _ntdll = ctypes.WinDLL("ntdll")
    _ntdll.NtResumeProcess.restype = ctypes.c_long
    _ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]


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

    def __init__(self, process, job=None, tag=None):
        self.process = process
        self.job = job
        self.tag = tag
        self.pid = process.pid
        self.stdin, self.stdout, self.stderr = process.stdin, process.stdout, process.stderr
        self._terminated = False

    @classmethod
    async def spawn(cls, argv, *, env, cwd, limit=4 * 1024 * 1024):
        kwargs = {}
        tag = uuid.uuid4().hex  # unique to this child; inherited by everything it starts
        env = {**env, TAG_ENV: tag}
        if WINDOWS:
            kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.CREATE_NO_WINDOW
                | _CREATE_SUSPENDED  # nothing runs until it is inside the job
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
                _resume(process.pid)
            except BaseException:
                with contextlib.suppress(ProcessLookupError):
                    process.kill()
                raise
        return cls(process, job, tag)

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
            _kill_posix_tree(self.pid, self.tag)

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
        if self.process.returncode is None:
            return False  # our own child has not even been reaped yet
        return not _posix_members(self.pid, self.tag)

    def _close_job(self):
        if WINDOWS and self.job:
            _k32.CloseHandle(self.job)
            self.job = None


def _proc_table():
    """Linux: {pid: (ppid, pgid, sid, state)} from /proc. Raises OSError if unreadable."""
    table = {}
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/stat", encoding="utf-8", errors="replace") as handle:
                fields = handle.read().rsplit(")", 1)[1].split()
            table[int(entry)] = (int(fields[1]), int(fields[2]), int(fields[3]), fields[0])
        except (OSError, IndexError, ValueError):
            continue  # it exited while we were looking
    return table


def _has_tag(pid, needle):
    try:
        with open(f"/proc/{pid}/environ", "rb") as handle:
            return needle in handle.read().split(b"\0")
    except OSError:
        return False


def _posix_members(root_pid, tag):
    """Live (non-zombie) processes that belong to the run, however they got out of its group."""
    try:
        table = _proc_table()
    except OSError:
        return {root_pid}  # cannot enumerate: never claim the tree is empty
    children = {}
    for pid, (ppid, _pgid, _sid, _state) in table.items():
        children.setdefault(ppid, []).append(pid)
    members, stack = set(), [root_pid]
    while stack:  # (b) every descendant by parent pid, whatever group or session it moved to
        pid = stack.pop()
        if pid in members:
            continue
        if pid in table:
            members.add(pid)
        stack.extend(children.get(pid, ()))
    for pid, (_ppid, pgid, sid, _state) in table.items():  # (a) the group and session
        if pgid == root_pid or sid == root_pid:
            members.add(pid)
    if tag:  # (c) anything carrying this run's tag, e.g. a detached grandchild already orphaned
        needle = f"{TAG_ENV}={tag}".encode()
        members.update(pid for pid in table if pid not in members and _has_tag(pid, needle))
    members.discard(os.getpid())
    return {pid for pid in members if table.get(pid, (0, 0, 0, "Z"))[3] != "Z"}


def _kill_posix_tree(root_pid, tag):
    """Freeze, then kill, every member. A stopped process cannot fork, so it cannot outrun us."""
    frozen = set()
    for _ in range(50):
        members = _posix_members(root_pid, tag)
        fresh = members - frozen
        if not fresh:
            break
        for pid in fresh:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.kill(pid, signal.SIGSTOP)
        frozen |= members
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(root_pid, signal.SIGKILL)
    for pid in frozen:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(pid, signal.SIGKILL)


def _resume(pid):
    """Windows: start a process that was created suspended (it is already inside the job)."""
    handle = _k32.OpenProcess(_PROCESS_SUSPEND_RESUME, False, pid)
    if not handle:
        raise ProcessTreeError("cannot open the child to resume it")
    try:
        if _ntdll.NtResumeProcess(handle) != 0:
            raise ProcessTreeError("cannot resume the child")
    finally:
        _k32.CloseHandle(handle)


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
