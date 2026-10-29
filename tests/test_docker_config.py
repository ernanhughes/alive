"""ALIVE-DOCKER-01 config regression tests (no Docker required)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_compose_defines_postgres_and_app():
    compose = read("compose.yaml")
    assert "pgvector/pgvector:pg16" in compose
    assert "condition: service_healthy" in compose
    assert '"127.0.0.1:8080:8000"' in compose
    assert "alive-pgdata" in compose and "alive-appdata" in compose
    assert "pg_isready" in compose
    assert "ALIVE_DEMO_MODE" in compose
    assert "ALIVE_COGNITIVE_PROVIDER" in compose


def test_compose_does_not_publish_database_port():
    lines = read("compose.yaml").splitlines()
    service, db_ports = None, False
    for line in lines:
        if line.startswith("  ") and not line.startswith("   ") and line.rstrip().endswith(":"):
            service = line.strip().rstrip(":")
        if service == "db" and line.strip() == "ports:":
            db_ports = True
    assert not db_ports, "database port must not be published"


def test_e2e_environment_is_isolated():
    e2e = read("compose.e2e.yaml")
    assert "alive-e2e-pgdata" in e2e and "alive-e2e-appdata" in e2e
    assert "alive-pgdata" not in e2e.replace("alive-e2e-pgdata", "")
    # The test runner must override the server entrypoint; a Compose `command:`
    # would be swallowed by ENTRYPOINT and silently run a second server.
    assert "entrypoint" in e2e and "scripts/docker-e2e.py" in e2e
    assert "ALIVE_DEMO_MODE" in e2e


def test_dockerfile_is_reproducible_and_secret_free():
    dockerfile = read("Dockerfile")
    assert "AS frontend-build" in dockerfile
    assert "python:3.13-slim" in dockerfile
    assert "uv sync --locked --no-dev" in dockerfile
    assert "USER alive" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "ENTRYPOINT" in dockerfile
    for secret in ("META_API_KEY=", "API_TOKEN=ey", "sk-"):
        assert secret not in dockerfile, secret
    assert ".env" not in dockerfile


def test_entrypoint_migrates_without_destroying_data():
    entrypoint = read("docker/entrypoint.sh")
    assert "alembic upgrade head" in entrypoint
    for destructive in ("drop database", "DROP DATABASE", "down -v", "alembic downgrade"):
        assert destructive not in entrypoint, destructive


def test_frontend_base_is_configurable():
    api = read("dashboard/src/api.ts")
    assert "VITE_ALIVE_API_BASE" in api
    assert "resolveApiBase" in api


def test_backend_serves_dashboard_without_touching_api():
    app = read("alive/app.py")
    assert "dashboard" in app and "dist" in app
    assert "include_router(experiment_router" in app
    assert "/api/v1/health" in app
