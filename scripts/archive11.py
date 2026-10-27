"""Immutable, bounded export of ALIVE-11's separately classified qualification evidence."""

import argparse
import json
import shutil
import sqlite3
from pathlib import Path

from alive.experiment_budget import charged_micro_usd, check_spend

ROOT = Path(__file__).resolve().parents[1]


def owned(path):
    path = path.resolve()
    if not path.is_relative_to((ROOT / ".alive").resolve()):
        raise ValueError("Export only owned local qualification artifacts")
    return path


def export(args):
    synthetic, meta, recall = map(owned, [args.synthetic, args.meta, args.recall])
    out = ROOT / "archives/ALIVE-11/qualification-v1"
    if out.exists():
        raise ValueError("Qualification archive already exists; use a supplementary version")
    s = json.loads((synthetic / "evidence.json").read_text())
    m = json.loads((meta / "evidence.json").read_text())
    r = json.loads((recall / "recall.json").read_text())
    assert s["status"] == "NATIVE_SYNTHETIC_PASS" and m["status"] == "NATIVE_META_PASS"
    assert r["status"] == "NATIVE_RECALL_PASS"
    assert s["provenance"]["source_commit"] == m["provenance"]["source_commit"]
    assert s["environment"]["panel_opened_as_ordinary_tab"] is False
    assert m["environment"]["panel_opened_as_ordinary_tab"] is False
    rows = json.loads((meta / "persisted-experience.json").read_text())
    notes = sorted((n for n in rows if n["kind"] == "note"), key=lambda n: n["data"]["started_at"])
    assert len(notes) == 8 and all(n["status"] == "validated" for n in notes)
    assert sum(n["data"]["charged_tokens"] for n in notes) <= 12000
    assert charged_micro_usd([n["data"] | {"status": n["status"]} for n in notes]) <= 100000
    audit, previous, spent_tokens = [], [], 0
    for n in notes:
        d = n["data"]
        receipt = check_spend(previous, d["reserved_tokens"], cap=100000)
        assert spent_tokens + d["reserved_tokens"] <= 12000
        audit.append(
            receipt
            | {
                "note_id": n["id"],
                "prior_charged_tokens": spent_tokens,
                "reserved_tokens": d["reserved_tokens"],
                "actual_tokens": d["charged_tokens"],
            }
        )
        spent_tokens += d["charged_tokens"]
        previous.append(d | {"status": n["status"]})
    out.mkdir(parents=True)
    (out / ".gitattributes").write_bytes(b"* -text whitespace=cr-at-eol\n")

    def clean(value):
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items()}
        if isinstance(value, list):
            return [clean(v) for v in value]
        if isinstance(value, str):
            return value.replace(str(ROOT), "[worktree]").replace(ROOT.as_posix(), "[worktree]")
        return value

    def write(name, data):
        text = json.dumps(clean(data), indent=2) + "\n"
        if "Bearer " in text or "LLM_" in text:
            raise ValueError("Potential credential in export; stop for redaction review")
        (out / name).write_bytes(text.encode())

    for name, data in [("native-synthetic.json", s), ("native-meta.json", m)]:
        data = dict(data)
        data["environment"] = {
            k: v
            for k, v in data["environment"].items()
            if k not in {"database", "template_extension", "isolated_extension"}
        }
        write(name, data)
    write("recall-only.json", r)
    write("meta-experience.json", rows)
    write("meta-approval.json", json.loads((ROOT / ".alive/meta-approval.json").read_text()))
    write("meta-preflight.json", json.loads((ROOT / ".alive/meta-preflight.json").read_text()))
    write(
        "budget-reconstruction.json",
        {
            "kind": "post-run guard reconstruction, not provider invoice",
            "ceiling_micro_usd": 100000,
            "token_ceiling": 12000,
            "calls": audit,
        },
    )
    with sqlite3.connect(meta / "native.db") as db:
        control = db.execute(
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
    for run, name in [(synthetic, "synthetic"), (meta, "meta")]:
        for source, target in [
            ("protocol.json", "protocol"),
            ("checkpoints.json", "checkpoints"),
            ("native-baselines.json", "matched-baselines"),
        ]:
            write(name + "-" + target + ".json", json.loads((run / source).read_text()))
        for stage in ["distinct-1", "distinct-3", "suppressed", "recovered"]:
            shutil.copyfile(run / (stage + ".png"), out / (name + "-" + stage + ".png"))
    shutil.copyfile(recall / "recall.png", out / "recall-only.png")
    for local, name in [
        ("docked-browser.png", "docked-synthetic-browser.png"),
        ("docked-meta-browser.png", "docked-meta-browser.png"),
    ]:
        shutil.copyfile(ROOT / ".alive/validation11" / local, out / name)
    write("controlled-api-comparison.json", json.loads(owned(args.comparison).read_text()))
    for name in ["backend", "frontend", "build", "extension", "comparison"]:
        text = (ROOT / ".alive/validation11" / (name + ".txt")).read_text(encoding="utf-8-sig")
        (out / (name + ".txt")).write_bytes((text.rstrip() + "\n").encode())
    shutil.copyfile(
        ROOT / ".alive/preparation-record/preparation-document.md", out / "preparation-document.md"
    )
    diagnostics = []
    for path in sorted((ROOT / ".alive").glob("native*/evidence.json")):
        data = json.loads(path.read_text())
        if data.get("status", "").endswith("FAIL"):
            diagnostics.append(
                {
                    "run": path.parent.name,
                    "classification": "development diagnostic",
                    "committed_runtime_qualification": False,
                    "evidence": data,
                }
            )
    write("preserved-diagnostics.json", diagnostics)
    (out / "source.txt").write_bytes((m["provenance"]["source_commit"] + "\n").encode())
    print(out)
    print("Add README/demo, then freeze manifest. No prior payload was overwritten.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic", type=Path, required=True)
    parser.add_argument("--meta", type=Path, required=True)
    parser.add_argument("--recall", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    export(parser.parse_args())
