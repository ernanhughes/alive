"""AI-FIRST-04 matched A/B/C/D experiment through production Pi on the frozen v2 corpus.

--approve-live authorizes only this frozen public corpus, bounded public derived lesson
exports, and the finite envelope below. No automatic retries. The oracle executes author-owned
fixture code, never code returned by a model.

Protocol enforced here, not left to discipline:
* the corpus/oracle lock must match before any call;
* the held-out set cannot be opened until development is complete and the policy is frozen
  (--open-heldout), and the policy digest is asserted unchanged on every later turn;
* held-out and ablation outcomes never write learned state;
* every turn is recorded, including failures, truncations and refusals.
"""

import argparse
import asyncio
import json
import random
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from alive.adaptation import oracle_v2, selection
from alive.adaptation import service as adaptation
from alive.admission import live
from alive.admission.profiles import PROFILES, definition_text
from alive.app import create_app
from alive.cognitive_models import ModelInvocation
from alive.cognitive_schema import CognitiveConfiguration
from alive.db import Database
from alive.models import Base, uid
from alive.sources import capture, custody
from alive.sources.cli import principal
from alive.workflows.context import digest
from alive.workflows.store import register_definition
from scripts.adaptation_demo import counts, settings_for
from scripts.live_bespoke_demo import TOKEN, call, response

SEED = 4401
MODES = {"A": "stateless", "B": "contextual", "C": "learned", "D": "selective"}
LIMITS = {"provider_requests": 560, "conservative_units": 8_000_000}
SESSION_ROLL = 170  # Governor session ceiling is 200 calls; roll before reaching it
REPEATS = ["num-06", "sta-06", "def-08", "err-09"]  # predeclared; mixed defective and correct
ABLATION_TASKS = 6
ABLATION_CONDITIONS = (
    "R1_one_relevant",
    "R2_one_irrelevant",
    "R3_mixed_three",
    "R4_three_irrelevant",
)
REFERENCE_FAILURES = ("lesson_not_supplied", "historical_reference_not_supplied")


def plan(corpus):
    rng = random.Random(SEED)
    by_split = {s: [t for t in corpus["tasks"] if t["split"] == s] for s in ("dev", "heldout")}
    runs = []
    for phase, arms in (("dev", "AD"), ("heldout", "ABCD")):
        tasks = list(by_split[phase])
        rng.shuffle(tasks)
        for task in tasks:
            order = list(arms)
            rng.shuffle(order)
            runs.extend({"phase": phase, "task_id": task["id"], "arm": a} for a in order)
    for task_id in REPEATS:
        order = list("ABCD")
        rng.shuffle(order)
        runs.extend({"phase": "repeat", "task_id": task_id, "arm": a} for a in order)
    return runs


def goal_for(task):
    return (
        f"Review the supplied implementation against this contract: {task['contract']} "
        "Identify any real defect, explain why and recommend a minimal correction if needed. "
        "For every named input case in README.md give the result the supplied code produces and "
        "the result the contract requires (a JSON value or ERROR:ExceptionName) in predictions, "
        "and set issue_present. Do not invent defects in correct code."
    )


def extraction_goal(task, experience):
    return (
        f"Extract a reusable {task['family']} strategy from verified training feedback "
        f"{experience}. This is a lesson-extraction request, not a review: return it in the "
        "lesson_proposal field with family, strategy, applies_when, not_when, "
        "supporting_experience_ids (cite that experience ID), mechanisms (the closed-vocabulary "
        "failure mechanisms it addresses), excluded_mechanisms (mechanisms it must not be applied "
        "to) and uncertainty. The lesson_proposal field must be present and not null; the answer "
        "field may be one short sentence. Do not copy answers, function names or source text."
    )


def compact(value):
    result = value.get("result_admission") or {}
    # A continuation turn runs on the exchange's own admission rather than a result admission.
    run = (result or value.get("admission") or {}).get("run") or {}
    return {
        k: value.get(k)
        for k in (
            "id",
            "goal",
            "conversation_ref",
            "answer",
            "context",
            "model_calls",
            "status",
            "availability",
            "followup",
            "selection",
        )
    } | {
        "result_admission_id": result.get("id"),
        "run": {"status": run.get("status"), "terminal_reason": run.get("terminal_reason")},
        "calls": [
            {
                "id": c["id"],
                "status": c["status"],
                "model": c["model"],
                "usage": c["usage"],
                "latency_ms": c["latency_ms"],
                "provenance": c["inference_provenance"],
                "provider_receipts": [
                    {
                        k: r[k]
                        for k in (
                            "request_id",
                            "http_status",
                            "response_sha256",
                            "model_requested",
                            "model_observed",
                            "latency_ms",
                        )
                    }
                    for r in c["provider_receipts"]
                ],
            }
            for c in value.get("calls", [])
        ],
    }


