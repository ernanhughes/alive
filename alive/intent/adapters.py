"""Trusted stage adapters for the intent-interpretation workflow (code-owned, fingerprinted)."""

from alive.bespoke.recipes import load_catalogue
from alive.intent.context import catalogue_sha256, context_package, project_catalogue
from alive.intent.contracts import ROLE, SCHEMA, IntentInterpretation, IntentSpec
from alive.workflows.adapters import StageResult
from alive.workflows.context import require


def source_view(source):
    """Names and sizes only. File content never enters the interpreter context."""
    files = sorted(
        ({"path": f["path"], "bytes": f["bytes"]} for f in source.content["files"]),
        key=lambda f: f["path"],
    )
    return {
        "type": source.source_type,
        "label": source.label,
        "classification": source.classification,
        "inventory": files,
    }


def package_inputs(kernel, source, goal):
    recipes = getattr(kernel, "bespoke_recipes", None) or load_catalogue()
    return {
        "user_goal": goal,
        "source": source_view(source),
        "catalogue": project_catalogue(recipes),
    }


async def interpret(ctx):
    """One governed model call: understand the goal; propose, never execute."""
    source, inputs = ctx.resources, dict(ctx.inputs)
    require(
        source is not None
        and source.source_type == "repository"
        and inputs["source_ref"] == source.source_ref,
        "intent_source_identity",
    )
    package = package_inputs(ctx.kernel, source, inputs["objective"])
    require(
        catalogue_sha256(package["catalogue"]) == inputs["catalogue_sha256"],
        "intent_catalogue_changed",
    )
    context = context_package(package)
    spec = IntentSpec(inputs=inputs, context_for=lambda _inputs: context)
    output = await ctx.cognition.call_role(
        ctx.inquiry_id,
        ROLE,
        context,
        ledger=ctx.ledger,
        output_ceiling=ctx.stage.limits.max_output_tokens,
        workflow_claim=(ctx.run_id, ctx.stage_id, ctx.owner),
        spec=spec,
    )
    return StageResult(
        {"interpretation": output.model_dump(mode="json")}, (source.source_ref,), "not_run"
    )


async def validate_interpretation(ctx):
    """Structure was checked by the schema; here the goal is compared with the owner's words."""
    interpretation = IntentInterpretation.model_validate(ctx.inputs["interpretation"])
    original = ctx.inputs["objective"]
    preserved = interpretation.explicit_goal == original
    result = {
        "schema": SCHEMA,
        "interpretation": interpretation.model_dump(mode="json"),
        "original_goal": original,
        "goal_preserved": preserved,
        "catalogue_sha256": ctx.inputs["catalogue_sha256"],
    }
    assessment = {
        "contract": SCHEMA,
        "goal_preserved": preserved,
        "origin": "model_inference",
        "semantic_status": "unverified",
        "independent_verification": False,
    }
    return StageResult(
        {"result": result, "assessment": assessment}, (ctx.inputs["catalogue_sha256"],), "passed"
    )
