"""AI-FIRST-04 demonstration: verified experience, owner-approved lesson, selective reuse.

Real-model run through production Pi on *development-split* fixtures only (never held-out tasks).
Seven stages, each printed and retained in ``selective-demo.json``:

1 verified experience   an independent evaluator checks a completed review
2 reusable lesson       the model proposes it; the owner approves the exact bounded text
3 applicability         a different conversation; the selector decides per task
4 new reasoning         a relevant task receives the lesson; an unrelated task receives none
5 measurement           the independent evaluator grades both new answers
6 feedback              the measured outcome updates the lesson's evidence (dev split only)
7 restart               the app is reopened: versions, decisions and outcomes are unchanged and
                        nothing is re-dispatched to the provider
"""

import argparse
import asyncio
import json
import subprocess
import time
from pathlib import Path

from fastapi.testclient import TestClient

from alive.adaptation import oracle_v2, selection
from alive.adaptation import service as adaptation
from alive.admission import live
from alive.admission.profiles import PROFILES, definition_text
from alive.app import create_app
from alive.cognitive_schema import CognitiveConfiguration
from alive.db import Database
from alive.models import Base, uid
from alive.sources import capture, custody
from alive.sources.cli import principal
from alive.workflows.context import digest
from alive.workflows.store import register_definition
from scripts.adaptation_demo import counts, settings_for
from scripts.live_bespoke_demo import TOKEN, call, response
from scripts.selective_experiment import compact, extraction_goal, goal_for

TRAIN, RELEVANT, UNRELATED = (
    "num-03",
    "num-05",
    "par-04",
)  # boundary lesson; boundary task; trim task


