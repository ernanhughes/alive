"""PI-01A dispatch seam: parity, sentinels, ratchet, ceiling.

The migration changes exactly one dispatch expression
(`alive/cognition.py::call_role`); reservation, ModelInvocation writes,
exception handling and ordering are untouched. These tests prove the seam is
byte-identical on the wire, that existing guards still bite through it, that
no new direct Meta construction can land unnoticed, and that the per-request
token ceiling refuses over-limit calls with zero dispatch.
"""

import ast
import json
import os
from pathlib import Path

import httpx
import pytest

from alive.model_gateway import DirectMetaGateway, StructuredRequest, gateway_for

ROLE_JSON = json.dumps(
    {
        "summary": "Controlled fixture summary.",
        "claims": [],
        "actions": [],
        "criticisms": [],
        "uncertainties": [],
        "recommendation": "proceed",
        "confidence": 0.9,
    }
)
USAGE = {
    "prompt_tokens": 10,
    "completion_tokens": 5,
    "total_tokens": 15,
    "mode": "structured",
}
FAKE_KEY = "test-fake-local-key-0000000000000000"


@pytest.fixture
def metaclient(tmp_path, monkeypatch):
    """conftest client variant with a configured (fake) Meta credential."""
    import asyncio

    from fastapi.testclient import TestClient

    from alive.app import create_app
    from alive.config import Settings
    from alive.db import Database
    from alive.models import Base
    from alive.providers import MetaProvider
    from tests.conftest import TOKEN

    async def discover(*args, **kwargs):
        return {"status": "available", "models": ["muse-spark-1.3"]}

    monkeypatch.setattr(MetaProvider, "discover", discover)
    settings = Settings(
        _env_file=None,
        alive_meta_api_key=FAKE_KEY,
        database_url=f"sqlite+aiosqlite:///{tmp_path}/meta.db",
        alive_api_token=TOKEN,
        alive_heartbeat_seconds=0.1,
        alive_workspace=tmp_path / "workspace",
    )

    async def schema():
        db = Database(settings.database_url)
        async with db.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await db.engine.dispose()

    asyncio.run(schema())
    with TestClient(create_app(settings), headers={"Authorization": f"Bearer {TOKEN}"}) as c:
        yield c


def _canned_handler(captured):
    def handler(request):
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": ROLE_JSON}, "finish_reason": "stop"}],
                "usage": dict(USAGE),
            },
        )

    return handler


def _request_kwargs(**over):
    kwargs = {
        "operation": "cognition.role",
        "instructions": "Assess the observation.",
        "data": {"observation": "green light", "sources": []},
        "schema": {"type": "object"},
        "model": "muse-spark-1.3",
        "max_output": 1536,
        "correlation": "call-123",
    }
    kwargs.update(over)
    return kwargs


def _settings():
    from alive.config import Settings

    return Settings(
        _env_file=None,
        alive_meta_api_key=FAKE_KEY,
        database_url="sqlite+aiosqlite:///:memory:",
        alive_api_token="t" * 32,
    )


def test_gateway_parity_with_direct_call():
    import asyncio

    from alive.providers import MetaProvider

    async def run():
        direct_seen, gateway_seen = [], []

        async def direct():
            return await MetaProvider(_settings()).structured(
                "Assess the observation.",
                {"observation": "green light", "sources": []},
                {"type": "object"},
                model="muse-spark-1.3",
                max_output=1536,
                correlation="call-123",
                transport=httpx.MockTransport(_canned_handler(direct_seen)),
            )

        async def gatewayed():
            return await DirectMetaGateway(
                _settings(), transport=httpx.MockTransport(_canned_handler(gateway_seen))
            ).structured(StructuredRequest(**_request_kwargs()))

        return await direct(), await gatewayed(), direct_seen, gateway_seen

    before, after, direct_seen, gateway_seen = asyncio.run(run())
    assert json.loads(direct_seen[0].read()) == json.loads(gateway_seen[0].read())
    assert dict(direct_seen[0].headers) == dict(gateway_seen[0].headers)
    assert before.text == after.text == ROLE_JSON
    assert before.usage == after.usage == USAGE


