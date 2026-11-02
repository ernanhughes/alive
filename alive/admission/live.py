"""Ask ALIVE: standing consent over existing closed, read-only admission profiles.

Events retain consent and conservative reservations. Each call still has an exact Grant,
source approval, Governor budget and Pi dispatch fence. No provider or runner lives here.
"""

import re
from datetime import datetime, timedelta

from sqlalchemy import select

from alive.admission import service
from alive.admission.contracts import ReviewRequest
from alive.admission.models import Admission
from alive.admission.profiles import (
    ANALYSIS,
    CODE_REPAIR,
    CODE_REVIEW,
    CONTEXT_PROFILES,
    CONTEXTUAL,
    INSPECTION,
    INTENT,
)
from alive.bespoke.recipes import recipe_hash
from alive.cognitive_models import ModelInvocation
from alive.intent import service as intent
from alive.models import Event, now
from alive.pi.models import PiProviderRequest, PiRun
from alive.research.contracts import ROLE as RESEARCH_ROLE
from alive.research.contracts import role_contract as research_role_contract
from alive.workflows.context import Refused, digest, require
from alive.workflows.models import WorkflowStageRun
from alive.workflows.runner import result_event

PREPARED = "admission.standing.prepared"
APPROVED = "admission.standing.approved"
REVOKED = "admission.standing.revoked"
FOLLOWUP_BLOCKED = "admission.live.followup.blocked"
FOLLOWUP_FAILED = "admission.live.followup.failed"
AUTHORIZATION_REFUSALS = {
    "standing_budget_exhausted": "budget_exhausted",
    "governor_budget_exhausted": "budget_exhausted",
    "standing_consent_required_expired_or_revoked": "consent_required",
    "admission_expired_or_revoked": "consent_required",
    "authorization_expired_or_revoked": "consent_required",
    "source_withdrawn": "consent_required",
    "source_approval_expired": "consent_required",
    "source_operation_not_approved": "consent_required",
}


async def followup_outcome(session, kernel, admission_id):
    return await session.scalar(
        select(Event)
        .where(
            Event.instance_id == kernel.instance_id,
            Event.source == "admission",
            Event.event_type.in_((FOLLOWUP_BLOCKED, FOLLOWUP_FAILED)),
            Event.correlation_id == admission_id,
        )
        .order_by(Event.sequence_number)
        .limit(1)
    )


async def retain_blocked_followup(kernel, admission_id, profile, error):
    await retain_followup(
        kernel,
        admission_id,
        profile,
        FOLLOWUP_BLOCKED,
        "analysis_not_authorized",
        AUTHORIZATION_REFUSALS[str(error)],
    )


async def retain_failed_followup(kernel, admission_id, profile, error):
    # Refused categories are code-owned identifiers, not arbitrary exception text.
    category = str(error)
    reason = category if re.fullmatch(r"[a-z][a-z0-9_]{0,119}", category) else "internal_failure"
    await retain_followup(kernel, admission_id, profile, FOLLOWUP_FAILED, "followup_failed", reason)


async def retain_followup(kernel, admission_id, profile, event_type, status, reason):
    # Retain intent and the actual outcome; replay is never implicit permission to redispatch.
    async with kernel.lock, kernel.db.sessions.begin() as session:
        if await followup_outcome(session, kernel, admission_id) is None:
            kernel.add_event(
                session,
                event_type,
                {
                    "status": status,
                    "reason": reason,
                    "profile": profile,
                },
                source="admission",
                correlation=admission_id,
            )


def scope(terms):
    """Pin authority and disclosure, allowing only the owner's words to vary."""
    grant = terms["proposed_grant_data"]
    disclosure = terms.get("model_disclosure", {})
    return {
        "profile": service.profile_of(terms).id,
        "source": terms["source"],
        "grant": {
            k: v
            for k, v in grant.items()
            if k
            not in {
                "goal_id",
                "investigation_id",
                "context_event_id",
                "context_sha256",
                "admission_ref",
                "inputs",
                "expires_at",
                "idempotency_key",
            }
        },
        "inputs": {
            k: v
            for k, v in grant["inputs"].items()
            if k not in ("objective", "context_ref", "context_sha256", "model_input_sha256")
        },
        "disclosure": {
            k: v
            for k, v in disclosure.items()
            if k
            not in {
                "goal_characters",
                "reserved_request_bytes",
                "context_sha256",
                "context_bytes",
                "conversation_ref",
                "model_input_sha256",
            }
        },
        "recipe_sha256": terms["candidate"]["recipe_sha256"],
    }


