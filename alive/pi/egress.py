"""ALIVE-owned, loopback-only, metered model egress for Pi (ALIVE-PI-01B, ADR-3).

Pi is configured with this endpoint as its model provider and a run-scoped token as its "API key".
The real provider credential never leaves ALIVE. For every request Pi makes, this endpoint:

1. authenticates the run token and finds the single approved run it belongs to;
2. atomically reserves a provider-request slot, or refuses (limit, run state, mismatch);
3. persists the request as `dispatched` BEFORE calling upstream;
4. builds the upstream call ENTIRELY from the request ALIVE approved: whatever Pi put in its own
   body (model, token limit, schema, messages) is recorded as a hash and otherwise ignored, so Pi
   cannot widen spending, substitute a model or change the response schema;
5. forwards it through the existing `DirectMetaGateway` (so the existing MetaProvider transport,
   headers and `response_format` are used unchanged and no new dispatch site exists);
6. records the outcome and answers in the OpenAI streaming shape Pi accepts.

An upstream request is never retried: a timeout or network error after dispatch is `ambiguous`,
and the slot counter stops Pi from asking again. The endpoint binds 127.0.0.1 only and is not part
of the public FastAPI application.
"""

import asyncio
import contextlib
import hashlib
import hmac
import json
import time
import uuid
from dataclasses import asdict, dataclass, field

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from alive.model_gateway import DirectMetaGateway, StructuredRequest
from alive.models import now
from alive.pi import states
from alive.pi.models import PiProviderRequest, PiRun
from alive.pi.process import shielded
from alive.providers import ProviderError

# After dispatch these mean "the request may have been received": the outcome is unknown.
AMBIGUOUS_CATEGORIES = frozenset({"timeout", "transient_network"})


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def render_prompt(req):
    """The text Pi is asked to process: exactly the approved instructions and data."""
    return f"{req.instructions}\n\n{json.dumps(req.data, ensure_ascii=False)}"


