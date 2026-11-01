"""Frozen AI-FIRST-03 comparison through production Pi on owner-authored public fixtures.

--approve-live authorizes only this frozen corpus, bounded public derived lesson exports,
180 provider requests and 2,000,000 conservative reservation units. No automatic retries.
The oracle executes author-owned corpus code, never code returned by a model.
"""

import argparse
import asyncio
import json
import random
import subprocess
import time
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from alive.adaptation import oracle
from alive.adaptation import service as adaptation
from alive.admission import live
from alive.admission.profiles import PROFILES, definition_text
from alive.app import create_app
from alive.cognitive_schema import CognitiveConfiguration
from alive.config import Settings
from alive.db import Database
from alive.models import Base, Event, uid
from alive.pi.models import PiProviderRequest
from alive.sources import capture, custody
from alive.sources.cli import principal
from alive.workflows.context import digest
from alive.workflows.store import register_definition
from scripts.live_bespoke_demo import TOKEN, call, response

MODES = {"A": "stateless", "B": "contextual", "C": "learned"}


def settings_for(folder):
    return Settings(
        database_url=f"sqlite+aiosqlite:///{folder / 'demo.db'}",
        alive_workspace=folder / "workspace",
        alive_api_token=TOKEN,
        alive_model_transport="pi",
        alive_meta_model="muse-spark-1.3-contributor",
        alive_role_models={},
        alive_embedding_enabled=False,
    )


async def counts(kernel):
    async with kernel.db.sessions() as session:
        return {
            "provider_requests": await session.scalar(
                select(func.count()).select_from(PiProviderRequest)
            ),
            "reserved_units": sum(
                e.payload.get("reserved_tokens", 0)
                for e in await session.scalars(
                    select(Event).where(
                        Event.instance_id == kernel.instance_id,
                        Event.event_type == "admission.owner.approved",
                    )
                )
            ),
        }


def plan(corpus):
    rng = random.Random(4319)
    runs = []
    for phase in ("dev", "heldout", "repeat"):
        tasks = [
            t for t in corpus["tasks"] if t["split"] == ("heldout" if phase == "repeat" else phase)
        ]
        if phase == "repeat":
            tasks = [t for t in tasks if t["id"] in ("numeric-5", "authorization-5")]
        for task in tasks:
            arms = list(MODES)
            rng.shuffle(arms)
            runs.extend({"phase": phase, "task_id": task["id"], "arm": a} for a in arms)
    return runs


def goal_for(task):
    return (
        f"Review the supplied implementation against this contract: {task['contract']} "
        "Identify any real defect, explain why and recommend a minimal correction if needed. "
        "For each named input case in README.md, predict observed and required "
        "Use JSON or ERROR:ExceptionName, and issue_present. Do not invent defects in correct code."
    )


def compact(value):
    return {
        k: value.get(k)
        for k in (
            "id",
            "goal",
            "conversation_ref",
            "answer",
            "context",
            "calls",
            "model_calls",
            "status",
            "availability",
            "followup",
        )
    } | {"result_admission_id": (value.get("result_admission") or {}).get("id")}


