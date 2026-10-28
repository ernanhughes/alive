"""ALIVE-14-R5 REVIEW-11 safety regressions.

These tests assert the corrected outcomes. The pre-fix unsafe outcomes are
preserved in archives/ALIVE-14-R5/evidence/review11-prefix.txt.
"""

import asyncio
import json

import pytest

import scripts.alive14r5_experiment as runner
from alive.cognitive_models import CognitiveControl
from alive.providers import ProviderError
from alive.research_relationships import MetaProvider, ResearchRelationships


def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(runner, "ARCHIVE", tmp_path / "archive")
    monkeypatch.delenv("ALIVE_META_API_KEY", raising=False)
    protocol = runner.verify_protocol_identity()
    state = runner.prepare("synthetic")
    directory = runner.run_dir("synthetic", protocol)
    token = (directory / "api-token.txt").read_text(encoding="utf-8").strip()
    return protocol, state, directory, token


def server_approve(runner_module, directory, token, state, stage=1):
    settings = runner_module.build_settings(
        "synthetic", runner_module.verify_protocol_identity(), directory, token
    )
    stage_name = "stage_1" if stage == 1 else "full"
    with runner_module.Client(settings, token) as client:
        return runner_module.call(
            client,
            "POST",
            "/research/experiment/campaigns/" + state["campaign_digest"] + "/approve",
            {
                "stage": stage,
                "call_cap": 2 if stage == 1 else 18,
                "max_input_tokens": state["campaign_stages"][stage_name]["reserved_tokens"],
                "max_output_tokens": 1536,
                "max_usd": 0.0,
                "no_retries": True,
                "human_attestation": False,
            },
        )


def test_revocation_after_call_one_prevents_call_two(tmp_path, monkeypatch):
    protocol, state, directory, token = setup(tmp_path, monkeypatch)
    approval = server_approve(runner, directory, token, state, 1)
    runner.approve("synthetic", synthetic=True, stage=1)
    calls = []
    original = ResearchRelationships._local_stub_paired
    original_call = runner.call

    def count(self, payload):
        calls.append(payload)
        return original(self, payload)

    monkeypatch.setattr(ResearchRelationships, "_local_stub_paired", count)

    def revoke_after_first(c, method, path, body=None, expected=200):
        result = original_call(c, method, path, body, expected)
        if method == "POST" and path == "/research/relationships" and len(calls) == 1:
            original_call(
                c,
                "POST",
                f"/research/experiment/approvals/{approval['data']['approval_id']}/revoke",
                {},
            )
        return result

    monkeypatch.setattr(runner, "call", revoke_after_first)
    result = runner.execute("synthetic", limit=2)
    assert len(calls) == 1
    assert result["phase"] == "blocked"
    assert result["blocked"]["stage"] == "approval_revoked"
    assert result["execution"]["attempted_dispatches"] == 1
    rows = runner.read_jsonl(directory / "outputs.jsonl")
    assert len(rows) == 1
    assert rows[0]["call_index"] == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("question", "Changed question outside the approved campaign"),
        ("current_excerpt", "Changed current excerpt."),
        ("historical_excerpt", "Changed historical excerpt."),
        ("current_url", "https://example.test/changed"),
        ("current_sha256", "0" * 64),
        ("historical_sha256", "1" * 64),
        ("goal", "Changed goal"),
    ],
)
def test_local_state_content_mutation_is_refused(tmp_path, monkeypatch, field, value):
    protocol, state, directory, token = setup(tmp_path, monkeypatch)
    server_approve(runner, directory, token, state, 1)
    runner.approve("synthetic", synthetic=True, stage=1)
    current = runner.read_json(directory / "state.json")
    current["tasks"][0][field] = value
    runner.write_json(directory / "state.json", current)
    calls = []
    original = ResearchRelationships._local_stub_paired

    def count(self, payload):
        calls.append(payload)
        return original(self, payload)

    monkeypatch.setattr(ResearchRelationships, "_local_stub_paired", count)
    try:
        result = runner.execute("synthetic", limit=2)
    except SystemExit:
        result = None
    assert result is None or result["phase"] == "blocked"
    assert calls == []
    assert len(runner.read_jsonl(directory / "outputs.jsonl")) == 0


