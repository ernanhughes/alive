# syntax=docker/dockerfile:1

# Pinned Node (version and digest) for the Pi runtime stage and the final image (ALIVE-PI-01B).
# Pi requires Node >= 22.19. To update: change the tag and digest together, then rebuild.
ARG NODE_IMAGE=node:24.22.2-slim@sha256:c86ecead9e55a5210ac1727de38a4ca840bf03dcaf34dc9749addbf383b1920c

# Semantic search: bake the pinned 384-dimensional MiniLM model into the image. Set to false
# to build a text-only image (the runtime still reports the absence honestly).
ARG ALIVE_INSTALL_EMBEDDING_MODEL=true

# Stage 1: build the real dashboard UI.
FROM node:24-slim AS frontend-build
WORKDIR /build
COPY dashboard/package.json dashboard/package-lock.json ./dashboard/
RUN cd dashboard && npm ci
COPY dashboard/ ./dashboard/
ARG VITE_ALIVE_API_BASE=""
ENV VITE_ALIVE_API_BASE=${VITE_ALIVE_API_BASE}
RUN cd dashboard && npm run build

# Stage 1b: the pinned Pi agent, from a lockfile, with install scripts disabled. Pi is only ever
# run when ALIVE_MODEL_TRANSPORT=pi; the default transport (direct) never starts it.
FROM ${NODE_IMAGE} AS pi-runtime
WORKDIR /pi
COPY pi-runtime/package.json pi-runtime/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund

# Stage 2: reproducible Python runtime serving API + built UI.
FROM python:3.13-slim
ARG ALIVE_INSTALL_EMBEDDING_MODEL
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:${PATH}" \
    ALIVE_EMBEDDING_ENABLED=${ALIVE_INSTALL_EMBEDDING_MODEL} \
    ALIVE_EMBEDDING_PATH=/app/models/minilm \
    HF_HOME=/tmp/huggingface
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl postgresql-client \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10000 alive \
    && mkdir -p /app && chown alive:alive /app
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
COPY --from=pi-runtime /usr/local/bin/node /usr/local/bin/node
COPY --chown=alive:alive pyproject.toml uv.lock alembic.ini ./
USER alive
RUN uv sync --locked --no-dev \
    && mkdir -p /app/.alive /app/dashboard \
    && chmod 700 /app/.alive
COPY --chown=alive:alive alive/ ./alive/
COPY --chown=alive:alive migrations/ ./migrations/
COPY --chown=alive:alive fixtures/ ./fixtures/
COPY --chown=alive:alive config/ ./config/
COPY --chown=alive:alive scripts/docker-demo-seed.py scripts/docker-e2e.py scripts/docker-smoke-test.py scripts/prepare_embeddings.py ./scripts/
COPY --chown=alive:alive docker/entrypoint.sh docker/healthcheck.py ./docker/
COPY --from=frontend-build --chown=alive:alive /build/dashboard/dist ./dashboard/dist
COPY --from=pi-runtime --chown=alive:alive /pi/ ./pi-runtime/
# Download the public, revision-pinned MiniLM files at build time. A missing model fails the
# build instead of silently shipping an image that claims semantic search but has no vectors.
RUN if [ "$ALIVE_INSTALL_EMBEDDING_MODEL" = "true" ]; then \
      python scripts/prepare_embeddings.py --path /app/models/minilm \
      && test -s /app/models/minilm/model.onnx \
      && test -s /app/models/minilm/tokenizer.json \
      && test -s /app/models/minilm/provenance.json; \
    fi \
    && rm -rf /tmp/huggingface
# Fail the build, not a run, if the pinned Pi does not start under this Node.
RUN node --version \
    && node pi-runtime/node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js --version
RUN chmod +x docker/entrypoint.sh
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --retries=12 --start-period=60s \
    CMD python docker/healthcheck.py
ENTRYPOINT ["./docker/entrypoint.sh"]
