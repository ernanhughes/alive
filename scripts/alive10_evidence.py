"""Generate ALIVE-10 controlled feedback-independence and recovery evidence.

Real companion API and SQLite; synthetic local provider. No native browser and no Meta call.
"""

import asyncio
import json
import shutil
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from alive.app import create_app
from alive.config import Settings
from alive.db import Database
from alive.models import Base
from alive.providers import MetaProvider
from alive.web_experience import digest

TOKEN = "alive10-evidence-token-123456789"
ROOT = "/api/v1/browser-experience"
URL = "https://docs.python.org/3/tutorial/"
TEXT = "Python is an easy to learn, powerful programming language. This excerpt is controlled."
WORK = Path(".alive/alive10-evidence")
ARCHIVE = Path("archives/ALIVE-10/evidence")
calls = []


async def fake_structured(*args, **kwargs):
    calls.append(kwargs)
    return SimpleNamespace(
        text=json.dumps(
            {
                "summary": "A limited controlled note.",
                "evidence_quote": "Python is an easy to learn",
                "limitations": "Only the selected controlled excerpt was read.",
            }
        ),
        usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    )


MetaProvider.structured = fake_structured


def main():
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    settings = Settings(
        _env_file=None,
        alive_meta_api_key="",
        database_url=f"sqlite+aiosqlite:///{(WORK / 'evidence.db').as_posix()}",
        alive_api_token=TOKEN,
        alive_workspace=WORK / "workspace",
    )

    async def schema():
        db = Database(settings.database_url)
        async with db.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await db.engine.dispose()

    asyncio.run(schema())
    headers = {"Authorization": "Bearer " + TOKEN}

    def post(client, path, body, expected=200):
        response = client.post(ROOT + path, json=body)
        assert response.status_code == expected, response.text
        return response.json()

    def goal(client, instruction):
        return post(client, "/goals", {"instruction": instruction})

    def consent(client, goal_id, tab):
        return post(
            client,
            "/grants",
            {"goal_id": goal_id, "url": URL, "tab_key": tab, "approved": True},
        )

    def snapshot(client, grant, text):
        return post(
            client,
            "/snapshots",
            {
                "grant_id": grant["id"],
                "url": URL,
                "title": "Tutorial",
                "text": text,
                "reviewed_sha256": digest(text),
                "language": "auto",
            },
        )

    def analyse(client, shot, owner_correction=False):
        return post(
            client,
            "/analyse",
            {
                "snapshot_id": shot["snapshot"]["id"],
                "reviewed_sha256": shot["snapshot"]["data"]["sha256"],
                "send_to_meta": True,
                "owner_correction": owner_correction,
            },
        )

    def wait(client, note_id):
        for _ in range(100):
            row = client.get(ROOT + "/notes/" + note_id).json()
            if row["status"] != "reserved":
                return row
            time.sleep(0.02)
        raise AssertionError("note did not settle")

    def feedback(client, note_id, useful):
        return post(client, "/feedback", {"note_id": note_id, "useful": useful})

    def context(policy, goal_id):
        return policy["contexts"][f"{goal_id}|{URL}|auto"]

    with TestClient(create_app(settings), headers=headers) as client:
        # A. Repeated ratings of the same unchanged excerpt.
        goal_a = goal(client, "Help me decide where to start learning Python A")
        grant_a = consent(client, goal_a["id"], "alive10-a")
        repeated = []
        for index in range(3):
            shot = snapshot(client, grant_a, TEXT)
            assert shot["decision"]["action"] == "analyse"
            note = wait(client, analyse(client, shot)["id"])
            row = feedback(client, note["id"], False)
            policy = client.get(ROOT).json()["policy"]["data"]
            repeated.append(
                {
                    "index": index + 1,
                    "policy_changed": row["data"]["policy_changed"],
                    "duplicate_evidence": row["data"]["duplicate_evidence"],
                    "distinct_support": row["data"]["distinct_support"],
                    "policy_version": policy["version"],
                }
            )
        after_repeated = snapshot(client, grant_a, TEXT)["decision"]
        assert after_repeated["action"] == "analyse"
        assert after_repeated["adaptive_policy"]["support"] == 1
        assert len(calls) == 3
        policy_a = client.get(ROOT).json()["policy"]["data"]
        assert len(context(policy_a, goal_a["id"])["evidence"]) == 1

        # B. Three genuinely distinct excerpts accumulate support; suppression then probe.
        goal_b = goal(client, "Help me decide where to start learning Python B")
        grant_b = consent(client, goal_b["id"], "alive10-b")
        distinct = []
        for index in range(3):
            text = TEXT + f" Distinct observation {index}."
            shot = snapshot(client, grant_b, text)
            assert shot["decision"]["action"] == "analyse"
            note = wait(client, analyse(client, shot)["id"])
            feedback(client, note["id"], False)
            policy = client.get(ROOT).json()["policy"]["data"]
            distinct.append(
                {
                    "index": index + 1,
                    "distinct_support": len(context(policy, goal_b["id"])["evidence"]),
                    "policy_version": policy["version"],
                }
            )
        assert distinct[-1]["distinct_support"] == 3
        assert len(calls) == 6

        suppressed = []
        for index in range(3):
            shot = snapshot(client, grant_b, TEXT + f" Paused observation {index}.")
            decision = shot["decision"]
            assert decision["action"] == "no_action"
            assert decision["no_action_source"] == "feedback_policy"
            assert decision["without_feedback_action"] == "analyse"
            suppressed.append(
                {
                    "index": index + 1,
                    "suppressions": decision["adaptive_policy"]["suppressions"],
                    "policy_version": decision["policy_version"],
                }
            )
        assert len(calls) == 6

        probe = snapshot(client, grant_b, TEXT + " Probe observation.")
        decision = probe["decision"]
        assert decision["action"] == "analyse"
        assert decision["probe"] is True
        assert decision["adaptive_policy"]["probe"] is True
        probe_note = wait(client, analyse(client, probe)["id"])
        feedback(client, probe_note["id"], True)
        policy_b = client.get(ROOT).json()["policy"]["data"]
        assert len(context(policy_b, goal_b["id"])["evidence"]) == 4
        assert len(calls) == 7
        restored = snapshot(client, grant_b, TEXT + " Restored observation.")["decision"]
        assert restored["action"] == "analyse"
        assert restored["adaptive_policy"]["useful_rate"] == 0.25

        # C. Revision and idempotency on one evidence unit.
        goal_c = goal(client, "Help me decide where to start learning Python C")
        grant_c = consent(client, goal_c["id"], "alive10-c")
        shot_c = snapshot(client, grant_c, TEXT + " Revision observation.")
        note_c = wait(client, analyse(client, shot_c)["id"])
        first = feedback(client, note_c["id"], True)
        duplicate = feedback(client, note_c["id"], True)
        revised = feedback(client, note_c["id"], False)
        assert first["data"]["distinct_support"] == 1
        assert duplicate["idempotent"] is True
        assert revised["data"]["revision"] is True
        policy_c = client.get(ROOT).json()["policy"]["data"]
        unit_c = next(iter(context(policy_c, goal_c["id"])["evidence"].values()))
        assert unit_c["useful"] is False
        assert len(context(policy_c, goal_c["id"])["evidence"]) == 1
        assert len(calls) == 8
        policy_before_restart = client.get(ROOT).json()["policy"]["data"]

        evidence = {
            "provenance": {
                "kind": "controlled companion API and SQLite",
                "native_chrome": False,
                "meta_inference": False,
                "paid_calls": 0,
                "provider": "synthetic local adapter",
                "source_commit": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"],
                    cwd=Path(__file__).resolve().parents[1],
                    text=True,
                ).strip(),
            },
            "repeated_same_excerpt": {
                "ratings": repeated,
                "next_decision": after_repeated,
                "evidence_units": len(context(policy_a, goal_a["id"])["evidence"]),
            },
            "distinct_excerpts": {
                "ratings": distinct,
                "suppressed": suppressed,
                "probe": decision,
                "restored": restored,
                "evidence_units": len(context(policy_b, goal_b["id"])["evidence"]),
            },
            "revision": {
                "first": first["data"],
                "duplicate": duplicate,
                "revised": revised["data"],
                "unit": unit_c,
            },
            "counts": {"provider_calls": len(calls)},
        }
        ARCHIVE.mkdir(parents=True, exist_ok=True)
        (ARCHIVE / "feedback-independence.json").write_text(
            json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
        )
        (ARCHIVE / "suppression-recovery.json").write_text(
            json.dumps(
                {
                    "kind": "controlled companion API",
                    "suppressed": suppressed,
                    "probe": decision,
                    "restored": restored,
                    "policy_version": policy_b["version"],
                    "provider_calls": len(calls),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print("wrote controlled evidence; calls", len(calls))

    with TestClient(create_app(settings), headers=headers) as reopened:
        policy = reopened.get(ROOT).json()["policy"]["data"]
        assert policy["version"] == policy_before_restart["version"]
        goal_rows = reopened.get(ROOT).json()["goals"]
        goal_b_id = next(
            row["id"] for row in goal_rows if row["data"]["instruction"].endswith("Python B")
        )
        fresh = consent(reopened, goal_b_id, "alive10-restart")
        decision = snapshot(reopened, fresh, TEXT + " Restart observation.")["decision"]
        assert decision["action"] == "analyse"
        assert decision["adaptive_policy"]["support"] == 4
        ARCHIVE.mkdir(parents=True, exist_ok=True)
        (ARCHIVE / "restart-proof.json").write_text(
            json.dumps(
                {
                    "scope": "controlled companion SQLite across a new app process",
                    "policy_version_before": policy_before_restart["version"],
                    "policy_version_after": policy["version"],
                    "decision_after_restart": decision["action"],
                    "distinct_support_after_restart": decision["adaptive_policy"]["support"],
                    "provider_calls_total": len(calls),
                    "duplicate_inference": False,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print("wrote restart proof")


if __name__ == "__main__":
    main()
