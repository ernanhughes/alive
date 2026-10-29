"""Trusted custodian evaluator core (ALIVE-EVAL-01). Offline, no model calls.

The implementer submits per-case output records. The custodian recomputes
everything from those records against custodian-controlled tasks and gold.
Caller-supplied aggregates, scopes, and attestations are never authoritative.
"""

import hashlib
import json
import re
from pathlib import Path

from scripts.notebook03a_protocol import ROOT, Annotation, Task
from scripts.notebook03a_r2_protocol import (
    OutcomeR2,
    citation_gate,
    load_threshold_contract,
    score_r2,
    validate_corpus_r2,
)

EVAL01_VERSION = "alive-eval-01-v1"
CUSTODIAN_POLICY_PATH = ROOT / "evaluations/alive-eval-01/custodian_policy.json"


def strict_json_loads(text):
    """Reject NaN/Infinity constants that stock JSON accepts."""

    def reject(value):
        raise ValueError(f"non-finite JSON constant rejected: {value}")

    return json.loads(text, parse_constant=reject)


def strict_json_load(path):
    return strict_json_loads(Path(path).read_text(encoding="utf-8"))


POLICY_SPEC = {
    "min_holdout_cases": (int, 1, None),
    "required_arms": (list, None, None),
    "min_independent_families": (int, 1, None),
    "min_useful_cases": (int, 1, None),
    "min_scored_cases": (int, 1, None),
}


def load_custodian_policy(path=CUSTODIAN_POLICY_PATH):
    """Strictly validate the custodian policy. No defaults, no unknown keys."""
    raw = strict_json_load(path)
    if not isinstance(raw, dict):
        raise ValueError("custodian policy must be a JSON object")
    allowed = set(POLICY_SPEC) | {
        "version",
        "scope",
        "forbidden",
        "allowed_protocols",
        "allowed_scorers",
        "citation_policy",
        "uncertainty_policy",
        "units",
    }
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(f"unknown custodian policy keys rejected: {sorted(unknown)}")
    missing = [k for k in POLICY_SPEC if k not in raw]
    if missing:
        raise ValueError(f"missing custodian policy keys rejected: {missing}")
    policy = {}
    for key, (typ, lo, hi) in POLICY_SPEC.items():
        value = raw[key]
        if not isinstance(value, typ) or isinstance(value, bool):
            raise ValueError(f"custodian policy {key} must be {typ.__name__}")
        if lo is not None and value < lo:
            raise ValueError(f"custodian policy {key} below minimum")
        policy[key] = value
    if not policy["required_arms"]:
        raise ValueError("required_arms must be non-empty")
    for entry in raw.get("allowed_protocols", []):
        if not entry.get("version"):
            raise ValueError("allowed protocol entry needs a version")
    for entry in raw.get("allowed_scorers", []):
        if not entry.get("module"):
            raise ValueError("allowed scorer entry needs a module")
    policy["version"] = raw.get("version")
    policy["allowed_protocols"] = raw.get("allowed_protocols", [])
    policy["allowed_scorers"] = raw.get("allowed_scorers", [])
    policy["uncertainty_policy"] = raw.get("uncertainty_policy", {})
    return policy


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def load_package_tasks(package_dir):
    package_dir = Path(package_dir)
    tasks = [Task.model_validate(t) for t in strict_json_load(package_dir / "tasks.json")]
    return tasks


def load_package_gold(gold_dir):
    gold_dir = Path(gold_dir)
    labels = [Annotation.model_validate(a) for a in strict_json_load(gold_dir / "annotations.json")]
    return labels


