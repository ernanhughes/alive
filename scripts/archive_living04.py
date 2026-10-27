"""Archive the native Chrome/Meta journey, causal checks and restart evidence."""

import asyncio
import hashlib
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from alive.cognitive_schema import RoleOutput
from alive.config import Settings
from alive.db import Database
from alive.experiment.freeze import file_hash
from alive.experiment_budget import charged_micro_usd
from alive.living_evaluation import assess
from alive.living_models import LivingPolicy, LivingTransition
from alive.living_policy import choose, update
from alive.models import BrowserSession, Event, Memory, record


async def database_evidence(settings, journey):
    db = Database(settings.database_url)
    browser_ids = [t["data"]["browser_session_id"] for t in journey["transitions"]]
    transition_ids = [t["id"] for t in journey["transitions"]]
    first_call, last_call = journey["data"]["ledger"][0], journey["data"]["ledger"][-1]
    lower = datetime.fromisoformat(first_call["completed_at"])
    upper = datetime.fromisoformat(last_call["started_at"])
    async with db.sessions() as session:
        events = (
            await session.scalars(
                select(Event)
                .where(
                    Event.event_type.like("living.%")
                    | Event.event_type.like("browser.%")
                    | (Event.event_type == "action.executed")
                    | (Event.event_type == "alive.started")
                )
                .order_by(Event.sequence_number)
            )
        ).all()
        kept, restarts = [], []
        for event in events:
            when = event.recorded_at
            if when.tzinfo is None:
                when = when.replace(tzinfo=lower.tzinfo)
            if event.event_type == "alive.started" and lower < when < upper:
                restarts.append(record(event))
            if (
                event.payload.get("journey_id") == journey["id"]
                or event.payload.get("session_id") in browser_ids
            ):
                kept.append(record(event))
        browsers = [record(await session.get(BrowserSession, key)) for key in browser_ids]
        memories = (await session.scalars(select(Memory))).all()
        memories = [
            record(m) for m in memories if m.metadata_json.get("transition_id") in transition_ids
        ]
        transitions = (
            await session.scalars(
                select(LivingTransition)
                .where(LivingTransition.journey_id == journey["id"])
                .order_by(LivingTransition.episode)
            )
        ).all()
        policy = await session.get(LivingPolicy, transitions[0].instance_id)
        evidence = {
            "backend": db.engine.dialect.name,
            "events": kept,
            "restarts_between_calls": restarts,
            "browsers": browsers,
            "memory_records": memories,
            "stored_transitions": [record(t) for t in transitions],
            "persistent_policy": policy.data,
        }
    await db.engine.dispose()
    return evidence


