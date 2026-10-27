import asyncio
import json
import time
from datetime import timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient

from alive.app import create_app
from alive.models import now
from alive.web_experience import WebCompanion, digest, goal_relevance
from alive.web_models import WebExperience
from tests.conftest import TOKEN

ROOT = "/api/v1/browser-experience"
URL = "https://docs.python.org/3/tutorial/"
TEXT = "Python is an easy to learn, powerful programming language. This excerpt is incomplete."


def post(client, path, body, expected=200):
    response = client.post(ROOT + path, json=body)
    assert response.status_code == expected, response.text
    return response.json()


def setup(client):
    goal = post(client, "/goals", {"instruction": "Help me decide where to start learning Python"})
    grant = consent(client, goal["id"])
    return goal, grant


def consent(client, goal_id):
    return post(
        client,
        "/grants",
        {"goal_id": goal_id, "url": URL, "tab_key": "test-session-tab", "approved": True},
    )


def snapshot(client, grant, text=TEXT, expected=200, language="auto"):
    return post(
        client,
        "/snapshots",
        {
            "grant_id": grant["id"],
            "url": URL,
            "title": "Tutorial",
            "text": text,
            "reviewed_sha256": digest(text),
            "language": language,
        },
        expected,
    )


def analyse(client, shot, expected=200, allow_uncertain=False, owner_correction=False):
    return post(
        client,
        "/analyse",
        {
            "snapshot_id": shot["snapshot"]["id"],
            "reviewed_sha256": shot["snapshot"]["data"]["sha256"],
            "send_to_meta": True,
            "allow_uncertain_analysis": allow_uncertain,
            "owner_correction": owner_correction,
        },
        expected,
    )


def wait(client, note_id):
    for _ in range(100):
        row = client.get(ROOT + "/notes/" + note_id).json()
        if row["status"] != "reserved":
            return row
        time.sleep(0.02)
    raise AssertionError("note did not settle")


def fake_model(monkeypatch, quote="Python is an easy to learn"):
    calls = []

    async def structured(*args, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            text=json.dumps(
                {
                    "summary": "A limited introductory note.",
                    "evidence_quote": quote,
                    "limitations": "Only the selected excerpt was read.",
                }
            ),
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        )

    monkeypatch.setattr("alive.web_experience.MetaProvider.structured", structured)
    return calls


def test_feedback_changes_exact_state_choice_and_survives_restart(client, settings, monkeypatch):
    calls = fake_model(monkeypatch)
    goal, grant = setup(client)
    first = snapshot(client, grant)
    note = wait(client, analyse(client, first)["id"])
    assert note["status"] == "validated"
    analyse(client, first, expected=409)
    # A memory alone does not change the action.
    before = snapshot(client, grant)
    assert before["decision"]["action"] == "analyse"
    feedback = post(client, "/feedback", {"note_id": note["id"], "useful": True})
    after = snapshot(client, grant)
    assert before["decision"]["same_state_sha256"] == after["decision"]["same_state_sha256"]
    assert after["decision"]["action"] == "recall"
    assert after["decision"]["without_feedback_action"] == "analyse"
    assert after["decision"]["feedback_id"] == feedback["id"]
    assert after["decision"]["note"]["id"] == note["id"]
    assert after["snapshot"]["data"]["verified_fact"] is False
    assert len(calls) == 1
    client.__exit__(None, None, None)
    with TestClient(create_app(settings), headers={"Authorization": f"Bearer {TOKEN}"}) as reopened:
        snapshot(reopened, grant, expected=403)
        fresh_grant = consent(reopened, goal["id"])
        recalled = snapshot(reopened, fresh_grant)
        assert recalled["decision"]["note"]["id"] == note["id"]
        assert len(calls) == 1


