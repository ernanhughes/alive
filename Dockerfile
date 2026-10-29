# syntax=docker/dockerfile:1

# Stage 1: build the real dashboard UI.
FROM node:24-slim AS frontend-build
WORKDIR /build
COPY dashboard/package.json dashboard/package-lock.json ./dashboard/
RUN cd dashboard && npm ci
COPY dashboard/ ./dashboard/
ARG VITE_ALIVE_API_BASE=""
ENV VITE_ALIVE_API_BASE=${VITE_ALIVE_API_BASE}
RUN cd dashboard && npm run build

# Stage 2: reproducible Python runtime serving API + built UI.
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:${PATH}"
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl postgresql-client \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10000 alive \
    && mkdir -p /app && chown alive:alive /app
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
COPY --chown=alive:alive pyproject.toml uv.lock alembic.ini ./
USER alive
RUN uv sync --locked --no-dev
COPY --chown=alive:alive alive/ ./alive/
COPY --chown=alive:alive migrations/ ./migrations/
COPY --chown=alive:alive fixtures/ ./fixtures/
COPY --chown=alive:alive config/ ./config/
COPY --chown=alive:alive scripts/docker-demo-seed.py ./scripts/docker-demo-seed.py
COPY --chown=alive:alive docker/entrypoint.sh docker/healthcheck.py ./docker/
COPY --from=frontend-build --chown=alive:alive /build/dashboard/dist ./dashboard/dist
RUN chmod +x docker/entrypoint.sh
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --retries=12 --start-period=60s \
    CMD python docker/healthcheck.py
ENTRYPOINT ["./docker/entrypoint.sh"]
