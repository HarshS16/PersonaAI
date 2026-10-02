# PersonaAI

**A persistent, evidence-backed AI representation of your professional identity.**

Connect your professional sources once — resume, GitHub, manual entry — and
PersonaAI builds a structured, verifiable *persona*: your skills, experience,
projects, education, and the evidence behind every claim. That persona then
becomes a reusable context layer for AI-powered tasks: ask questions about your
own background, generate a JD-tailored resume, analyze your fit for a role, and
prepare for interviews — all grounded in what you've actually done, with no
invented experience.

> **Core philosophy:** connect your professional identity once; let AI use that
> context everywhere.

See [srd.txt](srd.txt) for the original product definition, [PLAN.md](PLAN.md)
for the milestone-by-milestone build, and [docs/architecture.md](docs/architecture.md)
for a deeper architectural walkthrough.

---

## What it does

- **Aggregates multiple sources** into one persona — upload a resume (PDF/DOCX/TXT),
  connect GitHub (repos → projects, languages → skills), or add facts by hand.
- **Extracts structured facts with evidence.** Every skill, role, and project is
  backed by a verbatim quote from its source. Facts carry a confidence score and
  an evidence state (verified / inferred / user-confirmed).
- **Resolves conflicts instead of overwriting.** If a second source disagrees
  (e.g. a different job title), PersonaAI raises a conflict for you to resolve.
- **Ask My Persona** — a streaming chat that answers questions about your career
  using only your persona, with citations back to the sources.
- **Career suite** — paste a job description to get a requirement-by-requirement
  gap analysis (Strong / Partial / Not demonstrated), generate a resume whose
  every bullet is validated against your evidence, and produce grounded interview
  questions.
