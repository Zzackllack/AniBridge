# syntax=docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
FROM python:3.14.8-slim@sha256:fbecd461fc72d21b2143c6eaba25143738079154a6d0ea3da3aec724f50eed4a AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.23@sha256:61d393e44e249f2e4b526b6c7ddcecce245946826e608e11c93ad4f5bba55b21 /uv /usr/local/bin/uv
ENV SOURCE_DATE_EPOCH=0
COPY packages/catalog-core /build/packages/catalog-core
RUN uv build --wheel /build/packages/catalog-core --out-dir /wheels
WORKDIR /build/apps/catalog-worker
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
COPY apps/catalog-worker/pyproject.toml apps/catalog-worker/uv.lock ./
COPY apps/catalog-worker/src ./src
RUN uv sync --frozen --no-editable --no-install-package anibridge-catalog-core \
    && uv pip install --python /app/.venv/bin/python --no-deps /wheels/anibridge_catalog_core-*.whl \
    && sha256sum /wheels/*.whl > /app/catalog-core-wheel.sha256

FROM python:3.14.8-slim@sha256:fbecd461fc72d21b2143c6eaba25143738079154a6d0ea3da3aec724f50eed4a AS final
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
