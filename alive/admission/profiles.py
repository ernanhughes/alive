"""Closed, separately reviewed admission profiles. A profile is code, never request data.

`approved-repository-inspection` (L1-01) is the no-inference profile and stays unchanged:
its reviewed terms carry no `profile` key, so earlier review digests keep their meaning.
`approved-repository-analysis` (L1-02) adds exactly one governed model call and a separate
disclosure of the approved source to the configured model destination.
"""

import json
from dataclasses import dataclass, replace
from urllib.parse import urlsplit

from alive.analysis.context import context_package, request_bytes
from alive.analysis.contracts import (
    CONTEXT_POLICY,
    MAX_FILES,
    MAX_SOURCE_BYTES,
    ROLE,
    role_contract,
)
from alive.intent import context as intent_context
from alive.intent.contracts import CONTEXT_POLICY as INTENT_POLICY
from alive.intent.contracts import ROLE as INTENT_ROLE
from alive.intent.contracts import role_contract as intent_role_contract
from alive.providers import meta_endpoint_host, meta_endpoint_url
from alive.workflows.context import require

INSPECTION = "approved-repository-inspection"
ANALYSIS = "approved-repository-analysis"
INTENT = "intent-interpretation"
CONTEXTUAL = "contextual-reasoning"
CODE_REVIEW = "code-review-v1"
CODE_REPAIR = "code-review-repair-v1"
CONTEXT_PROFILES = (CONTEXTUAL, CODE_REVIEW, CODE_REPAIR)


@dataclass(frozen=True)
class Profile:
    id: str
    definition_file: str
    operations: tuple[str, ...]  # workflow operations the Grant names
    source_operations: tuple[str, ...]  # operations the source approval must also name
    resource_stages: tuple[str, ...]  # stages that receive the approved source resources
    max_files: int
    max_source_bytes: int
    wall_seconds: int
    max_model_calls: int
    max_output_tokens: int
    model: bool
    role: str | None = None
    reads_files: bool = True


PROFILES = {
    CONTEXTUAL: Profile(
        CONTEXTUAL,
        "contextual-reasoning.json",
        ("context.reason", "context.validate", "result.record"),
        ("context.reason", "context.validate"),
        ("reason", "validate"),
        MAX_FILES,
        MAX_SOURCE_BYTES,
        180,
        1,
        1536,
        True,
        "contextual_reasoner",
        False,
    ),
    INSPECTION: Profile(
        INSPECTION,
        "repository-inspection.json",
        ("repository.inspect",),
        ("repository.inspect",),
        ("read",),
        20,
        32768,
        30,
        0,
        0,
        False,
    ),
    ANALYSIS: Profile(
        ANALYSIS,
        "repository-analysis.json",
        (
            "repository.inspect",
            "repository.analyze",
            "repository.validate_findings",
            "result.record",
        ),
        ("repository.inspect", "repository.analyze"),
        ("read", "analyze"),
        MAX_FILES,
        MAX_SOURCE_BYTES,
        180,
        1,
        1536,
        True,
        ROLE,
    ),
    INTENT: Profile(
        INTENT,
        "intent-interpretation.json",
        ("intent.interpret", "intent.validate", "result.record"),
        ("intent.interpret",),
        ("interpret",),
        20,
        32768,
        180,
        1,
        1536,
        True,
        INTENT_ROLE,
        False,
    ),
}

for _id, _role in ((CODE_REVIEW, "code_reviewer"), (CODE_REPAIR, "code_review_repairer")):
    PROFILES[_id] = replace(PROFILES[CONTEXTUAL], id=_id, role=_role)


def analysis_inputs(source, paths, objective):
    """The model-bound input exactly as the read stage will present it, for the review."""
    files = {f["path"]: f for f in source.content["files"]}
    return {
        "source_ref": source.source_ref,
        "source_sha256": source.content_sha256,
        "scoped_sha256": source.scoped_sha256,
        "objective": objective,
        "files": [
            {k: files[p][k] for k in ("path", "content", "sha256", "bytes")} for p in sorted(paths)
        ],
        "omitted": [],
    }


