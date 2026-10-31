"""A closed live profile: source consent -> review -> local owner -> existing runner.

Preparing a proposed Grant is data, never authority. Only an independently recorded local
owner confirmation permits the host to publish that exact Grant to the existing validator.
"""

from datetime import timedelta
from types import SimpleNamespace

from sqlalchemy import select

from alive.admission.models import Admission
from alive.bespoke.recipes import recipe_hash
from alive.bespoke.selector import evaluate
from alive.capabilities.bindings import binding_record, digest, registry_for
from alive.capabilities.contracts import json_bytes, validate
from alive.cognitive_models import CognitiveControl
from alive.models import Event, Goal, now, uid
from alive.sources import custody
from alive.sources.models import SourceApproval
from alive.workflows.context import OWNER, Grant, aware, require
from alive.workflows.context import digest as owner_digest
from alive.workflows.models import WorkflowDefinition, WorkflowExecution, WorkflowRun
from alive.workflows.store import run_view

OWNER_SOURCE = "admission-owner"
PROFILE = "approved-repository-inspection"
POLICY = "owner-admission/v1"


def recipe_for(kernel):
    from alive.bespoke.recipes import load_catalogue

    recipes = getattr(kernel, "bespoke_recipes", None) or load_catalogue()
    return next(r for r in recipes if r.id == PROFILE and r.version == "1.0.0")


async def row_for(session, kernel, admission_id, *, lock=False):
    query = select(Admission).where(
        Admission.id == admission_id, Admission.instance_id == kernel.instance_id
    )
    row = await session.scalar(query.with_for_update() if lock else query)
    require(
        row is not None and digest(row.terms) == row.review_sha256,
        "admission_unavailable_or_changed",
    )
    return row


async def current_terms(session, kernel, row):
    """Revalidate exact reviewed deployment and source state, without executing a capability."""
    terms = row.terms
    require(
        terms["policy"] == POLICY and terms["instance_id"] == kernel.instance_id,
        "admission_policy_or_instance_changed",
    )
    proposed = Grant.model_validate(terms["proposed_grant_data"])
    require(
        proposed.expires_at > now() and row.revocation_ref is None, "admission_expired_or_revoked"
    )
    goal = await session.get(Goal, proposed.goal_id)
    require(
        goal is not None
        and goal.instance_id == kernel.instance_id
        and goal.status in ("active", "accepted"),
        "accepted_owner_goal_required",
    )
    control = await session.get(CognitiveControl, kernel.instance_id)
    require(
        control is not None
        and owner_digest(control.configuration) == proposed.configuration_sha256,
        "governor_configuration_changed",
    )
    recipe = recipe_for(kernel)
    require(recipe_hash(recipe) == terms["candidate"]["recipe_sha256"], "recipe_identity_changed")
    definition = await session.get(WorkflowDefinition, proposed.definition_id)
    require(
        definition is not None
        and definition.status == "active"
        and definition.definition_sha256 == proposed.definition_sha256,
        "workflow_identity_changed",
    )
    binding = await binding_record(session, kernel, definition)
    require(binding.snapshot_sha256 == proposed.capability_binding_sha256, "binding_changed")
    registry = registry_for(kernel)
    expected = registry.grants_for(
        binding.snapshot["stages"], resources={"read": terms["source"]["resources"]}
    )
    require(expected == proposed.capabilities, "deployment_or_capability_changed")
    source = await custody.resolve(kernel, terms["source"]["resources"], "repository.inspect")
    approval = await session.get(SourceApproval, source.approval_id)
    require(
        approval.approved_by == row.principal == proposed.principal
        and aware(approval.expires_at).isoformat() == terms["source"]["expires_at"],
        "source_owner_or_expiry_changed",
    )
    # Full deterministic feasibility again, including definition bytes and stage input contracts.
    candidate = await evaluate(
        session,
        kernel,
        recipe,
        SimpleNamespace(objective=recipe_context_objective(terms), constraints=recipe.limits),
        proposed,
        terms["selection_context"],
    )
    require(
        candidate.eligible and candidate.model_dump(mode="json") == terms["candidate"],
        "admission_no_longer_eligible",
    )
    return proposed


def recipe_context_objective(terms):
    from alive.bespoke.contracts import Objective

    return Objective.model_validate(terms["objective"])


