"""Frozen Notebook-02 fixed-pair comparison in isolated SQLite; zero inference.

Labels are loaded only by score(), after every runtime arm has produced its output.
Legacy lexical candidates are not recast as substantive semantic assertions.
"""

import argparse
import asyncio
import hashlib
import json
import platform
import statistics
import subprocess
import time
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from alive.app import create_app
from alive.config import Settings
from alive.db import Database
from alive.models import Base
from alive.providers import MetaProvider
from alive.web_models import WebExperience

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "evaluations/notebook02"
API = "/api/v1/browser-experience"
URLS = [
    "https://docs.python.org/3/tutorial/",
    "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide",
]


def sha(data):
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def verify_freeze():
    protocol = json.loads((FROZEN / "protocol.json").read_text(encoding="utf-8"))
    for name, wanted in protocol["files_sha256"].items():
        if sha((FROZEN / name).read_bytes()) != wanted:
            raise ValueError("Frozen input changed: " + name)
    return protocol


def post(client, path, body):
    response = client.post(API + path, json=body)
    if response.status_code != 200:
        raise AssertionError(f"{path}: {response.status_code}: {response.text}")
    return response.json()


def prepare_pair(client, case):
    g = post(client, "/goals", {"instruction": "Inspect research evidence carefully"})
    shots = []
    for source, url in zip((case["historical"], case["current"]), URLS, strict=True):
        grant = post(
            client,
            "/grants",
            {
                "goal_id": g["id"],
                "url": url,
                "tab_key": "notebook02-evaluation",
                "approved": True,
            },
        )
        text = source["text"][:2000]
        shot = post(
            client,
            "/snapshots",
            {
                "grant_id": grant["id"],
                "url": url,
                "title": source["title"],
                "text": text,
                "reviewed_sha256": hashlib.sha256(text.encode()).hexdigest(),
            },
        )["snapshot"]
        shots.append(shot)
    memory = post(client, "/research/memories", {"snapshot_id": shots[0]["id"]})
    if case.get("omit_historical_snapshot"):

        async def lose_backlink():
            async with client.app.state.kernel.db.sessions.begin() as session:
                row = await session.get(WebExperience, memory["id"])
                row.data = row.data | {"snapshot_id": "unavailable-original"}

        asyncio.run(lose_backlink())
    return {"snapshot_id": shots[1]["id"], "memory_id": memory["id"]}, shots


def run_case(client, case):
    request, shots = prepare_pair(client, case)
    outputs, latencies = {}, {}
    for arm, path in (("A", "/research/connections"), ("B", "/research/qualifications")):
        start = time.perf_counter()
        outputs[arm] = post(client, path, request)
        latencies[arm] = round((time.perf_counter() - start) * 1000, 3)
    outputs["D"] = {
        "outcome": "abstain",
        "semantic_judgement": "not_performed",
        "policy": "same-evidence-access-abstain-control-v1",
        "evidence_access": "identical bounded current and retained historical evidence",
    }
    # Hard gate: every claimed exact quote must occur at its recorded authoritative offset.
    b = outputs["B"]
    for key, shot in (("current_source", shots[1]), ("historical_source", shots[0])):
        ref = b[key]
        if ref:
            text = shot["data"]["text"][:2000]
            assert text[ref["quote_start"] : ref["quote_end"]] == ref["quote"]
            assert ref["sha256"] == hashlib.sha256(shot["data"]["text"].encode()).hexdigest()
    a = outputs["A"]["data"]
    for key, shot in (("current_quote", shots[1]), ("historical_quote", shots[0])):
        if a[key]:
            assert a[key] in shot["data"]["text"][:2000]
    assert b["inference_calls"] == b["token_usage"] == b["cost_micro_usd"] == 0
    assert a["inference_calls"] == 0
    return {
        "case_id": case["id"],
        "outputs": outputs,
        "latency_ms": latencies,
        "bounded_evidence": {"current": shots[1]["data"], "historical": shots[0]["data"]},
        "quote_gate": "PASS",
    }


