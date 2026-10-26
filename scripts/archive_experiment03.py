"""Export synthetic ALIVE-03 qualification evidence without credentials or browser data."""

import hashlib
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import httpx

from alive.config import Settings, prepare_local
from alive.experiment.freeze import ROOT, verify
from alive.experiment.prompts import specification


def main():
    archive = Path("archives/ALIVE-03-P1")
    if archive.exists():
        raise SystemExit("Archive exists; refusing to overwrite qualified evidence")
    settings = Settings()
    client = httpx.Client(
        base_url="http://127.0.0.1:8000/api/v1",
        headers={"Authorization": "Bearer " + prepare_local(settings)},
        timeout=30,
    )

    def get(path):
        response = client.get(path)
        response.raise_for_status()
        return response.json()

    pack = get("/experiments/review-pack")
    assert pack["ready_for_owner_review"] and not pack["full_run_executed"]
    frozen = verify(pack["freeze"]["freeze_id"])
    parameters = json.loads((ROOT / "policy-configuration.json").read_text())
    calibration = get("/experiments/runs/" + parameters["source_run_id"])
    pilot = get("/experiments/runs/" + pack["pilot_run_id"])
    for run in [calibration, pilot]:
        assert run["status"] == "completed" and run["provider"] == "meta"
        assert all(c["status"] == "validated" for c in run["data"]["ledger"])
        assert all(
            set(c["input"])
            <= {
                "subject",
                "objective",
                "operation",
                "required_fields",
                "action_risk",
                "sources",
                "initial_decision",
            }
            for c in run["data"]["ledger"]
        )

    def redact(value):
        if isinstance(value, dict):
            return {
                k: redact(v)
                for k, v in value.items()
                if k not in {"instance_id", "topics", "origins", "preferred_action"}
            }
        if isinstance(value, list):
            return [redact(v) for v in value]
        return value

    archive.mkdir(parents=True)

    def write(name, value):
        path = archive / name
        path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(redact(value), indent=2) + "\n"
        assert settings.alive_meta_api_key not in data
        path.write_bytes(data.encode())

    for name in [
        "calibration.json",
        "evaluation.sealed.json",
        "split-manifest.json",
        "freeze-design.json",
        "freeze-final.json",
        "policy-configuration.json",
        "calibration-evidence.json",
    ]:
        shutil.copyfile(ROOT / name, archive / name)
    write("results/live-calibration.json", calibration)
    write("results/live-pilot.json", pilot)
    write("review-pack.json", pack)
    write("model-and-prompts.json", specification())
    write(
        "usage/redacted-ledger.json",
        {
            "redaction": "No credentials, request headers, runtime identity, personal topics or "
            "browser data. All 24 physical model calls, synthetic inputs, structured outputs, "
            "usage, correlation IDs, latency and prompt text retained.",
            "calls": calibration["data"]["ledger"] + pilot["data"]["ledger"],
            "confirmed_provider_billing": None,
        },
    )
    # The run's pinned-model discovery gate already checked availability; no new model request.
    write(
        "pricing.json",
        pack["pricing"]
        | {
            "checked_on": "2026-10-26",
            "confirmed_provider_billing": None,
            "reasoning_tokens": "Already included in completion_tokens; never added again",
            "availability": "Pinned model passed live discovery and 24 structured calls",
        },
    )
    shutil.copyfile("docs/ALIVE-03-P1.md", archive / "protocol.md")
    shutil.copyfile(".alive/alive03-acceptance.png", archive / "acceptance.png")
    for name in ["backend-tests", "frontend-tests", "frontend-build", "browser-tests"]:
        path = archive / "validation" / (name + ".txt")
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(Path(".alive/alive03-" + name + ".txt").read_text().encode())
    old_root = Path("archives/ALIVE-02")
    old = json.loads((old_root / "manifest.json").read_text())
    checked = []
    for name, entry in old["files"].items():
        data = (old_root / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == entry["sha256"]
        assert len(data) == entry["bytes"]
        checked.append(name)
    write(
        "validation/baseline-integrity.json",
        {
            "required_baseline": "72b2e4c12b1864bb94136af96a82fd96a6a6bbe2",
            "all_15_payload_checksums_verified": len(checked) == 15,
            "checked_payloads": checked,
            "baseline_before_changes": {"backend": 33, "frontend": 4, "browser_e2e": 2},
            "final": {
                "backend_existing": 33,
                "backend_new": 22,
                "backend_total": 55,
                "frontend": 4,
                "browser_e2e_existing": 2,
                "browser_e2e_new": 1,
            },
            "production_build": "passed",
            "ruff_check_and_format": "passed",
            "warning": "Windows ZeroMQ uses a tornado selector thread; tests pass",
        },
    )
    summary = pilot["data"]["summary"]
    projection = pack["projection"]
    source_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    text = f"""# ALIVE-03-P1 qualification — PASS_WITH_LIMITATIONS

Gates A–F completed. Full evaluation has **not run** and remains subject to explicit owner
authorization and increased configured Governor budgets. No MR.Q or RL training was added.

Branch: `codex/alive-03-p1-selective-cognition`. Tested implementation: `{source_commit}`.
The following archive commit adds evidence only; use `git log` for the final branch HEAD.
Worktree at qualification contains only the pre-existing untracked `models.txt` after commits.
No push, merge, deployment or changes to main were performed.

- All 15 ALIVE-02 payload checksums verified; frozen evidence unchanged.
- Regressions: 33 existing backend tests, 4 frontend tests, 2 existing Chrome E2E tests.
- New: 22 backend tests and 1 policy-comparison Chrome E2E test. Total backend: 55 passing.
- Production dashboard build, Ruff lint and formatting pass.
- Corpus: 48 development tasks (12/category), 120 held-out tasks (30/category).
- Live calibration: 8 development pairs, 16 Meta calls, 20,616 tokens, estimated $0.042567.
- Distinct live pilot: 4 development tasks, 8 Meta calls, 10,747 tokens, estimated $0.02027745.
- Total qualification inference: 24 calls, 31,363 tokens, estimated $0.06284445.
- Always/Never/Selective pilot correctness: 4/4 each; Critic calls: 4/0/0 respectively.
- Calibration selected threshold 1.1: Selective currently behaves like NeverCritic. No Critic
  rescue or regression was observed. This result is preserved rather than tuned away.

Freeze identity: `{frozen["freeze_id"]}`.
Dataset/evaluator hashes: `freeze-final.json` (canonical UTF-8 source identities) and
`manifest.json` (exact archived bytes). Schema, scorer, dependency lock, policy, model and
prompt identities are frozen. Full-run entry verifies the same identity and consumes a one-use
authorization. Design/policy re-freezing is forbidden after evaluation unsealing.

## Full paid evaluation review

Pilot-scaled projection: **{projection["expected_unique_calls"]:.0f} calls,
{projection["expected_reported_tokens"]:,.0f} tokens, estimated
${projection["expected_rate_card_usd"]:.6f}**. Conservative run ceilings proposed:
360 calls and 1,500,000 charged tokens, across two explicitly authorized 60-task sessions.
At the current maximum published token rate, that token ceiling corresponds to a $6.375
rate-card bound; it is not an invoice or a guarantee about account billing.

Remaining Governor budget at snapshot:
{json.dumps(pack["remaining_governor_budget"], indent=2)}

The existing experiment call ceiling cannot cover even the projected 240 calls.
No budget was raised for the full run. The review pack suggests 180 calls/1,000,000 tokens
per session and 500 calls/2,000,000 tokens cumulative, preserving already spent counters.
Review these settings and give explicit full-run authorization before executing anything.
Ready **for owner review**, conditional on those two prerequisites; not automatically runnable.

## Interpretation and limitations

The pilot qualifies the pipeline, not unseen performance or selective-policy superiority.
Only eight pairs calibrated one threshold; all initial answers were already correct. The
controller may be underpowered or the development tasks too easy. Deterministic signal weights
are designed, not learned. No evaluation outcome was used for threshold selection.

The first-party numerical corpus is narrow. Operation families are separated across splits,
but lexical audits cannot prove semantic independence; templates within families are correlated.
The evaluation file is procedurally sealed plaintext, not blind to generator authors. It has
not been submitted for model inference. Prompts and scorer share an explicit evidence contract,
which may make these tasks easier than open-world investigations.

Shared initial outputs are not independent live trials. Critic outputs are separate when
invoked, although this live threshold never invokes Selective's Critic; controlled tests verify
the distinct-review path. Path latency excludes competing-arm queue time; task wall time is
recorded separately. Shared initial cost is attributed to every policy path but paid once.
Never add path totals to estimate provider billing.

Wilson intervals and family-cluster bootstrap intervals are descriptive; the four-task pilot
has weak uncertainty estimates. Full-run failure/timeout or budget interruption must be
reported with incomplete-task counts, not silently omitted. Source drift requires renewed
development qualification before evaluation; after unsealing, the policy remains frozen.

Costs use [Meta's published rate card](https://dev.meta.ai/docs/pricing-rate-limits), checked
2026-10-26: $1.25/M input, $0.15/M cached input, $4.25/M output. Reasoning is included in
completion usage. **Confirmed provider billing is unavailable.** Projection varies with task
length, sampling, caching and failures. Existing Governor request reservations are conservative
UTF-8 estimates, not provider-side guaranteed quotas.

See `protocol.md`, `review-pack.json`, `results/`, `usage/redacted-ledger.json`, `validation/`
and `acceptance.png`. The manifest covers every archive payload except itself.
"""
    (archive / "README.md").write_bytes(text.encode())
    (archive / ".gitattributes").write_bytes(b"* -text whitespace=cr-at-eol\n")
    payloads = {
        p.relative_to(archive).as_posix(): {
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "bytes": p.stat().st_size,
        }
        for p in sorted(archive.rglob("*"))
        if p.is_file()
    }
    write(
        "manifest.json",
        {
            "schema_version": 1,
            "captured_at": datetime.now(UTC).isoformat(),
            "implementation_commit": source_commit,
            "freeze_id": frozen["freeze_id"],
            "full_evaluation_executed": False,
            "files": payloads,
            "physical_pilot_calls": summary["physical_unique_calls"],
        },
    )
    print(f"Archived {len(payloads)} payloads; no full evaluation executed")


if __name__ == "__main__":
    main()
