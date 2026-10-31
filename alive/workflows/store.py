"""Registration and records for workflows (ALIVE-PI-02A). No execution, no scheduler.

Authority boundary: definitions are registered ONLY by code running inside the ALIVE process
(`seed_builtin` at startup, or a trusted caller such as a test or a later admin tool). There is no
HTTP write path. A registration is validated, canonicalised and hashed; a (name, version) pair is
immutable, so registering the same bytes again is a no-op and different bytes are refused.
"""

from datetime import UTC
from importlib import resources

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from alive.capabilities.bindings import bind_definition, registry_for
from alive.capabilities.trusted import LEGACY_DEFINITION_SHA256
from alive.models import now, uid
from alive.workflows import states
from alive.workflows.models import WorkflowDefinition, WorkflowRun, WorkflowStageRun
from alive.workflows.spec import (
    SCHEMA_VERSION,
    DefinitionError,
    canonical_dict,
    check_activatable,
    definition_sha256,
    hash_of_stored,
    parse_definition,
)


class WorkflowConflict(Exception):
    """(name, version) already holds different content, or a status change is not allowed."""


class UnknownWorkflow(KeyError):
    pass


# --- views: explicit field lists, so a new column is never exposed by accident ---


def definition_view(row, *, full=False):
    stages = row.definition_json.get("stages", [])
    view = {
        "id": row.id,
        "name": row.name,
        "version": row.version,
        "schema_version": row.schema_version,
        "title": row.title,
        "description": row.description,
        "status": row.status,
        "source": row.source,
        "stage_count": len(stages),
        "definition_sha256": row.definition_sha256,
        # Re-derived on every read: a stored definition that no longer matches its hash says so.
        "integrity": {"verified": hash_of_stored(row.definition_json) == row.definition_sha256},
        "created_at": row.created_at.isoformat(),
        "status_updated_at": row.status_updated_at.isoformat(),
    }
    if full:
        view["definition"] = row.definition_json
    return view


def _iso(value):
    return value.isoformat() if value else None


def run_view(row):
    return {
        "id": row.id,
        "workflow": {
            "name": row.workflow_name,
            "version": row.workflow_version,
            "definition_id": row.definition_id,
            "definition_sha256": row.definition_sha256,
            "schema_version": row.schema_version,
        },
        "goal_id": row.goal_id,
        "investigation_id": row.investigation_id,
        "trigger": row.trigger,
        "input_ref": row.input_ref,
        "input_sha256": row.input_sha256,
        "authorization_ref": row.authorization_ref,
        "budget": row.budget_json,
        "status": row.status,
        "terminal": row.status in states.RUN_TERMINAL,
        "terminal_reason": row.terminal_reason,
        "created_at": _iso(row.created_at),
        "started_at": _iso(row.started_at),
        "finished_at": _iso(row.finished_at),
    }


def validation_view(row):
    """Passed is a contract check, never a truth or workflow-completion claim."""
    checked = row.validation_status == "passed"
    return {
        "contract_status": row.validation_status,
        "structural_status": "passed" if checked else "not_established",
        "reference_identity_status": (
            "passed"
            if checked and row.operation in {"cognition.role", "evidence.validate_references"}
            else "not_established"
        ),
        "semantic_status": "unverified",
        "independent_verification": False,
        "uncited_claims_permitted": True,
    }


def stage_view(row):
    return {
        "id": row.id,
        "run_id": row.run_id,
        "stage_id": row.stage_id,
        "attempt": row.attempt,
        "type": row.stage_type,
        "operation": row.operation,
        "state": row.state,
        "terminal": row.state in states.STAGE_TERMINAL,
        "input_ref": row.input_ref,
        "input_sha256": row.input_sha256,
        "output_ref": row.output_ref,
        "output_sha256": row.output_sha256,
        "pi_run_id": row.pi_run_id,
        "model_invocation_id": row.model_invocation_id,
        "evidence_refs": row.evidence_refs,
        "validation_status": row.validation_status,
        "validation": validation_view(row),
        "error_category": row.error_category,
        "error_detail": row.error_detail,
        "uncertainty": row.uncertainty,
        "created_at": _iso(row.created_at),
        "started_at": _iso(row.started_at),
        "finished_at": _iso(row.finished_at),
        "duration_seconds": (
            row.finished_at.replace(tzinfo=UTC) - row.started_at.replace(tzinfo=UTC)
        ).total_seconds()
        if row.started_at and row.finished_at
        else None,
    }


