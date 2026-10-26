import asyncio
import contextlib
import hmac
import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, literal_column, select

from alive.agents import Agents
from alive.browser import Browsers
from alive.cognition import Cognition
from alive.cognitive_api import public_router, router
from alive.config import Settings, prepare_local
from alive.db import Database
from alive.kernel import Kernel, envelope
from alive.memory import MemoryService
from alive.models import AgentRun, BrowserSession, Event, Goal, Memory, now, record
from alive.providers import MetaProvider
from alive.schemas import (
    BrowserAction,
    GoalInput,
    GoalOutput,
    GoalTransition,
    MemoryOutput,
    Navigation,
    Observation,
    PersistedEvent,
    RunInput,
    RunOutput,
    SearchInput,
)
from alive.transport import ZmqTransport


def create_app(settings=None):
    settings = settings or Settings()
    token = prepare_local(settings)
    db = Database(settings.database_url)
    kernel = None

    @asynccontextmanager
    async def lifespan(app):
        nonlocal kernel
        transport = ZmqTransport()
        await transport.start()
        kernel = Kernel(db, transport, settings)
        await kernel.initialize()
        transport.task.add_done_callback(kernel.background_completed)
        app.state.kernel = kernel
        app.state.agents = Agents(kernel)
        app.state.browsers = Browsers(kernel)
        app.state.memory = MemoryService(kernel)
        app.state.cognition = Cognition(kernel, app.state.memory)
        if kernel.ready:
            await app.state.cognition.initialize()
        try:
            yield
        finally:
            await app.state.cognition.close()
            await app.state.agents.close()
            await app.state.browsers.close()
            await kernel.close()
            await transport.close()

    app = FastAPI(title="ALIVE", version="0.2.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.alive_allowed_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Correlation-ID"],
    )

    @app.middleware("http")
    async def correlation(request, call_next):
        request.state.correlation_id = str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = request.state.correlation_id
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return JSONResponse(
            {
                "error": {
                    "code": exc.status_code,
                    "message": exc.detail,
                    "correlation_id": request.state.correlation_id,
                }
            },
            status_code=exc.status_code,
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        return JSONResponse(
            {
                "error": {
                    "code": 500,
                    "message": "Operation failed; check integration configuration",
                    "correlation_id": request.state.correlation_id,
                }
            },
            status_code=500,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(
            {
                "error": {
                    "code": 422,
                    "message": "Invalid request data",
                    "correlation_id": request.state.correlation_id,
                    "fields": [".".join(map(str, e["loc"])) for e in exc.errors()],
                }
            },
            status_code=422,
        )

    bearer = HTTPBearer(auto_error=False)

    async def auth(
        request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)
    ):
        value = credentials.credentials if credentials else ""
        if not hmac.compare_digest(value.encode(), token.encode()):
            raise HTTPException(401, "A local ALIVE bearer token is required")
        origin = request.headers.get("origin")
        if (
            origin
            and origin not in settings.alive_allowed_origins
            and not origin.startswith("chrome-extension://")
        ):
            raise HTTPException(403, "Origin is not allowed")

    async def ready(_=Depends(auth)):
        if not kernel or not kernel.ready:
            raise HTTPException(
                503, "Database unavailable, migrations pending, or runtime already owned"
            )

    secured = [Depends(ready)]
    app.include_router(router(app, ready))
    app.include_router(public_router(app))

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        return await http_error(request, HTTPException(409, str(exc)))

    @app.exception_handler(PermissionError)
    async def permission_error(request, exc):
        return await http_error(request, HTTPException(403, str(exc)))

    @app.exception_handler(KeyError)
    async def key_error(request, exc):
        return await http_error(request, HTTPException(404, str(exc)))

    @app.get("/api/v1/health")
    async def health():
        return {"status": "ok" if kernel and kernel.ready else "degraded", "version": "0.2.0"}

    @app.get("/api/v1/capabilities", dependencies=[Depends(auth)])
    async def capabilities():
        return {
            "database": {
                "available": kernel.ready,
                "backend": db.engine.dialect.name,
                "error": kernel.error,
            },
            "pgvector": {
                "storage": kernel.vector_storage,
                "search": app.state.memory.embedding.available,
                "dimension": 384,
                "reason": "Pinned MiniLM available"
                if app.state.memory.embedding.available
                else "No embedding model configured",
            },
            "zeromq": {
                "available": True,
                "received": kernel.transport.received,
                "delivery": "Ephemeral PUB/SUB; recover via persisted sequence cursor",
            },
            "pi": {
                "configured": bool(settings.alive_pi_model),
                "tools": [],
                "command_configured": bool(settings.alive_pi_command),
            },
            "browser": {"engine": "Chrome / Playwright", "origins": settings.alive_browser_origins},
            "providers": {"mock": True, "meta": MetaProvider(settings).capabilities()},
        }

    @app.get("/api/v1/alive", dependencies=secured)
    async def alive():
        return await kernel.state()

    @app.post("/api/v1/alive/start", dependencies=secured)
    async def start():
        return await kernel.set_running(True)

    @app.post("/api/v1/alive/stop", dependencies=secured)
    async def stop():
        from alive.cognitive_schema import AutonomyCommand

        await app.state.cognition.command(AutonomyCommand(command="pause"))
        for session_id in list(app.state.browsers.watchers):
            await app.state.browsers.watch(session_id, False)
        return await kernel.set_running(False)

    @app.get("/api/v1/events", dependencies=secured, response_model=list[PersistedEvent])
    async def events(after: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=500)):
        async with db.sessions() as session:
            rows = (
                await session.scalars(
                    select(Event)
                    .where(Event.sequence_number > after)
                    .order_by(Event.sequence_number)
                    .limit(limit)
                )
            ).all()
            return [envelope(row) for row in rows]

    @app.post("/api/v1/events", dependencies=secured)
    async def ingest(data: Observation):
        if len(json.dumps(data.payload)) > 20000:
            raise HTTPException(413, "Observation is too large")
        return await kernel.ingest(data)

    @app.get("/api/v1/memories", dependencies=secured, response_model=list[MemoryOutput])
    async def memories():
        async with db.sessions() as session:
            return [
                record(row)
                for row in (
                    await session.scalars(
                        select(Memory).order_by(Memory.created_at.desc()).limit(100)
                    )
                ).all()
            ]

    @app.post("/api/v1/memories/search", dependencies=secured)
    async def search(data: SearchInput):
        if data.mode in ("vector", "hybrid"):
            try:
                return await app.state.memory.retrieve(data.query, data.mode, data.top_k)
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc
        if data.mode == "vector":
            raise HTTPException(409, "Semantic search unavailable: no embedding model configured")
        async with db.sessions() as session:
            query = select(Memory)
            if db.pg:
                document = literal_column("search_document")
                terms = func.plainto_tsquery("english", data.query)
                query = query.where(document.op("@@")(terms)).order_by(
                    func.ts_rank(document, terms).desc()
                )
            else:
                query = query.where(Memory.content.icontains(data.query, autoescape=True))
            rows = [record(row) for row in (await session.scalars(query.limit(100))).all()]
        await kernel.emit(
            "memory.retrieved", {"count": len(rows), "mode": "fts" if db.pg else "substring"}
        )
        return {"mode": "postgresql_fts" if db.pg else "sqlite_substring", "results": rows}

    @app.get("/api/v1/goals", dependencies=secured, response_model=list[GoalOutput])
    async def goals():
        async with db.sessions() as session:
            return [
                record(row)
                for row in (
                    await session.scalars(select(Goal).order_by(Goal.created_at.desc()).limit(100))
                ).all()
            ]

    @app.post("/api/v1/goals", dependencies=secured, response_model=GoalOutput)
    async def goal(data: GoalInput):
        async with kernel.lock, db.sessions.begin() as session:
            row = Goal(instance_id=kernel.instance_id, **data.model_dump())
            session.add(row)
            await session.flush()
            kernel.add_event(session, "goal.proposed", {"goal_id": row.id})
            return record(row)

    @app.post("/api/v1/goals/{goal_id}/transition", dependencies=secured)
    async def transition(goal_id: str, data: GoalTransition):
        transitions = {
            "proposed": {"accepted", "cancelled"},
            "accepted": {"active", "cancelled"},
            "active": {"completed", "cancelled"},
            "completed": set(),
            "cancelled": set(),
        }
        async with kernel.lock, db.sessions.begin() as session:
            row = await session.get(Goal, goal_id)
            if not row:
                raise HTTPException(404, "Goal not found")
            if data.status not in transitions[row.status]:
                raise HTTPException(409, "Invalid goal transition")
            row.status, row.updated_at = data.status, now()
            if data.status == "completed":
                row.completed_at = now()
            kernel.add_event(
                session,
                "goal.selected" if data.status == "accepted" else "goal.updated",
                {"goal_id": row.id, "status": data.status},
            )
            return record(row)

    @app.get("/api/v1/agents", dependencies=secured)
    async def agents():
        async with db.sessions() as session:
            return {
                "runners": ["mock", "pi"],
                "runs": [
                    record(row)
                    for row in (
                        await session.scalars(
                            select(AgentRun).order_by(AgentRun.started_at.desc()).limit(100)
                        )
                    ).all()
                ],
            }

    @app.post("/api/v1/agents/runs", dependencies=secured)
    async def run(data: RunInput):
        try:
            return {"id": await app.state.agents.start(data)}
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/v1/agents/runs/{run_id}", dependencies=secured, response_model=RunOutput)
    async def get_run(run_id: str):
        async with db.sessions() as session:
            row = await session.get(AgentRun, run_id)
            if not row:
                raise HTTPException(404, "Run not found")
            return record(row)

    @app.post("/api/v1/agents/runs/{run_id}/cancel", dependencies=secured)
    async def cancel(run_id: str):
        await app.state.agents.cancel(run_id)
        return {"status": "cancellation_requested"}

    @app.get("/api/v1/browser/sessions", dependencies=secured)
    async def sessions():
        async with db.sessions() as session:
            return [
                record(row)
                for row in (
                    await session.scalars(
                        select(BrowserSession).order_by(BrowserSession.created_at.desc()).limit(100)
                    )
                ).all()
            ]

    async def browser_operation(operation):
        try:
            return await operation
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        except Exception as exc:
            await kernel.emit("action.failed", {"error": type(exc).__name__})
            raise HTTPException(
                502, "Browser operation failed; check Chrome and locator availability"
            ) from exc

    @app.post("/api/v1/browser/sessions", dependencies=secured)
    async def create_session():
        return await browser_operation(app.state.browsers.create())

    @app.post("/api/v1/browser/sessions/{session_id}/navigate", dependencies=secured)
    async def navigate(session_id: str, data: Navigation):
        return await browser_operation(app.state.browsers.navigate(session_id, data.url))

    @app.post("/api/v1/browser/sessions/{session_id}/actions", dependencies=secured)
    async def action(session_id: str, data: BrowserAction):
        return await browser_operation(app.state.browsers.action(session_id, data))

    @app.delete("/api/v1/browser/sessions/{session_id}", dependencies=secured)
    async def close_session(session_id: str):
        await browser_operation(app.state.browsers.close_session(session_id))
        return {"status": "closed"}

    @app.get("/demo", include_in_schema=False)
    async def demo():
        return FileResponse(Path(__file__).with_name("demo.html"))

    @app.websocket("/api/v1/events/stream")
    async def stream(ws: WebSocket):
        origin = ws.headers.get("origin")
        if origin and origin not in settings.alive_allowed_origins:
            await ws.close(code=1008)
            return
        await ws.accept()
        queue = asyncio.Queue(maxsize=256)
        disconnect_task = None
        try:
            # First-frame authentication avoids secrets in URLs and HTTP access logs.
            first = await asyncio.wait_for(ws.receive_json(), 5)
            if (
                not hmac.compare_digest(str(first.get("token", "")).encode(), token.encode())
                or not kernel.ready
            ):
                await ws.close(code=1008)
                return
            cursor = max(0, int(first.get("after", 0)))
            kernel.transport.listeners.add(queue)
            disconnect_task = asyncio.create_task(ws.receive())
            while not disconnect_task.done():
                # Reconcile durable history every second, including gaps/slow subscribers.
                async with db.sessions() as session:
                    rows = (
                        await session.scalars(
                            select(Event)
                            .where(Event.sequence_number > cursor)
                            .order_by(Event.sequence_number)
                            .limit(200)
                        )
                    ).all()
                for row in rows:
                    await ws.send_json(envelope(row))
                    cursor = row.sequence_number
                if len(rows) == 200:
                    continue
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(queue.get(), 1)
        except (
            WebSocketDisconnect,
            RuntimeError,
            ValueError,
            TimeoutError,
            TypeError,
            AttributeError,
        ):
            pass
        finally:
            if disconnect_task:
                disconnect_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect):
                    await disconnect_task
            if kernel:
                kernel.transport.listeners.discard(queue)

    return app


app = create_app()
