"""Freeze a fresh ALIVE-11 paid rerun without touching qualification-v1."""

import argparse
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

from alive.experiment_budget import check_spend

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "archives/ALIVE-11/qualification-v2"


def clean(value):
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean(item) for item in value]
    if isinstance(value, str):
        return value.replace(str(ROOT), "[worktree]").replace(ROOT.as_posix(), "[worktree]")
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    args = parser.parse_args()
    if OUT.exists():
        raise SystemExit("qualification-v2 exists; preserve it and use a new version")
    run, approval = args.run, args.approval
    evidence = json.loads((run / "evidence.json").read_text())
    rows = json.loads((run / "persisted-experience.json").read_text())
    protocol = json.loads((run / "protocol.json").read_text())
    notes = sorted(
        (row for row in rows if row["kind"] == "note"), key=lambda row: row["data"]["started_at"]
    )
    assert evidence["status"] == "NATIVE_META_PASS"
    assert evidence["provider"]["paid"] is True
    assert evidence["provider"]["calls"] == 8
    assert len(notes) == 8 and all(row["status"] == "validated" for row in notes)
    tokens = sum(row["data"]["charged_tokens"] for row in notes)
    estimated = sum(row["data"].get("estimated_usd") or 0 for row in notes)
    assert tokens == evidence["provider"]["charged_tokens"] == 4246
    assert estimated <= 0.10
    assert tokens <= 12000
    assert evidence["restart"]["duplicate_inference"] is False
    assert evidence["environment"]["panel_opened_as_ordinary_tab"] is False

    OUT.mkdir(parents=True)
    (OUT / ".gitattributes").write_bytes(b"* -text whitespace=cr-at-eol\n")

    def write(name, value):
        text = json.dumps(clean(value), indent=2) + "\n"
        if "Bearer " in text or "ALIVE_META_API_KEY=" in text:
            raise SystemExit("Possible credential in archive")
        (OUT / name).write_text(text, encoding="utf-8")

    native = dict(evidence)
    native["environment"] = {
        key: value
        for key, value in native["environment"].items()
        if key
        not in {"database", "template_extension", "isolated_extension", "extension_id", "grant_id"}
    }
    native["provenance"] = native["provenance"] | {"paid_calls": 8}
    write("native-meta.json", native)
    write("meta-experience.json", rows)
    write("meta-protocol.json", protocol)
    approval_data = json.loads(approval.read_text())
    approval_data["credentials"] = "owner-provided ignored env file (not archived)"
    write("meta-approval.json", approval_data)
    write("meta-checkpoints.json", json.loads((run / "checkpoints.json").read_text()))
    write("meta-matched-baselines.json", json.loads((run / "native-baselines.json").read_text()))
    write(
        "provider-usage.json",
        {
            "provider": "Meta Model API",
            "model": "muse-spark-1.3",
            "calls": 8,
            "validated_calls": sum(row["status"] == "validated" for row in notes),
            "charged_tokens": tokens,
            "estimated_usd": round(estimated, 7),
            "paid": True,
            "per_note": [
                {
                    "note_id": row["id"],
                    "charged_tokens": row["data"]["charged_tokens"],
                    "estimated_usd": row["data"].get("estimated_usd"),
                    "error": row["data"].get("error"),
                    "started_at": row["data"].get("started_at"),
                }
                for row in notes
            ],
            "note": "Estimated with ALIVE's price() formula; not a provider invoice.",
        },
    )
    audit, previous, spent_tokens = [], [], 0
    for row in notes:
        data = row["data"]
        receipt = check_spend(previous, data["reserved_tokens"], cap=100000)
        assert spent_tokens + data["reserved_tokens"] <= 12000
        audit.append(
            receipt
            | {
                "note_id": row["id"],
                "prior_charged_tokens": spent_tokens,
                "reserved_tokens": data["reserved_tokens"],
                "actual_tokens": data["charged_tokens"],
            }
        )
        spent_tokens += data["charged_tokens"]
        previous.append(data | {"status": row["status"]})
    write(
        "budget-reconstruction.json",
        {
            "kind": "post-run guard reconstruction, not provider invoice",
            "ceiling_micro_usd": 100000,
            "token_ceiling": 12000,
            "calls": audit,
        },
    )
    with sqlite3.connect(run / "native.db") as database:
        control = database.execute(
            "SELECT spent,reserved,configuration FROM cognitive_control"
        ).fetchone()
    write(
        "governor-final.json",
        {
            "spent": json.loads(control[0]),
            "reserved": json.loads(control[1]),
            "configuration": json.loads(control[2]),
        },
    )
    for stage in ["native-panel", "distinct-1", "distinct-3", "suppressed", "recovered"]:
        shutil.copyfile(run / (stage + ".png"), OUT / (stage + ".png"))
    (OUT / "source.txt").write_text(
        evidence["provenance"]["source_commit"] + "\n", encoding="utf-8"
    )
    (OUT / "README.md").write_text(
        "# ALIVE-11 qualification v2 - fresh paid rerun\n\n"
        "Engineering **PASS**; research **BEHAVIOUR_CHANGE_DEMONSTRATED**; utility advantage "
        "**NOT ESTABLISHED**.\n\n"
        "This supplementary archive preserves a second, separately approved paid campaign. "
        "It does not modify `qualification-v1` or any ALIVE-01-10 archive.\n\n"
        "| Measure | Value |\n| --- | ---: |\n"
        "| Source | `" + evidence["provenance"]["source_commit"] + "` |\n"
        "| Model | `muse-spark-1.3` |\n"
        "| Calls / validated | 8 / 8 |\n"
        "| Charged tokens | 4,246 |\n"
        "| Estimated spend | $0.0113225 |\n"
        "| Approval | 8 calls / 12,000 tokens / $0.10 |\n"
        "| Chrome | " + evidence["environment"]["chrome"] + " |\n"
        "| Panel | " + evidence["environment"]["presentation"] + " |\n\n"
        "The native journey reproduced distinct-excerpt support, suppression, owner correction, "
        "stale-probe rejection, bounded recovery, policy v11 restart and negative authorisation "
        "checks. The five screenshots are genuine captures from this run.\n\n"
        "Feedback ratings are scripted branch interventions, not measured owner usefulness. "
        "The paid baseline arms share responses and are not independent replications. No utility "
        "or statistical advantage is claimed.\n",
        encoding="utf-8",
    )
    files = {}
    for path in sorted(p for p in OUT.rglob("*") if p.is_file() and p.name != "manifest.json"):
        data = path.read_bytes()
        files[path.relative_to(OUT).as_posix()] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        }
    manifest = {
        "status": "PASS",
        "research": "BEHAVIOUR_CHANGE_DEMONSTRATED",
        "source_commit": evidence["provenance"]["source_commit"],
        "paid_calls": 8,
        "charged_tokens": 4246,
        "estimated_usd": 0.0113225,
        "files": files,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(OUT)
    print("manifest payloads", len(files))


if __name__ == "__main__":
    main()
