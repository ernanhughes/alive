"""R0 review probes promoted to assertions for the repaired lifecycle behavior.

The original review asserted the unsafe outcomes to demonstrate old defects.
These regressions require withdrawal/revocation to suppress findings instead.
"""

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from alive.app import create_app
from alive.cognitive_models import CognitiveControl
from alive.research_relationships import ATTEMPT_KIND, CONNECTION_KIND
from tests.conftest import TOKEN
from tests.evidence_leaks import assert_no_derived_evidence
from tests.test_claim_runtime import rows
from tests.test_research_memory import (
    MDN,
    MDN_TEXT,
    PY_TEXT,
    ROOT,
    grant,
    historical,
    post,
    snapshot,
)


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
        {
            "consent_id": preview["id"],
            "payload_sha256": preview["payload_sha256"],
            "approved": True,
        },
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


def test_probe_A_withdrawal_invalidates_finding_across_restart(client, settings, monkeypatch):
    saved, _, preview = _meta_preview(client, monkeypatch)

    async def fast(*args, **kwargs):
        return _fixture_output(args[2])

    monkeypatch.setattr("alive.research_relationships.MetaProvider.structured", fast)
    result = post(client, "/research/relationships", {"consent_id": preview["id"]})
    assert result["analysis"]["status"] == "validated"
    assert result["connection"]["status"] == "candidate"
    connection_id = result["connection"]["id"]

    def finding(c):
        response = c.get(ROOT + "/research/relationships")
        assert response.status_code == 200
        return [row for row in response.json()["connections"] if row["id"] == connection_id]

    assert len(finding(client)) == 1
    post(client, f"/research/memories/{saved['id']}/withdraw", {})
    assert finding(client) == []
    stored = next(row for row in rows(client, CONNECTION_KIND) if row["id"] == connection_id)
    assert stored["status"] == "invalidated"
    assert_no_derived_evidence(client, "cycle collector")
    client.__exit__(None, None, None)
    with TestClient(create_app(settings), headers={"Authorization": f"Bearer {TOKEN}"}) as reopened:
        assert finding(reopened) == []
        assert_no_derived_evidence(reopened, "cycle collector")


def test_probe_B_grant_revoked_during_dispatch_discards_finding(client, monkeypatch):
    _, mdn_grant, preview = _meta_preview(client, monkeypatch)

    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()
        calls = []

        async def slow(*args, **kwargs):
            calls.append(1)
            started.set()
            await release.wait()
            return _fixture_output(args[2])

        monkeypatch.setattr("alive.research_relationships.MetaProvider.structured", slow)
        task = asyncio.create_task(client.app.state.relationships.analyze(preview["id"]))
        try:
            await asyncio.wait_for(started.wait(), timeout=5)
            await client.app.state.web.revoke(mdn_grant["id"])
            await client.app.state.relationships.invalidate_for_grant(mdn_grant["id"])
            release.set()
            result = await task
            assert calls == [1]
            return result
        finally:
            if not task.done():
                task.cancel()
                await task

    result = client.portal.call(scenario)
    assert result["connection"] is None
    assert result["analysis"]["status"] == "invalidated"
    assert result["analysis"]["data"]["dispatch_status"] == "dispatch_possibly_started"
    assert PY_TEXT not in json.dumps(result, default=str)
    assert client.get(ROOT + "/research/relationships").json()["connections"] == []


@pytest.mark.parametrize(
    "dispatch_status,charged",
    [
        ("reserved_never_dispatched", 0),
        ("dispatch_possibly_started", 999),
    ],
)
def test_probe_C_restart_charges_according_to_durable_dispatch_marker(
    client, dispatch_status, charged
):
    async def make_reserved_attempt():
        service = client.app.state.relationships
        async with service.k.db.sessions.begin() as session:
            service.web.add(
                session,
                ATTEMPT_KIND,
                {
                    "reserved_tokens": 999,
                    "historical_memory_id": "probe-memory",
                    "dispatch_status": dispatch_status,
                },
                status="reserved",
            )
            control = await session.get(CognitiveControl, service.k.instance_id)
            control.reserved = {"calls": 1, "tokens": 999}

    client.portal.call(make_reserved_attempt)
    client.portal.call(client.app.state.relationships.initialize)
    attempt = rows(client, ATTEMPT_KIND)[0]
    assert attempt["status"] == "interrupted"
    assert attempt["data"]["charged_tokens"] == attempt["data"]["cost_liability_tokens"] == charged
    assert attempt["data"]["settled_from_dispatch_status"] == dispatch_status