def test_gateway_parity_correlation_only_changes_request_id():
    import asyncio

    async def run():
        seen = []

        async def once(correlation):
            return await DirectMetaGateway(
                _settings(), transport=httpx.MockTransport(_canned_handler(seen))
            ).structured(StructuredRequest(**_request_kwargs(correlation=correlation)))

        await once("call-a")
        await once("call-b")
        return seen

    seen = asyncio.run(run())
    first, second = (dict(r.headers) for r in seen)
    # httpx normalises header names to lowercase.
    assert first["x-request-id"] == "call-a"
    assert second["x-request-id"] == "call-b"
    rest_first = {k: v for k, v in first.items() if k != "x-request-id"}
    rest_second = {k: v for k, v in second.items() if k != "x-request-id"}
    assert rest_first == rest_second
    assert json.loads(seen[0].read())["model"] == "muse-spark-1.3"


def test_gateway_for_routes_and_rejects_unknown():
    gateway = gateway_for(_settings(), "cognition.role")
    assert isinstance(gateway, DirectMetaGateway)
    with pytest.raises(KeyError):
        gateway_for(_settings(), "no.such.operation")


def _run_meta_investigation(client, **config):
    from tests.test_cognition import completed, observe

    if config:
        assert client.post("/api/v1/cognition/configuration", json=config).status_code == 200
    payload = {"command": "start", "provider": "meta"}
    assert client.post("/api/v1/cognition/control", json=payload).status_code == 200
    observe(client)
    return completed(client)


def test_migrated_path_records_identical_invocation_row(metaclient, monkeypatch):
    import re

    from alive import cognition as cognition_module
    from alive.society import mock_role

    captured = []
    calls = {"n": 0}
    roles = ["observer", "proposer", "critic"]

    def handler(request):

        captured.append(request)
        body = json.loads(request.content.decode())
        match = re.search(r"Role (\w+) spec", body["messages"][0]["content"])
        role = match.group(1) if match else roles[calls["n"] % len(roles)]
        context = json.loads(body["messages"][1]["content"])
        output = mock_role(role, context)
        calls["n"] += 1
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": output.model_dump_json()},
                        "finish_reason": "stop",
                    }
                ],
                "usage": dict(USAGE),
            },
        )

    real_gateway_for = cognition_module.gateway_for

    def gateway_for_test(settings, operation):
        gateway = real_gateway_for(settings, operation)
        gateway.transport = httpx.MockTransport(handler)
        return gateway

    monkeypatch.setattr(cognition_module, "gateway_for", gateway_for_test)
    result = _run_meta_investigation(metaclient, use_critic=True)
    assert result["state"] == "COMPLETED", result
    assert calls["n"] == 3, "observer, proposer and critic must each dispatch once"
    assert captured, "expected upstream requests through the gateway"
    for request in captured:
        sent = json.loads(request.read())
        assert sent["model"] == "muse-spark-1.3"
        assert [m["role"] for m in sent["messages"]] == ["developer", "user"]
        user_content = json.loads(sent["messages"][1]["content"])
        assert isinstance(user_content, dict)
        assert sent["max_completion_tokens"] == 1536  # cfg.output_tokens default
        assert sent["reasoning_effort"] == "minimal"
        assert sent["response_format"]["type"] == "json_schema"
        assert request.headers["Authorization"] == "Bearer " + FAKE_KEY
    invocations = result["invocations"]
    assert invocations, "expected ModelInvocation rows"
    for invocation in invocations:
        assert invocation["provider"] == "meta"
        assert invocation["model"] == "muse-spark-1.3"
        assert invocation["status"] == "validated"
        assert invocation["usage"]["total_tokens"] == USAGE["total_tokens"]
        assert invocation["usage"]["charged_tokens"] == USAGE["total_tokens"]
        assert invocation["reserved_tokens"] >= USAGE["total_tokens"]
        assert invocation["latency_ms"] > 0
        assert invocation["output_json"]["recommendation"] == "proceed"


