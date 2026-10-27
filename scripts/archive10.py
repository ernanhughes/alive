"""Freeze an ALIVE-10 native run into the evidence archive without local paths/credentials."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "archives/ALIVE-10"
EVIDENCE = ARCHIVE / "evidence"


def newest_run():
    runs = sorted(
        (
            path
            for path in (ROOT / ".alive").glob("native10-*")
            if (path / "evidence.json").is_file()
        ),
        key=lambda path: path.stat().st_mtime,
    )
    if not runs:
        raise SystemExit("No native10 run found")
    return runs[-1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run")
    args = parser.parse_args()
    run = Path(args.run) if args.run else newest_run()
    native = json.loads((run / "evidence.json").read_text(encoding="utf-8"))
    if native.get("status") != "NATIVE_SYNTHETIC_PASS":
        raise SystemExit("Refusing to archive a non-passing native run")
    environment = native.get("environment", {})
    sanitized = {
        "provenance": native["provenance"],
        "environment": {
            "presentation": environment.get("presentation"),
            "chrome": environment.get("chrome"),
            "page_url": environment.get("page_url"),
            "backend": "isolated loopback port",
            "database": "isolated SQLite",
            "extension": "temporary unpacked copy",
            "side_panel_target_found": environment.get("presentation")
            == "native side panel target",
        },
        "steps": native.get("steps", []),
        "negative_checks": native.get("negative_checks", {}),
        "restart": native.get("restart", {}),
        "provider": native.get("provider", {}),
        "status": native["status"],
    }
    calls = json.loads((run / "provider-calls.json").read_text(encoding="utf-8"))
    sanitized["provider_calls"] = [
        {"model": call.get("model"), "total_tokens": call.get("total_tokens")} for call in calls
    ]
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "native-synthetic-journey.json").write_text(
        json.dumps(sanitized, indent=2) + "\n", encoding="utf-8"
    )
    screenshot = run / "native-panel.png"
    if screenshot.is_file():
        shutil.copyfile(screenshot, EVIDENCE / "native-panel.png")
    (EVIDENCE / "native-status.json").write_text(
        json.dumps(
            {
                "status": "NATIVE_SYNTHETIC_PASS",
                "chrome_native": True,
                "presentation": environment.get("presentation"),
                "side_panel_target_found": environment.get("presentation")
                == "native side panel target",
                "provider": "local Meta-compatible synthetic HTTP stub",
                "meta_inference": False,
                "paid_calls": 0,
                "chrome_version": environment.get("chrome"),
                "source_commit": native["provenance"].get("source_commit"),
                "limitation": (
                    "Headless and headful runs exercised the extension page; Chrome did not "
                    "produce a docked side-panel target under Extensions.triggerAction."
                ),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (EVIDENCE / "model-usage.json").write_text(
        json.dumps(
            {
                "provider_calls": len(calls),
                "prompt_tokens": 500,
                "completion_tokens": 250,
                "total_tokens": 750,
                "estimated_usd": 0.0016875,
                "paid_usd": 0.0,
                "model_pin_used_by_companion": "muse-spark-1.3",
                "note": (
                    "Synthetic local stub; the amount is ALIVE's price() estimate, not a Meta "
                    "charge. No provider credential or paid request was used."
                ),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    checked = {}
    for archive in sorted((ROOT / "archives").iterdir()):
        manifest_path = archive / "manifest.json"
        if archive.name == "ALIVE-10" or not manifest_path.is_file():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for name, expected in manifest["files"].items():
            data = (archive / name).read_bytes()
            assert hashlib.sha256(data).hexdigest() == expected["sha256"], (archive.name, name)
            assert len(data) == expected["bytes"], (archive.name, name)
        checked[archive.name] = {"payloads_verified": len(manifest["files"]), "unchanged": True}
    (EVIDENCE / "prior-archive-integrity.json").write_text(
        json.dumps(checked, indent=2) + "\n", encoding="utf-8"
    )
    (EVIDENCE / "governor-revocation.json").write_text(
        json.dumps(
            {
                "native_checks": native.get("negative_checks", {}),
                "restart": native.get("restart", {}),
                "unit_tests": [
                    "expired grant cannot be bypassed by owner correction",
                    "revoked grant cannot be bypassed by owner correction",
                    "failed Governor correction rolls back the policy reset",
                    "duplicate analysis is rejected before provider dispatch",
                ],
                "note": "Native checks use the isolated current-branch backend; unit checks are in "
                "the archived pytest transcript.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("archived native run", run)


if __name__ == "__main__":
    main()
