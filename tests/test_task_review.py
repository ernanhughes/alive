# ruff: noqa: F811
"""Fast scripted infrastructure checks, never evidence of AI-quality improvement."""

import copy
import json

import httpx
import pytest

from alive.admission import live
from alive.sources.cli import principal
from alive.task_review import contracts, validation
from alive.workflows.context import digest
from tests.test_contextual_continuity import (  # noqa: F401
    BASE,
    case,
    quick_settle,
    ready,
    settings,
)
from tests.test_intent_interpretation import interpretation, respond_with
from tests.test_live_admission import call
from tests.test_pi_gateway import USAGE

CONTRACT = {"sha256": "a" * 64, "case_ids": ["c1", "c2"]}


def valid(contract=CONTRACT):
    return {
        "contract_version": 1,
        "contract_sha256": contract["sha256"],
        "explanation": "The divisor can be wrong; this is a prediction, not execution.",
        "predictions": [
            {
                "case_id": c,
                "observed": {"status": "predicted", "value": "2"},
                "required": {"status": "predicted", "value": "3"},
            }
            for c in contract["case_ids"]
        ],
        "defect": {"status": "determined", "issue_present": True},
        "citations": [],
        "reference_ids": [],
    }


@pytest.mark.parametrize(
    "change,code",
    [
        (lambda v: v.pop("predictions"), "missing_field"),
        (lambda v: v.pop("defect"), "missing_field"),
        (lambda v: v["predictions"].pop(), "missing_case"),
        (lambda v: v["predictions"].append(copy.deepcopy(v["predictions"][0])), "duplicate_case"),
        (lambda v: v["predictions"][0].update(case_id="fabricated"), "unexpected_case"),
        (
            lambda v: v.update(defect={"status": "determined", "issue_present": "true"}),
            "malformed_field",
        ),
        (lambda v: v.update(defect={"status": "undetermined", "reason": ""}), "malformed_field"),
        (lambda v: v.update(reference_ids=["not-supplied"]), "reference_not_supplied"),
        (lambda v: v.update(contract_version=2), "malformed_field"),
        (lambda v: v.update(contract_sha256="b" * 64), "contract_mismatch"),
    ],
)
def test_completion_errors(change, code):
    candidate = valid()
    change(candidate)
    result = validation.validate(candidate, CONTRACT, {}, [])
    assert not result["task_complete"]
    assert code in {e["code"] for e in result["errors"]}
    assert not result["semantically_verified"]


def test_complete_unknown_and_factually_wrong_are_not_verified():
    complete = validation.validate(valid(), CONTRACT, {}, [])
    assert complete["task_complete"] and complete["schema_valid"]
    assert not complete["semantically_verified"]  # Deliberately invented numerical predictions.
    candidate = valid()
    candidate["predictions"][0]["observed"] = {
        "status": "undetermined",
        "reason": "Input value unavailable",
    }
    candidate["defect"] = {"status": "undetermined", "reason": "Required behavior is not specified"}
    result = validation.validate(candidate, CONTRACT, {}, [])
    assert result["task_complete"] and result["contains_undetermined"]
    assert not result["semantically_verified"]


def test_repair_locks_partial_case_fields_and_explanation():
    candidate = valid()
    candidate["predictions"][1].pop("required")
    original = copy.deepcopy(candidate)
    changes = {"predictions": valid()["predictions"]}
    repair = {
        "contract_sha256": CONTRACT["sha256"],
        "original_sha256": digest(candidate),
        "changes": changes,
    }
    merged, result, rejected = validation.patch(candidate, repair, CONTRACT, {}, [])
    assert result["task_complete"] and rejected is None
    assert candidate == original and merged["explanation"] == candidate["explanation"]
    repair["changes"]["predictions"][0]["observed"]["value"] = "99"
    merged, _, rejected = validation.patch(candidate, repair, CONTRACT, {}, [])
    assert rejected and merged == original
    repair["changes"] = {"explanation": "Rewrite valid explanation"}
    assert validation.patch(candidate, repair, CONTRACT, {}, [])[2]