def usage_of(record):
    calls = record["calls"]
    return {
        "provider_requests": record["model_calls"],
        "tokens": sum((c["usage"] or {}).get("total_tokens", 0) for c in calls),
        "invocation_latency_ms": sum(c["latency_ms"] or 0 for c in calls),
    }


async def raw_model_output(kernel, record):
    """The retained raw output of a validated invocation whose answer a later check refused."""
    async with kernel.db.sessions() as session:
        rows = await session.scalars(
            select(ModelInvocation).where(
                ModelInvocation.id.in_([c["id"] for c in record["calls"]]),
                ModelInvocation.role == "contextual_reasoner",
            )
        )
        for row in rows:
            if row.status == "validated" and row.output_json:
                return row.output_json
    return None


def stable(value):
    """History is append-only: a later independent outcome may be attached to a retained turn."""
    value = dict(value)
    if value.get("selection"):
        value["selection"] = {
            k: v for k, v in value["selection"].items() if k != "independent_outcome"
        }
    return value


def run(folder, approve_live, *, through="ablate", open_heldout=False, limit_train=None):
    if not approve_live:
        raise ValueError("Explicit --approve-live required; otherwise live qualification NOT_RUN")
    folder = folder.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    settings = settings_for(folder)
    if not settings.alive_meta_api_key:
        raise ValueError("Meta credential absent; live qualification NOT_RUN")
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        raise ValueError("Commit implementation, corpus and oracle lock before live qualification")
    corpus, lock = oracle_v2.frozen_corpus()
    tasks = {t["id"]: t for t in corpus["tasks"]}
    path = folder / "selective-ledger.json"
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if path.exists():
        ledger = json.loads(path.read_text(encoding="utf-8"))
        assert ledger["corpus_lock"] == lock and ledger["plan"] == plan(corpus)
        drift = subprocess.run(
            ["git", "diff", "--exit-code", ledger["implementation_sha"], "--", "alive"]
        ).returncode
        if drift and ledger["evaluation"]:
            raise RuntimeError("alive/ changed after evaluated turns began; start a new run")
        ledger.setdefault("resumptions", []).append(
            {
                "harness_sha": head,
                "completed_evaluations": len(ledger["evaluation"]),
                # Allowed only while training is the sole completed phase: evaluated arms must
                # all run on one implementation. The change is disclosed, never hidden.
                "rebased_implementation_from": ledger["implementation_sha"] if drift else None,
                "alive_diff": subprocess.check_output(
                    ["git", "diff", "--stat", ledger["implementation_sha"], "--", "alive"],
                    text=True,
                )
                if drift
                else None,
            }
        )
        ledger["implementation_sha"] = head
    else:
        ledger = {
            "schema": "selective-live/v1",
            "status": "INCOMPLETE",
            "implementation_sha": head,
            "corpus_lock": lock,
            "plan": plan(corpus),
            "seed": SEED,
            "limits": LIMITS,
            "model": "muse-spark-1.3-contributor",
            "transport": "production Pi / network",
            "arms": MODES,
            "repeats": REPEATS,
            "cost": "unknown; no authoritative currency tariff available",
            "selection_policy": {
                "id": selection.POLICY,
                "allow_unproven": selection.ALLOW_UNPROVEN,
                "max_selected": selection.MAX_SELECTED,
            },
            "training": [],
            "evaluation": [],
            "ablation": [],
            "sources": {},
        }
    started = {"requests": 0}

    def save():
        path.write_text(json.dumps(ledger, indent=1), encoding="utf-8", newline="\n")

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
            configuration = CognitiveConfiguration(
                session_calls=200,
                session_tokens=1000000,
                experiment_calls=500,
                experiment_tokens=2000000,
                request_tokens=30000,
                use_critic=False,
            ).model_dump()

            def roll_session():
                response(client, "/cognition/control", {"command": "new_session"})
                response(
                    client, "/cognition/control", {"command": "enable_model", "provider": "meta"}
                )
                started["requests"] = call(client, counts)["provider_requests"]

            response(client, "/cognition/configuration", configuration)
            response(client, "/cognition/control", {"command": "enable_model", "provider": "meta"})

            async def register(kernel):
                for profile in PROFILES.values():
                    await register_definition(kernel, definition_text(profile), status="active")

            call(client, register)
            if ledger["sources"]:
                goal = {"id": next(iter(ledger["sources"].values()))["terms"]["goal_ref"]}
            else:
                goal = response(
                    client, "/goals", {"title": "Public frozen selective adaptation experiment"}
                )
                response(client, f"/goals/{goal['id']}/transition", {"status": "accepted"})
            roll_session()

            def setup(task):
                known = ledger["sources"].get(task["id"])
                if known and datetime.fromisoformat(known["terms"]["expires_at"]) > (
                    datetime.now(UTC) + timedelta(minutes=15)
                ):
                    return known
                directory = folder / "public-sources" / (task["id"] + "-" + uid()[:8])
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
                        ttl_seconds=21600,
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
                        "max_calls": 30,
                        "max_tokens": 450000,
                        "ttl_seconds": 21600,
                    },
                )
                approved = call(
                    client,
                    live.approve,
                    pending["id"],
                    confirm_sha256=pending["sha256"],
                    principal=principal(),
                )
                if known:
                    ledger.setdefault("superseded_sources", []).append(known["id"])
                ledger["sources"][task["id"]] = approved
                save()
                return approved

            def keep_goal_accepted():
                current = next(
                    g for g in client.get("/api/v1/goals").json() if g["id"] == goal["id"]
                )
                if current["status"] == "proposed":
                    response(client, f"/goals/{goal['id']}/transition", {"status": "accepted"})
                    ledger.setdefault("goal_recoveries", []).append(
                        "failed explicit run returned the disposable goal to proposed; no retry"
                    )

            def ask(task, arm, key, *, conversation=None, goal_text=None, lessons=None, why=None):
                keep_goal_accepted()
                consent = setup(task)
                if not conversation:
                    conversation = response(
                        client,
                        "/admissions/live/conversations",
                        {"consent_ref": consent["id"], "title": key},
                    )["id"]
                before = call(client, counts)
                if before["provider_requests"] - started["requests"] + 2 > SESSION_ROLL:
                    roll_session()
                    before = call(client, counts)
                if (
                    before["provider_requests"] + 2 > LIMITS["provider_requests"]
                    or before["reserved_units"] + 60000 > LIMITS["conservative_units"]
                ):
                    raise RuntimeError("Predeclared global envelope exhausted")
                request = {
                    "consent_ref": consent["id"],
                    "conversation_ref": conversation,
                    "goal": goal_text or goal_for(task),
                    "strategy_mode": MODES[arm],
                    "idempotency_key": key[:60],
                }
                began = time.monotonic()
                if lessons is None:
                    value = response(client, "/admissions/live/ask", request)
                else:
                    with selection.evaluation_override(lessons, why or "evaluation"):
                        value = response(client, "/admissions/live/ask", request)
                record = compact(value)
                record["request"] = request
                record["wall_seconds"] = time.monotonic() - began
                record["usage"] = usage_of(record)
                return record

            def grade(task, record):
                answer = record["answer"]
                failure = None
                if answer is None:
                    failure = (
                        record["run"]["terminal_reason"]
                        or record["availability"]
                        or "no_validated_answer"
                    )
                    raw = call(client, raw_model_output, record)
                    answer = raw
                valid = record["answer"] is not None
                return oracle_v2.grade(task, answer, run_failure=failure, reference_valid=valid), (
                    answer if record["answer"] is None else None
                )

            def measured(task, record, raw):
                """Bind the independent measurement to a persisted admission (dev/train only)."""
                admission = record["result_admission_id"]
                if record["answer"] is not None:
                    return call(client, oracle_v2.measure, admission, task["id"])
                if admission is None:
                    return None
                reason = record["run"]["terminal_reason"] or "no_validated_answer"
                return call(
                    client, oracle_v2.measure_failed_run, admission, task["id"], reason, answer=raw
                )

            def record_turn(phase, task, arm, key, **extra):
                record = ask(task, arm, key, **extra)
                result, raw = grade(task, record)
                entry = {
                    "phase": phase,
                    "task_id": task["id"],
                    "arm": arm,
                    "key": key,
                    "review": record,
                    "grade": result,
                    "raw_refused_output": raw,
                }
                print(
                    json.dumps(
                        {
                            "phase": phase,
                            "task": task["id"],
                            "arm": arm,
                            "key": key,
                            "end_to_end": result["end_to_end"],
                            "semantic": result["dimensions"]["semantic"],
                            "decision": (record.get("selection") or {}).get("decision"),
                            **call(client, counts),
                        }
                    ),
                    flush=True,
                )
                return entry

            def find_lesson(extracted):
                return next(
                    (
                        x
                        for x in call(client, adaptation.listing)["lessons"]
                        if x["lesson_id"] == extracted["id"]
                    ),
                    None,
                )

            # ------------------------------------------------------------ training
            trained = 0
            for task in (t for t in corpus["tasks"] if t["split"] == "train"):
                if any(r["task_id"] == task["id"] for r in ledger["training"]):
                    continue
                if limit_train is not None and trained >= limit_train:
                    break
                trained += 1
                entry = record_turn("train", task, "A", "train:" + task["id"])
                record = entry["review"]
                ledger["training"].append(entry)
                save()
                if record["answer"] is None:
                    continue
                admission = record["result_admission_id"]
                measurement = measured(task, record, None)
                feedback = call(
                    client, adaptation.experience, admission, measurement, "train:" + task["id"]
                )
                entry |= {"measurement_ref": measurement, "experience_id": feedback}
                extracted = ask(
                    task,
                    "A",
                    "extract:" + task["id"],
                    conversation=record["conversation_ref"],
                    goal_text=extraction_goal(task, feedback),
                )
                entry["extraction"] = extracted
                proposed = find_lesson(extracted)
                if proposed is None:
                    # Training-state preparation, not an evaluated arm: one declared, counted retry.
                    entry["extraction_retry"] = ask(
                        task,
                        "A",
                        "extract2:" + task["id"],
                        conversation=record["conversation_ref"],
                        goal_text=extraction_goal(task, feedback),
                    )
                    proposed = find_lesson(entry["extraction_retry"])
                if proposed:
                    entry["approved_public_export"] = adaptation.export_text(proposed)
                    for target in ("qualified", "active"):
                        current = next(
                            x
                            for x in call(client, adaptation.listing)["lessons"]
                            if x["lesson_id"] == proposed["lesson_id"]
                        )
                        call(
                            client,
                            adaptation.transition,
                            current["lesson_id"],
                            state=target,
                            expected_sha256=current["sha256"],
                            principal=principal(),
                            export_sha256=digest(entry["approved_public_export"]),
                        )
                save()
            if through == "train" or limit_train is not None:
                save()
                return

            # ------------------------------------------------------------ development
            roll_session()
            done = {(r["phase"], r["task_id"], r["arm"]) for r in ledger["evaluation"]}
            for planned in ledger["plan"]:
                if planned["phase"] != "dev" or ("dev", planned["task_id"], planned["arm"]) in done:
                    continue
                task = tasks[planned["task_id"]]
                entry = record_turn(
                    "dev", task, planned["arm"], f"dev:{task['id']}:{planned['arm']}"
                )
                entry["measurement_ref"] = measured(
                    task, entry["review"], entry["raw_refused_output"]
                )
                ledger["evaluation"].append(entry)
                save()
                pair = {
                    e["arm"]: e
                    for e in ledger["evaluation"]
                    if e["phase"] == "dev" and e["task_id"] == task["id"]
                }
                if len(pair) == 2 and "applications" not in pair["D"]:
                    treated, baseline = pair["D"], pair["A"]
                    if (
                        (treated["review"].get("selection") or {}).get("selected")
                        and treated["measurement_ref"]
                        and baseline["measurement_ref"]
                    ):
                        # Development evidence: a paired outcome that updates the lesson's standing.
                        treated["applications"] = call(
                            client,
                            selection.record_application,
                            treated["review"]["result_admission_id"],
                            treated["measurement_ref"],
                            baseline_measurement_ref=baseline["measurement_ref"],
                        )
                    else:
                        treated["applications"] = []
                    save()
            if "dev_policy" not in ledger:
                policy = call(client, adaptation.listing)
                ledger["dev_policy"] = policy
                ledger["frozen_policy_sha256"] = digest(policy)
                ledger["dev_complete"] = True
                save()
            if through == "dev" or not open_heldout:
                print("development complete; held-out set not opened", flush=True)
                return

            # ------------------------------------------------------------ held-out + repeats
            roll_session()
            for planned in ledger["plan"]:
                if planned["phase"] == "dev" or (
                    planned["phase"],
                    planned["task_id"],
                    planned["arm"],
                ) in {(r["phase"], r["task_id"], r["arm"]) for r in ledger["evaluation"]}:
                    continue
                assert digest(call(client, adaptation.listing)) == ledger["frozen_policy_sha256"]
                task = tasks[planned["task_id"]]
                key = f"{planned['phase']}:{task['id']}:{planned['arm']}"
                entry = record_turn(planned["phase"], task, planned["arm"], key)
                ledger["evaluation"].append(entry)  # report-only: no experience or lesson write
                save()
            ledger["policy_unchanged_after_heldout"] = (
                digest(call(client, adaptation.listing)) == ledger["frozen_policy_sha256"]
            )
            assert ledger["policy_unchanged_after_heldout"]
            if through != "ablate":
                return

            # ------------------------------------------------------------ relevance / quantity
            ablate(client, ledger, corpus, tasks, record_turn, save)
            ledger["totals"] = call(client, counts)
            ledger["status"] = "COMPLETE"
            save()
        replay(folder)
    except BaseException as error:
        ledger["failure"] = type(error).__name__ + ": " + str(error)
        save()
        raise


