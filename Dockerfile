# Lease Ledger: one container serving the API (/api/*) and the built React app (/, /app).
# Build:  docker build -t lease-ledger .
# Run:    docker run --rm -p 8000:8000 lease-ledger      -> http://localhost:8000  (Render sets $PORT itself)

# ---------------------------------------------------------------- 1. web app (static files)
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
# Same origin as the API: the browser calls /api/* on whatever host served the page.
ENV VITE_API_BASE=/api
RUN npm run build

# ---------------------------------------------------------------- 2. API + routing artifacts
FROM python:3.12-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app
WORKDIR /app

# Dependencies come from pyproject.toml (single source of truth); separate layer so code edits don't reinstall.
COPY pyproject.toml ./
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" \
        > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt && rm /tmp/requirements.txt

COPY . .
# Pin the "today" the feed policy uses so the image picks the same representative service week as the committed
# build and tests (week of Mon 2026-11-30). Bump it (or override with --build-arg) after dropping in new feeds.
ARG LEDGER_REFERENCE_DATE=2026-11-20
# Routing artifacts from the committed GTFS feeds (data/raw/gtfs_live) + Overture walk graph: ~20-60 s with numba.
# Then an uncompressed, memory-mappable copy of the label tables for LOW_MEMORY=1 (see DEPLOY.md).
RUN LEDGER_REFERENCE_DATE=$LEDGER_REFERENCE_DATE python -m ledger.pipeline.build \
    && python -m ledger.pipeline.transit --export-mmap \
    && python -c "import json; m=json.load(open('data/artifacts/manifest.json')); print('artifacts built', m.get('built_at') or m.get('built'))"

COPY --from=web /web/dist /app/web/dist

# Defaults; every one can be overridden in the Render dashboard (Environment tab) or with docker run -e.
ENV WEB_DIST=/app/web/dist \
    LLM_MODE=cached \
    LEDGER_ENV=prod \
    LOW_MEMORY=1 \
    LEDGER_NO_NUMBA=1 \
    MALLOC_ARENA_MAX=2 \
    PORT=8000

RUN useradd --create-home --uid 10001 ledger && chown -R ledger /app/data
USER ledger
EXPOSE 8000
# No Docker HEALTHCHECK: Render probes healthCheckPath (/api/health) itself, and a python-based probe is too
# slow to start on 0.1 CPU.
# One worker: the provider holds the routing tables in memory (a second worker would double it).
CMD ["sh", "-c", "exec uvicorn ledger.api.app:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips='*' --timeout-keep-alive 30"]
