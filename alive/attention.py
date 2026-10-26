"""Transparent attention policy v1. No model controls scores or resource ceilings."""

import hashlib
import re


def redact(text):
    text = re.sub(
        r"(?i)(bearer\s+|(?:api[_ -]?key|password|token)\s*[:=]\s*)\S+", r"\1[REDACTED]", str(text)
    )
    return re.sub(r"\bLLM_[A-Za-z0-9_]+", "[REDACTED]", text)[:8000]


def words(text):
    generic = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "this",
        "that",
        "into",
        "within",
        "verify",
        "investigate",
        "investigation",
        "novel",
        "observation",
        "observations",
        "research",
        "environment",
        "habitat",
        "controlled",
        "evidence",
        "analysis",
        "goal",
        "objective",
        "change",
        "changed",
        "new",
        "waiting",
        "quiet",
        "follow",
        "propose",
        "recorded",
        "local",
        "draft",
        "bounds",
        "observe",
        "form",
        "alive",
        "world",
        "cognitive",
        "laboratory",
        "loading",
        "sensor",
    }
    return set(re.findall(r"[a-z]{3,}", text.lower())) - generic


def claims_from_text(text):
    return [
        {
            "subject": m[0].strip(),
            "predicate": m[1].strip(),
            "value": m[2].strip(),
            "evidence_refs": [],
        }
        for m in re.findall(r"Claim:\s*([^|;]{1,100})\|\s*([^|;]{1,100})\|\s*([^|;]{1,200});", text)
    ][:4]


def attention(text, topics, previous=None, *, accepted=False, age_seconds=0):
    relevant = words(text) & words(" ".join(topics))
    relevance = min(1, len(relevant) / 2)
    if accepted:
        relevance = 1.0
    novelty = (
        1
        if not previous
        else 1 - len(words(text) & words(previous)) / max(1, len(words(text) | words(previous)))
    )
    # Numeric fact changes are meaningful even when almost all surrounding words are unchanged.
    if previous and claims_from_text(text) != claims_from_text(previous) and claims_from_text(text):
        novelty = max(novelty, 0.8)
    urgency = min(1, 0.3 + age_seconds / 300) if accepted else 0.2
    benefit, cost, uncertainty = relevance, 0.2, 0.6 if claims_from_text(text) else 0.3
    score = max(
        0,
        min(
            1,
            0.25 * relevance
            + 0.2 * urgency
            + 0.25 * benefit
            + 0.2 * novelty
            + 0.1 * uncertainty
            - 0.2 * cost,
        ),
    )
    return {
        "score": round(score, 4),
        "novelty": round(novelty, 4),
        "relevance": relevance,
        "urgency": urgency,
        "benefit": benefit,
        "cost": cost,
        "uncertainty": uncertainty,
        "matched_terms": sorted(relevant),
        "policy": "attention-v1",
        "explanation": "0.25 relevance + 0.20 urgency + 0.25 benefit + "
        "0.20 novelty + 0.10 uncertainty - 0.20 cost",
        "required_capabilities": ["structured_text"],
        "required_permissions": ["internal_analysis"],
    }


def fingerprint(instance_id, url, text):
    return hashlib.sha256(f"{instance_id}|{url}|{text.strip().lower()}".encode()).hexdigest()


def rank(candidates, current_time=None):
    from datetime import UTC

    def key(candidate):
        created = candidate["created_at"]
        commitment = candidate.get("provenance", {}).get("source_type") == "commitment"
        if current_time is not None and commitment:
            timestamp = created if created.tzinfo else created.replace(tzinfo=UTC)
            if (current_time - timestamp).total_seconds() >= 60:
                return (0, 0, created, candidate["id"])
        return (1, -candidate["attention"]["score"], created, candidate["id"])

    return sorted(candidates, key=key)
