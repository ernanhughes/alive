import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from alive.experiment.corpus import ROOT, audit, load
from alive.experiment.prompts import specification

SOURCE_FILES = [
    "alive/experiment/freeze.py",
    "alive/experiment/schema.py",
    "alive/experiment/scoring.py",
    "alive/experiment/corpus.py",
    "alive/experiment/policy.py",
    "alive/experiment/prompts.py",
    "alive/experiment/metrics.py",
    "alive/experiment/service.py",
    "alive/providers.py",
    "alive/society.py",
    "alive/cognitive_schema.py",
    "uv.lock",
    "pyproject.toml",
]


def file_hash(path):
    # Canonical UTF-8 text is stable across Windows/LF checkouts.
    return hashlib.sha256(Path(path).read_text(encoding="utf8").encode()).hexdigest()


def seal(final=False):
    report = audit(load("calibration"), load("evaluation"))
    sources = {path: file_hash(path) for path in SOURCE_FILES}
    sources.update(
        {
            str(ROOT / name).replace("\\", "/"): file_hash(ROOT / name)
            for name in ["calibration.json", "evaluation.sealed.json", "split-manifest.json"]
        }
    )
    if final:
        for name in ["policy-configuration.json", "calibration-evidence.json"]:
            sources[str(ROOT / name).replace("\\", "/")] = file_hash(ROOT / name)
    identity = {
        "schema_version": 1,
        "stage": "final-policy" if final else "corpus-and-scorer",
        "files": sources,
        "prompts": specification(),
        "audit": report,
        "evaluation_unsealed": False,
        "evaluation_requires_explicit_owner_authorization": True,
        "fixed_inference_controls": {
            "model": "muse-spark-1.3",
            "output_tokens": 1536,
            "reasoning_effort": "minimal",
            "retries": 0,
            "task_wall_seconds": 90,
        },
    }
    identity["freeze_id"] = hashlib.sha256(
        json.dumps(identity, sort_keys=True).encode()
    ).hexdigest()
    identity["sealed_at"] = datetime.now(UTC).isoformat()
    path = ROOT / ("freeze-final.json" if final else "freeze-design.json")
    if path.exists() and json.loads(path.read_text())["freeze_id"] == identity["freeze_id"]:
        return json.loads(path.read_text())
    path.write_bytes((json.dumps(identity, indent=2) + "\n").encode())
    return identity


def verify(freeze_id, final=True):
    path = ROOT / ("freeze-final.json" if final else "freeze-design.json")
    if not path.is_file():
        raise ValueError("Experiment is not frozen")
    frozen = json.loads(path.read_text())
    identity = {k: v for k, v in frozen.items() if k not in {"freeze_id", "sealed_at"}}
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    if digest != frozen["freeze_id"]:
        raise ValueError("Freeze manifest integrity failure")
    if freeze_id != frozen["freeze_id"]:
        raise ValueError("Freeze identity mismatch")
    for filename, expected in frozen["files"].items():
        if file_hash(filename) != expected:
            raise ValueError("Frozen specification changed: " + filename)
    return frozen
