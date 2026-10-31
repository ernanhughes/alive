"""Fast real-filesystem safety checks; no provider, server or database."""

import asyncio
import hashlib
import os
from types import SimpleNamespace

import pytest

from alive.capabilities.repository import capture_repository, reader_for, relative_path
from alive.workflows.context import Refused


@pytest.mark.parametrize(
    "path",
    ["../secret", "/etc/passwd", "C:/secret", "a\\b", "a//b", "./a", "a/../b", "a/", "a\x00b"],
)
def test_noncanonical_paths_are_refused(path):
    with pytest.raises(Refused, match="repository_path_refused"):
        relative_path(path)


def test_capture_binds_bytes_and_survives_later_root_edits(tmp_path):
    path = tmp_path / "README.md"
    path.write_bytes(b"approved content")
    first = capture_repository("fixture-repo", tmp_path, ["README.md"])
    second = capture_repository("fixture-repo", tmp_path, ["README.md"])
    assert first.sha256 == second.sha256
    path.write_bytes(b"changed after approval")
    assert first.files[0].content == "approved content"
    assert first.files[0].sha256 == hashlib.sha256(b"approved content").hexdigest()
    assert capture_repository("fixture-repo", tmp_path, ["README.md"]).sha256 != first.sha256
    assert str(tmp_path) not in repr(first)


def test_secret_and_ignored_paths_are_never_opened(tmp_path, monkeypatch):
    import alive.capabilities.repository as repository

    (tmp_path / ".gitignore").write_text("private/\n*.log\n", encoding="utf-8")
    original, opened = repository._read, []

    def recording(root, name, ceiling):
        opened.append(name)
        return original(root, name, ceiling)

    monkeypatch.setattr(repository, "_read", recording)
    names = [
        ".env.local",
        ".git/config",
        "private/data.txt",
        "debug.log",
        "server.key",
        "credentials.json",
    ]
    snapshot = capture_repository("fixture-repo", tmp_path, names)
    assert opened == [".gitignore"]
    assert not snapshot.files
    assert dict(snapshot.omitted) == {p: "ignored_by_host_policy" for p in names}


def test_binary_encoding_missing_and_size_failures_are_explicit(tmp_path):
    for name, content in {"binary": b"a\x00b", "encoding": b"\xff", "large": b"a" * 20}.items():
        (tmp_path / name).write_bytes(content)
    result = capture_repository(
        "fixture-repo", tmp_path, ["binary", "encoding", "large", "missing"], max_source_bytes=10
    )
    assert not result.files
    assert dict(result.omitted) == {
        "binary": "binary_file",
        "encoding": "invalid_utf8",
        "large": "repository_file_size_limit",
        "missing": "unavailable_or_linked_file",
    }


def test_hardlink_cannot_alias_an_unapproved_file(tmp_path):
    (tmp_path / ".env").write_text("secret", encoding="utf-8")
    os.link(tmp_path / ".env", tmp_path / "readme")
    snapshot = capture_repository("fixture-repo", tmp_path, ["readme"])
    assert snapshot.omitted == (("readme", "repository_hardlink_refused"),)
    assert not snapshot.files


@pytest.mark.parametrize("paths,limit", [(["a", "a"], 2), (["A", "a"], 2), (["a", "b"], 1)])
def test_duplicate_and_file_count_limits(tmp_path, paths, limit):
    with pytest.raises(Refused):
        capture_repository("fixture-repo", tmp_path, paths, max_files=limit)


def reader_fixture(tmp_path):
    for name in ("a", "b"):
        (tmp_path / name).write_text(name, encoding="utf-8")
    snapshot = capture_repository("fixture-repo", tmp_path, ["a", "b"])
    registry = SimpleNamespace(_snapshots={snapshot.reference: snapshot})
    grant = {
        "resources": {
            "repository_ref": snapshot.reference,
            "snapshot_sha256": snapshot.sha256,
            "paths": ["a"],
        },
        "limits": {"max_files": 1, "max_source_bytes": 1},
    }
    inputs = {"repository_ref": snapshot.reference, "paths": ["a"]}
    return registry, grant, inputs


def test_reader_exposes_only_the_exact_approved_subset(tmp_path):
    registry, grant, inputs = reader_fixture(tmp_path)
    reader = reader_for(registry, grant, inputs)
    assert [f.path for f in reader.files] == ["a"]
    output = asyncio.run(reader.output())
    assert [f["content"] for f in output["files"]] == ["a"]
    assert output["provenance"] == {
        "kind": "approved_content_capture/v1",
        "atomic_repository_snapshot": False,
        "semantic_status": "unverified",
    }
    assert not hasattr(reader, "snapshot") and not hasattr(reader, "root")


@pytest.mark.parametrize("attack", ["hash", "reference", "paths", "bytes", "files"])
def test_reader_requires_exact_owner_scope(tmp_path, attack):
    registry, grant, inputs = reader_fixture(tmp_path)
    if attack == "hash":
        grant["resources"]["snapshot_sha256"] = "0" * 64
    elif attack == "reference":
        inputs["repository_ref"] = "other-repo"
    elif attack == "paths":
        inputs["paths"] = ["b"]
    else:
        grant["limits"]["max_source_bytes" if attack == "bytes" else "max_files"] = 0
    with pytest.raises(Refused):
        reader_for(registry, grant, inputs)


def test_reader_observes_cancellation_between_files(tmp_path):
    registry, grant, inputs = reader_fixture(tmp_path)
    reader = reader_for(registry, grant, inputs)

    async def check():
        task = asyncio.create_task(reader.output())
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(check())
