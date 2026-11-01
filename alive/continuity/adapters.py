from sqlalchemy import select

from alive.admission.models import Admission
from alive.analysis.validation import OK, check_evidence
from alive.continuity import service
from alive.continuity.context import package
from alive.continuity.contracts import ROLE, ContextualAnswer, ReasoningSpec
from alive.workflows.adapters import StageResult
from alive.workflows.context import digest, require


async def reason(ctx):
    inputs = dict(ctx.inputs)
    async with ctx.kernel.db.sessions() as session:
        admission = await session.scalar(select(Admission).where(Admission.run_id == ctx.run_id))
        require(admission is not None, "context_admission_required")
        snapshot = await service.frozen(
            session,
            ctx.kernel,
            inputs["context_ref"],
            admission.terms["source"]["resources"],
            admission.principal,
        )
    require(bool(inputs["context_ref"]), "frozen_context_required")
    require(digest(snapshot) == inputs["context_sha256"], "context_snapshot_integrity")
    data = package(ctx.resources, inputs["paths"], inputs["objective"], snapshot)
    require(digest(data) == inputs["model_input_sha256"], "context_model_input_changed")
    spec = ReasoningSpec(inputs=inputs, context_for=lambda _: data)
    output = await ctx.cognition.call_role(
        ctx.inquiry_id,
        ROLE,
        data,
        ledger=ctx.ledger,
        output_ceiling=ctx.stage.limits.max_output_tokens,
        workflow_claim=(ctx.run_id, ctx.stage_id, ctx.owner),
        spec=spec,
    )
    return StageResult(
        {"answer": output.model_dump(mode="json"), "snapshot": snapshot},
        (ctx.resources.source_ref, inputs["context_ref"]),
        "not_run",
    )


async def validate_answer(ctx):
    output = ContextualAnswer.model_validate(ctx.inputs["answer"])
    snapshot = ctx.inputs["snapshot"]
    ids = {item["id"] for item in snapshot["items"]}
    require(set(output.recalled_item_ids) <= ids, "context_reference_not_supplied")
    for item in snapshot["items"]:
        require(digest(item["content"]) == item["content_sha256"], "context_item_integrity")
    if output.revision:
        model_ids = {i["id"] for i in snapshot["items"] if i["source_type"] != "owner_goal"}
        require(set(output.revision.supersedes) <= model_ids, "revision_target_not_supplied")
        require(
            set(output.revision.supersedes) <= set(output.recalled_item_ids),
            "revision_target_not_recalled",
        )
    files = {f["path"]: f for f in ctx.resources.content["files"]}
    citations = [check_evidence(e, files) for e in output.citations]
    value = output.model_dump(mode="json") | {
        "schema": "contextual-answer/v1",
        "context_ref": ctx.inputs["context_ref"],
        "context_sha256": digest(snapshot),
        "source_ref": ctx.resources.source_ref,
        "citation_checks": citations,
    }
    return StageResult(
        {
            "result": value,
            "assessment": {
                "semantic_status": "unverified",
                "independent_verification": False,
                "citations_match": all(c["status"] in OK for c in citations),
                "context_references_valid": True,
            },
        },
        (ctx.resources.source_ref, ctx.inputs["context_ref"]),
        "passed",
    )
