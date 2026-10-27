import asyncio
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from alive.app import create_app
from alive.browser import Browsers
from alive.db import Database
from alive.living_policy import choose, digest, numeric_equal, state_from_dom, update
from alive.models import Base
from tests.conftest import TOKEN


@pytest.fixture
def controlled_browser(monkeypatch):
    def payload(self, session_id):
        page = self._fixture_pages[session_id]
        text = "Claim: Aster endurance_hours 32; History event: source_replaced;"
        if page.retrieved:
            text += " Instrument reading: 20 hours;"
        if page.feedback:
            text += " Feedback measurement: 20 hours;"
        return {
            "text": text,
            "url": page.url,
            "title": "Controlled fixture",
            "session_id": session_id,
        }

    async def create(self):
        if not hasattr(self, "_fixture_pages"):
            self._fixture_pages = {}
        key = "fixture-browser-" + str(len(self._fixture_pages))
        self._fixture_pages[key] = SimpleNamespace(
            url="about:blank", retrieved=False, feedback=False
        )
        return {"id": key}

    async def navigate(self, session_id, url):
        self._fixture_pages[session_id].url = url
        return payload(self, session_id)

    async def action(self, session_id, data):
        assert data.operation == "click" and data.selector in {"#retrieve", "#feedback-button"}
        page = self._fixture_pages[session_id]
        if data.selector == "#retrieve":
            page.retrieved = True
        else:
            page.feedback = True
        return payload(self, session_id)

    async def close(self, session_id):
        self._fixture_pages.pop(session_id, None)

    monkeypatch.setattr(Browsers, "create", create)
    monkeypatch.setattr(Browsers, "navigate", navigate)
    monkeypatch.setattr(Browsers, "action", action)
    monkeypatch.setattr(Browsers, "page", lambda self, key: self._fixture_pages[key])
    monkeypatch.setattr(Browsers, "close_session", close)


