# syntax=docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
# --- Stage 1: Build dependencies ---
FROM python:3.14.8-slim@sha256:fbecd461fc72d21b2143c6eaba25143738079154a6d0ea3da3aec724f50eed4a AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ffmpeg \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# --- Stage 2: Install Python dependencies ---
FROM base AS deps
WORKDIR /build/apps/api
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
COPY --from=ghcr.io/astral-sh/uv:0.12.23@sha256:61d393e44e249f2e4b526b6c7ddcecce245946826e608e11c93ad4f5bba55b21 /uv /usr/local/bin/uv
ENV SOURCE_DATE_EPOCH=0
COPY packages/catalog-core /build/packages/catalog-core
RUN uv build --wheel /build/packages/catalog-core --out-dir /wheels
COPY apps/api/pyproject.toml ./pyproject.toml
COPY apps/api/uv.lock ./uv.lock
RUN uv sync --frozen --no-install-project --no-install-package anibridge-catalog-core
COPY apps/api/app/ ./app/
COPY VERSION ./
COPY apps/api/alembic.ini ./alembic.ini
COPY apps/api/README.md apps/api/LICENSE ./
RUN uv sync --frozen --no-editable --no-install-package anibridge-catalog-core \
    && uv pip install --python /app/.venv/bin/python --no-deps /wheels/anibridge_catalog_core-*.whl \
    && sha256sum /wheels/*.whl > /app/catalog-core-wheel.sha256

# --- Stage 3: Copy source and create non-root user ---
FROM base AS final
WORKDIR /app

ARG PILOT_COMMIT=unknown
LABEL org.opencontainers.image.revision=$PILOT_COMMIT

# Create default non-root user/group (IDs will be adjusted at runtime via entrypoint)
RUN addgroup --system appgroup && adduser --system --group appuser

ENV PATH="/app/.venv/bin:${PATH}"
COPY --from=deps /app/.venv /app/.venv
COPY --from=deps /app/catalog-core-wheel.sha256 /app/catalog-core-wheel.sha256
COPY apps/api/app/ ./app/
COPY VERSION ./
COPY apps/api/alembic.ini ./alembic.ini

# Prepare writable data directory for runtime mounts (ownership finalized at runtime)
RUN mkdir -p /data

COPY docker/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

USER root

EXPOSE 8000

# Healthcheck for FastAPI
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD gosu appuser:appgroup curl --fail --silent http://localhost:8000/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "app.main"]