def run(folder, approve_live, previous_ledger=None, resume=False):
    if not approve_live:
        raise ValueError("Explicit --approve-live required; otherwise live qualification NOT_RUN")
    folder = folder.resolve()
    folder.mkdir(parents=True, exist_ok=resume)
    settings = settings_for(folder)
    if not settings.alive_meta_api_key:
        raise ValueError("Meta credential absent; live qualification NOT_RUN")
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        raise ValueError("Commit implementation and frozen oracle before live qualification")
    corpus, lock = oracle.frozen_corpus()
    prior_requests = 0
    if previous_ledger:
        prior = json.loads(previous_ledger.read_text(encoding="utf-8"))
        prior_requests = sum(t["review"]["model_calls"] for t in prior["training"])
    ledger = {
        "schema": "adaptation-live/v1",
        "status": "INCOMPLETE",
        "implementation_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "corpus_lock": lock,
        "plan": plan(corpus),
        "seed": 4319,
        "limits": {"provider_requests": 180, "conservative_units": 2000000},
        "model": "muse-spark-1.3-contributor",
        "transport": "production Pi / network",
        "cost": "unknown; no authoritative currency tariff available",
        "training": [],
        "evaluation": [],
        "sources": {},
    }
    path = folder / "adaptation-ledger.json"
    ledger["earlier_attempt"] = {
        "ledger_sha256": digest(prior) if previous_ledger else None,
        "provider_requests": prior_requests,
        "conservative_units_upper_bound": prior_requests * 30000,
    }
    if resume:
        ledger = json.loads(path.read_text(encoding="utf-8"))
        assert ledger["corpus_lock"] == lock and ledger["plan"] == plan(corpus)
        subprocess.run(
            ["git", "diff", "--exit-code", ledger["implementation_sha"], "--", "alive"], check=True
        )
        for row in ledger["evaluation"]:
            task = next(t for t in corpus["tasks"] if t["id"] == row["task_id"])
            assert row["review"]["request"]["goal"] == goal_for(task)
        prior_requests = ledger["earlier_attempt"]["provider_requests"]
        ledger.setdefault("resumptions", []).append(
            {
                "harness_sha": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], text=True
                ).strip(),
                "prior_failure": ledger.pop("failure", None),
                "completed_evaluations": len(ledger["evaluation"]),
                "policy_sha256": ledger["frozen_policy_sha256"],
                "note": "Continue unattempted turns only; prior failed responses keep score zero.",
            }
        )

    def save():
        path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")

    async def schema():
        db = Database(settings.database_url)
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await db.engine.dispose()

    asyncio.run(schema())
    try:
        with TestClient(
            create_app(settings), headers={"Authorization": f"Bearer {TOKEN}"}
        ) as client:
            response(
                client,
                "/cognition/configuration",
                CognitiveConfiguration(
                    session_calls=200,
                    session_tokens=1000000,
                    experiment_calls=200,
                    experiment_tokens=2000000,
                    request_tokens=30000,
                    use_critic=False,
                ).model_dump(),
            )
            response(client, "/cognition/control", {"command": "enable_model", "provider": "meta"})

            async def register(kernel):
                for profile in PROFILES.values():
                    await register_definition(kernel, definition_text(profile), status="active")

            call(client, register)
            if resume:
                goal = {"id": next(iter(ledger["sources"].values()))["terms"]["goal_ref"]}
            else:
                goal = response(
                    client, "/goals", {"title": "Public frozen measured adaptation experiment"}
                )
                response(client, f"/goals/{goal['id']}/transition", {"status": "accepted"})

            def setup(task):
                if task["id"] in ledger["sources"]:
                    return ledger["sources"][task["id"]]
                directory = folder / "public-sources" / task["id"]
                directory.mkdir(parents=True)
                files = oracle.source_files(task)
                for name, text in files.items():
                    (directory / name).write_bytes(text.encode("utf-8"))

                async def approve(kernel):
                    candidate = await custody.create_capture(
                        kernel,
                        source_type="repository",
                        label="Public fixture " + task["id"],
                        locator=task["id"],
                        classification="owner_internal",
                        capture_method="owner_cli_repository",
                        content=capture.repository_content(directory, list(files)),
                    )
                    return await custody.approve(
                        kernel,
                        candidate["id"],
                        confirm_sha256=candidate["content_sha256"],
                        operations=[
                            "repository.inspect",
                            "repository.analyze",
                            "intent.interpret",
                            "context.reason",
                            "context.validate",
                        ],
                        scope={"items": list(files)},
                        ttl_seconds=14400,
                        principal=principal(),
                        request_id=uid(),
                    )

                source = call(client, approve)
                pending = response(
                    client,
                    "/admissions/live/setup",
                    {
                        "goal_ref": goal["id"],
                        "approval_ref": source["id"],
                        "paths": list(files),
                        "contextual": True,
                        "adaptive": True,
                        "max_calls": 16,
                        "max_tokens": 300000,
                        "ttl_seconds": 14400,
                    },
                )
                approved = call(
                    client,
                    live.approve,
                    pending["id"],
                    confirm_sha256=pending["sha256"],
                    principal=principal(),
                )
                ledger["sources"][task["id"]] = approved
                save()
                return approved

            def ask(task, arm, phase, *, conversation=None, goal_text=None):
                goals = client.get("/api/v1/goals").json()
                current_goal = next(g for g in goals if g["id"] == goal["id"])
                if current_goal["status"] == "proposed":
                    response(client, f"/goals/{goal['id']}/transition", {"status": "accepted"})
                    ledger.setdefault("disposable_goal_recoveries", []).append(
                        {
                            "before_task": task["id"],
                            "arm": arm,
                            "phase": phase,
                            "reason": (
                                "Previous failed explicit run demoted the experiment goal; "
                                "no inference retry."
                            ),
                        }
                    )
                    save()
                consent = setup(task)
                if not conversation:
                    conversation = response(
                        client,
                        "/admissions/live/conversations",
                        {"consent_ref": consent["id"], "title": f"{phase} {task['id']} {arm}"},
                    )["id"]
                before = call(client, counts)
                # Reserve worst-case room before a two-call turn. Existing checks fence each call.
                if (
                    before["provider_requests"] + prior_requests + 2 > 180
                    or before["reserved_units"] + prior_requests * 30000 + 60000 > 2000000
                ):
                    raise RuntimeError("Predeclared global envelope exhausted")
                request = {
                    "consent_ref": consent["id"],
                    "conversation_ref": conversation,
                    "goal": goal_text or goal_for(task),
                    "strategy_mode": MODES[arm],
                    "idempotency_key": f"{phase}:{task['id']}:{arm}",
                }
                started = time.monotonic()
                value = response(client, "/admissions/live/ask", request)
                elapsed = time.monotonic() - started
                return compact(value) | {"request": request, "wall_seconds": elapsed}

            for task in (t for t in corpus["tasks"] if t["split"] == "train"):
                if any(t["task_id"] == task["id"] for t in ledger["training"]):
                    continue
                value = ask(task, "A", "train")
                record = {
                    "task_id": task["id"],
                    "review": value,
                    "grade": oracle.grade(task, value["answer"]),
                }
                ledger["training"].append(record)
                save()
                if value["answer"]:
                    admission = value["result_admission_id"]
                    measurement = call(client, oracle.measure, admission, task["id"])
                    feedback = call(
                        client, adaptation.experience, admission, measurement, "train:" + task["id"]
                    )
                    record["measurement_ref"] = measurement
                    record["experience_id"] = feedback
                    extracted = ask(
                        task,
                        "A",
                        "extract",
                        conversation=value["conversation_ref"],
                        goal_text=f"Extract a reusable {task['family']} strategy from verified "
                        f"training feedback {feedback}. Cite that experience ID. State when it "
                        "applies/excludes and uncertainty. Do not copy answers or source text.",
                    )
                    record["extraction"] = extracted
                    state = call(client, adaptation.listing)
                    proposed = next(
                        (
                            lesson
                            for lesson in state["lessons"]
                            if lesson["lesson_id"] == extracted["id"]
                        ),
                        None,
                    )
                    if proposed:
                        # Public derived exports are authorized; retain exact approval hashes.
                        record["approved_public_export"] = adaptation.export_text(proposed)
                        for target in ("qualified", "active"):
                            current = next(
                                lesson
                                for lesson in call(client, adaptation.listing)["lessons"]
                                if lesson["lesson_id"] == extracted["id"]
                            )
                            call(
                                client,
                                adaptation.transition,
                                current["lesson_id"],
                                state=target,
                                expected_sha256=current["sha256"],
                                principal=principal(),
                                export_sha256=digest(record["approved_public_export"]),
                            )
                save()
                print(
                    json.dumps(
                        {
                            "phase": "train",
                            "task": task["id"],
                            "score": record["grade"]["score"],
                            **call(client, counts),
                        }
                    ),
                    flush=True,
                )

            policy = call(client, adaptation.listing)
            if resume:
                assert digest(policy) == ledger["frozen_policy_sha256"]
            else:
                ledger["frozen_policy"] = policy
                ledger["frozen_policy_sha256"] = digest(policy)
            save()
            by_id = {t["id"]: t for t in corpus["tasks"]}
            for planned in ledger["plan"]:
                if any(
                    all(row[k] == planned[k] for k in ("phase", "task_id", "arm"))
                    for row in ledger["evaluation"]
                ):
                    continue
                task = by_id[planned["task_id"]]
                assert digest(call(client, adaptation.listing)) == ledger["frozen_policy_sha256"]
                value = ask(task, planned["arm"], planned["phase"])
                grade = oracle.grade(task, value["answer"])
                record = planned | {"review": value, "grade": grade}
                # Heldout and development grades are report-only: no experience/lesson writes.
                ledger["evaluation"].append(record)
                save()
                print(
                    json.dumps(planned | {"score": grade["score"], **call(client, counts)}),
                    flush=True,
                )
            ledger["totals"] = call(client, counts)
            ledger["final_policy_sha256"] = digest(call(client, adaptation.listing))
            assert ledger["final_policy_sha256"] == ledger["frozen_policy_sha256"]
            ledger["status"] = "COMPLETE"
            save()
        replay(folder)
    except BaseException as error:
        ledger["failure"] = type(error).__name__ + ": " + str(error)
        save()
        raise


