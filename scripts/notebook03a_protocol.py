"""Offline Notebook-03A schemas, provenance/leakage gates and scoring. No model client."""

import hashlib
import json
import math
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "evaluations/notebook03a"
Relation = Literal[
    "substantive_connection",
    "corroboration_candidate",
    "contradiction_candidate",
    "supersession",
    "scoped_change",
    "independent_observations",
    "unsupported_claim",
    "unknown",
]
Sufficiency = Literal["sufficient_for_candidate", "insufficient", "unknown"]
Applicability = Literal["applicable", "scoped", "not_applicable", "unknown"]
Decision = Literal["use_with_qualification", "set_aside", "abstain"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Span(Strict):
    source_id: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=500)


class Source(Strict):
    id: str
    text: str = Field(min_length=10, max_length=2000)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    access: Literal["fixture_authorized", "withdrawn", "unauthorized"] = "fixture_authorized"
    untrusted_title: str = Field(max_length=200)


class Claim(Strict):
    id: str
    role: Literal["current", "historical", "presented"]
    passage: Span
    proposition: str | None = None
    qualifiers: list[str] = Field(default_factory=list)
    version_context: str | None = None
    temporal_context: str | None = None
    system_context: str | None = None


class Task(Strict):
    id: str = Field(pattern=r"^[0-9a-f]{16}$")
    family: str = Field(pattern=r"^[0-9a-f]{16}$")
    split: Literal["development", "public_evaluation", "independent_heldout"]
    kind: Literal["pair", "claim_support"]
    question: str = Field(min_length=10, max_length=500)
    claims: list[Claim] = Field(min_length=1, max_length=2)
    sources: list[Source] = Field(min_length=1, max_length=2)
    supporting_passages: list[Span] = Field(default_factory=list)

    @model_validator(mode="after")
    def bindings(self):
        sources = {s.id: s for s in self.sources}
        if len(sources) != len(self.sources) or len({c.id for c in self.claims}) != len(
            self.claims
        ):
            raise ValueError("Duplicate local source/claim identity")
        for source in self.sources:
            if digest(source.text) != source.sha256:
                raise ValueError("Source excerpt hash mismatch")
        for span in [c.passage for c in self.claims] + self.supporting_passages:
            check_span(span, sources)
        roles = {c.role for c in self.claims}
        if self.kind == "pair" and (len(self.claims) != 2 or roles != {"current", "historical"}):
            raise ValueError("Pair requires identifiable current and historical claims")
        if self.kind == "claim_support" and (len(self.claims) != 1 or roles != {"presented"}):
            raise ValueError("Claim-support requires one presented claim")
        if self.kind == "pair" and len({c.passage.source_id for c in self.claims}) != 2:
            raise ValueError("Pair baseline requires two source captures")
        return self


class Annotation(Strict):
    task_id: str
    status: Literal["draft", "adjudicated", "pending"]
    author: str = Field(min_length=1)
    independence: Literal["implementer_authored", "external_attested"]
    reviewers: list[str] = Field(default_factory=list)
    relationships: list[Relation] = Field(min_length=1)
    sufficiency: Sufficiency
    applicability: Applicability
    decisions: list[Decision] = Field(min_length=1)
    useful_finding: bool
    rationale: str = Field(min_length=10)
    required_evidence: list[Span]
    forbidden_conclusions: list[str] = Field(min_length=1)
    ambiguity_notes: str | None = None
    superseded_claim_ref: str | None = None
    replacement_claim_ref: str | None = None

    @model_validator(mode="after")
    def coherent(self):
        if len(set(self.relationships)) != len(self.relationships):
            raise ValueError("Duplicate accepted relationship")
        if self.sufficiency != "sufficient_for_candidate" and (
            self.relationships != ["unknown"]
            or self.decisions != ["abstain"]
            or self.useful_finding
        ):
            raise ValueError(
                "Unknown/insufficient evidence cannot prescribe a substantive judgment"
            )
        if self.sufficiency == "sufficient_for_candidate" and not self.required_evidence:
            raise ValueError("Sufficient annotations need required supporting evidence")
        if self.useful_finding and self.decisions == ["abstain"]:
            raise ValueError("Useful finding cannot be rewarded only for abstention")
        if len(self.relationships) > 1 and not self.ambiguity_notes:
            raise ValueError("Multiple accepted categories need explicit ambiguity notes")
        if self.independence == "external_attested" and (
            self.status != "adjudicated"
            or len(set(self.reviewers)) < 2
            or self.author in self.reviewers
        ):
            raise ValueError("External adjudication needs distinct reviewer attestations")
        return self


