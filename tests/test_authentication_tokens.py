"""F-001: token corruption, atomic publication and independent protocol denial."""

import asyncio
import os
import stat
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from alive.app import create_app
from alive.config import prepare_local
from alive.db import Database
from alive.models import Base

VALID = "compatible-local-token-123456789"
BAD = [
    b"",
    b" \t\r\n",
    b"x" * 23,
    b"x" * 24 + b" space",
    b"x" * 24 + b"\x00",
    b"x" * 24 + b"\ninside",
    "non-ascii-".encode() + "雪".encode() * 24,
    b"\xff" * 24,
]


@pytest.fixture
def local_settings(settings, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".alive").mkdir()
    settings.alive_api_token = ""
    return settings


def schema(settings):
    async def create():
        db = Database(settings.database_url)
        async with db.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await db.engine.dispose()

    asyncio.run(create())


@pytest.mark.parametrize("content", BAD)
def test_invalid_persisted_token_refuses_startup_without_rotation(local_settings, content):
    path = Path(".alive/token")
    path.write_bytes(content)
    with pytest.raises(ValueError) as error:
        create_app(local_settings)
    assert path.read_bytes() == content
    assert "token" in str(error.value).lower()
    assert "x" * 23 not in str(error.value)


@pytest.mark.parametrize(
    "value", [" " * 24, "x" * 23, "x" * 24 + " space", "x" * 24 + "\x00", "雪" * 24]
)
def test_configured_token_has_same_validation(local_settings, value):
    local_settings.alive_api_token = value
    with pytest.raises(ValueError):
        create_app(local_settings)
    assert not Path(".alive/token").exists()


@pytest.mark.parametrize("ending", ["", "\n", "\r\n"])
def test_valid_persisted_token_compatibility_and_protocol_denial(local_settings, ending):
    path = Path(".alive/token")
    path.write_bytes((VALID + ending).encode())
    schema(local_settings)
    with TestClient(create_app(local_settings)) as client:
        assert client.get("/api/v1/alive").status_code == 401
        assert client.post("/api/v1/goals", json={"title": "Must be denied"}).status_code == 401
        assert client.get("/api/v1/alive", headers={"Authorization": "Bearer "}).status_code == 401
        with client.websocket_connect("/api/v1/events/stream") as ws:
            ws.send_json({})
            with pytest.raises(WebSocketDisconnect) as error:
                ws.receive_json()
            assert error.value.code == 1008
        headers = {"Authorization": "Bearer " + VALID}
        assert client.get("/api/v1/alive", headers=headers).status_code == 200
        goal = client.post("/api/v1/goals", headers=headers, json={"title": "Authorized goal"})
        assert goal.status_code == 200
        with client.websocket_connect("/api/v1/events/stream") as ws:
            ws.send_json({"token": VALID})
            assert ws.receive_json()["event_id"]
        assert len(client.get("/api/v1/goals", headers=headers).json()) == 1
    assert path.read_bytes() == (VALID + ending).encode()


@pytest.mark.parametrize(
    "frame", [{}, {"token": ""}, {"token": None}, {"token": 0}, {"token": False}, {"token": []}, []]
)
def test_empty_expected_token_still_cannot_authorize_http_or_websocket(
    local_settings, monkeypatch, frame
):
    # Deliberately bypass the loader to prove the consumers defend independently.
    monkeypatch.setattr("alive.app.prepare_local", lambda settings: "")
    schema(local_settings)
    with TestClient(create_app(local_settings)) as client:
        assert client.get("/api/v1/alive").status_code == 401
        assert client.post("/api/v1/goals", json={"title": "Denied"}).status_code == 401
        with client.websocket_connect("/api/v1/events/stream") as ws:
            ws.send_json(frame)
            with pytest.raises(WebSocketDisconnect) as error:
                ws.receive_json()
            assert error.value.code == 1008


def test_first_creation_is_stable_and_private(local_settings):
    token = prepare_local(local_settings)
    path = Path(".alive/token")
    assert len(token) >= 24 and token.isascii() and not any(ch.isspace() for ch in token)
    assert prepare_local(local_settings) == token
    assert not list(path.parent.glob(".token-*"))
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    else:
        # The real ACL must be protected, with a single owner access rule.
        import re
        import subprocess

        subprocess.run(
            ["icacls", str(path), "/save", "acl.txt", "/q"],
            capture_output=True,
            check=True,
            timeout=5,
        )
        dacl = (
            Path("acl.txt").read_text(encoding="utf-16-le").removeprefix("\ufeff").splitlines()[1]
        )
        assert dacl.startswith("D:P")
        assert len(re.findall(r"\([^()]+\)", dacl)) == 1, dacl
        assert re.search(r"\(A;;FA;;;[A-Z0-9-]+\)", dacl), dacl


@pytest.mark.skipif(os.name != "nt", reason="Windows DACLs")
def test_restricting_removes_explicit_rules_left_by_the_creator(tmp_path):
    """Regression: `/inheritance:r` alone keeps EXPLICIT rules.

    An elevated creator's file carries explicit SYSTEM / Administrators / OWNER RIGHTS rules, so
    on GitHub's elevated Windows runner the token file kept four rules instead of one. Seed such
    rules (and a broad one) on any account and require that only the owner's grant survives.
    """
    import re
    import subprocess

    from alive.config import _restrict_token_file

    target = tmp_path / "token"
    target.write_text("placeholder", encoding="ascii")
    subprocess.run(
        ["icacls", str(target), "/grant", "*S-1-5-18:(F)", "*S-1-5-32-544:(F)", "*S-1-1-0:(R)"],
        capture_output=True,
        check=True,
        timeout=5,
    )
    _restrict_token_file(str(target))
    acl = tmp_path / "acl.txt"
    subprocess.run(
        ["icacls", str(target), "/save", str(acl), "/q"],
        capture_output=True,
        check=True,
        timeout=5,
    )
    dacl = acl.read_text(encoding="utf-16-le").removeprefix("﻿").splitlines()[1]
    rules = re.findall(r"\([^()]+\)", dacl)
    assert dacl.startswith("D:P") and len(rules) == 1, dacl
    assert re.fullmatch(r"\(A;;FA;;;[A-Z0-9-]+\)", rules[0]), dacl
    for broad in ("SY", "BA", "WD", "BU", "AU", "OW", "IU"):
        assert f";;;{broad})" not in dacl, (broad, dacl)


def test_concurrent_first_creation_never_publishes_partial_or_replaces_winner(local_settings):
    with ThreadPoolExecutor(max_workers=8) as pool:
        tokens = list(pool.map(lambda _: prepare_local(local_settings), range(16)))
    assert len(set(tokens)) == 1 and len(tokens[0]) >= 24
    assert Path(".alive/token").read_text(encoding="utf-8") == tokens[0]
    assert not list(Path(".alive").glob(".token-*"))


def test_failure_before_publication_does_not_leave_empty_token(local_settings, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("controlled fsync failure")

    monkeypatch.setattr(os, "fsync", fail)
    with pytest.raises((OSError, ValueError)):
        prepare_local(local_settings)
    assert not Path(".alive/token").exists()
    assert not list(Path(".alive").glob(".token-*"))


def test_corrupt_token_bytes_never_enter_startup_traceback(local_settings):
    import traceback

    marker = b"audit-private-sentinel-not-a-real-credential"
    Path(".alive/token").write_bytes(marker + b"\xff")
    with pytest.raises(ValueError) as error:
        create_app(local_settings)
    trace = "".join(traceback.format_exception(error.value))
    assert marker.decode() not in trace
    assert "UnicodeDecodeError" not in trace