def verify_binding(tasks, labels, outputs_by_arm):
    """Every output must bind exactly to the evaluated package.

    Rejects missing, duplicate, substituted, or extra outputs; claim-ref
    mismatches; non-exact citations; and source-content substitution
    (same task ID, changed source text) via per-source hash comparison.
    """
    by_id = {t.id: t for t in tasks}
    if len({t.id for t in tasks}) != len(tasks):
        raise ValueError("duplicate task identity in package")
    gold_ids = {a.task_id for a in labels}
    normalized = {}
    for arm, records in outputs_by_arm.items():
        seen = []
        arm_outs = []
        for rec in records:
            out = rec if isinstance(rec, OutcomeR2) else OutcomeR2.model_validate(rec)
            if out.arm != arm:
                raise ValueError(f"mixed-arm record in {arm} set")
            seen.append(out.task_id)
            arm_outs.append(out)
        if sorted(seen) != sorted(by_id):
            raise ValueError(
                f"{arm}: output task set does not match package "
                f"(missing={sorted(set(by_id) - set(seen))[:3]}, "
                f"extra={sorted(set(seen) - set(by_id))[:3]})"
            )
        for out in arm_outs:
            task = by_id[out.task_id]
            if set(out.claim_refs) != {c.id for c in task.claims} and out.action not in (
                "refuse",
                "not_applicable",
                "abstain",
            ):
                # abstain/refuse carry no claim burden; substantive actions must bind
                if out.relationship != "unknown":
                    raise ValueError(f"{arm}/{out.task_id}: claim binding mismatch")
            sources = {s.id: s for s in task.sources}
            for span in out.evidence:
                source = sources.get(span.source_id)
                if source is None or source.text[span.start : span.end] != span.text:
                    raise ValueError(f"{arm}/{out.task_id}: citation not exact at package offsets")
                if source.sha256 != hashlib.sha256(source.text.encode()).hexdigest():
                    raise ValueError(f"{arm}/{out.task_id}: source hash mismatch")
            for source in task.sources:
                if source.sha256 != hashlib.sha256(source.text.encode()).hexdigest():
                    raise ValueError(f"{arm}/{out.task_id}: package source hash mismatch")
        normalized[arm] = arm_outs
    if set(outputs_by_arm) - set(normalized):
        raise ValueError("unverifiable arm present")
    _ = gold_ids
    return normalized


def verify_fingerprints(
    protocol_dir, claimed_protocol_sha256, claimed_scorer_version, claimed_scorer_sha256, policy
):
    """Verify protocol freeze and scorer identity against custodian pins."""
    protocol_dir = Path(protocol_dir)
    protocol_text = (protocol_dir / "protocol.json").read_bytes()
    actual_protocol = hash_bytes(protocol_text)
    if claimed_protocol_sha256 != actual_protocol:
        raise ValueError("claimed protocol hash does not match the evaluated protocol")
    allowed_versions = {e["version"] for e in policy["allowed_protocols"]}
    protocol = json.loads(protocol_text.decode())
    if protocol.get("version") not in allowed_versions:
        raise ValueError("protocol version not in custodian allowlist")
    import scripts.notebook03a_r2_protocol as scorer

    actual_version = scorer.R2_VERSION
    if claimed_scorer_version != actual_version:
        raise ValueError("claimed scorer version does not match the executing scorer")
    actual_scorer = hash_bytes(Path(scorer.__file__).read_bytes())
    if claimed_scorer_sha256 != actual_scorer:
        raise ValueError("claimed scorer hash does not match the executing scorer")
    allowed_modules = {e["module"] for e in policy["allowed_scorers"]}
    if scorer.__name__ not in allowed_modules:
        raise ValueError("executing scorer module not in custodian allowlist")
    return {
        "protocol_sha256": actual_protocol,
        "protocol_version": protocol.get("version"),
        "scorer_version": actual_version,
        "scorer_sha256": actual_scorer,
    }


def determine_scope(tasks, custody):
    """Derive scope from package provenance, never from a caller flag.

    Blind scope requires every evaluated task to declare the sealed
    holdout split, a validated custody record, and adjudicated
    external gold. Anything else is public/diagnostic, regardless of
    what the caller requested.
    """
    requested = custody.get("requested_scope")
    if any(t.split != "independent_heldout" for t in tasks):
        return {
            "scope": "public_diagnostic",
            "requested": requested,
            "reason": "evaluated tasks are not all independent_heldout",
        }
    if not custody.get("custody_valid"):
        return {
            "scope": "public_diagnostic",
            "requested": requested,
            "reason": "no validated independent custody record",
        }
    if not custody.get("gold_adjudicated"):
        return {
            "scope": "public_diagnostic",
            "requested": requested,
            "reason": "gold labels are not adjudicated external_attested",
        }
    return {"scope": "blind", "requested": requested, "reason": "sealed package validated"}


