"""Permanent PR-C review assertions; one canonical copy, no diagnostic-only tests."""

import asyncio

from alive.research_relationships import ATTEMPT_KIND
from tests.evidence_leaks import assert_no_derived_evidence
from tests.test_claim_runtime import rows
from tests.test_demo01_foundation_probes import MARK, historical_preview
from tests.test_research_memory import ROOT, post
from tests.test_zz_review_probe import _fixture_output


def test_probe_C_real_midflight_crash_is_charged(client, monkeypatch):
    _, _, _, preview = historical_preview(client, monkeypatch)
    service = client.app.state.relationships

    async def scenario():
        started = asyncio.Event()

        async def hang(*args, **kwargs):
            started.set()
            await asyncio.Event().wait()

        monkeypatch.setattr("alive.research_relationships.MetaProvider.structured", hang)
        task = asyncio.create_task(service.analyze(preview["id"]))
        try:
            await asyncio.wait_for(started.wait(), timeout=5)
            await service.initialize()
        finally:
            task.cancel()
            await task

    client.portal.call(scenario)
    attempt = rows(client, ATTEMPT_KIND)[0]
    assert attempt["status"] == "interrupted"
    data = attempt["data"]
    assert data["settled_from_dispatch_status"] == "dispatch_possibly_started"
    assert data["charged_tokens"] == data["cost_liability_tokens"] == data["reserved_tokens"]


def test_probe_E_revocation_queued_at_dispatch_guard_discards_finding(client, monkeypatch):
    _, _, current, preview = historical_preview(client, monkeypatch)
    service = client.app.state.relationships
    grant_id = current["snapshot"]["parent_id"]

    async def scenario():
        gate, in_guard, revoked = asyncio.Event(), asyncio.Event(), asyncio.Event()
        original_ledger = service._ledger
        calls = []

        async def held_ledger(session, exclude_attempt_id=None):
            if exclude_attempt_id:
                in_guard.set()
                await gate.wait()
            return await original_ledger(session, exclude_attempt_id=exclude_attempt_id)

        async def record_call(*args, **kwargs):
            # A revoke queued behind the guard can commit after its durable marker.
            # Such a call is allowed to finish, but cannot produce a finding.
            calls.append(1)
            await revoked.wait()
            return _fixture_output(args[2])

        monkeypatch.setattr(service, "_ledger", held_ledger)
        monkeypatch.setattr("alive.research_relationships.MetaProvider.structured", record_call)
        task = asyncio.create_task(service.analyze(preview["id"]))
        revoke = None
        try:
            await asyncio.wait_for(in_guard.wait(), timeout=5)
            revoke = asyncio.create_task(service.web.revoke(grant_id))
            await asyncio.sleep(0)  # let revocation queue behind the guard's kernel lock
            assert not revoke.done()
            gate.set()
            await revoke
            revoked.set()
            result = await task
            assert calls == [1]
            return result
        finally:
            gate.set()
            revoked.set()
            if revoke is not None:
                await revoke
            if not task.done():
                task.cancel()
                await task

    result = client.portal.call(scenario)
    assert result["analysis"]["status"] == "invalidated"
    assert result["connection"] is None


def test_probe_D_full_database_scan_after_withdrawal(client, monkeypatch):
    note, saved, current, preview = historical_preview(client, monkeypatch, provider="local_stub")
    post(client, "/research/relationships", {"consent_id": preview["id"]})
    post(
        client,
        "/research/connections",
        {
            "snapshot_id": current["snapshot"]["id"],
            "memory_id": saved["id"],
        },
    )
    post(client, f"/research/memories/{saved['id']}/withdraw", {})
    assert_no_derived_evidence(client, MARK)
    for path in ("/research/relationships", "/research/memories", "", "/research/blind/runs"):
        response = client.get(ROOT + path)
        assert response.status_code == 200
        assert MARK not in response.text
    # Audit originals remain stored, but ordinary note reads are tombstoned.
    response = client.get(ROOT + f"/notes/{note['id']}")
    assert response.status_code == 410
    assert MARK not in response.text


def test_probe_F_paired_analysis_is_scrubbed_after_withdrawal(client, monkeypatch):
    _, saved, _, preview = historical_preview(
        client, monkeypatch, mode="paired", provider="local_stub"
    )
    result = post(client, "/research/relationships", {"consent_id": preview["id"]})
    assert result["analysis"]["status"] == "validated"
    post(client, f"/research/memories/{saved['id']}/withdraw", {})
    assert_no_derived_evidence(client, MARK)
    listing = client.get(ROOT + "/research/relationships")
    assert listing.status_code == 200
    assert listing.json()["paired_analyses"] == []
    assert MARK not in listing.text
