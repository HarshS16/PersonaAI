# PersonaAI

A persistent, evidence-backed AI representation of a person's professional identity.
Connect your professional sources once, and let AI use that context everywhere —
resume generation, interview prep, personal knowledge search, and more.

See [srd.txt](srd.txt) for the full product definition and [PLAN.md](PLAN.md) for
the implementation plan and milestone status.

## Architecture

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 (App Router), TypeScript, Tailwind v4, shadcn/ui, TanStack Query |
| Backend | FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic v2 |
| Jobs | Celery + Redis |
| Database | PostgreSQL 16 + pgvector (relational + graph-as-tables + embeddings) |
| AI | Provider abstraction (Anthropic / OpenAI / Gemini + a deterministic fake) |

```
PersonaAI/
├── apps/web/          # Next.js frontend
├── services/api/      # FastAPI + Celery backend
├── infra/             # docker-compose (Postgres, Redis, Mailpit)
├── eval/              # AI evaluation harness (M9)
└── PLAN.md            # milestone plan
```

## Prerequisites

- Docker Desktop (Postgres, Redis, Mailpit run in containers)
- Node 20+ and pnpm 10+
- Python 3.12+ and [uv](https://docs.astral.sh/uv/)

## Setup

```bash
# 1. Environment
cp .env.example .env            # defaults work for local dev (fake AI providers)

# 2. Infrastructure
pnpm infra:up                   # Postgres + Redis + Mailpit

# 3. Backend
cd services/api
uv venv --python 3.12
uv pip install -e ".[dev]"
cp ../../.env .env
.venv/Scripts/python -m alembic upgrade head   # apply migrations
cd ../..

# 4. Frontend
pnpm --dir apps/web install
```

## Running (three terminals)

```bash
pnpm dev:api        # FastAPI on :8000
pnpm dev:worker     # Celery worker (solo pool on Windows)
pnpm dev:web        # Next.js on :3000
```

Open http://localhost:3000. The browser calls the API through the Next proxy at
`/api/backend/*`, keeping auth cookies first-party.

- API health: http://localhost:8000/health
- Mailpit (dev email): http://localhost:8025

## Checks

```bash
pnpm test    # backend pytest + frontend type-check
pnpm lint    # ruff + mypy + eslint
```

## AI evaluation

```bash
cd services/api
.venv/Scripts/python -m eval          # synthetic persona; retrieval/groundedness/hallucination report
```

Runs against the fake provider by default (no keys needed); set `LLM_PROVIDER=groq`
to evaluate with the real model. Thresholds are enforced in the test suite.

## Production deployment

The full stack (Postgres, Redis, API, worker, beat, web, Caddy/TLS) ships as
Docker:

```bash
docker compose -f infra/docker-compose.prod.yml --env-file .env up -d --build
```

See [docs/deployment.md](docs/deployment.md) for configuration and operations,
and [docs/architecture.md](docs/architecture.md) for how the system fits together.

## Status

MVP complete (M0–M8) plus the AI evaluation framework (M9) and hardening +
deployment (M10): authentication, resume/GitHub/manual sources, an
evidence-backed persona, persona-aware RAG chat, the career suite (JD analysis,
validated resume generation, interview prep), dashboard/onboarding/explorer,
privacy & data ownership, observability, and a production Docker stack. See
[PLAN.md](PLAN.md) for the full milestone breakdown.