def test_sentinel_still_bites_through_gateway(metaclient, monkeypatch):
    from alive.providers import MetaProvider

    hits = []

    async def forbidden(*args, **kwargs):
        hits.append(args)
        raise AssertionError("forbidden upstream dispatch")

    monkeypatch.setattr(MetaProvider, "_request", forbidden)
    run = _run_meta_investigation(metaclient)
    assert run["state"] == "FAILED"
    assert "AssertionError" in (run.get("error") or "")
    assert len(hits) == 1, f"sentinel must fire exactly once, saw {len(hits)}"
    assert run["invocations"] and all(i["status"] == "failed" for i in run["invocations"])


def test_ceiling_blocks_over_limit_request_with_zero_dispatch(metaclient, monkeypatch):
    from alive.providers import MetaProvider

    hits = []

    async def forbidden(*args, **kwargs):
        hits.append(args)
        raise AssertionError("forbidden upstream dispatch")

    monkeypatch.setattr(MetaProvider, "_request", forbidden)
    assert (
        metaclient.post("/api/v1/cognition/configuration", json={"request_tokens": 512}).status_code
        == 200
    )
    run = _run_meta_investigation(metaclient)
    assert run["state"] == "FAILED"
    assert "Per-request" in (run.get("error") or "")
    assert run["usage"]["calls"] == 0
    assert run["invocations"] == []
    assert hits == [], "over-limit request must never reach the provider"


def test_ceiling_mutation_is_detected(metaclient, monkeypatch):
    """Neuter the ceiling by hand: the same request must then dispatch.

    Proves the zero-dispatch verdict above comes from the guard, not from a
    harness that could never dispatch.
    """
    from alive.cognitive_schema import CognitiveConfiguration
    from alive.providers import MetaProvider

    hits = []

    async def forbidden(*args, **kwargs):
        hits.append(args)
        raise AssertionError("forbidden upstream dispatch")

    monkeypatch.setattr(MetaProvider, "_request", forbidden)
    real_validate = CognitiveConfiguration.model_validate

    @classmethod
    def inflated(cls, data):
        config = real_validate(data)
        object.__setattr__(config, "request_tokens", 10**9)
        return config

    monkeypatch.setattr(CognitiveConfiguration, "model_validate", inflated)
    assert (
        metaclient.post("/api/v1/cognition/configuration", json={"request_tokens": 512}).status_code
        == 200
    )
    run = _run_meta_investigation(metaclient)
    assert run["state"] == "FAILED"
    assert len(hits) >= 1, "neutered ceiling must allow dispatch (mutation detected)"


# ---------------------------------------------------------------------------
# Ratchet: no new direct MetaProvider construction sites.
# ---------------------------------------------------------------------------

