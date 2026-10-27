"""Generate ALIVE-09 controlled evidence for the companion feedback-to-policy loop."""

import asyncio
import json
import shutil
import sqlite3
import time
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from alive.app import create_app
from alive.config import Settings
from alive.db import Database
from alive.models import Base
from alive.providers import MetaProvider
from alive.web_experience import adaptive_recommendation, digest

TOKEN = "alive09-evidence-token-123456789"
ROOT = "/api/v1/browser-experience"
URL = "https://docs.python.org/3/tutorial/"
BASE_TEXT = "Python is an easy to learn, powerful programming language. "
WORK = Path(".alive/alive09-evidence")
ARCHIVE = Path("archives/ALIVE-09")

calls = []


async def fake_structured(*args, **kwargs):
    calls.append(kwargs)
    return SimpleNamespace(
        text=json.dumps(
            {
                "summary": "A limited introductory note.",
                "evidence_quote": "Python is an easy to learn",
                "limitations": "Only the selected excerpt was read.",
            }
        ),
        usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    )


MetaProvider.structured = fake_structured


def main():
    if ARCHIVE.exists():
        raise SystemExit("ALIVE-09 archive exists; refusing overwrite")
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

    def consent(client, goal_id, tab="alive09-evidence-tab"):
        return post(
            client,
            "/grants",
            {"goal_id": goal_id, "url": URL, "tab_key": tab, "approved": True},
        )

    def snapshot(client, grant, suffix, expected=200):
        text = BASE_TEXT + suffix
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
            expected,
        )

    def analyse(client, shot, expected=200, owner_correction=False):
        return post(
            client,
            "/analyse",
            {
                "snapshot_id": shot["snapshot"]["id"],
                "reviewed_sha256": shot["snapshot"]["data"]["sha256"],
                "send_to_meta": True,
                "owner_correction": owner_correction,
            },
            expected,
        )

    def wait(client, note_id):
        for _ in range(100):
            row = client.get(ROOT + "/notes/" + note_id).json()
            if row["status"] != "reserved":
                return row
            time.sleep(0.02)
        raise AssertionError("note did not settle")

    with TestClient(create_app(settings), headers=headers) as client:
        goal = post(
            client, "/goals", {"instruction": "Help me decide where to start learning Python"}
        )
        grant = consent(client, goal["id"])
        decisions = []
        notes = []
        feedbacks = []
        for index, suffix in enumerate(
            [
                "First controlled excerpt.",
                "Second controlled excerpt.",
                "Third controlled excerpt.",
            ],
            1,
        ):
            shot = snapshot(client, grant, suffix)
            decisions.append(shot["decision"])
            assert shot["decision"]["action"] == "analyse", shot
            note = wait(client, analyse(client, shot)["id"])
            notes.append(note)
            feedbacks.append(post(client, "/feedback", {"note_id": note["id"], "useful": False}))
            assert feedbacks[-1]["data"]["policy_version_after"] == index

        fourth = snapshot(client, grant, "Fourth related excerpt.")
        suppressed = fourth["decision"]
        assert suppressed["action"] == "no_action"
        assert suppressed["no_action_source"] == "feedback_policy"
        assert suppressed["adaptive_policy"]["support"] == 3
        before_calls = len(calls)
        analyse(client, fourth, expected=409)
        assert len(calls) == before_calls

        corrected = analyse(client, fourth, owner_correction=True)
        corrected_note = wait(client, corrected["id"])
        assert corrected_note["data"]["owner_correction"] is True
        correction_feedback = post(
            client, "/feedback", {"note_id": corrected_note["id"], "useful": True}
        )
        fifth = snapshot(client, grant, "Fifth related excerpt.")
        restored = fifth["decision"]
        assert restored["action"] == "analyse"
        assert restored["adaptive_policy"]["support"] == 4
        assert restored["adaptive_policy"]["useful"] == 1
        assert restored["adaptive_policy"]["useful_rate"] == 0.25

        # Separate goal context for idempotency and revision evidence.
        other_goal = post(
            client, "/goals", {"instruction": "Help me decide where to start learning Python"}
        )
        other_grant = consent(client, other_goal["id"], "alive09-idempotency-tab")
        other_shot = snapshot(client, other_grant, "Idempotency excerpt.")
        other_note = wait(client, analyse(client, other_shot)["id"])
        first_feedback = post(client, "/feedback", {"note_id": other_note["id"], "useful": True})
        duplicate_feedback = post(
            client, "/feedback", {"note_id": other_note["id"], "useful": True}
        )
        revised_feedback = post(client, "/feedback", {"note_id": other_note["id"], "useful": False})
        assert duplicate_feedback["idempotent"] is True
        assert revised_feedback["data"]["revision"] is True

        status = client.get(ROOT).json()
        correction_rows = status["corrections"]
        policy = status["policy"]["data"]
        evidence = {
            "provenance": {
                "kind": "controlled companion API sequence",
                "native_chrome": False,
                "meta_inference": False,
                "paid_calls": 0,
                "provider": "synthetic local adapter",
                "note": (
                    "Real ALIVE companion API and SQLite persistence; no browser or Meta request."
                ),
            },
            "goal_id": goal["id"],
            "decisions": decisions,
            "feedback": feedbacks,
            "suppressed_decision": suppressed,
            "owner_correction": {
                "snapshot_id": fourth["snapshot"]["id"],
                "note_id": corrected_note["id"],
                "owner_correction": corrected_note["data"]["owner_correction"],
                "correction_rows": correction_rows,
                "feedback": correction_feedback,
            },
            "restored_decision": restored,
            "policy": policy,
            "policy_contexts": {
                "before_correction": suppressed["adaptive_policy"],
                "after_useful_correction": restored["adaptive_policy"],
            },
            "idempotency": {
                "first": first_feedback,
                "duplicate": duplicate_feedback,
                "revision": revised_feedback,
            },
            "counts": {
                "provider_calls": len(calls),
                "final_useful_feedback": 1,
                "final_not_useful_feedback": 4,
                "owner_corrections": len(correction_rows),
            },
        }
        output = ARCHIVE / "evidence"
        output.mkdir(parents=True)
        (output / "controlled-loop.json").write_text(
            json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
        )
        (ARCHIVE / "evidence" / "restart-proof.json").write_text(
            json.dumps(
                {
                    "note": "Restart-specific evidence is generated below into the same archive.",
                    "policy_version": policy["version"],
                    "policy_contexts": policy["contexts"],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print("wrote controlled loop evidence; calls", len(calls))
        restart_revoked_grant = consent(client, goal["id"], "alive09-restart-revoked-tab")

    def count_notes():
        with sqlite3.connect(WORK / "evidence.db") as connection:
            return connection.execute(
                "select count(*) from web_experiences where kind = 'note'"
            ).fetchone()[0]

    notes_before_restart = count_notes()

    # Restart proof using the same SQLite database.
    with TestClient(create_app(settings), headers=headers) as reopened:
        goal_rows = reopened.get(ROOT).json()["goals"]
        goal_id = next(
            row["id"] for row in goal_rows if row["data"]["instruction"].startswith("Help")
        )
        reopened_policy = reopened.get(ROOT).json()["policy"]["data"]
        assert reopened_policy["version"] == policy["version"]
        stale_text = "Stale pre-restart grant excerpt."
        stale_response = reopened.post(
            ROOT + "/snapshots",
            json={
                "grant_id": restart_revoked_grant["id"],
                "url": URL,
                "title": "Tutorial",
                "text": stale_text,
                "reviewed_sha256": digest(stale_text),
                "language": "auto",
            },
        )
        assert stale_response.status_code == 403, stale_response.text
        stale_grant = stale_response.json()
        fresh_grant = consent(reopened, goal_id, "alive09-restart-tab")
        restart_shot = snapshot(reopened, fresh_grant, "Restart continuity excerpt.")
        assert restart_shot["decision"]["action"] == "analyse"
        assert restart_shot["decision"]["adaptive_policy"]["support"] == 4

    notes_after_restart = count_notes()
    assert notes_after_restart == notes_before_restart
    assert len(calls) == 5
    restart = {
        "scope": "real companion SQLite persistence across a new app process",
        "policy_version_before": policy["version"],
        "policy_version_after": reopened_policy["version"],
        "decision_after_restart": restart_shot["decision"]["action"],
        "adaptive_support_after_restart": restart_shot["decision"]["adaptive_policy"]["support"],
        "provider_calls_total": len(calls),
        "notes_before_restart": notes_before_restart,
        "notes_after_restart": notes_after_restart,
        "duplicate_inference_detected": notes_after_restart != notes_before_restart
        or len(calls) != 5,
        "grants_revoked_on_restart": stale_response.status_code == 403,
        "pre_restart_grant_attempt": {
            "http_status": stale_response.status_code,
            "detail": stale_grant,
        },
        "note": "The active pre-restart grant was revoked by startup. The fresh grant is "
        "required, and no completed note was replayed or re-inferred.",
    }
    (ARCHIVE / "evidence" / "restart-proof.json").write_text(
        json.dumps(restart, indent=2) + "\n", encoding="utf-8"
    )

    # Controlled decision replay using the actual policy function.
    replay_contexts = {
        "three_negative_then_useless": {"useful": 0, "not_useful": 3},
        "three_negative_then_useful": {"useful": 0, "not_useful": 3},
        "one_negative_then_useless": {"useful": 0, "not_useful": 1},
        "positive_three": {"useful": 3, "not_useful": 0},
    }
    replay = []
    for name, context in replay_contexts.items():
        policy_doc = {
            "policy_id": "companion-feedback-usefulness-v1",
            "version": 3,
            "contexts": {"replay": context},
            "history": [],
            "minimum_support": 3,
            "maximum_useful_rate": 0.20,
        }
        adaptive = adaptive_recommendation(policy_doc, "replay")
        simple = adaptive_recommendation(policy_doc, "replay", minimum_support=1)
        replay.append(
            {
                "case": name,
                "support": context["useful"] + context["not_useful"],
                "adaptive": adaptive["recommendation"],
                "simple_one_negative": simple["recommendation"],
                "frozen_companion": "analyse",
                "constant_analyse": "analyse",
                "note": "Controlled policy replay; not native browser evidence.",
            }
        )
    (ARCHIVE / "evidence" / "baseline-replay.json").write_text(
        json.dumps(
            {
                "policy_id": "companion-feedback-usefulness-v1",
                "minimum_support": 3,
                "maximum_useful_rate": 0.20,
                "cases": replay,
                "caveat": "The replay compares decisions only. A suppressed analysis could have "
                "been useful; owner correction is required. No native outcome data is implied.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("wrote baseline replay and restart proof")


if __name__ == "__main__":
    main()