def test_server_rejects_changed_question_even_with_valid_approval(tmp_path, monkeypatch):
    protocol, state, directory, token = setup(tmp_path, monkeypatch)
    server_approve(runner, directory, token, state, 1)
    runner.approve("synthetic", synthetic=True, stage=1)
    approval = runner.read_json(directory / "approval.json")
    settings = runner.build_settings("synthetic", protocol, directory, token)
    with runner.Client(settings, token) as client:
        runner.reactivate_approved_grants(client, directory, state)
        task = next(row for row in state["tasks"] if row["task_id"] == state["task_order"][0])
        response = client.post(
            runner.API + "/research/outbound/preview",
            json={
                "snapshot_id": task["snapshot_id"],
                "analysis_mode": "paired",
                "research_question": "Changed question at the server boundary",
                "provider": "local_stub",
                "experiment": {
                    "campaign_digest": state["campaign_digest"],
                    "approval_id": approval["approval_id"],
                    "run_id": state["run_id"],
                    "stage": 1,
                    "task_id": task["task_id"],
                    "condition": "A",
                    "call_index": 0,
                },
            },
        )
    assert response.status_code in (403, 409), response.text
    assert "research question" in response.text.lower()
    assert len(runner.read_jsonl(directory / "outputs.jsonl")) == 0


def test_server_rejects_digest_mismatch_and_conflicting_registration(tmp_path, monkeypatch):
    protocol, state, directory, token = setup(tmp_path, monkeypatch)
    settings = runner.build_settings("synthetic", protocol, directory, token)
    campaign = runner.read_json(directory / "campaign.json")
    mutated = json.loads(json.dumps(campaign))
    mutated["content"]["tasks"][0]["question"] = "Mutated after approval"
    with runner.Client(settings, token) as client:
        response = client.post(
            runner.API + "/research/experiment/campaigns",
            json=mutated,
        )
    assert response.status_code == 409, response.text
    assert "canonical content" in response.text.lower()


def test_stage_two_requires_two_terminal_stage_one_attempts(tmp_path, monkeypatch):
    protocol, state, directory, token = setup(tmp_path, monkeypatch)
    server_approve(runner, directory, token, state, 1)
    runner.approve("synthetic", synthetic=True, stage=1)
    runner.execute("synthetic", limit=1)
    settings = runner.build_settings("synthetic", protocol, directory, token)
    with runner.Client(settings, token) as client:
        response = client.post(
            runner.API + f"/research/experiment/campaigns/{state['campaign_digest']}/approve",
            json={
                "stage": 2,
                "call_cap": 18,
                "max_input_tokens": state["campaign_stages"]["full"]["reserved_tokens"],
                "max_output_tokens": 1536,
                "max_usd": 0.0,
                "no_retries": True,
                "human_attestation": False,
            },
        )
    assert response.status_code == 409, response.text
    assert "not eligible" in response.text.lower()


def test_revoked_stage_two_approval_prevents_dispatch(tmp_path, monkeypatch):
    protocol, state, directory, token = setup(tmp_path, monkeypatch)
    server_approve(runner, directory, token, state, 1)
    runner.approve("synthetic", synthetic=True, stage=1)
    runner.execute("synthetic", limit=2)
    stage_two = server_approve(runner, directory, token, state, 2)
    runner.approve("synthetic", synthetic=True, stage=2)
    settings = runner.build_settings("synthetic", protocol, directory, token)
    with runner.Client(settings, token) as client:
        runner.call(
            client,
            "POST",
            f"/research/experiment/approvals/{stage_two['data']['approval_id']}/revoke",
            {},
        )
    with pytest.raises(SystemExit):
        runner.execute("synthetic", limit=16)
    assert len(runner.read_jsonl(directory / "outputs.jsonl")) == 2


def test_stage_one_over_cap_and_stage_two_before_eligibility_are_rejected(tmp_path, monkeypatch):
    protocol, state, directory, token = setup(tmp_path, monkeypatch)
    settings = runner.build_settings("synthetic", protocol, directory, token)
    digest = state["campaign_digest"]
    with runner.Client(settings, token) as client:
        for stage, cap, tokens in (
            (1, 18, state["campaign_stages"]["full"]["reserved_tokens"]),
            (1, 3, state["campaign_stages"]["stage_1"]["reserved_tokens"]),
            (2, 18, state["campaign_stages"]["full"]["reserved_tokens"]),
        ):
            response = client.post(
                runner.API + f"/research/experiment/campaigns/{digest}/approve",
                json={
                    "stage": stage,
                    "call_cap": cap,
                    "max_input_tokens": tokens,
                    "max_output_tokens": 1536,
                    "max_usd": 0.0,
                    "no_retries": True,
                    "human_attestation": False,
                },
            )
            assert response.status_code == 409, response.text
    server_approve(runner, directory, token, state, 1)
    runner.approve("synthetic", synthetic=True, stage=1)
    runner.execute("synthetic", limit=2)
    server_approve(runner, directory, token, state, 2)
    runner.approve("synthetic", synthetic=True, stage=2)
    end = runner.execute("synthetic", limit=16)
    assert end["phase"] == "awaiting_ratings"
    assert end["execution"]["attempted_dispatches"] == 18
    assert len(runner.read_jsonl(directory / "outputs.jsonl")) == 18


