"""Trusted stage adapters for the repository-analysis workflow (code-owned, fingerprinted)."""

from alive.analysis.context import context_package
from alive.analysis.contracts import ROLE, AnalysisSpec
from alive.analysis.validation import validate_analysis
from alive.workflows.adapters import StageResult
from alive.workflows.context import require


def captured_files(source):
    return {f["path"]: f for f in source.content["files"]}


async def analyze(ctx):
    """One governed model call over exactly the owner-approved captured files.

    Custody was re-verified for the `repository.analyze` disclosure operation when this stage
    started. Here the supplied bytes are bound again to the approved capture, so an upstream
    stage output cannot introduce text the owner never approved.
    """
    source, inputs = ctx.resources, dict(ctx.inputs)
    require(
        source is not None
        and source.source_type == "repository"
        and inputs["source_ref"] == source.source_ref
        and inputs["source_sha256"] == source.content_sha256
        and inputs["scoped_sha256"] == source.scoped_sha256,
        "analysis_source_identity",
    )
    approved = captured_files(source)
    require(
        all(
            approved.get(f["path"], {}).get("content") == f["content"]
            and approved[f["path"]]["sha256"] == f["sha256"]
            for f in inputs["files"]
        ),
        "analysis_input_not_in_approved_capture",
    )
    context = context_package(inputs)  # raises on truncation, byte ceiling or empty selection
    spec = AnalysisSpec(inputs=inputs, context_for=context_package)
    output = await ctx.cognition.call_role(
        ctx.inquiry_id,
        ROLE,
        context,
        ledger=ctx.ledger,
        output_ceiling=ctx.stage.limits.max_output_tokens,
        workflow_claim=(ctx.run_id, ctx.stage_id, ctx.owner),
        spec=spec,
    )
    # Schema-valid model output. Citations are unchecked here and the claims are unverified.
    return StageResult(
        {"analysis": output.model_dump(mode="json")}, (source.source_ref,), "not_run"
    )


async def validate_findings(ctx):
    result, assessment = validate_analysis(ctx.inputs["analysis"], ctx.inputs)
    return StageResult(
        {"result": result, "assessment": assessment},
        (result["source"]["source_ref"],),
        "passed",  # the citation-existence procedure ran; each finding carries its own outcome
    )
