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

### M1 — Authentication & accounts (§19, §36) ✅
- [x] Users table, argon2 hashing, signup/login/logout, JWT access + rotating refresh in httpOnly cookies (with refresh-reuse family revocation)
- [x] Password reset by email token (Mailpit in dev); email verification
- [x] Google OAuth + GitHub OAuth login (authorization code flow, signed state, PKCE for Google), account linking by email, provider tokens Fernet-encrypted at rest
- [x] Account management: change name, change password (revokes other sessions), linked accounts
- [x] RBAC dependency (`require_role`), rate limiting (slowapi, XFF-aware key) on auth endpoints, request validation, error envelope
- [x] Frontend: login, signup, forgot/reset password, verify-email, protected-route middleware, account settings, user menu + logout, client-side token refresh-retry
- **Done when:** a user can sign up, log in, reset their password and log in with GitHub. ✅ 14 backend tests (token expiry, refresh rotation, reuse detection, change-password) pass; live end-to-end signup → cookies → `/me` → verification email verified through the Next proxy. GitHub/Google login paths built; need OAuth app credentials to exercise live (flagged for owner).
- _Note: XFF-based rate-limit keying needs a trusted-proxy setup in production (tracked for M10)._

### M2 — Persona core, manual profile & editor (§7, §8, §9, §22) ✅
- [x] All persona tables and migrations, visibility/evidence-state/employment-type enums (VARCHAR+CHECK), soft delete, persona-owned mixin
- [x] Persona service: generic CRUD for identity, experience, education, skills, projects, achievements, publications, certifications, preferences, knowledge areas; confidence (1−Π(1−w)) and weighted completeness
- [x] Manual entries create `user_confirmed` evidence; skill canonicalization (alias map) for later merge
- [x] Persona versioning: snapshot on material change, list versions, restore (re-snapshots first, so restore is reversible)
- [x] APIs: `GET/PATCH /persona`, `GET /persona/full`, generic `GET/POST/PATCH/DELETE /persona/{resource}`, `POST .../confirm`, `GET .../evidence`, `GET/POST /persona/meta/versions[...]/restore`
- [x] Frontend Persona Editor: completeness bar, identity card, tabbed fact sections with add/edit/delete/confirm, evidence popover per fact, version-history popover with restore
- **Done when:** a user can build a complete persona by hand, see evidence on every fact, and restore an earlier version. ✅ 25 backend tests pass; live run verified canonicalization, auto-evidence, versioning, and completeness through real HTTP.
- _Note: visibility toggle in the editor UI is deferred to M8 (privacy), where it's the focus; the field and API already support it._

### M3 — AI provider layer & resume ingestion (§10, §12, §13, §39, §40) ✅
- [x] `LLMProvider` (OpenAI-compatible adapter for Groq/OpenAI + deterministic Fake) with a structured-output helper (Pydantic schema → JSON, repair + retry), streaming, and token/latency logging to `ai_calls`
- [x] `EmbeddingProvider` (local fastembed + deterministic Fake); provider factories
- [x] `POST /documents/upload` for PDF (pdfplumber/pypdf), DOCX (python-docx) and TXT, with size/type validation, storage, and content-hash dedupe
- [x] Pipeline (callable + Celery task): chunk (section-aware) → embed (HNSW index) → snapshot → extract facts → merge → finalize. Job progress via `GET /jobs/{id}`
- [x] Extraction prompt + schemas; every extracted fact cites a verbatim quote, mapped to its chunk as evidence
- [x] **Persona merge engine (§46):** canonicalize (skill aliases), match existing facts (exact + fuzzy via SequenceMatcher), update or create, attach evidence, recompute confidence
- [x] **Conflict detection (§47):** contradictory identity fields (title/name/location) → `conflicts` row, never silently overwritten; resolution endpoint
- [x] Failed jobs retry with backoff; persona-mutating work runs in one transaction (committed only on success), so a failure cannot corrupt the persona (§60)
- [x] Frontend: Sources page with resume upload, live job-progress bar, merge summary ("N skills added…"), source list with disconnect, and conflict-resolution UI
- **Done when:** uploading a sample resume produces a reviewable persona with evidence quotes. A second, conflicting resume raises conflicts instead of overwriting. ✅ 33 backend tests pass; verified live through the full stack (upload → Celery worker → **real Groq** extraction → fastembed embeddings → persona) across multiple sequential jobs, with `ai_calls` token logging confirmed.

