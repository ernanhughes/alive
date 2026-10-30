"""INT-02 production-shaped fixture integration; no live inference or action execution."""

import asyncio
import copy
import os
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select, update

from alive.intelligence import fixture, store
from alive.intelligence.contracts import OutcomeFeedback, ShadowResult
from alive.intelligence.models import (
    IntelligenceEpisode as Episode,
)
from alive.intelligence.models import (
    IntelligenceFeedback as Feedback,
)
from alive.intelligence.models import (
    IntelligenceLearningUpdate as LearningUpdate,
)
from alive.models import Event, Instance, uid
from alive.workflows.models import ImmutableRecord, WorkflowStageRun


def call(client, fn, *args, **kwargs):
    return client.portal.call(lambda: fn(client.app.state.kernel, *args, **kwargs))


async def counts(kernel):
    async with kernel.db.sessions() as session:
        return tuple(
            [
                await session.scalar(select(func.count()).select_from(model))
                for model in (Episode, Feedback, LearningUpdate, Event)
            ]
        )


@pytest.fixture(autouse=True)
def mutation_probe(monkeypatch):
    """Controlled test-only runtime mutations; no production mutation switch exists."""
    mutation = os.environ.get("ALIVE_INT02_MUTATION")
    original = store.require
    if mutation in ("trust", "payload"):
        message = {
            "trust": "Independent custody record required",
            "payload": "Feedback source/decision/payload substitution",
        }[mutation]
        monkeypatch.setattr(
            store,
            "require",
            lambda condition, text: None if text == message else original(condition, text),
        )
    elif mutation == "frozen":
        original_policies = store.policies
        monkeypatch.setattr(
            store,
            "policies",
            lambda state: (original_policies(state)[1], original_policies(state)[1]),
        )
    elif mutation == "update":
        from alive.intelligence.policies.empirical import EmpiricalPolicy

        monkeypatch.setattr(EmpiricalPolicy, "updated", lambda self, action, reward: self)
    elif mutation == "workflow":
        monkeypatch.setattr(
            store,
            "require",
            lambda condition, text: (
                None if text == "Historical fixture workflow changed" else original(condition, text)
            ),
        )


def test_complete_restart_replay_and_read_only_api(settings):
    from fastapi.testclient import TestClient

    from alive.app import create_app
    from tests.conftest import TOKEN

    # Existing schema test convention; migration parity is independently exercised below.
    async def schema():
        from alive.db import Database
        from alive.models import Base

        db = Database(settings.database_url)
        async with db.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await db.engine.dispose()

    asyncio.run(schema())
    headers = {"Authorization": f"Bearer {TOKEN}"}
    with TestClient(create_app(settings), headers=headers) as client:
        chain = call(client, fixture.lifecycle)
        first, second = chain["episodes"]
        assert chain["monitor_samples"] == 1 and chain["candidate_revision"] == 1
        assert first["intelligence_proposal"] == first["active_policy_choice"] == "monitor"
        assert second["intelligence_proposal"] == "retrieve"
        assert second["active_policy_choice"] == "monitor"
        assert second["previous_id"] == first["id"]
        assert first["observed_fixture_action"] == "monitor" and first["observed_reward"] == -0.5
        assert all(
            e["authorized_action"] is None
            and e["executed_action"] is None
            and e["workflow_state"] == "PENDING"
            for e in chain["episodes"]
        )
        saved_counts = call(client, counts)
        assert client.get("/api/v1/intelligence/states/" + chain["id"]).json() == chain
        assert (
            client.get("/api/v1/intelligence/states", headers={"Authorization": ""}).status_code
            == 401
        )
        assert client.post("/api/v1/intelligence/states/" + chain["id"], json={}).status_code == 405
    with TestClient(create_app(settings), headers=headers) as restarted:
        for _ in range(3):
            replayed = restarted.get("/api/v1/intelligence/states/" + chain["id"]).json()
            assert replayed == chain
        # Kernel restart adds its own event; replay itself adds no records/events.
        before = call(restarted, counts)
        assert before[:3] == saved_counts[:3]
        assert restarted.get("/api/v1/intelligence/episodes/" + first["id"]).json() == first
        assert call(restarted, counts) == before
        text = str(replayed)
        assert "safe_text" not in text and "excerpt" not in text and TOKEN not in text


