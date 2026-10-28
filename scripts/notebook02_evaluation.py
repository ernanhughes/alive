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
            if ref["selection_method"] == "caller_quote":
                assert ref["quote_exact"] is True
                assert text[ref["quote_start"] : ref["quote_end"]] == ref["quote"]
            else:
                assert ref["displayed_excerpt"] == text[:300]
                assert ref["quote"] is ref["quote_exact"] is None
            assert ref["sha256"] == hashlib.sha256(shot["data"]["text"].encode()).hexdigest()
    assert b["quotes_requested"] is False and b["source_quotes_verified"] is None
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


def decision(output, arm):
    """Map recorded API actions, without promoting lexical candidates to factual claims."""
    if arm == "A":
        if output["abstained"] is True:
            return "abstain"
        if output["abstained"] is False and output["data"]["status"] == "candidate":
            return "candidate_connection"
        raise ValueError("Unrecognized legacy decision")
    outcome = output["outcome"]
    if outcome not in ("abstain", "qualified_non_use", "candidate_connection"):
        raise ValueError("Unrecognized qualification decision")
    return outcome


def score(records):
    # Labels are only used after runtime decisions. Counts depend on recorded outcomes.
    labels = json.loads((FROZEN / "labels.json").read_text(encoding="utf-8"))
    positives = sum(labels[r["case_id"]]["useful_relationship"] for r in records)
    negatives = len(records) - positives
    summary = {}
    for arm in ("A", "B", "D"):
        candidates = useful_candidates = unsupported_candidates = 0
        correct_abstention = false_abstention = integrity_rejection = 0
        useful_rejected = negative_rejected = 0
        for record in records:
            useful = labels[record["case_id"]]["useful_relationship"]
            action = decision(record["outputs"][arm], arm)
            if action == "candidate_connection":
                candidates += 1
                useful_candidates += bool(useful)
                unsupported_candidates += not useful
            elif action == "abstain":
                correct_abstention += not useful
                false_abstention += bool(useful)
            else:
                integrity_rejection += 1
                useful_rejected += bool(useful)
                negative_rejected += not useful
        summary[arm] = {
            "cases": len(records),
            "useful_labels": positives,
            "negative_labels": negatives,
            "candidate_connections": candidates,
            "useful_candidates_retained": useful_candidates,
            "useful_candidate_recall": useful_candidates / positives if positives else None,
            "useful_candidates_lost": positives - useful_candidates,
            "unsupported_candidates": unsupported_candidates,
            "unsupported_candidate_rate": unsupported_candidates / candidates
            if candidates
            else None,
            "negative_candidate_rate": unsupported_candidates / negatives if negatives else None,
            "correct_abstention": correct_abstention,
            "correct_abstention_rate": correct_abstention / negatives if negatives else None,
            "false_abstention": false_abstention,
            "false_abstention_rate": false_abstention / positives if positives else None,
            "integrity_rejection": integrity_rejection,
            "useful_integrity_rejection": useful_rejected,
            "negative_integrity_rejection": negative_rejected,
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


METRIC_NOTES = [
    "Useful candidate recall is retained useful candidates divided by useful labels.",
    "Unsupported candidate rate uses emitted candidates as denominator; negative candidate "
    "rate uses negative labels. These labels do not identify false factual assertions.",
    "Correct/false abstention count explicit abstain decisions on negative/positive labels. "
    "Integrity rejection is separate, including its useful and negative label breakdown.",
    "Useful candidates lost = useful labels minus actual retained useful candidates. "
    "The former constant missed-substantive-relations metric is retired, not relabeled.",
    "No semantic reasoning is performed. Candidate usefulness labels do not establish "
    "substantive relation precision, source authenticity or factual truth.",
]


def portable_path(path):
    resolved = path.resolve()
    return (
        resolved.relative_to(ROOT).as_posix()
        if resolved.is_relative_to(ROOT)
        else "external-output/" + resolved.name
    )


def derive_historical(source, protocol):
    historical = json.loads(source.read_text(encoding="utf-8"))
    if historical["protocol"]["files_sha256"] != protocol["files_sha256"]:
        raise ValueError("Historical evidence uses different frozen inputs")
    return {
        "report_version": "notebook02-metrics-v2",
        "derived_from": {
            "path": portable_path(source),
            "sha256_lf_normalized": sha(source.read_bytes()),
            "execution_commit": historical["execution_commit"],
        },
        "scorer_sha256": sha(Path(__file__).read_bytes()),
        "frozen_inputs_sha256": protocol["files_sha256"],
        "metrics": {split: score(records) for split, records in historical["per_case"].items()},
        "metric_notes": METRIC_NOTES,
        "limitations": [
            "Recomputed from unchanged historical recorded actions; no new runtime "
            "or semantic judgments. Original metrics/evidence remain preserved.",
            "Historical default-excerpt quote verification is not retrospectively "
            "qualified. Inspect the R1 runtime reproduction for the corrected contract.",
        ],
        "new_provider_calls": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "docs/validation/alive-notebook-02-r1/evaluation.json"
    )
    parser.add_argument(
        "--derive-from",
        type=Path,
        help="Rescore preserved recorded outcomes without executing any arm",
    )
    args = parser.parse_args()
    protocol = verify_freeze()
    # Never overwrite the original evidence archive, even via an explicit output argument.
    historical_dir = ROOT / "docs/validation/alive-notebook-02"
    if args.output.resolve().is_relative_to(historical_dir):
        raise ValueError("Original Notebook-02 evidence is preserved; choose a new output path")
    if args.derive_from is not None:
        if args.output.resolve() == args.derive_from.resolve():
            raise ValueError("Derived output must not overwrite its input")
        report = derive_historical(args.derive_from, protocol)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps(report["metrics"], indent=2))
        print("Evidence:", portable_path(args.output))
        return
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
        "report_version": "notebook02-metrics-v2",
        "metric_notes": METRIC_NOTES,
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
        "integrity_gates": (
            "PASS; automatic excerpts checked as display context, not requested quotes"
        ),
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
    print("Evidence:", portable_path(args.output))


if __name__ == "__main__":
    main()
