import asyncio
import json
import time
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from alive.app import create_app
from alive.cognitive_models import CognitiveControl, CognitiveObservation, Investigation
from alive.memory import ALL_MEMORY_TYPES
from alive.models import Event, Goal, Instance, Memory, now, uid
from alive.web_experience import digest
from alive.web_models import WebExperience
from tests.conftest import TOKEN

ROOT = "/api/v1/browser-experience"
PY = "https://docs.python.org/3/tutorial/"
MDN = "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide"
PY_TEXT = "Python memory management uses reference counting and a cycle collector."
MDN_TEXT = "JavaScript memory management uses garbage collection and reachability."
GOAL = "Compare Python and JavaScript memory management"


def post(client, path, body, expected=200):
    response = client.post(ROOT + path, json=body)
    assert response.status_code == expected, response.text
    return response.json()


def goal(client, instruction=GOAL):
    return post(client, "/goals", {"instruction": instruction})


def grant(client, goal_id, url):
    return post(
        client,
        "/grants",
        {"goal_id": goal_id, "url": url, "tab_key": "research-memory-tab", "approved": True},
    )


def snapshot(client, grant, url, text):
    return post(
        client,
        "/snapshots",
        {
            "grant_id": grant["id"],
            "url": url,
            "title": "Controlled source",
            "text": text,
            "reviewed_sha256": digest(text),
        },
    )


def analyse(client, shot):
    return post(
        client,
        "/analyse",
        {
            "snapshot_id": shot["snapshot"]["id"],
            "reviewed_sha256": shot["snapshot"]["data"]["sha256"],
            "send_to_meta": True,
        },
    )


def wait(client, note_id):
    for _ in range(100):
        row = client.get(ROOT + "/notes/" + note_id).json()
        if row["status"] != "reserved":
            return row
        time.sleep(0.02)
    raise AssertionError("note did not settle")


def fake_model(monkeypatch):
    from types import SimpleNamespace

    async def structured(*args, **kwargs):
        return SimpleNamespace(
            text=json.dumps(
                {
                    "summary": "A controlled note about memory management.",
                    "evidence_quote": "memory management",
                    "limitations": "Only the controlled excerpt was read.",
                }
            ),
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        )

    monkeypatch.setattr("alive.web_experience.MetaProvider.structured", structured)


def historical(client, monkeypatch):
    fake_model(monkeypatch)
    g = goal(client)
    py_grant = grant(client, g["id"], PY)
    py_shot = snapshot(client, py_grant, PY, PY_TEXT)
    py_note = wait(client, analyse(client, py_shot)["id"])
    saved = post(client, "/research/memories", {"note_id": py_note["id"]})
    return g, py_grant, py_shot, py_note, saved


def connection_fixture(
    client,
    monkeypatch,
    goal_instruction,
    historical_text,
    current_text,
    historical_url=PY,
    current_url=MDN,
):
    from types import SimpleNamespace

    async def structured(*args, **kwargs):
        data = args[2] if len(args) > 2 else kwargs.get("data") or {}
        excerpt = data.get("untrusted_excerpt", historical_text)
        return SimpleNamespace(
            text=json.dumps(
                {
                    "summary": "Controlled connection fixture.",
                    "evidence_quote": excerpt[:100],
                    "limitations": "Only the controlled excerpt was read.",
                }
            ),
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        )

    monkeypatch.setattr("alive.web_experience.MetaProvider.structured", structured)
    g = goal(client, goal_instruction)
    hist_grant = grant(client, g["id"], historical_url)
    hist_shot = snapshot(client, hist_grant, historical_url, historical_text)
    hist_note = wait(
        client,
        post(
            client,
            "/analyse",
            {
                "snapshot_id": hist_shot["snapshot"]["id"],
                "reviewed_sha256": hist_shot["snapshot"]["data"]["sha256"],
                "send_to_meta": True,
                "owner_correction": True,
            },
        )["id"],
    )
    saved = post(client, "/research/memories", {"note_id": hist_note["id"]})
    cur_grant = grant(client, g["id"], current_url)
    current = snapshot(client, cur_grant, current_url, current_text)
    connection = post(
        client,
        "/research/connections",
        {"snapshot_id": current["snapshot"]["id"], "memory_id": saved["id"]},
    )
    return g, saved, current, connection