# --- definitions ----------------------------------------------------------------------------------


async def register_definition(kernel, raw, *, status="draft", source="admin"):
    """Validate, canonicalise and store a definition. Returns (view, created).

    Idempotent for identical content; a different definition under an existing (name, version)
    raises WorkflowConflict. An `active` definition must use only operations that can run.
    """
    spec = parse_definition(raw, operations=registry_for(kernel).operations)
    if status not in ("draft", "active"):
        raise DefinitionError([f"a definition is registered as draft or active, not {status!r}"])
    if status == "active":
        check_activatable(spec, registry_for(kernel).operations)
    content = canonical_dict(spec)
    digest = definition_sha256(spec)
    for attempt in (1, 2):
        try:
            async with kernel.lock, kernel.db.sessions.begin() as session:
                existing = await session.scalar(
                    select(WorkflowDefinition).where(
                        WorkflowDefinition.name == spec.name,
                        WorkflowDefinition.version == spec.version,
                    )
                )
                if existing is not None:
                    if existing.definition_sha256 != digest:
                        raise WorkflowConflict(
                            f"{spec.name} v{spec.version} already exists with different content; "
                            "register a new version instead"
                        )
                    # A row that exists without a binding predates migration 0011: genuinely
                    # historical, so it may be adopted under its original DAG-only contract.
                    await bind_definition(session, kernel, existing, spec, adopt_legacy=True)
                    return definition_view(existing), False
                row = WorkflowDefinition(
                    id=uid(),
                    name=spec.name,
                    version=spec.version,
                    schema_version=SCHEMA_VERSION,
                    title=spec.title,
                    description=spec.description,
                    definition_json=content,
                    definition_sha256=digest,
                    status=status,
                    source=source,
                )
                session.add(row)
                await session.flush()
                kernel.add_event(
                    session,
                    "workflow.definition.registered",
                    {
                        "definition_id": row.id,
                        "name": row.name,
                        "version": row.version,
                        "definition_sha256": digest,
                        "status": status,
                        "source": source,
                    },
                    source="workflow",
                    correlation=row.id,
                )
                await bind_definition(
                    session, kernel, row, spec, adopt_legacy=digest in LEGACY_DEFINITION_SHA256
                )
                return definition_view(row), True
        except IntegrityError:
            # Lost a race for the same (name, version): re-read and decide on the winner's bytes.
            if attempt == 2:
                raise
    raise AssertionError("unreachable")


async def set_status(kernel, name, version, new_status):
    """Lifecycle metadata only; the hashed content never changes. draft -> active needs all
    operations available."""
    async with kernel.lock, kernel.db.sessions.begin() as session:
        row = await _definition(session, name, version)
        if new_status not in states.DEFINITION_TRANSITIONS.get(row.status, ()):
            raise WorkflowConflict(f"{row.status} -> {new_status} is not allowed")
        if new_status == "active":
            registry = registry_for(kernel)
            check_activatable(
                parse_definition(row.definition_json, operations=registry.operations),
                registry.operations,
            )
        row.status, row.status_updated_at = new_status, now()
        kernel.add_event(
            session,
            "workflow.definition.status",
            {"definition_id": row.id, "name": name, "version": version, "status": new_status},
            source="workflow",
            correlation=row.id,
        )
        return definition_view(row)


async def _definition(session, name, version):
    row = await session.scalar(
        select(WorkflowDefinition).where(
            WorkflowDefinition.name == name, WorkflowDefinition.version == version
        )
    )
    if row is None:
        raise UnknownWorkflow(f"{name} v{version}")
    return row


def builtin_definitions():
    """Definitions shipped with ALIVE, read from package data (reviewed code, not user input)."""
    folder = resources.files("alive.workflows") / "builtin"
    for entry in sorted(folder.iterdir(), key=lambda item: item.name):
        if entry.name.endswith(".json"):
            yield entry.name, entry.read_text(encoding="utf-8")


