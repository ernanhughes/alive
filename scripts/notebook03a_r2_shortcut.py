"""Shortcut-control family v2 (shortcut-control-v2.0). Offline, deterministic.

An honest, stronger surface baseline to replace surface-cue-v1.0 in R2
decisions. v1.0 is preserved byte-unchanged as historical evidence and
still replayed for regression comparison.

Design rules enforced by test:
- No task/family/split lookup, no gold access, no expected-answer table.
- No dependence on filenames, titles, or metadata.
- No branch written to fail a specific adversarial case on purpose:
  every rule must be justifiable as a reasonable shallow heuristic.
- Lexical matching, surface patterns, and small deterministic inference
  features only (entity overlap, comparator match, replacement language,
  negation, universal-quantifier vs limitation asymmetry).
- Thresholds tuned on the DEVELOPMENT split only, frozen before the
  public-evaluation run; parameters and code hash recorded in replay
  output before any blind evaluation.
"""

import hashlib
import re

from scripts.notebook03a_r2_protocol import OutcomeR2, Span

VERSION = "shortcut-control-v2.0"

# Frozen parameters. Tuned once on the 16-case development split (v1.4
# templates only), then frozen before the R1/R2 public-evaluation run.
# Rationale per parameter is recorded below; any change needs a new
# version plus a protocol amendment.
PARAMS = {
    "overlap_high": 0.30,  # Jaccard at/above -> substantive link candidate
    "overlap_low": 0.08,  # Jaccard at/below -> independent observations
    "max_cite_chars": 400,  # per-source citation cap (precision pressure)
    "dev_basis": "16 development cases, v1.4 templates; frozen pre-evaluation",
}

RE_REPLACE = re.compile(r"\b(replac\w*|supersed\w*|retire[sd]?|obsolet\w*|deprecat\w*)\b", re.I)
RE_POLICY_REF = re.compile(r"\bpolic\w+\s+\d+\b|\bpolicy\s+[a-z]\b", re.I)
RE_NEG = re.compile(
    r"\b(did\s+not|did\s+no|not\s+detect\w*|no\s+benefit|never|without|not\s+demonstrated)\b",
    re.I,
)
RE_POS_OUTCOME = re.compile(r"\b(detect\w+|reduc\w+.*latency|improv\w+|benefit|valid\b)\b", re.I)
RE_UNIVERSAL = re.compile(r"\b(every|all|always|never|proves|demonstrates?)\b", re.I)
RE_LIMIT = re.compile(
    r"\b(only\s+\w+\s+(was\s+)?sampled|not\s+detected\s+in\s+that|omits?\b|"
    r"without\s+\w+|not\s+demonstrated|not\s+evidence|remains\s+valid)\b",
    re.I,
)
RE_COMPARATOR = re.compile(
    r"\b(against\s+\w+|synthetic|field|fifo|lru|baseline|comparator|corpus|"
    r"protocol\s+\w+|cohort\s+\w+|chamber\s+\w+|procedure\s+\w+)\b",
    re.I,
)
RE_CONDITION = RE_COMPARATOR
RE_INDEPENDENT_SRC = re.compile(
    r"\b(independent|different\s+(lab|team)|two\s+labs|separate)\b", re.I
)
RE_CALIB = re.compile(r"\bcalibration\b", re.I)


def _tok(text):
    return set(re.findall(r"[a-z0-9]{3,}", text.lower()))


def _entities(text):
    return set(re.findall(r"\b[A-Z][a-zA-Z]+\b", text))


def _jaccard(a, b):
    return len(a & b) / len(a | b) if (a | b) else 0.0


def _cite(source, start, end):
    text = source.text[start:end][: PARAMS["max_cite_chars"]]
    return Span(source_id=source.id, start=start, end=start + len(text), text=text)


def _cite_head(source, needle=None):
    if needle:
        start = source.text.find(needle)
        if start >= 0:
            return _cite(source, start, start + len(needle))
    return _cite(source, 0, min(len(source.text), PARAMS["max_cite_chars"]))


def _cite_around(source, pos, before=150, after=250):
    """Cite the window around the phrase the rule actually matched.

    The control cites what it looked at: the triggering phrase plus
    bounded context. This is honest localization, not gold knowledge.
    """
    start = max(0, pos - before)
    end = min(len(source.text), pos + after)
    return _cite(source, start, end)


def _cite_match(source, pattern):
    match = pattern.search(source.text)
    if match is None:
        return _cite_head(source)
    return _cite_around(source, match.start())


def _cite_polarity(source):
    for pattern in (RE_NEG, RE_POS_OUTCOME):
        match = pattern.search(source.text)
        if match is not None:
            return _cite_around(source, match.start())
    return _cite_head(source)