def test_changed_excerpt_and_negative_feedback_prevent_reuse(client, monkeypatch):
    fake_model(monkeypatch)
    _, grant = setup(client)
    shot = snapshot(client, grant)
    note = wait(client, analyse(client, shot)["id"])
    post(client, "/feedback", {"note_id": note["id"], "useful": True})
    changed = snapshot(client, grant, TEXT + " New content.")
    assert changed["decision"]["action"] == "analyse"
    assert changed["snapshot"]["data"]["text_status"] == "changed_excerpt"
    post(client, "/feedback", {"note_id": note["id"], "useful": False})
    assert snapshot(client, grant)["decision"]["action"] == "analyse"


def test_goal_relevance_is_deterministic_and_explicit():
    relevant = goal_relevance("Help me decide where to start learning Python", TEXT)
    assert relevant["policy"] == "deterministic-multilingual-relevance-v2"
    assert relevant["status"] == "supported"
    assert relevant["language"] == "en"
    assert relevant["relevant"] is True
    assert "python" in relevant["matched_terms"]

    irrelevant = goal_relevance("Check coolant temperature", TEXT)
    assert irrelevant["relevant"] is False
    assert irrelevant["matched_terms"] == []

    chinese = goal_relevance(
        "学习 Python 编程", "Python 是一种易于学习、功能强大的编程语言。", language="zh"
    )
    assert chinese["relevant"] is True
    assert {"学习", "编程"} <= set(chinese["matched_terms"])

    arabic = goal_relevance("تعلم البرمجة", "البرمجة سهلة التعلم.", language="ar")
    assert arabic["relevant"] is True

    mismatch = goal_relevance("Learn Python", TEXT, language="zh")
    assert mismatch["status"] == "uncertain"
    assert mismatch["relevant"] is None

    unsupported = goal_relevance("Привет мир", "Python is a language", language="auto")
    assert unsupported["status"] == "uncertain"
    assert unsupported["language_supported"] is False


def test_unrelated_goal_returns_no_action_without_model_call(client, monkeypatch):
    calls = fake_model(monkeypatch)
    goal = post(client, "/goals", {"instruction": "Check coolant temperature"})
    grant = consent(client, goal["id"])
    shot = snapshot(client, grant)

    decision = shot["decision"]
    assert decision["action"] == "no_action"
    assert decision["without_feedback_action"] == "no_action"
    assert decision["goal_relevance"]["relevant"] is False
    assert decision["inference_calls"] == 0
    assert decision["note"] is None and decision["candidate_note"] is None
    assert "does not match" in decision["reason"]
    assert not calls

    # The API must enforce the same gate, not rely on the panel disabling a button.
    analyse(client, shot, expected=409)
    assert not calls


def test_uncertain_language_requires_explicit_override(client, monkeypatch):
    calls = fake_model(monkeypatch)
    goal = post(client, "/goals", {"instruction": "Learn Python"})
    grant = consent(client, goal["id"])
    shot = snapshot(client, grant, language="zh")

    decision = shot["decision"]
    assert decision["action"] == "uncertain"
    assert decision["language_source"] == "explicit_mismatch"
    assert decision["goal_relevance"]["relevant"] is None
    assert decision["inference_calls"] == 0
    assert not calls

    analyse(client, shot, expected=409)
    assert not calls

    analysed = analyse(client, shot, allow_uncertain=True)
    note = wait(client, analysed["id"])
    assert note["status"] == "validated"
    assert note["data"]["language_override"] is True
    assert len(calls) == 1


def test_chinese_relevant_goal_analyses_and_recalls(client, monkeypatch):
    calls = fake_model(monkeypatch, quote="Python 是一种易于学习")
    text = "Python 是一种易于学习、功能强大的编程语言。"
    goal = post(client, "/goals", {"instruction": "学习 Python 编程"})
    grant = consent(client, goal["id"])
    shot = snapshot(client, grant, text=text, language="zh")

    assert shot["decision"]["action"] == "analyse"
    assert shot["decision"]["language"] == "zh"
    note = wait(client, analyse(client, shot)["id"])
    assert note["status"] == "validated"
    post(client, "/feedback", {"note_id": note["id"], "useful": True})
    recalled = snapshot(client, grant, text=text, language="zh")
    assert recalled["decision"]["action"] == "recall"
    assert recalled["decision"]["note"]["id"] == note["id"]
    assert len(calls) == 1


