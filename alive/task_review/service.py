"""Freeze task metadata after existing context selection; no new selection or persistence engine."""

import json

from sqlalchemy import select

from alive.admission.models import Admission
from alive.continuity import service as continuity
from alive.continuity.context import package as contextual_package
from alive.models import Event
from alive.task_review import contracts
from alive.workflows.context import digest, require

PROFILES = (contracts.PROFILE, contracts.REPAIR_PROFILE)


def package(source, paths, goal, snapshot):
    # The old 6KB bound still applies to selected memory. Task/repair data has its own bound.
    memory = {k: v for k, v in snapshot.items() if k not in ("task_request", "completion_repair")}
    data = contextual_package(source, paths, goal, memory)
    requested = snapshot.get("task_request", {})
    cases = requested.get("case_ids")
    if cases is None:
        readme = next(
            (f["content"] for f in source.content["files"] if f["path"] == "README.md"), ""
        )
        declarations = [
            line.removeprefix("Named input cases:").strip()
            for line in readme.splitlines()
            if line.startswith("Named input cases:")
        ]
        require(len(declarations) <= 1, "ambiguous_declared_task_cases")
        cases = []
        if declarations:
            try:
                rows = json.loads(declarations[0])
                require(isinstance(rows, list), "invalid_declared_task_cases")
                cases = [row["id"] for row in rows]
            except (ValueError, TypeError, KeyError):
                require(False, "invalid_declared_task_cases")
    require(
        isinstance(cases, list)
        and len(cases) <= 8
        and all(isinstance(c, str) and 1 <= len(c) <= 40 for c in cases)
        and len(set(cases)) == len(cases),
        "invalid_declared_task_cases",
    )
    body = {
        "task": "code_review",
        "version": 1,
        "requested_task": goal,
        "task_id": digest([source.source_ref, goal, cases]),
        "source": {
            "source_ref": source.source_ref,
            "approval_id": source.approval_id,
            "content_sha256": source.content_sha256,
            "scoped_sha256": source.scoped_sha256,
        },
        "files": [{"path": f["path"], "sha256": f["sha256"]} for f in source.content["files"]],
        "case_ids": cases,
        "required_outputs": list(contracts.Review.model_fields),
        "uncertainty": "Typed undetermined with reason; complete does not mean solved",
        "verification": "Independent semantic checker required; citations are insufficient",
        "completion": "Every case exactly once; typed values/decision and valid references",
    }
    contract = body | {"sha256": digest(body)}
    data = data | {"conversation": snapshot, "task_contract": contract}
    if "completion_repair" in snapshot:
        data["repair"] = snapshot["completion_repair"]
    require(len(json.dumps(data).encode()) <= 24000, "task_model_input_too_large")
    return data


def request_identity(request):
    return (
        {
            "mode": request.task_mode,
            "case_ids": request.task_case_ids,
            "repair_requested": request.repair_incomplete,
        }
        if request.task_mode == "code_review"
        else None
    )


async def validate_request_retry(session, kernel, request):
    if not request.conversation_ref:
        return
    previous = await session.scalar(
        select(Event).where(
            Event.instance_id == kernel.instance_id,
            Event.source == continuity.SOURCE,
            Event.event_type == continuity.SNAPSHOT,
            Event.correlation_id == request.conversation_ref,
            Event.payload["request_key"].as_string() == request.idempotency_key,
        )
    )
    if previous:
        require(
            previous.payload.get("task_request") == request_identity(request), "task_retry_conflict"
        )


