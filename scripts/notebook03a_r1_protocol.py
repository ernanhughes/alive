"""ALIVE-NOTEBOOK-03A-R1 protocol extensions (v1.5). No model client.

Extends v1.4 contracts without modifying frozen v1.4 files. Original
`scripts/notebook03a_protocol.py` and `evaluations/notebook03a/*` remain
byte-unchanged; R1 lives in `evaluations/notebook03a_r1/` and this module.
"""

import json
import re
import subprocess
from collections import Counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Reuse v1.4 base contracts
from scripts.notebook03a_protocol import (
    ROOT,
    Annotation,
    Prediction,
    Span,
    Task,
    canonical,
    check_span,
    file_digest,
    ratio,
    validate_prediction,
    wilson,
)
from scripts.notebook03a_protocol import (
    validate_corpus as validate_corpus_v14,
)

CORPUS_R1 = ROOT / "evaluations/notebook03a_r1"
R1_VERSION = "notebook03a-v1.5"
SURFACE_VERSION = "surface-cue-v1.0"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class OutcomeR1(Strict):
    """R1 outcome with surface-heuristic arm. v1.4 arms/modes preserved."""

    task_id: str
    arm: Literal["A", "B", "B0", "S", "C", "D"]
    mode: Literal[
        "lexical",
        "integrity",
        "constant_control",
        "surface_heuristic",
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


def load_corpus_r1(directory=CORPUS_R1):
    def read(name):
        return json.loads((directory / name).read_text(encoding="utf-8"))

    return (
        [Task.model_validate(t) for t in read("tasks.json")],
        [Annotation.model_validate(a) for a in read("annotations.json")],
        read("origins.json"),
    )


def verify_freeze_r1(directory=CORPUS_R1):
    protocol = json.loads((directory / "protocol.json").read_text(encoding="utf-8"))
    # R1 inventory: only top-level *.json counted;
    # annotation_package/ excluded (review material, not frozen inputs)
    actual_files = {f.name for f in directory.glob("*.json") if f.name != "protocol.json"}
    if actual_files != set(protocol["files_sha256"]):
        raise ValueError(
            f"Frozen R1 file inventory changed: actual={sorted(actual_files)} "
            f"expected={sorted(protocol['files_sha256'])}"
        )
    for name, wanted in protocol["files_sha256"].items():
        if file_digest(directory / name) != wanted:
            raise ValueError("Frozen R1 file drift: " + name)
    for name, wanted in protocol.get("tools_sha256", {}).items():
        if file_digest(ROOT / name) != wanted:
            raise ValueError("Frozen R1 tool contract drift: " + name)
    return protocol


def validate_corpus_r1(tasks, labels, origins, *, public=True):
    """v1.4 validation plus controlled Git-error handling.

    Missing Git revisions raise ValueError (controlled validation error),
    not CalledProcessError. Template-family similarity is reported separately
    via `template_similarity_report` (heuristic, non-blocking).
    """
    try:
        return validate_corpus_v14(tasks, labels, origins, public=public)
    except subprocess.CalledProcessError as e:
        raise ValueError(f"Pinned Git revision unavailable: {e.cmd}") from e


def normalize_tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", text.lower()))


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def template_similarity_report(tasks, threshold: float = 0.55):
    """Heuristic detection of closely related template families across splits.

    Compares concatenated source texts per task using token Jaccard. Reports
    pairs across different splits above threshold. This is a diagnostic only:
    it cannot prove semantic equivalence or detect all paraphrases, and it
    may flag coincidental lexical overlap. Family IDs remain the normative
    non-independence signal; paraphrases sharing meaning but not family must
    still be disclosed as non-independent in annotation notes.
    """
    by_family: dict[str, dict] = {}
    for t in tasks:
        blob = " ".join(s.text for s in t.sources)
        by_family.setdefault(t.family, {"split": t.split, "tokens": set(), "tasks": []})
        by_family[t.family]["tokens"] |= normalize_tokens(blob)
        by_family[t.family]["tasks"].append(t.id)
    fams = sorted(by_family.items())
    hits = []
    for i in range(len(fams)):
        for j in range(i + 1, len(fams)):
            (f1, d1), (f2, d2) = fams[i], fams[j]
            if d1["split"] == d2["split"]:
                continue
            sim = jaccard(d1["tokens"], d2["tokens"])
            if sim >= threshold:
                hits.append(
                    {
                        "family_a": f1,
                        "split_a": d1["split"],
                        "family_b": f2,
                        "split_b": d2["split"],
                        "jaccard": round(sim, 4),
                    }
                )
    return {
        "threshold": threshold,
        "families": len(fams),
        "cross_split_hits": sorted(hits, key=lambda h: -h["jaccard"]),
        "limitation": (
            "Token-Jaccard heuristic only; misses paraphrases with different vocabulary "
            "and may flag coincidental overlap. Not a proof of independence or leakage."
        ),
    }


def prepare_payload_r1(task):
    """R1 whitelist: removes version/temporal/system context cues.

    v1.4 included version_context/temporal_context/system_context, which
    correlated with authentic (ALIVE-*) vs synthetic (null) provenance.
    R1 withholds those fields to remove the inadvertent source-class cue.
    Question, task kind, claim passages/IDs/roles, and full bounded sources
    remain identical for all arms. Gold, IDs, splits, families, origins,
    annotation hints remain withheld as in v1.4.
    """
    if any(s.access != "fixture_authorized" for s in task.sources):
        raise PermissionError("Evidence unavailable")
    payload = {
        "contract_version": "notebook03-claim-input-v1.5-r1",
        "question": task.question,
        "task_kind": task.kind,
        "claims": [
            {"id": c.id, "role": c.role, "passage": c.passage.model_dump()} for c in task.claims
        ],
        "sources": [
            {
                "id": s.id,
                "text": s.text,
                "sha256": s.sha256,
                "untrusted_presentation": {"title": s.untrusted_title},
            }
            for s in task.sources
        ],
    }
    if len(canonical(payload)) > 16000:
        raise ValueError("Serialized evidence payload exceeds the frozen budget")
    return payload


def validate_outcomes_r1(tasks, outcomes, arm, *, allow_offline_fixtures=False):
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
        if outcome.mode in ("offline_scoring_fixture", "surface_heuristic"):
            if outcome.mode == "offline_scoring_fixture" and not allow_offline_fixtures:
                raise PermissionError(
                    "03A has no model execution or verified-consent admission path"
                )
            # Surface heuristic is an offline deterministic control; no consent gate.
            # Both modes must still satisfy exact-citation and claim-ref integrity.
            p = Prediction(
                relationship=outcome.relationship,  # type: ignore[arg-type]
                evidence_sufficiency=outcome.sufficiency,  # type: ignore[arg-type]
                applicability=outcome.applicability,  # type: ignore[arg-type]
                decision=outcome.action,  # type: ignore[arg-type]
                claim_refs=outcome.claim_refs,
                evidence=outcome.evidence,
                scope_differences=[],
                limitations=[
                    "R1 scoring; surface fixture"
                    if outcome.mode == "surface_heuristic"
                    else "Baseline scoring unit fixture"
                ],
                superseded_claim_ref=outcome.superseded_claim_ref,
                replacement_claim_ref=outcome.replacement_claim_ref,
            )
            validate_prediction(task, p)
        elif outcome.relationship != "unknown" or outcome.action in (
            "use_with_qualification",
            "set_aside",
        ):
            raise ValueError("A nonreasoning baseline cannot emit fake semantic findings")
        for sp in outcome.evidence:
            check_span(sp, {s.id: s for s in task.sources})


def _overlap_chars(a_start, a_end, b_start, b_end):
    return max(0, min(a_end, b_end) - max(a_start, b_start))


def citation_diagnostic(required: list[Span], cited: list[Span]):
    """Interpretable span precision/recall. Exact-match only; not entailment.

    Recall = required chars covered by any citation / total required chars.
    Precision = required chars covered / total cited chars (null if no citation).
    Overly broad citations achieve recall but low precision. Exact-string
    agreement alone cannot establish factual entailment; independent output
    adjudication remains required for semantic claims.
    """
    req_total = sum(r.end - r.start for r in required)
    cited_total = sum(c.end - c.start for c in cited)
    if not req_total:
        return {"recall": None, "precision": None, "required_chars": 0, "cited_chars": cited_total}
    covered = 0
    # per required char coverage (spans are small; brute force is fine)
    for r in required:
        for pos in range(r.start, r.end):
            for c in cited:
                if c.source_id == r.source_id and c.start <= pos < c.end:
                    covered += 1
                    break
    recall = covered / req_total if req_total else None
    precision = (covered / cited_total) if cited_total else None
    return {
        "recall": recall,
        "precision": precision,
        "required_chars": req_total,
        "cited_chars": cited_total,
        "covered_chars": covered,
    }


def score_r1(tasks, labels, outcomes, arm, *, allow_offline_fixtures=False):
    """R1 scoring with misleading-advance, non-use, and citation precision.

    Definitions (denominators explicit):
    - scored_tasks: authorized, annotated, applicable outcomes
      (refused/inapplicable/missing excluded).
    - useful_finding_retention = accepted substantive findings on useful gold / useful gold scored.
      (Semantic arms S/C/D only; lexical A uses useful_candidate_recall separately.)
    - misleading_advances: for S/C/D, unsupported substantive judgments (proposed relationship
      failing any acceptance check); for A, retain_candidate on non-useful or insufficient gold;
      for B/B0, 0 by construction (never advance). misleading_advance_rate = advances / scored.
    - correct_non_use = correct set_aside/abstain on non-useful gold (useful_finding=false):
      for S/C/D, accepted judgments with decision in gold decisions on non-useful; for A/B/B0,
      abstain or correct set_aside? A never set_asides/abstains usefully (always retains or abstains
      without semantics); counted as abstain on non-useful for B/B0,
      0 for A retains. Rate = correct / non-useful scored.
    - false_abstentions = abstain decisions on useful gold / useful gold scored.
    - category_accuracy: relationship match / scored, INCLUDING unknown/unknown as matches.
      category_accuracy_excluding_unknown_unknown reported separately; unknown matches do not
      count as substantive judgments.
    - sufficiency_accuracy: sufficiency match / scored.
    - unsupported_assertions = unsupported_substantive_judgments (S/C/D) or misleading retains (A).
    - citation precision/recall averaged over scored cases with required evidence.
    """
    # Accept both v1.4 Outcome and R1 Outcome; normalize to R1 for S support
    normed = []
    for o in outcomes:
        if isinstance(o, OutcomeR1):
            normed.append(o)
        else:
            normed.append(
                OutcomeR1(
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
    validate_outcomes_r1(tasks, normed, arm, allow_offline_fixtures=allow_offline_fixtures)
    gold = {a.task_id: a for a in labels if a.status != "pending"}
    by_id = {t.id: t for t in tasks}
    confusion, per_category = Counter(), {}
    useful = retained = candidate_retained = assertions = correct = unsupported = 0
    insufficient = abstained_insufficient = eligible = categories_correct = suff_correct = 0
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
        # unknown/unknown counts toward lenient accuracy, tracked separately
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
        is_semantic = output.mode in ("offline_scoring_fixture", "surface_heuristic")
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
        # correct non-use: accepted non-advancement on non-useful gold
        if not is_useful:
            if is_semantic:
                # accepted judgment (including correct
                # independent_observations set_aside) or correct
                # abstain on insufficient/unknown
                if judgment_ok and (assertion or output.action == "abstain"):
                    correct_non_use += 1
                elif output.action == "abstain" and annotation.sufficiency in (
                    "insufficient",
                    "unknown",
                ):
                    # abstain on insufficient/unknown without
                    # assertion: correct non-use only on full match.
                    # Lenient counting requires category/sufficiency
                    # match (unknown/unknown or unknown/insufficient).
                    if category_ok and output.sufficiency == annotation.sufficiency:
                        # Avoid double count (judgment_ok already
                        # false here); judgment_ok covers
                        # applicability, decisions, coverage.
                        # Non-matching stays non-counted (strict).
                        pass
            else:
                # lexical/integrity/constant: abstain on non-useful
                # counts; retain never counts as non-use
                if output.action == "abstain":
                    # B/B0 abstain on non-useful is correct non-use
                    # (even without semantics); A abstains rarely
                    correct_non_use += 1
        # misleading advances
        if is_semantic:
            misleading += bool(assertion and not judgment_ok)
        elif arm == "A":
            # lexical retains without semantics; retaining on non-useful
            # or insufficient is misleading advancement of a candidate
            if output.action == "retain_candidate" and (
                (not is_useful) or annotation.sufficiency == "insufficient"
            ):
                misleading += 1
        else:
            # B/B0 never advance
            pass
        # citation diagnostic (only when required evidence exists)
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
        "annotation_status": "PROVISIONAL_PUBLIC_DRAFT_LABELS_R1",
        "correct_substantive_judgments": correct,
        "substantive_judgments": assertions,
        "unsupported_substantive_judgments": unsupported,
        "unsupported_assertions": unsupported if arm in ("S", "C", "D") else misleading,
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
            "S/C/D: unsupported substantive judgments / scored; "
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


def evaluate_progress(metrics_by_arm: dict, thresholds: dict) -> dict:
    """Apply pre-registered R1 decision rule for future 03B arms.

    Comparators: A (lexical), B0 (always-abstain), S (surface-cue), C (general model, when run).
    Requires BOTH retention and false-advance conditions; no composite substitutes.
    Returns PROGRESS / NO_PROGRESS / INCONCLUSIVE with per-comparator verdicts.
    """

    def get(arm, key):
        return metrics_by_arm.get(arm, {}).get(key)

    results = {}
    # Thresholds file defines required deltas and caps; see decision_thresholds.json
    ret_min = thresholds.get("min_useful_retention", 0.5)
    mis_max = thresholds.get("max_misleading_advance_rate", 0.10)
    min_cases = thresholds.get("min_scored_cases", 30)
    for arm in ("C", "D"):
        m = metrics_by_arm.get(arm)
        if not m:
            results[arm] = {
                "verdict": "INCONCLUSIVE",
                "reason": "Arm not run (03A-R1 runs no inference).",
            }
            continue
        scored = m.get("scored_tasks", 0)
        if scored < min_cases:
            results[arm] = {
                "verdict": "INCONCLUSIVE",
                "reason": f"Only {scored} scored cases; need >={min_cases}.",
            }
            continue
        ret = m.get("useful_finding_retention")
        mis = m.get("misleading_advance_rate")
        if ret is None or mis is None:
            results[arm] = {
                "verdict": "INCONCLUSIVE",
                "reason": "Missing retention or misleading metric.",
            }
            continue
        # Compare vs controls (descriptive; thresholds are absolute,
        # justified against controls/sample size)
        cond_ret = ret >= ret_min
        cond_mis = mis <= mis_max
        if cond_ret and cond_mis:
            verdict = "PROGRESS"
        elif not cond_ret and not cond_mis:
            verdict = "NO_PROGRESS"
        elif not cond_ret:
            verdict = "NO_PROGRESS"
        else:
            verdict = "NO_PROGRESS"
        # INCONCLUSIVE if controls themselves insufficient? e.g., if S
        # already meets thresholds, require strict superiority?
        # Pre-registered: D must exceed S retention by margin and not exceed S misleading by margin.
        s_ret = get("S", "useful_finding_retention")
        s_mis = get("S", "misleading_advance_rate")
        margin = thresholds.get("margin_over_surface", 0.10)
        if s_ret is not None and ret < s_ret + margin:
            verdict = "NO_PROGRESS"
            reason = f"Retention {ret:.3f} does not exceed surface {s_ret:.3f} by {margin}."
        elif s_mis is not None and mis > s_mis + thresholds.get(
            "misleading_tolerance_over_surface", 0.05
        ):
            verdict = "NO_PROGRESS"
            reason = f"Misleading {mis:.3f} exceeds surface {s_mis:.3f} beyond tolerance."
        else:
            reason = f"Retention>={ret_min}={cond_ret}, misleading<={mis_max}={cond_mis}."
        results[arm] = {
            "verdict": verdict,
            "reason": reason,
            "retention": ret,
            "misleading": mis,
            "vs_surface_retention": s_ret,
            "vs_surface_misleading": s_mis,
        }
    return {
        "decision_rule": (
            "Both retention>=min and misleading<=max required; "
            "D must exceed S by margin; else NO_PROGRESS; "
            "insufficient evidence => INCONCLUSIVE."
        ),
        "thresholds": thresholds,
        "arms": results,
    }