def validate_custody(custody_dir, tasks, labels, submitter):
    """Validate the custody record structurally (not proof of independence).

    Requires: custody record present, package/gold hashes match, custodian
    identity distinct from the submitter, no exposure events, adjudicated
    external gold with distinct reviewers. Returns validity plus the facts
    a human reviewer must confirm for QUALIFIED custody.
    """
    if custody_dir is None:
        return {
            "custody_valid": False,
            "reason": "no custody directory supplied",
            "gold_adjudicated": False,
        }
    custody_dir = Path(custody_dir)
    try:
        record = strict_json_load(custody_dir / "custody.json")
    except (OSError, ValueError) as e:
        return {
            "custody_valid": False,
            "reason": f"unreadable custody record: {e}",
            "gold_adjudicated": False,
        }
    task_bytes = json.dumps([t.model_dump() for t in tasks], sort_keys=True).encode()
    gold_bytes = json.dumps([a.model_dump() for a in labels], sort_keys=True).encode()
    if record.get("package_sha256") != hash_bytes(task_bytes):
        return {
            "custody_valid": False,
            "reason": "custody package hash mismatch",
            "gold_adjudicated": False,
        }
    if record.get("gold_sha256") != hash_bytes(gold_bytes):
        return {
            "custody_valid": False,
            "reason": "custody gold hash mismatch",
            "gold_adjudicated": False,
        }
    if not record.get("custodian") or record["custodian"] == submitter:
        return {
            "custody_valid": False,
            "reason": "custodian identity missing or identical to submitter",
            "gold_adjudicated": False,
        }
    if record.get("exposure_events"):
        return {
            "custody_valid": False,
            "reason": "exposure events recorded",
            "gold_adjudicated": False,
        }
    adjudicated = (
        record.get("independent_annotation_status") == "ADJUDICATED"
        and all(a.status == "adjudicated" and a.independence == "external_attested" for a in labels)
        and all(len(set(a.reviewers)) >= 2 and a.author not in a.reviewers for a in labels)
    )
    if not adjudicated:
        return {
            "custody_valid": False,
            "reason": "gold not adjudicated external_attested",
            "gold_adjudicated": False,
        }
    return {
        "custody_valid": True,
        "reason": "structural custody checks pass; "
        "human must confirm the access boundary for QUALIFIED custody",
        "gold_adjudicated": True,
        "custodian": record["custodian"],
    }


