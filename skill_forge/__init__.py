"""ALIVE Skill Forge P0: safe, declarative skills and an evidence-backed inquiry graph.

No model-generated code execution. No browser permissions granted by this module.
"""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SAFE_CAPABILITIES = frozenset({
    "graph.query", "graph.add_observation", "history.related",
    "memory.retrieve", "ui.show_card", "ui.show_links",
})
SAFE_OPERATIONS = frozenset({
    "graph.query", "graph.add_observation", "history.related",
    "memory.retrieve", "ui.show_card", "ui.show_links",
})
ID_RE = re.compile(r"^[a-z][a-z0-9-]{2,63}$")
ALLOWED_KINDS = frozenset({"inquiry", "concept", "source", "claim", "observation"})
ALLOWED_RELATIONS = frozenset({
    "explores", "supports", "contradicts", "extends",
    "motivated_by", "applies_to", "derived_from", "related_to",
})


class SkillError(ValueError):
    """Invalid skill or denied capability."""


def validate_manifest(raw: dict[str, Any]) -> dict[str, Any]:
    """Accept only a constrained data manifest. Reject unknown fields."""
    if not isinstance(raw, dict) or set(raw) != {
        "id", "version", "description", "capabilities", "triggers", "steps"
    }:
        raise SkillError("manifest fields must match the P0 schema")
    if not isinstance(raw["id"], str) or not ID_RE.fullmatch(raw["id"]):
        raise SkillError("invalid skill id")
    if not isinstance(raw["version"], int) or isinstance(raw["version"], bool) or raw["version"] < 1:
        raise SkillError("version must be a positive integer")
    if not isinstance(raw["description"], str) or not 1 <= len(raw["description"]) <= 500:
        raise SkillError("invalid description")
    caps = raw["capabilities"]
    if not isinstance(caps, list) or len(caps) != len(set(map(str, caps))):
        raise SkillError("capabilities must be unique")
    if not all(isinstance(x, str) and x in SAFE_CAPABILITIES for x in caps):
        raise SkillError("unsupported or unsafe capability")
    triggers = raw["triggers"]
    if triggers != ["user_request"]:
        raise SkillError("P0 requires explicit user_request; background execution unavailable")
    steps = raw["steps"]
    if not isinstance(steps, list) or not 1 <= len(steps) <= 12:
        raise SkillError("a skill must have 1–12 steps")
    for step in steps:
        if not isinstance(step, dict) or set(step) != {"operation", "args"}:
            raise SkillError("invalid step structure")
        if step["operation"] not in SAFE_OPERATIONS or step["operation"] not in caps:
            raise SkillError("step operation not declared or unsupported")
        if not isinstance(step["args"], dict):
            raise SkillError("step args must be an object")
        if len(json.dumps(step["args"])) > 8192:
            raise SkillError("step args too large")
    return raw


@dataclass(frozen=True)
class SkillStatus:
    skill_id: str
    version: int
    enabled: bool
    approved: bool


