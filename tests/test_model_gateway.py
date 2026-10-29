"""PI-01A dispatch seam: parity, sentinels, ratchet (R2-hardened), ceiling, budget.

The migration changes exactly one dispatch expression
(`alive/cognition.py::call_role`); reservation, ModelInvocation writes,
exception handling and ordering are untouched.

R2 hardening (independent review): the ratchet now pins exact call sites with
counts, resolves aliases/subclasses/getattr indirection, fails closed on
ambiguous or unparseable code, and enforces a credential-access rule. Field
pass-through tests pin every StructuredRequest field on the wire, a golden
file pins the full migrated request shape, and the per-investigation call
budget gets a non-vacuous regression test with a mutation control.
"""

import ast
import json
import os
import re
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
                _settings(),
                "cognition.role",
                transport=httpx.MockTransport(_canned_handler(gateway_seen)),
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
                _settings(),
                "cognition.role",
                transport=httpx.MockTransport(_canned_handler(seen)),
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
    assert gateway.operation == "cognition.role"
    with pytest.raises(KeyError):
        gateway_for(_settings(), "no.such.operation")


def test_gateway_rejects_operation_mismatch_without_dispatch():
    import asyncio

    seen = []

    async def run():
        gateway = DirectMetaGateway(
            _settings(),
            "cognition.role",
            transport=httpx.MockTransport(_canned_handler(seen)),
        )
        with pytest.raises(ValueError, match="Operation mismatch"):
            await gateway.structured(StructuredRequest(**_request_kwargs(operation="other.op")))

    asyncio.run(run())
    assert seen == [], "mismatched operation must never reach the transport"


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
        sent = json.loads(request.content.decode())
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


def _counting_mock_transport(captured):
    import re

    from alive.society import mock_role

    def handler(request):
        captured.append(request)
        body = json.loads(request.content.decode())
        match = re.search(r"Role (\w+) spec", body["messages"][0]["content"])
        role = match.group(1) if match else "observer"
        context = json.loads(body["messages"][1]["content"])
        output = mock_role(role, context)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": output.model_dump_json()}, "finish_reason": "stop"}
                ],
                "usage": dict(USAGE),
            },
        )

    return httpx.MockTransport(handler)


def test_calls_budget_blocks_second_dispatch(metaclient, monkeypatch):
    """Per-investigation call budget: exceeding it dispatches nothing further."""
    from alive import cognition as cognition_module

    captured = []
    real_gateway_for = cognition_module.gateway_for

    def gateway_for_test(settings, operation):
        gateway = real_gateway_for(settings, operation)
        gateway.transport = _counting_mock_transport(captured)
        return gateway

    monkeypatch.setattr(cognition_module, "gateway_for", gateway_for_test)
    assert (
        metaclient.post(
            "/api/v1/cognition/configuration", json={"investigation_calls": 1}
        ).status_code
        == 200
    )
    run = _run_meta_investigation(metaclient)
    assert run["state"] == "FAILED"
    assert "budget" in (run.get("error") or "").lower()
    assert len(captured) == 1, f"exactly one dispatch before the budget trips, saw {len(captured)}"
    assert run["usage"]["calls"] == 1
    assert len(run["invocations"]) == 1
    assert run["invocations"][0]["status"] == "validated"


def test_calls_budget_mutation_is_detected(metaclient, monkeypatch):
    """Raise the persisted investigation budget: the second dispatch then occurs.

    The guard code is untouched; only its input (the investigation row budget,
    set at admission from `investigation_calls`) is mutated. This proves the
    zero-additional-dispatch result above is caused by the budget guard.
    """
    from alive import cognition as cognition_module
    from alive.cognition import Cognition
    from alive.cognitive_models import Investigation

    captured = []
    real_gateway_for = cognition_module.gateway_for

    def gateway_for_test(settings, operation):
        gateway = real_gateway_for(settings, operation)
        gateway.transport = _counting_mock_transport(captured)
        return gateway

    monkeypatch.setattr(cognition_module, "gateway_for", gateway_for_test)

    real_call_role = Cognition.call_role

    async def inflated_budget(self, run_id, role, context):
        async with self.k.db.sessions.begin() as session:
            row = await session.get(Investigation, run_id)
            if row and row.budget["calls"] <= 1:
                row.budget = {**row.budget, "calls": 10**9, "tokens": 10**12}
        return await real_call_role(self, run_id, role, context)

    monkeypatch.setattr(Cognition, "call_role", inflated_budget)
    assert (
        metaclient.post(
            "/api/v1/cognition/configuration", json={"investigation_calls": 1}
        ).status_code
        == 200
    )
    run = _run_meta_investigation(metaclient)
    assert run["state"] == "COMPLETED", run
    assert len(captured) == 2, f"neutered budget must allow both dispatches, saw {len(captured)}"


