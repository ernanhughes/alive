"""Independent-custody evaluation gate (ALIVE-EVAL-02). Offline, no model calls.

v1 (`alive_eval01_custodian`) proved structural validation: recomputed metrics,
exact binding, scope derivation, forgery battery. It cannot distinguish a
submitter who invents a distinct custodian identity from a genuine independent
custodian, so v1 verdicts must never count as qualified progress.

v2 keeps every v1 structural check and adds the trust layer:

- Machine-enforced custody states from the trust-model vocabulary:
  CUSTODY_NOT_ESTABLISHED / IMPLEMENTED_UNQUALIFIED / QUALIFIED.
- QUALIFIED requires sealed custody artifacts committed in the evaluator's own
  pinned sealed root plus a human-confirmed boundary. No anchor is configured,
  so QUALIFIED is unreachable by construction and PROGRESS can never issue.
- Diagnostic improvement is still measured honestly (IMPROVEMENT_OBSERVED)
  but reported alongside verdict INCONCLUSIVE/NO_PROGRESS and
  scientific_qualification NOT_ESTABLISHED.
- Receipts bind canonical fingerprints of every input; verification rejects
  tampering, substitution, and cross-package replay.

v1 is preserved byte-unchanged as the historical implementation; v2 is the
authoritative entry point for new qualification attempts.
"""

import hashlib
import json
import subprocess
from pathlib import Path

from scripts import alive_eval01_custodian as v1
from scripts.notebook03a_r2_protocol import score_r2, validate_corpus_r2

EVAL02_VERSION = "alive-eval-02-v1"
EVAL02_ROOT = Path(__file__).resolve().parents[1] / "evaluations" / "alive-eval-02"
TRUST_ANCHORS_PATH = EVAL02_ROOT / "trust_anchors.json"
PINNED_BOOTSTRAP_PATH = EVAL02_ROOT / "pinned_bootstrap.json"
SEALED_ROOT = EVAL02_ROOT / "sealed"

CUSTODY_NOT_ESTABLISHED = "CUSTODY_NOT_ESTABLISHED"
IMPLEMENTED_UNQUALIFIED = "IMPLEMENTED_UNQUALIFIED"
QUALIFIED = "QUALIFIED"


def canonical(data) -> bytes:
    return json.dumps(data, sort_keys=True, ensure_ascii=False).encode()


def fingerprint(data) -> str:
    return v1.hash_bytes(canonical(data))


def source_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
        sha = out.stdout.strip()
        return sha if len(sha) == 40 and all(c in "0123456789abcdef" for c in sha) else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def load_trust_anchors(path=TRUST_ANCHORS_PATH):
    raw = v1.strict_json_load(path)
    if not isinstance(raw, dict):
        raise ValueError("trust anchors must be a JSON object")
    custodians = raw.get("independent_custodians", [])
    if not isinstance(custodians, list) or any(not isinstance(c, str) for c in custodians):
        raise ValueError("independent_custodians must be a list of strings")
    return {"version": raw.get("version"), "independent_custodians": sorted(set(custodians))}


def load_pinned_bootstrap(path=PINNED_BOOTSTRAP_PATH):
    raw = v1.strict_json_load(path)
    pinned = {}
    for key in ("bootstrap_seed", "bootstrap_resamples", "ci_level"):
        if key not in raw:
            raise ValueError(f"pinned bootstrap missing {key}")
        pinned[key] = raw[key]
    if (
        not isinstance(pinned["bootstrap_seed"], int)
        or isinstance(pinned["bootstrap_seed"], bool)
        or not isinstance(pinned["bootstrap_resamples"], int)
        or isinstance(pinned["bootstrap_resamples"], bool)
        or not isinstance(pinned["ci_level"], (int, float))
        or isinstance(pinned["ci_level"], bool)
        or not 0.0 < pinned["ci_level"] < 1.0
    ):
        raise ValueError("pinned bootstrap values are malformed")
    return pinned


