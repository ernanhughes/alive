"""Claim runtime qualification with pinned synthetic sources and zero provider calls.

The prerequisite validated note is seeded directly; save and all later lifecycle
steps use real application APIs. These are not capture-v2 or real-source fixtures.
"""

import asyncio
import hashlib
import json
import os
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from alive.app import create_app
from alive.claim_comparison import CLAIM_VERSION
from alive.claim_fixtures import CLAIM_FIXTURES, CURRENT_TEXTS, HISTORICAL_TEXT
from alive.cognitive_models import CognitiveControl
from alive.models import now
from alive.research_relationships import ATTEMPT_KIND, CONNECTION_KIND, CONSENT_KIND
from tests.conftest import TOKEN
from tests.test_research_memory import MDN, PY, ROOT, goal, grant, post, snapshot


@pytest.fixture
def settings(settings):
    """Optionally run these tests in a fresh PostgreSQL database per test.

    ALIVE_CLAIM_TEST_PG_URL must name an isolated test server's admin database.
    The default remains the ordinary temporary SQLite fixture.
    """
    admin_url = os.environ.get("ALIVE_CLAIM_TEST_PG_URL")
    if not admin_url:
        yield settings
        return

    from sqlalchemy import text
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import create_async_engine

    database_name = "alive_claim_test_" + uuid.uuid4().hex
    url = make_url(admin_url).set(drivername="postgresql+asyncpg")

    async def manage(create):
        engine = create_async_engine(url, isolation_level="AUTOCOMMIT")
        try:
            async with engine.connect() as connection:
                if create:
                    await connection.execute(text(f'CREATE DATABASE "{database_name}"'))
                else:
                    await connection.execute(text(f'DROP DATABASE "{database_name}" WITH (FORCE)'))
        finally:
            await engine.dispose()

    asyncio.run(manage(True))
    settings.database_url = url.set(database=database_name).render_as_string(hide_password=False)
    try:
        yield settings
    finally:
        asyncio.run(manage(False))