def run(folder):
    folder = folder.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    settings = settings_for(folder)
    if not settings.alive_meta_api_key:
        raise ValueError("Meta credential absent; live demonstration NOT_RUN")
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        raise ValueError("Commit implementation before a live demonstration")
    corpus, lock = oracle_v2.frozen_corpus()
    tasks = {t["id"]: t for t in corpus["tasks"]}
    assert all(tasks[i]["split"] in ("train", "dev") for i in (TRAIN, RELEVANT, UNRELATED))
    record = {
        "schema": "selective-demo/v1",
        "implementation_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "corpus_lock": lock,
        "stages": {},
    }

    async def schema():
        db = Database(settings.database_url)
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await db.engine.dispose()

    asyncio.run(schema())
    with TestClient(create_app(settings), headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        response(
            client,
            "/cognition/configuration",
            CognitiveConfiguration(
                session_calls=60, session_tokens=400000, request_tokens=30000, use_critic=False
            ).model_dump(),
        )
        response(client, "/cognition/control", {"command": "enable_model", "provider": "meta"})

        async def register(kernel):
            for profile in PROFILES.values():
                await register_definition(kernel, definition_text(profile), status="active")

        call(client, register)
        goal = response(client, "/goals", {"title": "Selective adaptation demonstration"})
        response(client, f"/goals/{goal['id']}/transition", {"status": "accepted"})

        def consent_for(task):
            directory = folder / "sources" / (task["id"] + "-" + uid()[:6])
            directory.mkdir(parents=True)
            files = oracle_v2.source_files(task)
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
                    ttl_seconds=7200,
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
                    "max_calls": 12,
                    "max_tokens": 200000,
                    "ttl_seconds": 7200,
                },
            )
            return call(
                client,
                live.approve,
                pending["id"],
                confirm_sha256=pending["sha256"],
                principal=principal(),
            )

        def ask(task, consent, key, *, conversation=None, goal_text=None):
            conversation = (
                conversation
                or response(
                    client,
                    "/admissions/live/conversations",
                    {"consent_ref": consent["id"], "title": key},
                )["id"]
            )
            request = {
                "consent_ref": consent["id"],
                "conversation_ref": conversation,
                "goal": goal_text or goal_for(task),
                "strategy_mode": "selective",
                "idempotency_key": key,
            }
            began = time.monotonic()
            value = compact(response(client, "/admissions/live/ask", request))
            return value | {"request": request, "wall_seconds": time.monotonic() - began}

        def stage(number, name, **facts):
            record["stages"][f"{number}_{name}"] = facts
            print(
                json.dumps(
                    {"stage": f"{number} {name}"}
                    | {k: v for k, v in facts.items() if k != "detail"}
                ),
                flush=True,
            )

        # 1 -- verified experience
        train = tasks[TRAIN]
        train_consent = consent_for(train)
        first = ask(train, train_consent, "demo-train")
        measurement = call(client, oracle_v2.measure, first["result_admission_id"], TRAIN)
        experience = call(
            client, adaptation.experience, first["result_admission_id"], measurement, "demo"
        )
        stage(
            1,
            "verified_experience",
            task=TRAIN,
            passed_end_to_end=first["answer"]["contract_compliance"]["complete"],
            experience=experience,
        )

        # 2 -- reusable lesson, exact text approved by the owner
        extracted = ask(
            train,
            train_consent,
            "demo-extract",
            conversation=first["conversation_ref"],
            goal_text=extraction_goal(train, experience),
        )
        lesson = next(
            x
            for x in call(client, adaptation.listing)["lessons"]
            if x["lesson_id"] == extracted["id"]
        )
        export = adaptation.export_text(lesson)
        for target in ("qualified", "active"):
            current = next(
                x
                for x in call(client, adaptation.listing)["lessons"]
                if x["lesson_id"] == lesson["lesson_id"]
            )
            call(
                client,
                adaptation.transition,
                lesson["lesson_id"],
                state=target,
                expected_sha256=current["sha256"],
                principal=principal(),
                export_sha256=digest(export),
            )
        stage(
            2,
            "reusable_lesson",
            lesson=lesson["lesson_id"],
            mechanisms=lesson["proposal"]["mechanisms"],
            excluded=lesson["proposal"]["excluded_mechanisms"],
            approved_export_sha256=digest(export),
            detail=export,
        )

        # 3+4 -- two different conversations, two different decisions
        outcomes = {
            label: (tasks[task_id], consent_for(tasks[task_id]))
            for label, task_id in (("relevant", RELEVANT), ("unrelated", UNRELATED))
        }
        applied = {}
        for label, (task, consent) in outcomes.items():
            reply = ask(task, consent, f"demo-{label}-selective")
            applied[label] = reply
            chosen = reply["selection"]
            stage(
                4,
                f"reasoning_{label}",
                task=task["id"],
                decision=chosen["decision"],
                reason=chosen["no_lesson_reason"],
                task_mechanisms=chosen["task_mechanisms"],
                lessons_received=len(chosen["received"]),
                reported_used=len(chosen["reported_used"]),
            )
        # 5 -- independent measurement of both new answers
        measured = {}
        for label, reply in applied.items():
            task = outcomes[label][0]
            ref = call(client, oracle_v2.measure, reply["result_admission_id"], task["id"])
            measured[label] = ref
            stage(5, f"measurement_{label}", task=task["id"], measurement=ref)
        # 6 -- feedback: evidence about the lesson's usefulness (development split, not held-out)
        feedback = {}
        for label, reply in applied.items():
            if reply["selection"]["received"]:
                feedback[label] = call(
                    client,
                    selection.record_application,
                    reply["result_admission_id"],
                    measured[label],
                    key="demo-" + label,
                )
        standing = call(client, adaptation.listing)["lessons"]
        stage(
            6,
            "feedback",
            applications=sum(map(len, feedback.values())),
            lesson_standing=[x["utility"] for x in standing],
        )
        before = {
            "counts": call(client, counts),
            "lessons": digest(call(client, adaptation.listing)),
        }
        record |= {
            "turns": {
                "train": first,
                "extraction": extracted,
                **{f"selective_{k}": v for k, v in applied.items()},
            }
        }

    # 7 -- restart: reopen the same database in a new application instance
    with TestClient(create_app(settings), headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        for reply in applied.values():
            retained = compact(client.get("/api/v1/admissions/live/" + reply["id"]).json())
            replayed = compact(response(client, "/admissions/live/ask", reply["request"]))
            assert retained["selection"]["items_sha256"] == reply["selection"]["items_sha256"]
            assert retained["selection"]["decision"] == reply["selection"]["decision"]
            assert replayed == retained
        after = {
            "counts": call(client, counts),
            "lessons": digest(call(client, adaptation.listing)),
        }
        assert before == after
        stage(
            7,
            "restart",
            provider_requests_before=before["counts"]["provider_requests"],
            provider_requests_after=after["counts"]["provider_requests"],
            lesson_state_unchanged=True,
            decisions_unchanged=True,
        )
    record["totals"] = after["counts"]
    (folder / "selective-demo.json").write_text(
        json.dumps(record, indent=1), encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--approve-live", action="store_true")
    args = parser.parse_args()
    if not args.approve_live:
        raise SystemExit("Explicit --approve-live required; otherwise the demonstration is NOT_RUN")
    run(args.directory)
