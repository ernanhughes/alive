"""Pin observatory ownership against two real Pi workflows; no production writes."""

import json

import pytest
from sqlalchemy import select, text, update

from alive.cognitive_models import ModelInvocation
from alive.models import Instance
from alive.pi.models import PiRun
from alive.workflows.models import WorkflowDefinition, WorkflowRun, WorkflowStageRun
from tests.workflow_execution_helpers import call, lifecycle, observation
from tests.workflow_r2_helpers import pi_environment


def get(client, path, **kw):
    return client.get("/api/v1" + path, **kw)


def build_two(client, settings, monkeypatch):
    upstream = pi_environment(client, settings, monkeypatch)
    runner, cognition = client.app.state.workflows, client.app.state.cognition
    a, _ = call(client, lambda k: lifecycle(k, cognition, runner, model=True))
    observation(client)
    b, _ = call(client, lambda k: lifecycle(k, cognition, runner, model=True))
    return upstream, a, b


def stages_of(client, run_id):
    return get(client, f"/workflow-runs/{run_id}/stages").json()["stages"]


def attempt(client, run_id, stage_id):
    return next(s for s in stages_of(client, run_id) if s["stage_id"] == stage_id)


ATTACKS = [
    "foreign_attempt_via_other_run",
    "unknown_attempt",
    "deterministic_attempt_receipt",
    "pi_pointer_from_other_run",
    "invocation_pointer_from_other_run",
    "pi_other_instance",
    "pi_wrong_operation",
    "invocation_wrong_stage",
    "invocation_wrong_investigation",
    "invocation_wrong_run",
    "run_other_instance",
    "definition_json_altered",
    "definition_hash_altered",
    "stage_not_in_definition",
]


@pytest.mark.parametrize("attack", ATTACKS)
def test_b_identity_attacks_are_refused_server_side(client, settings, monkeypatch, attack):
    upstream, a, b = build_two(client, settings, monkeypatch)
    a_id, b_id = a["id"], b["id"]
    a_analyze, b_analyze = attempt(client, a_id, "analyze"), attempt(client, b_id, "analyze")
    assert a["status"] == b["status"] == "COMPLETED"
    assert a_analyze["pi_run_id"] != b_analyze["pi_run_id"]
    for run_id in (a_id, b_id):
        assert get(client, f"/workflow-runs/{run_id}/inspection").status_code == 200
    b_prepare = attempt(client, b_id, "prepare")
    probes = {}

    async def mutate(k):
        async with k.lock, k.db.sessions.begin() as session:
            pi_a = await session.scalar(select(PiRun).where(PiRun.id == a_analyze["pi_run_id"]))
            pi_b = await session.scalar(select(PiRun).where(PiRun.id == b_analyze["pi_run_id"]))
            inv_a = await session.get(ModelInvocation, a_analyze["model_invocation_id"])
            inv_b = await session.get(ModelInvocation, b_analyze["model_invocation_id"])
            if attack == "pi_pointer_from_other_run":
                await session.execute(
                    update(WorkflowStageRun)
                    .where(WorkflowStageRun.id == b_analyze["id"])
                    .values(pi_run_id=pi_a.id)
                )
            elif attack == "invocation_pointer_from_other_run":
                await session.execute(
                    update(WorkflowStageRun)
                    .where(WorkflowStageRun.id == b_analyze["id"])
                    .values(model_invocation_id=inv_a.id)
                )
            elif attack == "pi_other_instance":
                session.add(Instance(id="00000000-0000-4000-8000-000000000001"))
                await session.flush()
                pi_b.instance_id = "00000000-0000-4000-8000-000000000001"
            elif attack == "pi_wrong_operation":
                pi_b.operation = "other.operation"
            elif attack == "invocation_wrong_stage":
                inv_b.input_json = {**inv_b.input_json, "workflow_stage_id": b_prepare["id"]}
            elif attack == "invocation_wrong_investigation":
                inv_b.investigation_id = inv_a.investigation_id
            elif attack == "invocation_wrong_run":
                inv_b.input_json = {**inv_b.input_json, "workflow_run_id": a_id}
            elif attack == "run_other_instance":
                session.add(Instance(id="00000000-0000-4000-8000-000000000002"))
                await session.flush()
                await session.execute(
                    update(WorkflowRun)
                    .where(WorkflowRun.id == b_id)
                    .values(instance_id="00000000-0000-4000-8000-000000000002")
                )
            elif attack == "definition_json_altered":
                row = await session.get(WorkflowDefinition, b["workflow"]["definition_id"])
                changed = json.loads(json.dumps(row.definition_json))
                changed["title"] = "tampered title"
                await session.execute(
                    text(
                        "UPDATE workflow_definitions SET definition_json = :definition "
                        "WHERE id = :id"
                    ),
                    {"definition": json.dumps(changed), "id": row.id},
                )
            elif attack == "definition_hash_altered":
                await session.execute(
                    update(WorkflowRun)
                    .where(WorkflowRun.id == b_id)
                    .values(definition_sha256="0" * 64)
                )
            elif attack == "stage_not_in_definition":
                await session.execute(
                    update(WorkflowStageRun)
                    .where(WorkflowStageRun.id == b_prepare["id"])
                    .values(stage_id="phantom")
                )

    if attack == "foreign_attempt_via_other_run":
        probes["receipt_other_run_attempt"] = get(
            client, f"/workflow-runs/{b_id}/stages/{a_analyze['id']}/pi-receipt"
        ).status_code
    elif attack == "unknown_attempt":
        probes["receipt_unknown"] = get(
            client, f"/workflow-runs/{b_id}/stages/00000000-0000-4000-8000-0000000000aa/pi-receipt"
        ).status_code
    elif attack == "deterministic_attempt_receipt":
        probes["receipt_prepare"] = get(
            client, f"/workflow-runs/{b_id}/stages/{b_prepare['id']}/pi-receipt"
        ).status_code
    else:
        call(client, mutate)
        probes["inspection_b"] = get(client, f"/workflow-runs/{b_id}/inspection").status_code
        probes["timeline_b"] = get(client, f"/workflow-runs/{b_id}/timeline").status_code
        probes["receipt_b"] = get(
            client, f"/workflow-runs/{b_id}/stages/{b_analyze['id']}/pi-receipt"
        ).status_code
        probes["artifact_b"] = get(client, f"/workflow-runs/{b_id}/artifacts/record").status_code
        probes["inspection_a_unaffected"] = get(
            client, f"/workflow-runs/{a_id}/inspection"
        ).status_code
    if attack in {
        "foreign_attempt_via_other_run",
        "unknown_attempt",
        "deterministic_attempt_receipt",
    }:
        assert set(probes.values()) == {404}
    else:
        assert probes["inspection_b"] == 404, probes
        assert probes["timeline_b"] == 404, probes
        assert probes["receipt_b"] == 404, probes
        if attack != "definition_json_altered":
            assert probes["inspection_a_unaffected"] == 200, probes
    assert len(upstream.calls) == 2, "history reads must not dispatch a provider call"


