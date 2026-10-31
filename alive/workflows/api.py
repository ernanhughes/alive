"""Read-only workflow inspection API (ALIVE-PI-02A). No create, run, cancel or model endpoint.

Everything here is authenticated with the same dependency as the rest of /api/v1. Responses are
built from explicit field lists and contain hashes and opaque references only: no credentials, no
run tokens, no prompt text, no file paths.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict, Field

from alive.workflows import store
from alive.workflows.spec import NAME_RE, graph_of

NAME = Path(pattern=NAME_RE.pattern, description="workflow name")
VERSION = Path(ge=1, le=1_000_000)


class ArtifactView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    artifact_id: str
    kind: Literal["workflow_result"]
    schema_version: str = Field(alias="schema")
    run_id: str
    stage_id: str
    definition_sha256: str
    input_sha256: str
    sha256: str
    classification: Literal["owner_internal"]
    created_at: str = Field(max_length=64)
    result: dict
    assessment: dict
    evidence_refs: list[str]
    intelligence_episode_id: None
    independent_feedback: Literal[False]
    source_status: Literal["withdrawn", "unchanged"]
    run_status: str
    terminal_reason: str | None
    stage_state: str
    stage_validation: dict
    stage_uncertainty: str
    workflow_completed: bool
    context_provenance: dict


def router(app, ready, pi_receipt):
    api = APIRouter(prefix="/api/v1", dependencies=[Depends(ready)])

    def kernel():
        return app.state.kernel

    async def found(awaitable):
        try:
            return await awaitable
        except store.UnknownWorkflow:
            raise HTTPException(404, "Unknown workflow or run") from None

    @api.get("/workflow-operations")
    async def operations():
        """The closed set of operations a stage may name, and which of them exist today."""
        return {"operations": store.operation_listing()}

    @api.get("/workflows")
    async def workflows():
        grouped = {}
        for view in await store.list_definitions(kernel()):  # newest version first per name
            entry = grouped.setdefault(
                view["name"],
                {"name": view["name"], "title": view["title"], "latest_version": view["version"],
                 "latest_status": view["status"], "versions": []},
            )  # fmt: skip
            entry["versions"].append(
                {k: view[k] for k in ("version", "status", "definition_sha256", "stage_count")}
            )
        return {"workflows": list(grouped.values())}

    @api.get("/workflows/{name}")
    async def workflow(name: str = NAME):
        versions = await store.list_definitions(kernel(), name)
        if not versions:
            raise HTTPException(404, "Unknown workflow or run")
        return {"name": name, "versions": versions}

    @api.get("/workflows/{name}/versions/{version}")
    async def definition(name: str = NAME, version: int = VERSION):
        return await found(store.get_definition(kernel(), name, version))

    @api.get("/workflows/{name}/versions/{version}/graph")
    async def graph(name: str = NAME, version: int = VERSION):
        """Nodes and edges derived from the stored definition. Plain data for a viewer to escape."""
        view = await found(store.get_definition(kernel(), name, version))
        return {
            "name": name,
            "version": version,
            "definition_sha256": view["definition_sha256"],
            **graph_of(view["definition"]),
        }

    @api.get("/workflow-runs")
    async def runs(
        workflow: str | None = Query(None, pattern=NAME_RE.pattern),
        status: str | None = Query(None, max_length=20),
        limit: int = Query(50, ge=1, le=200),
    ):
        return {
            "runs": await store.list_runs(kernel(), workflow=workflow, status=status, limit=limit)
        }

    @api.get("/workflow-runs/{run_id}")
    async def run(run_id: str = Path(max_length=36)):
        return await found(store.get_run(kernel(), run_id))

    @api.get("/workflow-runs/{run_id}/stages")
    async def stages(run_id: str = Path(max_length=36)):
        return {"run_id": run_id, "stages": await found(store.get_stage_runs(kernel(), run_id))}

    @api.get("/workflow-runs/{run_id}/inspection")
    async def inspection(run_id: str = Path(max_length=36)):
        from alive.workflows.observatory import inspected_run

        return await found(inspected_run(kernel(), run_id))

    @api.get("/workflow-runs/{run_id}/timeline")
    async def timeline(
        run_id: str = Path(max_length=36),
        after: int = Query(0, ge=0),
        limit: int = Query(200, ge=1, le=500),
    ):
        from alive.workflows.observatory import timeline as projection

        return await found(projection(kernel(), run_id, after=after, limit=limit))

    @api.get("/workflow-runs/{run_id}/stages/{attempt_id}/pi-receipt")
    async def stage_receipt(
        run_id: str = Path(max_length=36), attempt_id: str = Path(max_length=36)
    ):
        from alive.workflows.observatory import stage_receipt as projection

        return await found(projection(kernel(), run_id, attempt_id, pi_receipt))

    @api.get("/workflow-runs/{run_id}/artifacts/{stage_id}", response_model=ArtifactView)
    async def artifact(run_id: str = Path(max_length=36), stage_id: str = Path(max_length=32)):
        from alive.workflows.runner import artifact_view

        try:
            return await artifact_view(kernel(), run_id, stage_id)
        except (ValueError, KeyError, TypeError):
            raise HTTPException(404, "Result unavailable or integrity check failed") from None

    return api
