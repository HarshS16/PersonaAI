# PersonaAI API image (also used for the Celery worker/beat).
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_SYSTEM_PYTHON=1

# System libs: build tools for any wheels, libpq for psycopg.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# uv for fast, reproducible installs.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml ./
RUN uv pip install --system ".[ingestion,ai,embeddings,observability]"

# Application code.
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./

EXPOSE 8000

# Default: API server. The worker/beat override the command in compose.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