async def prepare(kernel, request):
    recipe = recipe_for(kernel)
    require(request.recipe_sha256 == recipe_hash(recipe), "recipe_identity_changed")
    require(len(set(request.paths)) == len(request.paths), "duplicate_source_path")
    async with kernel.lock, kernel.db.sessions.begin() as session:
        approval = await session.get(SourceApproval, request.approval_ref)
        require(
            approval is not None and approval.instance_id == kernel.instance_id,
            "owned_source_approval_required",
        )
        resources = custody.resources_for(approval)
        source = await custody.resolve(kernel, resources, "repository.inspect")
        require(
            source.source_type == "repository" and approval.approved_by.startswith("owner-cli:"),
            "local_owner_repository_approval_required",
        )
        paths = sorted(request.paths)
        require(
            sorted(f["path"] for f in source.content["files"]) == paths,
            "admission_requires_exact_approved_file_scope",
        )
        require(
            sum(f["bytes"] for f in source.content["files"]) <= 32768,
            "admission_source_byte_ceiling",
        )
        existing = await session.scalar(
            select(Admission).where(
                Admission.instance_id == kernel.instance_id,
                Admission.principal == approval.approved_by,
                Admission.idempotency_key == request.idempotency_key,
            )
        )
        request_hash = digest(request.model_dump(mode="json"))
        if existing:
            require(existing.request_sha256 == request_hash, "admission_retry_conflict")
            return await view(session, kernel, existing)
        goal = await session.get(Goal, request.goal_ref)
        require(
            goal is not None
            and goal.instance_id == kernel.instance_id
            and goal.status in ("active", "accepted"),
            "accepted_owner_goal_required",
        )
        definition = await session.scalar(
            select(WorkflowDefinition).where(
                WorkflowDefinition.name == recipe.workflow.name,
                WorkflowDefinition.version == recipe.workflow.version,
            )
        )
        require(
            definition is not None and definition.status == "active",
            "install_admission_profile_first",
        )
        binding = await binding_record(session, kernel, definition)
        control = await session.get(CognitiveControl, kernel.instance_id)
        require(control is not None, "governor_required")
        admission_id, context_id, inquiry_id = uid(), uid(), uid()
        inputs = {"source_ref": source.source_ref, "paths": paths}
        cap = registry_for(kernel).get("repository.inspect", "1.1.0")
        validate({"mode": "read", **inputs}, cap.manifest["inputs"])
        context = {
            "goal_id": goal.id,
            "admission_ref": admission_id,
            "context": {
                "observation": request.objective.requested_outcome,
                "claims": [],
                "sources": [{"id": source.source_ref, "content_sha256": source.content_sha256}],
                "memories": [],
                "source_event_ids": [context_id],
                "requested_action_kind": "record_analysis",
            },
        }
        expiry = min(now() + timedelta(seconds=request.ttl_seconds), aware(approval.expires_at))
        proposed = Grant(
            principal=approval.approved_by,
            goal_id=goal.id,
            investigation_id=inquiry_id,
            definition_id=definition.id,
            definition_sha256=definition.definition_sha256,
            context_event_id=context_id,
            context_sha256=owner_digest(context),
            admission_ref=admission_id,
            context_provenance={
                "source": OWNER_SOURCE,
                "event_type": "workflow.owner.context",
                "custody": "approved_capture",
                "consent": "exact_content_and_scope",
            },
            operations=("repository.inspect",),
            capability_binding_sha256=binding.snapshot_sha256,
            capabilities=registry_for(kernel).grants_for(
                binding.snapshot["stages"], resources={"read": resources}
            ),
            inputs=inputs,
            configuration_sha256=owner_digest(control.configuration),
            models={},
            role_contracts={},
            max_model_calls=0,
            max_output_tokens=0,
            wall_seconds=30,
            expires_at=expiry,
            outbound_approved=False,
            idempotency_key="admission:" + admission_id,
        )
        selection_context = {
            "surface": "repository",
            "claims_count": 0,
            "sources_count": 1,
            "inputs_sha256": digest(inputs),
        }
        candidate = await evaluate(
            session,
            kernel,
            recipe,
            SimpleNamespace(objective=request.objective, constraints=recipe.limits),
            proposed,
            selection_context,
        )
        require(candidate.eligible, "admission_recipe_ineligible")
        terms = {
            "schema": "owner-admission/v1",
            "policy": POLICY,
            "instance_id": kernel.instance_id,
            "goal": {"id": goal.id, "title": goal.title},
            "objective": request.objective.model_dump(mode="json"),
            "source": {
                "resources": resources,
                "label": source.label,
                "scope": approval.scope,
                "inventory": custody.inventory("repository", source.content),
                "expires_at": aware(approval.expires_at).isoformat(),
                "principal": approval.approved_by,
            },
            "candidate": candidate.model_dump(mode="json"),
            "selection_context": selection_context,
            "proposed_grant_data": proposed.model_dump(mode="json"),
            "context": context,
            "expected_output": "captured_files",
            "semantic_status": "unverified",
            "cost_status": "no_inference; currency_cost_not_estimated",
        }
        require(len(json_bytes(terms)) <= 65536, "admission_review_size")
        row = Admission(
            id=admission_id,
            instance_id=kernel.instance_id,
            principal=approval.approved_by,
            idempotency_key=request.idempotency_key,
            request_sha256=request_hash,
            review_sha256=digest(terms),
            terms=terms,
        )
        session.add(row)
        await session.flush()
        kernel.add_event(
            session,
            "admission.review.prepared",
            {"admission_id": row.id, "review_sha256": row.review_sha256},
            source="admission",
            correlation=row.id,
        )
        return await view(session, kernel, row)


async def approval_receipt(session, row):
    event = await session.scalar(select(Event).where(Event.id == row.approval_ref))
    require(
        event is not None
        and event.instance_id == row.instance_id
        and event.source == OWNER_SOURCE
        and event.event_type == "admission.owner.approved"
        and event.payload
        == {"admission_id": row.id, "review_sha256": row.review_sha256, "principal": row.principal},
        "local_owner_approval_required",
    )