def validate_decision_contract_strict(contract):
    """Enforce section-7 admission rules on the loaded threshold contract.

    v1.6 parsing is frozen; this layer rejects values that would disable
    mandatory integrity requirements or that JSON smuggles past lenient
    parsing (NaN/Infinity are rejected at read time by strict_json_load).
    """
    ci = contract["ci_level"]
    if not (0.0 < ci < 1.0):
        raise ValueError("ci_level must lie strictly inside (0, 1)")
    if not contract["min_citation_precision"] > 0.0:
        raise ValueError("min_citation_precision of 0 disables the citation gate")
    if contract["require_full_citation_recall"] is not True:
        raise ValueError("require_full_citation_recall must be true")
    if not contract["min_useful_retention"] > 0.0:
        raise ValueError("min_useful_retention of 0 disables the retention gate")
    if not contract["max_misleading_advance_rate"] < 1.0:
        raise ValueError("max_misleading_advance_rate of 1 disables the misleading gate")
    for key in (
        "bootstrap_resamples",
        "bootstrap_seed",
        "min_scored_cases",
        "min_independent_families",
        "min_useful_cases",
    ):
        value = contract[key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{key} must be an integer")
    return contract


def gated_flags(tasks, labels, outputs_by_arm, contract):
    """Per-case flags with the same citation and integrity gates as scoring."""
    gold = {a.task_id: a for a in labels if a.status != "pending"}
    by_id = {t.id: t for t in tasks}
    flags = {}
    for arm, outs in outputs_by_arm.items():
        per_case = {}
        for out in outs:
            if isinstance(out, dict):
                out = OutcomeR2.model_validate(out)
            task = by_id[out.task_id]
            annotation = gold.get(task.id)
            if out.action in ("refuse", "not_applicable") or annotation is None:
                per_case[out.task_id] = None
                continue
            required = annotation.required_evidence
            gate = citation_gate(required, out.evidence, contract)
            category_ok = out.relationship in annotation.relationships
            covered = all(
                any(
                    c.source_id == r.source_id and c.start <= r.start and c.end >= r.end
                    for c in out.evidence
                )
                for r in required
            )
            judgment_ok = (
                category_ok
                and out.sufficiency == annotation.sufficiency
                and out.applicability == annotation.applicability
                and out.action in annotation.decisions
                and covered
                and out.superseded_claim_ref == annotation.superseded_claim_ref
                and out.replacement_claim_ref == annotation.replacement_claim_ref
            )
            is_semantic = out.mode in (
                "offline_scoring_fixture",
                "surface_heuristic",
                "shortcut_v2",
            )
            assertion = is_semantic and out.relationship != "unknown"
            accepted = judgment_ok and (gate["pass"] if assertion else True)
            per_case[out.task_id] = {
                "family": task.family,
                "useful": bool(annotation.useful_finding),
                "scored": True,
                "retained": bool(annotation.useful_finding and accepted and assertion),
                "misleading": bool(assertion and not accepted),
            }
        flags[arm] = per_case
    return flags


def family_intervals(tasks, flags, contract):
    """Operative family bootstrap. Intervals govern the verdict."""
    import random

    families = sorted({t.family for t in tasks})
    members = {}
    for t in tasks:
        members.setdefault(t.family, []).append(t.id)
    total_cases = sum(len(v) for v in members.values())
    max_family_share = max(len(v) / total_cases for v in members.values()) if members else 0.0
    imbalance_warning = max_family_share >= 0.5
    resamples = contract["bootstrap_resamples"]
    level = contract["ci_level"]
    seed = contract["bootstrap_seed"]
    rng = random.Random(seed)
    alpha = 1.0 - level
    arms = sorted(flags)
    draws = {arm: {"retention": [], "misleading": []} for arm in arms}
    pair_diffs = {
        "D-S_retention": [],
        "D-S_misleading": [],
        "D-C_retention": [],
        "D-C_misleading": [],
    }
    for _ in range(resamples):
        chosen = [rng.choice(families) for _ in families]
        ids = [i for f in chosen for i in members[f]]
        for arm in arms:
            vals = [flags[arm][i] for i in ids if flags[arm].get(i) is not None]
            useful = [v for v in vals if v["useful"]]
            draws[arm]["retention"].append(
                sum(v["retained"] for v in useful) / len(useful) if useful else 0.0
            )
            draws[arm]["misleading"].append(
                sum(v["misleading"] for v in vals) / len(vals) if vals else 0.0
            )
        for key, (a, b, metric) in {
            "D-S_retention": ("D", "S", "retention"),
            "D-S_misleading": ("D", "S", "misleading"),
            "D-C_retention": ("D", "C", "retention"),
            "D-C_misleading": ("D", "C", "misleading"),
        }.items():
            if a in draws and b in draws:
                pair_diffs[key].append(draws[a][metric][-1] - draws[b][metric][-1])

    def interval(xs):
        ordered = sorted(xs)
        lo = ordered[max(0, int((alpha / 2) * len(ordered)))]
        hi = ordered[min(len(ordered) - 1, int((1 - alpha / 2) * len(ordered)))]
        return [lo, hi]

    return {
        "method": "custodian family-level paired bootstrap (gated flags)",
        "families": len(families),
        "max_family_share": max_family_share,
        "imbalance_warning": imbalance_warning,
        "resamples": resamples,
        "seed": seed,
        "level": level,
        "draws_per_arm": {arm: len(d["retention"]) for arm, d in draws.items()},
        "arms": {arm: {k: interval(v) for k, v in d.items()} for arm, d in draws.items()},
        "paired_differences": {k: interval(v) for k, v in pair_diffs.items() if v},
    }


def evaluate(request, paths):
    """Run the full custodian pipeline. Returns a reproducible receipt.

    request: {protocol_dir, claimed_protocol_sha256, claimed_scorer_version,
              claimed_scorer_sha256, requested_scope, submitter,
              submitted_summary (optional, echoed only)}.
    paths: {package_dir, gold_dir, outputs_path, custody_dir, output_path,
            policy_path, contract_path}.
    """
    policy = load_custodian_policy(paths["policy_path"])
    strict_json_loads(Path(paths["contract_path"]).read_text(encoding="utf-8"))
    contract = validate_decision_contract_strict(load_threshold_contract(paths["contract_path"]))
    tasks = load_package_tasks(paths["package_dir"])
    labels = load_package_gold(paths["gold_dir"])
    origins = (
        strict_json_load(Path(paths["gold_dir"]) / "origins.json")
        if (Path(paths["gold_dir"]) / "origins.json").exists()
        else strict_json_load(Path(paths["package_dir"]) / "origins.json")
    )
    validate_corpus_r2(tasks, labels, origins, public=False)
    raw_outputs = strict_json_load(paths["outputs_path"])
    if not isinstance(raw_outputs, dict) or "outcomes" not in raw_outputs:
        raise ValueError("outputs must be an object with an outcomes map")
    normalized = verify_binding(tasks, labels, raw_outputs["outcomes"])
    fingerprints = verify_fingerprints(
        request["protocol_dir"],
        request["claimed_protocol_sha256"],
        request["claimed_scorer_version"],
        request["claimed_scorer_sha256"],
        policy,
    )
    custody = validate_custody(paths.get("custody_dir"), tasks, labels, request.get("submitter"))
    scope = determine_scope(tasks, {**custody, "requested_scope": request.get("requested_scope")})
    metrics = {}
    for arm, outs in normalized.items():
        metrics[arm] = score_r2(tasks, labels, outs, arm, contract, allow_offline_fixtures=True)
    flags = gated_flags(tasks, labels, normalized, contract)
    intervals = family_intervals(tasks, flags, contract)
    verdict = decide_custodian_verdict(
        tasks, labels, metrics, intervals, flags, custody, scope, policy, contract
    )
    receipt = {
        "evaluator": EVAL01_VERSION,
        "verdict": verdict["verdict"],
        "reasons": verdict["reasons"],
        "entailment": "requires_human_adjudication",
        "scope_determined": scope,
        "custody": {k: v for k, v in custody.items()},
        "fingerprints": fingerprints,
        "metrics": metrics,
        "uncertainty": intervals,
        "underpowered": verdict["underpowered"],
        "imbalance_warning": intervals.get("imbalance_warning", False),
        "submitted_summary_echo": request.get("submitted_summary"),
        "summary_authoritative": False,
        "policy_version": policy.get("version"),
    }
    if paths.get("output_path"):
        out = Path(paths["output_path"])
        if out.exists():
            raise ValueError("refusing to overwrite existing receipt; choose a new path")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )
    return receipt


