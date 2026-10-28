"""ALIVE-14-R5-R1 regressions for REVIEW-12 blockers B1-B4.

These tests exercise the authenticated backend and the ordinary runner boundary.
The unsafe REVIEW-12 reproductions are preserved in
``archives/ALIVE-14-R5-R1/evidence/review12-prefix.txt``.
"""

import asyncio
import copy
import hashlib
import json

import pytest

import scripts.alive14r5_experiment as runner
from alive.providers import MetaProvider, ProviderError
from alive.research_relationships import ResearchRelationships
from alive.web_models import WebExperience


@pytest.fixture(autouse=True)
def no_meta_transport(monkeypatch):
    monkeypatch.delenv("ALIVE_META_API_KEY", raising=False)

    async def forbidden(*args, **kwargs):
        raise AssertionError("R5-R1 tests must not perform Meta transport")

    monkeypatch.setattr(MetaProvider, "_request", forbidden)


def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(runner, "ARCHIVE", tmp_path / "archive")
    protocol = runner.verify_protocol_identity()
    state = runner.prepare("synthetic")
    directory = runner.run_dir("synthetic", protocol)
    token = (directory / "api-token.txt").read_text(encoding="utf-8").strip()
    runner.approve("synthetic", synthetic=True, stage=1)
    state = runner.read_json(directory / "state.json")
    approval = runner.read_json(directory / "approval.json")
    return protocol, state, directory, token, approval


def approve_stage(runner_module, directory, token, state, stage):
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


