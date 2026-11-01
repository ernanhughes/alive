"""Owner-local LIVE qualification through production Pi; never substitutes a fake provider.

Review --help and SOURCE / CASES below before granting --approve-live. All state goes into
a new disposable directory. Credentials are read by Settings and are never written to the ledger.
"""

import argparse
import asyncio
import json
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from alive.admission import live
from alive.admission.profiles import ANALYSIS, PROFILES, definition_text
from alive.app import create_app
from alive.bespoke.recipes import load_catalogue
from alive.config import Settings
from alive.db import Database
from alive.intent.recommend import eligibility
from alive.models import Base, uid
from alive.pi.models import PiProviderRequest
from alive.sources import capture, custody
from alive.sources.cli import principal
from alive.workflows.store import register_definition

SOURCE = {
    "README.md": "# Public toy arithmetic repository\nmean should return the arithmetic mean.\n",
    "mean.py": "def mean(values):\n    return sum(values) / (len(values) + 1)\n",
}
# Frozen owner-reviewable labels, independent of model output. No tuning after the run.
CASES = [
    {
        "goal": "Review the supplied repository for bugs that prevent shipping.",
        "expected": ANALYSIS,
    },
    {
        "goal": "Check whether mean([2, 4]) returns the correct arithmetic mean.",
        "expected": ANALYSIS,
    },
    {"goal": "Write a sonnet about autumn; do not review the repository.", "expected": None},
]
TOKEN = "owner-local-live-demo-disposable-token"


def call(client, function, *args, **kwargs):
    return client.portal.call(lambda: function(client.app.state.kernel, *args, **kwargs))


def response(client, path, body):
    value = client.post("/api/v1" + path, json=body)
    value.raise_for_status()
    return value.json()


def verify_history(folder):
    """Restart-only verification, including a ledger produced by the browser scenario."""
    folder = folder.resolve()
    path = folder / "evidence-ledger.json"
    ledger = json.loads(path.read_text(encoding="utf-8"))
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{folder / 'demo.db'}",
        alive_workspace=folder / "workspace",
        alive_api_token=TOKEN,
        alive_model_transport="pi",
        alive_embeddings_enabled=False,
    )
    with TestClient(create_app(settings), headers={"Authorization": f"Bearer {TOKEN}"}) as client:

        async def count(kernel):
            async with kernel.db.sessions() as session:
                return await session.scalar(select(func.count()).select_from(PiProviderRequest))

        before = call(client, count)
        history = client.get("/api/v1/admissions/live")
        history.raise_for_status()
        for exchange in ledger["exchanges"]:
            retained = client.get("/api/v1/admissions/live/" + exchange["id"])
            retained.raise_for_status()
            assert retained.json()["calls"] == exchange["calls"]
            assert retained.json()["report"] == exchange["report"]
            assert retained.json().get("inspection") == exchange.get("inspection")

            async def baseline(kernel):
                async with kernel.db.sessions() as session:
                    options = await eligibility(
                        session,
                        kernel,
                        load_catalogue(),
                        exchange["goal"],
                        "unclear",
                        exchange["source"]["resources"]["source_ref"],
                        sorted(SOURCE),
                    )
                    eligible = [c for c in options.values() if c.eligible]
                    return (
                        max(eligible, key=lambda c: c.suitability).recipe.id if eligible else None
                    )

            exchange["deterministic_choice"] = call(client, baseline)
        after = call(client, count)
        assert before == after and len(history.json()["exchanges"]) == 3
        ledger["restart"] = {
            "provider_requests_before": before,
            "provider_requests_after": after,
            "no_redispatch": before == after,
            "retained_exchanges": 3,
        }
    for exchange, case in zip(ledger["exchanges"], CASES, strict=True):
        record = exchange["recommendation"]["record"] if exchange["recommendation"] else None
        chosen = (
            record["recommendation"]["recipe_id"] if record and record["recommendation"] else None
        )
        exchange["independent_label"] = case["expected"]
        exchange["live_choice"] = chosen
        exchange["correct_choice"] = chosen == case["expected"]
        exchange["fixed_choice"] = ANALYSIS
    ledger["comparison"] = {}
    for name, field in (
        ("live_hybrid", "live_choice"),
        ("deterministic", "deterministic_choice"),
        ("fixed_analysis", "fixed_choice"),
    ):
        ledger["comparison"][name] = {
            "correct": sum(e[field] == e["independent_label"] for e in ledger["exchanges"]),
            "false_choices": sum(
                e[field] is not None and e[field] != e["independent_label"]
                for e in ledger["exchanges"]
            ),
            "abstentions": sum(e[field] is None for e in ledger["exchanges"]),
        }
    ledger["status"] = "LIVE_DEMONSTRATED; history retained after restart without redispatch"
    path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": ledger["status"],
                "restart": ledger["restart"],
                "comparison": ledger["comparison"],
            },
            indent=2,
        )
    )


