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


def test_compose_requires_one_explicit_api_token():
    compose = read("compose.yaml")
    assert "${ALIVE_API_TOKEN:?" in compose
    assert "alive-dev-token-replace-for-local-use-000" not in compose


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


# --- ALIVE-PI-01B: the pinned Pi runtime -------------------------------------------------------

PI_PACKAGE = "@earendil-works/pi-coding-agent"
PI_INTEGRITY = (
    "sha512-Z41LpZ3yYHSC/UUps6Mr39UMFPwH8elhJBG9DY1P7kuzsE5qSK/6eMj2EHzO5evJRQWLbKSqUMw"
    "+4nCNtIyiQg=="
)


def test_pi_runtime_is_pinned_to_one_exact_version_with_an_integrity_hash():
    package = json.loads(read("pi-runtime/package.json"))
    assert package["private"] is True
    assert package["dependencies"] == {PI_PACKAGE: "1.4.0"}  # exact: no ^, ~, or range
    lock = json.loads(read("pi-runtime/package-lock.json"))
    pinned = lock["packages"][f"node_modules/{PI_PACKAGE}"]
    assert pinned["version"] == "1.4.0" and pinned["integrity"] == PI_INTEGRITY
    from alive.config import Settings

    assert Settings(_env_file=None).alive_pi_pinned_version == "1.4.0"


def test_every_locked_pi_dependency_is_hashed_and_comes_from_the_npm_registry():
    packages = json.loads(read("pi-runtime/package-lock.json"))["packages"]
    for path, meta in packages.items():
        if not path:
            continue
        assert meta["resolved"].startswith("https://registry.npmjs.org/"), path
        assert meta["integrity"].startswith("sha512-"), path


def test_dockerfile_installs_pi_from_the_lockfile_without_running_install_scripts():
    dockerfile = read("Dockerfile")
    assert re.search(
        r"^ARG NODE_IMAGE=node:\d+\.\d+\.\d+-slim@sha256:[0-9a-f]{64}$", dockerfile, re.M
    )
    assert "FROM ${NODE_IMAGE} AS pi-runtime" in dockerfile
    assert "npm ci --ignore-scripts" in dockerfile
    assert "pi-runtime/package-lock.json" in dockerfile
    assert "npm install" not in dockerfile  # only a lockfile-exact install
    final = dockerfile.split("FROM python:3.13-slim", 1)[1]
    assert "USER alive" in final.split("COPY --from=pi-runtime --chown=alive:alive", 1)[0]
    assert "cli.js --version" in dockerfile  # the build proves Pi starts under this Node


def test_compose_does_not_switch_the_model_transport_to_pi():
    for name in ("compose.yaml", "compose.e2e.yaml"):
        assert "ALIVE_MODEL_TRANSPORT" not in read(name), "the default transport stays direct"
