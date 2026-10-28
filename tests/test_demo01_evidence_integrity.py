"""Targeted lifecycle regressions for the ALIVE-DEMO-01 integrity seam."""
from types import SimpleNamespace

import pytest

from alive.research_relationships import ResearchRelationships


def test_withdrawal_scrub_drops_copied_source_content():
    data = {
        "historical_memory_id": "memory-one",
        "current_quote": "current excerpt",
        "historical_quote": "private copied evidence",
        "model_evidence_quote": "private copied evidence",
        "raw_response": '{"historical_quote":"private copied evidence"}',
        "payload": {"historical_excerpt": "private copied evidence"},
        "explanation": "The retired source proves a point",
        "charged_tokens": 300,
        "reserved_tokens": 400,
        "request_sha256": "hash",
    }
    cleaned = ResearchRelationships._scrub_withdrawn_data(data)
    assert "private copied evidence" not in str(cleaned)
    assert "The retired source" not in str(cleaned)
    assert cleaned["charged_tokens"] == 300
    assert cleaned["historical_memory_id"] == "memory-one"
    assert cleaned["invalid_reason"] == "historical_memory_withdrawn"


@pytest.mark.asyncio
async def test_settlement_rejects_withdrawn_authoritative_source():
    class Web:
        async def get(self, session, identifier, kind):
            assert kind == "snapshot"
            return SimpleNamespace(data={"sha256": "current-sha"}, parent_id="grant")
        async def valid_grant(self, session, identifier):
            return True

    class Research:
        async def _research_row(self, session, identifier):
            return SimpleNamespace(status="withdrawn", data={
                "sha256": "historical-sha", "goal_id": "goal"
            })

    instance = object.__new__(ResearchRelationships)
    instance.web = Web()
    instance.research = Research()
    assert not await instance._settlement_source_valid(None, {
        "current_snapshot_id": "snapshot",
        "current_sha256": "current-sha",
        "historical_memory_id": "memory",
        "historical_sha256": "historical-sha",
        "goal_id": "goal",
    })


@pytest.mark.asyncio
async def test_settlement_rejects_revoked_current_grant():
    class Web:
        async def get(self, session, identifier, kind):
            return SimpleNamespace(data={"sha256": "current-sha"}, parent_id="grant")
        async def valid_grant(self, session, identifier):
            raise PermissionError("grant revoked")

    instance = object.__new__(ResearchRelationships)
    instance.web = Web()
    assert not await instance._settlement_source_valid(None, {
        "current_snapshot_id": "snapshot", "current_sha256": "current-sha",
    })
