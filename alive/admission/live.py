"""Ask ALIVE: standing consent over existing closed, read-only admission profiles.

Events retain consent and conservative reservations. Each call still has an exact Grant,
source approval, Governor budget and Pi dispatch fence. No provider or runner lives here.
"""

from datetime import datetime, timedelta

from sqlalchemy import select

from alive.admission import service
from alive.admission.contracts import ReviewRequest
from alive.admission.models import Admission
from alive.admission.profiles import ANALYSIS, INSPECTION, INTENT
from alive.bespoke.recipes import recipe_hash
from alive.cognitive_models import ModelInvocation
from alive.intent import service as intent
from alive.models import Event, now
from alive.pi.models import PiProviderRequest, PiRun
from alive.workflows.context import digest, require
from alive.workflows.models import WorkflowStageRun
from alive.workflows.runner import result_event

PREPARED = "admission.standing.prepared"
APPROVED = "admission.standing.approved"
REVOKED = "admission.standing.revoked"


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
        "inputs": {k: v for k, v in grant["inputs"].items() if k != "objective"},
        "disclosure": {
            k: v
            for k, v in disclosure.items()
            if k
            not in {
                "goal_characters",
                "reserved_request_bytes",
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
    for profile in (INTENT, ANALYSIS, INSPECTION):
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
    async with kernel.db.sessions() as session:
        current = await consent(session, kernel, request.consent_ref)
    terms = current["terms"]

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
                idempotency_key=f"live:{request.idempotency_key}:{suffix}",
            ),
        )
        # A retained terminal run is history, even after consent expires. No restart/retry.
        if not review["run"]:
            await authorize(kernel, request.consent_ref, review)
        return await service.start(app, review["id"], review["review_sha256"])

    interpreted = await run(INTENT, "intent")
    if interpreted["run"]["status"] != "COMPLETED":
        return await exchange(kernel, interpreted["id"])
    recommendation = (await intent.compose(kernel, interpreted["id"]))["record"]
    chosen = recommendation["recommendation"]
    if (
        chosen
        and chosen["recipe_id"] in (ANALYSIS, INSPECTION)
        and not recommendation["uncertainty"]["needs_clarification"]
    ):
        await run(chosen["recipe_id"], "result")
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
        recommendation = await intent.stored(session, kernel, row.id)
        inquiries = [r.terms["proposed_grant_data"]["investigation_id"] for r in (row, result) if r]
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
                    for r in (row, result)
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
                    "request_id": request.id,
                    "state": request.state,
                    "http_status": request.http_status,
                    "usage": request.usage_json,
                    "response_sha256": request.response_sha256,
                    "model_observed": request.model_observed,
                    "latency_ms": request.latency_ms,
                }
                for run, request in upstream
            ]
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
            "status": "LIVE MODEL"
            if any(c.status == "validated" for c in calls)
            else "NO MODEL CALL",
            "report": None,
            "inspection": None,
        }
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
            "AI unavailable"
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
    return {"consents": configs, "exchanges": [await exchange(kernel, r.id) for r in rows]}