ALLOWLIST = [
    # (path, function, kind, owner, removal milestone)
    (
        "alive/model_gateway.py",
        "structured",
        "structured",
        "PI-01A",
        "permanent seam: the only authorized construction",
    ),
    (
        "alive/app.py",
        "capabilities",
        "capabilities",
        "PI-01A",
        "keep: health reporting probe, no dispatch",
    ),
    ("alive/cognition.py", "command", "discover", "PI-01A", "governor-consolidation"),
    ("alive/cognitive_api.py", "probe", "discover", "PI-01A", "governor-consolidation"),
    ("alive/living.py", "create", "discover", "PI-01A", "governor-consolidation"),
    ("alive/living.py", "reason", "structured", "PI-01A", "governor-consolidation"),
    ("alive/experiment/service.py", "start", "discover", "PI-01A", "governor-consolidation"),
    ("alive/experiment/service.py", "call", "structured", "PI-01A", "governor-consolidation"),
    (
        "alive/research_relationships.py",
        "_analyze_bounded",
        "structured",
        "PI-01A",
        "governor-consolidation",
    ),
    (
        "alive/research_relationships.py",
        "analyze",
        "structured",
        "PI-01A",
        "governor-consolidation",
    ),
    ("alive/web_experience.py", "execute", "structured", "PI-01A", "governor-consolidation"),
    (
        "scripts/benchmark.py",
        "run_benchmark",
        "discover",
        "PI-01A",
        "keep: explicit opt-in benchmark",
    ),
    ("scripts/benchmark.py", "invoke", "structured", "PI-01A", "keep: explicit opt-in benchmark"),
    ("scripts/native11.py", "qualify", "discover", "PI-01A", "keep: qualification script"),
]


def find_meta_constructions(*roots):
    """Return [(path, function, kinds)] for every MetaProvider(...) construction.

    Paths are relative to the common root. Kinds are the methods invoked on the
    constructed provider (chained or via an assigned name) among
    {structured, discover, capabilities}.
    """
    roots = [Path(r) for r in roots]
    base = Path(os.path.commonpath([str(r) for r in roots]))
    findings = []
    for root in roots:
        for path in sorted(root.rglob("*.py")):
            rel = path.relative_to(base).as_posix()
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                continue
            parents = {}

            def index(node, parent=None):
                parents[node] = parent
                for child in ast.iter_child_nodes(node):
                    index(child, node)

            index(tree, None)

            def walk(node, func):
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        walk(child, child.name)
                        continue
                    if isinstance(child, ast.Call):
                        func_node = getattr(child, "func", None)
                        name = getattr(func_node, "id", None) or getattr(func_node, "attr", None)
                        if name == "MetaProvider":
                            parent = parents.get(child)
                            if isinstance(parent, ast.Attribute) and parent.attr in (
                                "structured",
                                "discover",
                                "capabilities",
                            ):
                                kinds = {parent.attr}
                            else:
                                kinds = set()
                                target = None
                                if isinstance(parent, ast.Assign) and len(parent.targets) == 1:
                                    target = parent.targets[0]
                                elif isinstance(parent, ast.AnnAssign):
                                    target = parent.target
                                if isinstance(target, ast.Name):
                                    for sub in ast.walk(node):
                                        if (
                                            isinstance(sub, ast.Attribute)
                                            and isinstance(sub.value, ast.Name)
                                            and sub.value.id == target.id
                                            and sub.attr
                                            in ("structured", "discover", "capabilities")
                                        ):
                                            kinds.add(sub.attr)
                            findings.append((rel, func or "<module>", kinds))
                    walk(child, func)

            walk(tree, None)
    return findings


def check_allowlist(findings):
    allowed = {
        (path, func): kinds
        for path, func, kinds, _, _ in [(p, f, {k}, o, m) for p, f, k, o, m in ALLOWLIST]
    }
    violations = []
    for path, func, kinds in findings:
        key = (path, func)
        if key not in allowed or not kinds <= allowed[key]:
            violations.append((path, func, sorted(kinds)))
    return violations


def test_ratchet_no_new_direct_meta_construction():
    root = Path(__file__).resolve().parents[1]
    violations = check_allowlist(find_meta_constructions(root / "alive", root / "scripts"))
    assert violations == [], f"new direct MetaProvider sites: {violations}"


def test_ratchet_catches_new_site(tmp_path):
    rogue = tmp_path / "rogue.py"
    rogue.write_text(
        "from alive.providers import MetaProvider\n"
        "async def run(settings):\n"
        "    return await MetaProvider(settings).structured('i', {}, {}, model='m')\n"
    )
    violations = check_allowlist(find_meta_constructions(tmp_path))
    assert violations == [("rogue.py", "run", ["structured"])]
