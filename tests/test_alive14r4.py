"""ALIVE-14-R4 pilot-safety regressions."""

import asyncio
import json

import pytest

import scripts.alive14r4_experiment as runner
from alive.providers import ProviderError
from alive.research_relationships import ResearchRelationships
from alive.web_models import WebExperience

ROOT = "/api/v1/browser-experience"


def post(client, path, body, expected=200):
    response = client.post(ROOT + path, json=body)
    assert response.status_code == expected, response.text
    return response.json()


def goal(client):
    return post(client, "/goals", {"instruction": "Assess a controlled design"})


def grant(client, goal_id, url):
    return post(
        client,
        "/grants",
        {
            "goal_id": goal_id,
            "url": url,
            "tab_key": "alive14r4-test",
            "approved": True,
        },
    )


def snapshot(client, grant_row, url, text):
    from alive.web_experience import digest

    return post(
        client,
        "/snapshots",
        {
            "grant_id": grant_row["id"],
            "url": url,
            "title": "Controlled source",
            "text": text,
            "reviewed_sha256": digest(text),
        },
    )


def grant_row(client, grant_id):
    async def fetch():
        async with client.app.state.kernel.db.sessions() as session:
            return await session.get(WebExperience, grant_id)

    return client.portal.call(fetch)


def prepare_real_approval(runner_module, protocol, directory, token, human=True, max_usd=0.45):
    settings = runner_module.build_settings("real", protocol, directory, token)
    with runner_module.Client(settings, token) as client:
        return runner_module.call(
            client,
            "POST",
            "/research/experiment/campaigns/"
            + runner_module.read_json(directory / "state.json")["campaign_digest"]
            + "/approve",
            {
                "stage": 1,
                "call_cap": 18,
                "max_input_tokens": runner_module.read_json(directory / "state.json")[
                    "campaign_stages"
                ]["full"]["reserved_tokens"],
                "max_output_tokens": 1536,
                "max_usd": max_usd,
                "no_retries": True,
                "human_attestation": human,
            },
        )


def prepare_synthetic_stage(runner_module, directory, token, stage, call_cap, tokens):
    settings = runner_module.build_settings(
        "synthetic", runner_module.verify_protocol_identity(), directory, token
    )
    digest = runner_module.read_json(directory / "state.json")["campaign_digest"]
    with runner_module.Client(settings, token) as client:
        return runner_module.call(
            client,
            "POST",
            f"/research/experiment/campaigns/{digest}/approve",
            {
                "stage": stage,
                "call_cap": call_cap,
                "max_input_tokens": tokens,
                "max_output_tokens": 1536,
                "max_usd": 0.0,
                "no_retries": True,
                "human_attestation": False,
            },
        )


def test_explicit_revocation_of_restart_suspended_grant_is_permanent(client):
    g = goal(client)
    g_row = grant(client, g["id"], "https://docs.python.org/3/tutorial/")
    shot = snapshot(client, g_row, "https://docs.python.org/3/tutorial/", "Controlled page text.")
    assert shot["snapshot"]["id"]
    # Restart suspends the active grant.
    client.portal.call(client.app.state.web.initialize)
    row = grant_row(client, g_row["id"])
    assert row.status == "revoked_restart"
    # Explicit owner revocation while suspended must become permanent.
    post(client, f"/grants/{g_row['id']}/revoke", {})
    row = grant_row(client, g_row["id"])
    assert row.status == "revoked"
    assert row.data["owner_revoked"] is True
    assert row.data["revocation_reason"] == "owner_explicit"
    with pytest.raises(PermissionError):
        client.portal.call(
            client.app.state.web.reactivate_grant,
            g_row["id"],
            "test-run",
            "test-approval",
        )
    # No outbound preview is possible after revocation.
    post(
        client,
        "/research/outbound/preview",
        {
            "snapshot_id": shot["snapshot"]["id"],
            "analysis_mode": "paired",
            "research_question": "What does the page support?",
        },
        403,
    )
    assert client.portal.call(client.app.state.relationships.list)["analyses"] == []


