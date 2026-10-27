import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from alive.app import create_app
from alive.experiment_budget import worst_micro_usd
from tests.conftest import TOKEN
from tests.test_web_experience import ROOT, analyse, consent, fake_model, setup, snapshot, wait


def test_provenance_authentication_and_no_local_secret_disclosure(client, settings):
    assert client.get("/api/v1/provenance", headers={"Authorization": ""}).status_code == 401
    identity = client.get("/api/v1/provenance").json()
    assert identity["protocol_version"] == 1
    assert len(identity["runtime_sha256"]) == 64
    path = Path(settings.database_url.removeprefix("sqlite+aiosqlite:///"))
    assert (
        identity["database"]["fingerprint"]
        == hashlib.sha256(str(path.resolve()).encode()).hexdigest()
    )
    assert "alive/web_experience.py" in identity["module_sha256"]
    text = json.dumps(identity)
    assert TOKEN not in text
    assert str(path) not in text
    assert "api_key" not in text


def test_companion_usd_limit_is_cumulative_across_restart(client, settings, monkeypatch):
    calls = fake_model(monkeypatch)
    settings.alive_companion_micro_usd_limit = 100000
    goal, grant = setup(client)
    first = wait(client, analyse(client, snapshot(client, grant))["id"])
    settings.alive_companion_micro_usd_limit = worst_micro_usd(first["data"]["reserved_tokens"])
    client.__exit__(None, None, None)
    with TestClient(create_app(settings), headers={"Authorization": f"Bearer {TOKEN}"}) as reopened:
        new_grant = consent(reopened, goal["id"])
        analyse(reopened, snapshot(reopened, new_grant), expected=409)
        assert len(calls) == 1
        assert reopened.get(ROOT).json()["corrections"] == []


def test_companion_usd_limit_conservatively_counts_failed_reservations(
    client, settings, monkeypatch
):
    calls = fake_model(monkeypatch, "not in the reviewed excerpt")
    settings.alive_companion_micro_usd_limit = 100000
    _, grant = setup(client)
    first = wait(client, analyse(client, snapshot(client, grant))["id"])
    assert first["status"] == "failed"
    settings.alive_companion_micro_usd_limit = (
        2 * worst_micro_usd(first["data"]["reserved_tokens"]) - 1
    )
    analyse(client, snapshot(client, grant), expected=409)
    assert len(calls) == 1


def test_zero_companion_usd_limit_blocks_before_dispatch(client, settings, monkeypatch):
    calls = fake_model(monkeypatch)
    settings.alive_companion_micro_usd_limit = 0
    _, grant = setup(client)
    analyse(client, snapshot(client, grant), expected=409)
    assert not calls


def test_invalid_structured_response_is_retained_without_becoming_a_note(client, monkeypatch):
    async def malformed(*args, **kwargs):
        return SimpleNamespace(
            text="not valid JSON",
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        )

    monkeypatch.setattr("alive.web_experience.MetaProvider.structured", malformed)
    _, grant = setup(client)
    row = wait(client, analyse(client, snapshot(client, grant))["id"])
    assert row["status"] == "failed"
    assert row["data"]["raw_response"] == "not valid JSON"
    assert row["data"]["raw_response_sha256"] == hashlib.sha256(b"not valid JSON").hexdigest()
    assert row["data"]["dispatch_started_at"]
    assert row["data"]["output"] is None
