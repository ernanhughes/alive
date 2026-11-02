"""Read-only environment report: what ALIVE is configured with, what it needs, what is missing.

Run from the repository root:  uv run python scripts/alive_doctor.py

The configuration table is generated from the `Settings` class, so a new setting appears here
without anyone editing this file. Secrets are never printed (only "set (N chars)"). Nothing is
installed, started, connected to beyond a 2 second TCP probe, or modified.
"""

import os
import re
import shutil
import socket
import sys
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)  # Settings reads ".env" relative to the working directory

from alive.config import Settings  # noqa: E402

# Variables ALIVE tooling reads outside `Settings`. Listed so nothing is a surprise.
EXTERNAL = {
    "ALIVE_BASE_URL": "scripts/docker-*.py: where the smoke/e2e scripts send requests",
    "ALIVE_DEMO_MODE": "docker/entrypoint.sh + compose.yaml: seed fixture content on start",
    "ALIVE_HOST_PORT": "compose.yaml: host port for the container (extension expects 8000)",
    "ALIVE_DOCKER_PI_PROVIDER": "compose.yaml: Pi provider inside the container",
    "ALIVE_DOCKER_PI_MODEL": "compose.yaml: Pi model inside the container",
    "ALIVE_INSTALL_BROWSER": "Dockerfile/compose.yaml: install Chrome into the image",
    "VITE_ALIVE_API_BASE": "Dockerfile/dashboard build: API origin baked into the UI",
    "POSTGRES_DB": "compose.yaml: database name for the db service",
    "POSTGRES_USER": "compose.yaml: database user for the db service",
    "POSTGRES_PASSWORD": "compose.yaml: database password for the db service",
}
SECRETS = {"database_url", "alive_api_token", "alive_meta_api_key"}
results = []


def record(level, title, detail="", fix=""):
    results.append((level, title, detail, fix))
    print(f"[{level:<4}] {title}" + (f": {detail}" if detail else ""))
    if fix:
        print(f"         fix: {fix}")


def names_for(name, field):
    alias = field.validation_alias
    choices = getattr(alias, "choices", None)
    names = [str(c).upper() for c in choices] if choices else [name.upper()]
    return list(dict.fromkeys(names))  # the lowercase field name repeats the env name


def show(name, value):
    if name == "database_url":
        parts = urlsplit(str(value))
        user = f"{parts.username}:***@" if parts.username else ""
        host = f"{parts.hostname}:{parts.port}" if parts.hostname else ""
        return f"{parts.scheme}://{user}{host}{parts.path}"
    if name in SECRETS:
        return f"set ({len(value)} chars)" if value else "not set"
    return repr(value)


def configuration():
    print("\n== Configuration (every Settings field; source = where the value came from)")
    env_file = {k.upper(): v for k, v in dotenv_values(".env").items()}
    environment = {k.upper(): v for k, v in os.environ.items()}
    try:
        settings = Settings()
    except ValidationError as error:
        # Field names only: the invalid value may be a secret.
        fields = ", ".join(".".join(map(str, e["loc"])) for e in error.errors())
        record("FAIL", "settings do not validate", fields, "correct these values in .env")
        return None, set(), env_file, environment
    known = {name: name for name in EXTERNAL}  # every recognised name -> its primary name
    shadowed = []
    for name, field in Settings.model_fields.items():
        candidates = [c.upper() for c in names_for(name, field)]
        known.update({c: candidates[0] for c in candidates})
        present = [c for c in candidates if c in environment or c in env_file]
        if len(present) > 1:  # AliasChoices order is the precedence order
            shadowed.append((present, present[0]))
        source = next(
            (
                label
                for label, store in (("environment", environment), (".env", env_file))
                for c in candidates
                if c in store
            ),
            "default",
        )
        print(f"  {candidates[0]:<42} {show(name, getattr(settings, name)):<44} {source}")
    print("")
    for present, winner in shadowed:
        record(
            "WARN",
            f"{' and '.join(present)} are all set for one setting",
            f"{winner} wins",
            "keep one of them so there is a single place to look",
        )
    return settings, known, env_file, environment