async def lessons_by_origin(kernel):
    """lesson id -> originating training task, from the supporting independent experience."""
    out = {}
    async with kernel.db.sessions() as session:
        experiences = {
            r.id: adaptation.value(r)
            for r in await adaptation.rows(session, kernel, adaptation.EXPERIENCE)
        }
        for row in (await adaptation.latest(session, kernel)).values():
            body = adaptation.value(row)
            first = body["proposal"]["supporting_experience_ids"][0]
            if body["state"] == "active" and first in experiences:
                out[body["lesson_id"]] = experiences[first]["task_id"]
    return out


def ablate(client, ledger, corpus, tasks, record_turn, save):
    """Relevance vs quantity on development tasks, relevance fixed by independent task analysis."""
    origin = call(client, lessons_by_origin)
    done = {(r["task_id"], r["condition"]) for r in ledger["ablation"]}
    chosen = []
    for planned in ledger["plan"]:
        task = tasks[planned["task_id"]]
        if planned["phase"] != "dev" or planned["arm"] != "A" or task in chosen:
            continue
        gold = set(task["mechanisms"])
        relevant = sorted(i for i, t in origin.items() if gold & set(tasks[t]["mechanisms"]))
        irrelevant = sorted(
            i
            for i, t in origin.items()
            if not gold & set(tasks[t]["mechanisms"]) and tasks[t]["family"] != task["family"]
        )
        if relevant and len(irrelevant) >= 3:
            chosen.append(task)
            task["_ablation"] = (relevant, irrelevant)
        if len(chosen) == ABLATION_TASKS:
            break
    for task in chosen:
        relevant, irrelevant = task.pop("_ablation")
        sets = {
            "R1_one_relevant": relevant[:1],
            "R2_one_irrelevant": irrelevant[:1],
            "R3_mixed_three": relevant[:1] + irrelevant[:2],
            "R4_three_irrelevant": irrelevant[:3],
        }
        for condition, lessons in sets.items():
            if (task["id"], condition) in done:
                continue
            entry = record_turn(
                "ablation",
                task,
                "D",
                f"ablate:{task['id']}:{condition}"[:60],
                lessons=lessons,
                why="relevance-quantity-ablation:" + condition,
            )
            entry |= {"condition": condition, "lessons": lessons, "relevant_lessons": relevant[:1]}
            ledger["ablation"].append(entry)
            save()


