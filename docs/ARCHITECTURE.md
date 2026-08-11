# Architecture Guide

## Overview

MovieRoulette is split into two fully decoupled applications that communicate
exclusively over a versioned REST API:

- **`backend/`** — FastAPI (async), SQLAlchemy 2.0, PostgreSQL, Redis
- **`frontend/`** — static HTML/CSS/ES6 modules, no build step required

This document covers the **foundation phase** only. It will be extended as
each subsequent phase (backend models/API, frontend UI, features, testing,
DevOps hardening) lands.

## Backend layering

```
Request
  → API layer (app/api)         — HTTP concerns only: parsing, status codes, routing
  → Service layer (app/services) — business logic, framework-agnostic
  → Data layer (app/db, app/models) — persistence
```

Routers never talk to the database directly and services never import
FastAPI types. This means:

- Business logic (e.g. the future roulette engine, recommendation scoring)
  is unit-testable without spinning up HTTP.
- The recommendation system's planned Version 2 (embeddings, vector search)
  can be introduced as a new service implementation behind the same
  interface, without touching routers.

## Configuration

All environment-driven configuration lives in one place:
`app/core/config.py`'s `Settings` (Pydantic Settings). The app fails fast at
startup if required values are missing or invalid — misconfiguration is a
boot-time error, not a runtime surprise.

## Database access

- **Async engine** (`asyncpg`) for the running application — see
  `app/db/session.py`. Async matters because request handlers will
  eventually fan out to multiple I/O-bound calls per request (DB + Redis +
  future vector search), and async lets one worker serve many concurrent
  requests during that I/O wait.
- **Sync engine** (`psycopg2`) used only by Alembic, since its migration
  runner is synchronous.
- **Naming conventions** for all constraints (`app/db/base.py`) so
  `alembic revision --autogenerate` produces stable, greppable migration
  names instead of database-generated hashes.
- **Polymorphic `Title` hierarchy** — see `docs/DATABASE.md` for the full
  reasoning and the important caveat about querying the concrete subclass
  (`Movie`/`TVShow`) rather than the base `Title` when subtype-specific
  columns are needed.

## Service layer patterns (backend phase)

- **Services return ORM objects or raise typed exceptions** (e.g.
  `TitleNotFoundError`, `CollectionNotFoundError`), never HTTP-flavored
  errors — the API layer is solely responsible for translating those into
  status codes. This is what keeps services callable from anywhere (a future
  background job, a CLI script, another service) without an HTTP context.
- **Idempotent writes use PUT, not POST** (favoriting, watch-later, adding a
  collection item) — favoriting an already-favorited title is a no-op, not
  an error, matching PUT's semantics and sparing the frontend from needing
  to track "is this already favorited" before every request.
- **Ownership checks live in the service, not the router** — every
  collection mutation resolves "does this belong to this user" as the first
  step, and returns a 404 (not 403) for both "doesn't exist" and "exists but
  isn't yours," so a collection ID's mere existence is never leaked to a
  user who doesn't own it.
- **The roulette engine** (`app/services/roulette_service.py`) is
  deliberately factored so its V1 implementation (filter → bounded candidate
  pool → popularity-weighted random pick) can be replaced by a smarter
  ranking function later without touching filter-building or spin-logging —
  see the module's docstring for the full reasoning.

## Testing approach

Tests run against an in-memory SQLite database via `StaticPool`, with a
fresh `AsyncSession` created per simulated HTTP request (mirroring
production's per-request session lifecycle in `get_db`) rather than one
session reused for a whole test. This distinction caught a real bug during
development: a stale SQLAlchemy identity-map cache that a single
shared-session test fixture would have masked. See `tests/conftest.py`.

## Caching

`app/core/cache.py` wraps a shared Redis connection pool with a minimal
JSON get/set/delete helper. Wired in during the foundation phase, before any
feature needs it, so future caching (trending lists, search results, roulette
session state) has one consistent client to depend on instead of ad hoc
Redis connections scattered across services.

## Security

- Passwords are hashed with bcrypt via `passlib` (`app/core/security.py`),
  never stored in plaintext.
- JWTs carry an explicit `type` claim (`access` vs `refresh`) so a leaked
  refresh token cannot be replayed as an access token.
- CORS uses an explicit origin allow-list, not `*`, since the frontend is a
  separately-hosted static app.
- Rate limiting (`app/middleware/rate_limit.py`) is Redis-backed rather than
  in-process, so the limit means the same thing regardless of how many
  worker processes or app instances are running — and fails *open* (allows
  requests) if Redis becomes unreachable, so a caching outage never takes
  down the whole API.

## Observability

Structured logging is configured once at startup (`app/core/logging.py`).
`/api/v1/health` and `/api/v1/health/ready` give an orchestrator a clean way
to distinguish "process is alive" from "process can serve traffic" — the
readiness check actually touches Postgres and Redis.

## What's intentionally NOT built yet

The foundation phase is complete. As of the **backend phase**, the following
are also done: database schema, ORM models, Alembic migrations, JWT auth,
and the core CRUD/browse API (movies, TV shows, genres, favorites,
watch-later, ratings, viewing history, collections, and a working V1
roulette engine). See `docs/DATABASE.md` for schema details.

Still ahead, in later phases:

- Real frontend UI components (the current `index.html` only proves
  frontend↔backend connectivity)
- Cast/crew/person detail pages and streaming-availability data ingestion
  (the schema supports these; no data source is wired up yet)
- The Version 2 recommendation system (collaborative filtering, embeddings,
  semantic search) — the roulette engine is architected so this replaces
  one function (`roulette_service._select_candidate`) without touching
  filtering or spin-logging
- Full test coverage of edge cases beyond the current feature-level suite
- Deployment hardening, observability beyond basic health checks, and a
  populated content catalog (current seed data is minimal, for dev only)
