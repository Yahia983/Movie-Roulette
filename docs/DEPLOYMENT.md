# Deployment Guide

## Overview

MovieRoulette deploys as three independent pieces: the FastAPI backend, the
static frontend (served by nginx), and PostgreSQL + Redis. `docker-compose.yml`
wires all four together for a single-host deployment; a multi-host/cloud
deployment runs the same images behind your own orchestration (ECS, Cloud
Run, Kubernetes, etc.) — nothing in this app assumes docker-compose
specifically.

## Before deploying

### Required environment variables

Copy `backend/.env.example` to `backend/.env` (or set these as real
environment variables / secrets in your platform — never commit `.env`)
and set, at minimum:

| Variable | Why it matters in production |
|----------|-------------------------------|
| `SECRET_KEY` | JWT signing key. **The app refuses to start in production with the default dev value** (see `app/core/config.py`) — generate one with `python -c "import secrets; print(secrets.token_urlsafe(64))"`. |
| `ENVIRONMENT` | Set to `production`. Enables the `SECRET_KEY` check above and disables debug-level logging noise. |
| `DATABASE_URL` / `DATABASE_URL_SYNC` | Point at your real Postgres instance. The async URL (`postgresql+asyncpg://...`) is used by the running app; the sync URL (`postgresql+psycopg2://...`) is used only by Alembic migrations. |
| `REDIS_URL` | Point at your real Redis instance. Used for rate limiting and future caching — see `docs/ARCHITECTURE.md`. Rate limiting fails *open* if Redis is unreachable, so a Redis outage degrades protection rather than taking the API down, but don't rely on that for normal operation. |
| `CORS_ALLOWED_ORIGINS` | Set to your real frontend origin(s). Never use `*` — the frontend is a separately-hosted static app, and an open CORS policy here would let any site make authenticated requests on a logged-in user's behalf. |
| `TMDB_API_KEY` | Only needed if you're running `scripts/sync_tmdb.py` to populate the catalog — see `docs/FEATURES.md`. |

### Database migrations

Run migrations as a deploy step, before the new app version starts
receiving traffic:

```bash
cd backend
alembic upgrade head
```

This is intentionally a manual/scripted step, not something the app runs
automatically on startup — an app instance auto-migrating on boot is a
common source of race conditions when multiple instances start
simultaneously (each trying to run the same migration at once). Run it
once, from your deploy pipeline, before rolling out new app instances.

## Deploying with Docker Compose (single host)

```bash
cp backend/.env.example backend/.env
# edit backend/.env with real production values (see table above)

docker compose up --build -d

# Run migrations once the postgres service is healthy:
docker compose exec backend alembic upgrade head
```

Put a TLS-terminating reverse proxy (Caddy, another nginx instance, your
cloud provider's load balancer) in front of this on a real domain — the
`frontend` service's nginx (see `frontend/nginx.conf`) serves plain HTTP
and proxies `/api/v1/*` to the backend container; it does not terminate
TLS itself.

## Deploying backend and frontend as separate services (recommended for scale)

The backend and frontend are fully decoupled (see `docs/ARCHITECTURE.md`)
and don't need to live on the same host or even the same platform:

- **Backend**: deploy `backend/Dockerfile`'s image anywhere that runs
  containers and can reach your Postgres/Redis instances. It's stateless
  (all state lives in Postgres/Redis), so it horizontally scales by adding
  instances behind a load balancer with no special session affinity needed.
- **Frontend**: since it's fully static with no build step (see
  `docs/FRONTEND.md`), the `frontend/` directory can be served by *any*
  static host — a CDN, S3+CloudFront, Netlify, Vercel, GitHub Pages,
  whatever you already use. If not using `frontend/nginx.conf`'s reverse
  proxy, set `CORS_ALLOWED_ORIGINS` on the backend to the frontend's real
  domain, and the frontend's `js/api.js` will call the backend's public URL
  directly cross-origin (its same-origin `/api/v1` fallback is specifically
  for the case where a reverse proxy like `frontend/nginx.conf` is in
  front of it — see that file's comments).

## Health checks

- `GET /api/v1/health` — liveness only, no dependencies checked. Use for
  "is the process up" checks (e.g. a container orchestrator's liveness
  probe).
- `GET /api/v1/health/ready` — readiness: actually pings Postgres and
  Redis. Use for "should this instance receive traffic" checks (readiness
  probes, load balancer health checks).
- `GET /healthz` on the frontend's nginx — trivial liveness check for the
  static file server.

## Populating the catalog

A fresh deployment has an empty catalog until you either run the dev seed
script (`python scripts/seed_dev_data.py` — two placeholder titles, for
demos only) or a real TMDB sync (`python scripts/sync_tmdb.py --media-type
movie --pages N` — see `docs/FEATURES.md`). Neither runs automatically;
both are deliberate, explicit steps.

## What's NOT included yet

This guide covers getting the current codebase running in production. It
does not cover (and a real launch would need to add): TLS certificate
provisioning/renewal, a CDN in front of the frontend, structured log
aggregation beyond the app's stdout logging (see `app/core/logging.py`),
metrics/tracing, secrets management beyond environment variables (e.g. a
real secrets manager), database backup/restore procedures, or a blue-green
or canary rollout strategy.
