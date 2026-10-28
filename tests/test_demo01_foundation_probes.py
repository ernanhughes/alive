"""Permanent C-real/D/E/F probes from Claude's PR-C and C1B reviews.

External dispatch is replaced by an in-process fake object. No real MetaProvider
implementation runs. Audit-original retention is tested explicitly, not deletion.
"""

import asyncio
import json
from types import SimpleNamespace

from alive.cognitive_models import CognitiveControl
from alive.research_relationships import ATTEMPT_KIND
from tests.evidence_leaks import assert_no_derived_evidence
from tests.test_claim_runtime import (
    analyze,
    assert_no_copies,
    authorize,
    preview,
    rows,
    setup_claim,
)
from tests.test_claim_runtime import settings as settings
from tests.test_research_memory import MDN, MDN_TEXT, ROOT, grant, historical, post, snapshot

MARK = "cycle collector"


def historical_preview(client, monkeypatch, mode="history_assisted", provider="meta"):
    g, _, _, note, saved = historical(client, monkeypatch)
    cg = grant(client, g["id"], MDN)
    current = snapshot(client, cg, MDN, MDN_TEXT)
    client.app.state.kernel.settings.alive_research_meta_enabled = True
    consent = preview(
        client,
        {
            "snapshot_id": current["snapshot"]["id"],
            "research_id": saved["id"],
            "provider": provider,
            "analysis_mode": mode,
            "research_question": "Compare memory management.",
        },
    )
    authorize(client, consent)
    return note, saved, current, consent


def test_C_real_midflight_recovery_charges_full_liability_once(client, monkeypatch):
    _, _, _, consent = historical_preview(client, monkeypatch)
    service = client.app.state.relationships

    async def scenario():
        entered = asyncio.Event()

        async def hang(*args, **kwargs):
            entered.set()
            await asyncio.Event().wait()

        monkeypatch.setattr(
            "alive.research_relationships.MetaProvider",
            lambda settings: SimpleNamespace(structured=hang),
        )
        async with service.k.db.sessions() as session:
            control = await session.get(CognitiveControl, service.k.instance_id)
            before = control.spent.get("session_calls", 0)
        task = asyncio.create_task(service.analyze(consent["id"]))
        try:
            await asyncio.wait_for(entered.wait(), timeout=5)
            await service.initialize()
        finally:
            task.cancel()
            await task  # ordinary history path settles/returns; never invokes a real provider
        async with service.k.db.sessions() as session:
            control = await session.get(CognitiveControl, service.k.instance_id)
            assert control.reserved == {"calls": 0, "tokens": 0}
            assert control.spent["session_calls"] == before + 1

    client.portal.call(scenario)
    attempt = rows(client, ATTEMPT_KIND)[0]
    assert attempt["status"] == "interrupted"
    data = attempt["data"]
    assert data["settled_from_dispatch_status"] == "dispatch_possibly_started"
    assert data["charged_tokens"] == data["cost_liability_tokens"] == data["reserved_tokens"]
    assert client.get(ROOT + "/research/relationships").json()["connections"] == []


def test_D_all_tables_and_public_reads_after_withdrawal(client, monkeypatch):
    note, saved, current, consent = historical_preview(client, monkeypatch, provider="local_stub")
    analyze(client, consent)
    post(
        client,
        "/research/connections",
        {
            "snapshot_id": current["snapshot"]["id"],
            "memory_id": saved["id"],
        },
    )
    post(client, f"/research/memories/{saved['id']}/withdraw", {})
    hits = assert_no_derived_evidence(client, MARK)
    assert {hit["kind"] for hit in hits} == {"snapshot", "note", "research_memory"}
    for path in ("/research/relationships", "/research/memories", "", "/research/blind/runs"):
        response = client.get(ROOT + path)
        assert response.status_code == 200
        assert MARK not in response.text
    # Existing policy retains the authoritative note endpoint; report this explicitly.
    response = client.get(ROOT + f"/notes/{note['id']}")
    assert response.status_code == 200
    assert MARK in response.text


