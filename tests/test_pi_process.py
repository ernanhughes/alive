"""ALIVE-PI-01B: a Pi run's whole process tree is killed, and cleanup is confirmed, not assumed."""

import asyncio
import os
import sys
import time

import pytest

from alive.pi import process as proc

GRANDCHILD = "import time; time.sleep(120)"
PARENT_KEEPS_GRANDCHILD = (
    "import subprocess, sys, time;"
    f"g = subprocess.Popen([sys.executable, '-c', {GRANDCHILD!r}]);"
    "print(g.pid, flush=True); time.sleep(120)"
)
PARENT_EXITS_LEAVING_ORPHAN = (
    "import subprocess, sys;"
    f"g = subprocess.Popen([sys.executable, '-c', {GRANDCHILD!r}]);"
    "print(g.pid, flush=True)"
)


def pid_alive(pid):
    if sys.platform == "win32":
        import ctypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = ctypes.c_void_p
        handle = k32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if not handle:
            return False
        try:
            return k32.WaitForSingleObject(ctypes.c_void_p(handle), 0) == 0x102  # WAIT_TIMEOUT
        finally:
            k32.CloseHandle(ctypes.c_void_p(handle))
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8") as handle:
            return handle.read().rsplit(")", 1)[1].split()[0] != "Z"  # a zombie is not alive
    except OSError:
        return True


