"""Permanent regressions adapted from the independent PR #83 review probes.

P1 now asserts refusal (zero outbound requests); proxy checks are socket-based in
test_model_transport_environment.py, rather than inspecting source text.
"""

import asyncio
import json

import httpx
import pytest
from sqlalchemy import text as sql_text

from alive.admission import service
from tests import test_repository_analysis as analysis_fixtures
from tests.test_owner_admission import approve_review, call
from tests.test_pi_gateway import USAGE
from tests.test_repository_analysis import (
    BASE,
    CANARY,
    prepared,
    start,
)

case = analysis_fixtures.case
ready = analysis_fixtures.ready
settings = analysis_fixtures.settings
quick_settle = analysis_fixtures.quick_settle

GOOD = "https://api.meta.ai/v1/chat/completions"
EVIL = "https://attacker.example/v1/chat/completions"


class Recorder:
    """Scripted upstream that records every URL it is asked for and can echo the request."""

    def __init__(self, echo=False):
        self.urls, self.echo = [], echo

    async def handle(self, request):
        self.urls.append(str(request.url))
        if self.echo:
            return httpx.Response(
                400, json={"error": "bad request", "echo": request.content.decode()}
            )
        content = json.dumps({"summary": "ok", "findings": [], "unresolved_questions": []})
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "usage": USAGE,
            },
        )


def install(client, recorder):
    client.app.state.pi.upstream_transport = httpx.MockTransport(recorder.handle)


def test_P1_a_change_made_and_reverted_around_the_snapshot_cannot_redirect_dispatch(
    ready, monkeypatch
):
    """Poison the gateway snapshot, then restore live settings before the fence."""
    client, upstream, _, settings, *_ = ready
    recorder = Recorder()
    install(client, recorder)
    review = prepared(ready)
    approve_review(client, review)
    from alive.pi import gateway as pi_gateway

    original = pi_gateway.gateway_for_run

    def poisoned(settings_arg, operation, transport=None):
        settings.alive_meta_url = EVIL
        try:
            return original(settings_arg, operation, transport)
        finally:
            settings.alive_meta_url = ""

    monkeypatch.setattr(pi_gateway, "gateway_for_run", poisoned)
    start(client, review)
    assert recorder.urls == [], "a poisoned pinned destination must refuse before network I/O"


def test_P1b_a_change_between_reservation_and_snapshot_that_stays_is_refused(ready, monkeypatch):
    client, upstream, _, settings, *_ = ready
    recorder = Recorder()
    install(client, recorder)
    review = prepared(ready)
    approve_review(client, review)
    from alive.pi import gateway as pi_gateway

    original = pi_gateway.gateway_for_run

    def poisoned(settings_arg, operation, transport=None):
        settings.alive_meta_url = EVIL
        return original(settings_arg, operation, transport)

    monkeypatch.setattr(pi_gateway, "gateway_for_run", poisoned)
    start(client, review)
    assert all("attacker.example" not in u for u in recorder.urls), recorder.urls


@pytest.mark.parametrize(
    "url",
    [
        "https://api.meta.ai\\@attacker.example/v1",
        "https://api.meta.ai%2f@attacker.example/",
        "https://attacker.example\\.api.meta.ai/v1",
        "https://api.meta.ai:443@attacker.example/",
        "https://attacker.example:80:443/",
        "https://api.meta.ai./v1",
        "https://API.META.AI/v1",
        "https://api.meta.ai\t.attacker.example/",
        "https://[::1]/v1",
        "https://127.0.0.1/v1",
        "https://localhost/v1",
        "https://0x7f.1/v1",
        "https://2130706433/v1",
        "https://ａpi.meta.ai/v1",
        "https://api.meta.ai/v1;@attacker.example",
        "https://api.meta.ai:/v1",
        " https://api.meta.ai/v1",
    ],
)
def test_P2_the_validated_host_is_the_host_httpx_will_contact(url):
    """If the PR's validator accepts a URL, urlsplit and httpx must agree on host and port."""
    from types import SimpleNamespace
    from urllib.parse import urlsplit

    from alive.admission.profiles import analysis_endpoint
    from alive.workflows.context import Refused

    try:
        analysis_endpoint(SimpleNamespace(alive_meta_url=url))
    except Refused:
        return
    parsed = urlsplit(url)
    try:
        target = httpx.URL(url)
    except Exception:  # noqa: BLE001 - dispatch would fail closed
        return
    seen_host = (parsed.hostname or "").rstrip(".")
    assert target.host.rstrip(".").lower() == seen_host.lower(), (url, parsed.hostname, target.host)
    assert (target.port or 443) == (parsed.port or 443), (url, parsed.port, target.port)


def test_P3_provider_error_echo_does_not_spread_source_content(ready):
    client, upstream, _, settings, *_ = ready
    recorder = Recorder(echo=True)
    install(client, recorder)
    review = prepared(ready)
    approve_review(client, review)
    done = start(client, review).json()
    run_id = done["run"]["id"]
    surfaces = {}
    surfaces["events"] = json.dumps(client.get("/api/v1/events", params={"limit": 500}).json())
    for suffix in ("inspection", "timeline", "stages"):
        surfaces[suffix] = client.get(f"/api/v1/workflow-runs/{run_id}/{suffix}").text
    surfaces["admission"] = client.get(BASE + f"/{review['id']}").text
    surfaces["list"] = client.get(BASE).text

    async def tables(kernel):
        found = {}
        async with kernel.db.sessions() as session:
            for table in (
                "pi_runs",
                "pi_provider_requests",
                "cognitive_messages",
                "model_invocations",
            ):
                rows = (await session.execute(sql_text(f"SELECT * FROM {table}"))).all()
                found[table] = json.dumps([[str(c) for c in r] for r in rows])
        return found

    stored = call(client, tables)
    leaked = [k for k, v in surfaces.items() if CANARY in v]
    assert not leaked, f"source canary reached public API surfaces: {leaked}"
    # Retention is documented for these two; the echo must not add copies elsewhere.
    unexpected = [k for k, v in stored.items() if CANARY in v and k not in {"model_invocations"}]
    assert not unexpected, f"canary persisted in unexpected tables: {unexpected}"