def setup_episode(client, *, shadow=None):
    state = call(client, fixture.start)
    episode = call(client, fixture.assessment, state, shadow=shadow)
    source, feedback = call(client, fixture.independent_outcome, episode)
    return state, episode, source, feedback


def test_durable_identical_duplicate_conflict_and_restart_safe(client):
    state, episode, source, feedback = setup_episode(client)
    assert (
        call(
            client,
            store.accept_feedback,
            episode_id=episode,
            source_event_id=source,
            feedback=feedback,
        )
        == "accepted"
    )
    before = call(client, counts)
    assert (
        call(
            client,
            store.accept_feedback,
            episode_id=episode,
            source_event_id=source,
            feedback=feedback,
        )
        == "duplicate"
    )
    with pytest.raises(store.Refused):
        call(
            client,
            store.accept_feedback,
            episode_id=episode,
            source_event_id=source,
            feedback=OutcomeFeedback.model_validate(feedback.model_dump() | {"result": "changed"}),
        )
    assert call(client, counts)[:3] == before[:3]
    assert call(client, store.inspect_chain, state)["monitor_samples"] == 1


@pytest.mark.parametrize(
    "change",
    [
        {"episode_id": "other"},
        {"goal_id": "other"},
        {"proposal_id": "other"},
        {"observed_action": "retrieve"},
        {"origin": "live"},
        {"split": "test"},
        {"completion": "interrupted"},
        {"executed": False},
    ],
)
def test_feedback_bound_to_independent_payload(client, change):
    state, episode, source, feedback = setup_episode(client)
    changed = OutcomeFeedback.model_validate(feedback.model_dump() | change)
    with pytest.raises(store.Refused):
        call(
            client,
            store.accept_feedback,
            episode_id=episode,
            source_event_id=source,
            feedback=changed,
        )
    assert call(client, store.inspect_chain, state)["monitor_samples"] == 0


def test_reward_substitution(client):
    state, episode, source, feedback = setup_episode(client)
    data = feedback.model_dump()
    data["rewards"][0]["value"] = 0.75
    with pytest.raises(store.Refused):
        call(
            client,
            store.accept_feedback,
            episode_id=episode,
            source_event_id=source,
            feedback=OutcomeFeedback.model_validate(data),
        )
    assert call(client, store.inspect_chain, state)["candidate_revision"] == 0


def test_missing_episode_rejection_is_audited_with_safe_correlation(client):
    _, _, source, feedback = setup_episode(client)
    before = call(client, counts)
    with pytest.raises(store.Refused):
        call(
            client,
            store.accept_feedback,
            episode_id="missing",
            source_event_id=source,
            feedback=feedback,
        )
    after = call(client, counts)
    assert after[:3] == before[:3] and after[3] == before[3] + 1


@pytest.mark.parametrize("mode", ["missing", "ambiguous", "model"])
def test_assessment_cannot_manufacture_workflow_or_model_execution(client, mode):
    state, episode, _, _ = setup_episode(client)

    async def probe(kernel):
        async with kernel.db.sessions.begin() as session:
            row = await session.get(Episode, episode)
            stage_id, source_id = row.workflow_stage_id, row.source_event_id
            result = copy.deepcopy(row.snapshot_json["assessment"])
            if mode == "ambiguous":
                stage = await session.get(WorkflowStageRun, stage_id)
                stage.state, stage.uncertainty = "UNKNOWN", "ambiguous_dispatch"
            elif mode == "model":
                result["reasoning"]["invocation"]["provenance"] = "model"
            else:
                stage_id = uid()
        return await store.record_assessment(
            kernel, state_id=state, stage_id=stage_id, source_event_id=source_id, result=result
        )

    with pytest.raises(store.Refused):
        call(client, probe)


