"""ALIVE-DOCKER-01 config regression tests (no Docker required)."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_compose_defines_postgres_and_app():
    compose = read("compose.yaml")
    assert "pgvector/pgvector:pg16" in compose
    assert "condition: service_healthy" in compose
    assert '"127.0.0.1:${ALIVE_HOST_PORT:-8000}:8000"' in compose
    assert "alive-pgdata" in compose and "alive-appdata" in compose
    assert "pg_isready" in compose
    assert "ALIVE_DEMO_MODE" in compose
    assert "ALIVE_COGNITIVE_PROVIDER" in compose


def compose_default_port():
    match = re.search(r"ALIVE_HOST_PORT:-(\d+)\}:8000", read("compose.yaml"))
    assert match, "compose must publish the app on ${ALIVE_HOST_PORT:-<port>}"
    return int(match.group(1))


def test_published_port_matches_extension_and_server_allowlist():
    """The demo only works if Docker, the extension and the server agree on the port."""
    port = compose_default_port()
    manifest = json.loads(read("extension/manifest.json"))
    hosts = manifest["host_permissions"]
    assert f"http://127.0.0.1:{port}/*" in hosts and f"http://localhost:{port}/*" in hosts
    config = read("extension/config.js")
    assert f"DEFAULT_BACKEND = 'http://127.0.0.1:{port}'" in config
    assert f"http://${{host}}:{port}/demo-live-01/" in config
    from alive.web_experience import PAGES

    for host in ("127.0.0.1", "localhost"):
        for name in ("python-3.11", "python-3.12", "synthetic-no-change"):
            assert f"http://{host}:{port}/demo-live-01/{name}.html" in PAGES


def test_allowed_origins_follow_the_published_port():
    compose = read("compose.yaml")
    for line in compose.splitlines():
        if "ALIVE_ALLOWED_ORIGINS" in line:
            assert "localhost:${ALIVE_HOST_PORT:-8000}" in line
            assert "127.0.0.1:${ALIVE_HOST_PORT:-8000}" in line
            break
    else:
        raise AssertionError("ALIVE_ALLOWED_ORIGINS missing from compose.yaml")


def test_fixture_provider_is_tied_to_demo_mode_and_paid_flags_stay_off():
    compose = read("compose.yaml")
    assert "ALIVE_RELATIONSHIP_ALLOW_TEST_PROVIDERS: ${ALIVE_DEMO_MODE:-true}" in compose, (
        "fixture provider must follow ALIVE_DEMO_MODE, never a literal true"
    )
    for paid in ("ALIVE_CLAIM_META_ENABLED", "ALIVE_RESEARCH_META_ENABLED"):
        assert paid not in compose, f"{paid} must not be enabled by compose"
    e2e = read("compose.e2e.yaml")
    assert "ALIVE_RELATIONSHIP_ALLOW_TEST_PROVIDERS" not in e2e
    assert 'ALIVE_DEMO_MODE: "false"' in e2e


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
