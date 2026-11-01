"""Small event-backed lesson projection. Evidence stays in existing admission artifacts.

The only writer of oracle measurements is the owner-local frozen-fixture evaluator.
There is intentionally no HTTP endpoint accepting a client's ``verified`` assertion.
"""

import json
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select

from alive.adaptation.contracts import LessonProposal
from alive.admission.models import Admission
from alive.cognitive_models import ModelInvocation
from alive.continuity import service as continuity
from alive.models import Event
from alive.workflows.context import digest, require

SOURCE = "adaptation"
ORACLE = "adaptation-fixture-oracle"
MEASURED = "adaptation.measurement"
EXPERIENCE = "adaptation.experience"
LESSON = "adaptation.lesson"


async def rows(session, kernel, kind, source=SOURCE):
    return list(
        await session.scalars(
            select(Event)
            .where(
                Event.instance_id == kernel.instance_id,
                Event.source == source,
                Event.event_type == kind,
            )
            .order_by(Event.sequence_number)
        )
    )


async def put(session, kernel, kind, key, payload, *, source=SOURCE):
    ref = str(uuid5(NAMESPACE_URL, f"{kernel.instance_id}:{source}:{kind}:{key}"))
    old = await session.scalar(select(Event).where(Event.id == ref))
    body = {"value": payload, "sha256": digest(payload)}
    if old:
        require(
            old.source == source and old.event_type == kind and old.payload == body,
            "adaptation_idempotency_conflict",
        )
    else:
        kernel.add_event(session, kind, body, source=source, event_id=ref)
        await session.flush()  # unique Event.id also fences concurrent owner processes
    return ref


def value(row):
    require(
        row is not None and digest(row.payload["value"]) == row.payload["sha256"],
        "adaptation_integrity",
    )
    return row.payload["value"]


async def experience(kernel, admission_id, measurement_ref, feedback_key):
    """Consume a trusted measurement, never a model or owner self-rating."""
    from alive.admission.service import row_for

    async with kernel.lock, kernel.db.sessions.begin() as session:
        admission = await row_for(session, kernel, admission_id)
        measured = await session.scalar(select(Event).where(Event.id == measurement_ref))
        require(
            measured is not None
            and measured.instance_id == kernel.instance_id
            and measured.source == ORACLE
            and measured.event_type == MEASURED,
            "independent_measurement_required",
        )
        outcome = value(measured)
        artifact = await continuity.artifact(session, kernel, admission)
        require(
            artifact is not None
            and outcome["admission_id"] == admission_id
            and outcome["artifact_sha256"] == artifact["sha256"]
            and outcome["source_sha256"] == digest(admission.terms["source"]),
            "measurement_binding_changed",
        )
        calls = list(
            await session.scalars(
                select(ModelInvocation).where(
                    ModelInvocation.investigation_id
                    == admission.terms["proposed_grant_data"]["investigation_id"]
                )
            )
        )
        require(
            bool(calls) and all(c.status == "validated" for c in calls),
            "validated_model_result_required",
        )
        body = {
            "admission_id": admission_id,
            "principal": admission.principal,
            "source": admission.terms["source"],
            "artifact_sha256": artifact["sha256"],
            "measurement_ref": measurement_ref,
            "measurement_sha256": measured.payload["sha256"],
            "task_id": outcome["task_id"],
            "split": outcome["split"],
            "family": outcome["family"],
            "outcome": outcome["score"],
            "passed": outcome["passed"],
            "verifier": outcome["verifier"],
            "prose_verified": False,
            "calls": [
                {
                    "id": c.id,
                    "provider": c.provider,
                    "model": c.model,
                    "role": c.role,
                    "usage": c.usage,
                }
                for c in calls
            ],
            "destination": admission.terms["model_disclosure"]["destination"],
        }
        await put(
            session,
            kernel,
            "adaptation.feedback.key",
            feedback_key,
            {"measurement_ref": measurement_ref},
        )
        return await put(session, kernel, EXPERIENCE, measurement_ref, body)