def test_exact_consent_hash_and_owner_goal_isolation(client, monkeypatch):
    fake_model(monkeypatch)
    goal, grant = setup(client)
    for url in [URL + "?secret=x", URL + "index.html", "https://example.com", URL + "../"]:
        post(
            client,
            "/grants",
            {"goal_id": goal["id"], "url": url, "tab_key": "test-session-tab", "approved": True},
            403,
        )
    post(
        client,
        "/snapshots",
        {
            "grant_id": grant["id"],
            "url": URL,
            "title": "Tutorial",
            "text": TEXT,
            "reviewed_sha256": "wrong",
        },
        403,
    )
    shot = snapshot(client, grant)
    note = wait(client, analyse(client, shot)["id"])
    post(client, "/feedback", {"note_id": note["id"], "useful": True})
    _, other = setup(client)
    assert snapshot(client, other)["decision"]["action"] == "analyse"
    post(client, "/grants/" + grant["id"] + "/revoke", {})
    snapshot(client, grant, expected=403)
    analyse(client, shot, expected=403)


def test_zero_governor_budget_blocks_calls(client, monkeypatch):
    calls = fake_model(monkeypatch)
    _, grant = setup(client)
    shot = snapshot(client, grant)
    assert (
        client.post("/api/v1/cognition/configuration", json={"session_calls": 0}).status_code == 200
    )
    analyse(client, shot, expected=409)
    assert not calls


def test_bad_citation_preserves_failure_and_consumes_reservation(client, monkeypatch):
    fake_model(monkeypatch, "invented evidence")
    _, grant = setup(client)
    note = wait(client, analyse(client, snapshot(client, grant))["id"])
    assert note["status"] == "failed"
    assert note["data"]["error"] == "ValueError"
    assert note["data"]["charged_tokens"] == note["data"]["reserved_tokens"]
    post(client, "/feedback", {"note_id": note["id"], "useful": True}, 409)


def test_stop_cancels_paid_worker_and_settles_unknown_usage(client, monkeypatch):
    import asyncio

    async def blocked(*args, **kwargs):
        await asyncio.sleep(30)

    monkeypatch.setattr("alive.web_experience.MetaProvider.structured", blocked)
    _, grant = setup(client)
    note_id = analyse(client, snapshot(client, grant))["id"]
    assert client.post("/api/v1/cognition/configuration", json={}).status_code == 409
    assert client.post("/api/v1/alive/stop").status_code == 200
    row = wait(client, note_id)
    assert row["status"] == "failed"
    assert row["data"]["error"] == "CancelledError"
    assert row["data"]["charged_tokens"] == row["data"]["reserved_tokens"]
    snapshot(client, grant, expected=403)


def test_revocation_before_inference_prevents_provider_call(client, monkeypatch):
    calls = fake_model(monkeypatch)
    _, grant = setup(client)
    shot = snapshot(client, grant)

    original_execute = WebCompanion.execute

    async def delayed_execute(self, note_id, context, cfg, reserve):
        await asyncio.sleep(0.5)
        return await original_execute(self, note_id, context, cfg, reserve)

    async def no_cancel(self):
        return None

    monkeypatch.setattr(WebCompanion, "execute", delayed_execute)
    monkeypatch.setattr(WebCompanion, "cancel", no_cancel)

    note_id = analyse(client, shot)["id"]
    post(client, "/grants/" + grant["id"] + "/revoke", {})
    row = wait(client, note_id)

    assert row["status"] == "failed"
    assert row["data"]["error"] == "PermissionError"
    assert row["data"]["charged_tokens"] == row["data"]["reserved_tokens"]
    assert not calls
    assert client.get(ROOT).json()["active"] is False