def test_P4_another_instance_cannot_read_or_start_a_review(ready):
    client, upstream, *_ = ready
    review = prepared(ready)
    approve_review(client, review)
    run_ok = start(client, review)
    assert run_ok.status_code == 200
    import copy

    from alive.models import Instance, uid

    foreign = copy.copy(client.app.state.kernel)
    foreign.instance_id = uid()

    async def attempt(kernel):
        async with kernel.db.sessions.begin() as session:
            session.add(Instance(id=foreign.instance_id, name="Other"))
        results = []
        for work in (service.get, service.report):
            try:
                await work(foreign, review["id"])
                results.append("readable")
            except Exception as error:  # noqa: BLE001
                results.append(type(error).__name__)
        return results

    assert call(client, attempt) == ["Refused", "Refused"]


def test_P5_two_reviews_never_overlap_their_provider_calls(ready, tmp_path):
    client, upstream, root, settings, paths, captured, approval = ready
    first, second = prepared(ready), prepared(ready)
    for review in (first, second):
        approve_review(client, review)
    state = {"active": 0, "peak": 0}

    async def handle(request):
        state["active"] += 1
        state["peak"] = max(state["peak"], state["active"])
        await asyncio.sleep(0.4)
        state["active"] -= 1
        content = json.dumps({"summary": "ok", "findings": [], "unresolved_questions": []})
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "usage": USAGE,
            },
        )

    client.app.state.pi.upstream_transport = httpx.MockTransport(handle)

    async def both(kernel):
        return await asyncio.gather(
            service.start(client.app, first["id"], first["review_sha256"]),
            service.start(client.app, second["id"], second["review_sha256"]),
            return_exceptions=True,
        )

    call(client, both)
    assert state["peak"] <= 1, state


def test_T16_a_typed_role_without_a_workflow_claim_is_refused_even_with_a_live_inquiry(case):
    """Targeted probe for mutant M16: with a REAL admitted inquiry the only barrier is the guard."""
    from alive.analysis.context import context_package
    from alive.analysis.contracts import ROLE, AnalysisSpec
    from tests.analysis_cases import SEEDED, inputs_for
    from tests.workflow_execution_helpers import observation

    client, upstream, *_ = case
    observation(client)
    inputs = inputs_for(SEEDED)

    async def attempt(kernel):
        cognition = client.app.state.cognition
        async with cognition.workflow_inquiry() as inquiry:
            try:
                await cognition.call_role(
                    inquiry,
                    ROLE,
                    context_package(inputs),
                    spec=AnalysisSpec(inputs=inputs, context_for=context_package),
                )
            except ValueError as error:
                return str(error)
            except Exception as error:  # noqa: BLE001
                return "other:" + type(error).__name__
        return "dispatched"

    outcome = call(client, attempt)
    assert "only inside an authorized workflow stage" in outcome, outcome
    assert not upstream.calls


def test_T21_fabricated_file_receives_a_refusal_classification_not_validity():
    from alive.analysis.contracts import Evidence
    from alive.analysis.validation import check_evidence

    try:
        outcome = check_evidence(Evidence(file="fabricated.py", line_start=1, line_end=1), {})
    except Exception as error:  # expose a broken contract as an explicit behavioral assertion
        outcome = {"status": "raised", "error": type(error).__name__}
    assert outcome == {"status": "unknown_file", "file": "fabricated.py"}, outcome


@pytest.mark.parametrize("change", ["remove", "endpoint", "review_sha256", "admission_id"])
def test_invocation_destination_cannot_be_replaced_after_reservation(ready, monkeypatch, change):
    from dataclasses import replace

    from alive.pi.gateway import PiGateway

    client, upstream, *_ = ready
    review = prepared(ready)
    approve_review(client, review)
    original = PiGateway.structured

    async def substituted(self, request):
        destination = request.destination
        assert destination is not None
        if change == "remove":
            destination = None
        else:
            destination = replace(destination, **{change: "https://attacker.example/collect"})
        return await original(self, replace(request, destination=destination))

    monkeypatch.setattr(PiGateway, "structured", substituted)
    done = start(client, review)
    assert done.status_code == 200
    assert done.json()["run"]["status"] in {"FAILED", "UNKNOWN"}
    assert not upstream.calls


def test_dispatch_fence_binds_destination_to_the_immutable_review(ready, monkeypatch):
    from alive.cognitive_models import ModelInvocation
    from alive.pi.models import PiProviderRequest, PiRun

    client, upstream, *_ = ready
    review = prepared(ready)
    approve_review(client, review)
    egress = client.app.state.pi.egress
    original = egress._dispatch

    async def changed_receipt(request_id):
        kernel = client.app.state.kernel
        async with kernel.lock, kernel.db.sessions.begin() as session:
            request = await session.get(PiProviderRequest, request_id)
            run = await session.get(PiRun, request.run_id)
            invocation = await session.get(ModelInvocation, run.reservation_ref)
            destination = invocation.input_json["model_destination"] | {"review_sha256": "0" * 64}
            invocation.input_json = invocation.input_json | {"model_destination": destination}
        return await original(request_id)

    monkeypatch.setattr(egress, "_dispatch", changed_receipt)
    assert start(client, review).status_code == 200
    assert not upstream.calls
