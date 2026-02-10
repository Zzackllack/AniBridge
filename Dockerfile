# syntax=docker/dockerfile:1
# --- Stage 1: Build dependencies ---
FROM python:3.14-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# --- Stage 2: Install Python dependencies ---
FROM base AS deps
COPY --from=ghcr.io/astral-sh/uv:0.10.0 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project
COPY app/ ./app/
COPY VERSION ./
COPY alembic.ini ./
RUN uv sync --frozen --no-editable

# --- Stage 3: Copy source and create non-root user ---
FROM base AS final
WORKDIR /app

# Create default non-root user/group (IDs will be adjusted at runtime via entrypoint)
RUN addgroup --system appgroup && adduser --system --group appuser

ENV PATH="/app/.venv/bin:${PATH}"
COPY --from=deps /app/.venv /app/.venv
COPY app/ ./app/
COPY VERSION ./
COPY alembic.ini ./

# Prepare writable data directory for runtime mounts (ownership finalized at runtime)
RUN mkdir -p /data

# Lightweight entrypoint that adjusts UID/GID to PUID/PGID and drops privileges
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER root

EXPOSE 8000

# Healthcheck for FastAPI
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl --fail --silent http://localhost:8000/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "app.main"]