def test_feedback_policy_is_idempotent_and_revision_replaces_evidence(client, monkeypatch):
    fake_model(monkeypatch)
    _, grant = setup(client)
    shot = snapshot(client, grant)
    note = wait(client, analyse(client, shot)["id"])

    first = post(client, "/feedback", {"note_id": note["id"], "useful": True})
    assert first["data"]["policy_version_before"] == 0
    assert first["data"]["policy_version_after"] == 1
    duplicate = post(client, "/feedback", {"note_id": note["id"], "useful": True})
    assert duplicate["idempotent"] is True
    assert duplicate["data"]["policy_version_after"] == 1

    revised = post(client, "/feedback", {"note_id": note["id"], "useful": False})
    assert revised["data"]["revision"] is True
    assert revised["data"]["policy_version_before"] == 1
    assert revised["data"]["policy_version_after"] == 2

    policy = client.get(ROOT).json()["policy"]["data"]
    assert policy["version"] == 2
    context = next(iter(policy["contexts"].values()))
    assert len(context["evidence"]) == 1
    assert next(iter(context["evidence"].values()))["useful"] is False


def test_three_negative_feedback_suppresses_analysis_and_owner_correction_restores(
    client, monkeypatch
):
    calls = fake_model(monkeypatch)
    _, grant = setup(client)
    texts = [TEXT, TEXT + " Extra one.", TEXT + " Extra two."]
    for text in texts:
        shot = snapshot(client, grant, text=text)
        assert shot["decision"]["action"] == "analyse"
        note = wait(client, analyse(client, shot)["id"])
        post(client, "/feedback", {"note_id": note["id"], "useful": False})
    assert len(calls) == 3

    fourth_text = TEXT + " Fourth distinct excerpt."
    fourth = snapshot(client, grant, text=fourth_text)
    decision = fourth["decision"]
    assert decision["action"] == "no_action"
    assert decision["no_action_source"] == "feedback_policy"
    assert decision["adaptive_policy"]["support"] == 3
    assert decision["adaptive_policy"]["useful"] == 0
    assert len(calls) == 3

    analyse(client, fourth, expected=409)
    assert len(calls) == 3

    analysed = analyse(client, fourth, owner_correction=True)
    note = wait(client, analysed["id"])
    assert note["data"]["owner_correction"] is True
    assert len(calls) == 4
    post(client, "/feedback", {"note_id": note["id"], "useful": True})

    fifth = snapshot(client, grant, text=TEXT + " Fifth distinct excerpt.")
    assert fifth["decision"]["action"] == "analyse"
    assert fifth["decision"]["adaptive_policy"]["support"] == 4
    assert fifth["decision"]["adaptive_policy"]["useful"] == 1
    assert fifth["decision"]["adaptive_policy"]["useful_rate"] == 0.25

    corrections = client.get(ROOT).json()["corrections"]
    assert any(row["data"]["snapshot_id"] == fourth["snapshot"]["id"] for row in corrections)


def test_lexical_no_action_requires_explicit_owner_correction(client, monkeypatch):
    calls = fake_model(monkeypatch)
    goal = post(client, "/goals", {"instruction": "Check coolant temperature"})
    grant = consent(client, goal["id"])
    shot = snapshot(client, grant)
    assert shot["decision"]["action"] == "no_action"
    assert shot["decision"]["no_action_source"] == "lexical_relevance"

    analyse(client, shot, expected=409)
    assert not calls
    analysed = analyse(client, shot, owner_correction=True)
    note = wait(client, analysed["id"])
    assert note["data"]["owner_correction"] is True
    assert len(calls) == 1
    corrections = client.get(ROOT).json()["corrections"]
    assert corrections[-1]["data"]["prior_action"] == "no_action"


def test_owner_correction_cannot_bypass_revoked_grant(client, monkeypatch):
    calls = fake_model(monkeypatch)
    goal = post(client, "/goals", {"instruction": "Check coolant temperature"})
    grant = consent(client, goal["id"])
    shot = snapshot(client, grant)
    post(client, "/grants/" + grant["id"] + "/revoke", {})
    analyse(client, shot, expected=403, owner_correction=True)
    assert not calls