async def capture_proposal(kernel, admission_id):
    """Called after a completed write path, never by history/read projections."""
    async with kernel.lock, kernel.db.sessions.begin() as session:
        admission = await session.get(Admission, admission_id)
        artifact = await continuity.artifact(session, kernel, admission)
        proposed = artifact and artifact["result"].get("lesson_proposal")
        if not proposed:
            return None
        proposal = LessonProposal.model_validate(proposed).model_dump(mode="json")
        context_ref = admission.terms["proposed_grant_data"]["inputs"]["context_ref"]
        snapshot = await continuity.frozen(
            session,
            kernel,
            context_ref,
            admission.terms["source"]["resources"],
            admission.principal,
        )
        supplied = {i["id"] for i in snapshot["items"] if i["source_type"] == "verified_feedback"}

        async def reject(reason):
            await put(
                session,
                kernel,
                "adaptation.proposal.rejected",
                admission_id,
                {"admission_id": admission_id, "reason": reason},
            )
            return None

        if not set(proposal["supporting_experience_ids"]) <= supplied:
            return await reject("lesson_evidence_not_supplied")
        for ref in proposal["supporting_experience_ids"]:
            row = await session.scalar(select(Event).where(Event.id == ref))
            evidence = value(row)
            if not (
                row.source == SOURCE
                and row.event_type == EXPERIENCE
                and evidence["split"] == "train"
                and evidence["family"] == proposal["family"]
                and evidence["principal"] == admission.principal
            ):
                return await reject("training_evidence_required")
        first = value(
            await session.scalar(
                select(Event).where(Event.id == proposal["supporting_experience_ids"][0])
            )
        )
        previous = await session.get(Admission, first["admission_id"])
        previous_artifact = await continuity.artifact(session, kernel, previous)
        history = {
            "family": first["family"],
            "prior_assessment": previous_artifact["result"]["answer"][:600],
            "past_score": first["outcome"],
            "past_passed": first["passed"],
            "prose_verified": False,
        }
        body = {
            "history_export": history,
            "lesson_id": admission_id,
            "version": 1,
            "state": "proposed",
            "proposal": proposal,
            "origin_admission": admission_id,
            "origin_artifact_sha256": artifact["sha256"],
            "principal": admission.principal,
            "destination": admission.terms["model_disclosure"]["destination"],
            "source": admission.terms["source"],
            "previous_sha256": None,
            "qualification": "provisional; one observation is not general validity",
            "export": None,
        }
        await put(session, kernel, LESSON, f"{admission_id}:1", body)
        return admission_id


async def latest(session, kernel):
    state = {}
    for row in await rows(session, kernel, LESSON):
        body = value(row)
        prior = state.get(body["lesson_id"])
        require(
            body["version"] == (value(prior)["version"] + 1 if prior else 1)
            and body["previous_sha256"] == (prior.payload["sha256"] if prior else None),
            "lesson_version_chain_changed",
        )
        state[body["lesson_id"]] = row
    return state


def export_text(body):
    # Exact model-derived text is reviewable before owner approval; never export source bytes.
    return {
        "strategy": {
            k: body["proposal"][k]
            for k in ("family", "strategy", "applies_when", "not_when", "uncertainty")
        },
        "history": body["history_export"],
    }


async def transition(
    kernel,
    lesson_id,
    *,
    state,
    expected_sha256,
    principal,
    export_sha256=None,
    counterevidence_ref=None,
):
    """Explicit owner-local qualification/export or independently evidenced demotion."""
    async with kernel.lock, kernel.db.sessions.begin() as session:
        current = (await latest(session, kernel)).get(lesson_id)
        body = value(current)
        require(body["principal"] == principal, "lesson_owner_required")
        if current.payload["sha256"] != expected_sha256:
            require(
                body["state"] == state and body["previous_sha256"] == expected_sha256,
                "lesson_version_conflict",
            )
            return current.id
        allowed = {
            "proposed": {"qualified", "rejected"},
            "qualified": {"active", "rejected"},
            "active": {"revised", "rejected"},
            "revised": {"qualified", "rejected"},
            "rejected": set(),
        }
        require(state in allowed[body["state"]], "lesson_transition_invalid")
        export = body["export"]
        if state in ("qualified", "active"):
            candidate = export_text(body)
            require(
                export_sha256 == digest(candidate) and len(json.dumps(candidate).encode()) <= 2600,
                "exact_bounded_owner_export_required",
            )
            export = candidate
        if body["state"] == "active":
            evidence = await session.scalar(select(Event).where(Event.id == counterevidence_ref))
            counter = value(evidence)
            require(
                evidence.source == SOURCE
                and evidence.event_type == EXPERIENCE
                and counter["split"] in ("train", "dev")
                and counter["family"] == body["proposal"]["family"]
                and counter["principal"] == principal
                and not counter["passed"],
                "verified_counterevidence_required",
            )
        updated = body | {
            "version": body["version"] + 1,
            "state": state,
            "export": export,
            "previous_sha256": current.payload["sha256"],
            "counterevidence_ref": counterevidence_ref,
        }
        return await put(session, kernel, LESSON, f"{lesson_id}:{updated['version']}", updated)


