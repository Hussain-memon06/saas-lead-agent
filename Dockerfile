# syntax=docker/dockerfile:1.7
#
# Multi-stage build for the AI SDR lead-research agent.
#
# Stage 1 (builder): install all deps into /app/.venv via uv
# Stage 2 (runtime): copy the venv + source into a slim image, run as non-root
#
# Cloud Run reads the PORT env var; default is 8080 for local docker-compose.

# ---------------------------------------------------------------------------
# Stage 1 — builder
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# Build deps for psycopg / asyncpg native bits
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# uv binary (pinned major.minor for reproducibility)
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /usr/local/bin/

WORKDIR /app

# 1. Resolve and install dependencies first (good cache layer).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# 2. Copy source and install the project itself.
COPY src ./src
RUN uv sync --frozen --no-dev

# ---------------------------------------------------------------------------
# Stage 2 — runtime
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PORT=8080

# Runtime libs only (no build-essential, no compilers).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Non-root user — Cloud Run requires the container to run as non-root.
RUN useradd --create-home --shell /bin/bash --uid 1000 app

WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src /app/src
COPY --chown=app:app pyproject.toml /app/pyproject.toml

USER app

EXPOSE 8080

# Cloud Run injects PORT; default to 8080 for docker-compose / local.
# Use sh -c so ${PORT} is expanded at container start, not build.
CMD ["sh", "-c", "exec uvicorn saas_lead_agent.api.main:app --host 0.0.0.0 --port ${PORT:-8080} --timeout-keep-alive 120"]