async def seed_builtin(kernel):
    """Register the shipped definitions. Idempotent. A conflict (the stored bytes differ from the
    shipped ones) is reported, never overwritten, and never stops startup."""
    results = []
    for filename, text in builtin_definitions():
        try:
            try:
                check_activatable(parse_definition(text))
                status = "active"  # every operation it names can run
            except DefinitionError:
                status = (
                    "draft"  # it names an unavailable operation (or is invalid: re-raised below)
                )
            view, created = await register_definition(kernel, text, status=status, source="builtin")
            results.append((filename, "created" if created else "unchanged"))
        except (WorkflowConflict, DefinitionError) as exc:
            results.append((filename, f"refused: {exc}"))
    return results


# --- reads ----------------------------------------------------------------------------------------


async def list_definitions(kernel, name=None):
    async with kernel.db.sessions() as session:
        query = select(WorkflowDefinition).order_by(
            WorkflowDefinition.name, WorkflowDefinition.version.desc()
        )
        if name:
            query = query.where(WorkflowDefinition.name == name)
        return [definition_view(row) for row in (await session.scalars(query)).all()]


async def get_definition(kernel, name, version):
    async with kernel.db.sessions() as session:
        return definition_view(await _definition(session, name, version), full=True)


async def list_runs(kernel, *, workflow=None, status=None, limit=50):
    async with kernel.db.sessions() as session:
        query = (
            select(WorkflowRun)
            .where(WorkflowRun.instance_id == kernel.instance_id)
            .order_by(WorkflowRun.created_at.desc(), WorkflowRun.id)
            .limit(limit)
        )
        if workflow:
            query = query.where(WorkflowRun.workflow_name == workflow)
        if status:
            query = query.where(WorkflowRun.status == status)
        return [run_view(row) for row in (await session.scalars(query)).all()]


async def get_run(kernel, run_id):
    async with kernel.db.sessions() as session:
        row = await session.get(WorkflowRun, run_id)
        if row is None or row.instance_id != kernel.instance_id:
            raise UnknownWorkflow(run_id)
        return run_view(row)


async def get_stage_runs(kernel, run_id):
    async with kernel.db.sessions() as session:
        run = await session.get(WorkflowRun, run_id)
        if run is None or run.instance_id != kernel.instance_id:
            raise UnknownWorkflow(run_id)
        from alive.capabilities.bindings import retained

        try:
            capabilities = await retained(session, kernel, run)
        except (ValueError, TypeError, KeyError):
            raise UnknownWorkflow(run_id) from None
        rows = await session.scalars(
            select(WorkflowStageRun)
            .where(WorkflowStageRun.run_id == run_id)
            .order_by(
                WorkflowStageRun.created_at, WorkflowStageRun.stage_id, WorkflowStageRun.attempt
            )
        )
        from alive.cognitive_models import ModelInvocation

        views = []
        for row in rows.all():
            view = stage_view(row)
            if capabilities:
                binding = capabilities.get(row.stage_id)
                if not binding or binding["identity"]["id"] != row.operation:
                    raise UnknownWorkflow(run_id)
                view["capability"] = binding["identity"]
            call = (
                await session.get(ModelInvocation, row.model_invocation_id)
                if row.model_invocation_id
                else None
            )
            if call is not None and call.investigation_id != run.investigation_id:
                raise UnknownWorkflow(run_id)
            fields = ("prompt_tokens", "completion_tokens", "total_tokens")
            usage = call.usage if call else {}
            view.update(
                {
                    "model_requested": call.model if call else None,
                    "usage": {key: usage[key] for key in fields}
                    if all(type(usage.get(key)) is int for key in fields)
                    else None,
                    "charged_tokens": usage.get("charged_tokens"),
                    "cost_usd": None,
                    "cost_status": "no_price_table; unknown is not zero",
                }
            )
            views.append(view)
        return views


async def count_runs(kernel):
    async with kernel.db.sessions() as session:
        return await session.scalar(select(func.count()).select_from(WorkflowRun))


# --- run and stage RECORDS (no scheduler: PI-02B drives these transitions) ------------------------