- **The claim validator** — the anti-hallucination guard. It drops unsupported
  claims, rejects unsupported figures, and softens over-claimed leadership
  ("Led a team of 50" → removed if there's no evidence). *No evidence, no claim.*
- **Dashboard, onboarding, and a Persona Explorer graph** of how your skills,
  projects, and experience connect.
- **You own your data** — per-fact visibility (private / shared / public), full
  export (JSON + documents ZIP), and one-click account deletion.

---

## How it works

```
CONNECT ──> EXTRACT ──> EVIDENCE ──> REMEMBER ──> ASSIST
 sources    LLM pulls    every fact   persona +    chat, resume,
 (resume,   structured   cites a      embeddings   gap analysis,
  GitHub,   facts        source quote  (RAG)        interview prep
  manual)
```

1. **Ingest.** An uploaded document or GitHub sync runs through a background
   pipeline: extract text → chunk → embed (pgvector) → extract facts with the
   LLM → merge into the persona. GitHub repos become projects, languages become
   skills. The persona is snapshotted first, and the whole update is one
   transaction, so a failed job can never corrupt it.
2. **Ground.** Each extracted fact keeps a quote and a link to its source chunk.
   Confidence combines evidence across sources as `1 − Π(1 − wᵢ)`.
3. **Retrieve.** Questions and generators use persona-aware RAG: structured SQL
   over facts + vector search + full-text search, fused with reciprocal rank
   fusion.
4. **Validate.** Any professional output is checked claim-by-claim against the
   retrieved evidence before you see it.

---

## Architecture

```
Browser ──> Next.js (web) ──/api/backend/*──> FastAPI (api) ──> PostgreSQL + pgvector
                                                   │                    ▲
                                                   ├─ Redis ─ Celery ───┘  (ingestion, GitHub sync)
                                                   └─ Groq (LLM) · fastembed (embeddings)
```

- The browser only talks to the Next.js origin; API calls are proxied to FastAPI
  at `/api/backend/*`, so auth cookies stay first-party and OAuth/provider tokens
  never reach the browser.
- FastAPI owns all domain logic and data. Heavy work (ingestion, GitHub sync)
  runs on Celery workers via Redis.
- One PostgreSQL database holds everything: relational persona data, the
  evidence graph, embeddings (pgvector + HNSW), and full-text indexes.
- AI is behind provider interfaces (`LLMProvider`, `EmbeddingProvider`) so no
  domain code is coupled to a vendor. A deterministic fake provider backs the
  tests and the evaluation harness, so CI needs no API keys.

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 (App Router), TypeScript, Tailwind v4, shadcn/ui, TanStack Query, React Flow |
| Backend | FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic v2 |
| Jobs | Celery + Redis |
| Database | PostgreSQL 16 + pgvector (relational + graph + embeddings + full-text) |
| LLM | Groq (OpenAI-compatible) by default; OpenAI/Anthropic/Gemini pluggable; fake for tests |
| Embeddings | local `fastembed` (no key, no cost); OpenAI/Voyage pluggable |
| Observability | structlog, Prometheus `/metrics`, optional Sentry + OpenTelemetry |

### Repository layout

```
PersonaAI/
├── apps/web/            # Next.js frontend
│   └── src/
│       ├── app/(app)/   # authenticated pages: dashboard, persona, sources, ask, career, settings
│       ├── app/(auth)/  # login, signup, password reset
│       ├── components/  # UI + feature components
│       └── lib/ hooks/  # API clients and React Query hooks
├── services/api/        # FastAPI + Celery backend
│   └── app/
│       ├── api/         # HTTP routers
│       ├── domain/      # persona engine, merge/conflict, career, dashboard
│       ├── ai/          # LLM/embedding providers, RAG retrieval, claim validation
│       ├── ingestion/   # text extraction, chunking, the pipeline
│       ├── connectors/  # GitHub connector
│       ├── models/      # SQLAlchemy models
│       └── workers/     # Celery app + tasks
│   ├── eval/            # AI evaluation harness
│   └── migrations/      # Alembic migrations
├── infra/               # docker-compose (dev + prod), Caddy, Postgres init
└── docs/                # architecture + deployment docs
```

---

## Running it locally

### Prerequisites

- **Docker Desktop** (runs Postgres, Redis, Mailpit)
- **Node 20+** and **pnpm 10+**
- **Python 3.12+** and **[uv](https://docs.astral.sh/uv/)**
- A **Groq API key** (free tier) for real AI — or run on the fake provider with
  no key.

### 1. Environment

```bash
cp .env.example .env
```

The defaults work for local development. To use real AI, set `GROQ_API_KEY` in
`.env` (and copy it to `services/api/.env`). Embeddings run locally via
`fastembed` with no key. Generate the two secrets:

```bash
# JWT signing secret
python -c "import secrets; print(secrets.token_urlsafe(64))"
# Fernet key for encrypting OAuth tokens at rest
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2. Infrastructure

```bash
pnpm infra:up      # Postgres (pgvector) + Redis + Mailpit
```

### 3. Backend

```bash
cd services/api
uv venv --python 3.12
uv pip install -e ".[dev,ingestion,ai,embeddings]"
cp ../../.env .env
uv run --no-sync alembic upgrade head    # apply migrations
cd ../..
```

### 4. Frontend

```bash
pnpm --dir apps/web install
```

### 5. Run (three terminals)

```bash
pnpm dev:api        # FastAPI on http://localhost:8000
pnpm dev:worker     # Celery worker (processes resume/GitHub ingestion)
pnpm dev:web        # Next.js on http://localhost:3000
```

Open **http://localhost:3000**. Dev email (password-reset links) is viewable at
**http://localhost:8025** (Mailpit). API health is at
**http://localhost:8000/health**.

> The **worker must be running** for resume uploads and GitHub syncs to be
> processed — the API enqueues the job and the worker does the work.

---

## Using it end to end

1. **Sign up** at `/signup` (email + password), or use *Continue with GitHub*.
2. On the **Dashboard** you'll see the "Build your AI Persona" onboarding card.
3. **Add sources** (Sources page):
   - **Upload a resume** (PDF/DOCX/TXT). Watch the progress bar; when it finishes
     you'll see a summary like "6 skills added".
   - **Connect GitHub** by entering a public username (or log in with GitHub to
     include private repos), then sync.
4. **Review your persona** (Persona page): every fact is editable, each has an
   **Evidence** popover showing the quote it came from. Confirm inferred facts,
   fix anything wrong, set per-fact visibility, and open the **Explorer** to see
   the graph. If two sources disagreed, resolve the **conflict** on the Sources
   page.
5. **Ask My Persona** (Ask AI page): e.g. *"What projects have I built involving
   RAG?"* — the answer streams with citation chips.
6. **Career** (Career page): paste a job description, then
   - **Gap analysis** — each requirement marked Strong / Partial / Not demonstrated;
   - **Resume** — a tailored, evidence-validated resume with ATS keyword coverage
     and a copy-to-markdown button;
   - **Interview** — grounded questions across technical / project / system-design
     / behavioral / HR modes.
7. **Settings**: export your data (JSON or ZIP), manage visibility, or delete your
   account.

---

## AI evaluation

```bash
cd services/api
.venv/Scripts/python -m eval                 # fake provider (no key needed)
# or, with real AI:
# (ensure LLM_PROVIDER=groq and GROQ_API_KEY are set in .env)
```

Builds a synthetic persona and reports retrieval recall/MRR, negative-handling
accuracy, groundedness, and **hallucination rate** against thresholds. The same
thresholds are asserted in the test suite.

## Tests & checks

```bash
pnpm test          # backend pytest (against the dockerized Postgres) + frontend type-check
pnpm lint          # ruff + mypy + eslint
pnpm build:web     # production build of the frontend
```

The backend tests use the deterministic fake AI provider, so they need no API
keys or network — just the dev Postgres from `pnpm infra:up`.

## Production deployment

The whole stack ships as Docker — Postgres, Redis, API, Celery worker + beat,
the web app, and Caddy for automatic HTTPS:

```bash
docker compose -f infra/docker-compose.prod.yml --env-file .env up -d --build
```

Migrations are applied automatically by a one-shot `migrate` service before the
API starts. See [docs/deployment.md](docs/deployment.md) for full configuration
and operations.

---

## Configuration

Key environment variables (see [.env.example](.env.example) for the full list):

| Variable | Purpose |
|---|---|
| `LLM_PROVIDER` | `groq` (default), `openai`, `anthropic`, `gemini`, or `fake` |
| `GROQ_API_KEY` | Groq key; models default to GPT-OSS 20B/120B |
| `EMBEDDING_PROVIDER` | `fastembed` (default, local), `openai`, `voyage`, or `fake` |
| `JWT_SECRET` / `ENCRYPTION_KEY` | auth signing + provider-token encryption |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | GitHub login + connector (OAuth app) |
| `DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER_URL` | infrastructure endpoints |
| `SENTRY_DSN`, `OTEL_EXPORTER_OTLP_ENDPOINT` | optional observability |

---

## Status

The full MVP and hardening plan (M0–M10) is complete: authentication,
resume/GitHub/manual sources, the evidence-backed persona with conflict
detection, persona-aware RAG chat, the career suite, dashboard/onboarding/
explorer, privacy & data ownership, an AI evaluation framework, observability,
and a production Docker stack. Future phases (LinkedIn/Medium/X connectors,
portfolio & content generators, the public "Ask &lt;Name&gt; AI" page) are
outlined in [PLAN.md](PLAN.md).
