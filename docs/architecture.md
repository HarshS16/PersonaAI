# PersonaAI — Architecture

A persistent, evidence-backed AI representation of a person's professional
identity. This document describes how the system is put together; see
[../PLAN.md](../PLAN.md) for milestone history and [../srd.txt](../srd.txt) for
the product requirements.

## High-level shape

```
Browser ──> Next.js (web) ──/api/backend/*──> FastAPI (api) ──> PostgreSQL + pgvector
                                                   │                    ▲
                                                   ├─ Redis ─ Celery ───┘  (ingestion, GitHub sync)
                                                   └─ Groq (LLM) · fastembed (embeddings)
```

- The browser only ever talks to the Next.js origin. API calls go to
  `/api/backend/*`, which Next proxies to FastAPI, so auth cookies stay
  first-party and OAuth/provider tokens never reach client JavaScript.
- FastAPI owns all domain logic and data. Long-running work (document
  ingestion, GitHub sync) is handed to Celery workers over Redis.
- One PostgreSQL database holds everything: relational persona data, the
  graph-as-edges, embeddings (pgvector + HNSW), and full-text indexes.

## Backend layers (`services/api/app`)

| Layer | Responsibility |
|---|---|
| `api/` | HTTP routers; thin, translate requests to domain calls |
| `domain/` | Persona engine, merge/conflict, career tools, dashboard — no framework deps |
| `ai/` | LLM + embedding provider abstractions, RAG retrieval, claim validation |
| `ingestion/` | Text extraction, chunking, the ingestion pipeline |
| `connectors/` | External sources (GitHub) normalized to a common shape |
| `workers/` | Celery app + tasks |
| `models/` | SQLAlchemy models; `core/` holds config, db, security, observability |

### The persona & evidence model

Every persona fact (skill, experience, project, education, achievement,
publication, certification) carries a **visibility** (private/shared/public), an
**evidence state** (verified/inferred/user-confirmed/unknown) and a numeric
**confidence**. Confidence combines independent evidence as `1 − Π(1 − wᵢ)`,
weighted by source kind (user-confirmed 1.0, resume 0.6, GitHub 0.5, …).

Every fact can have **evidence** rows pointing back to the source chunk and a
verbatim quote. Manual entries create their own user-confirmed evidence. This is
what makes the platform's claims auditable.

### Ingestion pipeline

```
upload ─> extract text ─> chunk ─> embed (pgvector) ─> snapshot persona
       ─> extract facts (LLM, with cited quotes) ─> merge ─> finalize
```

Merging canonicalizes (skill aliases), matches existing facts (exact + fuzzy),
attaches evidence, and recomputes confidence. Contradictory single-valued
identity fields raise a **conflict** for the user instead of overwriting. The
persona-mutating work runs in one transaction that commits only on success, so a
failed job never corrupts the persona; a snapshot is taken first for recovery.

### Persona-aware RAG

Retrieval fuses three signals, scoped to one persona: structured SQL over facts,
pgvector cosine search, and Postgres full-text — combined with reciprocal rank
fusion. Generated professional content passes the **claim validator**, which
drops unsupported claims, rejects unsupported figures, and softens unbacked
leadership ("Led" → "Worked on"). No evidence, no factual claim.

## Frontend (`apps/web`)

Next.js (App Router) + Tailwind + shadcn/ui. TanStack Query for data, an SSE
client for streaming chat, React Flow for the persona graph. Route protection is
a lightweight middleware gate on the refresh cookie; the API is the real
authority.

## AI providers

`LLMProvider` and `EmbeddingProvider` interfaces keep domain logic independent of
any vendor. Groq (OpenAI-compatible) is the default LLM; fastembed runs
embeddings locally at no cost. A deterministic fake provider backs the tests and
the evaluation harness, so CI needs no API keys or network.

## Evaluation (`services/api/eval`)

A synthetic persona plus question sets measure retrieval recall/MRR, negative
handling, groundedness, and hallucination rate against thresholds
(`python -m eval`). Run in CI with the fake provider; swap in Groq to also judge
generation quality.

## Observability & security

Structured JSON logs (structlog), Prometheus metrics at `/metrics`, optional
Sentry and OpenTelemetry (env-gated), and an `ai_calls` table tracking per-call
tokens and latency. Argon2 passwords, rotating refresh tokens with reuse
detection, Fernet-encrypted provider tokens, rate limiting, secure headers, and
strict per-persona scoping on every query.