def score(records):
    # Ground truth is intentionally absent from prepare_pair/run_case and all API inputs.
    labels = json.loads((FROZEN / "labels.json").read_text(encoding="utf-8"))
    summary = {}
    positives = sum(labels[r["case_id"]]["useful_relationship"] for r in records)
    negatives = len(records) - positives
    for arm in ("A", "B", "D"):
        declines = correct_declines = candidates = useful_candidates = 0
        for r in records:
            useful = labels[r["case_id"]]["useful_relationship"]
            output = r["outputs"][arm]
            decline = (
                output["abstained"]
                if arm == "A"
                else (output["outcome"] in ("abstain", "qualified_non_use"))
            )
            declines += decline
            correct_declines += bool(decline and not useful)
            candidates += not decline
            useful_candidates += bool(not decline and useful)
        summary[arm] = {
            "cases": len(records),
            "useful_labels": positives,
            "negative_labels": negatives,
            "substantive_findings": 0,
            "supported_substantive_relation_precision": None,
            "precision_limitation": "No arm executed semantic reasoning; lexical candidates "
            "are not substantive relationship assertions.",
            "correct_non_use_or_abstention": correct_declines,
            "correct_non_use_or_abstention_rate": correct_declines / negatives
            if negatives
            else None,
            "missed_useful_substantive_relationships": positives,
            "missed_useful_substantive_relationship_rate": 1.0 if positives else None,
            "declines": declines,
            "candidate_connections": candidates,
            "useful_label_candidates": useful_candidates,
            "candidate_label_precision_diagnostic": useful_candidates / candidates
            if candidates
            else None,
            "p50_latency_ms": (
                statistics.median(r["latency_ms"][arm] for r in records) if arm != "D" else None
            ),
        }
    summary["C"] = {
        "status": "NOT RUN",
        "model": None,
        "calls": 0,
        "tokens": 0,
        "cost_micro_usd": 0,
    }
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "docs/validation/alive-notebook-02/evaluation.json"
    )
    args = parser.parse_args()
    protocol = verify_freeze()
    work = ROOT / ".alive" / ("notebook02-eval-" + uuid.uuid4().hex)
    work.mkdir(parents=True)
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{(work / 'evaluation.db').as_posix()}",
        alive_workspace=work / "workspace",
        alive_api_token="notebook02-isolated-evaluation-token",
        alive_meta_api_key="",
        alive_meta_base_url="http://127.0.0.1:1",
        alive_research_meta_enabled=False,
        alive_claim_meta_enabled=False,
        alive_embedding_enabled=False,
        alive_cognitive_provider="mock",
    )

    async def schema():
        db = Database(settings.database_url)
        async with db.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await db.engine.dispose()

    asyncio.run(schema())
    original = MetaProvider.structured

    async def forbidden(*args, **kwargs):
        raise AssertionError("Evaluation attempted external inference")

    MetaProvider.structured = forbidden
    runs = {}
    try:
        with TestClient(
            create_app(settings), headers={"Authorization": "Bearer " + settings.alive_api_token}
        ) as client:
            for split in ("development", "heldout"):
                cases = json.loads((FROZEN / (split + ".json")).read_text(encoding="utf-8"))
                runs[split] = [run_case(client, case) for case in cases]
            heldout = json.loads((FROZEN / "heldout.json").read_text(encoding="utf-8"))
            reverse, distractors = [], []
            for case in heldout:
                if case.get("omit_historical_snapshot"):
                    continue
                reverse.append(
                    run_case(
                        client,
                        case | {"historical": case["current"], "current": case["historical"]},
                    )
                )
                sentence = " Shared archive words: protocol evidence result comparison system."
                changed = case | {
                    key: value | {"text": value["text"] + sentence}
                    for key, value in case.items()
                    if key in ("current", "historical")
                }
                distractors.append(run_case(client, changed))
            runs["reversed_heldout"] = reverse
            runs["distractor_heldout"] = distractors
    finally:
        MetaProvider.structured = original
    report = {
        "protocol": protocol,
        "protocol_sha256": sha((FROZEN / "protocol.json").read_bytes()),
        "execution_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "implementation_files_sha256": {
            name: sha((ROOT / name).read_bytes())
            for name in (
                "alive/evidence_qualification.py",
                "alive/web_experience.py",
                "scripts/notebook02_evaluation.py",
            )
        },
        "environment": {"platform": platform.platform(), "python": platform.python_version()},
        "integrity_gates": "PASS; every emitted quote checked against retained input and offset",
        "external_model_calls": 0,
        "tokens": 0,
        "cost_micro_usd": 0,
        "metrics": {split: score(records) for split, records in runs.items()},
        "per_case": runs,
        "limitations": [
            "Author-prepared synthetic labels are not independent human ratings.",
            "No semantic qualification, supersession detection or R4 mismatch "
            "detection was demonstrated.",
            "B and the same-access abstain control D both miss every useful "
            "substantive relationship. No reasoning improvement is established.",
            "Latency is a single local observation; diagnostics reuse original "
            "usefulness labels, not directional semantic labels.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(report["metrics"], indent=2))
    print("Evidence:", args.output)


if __name__ == "__main__":
    main()
