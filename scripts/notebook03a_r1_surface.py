"""Frozen surface-cue control (surface-cue-v1.0). Deterministic, offline, no model.

Implements inexpensive regex/phrase/overlap heuristics that succeed on v1.4
synthetic templates but fail on authentic paraphrases. Genuine executable
baseline, not a lookup table: no task IDs, families, splits, or gold labels
are referenced. Frozen before R1 holdout evaluation; see R1 design/report.
"""

import hashlib
import re

from scripts.notebook03a_r1_protocol import OutcomeR1, Span

VERSION = "surface-cue-v1.0"
# Frozen: 2026-10-29. Patterns derived from v1.4 development templates only.
# Do not tune on R1 holdout; any change requires new version + amendment.

RE_REPLACES = re.compile(r"\bexplicitly\s+replaces?\b|\breplaces?\s+policy\b", re.I)
RE_INDEPENDENT = re.compile(
    r"\bindependent\b.*\b(measured|observed|lab|team)\b|\blab\s+(one|two)\b", re.I
)
RE_DETECTED = re.compile(r"\bdetected\b", re.I)
RE_NOT_DETECTED = re.compile(r"\bdid\s+not\s+detect\b|\bnot\s+detected\b|\bno\s+benefit\b", re.I)
RE_FIFO_LRU = re.compile(r"\bagainst\s+(FIFO|LRU)\b|\bsynthetic\s+tasks\b|\bfield\s+tasks\b", re.I)
RE_CHARGE = re.compile(r"\bcharge\s+(cycles|filings)\b", re.I)
RE_BASELINE_OMIT = re.compile(r"\bomits?\s+the\s+baseline\b|\bwithout\s+stating\s+baseline\b", re.I)
RE_CALIBRATION = re.compile(
    r"\bcalibration\b.*\b(remains\s+valid|without\s+any\s+replacement|mentioned\s+without)\b", re.I
)
RE_MERCURY = re.compile(r"\bevery\b.*\bwater\s+batch\b.*\bfree\b|\bonly\s+batch\s+q\b", re.I)
RE_3DB = re.compile(r"\b3\s*dB\b|\b3-decibel\b", re.I)


def _tok(text):
    return set(re.findall(r"[a-z0-9]{3,}", text.lower()))


def _find_span(source, needle):
    """Exact substring span; raises if not found (caller must handle)."""
    s = source.text.find(needle)
    if s < 0:
        return None
    if len(needle) > 500:
        needle = needle[:500]
    return Span(source_id=source.id, start=s, end=s + len(needle), text=needle)


def _full_span(source, max_len=500):
    txt = source.text[:max_len]
    return Span(source_id=source.id, start=0, end=len(txt), text=txt)