# ---------------------------------------------------------------------------
# R2 field pass-through on the REAL migrated path.
#
# A spy wraps the production gateway and records the StructuredRequest built by
# cognition.call_role. Expectations come from code the migration does not touch
# (society.role_prompt, the RoleOutput schema, pinned settings defaults, the
# committed golden artifact, and the persisted invocation identity), so a drift
# in cognition.py fails the corresponding test rather than moving both sides.
# ---------------------------------------------------------------------------


class _SpyGateway:
    def __init__(self, inner):
        self.inner = inner
        self.requests = []
        self.bodies = []

    async def structured(self, req):
        self.requests.append(req)
        return await self.inner.structured(req)


def _spy_run(metaclient, monkeypatch, use_critic=False):
    import httpx as _httpx

    from alive import cognition as cognition_module

    real_gateway_for = cognition_module.gateway_for
    spy = _SpyGateway(None)

    def handler(request):
        spy.bodies.append(request)
        return _httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": ROLE_JSON}, "finish_reason": "stop"}],
                "usage": dict(USAGE),
            },
        )

    transport = _httpx.MockTransport(handler)

    def gateway_for_test(settings, operation):
        # Route through the real factory so an unknown/mismatched operation
        # raises exactly as production would (a mutation must not be masked).
        inner = real_gateway_for(settings, operation)
        inner.transport = transport
        spy.inner = inner
        return spy

    monkeypatch.setattr(cognition_module, "gateway_for", gateway_for_test)
    run = _run_meta_investigation(metaclient, **({"use_critic": True} if use_critic else {}))
    return run, spy


def test_field_instructions_match_independent_role_prompt(metaclient, monkeypatch):
    from alive.society import role_prompt

    run, spy = _spy_run(metaclient, monkeypatch)
    assert run["state"] in ("COMPLETED", "ABSTAINED"), run
    assert spy.requests, "expected at least one dispatch"
    assert spy.requests[0].instructions == role_prompt("observer")


def test_field_data_matches_committed_golden_context(metaclient, monkeypatch):
    run, spy = _spy_run(metaclient, monkeypatch)
    assert run["state"] in ("COMPLETED", "ABSTAINED"), run
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    expected = json.loads(golden["requests"][0]["body"]["messages"][1]["content"])
    assert _normalize(spy.requests[0].data) == expected
    assert "injected" not in spy.requests[0].data


def test_field_schema_matches_role_output_schema(metaclient, monkeypatch):
    from alive.cognitive_schema import RoleOutput

    run, spy = _spy_run(metaclient, monkeypatch)
    assert run["state"] in ("COMPLETED", "ABSTAINED"), run
    assert spy.requests[0].schema == RoleOutput.model_json_schema()


def test_field_model_matches_selected_default(metaclient, monkeypatch):
    run, spy = _spy_run(metaclient, monkeypatch)
    assert run["state"] in ("COMPLETED", "ABSTAINED"), run
    assert spy.requests[0].model == "muse-spark-1.3"


def test_field_max_output_matches_configured_limit(metaclient, monkeypatch):
    from alive.cognitive_schema import CognitiveConfiguration

    run, spy = _spy_run(metaclient, monkeypatch)
    assert run["state"] in ("COMPLETED", "ABSTAINED"), run
    assert spy.requests[0].max_output == CognitiveConfiguration().output_tokens


def test_field_correlation_matches_persisted_invocation(metaclient, monkeypatch):
    run, spy = _spy_run(metaclient, monkeypatch)
    assert run["state"] in ("COMPLETED", "ABSTAINED"), run
    invocation_ids = {row["id"] for row in run["invocations"]}
    assert spy.requests[0].correlation in invocation_ids
    assert spy.bodies[0].headers["x-request-id"] == spy.requests[0].correlation


def test_field_operation_matches_gateway_route(metaclient, monkeypatch):
    run, spy = _spy_run(metaclient, monkeypatch)
    assert run["state"] in ("COMPLETED", "ABSTAINED"), run
    assert spy.inner.operation == "cognition.role"
    assert spy.requests[0].operation == "cognition.role"


def test_field_operation_mismatch_rejected_by_gateway():
    import asyncio

    seen = []

    async def run():
        gateway = DirectMetaGateway(
            _settings(),
            "cognition.role",
            transport=httpx.MockTransport(_canned_handler(seen)),
        )
        with pytest.raises(ValueError, match="Operation mismatch"):
            await gateway.structured(StructuredRequest(**_request_kwargs(operation="other.op")))

    asyncio.run(run())
    assert seen == []


# ---------------------------------------------------------------------------
# R2 golden request: full migrated wire shape pinned to a committed file.
# Regenerate deliberately: any request-construction change fails this test.
# ---------------------------------------------------------------------------