def replay(folder):
    folder = folder.resolve()
    path = folder / "adaptation-ledger.json"
    ledger = json.loads(path.read_text(encoding="utf-8"))
    with TestClient(
        create_app(settings_for(folder)), headers={"Authorization": f"Bearer {TOKEN}"}
    ) as client:
        before = call(client, counts)
        assert digest(call(client, adaptation.listing)) == ledger["frozen_policy_sha256"]
        values = [v["review"] for v in ledger["training"]] + [
            v["extraction"] for v in ledger["training"] if "extraction" in v
        ]
        values += [v["review"] for v in ledger["evaluation"]]
        for previous in values:
            retained = client.get("/api/v1/admissions/live/" + previous["id"])
            retained.raise_for_status()
            assert compact(retained.json()) == {
                k: v for k, v in previous.items() if k not in ("request", "wall_seconds")
            }
            repeated = response(client, "/admissions/live/ask", previous["request"])
            assert compact(repeated) == compact(retained.json())
        for training in ledger["training"]:
            if "experience_id" in training:
                assert (
                    call(
                        client,
                        adaptation.experience,
                        training["review"]["result_admission_id"],
                        training["measurement_ref"],
                        "train:" + training["task_id"],
                    )
                    == training["experience_id"]
                )
        after = call(client, counts)
        assert before == after
        assert digest(call(client, adaptation.listing)) == ledger["frozen_policy_sha256"]
        ledger["restart_replay"] = {
            "before": before,
            "after": after,
            "exchanges": len(values),
            "policy_unchanged": True,
            "feedback_idempotent": True,
        }
        path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
        print(json.dumps(ledger["restart_replay"]), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--approve-live", action="store_true")
    parser.add_argument("--replay-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--previous-ledger", type=Path)
    args = parser.parse_args()
    replay(args.directory) if args.replay_only else run(
        args.directory, args.approve_live, args.previous_ledger, args.resume
    )