def check_sealed_custody(custody_dir, tasks, labels, sealed_root=SEALED_ROOT):
    """Match the submitted custody record against repo-pinned sealed artifacts.

    Returns (matched, detail). A match requires a byte-identical sealed record
    whose package/gold hashes bind the evaluated inputs and which carries a
    human-confirmed access boundary. An empty sealed root never matches.
    """
    if custody_dir is None:
        return False, "no custody directory supplied"
    sealed_root = Path(sealed_root)
    try:
        submitted = (Path(custody_dir) / "custody.json").read_bytes()
    except OSError as exc:
        return False, f"unreadable custody record: {exc}"
    task_bytes = canonical([t.model_dump() for t in tasks])
    gold_bytes = canonical([a.model_dump() for a in labels])
    candidates = []
    if sealed_root.is_dir():
        candidates = sorted(sealed_root.glob("*.json"))
    for path in candidates:
        try:
            sealed = path.read_bytes()
        except OSError:
            continue
        if sealed != submitted:
            continue
        try:
            record = json.loads(sealed.decode())
        except ValueError:
            continue
        if record.get("package_sha256") != v1.hash_bytes(task_bytes):
            continue
        if record.get("gold_sha256") != v1.hash_bytes(gold_bytes):
            continue
        boundary = record.get("human_boundary_confirmed") or {}
        if boundary.get("confirmed") is True and boundary.get("confirmer"):
            return True, f"sealed artifact {path.name} with confirmed boundary"
        return False, "sealed record lacks a human-confirmed boundary"
    return False, "no sealed custody artifact matches this evaluation"


def determine_custody_state(structural, sealed_ok, scope):
    """Machine-enforced custody state. Manifest strings are never consulted."""
    if not structural.get("custody_valid"):
        return CUSTODY_NOT_ESTABLISHED, structural.get("reason", "structural checks failed")
    if scope.get("scope") == "blind" and structural.get("gold_adjudicated") and sealed_ok[0]:
        return QUALIFIED, f"independently authenticated: {sealed_ok[1]}"
    if scope.get("scope") == "blind" and structural.get("gold_adjudicated"):
        return (
            IMPLEMENTED_UNQUALIFIED,
            "structurally valid but no independently authenticated custody; "
            f"sealed check: {sealed_ok[1]}",
        )
    return (
        IMPLEMENTED_UNQUALIFIED,
        f"diagnostic posture: scope={scope.get('scope')}; {sealed_ok[1]}",
    )


def require_consistent_counts(metrics, required_arms):
    """Counts must agree across compared arms; disagreement rejects the package."""
    counts = {}
    for arm in required_arms:
        if arm not in metrics:
            continue
        counts[arm] = (
            metrics[arm].get("useful_findings", 0),
            metrics[arm].get("scored_tasks", 0),
        )
    if len(set(counts.values())) > 1:
        raise ValueError(f"inconsistent arm counts across comparators: {counts}")
    arm = next((a for a in ("D", "C", "S", "V") if a in counts), next(iter(counts), None))
    if arm is None:
        raise ValueError("no comparator arms with counts present")
    return {"useful": counts[arm][0], "scored": counts[arm][1]}


def cross_family_duplicates(tasks):
    """Identical normalized source text in two families destroys independence."""
    seen = {}
    for task in tasks:
        for source in task.sources:
            text = " ".join(str(source.text).split())
            if not text:
                continue
            owners = seen.setdefault(text, set())
            owners.add(task.family)
    return sorted(
        {text for text, owners in seen.items() if len(owners) > 1},
        key=len,
    )[:5]


def paired_interval(flags, tasks, contract, arm_a, arm_b, metric, seed):
    """Paired family bootstrap for one arm pair and metric (pinned seed)."""
    import random

    families = sorted({t.family for t in tasks})
    members = {}
    for t in tasks:
        members.setdefault(t.family, []).append(t.id)
    by_id_flags = flags
    rng = random.Random(seed)
    level = contract["ci_level"]
    alpha = 1.0 - level
    diffs = []
    for _ in range(contract["bootstrap_resamples"]):
        chosen = [rng.choice(families) for _ in families]
        ids = [i for f in chosen for i in members[f]]
        acc = {}
        for arm in (arm_a, arm_b):
            vals = [by_id_flags[arm][i] for i in ids if by_id_flags[arm].get(i) is not None]
            if metric == "retention":
                useful = [v for v in vals if v["useful"]]
                acc[arm] = sum(v["retained"] for v in useful) / len(useful) if useful else 0.0
            else:
                acc[arm] = sum(v["misleading"] for v in vals) / len(vals) if vals else 0.0
        diffs.append(acc[arm_a] - acc[arm_b])
    ordered = sorted(diffs)
    lo = ordered[max(0, int((alpha / 2) * len(ordered)))]
    hi = ordered[min(len(ordered) - 1, int((1 - alpha / 2) * len(ordered)))]
    return [lo, hi]