@pytest.fixture
def task(ready):
    client, upstream, _, body, *_ = ready
    setup = client.post(
        BASE + "/setup",
        json=body | {"adaptive": True, "code_review": True, "completion_repair": True},
    ).json()
    assert "terms" in setup, setup
    call(client, live.approve, setup["id"], confirm_sha256=setup["sha256"], principal=principal())
    state = {
        "inputs": [],
        "mode": "missing",
        "patch_overwrite": False,
        "settings": ready[-1],
        "setup_body": body,
    }

    def respond(request):
        data = json.loads(request["messages"][1]["content"])
        state["inputs"].append(data)
        if "conversation" not in data:
            return respond_with(lambda g: interpretation(g, problem_families=["numeric"]))(request)
        if "task_contract" not in data:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "answer": "General conversation still available",
                                        "recalled_item_ids": [],
                                        "citations": [],
                                        "uncertainty": [],
                                    }
                                )
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": USAGE,
                },
            )
        contract = data["task_contract"]
        if state["mode"] == "invalid-json" and "repair" not in data:
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "{broken-json"}, "finish_reason": "stop"}],
                    "usage": USAGE,
                },
            )
        candidate = valid(contract)
        candidate["citations"] = [{"file": "calc.py", "line_start": 1, "line_end": 1, "quote": ""}]
        if "repair" in data:
            repair = data["repair"]
            if state["mode"] == "repair-failed":
                return httpx.Response(503, json={"error": "unavailable"})
            candidate = {
                "contract_sha256": contract["sha256"],
                "original_sha256": repair["original_sha256"],
                "changes": {field: candidate[field] for field in repair["allowed_fields"]},
            }
            if state["patch_overwrite"]:
                candidate["changes"]["explanation"] = "Overwritten original"
        else:
            if state["mode"] == "explanation-missing":
                candidate.pop("explanation")
            elif state["mode"] != "complete":
                candidate["predictions"].pop()
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": json.dumps(candidate)}, "finish_reason": "stop"}
                ],
                "usage": USAGE,
            },
        )

    upstream.respond = respond
    ref = client.post(
        BASE + "/conversations", json={"consent_ref": setup["id"], "title": "Task review"}
    ).json()["id"]
    request = {
        "consent_ref": setup["id"],
        "conversation_ref": ref,
        "goal": "Review the arithmetic implementation",
        "task_mode": "code_review",
        "task_case_ids": ["c1", "c2"],
        "idempotency_key": "task-1",
    }
    return client, upstream, setup, request, state


def test_opt_in_partial_repair_replay_and_general_compatibility(task):
    client, upstream, setup, request, state = task
    request["repair_incomplete"] = True
    response = client.post(BASE + "/ask", json=request)
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["task_review"]["original"]["candidate"]["explanation"]
    assert not value["task_review"]["original"]["task_complete"]
    assert value["task_review"]["repair_successful"]
    assert value["task_review"]["additional_model_calls"] == 1
    assert value["model_calls"] == 3 and len(upstream.calls) == 3
    repair_input = state["inputs"][-1]
    assert repair_input["repair"]["allowed_fields"] == ["predictions"]
    assert repair_input["repair"]["errors"][0]["case_id"] == "c2"
    assert not value["task_review"]["effective"]["semantically_verified"]
    assert (
        value["task_review"]["effective"]["parent_candidate_id"]
        == value["task_review"]["original"]["candidate_id"]
    )
    assert client.post(BASE + "/ask", json=request).json() == value
    assert client.get(BASE + "/" + value["id"]).json() == value
    assert len(upstream.calls) == 3
    assert value["selection"]["policy"] == "selective-adaptation/v1"
    assert value["selection"]["decision"] == "none"
    assert value["selection"]["no_lesson_reason"] == "no_lessons_available"
    assert repair_input["source"] == state["inputs"][-2]["source"]
    assert repair_input["conversation"]["items"] == state["inputs"][-2]["conversation"]["items"]
    request.update(
        task_mode="general_contextual",
        task_case_ids=None,
        repair_incomplete=False,
        goal="Explain the earlier review",
        idempotency_key="general-2",
    )
    general = client.post(BASE + "/ask", json=request)
    assert general.status_code == 200, general.text
    assert general.json()["answer"]["answer"] == "General conversation still available"
    assert "task_contract" not in state["inputs"][-1]


def test_invalid_json_is_retained_without_claiming_schema_or_semantic_validity(task):
    client, _, _, request, state = task
    state["mode"] = "invalid-json"
    value = client.post(BASE + "/ask", json=request).json()["task_review"]["original"]
    assert value["raw_text"] == "{broken-json" and value["candidate"] is None
    assert value["transport_completed"] and not value["response_schema_valid"]
    assert not value["schema_valid"] and not value["task_complete"]
    assert not value["semantically_verified"]


def test_repair_and_case_changes_cannot_be_smuggled_into_replay(task):
    client, upstream, _, request, _ = task
    response = client.post(BASE + "/ask", json=request)
    assert response.status_code == 200, response.text
    count = len(upstream.calls)
    for change in (
        {"repair_incomplete": True},
        {"task_case_ids": ["different"]},
        {"task_mode": "general_contextual", "task_case_ids": None},
    ):
        refused = client.post(BASE + "/ask", json=request | change)
        assert refused.status_code == 409, refused.text
        assert len(upstream.calls) == count


