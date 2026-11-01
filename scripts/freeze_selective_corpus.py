"""Write the immutable lock for the AI-FIRST-04 corpus, oracle v2 and response contracts.

Run once, commit, and only then spend live inference. ``oracle_v2.frozen_corpus`` refuses to
grade if any locked artifact changes afterwards.
"""

import json
from pathlib import Path

from alive.adaptation import oracle_v2
from alive.continuity.contracts import role_contract as contextual_contract
from alive.intent.contracts import role_contract as intent_contract
from alive.workflows.context import digest

AUDIT = oracle_v2.CORPUS.with_name("selective-corpus-v2-audit.json")


def main():
    corpus = json.loads(oracle_v2.CORPUS.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert audit["problems"] == [], "audit must be clean before freezing"
    lock = {
        "corpus_sha256": digest(corpus),
        "oracle_sha256": digest(Path(oracle_v2.__file__).read_text(encoding="utf-8")),
        "audit_sha256": digest(audit),
        "contextual_role_contract_sha256": contextual_contract(),
        "intent_role_contract_sha256": intent_contract(),
        "seed": 4401,
        "purpose": "AI-FIRST-04 fresh corpus; train/dev/heldout split immutable once locked. "
        "Programmatically audited, not independently human-adjudicated.",
    }
    oracle_v2.MANIFEST.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(lock, indent=2))


if __name__ == "__main__":
    main()