def create(client, provider="mock"):
    response = client.post(
        "/api/v1/living/journeys", json={"provider": provider, "allow_controlled_read": True}
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def advance(client, journey):
    response = client.post(f"/api/v1/living/journeys/{journey}/advance", json={})
    assert response.status_code == 200, response.text
    for _ in range(500):
        row = client.get("/api/v1/living/journeys/" + journey).json()
        if row["status"] != "running" and not client.get("/api/v1/living").json()["active"]:
            return row
        time.sleep(0.01)
    raise AssertionError("Living episode did not finish")


def test_empirical_choice_changes_only_after_feedback():
    policy = {"version": 0, "contexts": {}}
    cold = choose(policy)
    assert cold["action"] == "monitor" and cold["predictions"]["retrieve"]["n"] == 0
    learned = update(policy, "monitor", -0.5)
    assert choose(learned)["action"] == "retrieve"
    assert digest(policy) == cold["policy_hash"] and learned["version"] == 1
    assert choose(policy)["action"] == "monitor"
    text = "Claim: Aster endurance_hours 32; History event: source_replaced;"
    fixture_context = state_from_dom(text, "mock")["context"]
    live_context = state_from_dom(text, "meta")["context"]
    fixture_policy = update(policy, "monitor", -0.5, fixture_context)
    assert (
        fixture_context != live_context
        and choose(fixture_policy, live_context)["action"] == "monitor"
    )
    assert numeric_equal("20.000", "20") and not numeric_equal("nan", "20")
    assert not numeric_equal(None, "20") and not numeric_equal(["20"], "20")
    with pytest.raises(ValueError):
        update(policy, "send_message", 1)
    with pytest.raises(ValueError):
        state_from_dom("Untrusted arbitrary browser text")


def test_assessment_checks_claim_against_cited_source_and_requires_feedback_corroboration():
    from alive.cognitive_schema import RoleOutput
    from alive.living_evaluation import assess

    def output(value, recommendation="proceed"):
        return RoleOutput(
            summary="Controlled measurement",
            claims=[
                {
                    "subject": "Aster",
                    "predicate": "endurance_hours",
                    "value": value,
                    "evidence_refs": ["current"],
                }
            ],
            actions=[],
            criticisms=[],
            uncertainties=[],
            recommendation=recommendation,
            confidence=0.9,
        )

    source = [{"id": "current", "value": "20"}]
    contradicted = assess(output("21"), source, "21")
    assert contradicted["factual_correct"] is False
    assert contradicted["feedback_confirms_source"] is False
    assert contradicted["resolved"] is False

    supported_but_unconfirmed = assess(output("20"), source, "21")
    assert supported_but_unconfirmed["factual_correct"] is True
    assert supported_but_unconfirmed["feedback_confirms_source"] is False
    assert supported_but_unconfirmed["resolved"] is False
    assert supported_but_unconfirmed["conclusion_contract_correct"] is False

    confirmed = assess(output("20"), source, "20")
    assert confirmed["factual_correct"] is True
    assert confirmed["feedback_confirms_source"] is True
    assert confirmed["resolved"] is True


def test_supported_fact_is_not_an_incorrect_fact_when_recommendation_is_investigate():
    from alive.cognitive_schema import RoleOutput
    from alive.living_evaluation import assess

    output = RoleOutput(
        summary="Correct measurement, unnecessary follow-up",
        claims=[
            {
                "subject": "Aster",
                "predicate": "endurance_hours",
                "value": "20.0",
                "evidence_refs": ["current"],
            }
        ],
        actions=[],
        criticisms=[],
        uncertainties=[],
        recommendation="investigate",
        confidence=0.9,
    )
    result = assess(output, [{"id": "current", "value": "20"}], "20")
    assert result["factual_correct"] is True
    assert result["resolved"] is False and result["conclusion_contract_correct"] is False


def test_controlled_journey_has_causal_memory_and_real_counterfactual(client, controlled_browser):
    journey = create(client)
    first = advance(client, journey)
    assert first["status"] == "ready", first["data"].get("error")
    a = first["transitions"][0]
    assert a["data"]["choice"]["action"] == "monitor" and a["data"]["reward"] == -0.5
    assert a["data"]["outcome"]["safe_abstention"]
    assert not a["data"]["memory_ids"] and a["data"]["evidence"] is None
    second = advance(client, journey)
    assert second["status"] == "completed", second["data"].get("error")
    b = second["transitions"][1]["data"]
    assert b["choice"]["action"] == "retrieve" and b["reward"] == 0.85
    assert b["initial_policy_counterfactual"]["action"] == "monitor"
    assert b["state"]["feature_hash"] == a["data"]["state"]["feature_hash"]
    assert b["before_hash"] == a["data"]["after_hash"]
    assert b["memory_ids"] == [a["id"]] and b["outcome"]["resolved"]
    assert second["current_policy"]["version"] == 2 and len(second["data"]["ledger"]) == 2
    assert len(second["data"]["tool_log"]) == 5
    assert all(c["usage"]["mode"] == "controlled_fixture" for c in second["data"]["ledger"])
    assert client.post(f"/api/v1/living/journeys/{journey}/advance", json={}).status_code == 409


def test_no_hidden_reset_or_out_of_scope_permission(client, controlled_browser):
    assert client.post("/api/v1/living/journeys", json={"provider": "mock"}).status_code == 422
    assert (
        client.post(
            "/api/v1/living/journeys",
            json={"provider": "mock", "allow_controlled_read": True, "url": "https://example.com"},
        ).status_code
        == 422
    )
    journey = create(client)
    first = advance(client, journey)
    assert client.post(f"/api/v1/living/journeys/{journey}/stop", json={}).status_code == 200
    assert client.post(f"/api/v1/living/journeys/{journey}/advance", json={}).status_code == 409
    new = create(client)
    row = client.get("/api/v1/living/journeys/" + new).json()
    assert row["data"]["initial_policy"] == first["current_policy"]
    context = first["transitions"][0]["data"]["state"]["context"]
    assert choose(row["data"]["initial_policy"], context)["action"] == "retrieve"


def test_zero_governor_budget_blocks_inference_and_policy_update(client, controlled_browser):
    client.post("/api/v1/cognition/configuration", json={"session_calls": 0})
    row = advance(client, create(client))
    assert row["status"] == "failed" and not row["data"]["ledger"]
    assert not row["transitions"] and row["current_policy"]["version"] == 0
    assert "budget exhausted" in row["data"]["error"]


def test_stop_settles_unknown_call_and_forbids_budget_reset(
    client, controlled_browser, monkeypatch
):
    from alive.providers import MetaProvider

    async def discover(self):
        return {"models": ["muse-spark-1.3"]}

    async def wait(*args, **kwargs):
        await asyncio.sleep(300)

    monkeypatch.setattr(MetaProvider, "discover", discover)
    monkeypatch.setattr(MetaProvider, "structured", wait)
    journey = create(client, "meta")
    client.post(f"/api/v1/living/journeys/{journey}/advance", json={})
    for _ in range(300):
        row = client.get("/api/v1/living/journeys/" + journey).json()
        if row["data"]["ledger"]:
            break
        time.sleep(0.01)
    assert row["data"]["ledger"][0]["status"] == "reserved"
    assert (
        client.post("/api/v1/cognition/control", json={"command": "new_session"}).status_code == 409
    )
    assert client.post("/api/v1/cognition/configuration", json={}).status_code == 409
    assert client.post("/api/v1/alive/stop", json={}).status_code == 200
    row = client.get("/api/v1/living/journeys/" + journey).json()
    assert row["status"] == "stopped" and not row["transitions"]
    assert row["data"]["ledger"][0]["charged_tokens"] > 0
    assert client.get("/api/v1/cognition").json()["control"]["reserved"]["calls"] == 0
    assert row["current_policy"]["version"] == 0


def test_revoked_permission_blocks_inference(client, controlled_browser, monkeypatch):
    from alive.living import Living
    from alive.living_models import LivingJourney

    original = Living.phase

    async def revoke_after_action(self, journey_id, stage, data=None):
        await original(self, journey_id, stage, data)
        if stage == "acting":
            async with self.k.db.sessions.begin() as session:
                row = await session.get(LivingJourney, journey_id)
                row.data = row.data | {"allow": False}

    monkeypatch.setattr(Living, "phase", revoke_after_action)
    journey = create(client)
    row = advance(client, journey)
    assert row["status"] == "failed"
    assert "permission revoked" in row["data"]["error"]
    assert not row["data"]["ledger"] and not row["transitions"]
    assert row["current_policy"]["version"] == 0


def test_restart_retains_policy_and_requires_explicit_next_step(settings, controlled_browser):
    async def schema():
        db = Database(settings.database_url)
        async with db.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await db.engine.dispose()

    asyncio.run(schema())
    headers = {"Authorization": "Bearer " + TOKEN}
    with TestClient(create_app(settings), headers=headers) as first:
        journey = create(first)
        saved = advance(first, journey)
        policy_hash = digest(saved["current_policy"])
    with TestClient(create_app(settings), headers=headers) as second:
        row = second.get("/api/v1/living/journeys/" + journey).json()
        assert row["status"] == "ready" and len(row["transitions"]) == 1
        assert digest(row["current_policy"]) == policy_hash
        assert not second.get("/api/v1/living").json()["active"]
        result = advance(second, journey)
        assert result["status"] == "completed"
        assert result["transitions"][1]["data"]["choice"]["action"] == "retrieve"


def test_restart_interrupts_a_running_journey_and_revokes_its_grant(settings, controlled_browser):
    from alive.cognitive_models import CognitiveControl
    from alive.living_models import LivingJourney

    async def schema():
        db = Database(settings.database_url)
        async with db.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await db.engine.dispose()

    asyncio.run(schema())
    headers = {"Authorization": "Bearer " + TOKEN}
    with TestClient(create_app(settings), headers=headers) as first:
        journey = create(first)
        identity = first.get("/api/v1/alive").json()["identity"]["id"]

    async def mark_running():
        db = Database(settings.database_url)
        async with db.sessions.begin() as session:
            row = await session.get(LivingJourney, journey)
            row.status = "running"
            row.data = row.data | {
                "allow": True,
                "stage": "reasoning",
                "ledger": [
                    {
                        "id": "reserved-interrupted",
                        "episode": 1,
                        "status": "reserved",
                        "reserved_tokens": 123,
                        "provider": "mock",
                        "model": "controlled-living-v1",
                    }
                ],
            }
            control = await session.get(CognitiveControl, identity)
            control.reserved = control.reserved | {"calls": 1, "tokens": 123}
        await db.engine.dispose()

    asyncio.run(mark_running())
    with TestClient(create_app(settings), headers=headers) as second:
        row = second.get("/api/v1/living/journeys/" + journey).json()
        assert row["status"] == "interrupted"
        assert row["data"]["allow"] is False
        assert row["data"]["ledger"][0]["status"] == "interrupted"
        assert row["data"]["ledger"][0]["charged_tokens"] == 123
        assert not row["transitions"] and row["current_policy"]["version"] == 0
        assert second.get("/api/v1/cognition").json()["control"]["reserved"]["calls"] == 0
        assert second.post(f"/api/v1/living/journeys/{journey}/advance", json={}).status_code == 409
        assert (
            second.get("/api/v1/living/journeys/" + journey).json()["data"]["ledger"]
            == row["data"]["ledger"]
        )