def test_untrusted_observer_self_certification(client):
    state, episode, source, feedback = setup_episode(client)

    async def corrupt(kernel):
        async with kernel.db.sessions.begin() as session:
            await session.execute(
                update(Event).where(Event.id == source).values(source="model-opinion")
            )

    call(client, corrupt)
    with pytest.raises(store.Refused):
        call(
            client,
            store.accept_feedback,
            episode_id=episode,
            source_event_id=source,
            feedback=feedback,
        )
    assert call(client, store.inspect_chain, state)["monitor_samples"] == 0


@pytest.mark.parametrize("kind", ["source", "snapshot", "workflow", "goal", "instance"])
def test_identity_substitution_and_cross_instance_reads(client, kind):
    state, episode, _, _ = setup_episode(client)

    async def corrupt(kernel):
        async with kernel.db.sessions.begin() as session:
            row = await session.get(Episode, episode)
            if kind == "source":
                event = await session.scalar(select(Event).where(Event.id == row.source_event_id))
                await session.execute(update(Event).where(Event.id == event.id).values(payload={}))
            elif kind == "snapshot":
                await session.execute(
                    update(Episode).where(Episode.id == row.id).values(snapshot_json={})
                )
            elif kind == "workflow":
                stage = await session.get(WorkflowStageRun, row.workflow_stage_id)
                await session.execute(
                    update(WorkflowStageRun)
                    .where(WorkflowStageRun.id == stage.id)
                    .values(operation="memory.retrieve")
                )
            elif kind == "goal":
                event = await session.scalar(select(Event).where(Event.id == row.source_event_id))
                changed = copy.deepcopy(event.payload)
                changed["context"]["goal_id"] = "other"
                await session.execute(
                    update(Event).where(Event.id == event.id).values(payload=changed)
                )
            else:
                other = Instance(id=uid())
                session.add(other)
                await session.flush()
                return SimpleNamespace(db=kernel.db, instance_id=other.id)

    other_kernel = call(client, corrupt)
    if kind == "instance":

        async def inspect_other(_):
            return await store.inspect_chain(other_kernel, state)

        with pytest.raises(store.Refused):
            call(client, inspect_other)
    else:
        assert client.get("/api/v1/intelligence/states/" + state).status_code == 404


def test_independent_feedback_tracks_frozen_decision_after_proposal_diverges(client):
    state, first, source, feedback = setup_episode(client)
    call(client, store.accept_feedback, episode_id=first, source_event_id=source, feedback=feedback)
    second = call(client, fixture.assessment, state, previous_id=first)
    source2, feedback2 = call(client, fixture.independent_outcome, second)
    assert feedback2.observed_action == "monitor"  # proposal is retrieve, never authorized
    assert (
        call(
            client,
            store.accept_feedback,
            episode_id=second,
            source_event_id=source2,
            feedback=feedback2,
        )
        == "accepted"
    )
    chain = call(client, store.inspect_chain, state)
    assert chain["monitor_samples"] == 2 and chain["retrieve_samples"] == 0
    assert all(e["active_policy_choice"] == "monitor" for e in chain["episodes"])


def test_failed_transaction_rolls_back_learning_and_events(client, monkeypatch):
    state, episode, source, feedback = setup_episode(client)
    before = call(client, counts)
    kernel = client.app.state.kernel
    original = kernel.add_event

    def broken(session, event_type, *args, **kwargs):
        if event_type == "intelligence.learning.updated":
            raise RuntimeError("Injected transaction failure")
        return original(session, event_type, *args, **kwargs)

    monkeypatch.setattr(kernel, "add_event", broken)
    with pytest.raises(RuntimeError):
        call(
            client,
            store.accept_feedback,
            episode_id=episode,
            source_event_id=source,
            feedback=feedback,
        )
    assert call(client, counts) == before
    assert call(client, store.inspect_chain, state)["candidate_revision"] == 0
    monkeypatch.setattr(kernel, "add_event", original)
    assert (
        call(
            client,
            store.accept_feedback,
            episode_id=episode,
            source_event_id=source,
            feedback=feedback,
        )
        == "accepted"
    )
    assert call(client, store.inspect_chain, state)["monitor_samples"] == 1