def wait_dead(pid, seconds=5.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if not pid_alive(pid):
            return True
        time.sleep(0.05)
    return not pid_alive(pid)


async def spawn(script):
    return await proc.ManagedProcess.spawn(
        [sys.executable, "-c", script], env=dict(os.environ), cwd=None
    )


async def grandchild_pid(managed):
    return int((await asyncio.wait_for(managed.stdout.readline(), 10)).decode().strip())


def test_the_whole_tree_is_killed_and_confirmed():
    async def scenario():
        managed = await spawn(PARENT_KEEPS_GRANDCHILD)
        grandchild = await grandchild_pid(managed)
        assert pid_alive(managed.pid) and pid_alive(grandchild)
        confirmed = await managed.terminate_tree()
        return managed.pid, grandchild, confirmed

    parent, grandchild, confirmed = asyncio.run(scenario())
    assert confirmed is True
    assert wait_dead(parent) and wait_dead(grandchild)


def test_an_orphan_left_by_an_exited_parent_is_still_killed():
    async def scenario():
        managed = await spawn(PARENT_EXITS_LEAVING_ORPHAN)
        grandchild = await grandchild_pid(managed)
        # Poll: asyncio's Process.wait() blocks while the orphan still holds the inherited pipes.
        for _ in range(200):
            if not pid_alive(managed.pid):
                break
            await asyncio.sleep(0.05)
        assert not pid_alive(managed.pid)  # the parent is gone...
        assert pid_alive(grandchild)  # ...but its child is not
        return grandchild, await managed.terminate_tree()

    grandchild, confirmed = asyncio.run(scenario())
    assert confirmed is True
    assert wait_dead(grandchild)


def test_terminate_is_idempotent():
    async def scenario():
        managed = await spawn("import time; time.sleep(120)")
        first = await managed.terminate_tree()
        second = await managed.terminate_tree()
        return first, second

    assert asyncio.run(scenario()) == (True, True)


def test_cleanup_cannot_be_confirmed_while_a_descendant_lives():
    """The confirmation is a real check, not a constant: a live tree must not be reported empty."""

    async def scenario():
        managed = await spawn(PARENT_KEEPS_GRANDCHILD)
        grandchild = await grandchild_pid(managed)
        empty_while_alive = managed.tree_is_empty()
        await managed.terminate_tree()
        return grandchild, empty_while_alive

    grandchild, empty_while_alive = asyncio.run(scenario())
    assert empty_while_alive is False
    assert wait_dead(grandchild)


def test_shielded_work_finishes_even_if_the_caller_is_cancelled_again():
    done = []

    async def cleanup():
        await asyncio.sleep(0.2)
        done.append("cleaned")

    async def caller():
        await proc.shielded(cleanup())

    async def scenario():
        task = asyncio.create_task(caller())
        await asyncio.sleep(0.05)
        task.cancel()  # a cancel arrives while cleanup is running
        with pytest.raises(asyncio.CancelledError):
            await task  # it is not lost...
        return list(done)  # ...but the cleanup still completed first

    assert asyncio.run(scenario()) == ["cleaned"]


# --- PIB-01: a process group is not containment (POSIX) ---

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX sessions and /proc")

ESCAPED_GRANDCHILD_LIVE_PARENT = (
    "import subprocess, sys, time;"
    f"g = subprocess.Popen([sys.executable, '-c', {GRANDCHILD!r}], start_new_session=True);"
    "print(g.pid, flush=True); time.sleep(120)"
)
ESCAPED_GRANDCHILD_EXITED_PARENT = (
    "import subprocess, sys;"
    f"g = subprocess.Popen([sys.executable, '-c', {GRANDCHILD!r}], start_new_session=True);"
    "print(g.pid, flush=True)"
)
FORKS_ESCAPING_CHILDREN = (
    "import subprocess, sys, time;"
    "pids = [];"
    "[pids.append(subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'],"
    " start_new_session=True).pid) for _ in range(30)];"
    "print(','.join(map(str, pids)), flush=True); time.sleep(120)"
)


@posix_only
def test_a_grandchild_in_its_own_session_is_found_killed_and_not_falsely_confirmed():
    """The reviewed defect: cleanup_confirmed=True while a setsid() descendant was still alive."""

    async def scenario():
        managed = await spawn(ESCAPED_GRANDCHILD_LIVE_PARENT)
        grandchild = await grandchild_pid(managed)
        assert os.getsid(grandchild) != os.getsid(managed.pid)  # it really left the session
        assert os.getpgid(grandchild) != managed.pid  # and the process group
        empty_while_alive = managed.tree_is_empty()
        confirmed = await managed.terminate_tree()
        return grandchild, empty_while_alive, confirmed

    grandchild, empty_while_alive, confirmed = asyncio.run(scenario())
    assert empty_while_alive is False
    assert confirmed is True
    assert wait_dead(grandchild)  # confirmation now means the escaped descendant is really gone


@posix_only
def test_an_escaped_grandchild_whose_parent_already_exited_is_found_by_its_tag():
    async def scenario():
        managed = await spawn(ESCAPED_GRANDCHILD_EXITED_PARENT)
        grandchild = await grandchild_pid(managed)
        for _ in range(200):
            if not pid_alive(managed.pid):
                break
            await asyncio.sleep(0.05)
        assert not pid_alive(managed.pid) and pid_alive(grandchild)
        assert proc._posix_members(managed.pid, managed.tag)  # found although orphaned
        for _ in range(100):  # once our child is reaped, "empty" must still be False
            if managed.process.returncode is not None:
                break
            await asyncio.sleep(0.05)
        assert managed.process.returncode is not None
        assert managed.tree_is_empty() is False
        return grandchild, await managed.terminate_tree()

    grandchild, confirmed = asyncio.run(scenario())
    assert confirmed is True
    assert wait_dead(grandchild)


@posix_only
def test_many_escaping_children_are_frozen_then_all_killed():
    async def scenario():
        managed = await spawn(FORKS_ESCAPING_CHILDREN)
        line = (await asyncio.wait_for(managed.stdout.readline(), 20)).decode().strip()
        children = [int(pid) for pid in line.split(",")]
        confirmed = await managed.terminate_tree()
        return children, confirmed, proc._posix_members(managed.pid, managed.tag)

    children, confirmed, remaining = asyncio.run(scenario())
    assert confirmed is True and not remaining
    assert all(wait_dead(pid) for pid in children)


@posix_only
def test_a_stopped_process_cannot_hide_a_descendant_from_cleanup():
    """SIGSTOPped members are still found and killed (cleanup freezes them itself)."""

    async def scenario():
        managed = await spawn(ESCAPED_GRANDCHILD_LIVE_PARENT)
        grandchild = await grandchild_pid(managed)
        os.kill(grandchild, 19)  # SIGSTOP
        confirmed = await managed.terminate_tree()
        return grandchild, confirmed

    grandchild, confirmed = asyncio.run(scenario())
    assert confirmed is True and wait_dead(grandchild)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Job Object")
def test_a_windows_child_starts_only_inside_the_job():
    """Created suspended, assigned, then resumed: the very first thing it does is already jobbed."""

    async def scenario():
        managed = await spawn(PARENT_KEEPS_GRANDCHILD)
        grandchild = await grandchild_pid(managed)  # forked in the child's first instant
        confirmed = await managed.terminate_tree()
        return grandchild, confirmed

    grandchild, confirmed = asyncio.run(scenario())
    assert confirmed is True and wait_dead(grandchild)


ESCAPED_GRANDCHILD_WITH_SCRUBBED_ENV = (
    "import subprocess, sys, time;"
    f"g = subprocess.Popen([sys.executable, '-c', {GRANDCHILD!r}], env={{}},"
    " start_new_session=True);"
    "print(g.pid, flush=True); time.sleep(120)"
)


@posix_only
def test_a_grandchild_that_scrubs_its_environment_is_still_found_while_its_parent_lives():
    """The tag cannot find it; the parent-pid walk does (the two are independent mechanisms)."""

    async def scenario():
        managed = await spawn(ESCAPED_GRANDCHILD_WITH_SCRUBBED_ENV)
        grandchild = await grandchild_pid(managed)
        with open(f"/proc/{grandchild}/environ", "rb") as handle:
            assert proc.TAG_ENV.encode() not in handle.read()  # it really has no tag
        confirmed = await managed.terminate_tree()
        return grandchild, confirmed

    grandchild, confirmed = asyncio.run(scenario())
    assert confirmed is True and wait_dead(grandchild)
