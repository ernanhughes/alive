#!/bin/sh
# ALIVE-DOCKER-01 entrypoint: wait for PostgreSQL, migrate, optionally seed,
# then run the real application. Never destroys existing data.
set -eu

wait_for_postgres() {
  python - <<'EOF'
import os, socket, sys, time
from urllib.parse import urlparse

url = os.environ.get("DATABASE_URL", "")
parsed = urlparse(url)
host = parsed.hostname or "db"
port = parsed.port or 5432
deadline = time.time() + 120
while time.time() < deadline:
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"postgres reachable at {host}:{port}", flush=True)
            sys.exit(0)
    except OSError:
        time.sleep(1)
print(f"postgres not reachable at {host}:{port} after 120s", file=sys.stderr)
sys.exit(1)
EOF
}

case "${DATABASE_URL:-}" in
*postgres*)
  wait_for_postgres
  ;;
*)
  echo "Non-PostgreSQL DATABASE_URL; skipping TCP wait" >&2
  ;;
esac

echo "Running database migrations (alembic upgrade head)..." >&2
alembic upgrade head

if [ "${ALIVE_DEMO_MODE:-true}" = "true" ]; then
  # Seed in the background once the server is healthy; the server itself
  # starts immediately so readiness probes are not delayed.
  (python scripts/docker-demo-seed.py || echo "demo seed skipped (see log above)") &
fi

exec uvicorn alive.app:app --host 0.0.0.0 --port 8000 --proxy-headers