def campaign_task(state, index):
    task_id = state["task_order"][index // 2]
    return next(row for row in state["tasks"] if row["task_id"] == task_id)


def consent(client, state, approval, index, stage=None):
    task = campaign_task(state, index)
    condition = "A" if index % 2 == 0 else "B"
    experiment = {
        "campaign_digest": state["campaign_digest"],
        "approval_id": approval["approval_id"],
        "run_id": state["run_id"],
        "stage": int(stage if stage is not None else approval["stage"]),
        "task_id": task["task_id"],
        "condition": condition,
        "call_index": index,
    }
    fresh = runner.preview(
        client,
        task,
        state["provider"],
        task["memory_id"] if condition == "B" else None,
        experiment,
    )
    runner.call(
        client,
        "POST",
        "/research/outbound/authorize",
        {
            "consent_id": fresh["id"],
            "payload_sha256": fresh["payload_sha256"],
            "approved": True,
        },
    )
    return fresh


def dispatch(client, state, approval, index, stage=None):
    fresh = consent(client, state, approval, index, stage)
    return runner.call(
        client,
        "POST",
        "/research/relationships",
        {"consent_id": fresh["id"]},
    )


def capture_stub(monkeypatch):
    calls = []
    original = ResearchRelationships._local_stub_paired

    def capture(self, payload):
        calls.append(copy.deepcopy(payload))
        return original(self, payload)

    monkeypatch.setattr(ResearchRelationships, "_local_stub_paired", capture)
    return calls


def test_backend_fatal_is_durable_and_blocks_later_dispatch(tmp_path, monkeypatch):
    protocol, state, directory, token, approval = setup(tmp_path, monkeypatch)
    calls = []

    def fail(self, payload):
        calls.append(payload)
        raise ProviderError("authentication", 401)

    monkeypatch.setattr(ResearchRelationships, "_local_stub_paired", fail)
    settings = runner.build_settings("synthetic", protocol, directory, token)
    with runner.Client(settings, token) as client:
        runner.reactivate_approved_grants(client, directory, state)
        first = dispatch(client, state, approval, 0)
        assert first["analysis"]["data"]["campaign_fatal"] is True
        assert first["analysis"]["data"]["cost_liability_tokens"] > 0
        campaign = runner.fetch_campaign(client, state["campaign_digest"])["data"]
        assert campaign["blocked"]["attempt_id"] == first["analysis"]["id"]
        with pytest.raises(RuntimeError, match="blocked"):
            consent(client, state, approval, 1)
        blocked_approval = client.post(
            runner.API + f"/research/experiment/campaigns/{state['campaign_digest']}/approve",
            json={
                "stage": 1,
                "call_cap": 2,
                "max_input_tokens": state["campaign_stages"]["stage_1"]["reserved_tokens"],
                "max_output_tokens": 1536,
                "max_usd": 0.0,
                "no_retries": True,
                "human_attestation": False,
            },
        )
        assert blocked_approval.status_code == 409
        still_blocked = runner.fetch_campaign(client, state["campaign_digest"])["data"]
        assert still_blocked["blocked"]["reason"]
    result = runner.execute("synthetic", limit=2)
    assert result["phase"] == "blocked"
    assert result["blocked"]["stage"] == "campaign_blocked"
    assert len(calls) == 1
    with runner.Client(settings, token) as client:
        runner.call(
            client,
            "POST",
            f"/research/experiment/approvals/{approval['approval_id']}/revoke",
            {},
        )
        after_revocation = runner.fetch_campaign(client, state["campaign_digest"])["data"]
        assert after_revocation["blocked"]["reason"]


def test_runner_crash_recovery_after_fatal_does_not_dispatch(tmp_path, monkeypatch):
    protocol, state, directory, token, approval = setup(tmp_path, monkeypatch)
    calls = []
    original = ResearchRelationships._local_stub_paired

    def fail_once(self, payload):
        calls.append(payload)
        if len(calls) == 1:
            raise ProviderError("authentication", 401)
        return original(self, payload)

    monkeypatch.setattr(ResearchRelationships, "_local_stub_paired", fail_once)
    normal_call = runner.call
    crashed = []

    def crash_after_dispatch(c, method, path, body=None, expected=200):
        result = normal_call(c, method, path, body, expected)
        if method == "POST" and path == "/research/relationships" and not crashed:
            crashed.append(True)
            raise SystemExit("simulated process exit after durable fatal settlement")
        return result

    monkeypatch.setattr(runner, "call", crash_after_dispatch)
    with pytest.raises(SystemExit, match="simulated process exit"):
        runner.execute("synthetic", limit=2)
    assert len(calls) == 1
    monkeypatch.setattr(runner, "call", normal_call)
    result = runner.execute("synthetic", limit=2)
    assert result["phase"] == "blocked"
    assert result["blocked"]["stage"] == "campaign_blocked"
    assert len(calls) == 1
    rows = runner.read_jsonl(directory / "outputs.jsonl")
    assert rows == []
    settings = runner.build_settings("synthetic", protocol, directory, token)
    with runner.Client(settings, token) as client:
        inventory = runner.call(client, "GET", "/research/relationships")
        attempts = [
            row
            for row in inventory["analyses"]
            if row["data"].get("campaign_digest") == state["campaign_digest"]
        ]
        assert len(attempts) == 1
        assert attempts[0]["data"]["campaign_fatal"] is True
        assert attempts[0]["data"]["cost_liability_tokens"] > 0


def test_cancellation_settlement_commits_and_blocks_stage_two(tmp_path, monkeypatch):
    protocol, state, directory, token, approval = setup(tmp_path, monkeypatch)
    calls = []
    original = ResearchRelationships._local_stub_paired

    def cancel_second(self, payload):
        calls.append(payload)
        if len(calls) == 2:
            raise asyncio.CancelledError()
        return original(self, payload)

    monkeypatch.setattr(ResearchRelationships, "_local_stub_paired", cancel_second)
    settings = runner.build_settings("synthetic", protocol, directory, token)
    with runner.Client(settings, token) as client:
        runner.reactivate_approved_grants(client, directory, state)
        first = dispatch(client, state, approval, 0)
        assert first["analysis"]["status"] == "validated"
        fresh = consent(client, state, approval, 1)

        async def cancel_and_inspect():
            try:
                await client.app.state.relationships.analyze(fresh["id"])
            except asyncio.CancelledError:
                pass
            async with client.app.state.kernel.db.sessions() as session:
                rows = await client.app.state.approvals.attempts_locked(
                    session, state["campaign_digest"]
                )
                second = next(row for row in rows if row.data.get("call_index") == 1)
                campaign = await client.app.state.approvals.campaign_locked(
                    session, state["campaign_digest"]
                )
                return second.status, dict(second.data), dict(campaign.data)

        status, data, campaign = client.portal.call(cancel_and_inspect)
        assert status == "failed"
        assert data["campaign_fatal"] is True
        assert data["cost_liability_tokens"] > 0
        assert data["dispatch_status"] == "dispatch_possibly_started"
        assert campaign["blocked"]["category"] == "cancelled"
        client.portal.call(client.app.state.relationships.initialize)
        campaign = runner.fetch_campaign(client, state["campaign_digest"])["data"]
        assert campaign["blocked"]["category"] == "cancelled"
        stage_two = client.post(
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
        assert stage_two.status_code == 409
        with pytest.raises(RuntimeError, match="blocked"):
            consent(client, state, approval, 2)
    assert len(calls) == 2


@pytest.mark.parametrize(
    "dispatch_status,expected_liability",
    [
        ("reserved_never_dispatched", 0),
        ("dispatch_guard_passed", 1000),
        ("dispatch_possibly_started", 1000),
        ("provider_response_received", 1000),
    ],
)
def test_interrupted_reservation_blocks_campaign_after_restart(
    tmp_path, monkeypatch, dispatch_status, expected_liability
):
    protocol, state, directory, token, approval = setup(tmp_path, monkeypatch)
    settings = runner.build_settings("synthetic", protocol, directory, token)
    with runner.Client(settings, token) as client:

        async def seed():
            async with client.app.state.kernel.db.sessions.begin() as session:
                row = WebExperience(
                    id=runner.uid(),
                    instance_id=client.app.state.kernel.instance_id,
                    kind="research_relationship_analysis",
                    status="reserved",
                    data={
                        "consent_id": "simulated-crash",
                        "analysis_mode": "paired",
                        "reserved_tokens": 1000,
                        "dispatch_status": dispatch_status,
                        "campaign_digest": state["campaign_digest"],
                        "approval_id": approval["approval_id"],
                        "run_id": state["run_id"],
                        "stage": 1,
                        "task_id": state["task_order"][0],
                        "condition": "A",
                        "call_index": 0,
                        "content_sha256": "f" * 64,
                    },
                )
                session.add(row)
                await session.flush()
                return row.id

        attempt_id = client.portal.call(seed)
        client.portal.call(client.app.state.relationships.initialize)

        async def inspect():
            async with client.app.state.kernel.db.sessions() as session:
                row = await session.get(WebExperience, attempt_id)
                campaign = await client.app.state.approvals.campaign_locked(
                    session, state["campaign_digest"]
                )
                return row.status, dict(row.data), dict(campaign.data)

        status, data, campaign = client.portal.call(inspect)
        assert status == "interrupted"
        assert data["campaign_fatal"] is (dispatch_status != "reserved_never_dispatched")
        assert data["cost_liability_tokens"] == expected_liability
        assert campaign["blocked"]["reason"]
        stage_two = client.post(
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
        assert stage_two.status_code == 409


def test_index_one_before_index_zero_is_refused(tmp_path, monkeypatch):
    protocol, state, directory, token, approval = setup(tmp_path, monkeypatch)
    calls = capture_stub(monkeypatch)
    settings = runner.build_settings("synthetic", protocol, directory, token)
    with runner.Client(settings, token) as client:
        runner.reactivate_approved_grants(client, directory, state)
        with pytest.raises(RuntimeError, match="next eligible"):
            consent(client, state, approval, 1)
        assert calls == []
        first = dispatch(client, state, approval, 0)
        second = dispatch(client, state, approval, 1)
        assert first["analysis"]["data"]["call_index"] == 0
        assert second["analysis"]["data"]["call_index"] == 1
    assert len(calls) == 2


def test_concurrent_same_index_dispatches_at_most_once(tmp_path, monkeypatch):
    protocol, state, directory, token, approval = setup(tmp_path, monkeypatch)
    calls = capture_stub(monkeypatch)
    settings = runner.build_settings("synthetic", protocol, directory, token)
    with runner.Client(settings, token) as client:
        runner.reactivate_approved_grants(client, directory, state)
        first = consent(client, state, approval, 0)
        second = consent(client, state, approval, 0)

        async def race():
            return await asyncio.gather(
                client.app.state.relationships.analyze(first["id"]),
                client.app.state.relationships.analyze(second["id"]),
                return_exceptions=True,
            )

        results = client.portal.call(race)
        assert all(
            not isinstance(result, BaseException)
            or isinstance(result, (PermissionError, ValueError))
            for result in results
        ), results

        async def attempt_count():
            async with client.app.state.kernel.db.sessions() as session:
                rows = await client.app.state.approvals.attempts_locked(
                    session, state["campaign_digest"]
                )
                return len([row for row in rows if row.data.get("call_index") == 0])

        assert client.portal.call(attempt_count) == 1
    assert len(calls) == 1


def test_independent_client_cannot_replay_a_settled_cell(tmp_path, monkeypatch):
    protocol, state, directory, token, approval = setup(tmp_path, monkeypatch)
    calls = capture_stub(monkeypatch)
    settings = runner.build_settings("synthetic", protocol, directory, token)
    with runner.Client(settings, token) as first_client:
        runner.reactivate_approved_grants(first_client, directory, state)
        first = dispatch(first_client, state, approval, 0)
        assert first["analysis"]["data"]["call_index"] == 0
    with runner.Client(settings, token) as second_client:
        runner.reactivate_approved_grants(second_client, directory, state)
        with pytest.raises(RuntimeError, match="next eligible|already been attempted"):
            consent(second_client, state, approval, 0)
    assert len(calls) == 1


def test_later_index_cannot_overtake_missing_lower_index(tmp_path, monkeypatch):
    protocol, state, directory, token, approval = setup(tmp_path, monkeypatch)
    calls = capture_stub(monkeypatch)
    settings = runner.build_settings("synthetic", protocol, directory, token)
    with runner.Client(settings, token) as client:
        runner.reactivate_approved_grants(client, directory, state)

        async def seed():
            async with client.app.state.kernel.db.sessions.begin() as session:
                row = WebExperience(
                    id=runner.uid(),
                    instance_id=client.app.state.kernel.instance_id,
                    kind="research_relationship_analysis",
                    status="validated",
                    data={
                        "consent_id": "out-of-order",
                        "analysis_mode": "paired",
                        "reserved_tokens": 1000,
                        "dispatch_status": "provider_response_received",
                        "campaign_digest": state["campaign_digest"],
                        "approval_id": approval["approval_id"],
                        "run_id": state["run_id"],
                        "stage": 1,
                        "task_id": state["task_order"][0],
                        "condition": "B",
                        "call_index": 1,
                        "content_sha256": "f" * 64,
                        "cost_liability_tokens": 0,
                    },
                )
                session.add(row)
                await session.flush()

        client.portal.call(seed)
        with pytest.raises(RuntimeError, match="later call index"):
            consent(client, state, approval, 0)
        assert calls == []


def test_stage_two_cannot_dispatch_out_of_order(tmp_path, monkeypatch):
    protocol, state, directory, token, approval = setup(tmp_path, monkeypatch)
    calls = capture_stub(monkeypatch)
    settings = runner.build_settings("synthetic", protocol, directory, token)
    with runner.Client(settings, token) as client:
        runner.reactivate_approved_grants(client, directory, state)
        dispatch(client, state, approval, 0)
        dispatch(client, state, approval, 1)
    runner.approve("synthetic", synthetic=True, stage=2)
    state = runner.read_json(directory / "state.json")
    stage_two = runner.read_json(directory / "approval.json")
    assert stage_two["stage"] == 2
    with runner.Client(settings, token) as client:
        runner.reactivate_approved_grants(client, directory, state)
        with pytest.raises(RuntimeError, match="next eligible"):
            consent(client, state, stage_two, 3)
        accepted = dispatch(client, state, stage_two, 2)
        assert accepted["analysis"]["data"]["call_index"] == 2
    assert len(calls) == 3


def test_campaign_state_reports_technical_eligibility(tmp_path, monkeypatch):
    protocol, state, directory, token, approval = setup(tmp_path, monkeypatch)
    settings = runner.build_settings("synthetic", protocol, directory, token)
    with runner.Client(settings, token) as client:
        initial = runner.call(
            client,
            "GET",
            f"/research/experiment/campaigns/{state['campaign_digest']}/state",
        )
        assert initial["stage_1_eligible"] is False
        assert initial["stage_2_eligible"] is False
        assert initial["attempts"] == []
        runner.reactivate_approved_grants(client, directory, state)
        dispatch(client, state, approval, 0)
        dispatch(client, state, approval, 1)
        complete = runner.call(
            client,
            "GET",
            f"/research/experiment/campaigns/{state['campaign_digest']}/state",
        )
        assert complete["stage_1_eligible"] is True
        assert complete["stage_2_eligible"] is True
        assert [row["call_index"] for row in complete["attempts"]] == [0, 1]


def test_server_discloses_exact_instruction_and_schema(tmp_path, monkeypatch):
    protocol, state, directory, token, approval = setup(tmp_path, monkeypatch)
    settings = runner.build_settings("synthetic", protocol, directory, token)
    with runner.Client(settings, token) as client:
        record = runner.fetch_campaign(client, state["campaign_digest"])["data"]
    disclosure = record["disclosure"]
    assert disclosure["instructions"] == runner.PAIRED_INSTRUCTIONS
    assert disclosure["schema"] == runner.PairedAnswerOutput.model_json_schema()
    assert disclosure["instructions_sha256"] == record["content"]["instructions_sha256"]
    assert disclosure["schema_sha256"] == record["content"]["schema_sha256"]


def test_server_rejects_client_recomputed_instruction_hash(tmp_path, monkeypatch):
    protocol, state, directory, token, approval = setup(tmp_path, monkeypatch)
    campaign = runner.read_json(directory / "campaign.json")
    mutated = copy.deepcopy(campaign)
    mutated["content"]["instructions_sha256"] = "0" * 64
    mutated["manifest"]["instructions_sha256"] = "0" * 64
    mutated["campaign_digest"] = hashlib.sha256(
        json.dumps(mutated["content"], sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    settings = runner.build_settings("synthetic", protocol, directory, token)
    with runner.Client(settings, token) as client:
        response = client.post(
            runner.API + "/research/experiment/campaigns",
            json=mutated,
        )
    assert response.status_code == 409, response.text
    assert "instruction hash" in response.text.lower()


def test_duplicate_registration_accepts_identical_canonical_content(tmp_path, monkeypatch):
    protocol, state, directory, token, approval = setup(tmp_path, monkeypatch)
    campaign = runner.read_json(directory / "campaign.json")
    settings = runner.build_settings("synthetic", protocol, directory, token)
    with runner.Client(settings, token) as client:
        response = client.post(
            runner.API + "/research/experiment/campaigns",
            json=campaign,
        )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["campaign_digest"] == state["campaign_digest"]


def test_manifest_cell_divergence_is_rejected(tmp_path, monkeypatch):
    protocol, state, directory, token, approval = setup(tmp_path, monkeypatch)
    campaign = runner.read_json(directory / "campaign.json")
    mutated = copy.deepcopy(campaign)
    mutated["manifest"]["cells"][0]["question"] = "Cell question differs"
    settings = runner.build_settings("synthetic", protocol, directory, token)
    with runner.Client(settings, token) as client:
        response = client.post(
            runner.API + "/research/experiment/campaigns",
            json=mutated,
        )
    assert response.status_code == 409, response.text
    assert "display manifest" in response.text.lower()


@pytest.mark.parametrize(
    "field,value",
    [
        ("question", "DISPLAYED QUESTION DIFFERS FROM ENFORCED CONTENT"),
        ("current_excerpt", "Displayed current excerpt differs."),
        ("historical_excerpt", "Displayed historical excerpt differs."),
        ("current_url", "https://example.test/displayed-current"),
        ("historical_url", "https://example.test/displayed-historical"),
        ("current_sha256", "0" * 64),
        ("historical_sha256", "1" * 64),
        ("goal", "Displayed goal differs"),
        ("instructions_sha256", "2" * 64),
        ("schema_sha256", "3" * 64),
        ("provider", "meta"),
        ("model", "different-model"),
        ("max_output_tokens", 2048),
    ],
)
def test_manifest_divergence_is_rejected_at_registration(tmp_path, monkeypatch, field, value):
    protocol, state, directory, token, approval = setup(tmp_path, monkeypatch)
    campaign = runner.read_json(directory / "campaign.json")
    mutated = copy.deepcopy(campaign)
    if field in mutated["manifest"]["tasks"][0]:
        mutated["manifest"]["tasks"][0][field] = value
    else:
        mutated["manifest"][field] = value
    settings = runner.build_settings("synthetic", protocol, directory, token)
    with runner.Client(settings, token) as client:
        response = client.post(
            runner.API + "/research/experiment/campaigns",
            json=mutated,
        )
    assert response.status_code == 409, response.text
    assert "display manifest" in response.text.lower()


def test_registered_display_is_the_canonical_dispatch_content(tmp_path, monkeypatch):
    protocol, state, directory, token, approval = setup(tmp_path, monkeypatch)
    calls = capture_stub(monkeypatch)
    settings = runner.build_settings("synthetic", protocol, directory, token)
    with runner.Client(settings, token) as client:
        record = runner.fetch_campaign(client, state["campaign_digest"])["data"]
        assert record["manifest"]["tasks"] == record["content"]["tasks"]
        assert record["manifest"]["cells"] == record["content"]["cells"]
        assert record["manifest"]["stages"] == record["stages"]
        runner.reactivate_approved_grants(client, directory, state)
        dispatch(client, state, approval, 0)
    assert calls[0]["research_question"] == record["content"]["tasks"][0]["question"]
    assert "historical_excerpt" not in calls[0]
