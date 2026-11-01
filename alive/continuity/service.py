"""Conversation links and frozen selections over existing events/artifacts, not a memory store."""

import json
import re

from sqlalchemy import select

from alive.admission.models import Admission
from alive.cognitive_models import CognitiveMessage
from alive.continuity.context import MAX_BYTES, MAX_ITEMS, empty_snapshot
from alive.continuity.contracts import PROFILE
from alive.models import Event
from alive.workflows.context import aware, digest, require
from alive.workflows.models import WorkflowRun, WorkflowStageRun
from alive.workflows.runner import result_event

SOURCE = "continuity"
OPENED, SNAPSHOT, LINKED = "conversation.opened", "conversation.snapshot", "conversation.exchange"


async def event(session, kernel, ref, kind):
    row = await session.scalar(select(Event).where(Event.id == ref))
    require(
        row is not None
        and row.instance_id == kernel.instance_id
        and row.source == SOURCE
        and row.event_type == kind,
        "conversation_unavailable",
    )
    return row


async def conversation(session, kernel, ref, consent):
    row = await event(session, kernel, ref, OPENED)
    require(
        row.payload["principal"] == consent["terms"]["principal"]
        and row.payload["consent_ref"] == consent["id"]
        and row.payload["resources"]
        == consent["terms"]["profiles"][PROFILE]["source"]["resources"],
        "conversation_owner_or_scope_changed",
    )
    return row


async def create(kernel, consent_ref, title):
    from alive.admission import live

    async with kernel.lock, kernel.db.sessions.begin() as session:
        approved = await live.consent(session, kernel, consent_ref)
        require(
            PROFILE in approved["terms"]["profiles"], "contextual_session_configuration_required"
        )
        row = kernel.add_event(
            session,
            OPENED,
            {
                "principal": approved["terms"]["principal"],
                "consent_ref": consent_ref,
                "resources": approved["terms"]["profiles"][PROFILE]["source"]["resources"],
                "title": title,
            },
            source=SOURCE,
        )
        await session.flush()
        return {"id": str(row.event_id), "title": title, "consent_ref": consent_ref}


async def artifact(session, kernel, row):
    from alive.admission.service import row_for

    await row_for(session, kernel, row.id)
    run = await session.get(WorkflowRun, row.run_id) if row.run_id else None
    if run is None or run.status != "COMPLETED":
        return None
    stage = await session.scalar(
        select(WorkflowStageRun).where(
            WorkflowStageRun.run_id == run.id,
            WorkflowStageRun.stage_id == "record",
        )
    )
    if stage is None:
        return None
    output = await result_event(session, stage)
    message = await session.get(CognitiveMessage, stage.id)
    require(
        message is not None
        and message.investigation_id == run.investigation_id
        and digest(message.content) == output["sha256"],
        "conversation_artifact_integrity",
    )
    return {"sha256": output["sha256"], **message.content}


async def items_for(session, kernel, row):
    """Projection only: no retrieval from unrelated Memory, history imports or other sources."""
    items = []

    def add(suffix, kind, content, source_sha, ordinal=None):
        items.append(
            {
                "id": row.id + ":" + suffix,
                "admission_id": row.id,
                "source_type": kind,
                "content": content,
                "content_sha256": digest(content),
                "source_sha256": source_sha,
                "recorded_at": aware(row.created_at).isoformat(),
                "ordinal": ordinal,
                "verification": "owner_statement"
                if kind == "owner_goal"
                else "unverified_model_assessment",
            }
        )

    add("goal", "owner_goal", row.terms["objective"]["requested_outcome"], row.review_sha256)
    stored = await artifact(session, kernel, row)
    if stored:
        result = stored["result"]
        if row.terms.get("profile") == PROFILE:
            add(
                "answer",
                "model_answer",
                {
                    k: result[k]
                    for k in ("answer", "revision", "citations", "recalled_item_ids", "uncertainty")
                },
                stored["sha256"],
            )
        elif "findings" in result:
            for index, finding in enumerate(result["findings"], 1):
                add(finding["finding_id"], "model_finding", finding, stored["sha256"], index)
    from alive.adaptation.service import feedback_items

    items.extend(await feedback_items(session, kernel, row.id))
    return items


