# ─── Stage 1: Frontend Build ────────────────────────────────────
FROM node:22-alpine AS frontend

WORKDIR /app/frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

# ─── Stage 2: Python Dependencies ───────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock* hatch_build.py ./
RUN uv sync --no-dev --all-extras --frozen

COPY src/ ./src/

# ─── Stage 3: Production Runtime ────────────────────────────────
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.source="https://github.com/onllm-dev/4DPocket"
LABEL org.opencontainers.image.description="Self-hosted AI-powered personal knowledge base"
LABEL org.opencontainers.image.licenses="GPL-3.0"

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy built assets
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/pyproject.toml /app/pyproject.toml
COPY --from=frontend /app/frontend/dist /app/frontend/dist

# Copy entrypoint
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    PYTHONUNBUFFERED=1 \
    FDP_STORAGE__BASE_PATH=/data \
    FDP_SERVER__HOST=0.0.0.0 \
    FDP_SERVER__PORT=4040

# Create non-root user
RUN groupadd -r fourdpocket && useradd -r -g fourdpocket -d /app fourdpocket \
    && mkdir -p /data && chown -R fourdpocket:fourdpocket /app /data

USER fourdpocket

VOLUME /data
EXPOSE 4040

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:4040/api/v1/health || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["server"]
