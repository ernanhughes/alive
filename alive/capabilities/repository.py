"""Trusted bounded import; execution receives immutable approved content, not a root path.

Captures identify the bytes read. They are not an atomic Git/filesystem snapshot.
The host must approve the resulting content identity before minting a run grant.
"""

import asyncio
import fnmatch
import hashlib
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from alive.capabilities.contracts import json_bytes
from alive.models import now
from alive.workflows.context import Refused, require

REFERENCE = re.compile(r"^[a-z][a-z0-9-]{2,63}$")
DEVICE_NAMES = {"con", "prn", "aux", "nul", "conin$", "conout$"} | {
    f"{kind}{n}" for kind in ("com", "lpt") for n in range(1, 10)
}
SECRET_PARTS = {".git", ".ssh", ".aws", ".azure", ".gnupg", "node_modules", "__pycache__"}
SECRET_NAMES = (
    ".env*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "id_rsa*",
    "id_ed25519*",
    "credentials*",
    ".npmrc",
    ".pypirc",
    "token",
    "token.json",
    "secrets.*",
)


def relative_path(value):
    require(
        type(value) is str
        and 1 <= len(value) <= 256
        and "\\" not in value
        and ":" not in value
        and "\x00" not in value,
        "repository_path_refused",
    )
    path = PurePosixPath(value)
    require(
        not path.is_absolute()
        and str(path) == value
        and all(part not in {".", "..", ""} for part in path.parts)
        # Windows resolves these names to devices (CON, NUL, COM1...) whatever the directory.
        and not any(
            part.split(".")[0].rstrip(" ").casefold() in DEVICE_NAMES for part in path.parts
        ),
        "repository_path_refused",
    )
    return value


def _inside(path, root):
    try:
        return os.path.commonpath(
            [os.path.normcase(str(path)), os.path.normcase(str(root))]
        ) == os.path.normcase(str(root))
    except ValueError:
        return False


def _windows_final_path(fd):
    import ctypes
    import msvcrt
    from ctypes import wintypes

    function = ctypes.WinDLL("kernel32", use_last_error=True).GetFinalPathNameByHandleW
    function.argtypes = (wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD)
    function.restype = wintypes.DWORD
    buffer = ctypes.create_unicode_buffer(32768)
    length = function(msvcrt.get_osfhandle(fd), buffer, len(buffer), 0)
    require(0 < length < len(buffer), "repository_handle_path_unavailable")
    value = buffer.value
    if value.startswith("\\\\?\\UNC\\"):
        value = "\\\\" + value[8:]
    elif value.startswith("\\\\?\\"):
        value = value[4:]
    return Path(value)


def _read(root, name, ceiling):
    """No-follow directory handles on POSIX; verify the opened handle on Windows."""
    parts = PurePosixPath(relative_path(name)).parts
    descriptors = []
    try:
        if os.name != "nt":
            directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            descriptors.append(directory)
            for part in parts[:-1]:
                directory = os.open(
                    part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory
                )
                descriptors.append(directory)
            # O_NONBLOCK: opening a FIFO read-only would otherwise wait for a writer forever,
            # before the regular-file check below could refuse it. It has no effect on regular
            # files. O_NOCTTY keeps a terminal device from becoming the controlling terminal.
            fd = os.open(
                parts[-1],
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_NOCTTY", 0),
                dir_fd=directory,
            )
        else:
            target = root
            for part in parts:
                target = target / part
                require(
                    not target.is_symlink() and not target.is_junction(), "repository_link_refused"
                )
            fd = os.open(target, os.O_RDONLY | os.O_BINARY)
        descriptors.append(fd)
        if os.name == "nt":
            final = _windows_final_path(fd)
            require(
                _inside(final, root)
                and os.path.normcase(str(final)) == os.path.normcase(str(root.joinpath(*parts))),
                "repository_handle_outside_root",
            )
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode), "repository_regular_file_required")
        require(before.st_nlink == 1, "repository_hardlink_refused")
        require(before.st_size <= ceiling, "repository_file_size_limit")
        content = bytearray()
        while len(content) <= ceiling:
            chunk = os.read(fd, min(8192, ceiling + 1 - len(content)))
            if not chunk:
                break
            content.extend(chunk)
        require(len(content) <= ceiling, "repository_file_size_limit")
        after = os.fstat(fd)
        require(
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
            "repository_changed_during_capture",
        )
        if os.name == "nt":
            final = _windows_final_path(fd)
            require(
                _inside(final, root)
                and os.path.normcase(str(final)) == os.path.normcase(str(root.joinpath(*parts))),
                "repository_handle_outside_root",
            )
        return bytes(content)
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def _ignored(name, patterns):
    parts = PurePosixPath(name).parts
    if any(part.casefold() in SECRET_PARTS for part in parts):
        return True
    if any(
        fnmatch.fnmatchcase(part.casefold(), pattern) for part in parts for pattern in SECRET_NAMES
    ):
        return True
    for pattern in patterns:
        pattern = pattern.lstrip("/").rstrip("/")
        if fnmatch.fnmatchcase(name, pattern) or any(
            fnmatch.fnmatchcase(part, pattern) for part in parts
        ):
            return True
        if any(fnmatch.fnmatchcase("/".join(parts[:i]), pattern) for i in range(1, len(parts))):
            return True
    return False


@dataclass(frozen=True)
class File:
    path: str
    content: str
    sha256: str
    bytes: int


@dataclass(frozen=True)
class RepositorySnapshot:
    reference: str
    sha256: str
    captured_at: str
    files: tuple[File, ...]
    omitted: tuple[tuple[str, str], ...]


