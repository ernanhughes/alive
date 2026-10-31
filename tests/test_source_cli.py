"""The owner's production path: prepare, inspect, approve, withdraw, in real child processes."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alive.app import create_app
from tests.conftest import TOKEN, _boot

ROOT = Path(__file__).resolve().parents[1]
SECRET = "TOP-SECRET-VALUE"


@pytest.fixture
def database(settings):
    """A database the app has started against once, so an instance exists, then stopped."""
    app = create_app(settings, include_experiments=True)
    _boot(settings)
    with TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"}):
        pass
    return settings.database_url


def owner(database, *argv, expect=0):
    env = os.environ | {"DATABASE_URL": database, "PYTHONDONTWRITEBYTECODE": "1"}
    done = subprocess.run(
        [sys.executable, "-m", "alive.sources", *argv],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.returncode == expect, (done.stdout[-800:], done.stderr[-800:])
    return done


def make_repository(tmp_path):
    root = tmp_path / "project"
    (root / "src").mkdir(parents=True)
    (root / "README.md").write_text("# Project\nhello\n", encoding="utf-8")
    (root / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")
    (root / ".env").write_text(f"KEY={SECRET}\n", encoding="utf-8")
    (root / "blob.bin").write_bytes(b"\x00\x01\x02")
    (root / ".gitignore").write_text("*.log\n", encoding="utf-8")
    return root


def test_the_owner_flow_prepare_inspect_approve_withdraw(database, tmp_path):
    root = make_repository(tmp_path)
    prepared = owner(
        database, "prepare", "repository", "--root", str(root), "--label", "project", "--all"
    )
    capture = json.loads(prepared.stdout)
    assert "CANDIDATE" in prepared.stderr and "not approved" in prepared.stderr
    assert capture["source_type"] == "repository" and len(capture["content_sha256"]) == 64
    reasons = {o["path"]: o["reason"] for o in capture["inventory"]["omitted"]}
    assert reasons[".env"] == "ignored_by_host_policy" and "blob.bin" in reasons
    items = {i["item"] for i in capture["inventory"]["items"]}
    assert {"README.md", "src/app.py"} <= items and ".env" not in items
    # Inspection exposes identities and sizes, never content or the host path.
    assert SECRET not in prepared.stdout and str(root) not in prepared.stdout
    assert "hello" not in prepared.stdout

    assert [c["id"] for c in json.loads(owner(database, "list").stdout)] == [capture["id"]]
    assert json.loads(owner(database, "inspect", capture["id"]).stdout)["id"] == capture["id"]

    wrong = owner(
        database,
        "approve", capture["id"], "--confirm-sha256", "0" * 64,
        "--operation", "repository.inspect", "--all",
        expect=1,
    )  # fmt: skip
    assert "source_digest_mismatch" in wrong.stderr
    both = owner(
        database,
        "approve", capture["id"], "--confirm-sha256", capture["content_sha256"],
        "--operation", "repository.inspect", "--all", "--item", "README.md",
        expect=1,
    )  # fmt: skip
    assert "source_scope_choose_all_or_items" in both.stderr
    assert json.loads(owner(database, "approvals").stdout) == []  # refusals approve nothing

    args = [
        "approve", capture["id"], "--confirm-sha256", capture["content_sha256"],
        "--operation", "repository.inspect", "--item", "README.md",
        "--ttl-hours", "2", "--request-id", "cli-request-0001",
    ]  # fmt: skip
    approval = json.loads(owner(database, *args).stdout)
    again = json.loads(owner(database, *args).stdout)
    assert again["id"] == approval["id"]  # a retried request is the same decision
    assert approval["scope"] == {"items": ["README.md"]}
    assert approval["approved_by"].startswith("owner-cli:")
    assert set(approval["resources"]) == {
        "source_ref",
        "approval_id",
        "content_sha256",
        "scope_sha256",
    }

    out = json.loads(
        owner(database, "withdraw", approval["id"], "--reason", "no longer needed").stdout
    )
    assert out["withdrawn_at"] and out["withdrawn_reason"] == "no longer needed"
    final = json.loads(owner(database, "withdraw", approval["id"], "--reason", "second").stdout)
    assert final["withdrawn_reason"] == "no longer needed"  # the first withdrawal stands


def test_documents_are_parsed_at_capture_and_pdf_is_refused_plainly(database, tmp_path):
    note = tmp_path / "notes.md"
    note.write_text("# Intro\nfirst\n\n## Method\nsecond\n", encoding="utf-8")
    capture = json.loads(
        owner(database, "prepare", "document", "--file", str(note), "--label", "notes").stdout
    )
    headings = [i["heading"] for i in capture["inventory"]["items"]]
    assert headings == ["Intro", "Method"] and capture["inventory"]["format"] == "markdown"
    assert capture["inventory"]["parser"]["id"] == "alive-document-sections/v1"
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.7 fake")
    refused = owner(
        database, "prepare", "document", "--file", str(pdf), "--label", "paper", expect=1
    )
    assert "pdf_parser_not_installed" in refused.stderr
    binary = tmp_path / "x.txt"
    binary.write_bytes(b"ab\x00cd")
    assert (
        "document_binary"
        in owner(
            database, "prepare", "document", "--file", str(binary), "--label", "b", expect=1
        ).stderr
    )


def test_unsafe_paths_are_refused_without_naming_host_locations(database, tmp_path):
    root = make_repository(tmp_path)
    for bad in ("CON", "../outside", "src/../../x"):
        done = owner(
            database, "prepare", "repository", "--root", str(root), "--label", "p", "--path", bad,
            expect=1,
        )  # fmt: skip
        assert "repository_path_refused" in done.stderr and str(tmp_path) not in done.stderr


def test_the_command_refuses_a_database_the_app_never_started_against(tmp_path):
    empty = f"sqlite+aiosqlite:///{tmp_path}/never-started.db"
    done = owner(empty, "list", expect=1)
    assert done.returncode == 1  # no instance exists; nothing is invented on its behalf