def test_save_is_idempotent_and_cross_page_retrieval_is_goal_scoped(client, monkeypatch):
    g, _, _, _, saved = historical(client, monkeypatch)
    duplicate = post(client, "/research/memories", {"note_id": saved["parent_id"]})
    assert duplicate["idempotent"] is True
    assert duplicate["id"] == saved["id"]
    assert saved["data"]["url"] == PY
    assert saved["data"]["goal_id"] == g["id"]
    assert saved["data"]["sha256"] == digest(PY_TEXT)
    assert saved["data"]["source_kind"] == "reviewed_browser_excerpt"

    mdn_grant = grant(client, g["id"], MDN)
    current = snapshot(client, mdn_grant, MDN, MDN_TEXT)
    retrieved = post(client, "/research/retrieve", {"snapshot_id": current["snapshot"]["id"]})
    assert retrieved["abstained"] is False
    assert retrieved["results"][0]["memory_id"] == saved["id"]
    assert retrieved["results"][0]["source_url"] == PY
    assert retrieved["results"][0]["source_url"] != MDN
    assert retrieved["results"][0]["sha256"] == digest(PY_TEXT)
    assert retrieved["results"][0]["owner_useful"] is None
    assert "memory management" in retrieved["results"][0]["excerpt"]

    other_goal = goal(client, "Design a Python tutorial")
    other_grant = grant(client, other_goal["id"], PY)
    other_shot = snapshot(client, other_grant, PY, PY_TEXT)
    empty = post(client, "/research/retrieve", {"snapshot_id": other_shot["snapshot"]["id"]})
    assert empty["abstained"] is True


def test_withdraw_removes_memory_from_retrieval_and_restart_cannot_resurrect(
    client, settings, monkeypatch
):
    g, _, _, _, saved = historical(client, monkeypatch)
    mdn_grant = grant(client, g["id"], MDN)
    current = snapshot(client, mdn_grant, MDN, MDN_TEXT)
    assert (
        post(client, "/research/retrieve", {"snapshot_id": current["snapshot"]["id"]})["abstained"]
        is False
    )
    withdrawn = post(client, f"/research/memories/{saved['id']}/withdraw", {})
    assert withdrawn["status"] == "withdrawn"
    assert (
        post(client, "/research/retrieve", {"snapshot_id": current["snapshot"]["id"]})["abstained"]
        is True
    )
    assert post(client, "/research/memories", {"note_id": saved["parent_id"]}, 409)
    assert client.get(ROOT + "/research/memories").json()["memories"] == []

    client.__exit__(None, None, None)
    with TestClient(create_app(settings), headers={"Authorization": f"Bearer {TOKEN}"}) as reopened:
        assert reopened.get(ROOT + "/research/memories").json()["memories"] == []
        assert (
            post(reopened, "/research/retrieve", {"snapshot_id": current["snapshot"]["id"]})[
                "abstained"
            ]
            is True
        )


def test_connection_has_two_sources_and_persisted_feedback(client, monkeypatch):
    g, _, _, _, saved = historical(client, monkeypatch)
    mdn_grant = grant(client, g["id"], MDN)
    current = snapshot(client, mdn_grant, MDN, MDN_TEXT)
    retrieved = post(client, "/research/retrieve", {"snapshot_id": current["snapshot"]["id"]})
    result = retrieved["results"][0]
    connection = post(
        client,
        "/research/connections",
        {"snapshot_id": current["snapshot"]["id"], "memory_id": result["memory_id"]},
    )
    assert connection["data"]["status"] in {"candidate", "insufficient_evidence"}
    assert connection["current_source"]["url"] == MDN
    assert connection["historical_source"]["url"] == PY
    assert connection["historical_source"]["sha256"] == result["sha256"]
    assert connection["data"]["relation_type"] in {
        "topic_overlap_candidate",
        "weak_lexical_overlap",
        "insufficient_evidence",
    }
    if connection["data"]["status"] == "candidate":
        assert connection["data"]["quote_validation"]["current_exact"] is True
        assert connection["data"]["quote_validation"]["historical_exact"] is True
    feedback = post(
        client,
        f"/research/connections/{connection['id']}/feedback",
        {"useful": True},
    )
    assert feedback["data"]["owner_useful"] is True


def test_connection_abstains_without_shared_evidence(client, monkeypatch):
    g, _, _, _, saved = historical(client, monkeypatch)
    mdn_grant = grant(client, g["id"], MDN)
    current = snapshot(
        client,
        mdn_grant,
        MDN,
        "JavaScript syntax covers functions, objects and asynchronous control flow.",
    )
    # The preserved memory is still eligible by goal/URL filtering, but the
    # deterministic connection check has no inspectable shared term.
    connection = post(
        client,
        "/research/connections",
        {"snapshot_id": current["snapshot"]["id"], "memory_id": saved["id"]},
    )
    assert connection["data"]["status"] == "insufficient_evidence"
    assert connection["data"]["relation_type"] == "insufficient_evidence"
    assert connection["data"]["historical_quote"] is None
    assert connection["data"]["current_quote"] is None
    assert connection["data"]["model_evidence_quote"] is not None
    assert connection["abstained"] is True