def predict(task) -> OutcomeR2:
    """Deterministic honest heuristic. Abstains when evidence is thin."""
    denied = any(s.access != "fixture_authorized" for s in task.sources)
    if denied:
        return OutcomeR2(
            task_id=task.id,
            arm="V",
            mode="shortcut_v2",
            action="refuse",
            raw_policy=VERSION + ":access-refused",
        )
    claim_ids = [c.id for c in task.claims]

    def out(rel, suff, appl, action, evidence, sup=None, rep=None, why=""):
        return OutcomeR2(
            task_id=task.id,
            arm="V",
            mode="shortcut_v2",
            action=action,
            relationship=rel,
            sufficiency=suff,
            applicability=appl,
            evidence=evidence,
            claim_refs=claim_ids,
            raw_policy=VERSION + ":" + why,
            superseded_claim_ref=sup,
            replacement_claim_ref=rep,
        )

    if task.kind == "claim_support":
        s0 = task.sources[0]
        claim_text = task.claims[0].passage.text
        universal = RE_UNIVERSAL.search(claim_text) is not None
        limit = _cite_match(s0, RE_LIMIT) if RE_LIMIT.search(s0.text) else None
        if universal and limit is not None:
            return out(
                "unsupported_claim",
                "sufficient_for_candidate",
                "not_applicable",
                "set_aside",
                [limit],
                why="universal-vs-limitation",
            )
        if RE_LIMIT.search(s0.text) and not universal:
            return out(
                "unknown",
                "insufficient",
                "unknown",
                "abstain",
                [],
                why="qualified-single-observation",
            )
        return out(
            "unknown", "insufficient", "unknown", "abstain", [], why="single-default-abstain"
        )

    s0, s1 = task.sources
    t0, t1 = s0.text, s1.text
    tok0, tok1 = _tok(t0), _tok(t1)
    jac = _jaccard(tok0, tok1)
    ent = _entities(t0) & _entities(t1)
    cond0, cond1 = set(RE_CONDITION.findall(t0.lower())), set(RE_CONDITION.findall(t1.lower()))
    cond_overlap = bool(cond0 & cond1)

    # 1. Explicit replacement of a referenced item -> supersession.
    if RE_REPLACE.search(t0 + " " + t1) and (RE_POLICY_REF.search(t0) or RE_POLICY_REF.search(t1)):
        rep_source = s1 if RE_REPLACE.search(t1) else s0
        other = s0 if rep_source is s1 else s1
        rep_c = next(
            (c.id for c in task.claims if c.passage.source_id == rep_source.id),
            claim_ids[-1],
        )
        sup_c = next((c.id for c in task.claims if c.passage.source_id == other.id), claim_ids[0])
        return out(
            "supersession",
            "sufficient_for_candidate",
            "scoped",
            "use_with_qualification",
            [_cite_match(s0, RE_REPLACE), _cite_match(s1, RE_REPLACE)],
            sup=sup_c,
            rep=rep_c,
            why="replacement-language",
        )

    # 2. Calibration-style later mention without replacement language.
    # Specific beats general: date-only discussion is checked before
    # outcome-polarity heuristics so a bare later mention can never be
    # upgraded to a scoped or contradiction finding.
    if RE_CALIB.search(t0 + " " + t1) and not RE_REPLACE.search(t0 + " " + t1):
        return out(
            "unknown", "insufficient", "unknown", "abstain", [], why="date-only-no-replacement"
        )

    # 3. Opposite outcome language under shared entities and shared
    # conditions -> contradiction candidate. Differing *stated* conditions
    # -> scoped change. Without stated conditions on either side there is
    # nothing to scope, so fall through (honest rule: never assert
    # contradiction across mismatched conditions, never invent scope).
    neg0, neg1 = RE_NEG.search(t0) is not None, RE_NEG.search(t1) is not None
    pos0, pos1 = RE_POS_OUTCOME.search(t0) is not None, RE_POS_OUTCOME.search(t1) is not None
    if (neg0 != neg1 or pos0 != pos1) and ent:
        if cond_overlap:
            return out(
                "contradiction_candidate",
                "sufficient_for_candidate",
                "applicable",
                "use_with_qualification",
                [_cite_polarity(s0), _cite_polarity(s1)],
                why="opposite-outcome-shared-conditions",
            )
        if cond0 or cond1:
            return out(
                "scoped_change",
                "sufficient_for_candidate",
                "scoped",
                "use_with_qualification",
                [_cite_polarity(s0), _cite_polarity(s1)],
                why="opposite-outcome-different-conditions",
            )

    # 4. Matching outcome language under shared entities and conditions,
    # with an explicit independence cue, -> corroboration candidate.
    # Corroboration means independent evidence by definition, so a
    # same-origin restatement without such a cue falls through instead
    # of being miscounted as corroboration.
    if (
        ent
        and cond_overlap
        and jac >= PARAMS["overlap_high"]
        and not (neg0 != neg1)
        and RE_INDEPENDENT_SRC.search(t0 + " " + t1)
    ):
        return out(
            "corroboration_candidate",
            "sufficient_for_candidate",
            "applicable",
            "use_with_qualification",
            [_cite_match(s0, RE_INDEPENDENT_SRC), _cite_match(s1, RE_INDEPENDENT_SRC)],
            why="matching-outcome-shared-conditions",
        )

    # 5. Different-condition comparisons with shared vocabulary -> scoped.
    if RE_COMPARATOR.search(t0 + " " + t1) and ent:
        return out(
            "scoped_change",
            "sufficient_for_candidate",
            "scoped",
            "use_with_qualification",
            [_cite_match(s0, RE_COMPARATOR), _cite_match(s1, RE_COMPARATOR)],
            why="comparator-vocabulary",
        )

    # 6. Lexical overlap fallback with entity support.
    if jac >= PARAMS["overlap_high"] and ent:
        return out(
            "substantive_connection",
            "sufficient_for_candidate",
            "scoped",
            "use_with_qualification",
            [_cite_head(s0), _cite_head(s1)],
            why=f"overlap-with-entities-{jac:.2f}",
        )
    if jac <= PARAMS["overlap_low"]:
        return out(
            "independent_observations",
            "sufficient_for_candidate",
            "not_applicable",
            "set_aside",
            [_cite_head(s0), _cite_head(s1)],
            why=f"lexical-disjoint-{jac:.2f}",
        )
    return out("unknown", "insufficient", "unknown", "abstain", [], why=f"thin-evidence-{jac:.2f}")


def implementation_record():
    """Version, parameters, and code hash recorded before blind evaluation."""
    return {
        "version": VERSION,
        "params": dict(PARAMS),
        "code_sha256": implementation_hash(),
    }


def implementation_hash():
    import pathlib

    path = pathlib.Path(__file__).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(path).hexdigest()