def decide_v2(tasks, metrics, intervals, flags, scope, policy, contract, pinned, duplicates):
    """Corrected decision: absolute, paired, and V-gate evidence classified.

    Returns (outcome, reasons, underpowered, diagnostics) with outcome in
    {improvement_supported, no_improvement_demonstrated, indeterminate}.
    The caller maps outcome + custody mode to verdict/diagnostic_result.
    """
    reasons = []
    diagnostics = {"comparator_diagnostics": None, "paired": {}}
    if scope["scope"] != "blind":
        return (
            "indeterminate",
            [f"scope is {scope['scope']}: {scope['reason']}"],
            False,
            diagnostics,
        )
    missing = [a for a in policy["required_arms"] if a not in metrics]
    if missing:
        return (
            "indeterminate",
            [f"missing required comparator outputs: {missing}"],
            False,
            diagnostics,
        )
    if len(tasks) < policy["min_holdout_cases"]:
        return (
            "indeterminate",
            [f"only {len(tasks)} holdout cases, need >={policy['min_holdout_cases']}"],
            True,
            diagnostics,
        )
    counts = require_consistent_counts(metrics, policy["required_arms"])
    underpowered = False
    if intervals["families"] < policy["min_independent_families"]:
        underpowered = True
        reasons.append(f"only {intervals['families']} independent families")
    if counts["useful"] < policy["min_useful_cases"]:
        underpowered = True
        reasons.append(f"only {counts['useful']} useful cases")
    if counts["scored"] < policy["min_scored_cases"]:
        underpowered = True
        reasons.append(f"only {counts['scored']} scored cases")
    if underpowered:
        return "indeterminate", reasons, True, diagnostics
    if duplicates:
        return (
            "indeterminate",
            ["cross-family duplicate content undermines family independence"],
            False,
            diagnostics,
        )
    ret_floor = contract["min_useful_retention"]
    mis_cap = contract["max_misleading_advance_rate"]
    failed, undetermined = [], []

    arm_d, arm_c = metrics["D"], metrics.get("C", {})
    iv_d = intervals["arms"].get("D", {})
    gate_checks = [
        (
            "D retention gate",
            arm_d["gated_useful_finding_retention"] >= ret_floor,
            iv_d.get("retention", [0, 0]),
            ret_floor,
            None,
        ),
        (
            "D misleading gate",
            arm_d["gated_misleading_advance_rate"] <= mis_cap,
            iv_d.get("misleading", [1, 1]),
            None,
            mis_cap,
        ),
    ]
    for name, value_ok, interval, floor, cap in gate_checks:
        lo, hi = interval
        if floor is not None:
            status = "pass" if (value_ok and lo >= floor) else ("fail" if hi < floor else "indet")
        else:
            status = "pass" if (value_ok and hi <= cap) else ("fail" if lo > cap else "indet")
        if status == "fail":
            failed.append(name)
        elif status == "indet":
            undetermined.append(f"{name} cannot distinguish")
    if (arm_d.get("citation_gate") or {}).get("pass_rate", 0) != 1.0:
        failed.append("D citation gate")
    c_iv = intervals["arms"].get("C", {})
    comparator_diagnostics = {
        "C_absolute": {
            "retention_point": arm_c.get("gated_useful_finding_retention"),
            "retention_interval": c_iv.get("retention"),
            "misleading_point": arm_c.get("gated_misleading_advance_rate"),
            "misleading_interval": c_iv.get("misleading"),
            "vetoes_D": False,
        }
    }

    def classify_paired(iv, margin=None, tolerance=None):
        lo, hi = iv
        if margin is not None:
            if lo >= margin:
                return "pass"
            if hi < margin:
                return "fail"
            return "indeterminate"
        if hi <= tolerance:
            return "pass"
        if lo > tolerance:
            return "fail"
        return "indeterminate"

    seed = pinned["bootstrap_seed"]
    pairs = {}
    for key, margin, tolerance in (
        ("D-S_retention", contract["margin_over_surface_retention"], None),
        ("D-S_misleading", None, contract["tolerance_over_surface_misleading"]),
        ("D-C_retention", contract["margin_over_general_retention"], None),
        ("D-C_misleading", None, contract["tolerance_over_general_misleading"]),
    ):
        iv = intervals["paired_differences"].get(key)
        if not iv:
            undetermined.append(f"paired interval {key} unavailable")
            continue
        result = classify_paired(iv, margin=margin, tolerance=tolerance)
        pairs[key] = {"interval": iv, "result": result}
        if result == "fail":
            failed.append(f"paired {key} {iv} demonstrates no advantage")
        elif result == "indeterminate":
            undetermined.append(f"paired {key} {iv} cannot distinguish advantage")
    dv_ret = paired_interval(flags, tasks, contract, "D", "V", "retention", seed)
    dv_mis = paired_interval(flags, tasks, contract, "D", "V", "misleading", seed)
    pairs["D-V_retention"] = {"interval": dv_ret, "result": None}
    pairs["D-V_misleading"] = {"interval": dv_mis, "result": None}
    if "V" not in metrics:
        undetermined.append("V comparator outputs unavailable")
    else:
        v_ok = dv_ret[0] >= 0 and dv_mis[1] <= 0
        v_bad = dv_ret[1] < 0 or dv_mis[0] > 0
        pairs["D-V_retention"]["result"] = (
            "pass" if dv_ret[0] >= 0 else ("fail" if dv_ret[1] < 0 else "indeterminate")
        )
        pairs["D-V_misleading"]["result"] = (
            "pass" if dv_mis[1] <= 0 else ("fail" if dv_mis[0] > 0 else "indeterminate")
        )
        if v_bad:
            failed.append(f"D loses to evaluation-informed V control {dv_ret} {dv_mis}")
        elif not v_ok:
            undetermined.append(f"D vs V inconclusive {dv_ret} {dv_mis}")
    diagnostics["comparator_diagnostics"] = comparator_diagnostics
    diagnostics["paired"] = pairs
    if failed:
        return "no_improvement_demonstrated", failed + undetermined, False, diagnostics
    if undetermined:
        return "indeterminate", undetermined, False, diagnostics
    return (
        "improvement_supported",
        ["D absolute, paired, and V non-inferiority gates all clear"],
        False,
        diagnostics,
    )


