"""Ordinary note reads hide withdrawn lineage while preserving audit originals."""

from fastapi.testclient import TestClient
from sqlalchemy import select

from alive.app import create_app
from alive.web_models import WebExperience
from tests.conftest import TOKEN
from tests.evidence_leaks import assert_no_derived_evidence
from tests.test_claim_runtime import settings as settings
from tests.test_research_memory import (
    MDN,
    MDN_TEXT,
    ROOT,
    analyse,
    grant,
    historical,
    post,
    snapshot,
    wait,
)

MARK = "cycle collector"


def test_withdrawn_note_enumeration_public_reads_and_restart(client, settings, monkeypatch):
    _, _, _, note, saved = historical(client, monkeypatch)
    post(client, f"/research/memories/{saved['id']}/withdraw", {})
    assert_no_derived_evidence(client, MARK)
    events = client.get("/api/v1/events?limit=500").json()
    note_ids = [event["payload"]["id"] for event in events if event["event_type"] == "web.note"]
    assert note["id"] in note_ids
    for note_id in note_ids:
        response = client.get(ROOT + f"/notes/{note_id}")
        assert response.status_code in (404, 410)
        assert MARK not in response.text
    for path, methods in client.get("/openapi.json").json()["paths"].items():
        if "get" in methods and "{" not in path:
            response = client.get(path)
            assert MARK not in response.text, path

    async def retained():
        async with client.app.state.kernel.db.sessions() as session:
            row = await session.scalar(select(WebExperience).where(WebExperience.id == note["id"]))
            return row.data

    assert MARK in str(client.portal.call(retained))
    client.__exit__(None, None, None)
    with TestClient(create_app(settings), headers={"Authorization": "Bearer " + TOKEN}) as reopened:
        response = reopened.get(ROOT + f"/notes/{note['id']}")
        assert response.status_code == 410
        assert MARK not in response.text


def test_other_active_and_unsaved_notes_remain_readable(client, monkeypatch):
    g, _, _, note, saved = historical(client, monkeypatch)
    permission = grant(client, g["id"], MDN)
    shot = snapshot(client, permission, MDN, MDN_TEXT)
    other = wait(client, analyse(client, shot)["id"])
    assert client.get(ROOT + f"/notes/{other['id']}").status_code == 200
    post(client, "/research/memories", {"note_id": other["id"]})
    post(client, f"/research/memories/{saved['id']}/withdraw", {})
    assert client.get(ROOT + f"/notes/{note['id']}").status_code == 410
    response = client.get(ROOT + f"/notes/{other['id']}")
    assert response.status_code == 200
    assert response.json()["data"] == other["data"]
