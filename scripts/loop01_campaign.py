"""LOOP-01 live campaign: real model, disposable database, bounded dispatches.

This is a qualification script, not a product entry point. It refuses to run unless the operator
has explicitly opted in, the database target is disposable, and Pi carries the real Meta model.

It runs three controlled research tasks (one multi-document answer, one single-document answer,
one reuse probe) and one one-call full-corpus baseline. The campaign ceiling is 12 dispatches.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from alive.admission import live
from alive.admission.contracts import LiveGoal, LiveSetup
from alive.app import create_app
from alive.cognitive_schema import AutonomyCommand
from alive.config import Settings
from alive.db_target import migration_database_url
from alive.models import Goal, uid
from alive.research import service as research
from alive.research.contracts import ResearchReference
from alive.sources import capture, custody
from alive.sources.cli import principal

SOURCE_OPERATIONS = [
    "intent.interpret",
    "repository.inspect",
    "repository.analyze",
    "context.reason",
    "context.validate",
]

CORPUS = {
    "policy.md": (
        "# Returns overview\n\n"
        "This policy explains how the return process works for every customer.\n\n"
        "The request window is 30 days from delivery.\n\n"
        "Items must be unused and in their original packaging.\n"
    ),
    "refunds.md": (
        "# Refund overview\n\n"
        "This page explains how refunds are handled after an item is returned.\n\n"
        "Refunds are issued within 10 business days after inspection.\n\n"
        "The original payment method is used.\n"
    ),
    "shipping.md": (
        "# Shipping overview\n\n"
        "This page explains the available shipping options.\n\n"
        "Standard shipping takes 5 business days.\n\n"
        "Express shipping takes 2 business days.\n"
    ),
    "warranty.md": "# Warranty overview\n\nThe warranty period is 12 months from delivery.\n",
}

TASKS = [
    {
        "key": "loop01-return-refund",
        "question": (
            "What is the return request window and the refund issue time? "
            "Answer exactly as '<window>; <refund time>'."
        ),
        "expected": "30 days; 10 business days",
        "accepted": [
            "30 days; 10 business days",
            "30 days;10 business days",
            "30 days from delivery; 10 business days after inspection",
            "30 days from delivery;10 business days after inspection",
            "30 days from delivery; 10 business days",
            "30 days; 10 business days after inspection",
        ],
        "citations": [
            {"document_id": "policy.md", "quote": "The request window is 30 days from delivery."},
            {
                "document_id": "refunds.md",
                "quote": "Refunds are issued within 10 business days after inspection.",
            },
        ],
        "baseline": True,
    },
    {
        "key": "loop01-express",
        "question": "How long does express shipping take? Answer with the duration only.",
        "expected": "2 business days",
        "accepted": ["2 business days", "two business days"],
        "citations": [
            {"document_id": "shipping.md", "quote": "Express shipping takes 2 business days."}
        ],
        "baseline": False,
    },
    {
        "key": "loop01-return-reuse",
        "question": (
            "How long do customers have to request a return? Answer with the duration only."
        ),
        "expected": "30 days",
        "accepted": ["30 days", "thirty days", "30 days from delivery"],
        "citations": [
            {"document_id": "policy.md", "quote": "The request window is 30 days from delivery."}
        ],
        "baseline": False,
    },
    {
        "key": "loop01-return-reuse-fixed",
        "question": (
            "Within how many days must a customer request a return? Answer with the duration only."
        ),
        "expected": "30 days",
        "accepted": ["30 days", "thirty days", "30 days from delivery"],
        "citations": [
            {"document_id": "policy.md", "quote": "The request window is 30 days from delivery."}
        ],
        "baseline": False,
    },
]


def refused(message: str) -> None:
    print(f"NOT_RUN: {message}", file=sys.stderr)
    raise SystemExit(2)


def guard() -> Settings:
    if os.environ.get("ALIVE_LOOP01_LIVE") != "1":
        refused("set ALIVE_LOOP01_LIVE=1 to authorize live model dispatches")
    settings = Settings()
    if not settings.alive_db_target.startswith("disposable:"):
        refused("ALIVE_DB_TARGET must identify a disposable database")
    if not settings.alive_qualification:
        refused("ALIVE_QUALIFICATION=1 is required for frozen references")
    if settings.alive_model_transport != "pi":
        refused("ALIVE_MODEL_TRANSPORT must be pi for the approved production path")
    if not settings.alive_meta_api_key:
        refused("no approved Meta credential is configured")
    if not settings.database_url.startswith("sqlite+aiosqlite:"):
        refused("this qualification script uses a disposable SQLite database only")
    # FINISH-01R: resolve and refuse an ambiguous target before any engine is created.
    migration_database_url(settings)
    return settings


def corpus_root() -> Path:
    configured = os.environ.get("ALIVE_LOOP01_CORPUS", "")
    if not configured:
        refused("set ALIVE_LOOP01_CORPUS to a disposable workspace")
    root = Path(configured)
    root.mkdir(parents=True, exist_ok=True)
    for name, text in CORPUS.items():
        (root / name).write_text(text, encoding="utf-8")
    return root


async def seed(kernel, root: Path):
    async with kernel.lock, kernel.db.sessions.begin() as session:
        goal = Goal(
            id=uid(),
            instance_id=kernel.instance_id,
            title="LOOP-01 controlled research corpus",
            description="Disposable owner corpus for the first production research loop.",
            status="accepted",
        )
        session.add(goal)
        await session.flush()
        goal_id = goal.id
    paths = sorted(CORPUS)
    candidate = await custody.create_capture(
        kernel,
        source_type="repository",
        label="LOOP-01 disposable corpus",
        locator="loop01-disposable-corpus",
        classification="owner_internal",
        capture_method="owner_cli_repository",
        content=capture.repository_content(root, paths),
    )
    approval = await custody.approve(
        kernel,
        candidate["id"],
        confirm_sha256=candidate["content_sha256"],
        operations=SOURCE_OPERATIONS,
        scope={"items": paths},
        ttl_seconds=7200,
        principal=principal(),
        request_id=uid(),
    )
    return goal_id, approval, paths


def reference(task) -> ResearchReference:
    return ResearchReference(
        reference_id=task["key"],
        expected_answer=task["expected"],
        accepted_answers=task["accepted"],
        required_citations=task["citations"],
    )


def sanitize(value: dict) -> dict:
    """Remove retained source text and message bodies from the evidence file."""

    def action(item):
        chosen = item.get("action", {})
        observation = item.get("observation") or {}
        result = {
            "step": item.get("step"),
            "action": chosen.get("action"),
            "params": {
                key: chosen.get(key)
                for key in ("query", "document_id", "section", "answer", "citations", "reason")
                if chosen.get(key) not in (None, "", [])
            },
            "observation": {},
        }
        if observation.get("action") == "search":
            result["observation"] = {
                "action": "search",
                "query": observation.get("query"),
                "documents": [
                    {
                        "document_id": row.get("document_id"),
                        "line_start": row.get("line_start"),
                        "line_end": row.get("line_end"),
                        "score": row.get("score"),
                    }
                    for row in observation.get("results", [])
                ],
            }
        elif observation.get("action") == "read":
            document = observation.get("document") or {}
            result["observation"] = {
                "action": "read",
                "document_id": document.get("document_id"),
                "line_start": document.get("line_start"),
                "line_end": document.get("line_end"),
                "bytes": len(str(document.get("text", "")).encode()),
            }
        elif observation.get("verification"):
            result["observation"] = {"verification": observation["verification"]}
        elif observation.get("error"):
            result["observation"] = {"error": observation["error"]}
        elif observation.get("baseline"):
            result["observation"] = {"baseline": observation["baseline"]}
        return result

    return {
        "task_id": value.get("task_id"),
        "episode_id": value.get("episode_id"),
        "question": value.get("question"),
        "state": value.get("state"),
        "status": value.get("status"),
        "model_calls": value.get("model_calls"),
        "models": value.get("models"),
        "usage": value.get("usage"),
        "actions": [action(item) for item in value.get("actions", [])],
        "verification": value.get("verification"),
        "conclusion_status": value.get("conclusion_status"),
        "outcome": value.get("outcome"),
        "reuse": value.get("reuse"),
        "previous_episode": (
            None
            if not value.get("previous_episode")
            else {
                "episode_id": value["previous_episode"].get("episode_id"),
                "verified_success": value["previous_episode"].get("verified_success"),
                "verification": value["previous_episode"].get("verification"),
                "first_action": value["previous_episode"].get("first_action"),
            }
        ),
        "message_senders": [item.get("sender") for item in value.get("messages", [])],
    }


async def orchestrate(client, evidence: dict, args) -> None:
    kernel = client.app.state.kernel
    if not kernel.ready:
        refused("database unavailable or migrations pending")
    from alive.admission.profiles import PROFILES, definition_text
    from alive.workflows.store import register_definition

    for profile in PROFILES.values():
        await register_definition(kernel, definition_text(profile), status="active", source="admin")
    if args.new_consent_from:
        async with kernel.db.sessions() as session:
            previous = await live.consent(session, kernel, args.new_consent_from)
        setup = await live.prepare(
            kernel,
            LiveSetup(
                goal_ref=previous["terms"]["goal_ref"],
                approval_ref=previous["terms"]["approval_ref"],
                paths=previous["terms"]["paths"],
                max_calls=args.max_calls,
                max_tokens=120000,
                contextual=True,
                research=True,
            ),
        )
        approved = await live.approve(
            kernel,
            setup["id"],
            confirm_sha256=setup["sha256"],
            principal=principal(),
        )
        if approved["state"] != "approved":
            refused("owner consent was not approved")
        consent_id = setup["id"]
    elif args.consent_id:
        consent_id = args.consent_id
        async with kernel.db.sessions() as session:
            approved = await live.consent(session, kernel, consent_id)
        if approved["state"] != "approved":
            refused("the retained owner consent is not approved")
    else:
        root = Path(os.environ["ALIVE_LOOP01_CORPUS"])
        goal_id, approval, paths = await seed(kernel, root)
        setup = await live.prepare(
            kernel,
            LiveSetup(
                goal_ref=goal_id,
                approval_ref=approval["id"],
                paths=paths,
                max_calls=4,
                max_tokens=120000,
                contextual=True,
                research=True,
            ),
        )
        approved = await live.approve(
            kernel,
            setup["id"],
            confirm_sha256=setup["sha256"],
            principal=principal(),
        )
        if approved["state"] != "approved":
            refused("owner consent was not approved")
        consent_id = setup["id"]
    await client.app.state.cognition.command(
        AutonomyCommand(command="enable_model", provider="meta")
    )
    evidence["consent"] = {
        "id": consent_id,
        "source_ref": approved["terms"]["source"]["resources"]["source_ref"],
        "paths": approved["terms"]["paths"],
        "research": {
            key: approved["terms"]["research"][key]
            for key in (
                "role",
                "model",
                "max_model_calls",
                "max_output_tokens",
                "max_steps",
                "max_tokens",
            )
        },
    }
    for index, task in enumerate(TASKS):
        if args.only_key and task["key"] != args.only_key:
            continue
        if index < args.start_index or (args.smoke and index > args.start_index):
            continue
        async with kernel.db.sessions() as session:
            current = await live.consent(session, kernel, consent_id)
        request = LiveGoal(
            consent_ref=consent_id,
            goal=task["question"],
            idempotency_key=task["key"],
            task_mode="research",
            reference=reference(task),
        )
        value = await live.ask(client.app, request)
        evidence["tasks"].append(
            {"key": task["key"], "expected": task["expected"], **sanitize(value)}
        )
        print(f"task {task['key']}: {value['state']} {value['verification']['status']}")
        if task.get("baseline"):
            baseline_request = LiveGoal(
                consent_ref=consent_id,
                goal=task["question"],
                idempotency_key=task["key"] + "-baseline",
                task_mode="research",
                reference=reference(task),
            )
            baseline = await research.run(
                client.app,
                baseline_request,
                current,
                reference=reference(task),
                baseline=True,
            )
            evidence["baseline"] = {
                "key": task["key"],
                "comparison": "one call with full approved corpus, no tool round-trip",
                **sanitize(baseline),
            }
            print(
                f"baseline {task['key']}: {baseline['state']} {baseline['verification']['status']}"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="docs/intelligence/loop-01-live-evidence.json")
    parser.add_argument("--smoke", action="store_true", help="run only one task")
    parser.add_argument("--start-index", type=int, default=0, help="skip earlier tasks")
    parser.add_argument("--consent-id", default="", help="reuse an approved consent")
    parser.add_argument("--new-consent-from", default="", help="derive a consent from another")
    parser.add_argument("--max-calls", type=int, default=4, help="new consent call ceiling")
    parser.add_argument("--only-key", default="", help="run one declared task")
    args = parser.parse_args()

    settings = guard()
    corpus_root()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    token = os.environ.get("ALIVE_API_TOKEN") or "loop01-qualification-token-000000000000"
    settings.alive_api_token = token
    app = create_app(settings, include_experiments=False)
    evidence = {
        "milestone": "ALIVE-LOOP-01",
        "started_at": datetime.now(UTC).isoformat(),
        "database_target": settings.alive_db_target.split(":", 1)[1],
        "model_transport": settings.alive_model_transport,
        "model": settings.alive_meta_model,
        "campaign_dispatch_ceiling": 12,
        "tasks": [],
        "baseline": None,
    }
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as client:
        client.portal.call(lambda: orchestrate(client, evidence, args))
    evidence["finished_at"] = datetime.now(UTC).isoformat()
    evidence["dispatches"] = sum(item.get("model_calls", 0) for item in evidence["tasks"])
    if evidence["baseline"]:
        evidence["dispatches"] += evidence["baseline"].get("model_calls", 0)
    evidence["within_campaign_ceiling"] = evidence["dispatches"] <= 12
    out.write_text(
        json.dumps(evidence, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"wrote {out} ({evidence['dispatches']} dispatches)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