def evaluate_v2(request, paths, trust_anchors_path=None, pinned_path=None, sealed_root=None):
    """Run the v2 custodian pipeline. Returns a qualification-aware receipt."""
    trust_anchors_path = trust_anchors_path or TRUST_ANCHORS_PATH
    pinned_path = pinned_path or PINNED_BOOTSTRAP_PATH
    sealed_root = sealed_root or SEALED_ROOT
    anchors = load_trust_anchors(trust_anchors_path)
    pinned = load_pinned_bootstrap(pinned_path)
    policy = v1.load_custodian_policy(paths["policy_path"])
    v1.strict_json_loads(Path(paths["contract_path"]).read_text(encoding="utf-8"))
    contract = v1.validate_decision_contract_strict(
        v1.load_threshold_contract(paths["contract_path"])
    )
    for key in ("bootstrap_seed", "bootstrap_resamples", "ci_level"):
        if contract[key] != pinned[key]:
            raise ValueError(
                f"contract {key}={contract[key]} does not match evaluator-pinned "
                f"{pinned[key]}; randomness is not caller-tunable"
            )
    tasks = v1.load_package_tasks(paths["package_dir"])
    labels = v1.load_package_gold(paths["gold_dir"])
    origins = (
        v1.strict_json_load(Path(paths["gold_dir"]) / "origins.json")
        if (Path(paths["gold_dir"]) / "origins.json").exists()
        else v1.strict_json_load(Path(paths["package_dir"]) / "origins.json")
    )
    validate_corpus_r2(tasks, labels, origins, public=False)
    raw_outputs = v1.strict_json_load(paths["outputs_path"])
    if not isinstance(raw_outputs, dict) or "outcomes" not in raw_outputs:
        raise ValueError("outputs must be an object with an outcomes map")
    normalized = v1.verify_binding(tasks, labels, raw_outputs["outcomes"])
    fingerprints_v1 = v1.verify_fingerprints(
        request["protocol_dir"],
        request["claimed_protocol_sha256"],
        request["claimed_scorer_version"],
        request["claimed_scorer_sha256"],
        policy,
    )
    custody = v1.validate_custody(paths.get("custody_dir"), tasks, labels, request.get("submitter"))
    sealed = check_sealed_custody(paths.get("custody_dir"), tasks, labels, sealed_root)
    scope = v1.determine_scope(
        tasks, {**custody, "requested_scope": request.get("requested_scope")}
    )
    custody_state, custody_reason = determine_custody_state(custody, sealed, scope)
    metrics = {}
    for arm, outs in normalized.items():
        metrics[arm] = score_r2(tasks, labels, outs, arm, contract, allow_offline_fixtures=True)
    flags = v1.gated_flags(tasks, labels, normalized, contract)
    intervals = v1.family_intervals(tasks, flags, contract)
    duplicates = cross_family_duplicates(tasks)
    outcome, outcome_reasons, underpowered, decision_diagnostics = decide_v2(
        tasks, metrics, intervals, flags, scope, policy, contract, pinned, duplicates
    )
    mode = "qualified" if custody_state == QUALIFIED else "diagnostic"
    if mode == "qualified" and outcome == "improvement_supported" and scope["scope"] == "blind":
        verdict = "PROGRESS"
    elif outcome == "no_improvement_demonstrated":
        verdict = "NO_PROGRESS"
    else:
        verdict = "INCONCLUSIVE"
    diagnostic_result = {
        "improvement_supported": "IMPROVEMENT_OBSERVED",
        "no_improvement_demonstrated": "NO_IMPROVEMENT_OBSERVED",
        "indeterminate": "INDETERMINATE",
    }[outcome]
    commit = source_commit()
    task_bytes = canonical([t.model_dump() for t in tasks])
    gold_bytes = canonical([a.model_dump() for a in labels])
    outputs_bytes = canonical(
        {arm: [o.model_dump() for o in outs] for arm, outs in normalized.items()}
    )
    contract_bytes = canonical(contract)
    policy_bytes = canonical(policy)
    package_identity = fingerprint(
        {
            "tasks": hashlib.sha256(task_bytes).hexdigest(),
            "gold": hashlib.sha256(gold_bytes).hexdigest(),
            "outputs": hashlib.sha256(outputs_bytes).hexdigest(),
            "contract": hashlib.sha256(contract_bytes).hexdigest(),
            "policy": hashlib.sha256(policy_bytes).hexdigest(),
            "protocol_version": fingerprints_v1["protocol_version"],
            "scorer_version": fingerprints_v1["scorer_version"],
            "evaluator": EVAL02_VERSION,
        }
    )
    receipt = {
        "evaluator": EVAL02_VERSION,
        "custody_state": custody_state,
        "custody_reason": custody_reason,
        "evaluation_mode": mode,
        "verdict": verdict,
        "diagnostic_result": diagnostic_result,
        "scientific_qualification": "ESTABLISHED"
        if (verdict == "PROGRESS" and custody_state == QUALIFIED)
        else "NOT_ESTABLISHED",
        "entailment": "requires_human_adjudication",
        "scope_determined": scope,
        "custody": {k: v for k, v in custody.items()},
        "sealed_match": {"matched": sealed[0], "detail": sealed[1]},
        "fingerprints": {
            "tasks_sha256": hashlib.sha256(task_bytes).hexdigest(),
            "gold_sha256": hashlib.sha256(gold_bytes).hexdigest(),
            "outputs_sha256": hashlib.sha256(outputs_bytes).hexdigest(),
            "contract_sha256": hashlib.sha256(contract_bytes).hexdigest(),
            "policy_sha256": hashlib.sha256(policy_bytes).hexdigest(),
            "protocol_sha256": fingerprints_v1["protocol_sha256"],
            "protocol_version": fingerprints_v1["protocol_version"],
            "scorer_version": fingerprints_v1["scorer_version"],
            "scorer_sha256": fingerprints_v1["scorer_sha256"],
            "package_identity": package_identity,
            "source_commit": commit,
            "source_commit_available": commit is not None,
            "evaluator_version": EVAL02_VERSION,
            "trust_anchors_sha256": fingerprint(anchors),
            "pinned_bootstrap_sha256": fingerprint(pinned),
            "bootstrap_seed_source": "evaluator_pinned",
            "bootstrap_seed_claimed": contract["bootstrap_seed"],
            "execution_provenance": "offline_fixture_unprovenanced",
        },
        "metrics": metrics,
        "uncertainty": intervals,
        "paired_v_gate": "computed in decide_v2; see reasons",
        "underpowered": underpowered,
        "reasons": outcome_reasons,
        "decision_diagnostics": decision_diagnostics,
        "submitted_summary_echo": request.get("submitted_summary"),
        "summary_authoritative": False,
        "policy_version": policy.get("version"),
    }
    if paths.get("output_path"):
        out = Path(paths["output_path"])
        if out.exists():
            raise ValueError("refusing to overwrite existing receipt; choose a new path")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return receipt