def test_F_paired_lineage_is_scrubbed_and_hidden(client, monkeypatch):
    _, saved, _, consent = historical_preview(
        client, monkeypatch, mode="paired", provider="local_stub"
    )
    result = analyze(client, consent)
    assert result["analysis"]["status"] == "validated"
    post(client, f"/research/memories/{saved['id']}/withdraw", {})
    assert_no_derived_evidence(client, MARK)
    listing = client.get(ROOT + "/research/relationships").json()
    assert listing["paired_analyses"] == []
    assert MARK not in json.dumps(listing)


def test_E_IE1_committed_revocation_before_marker_never_dispatches(client, monkeypatch):
    _, cg, request = setup_claim(client)
    consent = preview(client, request)
    authorize(client, consent)
    service = client.app.state.relationships
    original = service._validate_sources
    checks = 0

    def forbidden(payload):
        raise AssertionError("Fixture must never dispatch after pre-marker revocation")

    monkeypatch.setattr(service, "_local_fixture_claim", forbidden)

    async def revoke_before_guard(session, consent):
        nonlocal checks
        checks += 1
        if checks == 2:
            # This callback already owns k.lock. Commit revocation in a separate
            # transaction before the guard reads sources or writes its marker.
            async with service.k.db.sessions.begin() as revoke_session:
                row = await service.web.get(revoke_session, cg["id"], "grant")
                row.status = "revoked"
                row.data = row.data | {"owner_revoked": True}
        return await original(session, consent)

    monkeypatch.setattr(service, "_validate_sources", revoke_before_guard)
    result = analyze(client, consent)
    assert result["analysis"]["status"] == "failed"
    data = result["analysis"]["data"]
    assert data["dispatch_status"] == "reserved_never_dispatched"
    assert data["charged_tokens"] == 0
    assert data["owner_revoked"] is True
    assert result["connection"] is None


def test_E_IE2_post_marker_revocation_discards_result(client, monkeypatch):
    _, cg, request = setup_claim(client)
    service = client.app.state.relationships
    service.settings.alive_research_meta_enabled = True
    service.settings.alive_claim_meta_enabled = True
    consent = preview(client, request | {"provider": "meta"})
    authorize(client, consent)
    from alive.claim_fixtures import CLAIM_FIXTURES

    payload = consent["preview"]
    output = CLAIM_FIXTURES[(payload["current_sha256"], payload["historical_sha256"])]

    async def scenario():
        entered, revoked = asyncio.Event(), asyncio.Event()
        calls = []

        async def response(*args, **kwargs):
            calls.append(1)
            entered.set()
            await revoked.wait()
            return SimpleNamespace(
                text=json.dumps(output),
                usage={
                    "prompt_tokens": 10,
                    "completion_tokens": 10,
                    "total_tokens": 20,
                },
            )

        monkeypatch.setattr(
            "alive.research_relationships.MetaProvider",
            lambda settings: SimpleNamespace(structured=response),
        )
        task = asyncio.create_task(service.analyze(consent["id"]))
        try:
            await asyncio.wait_for(entered.wait(), timeout=5)
            async with service.k.db.sessions() as session:
                attempts = await service.web.rows(session, ATTEMPT_KIND)
                assert attempts[0].data["dispatch_status"] == "dispatch_possibly_started"
            await service.web.revoke(cg["id"])
            await service.invalidate_for_grant(cg["id"])
            revoked.set()
            result = await task
            assert calls == [1]
            return result
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    result = client.portal.call(scenario)
    assert result["analysis"]["status"] == "invalidated"
    assert result["analysis"]["data"]["owner_revoked"] is True
    assert result["connection"] is None
    # Revoking the current grant does not withdraw the separate historical memory
    # or its active retrieval projection. Scan its claim dependents here.
    from alive.research_relationships import CONNECTION_KIND, CONSENT_KIND

    for kind in (CONSENT_KIND, ATTEMPT_KIND, CONNECTION_KIND):
        assert_no_copies(rows(client, kind))