GOLDEN_PATH = Path(__file__).parent / "fixtures" / "pi01a_golden_request.json"
_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)


def _normalize(obj):
    if isinstance(obj, dict):
        return {k: _normalize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize(v) for v in obj]
    if isinstance(obj, str):
        return _UUID_RE.sub("<ID>", obj)
    return obj


def test_golden_migrated_request_shape(metaclient, monkeypatch):
    import re as _re  # noqa: F401 (keeps stdlib import local to the networked test)

    from alive import cognition as cognition_module

    captured = []

    def handler(request):
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": ROLE_JSON}, "finish_reason": "stop"}],
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
    assert result["state"] in ("COMPLETED", "ABSTAINED")
    assert len(captured) == 3, "observer, proposer and critic must each dispatch once"
    normalized = []
    for request in captured:
        headers = {k: v for k, v in request.headers.items() if k != "x-request-id"}
        normalized.append(
            {"headers": headers, "body": _normalize(json.loads(request.content.decode()))}
        )
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    assert normalized == golden["requests"], "migrated request shape changed; inspect the diff"


# ---------------------------------------------------------------------------
# Ratchet R2: no unauthorized Meta dispatch path.
#
# A static scan is a regression guard, not a security boundary: it cannot see
# through dynamic imports or runtime indirection. Real enforcement for PI-01B
# is the ALIVE-owned credential plus the metered egress gateway. This ratchet
# guarantees every *static* dispatch path is an explicitly listed one.
# ---------------------------------------------------------------------------

PROVIDER_METHODS = {"structured", "discover", "capabilities", "generate", "decide", "stream"}

# (path, function, kinds, expected_count, owner, removal milestone)
ALLOWLIST = [
    ("alive/model_gateway.py", "structured", {"structured"}, 1, "PI-01A", "permanent seam"),
    ("alive/app.py", "capabilities", {"capabilities"}, 1, "PI-01A", "keep: health probe"),
    ("alive/cognition.py", "command", {"discover"}, 1, "PI-01A", "governor-consolidation"),
    ("alive/cognitive_api.py", "probe", {"discover"}, 1, "PI-01A", "governor-consolidation"),
    ("alive/living.py", "create", {"discover"}, 1, "PI-01A", "governor-consolidation"),
    ("alive/living.py", "reason", {"structured"}, 1, "PI-01A", "governor-consolidation"),
    ("alive/experiment/service.py", "start", {"discover"}, 1, "PI-01A", "governor-consolidation"),
    ("alive/experiment/service.py", "call", {"structured"}, 1, "PI-01A", "governor-consolidation"),
    (
        "alive/research_relationships.py",
        "_analyze_bounded",
        {"structured"},
        1,
        "PI-01A",
        "governor-consolidation",
    ),
    (
        "alive/research_relationships.py",
        "analyze",
        {"structured"},
        1,
        "PI-01A",
        "governor-consolidation",
    ),
    ("alive/web_experience.py", "execute", {"structured"}, 1, "PI-01A", "governor-consolidation"),
    (
        "scripts/benchmark.py",
        "run_benchmark",
        {"discover"},
        1,
        "PI-01A",
        "keep: explicit opt-in benchmark",
    ),
    (
        "scripts/benchmark.py",
        "invoke",
        {"structured"},
        1,
        "PI-01A",
        "keep: explicit opt-in benchmark",
    ),
    ("scripts/native11.py", "qualify", {"discover"}, 1, "PI-01A", "keep: qualification script"),
]

# Credential rule: (path, allowed kind set). Kinds are attribute reads
# (credential:key/url), sensitive literals, and env lookups.
CREDENTIAL_ALLOWLIST = {
    "config.py": {"credential:key", "credential:url", "credential:literal", "credential:env"},
    "providers.py": {"credential:key", "credential:url"},
    "provenance.py": {"credential:url"},
}


def _dotted(node, aliases):
    """Resolve Name/Attribute chains through import aliases to dotted paths."""
    if isinstance(node, ast.Name):
        return aliases.get(node.id)
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value, aliases)
        if base is None:
            return None
        return base + "." + node.attr
    return None


def _collect_imports(tree_or_node):
    aliases = {}
    for node in ast.walk(tree_or_node):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.asname:
                    aliases[a.asname] = a.name
                else:
                    aliases[a.name.split(".")[0]] = a.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            for a in node.names:
                if a.name == "*":
                    continue
                aliases[a.asname or a.name] = (node.module or "") + "." + a.name
    return aliases


def _is_getattr_call(node):
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name) and func.id == "getattr":
        return True
    return isinstance(func, ast.Attribute) and func.attr == "getattr"


