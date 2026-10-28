import json

import pytest

from skill_forge import InquiryGraph, SkillError, SkillRegistry, validate_manifest
from skill_forge.runtime import execute_requested_skill


def manifest(version=1):
    return {
        "id": "research-connections",
        "version": version,
        "description": "Find related inquiry evidence",
        "capabilities": ["graph.query", "ui.show_links"],
        "triggers": ["user_request"],
        "steps": [
            {"operation": "graph.query", "args": {"depth": 1}},
            {"operation": "ui.show_links", "args": {"title": "Related"}},
        ],
    }


def test_schema_rejects_privilege_and_background_triggers():
    for mutation in (
        lambda m: m["capabilities"].append("browser.execute_js"),
        lambda m: m.update(triggers=["page_observed"]),
        lambda m: m["steps"].append({"operation": "browser.execute_js", "args": {}}),
        lambda m: m.update(unexpected="extra"),
    ):
        item = manifest()
        mutation(item)
        with pytest.raises(SkillError):
            validate_manifest(item)


def test_requires_approval_and_explicit_invocation(tmp_path):
    registry = SkillRegistry(tmp_path / "skills.db")
    registry.propose(manifest())
    with pytest.raises(SkillError):
        registry.set_enabled("research-connections", True)
    registry.approve("research-connections")
    registry.set_enabled("research-connections", True)
    seen = []
    handlers = {
        "graph.query": lambda args: seen.append("query") or ["node1"],
        "ui.show_links": lambda args: seen.append("display") or True,
    }
    with pytest.raises(SkillError):
        execute_requested_skill(registry, "research-connections", handlers)
    result = execute_requested_skill(
        registry, "research-connections", handlers, owner_requested=True
    )
    assert len(result) == 2
    assert seen == ["query", "display"]
    registry.set_enabled("research-connections", False)
    with pytest.raises(SkillError):
        execute_requested_skill(registry, "research-connections", handlers, owner_requested=True)
    registry.close()


def test_revision_revokes_approval(tmp_path):
    registry = SkillRegistry(tmp_path / "registry.sqlite")
    registry.propose(manifest())
    registry.approve("research-connections")
    registry.set_enabled("research-connections", True)
    registry.propose(manifest(version=2))
    status = registry.status("research-connections")
    assert status.version == 2 and not status.approved and not status.enabled
    with pytest.raises(SkillError):
        registry.propose(manifest(version=2))
    registry.close()


def test_graph_provenance_and_candidate_status(tmp_path):
    graph = InquiryGraph(tmp_path / "graph.sqlite")
    graph.add_node("hci-inquiry", "inquiry", "HCI for ALIVE", "owner declaration")
    graph.add_node("adaptive-ui", "concept", "Adaptive interfaces", "page observation")
    graph.add_edge(
        "link-001", "hci-inquiry", "adaptive-ui", "explores", "source:https://example.org/paper"
    )
    edges = graph.neighborhood("hci-inquiry")
    assert edges[0]["status"] == "candidate"
    assert edges[0]["evidence_ref"] == "source:https://example.org/paper"
    with pytest.raises(SkillError):
        graph.add_edge("link-002", "hci-inquiry", "adaptive-ui", "supports", "")
    graph.close()


def test_example_is_valid():
    with open("skill_forge/examples/research-connections.json", encoding="utf-8") as f:
        assert validate_manifest(json.load(f))["id"] == "research-connections"