def test_restart_recovery_is_bounded_and_preserves_expiry(client):
    g = goal(client)
    g_row = grant(client, g["id"], "https://docs.python.org/3/tutorial/")
    shot = snapshot(client, g_row, "https://docs.python.org/3/tutorial/", "Controlled page text.")
    original_expiry = grant_row(client, g_row["id"]).data["expires_at"]
    client.portal.call(client.app.state.web.initialize)
    assert grant_row(client, g_row["id"]).status == "revoked_restart"
    restored = client.portal.call(
        client.app.state.web.reactivate_grant,
        g_row["id"],
        "test-run",
        "test-approval",
    )
    assert restored["status"] == "active"
    assert restored["data"]["expires_at"] == original_expiry
    assert restored["data"]["restored_from"] == "revoked_restart"
    # A second restart and explicit revoke cannot be undone.
    client.portal.call(client.app.state.web.initialize)
    post(client, f"/grants/{g_row['id']}/revoke", {})
    client.portal.call(client.app.state.web.initialize)
    assert grant_row(client, g_row["id"]).status == "revoked"
    with pytest.raises(PermissionError):
        client.portal.call(
            client.app.state.web.reactivate_grant,
            g_row["id"],
            "test-run",
            "test-approval",
        )
    # The snapshot remains intact but the revoked grant blocks preview.
    post(
        client,
        "/research/outbound/preview",
        {
            "snapshot_id": shot["snapshot"]["id"],
            "analysis_mode": "paired",
            "research_question": "What does the page support?",
        },
        403,
    )


def test_revocation_concurrent_with_recovery_never_leaves_grant_active(client):
    g = goal(client)
    g_row = grant(client, g["id"], "https://docs.python.org/3/tutorial/")
    snapshot(client, g_row, "https://docs.python.org/3/tutorial/", "Controlled page text.")
    client.portal.call(client.app.state.web.initialize)

    async def race():
        return await asyncio.gather(
            client.app.state.web.revoke(g_row["id"]),
            client.app.state.web.reactivate_grant(g_row["id"], "test-run", "test-approval"),
            return_exceptions=True,
        )

    outcomes = client.portal.call(race)
    row = grant_row(client, g_row["id"])
    assert row.status == "revoked"
    assert row.data["owner_revoked"] is True
    assert any(isinstance(outcome, PermissionError) for outcome in outcomes) or (
        outcomes[1]["status"] == "active" and row.status == "revoked"
    )
    with pytest.raises(PermissionError):
        client.portal.call(
            client.app.state.web.reactivate_grant,
            g_row["id"],
            "test-run",
            "test-approval-2",
        )


def test_expired_restart_suspended_grant_cannot_be_restored(client):
    g = goal(client)
    g_row = grant(client, g["id"], "https://docs.python.org/3/tutorial/")
    snapshot(client, g_row, "https://docs.python.org/3/tutorial/", "Controlled page text.")
    client.portal.call(client.app.state.web.initialize)

    async def expire():
        async with client.app.state.kernel.db.sessions.begin() as session:
            saved = await session.get(WebExperience, g_row["id"])
            saved.data = saved.data | {"expires_at": "2000-01-01T00:00:00+00:00"}

    client.portal.call(expire)
    with pytest.raises(PermissionError):
        client.portal.call(
            client.app.state.web.reactivate_grant,
            g_row["id"],
            "test-run",
            "test-approval",
        )


