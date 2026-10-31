"""Bounded calls through the existing runner; this module owns no execution state."""

import asyncio
import json
from dataclasses import dataclass, field, replace

import alive.sources.models  # noqa: F401  (registers the custody tables)
from alive.capabilities.contracts import json_bytes, validate
from alive.capabilities.trusted import permission_bits
from alive.workflows.context import require


@dataclass(frozen=True)
class ReadCapabilityContext:
    run_id: str
    stage_id: str
    inquiry_id: str
    owner: str
    resources: object
    inputs: dict = field(default_factory=dict)
    limits: dict = field(default_factory=dict)


async def invoke(registry, binding, grant, context):
    cap = registry.check_grant(binding, grant)
    manifest = cap.manifest
    limits = grant["limits"]
    validate(context.inputs, manifest["inputs"])
    size = len(json_bytes(context.inputs))
    if (
        "evidence.read" in permission_bits(manifest["permissions"])
        and context.inputs.get("context") != context.approved
    ):
        size += len(json_bytes(context.approved))
    require(
        size <= limits["max_input_bytes"] and len(context.inputs) <= limits["max_input_items"],
        "capability_input_limit",
    )
    resources = None
    bits = permission_bits(manifest["permissions"])
    if "repository.read" in bits:
        from alive.capabilities.repository import reader_for

        resources = reader_for(registry, grant, context.inputs)
    elif "source.read" in bits:
        # Custody is re-verified now, not when the grant was minted: a withdrawal, an expiry or a
        # changed capture takes effect for a grant that already exists.
        from alive.sources import custody

        resources = await custody.resolve(context.kernel, grant["resources"], cap.identity["id"])
        require(
            resources.source_type in manifest["supported_source_types"], "source_type_not_supported"
        )
        require(context.inputs.get("source_ref") == resources.source_ref, "source_ref_not_approved")
    if manifest["execution"]["kind"] == "pi_agent":
        require(
            limits["max_model_calls"] == 1
            and context.stage.limits.max_output_tokens <= limits["max_output_tokens"],
            "capability_model_ceiling",
        )
    call_context = replace(context, capability=cap.identity, resources=resources)
    if resources is not None and manifest["execution"]["kind"] != "pi_agent":
        call_context = ReadCapabilityContext(
            context.run_id,
            context.stage_id,
            context.inquiry_id,
            context.owner,
            resources,
            dict(context.inputs) if "source.read" in bits else {},
            dict(limits) if "source.read" in bits else {},
        )
    # No caller-supplied callback exists: the implementation is the one this identity names.
    callback = registry.adapter_for(cap.identity)
    async with asyncio.timeout(limits["timeout_seconds"]):
        return await callback(call_context)


def checked_result(registry, binding, grant, result):
    from alive.workflows.adapters import StageResult

    cap = registry.check_grant(binding, grant)
    require(isinstance(result, StageResult), "capability_result_type")
    require(
        result.artifact is None or grant["permissions"]["persistence"] == "workflow_result",
        "capability_writer_not_authorized",
    )
    validate(result.output, cap.manifest["outputs"])
    require(
        len(result.evidence_refs) <= 256
        and all(type(ref) is str and len(ref) <= 256 for ref in result.evidence_refs),
        "capability_evidence_reference_limit",
    )
    envelope = {
        "output": result.output,
        "artifact": result.artifact,
        "evidence_refs": list(result.evidence_refs),
        "validation_status": result.validation_status,
    }
    blob = json_bytes(envelope)
    require(len(blob) <= grant["limits"]["max_output_bytes"], "capability_output_limit")
    # Detach the persisted value from mutable dictionaries held by adapter code.
    captured = json.loads(blob)
    return StageResult(
        captured["output"],
        tuple(captured["evidence_refs"]),
        captured["validation_status"],
        captured["artifact"],
    )