async def links(session, kernel, ref):
    return (
        await session.scalars(
            select(Event)
            .where(
                Event.instance_id == kernel.instance_id,
                Event.source == SOURCE,
                Event.event_type == LINKED,
                Event.correlation_id == ref,
            )
            .order_by(Event.sequence_number)
        )
    ).all()


async def frozen(
    session, kernel, ref, resources, principal, consent_ref=None, *, for_dispatch=False
):
    if not ref:
        return empty_snapshot()  # initial configuration exemplar, never a dispatch input
    row = await event(session, kernel, ref, SNAPSHOT)
    payload = row.payload
    require(digest(payload["snapshot"]) == payload["sha256"], "context_snapshot_integrity")
    opened = await event(session, kernel, payload["snapshot"]["conversation_ref"], OPENED)
    require(
        opened.payload["resources"] == resources
        and opened.payload["principal"] == principal
        and (consent_ref is None or opened.payload["consent_ref"] == consent_ref),
        "context_owner_or_source_changed",
    )
    permitted = {e.payload["admission_id"] for e in await links(session, kernel, opened.id)}
    for item in payload["snapshot"]["items"]:
        if item["source_type"] in ("learned_strategy", "historical_experience"):
            from alive.adaptation.service import verify_item
            from alive.admission.live import consent

            approved = await consent(
                session, kernel, opened.payload["consent_ref"], active=for_dispatch
            )
            terms = approved["terms"]
            require(terms.get("adaptive"), "adaptive_consent_required")
            destination = terms["profiles"][PROFILE]["disclosure"]["destination"]
            await verify_item(
                session, kernel, item, principal, destination, for_dispatch=for_dispatch
            )
            continue
        require(item["admission_id"] in permitted, "context_not_in_conversation")
        parent = await session.get(Admission, item["admission_id"])
        require(
            parent is not None
            and parent.instance_id == kernel.instance_id
            and parent.principal == principal
            and parent.terms["source"]["resources"] == resources,
            "context_item_scope",
        )
        candidates = await items_for(session, kernel, parent)
        require(item in candidates, "context_item_changed")
    return payload["snapshot"]


async def adaptive_snapshot(kernel, request, approved, families):
    """Freeze a cross-conversation selection after live intent classification, once only."""
    from alive.adaptation.service import selected

    async with kernel.lock, kernel.db.sessions.begin() as session:
        opened = await conversation(session, kernel, request.conversation_ref, approved)
        key = request.idempotency_key + ":adaptation"
        previous = await session.scalar(
            select(Event).where(
                Event.instance_id == kernel.instance_id,
                Event.source == SOURCE,
                Event.event_type == SNAPSHOT,
                Event.correlation_id == opened.id,
                Event.payload["request_key"].as_string() == key,
            )
        )
        if previous:
            require(
                previous.payload["goal"] == request.goal
                and previous.payload["mode"] == request.strategy_mode,
                "adaptation_retry_conflict",
            )
            return previous.id
        destination = approved["terms"]["profiles"][PROFILE]["disclosure"]["destination"]
        items = await selected(
            session,
            kernel,
            opened.payload["principal"],
            destination,
            families,
            request.strategy_mode,
        )
        snapshot = empty_snapshot() | {
            "conversation_ref": opened.id,
            "items": items,
            "selection": "live intent families; bounded owner-approved exports",
            "strategy_mode": request.strategy_mode,
            "families": families,
        }
        require(len(json.dumps(snapshot).encode()) <= MAX_BYTES, "adaptation_context_budget")
        row = kernel.add_event(
            session,
            SNAPSHOT,
            {
                "request_key": key,
                "goal": request.goal,
                "snapshot": snapshot,
                "sha256": digest(snapshot),
                "continuation": False,
                "mode": request.strategy_mode,
            },
            source=SOURCE,
            correlation=opened.id,
        )
        await session.flush()
        return str(row.event_id)


