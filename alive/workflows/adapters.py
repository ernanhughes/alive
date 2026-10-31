"""Literal server-owned adapters. Registry binding strings are never executable authority."""

from dataclasses import dataclass, field
from types import MappingProxyType

from alive.capabilities.registry import default_registry
from alive.cognitive_schema import RoleOutput
from alive.models import now
from alive.society import evaluate, validate_references
from alive.workflows.context import bounded, digest, require


@dataclass(frozen=True)
class StageContext:
    kernel: object
    cognition: object
    run_id: str
    stage_id: str
    stage: object
    inquiry_id: str
    owner: str
    inputs: dict
    approved: dict
    dependencies: dict
    definition_hash: str
    input_hash: str
    ledger: dict = field(default_factory=dict)
    capability: dict | None = None
    resources: object | None = None


@dataclass(frozen=True)
class StageResult:
    output: dict
    evidence_refs: tuple[str, ...] = ()
    validation_status: str = "not_run"
    artifact: dict | None = None


async def prepare(ctx):
    require(not ctx.inputs, "context_prepare_has_no_ambient_inputs")
    return StageResult(
        {
            "context": ctx.approved,
            "claims": ctx.approved["claims"],
            "sources": ctx.approved["sources"],
        },
        tuple(ctx.approved["source_event_ids"]),
    )


async def role(ctx):
    require(
        set(ctx.inputs) == {"role", "context"}
        and ctx.inputs["role"] in {"observer", "proposer", "critic", "evaluator"}
        and ctx.inputs["context"] == ctx.approved,
        "approved_role_context_required",
    )
    output = await ctx.cognition.call_role(
        ctx.inquiry_id,
        ctx.inputs["role"],
        ctx.inputs["context"],
        ledger=ctx.ledger,
        output_ceiling=ctx.stage.limits.max_output_tokens,
        workflow_claim=(ctx.run_id, ctx.stage_id, ctx.owner),
    )
    return StageResult(
        {"analysis": output.model_dump()},
        tuple(sorted({ref for claim in output.claims for ref in claim.evidence_refs})),
        "passed",  # Structured/reference validation, never semantic certification.
    )


async def references(ctx):
    require(
        set(ctx.inputs) == {"analysis", "context"} and ctx.inputs["context"] == ctx.approved,
        "validation_context_scope",
    )
    output = RoleOutput.model_validate(ctx.inputs["analysis"])
    validate_references(output, ctx.approved)
    # Matching IDs is not semantic verification or an independent world observation.
    return StageResult(
        {
            "result": output.model_dump(),
            "assessment": {"contract": "citation-identity/v1", "semantic_status": "unverified"},
        },
        tuple(sorted({ref for c in output.claims for ref in c.evidence_refs})),
        "passed",
    )


async def compare(ctx):
    require(
        set(ctx.inputs) == {"claims", "sources"}
        and ctx.inputs["claims"] == ctx.approved["claims"]
        and ctx.inputs["sources"] == ctx.approved["sources"],
        "comparison_scope",
    )
    result = evaluate(ctx.inputs["claims"], [], ctx.inputs["sources"])
    return StageResult(
        {
            "result": result,
            "assessment": {
                "contract": "controlled-exact-comparison/v1",
                "semantic_status": "controlled_sources_only",
            },
        },
        tuple(source["id"] for source in ctx.approved["sources"]),
        "passed",
    )


async def record(ctx):
    require(set(ctx.inputs) == {"result", "assessment"}, "record_contract")
    require(
        any(
            item["operation"] in {"evidence.validate_references", "evidence.evaluate"}
            and item["validation_status"] == "passed"
            and item["output"] == ctx.inputs
            for item in ctx.dependencies.values()
        ),
        "independent_validation_dependency_required",
    )
    artifact = bounded(
        {
            "kind": "workflow_result",
            "schema": "workflow-result/v1",
            "run_id": ctx.run_id,
            "stage_id": ctx.stage.id,
            "definition_sha256": ctx.definition_hash,
            "input_sha256": ctx.input_hash,
            "classification": "owner_internal",
            "created_at": now().isoformat(),
            "result": ctx.inputs["result"],
            "assessment": ctx.inputs["assessment"],
            "evidence_refs": ctx.approved["source_event_ids"],
            "intelligence_episode_id": None,
            "independent_feedback": False,
        }
    )
    # The runner commits the message, result event and stage outcome together.
    return StageResult(
        {"artifact_id": ctx.stage_id, "sha256": digest(artifact)},
        tuple(ctx.approved["source_event_ids"]),
        "passed",
        artifact,
    )


# Compatibility/fault-injection seam, derived from the same catalogue. New
# manifests are resolved through the runtime registry; this is not an authority map.
ADAPTERS = MappingProxyType(
    {
        name: default_registry().adapter(name)
        for name in default_registry().operations
        if default_registry().get(name).executable
    }
)
