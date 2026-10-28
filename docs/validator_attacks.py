"""Adversarial cases against alive/claim_comparison.validate_claim (main cf8b3a9).
Texts are CONSTRUCTED to mimic observer capture (whitespace collapsed, nodes space-joined).
The utcnow strings approximate rendered Sphinx output and are UNVERIFIED against live HTML."""
from alive.claim_comparison import ClaimComparisonOutput as O, validate_claim as V

def run(name, rel, h, c, H, C, basis=None, aspect="status", scope="same", anchor=None, expect=None):
    out = O(relationship=rel, claim_aspect=aspect, historical_claim_quote=h, current_claim_quote=c,
            scope_alignment=scope, scope_note="n", supersession_basis_quote=basis,
            reason="r", limitations="l", confidence=0.5)
    p = {"historical_excerpt": H, "current_excerpt": C}
    if anchor is not None: p["reliance_anchor"] = anchor
    r = V(out, p)
    flag = "" if expect is None else ("OK " if r["decision"] == expect else "DEFECT")
    print(f"{flag:6} {name:52} -> {r['decision']:8} {r['relationship']:22} {r['reasons']}")

# 1. Headline case: 3.12 text is a strict superset of 3.11 (verified at .rst level).
BEH = "Return the current UTC date and time, with tzinfo None ."
H311 = "classmethod datetime. utcnow ( ) " + BEH + " This is like now() , but returns the current UTC date and time, as a naive datetime object."
DEP = "Deprecated since version 3.12: Use datetime.now() with UTC instead."
C312 = H311 + " " + DEP
run("utcnow golden (status supersession)", "explicit_supersession", BEH, DEP, H311, C312, basis=DEP, expect="accepted")
run("utcnow with heading-led excerpt boundary", "explicit_supersession", BEH, DEP, "x. " + BEH, C312, basis=DEP, expect="accepted")

# 2. Abbreviation boundary lets a quote shed a leading negation.
H = "Neither tool is approved; it is not true that, i.e. Caching improves recall."
run("i.e. boundary drops negation (supports)", "supports", "Caching improves recall.", "Caching improves recall in v2.",
    H, "Benchmarks show it. Caching improves recall in v2.", expect="rejected")

# 3. Truncated version number ends in '.' and passes.
C = "The interface is deprecated in version 3.12. It remains available."
run("quote truncated at '3.' accepted as sentence", "explicit_supersession", "The interface is recommended.",
    "The interface is deprecated in version 3.", "The interface is recommended.", C,
    basis="The interface is deprecated in version 3.", expect="rejected")

# 4. 'cannot' is not a negator.
run("asymmetric 'cannot' passes supports", "supports", "The parser cannot stream input.", "The parser streams input.",
    "The parser cannot stream input.", "The parser streams input.", expect="rejected")

# 5. Basis about a DIFFERENT entity on the same page.
C = "Return the local date and time. utcfromtimestamp() is deprecated since 3.12."
run("basis cites other method's deprecation", "explicit_supersession", "Return the current UTC time.",
    "Return the local date and time.", "Return the current UTC time.", C,
    basis="utcfromtimestamp() is deprecated since 3.12.", expect="demoted")

# 6. Negated marker.
C = "This option is not deprecated."
run("'not deprecated' counts as supersession", "explicit_supersession", "Use this option.", C,
    "Use this option.", C, basis=C, expect="demoted")

# 7. Marker in irrelevant sense.
C = "The codec uses error correction."
run("'error correction' counts as supersession", "explicit_supersession", "The codec is lossless.", C,
    "The codec is lossless.", C, basis=C, expect="demoted")

# 8. Supersession accepted on BEHAVIOUR aspect (the utcnow misreading).
H = "The method returns naive UTC time."; C = "The method is deprecated since 3.12."
run("explicit_supersession with aspect=behaviour", "explicit_supersession", H, C, H, C, basis=C,
    aspect="behaviour", expect="demoted")

# 9. Structured anchor (as C1B proposes) is always demoted.
run("structured dict anchor always demotes", "explicit_supersession", H, C, H, C, basis=C,
    anchor={"quote": H, "start": 0, "end": len(H)}, expect="accepted")

# 10. Quote occurs twice; only first occurrence checked.
H = "Caching improves recall. In practice it is not the case that caching improves recall."
run("duplicate occurrence: first-only boundary check", "supports", "Caching improves recall.", "Caching improves recall.x",
    H, "Caching improves recall.x", expect="rejected")

# 11. Empty explanation fields accepted.
out = O(relationship="qualifies", claim_aspect="other", historical_claim_quote="A b c.", current_claim_quote="D e f.",
        scope_alignment="different", scope_note="", supersession_basis_quote=None, reason="", limitations="", confidence=1.0)
r = V(out, {"historical_excerpt": "A b c.", "current_excerpt": "D e f."})
print(f"{'DEFECT' if r['decision']=='accepted' else 'OK':6} {'empty reason/limitations/scope_note accepted':52} -> {r['decision']}")

# 12. Bidi control char in quote.
q = "Use ‮emit‬ now."
run("bidi override chars accepted", "supports", q, "Use it now.", q, "Use it now.", expect="rejected")
