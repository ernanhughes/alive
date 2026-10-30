"""Explicit controlled owner harness and two procedures; never imported at startup."""

from datetime import timedelta

from sqlalchemy import select

from alive.cognitive_models import CognitiveControl, CognitiveObservation, Investigation, Laboratory
from alive.models import now, uid
from alive.workflows.context import OWNER, Grant, digest, role_contract
from alive.workflows.models import WorkflowDefinition
from alive.workflows.store import register_definition


def stage(identity, operation, kind, properties, *, dependencies=(), inputs=None):
    return {
        "id": identity,
        "title": identity.title(),
        "type": kind,
        "operation": operation,
        "depends_on": list(dependencies),
        "inputs": inputs or {},
        "output_schema": {
            "properties": {key: {"type": value} for key, value in properties.items()},
            "required": list(properties),
        },
        "limits": {
            "timeout_seconds": 45,
            **({"max_output_tokens": 1536} if kind == "pi_agent" else {}),
        },
    }


def definition(*, model=True):
    prepare = stage(
        "prepare",
        "context.prepare",
        "deterministic",
        {"context": "object", "claims": "array", "sources": "array"},
    )
    if model:
        middle = [
            stage(
                "analyze",
                "cognition.role",
                "pi_agent",
                {"analysis": "object"},
                dependencies=("prepare",),
                inputs={"role": "observer", "context": "$stage.prepare.context"},
            ),
            stage(
                "validate",
                "evidence.validate_references",
                "validation",
                {"result": "object", "assessment": "object"},
                dependencies=("prepare", "analyze"),
                inputs={"analysis": "$stage.analyze.analysis", "context": "$stage.prepare.context"},
            ),
        ]
        producer = "validate"
    else:
        middle = [
            stage(
                "compare",
                "evidence.evaluate",
                "validation",
                {"result": "object", "assessment": "object"},
                dependencies=("prepare",),
                inputs={"claims": "$stage.prepare.claims", "sources": "$stage.prepare.sources"},
            )
        ]
        producer = "compare"
    return {
        "schema_version": 1,
        "name": "research-review" if model else "source-comparison",
        "version": 2 if model else 1,
        "title": "Bounded evidence review" if model else "Source comparison",
        "limits": {
            "max_wall_seconds": 120,
            "max_model_calls": int(model),
            "max_total_output_tokens": 1536 if model else 0,
        },
        "stages": [
            prepare,
            *middle,
            stage(
                "record",
                "result.record",
                "deterministic",
                {"artifact_id": "string", "sha256": "string"},
                dependencies=(producer,),
                inputs={
                    "result": f"$stage.{producer}.result",
                    "assessment": f"$stage.{producer}.assessment",
                },
            ),
        ],
    }


async def fixture_authorization(kernel, inquiry_id, *, model=True, changes=None):
    """Trusted, independent owner approval for the synthetic lab only. No public write route."""
    raw = definition(model=model)
    await register_definition(kernel, raw, status="active", source="admin")
    async with kernel.lock, kernel.db.sessions.begin() as session:
        inquiry = await session.get(Investigation, inquiry_id)
        observation = await session.get(CognitiveObservation, inquiry.observation_id)
        laboratory_id = observation.provenance["url"].split("/world/")[-1]
        laboratory = await session.get(Laboratory, laboratory_id)
        if laboratory is None or laboratory.instance_id != kernel.instance_id:
            raise ValueError(
                "Only the independently controlled local lab may use this fixture owner"
            )
        control = await session.get(CognitiveControl, kernel.instance_id)
        selected = await session.scalar(
            select(WorkflowDefinition).where(
                WorkflowDefinition.name == raw["name"], WorkflowDefinition.version == raw["version"]
            )
        )
        event_id = uid()
        payload = {
            "goal_id": inquiry.goal_id,
            "context": {
                "observation": observation.content,
                "claims": observation.provenance["claims"],
                "sources": laboratory.sources,
                "memories": [],
                "source_event_ids": [event_id],
                "requested_action_kind": "record_analysis",
            },
        }
        kernel.add_event(
            session,
            "workflow.fixture.context",
            payload,
            source="controlled-laboratory",
            event_id=event_id,
            correlation=inquiry.id,
        )
        grant = Grant(
            principal="independent-fixture-owner",
            goal_id=inquiry.goal_id,
            investigation_id=inquiry.id,
            definition_id=selected.id,
            definition_sha256=selected.definition_sha256,
            context_event_id=event_id,
            context_sha256=digest(payload),
            operations=tuple(s["operation"] for s in raw["stages"]),
            configuration_sha256=digest(control.configuration),
            models={
                "observer": kernel.settings.alive_role_models.get(
                    "observer", kernel.settings.alive_meta_model
                )
            }
            if model
            else {},
            role_contracts={"observer": role_contract("observer")} if model else {},
            max_model_calls=int(model),
            max_output_tokens=1536 if model else 0,
            wall_seconds=120,
            expires_at=now() + timedelta(seconds=120),
            outbound_approved=model,
            idempotency_key=uid(),
        ).model_dump(mode="json")
        if changes:
            grant.update(changes)
        event = kernel.add_event(
            session, "workflow.execution.authorized", grant, source=OWNER, correlation=inquiry.id
        )
        return str(event.event_id)
