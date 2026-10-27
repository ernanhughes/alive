"""Export actual ALIVE-05 Postgres evidence without raw excerpts or credentials."""

import asyncio
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select

from alive.config import Settings
from alive.db import Database
from alive.models import record
from alive.web_models import WebExperience

LOCAL = Path(".alive/browser05")
ARCHIVE = Path("archives/ALIVE-05")


def sha(value):
    return hashlib.sha256(value).hexdigest()


def redact(value):
    if isinstance(value, dict):
        return {
            k: {"redacted": "raw page text", "sha256": sha(v.encode()), "characters": len(v)}
            if k in {"text", "untrusted_excerpt"} and isinstance(v, str)
            else sha(v.encode())
            if k == "instance_id"
            else redact(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


async def main():
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    first = json.loads((LOCAL / "first-note.json").read_text(encoding="utf-8"))
    mdn = json.loads((LOCAL / "mdn-note.json").read_text(encoding="utf-8"))
    reports = {
        name: json.loads((LOCAL / (name + ".json")).read_text(encoding="utf-8"))
        for name in ["first", "feedback", "revisit", "mdn"]
    }
    before, after = reports["feedback"]["selected"], reports["revisit"]["selected"]
    assert before["decision"]["action"] == "analyse"
    assert after["decision"]["action"] == "recall"
    assert before["decision"]["same_state_sha256"] == after["decision"]["same_state_sha256"]
    assert after["decision"]["note"]["id"] == first["id"]
    assert before["snapshot"]["parent_id"] != after["snapshot"]["parent_id"]
    db = Database(Settings().database_url)
    async with db.sessions() as session:
        rows = (
            await session.scalars(select(WebExperience).order_by(WebExperience.created_at))
        ).all()
        notes = [r for r in rows if r.kind == "note"]
        assert len(notes) == 2, "Account for every paid attempt, including failures"
        assert {r.id for r in notes} == {first["id"], mdn["id"]}
        evidence = {
            "qualification": "PASS_WITH_LIMITATIONS",
            "source_head_before_archive": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip(),
            "native_reports": reports,
            "persisted_rows": [jsonable_encoder(record(r)) for r in rows],
            "live_meta_calls": len(notes),
            "total_tokens": sum(r.data["usage"]["total_tokens"] for r in notes),
            "estimated_usd": sum(r.data["estimated_usd"] for r in notes),
            "revisit_new_calls": 0,
            "feedback_source": (
                "Automated qualification operator deliberately rated the inspected note useful; "
                "not a user study or independently measured task reward."
            ),
            "limitations": [
                "Two exact documentation landing pages, first 3000 visible characters only",
                (
                    "Configured usefulness-driven exact-match reuse; "
                    "no general learning advantage claimed"
                ),
                (
                    "Chrome side panel driven through CDP in headful stable Chrome, "
                    "not panel.html in a tab"
                ),
                (
                    "First model call succeeded; original native runner failed polling. "
                    "Original database rows recovered without inference replay."
                ),
                (
                    "Public demonstration is a static replay of verified runtime evidence; "
                    "live runtime remains local"
                ),
            ],
        }
    await db.engine.dispose()
    (ARCHIVE / "evidence.json").write_text(json.dumps(redact(evidence), indent=2), encoding="utf-8")
    shutil.copyfile(LOCAL / "revisit-native-panel.png", ARCHIVE / "native-recall.png")
    for log in LOCAL.glob("validation-*.txt"):
        shutil.copyfile(log, ARCHIVE / log.name)
    (ARCHIVE / ".gitattributes").write_text("* -text\n", encoding="utf-8")
    files = {
        str(p.relative_to(ARCHIVE)).replace("\\", "/"): {
            "sha256": sha(p.read_bytes()),
            "bytes": p.stat().st_size,
        }
        for p in ARCHIVE.rglob("*")
        if p.is_file() and p.name != "manifest.json"
    }
    sources = {
        str(p).replace("\\", "/"): sha(p.read_bytes())
        for p in [
            Path("alive/web_experience.py"),
            Path("alive/web_models.py"),
            *Path("extension").glob("*.js"),
            Path("extension/panel.html"),
            Path("extension/manifest.json"),
            Path("scripts/browser05.py"),
        ]
    }
    (ARCHIVE / "manifest.json").write_text(
        json.dumps({"files": files, "sources": sources}, indent=2), encoding="utf-8"
    )
    print(f"Archived {len(files)} payloads; {len(notes)} real Meta calls; no raw page excerpts")


if __name__ == "__main__":
    asyncio.run(main())