async def event_for(session, kernel, ref, kind):
    event = await session.scalar(select(Event).where(Event.id == ref))
    require(
        event is not None
        and event.instance_id == kernel.instance_id
        and event.source == service.OWNER_SOURCE
        and event.event_type == kind,
        "standing_consent_required",
    )
    return event


async def consent(session, kernel, ref, *, active=True):
    event = await event_for(session, kernel, ref, PREPARED)
    payload = event.payload
    require(digest(payload["terms"]) == payload["sha256"], "standing_consent_integrity")
    approvals = (
        await session.scalars(
            select(Event).where(
                Event.instance_id == kernel.instance_id,
                Event.source == service.OWNER_SOURCE,
                Event.correlation_id == ref,
                Event.event_type.in_([APPROVED, REVOKED]),
            )
        )
    ).all()
    approved = any(
        e.event_type == APPROVED
        and e.payload
        == {
            "consent_ref": ref,
            "sha256": payload["sha256"],
            "principal": payload["terms"]["principal"],
        }
        for e in approvals
    )
    revoked = any(e.event_type == REVOKED for e in approvals)
    expired = datetime.fromisoformat(payload["terms"]["expires_at"]) <= now()
    state = (
        "revoked" if revoked else "expired" if expired else "approved" if approved else "pending"
    )
    if active:
        require(state == "approved", "standing_consent_required_expired_or_revoked")
    return {"id": ref, **payload, "state": state}


async def prepare(kernel, request):
    reviews = {}
    profiles = (
        (INTENT, ANALYSIS, INSPECTION, CONTEXTUAL)
        if request.contextual or request.adaptive or request.code_review or request.research
        else (INTENT, ANALYSIS, INSPECTION)
    )
    require(
        not request.completion_repair or request.code_review, "task_profile_required_for_repair"
    )
    require(
        not request.research or request.contextual,
        "research_requires_contextual_source",
    )
    if request.code_review:
        profiles += (CODE_REVIEW,)
    if request.completion_repair:
        profiles += (CODE_REPAIR,)
    for profile in profiles:
        reviews[profile] = await service.prepare(
            kernel,
            ReviewRequest(
                profile=profile,
                goal_ref=request.goal_ref,
                approval_ref=request.approval_ref,
                recipe_sha256=recipe_hash(service.recipe_for(kernel, profile)),
                objective={
                    "kind": "inspect_implementation",
                    "requested_outcome": "Review approved work",
                },
                paths=request.paths,
                idempotency_key="setup:" + service.uid(),
            ),
        )
    async with kernel.lock, kernel.db.sessions.begin() as session:
        rows = [await service.row_for(session, kernel, r["id"]) for r in reviews.values()]
        for row in rows:
            await service.current_terms(session, kernel, row)
        terms = {
            "principal": rows[0].principal,
            "goal_ref": request.goal_ref,
            "approval_ref": request.approval_ref,
            "paths": sorted(request.paths),
            "profiles": {k: scope(r["terms"]) for k, r in reviews.items()},
            "max_calls": request.max_calls,
            "max_tokens": request.max_tokens,
            "expires_at": min(
                now() + timedelta(seconds=request.ttl_seconds),
                datetime.fromisoformat(rows[0].terms["source"]["expires_at"]),
            ).isoformat(),
            "disclosure": "Future goal text, file names and approved file content may leave this "
            "host. Local prompts/results persist. Read-only inspection/analysis is automatic. "
            "Reservations stay charged after failures; currency cost is unknown.",
        }
        if request.code_review:
            terms["code_review"] = True
            terms["completion_repair"] = request.completion_repair
            terms["disclosure"] += (
                " Opt-in code-review task contracts retain incomplete candidates."
            )
        if request.completion_repair:
            require(
                reviews[CODE_REVIEW]["terms"]["model_disclosure"]["destination"]
                == reviews[CODE_REPAIR]["terms"]["model_disclosure"]["destination"],
                "repair_requires_same_model_destination",
            )
            terms["disclosure"] += (
                " One requested repair may send the original candidate and omissions to the same "
                "model, charged as a separate call."
            )
        if request.adaptive:
            terms["adaptive"] = True
            terms["disclosure"] += (
                " Adaptive reasoning may reuse up to two bounded, explicitly owner-approved "
                "lesson exports from other conversations at this same provider/model. Raw prior "
                "source is not exported. Lessons remain fallible data, not execution authority."
            )
        if request.contextual or request.code_review:
            terms["disclosure"] += (
                " In a linked conversation, bounded prior owner statements, model findings and "
                "revisions from this exact source may also be disclosed to the same destination."
            )
        if request.research:
            destination = dict(reviews[CONTEXTUAL]["terms"]["model_disclosure"]["destination"])
            destination["model"] = kernel.settings.alive_role_models.get(
                RESEARCH_ROLE, kernel.settings.alive_meta_model
            )
            # The research tools read the same captured source the contextual profile approved.
            terms["source"] = reviews[CONTEXTUAL]["terms"]["source"]
            terms["research"] = {
                "role": RESEARCH_ROLE,
                "role_contract_sha256": research_role_contract(),
                "model": destination["model"],
                "destination": destination,
                "paths": sorted(request.paths),
                "max_model_calls": min(4, request.max_calls),
                "max_output_tokens": min(
                    1536,
                    reviews[CONTEXTUAL]["terms"]["model_disclosure"]["max_output_tokens"],
                ),
                "max_steps": 4,
                "max_tokens": request.max_tokens,
            }
            terms["disclosure"] += (
                " The research loop may make up to four model decisions and read only the "
                "approved captured corpus; it cannot fetch the web or write files."
            )
        event = kernel.add_event(
            session,
            PREPARED,
            {"terms": terms, "sha256": digest(terms)},
            source=service.OWNER_SOURCE,
        )
        await session.flush()
        return await consent(session, kernel, str(event.event_id), active=False)


