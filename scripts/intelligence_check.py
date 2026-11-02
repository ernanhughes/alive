"""INT-02 durable fixture lifecycle/restart/replay/concurrency on an EXPLICIT disposable DB.

ALIVE_DB_TARGET=disposable:<db> DATABASE_URL=...
ALIVE_API_TOKEN=<test token> python -m scripts.intelligence_check
Never uses default .env, live inference, Pi, tools or production evidence authority.
"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import select

from alive.app import create_app
from alive.config import Settings
from alive.intelligence import fixture, store
from alive.intelligence.contracts import OutcomeFeedback, digest
from alive.intelligence.models import (
    IntelligenceEpisode,
    IntelligenceFeedback,
    IntelligenceLearningUpdate,
    IntelligenceMeasurementUse,
    IntelligenceState,
)


def call(client, fn, *args, **kwargs):
    return client.portal.call(lambda: fn(client.app.state.kernel, *args, **kwargs))


async def durable_identity(kernel):
    async with kernel.db.sessions() as session:
        records = []
        for model in (
            IntelligenceEpisode,
            IntelligenceFeedback,
            IntelligenceLearningUpdate,
            IntelligenceState,
            IntelligenceMeasurementUse,
        ):
            rows = (
                await session.scalars(select(model).order_by(*model.__table__.primary_key))
            ).all()
            records.append(
                [
                    {
                        c.name: getattr(row, c.name)
                        for c in model.__table__.columns
                        if c.name != "created_at"
                    }
                    for row in rows
                ]
            )
        return digest(records)


async def concurrent_feedback(kernel, episode, source, feedback):
    workers = [
        SimpleNamespace(
            db=kernel.db,
            instance_id=kernel.instance_id,
            lock=asyncio.Lock(),
            add_event=kernel.add_event,
        )
        for _ in range(4)
    ]
    return await asyncio.gather(
        *(
            store.accept_feedback(
                worker, episode_id=episode, source_event_id=source, feedback=feedback
            )
            for worker in workers
        )
    )


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--replay":
        return process_replay(Path(sys.argv[2]))
    database = os.environ["DATABASE_URL"]
    token = os.environ["ALIVE_API_TOKEN"]
    # Caller must supply a dedicated database; no inferred production connection or .env.
    subprocess.run(
        [sys.executable, "-B", "-m", "alembic", "upgrade", "head"],
        check=True,
        env=os.environ | {"DATABASE_URL": database},
    )
    with tempfile.TemporaryDirectory(prefix="alive-int02-") as directory:
        settings = Settings(
            _env_file=None,
            database_url=database,
            alive_api_token=token,
            alive_meta_api_key="",
            alive_workspace=Path(directory),
            alive_heartbeat_seconds=0.2,
        )
        headers = {"Authorization": "Bearer " + token}
        with TestClient(create_app(settings), headers=headers) as client:
            chain = call(client, fixture.lifecycle)
            assert chain["monitor_samples"] == 1 and chain["candidate_revision"] == 1
            first, later = chain["episodes"]
            assert first["intelligence_proposal"] == "monitor"
            assert (
                later["intelligence_proposal"] == "retrieve"
                and later["active_policy_choice"] == "monitor"
            )
            assert first["active_policy_choice"] == "monitor"
            assert all(
                e["workflow_state"] == "PENDING" and e["executed_action"] is None
                for e in chain["episodes"]
            )
            other = call(client, fixture.start)
            episode = call(client, fixture.assessment, other)
            source, feedback = call(client, fixture.independent_outcome, episode)
            winners = call(client, concurrent_feedback, episode, source, feedback)
            assert winners.count("accepted") == 1 and winners.count("duplicate") == 3
            assert call(client, store.inspect_chain, other)["monitor_samples"] == 1
            identity = call(client, durable_identity)
        with TestClient(create_app(settings), headers=headers) as restarted:
            assert restarted.get("/api/v1/intelligence/states/" + chain["id"]).json() == chain
            assert call(restarted, durable_identity) == identity
            for _ in range(3):
                assert call(restarted, store.inspect_chain, chain["id"]) == chain
            assert (
                call(
                    restarted,
                    store.accept_feedback,
                    episode_id=episode,
                    source_event_id=source,
                    feedback=OutcomeFeedback.model_validate_json(feedback.model_dump_json()),
                )
                == "duplicate"
            )
            assert call(restarted, durable_identity) == identity
        expected = Path(directory) / "expected.json"
        expected.write_text(json.dumps({"chain": chain, "identity": identity}), encoding="utf-8")
        process = subprocess.run(
            [sys.executable, "-B", "-m", "scripts.intelligence_check", "--replay", str(expected)],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert "PROCESS_REPLAY_PASS" in process.stdout
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "mode": "independent controlled fixture, no physical execution",
                    "chain": chain,
                    "concurrent_winners": winners,
                    "restart": "PASS",
                    "process_restart": "PASS: separate interpreter reloaded exact durable chain",
                    "replay": "PASS: durable identity unchanged, zero dispatch",
                    "durable_identity": identity,
                },
                indent=2,
            )
        )


def process_replay(expected_path):
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="alive-int02-replay-") as directory:
        settings = Settings(
            _env_file=None,
            database_url=os.environ["DATABASE_URL"],
            alive_api_token=os.environ["ALIVE_API_TOKEN"],
            alive_meta_api_key="",
            alive_workspace=Path(directory),
            alive_heartbeat_seconds=0.2,
        )
        with TestClient(
            create_app(settings),
            headers={
                "Authorization": "Bearer " + settings.alive_api_token,
            },
        ) as client:
            assert (
                client.get("/api/v1/intelligence/states/" + expected["chain"]["id"]).json()
                == expected["chain"]
            )
            assert call(client, durable_identity) == expected["identity"]
    print("PROCESS_REPLAY_PASS")


if __name__ == "__main__":
    main()