def decide_custodian_verdict(
    tasks, labels, metrics, intervals, flags, custody, scope, policy, contract
):
    """Operative verdict. Intervals govern; missing gates force INCONCLUSIVE."""
    used = {
        "min_holdout_cases",
        "required_arms",
        "min_independent_families",
        "min_useful_cases",
        "min_scored_cases",
    }
    reasons = []
    underpowered = False
    n_families = intervals["families"]
    useful = max((m.get("useful_findings", 0) for m in metrics.values()), default=0)
    scored = max((m.get("scored_tasks", 0) for m in metrics.values()), default=0)
    if scope["scope"] != "blind":
        return {
            "verdict": "INCONCLUSIVE",
            "reasons": [f"scope is {scope['scope']}: {scope['reason']}"],
            "underpowered": underpowered,
            "consumed": sorted(used),
        }
    if not custody.get("custody_valid"):
        return {
            "verdict": "INCONCLUSIVE",
            "reasons": [f"custody invalid: {custody.get('reason')}"],
            "underpowered": underpowered,
            "consumed": sorted(used),
        }
    missing_arms = [a for a in policy["required_arms"] if a not in metrics]
    if missing_arms:
        return {
            "verdict": "INCONCLUSIVE",
            "reasons": [f"missing required comparator outputs: {missing_arms}"],
            "underpowered": underpowered,
            "consumed": sorted(used),
        }
    holdout_cases = len(tasks)
    if holdout_cases < policy["min_holdout_cases"]:
        return {
            "verdict": "INCONCLUSIVE",
            "reasons": [
                f"only {holdout_cases} holdout cases, need >={policy['min_holdout_cases']}"
            ],
            "underpowered": True,
            "consumed": sorted(used),
        }
    if n_families < policy["min_independent_families"]:
        underpowered = True
        reasons.append(f"only {n_families} independent families")
    if useful < policy["min_useful_cases"]:
        underpowered = True
        reasons.append(f"only {useful} useful cases")
    if scored < policy["min_scored_cases"]:
        underpowered = True
        reasons.append(f"only {scored} scored cases")
    if underpowered:
        return {
            "verdict": "INCONCLUSIVE",
            "reasons": reasons,
            "underpowered": True,
            "consumed": sorted(used),
        }
    ret_floor = contract["min_useful_retention"]
    mis_cap = contract["max_misleading_advance_rate"]
    failures = []
    for arm in ("C", "D"):
        m = metrics[arm]
        iv = intervals["arms"].get(arm, {})
        ret_iv = iv.get("retention", [0, 0])
        mis_iv = iv.get("misleading", [1, 1])
        if not (m["gated_useful_finding_retention"] >= ret_floor and ret_iv[0] >= ret_floor):
            failures.append(f"{arm} retention gate (point or interval)")
        if not (m["gated_misleading_advance_rate"] <= mis_cap and mis_iv[1] <= mis_cap):
            failures.append(f"{arm} misleading gate (point or interval)")
        if (m.get("citation_gate") or {}).get("pass_rate", 0) != 1.0:
            failures.append(f"{arm} citation gate")
    for key, margin, cap_side in (
        ("D-S_retention", contract["margin_over_surface_retention"], None),
        ("D-S_misleading", contract["tolerance_over_surface_misleading"], "upper"),
        ("D-C_retention", contract["margin_over_general_retention"], None),
        ("D-C_misleading", contract["tolerance_over_general_misleading"], "upper"),
    ):
        iv = intervals["paired_differences"].get(key)
        if not iv:
            failures.append(f"paired interval {key} unavailable")
            continue
        if "retention" in key and iv[0] < margin:
            failures.append(f"paired {key} interval {iv} clears no margin {margin}")
        if "misleading" in key and iv[1] > (
            contract["tolerance_over_surface_misleading"]
            if "surface" in key
            else contract["tolerance_over_general_misleading"]
        ):
            failures.append(f"paired {key} interval {iv} exceeds tolerance")
    if failures:
        kind = (
            "NO_PROGRESS"
            if any(
                "gate" in f or "margin" in f or "interval" in f or "tolerance" in f
                for f in failures
            )
            else "INCONCLUSIVE"
        )
        return {
            "verdict": kind,
            "reasons": failures,
            "underpowered": underpowered,
            "consumed": sorted(used),
        }
    return {
        "verdict": "PROGRESS",
        "reasons": ["clears absolute, citation, family-interval, and paired-margin gates"],
        "underpowered": underpowered,
        "consumed": sorted(used),
    }