def demo(
    folder, *, approve_live=False, max_calls=6, max_tokens=200000, model=None, setup_only=False
):
    if not approve_live:
        raise ValueError("Review SOURCE, CASES and budget, then explicitly pass --approve-live")
    folder = folder.resolve()
    folder.mkdir(parents=True, exist_ok=False)
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{folder / 'demo.db'}",
        alive_workspace=folder / "workspace",
        alive_api_token=TOKEN,
        alive_model_transport="pi",
        alive_embeddings_enabled=False,
    )
    if model:
        settings.alive_meta_model = model.removeprefix("meta/")
        settings.alive_role_models = {}
    if not settings.alive_meta_api_key:
        raise ValueError("Configured Meta credential is absent; LIVE acceptance NOT RUN")

    async def schema():
        database = Database(settings.database_url)
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await database.engine.dispose()

    asyncio.run(schema())
    source = folder / "approved-source"
    source.mkdir()
    for name, text in SOURCE.items():
        (source / name).write_text(text, encoding="utf-8")
    ledger = {
        "qualification": "LIVE",
        "status": "INCOMPLETE",
        "cases": CASES,
        "source": SOURCE,
        "max_calls": max_calls,
        "max_tokens": max_tokens,
        "code_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "working_tree_dirty": bool(
            subprocess.check_output(["git", "status", "--porcelain"], text=True)
        ),
        "exchanges": [],
        "independent_observation": "For [2,4], arithmetic mean is 3; supplied code returns 2.",
    }
    path = folder / "evidence-ledger.json"
    try:
        with TestClient(
            create_app(settings), headers={"Authorization": f"Bearer {TOKEN}"}
        ) as client:
            response(client, "/cognition/control", {"command": "enable_model", "provider": "meta"})
            goal = response(
                client, "/goals", {"title": "Review the approved public arithmetic demo"}
            )
            response(client, f"/goals/{goal['id']}/transition", {"status": "accepted"})

            async def approve_source(kernel):
                for profile in PROFILES.values():
                    await register_definition(kernel, definition_text(profile), status="active")
                candidate = await custody.create_capture(
                    kernel,
                    source_type="repository",
                    label="Public arithmetic demo",
                    locator="public-arithmetic-demo",
                    classification="owner_internal",
                    capture_method="owner_cli_repository",
                    content=capture.repository_content(source, list(SOURCE)),
                )
                return await custody.approve(
                    kernel,
                    candidate["id"],
                    confirm_sha256=candidate["content_sha256"],
                    operations=["intent.interpret", "repository.inspect", "repository.analyze"],
                    scope={"items": list(SOURCE)},
                    ttl_seconds=3600,
                    principal=principal(),
                    request_id=uid(),
                )

            approval = call(client, approve_source)
            setup = response(
                client,
                "/admissions/live/setup",
                {
                    "goal_ref": goal["id"],
                    "approval_ref": approval["id"],
                    "paths": list(SOURCE),
                    "max_calls": max_calls,
                    "max_tokens": max_tokens,
                    "ttl_seconds": 3600,
                },
            )
            ledger["consent"] = call(
                client,
                live.approve,
                setup["id"],
                confirm_sha256=setup["sha256"],
                principal=principal(),
            )
            if setup_only:
                ledger["status"] = "CONSENT_PREPARED; live goals NOT RUN"
                return ledger
            for case in CASES:
                exchange = response(
                    client,
                    "/admissions/live/ask",
                    {
                        "consent_ref": setup["id"],
                        "goal": case["goal"],
                        "idempotency_key": uid(),
                    },
                )
                record = (
                    exchange["recommendation"]["record"] if exchange["recommendation"] else None
                )
                chosen = (
                    record["recommendation"]["recipe_id"]
                    if record and record["recommendation"]
                    else None
                )
                exchange["independent_label"] = case["expected"]
                exchange["live_choice"] = chosen
                exchange["correct_choice"] = chosen == case["expected"]

                # Deterministic selector with the same raw goal and no supplied intent label.
                async def baseline(kernel):
                    async with kernel.db.sessions() as session:
                        options = await eligibility(
                            session,
                            kernel,
                            load_catalogue(),
                            case["goal"],
                            "unclear",
                            approval["capture_id"],
                            sorted(SOURCE),
                        )
                        eligible = [c for c in options.values() if c.eligible]
                        return (
                            max(eligible, key=lambda c: c.suitability).recipe.id
                            if eligible
                            else None
                        )

                exchange["deterministic_choice"] = call(client, baseline)
                exchange["fixed_choice"] = ANALYSIS
                ledger["exchanges"].append(exchange)
                path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")

        # A new production app against the retained DB. No model initialization command or calls.
        with TestClient(
            create_app(settings), headers={"Authorization": f"Bearer {TOKEN}"}
        ) as client:

            async def count(kernel):
                async with kernel.db.sessions() as session:
                    return await session.scalar(select(func.count()).select_from(PiProviderRequest))

            before = call(client, count)
            history = client.get("/api/v1/admissions/live")
            history.raise_for_status()
            after = call(client, count)
            ledger["restart"] = {
                "provider_requests_before": before,
                "provider_requests_after": after,
                "retained_exchanges": len(history.json()["exchanges"]),
                "no_redispatch": before == after,
            }
            assert before == after and len(history.json()["exchanges"]) == 3
            for previous in ledger["exchanges"]:
                retained = client.get("/api/v1/admissions/live/" + previous["id"])
                retained.raise_for_status()
                assert retained.json()["calls"] == previous["calls"]
                assert retained.json()["report"] == previous["report"]

        exchanges = ledger["exchanges"]
        ledger["comparison"] = {}
        for name, field in (
            ("live_hybrid", "live_choice"),
            ("deterministic", "deterministic_choice"),
            ("fixed_analysis", "fixed_choice"),
        ):
            ledger["comparison"][name] = {
                "correct": sum(e[field] == e["independent_label"] for e in exchanges),
                "false_choices": sum(
                    e[field] is not None and e[field] != e["independent_label"] for e in exchanges
                ),
                "abstentions": sum(e[field] is None for e in exchanges),
            }
        assert all(e["status"] == "LIVE MODEL" for e in exchanges), "Not three live responses"
        assert any(e["report"] for e in exchanges), "No complete read-only result"
        ledger["status"] = "LIVE_PATH_DEMONSTRATED; inspect choices and findings independently"
    except Exception as error:
        ledger["status"] = "FAILED_OR_INCOMPLETE"
        ledger["error_type"] = type(error).__name__
        raise
    finally:
        path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
        print(f"Evidence ledger: {path}")
    return ledger


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new disposable directory")
    parser.add_argument(
        "--approve-live",
        action="store_true",
        help="consent to SOURCE/CASES disclosure to configured model, with limits below",
    )
    parser.add_argument("--max-calls", type=int, default=6)
    parser.add_argument("--max-tokens", type=int, default=200000)
    parser.add_argument("--model", help="approved model id; accepts the meta/ prefix")
    parser.add_argument(
        "--history-only", action="store_true", help="restart/read existing ledger; no inference"
    )
    parser.add_argument(
        "--setup-only",
        action="store_true",
        help="prepare disposable consent for the live dashboard browser scenario",
    )
    args = parser.parse_args()
    if args.history_only:
        verify_history(args.output)
        return
    demo(
        args.output,
        approve_live=args.approve_live,
        max_calls=args.max_calls,
        max_tokens=args.max_tokens,
        model=args.model,
        setup_only=args.setup_only,
    )


if __name__ == "__main__":
    main()
