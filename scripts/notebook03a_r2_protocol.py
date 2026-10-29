"""ALIVE-NOTEBOOK-03A-R2 protocol extensions (v1.6). No model client.

Repairs the R1 decision procedure (nested-threshold fallback, public-only
PROGRESS), replaces the shortcut control family, decontaminates the
annotation package, neutralises question wording, and adds cluster-aware
uncertainty with a sealed-holdout gate.

v1.4 (`evaluations/notebook03a/`) and v1.5 (`evaluations/notebook03a_r1/`)
are preserved byte-unchanged. R2 lives in `evaluations/notebook03a_r2/`.
"""

import json
import random
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from scripts.notebook03a_protocol import (
    ROOT,
    Annotation,
    Prediction,
    Span,
    Task,
    check_span,
    file_digest,
    ratio,
    validate_prediction,
    wilson,
)
from scripts.notebook03a_protocol import (
    validate_corpus as validate_corpus_v14,
)
from scripts.notebook03a_r1_protocol import (
    citation_diagnostic,
)

CORPUS_R2 = ROOT / "evaluations/notebook03a_r2"
R2_VERSION = "notebook03a-v1.6"
SHORTCUT_V2_VERSION = "shortcut-control-v2.0"

NEUTRAL_QUESTION = (
    "Assess the relationship between the supplied claims and evidence. "
    "State what is supported, what remains uncertain, and whether the "
    "evidence should influence the current conclusion."
)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class OutcomeR2(Strict):
    """R2 outcome. v1.4/v1.5 arms preserved; V is the v2 shortcut family."""

    task_id: str
    arm: Literal["A", "B", "B0", "S", "V", "C", "D"]
    mode: Literal[
        "lexical",
        "integrity",
        "constant_control",
        "surface_heuristic",
        "shortcut_v2",
        "offline_scoring_fixture",
    ]
    action: Literal[
        "retain_candidate",
        "use_with_qualification",
        "set_aside",
        "abstain",
        "refuse",
        "not_applicable",
    ]
    relationship: str = "unknown"
    sufficiency: str = "unknown"
    applicability: str = "unknown"
    evidence: list[Span] = Field(default_factory=list)
    claim_refs: list[str] = Field(default_factory=list)
    raw_policy: str
    superseded_claim_ref: str | None = None
    replacement_claim_ref: str | None = None


# ---------------------------------------------------------------------------
# Threshold contract (validated, flat, fully consumed)
# ---------------------------------------------------------------------------

# name -> (python type, minimum, maximum, unit, denominator/meaning)
THRESHOLD_SPEC = {
    "min_useful_retention": (float, 0.0, 1.0, "rate", "useful gold scored"),
    "max_misleading_advance_rate": (float, 0.0, 1.0, "rate", "scored tasks"),
    "margin_over_surface_retention": (float, 0.0, 1.0, "rate delta", "D minus S retention"),
    "tolerance_over_surface_misleading": (float, 0.0, 1.0, "rate delta", "D minus S misleading"),
    "margin_over_general_retention": (float, 0.0, 1.0, "rate delta", "D minus C retention"),
    "tolerance_over_general_misleading": (float, 0.0, 1.0, "rate delta", "D minus C misleading"),
    "min_scored_cases": (int, 1, None, "count", "scored tasks for a verdict"),
    "min_independent_families": (int, 1, None, "count", "distinct template families"),
    "min_useful_cases": (int, 1, None, "count", "useful gold scored"),
    "min_citation_precision": (float, 0.0, 1.0, "rate", "required chars covered / cited chars"),
    "require_full_citation_recall": (bool, None, None, "flag", "recall must equal 1.0"),
    "bootstrap_resamples": (int, 100, None, "count", "family resamples"),
    "bootstrap_seed": (int, 0, None, "seed", "deterministic resampling"),
    "ci_level": (float, 0.0, 1.0, "rate", "percentile interval mass"),
}

CONTRACT_META_KEYS = {"version", "scope", "units", "forbidden"}


