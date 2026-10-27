"""Zero-cost A/B/C preflight for the frozen ALIVE-14-R2 paired experiment.

All inference uses the local deterministic stub. The owner endpoint is exercised
synthetically to verify the blind-rating lifecycle; these are not human ratings.
"""

import asyncio
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from alive.app import create_app
from alive.config import Settings
from alive.db import Database
from alive.models import Base, now, uid
from alive.web_experience import digest
from alive.web_models import WebExperience

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "archives/ALIVE-14-R2"
PROTOCOL = ARCHIVE / "protocol/relationship-experiment-v2.json"
WORK = ROOT / ".alive/alive14r2-preflight"
API = "/api/v1/browser-experience"
TOKEN = "alive14r2-preflight-" + "x" * 24
RUBRIC = {
    "factually_supported": "yes",
    "relevant_to_goal": "yes",
    "revealed_new": "yes",
    "already_obvious": "no",
    "would_act": "yes",
    "misleading": "no",
    "uncertain": "no",
}


def post(client, path, body, expected=200):
    response = client.post(API + path, json=body)
    assert response.status_code == expected, response.text
    return response.json()


def run():
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    urls = []
    for task in protocol["paired_tasks"]:
        urls.extend([task["current_source"]["url"], task["historical_source"]["url"]])
    settings = Settings(
        _env_file=None,
        alive_meta_api_key="",
        alive_embedding_enabled=False,
        alive_native_test_pages=",".join(sorted(set(urls))),
        alive_api_token=TOKEN,
        database_url=f"sqlite+aiosqlite:///{(WORK / 'preflight.db').as_posix()}",
        alive_workspace=WORK / "workspace",
    )

    async def schema():
        database = Database(settings.database_url)
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await database.engine.dispose()

    asyncio.run(schema())
    result = {
        "protocol_version": protocol["protocol_version"],
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "protocol_sha256": hashlib.sha256(
            PROTOCOL.read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "protocol_commit": subprocess.check_output(
            ["git", "log", "-1", "--format=%H", "--", str(PROTOCOL.relative_to(ROOT))],
            cwd=ROOT,
            text=True,
        ).strip(),
        "paid_calls": 0,
        "provider": "local_stub",
        "tasks": [],
        "blind_run": {},
    }
    with TestClient(create_app(settings), headers={"Authorization": "Bearer " + TOKEN}) as client:
        goal_rows = {}
        research_rows = {}
        for task in protocol["paired_tasks"]:
            goal = post(client, "/goals", {"instruction": task["goal"]})
            goal_rows[task["task_id"]] = goal
            current_grant = post(
                client,
                "/grants",
                {
                    "goal_id": goal["id"],
                    "url": task["current_source"]["url"],
                    "tab_key": "current-" + task["task_id"],
                    "approved": True,
                },
            )
            current = post(
                client,
                "/snapshots",
                {
                    "grant_id": current_grant["id"],
                    "url": task["current_source"]["url"],
                    "title": "Current controlled source",
                    "text": task["current_source"]["excerpt"],
                    "reviewed_sha256": digest(task["current_source"]["excerpt"]),
                },
            )

            async def seed_research():
                async with client.app.state.kernel.db.sessions.begin() as session:
                    row = WebExperience(
                        id=uid(),
                        instance_id=client.app.state.kernel.instance_id,
                        kind="research_memory",
                        status="active",
                        data={
                            "goal_id": goal["id"],
                            "url": task["historical_source"]["url"],
                            "title": "Historical controlled source",
                            "excerpt": task["historical_source"]["excerpt"],
                            "sha256": digest(task["historical_source"]["excerpt"]),
                            "reviewed_at": now().isoformat(),
                            "source_kind": "reviewed_browser_excerpt",
                        },
                    )
                    session.add(row)
                    await session.flush()
                    return row.id

            research_id = client.portal.call(seed_research)
            research_rows[task["task_id"]] = research_id

            current_preview = post(
                client,
                "/research/outbound/preview",
                {
                    "snapshot_id": current["snapshot"]["id"],
                    "analysis_mode": "current_only",
                    "research_question": task["question"],
                },
            )
            post(
                client,
                "/research/outbound/authorize",
                {
                    "consent_id": current_preview["id"],
                    "payload_sha256": current_preview["payload_sha256"],
                    "approved": True,
                },
            )
            current_result = post(
                client,
                "/research/relationships",
                {"consent_id": current_preview["id"]},
            )

            history_preview = post(
                client,
                "/research/outbound/preview",
                {
                    "snapshot_id": current["snapshot"]["id"],
                    "research_id": research_id,
                    "analysis_mode": "history_assisted",
                    "research_question": task["question"],
                },
            )
            post(
                client,
                "/research/outbound/authorize",
                {
                    "consent_id": history_preview["id"],
                    "payload_sha256": history_preview["payload_sha256"],
                    "approved": True,
                },
            )
            history_result = post(
                client,
                "/research/relationships",
                {"consent_id": history_preview["id"]},
            )
            a_text = current_result["current_analysis"]["data"]["assessment"]
            b_connection = history_result.get("connection")
            b_text = (
                b_connection["data"]["explanation"]
                if b_connection
                else "History-assisted analysis abstained or rejected the output."
            )
            result["tasks"].append(
                {
                    "task_id": task["task_id"],
                    "stratum": task["stratum"],
                    "history_expectation": task["history_expectation"],
                    "current_only": {
                        "status": current_result["analysis"]["status"],
                        "sufficient_evidence": current_result["current_analysis"]["data"][
                            "sufficient_evidence"
                        ],
                        "assessment": a_text,
                    },
                    "history_assisted": {
                        "status": history_result["analysis"]["status"],
                        "relation_type": b_connection["data"]["relation_type"]
                        if b_connection
                        else None,
                        "assessment": b_text,
                    },
                    "direct_history": task["historical_source"]["excerpt"],
                    "current_attempt_id": current_result["analysis"]["id"],
                    "history_attempt_id": history_result["analysis"]["id"],
                }
            )

        blind_tasks = []
        for task, observed in zip(protocol["paired_tasks"], result["tasks"], strict=True):
            blind_tasks.append(
                {
                    "task_id": task["task_id"],
                    "question": task["question"],
                    "current_excerpt": task["current_source"]["excerpt"],
                    "historical_excerpt": task["historical_source"]["excerpt"],
                    "current_url": task["current_source"]["url"],
                    "historical_url": task["historical_source"]["url"],
                    "current_sha256": task["current_source"]["sha256"],
                    "historical_sha256": task["historical_source"]["sha256"],
                    "outputs": {
                        "A_current_only": observed["current_only"]["assessment"],
                        "B_current_plus_history": observed["history_assisted"]["assessment"],
                        "C_history_without_synthesis": observed["direct_history"],
                    },
                    "attempt_ids": {
                        "A_current_only": observed["current_attempt_id"],
                        "B_current_plus_history": observed["history_attempt_id"],
                    },
                    "output_metadata": {
                        "A_current_only": {"provider": "local_stub", "usage": {"total_tokens": 0}},
                        "B_current_plus_history": {
                            "provider": "local_stub",
                            "usage": {"total_tokens": 0},
                        },
                        "C_history_without_synthesis": {"provider": "none"},
                    },
                }
            )
        run = post(
            client,
            "/research/blind/runs",
            {
                "experiment_id": protocol["experiment_id"],
                "seed": protocol["seed"],
                "tasks": blind_tasks,
            },
        )
        view = client.get(API + f"/research/blind/runs/{run['id']}").json()
        assert '"condition":' not in json.dumps(view)
        for output in view["outputs"]:
            post(
                client,
                f"/research/blind/runs/{run['id']}/ratings",
                {
                    "output_id": output["output_id"],
                    "output_sha256": output["output_sha256"],
                    "capability": view["rating_capability"],
                    "rubric": RUBRIC,
                },
            )
        reveal = post(client, f"/research/blind/runs/{run['id']}/reveal", {})
        archived = post(client, f"/research/blind/runs/{run['id']}/archive", {})
        result["blind_run"] = {
            "run_id": run["id"],
            "status_before_reveal": view["status"],
            "outputs": len(view["outputs"]),
            "ratings": len(reveal["ratings"]),
            "conditions_revealed": sorted({row["condition"] for row in reveal["outputs"]}),
            "revealed_at": reveal["revealed_at"],
            "assignment_commitment": reveal["assignment_commitment"],
            "legacy_assignment_sha256": None,
            "archive_status": archived["status"],
            "owner_endpoint_exercised_synthetically": True,
            "human_owner_ratings": False,
        }
    (ARCHIVE / "evidence").mkdir(parents=True, exist_ok=True)
    (ARCHIVE / "evidence/preflight.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result["blind_run"], indent=2))
    print(ARCHIVE / "evidence/preflight.json")


if __name__ == "__main__":
    run()