def seed_research_rows(client, goal_id, items):
    async def seed():
        async with client.app.state.kernel.db.sessions.begin() as session:
            for item in items:
                text = item["text"]
                session.add(
                    WebExperience(
                        id=uid(),
                        instance_id=client.app.state.kernel.instance_id,
                        kind="research_memory",
                        status="active",
                        data={
                            "goal_id": goal_id,
                            "url": item["url"],
                            "title": item.get("title", "Seeded research"),
                            "excerpt": text,
                            "sha256": digest(text),
                            "reviewed_at": item["reviewed_at"],
                            "source_kind": "reviewed_browser_excerpt",
                        },
                    )
                )

    client.portal.call(seed)


def ranked(client, snapshot_id, ranker=None):
    body = {"snapshot_id": snapshot_id, "top_k": 3, "mode": "hybrid"}
    if ranker:
        body["ranker"] = ranker
    return post(client, "/research/retrieve", body)


def test_bm25_prefers_short_specific_source_over_newer_long_prose(client):
    g = goal(client, "Understand Python memory management and garbage collection")
    grant_py = grant(client, g["id"], PY)
    current = snapshot(
        client,
        grant_py,
        PY,
        "Generational collection reduces pauses for short-lived objects in CPython.",
    )
    target = "Generational collection reduces pauses for short-lived objects."
    long_text = (
        target + " Python memory management ordinary retained note about data systems and records."
    )
    seed_research_rows(
        client,
        g["id"],
        [
            {
                "url": "http://127.0.0.1:9300/historical/short",
                "text": target,
                "reviewed_at": (now() - timedelta(days=2)).isoformat(),
            },
            {
                "url": "http://127.0.0.1:9300/historical/long",
                "text": long_text,
                "reviewed_at": now().isoformat(),
            },
        ],
    )
    old = ranked(client, current["snapshot"]["id"], "alive13-scoped-lexical-v1")
    new = ranked(client, current["snapshot"]["id"])
    assert old["results"][0]["source_url"].endswith("/long")
    assert new["results"][0]["source_url"].endswith("/short")
    assert new["ranking_version"] == "alive14-bm25-v1"
    assert new["results"][0]["retrieval_score"] > new["results"][1]["retrieval_score"]


def test_bm25_abstains_when_only_generic_terms_overlap(client):
    g = goal(client, "Understand Python memory management and garbage collection")
    grant_py = grant(client, g["id"], PY)
    current = snapshot(
        client,
        grant_py,
        PY,
        "System data information source process workflow.",
    )
    seed_research_rows(
        client,
        g["id"],
        [
            {
                "url": f"http://127.0.0.1:9300/historical/generic-{index}",
                "text": "System data information source process.",
                "reviewed_at": now().isoformat(),
            }
            for index in range(4)
        ],
    )
    old = ranked(client, current["snapshot"]["id"], "alive13-scoped-lexical-v1")
    new = ranked(client, current["snapshot"]["id"])
    assert len(old["results"]) >= 1
    assert new["abstained"] is True
    assert new["candidate_count"] == 4
    assert new["qualified_count"] == 0


def test_connection_feedback_records_revisions(client, monkeypatch):
    g, _, _, _, saved = historical(client, monkeypatch)
    mdn_grant = grant(client, g["id"], MDN)
    current = snapshot(client, mdn_grant, MDN, MDN_TEXT)
    retrieved = post(client, "/research/retrieve", {"snapshot_id": current["snapshot"]["id"]})
    connection = post(
        client,
        "/research/connections",
        {
            "snapshot_id": current["snapshot"]["id"],
            "memory_id": retrieved["results"][0]["memory_id"],
        },
    )
    first = post(
        client,
        f"/research/connections/{connection['id']}/feedback",
        {
            "factually_supported": "yes",
            "relevant_to_goal": "yes",
            "revealed_new": "no",
            "misleading": "no",
        },
    )
    assert first["data"]["feedback_revision"] == 1
    assert first["data"]["owner_useful"] is True
    second = post(
        client,
        f"/research/connections/{connection['id']}/feedback",
        {
            "factually_supported": "no",
            "relevant_to_goal": "no",
            "misleading": "yes",
        },
    )
    assert second["data"]["feedback_revision"] == 2
    assert second["data"]["owner_useful"] is False
    assert len(second["data"]["feedback_history"]) == 2