def test_owner_correction_cannot_bypass_expired_grant(client, monkeypatch):
    calls = fake_model(monkeypatch)
    goal = post(client, "/goals", {"instruction": "Check coolant temperature"})
    grant = consent(client, goal["id"])
    shot = snapshot(client, grant)

    async def expire():
        async with client.app.state.kernel.db.sessions.begin() as session:
            row = await session.get(WebExperience, grant["id"])
            row.data = row.data | {"expires_at": (now() - timedelta(minutes=1)).isoformat()}

    asyncio.run(expire())
    analyse(client, shot, expected=403, owner_correction=True)
    assert not calls


def test_adaptive_policy_persists_across_restart(client, settings, monkeypatch):
    calls = fake_model(monkeypatch)
    goal, grant = setup(client)
    texts = [TEXT, TEXT + " Restart one.", TEXT + " Restart two."]
    for text in texts:
        shot = snapshot(client, grant, text=text)
        note = wait(client, analyse(client, shot)["id"])
        post(client, "/feedback", {"note_id": note["id"], "useful": False})
    assert client.get(ROOT).json()["policy"]["data"]["version"] == 3
    assert len(calls) == 3

    client.__exit__(None, None, None)
    with TestClient(create_app(settings), headers={"Authorization": f"Bearer {TOKEN}"}) as reopened:
        fresh_grant = consent(reopened, goal["id"])
        fourth = snapshot(reopened, fresh_grant, text=TEXT + " Restart fourth excerpt.")
        assert fourth["decision"]["action"] == "no_action"
        assert fourth["decision"]["adaptive_policy"]["support"] == 3
        assert reopened.get(ROOT).json()["policy"]["data"]["version"] == 4
        assert len(calls) == 3


def test_repeated_ratings_of_unchanged_excerpt_count_as_one_evidence_unit(client, monkeypatch):
    calls = fake_model(monkeypatch)
    _, grant = setup(client)
    for _ in range(3):
        shot = snapshot(client, grant)
        note = wait(client, analyse(client, shot)["id"])
        feedback = post(client, "/feedback", {"note_id": note["id"], "useful": False})
        assert feedback["data"]["distinct_support"] == 1

    decision = snapshot(client, grant)["decision"]
    assert decision["action"] == "analyse"
    assert decision["adaptive_policy"]["support"] == 1
    assert decision["adaptive_policy"]["distinct_evidence"] == 1
    assert len(calls) == 3
    context = next(iter(client.get(ROOT).json()["policy"]["data"]["contexts"].values()))
    assert len(context["evidence"]) == 1


def test_three_distinct_excerpts_suppress_and_probe_recovers(client, monkeypatch):
    calls = fake_model(monkeypatch)
    _, grant = setup(client)
    for index in range(3):
        shot = snapshot(client, grant, text=TEXT + f" Distinct evidence {index}.")
        note = wait(client, analyse(client, shot)["id"])
        post(client, "/feedback", {"note_id": note["id"], "useful": False})

    suppressed = []
    for index in range(3):
        shot = snapshot(client, grant, text=TEXT + f" Suppressed observation {index}.")
        decision = shot["decision"]
        assert decision["action"] == "no_action"
        assert decision["no_action_source"] == "feedback_policy"
        assert decision["without_feedback_action"] == "analyse"
        assert decision["adaptive_policy"]["support"] == 3
        suppressed.append(decision)
    assert [d["adaptive_policy"]["suppressions"] for d in suppressed] == [1, 2, 3]
    assert len(calls) == 3

    probe = snapshot(client, grant, text=TEXT + " Probe recovery excerpt.")
    decision = probe["decision"]
    assert decision["action"] == "analyse"
    assert decision["probe"] is True
    assert decision["adaptive_policy"]["probe"] is True
    assert decision["adaptive_policy"]["suppressions"] == 0
    assert decision["adaptive_policy"]["probes"] == 1
    note = wait(client, analyse(client, probe)["id"])
    assert len(calls) == 4
    post(client, "/feedback", {"note_id": note["id"], "useful": True})

    restored = snapshot(client, grant, text=TEXT + " After probe excerpt.")
    decision = restored["decision"]
    assert decision["action"] == "analyse"
    assert decision["adaptive_policy"]["support"] == 4
    assert decision["adaptive_policy"]["useful"] == 1
    assert decision["adaptive_policy"]["useful_rate"] == 0.25


