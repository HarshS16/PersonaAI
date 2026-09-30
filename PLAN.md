# PersonaAI — Implementation Plan

Source of truth for requirements: [srd.txt](srd.txt). This file is the execution plan; checkboxes are updated as work lands.

**Strategy:** build the persona + evidence engine first (SRD §71), then add applications on top of it as vertical slices (backend + UI + tests per milestone). Each milestone ends in a runnable, tested state.

---

## 0. Key decisions

| Area | Decision | SRD ref |
|---|---|---|
| Frontend | Next.js (App Router) + TypeScript + Tailwind + shadcn/ui, TanStack Query, react-hook-form + zod | §38 |
| Backend | FastAPI (Python 3.13 via uv), SQLAlchemy 2 (async) + Alembic, Pydantic v2 | §38 |
| DB | PostgreSQL 16 + pgvector (one database for relational, graph-as-tables, embeddings, full-text) | §14, §15, §37 |
| Queue | Redis + Celery worker (in Docker; on Windows, run natively with `--pool=solo`) | §40 |
| Graph | Relational edge table (`relations`) in Postgres; no Neo4j for MVP | §14 |
| RAG | Own thin retrieval layer (SQL + pgvector + tsvector hybrid). No LangChain, so domain logic stays independent of any framework | §39 |
| LLM | `LLMProvider` interface with Anthropic (default), OpenAI and Gemini adapters, plus a deterministic `FakeProvider` for tests. Fast model for extraction/intent, strong model for generation | §39 |
| Embeddings | `EmbeddingProvider` interface: Voyage / OpenAI / Gemini / local `fastembed` (works with no API key). Dimension fixed by config; switching models triggers a re-embed job | §39 |
| Auth | Email+password (argon2), Google + GitHub OAuth, JWT access + refresh tokens in httpOnly cookies, RBAC (`user`, `admin`) | §19, §36 |
| Secrets | OAuth provider tokens Fernet-encrypted in the DB, never sent to the browser. Next.js proxies `/api/*` to FastAPI, which keeps calls same-origin | §36 |
| File storage | Storage interface; local volume in dev, S3-compatible adapter for production | §13 |
| Email | SMTP interface; Mailpit in docker-compose for dev (password reset) | §19 |
| Observability | structlog JSON logs, OpenTelemetry tracing, Prometheus `/metrics`, optional Sentry, `ai_calls` table for latency and tokens | §61 |

### Repo layout
```
PersonaAI/
├── apps/web/                 # Next.js frontend
├── services/api/             # FastAPI + Celery
│   └── app/
│       ├── api/              # routers (auth, persona, sources, chat, career, ...)
│       ├── core/             # config, security, db, logging, rate limiting
│       ├── models/           # SQLAlchemy models
│       ├── schemas/          # Pydantic DTOs
│       ├── domain/           # persona engine, evidence, merge/conflict, validation (no framework deps)
│       ├── ai/               # providers, prompts, extraction schemas, RAG, claim validator
│       ├── connectors/       # base Connector + resume, github, manual, (phase 2) medium, hashnode...
│       ├── ingestion/        # parse → normalize → chunk → extract → validate → update → embed
│       └── workers/          # Celery app + tasks
├── eval/                     # synthetic personas, question sets, eval runner
├── infra/                    # docker-compose, Dockerfiles, Caddy config
└── docs/                     # architecture notes, API docs
```

---

## 1. Data model (Postgres)

All persona-owned rows carry `persona_id`, `visibility` (`private|shared|public`, default `private`), `state` (`verified|inferred|user_confirmed|unknown`), `confidence`, `created_at`, `updated_at`, `deleted_at`.

- **users**: id, email, name, password_hash, role, email_verified, created_at, updated_at
- **oauth_accounts**: user_id, provider, provider_user_id, access_token_enc, refresh_token_enc, scopes
- **sessions/refresh_tokens**, **password_reset_tokens**
- **personas**: id, user_id, version, status, headline/title, summary, location, links (jsonb), completeness
- **persona_versions**: persona_id, version, snapshot (jsonb), reason, created_at (supports recovery, §60)
- **sources**: id, persona_id, type, provider, url, status, last_synced, stats (jsonb), error
- **documents**: id, source_id, title, mime, content, metadata, content_hash
- **chunks**: id, document_id, ordinal, text, tsvector, embedding vector(N), metadata (HNSW + GIN indexes). This is the SRD's "Embedding" entity.
- **skills**: name, canonical_name, category, confidence, evidence_count
- **experiences**: company, role, employment_type (job/internship/freelance/oss/volunteer/leadership), start/end, description, highlights
- **projects**: name, description, technologies[], role, outcomes[], repository_url
- **education**, **achievements**, **publications** (research), **certifications**
- **knowledge_areas**: name, parent_id (tree, §8.5)
- **preferences**: key, value, source (`explicit|inferred_pending|confirmed`)
- **writing_style**: per-persona metrics (jsonb)
- **evidence**: entity_type, entity_id, source_id, chunk_id, quote/content, locator (jsonb, e.g. repo/section), confidence
- **relations**: subject_type/id, predicate (`worked_at|built|uses|contributed_to|authored|skilled_in|published`), object_type/id, evidence_id
- **conflicts**: persona_id, field, candidates (jsonb), status (`open|resolved`), resolution
- **activity_events**: dashboard "Recent updates" feed
- **jobs**: ingestion job tracking (status, progress, error, attempts)
- **chat_sessions / chat_messages**: with citations jsonb
- **generations**: type (resume/cover_letter/...), input, output, claims (jsonb with evidence + verdicts)
- **ai_calls**: provider, model, purpose, tokens_in/out, latency_ms, cost estimate