def analysis_endpoint(settings):
    """Refuse URL shapes that can disagree between disclosure and the HTTP client."""
    endpoint = meta_endpoint_url(settings)
    try:
        parsed = urlsplit(endpoint)
        valid_endpoint = (
            not any(ord(character) <= 32 or ord(character) == 127 for character in endpoint)
            and parsed.scheme == "https"
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and not parsed.query
            and not parsed.fragment
            and parsed.port != 0
        )
    except ValueError:
        valid_endpoint = False
    require(valid_endpoint, "analysis_requires_safe_https_endpoint")
    return endpoint


def disclosure(kernel, control, source, paths, objective):
    """What leaves the host, to whom and under what ceilings. Every field is recomputed later."""
    from alive.cognition import CognitiveConfiguration

    config = CognitiveConfiguration.model_validate(control.configuration)
    settings = kernel.settings
    endpoint = analysis_endpoint(settings)
    inputs = analysis_inputs(source, paths, objective)
    context_package(inputs)  # raises on any size or shape violation
    output_limit = min(config.output_tokens, PROFILES[ANALYSIS].max_output_tokens)
    request = request_bytes(inputs, output_limit)
    require(
        request <= config.request_tokens and request <= config.investigation_tokens,
        "context_exceeds_governor_request_ceiling",
    )
    return {
        "operation": "repository.analyze",
        "destination": {
            "kind": "remote_provider",
            "provider": "meta",
            "transport": "pi",
            "host": meta_endpoint_host(settings),
            "endpoint": endpoint,
            "model": settings.alive_role_models.get(ROLE, settings.alive_meta_model),
        },
        "role": ROLE,
        "role_contract_sha256": role_contract(),
        "context_policy": CONTEXT_POLICY,
        "files": [{"path": f["path"], "bytes": f["bytes"]} for f in inputs["files"]],
        "source_bytes": sum(f["bytes"] for f in inputs["files"]),
        "reserved_request_bytes": request,
        "max_model_calls": 1,
        "max_output_tokens": output_limit,
        "leaves_host": True,
        "cost": "unknown; no price is configured and none is estimated",
        "cancellation": "A request already sent to the provider cannot be recalled. An "
        "ambiguous outcome is never retried; its reservation stays charged.",
        "retention": "The prompt and response are retained in the local database in clear text.",
    }


def intent_disclosure(kernel, control, source, paths, objective):
    """What the interpreter receives: the goal, file names and sizes, and the catalogue."""
    from alive.bespoke.recipes import load_catalogue
    from alive.cognition import CognitiveConfiguration
    from alive.intent.adapters import source_view

    config = CognitiveConfiguration.model_validate(control.configuration)
    settings = kernel.settings
    endpoint = analysis_endpoint(settings)
    recipes = getattr(kernel, "bespoke_recipes", None) or load_catalogue()
    rows = intent_context.project_catalogue(recipes)
    view = source_view(source)
    require(sorted(f["path"] for f in view["inventory"]) == sorted(paths), "intent_scope_mismatch")
    inputs = {"user_goal": objective, "source": view, "catalogue": rows}
    intent_context.context_package(inputs)  # raises on any size or shape violation
    output_limit = min(config.output_tokens, PROFILES[INTENT].max_output_tokens)
    request = intent_context.request_bytes(inputs, output_limit)
    require(
        request <= config.request_tokens and request <= config.investigation_tokens,
        "context_exceeds_governor_request_ceiling",
    )
    return {
        "operation": "intent.interpret",
        "destination": {
            "kind": "remote_provider",
            "provider": "meta",
            "transport": "pi",
            "host": meta_endpoint_host(settings),
            "endpoint": endpoint,
            "model": settings.alive_role_models.get(INTENT_ROLE, settings.alive_meta_model),
        },
        "role": INTENT_ROLE,
        "role_contract_sha256": intent_role_contract(),
        "context_policy": INTENT_POLICY,
        "files": [{"path": f["path"], "bytes": f["bytes"]} for f in view["inventory"]],
        "source_bytes": 0,
        "content_sent": False,
        "goal_characters": len(objective),
        "catalogue_sha256": intent_context.catalogue_sha256(rows),
        "catalogue_entries": len(rows),
        "reserved_request_bytes": request,
        "max_model_calls": 1,
        "max_output_tokens": output_limit,
        "leaves_host": True,
        "cost": "unknown; no price is configured and none is estimated",
        "cancellation": "A request already sent to the provider cannot be recalled. An "
        "ambiguous outcome is never retried; its reservation stays charged.",
        "retention": "The prompt and response are retained in the local database in clear text.",
    }


