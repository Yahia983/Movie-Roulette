# Troubleshooting Guide

Issues below are grouped by symptom. Several are things that were actually
hit and fixed during this project's development (noted where relevant) —
included here because they're exactly the kind of issue a new contributor
is likely to re-encounter.

## Backend

### `alembic upgrade head` fails with "No support for ALTER of constraints in SQLite dialect"

SQLite can't `ALTER TABLE ... ADD CONSTRAINT` directly. Any migration that
adds a constraint (unique, foreign key, check) to an *existing* table must
use `op.batch_alter_table(...)` instead of bare `op.add_column`/
`op.create_unique_constraint`. See
`backend/alembic/versions/e0b31a9ca46b_*.py` for a worked example — this
exact error was hit and fixed while adding the `tmdb_id` columns.

### `MissingGreenlet` / "greenlet_spawn has not been called" errors

This means something tried to lazily load a relationship or column
outside of an `await`, which the async SQLAlchemy engine can't do
implicitly. Three specific causes of this were found and fixed in this
codebase (see `docs/FEATURES.md`'s "subtle async SQLAlchemy bug class"
section for the full writeup):

1. Calling `db.refresh(obj)` — this expires relationship attributes
   regardless of `expire_on_commit`. Use a fresh `select()` instead.
2. Assigning into a relationship collection on a just-flushed, never-queried
   object (e.g. `new_row.genres = [...]` right after `db.add(new_row)`).
   Re-query the object via `select()` first so its `lazy="selectin"`
   relationships actually load.
3. Adding child rows via `db.add_all(rows)` where each row's foreign key
   points at a parent, instead of assigning through the parent's
   relationship attribute (`parent.children = rows`). The former leaves
   the parent's in-memory collection silently stale for the rest of the
   session.

If you hit a new instance of this error, the fix is almost always one of
the three patterns above — find where a relationship is touched without
having gone through a `select()` first.

### `bcrypt`/passlib errors on password hashing (`AttributeError: module 'bcrypt' has no attribute '__about__'`)

`passlib` (the library this project used to use for password hashing) is
unmaintained and breaks on `bcrypt` >= 4.1's changed internals. This
project now calls `bcrypt` directly (`app/core/security.py`) instead of
through passlib — if you see this error, something is depending on
`passlib` again; remove it.

### Tests fail with `UNIQUE constraint failed` on a table you didn't touch, only on the *second* call to a function in the same test

This is usually the same root cause as the `MissingGreenlet` class above,
manifesting differently: a parent's relationship collection is stale in
memory (still showing the *old* child rows), so re-syncing/re-saving
inserts a new child row that collides with the still-present old one. See
`docs/FEATURES.md` for the specific `db.add_all()` case that caused this
during ingestion-service development.

### `pytest` can't find Postgres / all `tests/postgres/` tests are skipped

That's expected without a running Postgres instance — this tier is
opt-in for local development (see `tests/postgres/conftest.py`). To run
it: start a local Postgres (`docker run -p 5432:5432 -e
POSTGRES_PASSWORD=postgres postgres:16-alpine`, or a system install), then
`pytest -m postgres`. It's mandatory (not skippable) in its own CI job —
see `.github/workflows/backend-ci.yml`'s `postgres-integration-test` job.

### Password/email validation errors that don't match what you typed

If you're testing via a script/CLI and a submitted email or similar
literal-looking string comes through mangled or missing characters,
check whatever's generating or logging that string for any text-scrubbing
step in your own tooling (e.g. a shell wrapper, logging pipeline, or
transcript-recording layer) — this isn't an app bug; the app receives and
validates exactly the bytes it's sent.

## Frontend

### An element with the `hidden` attribute is still visible

Check whether any CSS rule sets `display` on that element or its tag (e.g.
`img { display: block }`). Per the CSS cascade, **any author-origin style
always overrides a user-agent style, regardless of specificity** — so
`[hidden] { display: none }` (a UA-stylesheet rule) loses to `img {
display: block }` (an author rule) even though `[hidden]`'s specificity is
technically higher. `frontend/css/base.css` has a global
`[hidden] { display: none !important; }` rule specifically to prevent
this — if you're seeing this bug, something is likely overriding that with
its own `!important`, or the element in question isn't covered by that
global rule for some other reason.

### A grid layout looks scrambled — content that should be side-by-side lands in a wrong column

Check that the number of *direct children* of the grid container matches
the number of columns you expect. CSS grid auto-placement fills columns
left-to-right, top-to-bottom, wrapping extra children into new rows — a
stray extra child (e.g. two elements that should visually stack but
aren't wrapped in one container) throws off every subsequent element's
position. See `docs/FRONTEND.md`'s writeup of the title-detail page's
poster/fallback bug for a concrete example.

### `console.error` messages about the Google Fonts CDN (403 or `net::ERR_FAILED`)

Harmless in any network-restricted environment without access to
`fonts.googleapis.com`/`fonts.gstatic.com` — the app falls back to system
fonts and functions identically. The e2e test suite blocks these requests
proactively (`e2e/conftest.py`'s `block_external_fonts` fixture) so they
don't produce console noise in CI; if you're debugging manually, they're
safe to ignore.

### A page's Cumulative Layout Shift score looks bad in Lighthouse

Almost always caused by a container that's empty (zero height) at first
paint and then jumps to full height once JS populates it via a fetch. Fix:
reserve space with `min-height` on that container, sized to roughly match
its populated content. See `frontend/css/layout.css`'s `.rail__track` and
`.title-grid` rules for the pattern, and `e2e/lighthouse/README.md` for
the before/after scores this fixed.

## DevOps / CI

### CI's `postgres-integration-test` job passes locally but fails in CI (or vice versa)

Check `POSTGRES_TEST_URL` — CI sets it via the `postgres` service
container's hostname (`localhost` inside the job's network, per the
`services:` block in `.github/workflows/backend-ci.yml`); locally it
defaults to `localhost:5432` with `postgres`/`postgres` credentials (see
`tests/postgres/conftest.py`). Mismatched credentials or a different local
Postgres setup are the most common cause of local-only failures here.

### A Docker Compose deployment's frontend can't reach the API (works with `docker compose up` locally on `localhost` but not on a real domain)

See `docs/DEPLOYMENT.md`'s "Deploying with Docker Compose" section — this
requires `frontend/nginx.conf`'s `/api/v1/` proxy block to actually be
mounted (check the `frontend` service's volumes in `docker-compose.yml`).
This exact gap (nginx serving static files with no proxy_pass configured
at all) was caught and fixed during the DevOps hardening pass — a
docker-compose deployment previously "worked" only in local dev because
both services were separately reachable at `localhost` either way, masking
the missing proxy.

## Still stuck?

Check the phase-specific docs for more context on *why* something is built
the way it is, which often clarifies whether unexpected behavior is a bug
or by design: `docs/ARCHITECTURE.md`, `docs/DATABASE.md`,
`docs/FRONTEND.md`, `docs/FEATURES.md`, `docs/DEVOPS.md`.
