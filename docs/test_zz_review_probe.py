"""R0 review probes. Throwaway; lives only in the reviewer's local clone."""

import asyncio
import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from alive.app import create_app
from alive.cognitive_models import CognitiveControl
from tests.conftest import TOKEN
from tests.test_research_memory import MDN, MDN_TEXT, ROOT, grant, historical, post, snapshot


def _meta_preview(client, monkeypatch):
    g, _, _, _, saved = historical(client, monkeypatch)
    mdn_grant = grant(client, g["id"], MDN)
    current = snapshot(client, mdn_grant, MDN, MDN_TEXT)
    client.app.state.kernel.settings.alive_research_meta_enabled = True
    preview = post(
        client,
        "/research/outbound/preview",
        {"snapshot_id": current["snapshot"]["id"], "research_id": saved["id"], "provider": "meta"},
    )
    post(
        client,
        "/research/outbound/authorize",
        {"consent_id": preview["id"], "payload_sha256": preview["payload_sha256"], "approved": True},
    )
    return saved, mdn_grant, preview


def _fixture_output(payload):
    return SimpleNamespace(
        text=json.dumps(
            {
                "relationship": "possible_disagreement",
                "explanation": "Controlled probe hypothesis.",
                "current_quote": payload["current_excerpt"],
                "historical_quote": payload["historical_excerpt"],
                "limitations": "Controlled probe fixture.",
                "confidence": 0.4,
            }
        ),
        usage={"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
    )


def test_probe_A_finding_survives_historical_withdrawal(client, settings, monkeypatch):
    saved, _, preview = _meta_preview(client, monkeypatch)

    async def fast(*args, **kwargs):
        return _fixture_output(args[2])

    monkeypatch.setattr("alive.research_relationships.MetaProvider.structured", fast)
    result = post(client, "/research/relationships", {"consent_id": preview["id"]})
    connection_id = result["connection"]["id"]
    post(client, f"/research/memories/{saved['id']}/withdraw", {})

    def surviving(c):
        rows = c.get(ROOT + "/research/relationships").json()["connections"]
        return [r for r in rows if r["id"] == connection_id]

    after = surviving(client)
    print("\nPROBE_A after withdrawal:", json.dumps(
        {"status": after[0]["status"] if after else None,
         "historical_quote": after[0]["data"].get("historical_quote") if after else None}))
    client.__exit__(None, None, None)
    with TestClient(create_app(settings), headers={"Authorization": f"Bearer {TOKEN}"}) as reopened:
        restarted = surviving(reopened)
        print("PROBE_A after restart:", restarted[0]["status"] if restarted else None)
    assert after and after[0]["status"] == "candidate"  # documents the gap


def test_probe_B_grant_revoke_during_dispatch_still_creates_finding(client, monkeypatch):
    _, mdn_grant, preview = _meta_preview(client, monkeypatch)

    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()

        async def slow(*args, **kwargs):
            started.set()
            await release.wait()
            return _fixture_output(args[2])

        monkeypatch.setattr("alive.research_relationships.MetaProvider.structured", slow)
        task = asyncio.create_task(client.app.state.relationships.analyze(preview["id"]))
        await started.wait()
        await client.app.state.web.revoke(mdn_grant["id"])
        await client.app.state.relationships.invalidate_for_grant(mdn_grant["id"])
        release.set()
        return await task

    result = client.portal.call(scenario)
    status = result["connection"]["status"] if result["connection"] else None
    print("\nPROBE_B finding status after grant revoked mid-dispatch:", status)
    assert status == "candidate"  # documents the gap


def test_probe_C_restart_after_dispatch_charges_zero(client, settings, monkeypatch):
    _, _, preview = _meta_preview(client, monkeypatch)

    async def scenario():
        started = asyncio.Event()

        async def hang(*args, **kwargs):
            started.set()
            await asyncio.Event().wait()

        monkeypatch.setattr("alive.research_relationships.MetaProvider.structured", hang)
        task = asyncio.create_task(client.app.state.relationships.analyze(preview["id"]))
        await started.wait()
        task.cancel()  # simulate process death after the request left the box
        try:
            await task
        except BaseException:
            pass

    # Cancellation is caught inside analyze() and settled; to model a hard crash we instead
    # inspect what initialize() would do with a reserved, actually-dispatched attempt.
    from alive.research_relationships import ATTEMPT_KIND
    from alive.web_models import WebExperience
    from sqlalchemy import select

    async def make_reserved_attempt():
        async with client.app.state.kernel.db.sessions.begin() as s:
            row = WebExperience(
                instance_id=client.app.state.kernel.instance_id,
                kind=ATTEMPT_KIND,
                status="reserved",
                data={"reserved_tokens": 999, "historical_memory_id": "x"},
            )
            s.add(row)
            control = await s.get(CognitiveControl, client.app.state.kernel.instance_id)
            control.reserved = {"calls": 1, "tokens": 999}

    client.portal.call(make_reserved_attempt)
    client.portal.call(client.app.state.relationships.initialize)

    async def read():
        async with client.app.state.kernel.db.sessions() as s:
            rows = (await s.scalars(select(WebExperience).where(WebExperience.kind == ATTEMPT_KIND))).all()
            return [(r.status, r.data.get("charged_tokens"), r.data.get("settled_from_dispatch_status")) for r in rows]

    print("\nPROBE_C history_assisted attempt recovered as:", client.portal.call(read))