def test_exact_useful_recall_precedes_adaptive_pause(client, monkeypatch):
    calls = fake_model(monkeypatch)
    _, grant = setup(client)
    first = snapshot(client, grant)
    note = wait(client, analyse(client, first)["id"])
    post(client, "/feedback", {"note_id": note["id"], "useful": True})
    for index in range(4):
        shot = snapshot(client, grant, text=TEXT + f" Negative evidence {index}.")
        negative = wait(client, analyse(client, shot)["id"])
        post(client, "/feedback", {"note_id": negative["id"], "useful": False})

    exact = snapshot(client, grant)
    decision = exact["decision"]
    assert decision["action"] == "recall"
    assert decision["note"]["id"] == note["id"]
    assert decision["adaptive_policy"]["support"] == 5
    assert decision["adaptive_policy"]["useful"] == 1
    assert decision["adaptive_policy"]["useful_rate"] == 0.2
    assert len(calls) == 5


def test_failed_feedback_does_not_change_policy(client, monkeypatch):
    fake_model(monkeypatch, "invented evidence")
    _, grant = setup(client)
    note = wait(client, analyse(client, snapshot(client, grant))["id"])
    assert note["status"] == "failed"
    before = client.get(ROOT).json()["policy"]["data"]
    post(client, "/feedback", {"note_id": note["id"], "useful": True}, 409)
    after = client.get(ROOT).json()["policy"]["data"]
    assert after["version"] == before["version"]
    assert after == before


def test_failed_governor_correction_does_not_reset_suppression(client, monkeypatch):
    calls = fake_model(monkeypatch)
    _, grant = setup(client)
    for index in range(3):
        shot = snapshot(client, grant, text=TEXT + f" Governor evidence {index}.")
        note = wait(client, analyse(client, shot)["id"])
        post(client, "/feedback", {"note_id": note["id"], "useful": False})

    fourth = snapshot(client, grant, text=TEXT + " Governor suppressed excerpt.")
    assert fourth["decision"]["action"] == "no_action"
    before = client.get(ROOT).json()["policy"]["data"]
    assert next(iter(before["contexts"].values()))["suppressions"] == 1

    assert (
        client.post("/api/v1/cognition/configuration", json={"session_calls": 0}).status_code == 200
    )
    analyse(client, fourth, expected=409, owner_correction=True)
    after = client.get(ROOT).json()["policy"]["data"]
    assert after["version"] == before["version"]
    assert after == before
    assert client.get(ROOT).json()["corrections"] == []
    assert len(calls) == 3


def test_feedback_duplicate_evidence_does_not_increment_policy(client, monkeypatch):
    fake_model(monkeypatch)
    _, grant = setup(client)
    first = snapshot(client, grant)
    first_note = wait(client, analyse(client, first)["id"])
    one = post(client, "/feedback", {"note_id": first_note["id"], "useful": False})
    assert one["data"]["policy_version_after"] == 1

    second = snapshot(client, grant)
    second_note = wait(client, analyse(client, second)["id"])
    duplicate = post(client, "/feedback", {"note_id": second_note["id"], "useful": False})
    assert duplicate["data"]["duplicate_evidence"] is True
    assert duplicate["data"]["policy_changed"] is False
    assert duplicate["data"]["policy_version_after"] == 1
    context = next(iter(client.get(ROOT).json()["policy"]["data"]["contexts"].values()))
    assert len(context["evidence"]) == 1
