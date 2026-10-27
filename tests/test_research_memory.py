import json
import time

from fastapi.testclient import TestClient

from alive.app import create_app
from alive.web_experience import digest
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
    assert connection["data"]["relation_type"] == "no_supported_connection"
    assert connection["data"]["historical_quote"] is not None
    assert connection["data"]["current_quote"] is None
    assert connection["abstained"] is True


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
