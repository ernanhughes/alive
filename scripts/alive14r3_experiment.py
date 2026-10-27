"""Gated runner for the frozen ALIVE-14-R3 paired experiment.

Phases are deliberately separate. No phase authorises the next one implicitly.

    prepare -> approve -> execute -> rate -> reveal -> analyse -> archive

`prepare`, `approve` and the synthetic path never dispatch a paid provider call.
A real run requires an explicit approval JSON whose payload hashes, model, call
count and spend ceiling match the prepared manifest exactly.
"""

import argparse
import asyncio
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from alive.app import create_app
from alive.config import Settings
from alive.db import Database
from alive.experiment.metrics import wilson
from alive.experiment_budget import worst_micro_usd
from alive.models import Base, now, uid
from alive.research_blind import verify_commitment
from alive.web_experience import digest
from alive.web_models import WebExperience
from scripts.verify_alive14r3_protocol import (
    EXPECTED_ANSWER_KEY_SHA256,
    EXPECTED_PROTOCOL_SHA256,
)

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "archives/ALIVE-14-R3/protocol/relationship-experiment-v3.json"
ANSWER_KEY = ROOT / "archives/ALIVE-14-R3/protocol/answer-key-v3.json"
RUNS = ROOT / ".alive/alive14r3-runs"
ARCHIVE = ROOT / "archives/ALIVE-14-R3/evidence/runs"
API = "/api/v1/browser-experience"
HISTORICAL_KEYS = {
    "historical_memory_id",
    "historical_url",
    "historical_sha256",
    "historical_excerpt",
}
RUBRIC_CHOICES = ("yes", "no", "uncertain")


def synthetic_rubric(task_id):
    """Deterministic null pattern: identical for A/B/C on the same task.

    The pattern exists only to exercise the rating and analysis plumbing. It is not a
    simulated owner judgement and cannot create a condition difference.
    """
    seed = hashlib.sha256(task_id.encode()).digest()
    return {
        "factually_supported": RUBRIC_CHOICES[seed[0] % 3],
        "relevant_to_goal": RUBRIC_CHOICES[seed[1] % 3],
        "revealed_new": RUBRIC_CHOICES[seed[2] % 3],
        "already_obvious": RUBRIC_CHOICES[seed[3] % 3],
        "would_act": RUBRIC_CHOICES[seed[4] % 3],
        "misleading": RUBRIC_CHOICES[seed[5] % 3],
        "uncertain": "yes" if seed[6] % 2 else "no",
    }


MISSING_OUTPUT = "No validated model output is available for this item."


