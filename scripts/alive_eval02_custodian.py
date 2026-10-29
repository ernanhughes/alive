"""Independent-custody evaluation gate (ALIVE-EVAL-02 R2). Offline, no model calls.

R1 review demonstrated that caller-controlled trust-root overrides
(--sealed-root and friends) let a submitter manufacture QUALIFIED / PROGRESS /
ESTABLISHED without touching application code. R2 closes that boundary:

- Trust roots are evaluator-pinned constants. No CLI flag, request field, or
  function parameter can redirect them; tests reach alternatives only by
  monkeypatching module constants (in-process only, never a trust boundary).
- QUALIFIED additionally requires: custodian identity in the active,
  unrevoked, unexpired administrator-controlled registry; a sealed record with
  a detached signature whose signed payload binds the exact package identity;
  canonical (repo-pinned) policy and contract; governed execution provenance;
  verified deterministic controls; and signature-math verification. The math
  backend does not exist yet, so QUALIFIED is unreachable by construction.
- `verify_receipt` returns a `VerifiedReceipt` object. `is_qualified_progress`
  accepts only that type, so hand-typed dictionaries can never authenticate.
- Diagnostic evaluation is unchanged in honesty: improvement is measured and
  reported, but never qualified.

v1 (`alive_eval01_custodian`) is preserved byte-unchanged as the historical
implementation; v2 is the authoritative entry point for new attempts.
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
REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_POLICY_PATH = REPO_ROOT / "evaluations" / "alive-eval-01" / "custodian_policy.json"
CANONICAL_CONTRACT_PATH = REPO_ROOT / "evaluations" / "notebook03a_r2" / "decision_thresholds.json"

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
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
        sha = out.stdout.strip()
        return sha if len(sha) == 40 and all(c in "0123456789abcdef" for c in sha) else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def load_trust_anchors(path=None):
    """Load the administrator-controlled trust registry (evaluator-pinned path).

    Entries beyond the legacy string list carry key identity, algorithm,
    status and expiry. No caller-supplied path is ever consulted. The default
    resolves at call time so tests may monkeypatch the module constant.
    """
    raw = v1.strict_json_load(path or TRUST_ANCHORS_PATH)
    if not isinstance(raw, dict):
        raise ValueError("trust anchors must be a JSON object")
    simple = raw.get("independent_custodians", [])
    if not isinstance(simple, list) or any(not isinstance(c, str) for c in simple):
        raise ValueError("independent_custodians must be a list of strings")
    detailed = raw.get("custodians", {})
    if not isinstance(detailed, dict):
        raise ValueError("custodians must be an object")
    entries = {}
    for name in sorted(set(simple)):
        entries[name] = {
            "key_fingerprint": None,
            "algorithm": None,
            "status": "active",
            "expires": None,
        }
    for name, entry in detailed.items():
        if not isinstance(entry, dict):
            raise ValueError(f"custodian entry {name} must be an object")
        entries[name] = {
            "key_fingerprint": entry.get("key_fingerprint"),
            "algorithm": entry.get("algorithm"),
            "status": entry.get("status", "active"),
            "expires": entry.get("expires"),
        }
    return {"version": raw.get("version"), "custodians": entries}


def load_pinned_bootstrap(path=None):
    path = path or PINNED_BOOTSTRAP_PATH
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


def _dumped(obj):
    return obj.model_dump() if hasattr(obj, "model_dump") else obj


def assess_sealed_custody(custody_dir, tasks, labels):
    """Assess the sealed custody record against evaluator-pinned roots.

    Every root is a module constant pointing inside this repository; there is
    no parameter, flag, or request field that redirects them. Returns a detail
    dict; ``qualified_ready`` is True only when every independently checkable
    condition holds (signature math is verified by ``signature_math_ok``,
    which fail-closes until a verification backend exists).
    """
    detail = {
        "record_present": False,
        "record_sealed": False,
        "hashes_bind": False,
        "boundary_confirmed": False,
        "custodian_authorized": False,
        "signature_present": False,
        "signature_binds_package": False,
        "signature_math_ok": False,
        "signature_detail": "signature verification backend unavailable",
        "canonical_policy_match": False,
        "canonical_contract_match": False,
        "qualified_ready": False,
    }
    if custody_dir is None:
        detail["signature_detail"] = "no custody directory supplied"
        return detail
    try:
        submitted = (Path(custody_dir) / "custody.json").read_bytes()
    except OSError as exc:
        detail["signature_detail"] = f"unreadable custody record: {exc}"
        return detail
    detail["record_present"] = True
    try:
        record = json.loads(submitted.decode())
    except ValueError:
        return detail
    task_bytes = canonical([_dumped(t) for t in tasks])
    gold_bytes = canonical([_dumped(a) for a in labels])
    sealed_file = SEALED_ROOT / "custody.json"
    try:
        sealed = sealed_file.read_bytes()
    except OSError:
        return detail
    if sealed != submitted:
        return detail
    detail["record_sealed"] = True
    if record.get("package_sha256") != v1.hash_bytes(task_bytes):
        return detail
    if record.get("gold_sha256") != v1.hash_bytes(gold_bytes):
        return detail
    detail["hashes_bind"] = True
    boundary = record.get("human_boundary_confirmed") or {}
    if not (boundary.get("confirmed") is True and boundary.get("confirmer")):
        return detail
    detail["boundary_confirmed"] = True
    anchors = load_trust_anchors()
    entry = anchors["custodians"].get(record.get("custodian") or "")
    if entry is None or entry.get("status") != "active":
        detail["signature_detail"] = "custodian not in active trust registry"
        return detail
    if entry.get("expires") is not None:
        detail["signature_detail"] = "custodian entry has an expiry; expiry enforcement pending"
        return detail
    detail["custodian_authorized"] = True
    sig_file = SEALED_ROOT / "custody.json.sig"
    try:
        sig_blob = json.loads(sig_file.read_bytes().decode())
    except (OSError, ValueError):
        detail["signature_detail"] = "missing or unreadable detached signature"
        return detail
    detail["signature_present"] = True
    package_identity = fingerprint(
        {
            "tasks": hashlib.sha256(task_bytes).hexdigest(),
            "gold": hashlib.sha256(gold_bytes).hexdigest(),
        }
    )
    if sig_blob.get("custodian") != record.get("custodian"):
        detail["signature_detail"] = "signature custodian mismatch"
        return detail
    if sig_blob.get("signed_package_identity") != package_identity:
        detail["signature_detail"] = "signature does not bind this package (replay rejected)"
        return detail
    detail["signature_binds_package"] = True
    # Signature math has no verification backend in the standard library and no
    # new dependency is authorized for this change: fail closed, explicitly.
    return detail


def determine_custody_state(structural, sealed, scope, canonical_match, execution_ok):
    """Machine-enforced custody state. Manifest strings are never consulted."""
    if not structural.get("custody_valid"):
        return CUSTODY_NOT_ESTABLISHED, structural.get("reason", "structural checks failed")
    if (
        scope.get("scope") == "blind"
        and structural.get("gold_adjudicated")
        and sealed.get("qualified_ready")
        and canonical_match
        and execution_ok
    ):
        return QUALIFIED, "independently authenticated custody verified"
    reasons = []
    if scope.get("scope") != "blind":
        reasons.append(f"scope={scope.get('scope')}")
    if not structural.get("gold_adjudicated"):
        reasons.append("gold not adjudicated")
    if not sealed.get("qualified_ready"):
        reasons.append(f"sealed: {sealed.get('signature_detail')}")
    if not canonical_match:
        reasons.append("policy/contract differ from repo-pinned canonical inputs")
    if not execution_ok:
        reasons.append("no governed execution provenance")
    if not reasons:
        reasons.append("independent authentication unavailable")
    return IMPLEMENTED_UNQUALIFIED, "structurally valid but unqualified: " + "; ".join(reasons)


def require_applicable_counts(metrics, required_arms):
    """Counts are per-arm from the candidate outward; no cross-arm equalization.

    Eligibility floors apply to the candidate arm D. Comparator arms report
    their own counts; paired comparisons additionally gate on overlap.
    """
    if "D" not in metrics:
        raise ValueError("candidate arm D outputs missing")
    return {
        "useful": metrics["D"].get("useful_findings", 0),
        "scored": metrics["D"].get("scored_tasks", 0),
    }


def overlap_scored(flags, arm_a, arm_b):
    """Tasks scored under both arms (paired-comparison eligible)."""
    ids_a = {i for i, v in flags.get(arm_a, {}).items() if v is not None}
    ids_b = {i for i, v in flags.get(arm_b, {}).items() if v is not None}
    return len(ids_a & ids_b)


def cross_family_duplicates(tasks):
    """Identical normalized source text in two families destroys independence."""
    seen = {}
    for task in tasks:
        for source in task.sources:
            text = " ".join(str(source.text).split()).casefold()
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
    rng = random.Random(seed)
    level = contract["ci_level"]
    alpha = 1.0 - level
    diffs = []
    for _ in range(contract["bootstrap_resamples"]):
        chosen = [rng.choice(families) for _ in families]
        ids = [i for f in chosen for i in members[f]]
        acc = {}
        for arm in (arm_a, arm_b):
            vals = [flags[arm][i] for i in ids if flags[arm].get(i) is not None]
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


def decide_v2(
    tasks, metrics, intervals, flags, normalized, scope, policy, contract, pinned, duplicates
):
    """Corrected decision: absolute, paired, and V-gate evidence classified.

    Returns (outcome, reasons, underpowered, diagnostics) with outcome in
    {improvement_supported, no_improvement_demonstrated, indeterminate}.
    """
    reasons = []
    diagnostics = {"comparator_diagnostics": None, "paired": {}, "overlap": {}}
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
    counts = require_applicable_counts(metrics, policy["required_arms"])
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

    arm_d = metrics["D"]
    iv_d = intervals["arms"].get("D", {})

    def classify_absolute(value_ok, interval, floor=None, cap=None):
        lo, hi = interval
        if floor is not None:
            if value_ok and lo >= floor:
                return "pass"
            if not value_ok and hi < floor:
                return "fail"
            return "indeterminate"
        if value_ok and hi <= cap:
            return "pass"
        if not value_ok and lo > cap:
            return "fail"
        return "indeterminate"

    ret_status = classify_absolute(
        arm_d["gated_useful_finding_retention"] >= ret_floor,
        iv_d.get("retention", [0, 0]),
        floor=ret_floor,
    )
    mis_status = classify_absolute(
        arm_d["gated_misleading_advance_rate"] <= mis_cap,
        iv_d.get("misleading", [1, 1]),
        cap=mis_cap,
    )
    if ret_status == "fail":
        failed.append("D retention gate (point and interval below floor)")
    elif ret_status == "indeterminate":
        undetermined.append("D retention gate cannot distinguish")
    if mis_status == "fail":
        failed.append("D misleading gate (point and interval above cap)")
    elif mis_status == "indeterminate":
        undetermined.append("D misleading gate cannot distinguish")
    if (arm_d.get("citation_gate") or {}).get("pass_rate", 0) != 1.0:
        failed.append("D citation gate")
    arm_c = metrics.get("C", {})
    c_iv = intervals["arms"].get("C", {})
    diagnostics["comparator_diagnostics"] = {
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
    for key, arm_b, margin, tolerance in (
        ("D-S_retention", "S", contract["margin_over_surface_retention"], None),
        ("D-S_misleading", "S", None, contract["tolerance_over_surface_misleading"]),
        ("D-C_retention", "C", contract["margin_over_general_retention"], None),
        ("D-C_misleading", "C", None, contract["tolerance_over_general_misleading"]),
    ):
        iv = intervals["paired_differences"].get(key)
        if not iv:
            undetermined.append(f"paired interval {key} unavailable")
            continue
        overlap = overlap_scored(flags, "D", arm_b)
        diagnostics["overlap"][key] = overlap
        if overlap < policy["min_scored_cases"]:
            undetermined.append(f"paired {key} has only {overlap} overlapping scored cases")
            pairs[key] = {"interval": iv, "result": "indeterminate", "overlap": overlap}
            continue
        result = classify_paired(iv, margin=margin, tolerance=tolerance)
        pairs[key] = {"interval": iv, "result": result, "overlap": overlap}
        if result == "fail":
            failed.append(f"paired {key} {iv} demonstrates no advantage")
        elif result == "indeterminate":
            undetermined.append(f"paired {key} {iv} cannot distinguish advantage")
    dv_ret = paired_interval(flags, tasks, contract, "D", "V", "retention", seed)
    dv_mis = paired_interval(flags, tasks, contract, "D", "V", "misleading", seed)
    dv_overlap = overlap_scored(flags, "D", "V")
    if "V" not in metrics:
        undetermined.append("V comparator outputs unavailable")
        pairs["D-V_retention"] = {
            "interval": dv_ret,
            "result": "indeterminate",
            "overlap": dv_overlap,
        }
        pairs["D-V_misleading"] = {
            "interval": dv_mis,
            "result": "indeterminate",
            "overlap": dv_overlap,
        }
    elif dv_overlap < policy["min_scored_cases"]:
        undetermined.append(f"D-V has only {dv_overlap} overlapping scored cases")
        pairs["D-V_retention"] = {
            "interval": dv_ret,
            "result": "indeterminate",
            "overlap": dv_overlap,
        }
        pairs["D-V_misleading"] = {
            "interval": dv_mis,
            "result": "indeterminate",
            "overlap": dv_overlap,
        }
    else:
        v_ok = dv_ret[0] >= 0 and dv_mis[1] <= 0
        v_bad = dv_ret[1] < 0 or dv_mis[0] > 0
        pairs["D-V_retention"] = {
            "interval": dv_ret,
            "result": "pass" if dv_ret[0] >= 0 else ("fail" if dv_ret[1] < 0 else "indeterminate"),
            "overlap": dv_overlap,
        }
        pairs["D-V_misleading"] = {
            "interval": dv_mis,
            "result": "pass" if dv_mis[1] <= 0 else ("fail" if dv_mis[0] > 0 else "indeterminate"),
            "overlap": dv_overlap,
        }
        if v_bad:
            failed.append(f"D loses to evaluation-informed V control {dv_ret} {dv_mis}")
        elif not v_ok:
            undetermined.append(f"D vs V inconclusive {dv_ret} {dv_mis}")
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


def evaluate_v2(request, paths):
    """Run the v2 custodian pipeline. Trust roots are evaluator-pinned constants.

    No parameter, flag, or request field redirects the trust roots; tests reach
    alternatives only by monkeypatching module constants in-process.
    """
    anchors = load_trust_anchors()
    pinned = load_pinned_bootstrap()
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
    sealed = assess_sealed_custody(paths.get("custody_dir"), tasks, labels)
    scope = v1.determine_scope(
        tasks, {**custody, "requested_scope": request.get("requested_scope")}
    )
    canonical_policy = v1.strict_json_load(CANONICAL_POLICY_PATH)
    canonical_contract = v1.strict_json_load(CANONICAL_CONTRACT_PATH)
    supplied_policy = v1.strict_json_load(paths["policy_path"])
    supplied_contract = v1.strict_json_load(paths["contract_path"])
    policy_match = canonical(supplied_policy) == canonical(canonical_policy)
    contract_match = canonical(supplied_contract) == canonical(canonical_contract)
    canonical_match = policy_match and contract_match
    execution_ok = False
    metrics = {}
    for arm, outs in normalized.items():
        metrics[arm] = score_r2(tasks, labels, outs, arm, contract, allow_offline_fixtures=True)
    flags = v1.gated_flags(tasks, labels, normalized, contract)
    intervals = v1.family_intervals(tasks, flags, contract)
    duplicates = cross_family_duplicates(tasks)
    custody_state, custody_reason = determine_custody_state(
        custody, sealed, scope, canonical_match, execution_ok
    )
    outcome, outcome_reasons, underpowered, decision_diagnostics = decide_v2(
        tasks, metrics, intervals, flags, normalized, scope, policy, contract, pinned, duplicates
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
        "sealed_assessment": sealed,
        "trust_anchors_sha256": fingerprint(anchors),
        "canonical_policy_match": policy_match,
        "canonical_contract_match": contract_match,
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
            "pinned_bootstrap_sha256": fingerprint(pinned),
            "bootstrap_seed_source": "evaluator_pinned",
            "bootstrap_seed_claimed": contract["bootstrap_seed"],
            "execution_provenance": "offline_fixture_unprovenanced",
            "governed_execution": False,
            "controls_verified": False,
        },
        "metrics": metrics,
        "uncertainty": intervals,
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


class VerifiedReceipt:
    """A receipt that passed full re-verification against bound artifacts.

    Only this type satisfies `is_qualified_progress`. Plain dictionaries,
    however carefully typed, never authenticate.
    """

    __slots__ = ("receipt", "package_identity", "custody_state", "verified_fields")

    def __init__(self, receipt, package_identity, custody_state, verified_fields):
        self.receipt = receipt
        self.package_identity = package_identity
        self.custody_state = custody_state
        self.verified_fields = verified_fields


def verify_receipt(receipt, request, paths):
    """Recompute input fingerprints and reject tampering, substitution, replay.

    Returns a VerifiedReceipt; raises ValueError on any mismatch. QUALIFIED
    receipts additionally require their sealed artifacts to verify now.
    """
    if not isinstance(receipt, dict) or receipt.get("evaluator") != EVAL02_VERSION:
        raise ValueError("not a v2 receipt; historical receipts never qualify")
    for key in (
        "fingerprints",
        "custody_state",
        "evaluation_mode",
        "verdict",
        "scientific_qualification",
        "diagnostic_result",
    ):
        if key not in receipt:
            raise ValueError(f"receipt missing required field: {key}")
    recomputed = evaluate_v2(
        {**request, "submitted_summary": receipt.get("submitted_summary_echo")},
        {**paths, "output_path": None},
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
        sealed = assess_sealed_custody(
            paths.get("custody_dir"),
            v1.load_package_tasks(paths["package_dir"]),
            v1.load_package_gold(paths["gold_dir"]),
        )
        if not sealed.get("qualified_ready"):
            raise ValueError("QUALIFIED receipt has no verifying sealed artifacts now")
    return VerifiedReceipt(
        receipt=receipt,
        package_identity=receipt["fingerprints"]["package_identity"],
        custody_state=receipt["custody_state"],
        verified_fields=sorted(receipt["fingerprints"])
        + [
            "custody_state",
            "evaluation_mode",
            "verdict",
            "diagnostic_result",
            "scientific_qualification",
        ],
    )


def is_qualified_progress(maybe_receipt):
    """Strict consumer gate: only a verified QUALIFIED PROGRESS receipt counts."""
    if not isinstance(maybe_receipt, VerifiedReceipt):
        return False
    receipt = maybe_receipt.receipt
    try:
        return bool(
            receipt.get("custody_state") == QUALIFIED
            and receipt.get("evaluation_mode") == "qualified"
            and receipt.get("verdict") == "PROGRESS"
            and receipt.get("scope_determined", {}).get("scope") == "blind"
            and receipt.get("scientific_qualification") == "ESTABLISHED"
            and maybe_receipt.custody_state == QUALIFIED
        )
    except AttributeError:
        return False
