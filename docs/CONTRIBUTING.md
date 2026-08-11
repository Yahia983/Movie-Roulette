# Contributing Guide

## Getting set up

See the root [`README.md`](../README.md)'s "Getting started" sections for
backend and frontend setup. In short:

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pre-commit install
cp .env.example .env  # point DATABASE_URL/DATABASE_URL_SYNC at sqlite for local dev
alembic upgrade head
python scripts/seed_dev_data.py
uvicorn app.main:app --reload

# Frontend (separate terminal)
cd frontend
python -m http.server 3000
```

## Project structure

Each major phase of this project has its own doc explaining what's there
and why:

- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — overall backend layering,
  config, security, caching
- [`docs/DATABASE.md`](DATABASE.md) — schema design, the `Title`
  polymorphic hierarchy, migration workflow
- [`docs/FRONTEND.md`](FRONTEND.md) — frontend structure and conventions
- [`docs/FEATURES.md`](FEATURES.md) — the TMDB ingestion pipeline and
  recommendation engine
- [`docs/DEVOPS.md`](DEVOPS.md) — testing tiers, CI, and the
  performance/accessibility tooling

Read the relevant one before making a non-trivial change in that area —
several design decisions (e.g. why relationships get re-queried instead of
refreshed, why the roulette engine doesn't use real-time randomization)
aren't obvious from the code alone.

## Before opening a PR

```bash
# Backend
cd backend
black --check .
ruff check .
mypy app
pytest                    # fast suite (SQLite-backed)
pytest -m postgres        # optional locally; mandatory in CI — needs a running Postgres

# e2e (needs both dev servers running — see e2e/README.md)
cd e2e
pytest

# Performance (needs both dev servers running — see e2e/lighthouse/README.md)
cd e2e/lighthouse
node run-audit.js http://localhost:3000/index.html
```

`pre-commit install` (once, after cloning) runs formatting/linting/type
checks automatically on every commit, so most of the above happens without
manual invocation — but run the full suite yourself before opening a PR
regardless, since pre-commit doesn't run the test suite (deliberately —
tests are slower than a commit hook should block on) or the e2e/performance
suites.

## Code style

- **Backend**: Black + Ruff (see `backend/pyproject.toml` for the exact
  rule set) and Mypy strict mode. If Mypy flags something that seems like
  a false positive, prefer a targeted fix (an explicit type annotation, a
  narrow `cast()`) over a blanket `# type: ignore` — see
  `app/services/ingestion_service.py`'s `isinstance`-based narrowing for an
  example of preferring the former.
- **Frontend**: no framework, no build step, no bundler — this is
  deliberate (see `docs/FRONTEND.md`). New pages follow the existing
  pattern: a plain HTML file including the shared stylesheets, a
  corresponding `js/pages/*.js` file with an `init()` function, and
  `renderChrome()` called first for the shared nav/footer.
- **Comments**: explain *why*, not *what* — the codebase leans heavily on
  this throughout (see any existing module for the expected style). A
  comment that just restates the code it's attached to isn't pulling its
  weight; a comment explaining a non-obvious tradeoff or a bug it's
  guarding against is.

## Writing tests

- **New backend logic** (a service function, an endpoint): add a test in
  `backend/tests/`. Prefer testing the service layer directly over only
  testing through the API when the logic is non-trivial — it's faster and
  pinpoints failures better.
- **New Postgres-specific behavior** (a cascade, a constraint): add a test
  in `backend/tests/postgres/` — the default SQLite-backed suite will not
  catch a missing `ON DELETE CASCADE` or constraint violation, since
  SQLite doesn't enforce foreign keys by default in this codebase's
  configuration. See `docs/TROUBLESHOOTING.md` for a worked example of a
  bug this exact gap could hide.
- **New frontend pages/flows**: add a test in `e2e/test_user_flows.py`
  (or `test_smoke.py` for a simple "loads cleanly" check). If the page
  should be scanned for accessibility issues (it should, unless it's
  trivial), add it to `PAGES_TO_SCAN` in `e2e/test_accessibility.py`.

## Database migrations

```bash
cd backend
# after changing a model:
alembic revision --autogenerate -m "describe the change"
# review the generated file — autogenerate is a strong starting point,
# not a guarantee (see docs/DATABASE.md)
alembic upgrade head
```

If the migration adds a constraint to an existing table, use
`op.batch_alter_table(...)` — see `docs/TROUBLESHOOTING.md`'s first entry
for why plain `op.add_column`/`op.create_unique_constraint` breaks on
SQLite.

New model modules must be imported in `app/models/__init__.py` or Alembic's
autogenerate won't see them.

## Commit messages

No enforced format, but a commit message should make it possible to
understand *why* a change was made without opening the diff — "fix bug" is
not useful; "fix stale relationship cache after db.add_all bypasses parent
collection" is.
