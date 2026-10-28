"""Real rendered Python mirrors through capture-v2 and ordinary authorized claim mode."""

import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from alive.app import create_app
from alive.claim_comparison import ClaimComparisonOutput, validate_claim
from alive.claim_fixtures import demo_fixtures
from alive.demo_live_01 import DIRECTORY, manifest
from alive.research_relationships import ATTEMPT_KIND
from tests.conftest import TOKEN
from tests.evidence_leaks import assert_no_derived_evidence
from tests.test_claim_runtime import analyze, authorize, preview, rows
from tests.test_claim_runtime import settings as settings
from tests.test_research_memory import ROOT, goal, grant, post

BEHAVIOR = "Return the current UTC date and time, with tzinfo None."
DEPRECATION = "Deprecated since version 3.12: Use datetime.now() with UTC instead."


def capture(name):
    return json.loads((DIRECTORY / (name + ".capture.json")).read_text(encoding="utf-8"))


def setup(client, newer="python-3.12", anchor=True, version=2):
    client.app.state.kernel.settings.alive_relationship_allow_test_providers = True
    g = goal(client, "Investigate datetime.utcnow behavior and recommended standing")
    snapshots = []
    for name in ("python-3.11", newer):
        data = capture(name)
        if version == 1:
            data = {"text": data["text"]}
        url = "http://127.0.0.1:8000/demo-live-01/" + name + ".html"
        permission = grant(client, g["id"], url)
        snapshots.append(
            post(
                client,
                "/snapshots",
                {
                    "grant_id": permission["id"],
                    "url": url,
                    "title": name,
                    **data,
                    "reviewed_sha256": hashlib.sha256(data["text"].encode()).hexdigest(),
                },
            )["snapshot"]
        )
    saved = post(client, "/research/memories", {"snapshot_id": snapshots[0]["id"]})
    if anchor:
        post(
            client,
            f"/research/memories/{saved['id']}/anchor",
            {
                "quote": BEHAVIOR,
                "expected_sha256": saved["data"]["sha256"],
                "expected_revision": 0,
                "occurrence_start": saved["data"]["excerpt"].index(BEHAVIOR),
            },
        )
    request = {
        "snapshot_id": snapshots[1]["id"],
        "research_id": saved["id"],
        "analysis_mode": "claim_comparison",
        "provider": "local_fixture_claim",
    }
    return g, saved, snapshots, request