def unknown_variables(known, env_file, environment):
    print("\n== Unrecognised ALIVE variables (ignored silently by Settings)")
    found = sorted(
        {
            k
            for k in [*env_file, *environment]
            if k.startswith(("ALIVE_", "VITE_ALIVE")) and k not in known
        }
    )
    if not found:
        record("OK", "no unrecognised ALIVE_* variables")
    for name in found:
        record("WARN", f"{name} is set but nothing reads it", "", "check the spelling in .env")


def node_check(settings):
    node = settings.alive_pi_node or shutil.which("node")
    if not node:
        record("FAIL", "node not found", "", "install Node >= 22.19 (the Docker image pins 24.x)")
        return
    import subprocess

    out = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()
    major, minor = (int(x) for x in re.findall(r"\d+", out)[:2])
    ok = (major, minor) >= (22, 19)
    record("OK" if ok else "FAIL", "node", out, "" if ok else "Pi needs Node >= 22.19")


def prerequisites(settings):
    print("\n== Prerequisites")
    record("OK", "python", sys.version.split()[0])
    record(
        "OK" if shutil.which("uv") else "WARN",
        "uv",
        shutil.which("uv") or "not on PATH",
        "" if shutil.which("uv") else "install uv (https://docs.astral.sh/uv/)",
    )
    node_check(settings)

    from alive.pi.runner import PiRunFailure, locate_pi

    try:
        install = locate_pi(settings)
        record("OK", "pinned Pi (governed model path)", f"v{install.version}, bundle verified")
    except PiRunFailure as error:
        record(
            "FAIL" if settings.alive_model_transport == "pi" else "WARN",
            "pinned Pi (governed model path)",
            str(error),
            "npm ci --ignore-scripts --prefix pi-runtime  "
            "(only needed when ALIVE_MODEL_TRANSPORT=pi or for the Pi test suites)",
        )

    command = settings.alive_pi_command
    resolved = shutil.which(command[0]) if command else None
    script = next((Path(a) for a in command[1:] if a.endswith(".js")), None)
    if resolved and (script is None or script.is_file()):
        record("OK", "external Pi command (Agents runner only)", " ".join(command))
    else:
        record(
            "WARN",
            "external Pi command (Agents runner only)",
            "not runnable: " + " ".join(command),
            'set ALIVE_PI_COMMAND, e.g. ["node","C:/Users/YOU/.pi/agent/bin/pi-launcher.js"]',
        )

    from alive import ollama
    from alive.agents import pi_status

    ollama_status = ollama.probe(
        settings.alive_ollama_url or ollama.DEFAULT_URL,
        timeout=1.5,
        chat_model=settings.alive_ollama_chat_model,
    )
    if ollama_status["available"]:
        record(
            "OK",
            "Ollama",
            f"{ollama_status['url']}  chat={ollama_status['chat_model'] or 'none'}  "
            f"embedding={ollama_status['embedding_model'] or 'none'}",
        )
    else:
        record(
            "INFO",
            "Ollama",
            ollama_status["reason"],
            "start Ollama or set ALIVE_OLLAMA_URL",
        )
    pi = pi_status(settings, ollama_status)
    record(
        "OK" if pi["configured"] else "WARN",
        "Pi agent model",
        pi["reason"],
        pi["next_action"],
    )

    token_file = ROOT / ".alive" / "token"
    have_token = bool(settings.alive_api_token) or token_file.is_file()
    record(
        "OK" if have_token else "WARN",
        "API token",
        "configured" if have_token else "none",
        "" if have_token else "run scripts/init.ps1 (Docker refuses to start without it)",
    )

    dist = ROOT / "dashboard" / "dist"
    record(
        "OK" if dist.is_dir() else "WARN",
        "built dashboard (served by the API)",
        "present" if dist.is_dir() else "missing",
        "" if dist.is_dir() else "npm --prefix dashboard ci && npm --prefix dashboard run build",
    )
    deps = (ROOT / "dashboard" / "node_modules").is_dir()
    record("OK" if deps else "WARN", "dashboard dependencies", "installed" if deps else "missing",
           "" if deps else "npm --prefix dashboard ci")  # fmt: skip

    from alive.memory import LocalEmbedding

    embedding = LocalEmbedding(settings)
    if settings.alive_embedding_enabled:
        record(
            "OK" if embedding.available else "FAIL",
            "embedding model (ALIVE_EMBEDDING_ENABLED=true)",
            f"{settings.alive_embedding_path} ({embedding.provider_id})",
            ""
            if embedding.available
            else "run scripts/prepare_embeddings.py or set ALIVE_EMBEDDING_ENABLED=false",
        )
    else:
        record(
            "INFO",
            "embedding model",
            "disabled (text search only)",
            "set ALIVE_EMBEDDING_ENABLED=true and run scripts/prepare_embeddings.py",
        )
    if settings.alive_cognitive_provider != "mock" or settings.alive_model_transport == "pi":
        record(
            "OK" if settings.alive_meta_api_key else "FAIL",
            "Meta API key (live provider selected)",
            "set" if settings.alive_meta_api_key else "not set",
            "" if settings.alive_meta_api_key else "set ALIVE_META_API_KEY in .env",
        )
    record("OK" if shutil.which("docker") else "WARN", "docker",
           shutil.which("docker") or "not on PATH", "")  # fmt: skip