async def open_run(
    kernel,
    name,
    version,
    *,
    input_ref=None,
    input_sha256=None,
    goal_id=None,
    investigation_id=None,
    trigger="manual",
    authorization_ref=None,
    budget=None,
    idempotency_key=None,
):
    """Create a PENDING run and one PENDING record per stage. The definition must be `active`."""
    async with kernel.lock, kernel.db.sessions.begin() as session:
        definition = await _definition(session, name, version)
        if definition.status != "active":
            raise WorkflowConflict(f"{name} v{version} is {definition.status}; only active runs")
        if idempotency_key:
            prior = await session.scalar(
                select(WorkflowRun).where(WorkflowRun.idempotency_key == idempotency_key)
            )
            if prior is not None:
                if prior.definition_id != definition.id:
                    raise WorkflowConflict("idempotency key belongs to a different workflow")
                return run_view(prior), False
        return await create_run(
            session,
            kernel,
            definition,
            input_ref=input_ref,
            input_sha256=input_sha256,
            goal_id=goal_id,
            investigation_id=investigation_id,
            trigger=trigger,
            authorization_ref=authorization_ref,
            budget=budget,
            idempotency_key=idempotency_key,
        )


async def create_run(
    session,
    kernel,
    definition,
    *,
    input_ref=None,
    input_sha256=None,
    goal_id=None,
    investigation_id=None,
    trigger="manual",
    authorization_ref=None,
    budget=None,
    idempotency_key=None,
):
    """Shared row/event construction inside a caller-owned transaction."""
    run = WorkflowRun(
        id=uid(),
        instance_id=kernel.instance_id,
        definition_id=definition.id,
        workflow_name=definition.name,
        workflow_version=definition.version,
        definition_sha256=definition.definition_sha256,
        schema_version=definition.schema_version,
        goal_id=goal_id,
        investigation_id=investigation_id,
        trigger=trigger,
        input_ref=input_ref,
        input_sha256=input_sha256,
        authorization_ref=authorization_ref,
        budget_json=budget or {},
        idempotency_key=idempotency_key,
    )
    session.add(run)
    await session.flush()
    for stage in definition.definition_json["stages"]:
        session.add(
            WorkflowStageRun(
                id=uid(),
                run_id=run.id,
                stage_id=stage["id"],
                stage_type=stage["type"],
                operation=stage["operation"],
            )
        )
    await session.flush()
    kernel.add_event(
        session,
        "workflow.run.opened",
        {
            "run_id": run.id,
            "name": run.workflow_name,
            "version": run.workflow_version,
            "definition_sha256": run.definition_sha256,
        },
        source="workflow",
        correlation=run.id,
    )
    return run_view(run), True


async def advance_run(kernel, run_id, new_state, *, reason=None):
    async with kernel.lock, kernel.db.sessions.begin() as session:
        run = await session.get(WorkflowRun, run_id)
        if run is None:
            raise UnknownWorkflow(run_id)
        run.status = states.advance(run.status, new_state, states.RUN_TRANSITIONS)
        if new_state == states.RUNNING and run.started_at is None:
            run.started_at = now()
        if new_state in states.RUN_TERMINAL:
            run.finished_at, run.terminal_reason = now(), reason
        kernel.add_event(
            session,
            f"workflow.run.{new_state.lower()}",
            {"run_id": run.id, "reason": reason},
            source="workflow",
            correlation=run.id,
        )
        return run_view(run)


async def advance_stage(kernel, run_id, stage_id, new_state, *, attempt=1, **fields):
    allowed = {
        "input_ref", "input_sha256", "output_ref", "output_sha256", "pi_run_id",
        "model_invocation_id", "evidence_refs", "validation_status", "error_category",
        "error_detail", "uncertainty",
    }  # fmt: skip
    if set(fields) - allowed:
        raise ValueError(f"cannot set {sorted(set(fields) - allowed)} on a stage record")
    async with kernel.lock, kernel.db.sessions.begin() as session:
        stage = await session.scalar(
            select(WorkflowStageRun).where(
                WorkflowStageRun.run_id == run_id,
                WorkflowStageRun.stage_id == stage_id,
                WorkflowStageRun.attempt == attempt,
            )
        )
        if stage is None:
            raise UnknownWorkflow(f"{run_id}/{stage_id}#{attempt}")
        stage.state = states.advance(stage.state, new_state, states.STAGE_TRANSITIONS)
        for name, value in fields.items():
            setattr(stage, name, value)
        if new_state == states.RUNNING and stage.started_at is None:
            stage.started_at = now()
        if new_state in states.STAGE_TERMINAL:
            stage.finished_at = now()
        return stage_view(stage)


def operation_listing(kernel=None):
    from alive.workflows.operations import public_view

    return [public_view(operation) for operation in registry_for(kernel).operations.values()]