def _classifies_as_provider_dotted(dotted):
    return dotted == "alive.providers.MetaProvider"


def find_meta_constructions(*roots):
    """Return [(path, function, kinds, flags)] for provider-related activity.

    Paths are relative to the common root. Kinds are invoked method names plus
    marker kinds: ambiguous, dynamic, unbound, subclass, parse-error. Flags
    explain how the construction was classified.
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
                findings.append((rel, "<module>", {"parse-error"}, {"unreadable-or-unparseable"}))
                continue
            file_aliases = _collect_imports(tree)
            file_subclasses = set()
            file_env = {}
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    for b in node.bases:
                        dotted = _dotted(b, file_aliases)
                        if dotted == "alive.providers.MetaProvider" or dotted in file_subclasses:
                            file_subclasses.add(node.name)
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    if len(targets) == 1 and isinstance(targets[0], ast.Name):
                        dotted = _dotted(node.value, file_aliases)
                        if dotted == "alive.providers.MetaProvider" or dotted in file_subclasses:
                            file_env[targets[0].id] = ("ctor-alias", targets[0].id)
            scopes = [("<module>", tree)]
            scopes.extend(
                (n.name, n)
                for n in ast.walk(tree)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            )
            scopes.extend(
                (f"<class {n.name}>", n) for n in ast.walk(tree) if isinstance(n, ast.ClassDef)
            )
            seen = set()
            for func_name, scope_node in scopes:
                if id(scope_node) in seen:
                    continue
                seen.add(id(scope_node))
                findings.extend(
                    _scan_scope(scope_node, rel, func_name, file_aliases, file_subclasses, file_env)
                )
    return findings


def _scan_scope(scope_node, path, func_name, file_aliases, file_subclasses, file_env):
    findings = []
    aliases = dict(file_aliases)
    for node in ast.walk(scope_node):
        if isinstance(node, (ast.Import, ast.ImportFrom)) and node is not scope_node:
            aliases.update(_collect_imports(node))
    env = dict(file_env)
    subclasses = set(file_subclasses)

    def local_nodes():
        if isinstance(scope_node, ast.Module):
            children = list(scope_node.body)
        else:
            children = list(scope_node.body)
        stack = list(children)
        while stack:
            node = stack.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node is not scope_node:
                    continue
            yield node
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            stack.extend(ast.iter_child_nodes(node))

    nodes = list(local_nodes())

    def resolve(node):
        if isinstance(node, ast.Name):
            if node.id in env:
                return env[node.id]
            if node.id in aliases:
                dotted = aliases[node.id]
                if dotted == "alive.providers.MetaProvider":
                    return ("provider-class", node.id)
                if dotted in subclasses:
                    return ("provider-subclass", node.id)
                if dotted.endswith(".MetaProvider"):
                    return ("unknown-provider", node.id)
                return ("module-path", dotted)
            if node.id in subclasses:
                return ("provider-subclass", node.id)
            if node.id == "MetaProvider":
                return ("unknown-provider", node.id)
            return ("unknown", node.id)
        if isinstance(node, ast.Attribute):
            base = resolve(node.value)
            if base is None or base[0] == "unknown":
                if node.attr == "MetaProvider":
                    return ("unknown-provider", node.attr)
                return ("unknown", node.attr)
            if base[0] == "module-path":
                dotted = base[1] + "." + node.attr
                if dotted == "alive.providers.MetaProvider":
                    return ("provider-class", node.attr)
                return ("module-path", dotted)
            if base[0] in ("provider-class", "ctor-alias", "provider-subclass"):
                return ("unbound-method", node.attr)
            if base[0] == "instance":
                return ("instance-method", node.attr)
            return ("unknown", node.attr)
        return ("unknown", None)

    def is_provider_class(ref):
        return ref is not None and (
            ref == ("module-path", "alive.providers.MetaProvider") or ref[0] == "provider-class"
        )

    for _pass in range(2):
        for node in nodes:
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    ref = resolve(base)
                    if is_provider_class(ref) or (
                        ref is not None and ref[0] == "provider-subclass"
                    ):
                        subclasses.add(node.name)
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if len(targets) != 1 or not isinstance(targets[0], ast.Name):
                    continue
                name = targets[0].id
                value = node.value
                if isinstance(value, ast.Call):
                    if _is_getattr_call(value):
                        env[name] = ("dynamic", name)
                    else:
                        ref = resolve(value.func)
                        if is_provider_class(ref) or (
                            ref is not None and ref[0] in ("provider-subclass", "ctor-alias")
                        ):
                            env[name] = ("instance", name)
                        elif ref is not None and ref[0] == "unknown-provider":
                            env[name] = ("unknown-provider-instance", name)
                else:
                    ref = resolve(value)
                    if is_provider_class(ref):
                        env[name] = ("ctor-alias", name)
                    elif ref is not None and ref[0] == "provider-subclass":
                        env[name] = ("ctor-alias", name)
    parents = {}
    for node in nodes:
        for child in ast.iter_child_nodes(node):
            parents.setdefault(child, node)
    pending = {}
    for node in nodes:
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if _is_getattr_call(node):
            args = node.args
            hits = any(isinstance(a, ast.Constant) and a.value == "MetaProvider" for a in args)
            if not hits and args and isinstance(args[0], (ast.Name, ast.Attribute)):
                ref = resolve(args[0])
                hits = ref is not None and (
                    ref[0]
                    in (
                        "provider-class",
                        "provider-subclass",
                        "ctor-alias",
                        "instance",
                    )
                    or (ref[0] == "module-path" and "MetaProvider" in ref[1])
                    or (ref[0] == "unknown" and "MetaProvider" in str(ref[1]))
                )
            if hits:
                findings.append((path, func_name, {"dynamic"}, {"dynamic-getattr"}))
            continue
        kinds = None
        flags = set()
        assigned_target = None
        if isinstance(func, ast.Attribute):
            base = resolve(func.value)
            if base == ("module-path", "alive.providers") and func.attr == "MetaProvider":
                kinds, flags = {"ambiguous"}, {"unresolved-target"}
            elif base is not None and base[0] in (
                "provider-class",
                "ctor-alias",
                "provider-subclass",
            ):
                kinds, flags = {func.attr}, {"unbound-method"}
            elif base is not None and base[0] == "unknown-provider":
                kinds, flags = {"ambiguous"}, {"unresolved-provider"}
            elif isinstance(func.value, ast.Call):
                inner = func.value
                iref = resolve(inner.func) if isinstance(inner, ast.Call) else None
                if iref is not None and (
                    is_provider_class(iref) or iref[0] in ("provider-subclass", "ctor-alias")
                ):
                    kinds, flags = {func.attr}, {"chained"}
        elif isinstance(func, ast.Name):
            ref = resolve(func)
            if ref is not None:
                kind, _name = ref
                if kind in ("provider-class", "ctor-alias", "provider-subclass"):
                    parent = parents.get(node)
                    if (
                        isinstance(parent, ast.Attribute)
                        and parent.value is node
                        and isinstance(parents.get(parent), ast.Call)
                        and parents.get(parent).func is parent
                    ):
                        continue  # inner call of a chained call; counted at the outer call
                    if isinstance(parent, ast.Attribute) and parent.attr in PROVIDER_METHODS:
                        kinds, flags = {parent.attr}, {"chained"}
                    else:
                        target = None
                        if isinstance(parent, ast.Assign) and len(parent.targets) == 1:
                            target = parent.targets[0]
                        elif isinstance(parent, ast.AnnAssign):
                            target = parent.target
                        if isinstance(target, ast.Name):
                            assigned_target = target.id
                        else:
                            kinds, flags = {"ambiguous"}, {"unresolved-use"}
                elif kind == "unknown-provider":
                    kinds, flags = {"ambiguous"}, {"unresolved-provider"}
                elif kind == "dynamic":
                    kinds, flags = {"ambiguous"}, {"dynamic-alias"}
        if kinds is None and assigned_target is None:
            continue
        if assigned_target is not None:
            pending[assigned_target] = pending.get(assigned_target, 0) + 1
            continue
        findings.append((path, func_name, kinds, flags))
    for name, constructions in pending.items():
        used = sorted(
            {
                sub.attr
                for sub in nodes
                if isinstance(sub, ast.Attribute)
                and isinstance(sub.value, ast.Name)
                and sub.value.id == name
                and isinstance(sub.attr, str)
            }
        )
        methods = {m for m in used if m in PROVIDER_METHODS}
        others = [
            n
            for n in nodes
            if isinstance(n, ast.Name)
            and n.id == name
            and not isinstance(n.ctx, (ast.Store, ast.Del))
        ]
        # One finding per construction: an extra constructor must never be
        # merged away by sharing a variable name with a legitimate one.
        for _ in range(constructions):
            if methods:
                findings.append((path, func_name, methods, {"assigned"}))
            elif others:
                findings.append((path, func_name, {"ambiguous"}, {"opaque-use"}))
            else:
                findings.append((path, func_name, {"ambiguous"}, {"unused-assignment"}))
    return findings


BENIGN_FLAGS = {"chained", "assigned"}


def check_allowlist(findings):
    allowed = {(p, f): (k, n) for p, f, k, n, _, _ in ALLOWLIST}
    counts = {}
    unions = {}
    for path, func, kinds, flags in findings:
        key = (path, func)
        counts[key] = counts.get(key, 0) + 1
        union, current = unions.get(key, (set(), set()))
        union.update(kinds)
        current.update(flags)
        unions[key] = (union, current)
    violations = []
    for path, func in sorted(counts):
        kinds, flags = unions[(path, func)]
        total = counts[(path, func)]
        if set(flags) - BENIGN_FLAGS or (path, func) not in allowed:
            violations.append((path, func, sorted(kinds), sorted(flags), total, None))
            continue
        exp_kinds, exp_count = allowed[(path, func)]
        if set(kinds) != set(exp_kinds) or total != exp_count:
            violations.append((path, func, sorted(kinds), sorted(flags), total, exp_count))
    # Reverse inventory: a deleted expected site must fail closed, not vanish.
    for path, func in sorted(set(allowed) - set(counts)):
        exp_kinds, exp_count = allowed[(path, func)]
        violations.append((path, func, sorted(exp_kinds), ["missing-expected-site"], 0, exp_count))
    return violations


def find_credential_uses(*roots):
    """Return [(path, function, kinds)] for Meta credential material.

    Only files under alive/ are scanned; paths are relative to the common root.
    """
    roots = [Path(r) for r in roots]
    findings = []

    def credential_kind_for_call(func, args):
        names = [a.value for a in args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        if isinstance(func, ast.Attribute) and func.attr == "getenv":
            if isinstance(func.value, ast.Name) and func.value.id == "os":
                keys = names
            else:
                return None
        elif isinstance(func, ast.Name) and func.id in ("getenv", "environ"):
            keys = names
        elif (
            isinstance(func, ast.Attribute)
            and func.attr == "get"
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "environ"
            and isinstance(func.value.value, ast.Name)
            and func.value.value.id == "os"
        ):
            keys = names
        else:
            return None
        if any("API_KEY" in k or "MODEL_API_KEY" in k for k in keys):
            return "credential:env"
        return None

    for root in roots:
        for path in sorted(root.rglob("*.py")):
            rel = path.relative_to(root).as_posix()
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                findings.append((rel, "<module>", {"parse-error"}))
                continue

            def walk(node, func, rel=rel, findings=findings):
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        walk(child, child.name)
                        continue
                    if isinstance(child, ast.Attribute):
                        if child.attr == "alive_meta_api_key":
                            findings.append((rel, func or "<module>", {"credential:key"}))
                        elif child.attr in ("alive_meta_url", "alive_meta_base_url"):
                            findings.append((rel, func or "<module>", {"credential:url"}))
                    if isinstance(child, ast.Constant) and isinstance(child.value, str):
                        if (
                            "META_API_KEY" in child.value
                            or "MODEL_API_KEY" in child.value
                            or "api.meta.ai" in child.value
                        ):
                            findings.append((rel, func or "<module>", {"credential:literal"}))
                    if isinstance(child, ast.Call):
                        kind = credential_kind_for_call(child.func, child.args)
                        if kind:
                            findings.append((rel, func or "<module>", {kind}))
                    if isinstance(child, ast.Subscript):
                        value = child.value
                        key = None
                        if (
                            isinstance(value, ast.Attribute)
                            and value.attr == "environ"
                            and isinstance(value.value, ast.Name)
                            and value.value.id == "os"
                        ):
                            sl = child.slice
                            if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
                                key = sl.value
                        elif isinstance(value, ast.Name) and value.id == "environ":
                            sl = child.slice
                            if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
                                key = sl.value
                        if key and ("API_KEY" in key or "MODEL_API_KEY" in key):
                            findings.append((rel, func or "<module>", {"credential:env"}))
                    walk(child, func)

            walk(tree, None)
    return findings


def check_credentials(findings):
    violations = []
    for path, func, kinds in findings:
        allowed = CREDENTIAL_ALLOWLIST.get(path, set())
        if not kinds <= allowed:
            violations.append((path, func, sorted(kinds)))
    return violations


def test_ratchet_no_new_direct_meta_construction():
    root = Path(__file__).resolve().parents[1]
    violations = check_allowlist(find_meta_constructions(root / "alive", root / "scripts"))
    assert violations == [], f"new direct MetaProvider sites: {violations}"


def test_ratchet_no_new_credential_access():
    root = Path(__file__).resolve().parents[1]
    violations = check_credentials(find_credential_uses(root / "alive"))
    assert violations == [], f"new Meta credential access: {violations}"


def _violations_for(violations, filename):
    """Rogue fixtures also report missing expected sites; scope to the rogue file."""
    return [v for v in violations if v[0] == filename]


def _write_rogue(tmp_path, name, body):
    target = tmp_path / name
    target.write_text(body)
    return target


def test_ratchet_catches_extra_constructor_in_approved_function(tmp_path):
    _write_rogue(
        tmp_path,
        "extra.py",
        "from alive.providers import MetaProvider\n"
        "async def command(settings):\n"
        "    a = await MetaProvider(settings).discover()\n"
        "    b = await MetaProvider(settings).structured('i', {}, {}, model='m')\n"
        "    return a, b\n",
    )
    violations = _violations_for(check_allowlist(find_meta_constructions(tmp_path)), "extra.py")
    assert len(violations) == 1
    assert violations[0][0] == "extra.py" and violations[0][1] == "command"
    assert violations[0][4] == 2


def test_ratchet_catches_assigned_variable_in_new_function(tmp_path):
    _write_rogue(
        tmp_path,
        "assigned.py",
        "from alive.providers import MetaProvider\n"
        "async def probe(settings):\n"
        "    provider = MetaProvider(settings)\n"
        "    return await provider.discover()\n",
    )
    violations = _violations_for(check_allowlist(find_meta_constructions(tmp_path)), "assigned.py")
    assert violations == [("assigned.py", "probe", ["discover"], ["assigned"], 1, None)]


def test_ratchet_catches_aliased_import(tmp_path):
    _write_rogue(
        tmp_path,
        "aliased.py",
        "from alive.providers import MetaProvider as MP\n"
        "async def run(settings):\n"
        "    return await MP(settings).structured('i', {}, {}, model='m')\n",
    )
    violations = _violations_for(check_allowlist(find_meta_constructions(tmp_path)), "aliased.py")
    assert violations == [("aliased.py", "run", ["structured"], ["chained"], 1, None)]


def test_ratchet_catches_subclass_construction(tmp_path):
    _write_rogue(
        tmp_path,
        "subclassed.py",
        "from alive.providers import MetaProvider\n"
        "class Sneaky(MetaProvider):\n"
        "    pass\n"
        "async def run(settings):\n"
        "    return await Sneaky(settings).structured('i', {}, {}, model='m')\n",
    )
    violations = _violations_for(
        check_allowlist(find_meta_constructions(tmp_path)), "subclassed.py"
    )
    assert violations == [("subclassed.py", "run", ["structured"], ["chained"], 1, None)]


def test_ratchet_catches_constructor_alias(tmp_path):
    _write_rogue(
        tmp_path,
        "aliased_ctor.py",
        "from alive.providers import MetaProvider\n"
        "MP = MetaProvider\n"
        "async def run(settings):\n"
        "    return await MP(settings).structured('i', {}, {}, model='m')\n",
    )
    violations = _violations_for(
        check_allowlist(find_meta_constructions(tmp_path)), "aliased_ctor.py"
    )
    assert violations == [("aliased_ctor.py", "run", ["structured"], ["chained"], 1, None)]


def test_ratchet_catches_getattr_dispatch(tmp_path):
    _write_rogue(
        tmp_path,
        "dynamic.py",
        "import alive.providers as providers\n"
        "async def run(settings):\n"
        "    cls = getattr(providers, 'MetaProvider')\n"
        "    return await cls(settings).structured('i', {}, {}, model='m')\n",
    )
    violations = _violations_for(check_allowlist(find_meta_constructions(tmp_path)), "dynamic.py")
    assert len(violations) == 1
    path, func, kinds, flags, total, _ = violations[0]
    assert (path, func, total) == ("dynamic.py", "run", 2)
    assert "dynamic-getattr" in flags and "dynamic" in kinds


def test_ratchet_catches_unbound_method(tmp_path):
    _write_rogue(
        tmp_path,
        "unbound.py",
        "from alive.providers import MetaProvider\n"
        "async def run(provider, settings):\n"
        "    return await MetaProvider.structured(provider, 'i', {}, {}, model='m')\n",
    )
    violations = _violations_for(check_allowlist(find_meta_constructions(tmp_path)), "unbound.py")
    assert ("unbound.py", "run", ["structured"], ["unbound-method"], 1, None) in violations


def test_ratchet_catches_ambiguous_construction(tmp_path):
    _write_rogue(
        tmp_path,
        "ambiguous.py",
        "from alive.providers import MetaProvider\n"
        "def run(settings):\n"
        "    provider = MetaProvider(settings)\n"
        "    return provider\n",
    )
    violations = _violations_for(check_allowlist(find_meta_constructions(tmp_path)), "ambiguous.py")
    assert violations == [("ambiguous.py", "run", ["ambiguous"], ["opaque-use"], 1, None)]


def test_ratchet_fails_closed_on_unparseable(tmp_path):
    rogue = tmp_path / "broken.py"
    rogue.write_bytes(b"def broken(:\n    pass\n")
    violations = _violations_for(check_allowlist(find_meta_constructions(tmp_path)), "broken.py")
    assert violations == [
        ("broken.py", "<module>", ["parse-error"], ["unreadable-or-unparseable"], 1, None)
    ]


def test_ratchet_catches_direct_httpx_with_credential(tmp_path):
    _write_rogue(
        tmp_path,
        "direct.py",
        "import httpx\n"
        "async def run(settings):\n"
        "    return await httpx.post(\n"
        "        'https://api.meta.ai/v1/chat/completions',\n"
        "        headers={'Authorization': 'Bearer ' + settings.alive_meta_api_key},\n"
        "        json={},\n"
        "    )\n",
    )
    creds = check_credentials(find_credential_uses(tmp_path))
    kinds = {k for _, _, ks in creds for k in ks}
    assert "credential:key" in kinds, creds
    assert "credential:literal" in kinds, creds


def _mirror(tmp_path, modules):
    """Mirror selected repo modules into tmp/alive so allow-list paths match."""
    import shutil

    root = Path(__file__).resolve().parents[1]
    alive = tmp_path / "alive"
    alive.mkdir(parents=True, exist_ok=True)
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    for rel in modules:
        shutil.copy(root / rel, alive / Path(rel).name)
    return alive


def test_ratchet_detects_missing_expected_site(tmp_path):
    """R3: deleting a legitimate construction must fail, not pass silently."""
    alive = _mirror(tmp_path, ["alive/living.py", "alive/model_gateway.py"])
    text = (alive / "living.py").read_text(encoding="utf-8")
    needle = "MetaProvider(self.k.settings).structured("
    assert needle in text
    (alive / "living.py").write_text(
        text.replace(needle, "_removed_provider_call(", 1), encoding="utf-8"
    )
    violations = check_allowlist(find_meta_constructions(alive, tmp_path / "scripts"))
    assert (
        "alive/living.py",
        "reason",
        ["structured"],
        ["missing-expected-site"],
        0,
        1,
    ) in violations


def test_ratchet_detects_unused_assigned_instance(tmp_path):
    """R3: an unused provider assignment must be reported, not dropped."""
    alive = _mirror(tmp_path, ["alive/cognition.py", "alive/model_gateway.py"])
    text = (alive / "cognition.py").read_text(encoding="utf-8")
    anchor = "    async def command(self, data):\n        async with self.command_lock:"
    assert anchor in text
    injected = (
        "    async def command(self, data):\n"
        "        r3_unused = MetaProvider(self.k.settings)\n"
        "        async with self.command_lock:"
    )
    (alive / "cognition.py").write_text(text.replace(anchor, injected, 1), encoding="utf-8")
    findings = find_meta_constructions(alive, tmp_path / "scripts")
    assert any(
        f[0].endswith("cognition.py") and f[1] == "command" and "unused-assignment" in f[3]
        for f in findings
    )
    violations = check_allowlist(findings)
    assert any(
        v[0].endswith("cognition.py") and v[1] == "command" and "unused-assignment" in v[3]
        for v in violations
    )


def test_ratchet_nested_scope_counted_once(tmp_path):
    """A construction inside a nested function is attributed to it exactly once."""
    alive = tmp_path / "alive"
    alive.mkdir()
    (tmp_path / "scripts").mkdir()
    (alive / "nested.py").write_text(
        "from alive.providers import MetaProvider\n"
        "async def outer(settings):\n"
        "    async def inner():\n"
        "        return await MetaProvider(settings).structured('i', {}, {}, model='m')\n"
        "    return await inner()\n",
        encoding="utf-8",
    )
    violations = check_allowlist(find_meta_constructions(alive, tmp_path / "scripts"))
    mine = [v for v in violations if v[0] == "alive/nested.py"]
    assert mine == [("alive/nested.py", "inner", ["structured"], ["chained"], 1, None)]


def test_ratchet_detects_class_body_construction(tmp_path):
    """R3: class-level constructions are scanned (previously invisible)."""
    alive = tmp_path / "alive"
    alive.mkdir()
    (tmp_path / "scripts").mkdir()
    (alive / "holder.py").write_text(
        "from alive.providers import MetaProvider\n"
        "class Holder:\n"
        "    provider = MetaProvider(None)\n"
        "\n"
        "async def use():\n"
        "    return await Holder.provider.discover()\n",
        encoding="utf-8",
    )
    violations = check_allowlist(find_meta_constructions(alive, tmp_path / "scripts"))
    assert (
        "alive/holder.py",
        "<class Holder>",
        ["ambiguous"],
        ["unused-assignment"],
        1,
        None,
    ) in violations


def test_credentials_allowlist_matches_repo():
    root = Path(__file__).resolve().parents[1]
    violations = check_credentials(find_credential_uses(root / "alive"))
    assert violations == [], f"unexpected Meta credential access: {violations}"
