"""C0 regression: paired outputs depend on the consent's research-memory lineage.

These tests are local-stub only; no model provider or campaign dispatch.
"""

import json

from tests.test_research_memory import (
    MDN,
    MDN_TEXT,
    ROOT,
    grant,
    historical,
    post,
    snapshot,
)


def test_paired_analysis_invalidated_through_consent_lineage(client, monkeypatch):
    goal, _, _, _, saved = historical(client, monkeypatch)
    current_grant = grant(client, goal["id"], MDN)
    current = snapshot(client, current_grant, MDN, MDN_TEXT)
    preview = post(
        client,
        "/research/outbound/preview",
        {
            "snapshot_id": current["snapshot"]["id"],
            "research_id": saved["id"],
            "provider": "local_stub",
            "analysis_mode": "paired",
            "research_question": "How do the two runtimes reclaim memory?",
        },
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
    post(client, "/research/relationships", {"consent_id": preview["id"]})
    post(client, f"/research/memories/{saved['id']}/withdraw", {})
    listing = client.get(ROOT + "/research/relationships").json()
    assert not any(r["status"] == "validated" for r in listing["paired_analyses"])
    assert "cycle collector" not in json.dumps(listing)


def test_withdrawal_does_not_reappear_in_goal_scoped_read(client, monkeypatch):
    goal, _, _, _, saved = historical(client, monkeypatch)
    post(client, f"/research/memories/{saved['id']}/withdraw", {})
    scoped = client.get(ROOT + "/research/relationships", params={"goal_id": goal["id"]})
    assert scoped.status_code == 200
    assert "cycle collector" not in scoped.text