@pytest.mark.parametrize("change", ["operation", "state", "uncertainty", "context"])
def test_feedback_revalidates_workflow_before_learning(client, change):
    _, episode, source, feedback = setup_episode(client)

    async def corrupt(kernel):
        from alive.workflows.models import WorkflowRun

        async with kernel.db.sessions.begin() as session:
            row = await session.get(Episode, episode)
            stage = await session.get(WorkflowStageRun, row.workflow_stage_id)
            if change == "context":
                await session.execute(
                    update(WorkflowRun)
                    .where(WorkflowRun.id == stage.run_id)
                    .values(input_sha256="0" * 64)
                )
            else:
                values = {
                    "operation": {"operation": "memory.retrieve"},
                    "state": {"state": "COMPLETED"},
                    "uncertainty": {"uncertainty": "ambiguous_dispatch"},
                }[change]
                await session.execute(
                    update(WorkflowStageRun).where(WorkflowStageRun.id == stage.id).values(**values)
                )

    call(client, corrupt)
    before = call(client, counts)
    with pytest.raises(store.Refused):
        call(
            client,
            store.accept_feedback,
            episode_id=episode,
            source_event_id=source,
            feedback=feedback,
        )
    assert call(client, counts)[:3] == before[:3]


def test_cancelled_feedback_transaction_rolls_back(client, monkeypatch):
    state, episode, source, feedback = setup_episode(client)
    before = call(client, counts)
    original = client.app.state.kernel.add_event

    def cancel(session, event_type, *args, **kwargs):
        if event_type == "intelligence.learning.updated":
            raise asyncio.CancelledError()
        return original(session, event_type, *args, **kwargs)

    async def probe(kernel):
        with pytest.raises(asyncio.CancelledError):
            await store.accept_feedback(
                kernel, episode_id=episode, source_event_id=source, feedback=feedback
            )

    monkeypatch.setattr(client.app.state.kernel, "add_event", cancel)
    call(client, probe)
    assert call(client, counts) == before
    assert call(client, store.inspect_chain, state)["candidate_revision"] == 0


def test_conflicting_independent_measurement_versions_refused(client):
    state, episode, source, feedback = setup_episode(client)
    from alive.intelligence.contracts import Evidence

    measurement = feedback.measurements[0]
    altered = Evidence.model_validate(
        measurement.model_dump()
        | {
            "id": "second-measurement",
            "fingerprint": "0" * 64,
        }
    )
    changed = OutcomeFeedback.model_validate(
        feedback.model_dump()
        | {
            "measurements": (measurement, altered),
        }
    )

    async def custody(kernel):
        async with kernel.db.sessions.begin() as session:
            row = await session.scalar(select(Event).where(Event.id == source))
            row.payload = row.payload | {"feedback": changed.model_dump(mode="json")}

    call(client, custody)
    with pytest.raises(store.Refused):
        call(
            client,
            store.accept_feedback,
            episode_id=episode,
            source_event_id=source,
            feedback=changed,
        )
    assert call(client, store.inspect_chain, state)["candidate_revision"] == 0


