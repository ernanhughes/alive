"""Offline reproduction CLI for Notebook-03A. Never executes a model."""

import argparse
import asyncio
import json
import subprocess
import uuid
from pathlib import Path

from scripts.notebook03a_protocol import (
    CORPUS,
    ROOT,
    Exposure,
    Outcome,
    Span,
    file_digest,
    load_corpus,
    prepare_payload,
    score,
    validate_corpus,
    verify_freeze,
)


def write_new(path, value):
    path = path.resolve()
    if path.is_relative_to(CORPUS) or path.exists():
        raise ValueError(
            "Refusing to overwrite frozen inputs or earlier evidence; choose a new path"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )


def citation(source, quote):
    if not quote:
        return None
    start = source.text.find(quote)
    if start < 0:
        raise ValueError("Actual baseline emitted an unverifiable quote")
    return Span(source_id=source.id, start=start, end=start + len(quote), text=quote)


def replay(tasks):
    # Imports and Core startup occur only for baseline replay, never payload/label validation.
    from fastapi.testclient import TestClient

    from alive.app import create_app
    from alive.config import Settings
    from alive.db import Database
    from alive.models import Base
    from alive.providers import MetaProvider
    from scripts.notebook02_evaluation import URLS, post

    work = ROOT / ".alive" / ("notebook03a-replay-" + uuid.uuid4().hex)
    work.mkdir(parents=True)
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{(work / 'baseline.db').as_posix()}",
        alive_workspace=work / "workspace",
        alive_api_token="notebook03a-local-test-token",
        alive_meta_api_key="",
        alive_meta_base_url="http://127.0.0.1:1",
        alive_research_meta_enabled=False,
        alive_claim_meta_enabled=False,
        alive_embedding_enabled=False,
        alive_cognitive_provider="mock",
    )

    async def schema():
        db = Database(settings.database_url)
        async with db.engine.begin() as c:
            await c.run_sync(Base.metadata.create_all)
        await db.engine.dispose()

    asyncio.run(schema())
    original = MetaProvider.structured

    async def forbidden(*args, **kwargs):
        raise AssertionError("03A attempted model inference")

    MetaProvider.structured = forbidden
    records = {arm: [] for arm in ("A", "B", "B0")}
    raw = {}
    try:
        with TestClient(
            create_app(settings), headers={"Authorization": "Bearer " + settings.alive_api_token}
        ) as client:
            for task in tasks:
                unavailable = any(s.access != "fixture_authorized" for s in task.sources)
                for arm in records:
                    if (
                        unavailable
                        or task.kind == "claim_support"
                        and arm in ("A", "B")
                        or arm == "B0"
                    ):
                        action = (
                            "refuse"
                            if unavailable
                            else "not_applicable"
                            if arm != "B0"
                            else "abstain"
                        )
                        records[arm].append(
                            Outcome(
                                task_id=task.id,
                                arm=arm,
                                action=action,
                                mode="constant_control"
                                if arm == "B0"
                                else "lexical"
                                if arm == "A"
                                else "integrity",
                                raw_policy="offline-access-fixture"
                                if unavailable
                                else "pair-api-inapplicable"
                                if arm != "B0"
                                else "explicit-always-abstain-reference",
                            )
                        )
                if unavailable or task.kind != "pair":
                    continue
                g = post(client, "/goals", {"instruction": task.question})
                sources = {s.id: s for s in task.sources}
                ordered = [
                    sources[next(c.passage.source_id for c in task.claims if c.role == role)]
                    for role in ("historical", "current")
                ]
                shots = []
                for source, url in zip(ordered, URLS, strict=True):
                    grant = post(
                        client,
                        "/grants",
                        {
                            "goal_id": g["id"],
                            "url": url,
                            "tab_key": "notebook03a-fixture",
                            "approved": True,
                        },
                    )
                    shots.append(
                        post(
                            client,
                            "/snapshots",
                            {
                                "grant_id": grant["id"],
                                "url": url,
                                "title": source.untrusted_title,
                                "text": source.text,
                                "reviewed_sha256": source.sha256,
                            },
                        )["snapshot"]
                    )
                memory = post(client, "/research/memories", {"snapshot_id": shots[0]["id"]})
                request = {"snapshot_id": shots[1]["id"], "memory_id": memory["id"]}
                a = post(client, "/research/connections", request)
                b = post(client, "/research/qualifications", request)
                raw[task.id] = {
                    "A": a,
                    "B": b,
                    "transport_note": (
                        "Existing allowlisted fixture URLs; canonical attribution is in "
                        "pinned Git provenance, not these URLs."
                    ),
                }
                quotes = [
                    citation(ordered[1], a["data"]["current_quote"]),
                    citation(ordered[0], a["data"]["historical_quote"]),
                ]
                records["A"].append(
                    Outcome(
                        task_id=task.id,
                        arm="A",
                        mode="lexical",
                        action="abstain" if a["abstained"] else "retain_candidate",
                        evidence=[q for q in quotes if q],
                        raw_policy=a["data"]["model"],
                    )
                )
                records["B"].append(
                    Outcome(
                        task_id=task.id,
                        arm="B",
                        mode="integrity",
                        action="abstain",
                        raw_policy=b["qualifier_version"] + ":" + b["outcome"],
                    )
                )
                if (
                    b["outcome"] != "abstain"
                    or b["semantic_judgement"] != "not_performed"
                    or b["inference_calls"] != 0
                ):
                    raise ValueError(
                        "Unexpected integrity baseline action; amend instead of faking a result"
                    )
    finally:
        MetaProvider.structured = original
    return records, raw