async def approve(kernel, ref, *, confirm_sha256, principal):
    async with kernel.lock, kernel.db.sessions.begin() as session:
        current = await consent(session, kernel, ref, active=False)
        require(
            current["state"] in ("pending", "approved")
            and current["sha256"] == confirm_sha256
            and current["terms"]["principal"] == principal,
            "exact_local_owner_confirmation_required",
        )
        kernel.add_event(
            session,
            APPROVED,
            {
                "consent_ref": ref,
                "sha256": confirm_sha256,
                "principal": principal,
            },
            source=service.OWNER_SOURCE,
            correlation=ref,
        )
        await session.flush()
        return await consent(session, kernel, ref)


async def revoke(kernel, ref, *, principal):
    async with kernel.lock, kernel.db.sessions.begin() as session:
        current = await consent(session, kernel, ref, active=False)
        require(current["terms"]["principal"] == principal, "local_owner_required")
        kernel.add_event(
            session,
            REVOKED,
            {"consent_ref": ref, "principal": principal},
            source=service.OWNER_SOURCE,
            correlation=ref,
        )


async def validate_receipt(session, kernel, row, receipt):
    current = await consent(session, kernel, receipt["standing_ref"])
    terms = current["terms"]
    require(
        row.principal == terms["principal"]
        and row.terms["goal"]["id"] == terms["goal_ref"]
        and scope(row.terms) == terms["profiles"].get(service.profile_of(row.terms).id),
        "standing_scope_changed",
    )
    if service.profile_of(row.terms).id in CONTEXT_PROFILES:
        from alive.continuity.service import frozen

        grant = row.terms["proposed_grant_data"]
        require(bool(grant["inputs"]["context_ref"]), "frozen_context_required")
        snapshot = await frozen(
            session,
            kernel,
            grant["inputs"]["context_ref"],
            row.terms["source"]["resources"],
            row.principal,
            consent_ref=current["id"],
            for_dispatch=True,
        )
        require(digest(snapshot) == grant["inputs"]["context_sha256"], "context_snapshot_integrity")