def capture_repository(reference, root, paths, *, max_files=64, max_source_bytes=65536, ignore=()):
    """Trusted host operation, never exposed by the public capability catalogue."""
    require(
        type(reference) is str and REFERENCE.fullmatch(reference), "repository_reference_required"
    )
    require(
        type(max_files) is int
        and 1 <= max_files <= 64
        and type(max_source_bytes) is int
        and 1 <= max_source_bytes <= 65536,
        "repository_capture_limits",
    )
    root = Path(root)
    require(not root.is_symlink() and not root.is_junction(), "repository_root_link_refused")
    root = root.resolve(strict=True)
    require(root.is_dir(), "repository_root_required")
    require(type(paths) in (tuple, list) and len(paths) <= max_files, "repository_file_count_limit")
    names = [relative_path(p) for p in paths]
    require(len({p.casefold() for p in names}) == len(names), "repository_duplicate_path")
    patterns = list(ignore)
    try:
        ignore_bytes = _read(root, ".gitignore", 8192)
    except FileNotFoundError:
        ignore_bytes = b""
    except Refused as error:
        # Ignoring a rule file could expose files it hides, so capture fails closed, but with a
        # reason that names the real problem instead of a generic size or type error.
        too_large = str(error) == "repository_file_size_limit"
        raise Refused(
            "repository_ignore_too_large" if too_large else "repository_ignore_unreadable"
        ) from None
    try:
        patterns += [
            line.strip()
            for line in ignore_bytes.decode("utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    except UnicodeDecodeError:
        raise Refused("repository_ignore_encoding") from None
    # Conservative subset: no negation/escape rules that could silently re-include secrets.
    require(
        len(patterns) <= 128
        and all(
            type(p) is str and 0 < len(p) <= 256 and not p.startswith("!") and "\\" not in p
            for p in patterns
        ),
        "repository_ignore_contract",
    )
    files, omitted, remaining = [], [], max_source_bytes
    for name in sorted(names):
        if _ignored(name, patterns):
            omitted.append((name, "ignored_by_host_policy"))
            continue
        try:
            raw = _read(root, name, remaining)
            if b"\x00" in raw:
                omitted.append((name, "binary_file"))
                continue
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError:
                omitted.append((name, "invalid_utf8"))
                continue
            files.append(File(name, content, hashlib.sha256(raw).hexdigest(), len(raw)))
            remaining -= len(raw)
        except Refused as error:
            omitted.append((name, str(error)))
        except OSError:
            omitted.append((name, "unavailable_or_linked_file"))
    identity = {
        "kind": "approved_content_capture/v1",
        "reference": reference,
        "files": [{"path": f.path, "sha256": f.sha256, "bytes": f.bytes} for f in files],
        "omitted": omitted,
    }
    return RepositorySnapshot(
        reference,
        hashlib.sha256(json_bytes(identity)).hexdigest(),
        now().isoformat(),
        tuple(files),
        tuple(omitted),
    )


@dataclass(frozen=True)
class RepositoryReader:
    reference: str
    sha256: str
    captured_at: str
    files: tuple[File, ...]
    omitted: tuple[tuple[str, str], ...]

    async def output(self):
        files = []
        for f in self.files:
            await asyncio.sleep(0)  # Cancellation is observed between bounded in-memory reads.
            source_id = (
                "repository:"
                + self.sha256
                + ":"
                + hashlib.sha256((f.path + "\x00" + f.sha256).encode()).hexdigest()
            )
            files.append(
                {
                    "path": f.path,
                    "content": f.content,
                    "sha256": f.sha256,
                    "bytes": f.bytes,
                    "source_id": source_id,
                }
            )
        return {
            "repository_ref": self.reference,
            "snapshot_sha256": self.sha256,
            "captured_at": self.captured_at,
            "files": files,
            "omitted": [{"path": p, "reason": r} for p, r in self.omitted],
            "provenance": {
                "kind": "approved_content_capture/v1",
                "atomic_repository_snapshot": False,
                "semantic_status": "unverified",
            },
        }


def reader_for(registry, grant, inputs):
    resources = grant["resources"]
    require(
        set(resources) == {"repository_ref", "snapshot_sha256", "paths"},
        "repository_owner_scope_required",
    )
    reference = inputs["repository_ref"]
    snapshot = registry._snapshots.get(reference)
    require(
        snapshot is not None
        and resources["repository_ref"] == reference
        and resources["snapshot_sha256"] == snapshot.sha256,
        "repository_snapshot_not_approved",
    )
    paths = inputs["paths"]
    require(
        type(paths) is list and paths and len(paths) <= grant["limits"]["max_files"],
        "repository_file_count_limit",
    )
    names = [relative_path(p) for p in paths]
    require(
        len(set(names)) == len(names) and sorted(names) == resources["paths"],
        "repository_paths_not_approved",
    )
    captured = {f.path for f in snapshot.files} | {p for p, _ in snapshot.omitted}
    require(set(names) <= captured, "repository_path_not_captured")
    require(
        sum(f.bytes for f in snapshot.files if f.path in names)
        <= grant["limits"]["max_source_bytes"],
        "repository_source_byte_limit",
    )
    return RepositoryReader(
        snapshot.reference,
        snapshot.sha256,
        snapshot.captured_at,
        tuple(f for f in snapshot.files if f.path in names),
        tuple((p, r) for p, r in snapshot.omitted if p in names),
    )


async def inspect_repository(context):
    from alive.workflows.adapters import StageResult

    require(
        isinstance(context.resources, RepositoryReader), "constrained_repository_reader_required"
    )
    output = await context.resources.output()
    # Retrieval is not validation: nothing here checks any claim about these bytes.
    return StageResult(output, tuple(f["source_id"] for f in output["files"]), "not_run")
