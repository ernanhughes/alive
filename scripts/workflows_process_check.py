"""Independent-process lease/replay probe, invoked by the disposable execution fixture."""

import argparse
import json
import os
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from alive.app import create_app
from alive.config import Settings
from alive.workflows import store
from scripts.pi_integration import TOKEN
from scripts.workflows_execute_check import call, durable_counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expect-owned", action="store_true")
    parser.add_argument("--replay", type=Path)
    args = parser.parse_args()
    assert os.environ["DATABASE_URL"].startswith("postgresql+")
    with tempfile.TemporaryDirectory(prefix="alive-pi02b-process-") as directory:
        settings = Settings(
            _env_file=None,
            alive_meta_api_key="",
            alive_api_token=TOKEN,
            database_url=os.environ["DATABASE_URL"],
            alive_workspace=Path(directory),
        )
        with TestClient(
            create_app(settings), headers={"Authorization": "Bearer " + TOKEN}
        ) as client:
            kernel = client.app.state.kernel
            if args.expect_owned:
                assert not kernel.ready, "competing process acquired the existing host lease"
                assert client.get("/api/v1/workflow-runs").status_code == 503
                print(
                    json.dumps(
                        {
                            "status": "PASS",
                            "pid": os.getpid(),
                            "competing_host": "refused_by_production_lease",
                        }
                    )
                )
                return
            assert kernel.ready, kernel.error
            before = call(client, durable_counts)
            results = json.loads(args.replay.read_text())
            for result in results:
                run_id = result["run"]["id"]
                assert client.get(f"/api/v1/workflow-runs/{run_id}").json() == result["run"]
                assert (
                    client.get(f"/api/v1/workflow-runs/{run_id}/stages").json()["stages"]
                    == result["stages"]
                )
                assert (
                    client.get(f"/api/v1/workflow-runs/{run_id}/artifacts/record").json()
                    == result["artifact"]
                )

                async def replay(k):
                    assert (await client.app.state.workflows.execute(run_id))[
                        "status"
                    ] == "COMPLETED"
                    assert (await store.get_run(k, run_id))["status"] == "COMPLETED"

                call(client, replay)
            assert call(client, durable_counts) == before
            print(
                json.dumps(
                    {
                        "status": "PASS",
                        "pid": os.getpid(),
                        "successor_host": "owns_production_lease",
                        "replayed_runs": len(results),
                        "effect_count_delta": 0,
                    }
                )
            )


if __name__ == "__main__":
    main()