class Prediction(Strict):
    """Proposed 03B model output schema only; no dispatch/admission implementation."""

    relationship: Relation
    evidence_sufficiency: Sufficiency
    applicability: Applicability
    decision: Decision
    claim_refs: list[str] = Field(min_length=1)
    evidence: list[Span]
    scope_differences: list[str]
    limitations: list[str] = Field(min_length=1)
    review_required: Literal[True] = True
    superseded_claim_ref: str | None = None
    replacement_claim_ref: str | None = None

    @model_validator(mode="after")
    def uncertain(self):
        if self.relationship == "unknown" and self.decision != "abstain":
            raise ValueError(
                "An unknown relation cannot authorize use or a substantive non-use claim"
            )
        if self.evidence_sufficiency != "sufficient_for_candidate" and (
            self.relationship != "unknown" or self.decision != "abstain"
        ):
            raise ValueError("Insufficient evidence requires explicit uncertainty")
        return self


class Outcome(Strict):
    task_id: str
    arm: Literal["A", "B", "B0", "C", "D"]
    mode: Literal["lexical", "integrity", "constant_control", "offline_scoring_fixture"]
    action: Literal[
        "retain_candidate",
        "use_with_qualification",
        "set_aside",
        "abstain",
        "refuse",
        "not_applicable",
    ]
    relationship: Relation = "unknown"
    sufficiency: Sufficiency = "unknown"
    applicability: Applicability = "unknown"
    evidence: list[Span] = Field(default_factory=list)
    claim_refs: list[str] = Field(default_factory=list)
    raw_policy: str
    superseded_claim_ref: str | None = None
    replacement_claim_ref: str | None = None


class Exposure(Strict):
    set_id: str
    custodian: str
    access_restricted_attested: bool
    implementer_exposure_events: list[str]
    independent_annotation_status: Literal["PENDING_INDEPENDENT_LABELING", "ADJUDICATED"]
    inputs_sha256: str | None = Field(pattern=r"^[0-9a-f]{64}$")
    gold_sha256: str | None = Field(pattern=r"^[0-9a-f]{64}$")
    target_cases: int = Field(ge=1)

    @property
    def blind_eligible(self):
        return (
            self.access_restricted_attested
            and not self.implementer_exposure_events
            and self.independent_annotation_status == "ADJUDICATED"
            and self.inputs_sha256 is not None
            and self.gold_sha256 is not None
        )


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def check_span(span, sources):
    source = sources.get(span.source_id)
    if source is None or span.end > len(source.text) or span.start >= span.end:
        raise ValueError("Unknown source or invalid quote offsets")
    if source.text[span.start : span.end] != span.text:
        raise ValueError("Quotation is not exact at the supplied source offsets")


