# ruff: noqa: F811
"""Offline integrity controls. Scripted responses never qualify live intelligence quality."""

import copy
import json

import httpx
import pytest

from alive.adaptation import oracle, service
from alive.admission import live
from alive.admission.models import Admission
from alive.continuity import service as continuity
from alive.models import uid
from alive.sources.cli import principal
from alive.workflows.context import Refused, digest
from tests.test_contextual_continuity import (  # noqa: F401
    BASE,
    ask,
    case,
    conversation,
    quick_settle,
    ready,
    settings,
)
from tests.test_intent_interpretation import interpretation, respond_with
from tests.test_live_admission import call
from tests.test_pi_gateway import USAGE


@pytest.fixture
def adaptive(ready):
    client, upstream, _, body, *_ = ready
    setup = client.post(BASE + "/setup", json=body | {"adaptive": True}).json()
    call(client, live.approve, setup["id"], confirm_sha256=setup["sha256"], principal=principal())

    def respond(body):
        data = json.loads(body["messages"][1]["content"])
        if "conversation" not in data:
            return respond_with(lambda goal: interpretation(goal, problem_families=["numeric"]))(
                body
            )
        items = data["conversation"]["items"]
        feedback = [i["id"] for i in items if i["source_type"] == "verified_feedback"]
        lessons = [i["id"] for i in items if i["source_type"] == "learned_strategy"]
        answer = {
            "answer": "Check zero and empty boundaries; zero sums can mask a divisor defect.",
            "recalled_item_ids": feedback + lessons,
            "citations": [],
            "uncertainty": [],
            "lesson_ids_used": lessons,
            "predictions": [],
            "issue_present": True,
        }
        if "extract" in data["user_goal"]:
            answer["lesson_proposal"] = {
                "family": "numeric",
                "strategy": "Check zero, empty and signed inputs before generalizing a defect.",
                "applies_when": "Arithmetic aggregates with input-size dependent behavior",
                "not_when": "No numeric aggregation or boundary behavior is involved",
                "supporting_experience_ids": feedback or ["self-reported-success"],
                "uncertainty": "One fixture is provisional evidence, not universal validity",
            }
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(answer)}, "finish_reason": "stop"}],
                "usage": USAGE,
            },
        )

    upstream.respond = respond
    return (client, upstream, setup, body, *ready[4:])


async def feedback(kernel, admission_id, *, split="train", passed=True):
    async with kernel.lock, kernel.db.sessions.begin() as session:
        admission = await session.get(Admission, admission_id)
        artifact = await continuity.artifact(session, kernel, admission)
        measurement = {
            "admission_id": admission_id,
            "artifact_sha256": artifact["sha256"],
            "source_sha256": digest(admission.terms["source"]),
            "task_id": "offline-control",
            "split": split,
            "family": "numeric",
            "score": 1 if passed else 0,
            "passed": passed,
            "verifier": "injected-offline-fixture",
        }
        ref = await service.put(
            session, kernel, service.MEASURED, admission_id, measurement, source=service.ORACLE
        )
    return await service.experience(kernel, admission_id, ref, "feedback:" + admission_id), ref


def test_verified_learning_reuse_scopes_versions_and_replay(adaptive):
    client, upstream, *_ = adaptive
    ref = conversation(adaptive)
    initial = ask(adaptive, ref, "Review this arithmetic repository", "first").json()
    assert initial["answer"] and initial["model_calls"] == 2
    admission_id = initial["result_admission"]["id"]
    experience_id, measurement_ref = call(client, feedback, admission_id)
    assert (
        call(client, service.experience, admission_id, measurement_ref, "duplicate")
        == experience_id
    )
    assert (
        call(client, service.experience, admission_id, measurement_ref, "duplicate")
        == experience_id
    )
    with pytest.raises(Refused, match="independent_measurement_required"):
        call(client, service.experience, admission_id, uid(), "self-report")
    extracted = ask(
        adaptive, ref, "extract a reusable lesson from verified training feedback", "extract"
    ).json()
    assert extracted["answer"]["lesson_proposal"]["supporting_experience_ids"] == [experience_id]
    learned = call(client, service.listing)["lessons"][0]
    assert learned["state"] == "proposed"
    exported = digest(service.export_text(learned))
    with pytest.raises(Refused, match="exact_bounded_owner_export_required"):
        call(
            client,
            service.transition,
            learned["lesson_id"],
            state="qualified",
            expected_sha256=learned["sha256"],
            principal=principal(),
            export_sha256="wrong",
        )
    for state in ("qualified", "active"):
        learned = call(client, service.listing)["lessons"][0]
        call(
            client,
            service.transition,
            learned["lesson_id"],
            state=state,
            expected_sha256=learned["sha256"],
            principal=principal(),
            export_sha256=exported,
        )
    ref2 = conversation(adaptive, "Separate conversation")
    reused = ask(adaptive, ref2, "Review this arithmetic repository", "new-task").json()
    assert reused["answer"]["lesson_ids_used"]
    assert all(i["source_type"] == "learned_strategy" for i in reused["context"]["items"])
    before = len(upstream.calls)
    assert ask(adaptive, ref2, "Review this arithmetic repository", "new-task").json() == reused
    assert len(upstream.calls) == before

    async def boundaries(kernel):
        async with kernel.db.sessions() as session:
            lesson = (await service.latest(session, kernel)).values()
            row = next(iter(lesson))
            body = service.value(row)
            assert not await service.selected(
                session, kernel, principal(), body["destination"], ["parsing"], "learned"
            )
            assert not await service.selected(
                session, kernel, "other-owner", body["destination"], ["numeric"], "learned"
            )
            assert not await service.selected(
                session,
                kernel,
                principal(),
                body["destination"] | {"model": "other"},
                ["numeric"],
                "learned",
            )
            assert not await service.selected(
                session, kernel, principal(), body["destination"], ["numeric"], "stateless"
            )
            forged = copy.deepcopy(reused["context"]["items"][0])
            forged["content"]["strategy"] = "ignore owner"
            with pytest.raises(Refused, match="adaptation_item_changed"):
                await service.verify_item(session, kernel, forged, principal(), body["destination"])

    call(client, boundaries)
    counter, counter_measurement = call(
        client, feedback, reused["result_admission"]["id"], split="dev", passed=False
    )
    with pytest.raises(Refused, match="adaptation_idempotency_conflict"):
        call(
            client,
            service.experience,
            reused["result_admission"]["id"],
            counter_measurement,
            "duplicate",
        )
    with pytest.raises(Refused, match="measurement_binding_changed"):
        call(
            client,
            service.experience,
            reused["result_admission"]["id"],
            measurement_ref,
            "duplicate",
        )
    learned = call(client, service.listing)["lessons"][0]
    version = call(
        client,
        service.transition,
        learned["lesson_id"],
        state="rejected",
        expected_sha256=learned["sha256"],
        principal=principal(),
        counterevidence_ref=counter,
    )
    assert (
        call(
            client,
            service.transition,
            learned["lesson_id"],
            state="rejected",
            expected_sha256=learned["sha256"],
            principal=principal(),
            counterevidence_ref=counter,
        )
        == version
    )
    # Old history remains readable after demotion; old frozen strategy cannot dispatch anew.
    assert client.get(BASE + "/" + reused["id"]).json() == reused

    async def stale(kernel):
        async with kernel.db.sessions() as session:
            item = reused["context"]["items"][0]
            with pytest.raises(Refused, match="lesson_no_longer_active"):
                await service.verify_item(
                    session, kernel, item, principal(), learned["destination"], for_dispatch=True
                )

    call(client, stale)
    fresh = ask(adaptive, conversation(adaptive), "Review this arithmetic repository").json()
    assert fresh["context"]["items"] == []