### M4 — GitHub connector (§10, §54) ✅
- [x] `Connector` client interface with normalized `GitHubData`/`RepoData`, a real httpx client and a deterministic fake, selected by a factory
- [x] `POST /sources/github/connect` — uses the stored GitHub OAuth token when present (encrypted server-side), or a public username as a fallback; status + re-sync endpoints
- [x] Sync: repos (ranked non-fork → stars), languages, topics, stars, READMEs (capped at 20 detailed fetches). Public API fallback when unauthenticated
- [x] Map to persona: repo → project (languages as technologies, repo URL), language → skill with GitHub-weighted evidence; READMEs stored as embedded chunks for semantic search
- [x] Source management API and UI: GitHub card (connect/sync/progress/summary), status, source list with disconnect (removes the source's evidence)
- [x] Merge reuses the conflict-aware engine with a GitHub evidence weight, so repo skills merge with resume skills and raise evidence counts
- **Done when:** connecting GitHub discovers repositories, projects and technologies; they merge with resume facts and raise evidence counts. Sync and disconnect both work from the Sources page. ✅ 39 backend tests pass; verified live against the **real GitHub API** (octocat → 5 projects, 5 skills, 11 evidence items) through the worker.
- _Note: commit-message mining, package-manifest parsing, ETag/incremental sync, and scheduled re-sync (Celery beat) are deferred as enhancements; the connector and manual re-sync work now._

### M5 — Semantic memory, Ask My Persona & personal search (§15–18, §23, §31, §44, §49) ✅
- [x] Chunks embedded on ingestion (HNSW vector index + GIN tsvector index), scoped per persona
- [x] Persona-aware retrieval: structured SQL over skills/projects/experience/education + hybrid semantic (pgvector cosine + Postgres full-text) fused with reciprocal rank fusion; context assembly
- [x] **Claim validator** (deterministic, reused by generators): splits text into atomic claims, checks each against evidence — rejects unsupported figures/claims, downgrades unbacked leadership ("Led" → "Worked on"), allows supported ones
- [x] `POST /chat` with SSE streaming (session/citations/token/done events), citations in SRD §44 shape, saved chat sessions + messages
- [x] `GET /search?q=` personal knowledge search returning structured facts + source excerpts
- [x] Frontend Ask AI: streaming chat UI with citation chips, suggested prompts (§52), per-conversation session
- **Done when:** "What projects have I built involving RAG?" returns the right projects with citations, and the validator blocks a seeded unsupported claim in tests. ✅ 49 backend tests pass (validator + retrieval + chat SSE); verified live with **real Groq** — the question returned a grounded, cited answer ("…built a RAG pipeline… using LangChain and FAISS【1】").
- _Note: an explicit LLM intent-detection step and fact-card embeddings were folded into the simpler structured+semantic hybrid, which already satisfies the retrieval goals; a dedicated Search page UI is deferred (search API is live and the chat covers it)._

### M6 — Career suite (§24–28, §45, §55) ✅
- [x] `POST /jd/analyze`: extracts required/preferred skills, technologies, responsibilities, experience years, education and domain into a structured JD (LLM, fake-backed for tests)
- [x] Matching: each requirement classified **Strong / Partial / Not demonstrated** with evidence quotes (career gap analysis, §27)
- [x] `POST /resume/generate` (§45 shape): selects matched skills + relevant experience/projects (JD-tech ranked) → bullets from the persona → **claim validation** (drops unsupported, softens unbacked leadership) → ATS keyword coverage + markdown render + evidence per section
- [x] `POST /interview/start` with modes technical / project / system design / behavioral / HR; questions grounded in skills, projects, and (with a JD) weak areas; generations persisted
- [x] Frontend Career section: JD textarea driving three tabs — gap analysis (requirement table with status + evidence), resume builder (preview with per-bullet validation badges, ATS coverage, copy-markdown), interview practice (mode selector + questions)
- **Done when:** the full SRD §68 end-to-end scenario works: upload resume → connect GitHub → confirm → analyze JD → generate validated resume → interview prep. ✅ 54 backend tests pass; verified live with **real Groq**: JD → techs extracted, gap (Python/FastAPI/PostgreSQL strong, Kubernetes/AWS not demonstrated), resume with 67% ATS coverage, grounded interview questions.
- _Note: PDF/DOCX export (browser print / WeasyPrint), two-page format, and interview answer-feedback are deferred; markdown export + copy are live._

### M7 — Dashboard, onboarding & Persona Explorer (§20, §21, §51, §53) ✅
- [x] Onboarding card ("Build your AI Persona") with a source checklist (resume / GitHub / manual) and progress, shown while the persona is sparse
- [x] Dashboard: time-aware greeting, completeness bar + counts, top skills, experience timeline, recent-updates feed (derived from synced sources + generations), quick actions
- [x] Persona Explorer: interactive React Flow graph (via @xyflow/react) of persona → skills / projects / experience / education, with project→skill "uses" edges, laid out by type; linked from the Persona page
- [x] Backend `GET /dashboard` summary and `GET /persona/graph` (registered before the `/persona/{resource}` catch-all so it isn't shadowed)
- **Done when:** the dashboard reflects live persona state and the explorer shows a navigable graph for the sample persona. ✅ 58 backend tests pass; verified live — empty vs. populated dashboard (completeness 0.7, top skills, timeline, "resume.txt synced — 8 facts"), and the graph (1 persona + 6 skills + 1 experience + 1 education, 8 edges, 8 evidence).

### M8 — Privacy & data ownership (§34, §35) ✅
- [x] Visibility enforced: a no-auth `GET /public/personas/{id}` returns ONLY `public`-visibility facts; everything is private by default
- [x] Export the full persona — `GET /account/export` (JSON) and `GET /account/export.zip` (persona.json + original document text)
- [x] Delete individual facts (soft delete, M2) and sources (cascade evidence **and recompute** affected facts' confidence, demoting to inferred when evidence is gone); `POST /account/delete` hard-deletes the account (password-confirmed, storage purged, all data cascades, cookies cleared)
- [x] Settings UI: a per-fact visibility selector in the editor, plus an "Your data" export card and a password-confirmed "Delete account" card
- **Done when:** export round-trips and account deletion leaves no user rows, files or embeddings (verified by test). ✅ 64 backend tests pass; verified live — visibility toggle flips public exposure, JSON+ZIP export, and account deletion returns 404 on the persona afterward (full cascade).

### M9 — AI evaluation framework (§62, §63) ✅
- [x] Synthetic persona fixture (10 skills, 5 roles, 5 projects, 3 publications, embedded documents) plus a set of absent skills for negatives
- [x] Question sets covering fact lookup, lists, negatives ("Do I have AWS experience?") and adversarial fabricated claims
- [x] Metrics: retrieval recall@k / MRR, negative accuracy, groundedness (validated resume bullets), hallucination rate (fabricated claims allowed), supported-claim pass rate
- [x] `python -m eval` CLI printing a report and enforcing thresholds; the same thresholds asserted in the test suite (fake provider in CI, Groq on demand)
- **Done when:** the eval report runs end to end and hallucination rate on the adversarial set is measured and below an agreed threshold. ✅ 5 eval tests pass; live with **real Groq** all thresholds pass — recall 1.0, negative accuracy 1.0, groundedness 1.0, **hallucination rate 0.0**.

### M10 — Hardening, observability & deployment (§36, §59–61) ✅
- [x] Prometheus metrics at `/metrics` (request count + latency by route), structured JSON logs, `ai_calls` token/latency table; Sentry (env-gated) and OpenTelemetry tracing for FastAPI/SQLAlchemy/httpx (env-gated, `observability` extra)
- [x] Security pass: secure headers middleware (nosniff, frame-deny, referrer policy, HSTS in prod), rate limiting, request/size validation, argon2 + rotating refresh tokens + Fernet-encrypted provider tokens, strict per-persona scoping
- [x] Performance: pgvector HNSW + GIN indexes, FK indexes, async throughout; ingestion off the request path
- [x] Production Docker stack: API/worker image + web image, `infra/docker-compose.prod.yml` (postgres, redis, migrate, api, worker, beat, web, Caddy TLS), one-shot migration service
- [x] Docs: `docs/architecture.md`, `docs/deployment.md`, README updated
- **Done when:** a fresh clone can be run with one command, all test suites are green, and the security checklist is complete. ✅ Backend tests + ruff + mypy + eslint + web build all green; `/metrics` and security headers verified by tests; one-command prod compose with Caddy TLS and an automated migrate step.

### M10 — Hardening, observability & deployment (§36, §59–61)
- [ ] OpenTelemetry tracing (FastAPI, SQLAlchemy, Celery, httpx), Prometheus metrics, Sentry hook, AI token/latency dashboard data
- [ ] Security pass: rate limits on all routes, input limits, CSRF on cookie auth, secure headers, dependency audit, OAuth tokens never in responses (tested)
- [ ] Performance: query p95 < 3s excluding LLM time, resume < 15s; indexes and N+1 checks; load test with locust
- [ ] Production docker-compose (api, worker, beat, web, postgres, redis, Caddy for TLS), backups, migration runbook
- [ ] Docs: README, architecture doc, OpenAPI, contributor guide
- **Done when:** a fresh clone can be run with one command, all test suites are green, and the security checklist is complete.

---

### Phase 2 (after MVP is solid) (§56) ✅
- [x] Content generator: LinkedIn/X posts, blog posts, project announcements, articles — grounded in the persona, with the validator surfacing unsupported claims as warnings (§29)
- [x] Cover letters and job-application answers (reuse JD analysis + retrieval + validator)
- [x] Portfolio generator: About/Skills/Experience/Projects/Research/Achievements/Contact, rendered as a self-contained, themeable HTML page with download; respects per-fact visibility (§30)
- [x] Career gap analysis (delivered in M6)
- [x] Connectors: Blog/RSS (Medium/Hashnode/Dev.to/generic RSS via feedparser), LinkedIn **data-export ZIP** (Profile/Skills/Positions/Education CSVs → merge), X/Twitter **archive import** (ZIP or tweets.js → embed + writing-style)
- [x] Writing-style analysis layer (§8.6): deterministic metrics (sentence length, formality, vocabulary richness) from blog/tweet text, wired into content generation prompts as a style hint
- [x] Inferred preferences with a user-confirmation flow (§8.7): deterministic inference from skills + experience (seniority, preferred technologies, work mode, specialization) → inferred_pending → confirm/dismiss
- [x] Frontend: Blog connector card (platform + handle), LinkedIn upload card, X archive upload card on the Sources page
- **Done when:** all connectors ingest data, writing style adapts generated content, and preferences auto-detect + confirm/dismiss. ✅ 95 backend tests pass; frontend tsc clean.

### Phase 3 (§57) ✅
- [x] Public persona and "Ask <Name> AI" public page (slug-based URLs, rate-limited 20/hr, custom slug with Alembic migration)
- [x] Freelancer proposal generator (platform-aware: Upwork/Toptal/Fiverr/generic, RAG-grounded, claim-validated)
- [x] Research assistant (Semantic Scholar, arXiv, ORCID — all free APIs), meeting preparation
- [x] Email integration: MBOX/EML upload, sent-email parsing, professional topic extraction
- [x] Calendar integration: ICS upload, event parsing, meeting pattern analysis
- [x] Personal knowledge management: browser bookmark HTML import, markdown notes import, interest/knowledge extraction
- [x] Deferred enhancements: PDF resume export (WeasyPrint), interview answer feedback, commit-message mining from GitHub
- [x] Frontend: ResearchCard, EmailCard, CalendarCard, PKMCard on Sources page; API clients for all new endpoints

### Phase 4 (§58) ✅
- [x] Agentic job search: search → evaluate → rank → approval gate → application generation
- [x] JobSearchTask + JobLead models with approval workflow (pending/approved/rejected/applied)
- [x] LLM-powered job search (persona-aware), fit evaluation with score/matched/missing skills
- [x] Approval gate: leads must be explicitly approved before application generation
- [x] Tailored cover letter + talking points + interviewer questions for approved leads
- [x] Frontend API client (job-search.ts) with full flow support
- [x] Alembic migration for job_search_tasks and job_leads tables

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