@pytest.mark.parametrize("rename", [False, True])
def test_measurement_cannot_train_two_decisions_under_new_custody(client, rename):
    from alive.intelligence.contracts import Evidence

    state = call(client, fixture.start)
    first = call(client, fixture.assessment, state)
    second = call(client, fixture.assessment, state, previous_id=first)
    source1, feedback1 = call(client, fixture.independent_outcome, first)
    source2, feedback2 = call(client, fixture.independent_outcome, second)
    call(
        client, store.accept_feedback, episode_id=first, source_event_id=source1, feedback=feedback1
    )
    measurement = Evidence.model_validate(
        feedback1.measurements[0].model_dump() | ({"id": "renamed-observation"} if rename else {})
    )
    payload = feedback2.model_dump() | {"measurements": (measurement,)}
    payload["rewards"][0]["source_ref"] = measurement.id
    altered = OutcomeFeedback.model_validate(payload)

    async def custody(kernel):
        async with kernel.db.sessions.begin() as session:
            row = await session.scalar(select(Event).where(Event.id == source2))
            row.payload = row.payload | {"feedback": altered.model_dump(mode="json")}

    call(client, custody)
    with pytest.raises(store.Refused, match="Concurrent feedback conflict"):
        call(
            client,
            store.accept_feedback,
            episode_id=second,
            source_event_id=source2,
            feedback=altered,
        )
    assert call(client, store.inspect_chain, state)["monitor_samples"] == 1


def test_concurrent_feedback_independent_locks_one_durable_winner(client):
    state, episode, source, feedback = setup_episode(client)

    async def concurrent(kernel):
        workers = [
            SimpleNamespace(
                db=kernel.db,
                instance_id=kernel.instance_id,
                lock=asyncio.Lock(),
                add_event=kernel.add_event,
            )
            for _ in range(2)
        ]
        return await asyncio.gather(
            *(
                store.accept_feedback(
                    k, episode_id=episode, source_event_id=source, feedback=feedback
                )
                for k in workers
            )
        )

    assert sorted(call(client, concurrent)) == ["accepted", "duplicate"]
    assert call(client, store.inspect_chain, state)["monitor_samples"] == 1


def test_withdrawal_correction_and_historical_immutability(client):
    state, episode, source, feedback = setup_episode(client)
    call(
        client, store.accept_feedback, episode_id=episode, source_event_id=source, feedback=feedback
    )

    async def notices(kernel):
        async with kernel.db.sessions.begin() as session:
            row = await session.get(Episode, episode)
            snapshot = copy.deepcopy(row.snapshot_json)
            kernel.add_event(
                session,
                "intelligence.custody.withdrawn",
                {"source_event_id": row.source_event_id},
                source=store.CUSTODIAN,
                correlation=row.id,
            )
            notice = kernel.add_event(
                session,
                "intelligence.fixture.correction",
                {"feedback_id": feedback.id, "status": "revoked"},
                source=store.OBSERVER,
                correlation=row.id,
            )
            return str(notice.event_id), snapshot

    notice, snapshot = call(client, notices)
    assert call(client, store.inspect_chain, state)["episodes"][0]["evidence_status"] == "withdrawn"
    call(client, store.quarantine_feedback, feedback_id=feedback.id, notice_event_id=notice)
    chain = call(client, store.inspect_chain, state)
    assert chain["quarantined"] and chain["monitor_samples"] == 1
    assert chain["episodes"][0]["feedback_status"] == "accepted_historical_quarantined"
    with pytest.raises(store.Refused):
        call(client, fixture.assessment, state, previous_id=episode)

    async def immutable(kernel):
        async with kernel.db.sessions.begin() as session:
            row = await session.get(Episode, episode)
            assert row.snapshot_json == snapshot
            row.previous_id = episode

    with pytest.raises(ImmutableRecord):
        call(client, immutable)


@pytest.mark.parametrize("action", ["monitor", "retrieve"])
def test_shadow_never_overrides_frozen_decision(client, action):
    state, _, _, _ = setup_episode(
        client,
        shadow=ShadowResult(
            status="available", explanation="Controlled shadow fixture", action=action
        ),
    )
    chain = call(client, store.inspect_chain, state)
    assert chain["episodes"][0]["shadow_suggestion"] == action
    assert chain["episodes"][0]["active_policy_choice"] == "monitor"
    assert chain["candidate_revision"] == 0