async def authorize(kernel, ref, review):
    async with kernel.lock, kernel.db.sessions.begin() as session:
        row = await service.row_for(session, kernel, review["id"], lock=True)
        if row.approval_ref:
            await service.approval_receipt(session, row, kernel)
            return
        receipt = {
            "admission_id": row.id,
            "review_sha256": row.review_sha256,
            "principal": row.principal,
            "standing_ref": ref,
        }
        await validate_receipt(session, kernel, row, receipt)
        await service.current_terms(session, kernel, row)
        current = await consent(session, kernel, ref)
        previous = (
            await session.scalars(
                select(Event).where(
                    Event.instance_id == kernel.instance_id,
                    Event.source == service.OWNER_SOURCE,
                    Event.event_type == "admission.owner.approved",
                )
            )
        ).all()
        used = [e for e in previous if e.payload.get("standing_ref") == ref]
        reservation = row.terms.get("model_disclosure", {}).get("reserved_request_bytes", 0)
        require(
            sum(e.payload["reserved_tokens"] > 0 for e in used) + (reservation > 0)
            <= current["terms"]["max_calls"]
            and sum(e.payload["reserved_tokens"] for e in used) + reservation
            <= current["terms"]["max_tokens"],
            "standing_budget_exhausted",
        )
        receipt["reserved_tokens"] = reservation
        event = kernel.add_event(
            session,
            "admission.owner.approved",
            receipt,
            source=service.OWNER_SOURCE,
            correlation=row.id,
        )
        await session.flush()
        row.approval_ref = str(event.event_id)


