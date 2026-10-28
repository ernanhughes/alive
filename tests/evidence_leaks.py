"""Reusable all-table scan for copied evidence, with explicit audit-original policy."""

import json

from sqlalchemy import select

from alive.models import Base


def evidence_copies(client, marker):
    async def scan():
        hits = []
        async with client.app.state.kernel.db.sessions() as session:
            for table in Base.metadata.sorted_tables:
                for row in (await session.execute(select(table))).mappings():
                    if marker in json.dumps(dict(row), default=str):
                        hits.append(
                            {
                                "table": table.name,
                                "id": row.get("id"),
                                "kind": row.get("kind"),
                                "status": row.get("status"),
                            }
                        )
        return hits

    return client.portal.call(scan)


def assert_no_derived_evidence(client, marker):
    hits = evidence_copies(client, marker)
    allowed = {"snapshot", "note", "research_memory"}
    leaks = [
        hit
        for hit in hits
        if not (
            hit["table"] == "web_experiences"
            and hit["kind"] in allowed
            and (hit["kind"] != "research_memory" or hit["status"] == "withdrawn")
        )
    ]
    assert not leaks, leaks
    return hits
