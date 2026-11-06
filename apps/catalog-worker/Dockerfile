# syntax=docker/dockerfile:1
FROM python:3.14.8-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /usr/local/bin/uv
ENV SOURCE_DATE_EPOCH=0
COPY packages/catalog-core /build/packages/catalog-core
RUN uv build --wheel /build/packages/catalog-core --out-dir /wheels
WORKDIR /build/apps/catalog-worker
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
COPY apps/catalog-worker/pyproject.toml apps/catalog-worker/uv.lock ./
COPY apps/catalog-worker/src ./src
RUN uv sync --frozen --no-editable --no-install-package anibridge-catalog-core \
    && uv pip install --python /app/.venv/bin/python --no-deps /wheels/anibridge_catalog_core-1.0.0-py3-none-any.whl \
    && sha256sum /wheels/*.whl > /app/catalog-core-wheel.sha256

FROM python:3.14.8-slim AS final
WORKDIR /app
ARG PILOT_COMMIT=unknown
LABEL org.opencontainers.image.revision=$PILOT_COMMIT
ENV PATH="/app/.venv/bin:${PATH}"
COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/catalog-core-wheel.sha256 /app/catalog-core-wheel.sha256
RUN useradd --uid 1000 --create-home worker \
    && install -d -o worker -g worker /state /public
USER worker
EXPOSE 8080
ENTRYPOINT ["anibridge-catalog-worker"]
CMD ["--config", "/config/worker.json"]