@pytest.fixture(autouse=True)
def no_external_models(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No external provider may be entered by a live-demo test")

    monkeypatch.setattr("alive.providers.MetaProvider.structured", forbidden)


def test_fixture_bytes_provenance_and_real_neighbor_are_pinned():
    for item in manifest()["sources"]:
        assert (
            hashlib.sha256((DIRECTORY / item["file"]).read_bytes()).hexdigest()
            == item["mirror_html_sha256"]
        )
        data = capture(item["id"])
        assert hashlib.sha256(data["text"].encode()).hexdigest() == item["captured_text_sha256"]
        assert data["capture_entries"] == item["capture_entries"]
        assert (
            "LOCAL MIRROR — PYTHON DOCUMENTATION"
            in (DIRECTORY / item["file"]).read_text(encoding="utf-8")
            if item["kind"] == "local_mirror"
            else item["kind"] == "synthetic"
        )
        if item["kind"] == "local_mirror":
            assert item["upstream_revision"] is None
            assert (
                hashlib.sha256((DIRECTORY / item["source_html_file"]).read_bytes()).hexdigest()
                == item["source_html_sha256"]
            )
            assert [entry["subject"] for entry in data["capture_entries"]] == [
                "datetime.datetime.utcnow",
                "datetime.datetime.utcfromtimestamp",
            ]
    assert DEPRECATION in capture("python-3.12")["text"]
    assert (
        "Deprecated since version 3.12: Use datetime.fromtimestamp() with UTC instead."
        in capture("python-3.12")["text"]
    )


def test_source_save_requires_reviewed_grant_but_no_model_note(client):
    _, saved, snapshots, _ = setup(client)
    assert saved["data"]["source_kind"] == "owner_selected_source"
    assert saved["data"]["note_id"] is None
    assert saved["data"]["capture_format_version"] == 2
    assert saved["data"]["source_identity"]["id"] == "python-3.11"
    again = post(client, "/research/memories", {"snapshot_id": snapshots[0]["id"]})
    assert again["id"] == saved["id"]
    assert again["idempotent"]
    assert rows(client, "note") == []
    assert rows(client, ATTEMPT_KIND) == []


def test_real_mirror_preview_authorize_candidate_reuse_withdraw_restart(client, settings):
    g, saved, snapshots, request = setup(client)
    consent = preview(client, request)
    payload = consent["preview"]
    assert payload["analysis_mode"] == "claim_comparison"
    assert (
        payload["historical_capture_format_version"]
        == payload["current_capture_format_version"]
        == 2
    )
    assert payload["reliance"]["revision"] == 1
    authorize(client, consent)
    result = analyze(client, consent)
    assert result["analysis"]["status"] == "validated", result
    candidate = result["connection"]
    assert candidate["data"]["validation"]["subject_entry"] == "datetime.datetime.utcnow"
    assert candidate["data"]["historical_quote_retained_in_current"] is True
    assert candidate["data"]["claim_aspect"] == "status"
    assert candidate["data"]["supersession_basis_quote"] == DEPRECATION
    assert candidate["status"] == "candidate"
    cached = preview(client, request)
    authorize(client, cached)
    assert analyze(client, cached)["id"] == candidate["id"]
    assert len(rows(client, ATTEMPT_KIND)) == 1
    assert (
        client.get(ROOT + "/research/relationships", params={"goal_id": g["id"]}).json()[
            "connections"
        ][0]["id"]
        == candidate["id"]
    )
    post(client, f"/research/memories/{saved['id']}/withdraw", {})
    assert_no_derived_evidence(client, "tzinfo None")
    assert client.get(ROOT + "/research/relationships").json()["connections"] == []
    client.__exit__(None, None, None)
    with TestClient(create_app(settings), headers={"Authorization": "Bearer " + TOKEN}) as reopened:
        assert reopened.get(ROOT + "/research/relationships").json()["connections"] == []
        assert_no_derived_evidence(reopened, "tzinfo None")


def test_synthetic_newer_source_leaves_a_real_abstention_ledger_entry(client):
    _, _, _, request = setup(client, newer="synthetic-no-change")
    consent = preview(client, request)
    authorize(client, consent)
    result = analyze(client, consent)
    assert result["analysis"]["status"] == "validated"
    assert result["analysis"]["data"]["validation"]["relationship"] == "insufficient_evidence"
    assert result["connection"] is None
    assert result["analysis"]["data"]["charged_tokens"] == 0
    assert result["abstained"]


def test_wrong_method_basis_cannot_be_accepted(client):
    _, _, _, request = setup(client)
    consent = preview(client, request)
    payload = consent["preview"]
    output = demo_fixtures()[(payload["current_sha256"], payload["historical_sha256"])]
    wrong = "Deprecated since version 3.12: Use datetime.fromtimestamp() with UTC instead."
    result = validate_claim(
        ClaimComparisonOutput(
            **(
                output
                | {
                    "current_claim_quote": wrong,
                    "supersession_basis_quote": wrong,
                }
            )
        ),
        payload,
    )
    assert result["decision"] == "demoted"
    assert "current_evidence_outside_anchored_subject_entry" in result["reasons"]


def test_forged_capture_identity_and_entries_abstain(client):
    _, _, _, request = setup(client)
    consent = preview(client, request)
    payload = consent["preview"]
    output = ClaimComparisonOutput(
        **demo_fixtures()[(payload["current_sha256"], payload["historical_sha256"])]
    )
    for changed in (
        {"current_source_identity": None},
        {"current_capture_entries": []},
        {"current_capture_format_version": 1},
    ):
        result = validate_claim(output, payload | changed)
        assert result["decision"] == "demoted"
        assert result["relationship"] == "insufficient_evidence"


def test_anchor_revision_and_goal_isolation(client):
    g, saved, _, request = setup(client)
    pending = preview(client, request)
    post(
        client,
        f"/research/memories/{saved['id']}/anchor",
        {
            "quote": BEHAVIOR,
            "expected_sha256": saved["data"]["sha256"],
            "expected_revision": 1,
        },
    )
    post(
        client,
        "/research/outbound/authorize",
        {
            "consent_id": pending["id"],
            "payload_sha256": pending["payload_sha256"],
            "approved": True,
        },
        409,
    )
    assert rows(client, ATTEMPT_KIND) == []
    revised = preview(client, request)
    assert revised["payload_sha256"] != pending["payload_sha256"]
    assert revised["preview"]["reliance"]["revision"] == 2
    other = goal(client, "A different investigation")
    assert (
        client.get(ROOT + "/research/relationships", params={"goal_id": other["id"]}).json()[
            "connections"
        ]
        == []
    )
    retrieved = post(
        client, "/research/retrieve", {"snapshot_id": request["snapshot_id"], "mode": "text"}
    )
    assert retrieved["results"][0]["reliance_anchor"]["revision"] == 2
    assert retrieved["results"][0]["goal_id"] == g["id"]


def test_invalid_capture_ranges_and_unregistered_mirror_fail_closed(client):
    g = goal(client)
    url = "http://127.0.0.1:8000/demo-live-01/python-3.11.html"
    permission = grant(client, g["id"], url)
    data = capture("python-3.11")
    body = {
        "grant_id": permission["id"],
        "url": url,
        "title": "source",
        **data,
        "reviewed_sha256": hashlib.sha256(data["text"].encode()).hexdigest(),
    }
    post(
        client,
        "/snapshots",
        body | {"capture_entries": [{"subject": "x", "start": 0, "end": 10000}]},
        422,
    )
    changed = data["text"] + " "
    result = post(
        client,
        "/snapshots",
        body | {"text": changed, "reviewed_sha256": hashlib.sha256(changed.encode()).hexdigest()},
    )
    assert result["snapshot"]["data"]["source_identity"] is None
    assert client.get("/demo-live-01/unknown.html").status_code == 404


def test_settlement_rechecks_capture_provenance(client, monkeypatch):
    _, _, snapshots, request = setup(client)
    consent = preview(client, request)
    authorize(client, consent)
    service = client.app.state.relationships
    original = service._settlement_source_valid

    async def changed(session, payload):
        snapshot = await service.web.get(session, snapshots[1]["id"], "snapshot")
        snapshot.data = snapshot.data | {"capture_entries": []}
        return await original(session, payload)

    monkeypatch.setattr(service, "_settlement_source_valid", changed)
    result = analyze(client, consent)
    assert result["analysis"]["status"] == "invalidated"
    assert result["connection"] is None


def test_malformed_or_ambiguous_anchors_are_not_silently_selected(client):
    _, saved, _, _ = setup(client, anchor=False)
    path = f"/research/memories/{saved['id']}/anchor"
    body = {"quote": BEHAVIOR, "expected_sha256": saved["data"]["sha256"], "expected_revision": 0}
    post(client, path, body | {"occurrence_start": 1}, 422)
    post(client, path, body | {"expected_sha256": "0" * 64}, 409)
    post(client, "/research/memories", {}, 422)
    assert client.get("/demo-live-01/python-3.11.html").status_code == 200


def test_real_fixture_cannot_bypass_identity_by_downgrading_to_capture_v1(client):
    _, _, _, request = setup(client, version=1)
    consent = preview(client, request)
    assert "current_source_identity" not in consent["preview"]
    authorize(client, consent)
    result = analyze(client, consent)
    assert result["analysis"]["status"] == "failed"
    assert result["analysis"]["data"]["error"] == "PermissionError"
    assert result["connection"] is None
    assert result["analysis"]["data"]["charged_tokens"] == 0


def test_legacy_named_other_method_is_not_a_supersession():
    historical = "Return the current UTC time."
    current_quote = "Return the local date and time."
    basis = "utcfromtimestamp() is deprecated since 3.12."
    output = ClaimComparisonOutput(
        relationship="explicit_supersession",
        claim_aspect="status",
        historical_claim_quote=historical,
        current_claim_quote=current_quote,
        supersession_basis_quote=basis,
        scope_alignment="same",
        scope_note="Unverified scope.",
        reason="A constructed wrong-method attack.",
        limitations="No entity binding supplied.",
        confidence=0.4,
    )
    result = validate_claim(
        output, {"historical_excerpt": historical, "current_excerpt": current_quote + " " + basis}
    )
    assert result["decision"] == "demoted"
    assert "supersession_named_subject_not_bound" in result["reasons"]