def disclose(profile, kernel, control, source, paths, objective, snapshot=None):
    if profile.id in CONTEXT_PROFILES:
        return contextual_disclosure(
            kernel, control, source, paths, objective, snapshot, profile=profile.id
        )
    work = intent_disclosure if profile.id == INTENT else disclosure
    return work(kernel, control, source, paths, objective)


def contextual_disclosure(
    kernel, control, source, paths, objective, snapshot, *, profile=CONTEXTUAL
):
    from alive.cognition import CognitiveConfiguration
    from alive.continuity.context import empty_snapshot, package, request_bytes
    from alive.continuity.contracts import POLICY, ROLE, role_contract
    from alive.workflows.context import digest

    config = CognitiveConfiguration.model_validate(control.configuration)
    snapshot = snapshot if snapshot is not None else empty_snapshot()
    if profile != CONTEXTUAL:
        from alive.task_review import contracts as task
        from alive.task_review.service import package

        ROLE = PROFILES[profile].role

        def role_contract():
            return task.role_contract(profile == CODE_REPAIR)

    data = package(source, paths, objective, snapshot)
    limit = min(config.output_tokens, PROFILES[profile].max_output_tokens)
    if profile == CONTEXTUAL:
        request = request_bytes(data, limit)
    else:
        spec = task.Spec({}, lambda _: data, repair=profile == CODE_REPAIR)
        request = (
            len(
                json.dumps(
                    {"instructions": spec.instructions, "data": data, "schema": spec.schema}
                ).encode()
            )
            + 1024
            + limit
        )
    require(
        request <= config.request_tokens and request <= config.investigation_tokens,
        "context_exceeds_governor_request_ceiling",
    )
    settings = kernel.settings
    return {
        "operation": "context.reason",
        "destination": {
            "kind": "remote_provider",
            "provider": "meta",
            "transport": "pi",
            "host": meta_endpoint_host(settings),
            "endpoint": analysis_endpoint(settings),
            "model": settings.alive_role_models.get(ROLE, settings.alive_meta_model),
        },
        "role": ROLE,
        "role_contract_sha256": role_contract(),
        "context_policy": POLICY,
        "files": [{"path": f["path"], "bytes": f["bytes"]} for f in source.content["files"]],
        "source_bytes": sum(f["bytes"] for f in source.content["files"]),
        "context_sha256": digest(snapshot),
        "context_bytes": len(json.dumps(snapshot).encode()),
        "model_input_sha256": digest(data),
        "conversation_ref": snapshot["conversation_ref"],
        "reserved_request_bytes": request,
        "max_model_calls": 1,
        "max_output_tokens": limit,
        "leaves_host": True,
        "cost": "unknown; not estimated",
        "retention": "Local prompts, frozen context and responses persist in clear text.",
        "cancellation": "Disclosed data cannot be recalled; ambiguous calls are not retried.",
    }


def definition_text(profile):
    from importlib import resources

    text = (resources.files("alive.admission") / profile.definition_file).read_text()
    if profile.id in (CODE_REVIEW, CODE_REPAIR):
        data = json.loads(text)
        data["name"] = "owner-" + profile.id
        data["title"] = (
            "Code review completion" if profile.id == CODE_REVIEW else "Code review repair"
        )
        text = json.dumps(data)
    return text


def check_definition_file(profile):
    json.loads(definition_text(profile))
