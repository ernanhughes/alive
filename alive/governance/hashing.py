"""Deterministic file hashing for freeze manifests and provenance.

Canonical runtime home for the helper historically reached via
``alive.experiment.freeze.file_hash``. The frozen research copy is left
byte-identical; new production and learning code must import from here.
"""

import hashlib
from pathlib import Path


def file_hash(path):
    # Canonical UTF-8 text is stable across Windows/LF checkouts.
    return hashlib.sha256(Path(path).read_text(encoding="utf8").encode()).hexdigest()