def test_withdrawal_is_blocked_while_outbound_analysis_is_inflight(client, monkeypatch):
    g, _, _, _, saved = historical(client, monkeypatch)

    async def withdraw_inflight():
        client.app.state.research.outbound_inflight.add(saved["id"])
        try:
            return await client.app.state.research.withdraw(saved["id"])
        finally:
            client.app.state.research.outbound_inflight.discard(saved["id"])

    with pytest.raises(ValueError, match="outbound analysis"):
        client.portal.call(withdraw_inflight)
    rows = client.get(ROOT + "/research/memories").json()["memories"]
    assert [row["id"] for row in rows] == [saved["id"]]


def test_meta_relationship_preview_is_disabled_by_default(client, monkeypatch):
    g, _, _, _, saved = historical(client, monkeypatch)
    mdn_grant = grant(client, g["id"], MDN)
    current = snapshot(client, mdn_grant, MDN, MDN_TEXT)
    post(
        client,
        "/research/outbound/preview",
        {
            "snapshot_id": current["snapshot"]["id"],
            "research_id": saved["id"],
            "provider": "meta",
        },
        403,
    )


def test_outbound_preview_and_authorisation_bind_the_exact_payload(client, monkeypatch):
    g, _, _, _, saved = historical(client, monkeypatch)
    mdn_grant = grant(client, g["id"], MDN)
    current = snapshot(client, mdn_grant, MDN, MDN_TEXT)
    preview = post(
        client,
        "/research/outbound/preview",
        {"snapshot_id": current["snapshot"]["id"], "research_id": saved["id"]},
    )
    assert preview["status"] == "pending"
    assert preview["preview"]["current_excerpt"] == MDN_TEXT
    assert preview["preview"]["historical_excerpt"] == saved["data"]["excerpt"]
    assert preview["provider"]["external"] is False
    assert preview["requires_owner_authorisation"] is True
    post(
        client,
        "/research/relationships",
        {"consent_id": preview["id"]},
        409,
    )
    post(
        client,
        "/research/outbound/authorize",
        {
            "consent_id": preview["id"],
            "payload_sha256": "0" * 64,
            "approved": True,
        },
        403,
    )
    authorized = post(
        client,
        "/research/outbound/authorize",
        {
            "consent_id": preview["id"],
            "payload_sha256": preview["payload_sha256"],
            "approved": True,
        },
    )
    assert authorized["status"] == "authorized"
    result = post(
        client,
        "/research/relationships",
        {"consent_id": preview["id"]},
    )
    assert result["analysis"]["status"] == "validated"
    assert result["analysis"]["data"]["validation"]["valid"] is True
    assert result["connection"]["data"]["relation_type"] == "possible_conceptual_connection"
    assert result["connection"]["data"]["current_quote"] in MDN_TEXT
    assert result["connection"]["data"]["historical_quote"] in saved["data"]["excerpt"]
    assert result["connection"]["data"]["inference_calls"] == 0
    assert result["analysis"]["data"]["usage"]["total_tokens"] == 0
    post(
        client,
        "/research/relationships",
        {"consent_id": preview["id"]},
        409,
    )