async def ask(app, request):
    kernel = app.state.kernel
    request_key = (
        digest([request.conversation_ref, request.idempotency_key])[:60]
        if request.conversation_ref
        else request.idempotency_key
    )
    async with kernel.db.sessions() as session:
        from alive.task_review.service import validate_request_retry

        await validate_request_retry(session, kernel, request)
        current = await consent(session, kernel, request.consent_ref, active=False)
        existing = await session.scalar(
            select(Admission).where(
                Admission.instance_id == kernel.instance_id,
                Admission.principal == current["terms"]["principal"],
                Admission.idempotency_key == f"live:{request_key}:intent",
            )
        )
        if existing and await followup_outcome(session, kernel, existing.id):
            approval = await session.scalar(select(Event).where(Event.id == existing.approval_ref))
            require(
                existing.terms["objective"]["requested_outcome"] == request.goal
                and approval is not None
                and approval.payload.get("standing_ref") == request.consent_ref,
                "live_retry_conflict",
            )
            return await exchange(kernel, existing.id)
        require(current["state"] == "approved", "standing_consent_required_expired_or_revoked")
    terms = current["terms"]
    if request.task_mode == "research":
        require(terms.get("research"), "research_not_authorized")
        require(
            request.task_case_ids is None and not request.repair_incomplete,
            "research_task_options_invalid",
        )
        from alive.research import service as research_service

        return await research_service.run(app, request, current, reference=request.reference)
    task_review = request.task_mode == "code_review"
    if task_review:
        require(
            terms.get("code_review") and request.conversation_ref, "code_review_session_required"
        )
        require(
            not request.repair_incomplete or terms.get("completion_repair"), "repair_not_authorized"
        )
    else:
        require(
            request.task_case_ids is None and not request.repair_incomplete,
            "explicit_code_review_required",
        )
    context_ref, continuation = None, False
    if request.conversation_ref:
        from alive.continuity.service import prepare_turn

        context_ref, continuation = await prepare_turn(kernel, request, current)

    async def run(profile, suffix):
        review = await service.prepare(
            kernel,
            ReviewRequest(
                profile=profile,
                goal_ref=terms["goal_ref"],
                approval_ref=terms["approval_ref"],
                recipe_sha256=terms["profiles"][profile]["recipe_sha256"],
                objective={"kind": "inspect_implementation", "requested_outcome": request.goal},
                paths=terms["paths"],
                idempotency_key=f"live:{request_key}:{suffix}",
                context_ref=context_ref if profile in CONTEXT_PROFILES else None,
            ),
        )
        if request.conversation_ref:
            from alive.continuity.service import link

            await link(kernel, request.conversation_ref, review["id"])
        # A retained terminal run is history, even after consent expires. No restart/retry.
        if not review["run"]:
            await authorize(kernel, request.consent_ref, review)
        return await service.start(app, review["id"], review["review_sha256"])

    async def finish_task(original, root_id):
        nonlocal context_ref
        if request.repair_incomplete and original["run"]["status"] == "COMPLETED":
            from alive.continuity.service import artifact
            from alive.task_review.service import freeze

            async with kernel.db.sessions() as session:
                stored = await artifact(
                    session, kernel, await service.row_for(session, kernel, original["id"])
                )
            if stored and not stored["result"]["completion"]["task_complete"]:
                try:
                    context_ref = await freeze(
                        kernel, request, current, context_ref, original_id=original["id"]
                    )
                    await run(CODE_REPAIR, "repair")
                except Refused as error:
                    if str(error) in AUTHORIZATION_REFUSALS:
                        await retain_blocked_followup(kernel, root_id, CODE_REPAIR, error)
                    else:
                        await retain_failed_followup(kernel, root_id, CODE_REPAIR, error)
        return await exchange(kernel, root_id)

    if continuation and task_review:
        from alive.task_review.service import freeze

        context_ref = await freeze(kernel, request, current, context_ref)
        interpreted = await run(CODE_REVIEW, "intent")
        return await finish_task(interpreted, interpreted["id"])
    interpreted = await run(CONTEXTUAL if continuation else INTENT, "intent")
    if continuation:
        from alive.adaptation.service import capture_proposal

        if terms.get("adaptive") and interpreted["run"]["status"] == "COMPLETED":
            await capture_proposal(kernel, interpreted["id"])
        return await exchange(kernel, interpreted["id"])
    if interpreted["run"]["status"] != "COMPLETED":
        return await exchange(kernel, interpreted["id"])
    recommendation = (await intent.compose(kernel, interpreted["id"]))["record"]
    if (terms.get("adaptive") or task_review) and request.conversation_ref:
        from alive.continuity.service import adaptive_snapshot

        interpretation = recommendation["interpretation"]["value"]
        if terms.get("adaptive"):
            context_ref = await adaptive_snapshot(
                kernel,
                request,
                current,
                interpretation.get("problem_families", []),
                interpretation.get("task_mechanisms", []),
            )
        if task_review:
            from alive.task_review.service import freeze

            context_ref = await freeze(kernel, request, current, context_ref)
        try:
            result = await run(CODE_REVIEW if task_review else CONTEXTUAL, "result")
            if task_review:
                return await finish_task(result, interpreted["id"])
        except Refused as error:
            if str(error) in AUTHORIZATION_REFUSALS:
                await retain_blocked_followup(kernel, interpreted["id"], CONTEXTUAL, error)
            else:
                await retain_failed_followup(kernel, interpreted["id"], CONTEXTUAL, error)
        return await exchange(kernel, interpreted["id"])
    chosen = recommendation["recommendation"]
    if (
        chosen
        and chosen["recipe_id"] in (ANALYSIS, INSPECTION)
        and not recommendation["uncertainty"]["needs_clarification"]
    ):
        try:
            await run(chosen["recipe_id"], "result")
        except Refused as error:
            if str(error) in AUTHORIZATION_REFUSALS:
                await retain_blocked_followup(kernel, interpreted["id"], chosen["recipe_id"], error)
            else:
                await retain_failed_followup(kernel, interpreted["id"], chosen["recipe_id"], error)
    return await exchange(kernel, interpreted["id"])