def test_raw_timeout_is_campaign_fatal(tmp_path, monkeypatch):
    protocol, state, directory, token = setup(tmp_path, monkeypatch)
    server_approve(runner, directory, token, state, 1)
    runner.approve("synthetic", synthetic=True, stage=1)
    calls = []

    def fail(self, payload):
        calls.append(payload)
        raise TimeoutError("governor wall timeout")

    monkeypatch.setattr(ResearchRelationships, "_local_stub_paired", fail)
    result = runner.execute("synthetic", limit=2)
    assert len(calls) == 1
    assert result["phase"] == "blocked"
    rows = runner.read_jsonl(directory / "outputs.jsonl")
    assert len(rows) == 1
    assert rows[0]["error_category"] == "wall_clock_timeout"
    assert rows[0]["campaign_fatal"] is True
    assert rows[0]["cost_liability_tokens"] > 0


@pytest.mark.parametrize(
    "category,status",
    [
        ("authentication", 401),
        ("access_denied", 403),
        ("unsupported_schema", 400),
        ("quota_exhausted", 402),
        ("rate_limit", 429),
        ("server_error", 500),
    ],
)
def test_fatal_provider_categories_stop_after_one(tmp_path, monkeypatch, category, status):
    protocol, state, directory, token = setup(tmp_path, monkeypatch)
    server_approve(runner, directory, token, state, 1)
    runner.approve("synthetic", synthetic=True, stage=1)
    calls = []

    def fail(self, payload):
        calls.append(payload)
        raise ProviderError(category, status)

    monkeypatch.setattr(ResearchRelationships, "_local_stub_paired", fail)
    result = runner.execute("synthetic", limit=2)
    assert len(calls) == 1
    assert result["phase"] == "blocked"
    rows = runner.read_jsonl(directory / "outputs.jsonl")
    assert len(rows) == 1
    assert rows[0]["campaign_fatal"] is True
    assert rows[0]["error_category"] == category
    assert rows[0]["cost_liability_tokens"] > 0
    with pytest.raises(SystemExit):
        runner.execute("synthetic", limit=2)
    assert len(calls) == 1


def test_actual_asyncio_timeout_is_campaign_fatal(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(runner, "ARCHIVE", tmp_path / "archive")
    monkeypatch.setenv("ALIVE_META_API_KEY", "r5-stub-only")
    protocol = runner.verify_protocol_identity()
    state = runner.prepare("real")
    directory = runner.run_dir("real", protocol)
    token = (directory / "api-token.txt").read_text(encoding="utf-8").strip()
    settings = runner.build_settings("real", protocol, directory, token)
    with runner.Client(settings, token) as client:
        runner.call(
            client,
            "POST",
            "/research/experiment/campaigns/" + state["campaign_digest"] + "/approve",
            {
                "stage": 1,
                "call_cap": 2,
                "max_input_tokens": state["campaign_stages"]["stage_1"]["reserved_tokens"],
                "max_output_tokens": 1536,
                "max_usd": 0.45,
                "no_retries": True,
                "human_attestation": True,
            },
        )

        async def shorten_wall_clock():
            async with client.app.state.kernel.db.sessions.begin() as session:
                control = await session.get(CognitiveControl, client.app.state.kernel.instance_id)
                configuration = dict(control.configuration)
                configuration["wall_seconds"] = 1
                control.configuration = configuration

        client.portal.call(shorten_wall_clock)
    runner.approve("real")
    calls = []

    async def slow(self, *args, **kwargs):
        calls.append(kwargs.get("correlation"))
        await asyncio.sleep(2)

    original = MetaProvider.structured
    MetaProvider.structured = slow
    try:
        result = runner.execute("real")
    finally:
        MetaProvider.structured = original
    assert len(calls) == 1
    assert result["phase"] == "blocked"
    rows = runner.read_jsonl(directory / "outputs.jsonl")
    assert len(rows) == 1
    assert rows[0]["error_category"] == "wall_clock_timeout"
    assert rows[0]["campaign_fatal"] is True
    assert rows[0]["cost_liability_tokens"] > 0