def test_c_timeline_pagination_and_run_isolation(client, settings, monkeypatch):
    upstream, a, b = build_two(client, settings, monkeypatch)
    full = get(client, f"/workflow-runs/{a['id']}/timeline?limit=500").json()
    seqs = [e["sequence"] for e in full["events"]]
    a_pi = {s["pi_run_id"] for s in stages_of(client, a["id"]) if s["pi_run_id"]}
    b_pi = {s["pi_run_id"] for s in stages_of(client, b["id"]) if s["pi_run_id"]}

    def pages(limit):
        out, after, hops = [], 0, 0
        while hops <= len(full["events"]) + 1:
            page = get(
                client, f"/workflow-runs/{a['id']}/timeline?after={after}&limit={limit}"
            ).json()
            out += page["events"]
            hops += 1
            if not page["has_more"]:
                return out, hops
            assert page["events"], "has_more with an empty page"
            assert page["next_after"] > after
            after = page["next_after"]
        pytest.fail("timeline pagination did not terminate")

    paged = {limit: pages(limit) for limit in (1, 2, 3, 7)}
    edge_exact = get(client, f"/workflow-runs/{a['id']}/timeline?limit={len(seqs)}").json()
    edge_short = get(client, f"/workflow-runs/{a['id']}/timeline?limit={len(seqs) - 1}").json()
    beyond = get(client, f"/workflow-runs/{a['id']}/timeline?after=99999999").json()
    bad = {
        "after=-1": get(client, f"/workflow-runs/{a['id']}/timeline?after=-1").status_code,
        "limit=0": get(client, f"/workflow-runs/{a['id']}/timeline?limit=0").status_code,
        "limit=501": get(client, f"/workflow-runs/{a['id']}/timeline?limit=501").status_code,
        "after=abc": get(client, f"/workflow-runs/{a['id']}/timeline?after=abc").status_code,
    }
    foreign_pi = [e for e in full["events"] if e["pi_run_id"] in b_pi]
    foreign_run = [e for e in full["events"] if e["run_id"] != a["id"]]
    pi_events = [e for e in full["events"] if e["event_type"].startswith("pi.")]
    assert seqs and a_pi and b_pi and a_pi.isdisjoint(b_pi)
    assert beyond["events"] == [] and beyond["next_after"] == 99999999
    assert beyond["has_more"] is False
    assert len(upstream.calls) == 2
    assert seqs == sorted(set(seqs))
    for limit, (events, _) in paged.items():
        assert events == full["events"], limit
    assert edge_exact["has_more"] is False and edge_short["has_more"] is True
    assert not foreign_pi and not foreign_run
    assert {e["pi_run_id"] for e in pi_events} == a_pi
    assert set(bad.values()) == {422}
    assert full["complete_transition_history"] is False
