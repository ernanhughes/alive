"""ALIVE-SF-P1 regression tests for bounded, revocation-aware graph projection."""
from types import SimpleNamespace

import pytest

from alive.exploration_api import MAX_SOURCES, project_inquiry, projection_from_authoritative_store


def row(identifier, text, *, title="Paper", url=None):
    return SimpleNamespace(
        id=identifier,
        data={
            "excerpt": text,
            "title": title,
            "url": url or f"https://example.org/{identifier}",
            "sha256": identifier,
        },
    )


def test_shared_terms_become_candidates_not_verified_claims():
    graph = project_inquiry(
        "goal-a", "Research HCI for ALIVE",
        [
            row("source-a", "Adaptive interfaces improve interaction design."),
            row("source-b", "Adaptive interfaces alter interaction timing."),
        ],
    )
    assert graph["source_count"] == 2
    assert any(n["kind"] == "concept" and n["label"] == "adaptive" for n in graph["nodes"])
    assert all(
        edge["status"] == "candidate"
        for edge in graph["edges"] if edge["relation"] == "related_to"
    )
    assert all(edge["evidence_ref"] in {"source-a", "source-b"} for edge in graph["edges"])


def test_empty_or_unrelated_sources_abstain_on_concepts():
    empty = project_inquiry("goal-a", "Investigate HCI", [])
    assert len(empty["nodes"]) == 1
    assert empty["edges"] == []
    separated = project_inquiry(
        "goal-a", "Investigate HCI",
        [row("source-a", "Compaction scheduling throughput"), row("source-b", "Mobile screen brightness")],
    )
    assert not any(node["kind"] == "concept" for node in separated["nodes"])


def test_graph_has_stable_ids_and_bound():
    sources = [row(f"source-{i}", "Adaptive interfaces") for i in range(3)]
    assert project_inquiry("goal-a", "Explore", sources) == project_inquiry(
        "goal-a", "Explore", sources
    )
    with pytest.raises(ValueError):
        project_inquiry("goal-a", "Explore", sources * (MAX_SOURCES // 3 + 1))


def test_no_page_body_or_private_excerpt_in_response():
    secret = "PRIVATE_COMPANION_CONTENT_293"
    result = project_inquiry(
        "goal-a", "Explore",
        [row("source-a", secret), row("source-b", "Unrelated source")],
    )
    assert secret not in str(result)