**Confidence:** `1 − Π(1 − wᵢ)` across distinct evidence items. Weights by source kind: user-confirmed 1.0, resume explicit 0.6, GitHub code or language 0.5, README mention 0.35, inferred 0.25. Shown as High / Medium / Low.
**Completeness:** weighted coverage of identity, experience, education, skills (≥5), projects (≥2), achievements, preferences, plus the evidence ratio.

---

## 2. Milestones

### M0 — Foundations ✅
- [x] `git init`, `.gitignore`, `.editorconfig`, root `README.md`, root `package.json` scripts (`dev`, `test`, `lint`)
- [x] `infra/docker-compose.yml`: postgres+pgvector, redis, mailpit
- [x] FastAPI skeleton: settings (pydantic-settings, `.env.example`), async DB session, Alembic, `/health` + `/health/ready`, structlog, error envelope, CORS, request IDs, rate limiter
- [x] Celery app plus a sample task, with retry/backoff defaults
- [x] Next.js skeleton: Tailwind v4, shadcn/ui, app shell with the SRD §50 navigation (Dashboard, Persona, Sources, Ask AI, Career, Content, Portfolio, Settings), API proxy, TanStack Query
- [x] Tooling: ruff + mypy + pytest (backend); eslint + tsc (frontend)
- **Done when:** `docker compose up` + `pnpm dev` show the app shell, `/health` is green, and CI-style `pnpm test` passes. ✅ Verified: infra up, migrations apply, pytest + tsc + eslint + next build all green.
- _Note: Playwright E2E and pre-commit deferred to M1 (added alongside the first real user journey)._

### M1 — Authentication & accounts (§19, §36)
- [ ] Users table, argon2 hashing, signup/login/logout, JWT access + rotating refresh in httpOnly cookies
- [ ] Password reset by email token (Mailpit in dev); email verification
- [ ] Google OAuth + GitHub OAuth login (authorization code flow, state + PKCE), account linking
- [ ] Account management: change name/email/password, linked accounts
- [ ] RBAC dependency, rate limiting (slowapi + Redis) on auth endpoints, request validation
- [ ] Frontend: login, signup, forgot/reset password, protected-route middleware, account settings
- **Done when:** a user can sign up, log in, reset their password and log in with GitHub. Tests cover token expiry, refresh rotation and rate limiting.

### M2 — Persona core, manual profile & editor (§7, §8, §9, §22)
- [ ] All persona tables and migrations, visibility and evidence state enums, soft delete
- [ ] Persona service: CRUD for identity, experience, education, skills, projects, achievements, publications, preferences, knowledge areas
- [ ] Manual entries create `user_confirmed` evidence, so manual data is evidence-backed
- [ ] Persona versioning: snapshot on every material change, list versions, restore
- [ ] APIs: `GET/PATCH /persona`, `GET/POST/PATCH/DELETE /skills|/projects|/experience|/education|/achievements|/preferences`, `POST /facts/{id}/confirm`, `GET /facts/{id}/evidence`
- [ ] Frontend Persona Editor: tabbed sections; edit, delete and confirm inferred facts; add missing info; evidence drawer per fact; visibility toggle
- **Done when:** a user can build a complete persona by hand, see evidence on every fact, and restore an earlier version.