class SkillRegistry:
    """Local registry; proposal, approval and enablement are separate operations."""

    def __init__(self, db_path: str | Path):
        self.db = sqlite3.connect(str(db_path))
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS skills (
                id TEXT PRIMARY KEY, version INTEGER NOT NULL, manifest TEXT NOT NULL,
                approved INTEGER NOT NULL DEFAULT 0, enabled INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS skill_audit (
                id INTEGER PRIMARY KEY, skill_id TEXT NOT NULL, event TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '', occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.db.commit()

    def _audit(self, skill_id: str, event: str, detail: str = "") -> None:
        self.db.execute(
            "INSERT INTO skill_audit(skill_id,event,detail) VALUES (?,?,?)",
            (skill_id, event, detail),
        )

    def propose(self, manifest: dict[str, Any]) -> SkillStatus:
        manifest = validate_manifest(manifest)
        sid, version = manifest["id"], manifest["version"]
        old = self.db.execute("SELECT version FROM skills WHERE id=?", (sid,)).fetchone()
        if old and version <= old[0]:
            raise SkillError("new version must increase monotonically")
        # Revisions revoke approval and disable the previous version.
        self.db.execute(
            "INSERT INTO skills(id,version,manifest,approved,enabled) VALUES (?,?,?,0,0) "
            "ON CONFLICT(id) DO UPDATE SET version=excluded.version, "
            "manifest=excluded.manifest,approved=0,enabled=0",
            (sid, version, json.dumps(manifest, sort_keys=True)),
        )
        self._audit(sid, "proposed", f"v{version}")
        self.db.commit()
        return SkillStatus(sid, version, False, False)

    def approve(self, skill_id: str) -> SkillStatus:
        self._require(skill_id)
        self.db.execute("UPDATE skills SET approved=1 WHERE id=?", (skill_id,))
        self._audit(skill_id, "approved")
        self.db.commit()
        return self.status(skill_id)

    def set_enabled(self, skill_id: str, enabled: bool) -> SkillStatus:
        row = self._require(skill_id)
        if enabled and not row[1]:
            raise SkillError("skill needs explicit owner approval before enabling")
        self.db.execute("UPDATE skills SET enabled=? WHERE id=?", (int(enabled), skill_id))
        self._audit(skill_id, "enabled" if enabled else "disabled")
        self.db.commit()
        return self.status(skill_id)

    def _require(self, skill_id: str) -> tuple[int, int, int]:
        row = self.db.execute(
            "SELECT version,approved,enabled FROM skills WHERE id=?", (skill_id,)
        ).fetchone()
        if row is None:
            raise SkillError("unknown skill")
        return row

    def status(self, skill_id: str) -> SkillStatus:
        version, approved, enabled = self._require(skill_id)
        return SkillStatus(skill_id, version, bool(enabled), bool(approved))

    def enabled_manifest(self, skill_id: str) -> dict[str, Any]:
        status = self.status(skill_id)
        if not status.approved or not status.enabled:
            raise SkillError("skill is not enabled and approved")
        row = self.db.execute("SELECT manifest FROM skills WHERE id=?", (skill_id,)).fetchone()
        return validate_manifest(json.loads(row[0]))

    def close(self) -> None:
        self.db.close()


class InquiryGraph:
    """Evidence-labeled graph; no inferred edge is presented as a verified fact."""

    def __init__(self, db_path: str | Path):
        self.db = sqlite3.connect(str(db_path))
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS inquiry_nodes (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, label TEXT NOT NULL,
                source_ref TEXT, provenance TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS inquiry_edges (
                id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES inquiry_nodes(id),
                target_id TEXT NOT NULL REFERENCES inquiry_nodes(id),
                relation TEXT NOT NULL, evidence_ref TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('candidate','confirmed','rejected')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.db.commit()

    def add_node(self, node_id: str, kind: str, label: str, provenance: str,
                 source_ref: str | None = None) -> None:
        if not ID_RE.fullmatch(node_id) or kind not in ALLOWED_KINDS:
            raise SkillError("invalid node")
        if not label.strip() or not provenance.strip():
            raise SkillError("label and provenance required")
        self.db.execute(
            "INSERT INTO inquiry_nodes(id,kind,label,source_ref,provenance) VALUES (?,?,?,?,?)",
            (node_id, kind, label, source_ref, provenance),
        )
        self.db.commit()

    def add_edge(self, edge_id: str, source_id: str, target_id: str,
                 relation: str, evidence_ref: str, status: str = "candidate") -> None:
        if not ID_RE.fullmatch(edge_id) or relation not in ALLOWED_RELATIONS:
            raise SkillError("invalid edge")
        if status not in {"candidate", "confirmed", "rejected"} or not evidence_ref.strip():
            raise SkillError("edges require evidence and an explicit status")
        self.db.execute(
            "INSERT INTO inquiry_edges(id,source_id,target_id,relation,evidence_ref,status) "
            "VALUES (?,?,?,?,?,?)",
            (edge_id, source_id, target_id, relation, evidence_ref, status),
        )
        self.db.commit()

    def neighborhood(self, node_id: str) -> list[dict[str, str]]:
        rows = self.db.execute(
            "SELECT source_id,target_id,relation,evidence_ref,status FROM inquiry_edges "
            "WHERE source_id=? OR target_id=? ORDER BY id",
            (node_id, node_id),
        ).fetchall()
        return [dict(zip(("source_id","target_id","relation","evidence_ref","status"), r))
                for r in rows]

    def close(self) -> None:
        self.db.close()
