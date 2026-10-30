"""Owner-supplied admission and bounded data. Public observation text cannot mint grants."""

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select

from alive.cognitive_models import CognitiveControl, Investigation
from alive.cognitive_schema import CognitiveConfiguration, RoleOutput
from alive.models import Event, Goal, now
from alive.society import ROLE_SPEC_VERSION, role_prompt
from alive.workflows.models import (
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowRun,
    WorkflowStageRun,
)
from alive.workflows.spec import definition_sha256, parse_definition

OWNER = "workflow-owner"
MAX_BYTES = 65536


class Refused(ValueError):
    """Bounded refusal category; adapter exception text is never a public receipt."""


def require(condition, category):
    if not condition:
        raise Refused(category)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def aware(value):
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class ContextProvenance(BaseModel):
    """Custody labels bind authorized use; they do not authenticate page content."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    source: Literal["controlled-laboratory", "extension", "user"]
    event_type: str = Field(min_length=1, max_length=100)
    custody: Literal["controlled_fixture", "untrusted_browser"]
    consent: Literal["exact_content_and_scope"]


def provenance_for(source):
    eligible = {
        ("controlled-laboratory", "workflow.fixture.context"): "controlled_fixture",
        ("extension", "browser.dom_changed"): "untrusted_browser",
        ("extension", "browser.page_opened"): "untrusted_browser",
        ("user", "browser.dom_changed"): "untrusted_browser",
        ("user", "browser.page_opened"): "untrusted_browser",
    }
    custody = eligible.get((source.source, source.event_type))
    require(custody is not None, "unsupported_context_provenance")
    return ContextProvenance(
        source=source.source,
        event_type=source.event_type,
        custody=custody,
        consent="exact_content_and_scope",
    )


class Grant(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: Literal[1] = 1
    principal: str = Field(min_length=1, max_length=100)
    goal_id: str = Field(min_length=1, max_length=36)
    investigation_id: str = Field(min_length=1, max_length=36)
    definition_id: str = Field(min_length=1, max_length=36)
    definition_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    context_event_id: str = Field(min_length=1, max_length=36)
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    # Legacy grants remain readable for forensics; new execution requires provenance.
    context_provenance: ContextProvenance | None = None
    operations: tuple[str, ...] = Field(min_length=1, max_length=16)
    inputs: dict = Field(default_factory=dict, max_length=16)
    configuration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    models: dict[str, str] = Field(default_factory=dict, max_length=4)
    role_contracts: dict[str, str] = Field(default_factory=dict, max_length=4)
    max_model_calls: int = Field(ge=0, le=8)
    max_output_tokens: int = Field(ge=0, le=16384)
    wall_seconds: int = Field(ge=1, le=3600)
    expires_at: datetime
    outbound_approved: bool = False
    idempotency_key: str = Field(min_length=1, max_length=100)

    @field_validator("expires_at")
    @classmethod
    def timezone(cls, value):
        require(value.tzinfo is not None, "timezone_required")
        return value


def bounded(value):
    require(len(json.dumps(value, allow_nan=False).encode()) <= MAX_BYTES, "data_size_limit")
    return value


def role_contract(role):
    return digest(
        {
            "instructions": role_prompt(role),
            "schema": RoleOutput.model_json_schema(),
            "version": ROLE_SPEC_VERSION,
        }
    )


async def authorized(session, kernel, authorization_id, expected_hash=None):
    event = await session.scalar(
        select(Event).where(Event.id == authorization_id).with_for_update()
    )
    require(
        event is not None
        and event.instance_id == kernel.instance_id
        and event.source == OWNER
        and event.event_type == "workflow.execution.authorized",
        "owner_authorization_required",
    )
    require(
        expected_hash is None or digest(event.payload) == expected_hash, "authorization_changed"
    )
    grant = Grant.model_validate(bounded(event.payload))
    authorization_hash = digest(event.payload)
    revoked = await session.scalar(
        select(Event.id)
        .where(
            Event.instance_id == kernel.instance_id,
            Event.source == OWNER,
            Event.event_type == "workflow.execution.revoked",
            Event.payload["authorization_id"].as_string() == event.id,
        )
        .limit(1)
    )
    require(not revoked and grant.expires_at > now(), "authorization_expired_or_revoked")
    goal = await session.get(Goal, grant.goal_id)
    inquiry = await session.get(Investigation, grant.investigation_id)
    require(
        goal is not None
        and goal.instance_id == kernel.instance_id
        and goal.status in ("active", "accepted")
        and inquiry is not None
        and inquiry.instance_id == kernel.instance_id
        and inquiry.goal_id == goal.id
        and inquiry.state not in ("COMPLETED", "FAILED", "CANCELLED", "ABSTAINED"),
        "authorized_inquiry_required",
    )
    definition = await session.get(WorkflowDefinition, grant.definition_id)
    require(definition is not None and definition.status == "active", "active_definition_required")
    spec = parse_definition(definition.definition_json)
    require(
        definition_sha256(spec) == grant.definition_sha256 == definition.definition_sha256,
        "definition_integrity",
    )
    source = await session.scalar(
        select(Event).where(Event.id == grant.context_event_id).with_for_update()
    )
    require(
        source is not None
        and source.instance_id == kernel.instance_id
        and digest(source.payload) == grant.context_sha256
        and source.payload.get("goal_id") == goal.id,
        "context_scope_or_integrity",
    )
    require(
        grant.context_provenance is not None and grant.context_provenance == provenance_for(source),
        "context_provenance_required_or_changed",
    )
    withdrawn = await session.scalar(
        select(Event.id)
        .where(
            Event.instance_id == kernel.instance_id,
            Event.source == OWNER,
            Event.event_type == "workflow.context.withdrawn",
            Event.payload["source_event_id"].as_string() == source.id,
        )
        .limit(1)
    )
    require(not withdrawn, "context_withdrawn")
    context = bounded(source.payload["context"])
    require(
        set(context)
        == {
            "observation",
            "claims",
            "sources",
            "memories",
            "source_event_ids",
            "requested_action_kind",
        },
        "context_contract",
    )
    require(
        isinstance(context["observation"], str)
        and len(context["observation"]) <= 4096
        and isinstance(context["claims"], list)
        and len(context["claims"]) <= 16
        and isinstance(context["sources"], list)
        and len(context["sources"]) <= 16
        and context["memories"] == []
        and context["source_event_ids"] == [source.id]
        and context["requested_action_kind"] == "record_analysis",
        "bounded_evidence_scope",
    )
    ids = [item["id"] for item in context["sources"]]
    require(len(set(ids)) == len(ids), "duplicate_source_identity")
    control = await session.get(CognitiveControl, kernel.instance_id)
    require(
        control is not None and digest(control.configuration) == grant.configuration_sha256,
        "governor_configuration_changed",
    )
    CognitiveConfiguration.model_validate(control.configuration)
    return grant, spec, definition, inquiry, context, authorization_hash


async def model_claim(session, kernel, claim, role, context, model, output_limit):
    """Called inside Cognition's existing reservation transaction, before dispatch is possible."""
    run_id, stage_id, owner = claim
    execution = await session.get(WorkflowExecution, run_id)
    run = await session.get(WorkflowRun, run_id)
    stage = await session.get(WorkflowStageRun, stage_id)
    if execution is not None and execution.cancel_requested:
        raise asyncio.CancelledError()
    require(
        execution is not None
        and execution.owner == owner
        and not execution.cancel_requested
        and run is not None
        and run.instance_id == kernel.instance_id
        and run.status == "RUNNING"
        and stage is not None
        and stage.run_id == run.id
        and stage.state == "RUNNING"
        and stage.operation == "cognition.role"
        and stage.model_invocation_id is None,
        "model_stage_claim_required",
    )
    grant, spec, _, inquiry, approved, _ = await authorized(
        session, kernel, execution.authorization_id, execution.authorization_sha256
    )
    selected = next(item for item in spec.stages if item.id == stage.stage_id)
    require(
        grant.outbound_approved
        and grant.models.get(role) == model
        and grant.role_contracts.get(role) == role_contract(role)
        and context == approved
        and inquiry.id == run.investigation_id
        and aware(execution.deadline) > now()
        and kernel.settings.alive_model_transport == "pi",
        "exact_model_authority_required",
    )
    require(stage.input_sha256 == digest({"role": role, "context": context}), "model_input_changed")
    require(
        output_limit <= selected.limits.max_output_tokens <= grant.max_output_tokens
        and "cognition.role" in grant.operations,
        "model_output_ceiling",
    )
    return stage


async def revoke(kernel, authorization_id):
    """Trusted owner revocation, serialized with the existing Pi dispatch transaction."""
    async with kernel.lock, kernel.db.sessions.begin() as session:
        event = await session.scalar(
            select(Event).where(Event.id == authorization_id).with_for_update()
        )
        require(
            event is not None
            and event.instance_id == kernel.instance_id
            and event.source == OWNER
            and event.event_type == "workflow.execution.authorized",
            "owner_authorization_required",
        )
        kernel.add_event(
            session,
            "workflow.execution.revoked",
            {"authorization_id": event.id},
            source=OWNER,
            correlation=event.correlation_id,
        )


async def withdraw(kernel, source_event_id):
    """Owner withdraws retained context while preserving the historical bytes and references."""
    async with kernel.lock, kernel.db.sessions.begin() as session:
        event = await session.scalar(
            select(Event).where(Event.id == source_event_id).with_for_update()
        )
        require(
            event is not None and event.instance_id == kernel.instance_id, "owned_context_required"
        )
        kernel.add_event(
            session,
            "workflow.context.withdrawn",
            {"source_event_id": event.id},
            source=OWNER,
            correlation=event.correlation_id,
        )
