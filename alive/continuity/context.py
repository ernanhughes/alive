import json

from alive.admission.profiles import analysis_inputs
from alive.analysis.context import context_package as source_package
from alive.continuity.contracts import INSTRUCTIONS, POLICY, ContextualAnswer
from alive.workflows.context import digest, require

MAX_ITEMS = 8
MAX_BYTES = 6000


def empty_snapshot():
    return {"policy": POLICY, "conversation_ref": "", "items": [], "omitted": []}


def package(source, paths, goal, snapshot):
    require(
        snapshot["policy"] == POLICY and len(snapshot["items"]) <= MAX_ITEMS,
        "context_snapshot_policy",
    )
    require(
        len(json.dumps(snapshot, ensure_ascii=False).encode()) <= MAX_BYTES,
        "context_snapshot_byte_ceiling",
    )
    for item in snapshot["items"]:
        require(digest(item["content"]) == item["content_sha256"], "context_item_integrity")
    data = source_package(analysis_inputs(source, paths, goal))
    return {"user_goal": goal, "source": data, "conversation": snapshot}


def request_bytes(context, output_tokens):
    return (
        len(
            json.dumps(
                {
                    "instructions": INSTRUCTIONS,
                    "data": context,
                    "schema": ContextualAnswer.model_json_schema(),
                },
                ensure_ascii=False,
            ).encode()
        )
        + 1024
        + output_tokens
    )