async def prepare_turn(kernel, request, approved):
    """Select once per request. Recency is a candidate window; the model resolves relevance."""
    async with kernel.lock, kernel.db.sessions.begin() as session:
        opened = await conversation(session, kernel, request.conversation_ref, approved)
        previous = await session.scalar(
            select(Event).where(
                Event.instance_id == kernel.instance_id,
                Event.source == SOURCE,
                Event.event_type == SNAPSHOT,
                Event.correlation_id == opened.id,
                Event.payload["request_key"].as_string() == request.idempotency_key,
            )
        )
        if previous:
            require(previous.payload["goal"] == request.goal, "conversation_retry_conflict")
            await frozen(
                session,
                kernel,
                previous.id,
                opened.payload["resources"],
                opened.payload["principal"],
                approved["id"],
            )
            return previous.id, previous.payload["continuation"]
        history = await links(session, kernel, opened.id)
        candidates = []
        explicit_parents = set(
            re.findall(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", request.goal)
        )
        window = {e.id for e in history[-20:] + history[:2]}
        for link in history:
            if link.id not in window and link.payload["admission_id"] not in explicit_parents:
                continue
            parent = await session.get(Admission, link.payload["admission_id"])
            require(
                parent is not None
                and parent.instance_id == kernel.instance_id
                and parent.principal == opened.payload["principal"]
                and parent.terms["source"]["resources"] == opened.payload["resources"],
                "conversation_history_scope",
            )
            candidates.extend(await items_for(session, kernel, parent))

        revisions = [
            i for i in candidates if i["source_type"] == "model_answer" and i["content"]["revision"]
        ]
        latest_revision = revisions[-1]["id"] if revisions else None

        # Explicit IDs first, then the current revision, findings and recent turn context.
        def priority(item):
            suffix = item["id"].split(":")[-1]
            explicit = item["id"] in request.goal or (
                suffix not in ("goal", "answer") and suffix in request.goal
            )
            revised = item["id"] == latest_revision
            return (bool(explicit), bool(revised), item["source_type"] == "model_finding")

        ordered = sorted(reversed(candidates), key=priority, reverse=True)
        snapshot = empty_snapshot() | {"conversation_ref": opened.id}
        for item in ordered:
            proposed = snapshot | {"items": snapshot["items"] + [item]}
            if (
                len(snapshot["items"]) < MAX_ITEMS
                and len(json.dumps(proposed, ensure_ascii=False).encode()) <= MAX_BYTES - 1400
            ):
                snapshot["items"].append(item)
            else:
                snapshot["omitted"].append({"id": item["id"], "reason": "context_budget"})
        # Omission inventory is itself bounded; never silently drop essential explicit references.
        selected_ids = {i["id"] for i in snapshot["items"]}
        require(
            not revisions or revisions[-1]["id"] in selected_ids, "essential_context_does_not_fit"
        )
        require(
            not any(i["id"] in request.goal and i["id"] not in selected_ids for i in candidates),
            "essential_context_does_not_fit",
        )
        snapshot["omitted_count"] = len(snapshot["omitted"])
        snapshot["omitted"] = snapshot["omitted"][:8]
        snapshot["selection"] = (
            "explicit identifiers, revisions, findings and recent turns; model resolves relevance"
        )
        require(not candidates or snapshot["items"], "essential_context_does_not_fit")
        row = kernel.add_event(
            session,
            SNAPSHOT,
            {
                "request_key": request.idempotency_key,
                "goal": request.goal,
                "snapshot": snapshot,
                "sha256": digest(snapshot),
                "continuation": bool(history),
            },
            source=SOURCE,
            correlation=opened.id,
        )
        await session.flush()
        return str(row.event_id), bool(history)


async def link(kernel, conversation_ref, admission_id):
    async with kernel.lock, kernel.db.sessions.begin() as session:
        existing = await links(session, kernel, conversation_ref)
        if not any(e.payload["admission_id"] == admission_id for e in existing):
            kernel.add_event(
                session,
                LINKED,
                {"admission_id": admission_id},
                source=SOURCE,
                correlation=conversation_ref,
            )


async def listing(kernel):
    async with kernel.db.sessions() as session:
        opened = (
            await session.scalars(
                select(Event)
                .where(
                    Event.instance_id == kernel.instance_id,
                    Event.source == SOURCE,
                    Event.event_type == OPENED,
                )
                .order_by(Event.sequence_number.desc())
                .limit(30)
            )
        ).all()
        return [
            {
                "id": row.id,
                "title": row.payload["title"],
                "consent_ref": row.payload["consent_ref"],
                "admission_ids": [
                    e.payload["admission_id"] for e in await links(session, kernel, row.id)
                ],
            }
            for row in opened
        ]