def prepare_payload(task):
    """No gold, provenance labels, case ID, split or family can enter this whitelist."""
    if any(s.access != "fixture_authorized" for s in task.sources):
        raise PermissionError("Evidence unavailable")
    payload = {
        "contract_version": "notebook03-claim-input-v1",
        "question": task.question,
        "task_kind": task.kind,
        "claims": [
            {
                "id": c.id,
                "role": c.role,
                "passage": c.passage.model_dump(),
                "version_context": c.version_context,
                "temporal_context": c.temporal_context,
                "system_context": c.system_context,
            }
            for c in task.claims
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


def validate_prediction(task, prediction):
    if any(s.access != "fixture_authorized" for s in task.sources):
        raise PermissionError("No prediction may expose unavailable evidence")
    ids = {c.id for c in task.claims}
    if set(prediction.claim_refs) != ids:
        raise ValueError("Missing or unsupported claim reference")
    if prediction.relationship == "supersession":
        if (
            prediction.superseded_claim_ref not in ids
            or prediction.replacement_claim_ref not in ids
            or prediction.superseded_claim_ref == prediction.replacement_claim_ref
        ):
            raise ValueError("Supersession requires an explicit directed claim replacement")
    elif (
        prediction.superseded_claim_ref is not None or prediction.replacement_claim_ref is not None
    ):
        raise ValueError("Replacement direction is only meaningful for supersession")
    for span in prediction.evidence:
        check_span(span, {s.id: s for s in task.sources})
    if prediction.relationship != "unknown" and not prediction.evidence:
        raise ValueError("A relationship proposal needs inspectable exact citations")
    # This proves citation consistency only, never semantic entailment or owner consent.
    return True


def validate_corpus(tasks, labels, origins, *, public=True):
    ids = {t.id for t in tasks}
    if len(ids) != len(tasks) or len({a.task_id for a in labels}) != len(labels):
        raise ValueError("Duplicate task or annotation identity")
    if set(origins) != ids or set(a.task_id for a in labels) - ids:
        raise ValueError("Orphan provenance or unsupported annotation reference")
    families, sources_seen = {}, {}
    for task in tasks:
        if public and task.split == "independent_heldout":
            raise ValueError("A repo-accessible task is not a blind independent holdout")
        prior = families.setdefault(task.family, task.split)
        if prior != task.split:
            raise ValueError("Related task family crosses splits")
        for source in task.sources:
            seen = sources_seen.setdefault(source.sha256, task.split)
            if seen != task.split:
                raise ValueError("Duplicate source text crosses splits")
        entries = origins[task.id]
        if set(entries) != {s.id for s in task.sources}:
            raise ValueError("Incomplete source provenance")
        for source in task.sources:
            origin = entries[source.id]
            if set(origin) != {
                "kind",
                "document",
                "commit",
                "document_sha256",
                "quote",
                "start",
                "note",
            }:
                raise ValueError("Malformed source provenance")
            if origin["kind"] not in ("authentic", "controlled", "synthetic"):
                raise ValueError("Unknown provenance kind")
            if origin["kind"] in ("authentic", "controlled"):
                path, commit = origin["document"], origin["commit"]
                if not isinstance(path, str) or not re.fullmatch(r"docs/[A-Za-z0-9_-]+\.md", path):
                    raise ValueError("Source reference must name a canonical docs file")
                if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
                    raise ValueError("Source reference must pin a Git object")
                text = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{commit}:{path}"])
                text = text.replace(b"\r\n", b"\n").decode("utf-8")
                if digest(text) != origin["document_sha256"]:
                    raise ValueError("Pinned document hash mismatch")
                start, quote = origin["start"], origin["quote"]
                if (
                    not isinstance(start, int)
                    or start < 0
                    or text[start : start + len(quote)] != quote
                ):
                    raise ValueError("Pinned source quote does not exist")
                if origin["kind"] == "authentic" and source.text != quote:
                    raise ValueError("Authentic excerpt is not verbatim")
                if origin["kind"] == "controlled" and (
                    not origin["note"] or quote not in source.text
                ):
                    raise ValueError(
                        "Controlled perturbation needs retained source evidence and note"
                    )
            elif any(
                origin[k] is not None
                for k in ("document", "commit", "document_sha256", "quote", "start")
            ):
                raise ValueError("Synthetic material must not masquerade as a canonical source")
    by_id = {t.id: t for t in tasks}
    for annotation in labels:
        task = by_id[annotation.task_id]
        if public and annotation.independence != "implementer_authored":
            raise ValueError("Public repo labels cannot be claimed as a blind independent holdout")
        claim_ids = {c.id for c in task.claims}
        if "supersession" in annotation.relationships:
            if (
                annotation.superseded_claim_ref not in claim_ids
                or annotation.replacement_claim_ref not in claim_ids
                or annotation.superseded_claim_ref == annotation.replacement_claim_ref
            ):
                raise ValueError("Supersession annotation needs directed claim identities")
        elif (
            annotation.superseded_claim_ref is not None
            or annotation.replacement_claim_ref is not None
        ):
            raise ValueError("Unexpected supersession annotation direction")
        for span in annotation.required_evidence:
            check_span(span, {s.id: s for s in task.sources})
    missing = sorted(ids - {a.task_id for a in labels if a.status != "pending"})
    return {
        "status": "INCOMPLETE" if missing else "PUBLIC_COMPLETE",
        "cases": len(tasks),
        "missing_or_pending_annotations": missing,
        "splits": dict(Counter(t.split for t in tasks)),
        "categories": dict(Counter(r for a in labels for r in a.relationships)),
        "annotation_independence": "IMPLEMENTER_EXPOSED; NOT BLIND",
    }


def validate_outcomes(tasks, outcomes, arm, *, allow_offline_fixtures=False):
    by_id = {t.id: t for t in tasks}
    if len(outcomes) != len(tasks) or {o.task_id for o in outcomes} != set(by_id):
        raise ValueError("Exactly one recorded outcome per task is required")
    if len({o.task_id for o in outcomes}) != len(outcomes) or any(o.arm != arm for o in outcomes):
        raise ValueError("Duplicate result or mixed-arm result set")
    for outcome in outcomes:
        task = by_id[outcome.task_id]
        expected_mode = {
            "A": "lexical",
            "B": "integrity",
            "B0": "constant_control",
            "C": "offline_scoring_fixture",
            "D": "offline_scoring_fixture",
        }[arm]
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
        if outcome.mode == "offline_scoring_fixture":
            if not allow_offline_fixtures:
                raise PermissionError(
                    "03A has no model execution or verified-consent admission path"
                )
            p = Prediction(
                relationship=outcome.relationship,
                evidence_sufficiency=outcome.sufficiency,
                applicability=outcome.applicability,
                decision=outcome.action,
                claim_refs=outcome.claim_refs,
                evidence=outcome.evidence,
                scope_differences=[],
                limitations=["Offline scoring unit fixture"],
                superseded_claim_ref=outcome.superseded_claim_ref,
                replacement_claim_ref=outcome.replacement_claim_ref,
            )
            validate_prediction(task, p)
        elif outcome.relationship != "unknown" or outcome.action in (
            "use_with_qualification",
            "set_aside",
        ):
            raise ValueError("A nonreasoning baseline cannot emit fake semantic findings")
        for span in outcome.evidence:
            check_span(span, {s.id: s for s in task.sources})


def ratio(n, d):
    return n / d if d else None


def wilson(n, d):
    if not d:
        return None
    z = 1.96
    center = (n / d + z * z / (2 * d)) / (1 + z * z / d)
    radius = z * math.sqrt(n / d * (1 - n / d) / d + z * z / (4 * d * d)) / (1 + z * z / d)
    return [max(0, center - radius), min(1, center + radius)]


def score(tasks, labels, outcomes, arm, *, allow_offline_fixtures=False):
    validate_outcomes(tasks, outcomes, arm, allow_offline_fixtures=allow_offline_fixtures)
    gold = {a.task_id: a for a in labels if a.status != "pending"}
    by_id = {t.id: t for t in tasks}
    confusion, per_category = Counter(), {}
    useful = retained = candidate_retained = assertions = correct = unsupported = 0
    insufficient = abstained_insufficient = eligible = categories_correct = suff_correct = 0
    unscored = inapplicable = refused = 0
    decisions = Counter()
    for output in outcomes:
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
        useful += annotation.useful_finding
        insufficient += annotation.sufficiency == "insufficient"
        abstained_insufficient += (
            annotation.sufficiency == "insufficient" and output.action == "abstain"
        )
        category_ok = output.relationship in annotation.relationships
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
        assertion = output.mode == "offline_scoring_fixture" and output.relationship != "unknown"
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
        retained += bool(annotation.useful_finding and judgment_ok and assertion)
        candidate_retained += bool(
            annotation.useful_finding and output.action == "retain_candidate"
        )
        for category in annotation.relationships:
            row = per_category.setdefault(
                category,
                {"cases": 0, "category_correct": 0, "useful_findings": 0, "useful_retained": 0},
            )
            row["cases"] += 1
            row["category_correct"] += category_ok
            row["useful_findings"] += annotation.useful_finding
            row["useful_retained"] += bool(annotation.useful_finding and judgment_ok and assertion)
    return {
        "arm": arm,
        "total_tasks": len(tasks),
        "scored_tasks": eligible,
        "unscored_missing_annotations": unscored,
        "not_applicable": inapplicable,
        "access_refused": refused,
        "annotation_status": "PROVISIONAL_PUBLIC_DRAFT_LABELS",
        "correct_substantive_judgments": correct,
        "substantive_judgments": assertions,
        "unsupported_substantive_judgments": unsupported,
        "substantive_precision": ratio(correct, assertions),
        "category_accuracy": ratio(categories_correct, eligible),
        "sufficiency_accuracy": ratio(suff_correct, eligible),
        "useful_findings": useful,
        "useful_findings_retained": retained,
        "useful_finding_retention": ratio(retained, useful),
        "missed_useful_findings": useful - retained,
        "useful_candidates_retained": candidate_retained,
        "useful_candidate_recall": ratio(candidate_retained, useful),
        "insufficient_cases": insufficient,
        "correct_insufficient_abstention": abstained_insufficient,
        "correct_insufficient_abstention_rate": ratio(abstained_insufficient, insufficient),
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


def load_corpus(directory=CORPUS):
    def read(name):
        return json.loads((directory / name).read_text(encoding="utf-8"))

    return (
        [Task.model_validate(t) for t in read("tasks.json")],
        [Annotation.model_validate(a) for a in read("annotations.json")],
        read("origins.json"),
    )


def verify_freeze(directory=CORPUS):
    protocol = json.loads((directory / "protocol.json").read_text(encoding="utf-8"))
    actual_files = {f.name for f in directory.glob("*.json") if f.name != "protocol.json"}
    if actual_files != set(protocol["files_sha256"]):
        raise ValueError("Frozen file inventory changed")
    for name, wanted in protocol["files_sha256"].items():
        if not re.fullmatch(r"[a-z_]+\.json", name) or file_digest(directory / name) != wanted:
            raise ValueError("Frozen file drift: " + name)
    for name, wanted in protocol.get("tools_sha256", {}).items():
        if name not in ("scripts/notebook03a.py", "scripts/notebook03a_protocol.py"):
            raise ValueError("Unsupported frozen tool reference")
        if file_digest(ROOT / name) != wanted:
            raise ValueError("Frozen tool contract drift: " + name)
    return protocol
