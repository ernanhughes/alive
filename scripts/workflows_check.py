"""ALIVE-PI-02A: the workflow foundation against a REAL database (PostgreSQL in CI).

    DATABASE_URL=postgresql+asyncpg://... ALIVE_API_TOKEN=<32+ chars> \
        uv run python -m scripts.workflows_check

Applies the migrations (up, down to 0006, up again), starts the real application, and checks the
promises that matter on a real server: the shipped definition is seeded, versions are immutable,
concurrent registration has one winner, runs keep their definition snapshot, history survives a
restart, and no response leaks the token. No provider is called and no process is started.
"""

import asyncio
import os
import subprocess
import sys

from fastapi.testclient import TestClient

from alive.app import create_app
from alive.config import Settings
from alive.workflows import states, store
from alive.workflows.spec import DefinitionError

DEMO = {
    "schema_version": 1,
    "name": "check-flow",
    "version": 1,
    "title": "Check flow",
    "stages": [
        {
            "id": "prepare",
            "title": "Prepare",
            "type": "deterministic",
            "operation": "context.prepare",
            "output_schema": {"properties": {"snapshot": {"type": "object"}}},
        },
        {
            "id": "check",
            "title": "Check",
            "type": "validation",
            "operation": "evidence.validate_references",
            "depends_on": ["prepare"],
            "output_schema": {"properties": {"valid": {"type": "boolean"}}},
        },
    ],
}
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("PASS  " if ok else "FAIL  ") + name + (f"  [{detail}]" if detail else ""))


def alembic(*args):
    subprocess.run([sys.executable, "-m", "alembic", *args], check=True, capture_output=True)


def call(client, fn, *args, **kwargs):
    return client.portal.call(lambda: fn(client.app.state.kernel, *args, **kwargs))


def main():
    token = os.environ["ALIVE_API_TOKEN"]
    headers = {"Authorization": f"Bearer {token}"}
    alembic("downgrade", "0006") if os.environ.get("WORKFLOWS_CHECK_REMIGRATE") else None
    alembic("upgrade", "head")
    check("migrations apply", True)

    with TestClient(create_app(Settings()), headers=headers) as client:
        listing = client.get("/api/v1/workflows").json()["workflows"]
        names = {w["name"]: w for w in listing}
        check(
            "the shipped definition is seeded as a draft",
            names["research-review"]["latest_status"] == "draft",
        )
        check(
            "the API requires the token",
            TestClient(client.app).get("/api/v1/workflows").status_code == 401,
        )

        view, created = call(client, store.register_definition, DEMO, status="active")
        again, created_again = call(client, store.register_definition, DEMO, status="active")
        check(
            "registration is idempotent",
            created and not created_again and view["id"] == again["id"],
        )
        try:
            call(client, store.register_definition, {**DEMO, "title": "Changed"})
            check("a changed version is refused", False)
        except store.WorkflowConflict:
            check("a changed version is refused", True)
        try:
            call(client, store.register_definition, {**DEMO, "name": "bad-flow", "stages": []})
            check("an invalid definition is refused", False)
        except DefinitionError:
            check("an invalid definition is refused", True)

        async def race():
            kernel = client.app.state.kernel
            attempts = [
                store.register_definition(kernel, {**DEMO, "name": "race-flow", "title": f"T{i}"})
                for i in range(8)
            ]
            return await asyncio.gather(*attempts, return_exceptions=True)

        outcome = client.portal.call(race)
        winners = [r for r in outcome if not isinstance(r, Exception)]
        check(
            "concurrent registration has exactly one winner",
            len(winners) == 1,
            f"{len(winners)} winners",
        )

        run, _ = call(
            client, store.open_run, "check-flow", 1, input_ref="input:1", input_sha256="a" * 64
        )
        call(client, store.advance_run, run["id"], states.RUNNING)
        call(client, store.advance_stage, run["id"], "prepare", states.RUNNING)
        call(
            client,
            store.register_definition,
            {**DEMO, "version": 2, "title": "Check flow two"},
            status="active",
        )
        call(client, store.set_status, "check-flow", 1, "superseded")
        detail = client.get(f"/api/v1/workflow-runs/{run['id']}").json()
        check(
            "a run keeps the definition it was opened against",
            detail["workflow"]["definition_sha256"] == view["definition_sha256"],
        )
        stages = client.get(f"/api/v1/workflow-runs/{run['id']}/stages").json()["stages"]
        check(
            "stage records are readable",
            [(s["stage_id"], s["state"]) for s in stages]
            == [("prepare", "RUNNING"), ("check", "PENDING")],
        )
        blob = "".join(
            client.get(p).text
            for p in (
                "/api/v1/workflows",
                "/api/v1/workflows/check-flow/versions/1",
                f"/api/v1/workflow-runs/{run['id']}",
            )
        )
        check(
            "no response contains the token or the database URL",
            token not in blob and "postgresql" not in blob,
        )
        first = call(client, store.get_definition, "check-flow", 1)

    with TestClient(create_app(Settings()), headers=headers) as client:
        check(
            "the shipped definition is unchanged after restart",
            dict(client.app.state.workflow_seed)["research-review.v1.json"] == "unchanged",
        )
        check(
            "the definition survives a restart",
            call(client, store.get_definition, "check-flow", 1) == first,
        )
        check(
            "the run survives a restart",
            call(client, store.get_run, run["id"])["status"] == "RUNNING",
        )

    alembic("downgrade", "0006")
    alembic("upgrade", "head")
    check("downgrade to 0006 and upgrade again", True)
    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
