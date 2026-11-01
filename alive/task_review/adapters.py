from pydantic import ValidationError

from alive.task_review import contracts, service, validation
from alive.workflows.adapters import StageResult
from alive.workflows.context import digest, require


async def validate_answer(ctx):
    snapshot, envelope = ctx.inputs["snapshot"], ctx.inputs["answer"]
    contract = envelope["task_contract"]
    paths = sorted(f["path"] for f in ctx.resources.content["files"])
    data = service.package(ctx.resources, paths, contract["requested_task"], snapshot)
    require(data["task_contract"] == contract, "task_contract_changed")
    files = {f["path"]: f for f in ctx.resources.content["files"]}
    contract, candidate = data["task_contract"], envelope["candidate"]
    raw_candidate = candidate
    rejection = None
    repair = snapshot.get("completion_repair")
    if repair:
        candidate, completion, rejection = validation.patch(
            repair["original_candidate"],
            candidate,
            contract,
            files,
            snapshot["items"],
            original_sha256=repair["original_sha256"],
        )
    else:
        completion = validation.validate(candidate, contract, files, snapshot["items"])
    try:
        (contracts.Repair if repair else contracts.Review).model_validate(raw_candidate)
        response_schema_valid = True
    except ValidationError:
        response_schema_valid = False
    accepted = completion["accepted"]
    candidate_id = digest(
        {
            "contract": contract["sha256"],
            "raw": envelope["raw_text"],
            "parent": repair["original_sha256"] if repair else None,
        }
    )
    value = {
        "schema": "code-review-result/v1",
        "contract": contract,
        "candidate_id": candidate_id,
        "parent_candidate_id": repair["original_sha256"] if repair else None,
        "raw_text": envelope["raw_text"],
        "raw_candidate": raw_candidate,
        "candidate": candidate,
        "completion": completion,
        "repair_rejection": rejection,
        "transport_completed": True,
        "response_schema_valid": response_schema_valid,
        "schema_valid": completion["schema_valid"],
        "task_complete": completion["task_complete"],
        "semantically_verified": False,
        "context_sha256": digest(snapshot),
        "source_ref": ctx.resources.source_ref,
        "answer": accepted.get(
            "explanation", "Incomplete code-review response; inspect retained candidate."
        ),
        "citations": accepted.get("citations", []),
        "recalled_item_ids": [],
        "lesson_ids_used": [],
        "historical_ids_used": [],
        "revision": None,
        "uncertainty": [],
    }
    ids = set(accepted.get("reference_ids", []))
    for item in snapshot["items"]:
        if item["id"] in ids:
            key = {
                "learned_strategy": "lesson_ids_used",
                "historical_experience": "historical_ids_used",
            }.get(item["source_type"], "recalled_item_ids")
            value[key].append(item["id"])
    return StageResult(
        {
            "result": value,
            "assessment": {
                "contract_complete": completion["task_complete"],
                "semantic_status": "unverified",
                "independent_verification": False,
            },
        },
        (ctx.resources.source_ref, ctx.inputs["context_ref"]),
        "passed",
    )