def test_task_and_repair_need_their_explicit_standing_profiles(ready):
    client, upstream, setup, *_ = ready
    ref = client.post(BASE + "/conversations", json={"consent_ref": setup["id"]}).json()["id"]
    request = {
        "consent_ref": setup["id"],
        "conversation_ref": ref,
        "idempotency_key": "not-authorized",
        "goal": "Review",
        "task_mode": "code_review",
    }
    refused = client.post(BASE + "/ask", json=request)
    assert refused.status_code == 409 and not upstream.calls


def test_restart_preserves_original_repair_and_receipts_without_inference(task):
    from fastapi.testclient import TestClient

    from alive.app import create_app
    from tests.conftest import TOKEN
    from tests.test_pi_gateway import use_pi

    client, upstream, _, request, state = task
    request["repair_incomplete"] = True
    before = client.post(BASE + "/ask", json=request).json()
    assert before["task_review"]["repair_successful"]
    count = len(upstream.calls)
    client.__exit__(None, None, None)
    with TestClient(
        create_app(state["settings"]), headers={"Authorization": "Bearer " + TOKEN}
    ) as reopened:
        runtime = use_pi(reopened, state["settings"], upstream)
        runtime.egress.workflow_guard = reopened.app.state.workflows.authorize_dispatch
        assert reopened.get(BASE + "/" + before["id"]).json() == before
        assert reopened.post(BASE + "/ask", json=request).json() == before
        assert len(upstream.calls) == count


def test_general_contract_identity_is_unchanged():
    from alive.continuity.contracts import role_contract

    assert role_contract() == "26abfc77d3f5e32a533ef4a07c5d8ad5790733bcec9e3846fdab403205b3579a"
    assert contracts.role_contract() != role_contract()


def test_complete_first_pass_does_not_spend_a_repair(task):
    client, upstream, _, request, state = task
    state["mode"] = "complete"
    request["repair_incomplete"] = True
    result = client.post(BASE + "/ask", json=request).json()["task_review"]
    assert result["original"]["task_complete"]
    assert not result["repair_attempted"] and result["additional_model_calls"] == 0
    assert len(upstream.calls) == 2


def test_repair_of_missing_explanation_returns_new_candidate_and_keeps_original(task):
    client, _, _, request, state = task
    state["mode"] = "explanation-missing"
    request["repair_incomplete"] = True
    value = client.post(BASE + "/ask", json=request).json()
    assert value["task_review"]["repair_successful"]
    assert "explanation" not in value["task_review"]["original"]["candidate"]
    assert value["answer"]["answer"] == valid()["explanation"]
    assert (
        value["answer"]["parent_candidate_id"] == value["task_review"]["original"]["candidate_id"]
    )


def test_response_parser_and_partial_value_gate_preserve_unknown_information():
    spec = contracts.Spec({}, lambda _: {})
    parsed = spec.parse("{invalid")
    assert parsed.raw_text == "{invalid" and parsed.candidate is None
    assert spec.parse('{"value": NaN}').candidate is None
    candidate = valid()
    candidate["predictions"][0]["required"] = {"status": "undetermined", "reason": "  "}
    result = validation.validate(candidate, CONTRACT, {}, [])
    assert not result["task_complete"]
    assert (
        result["accepted"]["predictions"]["c1"]["observed"] == valid()["predictions"][0]["observed"]
    )


@pytest.mark.parametrize(
    "declaration,expected",
    [
        ('[{"id":"c1","input":null},{"id":"c2","input":[]}]', ["c1", "c2"]),
        ('[{"id":"c1"},{"id":"c1"}]', None),
        ("not-json", None),
        ("[]", []),
    ],
)
def test_declared_source_cases_are_exact_and_never_execute_source(declaration, expected):
    import hashlib
    from types import SimpleNamespace

    from alive.continuity.context import empty_snapshot
    from alive.task_review.service import package
    from alive.workflows.context import Refused

    texts = {
        "README.md": "Named input cases: " + declaration + "\n",
        "calc.py": "raise RuntimeError('source must never execute')\n",
    }
    files = [
        {
            "path": path,
            "content": text,
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "bytes": len(text.encode()),
        }
        for path, text in texts.items()
    ]
    source = SimpleNamespace(
        source_ref="unit-capture",
        approval_id="unit-approval",
        content={"files": files},
        content_sha256=digest(files),
        scoped_sha256=digest(files),
    )
    if expected is None:
        with pytest.raises(Refused, match="invalid_declared_task_cases"):
            package(source, list(texts), "Review", empty_snapshot())
    else:
        result = package(source, list(texts), "Review", empty_snapshot())
        contract = result["task_contract"]
        assert contract["case_ids"] == expected
        assert digest({k: v for k, v in contract.items() if k != "sha256"}) == contract["sha256"]
        assert contract["source"]["approval_id"] == "unit-approval"


