# PersonaAI — Deployment

The production stack runs entirely in Docker: Postgres (pgvector), Redis, the
FastAPI API, a Celery worker and beat scheduler, the Next.js web app, and Caddy
for automatic HTTPS. Only Caddy is exposed to the internet.

## Prerequisites

- A host with Docker + Docker Compose.
- A domain pointed at the host (for real TLS), or `localhost` for local testing.
- A Groq API key (or another configured LLM provider).
- A GitHub OAuth app whose callback is
  `https://YOUR_DOMAIN/api/backend/auth/github/callback`.

## Configure

```bash
cp .env.example .env
```

Set at least these in `.env`:

| Variable | Notes |
|---|---|
| `DOMAIN` | your hostname, e.g. `personaai.example.com` (or `localhost`) |
| `POSTGRES_PASSWORD` | strong password |
| `JWT_SECRET` | `python -c "import secrets;print(secrets.token_urlsafe(64))"` |
| `ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"` |
| `CORS_ORIGINS` | `https://YOUR_DOMAIN` |
| `GROQ_API_KEY` | your key |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` / `GITHUB_REDIRECT_URI` | from the OAuth app |
| `SENTRY_DSN`, `OTEL_EXPORTER_OTLP_ENDPOINT` | optional |

## Launch

```bash
docker compose -f infra/docker-compose.prod.yml --env-file .env up -d --build
```

Startup order is handled for you: the `migrate` service runs `alembic upgrade
head` and must complete before `api` and `worker` start. Caddy obtains a TLS
certificate automatically on first request (real domain only).

## Operations

- **Migrations**: shipped in the image. On deploy, the one-shot `migrate`
  service applies them. To run manually:
  `docker compose -f infra/docker-compose.prod.yml run --rm migrate`.
- **Logs**: `docker compose -f infra/docker-compose.prod.yml logs -f api worker`.
- **Metrics**: the API exposes Prometheus metrics at `/metrics` (scrape it from
  inside the network; it is not routed through Caddy).
- **Health**: `GET /health` (liveness) and `/health/ready` (DB readiness).
- **Backups**: snapshot the `pgdata` volume and the `uploads` volume regularly,
  e.g. `docker compose ... exec postgres pg_dump -U persona persona > backup.sql`.
- **Scaling**: the API and worker are stateless (uploads live on a shared
  volume; move to S3 via the storage interface for multi-host). Scale with
  `--scale api=3 --scale worker=4` behind Caddy.

## Rollback

Images are tagged by your CI. To roll back, redeploy the previous image tags.
Database migrations are additive; if a release must be reverted across a schema
change, run `alembic downgrade <rev>` via the `migrate` service before switching
images. Persona versions are recoverable in-app, independent of deploys.

## Tracing (optional)

OpenTelemetry activates only when `OTEL_EXPORTER_OTLP_ENDPOINT` is set. The
instrumentation packages are in the image (installed via the `observability`
extra), so pointing the env var at a collector is all that's needed.
