"""Audit-only probes. Run explicitly; all provider traffic uses MockTransport.

Tests assert the intended contract, including deliberately red defect regressions.
No production source is changed.
"""
import asyncio
import copy
import json
from contextlib import asynccontextmanager

import httpx
import pytest

from alive.config import Settings
from alive.model_gateway import DirectMetaGateway, StructuredRequest
from alive.providers import MetaProvider, ProviderError
from tests.conftest import client, settings  # noqa: F401
from tests.test_cognition import completed, observe
from tests.test_research_memory import ROOT, PY, MDN, goal, grant, snapshot, post


def configured():
    return Settings(_env_file=None, alive_meta_api_key="audit-fake-no-value",
                    alive_api_token="audit-local-token-00000000000000000")


async def wire(data=None, response=None, **overrides):
    seen = []
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=response if response is not None else {
            "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 0}})
    req = StructuredRequest(operation="cognition.role", instructions="审计 🧪 \\\n",
        data=data or {}, schema={"type": "object"}, model="audit-model", max_output=256,
        correlation="audit-invocation-001")
    req = StructuredRequest(**(req.__dict__ | overrides))
    import inspect
    gateway_args = {"transport": httpx.MockTransport(handler)}
    if "operation" in inspect.signature(DirectMetaGateway).parameters:
        gateway_args["operation"] = "cognition.role"
    result = await DirectMetaGateway(configured(), **gateway_args).structured(req)
    return seen, result


@pytest.mark.parametrize("sentinel", [
    {"empty": "", "zero": 0, "nil": None, "false": False, "array": []},
    {"nested": {"工具": {"arguments": {"path": "a\\b\"c\n雪", "id": "call-α"}}}},
    {"long": "雪🧪" * 4000, "deep": {"a": {"b": {"c": 0}}}},
])
def test_sentinel_payload_survives(sentinel):
    seen, _ = asyncio.run(wire(sentinel))
    assert json.loads(seen[0]["messages"][1]["content"]) == sentinel
    from pathlib import Path
    name = __import__('hashlib').sha256(json.dumps(sentinel).encode()).hexdigest()[:12]
    (Path(__file__).parent / "receipts" / f"transport-{name}.json").write_text(
        json.dumps({"intended_data": sentinel, "dispatched_body": seen[0]}, ensure_ascii=False, indent=2), encoding="utf-8")


def test_zero_output_limit_is_not_silently_replaced():
    # Either rejecting zero before dispatch or preserving it is acceptable.
    try:
        seen, _ = asyncio.run(wire(max_output=0))
    except (ValueError, TypeError):
        return
    assert seen[0]["max_completion_tokens"] == 0


@pytest.mark.parametrize("response", [
    {"choices": []},
    {"choices": [{"message": {"content": None}, "finish_reason": "stop"}]},
    {"choices": [{"message": {"content": [{"type": "text", "text": "{}"}]}}]},
])
def test_malformed_response_is_typed_provider_failure(response):
    with pytest.raises(ProviderError) as error:
        asyncio.run(wire(response=response))
    assert error.value.category == "invalid_response"


def test_truncated_output_never_succeeds():
    with pytest.raises(ProviderError, match="output_truncated"):
        asyncio.run(wire(response={"choices": [{"message": {"content": "{}"},
            "finish_reason": "length"}], "usage": {"total_tokens": 7}}))


def test_unknown_request_operation_refused():
    with pytest.raises((ValueError, KeyError)):
        asyncio.run(wire(operation="audit.unauthorized"))


def test_first_file_direct_construction_is_detected(tmp_path):
    from tests.test_model_gateway import find_meta_constructions, check_allowlist
    (tmp_path / "a_rogue.py").write_text("from alive.providers import MetaProvider\n"
        "def run(s): return MetaProvider(s).structured('x', {}, {})\n")
    (tmp_path / "z_clean.py").write_text("x = 1\n")
    assert check_allowlist(find_meta_constructions(tmp_path))


def test_alias_construction_is_detected(tmp_path):
    from tests.test_model_gateway import find_meta_constructions, check_allowlist
    (tmp_path / "a_alias.py").write_text("from alive.providers import MetaProvider as Alias\n"
        "def run(s): return Alias(s).structured('x', {}, {})\n")
    (tmp_path / "z_clean.py").write_text("x = 1\n")
    assert check_allowlist(find_meta_constructions(tmp_path))


def test_invalid_first_reference_not_hidden_by_valid_last():
    from alive.society import validate_references, mock_role
    output = mock_role("observer", {"claims": [], "sources": []})
    from alive.cognitive_schema import Claim
    output.claims = [Claim(subject="x", predicate="y", value="1", evidence_refs=["rogue"]),
                     Claim(subject="x", predicate="y", value="1", evidence_refs=["valid"])]
    with pytest.raises(ValueError):
        validate_references(output, {"source_event_ids": ["valid"]})


def test_authentication_and_origin_both_required(client):
    assert client.get("/api/v1/alive", headers={"Authorization": "Bearer invalid"}).status_code == 401
    assert client.get("/api/v1/alive", headers={"Origin": "https://evil.invalid"}).status_code == 403


def test_snapshot_grant_cannot_switch_url(client):
    g = goal(client)
    permission = grant(client, g["id"], PY)
    r = client.post(ROOT + "/snapshots", json={"grant_id": permission["id"], "url": MDN,
        "title": "audit", "text": "Audit source text.",
        "reviewed_sha256": __import__('hashlib').sha256(b"Audit source text.").hexdigest()})
    assert r.status_code == 403


def test_withdraw_first_of_two_sources_isolated_and_irreversible(client):
    g = goal(client)
    sources = []
    for url, text in [(PY, "Audit alpha source describes a stable result."),
                      (MDN, "Audit beta source describes a distinct result.")]:
        permission = grant(client, g["id"], url)
        shot = snapshot(client, permission, url, text)["snapshot"]
        sources.append((shot, post(client, "/research/memories", {"snapshot_id": shot["id"]})))
    post(client, f"/research/memories/{sources[0][1]['id']}/withdraw", {})
    memories = client.get(ROOT + "/research/memories").json()["memories"]
    assert any(r["id"] == sources[1][1]["id"] and r["status"] == "active" for r in memories)
    r = client.post(ROOT + "/research/memories", json={"snapshot_id": sources[0][0]["id"]})
    assert r.status_code == 409


def test_capture_hash_mismatch_refused(client):
    g = goal(client)
    permission = grant(client, g["id"], PY)
    response = client.post(ROOT + "/snapshots", json={"grant_id": permission["id"], "url": PY,
        "title": "audit", "text": "Audit tampered source text.", "reviewed_sha256": "0" * 64})
    assert response.status_code == 403


def test_empty_persisted_token_never_allows_unauthenticated_access(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from alive.app import create_app
    from alive.models import Base
    from alive.db import Database
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".alive").mkdir()
    (tmp_path / ".alive/token").write_text("")
    config = Settings(_env_file=None, alive_meta_api_key="", alive_api_token="",
        database_url=f"sqlite+aiosqlite:///{tmp_path}/blank-token.db",
        alive_workspace=tmp_path / "workspace")
    async def schema():
        db = Database(config.database_url)
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await db.engine.dispose()
    asyncio.run(schema())
    try:
        app = create_app(config)
    except ValueError:
        return  # Refusing startup is also fail closed.
    with TestClient(app) as unauthenticated:
        read = unauthenticated.get("/api/v1/alive")
        mutation = unauthenticated.post("/api/v1/goals", json={"title": "Audit unauthorized goal fixture"})
        from pathlib import Path
        from starlette.websockets import WebSocketDisconnect
        websocket_delivered_event = False
        try:
            with unauthenticated.websocket_connect("/api/v1/events/stream") as ws:
                ws.send_json({})
                websocket_delivered_event = bool(ws.receive_json().get("event_id"))
        except WebSocketDisconnect:
            pass
        (Path(__file__).parent / "receipts/empty-token-impact.json").write_text(json.dumps({
            "unauthenticated_get_status": read.status_code,
            "unauthenticated_post_goal_status": mutation.status_code,
            "websocket_without_token_delivered_event": websocket_delivered_event,
            "data_and_token_are_temporary_fixtures": True}, indent=2), encoding="utf-8")
        assert read.status_code == 401


def test_later_capture_does_not_inherit_prior_hash(client):
    g = goal(client)
    permission = grant(client, g["id"], PY)
    first = snapshot(client, permission, PY, "Alpha source contains an initial measured result.")
    second = snapshot(client, permission, PY, "Alpha source contains a changed measured result.")
    assert second["snapshot"]["data"]["text_status"] == "changed_excerpt"
    assert first["snapshot"]["data"]["sha256"] != second["snapshot"]["data"]["sha256"]


def test_missing_second_grant_does_not_partially_import_history(client):
    response = client.post("/api/v1/history/preview", json={"entries": [
        {"url": PY, "title": "audit", "content": "First clean entry"},
        {"url": "https://user:fake@example.invalid/", "title": "audit", "content": "Second rejected entry"}]})
    # The valid first item must not make an unsafe second item acceptable.
    assert response.status_code in (403, 409, 422), response.text


def test_timeout_in_durable_reservation_exit_settles_invocation(client, monkeypatch):
    """Deterministically widen the committed-reservation -> handler window.

    The context wrapper delays transaction *exit* only after a model reservation
    has committed; it does not alter production data or model results.
    """
    async def discover(*args):
        return {"status": "available", "models": ["muse-spark-1.3"]}
    async def forbidden(*args, **kwargs):
        raise AssertionError("Provider must not be entered in this scheduling case")
    monkeypatch.setattr(MetaProvider, "discover", discover)
    monkeypatch.setattr(MetaProvider, "structured", forbidden)
    k = client.app.state.kernel
    original_begin, original_add = k.db.sessions.begin, k.add_event
    marker = {"reserved": False, "delayed": False}
    def add_event(*args, **kwargs):
        result = original_add(*args, **kwargs)
        if len(args) > 1 and args[1] == "cognition.model_reserved":
            marker["reserved"] = True
        return result
    @asynccontextmanager
    async def begin():
        async with original_begin() as session:
            yield session
        if marker["reserved"] and not marker["delayed"]:
            marker["delayed"] = True
            await asyncio.sleep(2)
    monkeypatch.setattr(k, "add_event", add_event)
    monkeypatch.setattr(k.db.sessions, "begin", begin)
    assert client.post("/api/v1/cognition/configuration", json={"wall_seconds": 1}).status_code == 200
    assert client.post("/api/v1/cognition/control", json={"command": "start", "provider": "meta"}).status_code == 200
    observe(client)
    run = completed(client)
    assert marker["delayed"] and run["state"] == "FAILED", run
    assert run["invocations"][0]["status"] == "cancelled", run["invocations"]