async def freeze(kernel, request, approved, base_ref, *, original_id=None):
    async with kernel.lock, kernel.db.sessions.begin() as session:
        opened = await continuity.conversation(session, kernel, request.conversation_ref, approved)
        base = await continuity.frozen(
            session,
            kernel,
            base_ref,
            opened.payload["resources"],
            opened.payload["principal"],
            approved["id"],
        )
        snapshot = base | {
            "task_request": {
                "case_ids": request.task_case_ids,
                "repair_requested": request.repair_incomplete,
            }
        }
        if original_id:
            admission = await session.get(Admission, original_id)
            stored = await continuity.artifact(session, kernel, admission)
            require(
                stored is not None and admission.terms.get("profile") == contracts.PROFILE,
                "original_task_result_required",
            )
            original = stored["result"]
            snapshot["completion_repair"] = {
                "original_admission_id": original_id,
                "artifact_sha256": stored["sha256"],
                "original_sha256": original["candidate_id"],
                "original_candidate": original["candidate"],
                "raw_text": original["raw_text"],
                "errors": original["completion"]["errors"],
                "allowed_fields": original["completion"]["allowed_repair_fields"],
            }
        key = request.idempotency_key + (":task-repair" if original_id else ":task")
        previous = await session.scalar(
            select(Event).where(
                Event.instance_id == kernel.instance_id,
                Event.source == continuity.SOURCE,
                Event.event_type == continuity.SNAPSHOT,
                Event.correlation_id == opened.id,
                Event.payload["request_key"].as_string() == key,
            )
        )
        if previous:
            require(
                previous.payload["snapshot"] == snapshot
                and previous.payload["goal"] == request.goal,
                "task_retry_conflict",
            )
            return previous.id
        require(len(json.dumps(snapshot).encode()) <= 18000, "task_snapshot_too_large")
        row = kernel.add_event(
            session,
            continuity.SNAPSHOT,
            {
                "request_key": key,
                "goal": request.goal,
                "snapshot": snapshot,
                "sha256": digest(snapshot),
                "continuation": True,
            },
            source=continuity.SOURCE,
            correlation=opened.id,
        )
        await session.flush()
        return str(row.event_id)


async def validate_repair_source(session, kernel, snapshot, resources, principal):
    repair = snapshot.get("completion_repair")
    if not repair:
        return
    original = await session.get(Admission, repair["original_admission_id"])
    require(
        original is not None
        and original.instance_id == kernel.instance_id
        and original.principal == principal
        and original.terms["source"]["resources"] == resources
        and original.terms.get("profile") == contracts.PROFILE,
        "task_repair_scope_changed",
    )
    artifact = await continuity.artifact(session, kernel, original)
    require(
        artifact is not None
        and artifact["sha256"] == repair["artifact_sha256"]
        and artifact["result"]["candidate_id"] == repair["original_sha256"]
        and artifact["result"]["candidate"] == repair["original_candidate"]
        and artifact["result"]["raw_text"] == repair["raw_text"]
        and artifact["result"]["completion"]["errors"] == repair["errors"]
        and artifact["result"]["completion"]["allowed_repair_fields"] == repair["allowed_fields"],
        "task_repair_candidate_changed",
    )
    original_ref = original.terms["proposed_grant_data"]["inputs"]["context_ref"]
    prior = await continuity.event(session, kernel, original_ref, continuity.SNAPSHOT)
    require(
        {k: v for k, v in snapshot.items() if k != "completion_repair"}
        == prior.payload["snapshot"],
        "task_repair_context_changed",
    )


def binding(call, stage, grant):
    repair = call.role == contracts.REPAIR_ROLE
    stored, data = call.input_json, call.input_json["context"]
    body = {k: v for k, v in data["task_contract"].items() if k != "sha256"}
    return (
        stored["instructions"]
        == (contracts.REPAIR_INSTRUCTIONS if repair else contracts.INSTRUCTIONS)
        and grant.role_contracts.get(call.role) == contracts.role_contract(repair)
        and digest(body) == data["task_contract"]["sha256"]
        and stored.get("context_sha256") == digest(data) == grant.inputs["model_input_sha256"]
        and data["user_goal"] == grant.inputs["objective"]
        and digest(data["conversation"]) == grant.inputs["context_sha256"]
        and data["source"]["source"]["source_sha256"]
        == grant.capabilities[stage.stage_id]["resources"]["content_sha256"]
    )