async def exchange(kernel, admission_id):
    """Read-only projection. Opening history cannot dispatch or compose anything."""
    async with kernel.db.sessions() as session:
        row = await service.row_for(session, kernel, admission_id)
        require(
            row.idempotency_key.startswith("live:") and row.idempotency_key.endswith(":intent"),
            "not_a_live_exchange",
        )
        result = await session.scalar(
            select(Admission).where(
                Admission.instance_id == kernel.instance_id,
                Admission.principal == row.principal,
                Admission.idempotency_key == row.idempotency_key[:-6] + "result",
            )
        )
        repair = await session.scalar(
            select(Admission).where(
                Admission.instance_id == kernel.instance_id,
                Admission.principal == row.principal,
                Admission.idempotency_key == row.idempotency_key[:-6] + "repair",
            )
        )
        recommendation = await intent.stored(session, kernel, row.id)
        from alive.continuity import service as continuity

        membership = await session.scalar(
            select(Event).where(
                Event.instance_id == kernel.instance_id,
                Event.source == continuity.SOURCE,
                Event.event_type == continuity.LINKED,
                Event.payload["admission_id"].as_string() == row.id,
            )
        )
        blocked = await followup_outcome(session, kernel, row.id)
        inquiries = [
            r.terms["proposed_grant_data"]["investigation_id"] for r in (row, result, repair) if r
        ]
        calls = (
            await session.scalars(
                select(ModelInvocation)
                .where(
                    ModelInvocation.investigation_id.in_(inquiries),
                )
                .order_by(ModelInvocation.created_at)
            )
        ).all()
        receipts = [
            {
                "id": c.id,
                "status": c.status,
                "provider": c.provider,
                "model": c.model,
                "usage": c.usage,
                "latency_ms": c.latency_ms,
                "endpoint": next(
                    r.terms["model_disclosure"]["destination"]["endpoint"]
                    for r in (row, result, repair)
                    if r
                    and r.terms["proposed_grant_data"]["investigation_id"] == c.investigation_id
                ),
            }
            for c in calls
        ]
        for receipt in receipts:
            upstream = (
                await session.execute(
                    select(PiRun, PiProviderRequest)
                    .join(PiProviderRequest, PiProviderRequest.run_id == PiRun.id)
                    .where(
                        PiRun.instance_id == kernel.instance_id,
                        PiRun.reservation_ref == receipt["id"],
                    )
                )
            ).all()
            receipt["provider_receipts"] = [
                {
                    "pi_run_id": run.id,
                    "pi_state": run.state,
                    "transport": run.requested_json.get("upstream_transport", "unknown"),
                    "request_id": request.id,
                    "state": request.state,
                    "http_status": request.http_status,
                    "usage": request.usage_json,
                    "response_sha256": request.response_sha256,
                    "model_observed": request.model_observed,
                    "model_requested": request.model_requested,
                    "latency_ms": request.latency_ms,
                }
                for run, request in upstream
            ]
            completed = [
                r
                for r in receipt["provider_receipts"]
                if r["pi_state"] == "SETTLED"
                and r["state"] == "settled"
                and r["http_status"] == 200
                and r["response_sha256"]
                and r["model_requested"] == receipt["model"]
            ]
            receipt["inference_provenance"] = (
                "production_pi"
                if any(r["transport"] == "network" for r in completed)
                else "injected_transport"
                if any(r["transport"] == "injected" for r in completed)
                else "unverified"
            )
        validated = [r for r in receipts if r["status"] == "validated"]
        status = (
            "LIVE MODEL"
            if any(r["inference_provenance"] == "production_pi" for r in validated)
            else "TEST MODEL RESPONSE"
            if any(r["inference_provenance"] == "injected_transport" for r in validated)
            else "MODEL RESPONSE"
            if validated
            else "NO MODEL CALL"
        )
        value = {
            "id": row.id,
            "goal": row.terms["objective"]["requested_outcome"],
            "source": row.terms["source"],
            "admission": await service.view(session, kernel, row),
            "recommendation": intent.view(recommendation) if recommendation else None,
            "result_admission": await service.view(session, kernel, result) if result else None,
            "calls": receipts,
            "model_calls": sum(
                1
                for receipt in receipts
                for request in receipt["provider_receipts"]
                if request["http_status"] is not None
                or request["state"] in ("dispatched", "ambiguous")
            ),
            "status": status,
            "followup": blocked.payload if blocked else None,
            "report": None,
            "inspection": None,
            "conversation_ref": membership.correlation_id if membership else None,
            "context": None,
            "answer": None,
            "selection": None,
        }
        contextual = next(
            (r for r in (result, row) if r and service.profile_of(r.terms).id in CONTEXT_PROFILES),
            None,
        )
        if contextual:
            context_ref = contextual.terms["proposed_grant_data"]["inputs"]["context_ref"]
            value["context"] = await continuity.frozen(
                session,
                kernel,
                context_ref,
                contextual.terms["source"]["resources"],
                contextual.principal,
            )
            retained = await continuity.artifact(session, kernel, contextual)
            if retained:
                value["answer"] = retained["result"] | {"artifact_sha256": retained["sha256"]}
            if contextual.terms.get("profile") == CODE_REVIEW and retained:
                repaired = await continuity.artifact(session, kernel, repair) if repair else None
                repair_calls = [
                    c
                    for c in receipts
                    if repair
                    and c["id"]
                    in {
                        call.id
                        for call in calls
                        if call.investigation_id
                        == repair.terms["proposed_grant_data"]["investigation_id"]
                    }
                ]
                request_ids = [p["request_id"] for c in receipts for p in c["provider_receipts"]]
                dispatched = set(
                    await session.scalars(
                        select(Event.payload["request_id"].as_string()).where(
                            Event.instance_id == kernel.instance_id,
                            Event.source == "pi",
                            Event.event_type == "pi.provider_request.dispatched",
                            Event.payload["request_id"].as_string().in_(request_ids),
                        )
                    )
                )
                value["model_calls"] = len(dispatched)
                adopted = repaired is not None and not repaired["result"]["repair_rejection"]
                effective = repaired["result"] if adopted else retained["result"]
                if adopted:
                    value["answer"] = effective | {"artifact_sha256": repaired["sha256"]}
                    value["context"] = await continuity.frozen(
                        session,
                        kernel,
                        repair.terms["proposed_grant_data"]["inputs"]["context_ref"],
                        repair.terms["source"]["resources"],
                        repair.principal,
                    )
                value["task_review"] = {
                    "original": retained["result"],
                    "effective": effective,
                    "repair": repaired["result"] if repaired else None,
                    "repair_admission": await service.view(session, kernel, repair)
                    if repair
                    else None,
                    "repair_requested": value["context"]
                    .get("task_request", {})
                    .get("repair_requested", False),
                    "repair_attempted": repair is not None and repair.run_id is not None,
                    "repair_blocked": blocked.payload
                    if blocked and blocked.payload.get("profile") == CODE_REPAIR
                    else None,
                    "repair_successful": bool(
                        repaired
                        and not effective["repair_rejection"]
                        and effective["task_complete"]
                    ),
                    "additional_model_calls": sum(
                        p["request_id"] in dispatched
                        for c in repair_calls
                        for p in c["provider_receipts"]
                    ),
                    "repair_calls": repair_calls,
                }
            from alive.adaptation.selection import view

            value["selection"] = await view(
                session, kernel, value["context"], value["answer"], contextual.id
            )
        if result and service.profile_of(result.terms).id == INSPECTION:
            from alive.workflows.models import WorkflowRun

            run = await session.get(WorkflowRun, result.run_id) if result.run_id else None
            if run and run.status == "COMPLETED":
                stage = await session.scalar(
                    select(WorkflowStageRun).where(
                        WorkflowStageRun.run_id == run.id,
                        WorkflowStageRun.stage_id == "read",
                    )
                )
                value["inspection"] = await result_event(session, stage)
        value["availability"] = (
            "available"
            if value.get("task_review")
            else "AI unavailable"
            if any(c.status in ("failed", "cancelled", "interrupted") for c in calls)
            else "available"
            if calls
            else "not_called"
        )
        if value["model_calls"] and value["status"] == "NO MODEL CALL":
            value["status"] = "MODEL CALL FAILED"
    if (
        value["result_admission"]
        and service.profile_of(value["result_admission"]["terms"]).id == ANALYSIS
        and value["result_admission"]["run"]
        and value["result_admission"]["run"]["status"] == "COMPLETED"
    ):
        value["report"] = await service.report(kernel, result.id)
    return value


async def listing(kernel):
    async with kernel.db.sessions() as session:
        rows = (
            await session.scalars(
                select(Admission)
                .where(
                    Admission.instance_id == kernel.instance_id,
                    Admission.idempotency_key.like("live:%:intent"),
                )
                .order_by(Admission.created_at.desc())
                .limit(20)
            )
        ).all()
        setups = (
            await session.scalars(
                select(Event)
                .where(
                    Event.instance_id == kernel.instance_id,
                    Event.event_type == PREPARED,
                    Event.source == service.OWNER_SOURCE,
                )
                .order_by(Event.sequence_number.desc())
                .limit(20)
            )
        ).all()
        configs = [await consent(session, kernel, e.id, active=False) for e in setups]
    from alive.adaptation.service import listing as adaptation
    from alive.continuity.service import listing as conversations

    return {
        "consents": configs,
        "exchanges": [await exchange(kernel, r.id) for r in rows],
        "conversations": await conversations(kernel),
        "adaptation": await adaptation(kernel),
    }
