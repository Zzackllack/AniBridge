# syntax=docker/dockerfile:1
# --- Stage 1: Build dependencies ---
FROM python:3.12-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# --- Stage 2: Install Python dependencies ---
FROM base AS deps
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# --- Stage 3: Copy source and create non-root user ---
FROM base AS final
WORKDIR /app

# Create non-root user
RUN addgroup --system appgroup && adduser --system --group appuser

COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY app/ ./app/
COPY requirements.txt ./

RUN chown -R appuser:appgroup /app
USER appuser

EXPOSE 8000

# Healthcheck for FastAPI
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl --fail --silent http://localhost:8000/health || exit 1

CMD ["python", "-m", "app.main"]