### M3 — AI provider layer & resume ingestion (§10, §12, §13, §39, §40)
- [ ] `LLMProvider` (Anthropic/OpenAI/Gemini/Fake) with structured-output helper (Pydantic schema → JSON, with repair and retry), streaming, and token/latency logging to `ai_calls`
- [ ] `EmbeddingProvider` (Voyage/OpenAI/Gemini/fastembed/Fake)
- [ ] `POST /documents/upload` for PDF (pdfplumber/pypdf), DOCX (python-docx) and TXT, with size/type validation and content-hash dedupe
- [ ] Pipeline as Celery chain: detect type → extract text → normalize → section-aware chunking → entity extraction → relation extraction → fact validation → persona update → embedding. Job progress via `GET /jobs/{id}`
- [ ] Extraction prompts and schemas for resume sections; every extracted fact must cite a chunk and a quote span, or it is dropped
- [ ] **Persona merge engine (§46):** canonicalize (skill alias dictionary, e.g. "ReactJS" → React, company/title normalization), match existing facts (exact + fuzzy + embedding similarity), update or create, attach evidence, recompute confidence
- [ ] **Conflict detection (§47):** contradictory single-valued fields (title, dates, role) → `conflicts` row, never silently overwritten
- [ ] Failed jobs retry with backoff; the persona update runs in one transaction, so a failure cannot corrupt the persona (§60)
- [ ] Frontend: onboarding resume upload with live progress, review screen ("We found 23 skills, 4 roles…" with ✓/✗ per fact), conflict resolution UI
- **Done when:** uploading a sample resume produces a reviewable persona with evidence quotes. A second, conflicting resume raises conflicts instead of overwriting.

### M4 — GitHub connector (§10, §54)
- [ ] `Connector` base interface (`connect`, `sync`, `disconnect`, `stats`) shared by all future sources
- [ ] `POST /sources/github/connect` (OAuth with `read:user`, `repo` optional for private repos, chosen by the user), tokens encrypted server-side
- [ ] Sync: repos (owned, forked, contributed), languages, topics, READMEs, commit counts and recent commit messages by the user, contribution stats, stars. Respects rate limits, conditional requests (ETag), incremental sync
- [ ] Map to persona: repo → project (README-summarized description, technologies from languages + manifests such as package.json, pyproject and requirements), language/tech → skills with GitHub evidence, OSS contributions → experience (type `oss`)
- [ ] Source management API and UI: status, last synced, repo count, Sync, Disconnect (disconnect removes the token and optionally the derived data)
- [ ] Scheduled periodic re-sync (Celery beat), opt-in
- **Done when:** connecting GitHub discovers repositories, projects and technologies; they merge with resume facts and raise evidence counts. Sync and disconnect both work from the Sources page.

### M5 — Semantic memory, Ask My Persona & personal search (§15–18, §23, §31, §44, §49)
- [ ] Embed all chunks plus a fact card for each structured fact; HNSW index; tsvector keyword index
- [ ] Persona-aware RAG: intent detection (fact lookup / list / evaluation / generation / search) → structured SQL retrieval → hybrid semantic search (vector + BM25-style, reciprocal rank fusion) → evidence fetch → context assembly with token budget
- [ ] **Claim validator** (reused by every generator): split the draft into atomic claims, match each against retrieved evidence (LLM judge with strict rubric + lexical checks for numbers, titles and team sizes), then allow, downgrade ("Led" → "Worked on" if only that is supported) or reject
- [ ] `POST /chat` with SSE streaming, sources/citations in the response (SRD §44 shape), saved chat sessions
- [ ] `GET /search?q=` personal knowledge search with snippets, grouped by source
- [ ] Frontend Ask AI: chat UI with streaming, citation chips that open the evidence, suggested prompts (§52), session history; Search page
- **Done when:** "What projects have I built involving RAG?" returns the right projects with citations, and the validator blocks a seeded unsupported claim in tests.

### M6 — Career suite (§24–28, §45, §55)
- [ ] `POST /jd/analyze`: extract required/preferred skills, experience, education, responsibilities, technologies and domain into a structured JD
- [ ] Matching: each requirement is classified **Strong / Partial / Not demonstrated** with an evidence explanation (career gap analysis, §27)
- [ ] `POST /resume/generate` (§45 request/response): select relevant experience and projects → generate bullets in the user's style → ATS optimization (keyword coverage, standard headings, no tables) → claim validation → evidence map per bullet. Formats: one-page / two-page. Export to PDF (WeasyPrint or browser print) and DOCX
- [ ] `POST /interview/start` with modes technical / HR / project / system design / behavioral; questions grounded in JD + projects + weak areas; answer submission with feedback; session history
- [ ] Frontend Career section: JD analyzer (requirement table with evidence), gap view, resume builder (editable preview, click a bullet to see its evidence, regenerate a section), interview practice UI
- **Done when:** the full SRD §68 end-to-end scenario works: upload resume → connect GitHub → confirm → analyze JD → generate validated resume → interview prep.

### M7 — Dashboard, onboarding & Persona Explorer (§20, §21, §51, §53)
- [ ] Onboarding wizard ("Build your AI Persona") with source checklist and progress
- [ ] Dashboard: greeting, completeness bar, top skills, projects, experience timeline, recent updates feed, quick actions
- [ ] Persona Explorer: interactive graph (React Flow) of Skills ↔ Projects ↔ Technologies ↔ Experience ↔ Evidence, with filter and focus
- **Done when:** the dashboard reflects live persona state and the explorer shows a navigable graph for the sample persona.