async def approve(kernel, admission_id, *, confirm_sha256, principal):
    async with kernel.lock, kernel.db.sessions.begin() as session:
        row = await row_for(session, kernel, admission_id, lock=True)
        require(
            confirm_sha256 == row.review_sha256 and principal == row.principal,
            "exact_local_owner_confirmation_required",
        )
        await current_terms(session, kernel, row)
        if row.approval_ref:
            await approval_receipt(session, row)
        else:
            event = kernel.add_event(
                session,
                "admission.owner.approved",
                {
                    "admission_id": row.id,
                    "review_sha256": row.review_sha256,
                    "principal": principal,
                },
                source=OWNER_SOURCE,
                correlation=row.id,
            )
            await session.flush()  # the receipt row must exist before the foreign key points at it
            row.approval_ref = str(event.event_id)
        await session.flush()
        return await view(session, kernel, row)


async def revoke(kernel, admission_id, *, principal):
    async with kernel.lock, kernel.db.sessions.begin() as session:
        row = await row_for(session, kernel, admission_id, lock=True)
        require(principal == row.principal, "local_owner_required")
        if not row.revocation_ref:
            event = kernel.add_event(
                session,
                "admission.owner.revoked",
                {
                    "admission_id": row.id,
                    "review_sha256": row.review_sha256,
                    "principal": principal,
                },
                source=OWNER_SOURCE,
                correlation=row.id,
            )
            await session.flush()
            row.revocation_ref = str(event.event_id)
        await session.flush()
        return await view(session, kernel, row)


async def verify_grant(session, kernel, grant, authorization_id):
    row = await row_for(session, kernel, grant.admission_ref)
    await approval_receipt(session, row)
    require(
        row.authorization_ref == authorization_id
        and grant.model_dump(mode="json") == row.terms["proposed_grant_data"],
        "admission_grant_identity_changed",
    )
    await current_terms(session, kernel, row)


async def view(session, kernel, row):
    require(digest(row.terms) == row.review_sha256, "admission_integrity")
    authorization = (
        "revoked"
        if row.revocation_ref
        else "expired"
        if Grant.model_validate(row.terms["proposed_grant_data"]).expires_at <= now()
        else "approved"
        if row.approval_ref
        else "pending"
    )
    run = await session.get(WorkflowRun, row.run_id) if row.run_id else None
    return {
        "id": row.id,
        "review_sha256": row.review_sha256,
        "terms": row.terms,
        "authorization_state": authorization,
        "state": run.status.lower() if run else authorization,
        "run": run_view(run) if run else None,
    }


async def get(kernel, admission_id):
    async with kernel.db.sessions() as session:
        return await view(session, kernel, await row_for(session, kernel, admission_id))


async def start(app, admission_id, confirm_sha256):
    kernel, cognition, runner = app.state.kernel, app.state.cognition, app.state.workflows
    async with cognition.command_lock:
        async with kernel.lock, kernel.db.sessions.begin() as session:
            row = await row_for(session, kernel, admission_id, lock=True)
            require(row.review_sha256 == confirm_sha256, "admission_confirmation_changed")
            if row.run_id:
                return await view(session, kernel, row)  # history, never redispatch
            await approval_receipt(session, row)
            grant = await current_terms(session, kernel, row)
            if row.authorization_ref:
                execution = await session.scalar(
                    select(WorkflowExecution).where(
                        WorkflowExecution.authorization_id == row.authorization_ref
                    )
                )
                if execution:
                    row.run_id = execution.run_id
                    return await view(session, kernel, row)  # crash/retry: never resume work
                require(False, "interrupted_admission_requires_new_review")
            context_id = grant.context_event_id
            kernel.add_event(
                session,
                "workflow.owner.context",
                row.terms["context"],
                source=OWNER_SOURCE,
                event_id=context_id,
                correlation=grant.investigation_id,
            )
            await session.flush()
            await cognition.admit_owner_workflow(
                session,
                grant.investigation_id,
                grant.goal_id,
                context_id,
                row.terms["objective"]["requested_outcome"],
            )
            event = kernel.add_event(
                session,
                "workflow.execution.authorized",
                grant.model_dump(mode="json"),
                source=OWNER,
                correlation=grant.investigation_id,
            )
            await session.flush()
            row.authorization_ref = str(event.event_id)
            authority = row.authorization_ref
        try:
            started = await runner.start(authority)
        except BaseException:
            await cognition.finish(
                grant.investigation_id,
                "CANCELLED",
                {"effect": "none", "reason": "admission_failed"},
                truncated=True,
            )
            raise
        async with kernel.lock, kernel.db.sessions.begin() as session:
            row = await row_for(session, kernel, admission_id, lock=True)
            row.run_id = started["id"]
    await runner.execute(started["id"])
    return await get(kernel, admission_id)


async def cancel(app, admission_id):
    current = await get(app.state.kernel, admission_id)
    require(current["run"] is not None, "admission_not_started")
    await app.state.workflows.cancel(current["run"]["id"])
    return await get(app.state.kernel, admission_id)