def positive(folder, approve_live):
    """Lesson ablation for predeclared positive-transfer candidates (A failed, D passed)."""
    if not approve_live:
        raise ValueError("Explicit --approve-live required")
    folder = folder.resolve()
    settings = settings_for(folder)
    corpus, lock = oracle_v2.frozen_corpus()
    tasks = {t["id"]: t for t in corpus["tasks"]}
    path = folder / "selective-ledger.json"
    ledger = json.loads(path.read_text(encoding="utf-8"))
    assert ledger["corpus_lock"] == lock and ledger.get("policy_unchanged_after_heldout")
    by_key = {(r["phase"], r["task_id"], r["arm"]): r for r in ledger["evaluation"]}
    candidates = []
    for (phase, task_id, arm), treated in by_key.items():
        base = by_key.get((phase, task_id, "A"))
        if phase == "heldout" and arm == "D" and base:
            if (
                treated["grade"]["end_to_end"]
                and not base["grade"]["end_to_end"]
                and (treated["review"]["selection"] or {}).get("selected")
            ):
                candidates.append(treated)
    candidates = candidates[:4]
    ledger["positive_candidates"] = [c["task_id"] for c in candidates]
    done = {r["key"] for r in ledger.setdefault("positive_ablation", [])}
    with TestClient(create_app(settings), headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        response(client, "/cognition/control", {"command": "new_session"})
        response(client, "/cognition/control", {"command": "enable_model", "provider": "meta"})
        for treated in candidates:
            task = tasks[treated["task_id"]]
            lessons = [s["lesson_id"] for s in treated["review"]["selection"]["selected"]]
            for condition, ids in (("with_lesson", lessons), ("without_lesson", [])):
                for repetition in (1, 2):
                    key = f"pos:{task['id']}:{condition}:{repetition}"
                    if key in done:
                        continue
                    consent = ledger["sources"][task["id"]]
                    conversation = response(
                        client,
                        "/admissions/live/conversations",
                        {"consent_ref": consent["id"], "title": key},
                    )["id"]
                    request = {
                        "consent_ref": consent["id"],
                        "conversation_ref": conversation,
                        "goal": goal_for(task),
                        "strategy_mode": "selective",
                        "idempotency_key": key[:60],
                    }
                    with selection.evaluation_override(
                        ids, "positive-transfer-ablation:" + condition
                    ):
                        value = response(client, "/admissions/live/ask", request)
                    record = compact(value) | {"request": request}
                    answer = record["answer"]
                    result = oracle_v2.grade(
                        task,
                        answer,
                        run_failure=None
                        if answer
                        else (record["run"]["terminal_reason"] or "no_answer"),
                        reference_valid=answer is not None,
                    )
                    ledger["positive_ablation"].append(
                        {
                            "key": key,
                            "task_id": task["id"],
                            "condition": condition,
                            "repetition": repetition,
                            "lessons": ids,
                            "review": record,
                            "grade": result,
                        }
                    )
                    path.write_text(json.dumps(ledger, indent=1), encoding="utf-8", newline="\n")
                    print(json.dumps({"key": key, "end_to_end": result["end_to_end"]}), flush=True)


def replay(folder):
    """Restart, re-read and re-submit every retained request: no provider request may occur."""
    folder = folder.resolve()
    path = folder / "selective-ledger.json"
    ledger = json.loads(path.read_text(encoding="utf-8"))
    with TestClient(
        create_app(settings_for(folder)), headers={"Authorization": f"Bearer {TOKEN}"}
    ) as client:
        before = call(client, counts)
        policy_before = digest(call(client, adaptation.listing))
        values = [e["review"] for e in ledger["training"]]
        for key in ("extraction", "extraction_retry"):
            values += [e[key] for e in ledger["training"] if key in e]
        values += [e["review"] for e in ledger["evaluation"] + ledger["ablation"]]
        values += [e["review"] for e in ledger.get("positive_ablation", [])]
        checked = 0
        for previous in values:
            retained = client.get("/api/v1/admissions/live/" + previous["id"])
            retained.raise_for_status()
            assert stable(compact(retained.json())) == stable(
                {k: v for k, v in previous.items() if k not in ("request", "wall_seconds", "usage")}
            )
            repeated = response(client, "/admissions/live/ask", previous["request"])
            assert stable(compact(repeated)) == stable(compact(retained.json()))
            checked += 1
        after = call(client, counts)
        assert before == after
        assert digest(call(client, adaptation.listing)) == policy_before
        ledger["restart_replay"] = {
            "before": before,
            "after": after,
            "exchanges": checked,
            "policy_unchanged": True,
        }
        path.write_text(json.dumps(ledger, indent=1), encoding="utf-8", newline="\n")
        print(json.dumps(ledger["restart_replay"]), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run", "positive", "replay"])
    parser.add_argument("directory", type=Path)
    parser.add_argument("--approve-live", action="store_true")
    parser.add_argument(
        "--through", choices=["train", "dev", "heldout", "ablate"], default="ablate"
    )
    parser.add_argument("--open-heldout", action="store_true")
    parser.add_argument("--limit-train", type=int)
    args = parser.parse_args()
    if args.command == "replay":
        replay(args.directory)
    elif args.command == "positive":
        positive(args.directory, args.approve_live)
    else:
        run(
            args.directory,
            args.approve_live,
            through=args.through,
            open_heldout=args.open_heldout,
            limit_train=args.limit_train,
        )
