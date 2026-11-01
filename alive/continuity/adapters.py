import json
import re

from sqlalchemy import select

from alive.admission.models import Admission
from alive.analysis.validation import OK, check_evidence
from alive.continuity import service
from alive.continuity.context import package
from alive.continuity.contracts import ContextualAnswer, ReasoningSpec
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
            for_dispatch=True,
        )
    require(bool(inputs["context_ref"]), "frozen_context_required")
    require(digest(snapshot) == inputs["context_sha256"], "context_snapshot_integrity")
    from alive.task_review import contracts as task
    from alive.task_review.service import package as task_package

    task_mode = admission.terms.get("profile") in (task.PROFILE, task.REPAIR_PROFILE)
    assemble = task_package if task_mode else package
    data = assemble(ctx.resources, inputs["paths"], inputs["objective"], snapshot)
    require(digest(data) == inputs["model_input_sha256"], "context_model_input_changed")
    spec = (
        task.Spec(
            inputs=inputs,
            context_for=lambda _: data,
            repair=admission.terms["profile"] == task.REPAIR_PROFILE,
        )
        if task_mode
        else ReasoningSpec(inputs=inputs, context_for=lambda _: data)
    )
    output = await ctx.cognition.call_role(
        ctx.inquiry_id,
        spec.role,
        data,
        ledger=ctx.ledger,
        output_ceiling=ctx.stage.limits.max_output_tokens,
        workflow_claim=(ctx.run_id, ctx.stage_id, ctx.owner),
        spec=spec,
    )
    answer = output.model_dump(mode="json")
    if task_mode:
        answer["task_contract"] = data["task_contract"]
    return StageResult(
        {"answer": answer, "snapshot": snapshot},
        (ctx.resources.source_ref, inputs["context_ref"]),
        "not_run",
    )


README_CASES = re.compile(r"^Named input cases: (\[.*\])$", re.MULTILINE)
ADAPTATION_TYPES = ("learned_strategy", "historical_experience")


def review_cases(files):
    """Case IDs the supplied README names, if it follows the review-fixture convention."""
    readme = files.get("README.md")
    found = README_CASES.search(readme["content"]) if readme else None
    if not found:
        return None
    try:
        return [case["id"] for case in json.loads(found.group(1))] or None
    except (ValueError, KeyError, TypeError):
        return None


def contract_compliance(output, case_ids):
    """Structural obligation only. Says nothing about whether the predictions are right."""
    if case_ids is None:
        return {"required": False, "complete": True}
    given = [p.case_id for p in output.predictions]
    missing = [i for i in case_ids if i not in given]
    extra = [i for i in dict.fromkeys(given) if i not in case_ids]
    duplicate = [i for i in dict.fromkeys(given) if given.count(i) > 1]
    flag = output.issue_present is not None
    return {
        "required": True,
        "complete": not (missing or extra or duplicate) and flag,
        "missing_cases": missing,
        "unexpected_cases": extra,
        "duplicate_cases": duplicate,
        "issue_flag_present": flag,
    }


def typed_references(output, items):
    """Validate adaptation references by their actual item type.

    An ID that was never supplied is fabricated and refuses the turn. A real supplied item
    reported under the wrong type (a historical record as a strategy, a feedback record as
    history, ...) keeps the answer and is recorded under its actual type. Only a supplied
    ``learned_strategy`` is ever credited as strategy use.
    """
    actual = {i["id"]: i["source_type"] for i in items}
    strategies, historical, other, normalized = [], [], [], []
    for claimed, refs, refusal in (
        ("learned_strategy", output.lesson_ids_used, "lesson_not_supplied"),
        ("historical_experience", output.historical_ids_used, "historical_reference_not_supplied"),
    ):
        for ref in refs:
            require(ref in actual, refusal)
            kind = actual[ref]
            bucket = {"learned_strategy": strategies, "historical_experience": historical}
            bucket.get(kind, other).append(ref)
            if kind != claimed:
                normalized.append({"id": ref, "claimed_as": claimed, "actual": kind})
    unique = [list(dict.fromkeys(group)) for group in (strategies, historical, other)]
    return *unique, normalized


async def validate_answer(ctx):
    if "task_contract" in ctx.inputs["answer"]:
        from alive.task_review.adapters import validate_answer as validate_task

        return await validate_task(ctx)
    output = ContextualAnswer.model_validate(ctx.inputs["answer"])
    snapshot = ctx.inputs["snapshot"]
    ids = {item["id"] for item in snapshot["items"]}
    require(set(output.recalled_item_ids) <= ids, "context_reference_not_supplied")
    strategies, historical, other, normalized = typed_references(output, snapshot["items"])
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
    compliance = contract_compliance(output, review_cases(files))
    value = output.model_dump(mode="json") | {
        "recalled_item_ids": list(dict.fromkeys([*output.recalled_item_ids, *other])),
        "lesson_ids_used": strategies,
        "historical_ids_used": historical,
        "schema": "contextual-answer/v2",
        "context_ref": ctx.inputs["context_ref"],
        "context_sha256": digest(snapshot),
        "source_ref": ctx.resources.source_ref,
        "citation_checks": citations,
        "contract_compliance": compliance,
        "reference_integrity": {"status": "normalized" if normalized else "valid"}
        | ({"normalized": normalized} if normalized else {}),
    }
    return StageResult(
        {
            "result": value,
            "assessment": {
                "semantic_status": "unverified",
                "independent_verification": False,
                "citations_match": all(c["status"] in OK for c in citations),
                "context_references_valid": True,
                "contract_complete": compliance["complete"],
            },
        },
        (ctx.resources.source_ref, ctx.inputs["context_ref"]),
        "passed",
    )