def main():
    root = Path("archives/ALIVE-04")
    if root.exists():
        raise SystemExit("Archive exists; refusing overwrite")
    plan = json.loads(Path(".alive/alive04-plan.json").read_text())
    first = json.loads(Path(".alive/alive04-first.json").read_text())
    journey = json.loads(Path(".alive/alive04-second.json").read_text())
    restart = json.loads(Path(".alive/alive04-restart-proof.json").read_text())
    settings = Settings()
    db = asyncio.run(database_evidence(settings, journey))
    a, b = [t["data"] for t in journey["transitions"]]
    ledger = journey["data"]["ledger"]
    assert journey["status"] == "completed" and len(ledger) == 2
    assert db["backend"] == "postgresql" and db["restarts_between_calls"]
    assert len(db["memory_records"]) == 2 and all(p["status"] == "closed" for p in db["browsers"])
    assert a["state"]["feature_hash"] == b["state"]["feature_hash"]
    assert a["after_hash"] == b["before_hash"] == restart["policy_hash"]
    assert choose(plan["initial_policy"], b["state"]["context"])["action"] == "monitor"
    assert b["choice"]["action"] == "retrieve" and b["memory_ids"] == [
        journey["transitions"][0]["id"]
    ]
    assert a["outcome"]["safe_abstention"] and b["outcome"]["resolved"]
    assert all(c["provider"] == "meta" and c["status"] == "validated" for c in ledger)
    choices = [p for p in journey["data"]["phases"] if p["stage"] == "choosing"]
    assert all(choices[i]["at"] <= c["started_at"] for i, c in enumerate(ledger))
    assert ledger[0]["input"]["sources"] == []
    assert "Feedback measurement:" not in ledger[0]["input"]["observation"]
    for path, expected in plan["source_hashes"].items():
        native_source = subprocess.check_output(
            ["git", "show", plan["implementation_commit"] + ":" + path]
        )
        canonical_source = native_source.decode().replace("\r\n", "\n").encode()
        assert hashlib.sha256(canonical_source).hexdigest() == expected
    replay = []
    for transition, call in zip(journey["transitions"], ledger, strict=True):
        data = transition["data"]
        fresh = assess(
            RoleOutput.model_validate(data["model_output"]),
            call["input"]["sources"],
            data["outcome"]["measurement"],
        )
        assert all(
            fresh[key] == data["outcome"][key]
            for key in ["resolved", "safe_abstention", "factual_correct"]
        )
        assert (
            update(
                data["policy_before"],
                data["choice"]["action"],
                data["reward"],
                data["state"]["context"],
            )
            == data["policy_after"]
        )
        replay.append(
            {
                "episode": data["episode"],
                "assessment": fresh,
                "original_classification_retained": True,
                "policy_update_retained": True,
            }
        )
    prior = {}
    for archive in Path("archives").iterdir():
        if not (archive / "manifest.json").is_file():
            continue
        manifest = json.loads((archive / "manifest.json").read_text())
        for name, expected in manifest["files"].items():
            data = (archive / name).read_bytes()
            assert hashlib.sha256(data).hexdigest() == expected["sha256"]
            assert len(data) == expected["bytes"]
        prior[archive.name] = {"payloads_verified": len(manifest["files"]), "unchanged": True}
    root.mkdir(parents=True)

    def redact(value):
        if isinstance(value, dict):
            result = {
                k: redact(v)
                for k, v in value.items()
                if k not in {"instance_id", "agent_instance", "topics", "origins", "identity"}
            }
            if "identity" in value:
                result["identity_sha256"] = hashlib.sha256(
                    str(value["identity"]).encode()
                ).hexdigest()
            return result
        if isinstance(value, list):
            return [redact(v) for v in value]
        return value

    def write(name, value):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(redact(value), indent=2, default=str) + "\n"
        assert settings.alive_meta_api_key not in text
        path.write_bytes(text.encode())

    write("live/first-encounter.json", first)
    write("live/completed-journey.json", journey)
    write("live/redacted-usage-ledger.json", ledger)
    write("live/restart-proof.json", restart)
    write("live/database-evidence.json", db)
    write("live/qualification-plan.json", plan)
    write("live/release-evaluation-replay.json", replay)
    write(
        "release-source-hashes.json",
        {
            path: file_hash(path)
            for path in [
                "alive/living.py",
                "alive/living_policy.py",
                "alive/living_evaluation.py",
                "alive/living_api.py",
                "alive/living_models.py",
            ]
        },
    )
    write("prior-evidence-integrity.json", prior)
    write(
        "integration-baseline.json",
        {
            "main": "a060a6c",
            "p2": "f257cbc",
            "p3": "930fb23",
            "qualified_integration": "3719cf461e839c6af8aee3681725f43bd265d74d",
            "p2_p3_published": True,
            "new_main_merges": False,
            "baseline_tests": {"backend": 76, "frontend": 4, "browser": 5},
        },
    )
    for source, target in [
        ("alive04-backend-tests.txt", "validation/backend.txt"),
        ("alive04-browser-tests.txt", "validation/browser.txt"),
        ("alive04-living-browser-final.txt", "validation/final-living-browser.txt"),
        ("alive04-frontend-tests.txt", "validation/frontend.txt"),
        ("alive04-frontend-build.txt", "validation/build.txt"),
        ("alive04-baseline-backend.txt", "validation/baseline-backend.txt"),
        ("alive04-baseline-frontend.txt", "validation/baseline-frontend.txt"),
        ("alive04-baseline-browser.txt", "validation/baseline-browser.txt"),
        ("alive04-baseline-build.txt", "validation/baseline-build.txt"),
        ("alive04-acceptance.png", "acceptance.png"),
        ("alive04-encounters.png", "encounters.png"),
    ]:
        target_path = root / target
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(".alive") / source, target_path)
    shutil.copyfile("docs/ALIVE-04.md", root / "protocol.md")
    total_tokens = sum(c["usage"]["total_tokens"] for c in ledger)
    dollars = sum(c["estimated_usd"] for c in ledger)
    source_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    report = f"""# ALIVE-04 — Living Experience: PASS_WITH_LIMITATIONS

**ALIVE changed a permitted browser action after observed feedback, retained the learned policy
across a backend restart, and reused the relevant prior experience in a matched later situation.**
The action change is deterministic and precedes Meta synthesis; it is not a different answer
selected from model sampling. This is a controlled live integration result, not broad autonomy.

## Integration and publication

P2 and P3 histories/evidence are published at
[`f257cbc`](https://github.com/ernanhughes/alive/tree/codex/alive-03-p2-predictive-learning) and
[`930fb23`](https://github.com/ernanhughes/alive/tree/codex/alive-03-p3-prediction-diagnostic).
Their owner acceptance was PASS_WITH_LIMITATIONS. Baseline checks passed before integration:
76 backend, four frontend and five browser tests plus the production build. All prior evidence
hashes verified. Local integration `3719cf4` combines latest origin/main `a060a6c` with those
branches, without changing main. Its file tree matches the tested P3 baseline.

ALIVE-04 branch: `codex/alive-04-living-experience`. Native Chrome/Meta implementation commit:
`{plan["implementation_commit"]}`. Final UI/evidence tooling commit: `{source_commit}`.
The following archive commit contains evidence. No ALIVE-04 push, deployment or main change.
After commits, only the pre-existing `models.txt` is untracked.

## The completed journey

| Encounter | Prior relevant experiences | Action | Meta conclusion | Observed utility |
|---|---:|---|---|---:|
| First | 0 | Monitor | Safe abstention without current evidence | -0.50 |
| Related, after restart | 1 | Retrieve evidence | Verified 20, contradicting claimed 32 | +0.85 |

Both Chrome observations project to feature hash `{a["state"]["feature_hash"]}`. The page claim
and source-replacement cue match; episode/session identifiers are excluded from the state used
by the policy. The original snapshot still chooses **monitor** for the second state. The updated
policy chooses **retrieve**, using the first completed transition as its recalled experience.
First after-policy hash and second before-policy hash both equal `{a["after_hash"]}`.

Every action choice was recorded before the corresponding Meta request. Meta did not choose
the action. Its existing Proposer role supplied real, structured read-only reasoning from
visible browser evidence. The first input had no current instrument source; hidden instrument
and feedback text were excluded. The second source was extracted after an allowed DOM click.
Published end-of-episode feedback was read from Chrome after reasoning, not invented by a model.

The transition, feedback, policy update, generic Memory record and journey progress commit in
one PostgreSQL transaction. Two closed native Chrome sessions, two persisted Memory records,
two completed transitions, the policy and relevant event journal are captured in
`live/database-evidence.json`. Database dialect: **{db["backend"]}**.

## Restart and causal checks

There is a recorded `alive.started` event between the two model calls, as well as the explicit
restart proof. Identity digest, first transition, policy hash and one-call ledger persisted.
No worker or extra model call auto-resumed. The owner explicitly advanced the second encounter.
Native inference/browser code hashes match on both sides of the restart and match the preserved
implementation commit. A post-qualification classification patch separates factual support
from conclusion acceptance in the unobserved correct-fact/`investigate` edge case from P1.
The recorded native outcomes were replay-checked against that release assessment: both original
classifications, rewards and policy updates remain unchanged. No paid run was repeated and no
policy was reset. Native and release identities are preserved separately.

The causal counterfactual is the original deterministic action policy on the actual second
feature state. It is not an independently executed baseline Meta trial. A stronger fixed
history-aware rule would retrieve from the first encounter; this demonstration does not claim
to outperform that rule. There is no branch keyed on episode number that changes the action.

## Actual usage and limits

- Native Meta model: **muse-spark-1.3**, existing Proposer role, no mandatory Critic.
- **{len(ledger)} real model calls**, **{total_tokens:,} reported tokens**.
- **${dollars:.7f} estimated**.
- Conservative application charge: ${charged_micro_usd(ledger) / 1e6:.6f}.
- Journey ceilings: two calls, 40,000 tokens, six browser operations, estimated $0.15.
- Browser operations: **{len(journey["data"]["tool_log"])}**.
  First observe/feedback; then observe/retrieve/feedback.
- No automatic model retries, model errors or unknown usage in this live journey.

Prices use [Meta's published rate card](https://dev.meta.ai/docs/pricing-rate-limits), checked
27 October 2026. Dollar figures are estimates, not confirmed provider billing. Utility is a
separate synthetic task reward, not money. Reasoning tokens are included in completion usage.

## Governor and acceptance checks

The grant covers only the controlled local habitat's public observations and allowed clicks.
Arbitrary destinations, selectors, external actions and model-requested tools are not accepted.
Per-request, episode, journey, session and experiment budget checks precede model inference.
The native Browser checks origins and permitted DOM operations; the Governor checks tool limits.
Budget/configuration changes and concurrent autonomous/experimental workers are blocked while
living work is active. Stop revokes permission and conservatively settles interrupted usage.

Tests: **83 backend** (76 prior plus seven living tests), **four frontend**, **six browser E2E**;
production build and Ruff checks pass. The final living-only browser check also passes after
the visual polish. Coverage includes missing/out-of-scope grants, zero budget, stop/cancellation,
unknown-call settlement, no paid replay, fixture/live context isolation, restart persistence,
matched-state counterfactuals and the actual controlled DOM visibility/clicks. Unit credentials
are explicitly empty so tests cannot inherit the owner's provider key.

## What this proves, and its limits

The complete observe → remember → predict → choose → act → reason → feedback → learn loop is
visible in the Living tab. Feedback affects the next action and remains durable across restart.
After encounter two, stored action means are monitor -0.50 (one outcome) and retrieve +0.85
(one outcome). The UI shows those counts and small-sample uncertainty, including unknown priors.

This is a tiny empirical outcome-mean policy with a zero prior and lower-resource tie-break.
The first negative outcome causes exploration of an untried option. It is not deep RL, MR.Q,
general self-improvement, calibrated prediction confidence or proof of held-out generalization.
No predictive representation learner is a runtime dependency.

The two encounters deliberately reuse an inspectable synthetic fixture. The source-replacement
cue is explicitly published in the DOM, not inferred from unrestricted browser history or real
semantic embeddings. Memory retrieval is exact context matching, not open-ended semantic recall.
The synthetic feedback contract rewards current verification and penalizes unresolved goals.
Safe factual abstention in encounter one is preserved; it is not relabeled as a wrong fact.

Controlled fixtures and real-Meta contexts are separated so mock rewards do not train live
action values. New journeys reuse existing policies; there is no hidden reset for a favorable
demo. Warm journeys can show no new action change, and the UI reports that. Real-browser use
outside this controlled habitat needs additional implementation and evaluation.

## Evidence

`live/` contains both encounter snapshots, complete redacted model ledger, qualification plan,
restart proof, PostgreSQL/browser/memory/event evidence. `acceptance.png` and `encounters.png`
show the verified UI. `validation/` holds current and baseline test/build transcripts.
Prior qualification archives are byte-for-byte intact; their checksum results are retained.
Runtime identity is represented by digest where applicable; credentials and personal browsing
data are excluded. `manifest.json` hashes every archive payload except itself.
"""
    (root / "README.md").write_bytes(report.encode())
    (root / ".gitattributes").write_bytes(b"* -text whitespace=cr-at-eol\n")
    payloads = {
        p.relative_to(root).as_posix(): {
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "bytes": p.stat().st_size,
        }
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }
    write(
        "manifest.json",
        {"journey_id": journey["id"], "implementation_commit": source_commit, "files": payloads},
    )
    print(f"Archived {len(payloads)} payloads; causal behavior change and restart verified")


if __name__ == "__main__":
    main()