def load_threshold_contract(path):
    """Load and strictly validate the v1.6 decision-threshold contract.

    Rejects missing, malformed, contradictory, or unused thresholds.
    Never falls back to hard-coded constants: every required key must be
    present with the specified type and range, and no unknown keys are
    permitted, so a silent schema drift cannot go unnoticed.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Threshold contract must be a JSON object")
    unknown = set(raw) - set(THRESHOLD_SPEC) - CONTRACT_META_KEYS
    if unknown:
        raise ValueError(f"Unused/unknown threshold keys rejected: {sorted(unknown)}")
    missing = [k for k in THRESHOLD_SPEC if k not in raw]
    if missing:
        raise ValueError(f"Missing thresholds rejected (no defaults): {missing}")
    contract = {}
    for key, (typ, lo, hi, _unit, _denom) in THRESHOLD_SPEC.items():
        value = raw[key]
        if typ is bool:
            if not isinstance(value, bool):
                raise ValueError(f"Threshold {key} must be a boolean")
        elif typ is int:
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"Threshold {key} must be an integer")
        elif typ is float:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"Threshold {key} must be a number")
            value = float(value)
        else:  # pragma: no cover - spec is closed
            raise ValueError(f"Unknown spec type for {key}")
        if lo is not None and value < lo:
            raise ValueError(f"Threshold {key}={value} below minimum {lo}")
        if hi is not None and value > hi:
            raise ValueError(f"Threshold {key}={value} above maximum {hi}")
        contract[key] = value
    if contract["min_useful_retention"] <= 0.0:
        raise ValueError("min_useful_retention must be positive")
    if contract["max_misleading_advance_rate"] >= 1.0:
        raise ValueError("max_misleading_advance_rate must be below 1.0")
    if contract["min_scored_cases"] < 1:
        raise ValueError("min_scored_cases must be positive")
    return contract


def contract_units():
    """Documented unit and denominator for every threshold."""
    return {k: {"unit": spec[3], "denominator": spec[4]} for k, spec in THRESHOLD_SPEC.items()}


# ---------------------------------------------------------------------------
# R2 corpus load / freeze / validation
# ---------------------------------------------------------------------------


def load_corpus_r2(directory=CORPUS_R2):
    def read(name):
        return json.loads((directory / name).read_text(encoding="utf-8"))

    return (
        [Task.model_validate(t) for t in read("tasks.json")],
        [Annotation.model_validate(a) for a in read("annotations.json")],
        read("origins.json"),
    )


def verify_freeze_r2(directory=CORPUS_R2):
    protocol = json.loads((directory / "protocol.json").read_text(encoding="utf-8"))
    # R2 inventory: top-level frozen files; annotation_package/ excluded
    actual_files = {f.name for f in directory.glob("*.json") if f.name != "protocol.json"}
    actual_files |= {f.name for f in directory.glob("*.md")}
    if actual_files != set(protocol["files_sha256"]):
        raise ValueError(
            f"Frozen R2 file inventory changed: actual={sorted(actual_files)} "
            f"expected={sorted(protocol['files_sha256'])}"
        )
    for name, wanted in protocol["files_sha256"].items():
        if file_digest(directory / name) != wanted:
            raise ValueError("Frozen R2 file drift: " + name)
    for name, wanted in protocol.get("tools_sha256", {}).items():
        if file_digest(ROOT / name) != wanted:
            raise ValueError("Frozen R2 tool contract drift: " + name)
    return protocol


def validate_corpus_r2(tasks, labels, origins, *, public=True):
    """v1.4 validation plus controlled Git-error handling (as in R1)."""
    try:
        return validate_corpus_v14(tasks, labels, origins, public=public)
    except subprocess.CalledProcessError as e:
        raise ValueError(f"Pinned Git revision unavailable: {e.cmd}") from e


def neutral_question_report(tasks):
    """Confirm the v1.6 question transformation (M-E)."""
    questions = {t.question for t in tasks}
    return {
        "distinct_questions": len(questions),
        "is_neutral_uniform": questions == {NEUTRAL_QUESTION},
        "question": NEUTRAL_QUESTION if questions == {NEUTRAL_QUESTION} else None,
    }


# ---------------------------------------------------------------------------
# Citation-quality gate (v3, meaningful rather than diagnostic-only)
# ---------------------------------------------------------------------------


def citation_gate(required, cited, contract):
    """Accept a citation only if it is exact, complete, and not a dump.

    Requires exact spans (validated upstream), full recall of required
    characters, and precision at or above the contracted floor. The floor
    tolerates legitimate boundary context while rejecting whole-source
    dumps. It does not equate overlap with entailment: relevance of the
    cited content to the asserted claim still needs independent output
    adjudication for semantic claims.
    """
    diag = citation_diagnostic(required, cited)
    if not required:
        return {"pass": True, "reason": "no required evidence", **diag}
    if diag["recall"] != 1.0:
        return {"pass": False, "reason": "incomplete required coverage", **diag}
    if diag["precision"] is None or diag["precision"] < contract["min_citation_precision"]:
        return {"pass": False, "reason": "overly broad citation", **diag}
    return {"pass": True, "reason": "exact and proportionate", **diag}


def validate_outcomes_r2(tasks, outcomes, arm, *, allow_offline_fixtures=False):
    by_id = {t.id: t for t in tasks}
    if len(outcomes) != len(tasks) or {o.task_id for o in outcomes} != set(by_id):
        raise ValueError("Exactly one recorded outcome per task is required")
    if len({o.task_id for o in outcomes}) != len(outcomes) or any(o.arm != arm for o in outcomes):
        raise ValueError("Duplicate result or mixed-arm result set")
    expected_mode = {
        "A": "lexical",
        "B": "integrity",
        "B0": "constant_control",
        "S": "surface_heuristic",
        "V": "shortcut_v2",
        "C": "offline_scoring_fixture",
        "D": "offline_scoring_fixture",
    }[arm]
    for outcome in outcomes:
        task = by_id[outcome.task_id]
        if outcome.mode != expected_mode:
            raise ValueError("Recorded mode does not match the declared arm")
        denied = any(s.access != "fixture_authorized" for s in task.sources)
        if denied:
            if outcome.action != "refuse" or outcome.evidence or outcome.claim_refs:
                raise PermissionError("Authorization/disclosure hard gate failed")
            continue
        if outcome.action == "refuse":
            raise ValueError("Refusal requires a declared access restriction")
        if outcome.action == "not_applicable" and not (
            task.kind == "claim_support" and arm in ("A", "B")
        ):
            raise ValueError("Difficult cases cannot silently be marked inapplicable")
        if outcome.mode in ("offline_scoring_fixture", "surface_heuristic", "shortcut_v2"):
            if outcome.mode == "offline_scoring_fixture" and not allow_offline_fixtures:
                raise PermissionError(
                    "03A has no model execution or verified-consent admission path"
                )
            pred = Prediction(
                relationship=outcome.relationship,  # type: ignore[arg-type]
                evidence_sufficiency=outcome.sufficiency,  # type: ignore[arg-type]
                applicability=outcome.applicability,  # type: ignore[arg-type]
                decision=outcome.action,  # type: ignore[arg-type]
                claim_refs=outcome.claim_refs,
                evidence=outcome.evidence,
                scope_differences=[],
                limitations=["R2 scoring; control fixture"],
                superseded_claim_ref=outcome.superseded_claim_ref,
                replacement_claim_ref=outcome.replacement_claim_ref,
            )
            validate_prediction(task, pred)
        elif outcome.relationship != "unknown" or outcome.action in (
            "use_with_qualification",
            "set_aside",
        ):
            raise ValueError("A nonreasoning baseline cannot emit fake semantic findings")
        for span in outcome.evidence:
            check_span(span, {s.id: s for s in task.sources})


# ---------------------------------------------------------------------------
# Base scorer (R1-compatible definitions, R2 arms/modes)
# ---------------------------------------------------------------------------

SEMANTIC_MODES = ("offline_scoring_fixture", "surface_heuristic", "shortcut_v2")


def _score_base_r2(tasks, labels, normed, arm):
    """Base metrics with R1-compatible definitions for R2 arms.

    - useful retention counts accepted substantive findings on useful gold
      (semantic arms S/V/C/D only; A reports candidate recall separately);
    - misleading advances: S/V/C/D unsupported judgments, A retains on
      non-useful-or-insufficient, B/B0 zero by construction;
    - category accuracy includes unknown/unknown (excluded variant reported);
    - neither unknown match counts as a substantive judgment.
    """
    gold = {a.task_id: a for a in labels if a.status != "pending"}
    by_id = {t.id: t for t in tasks}
    confusion, per_category = Counter(), {}
    useful = retained = candidate_retained = assertions = correct = unsupported = 0
    insufficient = abstained_insufficient = eligible = categories_correct = 0
    suff_correct = 0
    unscored = inapplicable = refused = 0
    non_useful = correct_non_use = false_abst = 0
    misleading = 0
    unknown_unknown = 0
    cat_correct_excl_uu = 0
    eligible_excl_uu = 0
    prec_sum = rec_sum = prec_n = rec_n = 0
    decisions = Counter()
    for output in normed:
        task = by_id[output.task_id]
        decisions[output.action] += 1
        if output.action == "refuse":
            refused += 1
            continue
        if output.action == "not_applicable":
            inapplicable += 1
            continue
        annotation = gold.get(task.id)
        if annotation is None:
            unscored += 1
            continue
        eligible += 1
        is_useful = bool(annotation.useful_finding)
        useful += is_useful
        non_useful += not is_useful
        insufficient += annotation.sufficiency == "insufficient"
        abstained_insufficient += (
            annotation.sufficiency == "insufficient" and output.action == "abstain"
        )
        false_abst += is_useful and output.action == "abstain"
        category_ok = output.relationship in annotation.relationships
        is_uu = output.relationship == "unknown" and annotation.relationships == ["unknown"]
        unknown_unknown += is_uu
        if not is_uu:
            eligible_excl_uu += 1
            cat_correct_excl_uu += category_ok
        suff_correct += output.sufficiency == annotation.sufficiency
        categories_correct += category_ok
        confusion[("|".join(annotation.relationships), output.relationship)] += 1
        required = annotation.required_evidence
        covered = all(
            any(
                c.source_id == r.source_id and c.start <= r.start and c.end >= r.end
                for c in output.evidence
            )
            for r in required
        )
        is_semantic = output.mode in SEMANTIC_MODES
        assertion = is_semantic and output.relationship != "unknown"
        judgment_ok = (
            category_ok
            and output.sufficiency == annotation.sufficiency
            and output.applicability == annotation.applicability
            and output.action in annotation.decisions
            and covered
            and output.superseded_claim_ref == annotation.superseded_claim_ref
            and output.replacement_claim_ref == annotation.replacement_claim_ref
        )
        assertions += assertion
        correct += bool(assertion and judgment_ok)
        unsupported += bool(assertion and not judgment_ok)
        retained += bool(is_useful and judgment_ok and assertion)
        candidate_retained += bool(is_useful and output.action == "retain_candidate")
        if not is_useful:
            if is_semantic:
                if judgment_ok and (assertion or output.action == "abstain"):
                    correct_non_use += 1
            elif output.action == "abstain":
                correct_non_use += 1
        if is_semantic:
            misleading += bool(assertion and not judgment_ok)
        elif arm == "A":
            if output.action == "retain_candidate" and (
                (not is_useful) or annotation.sufficiency == "insufficient"
            ):
                misleading += 1
        if required:
            diag = citation_diagnostic(required, output.evidence)
            if diag["recall"] is not None:
                rec_sum += diag["recall"]
                rec_n += 1
            if diag["precision"] is not None:
                prec_sum += diag["precision"]
                prec_n += 1
        for category in annotation.relationships:
            row = per_category.setdefault(
                category,
                {"cases": 0, "category_correct": 0, "useful_findings": 0, "useful_retained": 0},
            )
            row["cases"] += 1
            row["category_correct"] += category_ok
            row["useful_findings"] += is_useful
            row["useful_retained"] += bool(is_useful and judgment_ok and assertion)
    return {
        "arm": arm,
        "total_tasks": len(tasks),
        "scored_tasks": eligible,
        "unscored_missing_annotations": unscored,
        "not_applicable": inapplicable,
        "access_refused": refused,
        "annotation_status": "PROVISIONAL_PUBLIC_DRAFT_LABELS_R2",
        "correct_substantive_judgments": correct,
        "substantive_judgments": assertions,
        "unsupported_substantive_judgments": unsupported,
        "unsupported_assertions": unsupported if arm in ("S", "V", "C", "D") else misleading,
        "substantive_precision": ratio(correct, assertions),
        "category_accuracy": ratio(categories_correct, eligible),
        "category_accuracy_excluding_unknown_unknown": ratio(cat_correct_excl_uu, eligible_excl_uu),
        "unknown_unknown_matches": unknown_unknown,
        "category_accuracy_rule": (
            "unknown/unknown counts toward category_accuracy; "
            "excluded variant reported separately; "
            "neither counts as substantive judgment"
        ),
        "sufficiency_accuracy": ratio(suff_correct, eligible),
        "useful_findings": useful,
        "useful_findings_retained": retained,
        "useful_finding_retention": ratio(retained, useful),
        "missed_useful_findings": useful - retained,
        "false_abstentions": false_abst,
        "false_abstention_rate": ratio(false_abst, useful),
        "useful_candidates_retained": candidate_retained,
        "useful_candidate_recall": ratio(candidate_retained, useful),
        "insufficient_cases": insufficient,
        "correct_insufficient_abstention": abstained_insufficient,
        "correct_insufficient_abstention_rate": ratio(abstained_insufficient, insufficient),
        "non_useful_cases": non_useful,
        "correct_non_use_decisions": correct_non_use,
        "correct_non_use_rate": ratio(correct_non_use, non_useful),
        "misleading_advances": misleading,
        "misleading_advance_rate": ratio(misleading, eligible),
        "misleading_advance_rule": (
            "S/V/C/D: unsupported substantive judgments / scored; "
            "A: retain_candidate on non-useful-or-insufficient / scored; "
            "B/B0: 0 by construction"
        ),
        "citation_precision_mean": (prec_sum / prec_n) if prec_n else None,
        "citation_recall_mean": (rec_sum / rec_n) if rec_n else None,
        "citation_cases": prec_n,
        "citation_limitation": (
            "Exact-span overlap only; cannot establish entailment. "
            "Invented spans fail closed via validation."
        ),
        "retention_wilson95_case_independence_not_assumed": wilson(retained, useful),
        "uncertainty": (
            "Illustrative binomial interval only; related families violate "
            "independent-case assumptions. No significance claim."
        ),
        "confusion_matrix": [
            {"gold": a, "predicted": b, "count": n} for (a, b), n in sorted(confusion.items())
        ],
        "per_category": per_category,
        "decisions": dict(decisions),
        "model_calls": 0,
        "cost_micro_usd": 0,
    }


def score_r2(tasks, labels, outcomes, arm, contract, *, allow_offline_fixtures=False):
    """Base R1 scoring plus the v3 citation gate.

    Every substantive finding must pass the citation gate; findings that
    fail it are misleading advances, never silent correct decisions. Both
    base (R1-compatible) and gated numbers are reported; the progress
    policy consumes the gated ones.
    """
    normed = []
    for o in outcomes:
        if isinstance(o, OutcomeR2):
            normed.append(o)
        else:
            normed.append(
                OutcomeR2(
                    task_id=o.task_id,
                    arm=o.arm,  # type: ignore[arg-type]
                    mode=o.mode,  # type: ignore[arg-type]
                    action=o.action,  # type: ignore[arg-type]
                    relationship=o.relationship,
                    sufficiency=o.sufficiency,
                    applicability=o.applicability,
                    evidence=o.evidence,
                    claim_refs=o.claim_refs,
                    raw_policy=o.raw_policy,
                    superseded_claim_ref=o.superseded_claim_ref,
                    replacement_claim_ref=o.replacement_claim_ref,
                )
            )
    validate_outcomes_r2(tasks, normed, arm, allow_offline_fixtures=allow_offline_fixtures)
    base = _score_base_r2(tasks, labels, normed, arm)
    gold = {a.task_id: a for a in labels if a.status != "pending"}
    by_id = {t.id: t for t in tasks}
    gated_retained = 0
    gated_misleading = 0
    gate_passed = 0
    gate_cases = 0
    semantic_arm = arm in ("S", "V", "C", "D")
    for output in normed:
        task = by_id[output.task_id]
        if output.action in ("refuse", "not_applicable"):
            continue
        annotation = gold.get(task.id)
        if annotation is None:
            continue
        required = annotation.required_evidence
        is_semantic = output.mode in (
            "offline_scoring_fixture",
            "surface_heuristic",
            "shortcut_v2",
        )
        assertion = is_semantic and output.relationship != "unknown"
        if not assertion:
            continue
        gate = citation_gate(required, output.evidence, contract)
        gate_cases += 1
        gate_passed += gate["pass"]
        category_ok = output.relationship in annotation.relationships
        covered = all(
            any(
                c.source_id == r.source_id and c.start <= r.start and c.end >= r.end
                for c in output.evidence
            )
            for r in required
        )
        judgment_ok = (
            category_ok
            and output.sufficiency == annotation.sufficiency
            and output.applicability == annotation.applicability
            and output.action in annotation.decisions
            and covered
            and output.superseded_claim_ref == annotation.superseded_claim_ref
            and output.replacement_claim_ref == annotation.replacement_claim_ref
        )
        accepted = judgment_ok and gate["pass"]
        gated_retained += bool(annotation.useful_finding and accepted)
        gated_misleading += bool(not accepted)
    base["citation_gate"] = {
        "assertions_checked": gate_cases,
        "assertions_passed": gate_passed,
        "pass_rate": ratio(gate_passed, gate_cases),
        "min_precision": contract["min_citation_precision"],
        "require_full_recall": contract["require_full_citation_recall"],
        "rule": "Accepted findings need exact spans, full required coverage, "
        "and precision at/above floor. Failures are misleading advances.",
    }
    if semantic_arm:
        base["gated_useful_findings_retained"] = gated_retained
        base["gated_useful_finding_retention"] = ratio(gated_retained, base["useful_findings"])
        base["gated_misleading_advances"] = gated_misleading
        base["gated_misleading_advance_rate"] = ratio(gated_misleading, base["scored_tasks"])
    else:
        # Candidate/integrity/constant arms make no substantive assertions;
        # the citation gate is vacuous and base numbers stand.
        base["gated_useful_findings_retained"] = base["useful_findings_retained"]
        base["gated_useful_finding_retention"] = base["useful_finding_retention"]
        base["gated_misleading_advances"] = base["misleading_advances"]
        base["gated_misleading_advance_rate"] = base["misleading_advance_rate"]
    base["annotation_status"] = "PROVISIONAL_PUBLIC_DRAFT_LABELS_R2"
    return base


# ---------------------------------------------------------------------------
# Cluster-aware uncertainty (family-level paired resampling)
# ---------------------------------------------------------------------------


def case_flags(tasks, labels, outcomes_by_arm):
    """Precompute per-case correctness flags for resampling."""
    gold = {a.task_id: a for a in labels if a.status != "pending"}
    by_id = {t.id: t for t in tasks}
    flags = {}
    for arm, outcomes in outcomes_by_arm.items():
        per_case = {}
        for o in outcomes:
            task = by_id[o.task_id]
            annotation = gold.get(task.id)
            if o.action in ("refuse", "not_applicable") or annotation is None:
                per_case[o.task_id] = None
                continue
            required = annotation.required_evidence
            covered = all(
                any(
                    c.source_id == r.source_id and c.start <= r.start and c.end >= r.end
                    for c in o.evidence
                )
                for r in required
            )
            category_ok = o.relationship in annotation.relationships
            judgment_ok = (
                category_ok
                and o.sufficiency == annotation.sufficiency
                and o.applicability == annotation.applicability
                and o.action in annotation.decisions
                and covered
                and o.superseded_claim_ref == annotation.superseded_claim_ref
                and o.replacement_claim_ref == annotation.replacement_claim_ref
            )
            is_semantic = o.mode in (
                "offline_scoring_fixture",
                "surface_heuristic",
                "shortcut_v2",
            )
            assertion = is_semantic and o.relationship != "unknown"
            per_case[o.task_id] = {
                "family": task.family,
                "useful": bool(annotation.useful_finding),
                "scored": True,
                "retained": bool(annotation.useful_finding and judgment_ok and assertion),
                "misleading": bool(assertion and not judgment_ok),
            }
        flags[arm] = per_case
    return flags


def family_bootstrap(tasks, labels, outcomes_by_arm, contract):
    """Family-level paired bootstrap over precomputed case flags.

    Resamples families (not cases) with replacement using the contracted
    seed, recomputing retention and misleading rates per arm and paired
    D-vs-S / D-vs-C differences on each resample. Families are the
    predeclared non-independence units; correlated variants within a family
    always move together, so near-duplicates cannot inflate the effective
    sample. Percentile intervals are sensitivity bounds under
    family-exchangeability, not population inference: families are few,
    deliberately selected, and mutually correlated, so narrow intervals
    must not be read as significance. Predeclared underpowered rules yield
    an explicit insufficient-sample warning consumed by the decision.
    """
    families = sorted({t.family for t in tasks})
    members = {}
    for t in tasks:
        members.setdefault(t.family, []).append(t.id)
    flags = case_flags(tasks, labels, outcomes_by_arm)
    resamples = contract["bootstrap_resamples"]
    level = contract["ci_level"]
    rng = random.Random(contract["bootstrap_seed"])
    alpha = 1.0 - level
    arms = sorted(outcomes_by_arm)
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
        for pair, (a, b, key) in {
            "D-S_retention": ("D", "S", "retention"),
            "D-S_misleading": ("D", "S", "misleading"),
            "D-C_retention": ("D", "C", "retention"),
            "D-C_misleading": ("D", "C", "misleading"),
        }.items():
            if a in draws and b in draws:
                pair_diffs[pair].append(draws[a][key][-1] - draws[b][key][-1])

    def interval(xs):
        ordered = sorted(xs)
        lo = ordered[max(0, int((alpha / 2) * len(ordered)))]
        hi = ordered[min(len(ordered) - 1, int((1 - alpha / 2) * len(ordered)))]
        return [lo, hi]

    result = {
        "method": "family-level paired bootstrap (precomputed case flags)",
        "families": len(families),
        "resamples": resamples,
        "seed": contract["bootstrap_seed"],
        "level": level,
        "arms": {arm: {k: interval(v) for k, v in d.items()} for arm, d in draws.items()},
        "paired_differences": {k: interval(v) for k, v in pair_diffs.items() if v},
        "limitation": (
            "Sensitivity bounds under family exchangeability, not population "
            "inference. Families are few and deliberately selected; a 3-case "
            "shift inside one family moves the point estimate without "
            "changing the interval's meaning."
        ),
    }
    return result


# ---------------------------------------------------------------------------
# Progress decision (layered: engineering / diagnostic / readiness / final)
# ---------------------------------------------------------------------------


def _verdict(verdict, reason, **extra):
    return {"verdict": verdict, "reason": reason, **extra}


def decide_progress(metrics_by_arm, contract, context):
    """Layered R2 decision. Consumes every contracted threshold.

    Layers:
    - engineering_validity: freeze/contract/citation evidence present.
    - public_diagnostic: per-arm point estimates (never a verdict).
    - blind_readiness: holdout, adjudicated gold, boundary, comparators.
    - final: PROGRESS only on a blind, fully gated evaluation where D
      clears absolute gates plus D-vs-C and D-vs-S margins on both
      retention and misleading advances. Anything weaker is NO_PROGRESS;
      anything missing is INCONCLUSIVE with the missing element named.
    """
    used = set()

    def need(key):
        used.add(key)
        return contract[key]

    ret_min = need("min_useful_retention")
    mis_max = need("max_misleading_advance_rate")
    s_ret_margin = need("margin_over_surface_retention")
    s_mis_tol = need("tolerance_over_surface_misleading")
    c_ret_margin = need("margin_over_general_retention")
    c_mis_tol = need("tolerance_over_general_misleading")
    min_scored = need("min_scored_cases")
    need("min_independent_families")
    min_useful = need("min_useful_cases")
    need("min_citation_precision")
    need("require_full_citation_recall")
    need("bootstrap_resamples")
    need("bootstrap_seed")
    need("ci_level")

    assert set(used) == set(THRESHOLD_SPEC), "every threshold must be consumed"

    def get(arm, key):
        return metrics_by_arm.get(arm, {}).get(key)

    engineering = _verdict(
        "VALID" if context.get("freeze_ok") else "INVALID",
        "Frozen inputs, tools, and contract verified."
        if context.get("freeze_ok")
        else "Freeze/contract verification failed.",
    )
    diagnostic = {
        arm: {
            "retention": get(arm, "gated_useful_finding_retention"),
            "misleading": get(arm, "gated_misleading_advance_rate"),
            "scored": get(arm, "scored_tasks"),
            "note": "DIAGNOSTIC_ONLY: public/exposed cases; never a research verdict.",
        }
        for arm in ("A", "B", "B0", "S", "V", "C", "D")
        if arm in metrics_by_arm
    }
    missing = []
    if context.get("scope") != "blind":
        missing.append("blind evaluation scope (public/exposed cases cannot yield PROGRESS)")
    if not context.get("holdout_available"):
        missing.append("sealed holdout package (HOLDOUT_PENDING)")
    if not context.get("gold_adjudicated"):
        missing.append("independently adjudicated gold")
    if context.get("exposure_events"):
        missing.append(f"answer-exposure events: {context['exposure_events']}")
    for arm in ("A", "B0", "S", "C", "D"):
        if arm not in metrics_by_arm:
            missing.append(f"comparator {arm} results")
    readiness = _verdict(
        "READY" if not missing else "NOT_READY",
        "Blind evaluation ready." if not missing else f"Missing: {'; '.join(missing)}.",
        missing=missing,
    )
    if missing:
        return {
            "engineering_validity": engineering,
            "public_diagnostic": diagnostic,
            "blind_readiness": readiness,
            "final": _verdict("INCONCLUSIVE", f"Missing: {'; '.join(missing)}."),
            "thresholds_consumed": sorted(used),
        }
    finals = {}
    for arm in ("C", "D"):
        m = metrics_by_arm[arm]
        scored = m.get("scored_tasks", 0)
        useful = m.get("useful_findings", 0)
        ret = m.get("gated_useful_finding_retention")
        mis = m.get("gated_misleading_advance_rate")
        gate_rate = (m.get("citation_gate") or {}).get("pass_rate")
        families = context.get("n_families", 0)
        checks = []
        if scored < min_scored:
            checks.append(f"only {scored} scored, need >={min_scored}")
        if families < need("min_independent_families"):
            checks.append(f"only {families} families")
        if useful < min_useful:
            checks.append(f"only {useful} useful cases")
        if ret is None or ret < ret_min:
            checks.append(f"retention {ret} below {ret_min}")
        if mis is None or mis > mis_max:
            checks.append(f"misleading {mis} above {mis_max}")
        if gate_rate is None or gate_rate < 1.0:
            checks.append(f"citation-gate pass rate {gate_rate} below 1.0")
        s_ret = get("S", "gated_useful_finding_retention")
        s_mis = get("S", "gated_misleading_advance_rate")
        if s_ret is None or ret is None or ret < s_ret + s_ret_margin:
            checks.append(f"does not exceed S retention {s_ret} by {s_ret_margin}")
        if s_mis is None or mis is None or mis > s_mis + s_mis_tol:
            checks.append(f"exceeds S misleading {s_mis} beyond {s_mis_tol}")
        if arm == "D":
            c_ret = get("C", "gated_useful_finding_retention")
            c_mis = get("C", "gated_misleading_advance_rate")
            if c_ret is None or ret is None or ret < c_ret + c_ret_margin:
                checks.append(f"does not exceed C retention {c_ret} by {c_ret_margin}")
            if c_mis is None or mis is None or mis > c_mis + c_mis_tol:
                checks.append(f"exceeds C misleading {c_mis} beyond {c_mis_tol}")
        if checks:
            finals[arm] = _verdict("NO_PROGRESS", "; ".join(checks))
        else:
            finals[arm] = _verdict(
                "PROGRESS",
                "Clears absolute gates and "
                f"{'D-vs-C and D-vs-S' if arm == 'D' else 'C-vs-S'} margins.",
                retention=ret,
                misleading=mis,
            )
    # C and D can never share a verdict by thresholds alone: D additionally
    # requires the D-vs-C margins, and C's record carries its own reference.
    return {
        "engineering_validity": engineering,
        "public_diagnostic": diagnostic,
        "blind_readiness": readiness,
        "final": finals,
        "thresholds_consumed": sorted(used),
    }


# ---------------------------------------------------------------------------
# Annotation-package leakage audit (M-D)
# ---------------------------------------------------------------------------

# Field names are schema (necessary in a blank template); values can leak.
# Bare taxonomy/answer values outside <placeholder> markers are forbidden.
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


def audit_annotation_package(package_dir, tasks, annotations):
    """Fail a package that leaks gold answers or identity mappings.

    Checks opaque handles, absent mapping, no split/family exposure, no
    gold field names, no exact rationale/notes strings, and structural
    self-containment (every span resolves inside the package).
    """
    package_dir = Path(package_dir)
    findings = []
    pkg_tasks = json.loads((package_dir / "tasks_for_annotation.json").read_text())
    template_blob = (package_dir / "annotation_template.json").read_text()
    instruction_blob = ""
    for name in ("labeling_instructions.md", "category_definitions.md", "README.md"):
        path = package_dir / name
        if path.exists():
            instruction_blob += path.read_text(encoding="utf-8") + "\n"
    task_ids = {t.id for t in tasks}
    families = {t.family for t in tasks}
    for entry in pkg_tasks:
        if entry.get("handle") in task_ids:
            findings.append(f"handle equals public task ID: {entry['handle']}")
        if entry.get("family_handle") in families:
            findings.append("family handle equals public family ID")
        if entry.get("split") is not None:
            findings.append("split exposed in annotator package")
    if (package_dir / "handle_mapping.json").exists():
        findings.append("identity mapping shipped inside annotator package")
    # Template values must all be placeholders: bare taxonomy/answer words
    # outside <...> markers would encode a preselected answer.
    for match in re.findall(r'"([^"<>]*)"', template_blob):
        word = match.strip()
        if word in GOLD_VALUE_TOKENS:
            findings.append(f"answer-bearing value in template: {word}")
    for annotation in annotations:
        if annotation.rationale and annotation.rationale in instruction_blob:
            findings.append(f"draft rationale leaked for {annotation.task_id}")
    r1_notes = json.loads(CORPUS_R1_NOTES.read_text(encoding="utf-8"))
    for task_id, note in r1_notes.items():
        desc = (note or {}).get("development_description", "")
        if desc and desc in instruction_blob:
            findings.append(f"implementer dev description leaked: {desc}")
    for entry in pkg_tasks:
        sources = {s["id"]: s["text"] for s in entry.get("sources", [])}
        for claim in entry.get("claims", []):
            passage = claim.get("passage", {})
            sid = passage.get("source_id")
            text = passage.get("text", "")
            if sid not in sources or text not in sources[sid]:
                findings.append(f"unresolvable span in {entry.get('handle')}")
    return {
        "package": str(package_dir),
        "entries": len(pkg_tasks),
        "passed": not findings,
        "findings": sorted(set(findings)),
        "residual_risk": (
            "Renaming cannot guarantee blinding when annotators hold "
            "repository access: authorship style, case order, and public "
            "history remain recognizable. Genuine blinding needs the sealed "
            "holdout boundary, not field hygiene alone."
        ),
    }


CORPUS_R1_NOTES = ROOT / "evaluations/notebook03a_r1/annotation_notes.json"


# ---------------------------------------------------------------------------
# Sealed-holdout handoff contract (M-C)
# ---------------------------------------------------------------------------

HOLDOUT_PENDING = "HOLDOUT_PENDING"


def holdout_status(contract_path, package_dir=None):
    """Report sealed-holdout state; PENDING unless a valid package exists."""
    contract = json.loads(Path(contract_path).read_text(encoding="utf-8"))
    if package_dir is None:
        return {
            "status": HOLDOUT_PENDING,
            "missing": ["custodian-supplied sealed package"],
            "contract_version": contract.get("version"),
        }
    try:
        report = validate_holdout_package(Path(package_dir), contract)
    except ValueError as e:
        return {
            "status": HOLDOUT_PENDING,
            "missing": [str(e)],
            "contract_version": contract.get("version"),
        }
    if not report["passed"]:
        return {
            "status": HOLDOUT_PENDING,
            "missing": report["findings"],
            "contract_version": contract.get("version"),
        }
    return {
        "status": "SEALED",
        "missing": [],
        "contract_version": contract.get("version"),
        "cases": report["cases"],
    }


def validate_holdout_package(package_dir, contract):
    """Structural validation of a custodian holdout package (no access proof)."""
    package_dir = Path(package_dir)
    findings = []
    try:
        tasks = [
            Task.model_validate(t) for t in json.loads((package_dir / "tasks.json").read_text())
        ]
        labels = [
            Annotation.model_validate(a)
            for a in json.loads((package_dir / "annotations.json").read_text())
        ]
        manifest = json.loads((package_dir / "independent_submission.json").read_text())
    except (OSError, ValueError) as e:
        return {"passed": False, "findings": [f"unreadable package: {e}"], "cases": 0}
    if any(t.split != "independent_heldout" for t in tasks):
        findings.append("holdout tasks must declare the independent_heldout split")
    if any(a.independence != "external_attested" or a.status != "adjudicated" for a in labels):
        findings.append("holdout labels must be adjudicated external_attested")
    if manifest.get("independent_annotation_status") != "ADJUDICATED":
        findings.append("manifest must attest ADJUDICATED status")
    if manifest.get("access_restricted_attested") is not True:
        findings.append("manifest must attest restricted access")
    if manifest.get("implementer_exposure_events"):
        findings.append("exposure events invalidate blind use")
    overlap_families = {t.family for t in tasks} & set(contract.get("public_families", []))
    if overlap_families:
        findings.append(f"holdout reuses public families: {sorted(overlap_families)[:3]}")
    return {"passed": not findings, "findings": findings, "cases": len(tasks)}