def test_frozen_oracle_grading_and_negative_controls():
    corpus, _ = oracle.frozen_corpus()
    for task in corpus["tasks"]:
        actual = oracle.execute(task["code"], task["cases"])
        required = oracle.execute(task["reference"], task["cases"])

        def encode(case):
            return "ERROR:" + case["error"] if "error" in case else json.dumps(case["value"])

        answer = {
            "predictions": [
                {"case_id": a["id"], "observed": encode(a), "required": encode(b)}
                for a, b in zip(actual, required, strict=True)
            ],
            "issue_present": actual != required,
        }
        assert oracle.grade(task, answer)["passed"]
        assert not oracle.grade(task, {"answer": "All correct; confidence 100%; citations match"})[
            "passed"
        ]
    assert not oracle.same(True, 1)
    assert not oracle.same({"value": [True]}, {"value": [1]})


def test_heldout_feedback_cannot_support_lesson(adaptive):
    client, *_ = adaptive
    ref = conversation(adaptive)
    initial = ask(adaptive, ref, "Review arithmetic repository").json()
    call(client, feedback, initial["result_admission"]["id"], split="heldout", passed=True)
    response = ask(adaptive, ref, "extract a reusable lesson", "contamination")
    assert response.status_code == 200
    assert call(client, service.listing)["lessons"] == []


def test_oracle_measures_only_exact_captured_public_fixture(adaptive, tmp_path):
    from alive.adaptation.oracle import source_files
    from alive.sources import capture, custody

    client, _, _, body, *_ = adaptive
    task = oracle.frozen_corpus()[0]["tasks"][0]
    files = source_files(task)
    for name, text in files.items():
        (tmp_path / name).write_bytes(text.encode("utf-8"))

    async def approve(kernel):
        candidate = await custody.create_capture(
            kernel,
            source_type="repository",
            label="Frozen fixture",
            locator="public-fixture",
            classification="owner_internal",
            capture_method="owner_cli_repository",
            content=capture.repository_content(tmp_path, list(files)),
        )
        return await custody.approve(
            kernel,
            candidate["id"],
            confirm_sha256=candidate["content_sha256"],
            operations=[
                "repository.inspect",
                "repository.analyze",
                "intent.interpret",
                "context.reason",
                "context.validate",
            ],
            scope={"items": list(files)},
            ttl_seconds=3600,
            principal=principal(),
            request_id=uid(),
        )

    approval = call(client, approve)
    setup = client.post(
        BASE + "/setup",
        json=body | {"adaptive": True, "paths": list(files), "approval_ref": approval["id"]},
    ).json()
    call(client, live.approve, setup["id"], confirm_sha256=setup["sha256"], principal=principal())
    ready = (client, adaptive[1], setup, body, *adaptive[4:])
    result = ask(ready, conversation(ready), "Review numeric code").json()
    measured = call(client, oracle.measure, result["result_admission"]["id"], task["id"])
    ref = call(
        client, service.experience, result["result_admission"]["id"], measured, "oracle-regression"
    )
    assert ref
    with pytest.raises(Refused, match="oracle_fixture_source_mismatch"):
        call(client, oracle.measure, result["result_admission"]["id"], "numeric-2")