def database(settings):
    print("\n== Database")
    parts = urlsplit(settings.database_url)
    if parts.scheme.startswith("sqlite"):
        record("OK", "SQLite", parts.path.lstrip("/") or "in-memory")
        return
    host, port = parts.hostname or "localhost", parts.port or 5432
    try:
        with socket.create_connection((host, port), timeout=2):
            record("OK", "PostgreSQL reachable", f"{host}:{port}")
    except OSError:
        record(
            "FAIL",
            "PostgreSQL not reachable",
            f"{host}:{port}",
            "start the database or fix DATABASE_URL",
        )


def docker_parity(known, env_file, environment):
    print("\n== Docker parity (set locally, but not passed to the container by compose.yaml)")
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    block = compose[compose.index("  app:") :]
    passed = set(re.findall(r"^\s{6}([A-Z][A-Z0-9_]+):", block, flags=re.M))
    # Aliases count as their primary name (ALIVE_DSN reaches the container as DATABASE_URL).
    local = {
        known[k]
        for k in [*env_file, *environment]
        if k in known and k.startswith(("ALIVE_", "DATABASE_URL"))
    }
    missing = sorted(
        local
        - passed
        - {
            "ALIVE_HOST_PORT",
            "ALIVE_BASE_URL",
            "VITE_ALIVE_API_BASE",
            "ALIVE_DOCKER_PI_PROVIDER",
            "ALIVE_DOCKER_PI_MODEL",
            "ALIVE_INSTALL_BROWSER",
        }
    )
    if not missing:
        record("OK", "every locally set ALIVE variable reaches the container")
    for name in missing:
        record("INFO", f"{name} does not reach the container", "the image uses its default",
               "add it under app.environment in compose.yaml if the demo needs it")  # fmt: skip
    if local & {"ALIVE_PI_PROVIDER", "ALIVE_PI_MODEL"}:
        record(
            "INFO",
            "host ALIVE_PI_* is not copied into the container",
            "use ALIVE_DOCKER_PI_PROVIDER / ALIVE_DOCKER_PI_MODEL for Docker",
        )
    if "ALIVE_MODEL_TRANSPORT" not in passed:
        record(
            "INFO", "container runs ALIVE_MODEL_TRANSPORT=direct (pinned Pi is installed, unused)"
        )


def main():
    print(f"ALIVE doctor, repository: {ROOT}")
    settings, known, env_file, environment = configuration()
    if settings is None:
        sys.exit(1)
    unknown_variables(known, env_file, environment)
    prerequisites(settings)
    database(settings)
    docker_parity(known, env_file, environment)
    counts = {lv: sum(r[0] == lv for r in results) for lv in ("OK", "INFO", "WARN", "FAIL")}
    print("\n" + ", ".join(f"{v} {k}" for k, v in counts.items()))
    sys.exit(1 if counts["FAIL"] else 0)


if __name__ == "__main__":
    main()