def test_new_task_metadata_and_repair_candidate_remain_bound_to_source(task):
    from sqlalchemy import select

    from alive.continuity import service as continuity
    from alive.models import Event
    from alive.workflows.context import Refused

    client, upstream, _, request, _ = task
    request["repair_incomplete"] = True
    result = client.post(BASE + "/ask", json=request).json()
    assert result["task_review"]["repair_successful"]
    ref = result["task_review"]["repair_admission"]["terms"]["proposed_grant_data"]["inputs"][
        "context_ref"
    ]

    async def tamper(kernel):
        async with kernel.db.sessions.begin() as session:
            row = await session.scalar(select(Event).where(Event.id == ref))
            payload = copy.deepcopy(row.payload)
            payload["snapshot"]["completion_repair"]["original_candidate"]["explanation"] = (
                "tampered"
            )
            payload["sha256"] = digest(payload["snapshot"])
            row.payload = payload
        async with kernel.db.sessions() as session:
            with pytest.raises(Refused, match="task_repair_candidate_changed"):
                await continuity.frozen(
                    session,
                    kernel,
                    ref,
                    result["source"]["resources"],
                    principal(),
                )

    count = len(upstream.calls)
    call(client, tamper)
    assert len(upstream.calls) == count


def test_repair_budget_block_preserves_partial_and_cannot_dispatch_on_retry(task):
    client, upstream, _, request, state = task
    setup = client.post(
        BASE + "/setup",
        json=state["setup_body"]
        | {"adaptive": True, "code_review": True, "completion_repair": True, "max_calls": 2},
    ).json()
    call(client, live.approve, setup["id"], confirm_sha256=setup["sha256"], principal=principal())
    ref = client.post(BASE + "/conversations", json={"consent_ref": setup["id"]}).json()["id"]
    request.update(consent_ref=setup["id"], conversation_ref=ref, repair_incomplete=True)
    response = client.post(BASE + "/ask", json=request)
    assert response.status_code == 200, response.text
    value = response.json()
    review = value["task_review"]
    assert review["original"]["candidate"]["predictions"]
    assert review["repair_blocked"]["reason"] == "budget_exhausted"
    assert not review["repair_attempted"] and review["additional_model_calls"] == 0
    assert len(upstream.calls) == 2
    assert client.post(BASE + "/ask", json=request).json() == value
    assert len(upstream.calls) == 2


def test_repair_profile_cannot_select_a_different_authorized_model(task):
    client, upstream, _, _, state = task
    state["settings"].alive_role_models = {contracts.REPAIR_ROLE: "different-model"}
    response = client.post(
        BASE + "/setup", json=state["setup_body"] | {"code_review": True, "completion_repair": True}
    )
    assert response.status_code == 409 and not upstream.calls


def test_repair_rejected_at_dispatch_counts_zero_additional_provider_calls(task):
    client, upstream, _, request, _ = task
    request["repair_incomplete"] = True
    original_guard = client.app.state.pi.egress.workflow_guard

    async def fence(session, call):
        if call.role == contracts.REPAIR_ROLE:
            return False
        return await original_guard(session, call)

    client.app.state.pi.egress.workflow_guard = fence
    response = client.post(BASE + "/ask", json=request)
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["task_review"]["repair_attempted"]
    assert value["task_review"]["additional_model_calls"] == 0
    assert value["model_calls"] == 2 and len(upstream.calls) == 2
    assert value["availability"] == "available"
    assert not value["task_review"]["original"]["task_complete"]


@pytest.mark.parametrize(
    "mode,overwrite,repair",
    [("missing", False, False), ("missing", True, True), ("repair-failed", False, True)],
)
def test_partial_is_preserved_when_disabled_rejected_or_failed(task, mode, overwrite, repair):
    client, upstream, _, request, state = task
    state.update(mode=mode, patch_overwrite=overwrite)
    request["repair_incomplete"] = repair
    response = client.post(BASE + "/ask", json=request)
    assert response.status_code == 200, response.text
    value = response.json()
    review = value["task_review"]
    assert not review["effective"]["task_complete"]
    assert review["original"]["raw_text"] and review["original"]["candidate"]["predictions"]
    assert review["effective"]["candidate"] == review["original"]["candidate"]
    count = len(upstream.calls)
    assert count == 2 + repair
    assert client.post(BASE + "/ask", json=request).json() == value
    assert len(upstream.calls) == count
