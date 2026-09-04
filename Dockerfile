# syntax=docker/dockerfile:1

# ReMediX API — serves the FastAPI backend (and the built SPA if present).
#
# Build:  docker build -t remedix-api .
# Run:     docker run -p 8000:8000 --env-file .env remedix-api
#
# Local datasets (CREEDS/DrugBank/GEO/PPInteraction) are NOT baked into the
# image (see .dockerignore). Mount them at /app/src/data, e.g.:
#   docker run -p 8000:8000 -v "$(pwd)/src/data:/app/src/data" remedix-api

FROM python:3.14-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Copy uv from the official image (no pip/bootstrap needed).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (layer-cached; uv.lock gives reproducibility).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code.
COPY main.py run.py ./
COPY src/ ./src/

# Non-root runtime user.
RUN useradd --system --uid 1000 remedix \
    && chown -R remedix:remedix /app
USER remedix

# Port uvicorn will bind (informational; set actual bind via CLI).
EXPOSE 8000

# Healthcheck against the app's own health endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status==200 else 1)"]

# Uvicorn: 4 workers is a sane default for a mid-size host; override with
# WEB_CONCURRENCY. --proxy-trust for platforms that forward client IPs.
CMD ["uv", "run", "--no-dev", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
