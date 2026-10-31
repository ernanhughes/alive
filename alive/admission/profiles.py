"""Closed, separately reviewed admission profiles. A profile is code, never request data.

`approved-repository-inspection` (L1-01) is the no-inference profile and stays unchanged:
its reviewed terms carry no `profile` key, so earlier review digests keep their meaning.
`approved-repository-analysis` (L1-02) adds exactly one governed model call and a separate
disclosure of the approved source to the configured model destination.
"""

import json
from dataclasses import dataclass
from urllib.parse import urlsplit

from alive.analysis.context import context_package, request_bytes
from alive.analysis.contracts import (
    CONTEXT_POLICY,
    MAX_FILES,
    MAX_SOURCE_BYTES,
    ROLE,
    role_contract,
)
from alive.providers import meta_endpoint_host, meta_endpoint_url
from alive.workflows.context import require

INSPECTION = "approved-repository-inspection"
ANALYSIS = "approved-repository-analysis"


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


PROFILES = {
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
    ),
}


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


def definition_text(profile):
    from importlib import resources

    return (resources.files("alive.admission") / profile.definition_file).read_text()


def check_definition_file(profile):
    json.loads(definition_text(profile))