GOLD_VALUE_TOKENS = (
    "substantive_connection",
    "corroboration_candidate",
    "contradiction_candidate",
    "supersession",
    "scoped_change",
    "independent_observations",
    "unsupported_claim",
    "sufficient_for_candidate",
    "insufficient",
    "not_applicable",
    "use_with_qualification",
    "set_aside",
    "implementer_authored",
    "external_attested",
    "adjudicated",
    "unknown",
    "applicable",
    "scoped",
    "abstain",
)


def audit_package_v17(package_dir, tasks, labels):
    """v1.7 package audit: R2 structural audit plus decontamination gates.

    R2 files are frozen, so the stricter v1.7 checks live here: no
    content-hash or access cues in annotator sources, no answer-bearing
    bare values in the template, and the open-questions section present.
    """
    from scripts.notebook03a_r2_protocol import audit_annotation_package

    package_dir = Path(package_dir)
    report = audit_annotation_package(package_dir, tasks, labels)
    findings = list(report["findings"])
    pkg_tasks = json.loads((package_dir / "tasks_for_annotation.json").read_text())
    for entry in pkg_tasks:
        for source in entry.get("sources", []):
            if "sha256" in source:
                findings.append("content hash in annotator package enables record matching")
                break
            if "access" in source:
                findings.append("access-status cue in annotator package")
                break
        if entry.get("family_handle") is not None or entry.get("split") is not None:
            findings.append("family or split exposed in annotator package")
            break
    template_blob = (package_dir / "annotation_template.json").read_text(encoding="utf-8")
    for match in re.findall(r'"([^"<>]*)"', template_blob):
        if match.strip() in GOLD_VALUE_TOKENS:
            findings.append(f"answer-bearing value in template: {match.strip()}")
    instructions = (package_dir / "labeling_instructions.md").read_text(encoding="utf-8")
    if "Open adjudication questions" not in instructions:
        findings.append("disputed rulings not framed as open adjudication questions")
    findings = sorted(set(findings))
    report = dict(report)
    report["package"] = str(package_dir)
    report["entries"] = len(pkg_tasks)
    report["passed"] = report["passed"] and not findings
    report["findings"] = sorted(set(report["findings"]) | set(findings))
    report["audit_version"] = "alive-eval-01-v1"
    return report
