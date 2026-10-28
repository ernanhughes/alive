"""Claim-mode review probes using the real pinned synthetic fixture provider.

No injected per-instance map or patched dispatch branch: these assertions exercise
what the application actually exposes, and fail if an external provider is entered.
"""

import pytest

from alive.claim_fixtures import HISTORICAL_TEXT
from alive.research_relationships import ATTEMPT_KIND, CONNECTION_KIND, CONSENT_KIND
from tests.evidence_leaks import assert_no_derived_evidence
from tests.test_claim_runtime import analyze, anchor, authorize, preview, rows, setup_claim
from tests.test_research_memory import ROOT, post


@pytest.fixture(autouse=True)
def forbid_external_provider(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Review probe entered the external provider")

    monkeypatch.setattr("alive.research_relationships.MetaProvider", forbidden)


def test_probe_1_fixture_provider_never_reaches_meta(client):
    _, _, request = setup_claim(client)
    consent = preview(client, request)
    authorize(client, consent)
    result = analyze(client, consent)
    assert result["analysis"]["status"] == "validated", result
    assert result["analysis"]["data"]["usage"]["total_tokens"] == 0
    assert result["connection"]["status"] == "candidate"


def test_probe_2_meta_gate(client):
    _, _, request = setup_claim(client)
    client.app.state.kernel.settings.alive_research_meta_enabled = True
    assert client.app.state.kernel.settings.alive_claim_meta_enabled is False
    post(client, "/research/outbound/preview", request | {"provider": "meta"}, 403)
    assert rows(client, CONSENT_KIND) == []
    assert rows(client, ATTEMPT_KIND) == []


def test_probe_3_real_fixture_dispatch_respects_anchor_revision(client):
    saved, _, request = setup_claim(client)
    consent = preview(client, request)
    assert consent["preview"]["reliance"]["revision"] == 1
    assert consent["request"]["schema"]["title"] == "ClaimComparisonOutput"
    authorize(client, consent)
    result = analyze(client, consent)
    assert result["analysis"]["status"] == "validated"
    assert result["connection"]["data"]["relation_type"] == "explicit_supersession"
    assert result["connection"]["data"]["validation"]["decision"] == "accepted"
    anchor(client, saved, revision=1)
    assert client.get(ROOT + "/research/relationships").json()["connections"] == []
    revised = preview(client, request)
    assert revised["payload_sha256"] != consent["payload_sha256"]
    authorize(client, revised)
    fresh = analyze(client, revised)
    assert fresh["connection"]["id"] != result["connection"]["id"]
    assert fresh["connection"]["data"]["reliance"]["revision"] == 2


def test_probe_4_withdrawal_scrubs_copied_claim_fields(client):
    saved, _, request = setup_claim(client)
    consent = preview(client, request)
    authorize(client, consent)
    assert analyze(client, consent)["connection"]["status"] == "candidate"
    post(client, f"/research/memories/{saved['id']}/withdraw", {})
    assert_no_derived_evidence(client, HISTORICAL_TEXT)
    stored = rows(client, CONNECTION_KIND)
    assert len(stored) == 1
    assert stored[0]["status"] == "invalidated"
    assert "reliance" not in stored[0]["data"]