def item(row, kind, content):
    return {
        "id": row.id,
        "admission_id": value(row).get("admission_id", value(row).get("origin_admission")),
        "source_type": kind,
        "content": content,
        "content_sha256": digest(content),
        "source_sha256": row.payload["sha256"],
        "recorded_at": row.occurred_at.isoformat(),
        "ordinal": None,
        "verification": "executable_fixture_outcome; prose_unverified"
        if kind == "verified_feedback"
        else "owner_approved_provisional_strategy",
    }


async def feedback_items(session, kernel, admission_id):
    return [
        item(
            row,
            "verified_feedback",
            {
                "experience_id": row.id,
                **{
                    k: value(row)[k]
                    for k in ("task_id", "split", "family", "outcome", "passed", "verifier")
                },
            },
        )
        for row in await rows(session, kernel, EXPERIENCE)
        if value(row)["admission_id"] == admission_id
    ]


async def selected(session, kernel, principal, destination, families, mode):
    if mode == "stateless":
        return []
    chosen = []
    for row in reversed(list((await latest(session, kernel)).values())):
        body = value(row)
        if (
            body["state"] != "active"
            or not body["export"]
            or body["principal"] != principal
            or body["destination"] != destination
            or body["proposal"]["family"] not in families
        ):
            continue
        if any(i["content"]["family"] == body["proposal"]["family"] for i in chosen):
            continue
        if mode == "learned":
            content = body["export"]["strategy"] | {
                "lesson_id": row.id,
                "version": body["version"],
                "qualification": body["qualification"],
            }
            chosen.append(item(row, "learned_strategy", content))
        else:
            # B gets owner-approved past assessment/outcome, never the learned strategy.
            chosen.append(item(row, "historical_experience", body["export"]["history"]))
        if len(chosen) == 2:
            break
    return chosen


async def verify_item(session, kernel, supplied, principal, destination, *, for_dispatch=False):
    row = await session.scalar(select(Event).where(Event.id == supplied["id"]))
    require(
        row is not None and row.instance_id == kernel.instance_id and row.source == SOURCE,
        "adaptation_item_scope",
    )
    body = value(row)
    if supplied["source_type"] == "verified_feedback":
        require(
            row.event_type == EXPERIENCE and body["principal"] == principal,
            "feedback_owner_changed",
        )
        candidates = await feedback_items(session, kernel, body["admission_id"])
        require(supplied in candidates, "adaptation_item_changed")
        return
    require(
        row.event_type == LESSON
        and body["state"] == "active"
        and body["export"]
        and body["principal"] == principal
        and body["destination"] == destination,
        "lesson_export_scope_changed",
    )
    if for_dispatch:
        require(
            (await latest(session, kernel))[body["lesson_id"]].id == row.id,
            "lesson_no_longer_active",
        )
    if supplied["source_type"] == "learned_strategy":
        content = body["export"]["strategy"] | {
            "lesson_id": row.id,
            "version": body["version"],
            "qualification": body["qualification"],
        }
    else:
        require(supplied["source_type"] == "historical_experience", "adaptation_kind_invalid")
        content = body["export"]["history"]
    require(supplied == item(row, supplied["source_type"], content), "adaptation_item_changed")


async def listing(kernel):
    async with kernel.db.sessions() as session:
        return {
            "experiences": [
                {"id": r.id, **value(r)} for r in await rows(session, kernel, EXPERIENCE)
            ],
            "lessons": [
                {"id": r.id, "sha256": r.payload["sha256"], **value(r)}
                for r in (await latest(session, kernel)).values()
            ],
        }