def test_outbound_consent_is_invalidated_by_withdrawal(client, monkeypatch):
    g, _, _, _, saved = historical(client, monkeypatch)
    mdn_grant = grant(client, g["id"], MDN)
    current = snapshot(client, mdn_grant, MDN, MDN_TEXT)
    preview = post(
        client,
        "/research/outbound/preview",
        {"snapshot_id": current["snapshot"]["id"], "research_id": saved["id"]},
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
    post(client, f"/research/memories/{saved['id']}/withdraw", {})
    post(
        client,
        "/research/relationships",
        {"consent_id": preview["id"]},
        409,
    )
    assert client.get(ROOT + "/research/memories").json()["memories"] == []


def test_outbound_consent_rejects_a_revoked_grant(client, monkeypatch):
    g, _, _, _, saved = historical(client, monkeypatch)
    mdn_grant = grant(client, g["id"], MDN)
    current = snapshot(client, mdn_grant, MDN, MDN_TEXT)
    preview = post(
        client,
        "/research/outbound/preview",
        {"snapshot_id": current["snapshot"]["id"], "research_id": saved["id"]},
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
    post(client, f"/grants/{mdn_grant['id']}/revoke", {})
    post(
        client,
        "/research/outbound/preview",
        {"snapshot_id": current["snapshot"]["id"], "research_id": saved["id"]},
        403,
    )
    post(
        client,
        "/research/relationships",
        {"consent_id": preview["id"]},
        409,
    )


def test_outbound_analysis_respects_the_governor_budget(client, monkeypatch):
    g, _, _, _, saved = historical(client, monkeypatch)
    mdn_grant = grant(client, g["id"], MDN)
    current = snapshot(client, mdn_grant, MDN, MDN_TEXT)
    preview = post(
        client,
        "/research/outbound/preview",
        {"snapshot_id": current["snapshot"]["id"], "research_id": saved["id"]},
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
    configured = client.post("/api/v1/cognition/configuration", json={"session_calls": 0})
    assert configured.status_code == 200, configured.text
    post(
        client,
        "/research/relationships",
        {"consent_id": preview["id"]},
        409,
    )


def test_invalid_model_quotations_are_rejected_without_a_connection(client, monkeypatch):
    g, _, _, _, saved = historical(client, monkeypatch)
    mdn_grant = grant(client, g["id"], MDN)
    current = snapshot(client, mdn_grant, MDN, MDN_TEXT)
    client.app.state.kernel.settings.alive_research_meta_enabled = True
    from types import SimpleNamespace

    async def invalid(*args, **kwargs):
        return SimpleNamespace(
            text=json.dumps(
                {
                    "relationship": "possible_conceptual_connection",
                    "explanation": "A hypothesis with an invalid quotation.",
                    "current_quote": "This sentence is not in the current excerpt.",
                    "historical_quote": "This sentence is not in the historical excerpt.",
                    "limitations": "Controlled invalid fixture.",
                    "confidence": 0.2,
                }
            ),
            usage={"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        )

    monkeypatch.setattr("alive.research_relationships.MetaProvider.structured", invalid)
    preview = post(
        client,
        "/research/outbound/preview",
        {
            "snapshot_id": current["snapshot"]["id"],
            "research_id": saved["id"],
            "provider": "meta",
        },
    )
    assert preview["provider"]["external"] is True
    post(
        client,
        "/research/outbound/authorize",
        {
            "consent_id": preview["id"],
            "payload_sha256": preview["payload_sha256"],
            "approved": True,
        },
    )
    result = post(
        client,
        "/research/relationships",
        {"consent_id": preview["id"]},
    )
    assert result["analysis"]["status"] == "rejected"
    assert result["connection"] is None
    assert result["analysis"]["data"]["validation"]["valid"] is False
    assert result["analysis"]["data"]["raw_response"]


def test_repeated_analysis_reuses_the_same_connection(client, monkeypatch):
    g, _, _, _, saved = historical(client, monkeypatch)
    mdn_grant = grant(client, g["id"], MDN)
    current = snapshot(client, mdn_grant, MDN, MDN_TEXT)
    first_preview = post(
        client,
        "/research/outbound/preview",
        {"snapshot_id": current["snapshot"]["id"], "research_id": saved["id"]},
    )
    post(
        client,
        "/research/outbound/authorize",
        {
            "consent_id": first_preview["id"],
            "payload_sha256": first_preview["payload_sha256"],
            "approved": True,
        },
    )
    first = post(
        client,
        "/research/relationships",
        {"consent_id": first_preview["id"]},
    )
    second_preview = post(
        client,
        "/research/outbound/preview",
        {"snapshot_id": current["snapshot"]["id"], "research_id": saved["id"]},
    )
    post(
        client,
        "/research/outbound/authorize",
        {
            "consent_id": second_preview["id"],
            "payload_sha256": second_preview["payload_sha256"],
            "approved": True,
        },
    )
    second = post(
        client,
        "/research/relationships",
        {"consent_id": second_preview["id"]},
    )
    assert second["idempotent"] is True
    assert second["id"] == first["connection"]["id"]
    assert second["reused"] is True


def test_contradictory_sources_are_only_topic_overlap(client, monkeypatch):
    _, _, _, connection = connection_fixture(
        client,
        monkeypatch,
        "Track persistent memory results for agent tasks",
        "Persistent memory improves agent task success in this benchmark.",
        "Persistent memory does not improve agent task success in this benchmark.",
    )
    data = connection["data"]
    assert data["status"] == "candidate"
    assert data["relation_type"] == "topic_overlap_candidate"
    assert "does not establish agreement" in data["explanation"]
    assert data["quote_validation"] == {"current_exact": True, "historical_exact": True}
    for term in data["shared_terms"]:
        assert term in data["current_quote"].lower()
        assert term in data["historical_quote"].lower()
    assert not any(
        claim in data["relation_type"]
        for claim in ("support", "contradict", "complement", "corrobor", "supersede")
    )


def test_unrelated_sources_sharing_generic_words_are_not_semantic_support(client, monkeypatch):
    _, _, _, connection = connection_fixture(
        client,
        monkeypatch,
        "Compare storage systems across domains",
        "The memory system stores records for later review.",
        "The legal system stores records for later review.",
    )
    data = connection["data"]
    assert data["relation_type"] == "topic_overlap_candidate"
    assert "topic-overlap candidate only" in data["explanation"]
    assert "shared words" in data["evidence_policy"]
    assert "support" not in data["relation_type"]
    for term in data["shared_terms"]:
        assert term in data["current_quote"].lower()
        assert term in data["historical_quote"].lower()


def test_competing_methods_sharing_one_term_are_a_weak_overlap(client, monkeypatch):
    _, _, _, connection = connection_fixture(
        client,
        monkeypatch,
        "Compare deterministic and learned selection policies",
        "A deterministic retrieval rule chooses the most recent source.",
        "A learned retrieval policy selects sources from observed feedback.",
    )
    data = connection["data"]
    assert data["relation_type"] == "weak_lexical_overlap"
    assert "requires owner review" in data["explanation"]
    assert data["shared_terms"] == ["retrieval"]
    assert "retrieval" in data["current_quote"].lower()
    assert "retrieval" in data["historical_quote"].lower()


def test_model_quotation_stays_separate_from_the_exact_source_span(client, monkeypatch):
    _, saved, _, connection = connection_fixture(
        client,
        monkeypatch,
        "Inspect a mixed evidence excerpt",
        "Alpha beta gamma. Memory management is important.",
        "Gamma radiation is measured in sieverts.",
    )
    data = connection["data"]
    assert data["historical_quote"] == "Alpha beta gamma."
    assert data["historical_quote"] in saved["data"]["excerpt"]
    assert data["model_evidence_quote"] != data["historical_quote"]
    assert data["model_evidence_quote"] in saved["data"]["excerpt"]
    assert data["quote_validation"]["historical_exact"] is True
    assert data["quote_validation"]["current_exact"] is True


def test_feedback_revision_updates_research_memory_usefulness(client, monkeypatch):
    g, _, _, note, saved = historical(client, monkeypatch)
    post(client, "/feedback", {"note_id": note["id"], "useful": True})
    mdn_grant = grant(client, g["id"], MDN)
    current = snapshot(client, mdn_grant, MDN, MDN_TEXT)
    useful = post(client, "/research/retrieve", {"snapshot_id": current["snapshot"]["id"]})
    assert useful["results"][0]["owner_useful"] is True
    post(client, "/feedback", {"note_id": note["id"], "useful": False})
    revised = post(client, "/research/retrieve", {"snapshot_id": current["snapshot"]["id"]})
    assert revised["results"][0]["owner_useful"] is False
    assert saved["data"]["owner_useful"] is None


def test_scoped_ranking_survives_sixty_general_memory_distractors(client, monkeypatch):
    fake_model(monkeypatch)
    g = goal(client)
    grant_py = grant(client, g["id"], PY)
    instance_id = client.app.state.kernel.instance_id

    async def seed():
        async with client.app.state.kernel.db.sessions.begin() as session:
            for index in range(60):
                session.add(
                    Memory(
                        id=uid(),
                        instance_id=instance_id,
                        content=(
                            "Python memory management ordinary history distractor " + str(index)
                        ),
                        memory_type="experience",
                    )
                )

    client.portal.call(seed)

    async def old_search():
        return await client.app.state.memory.retrieve("memory management", "text", 10)

    old = client.portal.call(old_search)
    assert all(row["memory_type"] != "research_memory" for row in old["results"])

    shot = snapshot(client, grant_py, PY, PY_TEXT)
    note = wait(client, analyse(client, shot)["id"])
    saved = post(client, "/research/memories", {"note_id": note["id"]})
    mdn_grant = grant(client, g["id"], MDN)
    current = snapshot(client, mdn_grant, MDN, MDN_TEXT)
    retrieved = post(client, "/research/retrieve", {"snapshot_id": current["snapshot"]["id"]})
    assert retrieved["results"][0]["memory_id"] == saved["id"]
    assert retrieved["results"][0]["retrieval_method"] == "scoped_bm25_v1"
    assert retrieved["results"][0]["ranking_version"] == "alive14-bm25-v1"
    assert retrieved["scoped_count"] == 1
    assert retrieved["candidate_count"] == 1
    assert retrieved["candidate_limit"] == 5000


def test_general_memory_retrieval_excludes_research_memory(client, monkeypatch):
    g, _, _, _, saved = historical(client, monkeypatch)

    async def general_search():
        return await client.app.state.memory.retrieve("memory management", "hybrid", 20)

    async def empty_allowlist():
        return await client.app.state.memory.retrieve(
            "memory management", "text", 5, memory_types=()
        )

    result = client.portal.call(general_search)
    assert all(row["memory_type"] != "research_memory" for row in result["results"])
    assert all("research_memory" not in json.dumps(row) for row in result["results"])
    with pytest.raises(ValueError, match="must not be empty"):
        client.portal.call(empty_allowlist)
    search = client.post(
        "/api/v1/memories/search", json={"query": "memory management", "mode": "text"}
    ).json()
    assert all(row["memory_type"] != "research_memory" for row in search["results"])
    assert saved["data"]["excerpt"].startswith("Python memory management")


def test_general_investigation_snapshot_excludes_research_memory_sentinel(client, monkeypatch):
    g, _, _, _, saved = historical(client, monkeypatch)
    sentinel = "UNIQUE_RESEARCH_SENTINEL_9F3"

    async def seed_snapshot():
        k = client.app.state.kernel
        identity = k.instance_id
        async with k.db.sessions.begin() as session:
            research_row = await session.get(WebExperience, saved["id"])
            research_row.data = research_row.data | {
                "excerpt": research_row.data["excerpt"] + " " + sentinel
            }
            projection = await session.get(Memory, saved["data"]["memory_projection_id"])
            projection.content = projection.content + " " + sentinel
            if not await session.get(CognitiveControl, identity):
                session.add(
                    CognitiveControl(
                        instance_id=identity,
                        mode="paused",
                        configuration={"session_calls": 10, "session_tokens": 10000},
                        spent={},
                        reserved={},
                    )
                )
            event = Event(
                id=uid(),
                instance_id=identity,
                event_type="test.observation",
                source="test",
                correlation_id=uid(),
                payload={},
                occurred_at=now(),
            )
            session.add(event)
            goal_row = Goal(
                id=uid(),
                instance_id=identity,
                title="General cognition isolation",
                status="active",
            )
            session.add(goal_row)
            await session.flush()
            observation = CognitiveObservation(
                id=uid(),
                instance_id=identity,
                source_event_id=event.id,
                fingerprint="general-isolation-" + uid(),
                content="Python memory management reference counting cycle collector",
                provenance={"url": "http://127.0.0.1:9300/current/general", "claims": []},
                attention={},
                status="OBSERVED",
            )
            session.add(observation)
            await session.flush()
            session.add(
                Memory(
                    id=uid(),
                    instance_id=identity,
                    content="Python memory management ordinary experience note.",
                    memory_type="experience",
                )
            )
            run = Investigation(
                id=uid(),
                instance_id=identity,
                observation_id=observation.id,
                goal_id=goal_row.id,
                state="INVESTIGATING",
                snapshot={},
                history=[],
                budget={"calls": 0, "tokens": 0, "tools": 1},
                usage={"calls": 0, "tokens": 0, "tools": 0},
            )
            session.add(run)
            await session.flush()
            return run.id

    run_id = client.portal.call(seed_snapshot)

    async def build_snapshot():
        return await client.app.state.cognition.world_state(run_id)

    async def old_unscoped_search():
        return await client.app.state.memory.retrieve(
            "Python memory management reference counting",
            "hybrid",
            10,
            memory_types=ALL_MEMORY_TYPES,
        )

    snapshot = client.portal.call(build_snapshot)
    memories = json.dumps(snapshot["memories"])
    assert sentinel not in memories
    assert "ordinary experience note" in memories
    old = client.portal.call(old_unscoped_search)
    assert sentinel in json.dumps(old["results"], default=str)


def test_withdraw_targets_only_the_requested_memory(client, monkeypatch):
    fake_model(monkeypatch)
    g = goal(client)
    py_grant = grant(client, g["id"], PY)
    first_shot = snapshot(client, py_grant, PY, PY_TEXT)
    first_note = wait(client, analyse(client, first_shot)["id"])
    first = post(client, "/research/memories", {"note_id": first_note["id"]})
    second_shot = snapshot(client, py_grant, PY, PY_TEXT + " Second source.")
    second_note = wait(client, analyse(client, second_shot)["id"])
    second = post(client, "/research/memories", {"note_id": second_note["id"]})
    withdrawn = post(client, f"/research/memories/{first['id']}/withdraw", {})
    assert withdrawn["id"] == first["id"]
    rows = client.get(ROOT + "/research/memories").json()["memories"]
    assert [row["id"] for row in rows] == [second["id"]]
    assert post(client, f"/research/memories/{first['id']}/withdraw", {})["id"] == first["id"]


def test_withdraw_rejects_unknown_and_wrong_instance_ids(client, monkeypatch):
    g, _, _, _, saved = historical(client, monkeypatch)
    post(client, "/research/memories/does-not-exist/withdraw", {}, 404)

    async def other_instance():
        async with client.app.state.kernel.db.sessions.begin() as session:
            session.add(Instance(id="other-instance", name="Other"))
            await session.flush()
            session.add(
                WebExperience(
                    id="other-research",
                    instance_id="other-instance",
                    kind="research_memory",
                    status="active",
                    data={},
                )
            )

    client.portal.call(other_instance)
    post(client, "/research/memories/other-research/withdraw", {}, 404)
    rows = client.get(ROOT + "/research/memories").json()["memories"]
    assert [row["id"] for row in rows] == [saved["id"]]


def test_concurrent_withdraw_is_idempotent_and_does_not_resurrect(client, monkeypatch):
    g, _, _, _, saved = historical(client, monkeypatch)

    async def withdraw_twice():
        return await asyncio.gather(
            client.app.state.research.withdraw(saved["id"]),
            client.app.state.research.withdraw(saved["id"]),
            return_exceptions=True,
        )

    results = client.portal.call(withdraw_twice)
    assert all(not isinstance(result, Exception) for result in results)
    assert {result["status"] for result in results} == {"withdrawn"}
    assert client.get(ROOT + "/research/memories").json()["memories"] == []


def test_retrieval_is_local_but_connection_requires_live_grant(client, monkeypatch):
    g, _, _, _, saved = historical(client, monkeypatch)
    mdn_grant = grant(client, g["id"], MDN)
    current = snapshot(client, mdn_grant, MDN, MDN_TEXT)
    post(client, f"/grants/{mdn_grant['id']}/revoke", {})
    local = post(client, "/research/retrieve", {"snapshot_id": current["snapshot"]["id"]})
    assert local["abstained"] is False
    assert local["results"][0]["memory_id"] == saved["id"]
    post(
        client,
        "/research/connections",
        {"snapshot_id": current["snapshot"]["id"], "memory_id": saved["id"]},
        403,
    )


def test_index_repair_refreshes_stale_projection_and_removes_withdrawn_leftovers(
    client, monkeypatch
):
    g, _, _, _, saved = historical(client, monkeypatch)
    projection_id = saved["data"]["memory_projection_id"]

    async def corrupt():
        async with client.app.state.kernel.db.sessions.begin() as session:
            projection = await session.get(Memory, projection_id)
            projection.content = "stale projection content"
            projection.metadata_json = projection.metadata_json | {
                "index_version": "alive11-research-v0"
            }

    client.portal.call(corrupt)
    repaired = post(client, "/research/index/repair", {})
    assert repaired["projection_created"] == 0
    assert repaired["projection_refreshed"] == 1
    assert repaired["withdrawn_skipped"] == 0

    async def check_projection():
        async with client.app.state.kernel.db.sessions() as session:
            projection = await session.get(Memory, projection_id)
            assert projection.content == saved["data"]["excerpt"]
            assert projection.metadata_json["index_version"] == "alive12-research-v1"

    client.portal.call(check_projection)
    again = post(client, "/research/index/repair", {})
    assert again["projection_refreshed"] == 0
    assert again["projection_created"] == 0

    post(client, f"/research/memories/{saved['id']}/withdraw", {})

    async def resurrect_leftover():
        async with client.app.state.kernel.db.sessions.begin() as session:
            session.add(
                Memory(
                    id=projection_id,
                    instance_id=client.app.state.kernel.instance_id,
                    content="leftover withdrawn projection",
                    memory_type="research_memory",
                    metadata_json={"research_memory_id": saved["id"]},
                )
            )

    client.portal.call(resurrect_leftover)
    repaired_after = post(client, "/research/index/repair", {})
    assert repaired_after["active"] == 0
    assert repaired_after["withdrawn_skipped"] == 1

    async def leftover_gone():
        async with client.app.state.kernel.db.sessions() as session:
            assert await session.get(Memory, projection_id) is None

    client.portal.call(leftover_gone)


def test_index_repair_rebuilds_missing_projection_without_resurrection(client, monkeypatch):
    g, _, _, _, saved = historical(client, monkeypatch)
    projection_id = saved["data"]["memory_projection_id"]

    async def remove_projection():
        async with client.app.state.kernel.db.sessions.begin() as session:
            row = await session.get(Memory, projection_id)
            assert row
            await session.delete(row)

    client.portal.call(remove_projection)
    repaired = post(client, "/research/index/repair", {})
    assert repaired["projection_created"] == 1
    assert repaired["withdrawn_skipped"] == 0
    assert repaired["index"]["available"] is False
    mdn_grant = grant(client, g["id"], MDN)
    current = snapshot(client, mdn_grant, MDN, MDN_TEXT)
    assert (
        post(client, "/research/retrieve", {"snapshot_id": current["snapshot"]["id"]})["results"][
            0
        ]["memory_id"]
        == saved["id"]
    )
    post(client, f"/research/memories/{saved['id']}/withdraw", {})
    repaired_after = post(client, "/research/index/repair", {})
    assert repaired_after["active"] == 0
    assert repaired_after["withdrawn_skipped"] == 1
