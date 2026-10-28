"""Pinned synthetic claim fixtures; never evidence about a real product.

Available only through the explicitly enabled local test provider.
Keys are (full current-source SHA256, full historical-source SHA256).
Changing even one source character must fail closed.
"""

HISTORICAL_TEXT = "The fixture interface is recommended for all clients."
CURRENT_TEXTS = {
    "conflicts": "The fixture interface is not recommended for any clients.",
    "qualifies": "The fixture interface is recommended only for local clients.",
    "explicit_supersession": "The fixture interface is deprecated in version 3.12.",
    "supports": "The fixture interface is recommended for all clients.",
}

CLAIM_FIXTURES = {
    (
        "61dadcae7a519f7ac05a3eb67838959d48051f7091251249cf928dcd2cce3a6e",
        "ad52164c4d1e38eb4cf1c7170bd4e8de3a8c6f4772fcb3d5e9af0c38eb5021fe",
    ): {
        "relationship": "conflicts",
        "claim_aspect": "recommendation",
        "historical_claim_quote": "The fixture interface is recommended for all clients.",
        "current_claim_quote": "The fixture interface is not recommended for any clients.",
        "scope_alignment": "same",
        "scope_note": "Same synthetic fixture interface.",
        "supersession_basis_quote": None,
        "reason": "A pinned synthetic source comparison.",
        "limitations": "Synthetic test data; no independent factual verification.",
        "confidence": 0.4,
    },
    (
        "71a85534c339030ae50f6df88c7ccc7a3503b54dcad67850c6f49579fb9a89de",
        "ad52164c4d1e38eb4cf1c7170bd4e8de3a8c6f4772fcb3d5e9af0c38eb5021fe",
    ): {
        "relationship": "qualifies",
        "claim_aspect": "recommendation",
        "historical_claim_quote": "The fixture interface is recommended for all clients.",
        "current_claim_quote": "The fixture interface is recommended only for local clients.",
        "scope_alignment": "same",
        "scope_note": "Same synthetic fixture interface.",
        "supersession_basis_quote": None,
        "reason": "A pinned synthetic source comparison.",
        "limitations": "Synthetic test data; no independent factual verification.",
        "confidence": 0.4,
    },
    (
        "bda769d11aaea4130322715f5d24dc6e3a59a48dbf80a4e2263f2890a94d2252",
        "ad52164c4d1e38eb4cf1c7170bd4e8de3a8c6f4772fcb3d5e9af0c38eb5021fe",
    ): {
        "relationship": "explicit_supersession",
        "claim_aspect": "status",
        "historical_claim_quote": "The fixture interface is recommended for all clients.",
        "current_claim_quote": "The fixture interface is deprecated in version 3.12.",
        "scope_alignment": "same",
        "scope_note": "Same synthetic fixture interface.",
        "supersession_basis_quote": "The fixture interface is deprecated in version 3.12.",
        "reason": "A pinned synthetic source comparison.",
        "limitations": "Synthetic test data; no independent factual verification.",
        "confidence": 0.4,
    },
    (
        "ad52164c4d1e38eb4cf1c7170bd4e8de3a8c6f4772fcb3d5e9af0c38eb5021fe",
        "ad52164c4d1e38eb4cf1c7170bd4e8de3a8c6f4772fcb3d5e9af0c38eb5021fe",
    ): {
        "relationship": "supports",
        "claim_aspect": "recommendation",
        "historical_claim_quote": "The fixture interface is recommended for all clients.",
        "current_claim_quote": "The fixture interface is recommended for all clients.",
        "scope_alignment": "same",
        "scope_note": "Same synthetic fixture interface.",
        "supersession_basis_quote": None,
        "reason": "A pinned synthetic source comparison.",
        "limitations": "Synthetic test data; no independent factual verification.",
        "confidence": 0.4,
    },
}


# Real mirror pairs are pinned by the committed manifest, never by lexical inference.
def demo_fixtures():
    import json

    from alive.demo_live_01 import DIRECTORY, manifest

    sources = {item["id"]: item for item in manifest()["sources"]}
    historical = sources["python-3.11"]
    h = "Return the current UTC date and time, with tzinfo None."
    fixtures = {}
    for name in ("python-3.12", "synthetic-no-change"):
        current = sources[name]
        captured = json.loads((DIRECTORY / current["capture_file"]).read_text(encoding="utf-8"))[
            "text"
        ]
        quote = (
            "Deprecated since version 3.12: Use datetime.now() with UTC instead."
            if name == "python-3.12"
            else "This synthetic publication adds no status or recommendation change."
        )
        assert quote in captured
        fixtures[(current["captured_text_sha256"], historical["captured_text_sha256"])] = {
            "relationship": "explicit_supersession"
            if name == "python-3.12"
            else "insufficient_evidence",
            "claim_aspect": "status",
            "historical_claim_quote": h,
            "current_claim_quote": quote,
            "scope_alignment": "same",
            "scope_note": "Same datetime.utcnow entry; standing, not behavior.",
            "supersession_basis_quote": quote if name == "python-3.12" else None,
            "reason": (
                "The newer source adds a deprecation recommendation; "
                "the behavior sentence remains present."
                if name == "python-3.12"
                else "Newer publication alone does not establish supersession."
            ),
            "limitations": "Deterministic local demonstration. "
            "No independent assessment of factual truth.",
            "confidence": 0.4 if name == "python-3.12" else 0.1,
        }
    return fixtures