def predict(task) -> OutcomeR1:
    """Deterministic surface heuristic. Never raises on authorized tasks; abstains when unsure."""
    denied = any(s.access != "fixture_authorized" for s in task.sources)
    if denied:
        return OutcomeR1(
            task_id=task.id,
            arm="S",
            mode="surface_heuristic",
            action="refuse",
            raw_policy=VERSION + ":access-refused",
        )
    texts = {s.id: s.text for s in task.sources}
    blob = " ".join(texts.values())
    blob_low = blob.lower()
    claim_ids = [c.id for c in task.claims]

    def out(rel, suff, appl, action, evidence, sup=None, rep=None, why=""):
        return OutcomeR1(
            task_id=task.id,
            arm="S",
            mode="surface_heuristic",
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

    def ev_for(sources):
        ev = []
        for s in sources:
            # cite full source up to 500 chars (imprecise by design;
            # precision diagnostic will penalize)
            ev.append(_full_span(s))
        return ev

    # Claim-support branch
    if task.kind == "claim_support":
        s0 = task.sources[0]
        if RE_MERCURY.search(s0.text) or ("every" in blob_low and "only batch" in blob_low):
            # universal vs single-batch -> unsupported
            m = re.search(r"Only batch Q[^.]*\.", s0.text)
            ev = [_find_span(s0, m.group(0)) if m else _full_span(s0)]
            ev = [e for e in ev if e]
            return out(
                "unsupported_claim",
                "sufficient_for_candidate",
                "not_applicable",
                "set_aside",
                ev,
                why="mercury-template",
            )
        if "proves" in blob_low and "not demonstrated" in blob_low.lower():
            m = re.search(r"NOT DEMONSTRATED[^\n]*|not evidence[^\n]*", s0.text, re.I)
            ev = [_find_span(s0, m.group(0)) if m else _full_span(s0)]
            ev = [e for e in ev if e]
            return out(
                "unsupported_claim",
                "sufficient_for_candidate",
                "not_applicable",
                "set_aside",
                ev,
                why="headline-denial",
            )
        if RE_BASELINE_OMIT.search(s0.text):
            return out("unknown", "insufficient", "unknown", "abstain", [], why="baseline-omit")
        # default: abstain (insufficient) when unsure
        return out("unknown", "insufficient", "unknown", "abstain", [], why="claim-default-abstain")

    # Pair branch
    assert len(task.sources) == 2
    s0, s1 = task.sources
    t0, t1 = s0.text, s1.text

    # Supersession: explicit replaces
    if RE_REPLACES.search(blob):
        # determine direction by which source contains replacement
        if "replaces" in t1.lower() or "replaces" in t0.lower():
            # find claim in replacement source vs other
            rep_source = s1 if "replaces" in t1.lower() else s0
            other = s0 if rep_source == s1 else s1
            # map to claim IDs via passage source
            rep_c = next(
                (c.id for c in task.claims if c.passage.source_id == rep_source.id), claim_ids[-1]
            )
            sup_c = next(
                (c.id for c in task.claims if c.passage.source_id == other.id), claim_ids[0]
            )
            return out(
                "supersession",
                "sufficient_for_candidate",
                "scoped",
                "use_with_qualification",
                ev_for([s0, s1]),
                sup=sup_c,
                rep=rep_c,
                why="replaces-keyword",
            )
    # Corroboration: independent + 3dB + chamber/protocol
    if RE_3DB.search(blob) and ("independent" in blob_low):
        # require both mention 3dB-ish and chamber?
        if "chamber" in blob_low and ("protocol" in blob_low or "procedure" in blob_low):
            return out(
                "corroboration_candidate",
                "sufficient_for_candidate",
                "applicable",
                "use_with_qualification",
                ev_for([s0, s1]),
                why="independent-3db",
            )
    # Contradiction: detected vs did-not-detect with same cohort/protocol tokens
    if (
        RE_DETECTED.search(t0)
        and RE_NOT_DETECTED.search(t1)
        or RE_DETECTED.search(t1)
        and RE_NOT_DETECTED.search(t0)
    ):
        # surface check: same cohort/protocol words?
        if "cohort p" in blob_low and "protocol z" in blob_low:
            return out(
                "contradiction_candidate",
                "sufficient_for_candidate",
                "applicable",
                "use_with_qualification",
                ev_for([s0, s1]),
                why="detected-negation",
            )
        # if cohorts/protocols differ, surface still predicts
        # contradiction (will be wrong on SC2) to demonstrate shortcut
        if "marker k" in blob_low:
            return out(
                "contradiction_candidate",
                "sufficient_for_candidate",
                "applicable",
                "use_with_qualification",
                ev_for([s0, s1]),
                why="detected-negation-surface",
            )
    # Scoped: FIFO/LRU + synthetic/field
    if RE_FIFO_LRU.search(blob) and ("reduced latency" in blob_low or "no benefit" in blob_low):
        return out(
            "scoped_change",
            "sufficient_for_candidate",
            "scoped",
            "use_with_qualification",
            ev_for([s0, s1]),
            why="fifo-lru-template",
        )
    # Independent: charge cycles vs filings
    if RE_CHARGE.search(blob) and (
        "battery" in blob_low and ("legal" in blob_low or "courthouse" in blob_low)
    ):
        return out(
            "independent_observations",
            "sufficient_for_candidate",
            "not_applicable",
            "set_aside",
            ev_for([s0, s1]),
            why="charge-template",
        )
    # Unknown date-only: calibration without replacement
    if RE_CALIBRATION.search(blob):
        return out("unknown", "insufficient", "unknown", "abstain", [], why="calibration-dateonly")
    # Lexical overlap fallback: high overlap -> substantive_connection, else independent?
    a, b = _tok(t0), _tok(t1)
    jac = len(a & b) / len(a | b) if (a | b) else 0
    if jac >= 0.35:
        return out(
            "substantive_connection",
            "sufficient_for_candidate",
            "scoped",
            "use_with_qualification",
            ev_for([s0, s1]),
            why=f"lexical-overlap-{jac:.2f}",
        )
    if jac <= 0.10:
        return out(
            "independent_observations",
            "sufficient_for_candidate",
            "not_applicable",
            "set_aside",
            ev_for([s0, s1]),
            why=f"lexical-disjoint-{jac:.2f}",
        )
    # unsure -> abstain
    return out("unknown", "insufficient", "unknown", "abstain", [], why=f"lexical-unsure-{jac:.2f}")


def implementation_hash() -> str:
    import pathlib

    p = pathlib.Path(__file__).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(p).hexdigest()