def verify_receipt(
    receipt, request, paths, trust_anchors_path=None, pinned_path=None, sealed_root=None
):
    """Recompute input fingerprints and reject tampering, substitution, replay."""
    if receipt.get("evaluator") != EVAL02_VERSION:
        raise ValueError("not a v2 receipt; historical receipts never qualify")
    for key in (
        "fingerprints",
        "custody_state",
        "evaluation_mode",
        "verdict",
        "scientific_qualification",
    ):
        if key not in receipt:
            raise ValueError(f"receipt missing required field: {key}")
    recomputed = evaluate_v2(
        {**request, "submitted_summary": receipt.get("submitted_summary_echo")},
        {**paths, "output_path": None},
        trust_anchors_path=trust_anchors_path,
        pinned_path=pinned_path,
        sealed_root=sealed_root,
    )
    for key in (
        "tasks_sha256",
        "gold_sha256",
        "outputs_sha256",
        "contract_sha256",
        "policy_sha256",
        "protocol_sha256",
        "scorer_sha256",
    ):
        if receipt["fingerprints"].get(key) != recomputed["fingerprints"][key]:
            raise ValueError(f"receipt input fingerprint mismatch: {key}")
    if (
        receipt["fingerprints"].get("package_identity")
        != recomputed["fingerprints"]["package_identity"]
    ):
        raise ValueError("receipt package identity mismatch: cross-package replay rejected")
    for key in (
        "custody_state",
        "evaluation_mode",
        "verdict",
        "diagnostic_result",
        "scientific_qualification",
    ):
        if receipt.get(key) != recomputed.get(key):
            raise ValueError(f"receipt field mismatch after recomputation: {key}")
    if receipt["custody_state"] == QUALIFIED:
        matched, _ = check_sealed_custody(
            paths.get("custody_dir"),
            v1.load_package_tasks(paths["package_dir"]),
            v1.load_package_gold(paths["gold_dir"]),
            sealed_root or SEALED_ROOT,
        )
        if not matched:
            raise ValueError("QUALIFIED receipt has no matching sealed artifact")
    return True


def is_qualified_progress(receipt):
    """Strict gate for consumers: only an authenticated QUALIFIED PROGRESS counts."""
    try:
        return bool(
            receipt.get("evaluator") == EVAL02_VERSION
            and receipt.get("custody_state") == QUALIFIED
            and receipt.get("evaluation_mode") == "qualified"
            and receipt.get("verdict") == "PROGRESS"
            and receipt.get("scope_determined", {}).get("scope") == "blind"
            and receipt.get("scientific_qualification") == "ESTABLISHED"
        )
    except AttributeError:
        return False