@pytest.fixture(autouse=True)
def forbid_models(monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("Claim qualification must never call a model provider")

    monkeypatch.setattr("alive.providers.MetaProvider.structured", forbidden)


def setup_claim(client, label="explicit_supersession", suffix=""):
    client.app.state.kernel.settings.alive_relationship_allow_test_providers = True
    g = goal(client, "Compare the synthetic fixture interface")
    hg = grant(client, g["id"], PY)
    hs = snapshot(client, hg, PY, HISTORICAL_TEXT)["snapshot"]

    async def seed_note():
        web = client.app.state.web
        async with web.k.lock, web.k.db.sessions.begin() as session:
            note = web.add(
                session,
                "note",
                {
                    "goal_id": g["id"],
                    "url": PY,
                    "sha256": hs["data"]["sha256"],
                    "output": {
                        "summary": "Synthetic prerequisite note.",
                        "evidence_quote": HISTORICAL_TEXT,
                        "limitations": "Seeded locally; no inference.",
                    },
                },
                hs["id"],
                "validated",
            )
            await session.flush()
            return note.id

    saved = post(client, "/research/memories", {"note_id": client.portal.call(seed_note)})
    anchor(client, saved)
    cg = grant(client, g["id"], MDN)
    current = snapshot(client, cg, MDN, CURRENT_TEXTS[label] + suffix)["snapshot"]
    request = {
        "snapshot_id": current["id"],
        "research_id": saved["id"],
        "analysis_mode": "claim_comparison",
        "provider": "local_fixture_claim",
    }
    return saved, cg, request


def anchor(client, saved, revision=0, **changes):
    return post(
        client,
        f"/research/memories/{saved['id']}/anchor",
        {
            "quote": HISTORICAL_TEXT,
            "expected_sha256": saved["data"]["sha256"],
            "expected_revision": revision,
            **changes,
        },
    )


def preview(client, request):
    return post(client, "/research/outbound/preview", request)


def authorize(client, consent):
    return post(
        client,
        "/research/outbound/authorize",
        {
            "consent_id": consent["id"],
            "payload_sha256": consent["payload_sha256"],
            "approved": True,
        },
    )


def analyze(client, consent):
    return post(client, "/research/relationships", {"consent_id": consent["id"]})


def rows(client, kind):
    async def read():
        from alive.models import record

        web = client.app.state.web
        async with web.k.db.sessions() as session:
            return [record(row) for row in await web.rows(session, kind)]

    return client.portal.call(read)


def mutate(client, kind, identifier, changes):
    async def update():
        web = client.app.state.web
        async with web.k.lock, web.k.db.sessions.begin() as session:
            row = await web.get(session, identifier, kind)
            row.data = row.data | changes

    client.portal.call(update)


def assert_no_copies(records):
    encoded = json.dumps(records, default=str)
    for text in (HISTORICAL_TEXT, *CURRENT_TEXTS.values()):
        assert text not in encoded
    for row in records:
        assert "reliance" not in row["data"]
        assert "raw_response" not in row["data"]
        assert "payload" not in row["data"]


@pytest.mark.parametrize("label", CURRENT_TEXTS)
def test_pinned_pair_dispatch_storage_and_listing(client, label):
    saved, _, request = setup_claim(client, label)
    consent = preview(client, request)
    assert consent["preview"]["reliance"]["revision"] == 1
    from alive.research_relationships import _digest

    assert consent["payload_sha256"] == _digest(consent["preview"])
    assert consent["request"]["schema"]["title"] == "ClaimComparisonOutput"
    authorize(client, consent)
    result = analyze(client, consent)
    assert result["analysis"]["status"] == "validated", result
    data = result["analysis"]["data"]
    assert data["analysis_version"] == data["validator_version"] == CLAIM_VERSION
    assert data["analysis_mode"] == "claim_comparison"
    assert data["charged_tokens"] == data["cost_liability_tokens"] == 0
    assert data["usage"]["total_tokens"] == 0
    listing = client.get(ROOT + "/research/relationships").json()
    if label == "supports":
        assert result["connection"] is None
        assert listing["connections"] == []
    else:
        assert result["connection"]["status"] == "candidate"
        assert result["connection"]["data"]["relation_type"] == label
        assert listing["connections"][0]["id"] == result["connection"]["id"]
    post(client, "/research/relationships", {"consent_id": consent["id"]}, 409)


def test_pinned_map_hashes_match_full_source_bytes():
    assert len(CLAIM_FIXTURES) == len(CURRENT_TEXTS)
    for label, current in CURRENT_TEXTS.items():
        pair = (
            hashlib.sha256(current.encode()).hexdigest(),
            hashlib.sha256(HISTORICAL_TEXT.encode()).hexdigest(),
        )
        assert CLAIM_FIXTURES[pair]["relationship"] == label


def test_unknown_pair_fails_closed_and_releases_reservation(client):
    _, _, request = setup_claim(client, suffix=" ")
    consent = preview(client, request)
    authorize(client, consent)
    result = analyze(client, consent)
    assert result["analysis"]["status"] == "failed"
    assert result["connection"] is None
    assert result["analysis"]["data"]["error"] == "ValueError"
    assert result["analysis"]["data"]["charged_tokens"] == 0

    async def reservation():
        kernel = client.app.state.kernel
        async with kernel.db.sessions() as session:
            return (await session.get(CognitiveControl, kernel.instance_id)).reserved

    assert client.portal.call(reservation) == {"calls": 0, "tokens": 0}


def test_full_lifecycle_cache_reanchor_withdraw_restart(client, settings):
    saved, _, request = setup_claim(client)
    consent = preview(client, request)
    authorize(client, consent)
    first = analyze(client, consent)
    again = preview(client, request)
    authorize(client, again)
    cached = analyze(client, again)
    assert cached["cached"] is True
    assert cached["id"] == first["connection"]["id"]
    assert len(rows(client, ATTEMPT_KIND)) == 1
    anchor(client, saved, revision=1)
    assert client.get(ROOT + "/research/relationships").json()["connections"] == []
    for kind in (CONSENT_KIND, ATTEMPT_KIND, CONNECTION_KIND):
        assert_no_copies(rows(client, kind))
    revised = preview(client, request)
    assert revised["payload_sha256"] != consent["payload_sha256"]
    assert revised["request_sha256"] != consent["request_sha256"]
    authorize(client, revised)
    assert analyze(client, revised)["connection"]["id"] != first["connection"]["id"]
    post(client, f"/research/memories/{saved['id']}/withdraw", {})
    for kind in (CONSENT_KIND, ATTEMPT_KIND, CONNECTION_KIND):
        assert_no_copies(rows(client, kind))
    client.__exit__(None, None, None)
    with TestClient(create_app(settings), headers={"Authorization": f"Bearer {TOKEN}"}) as reopened:
        listing = reopened.get(ROOT + "/research/relationships").json()
        assert listing["connections"] == listing["analyses"] == []
        for kind in (CONSENT_KIND, ATTEMPT_KIND, CONNECTION_KIND):
            assert_no_copies(rows(reopened, kind))


def test_anchor_http_conflicts_and_invalid_spans(client):
    saved, _, _ = setup_claim(client)
    path = f"/research/memories/{saved['id']}/anchor"
    body = {
        "quote": HISTORICAL_TEXT,
        "expected_sha256": saved["data"]["sha256"],
        "expected_revision": 1,
    }
    post(client, path, body | {"expected_revision": 0}, 409)
    post(client, path, body | {"expected_sha256": "0" * 64}, 409)
    post(client, path, body | {"quote": "This quote does not occur in the source."}, 422)
    post(client, path, body | {"occurrence_start": 1}, 422)
    post(client, path, body | {"quote": "short"}, 422)


def test_test_provider_and_paid_mode_are_disabled_by_default(client):
    _, _, request = setup_claim(client)
    settings = client.app.state.kernel.settings
    settings.alive_relationship_allow_test_providers = False
    post(client, "/research/outbound/preview", request, 403)
    settings.alive_research_meta_enabled = True
    assert settings.alive_claim_meta_enabled is False
    post(client, "/research/outbound/preview", request | {"provider": "meta"}, 403)
    post(client, "/research/outbound/preview", request | {"provider": "local_stub"}, 403)
    post(client, "/research/outbound/preview", request | {"analysis_mode": "history_assisted"}, 403)


@pytest.mark.parametrize("phase", ["pending", "authorized", "settled", "cached"])
def test_owner_revocation_invalidates_current_grant_lineage(client, phase):
    _, cg, request = setup_claim(client)
    consent = preview(client, request)
    if phase != "pending":
        authorize(client, consent)
    if phase in ("settled", "cached"):
        analyze(client, consent)
    if phase == "cached":
        other = preview(client, request)
        authorize(client, other)
        assert analyze(client, other)["cached"]
    post(client, f"/grants/{cg['id']}/revoke", {})
    assert client.get(ROOT + "/research/relationships").json()["connections"] == []
    for kind in (CONSENT_KIND, ATTEMPT_KIND, CONNECTION_KIND):
        records = rows(client, kind)
        assert_no_copies(records)
        assert all(r["status"] == "invalidated" and r["data"]["owner_revoked"] for r in records)


@pytest.mark.parametrize("authorized", [False, True])
def test_expired_consent_never_dispatches(client, authorized):
    _, _, request = setup_claim(client)
    consent = preview(client, request)
    if authorized:
        authorize(client, consent)
    mutate(
        client,
        CONSENT_KIND,
        consent["id"],
        {"expires_at": (now() - timedelta(seconds=1)).isoformat()},
    )
    if authorized:
        post(client, "/research/relationships", {"consent_id": consent["id"]}, 403)
    else:
        post(
            client,
            "/research/outbound/authorize",
            {
                "consent_id": consent["id"],
                "payload_sha256": consent["payload_sha256"],
                "approved": True,
            },
            403,
        )
    assert rows(client, ATTEMPT_KIND) == []
    assert rows(client, CONSENT_KIND)[0]["status"] == "expired"


def test_pre_dispatch_revalidation_failure_has_no_cost(client, monkeypatch):
    _, _, request = setup_claim(client)
    consent = preview(client, request)
    authorize(client, consent)
    service = client.app.state.relationships
    original = service._validate_sources
    calls = 0

    async def revoke_at_guard(session, consent):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise PermissionError("Deterministic revocation at dispatch guard")
        return await original(session, consent)

    monkeypatch.setattr(service, "_validate_sources", revoke_at_guard)
    result = analyze(client, consent)
    assert result["analysis"]["status"] == "failed"
    assert result["analysis"]["data"]["dispatch_status"] == "reserved_never_dispatched"
    assert result["analysis"]["data"]["charged_tokens"] == 0
    assert not service.research.outbound_inflight


def test_claim_timeout_settles_without_dispatch(client, monkeypatch):
    _, _, request = setup_claim(client)
    consent = preview(client, request)
    authorize(client, consent)
    service = client.app.state.relationships
    original = service._validate_sources
    calls = 0

    async def stall_at_guard(session, consent):
        nonlocal calls
        calls += 1
        if calls == 2:
            await asyncio.Event().wait()
        return await original(session, consent)

    async def short_timeout():
        kernel = service.k
        async with kernel.db.sessions.begin() as session:
            control = await session.get(CognitiveControl, kernel.instance_id)
            control.configuration = control.configuration | {"wall_seconds": 1}

    client.portal.call(short_timeout)
    monkeypatch.setattr(service, "_validate_sources", stall_at_guard)
    result = analyze(client, consent)
    assert result["analysis"]["status"] == "failed"
    assert result["analysis"]["data"]["error"] == "TimeoutError"
    assert result["analysis"]["data"]["charged_tokens"] == 0
    assert not service.research.outbound_inflight


def test_claim_cancellation_settles_and_propagates(client, monkeypatch):
    _, _, request = setup_claim(client)
    consent = preview(client, request)
    authorize(client, consent)
    service = client.app.state.relationships
    original = service._validate_sources

    async def scenario():
        at_guard = asyncio.Event()
        calls = 0

        async def stall(session, consent):
            nonlocal calls
            calls += 1
            if calls == 2:
                at_guard.set()
                await asyncio.Event().wait()
            return await original(session, consent)

        monkeypatch.setattr(service, "_validate_sources", stall)
        task = asyncio.create_task(service.analyze(consent["id"]))
        await asyncio.wait_for(at_guard.wait(), timeout=5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    client.portal.call(scenario)
    attempt = rows(client, ATTEMPT_KIND)[0]
    assert attempt["status"] == "failed"
    assert attempt["data"]["error"] == "CancelledError"
    assert attempt["data"]["charged_tokens"] == 0
    assert not service.research.outbound_inflight


@pytest.mark.parametrize(
    "dispatch_status",
    [
        "reserved_never_dispatched",
        "dispatch_guard_passed",
        "dispatch_possibly_started",
    ],
)
def test_restart_recovers_local_claim_without_spend_or_replay(client, settings, dispatch_status):
    saved, _, request = setup_claim(client)
    consent = preview(client, request)
    authorize(client, consent)
    reserve = consent["single_call_reservation"]

    async def reserve_attempt():
        service = client.app.state.relationships
        async with service.k.lock, service.k.db.sessions.begin() as session:
            row = await service.web.get(session, consent["id"], CONSENT_KIND)
            row.status = "consumed"
            service.web.add(
                session,
                ATTEMPT_KIND,
                {
                    "analysis_mode": "claim_comparison",
                    "provider": consent["provider"],
                    "consent_id": consent["id"],
                    "historical_memory_id": saved["id"],
                    "current_snapshot_id": request["snapshot_id"],
                    "reserved_tokens": reserve,
                    "dispatch_status": dispatch_status,
                },
                request["snapshot_id"],
                "reserved",
            )
            control = await session.get(CognitiveControl, service.k.instance_id)
            control.reserved = {"calls": 1, "tokens": reserve}

    client.portal.call(reserve_attempt)
    client.__exit__(None, None, None)
    with TestClient(create_app(settings), headers={"Authorization": f"Bearer {TOKEN}"}) as reopened:
        attempt = rows(reopened, ATTEMPT_KIND)[0]
        assert attempt["status"] == "interrupted"
        assert attempt["data"]["settled_from_dispatch_status"] == dispatch_status
        assert attempt["data"]["charged_tokens"] == attempt["data"]["cost_liability_tokens"] == 0
        assert rows(reopened, CONNECTION_KIND) == []
        post(reopened, "/research/relationships", {"consent_id": consent["id"]}, 409)


@pytest.mark.parametrize(
    "mutation,decision",
    [
        ({"current_claim_quote": "A fabricated source quotation."}, "rejected"),
        ({"supersession_basis_quote": None}, "demoted"),
    ],
)
def test_rejected_and_demoted_claims_never_become_candidates(
    client, monkeypatch, mutation, decision
):
    _, _, request = setup_claim(client)
    consent = preview(client, request)
    payload = consent["preview"]
    pair = (payload["current_sha256"], payload["historical_sha256"])
    monkeypatch.setitem(CLAIM_FIXTURES, pair, CLAIM_FIXTURES[pair] | mutation)
    authorize(client, consent)
    result = analyze(client, consent)
    assert result["analysis"]["data"]["validation"]["decision"] == decision
    assert result["connection"] is None
    assert rows(client, CONNECTION_KIND) == []
    assert result["analysis"]["data"]["charged_tokens"] == 0


def test_claim_settlement_rechecks_owner_revocation(client, monkeypatch):
    _, cg, request = setup_claim(client)
    consent = preview(client, request)
    authorize(client, consent)
    service = client.app.state.relationships
    original = service._settlement_source_valid

    async def revoke_at_settlement(session, payload):
        current_grant = await service.web.get(session, cg["id"], "grant")
        current_grant.status = "revoked"
        current_grant.data = current_grant.data | {"owner_revoked": True}
        return await original(session, payload)

    monkeypatch.setattr(service, "_settlement_source_valid", revoke_at_settlement)
    result = analyze(client, consent)
    assert result["analysis"]["status"] == "invalidated"
    assert result["analysis"]["data"]["owner_revoked"] is True
    assert result["analysis"]["data"]["invalid_reason"] == "current_page_grant_revoked"
    assert result["connection"] is None
    assert_no_copies(rows(client, ATTEMPT_KIND))


def test_authorization_hash_and_dispatch_provider_switch_are_rechecked(client, monkeypatch):
    _, _, request = setup_claim(client)
    consent = preview(client, request)
    post(
        client,
        "/research/outbound/authorize",
        {
            "consent_id": consent["id"],
            "payload_sha256": "0" * 64,
            "approved": True,
        },
        403,
    )
    authorize(client, consent)
    service = client.app.state.relationships
    original = service._validate_sources
    calls = 0

    async def disable_at_guard(session, consent):
        nonlocal calls
        calls += 1
        if calls == 2:
            service.settings.alive_relationship_allow_test_providers = False
        return await original(session, consent)

    monkeypatch.setattr(service, "_validate_sources", disable_at_guard)
    result = analyze(client, consent)
    assert result["analysis"]["status"] == "failed"
    assert result["analysis"]["data"]["dispatch_status"] == "reserved_never_dispatched"
    assert result["analysis"]["data"]["charged_tokens"] == 0