def canonical_sha256(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes((json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    os.replace(temporary, path)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def append_jsonl(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def read_jsonl(path):
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def verify_protocol_identity():
    if canonical_sha256(PROTOCOL) != EXPECTED_PROTOCOL_SHA256:
        raise SystemExit(
            "Frozen protocol hash mismatch: "
            + canonical_sha256(PROTOCOL)
            + " != "
            + EXPECTED_PROTOCOL_SHA256
        )
    if canonical_sha256(ANSWER_KEY) != EXPECTED_ANSWER_KEY_SHA256:
        raise SystemExit("Sealed answer-key hash mismatch")
    protocol = read_json(PROTOCOL)
    try:
        git("cat-file", "-e", protocol["baseline"] + "^{commit}")
    except subprocess.CalledProcessError:
        # Shallow CI checkouts do not contain the baseline object. The frozen
        # protocol hash above is still verified; ancestry is not checkable here.
        return protocol
    try:
        git("merge-base", "--is-ancestor", protocol["baseline"], "HEAD")
    except subprocess.CalledProcessError as exc:
        raise SystemExit("Protocol baseline is not an ancestor of HEAD") from exc
    return protocol


def run_id_for(mode, protocol):
    return f"{protocol['experiment_id']}-{mode}-{EXPECTED_PROTOCOL_SHA256[:12]}"


def run_dir(mode, protocol):
    return RUNS / run_id_for(mode, protocol)


def token_for(directory):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "api-token.txt"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    token = "alive14r3-" + secrets.token_urlsafe(32)
    path.write_text(token + "\n", encoding="utf-8")
    return token


def build_settings(mode, protocol, directory, token):
    urls = []
    for task in protocol["tasks"]:
        urls.extend([task["current_source"]["url"], task["historical_source"]["url"]])
    return Settings(
        _env_file=None,
        alive_meta_api_key=os.getenv("ALIVE_META_API_KEY", ""),
        alive_embedding_enabled=False,
        alive_native_test_pages=",".join(sorted(set(urls))),
        alive_api_token=token,
        alive_heartbeat_seconds=0.1,
        database_url=f"sqlite+aiosqlite:///{(directory / 'experiment.db').as_posix()}",
        alive_workspace=directory / "workspace",
        alive_research_meta_enabled=mode == "real",
        alive_meta_model=protocol["model_plan"]["model"],
        alive_meta_max_output=protocol["budget_plan"]["output_token_cap"],
        alive_relationship_micro_usd_limit=int(
            float(protocol["budget_plan"]["ceiling_usd"]) * 1_000_000
        ),
    )


def ensure_schema(settings):
    async def create():
        database = Database(settings.database_url)
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await database.engine.dispose()

    asyncio.run(create())


class Client:
    def __init__(self, settings, token):
        self.settings = settings
        self.token = token
        self.client = None

    def __enter__(self):
        self.client = TestClient(
            create_app(self.settings),
            headers={"Authorization": "Bearer " + self.token},
        )
        self.client.__enter__()
        return self.client

    def __exit__(self, *args):
        return self.client.__exit__(*args)


def call(client, method, path, body=None, expected=200):
    response = client.request(method, API + path, json=body)
    if response.status_code != expected:
        raise RuntimeError(
            f"{method} {path} returned {response.status_code}: {response.text[:2000]}"
        )
    return response.json()


def seed_memory(client, goal_id, task):
    text = task["historical_source"]["excerpt"]

    async def seed():
        async with client.app.state.kernel.db.sessions.begin() as session:
            row = WebExperience(
                id=uid(),
                instance_id=client.app.state.kernel.instance_id,
                kind="research_memory",
                status="active",
                data={
                    "goal_id": goal_id,
                    "url": task["historical_source"]["url"],
                    "title": "Historical controlled source " + task["task_id"],
                    "excerpt": text,
                    "sha256": digest(text),
                    "reviewed_at": now().isoformat(),
                    "source_kind": "reviewed_browser_excerpt",
                    "provenance": "alive14r3-frozen-protocol",
                },
            )
            session.add(row)
            await session.flush()
            return row.id

    return client.portal.call(seed)


def preview(client, task, provider, research_id=None):
    body = {
        "snapshot_id": task["snapshot_id"],
        "analysis_mode": "paired",
        "research_question": task["question"],
        "provider": provider,
    }
    if research_id:
        body["research_id"] = research_id
    return call(client, "POST", "/research/outbound/preview", body)


def assert_request_parity(a, b):
    assert a["analysis_mode"] == b["analysis_mode"] == "paired"
    assert a["request"]["instructions"] == b["request"]["instructions"]
    assert a["request"]["schema"] == b["request"]["schema"]
    assert HISTORICAL_KEYS.isdisjoint(a["request"]["input"])
    assert set(a["request"]["input"]) | HISTORICAL_KEYS == set(b["request"]["input"])
    for key in (
        "analysis_mode",
        "current_snapshot_id",
        "current_url",
        "current_sha256",
        "current_excerpt",
        "goal_id",
        "goal_instruction",
        "research_question",
        "provider",
        "model",
    ):
        assert a["request"]["input"][key] == b["request"]["input"][key]
    assert a["payload_sha256"] != b["payload_sha256"]


def load_or_create_state(mode, protocol):
    directory = run_dir(mode, protocol)
    state_file = directory / "state.json"
    if not state_file.exists():
        return directory, None
    state = read_json(state_file)
    if (
        state.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256
        or state.get("mode") != mode
        or state.get("run_id") != run_id_for(mode, protocol)
    ):
        raise SystemExit("Existing run state does not match the frozen protocol identity")
    return directory, state


def write_state(directory, state):
    state["updated_at"] = now().isoformat()
    write_json(directory / "state.json", state)


def prepare(mode):
    protocol = verify_protocol_identity()
    directory, existing = load_or_create_state(mode, protocol)
    if existing:
        print(f"prepare: existing phase={existing['phase']} run={existing['run_id']}")
        return existing
    if directory.exists():
        partial = directory.with_name(directory.name + "-partial-" + now().strftime("%H%M%S"))
        directory.rename(partial)
        print(f"prepare: moved incomplete run aside to {partial}")
    directory.mkdir(parents=True)
    token = token_for(directory)
    settings = build_settings(mode, protocol, directory, token)
    ensure_schema(settings)
    answer_key = read_json(ANSWER_KEY)
    if hashlib.sha256(ANSWER_KEY.read_bytes()).hexdigest() != EXPECTED_ANSWER_KEY_SHA256:
        raise SystemExit("Sealed answer key changed during prepare")
    provider = "meta" if mode == "real" else "local_stub"
    tasks = []
    total_reserved = 0
    total_micro = 0
    with Client(settings, token) as client:
        for task in protocol["tasks"]:
            goal = call(client, "POST", "/goals", {"instruction": task["goal"]})
            grant = call(
                client,
                "POST",
                "/grants",
                {
                    "goal_id": goal["id"],
                    "url": task["current_source"]["url"],
                    "tab_key": "alive14r3-" + task["task_id"].lower(),
                    "approved": True,
                },
            )
            shot = call(
                client,
                "POST",
                "/snapshots",
                {
                    "grant_id": grant["id"],
                    "url": task["current_source"]["url"],
                    "title": "Current controlled source " + task["task_id"],
                    "text": task["current_source"]["excerpt"],
                    "reviewed_sha256": task["current_source"]["sha256"],
                },
            )
            memory_id = seed_memory(client, goal["id"], task)
            base = {
                "task_id": task["task_id"],
                "goal_id": goal["id"],
                "snapshot_id": shot["snapshot"]["id"],
                "grant_id": grant["id"],
                "current_url": task["current_source"]["url"],
                "memory_id": memory_id,
                "question": task["question"],
            }
            a = preview(client, base, provider)
            b = preview(client, base, provider, memory_id)
            assert_request_parity(a, b)
            for label, row in (("A", a), ("B", b)):
                serialized = json.dumps(row["request"], ensure_ascii=False)
                assert "answer_key" not in serialized
                assert "sealed" not in serialized
                if mode == "real":
                    assert row["provider"]["model"] == protocol["model_plan"]["model"]
                else:
                    assert row["provider"]["model"].startswith("deterministic-local-stub")
            for key in ("reference_answer", "required_points", "prohibited_claims"):
                value = json.dumps(answer_key["tasks"][task["task_id"]][key], ensure_ascii=False)
                assert value[:80] not in json.dumps(a["request"], ensure_ascii=False)
                assert value[:80] not in json.dumps(b["request"], ensure_ascii=False)
            reserved = {
                "A": a["estimated_max_tokens"],
                "B": b["estimated_max_tokens"],
            }
            micro = {
                "A": worst_micro_usd(reserved["A"]),
                "B": worst_micro_usd(reserved["B"]),
            }
            total_reserved += reserved["A"] + reserved["B"]
            total_micro += micro["A"] + micro["B"]
            tasks.append(
                base
                | {
                    "payload_sha256s": {
                        "A": a["payload_sha256"],
                        "B": b["payload_sha256"],
                    },
                    "request_sha256s": {
                        "A": a["request_sha256"],
                        "B": b["request_sha256"],
                    },
                    "reserved_tokens": reserved,
                    "reserved_micro_usd": micro,
                    "current_sha256": task["current_source"]["sha256"],
                    "historical_sha256": task["historical_source"]["sha256"],
                }
            )
    state = {
        "run_id": run_id_for(mode, protocol),
        "mode": mode,
        "phase": "prepared",
        "protocol_version": protocol["protocol_version"],
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "answer_key_sha256": EXPECTED_ANSWER_KEY_SHA256,
        "baseline": protocol["baseline"],
        "source_commit": git("rev-parse", "HEAD"),
        "provider": provider,
        "model": (
            protocol["model_plan"]["model"] if mode == "real" else "deterministic-local-stub-v1"
        ),
        "task_order": list(protocol["task_order"]),
        "tasks": tasks,
        "synthetic": mode != "real",
        "totals": {
            "calls": len(tasks) * 2,
            "reserved_tokens": total_reserved,
            "worst_case_micro_usd": total_micro,
        },
        "parity": {
            "instructions_equal": True,
            "schema_equal": True,
            "a_has_no_historical_keys": True,
            "b_adds_only_historical_keys": True,
            "answer_key_not_in_requests": True,
        },
        "created_at": now().isoformat(),
        "updated_at": now().isoformat(),
    }
    write_state(directory, state)
    write_json(
        directory / "preview-manifest.json",
        {
            "run_id": state["run_id"],
            "protocol_sha256": state["protocol_sha256"],
            "answer_key_sha256": state["answer_key_sha256"],
            "provider": provider,
            "model": state["model"],
            "tasks": [
                {
                    "task_id": row["task_id"],
                    "payload_sha256s": row["payload_sha256s"],
                    "request_sha256s": row["request_sha256s"],
                    "reserved_tokens": row["reserved_tokens"],
                }
                for row in tasks
            ],
            "totals": state["totals"],
            "paid_calls": 0,
        },
    )
    print(
        f"prepare: {state['run_id']} tasks={len(tasks)} calls={state['totals']['calls']} "
        f"worst_case_usd={total_micro / 1e6:.6f} phase=prepared"
    )
    return state


def approve(mode, approval_file=None, synthetic=False):
    protocol = verify_protocol_identity()
    directory, state = load_or_create_state(mode, protocol)
    if not state:
        raise SystemExit("prepare must run first")
    if state["phase"] not in ("prepared", "approved"):
        print(f"approve: no-op for phase={state['phase']}")
        return state
    if synthetic:
        if mode != "synthetic":
            raise SystemExit("--synthetic approval is only valid for synthetic runs")
        approval = {
            "run_id": state["run_id"],
            "protocol_sha256": state["protocol_sha256"],
            "provider": "local_stub",
            "model": state["model"],
            "task_count": len(state["tasks"]),
            "calls": state["totals"]["calls"],
            "payload_sha256s": {row["task_id"]: row["payload_sha256s"] for row in state["tasks"]},
            "max_input_tokens": state["totals"]["reserved_tokens"],
            "max_output_tokens": protocol["budget_plan"]["output_token_cap"],
            "max_usd": 0.0,
            "no_retries": True,
            "human_approval": False,
            "approved_by": "synthetic-local-runner",
            "approved_at": now().isoformat(),
        }
    else:
        if not approval_file:
            raise SystemExit("A real run requires --approval-file")
        approval = read_json(Path(approval_file))
        expected_hashes = {row["task_id"]: row["payload_sha256s"] for row in state["tasks"]}
        checks = [
            (approval.get("run_id") == state["run_id"], "run_id"),
            (approval.get("protocol_sha256") == state["protocol_sha256"], "protocol_sha256"),
            (approval.get("provider") == "meta", "provider"),
            (approval.get("model") == state["model"], "model"),
            (approval.get("task_count") == len(state["tasks"]), "task_count"),
            (approval.get("calls") == state["totals"]["calls"], "calls"),
            (approval.get("payload_sha256s") == expected_hashes, "payload_sha256s"),
            (approval.get("no_retries") is True, "no_retries"),
            (approval.get("human_approval") is True, "human_approval"),
            (bool(approval.get("approved_by")), "approved_by"),
            (bool(approval.get("approved_at")), "approved_at"),
            (
                float(approval.get("max_usd", -1)) >= state["totals"]["worst_case_micro_usd"] / 1e6,
                "max_usd",
            ),
            (
                int(approval.get("max_input_tokens", -1)) >= state["totals"]["reserved_tokens"],
                "max_input_tokens",
            ),
            (
                int(approval.get("max_output_tokens", -1))
                >= protocol["budget_plan"]["output_token_cap"],
                "max_output_tokens",
            ),
        ]
        failed = [name for ok, name in checks if not ok]
        if failed:
            raise SystemExit("Approval rejected; mismatched fields: " + ", ".join(failed))
    write_json(directory / "approval.json", approval)
    state["phase"] = "approved"
    state["approval"] = {
        "approved_by": approval["approved_by"],
        "approved_at": approval["approved_at"],
        "human_approval": approval["human_approval"],
        "max_usd": approval["max_usd"],
        "no_retries": approval["no_retries"],
    }
    write_state(directory, state)
    print(f"approve: phase=approved human_approval={approval['human_approval']}")
    return state


def render_output(data):
    lines = [data["answer"], "", "Evidence quotations:"]
    evidence = data.get("evidence") or []
    if evidence:
        for item in evidence:
            lines.append('- "' + item["quote"].replace("\n", " ") + '"')
    else:
        lines.append("- None supplied.")
    lines.extend(
        [
            "",
            "Limitations: " + data["limitations"],
            "Uncertainty: " + data["uncertainty"],
        ]
    )
    if not data.get("sufficient_evidence"):
        lines.append("Abstention reason: " + (data.get("abstention_reason") or "Not stated."))
    return "\n".join(lines)


def output_record(task_id, condition, attempt, analysis, state):
    if analysis is None:
        return {
            "task_id": task_id,
            "condition": condition,
            "output_text": MISSING_OUTPUT,
            "output_sha256": hashlib.sha256(MISSING_OUTPUT.encode()).hexdigest(),
            "attempt_id": attempt["id"] if attempt else None,
            "analysis_id": None,
            "status": attempt["status"] if attempt else "missing",
            "missing": True,
            "abstained": None,
            "sufficient_evidence": None,
            "validation": attempt["data"].get("validation") if attempt else None,
            "error": attempt["data"].get("error") if attempt else None,
            "provider": state["provider"],
            "model": state["model"],
            "charged_tokens": attempt["data"].get("charged_tokens") if attempt else 0,
            "estimated_usd": attempt["data"].get("estimated_usd") if attempt else None,
            "synthetic": state["synthetic"],
            "recorded_at": now().isoformat(),
        }
    data = analysis["data"]
    text = render_output(data)
    return {
        "task_id": task_id,
        "condition": condition,
        "output_text": text,
        "output_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "attempt_id": attempt["id"] if attempt else data.get("consent_id"),
        "analysis_id": analysis["id"],
        "status": analysis["status"],
        "missing": False,
        "abstained": not data.get("sufficient_evidence"),
        "sufficient_evidence": data.get("sufficient_evidence"),
        "validation": data.get("validation"),
        "error": None,
        "provider": data.get("provider"),
        "model": data.get("model"),
        "charged_tokens": data.get("usage", {}).get("total_tokens", 0),
        "estimated_usd": data.get("estimated_usd"),
        "synthetic": state["synthetic"],
        "recorded_at": now().isoformat(),
    }


def reactivate_approved_grants(client, directory, state):
    """Re-activate only the grants bound to the approved immutable snapshots.

    ALIVE revokes live page grants on every restart. The owner approval covers the exact
    snapshot hashes and payloads, so the runner re-activates those grants and records it.
    """
    approval_bytes = (directory / "approval.json").read_bytes()
    approval_sha = hashlib.sha256(approval_bytes).hexdigest()

    async def activate():
        async with client.app.state.kernel.db.sessions.begin() as session:
            for task in state["tasks"]:
                snapshot = await session.get(WebExperience, task["snapshot_id"])
                grant = await session.get(WebExperience, task["grant_id"])
                if snapshot is None or grant is None:
                    raise PermissionError("Approved source or grant is missing")
                if snapshot.parent_id != grant.id:
                    raise PermissionError("Snapshot is not bound to the prepared grant")
                if snapshot.data.get("sha256") != task["current_sha256"]:
                    raise PermissionError("Approved current snapshot changed")
                if grant.data.get("url") != task["current_url"]:
                    raise PermissionError("Approved grant URL changed")
                if grant.status not in ("active", "revoked_restart"):
                    raise PermissionError("Approved grant is no longer re-activatable")
                grant.status = "active"
                grant.data = grant.data | {
                    "expires_at": (now() + timedelta(minutes=30)).isoformat(),
                    "reactivated_at": now().isoformat(),
                    "reactivated_for_run": state["run_id"],
                    "approval_sha256": approval_sha,
                }
        return True

    if client.portal.call(activate):
        state["grant_reactivations"] = {
            "count": len(state["tasks"]),
            "approval_sha256": approval_sha,
            "at": now().isoformat(),
            "note": "Grants bound to approved immutable snapshots re-activated after restart.",
        }


def execute(mode):
    protocol = verify_protocol_identity()
    directory, state = load_or_create_state(mode, protocol)
    if not state:
        raise SystemExit("prepare must run first")
    if state["phase"] in (
        "awaiting_ratings",
        "ready_to_reveal",
        "revealed",
        "analysed",
        "archived",
    ):
        print(f"execute: no-op for phase={state['phase']}")
        return state
    if state["phase"] not in ("approved", "executing"):
        raise SystemExit("execute requires an explicit approved phase")
    approval = read_json(directory / "approval.json")
    if approval.get("payload_sha256s") != {
        row["task_id"]: row["payload_sha256s"] for row in state["tasks"]
    }:
        raise SystemExit("Approval payload hashes no longer match the prepared manifest")
    if mode == "real" and not approval.get("human_approval"):
        raise SystemExit("Real execution requires human approval")
    if mode == "real" and not os.getenv("ALIVE_META_API_KEY"):
        raise SystemExit("ALIVE_META_API_KEY is not configured; no call was dispatched")
    state["phase"] = "executing"
    write_state(directory, state)
    token = token_for(directory)
    settings = build_settings(mode, protocol, directory, token)
    outputs_path = directory / "outputs.jsonl"
    outputs = {(row["task_id"], row["condition"]): row for row in read_jsonl(outputs_path)}
    tasks_by_id = {row["task_id"]: row for row in state["tasks"]}
    blocked = None
    with Client(settings, token) as client:
        reactivate_approved_grants(client, directory, state)
        inventory = call(client, "GET", "/research/relationships")
        attempts = inventory["analyses"]
        paired_by_id = {row["id"]: row for row in inventory.get("paired_analyses", [])}
        for task_id in state["task_order"]:
            task = tasks_by_id[task_id]
            for condition, research_id in (("A", None), ("B", task["memory_id"])):
                if (task_id, condition) in outputs:
                    continue
                approved_hash = task["payload_sha256s"][condition]
                prior = [
                    row
                    for row in attempts
                    if row["data"].get("current_snapshot_id") == task["snapshot_id"]
                    and row["data"].get("analysis_mode") == "paired"
                    and row["data"].get("payload_sha256") == approved_hash
                ]
                if prior:
                    attempt = prior[-1]
                    analysis = (
                        paired_by_id.get(attempt["data"].get("paired_analysis_id"))
                        if attempt["status"] == "validated"
                        else None
                    )
                    record = output_record(task_id, condition, attempt, analysis, state)
                    append_jsonl(outputs_path, record)
                    outputs[(task_id, condition)] = record
                    print(
                        f"execute: {task_id} {condition} recovered status={record['status']} "
                        f"missing={record['missing']}"
                    )
                    continue
                try:
                    fresh = preview(client, task, state["provider"], research_id)
                    if fresh["payload_sha256"] != approved_hash:
                        raise RuntimeError(
                            f"{task_id} {condition} payload hash changed after approval"
                        )
                    if fresh["request_sha256"] != task["request_sha256s"][condition]:
                        raise RuntimeError(
                            f"{task_id} {condition} request representation changed after approval"
                        )
                    call(
                        client,
                        "POST",
                        "/research/outbound/authorize",
                        {
                            "consent_id": fresh["id"],
                            "payload_sha256": fresh["payload_sha256"],
                            "approved": True,
                        },
                    )
                    result = call(
                        client,
                        "POST",
                        "/research/relationships",
                        {"consent_id": fresh["id"]},
                    )
                    attempt = result["analysis"]
                    analysis = result.get("paired_analysis")
                    record = output_record(task_id, condition, attempt, analysis, state)
                    append_jsonl(outputs_path, record)
                    outputs[(task_id, condition)] = record
                    print(
                        f"execute: {task_id} {condition} status={record['status']} "
                        f"abstained={record['abstained']} charged={record['charged_tokens']}"
                    )
                except Exception as exc:  # noqa: BLE001
                    blocked = {
                        "phase": "blocked",
                        "task_id": task_id,
                        "condition": condition,
                        "error": type(exc).__name__ + ": " + str(exc)[:1000],
                        "at": now().isoformat(),
                    }
                    print(f"execute: blocked at {task_id} {condition}: {blocked['error']}")
                    break
            if blocked:
                break
        if blocked:
            state["phase"] = "blocked"
            state["blocked"] = blocked
            write_state(directory, state)
            return state
        blind_tasks = []
        for task_id in state["task_order"]:
            task = tasks_by_id[task_id]
            source = next(row for row in protocol["tasks"] if row["task_id"] == task_id)
            outputs_for_task = {}
            metadata = {}
            attempt_ids = {}
            for condition in ("A", "B"):
                blind_condition = "A_current_only" if condition == "A" else "B_current_plus_history"
                record = outputs.get((task_id, condition))
                if record:
                    outputs_for_task[blind_condition] = record["output_text"]
                    metadata[blind_condition] = {
                        "provider": record.get("provider"),
                        "model": record.get("model"),
                        "usage": {"total_tokens": record.get("charged_tokens", 0)},
                        "estimated_usd": record.get("estimated_usd"),
                        "status": record["status"],
                        "missing": record["missing"],
                        "abstained": record["abstained"],
                    }
                    attempt_ids[blind_condition] = record.get("attempt_id")
                else:
                    outputs_for_task[blind_condition] = MISSING_OUTPUT
                    metadata[blind_condition] = {
                        "provider": None,
                        "model": None,
                        "usage": {"total_tokens": 0},
                        "estimated_usd": None,
                        "status": "missing",
                        "missing": True,
                        "abstained": None,
                    }
            outputs_for_task["C_history_without_synthesis"] = source["historical_source"]["excerpt"]
            metadata["C_history_without_synthesis"] = {
                "provider": None,
                "model": None,
                "usage": {"total_tokens": 0},
                "estimated_usd": None,
                "status": "direct_display",
                "missing": False,
                "abstained": None,
            }
            blind_tasks.append(
                {
                    "task_id": task_id,
                    "question": source["question"],
                    "current_excerpt": source["current_source"]["excerpt"],
                    "historical_excerpt": source["historical_source"]["excerpt"],
                    "current_url": source["current_source"]["url"],
                    "historical_url": source["historical_source"]["url"],
                    "current_sha256": source["current_source"]["sha256"],
                    "historical_sha256": source["historical_source"]["sha256"],
                    "outputs": outputs_for_task,
                    "attempt_ids": attempt_ids,
                    "output_metadata": metadata,
                }
            )
        blind = call(
            client,
            "POST",
            "/research/blind/runs",
            {
                "experiment_id": protocol["experiment_id"],
                "seed": protocol["seed"],
                "synthetic": state["synthetic"],
                "tasks": blind_tasks,
            },
        )
        state["blind"] = {
            "run_id": blind["id"],
            "rating_capability": blind["rating_capability"],
            "assignment_commitment": blind["assignment_commitment"],
            "output_count": len(blind_tasks) * 3,
            "randomized_creation_order": True,
            "condition_labels_hidden_before_reveal": True,
        }
        state["phase"] = "awaiting_ratings"
        write_state(directory, state)
        print(
            f"execute: phase=awaiting_ratings blind_run={blind['id']} "
            f"commitment={blind['assignment_commitment']}"
        )
        return state


def rate(mode, synthetic=False):
    protocol = verify_protocol_identity()
    directory, state = load_or_create_state(mode, protocol)
    if not state:
        raise SystemExit("prepare must run first")
    if state["phase"] in ("revealed", "analysed", "archived"):
        print(f"rate: no-op for phase={state['phase']}")
        return state
    if state["phase"] not in ("awaiting_ratings", "ready_to_reveal"):
        raise SystemExit("rate requires awaiting_ratings")
    token = token_for(directory)
    settings = build_settings(mode, protocol, directory, token)
    with Client(settings, token) as client:
        view = call(client, "GET", f"/research/blind/runs/{state['blind']['run_id']}")
        if synthetic:
            if mode != "synthetic":
                raise SystemExit("Synthetic ratings are only allowed for synthetic runs")
            if view["rating_capability"] is None:
                raise SystemExit("The rating capability is not available")
            rated = set(view["rated_output_ids"])
            for output in view["outputs"]:
                if output["output_id"] in rated:
                    continue
                call(
                    client,
                    "POST",
                    f"/research/blind/runs/{state['blind']['run_id']}/ratings",
                    {
                        "output_id": output["output_id"],
                        "output_sha256": output["output_sha256"],
                        "capability": view["rating_capability"],
                        "rubric": synthetic_rubric(output["task_id"]),
                        "synthetic": True,
                    },
                )
            view = call(client, "GET", f"/research/blind/runs/{state['blind']['run_id']}")
        rated = set(view["rated_output_ids"])
        total = len(view["outputs"])
        if rated == {row["output_id"] for row in view["outputs"]}:
            state["phase"] = "ready_to_reveal"
            state["ratings"] = {
                "owner_endpoint_ratings": len(rated),
                "synthetic": bool(synthetic),
                "human_owner_ratings": False if synthetic else None,
                "rating_pattern": (
                    "task_id_hash_null_pattern_identical_for_all_conditions"
                    if synthetic
                    else "owner_interface"
                ),
                "recorded_at": now().isoformat(),
            }
            write_state(directory, state)
            print(f"rate: phase=ready_to_reveal rated={len(rated)}/{total}")
            return state
        print(f"rate: complete {len(rated)}/{total} ratings through the native panel")
        return state


def reveal(mode):
    protocol = verify_protocol_identity()
    directory, state = load_or_create_state(mode, protocol)
    if not state:
        raise SystemExit("prepare must run first")
    if state["phase"] in ("revealed", "analysed", "archived"):
        print(f"reveal: no-op for phase={state['phase']}")
        return state
    if state["phase"] not in ("ready_to_reveal", "awaiting_ratings"):
        raise SystemExit("reveal requires completed ratings")
    token = token_for(directory)
    settings = build_settings(mode, protocol, directory, token)
    with Client(settings, token) as client:
        results = call(
            client,
            "POST",
            f"/research/blind/runs/{state['blind']['run_id']}/reveal",
            {},
        )
        if not verify_commitment(
            results["assignment_commitment"],
            results["commitment_salt"],
            results["commitment_payload"],
        ):
            raise SystemExit("Revealed assignment commitment did not verify")
        write_json(directory / "results.json", results)
        state["phase"] = "revealed"
        state["reveal"] = {
            "revealed_at": results["revealed_at"],
            "assignment_commitment": results["assignment_commitment"],
            "commitment_verified": True,
            "owner_ratings": len(results["ratings"]),
        }
        write_state(directory, state)
        print(f"reveal: phase=revealed ratings={len(results['ratings'])} commitment_verified=True")
        return state


def latest_ratings(results):
    latest = {}
    for row in results["ratings"]:
        key = row["data"]["output_id"]
        if key not in latest or row["data"]["revision"] > latest[key]["data"]["revision"]:
            latest[key] = row
    return latest


def supported_useful(rubric):
    return (
        rubric["factually_supported"] == "yes"
        and rubric["relevant_to_goal"] == "yes"
        and rubric["revealed_new"] == "yes"
        and rubric["misleading"] == "no"
    )


def analyse(mode):
    protocol = verify_protocol_identity()
    directory, state = load_or_create_state(mode, protocol)
    if not state:
        raise SystemExit("prepare must run first")
    if state["phase"] in ("analysed", "archived"):
        print(f"analyse: no-op for phase={state['phase']}")
        return state
    if state["phase"] != "revealed":
        raise SystemExit("analyse requires a revealed run")
    if canonical_sha256(ANSWER_KEY) != EXPECTED_ANSWER_KEY_SHA256:
        raise SystemExit("Sealed answer-key hash mismatch")
    answer_key = read_json(ANSWER_KEY)
    results = read_json(directory / "results.json")
    outputs = {
        (row["task_id"], row["condition"]): row for row in read_jsonl(directory / "outputs.jsonl")
    }
    ratings = latest_ratings(results)
    condition_rows = {"A": [], "B": [], "C": []}
    task_rows = []
    for task_id in state["task_order"]:
        task = next(row for row in protocol["tasks"] if row["task_id"] == task_id)
        key = answer_key["tasks"][task_id]
        conditions = {}
        for label in ("A", "B", "C"):
            output = next(
                row
                for row in results["outputs"]
                if row["task_id"] == task_id and row["condition"].startswith(label)
            )
            rating_row = ratings.get(output["output_id"])
            rubric = rating_row["data"]["rubric"] if rating_row else None
            supported = supported_useful(rubric) if rubric else None
            if supported is not None:
                condition_rows[label].append(supported)
            stored = outputs.get((task_id, label)) if label in ("A", "B") else None
            abstained = None
            if stored is not None:
                abstained = stored.get("abstained")
            elif label == "C":
                abstained = False
            expected_abstention = (
                key["expected_abstention"].get(label) if label in ("A", "B") else None
            )
            conditions[label] = {
                "output_id": output["output_id"],
                "supported_useful": supported,
                "rating": rubric,
                "rating_revision": rating_row["data"]["revision"] if rating_row else None,
                "rating_provenance": rating_row["data"].get("provenance") if rating_row else None,
                "owner_attestation": rating_row["data"].get("owner_attestation")
                if rating_row
                else None,
                "abstained": abstained,
                "expected_abstention": expected_abstention,
                "abstention_matches_expectation": (
                    abstained == expected_abstention
                    if abstained is not None and expected_abstention is not None
                    else None
                ),
                "missing": stored.get("missing") if stored else False,
                "attempt_id": output.get("attempt_id"),
            }
        task_rows.append(
            {
                "task_id": task_id,
                "stratum": task["stratum"],
                "history_role": task["history_role"],
                "expected_difference": task["expected_difference"],
                "reference_answer": key["reference_answer"],
                "prohibited_claims": key["prohibited_claims"],
                "conditions": conditions,
            }
        )
    summaries = {}
    for condition, values in condition_rows.items():
        summaries[condition] = {
            "n": len(values),
            "supported_useful": sum(1 for value in values if value),
            "proportion": sum(1 for value in values if value) / len(values) if values else None,
            "wilson_95": wilson(sum(1 for value in values if value), len(values))
            if values
            else None,
        }
    paired = [
        {
            "task_id": row["task_id"],
            "A": row["conditions"]["A"]["supported_useful"],
            "B": row["conditions"]["B"]["supported_useful"],
            "difference_b_minus_a": (
                row["conditions"]["B"]["supported_useful"]
                - row["conditions"]["A"]["supported_useful"]
                if row["conditions"]["A"]["supported_useful"] is not None
                and row["conditions"]["B"]["supported_useful"] is not None
                else None
            ),
        }
        for row in task_rows
    ]
    completed_pairs = [row for row in paired if row["difference_b_minus_a"] is not None]
    analysis = {
        "run_id": state["run_id"],
        "protocol_version": protocol["protocol_version"],
        "protocol_sha256": state["protocol_sha256"],
        "answer_key_sha256": state["answer_key_sha256"],
        "synthetic": state["synthetic"],
        "human_owner_ratings": False if state["synthetic"] else "requires_attestation",
        "owner_attestation_count": sum(
            1
            for row in task_rows
            for condition in ("A", "B", "C")
            if row["conditions"][condition]["owner_attestation"] == "human_reviewed"
        ),
        "primary_endpoint": protocol["primary_endpoint"],
        "model_request_parity": state.get("parity"),
        "conditions": summaries,
        "paired": paired,
        "paired_summary": {
            "completed_pairs": len(completed_pairs),
            "b_better": sum(1 for row in completed_pairs if row["difference_b_minus_a"] > 0),
            "a_better": sum(1 for row in completed_pairs if row["difference_b_minus_a"] < 0),
            "tied": sum(1 for row in completed_pairs if row["difference_b_minus_a"] == 0),
            "mean_difference": (
                sum(row["difference_b_minus_a"] for row in completed_pairs) / len(completed_pairs)
                if completed_pairs
                else None
            ),
        },
        "tasks": task_rows,
        "secondary": {
            "abstention_matches": sum(
                1
                for row in task_rows
                for condition in ("A", "B")
                if row["conditions"][condition]["abstention_matches_expectation"] is True
            ),
            "abstention_comparisons": len(task_rows) * 2,
            "missing_outputs": sum(
                1
                for row in task_rows
                for condition in ("A", "B")
                if row["conditions"][condition]["missing"]
            ),
            "misleading_yes": sum(
                1
                for row in task_rows
                for condition in ("A", "B", "C")
                if row["conditions"][condition]["rating"]
                and row["conditions"][condition]["rating"]["misleading"] == "yes"
            ),
            "invalid_outputs": sum(
                1
                for row in outputs.values()
                if row["status"] in ("rejected", "failed", "interrupted")
            ),
            "charged_tokens": sum(row.get("charged_tokens") or 0 for row in outputs.values()),
            "worst_case_micro_usd": state["totals"].get("worst_case_micro_usd", 0),
        },
        "limitations": [
            "Small pilot; no population-level significance claim.",
            "Semantic truth, relevance and novelty require owner judgement.",
            "C is a direct-display control and is not pooled with A or B.",
            "The analysis key is not a substitute for independent fact checking.",
        ],
        "analysed_at": now().isoformat(),
    }
    if state["synthetic"]:
        analysis["limitations"].insert(
            0, "Synthetic ratings are scripted and are not human owner ratings."
        )
    write_json(directory / "analysis.json", analysis)
    state["phase"] = "analysed"
    state["analysis_summary"] = {
        "conditions": summaries,
        "paired_summary": analysis["paired_summary"],
    }
    write_state(directory, state)
    print(
        "analyse: phase=analysed "
        + " ".join(
            f"{condition}= {summary['supported_useful']}/{summary['n']}"
            for condition, summary in summaries.items()
        )
    )
    return state


def archive(mode):
    protocol = verify_protocol_identity()
    directory, state = load_or_create_state(mode, protocol)
    if not state:
        raise SystemExit("prepare must run first")
    if state["phase"] == "archived":
        print("archive: no-op for phase=archived")
        return state
    if state["phase"] != "analysed":
        raise SystemExit("archive requires the analysed phase")
    token = token_for(directory)
    settings = build_settings(mode, protocol, directory, token)
    with Client(settings, token) as client:
        results = call(
            client,
            "GET",
            f"/research/blind/runs/{state['blind']['run_id']}/results",
        )
        if len(results["ratings"]) != state["blind"]["output_count"]:
            raise SystemExit("Restart retrieval did not return every owner rating")
        if not results.get("commitment_verified"):
            raise SystemExit("Restart retrieval did not preserve commitment verification")
        write_json(
            directory / "restart.json",
            {
                "retrieved_at": now().isoformat(),
                "rating_count": len(results["ratings"]),
                "commitment_verified": True,
                "status": results["status"],
            },
        )
    destination = ARCHIVE / state["run_id"]
    destination.mkdir(parents=True, exist_ok=True)
    state["phase"] = "archived"
    try:
        archive_path = str(destination.relative_to(ROOT))
    except ValueError:
        archive_path = str(destination)
    state["archive"] = {"path": archive_path, "at": now().isoformat()}
    write_state(directory, state)
    for name in (
        "state.json",
        "approval.json",
        "preview-manifest.json",
        "outputs.jsonl",
        "results.json",
        "analysis.json",
        "restart.json",
    ):
        source = directory / name
        if source.exists():
            shutil.copyfile(source, destination / name)
    files = {}
    for path in sorted(destination.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            payload = path.read_bytes().replace(b"\r\n", b"\n")
            files[path.relative_to(destination).as_posix()] = {
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
            }
    write_json(
        destination / "manifest.json",
        {
            "run_id": state["run_id"],
            "protocol_version": protocol["protocol_version"],
            "protocol_sha256": state["protocol_sha256"],
            "answer_key_sha256": state["answer_key_sha256"],
            "synthetic": state["synthetic"],
            "paid_calls": (0 if state["synthetic"] else "requires_provider_reconciliation"),
            "files": files,
        },
    )
    print(f"archive: phase=archived path={destination}")
    return state


def status(mode):
    protocol = verify_protocol_identity()
    directory, state = load_or_create_state(mode, protocol)
    if not state:
        raise SystemExit("No prepared run")
    print(
        json.dumps(
            {
                "run_id": state["run_id"],
                "mode": state["mode"],
                "phase": state["phase"],
                "protocol_sha256": state["protocol_sha256"],
                "provider": state["provider"],
                "model": state["model"],
                "tasks": len(state["tasks"]),
                "calls": state["totals"]["calls"],
                "worst_case_usd": state["totals"]["worst_case_micro_usd"] / 1e6,
                "blind_run": state.get("blind", {}).get("run_id"),
            },
            indent=2,
        )
    )
    return state


def full_synthetic():
    prepare("synthetic")
    approve("synthetic", synthetic=True)
    state = execute("synthetic")
    if state["phase"] == "blocked":
        raise SystemExit("Synthetic execution blocked: " + state["blocked"]["error"])
    rate("synthetic", synthetic=True)
    reveal("synthetic")
    analyse("synthetic")
    archive("synthetic")
    print("SYNTHETIC_FULL_RUN_COMPLETE")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "phase",
        choices=[
            "prepare",
            "approve",
            "execute",
            "rate",
            "reveal",
            "analyse",
            "archive",
            "status",
            "full-synthetic",
        ],
    )
    parser.add_argument("--mode", choices=["synthetic", "real"], default="synthetic")
    parser.add_argument("--approval-file")
    parser.add_argument("--synthetic", action="store_true")
    args = parser.parse_args(argv)
    if args.phase == "full-synthetic":
        full_synthetic()
        return 0
    if args.phase == "prepare":
        result = prepare(args.mode)
    elif args.phase == "approve":
        result = approve(args.mode, args.approval_file, args.synthetic)
    elif args.phase == "execute":
        result = execute(args.mode)
    elif args.phase == "rate":
        result = rate(args.mode, args.synthetic)
    elif args.phase == "reveal":
        result = reveal(args.mode)
    elif args.phase == "analyse":
        result = analyse(args.mode)
    elif args.phase == "archive":
        result = archive(args.mode)
    else:
        result = status(args.mode)
    return 1 if result.get("phase") == "blocked" else 0


if __name__ == "__main__":
    sys.exit(main())