def signature(metrics):
    # UUIDs/transport details and timings are intentionally absent from scored projections.
    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["validate", "prepare", "baseline", "score", "submission"]
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--records", type=Path)
    parser.add_argument("--arm", choices=["A", "B", "B0"])
    parser.add_argument("--check-against", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--package", type=Path, help="Custodian-only external package validation")
    args = parser.parse_args()
    protocol = verify_freeze()
    tasks, labels, origins = load_corpus()
    validation = validate_corpus(tasks, labels, origins)
    if validation["status"] != "PUBLIC_COMPLETE":
        print(json.dumps(validation, indent=2))
        return 1
    result = {
        "protocol_version": protocol["version"],
        "independent_holdout_status": protocol["independent_status"],
        "independent_cases_available": protocol["independent_cases_available"],
        "protocol_sha256": file_digest(CORPUS / "protocol.json"),
        "validation": validation,
        "model_calls": 0,
        "spend_micro_usd": 0,
    }
    if args.command == "submission":
        manifest = Exposure.model_validate(
            json.loads(
                (args.manifest or CORPUS / "independent_submission.json").read_text(
                    encoding="utf-8"
                )
            )
        )
        if args.package is not None:
            if args.package.resolve().is_relative_to(ROOT):
                raise ValueError(
                    "A blind submission cannot be retained inside the implementer repo"
                )
            manifest = Exposure.model_validate(
                json.loads(
                    (args.package / "independent_submission.json").read_text(encoding="utf-8")
                )
            )
            if not manifest.blind_eligible:
                raise ValueError("Independent labeling/access/exposure gate is not satisfied")
            external_tasks, external_labels, external_origins = load_corpus(args.package)
            if any(t.split != "independent_heldout" for t in external_tasks):
                raise ValueError("Independent package tasks must declare their restricted split")
            public_hashes = {s.sha256 for t in tasks for s in t.sources}
            public_families = {t.family for t in tasks}
            if any(
                t.family in public_families or any(s.sha256 in public_hashes for s in t.sources)
                for t in external_tasks
            ):
                raise ValueError("Independent package reuses exposed families or source text")
            checked = validate_corpus(
                external_tasks, external_labels, external_origins, public=False
            )
            if (
                len(external_tasks) != manifest.target_cases
                or checked["status"] != "PUBLIC_COMPLETE"
                or any(a.independence != "external_attested" for a in external_labels)
                or file_digest(args.package / "tasks.json") != manifest.inputs_sha256
                or file_digest(args.package / "annotations.json") != manifest.gold_sha256
            ):
                raise ValueError("Independent package completeness/hash/adjudication gate failed")
            result["external_package_counts"] = {"cases": len(external_tasks)}
        result.update(
            submission=manifest.model_dump(),
            attested_eligibility=manifest.blind_eligible,
            limitation=(
                "Attestation validation is not access-control verification. "
                "No blind holdout is currently available."
            ),
        )
    elif args.command == "prepare":
        payloads = {}
        refused = []
        for task in tasks:
            try:
                payloads[task.id] = prepare_payload(task)
            except PermissionError:
                refused.append(task.id)
        result.update(
            payloads=payloads,
            access_refused=refused,
            note="Opaque routing IDs are outside each payload; no payload is transmitted.",
        )
    elif args.command == "baseline":
        records, raw = replay(tasks)
        metrics = {a: score(tasks, labels, r, a) for a, r in records.items()}
        if args.check_against is not None:
            expected = json.loads(args.check_against.read_text(encoding="utf-8"))
            if signature(metrics) != expected["metrics"]:
                raise ValueError(
                    "Recorded baseline expectation changed; do not silently rewrite it"
                )
        groups = {
            "pair": [t for t in tasks if t.kind == "pair"],
            "claim_support": [t for t in tasks if t.kind == "claim_support"],
            "authentic": [
                t for t in tasks if all(x["kind"] == "authentic" for x in origins[t.id].values())
            ],
            "controlled": [
                t for t in tasks if any(x["kind"] == "controlled" for x in origins[t.id].values())
            ],
            "synthetic": [
                t for t in tasks if all(x["kind"] == "synthetic" for x in origins[t.id].values())
            ],
        }
        strata = {
            name: {
                a: score(subset, labels, [o for o in r if o.task_id in {t.id for t in subset}], a)
                for a, r in records.items()
            }
            for name, subset in groups.items()
        }
        paired = {
            "A_retains_B_declines": sum(
                a.action == "retain_candidate" and b.action == "abstain"
                for a, b in zip(records["A"], records["B"], strict=True)
            ),
            "B_retains_A_declines": sum(
                b.action == "retain_candidate" and a.action == "abstain"
                for a, b in zip(records["A"], records["B"], strict=True)
            ),
            "note": "Candidate actions only, not semantic judgment performance.",
        }
        result.update(
            metrics=metrics,
            strata=strata,
            paired_candidate_decisions=paired,
            outcomes={a: [o.model_dump() for o in r] for a, r in records.items()},
            raw_core_results=raw,
            not_run={"C": "NOT RUN", "D": "NOT RUN"},
            execution_commit=subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip(),
            runner_sha256=file_digest(Path(__file__)),
            contract_sha256=file_digest(ROOT / "scripts/notebook03a_protocol.py"),
        )
    elif args.command == "score":
        if args.records is None or args.arm is None:
            raise ValueError(
                "Scoring requires complete recorded outcomes and an executed baseline arm"
            )
        data = json.loads(args.records.read_text(encoding="utf-8"))
        outcomes = [Outcome.model_validate(r) for r in data["outcomes"][args.arm]]
        result["metrics"] = {args.arm: score(tasks, labels, outcomes, args.arm)}
    if args.output:
        write_new(args.output, result)
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in ("raw_core_results", "outcomes", "payloads")
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