def approved_request_sha256(req):
    return hashlib.sha256(
        json.dumps(asdict(req), sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def user_text(body):
    """The text of the last user message in an OpenAI-style request, parts joined."""
    for message in reversed(body.get("messages") or []):
        if isinstance(message, dict) and message.get("role") == "user":
            content = message.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "".join(
                    part.get("text", "")
                    for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                )
    return None


@dataclass
class RunContext:
    run_id: str
    token_sha256: str
    approved: StructuredRequest
    gateway: object
    max_requests: int
    prompt_text: str = ""
    last_text: str | None = None
    last_text_sha256: str | None = None
    inflight: int = 0
    idle: asyncio.Event = field(default_factory=asyncio.Event)

    def __post_init__(self):
        self.prompt_text = render_prompt(self.approved)
        self.idle.set()


class _QuietServer(uvicorn.Server):
    """A second uvicorn server inside ALIVE's process must not hijack its signal handling."""

    def capture_signals(self):
        return contextlib.nullcontext()


class PiEgress:
    def __init__(self, kernel, upstream_transport=None):
        self.kernel = kernel
        # Test seam only: an httpx transport for the UPSTREAM call. None in production.
        self.upstream_transport = upstream_transport
        self.contexts = {}
        self.port = None
        self._server = None
        self._task = None
        self.app = self._build_app()

    # -- lifecycle -------------------------------------------------------------------------
    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.port}/v1"

    async def start(self):
        config = uvicorn.Config(
            self.app,
            host="127.0.0.1",  # IPv4 loopback only; never a wildcard or the public interface
            port=0,
            log_level="warning",
            lifespan="off",
            access_log=False,
        )
        self._server = _QuietServer(config)
        self._task = asyncio.create_task(self._server.serve())
        for _ in range(200):
            if self._server.started:
                break
            if self._task.done():
                self._task.result()
            await asyncio.sleep(0.05)
        else:
            raise RuntimeError("the Pi egress did not start")
        self.port = self._server.servers[0].sockets[0].getsockname()[1]

    async def stop(self):
        if self._server is not None:
            self._server.should_exit = True
        if self._task is not None:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await asyncio.wait_for(self._task, 10)
        self._server = self._task = None

    # -- run registry ----------------------------------------------------------------------
    def register(self, token, ctx):
        self.contexts[hashlib.sha256(token.encode()).hexdigest()] = ctx

    def unregister(self, token):
        self.contexts.pop(hashlib.sha256(token.encode()).hexdigest(), None)

    def context_for(self, header):
        if not header or not header.lower().startswith("bearer "):
            return None
        digest = hashlib.sha256(header[7:].strip().encode()).hexdigest()
        for known, ctx in self.contexts.items():
            if hmac.compare_digest(known, digest):
                return ctx
        return None

    # -- HTTP surface ----------------------------------------------------------------------
    def _build_app(self):
        app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

        @app.post("/v1/chat/completions")
        async def chat(request: Request):
            return await self.handle(request)

        return app

    @staticmethod
    def _error(status, message, kind, **extra):
        return JSONResponse(
            {"error": {"message": message, "type": kind, **extra}}, status_code=status
        )

    async def handle(self, request):
        ctx = self.context_for(request.headers.get("authorization"))
        if ctx is None:
            return self._error(401, "invalid run credential", "authentication")
        raw = await request.body()
        inbound = sha256_bytes(raw)
        try:
            body = json.loads(raw)
            if not isinstance(body, dict):
                raise ValueError
        except ValueError:
            await self._reject(ctx, inbound, "malformed_request")
            return self._error(400, "malformed request body", "invalid_request")

        reason = None if body.get("stream") is True else "non_streaming_request"
        outcome, value = await self._admit(ctx, inbound, body, reason)
        if outcome == "refused":  # refused before any dispatch
            status = {"request_limit": 429, "run_not_running": 409, "inbound_mismatch": 409}
            return self._error(status.get(value, 400), f"refused: {value}", "refused", reason=value)
        request_id = value
        ctx.inflight += 1
        ctx.idle.clear()
        started = time.monotonic()
        try:
            await self._mark(request_id, states.R_DISPATCHED)  # durable BEFORE the upstream call
            try:
                generation = await ctx.gateway.structured(ctx.approved)
            except ProviderError as exc:
                ambiguous = exc.category in AMBIGUOUS_CATEGORIES
                await self._settle_failure(
                    request_id,
                    states.R_AMBIGUOUS if ambiguous else states.R_FAILED,
                    exc.category,
                    exc.status,
                    exc.usage or None,
                    started,
                )
                return self._error(
                    502, "upstream refused or failed", "upstream_error", category=exc.category
                )
            except asyncio.CancelledError:
                await shielded(
                    self._settle_failure(
                        request_id, states.R_AMBIGUOUS, "cancelled", None, None, started
                    )
                )
                raise
            except Exception as exc:  # noqa: BLE001 - after dispatch, anything unknown is ambiguous
                await self._settle_failure(
                    request_id, states.R_AMBIGUOUS, type(exc).__name__, None, None, started
                )
                return self._error(502, "upstream failed", "upstream_error", category="unknown")
            ctx.last_text = generation.text
            ctx.last_text_sha256 = hashlib.sha256(generation.text.encode("utf-8")).hexdigest()
            await self._settle_success(request_id, generation, started, ctx.last_text_sha256)
            return self._stream(body, generation)
        finally:
            ctx.inflight -= 1
            if ctx.inflight == 0:
                ctx.idle.set()

    # -- persistence -----------------------------------------------------------------------
    async def _admit(self, ctx, inbound_sha256, body, force_reason):
        """Count the request, then reserve a slot ("admitted", id) or refuse ("refused", reason)."""
        k = self.kernel
        async with k.lock, k.db.sessions.begin() as session:
            run = await session.get(PiRun, ctx.run_id)
            run.inbound_requests += 1
            seq = run.inbound_requests
            reason = force_reason
            if reason is None and run.state != states.RUNNING:
                reason = "run_not_running"
            elif reason is None and run.provider_requests >= run.max_provider_requests:
                reason = "request_limit"  # Pi's own retries and extra calls stop here
            elif reason is None and user_text(body) != ctx.prompt_text:
                reason = "inbound_mismatch"  # Pi was not asked what ALIVE approved
            row = PiProviderRequest(
                run_id=run.id,
                seq=seq,
                body_sha256_in=inbound_sha256,
                approved_request_sha256=approved_request_sha256(ctx.approved),
                model_requested=ctx.approved.model,
                updated_at=now(),
            )
            if reason is not None:
                row.state, row.error_category = states.R_REJECTED, reason
                session.add(row)
                k.add_event(
                    session,
                    "pi.provider_request.rejected",
                    {"run_id": run.id, "seq": seq, "reason": reason},
                    source="pi",
                    correlation=run.id,
                )
                return "refused", reason
            run.provider_requests += 1
            run.updated_at = now()
            session.add(row)
            await session.flush()
            k.add_event(
                session,
                "pi.provider_request.admitted",
                {"run_id": run.id, "seq": seq, "request_id": row.id},
                source="pi",
                correlation=run.id,
            )
            return "admitted", row.id

    async def _reject(self, ctx, inbound_sha256, reason):
        await self._admit(ctx, inbound_sha256, {}, reason)

    async def _mark(self, request_id, new_state):
        k = self.kernel
        async with k.lock, k.db.sessions.begin() as session:
            row = await session.get(PiProviderRequest, request_id)
            row.state = states.advance(row.state, new_state, states.REQUEST_TRANSITIONS)
            row.updated_at = now()
            k.add_event(
                session,
                f"pi.provider_request.{new_state}",
                {"run_id": row.run_id, "seq": row.seq, "request_id": row.id},
                source="pi",
                correlation=row.run_id,
            )

    async def _settle_success(self, request_id, generation, started, response_sha256):
        k = self.kernel
        async with k.lock, k.db.sessions.begin() as session:
            row = await session.get(PiProviderRequest, request_id)
            row.state = states.advance(row.state, states.R_SETTLED, states.REQUEST_TRANSITIONS)
            row.http_status = 200
            row.usage_json = generation.usage or None  # unknown stays NULL, never 0
            row.latency_ms = (time.monotonic() - started) * 1000
            row.response_sha256 = response_sha256
            row.updated_at = now()
            k.add_event(
                session,
                "pi.provider_request.settled",
                {"run_id": row.run_id, "seq": row.seq, "request_id": row.id},
                source="pi",
                correlation=row.run_id,
            )

    async def _settle_failure(self, request_id, new_state, category, status, usage, started):
        k = self.kernel
        async with k.lock, k.db.sessions.begin() as session:
            row = await session.get(PiProviderRequest, request_id)
            if row.state in states.REQUEST_TERMINAL:
                return
            row.state = states.advance(row.state, new_state, states.REQUEST_TRANSITIONS)
            row.error_category, row.http_status = category, status
            row.usage_json = usage or None
            row.latency_ms = (time.monotonic() - started) * 1000
            row.updated_at = now()
            k.add_event(
                session,
                f"pi.provider_request.{new_state}",
                {"run_id": row.run_id, "seq": row.seq, "category": category},
                source="pi",
                correlation=row.run_id,
            )

    # -- reply -----------------------------------------------------------------------------
    @staticmethod
    def _stream(body, generation):
        """The OpenAI streaming shape Pi 1.4.0 accepts (verified against real Pi)."""
        ident = "chatcmpl-" + uuid.uuid4().hex[:24]
        model = body.get("model") or "alive-approved"

        def chunk(delta, finish=None, usage=None, choices=True):
            payload = {
                "id": ident,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]
                if choices
                else [],
            }
            if usage is not None:
                payload["usage"] = usage
            return f"data: {json.dumps(payload)}\n\n"

        parts = [
            chunk({"role": "assistant", "content": generation.text}),
            chunk({}, finish="stop"),
        ]
        usage = {
            key: generation.usage[key]
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
            if isinstance(generation.usage.get(key), int)
        }
        if usage:  # an unknown usage is omitted, not reported as zero
            parts.append(chunk({}, usage=usage, choices=False))
        parts.append("data: [DONE]\n\n")
        return Response("".join(parts), media_type="text/event-stream")


def gateway_for_run(settings, operation, upstream_transport=None):
    """The upstream gateway for a run: the existing DirectMetaGateway, never a new dispatch site."""
    return DirectMetaGateway(settings, operation=operation, transport=upstream_transport)
