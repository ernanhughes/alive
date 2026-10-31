"""Durable contract custody. Reading retained contracts never authorizes execution."""

import hashlib

from sqlalchemy import select

from alive.capabilities.contracts import json_bytes
from alive.capabilities.manifest import ManifestError, canonical_bytes, parse
from alive.capabilities.registry import Operation, default_registry
from alive.models import Event, now
from alive.workflows.models import WorkflowCapabilityBinding, WorkflowExecution


def digest(value):
    return hashlib.sha256(json_bytes(value)).hexdigest()


def registry_for(kernel):
    return getattr(kernel, "capabilities", None) or default_registry()


def require(condition, category):
    if not condition:
        # Local import avoids a parser/adapter/authorization import cycle.
        from alive.workflows.context import Refused

        raise Refused(category)


def validate_snapshot(snapshot, definition_hash):
    require(
        type(snapshot) is dict
        and set(snapshot) == {"definition_sha256", "stages"}
        and snapshot["definition_sha256"] == definition_hash
        and type(snapshot["stages"]) is dict
        and 1 <= len(snapshot["stages"]) <= 32,
        "capability_binding_contract",
    )
    require(len(json_bytes(snapshot)) <= 262144, "capability_snapshot_size")
    for binding in snapshot["stages"].values():
        manifest = parse(json_bytes(binding["manifest"]))
        identity = binding["identity"]
        require(
            identity["id"] == manifest.id
            and identity["version"] == manifest.version
            and identity["manifest_sha256"] == hashlib.sha256(canonical_bytes(manifest)).hexdigest()
            and identity["implementation_id"] == manifest.implementation.id,
            "retained_manifest_integrity",
        )


async def binding_record(session, kernel, definition):
    row = await session.get(WorkflowCapabilityBinding, definition.id)
    require(
        row is not None and row.snapshot_sha256 == digest(row.snapshot),
        "capability_binding_missing_or_changed",
    )
    validate_snapshot(row.snapshot, definition.definition_sha256)
    event = await session.scalar(select(Event).where(Event.id == row.source_ref))
    require(
        event is not None
        and event.source == "workflow"
        and event.event_type == "workflow.capabilities.bound"
        and event.correlation_id == definition.id
        and event.payload.get("definition_id") == definition.id
        and event.payload.get("definition_sha256") == definition.definition_sha256
        and event.payload.get("capability_snapshot_sha256") == row.snapshot_sha256,
        "capability_registration_receipt",
    )
    return row


async def bind_definition(session, kernel, definition, spec, *, adopt_legacy=False):
    """Create the retained binding once. `adopt_legacy` is a provenance decision made by the
    caller from the registration path, never inferred from operation ids or missing pins."""
    existing = await session.get(WorkflowCapabilityBinding, definition.id)
    if existing is not None:
        return await binding_record(session, kernel, definition)
    from alive.workflows.spec import DefinitionError

    try:
        stages = registry_for(kernel).bind(spec, legacy_compatibility=adopt_legacy)
    except ManifestError as error:
        raise DefinitionError([f"capability contract: {error}"]) from None
    snapshot = {"definition_sha256": definition.definition_sha256, "stages": stages}
    validate_snapshot(snapshot, definition.definition_sha256)
    sha = digest(snapshot)
    payload = {
        "definition_id": definition.id,
        "definition_sha256": definition.definition_sha256,
        "capability_snapshot_sha256": sha,
    }
    event = kernel.add_event(
        session,
        "workflow.capabilities.bound",
        payload,
        source="workflow",
        correlation=definition.id,
    )
    row = WorkflowCapabilityBinding(
        definition_id=definition.id,
        snapshot=snapshot,
        snapshot_sha256=sha,
        source_ref=str(event.event_id),
        created_at=now(),
    )
    session.add(row)
    await session.flush()
    return row


async def verify_authorization(session, kernel, definition, spec, grant):
    row = await binding_record(session, kernel, definition)
    require(
        grant.capability_binding_sha256 == row.snapshot_sha256
        and set(grant.capabilities) == set(row.snapshot["stages"]),
        "exact_capability_owner_grant_required",
    )
    registry = registry_for(kernel)
    by_id = {s.id: s for s in spec.stages}
    require(set(by_id) == set(row.snapshot["stages"]), "capability_stage_identity")
    for stage_id, binding in row.snapshot["stages"].items():
        stage = by_id[stage_id]
        require(
            stage.operation == binding["identity"]["id"]
            and binding["stage_limits"]
            == {
                "timeout_seconds": stage.limits.timeout_seconds,
                "max_output_tokens": stage.limits.max_output_tokens or 0,
            },
            "capability_stage_identity",
        )
        try:
            registry.check_grant(binding, grant.capabilities[stage_id])
        except (KeyError, ValueError, TypeError):
            require(False, "capability_authority_changed")
    return row


def execution_snapshot(binding, grant):
    return {
        "binding": binding.snapshot,
        "binding_sha256": binding.snapshot_sha256,
        "grants": grant.capabilities,
    }


async def retained(session, kernel, run):
    execution = await session.get(WorkflowExecution, run.id)
    if execution is None or not execution.capability_snapshot:
        return {}  # No retroactive attribution for pre-PI-03 executions.
    captured = execution.capability_snapshot
    require(
        execution.instance_id == run.instance_id == kernel.instance_id
        and execution.capability_snapshot_sha256 == digest(captured)
        and captured["binding_sha256"] == digest(captured["binding"]),
        "retained_capability_integrity",
    )
    validate_snapshot(captured["binding"], run.definition_sha256)
    event = await session.scalar(select(Event).where(Event.id == execution.authorization_id))
    from alive.workflows.context import digest as owner_digest

    require(
        event is not None
        and event.instance_id == run.instance_id
        and event.source == "workflow-owner"
        and event.event_type == "workflow.execution.authorized"
        and owner_digest(event.payload) == execution.authorization_sha256
        and event.payload.get("capability_binding_sha256") == captured["binding_sha256"]
        and event.payload.get("capabilities") == captured["grants"],
        "retained_capability_owner_identity",
    )
    return captured["binding"]["stages"]


async def historical_operations(session, kernel, run):
    """Retained contracts permit parsing only, never implementation resolution."""
    stages = await retained(session, kernel, run)
    operations = dict(registry_for(kernel).operations) if not stages else {}
    for binding in stages.values():
        m = binding["manifest"]
        operations[m["id"]] = Operation(
            m["id"], m["execution"]["kind"], m["description"], m["execution"]["side_effects"], None
        )
    return operations