### M8 — Privacy & data ownership (§34, §35)
- [ ] Visibility enforced in every query path (the public API can only read `public` rows)
- [ ] Export the full persona (JSON + original documents ZIP)
- [ ] Delete individual facts, sources (cascade derived evidence and recompute), and the whole account (hard delete + token revocation)
- [ ] Settings UI: privacy, connected sources, export, delete account
- **Done when:** export round-trips and account deletion leaves no user rows, files or embeddings (verified by test).

### M9 — AI evaluation framework (§62, §63)
- [ ] Synthetic personas (e.g. Persona A: 20 projects, 10 skills, 5 jobs, 3 papers, 50 documents) generated as fixtures
- [ ] Question sets with expected answers covering facts, lists, negatives ("Does the person have AWS experience?" → no) and adversarial prompts that invite hallucination
- [ ] Metrics: factuality, groundedness (claims with evidence), retrieval recall@k / MRR, resume–JD relevance, hallucination rate, consistency across repeated runs
- [ ] `uv run eval` CLI producing a report; thresholds checked in tests (run against the Fake provider in CI, real provider on demand)
- **Done when:** the eval report runs end to end and hallucination rate on the adversarial set is measured and below an agreed threshold.

### M10 — Hardening, observability & deployment (§36, §59–61)
- [ ] OpenTelemetry tracing (FastAPI, SQLAlchemy, Celery, httpx), Prometheus metrics, Sentry hook, AI token/latency dashboard data
- [ ] Security pass: rate limits on all routes, input limits, CSRF on cookie auth, secure headers, dependency audit, OAuth tokens never in responses (tested)
- [ ] Performance: query p95 < 3s excluding LLM time, resume < 15s; indexes and N+1 checks; load test with locust
- [ ] Production docker-compose (api, worker, beat, web, postgres, redis, Caddy for TLS), backups, migration runbook
- [ ] Docs: README, architecture doc, OpenAPI, contributor guide
- **Done when:** a fresh clone can be run with one command, all test suites are green, and the security checklist is complete.

---

### Phase 2 (after MVP is solid) (§56)
- [ ] Cover letters and job-application answers (reuse JD analysis + validator)
- [ ] Portfolio generator: About/Experience/Projects/Skills/Research/Achievements/Contact, rendered as a themable static site with export (§30)
- [ ] Content generator: LinkedIn/X posts, blog posts, project announcements, articles, all grounded and style-adapted (§29); writing-style analysis layer (§8.6)
- [ ] Connectors: Medium and Hashnode (RSS / public GraphQL), personal website/portfolio URL ingestion (respecting robots.txt), LinkedIn **via the user's official data-export ZIP or profile PDF** (LinkedIn has no general-purpose public API), X **via the user's archive import**
- [ ] Inferred preferences with a user-confirmation flow (§8.7)

### Phase 3 (§57)
- [ ] Public persona and "Ask <Name> AI" public page (public-visibility facts only, separate rate-limited endpoint, custom slug)
- [ ] Freelancer proposal generator (§32)
- [ ] Research assistant (ORCID / arXiv / Semantic Scholar imports), meeting preparation
- [ ] Email and calendar integrations: listed but deferred; they need separate OAuth app approval and a scoping decision

### Phase 4 (§58): out of scope for this build
Agentic job search with approval gates. The architecture leaves room for it (action log + explicit-approval model), but it won't be built unless you ask.

---

## 3. Working method
- Work milestone by milestone, in order. Each one ships backend, frontend and tests, and must pass its "Done when" before the next starts.
- Tests: pytest (unit + API against real Postgres in Docker), the Fake LLM provider for deterministic CI, Playwright for the core user journey.
- After each milestone: update this file's checkboxes and commit with a descriptive message.
- No external side effects (deploys, publishing, real emails) without explicit confirmation.

## 4. Inputs needed from the project owner
1. **LLM API key(s)**: Anthropic recommended as default; OpenAI/Gemini optional. Without a key, development continues on the Fake provider + local fastembed, but real extraction quality can't be verified.
2. **Embedding provider**: Voyage/OpenAI key, or accept local `fastembed` (free, slightly lower quality).
3. **GitHub OAuth App** (client ID/secret, callback `http://localhost:3000/api/auth/github/callback`), needed for M1 GitHub login and M4.
4. **Google OAuth client** (for M1 Google login). Can come later; email+GitHub auth work without it.
5. **Docker Desktop running** (Postgres, Redis and Mailpit run in containers).
6. A sample resume + GitHub username for realistic end-to-end testing (optional; synthetic fixtures will be used otherwise).