def test_staged_two_call_execution_and_approved_continuation(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(runner, "ARCHIVE", tmp_path / "archive")
    protocol = runner.verify_protocol_identity()
    state = runner.prepare("synthetic")
    directory = runner.run_dir("synthetic", protocol)
    token = (directory / "api-token.txt").read_text(encoding="utf-8").strip()
    stage_one = state["campaign_stages"]["stage_1"]
    prepare_synthetic_stage(runner, directory, token, 1, 2, stage_one["reserved_tokens"])
    runner.approve("synthetic", synthetic=True)
    first = runner.execute("synthetic", limit=2)
    assert first["phase"] == "staged"
    assert first["execution"]["attempted_dispatches"] == 2
    assert len(runner.read_jsonl(directory / "outputs.jsonl")) == 2
    full = state["campaign_stages"]["full"]
    prepare_synthetic_stage(runner, directory, token, 2, 18, full["reserved_tokens"])
    runner.approve("synthetic", synthetic=True)
    second = runner.execute("synthetic", limit=16)
    assert second["phase"] == "awaiting_ratings"
    assert second["execution"]["attempted_dispatches"] == 18
    assert len(runner.read_jsonl(directory / "outputs.jsonl")) == 18


@pytest.mark.parametrize(
    "category,status",
    [
        ("authentication", 401),
        ("unsupported_schema", 400),
        ("quota_exhausted", 402),
    ],
)
@pytest.mark.skip(
    reason=(
        "R4 real path is superseded by the strict R5 content/stage contract; "
        "see test_alive14r5_safety.py"
    )
)
def test_campaign_fatal_provider_failure_stops_after_one(tmp_path, monkeypatch, category, status):
    monkeypatch.setattr(runner, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(runner, "ARCHIVE", tmp_path / "archive")
    monkeypatch.setenv("ALIVE_META_API_KEY", "r4-no-network")
    protocol = runner.verify_protocol_identity()
    runner.prepare("real")
    directory = runner.run_dir("real", protocol)
    token = (directory / "api-token.txt").read_text(encoding="utf-8").strip()
    prepare_real_approval(runner, protocol, directory, token)
    runner.approve("real")
    calls = []

    async def fail(self, *args, **kwargs):
        calls.append(kwargs.get("correlation"))
        raise ProviderError(category, status)

    from alive.research_relationships import MetaProvider

    original_method = MetaProvider.structured
    MetaProvider.structured = fail
    try:
        result = runner.execute("real")
    finally:
        MetaProvider.structured = original_method
    assert len(calls) == 1
    assert result["phase"] == "blocked"
    assert result["blocked"]["error_category"] == category
    assert result["blocked"]["dispatched_calls"] == 1
    outputs = runner.read_jsonl(directory / "outputs.jsonl")
    assert len(outputs) == 1
    assert outputs[0]["campaign_fatal"] is True


def test_campaign_digest_is_stable_and_content_sensitive():
    protocol = runner.verify_protocol_identity()
    model = protocol["model_plan"]["model"]
    first = runner.campaign_digest(protocol, "meta", model)
    second = runner.campaign_digest(protocol, "meta", model)
    assert first == second
    changed = json.loads(json.dumps(protocol))
    changed["tasks"][0]["current_source"]["excerpt"] += " Changed."
    assert runner.campaign_digest(changed, "meta", model) != first


@pytest.mark.skip(reason="R4 real approval path is superseded by R5; see test_alive14r5.py")
def test_real_approval_requires_attestation_and_effective_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(runner, "ARCHIVE", tmp_path / "archive")
    protocol = runner.verify_protocol_identity()
    runner.prepare("real")
    directory = runner.run_dir("real", protocol)
    token = (directory / "api-token.txt").read_text(encoding="utf-8").strip()
    with pytest.raises(RuntimeError):
        prepare_real_approval(runner, protocol, directory, token, human=False)
    prepare_real_approval(runner, protocol, directory, token, max_usd=0.01)
    with pytest.raises(SystemExit):
        runner.approve("real")
    prepare_real_approval(runner, protocol, directory, token, max_usd=0.45)
    monkeypatch.setenv("ALIVE_R4_RUNTIME_USD_CAP", "0.01")
    with pytest.raises(SystemExit):
        runner.approve("real")


@pytest.mark.skip(reason="R4 real approval path is superseded by R5; see test_alive14r5.py")
def test_file_only_and_revoked_server_approvals_are_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(runner, "ARCHIVE", tmp_path / "archive")
    protocol = runner.verify_protocol_identity()
    runner.prepare("real")
    directory = runner.run_dir("real", protocol)
    token = (directory / "api-token.txt").read_text(encoding="utf-8").strip()
    forged = {
        "approval_id": "forged",
        "provenance": "authenticated_owner_interface",
        "human_approval": True,
        "human_attestation": True,
    }
    path = tmp_path / "forged-approval.json"
    path.write_text(json.dumps(forged), encoding="utf-8")
    with pytest.raises(SystemExit):
        runner.approve("real", approval_file=str(path))
    approved = prepare_real_approval(runner, protocol, directory, token)
    runner.approve("real")
    settings = runner.build_settings("real", protocol, directory, token)
    with runner.Client(settings, token) as client:
        runner.call(
            client,
            "POST",
            "/research/experiment/approvals/" + approved["data"]["approval_id"] + "/revoke",
            {},
        )
    monkeypatch.setenv("ALIVE_META_API_KEY", "r4-no-network")
    with pytest.raises(SystemExit):
        runner.execute("real")


def test_dispatch_marker_preserves_ambiguity_and_no_dispatch_liability(client):
    from alive.models import uid

    async def seed():
        async with client.app.state.kernel.db.sessions.begin() as session:
            ambiguous = WebExperience(
                id=uid(),
                instance_id=client.app.state.kernel.instance_id,
                kind="research_relationship_analysis",
                status="reserved",
                data={
                    "consent_id": "ambiguous",
                    "analysis_mode": "paired",
                    "reserved_tokens": 1000,
                    "dispatch_status": "dispatch_possibly_started",
                },
            )
            never = WebExperience(
                id=uid(),
                instance_id=client.app.state.kernel.instance_id,
                kind="research_relationship_analysis",
                status="reserved",
                data={
                    "consent_id": "never",
                    "analysis_mode": "paired",
                    "reserved_tokens": 800,
                    "dispatch_status": "reserved_never_dispatched",
                },
            )
            session.add(ambiguous)
            session.add(never)
            await session.flush()
            return ambiguous.id, never.id

    ambiguous_id, never_id = client.portal.call(seed)
    client.portal.call(client.app.state.relationships.initialize)

    async def fetch():
        async with client.app.state.kernel.db.sessions() as session:
            return (
                await session.get(WebExperience, ambiguous_id),
                await session.get(WebExperience, never_id),
            )

    ambiguous, never = client.portal.call(fetch)
    assert ambiguous.status == "interrupted"
    assert ambiguous.data["charged_tokens"] == 1000
    assert ambiguous.data["cost_liability_tokens"] == 1000
    assert ambiguous.data["settled_from_dispatch_status"] == "dispatch_possibly_started"
    assert never.status == "interrupted"
    assert never.data["charged_tokens"] == 0
    assert never.data["cost_liability_tokens"] == 0
    assert never.data["error"] == "cancelled_before_dispatch"


@pytest.mark.skip(reason="R4 synthetic staged path is superseded by R5; see test_alive14r5.py")
def test_missing_output_and_revised_rating_archive(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(runner, "ARCHIVE", tmp_path / "archive")
    protocol = runner.verify_protocol_identity()
    runner.prepare("synthetic")
    runner.approve("synthetic", synthetic=True)
    original = ResearchRelationships._local_stub_paired

    def flaky(self, payload):
        if "Marrow-6" in payload.get("current_excerpt", ""):
            return self._local_stub_paired_invalid(payload)
        return original(self, payload)

    monkeypatch.setattr(ResearchRelationships, "_local_stub_paired", flaky)
    state = runner.execute("synthetic")
    assert state["phase"] == "awaiting_ratings"
    directory = runner.run_dir("synthetic", protocol)
    outputs = runner.read_jsonl(directory / "outputs.jsonl")
    assert any(row["missing"] for row in outputs)
    token = (directory / "api-token.txt").read_text(encoding="utf-8").strip()
    settings = runner.build_settings("synthetic", protocol, directory, token)
    with runner.Client(settings, token) as client:
        events = client.get("/api/v1/events", params={"limit": 500}).json()
        for event in events:
            if event["event_type"] == "research.paired_analysis_settled":
                assert set(event["payload"]) == {"analysis_mode", "settled"}
            if (
                event["event_type"] == "research.outbound_authorized"
                and event["payload"].get("analysis_mode") == "paired"
            ):
                assert set(event["payload"]) == {"analysis_mode", "authorized"}
        view = runner.call(client, "GET", f"/research/blind/runs/{state['blind']['run_id']}")
        serialized = json.dumps(view)
        assert '"condition":' not in serialized
        assert "attempt_id" not in serialized
        assert "local_stub" not in serialized
    runner.rate("synthetic", synthetic=True)
    token = (directory / "api-token.txt").read_text(encoding="utf-8").strip()
    settings = runner.build_settings("synthetic", protocol, directory, token)
    with runner.Client(settings, token) as client:
        view = runner.call(client, "GET", f"/research/blind/runs/{state['blind']['run_id']}")
        output = view["outputs"][0]
        runner.call(
            client,
            "POST",
            f"/research/blind/runs/{state['blind']['run_id']}/ratings",
            {
                "output_id": output["output_id"],
                "output_sha256": output["output_sha256"],
                "capability": view["rating_capability"],
                "rubric": {
                    "factually_supported": "yes",
                    "relevant_to_goal": "yes",
                    "revealed_new": "yes",
                    "already_obvious": "no",
                    "would_act": "yes",
                    "misleading": "no",
                    "uncertain": "no",
                },
                "synthetic": True,
            },
        )
    runner.reveal("synthetic")
    runner.analyse("synthetic")
    runner.archive("synthetic")
    analysis = json.loads((directory / "analysis.json").read_text(encoding="utf-8"))
    assert analysis["secondary"]["missing_outputs"] >= 1
    assert set(analysis["secondary"]["missing_outputs_by_condition"]) == {
        "A",
        "B",
        "C",
    }
    assert set(analysis["secondary"]["misleading_by_condition"]) == {"A", "B", "C"}
    missing_tasks = [
        row
        for row in analysis["tasks"]
        if any(row["conditions"][condition]["missing"] for condition in ("A", "B"))
    ]
    assert missing_tasks
    for row in missing_tasks:
        for condition in ("A", "B"):
            if row["conditions"][condition]["missing"]:
                assert row["conditions"][condition]["supported_useful"] is False
    results = json.loads((directory / "results.json").read_text(encoding="utf-8"))
    assert len(results["ratings"]) > state["blind"]["output_count"]
    assert (runner.ARCHIVE / state["run_id"] / "manifest.json").exists()
