# DevOps Guide

This phase added the testing and infrastructure layers the earlier phases
deliberately deferred: a real-Postgres test tier, a genuine end-to-end
browser test suite (replacing the ad-hoc interactive scripts used during
frontend/features development), automated accessibility scanning,
real Lighthouse performance audits, and production-hardening for the
frontend's nginx config.

## Testing tiers

There are now three distinct test tiers, each catching a different class of
bug, deliberately kept separate rather than merged into one suite:

| Tier | Location | What it catches | Speed |
|------|----------|------------------|-------|
| Unit/integration (SQLite) | `backend/tests/` | Application logic, API contracts, service behavior | Fast (~20s) |
| Postgres integration | `backend/tests/postgres/` | FK cascade enforcement, real constraint violations — things SQLite doesn't enforce by default | Slower, needs Postgres |
| End-to-end (browser) | `e2e/` | Frontend↔backend integration, real user flows, accessibility | Slowest, needs both servers + a browser |

### Why the Postgres tier is separate from the main suite

The main suite runs against in-memory SQLite for speed and zero external
dependencies (see `backend/tests/conftest.py`). But SQLite does not
enforce foreign key constraints unless `PRAGMA foreign_keys=ON` is
explicitly set (this codebase doesn't set it), which means the main suite
could pass with a broken `ON DELETE CASCADE`, a missing unique constraint,
or a violated check constraint, and never notice. `backend/tests/postgres/`
runs the actual Alembic migration chain against real PostgreSQL and
specifically tests cascade deletes and constraint violations — see its
module docstring and `docs/TROUBLESHOOTING.md` for the reasoning.

This tier is marked with `@pytest.mark.postgres` and excluded from the
default `pytest` run (`addopts` in `pyproject.toml` sets `-m "not
postgres"`), so a contributor without a local Postgres instance isn't
blocked. It runs as its own required CI job
(`.github/workflows/backend-ci.yml`'s `postgres-integration-test`) against
a real `postgres:` service container, so it's never actually skippable for
a merged PR.

### Why the e2e suite is a separate top-level directory, not under `backend/tests` or `frontend/`

It exercises both halves of the stack together and has a fundamentally
different execution model — it needs two real running servers and a real
browser, not just Python. Putting it under either `backend/` or
`frontend/` would misleadingly suggest it's scoped to one side.

It converts what were ad-hoc, interactively-run Playwright scripts (used
throughout frontend/features development to catch real bugs — see
`docs/FRONTEND.md` and `docs/FEATURES.md` for several caught this way) into
a proper, repeatable `pytest-playwright` suite that runs in CI on every
push.

## Accessibility testing

`e2e/test_accessibility.py` runs `axe-core` (via `axe-playwright-python`,
which bundles the JS locally — no CDN fetch, works with no external
network access) against every major page, failing on any `serious` or
`critical` impact violation. This is automated coverage toward the
project spec's WCAG 2.2 AA requirement — it catches a real, meaningful
subset of issues (missing labels, contrast, ARIA misuse, landmark
structure) but is explicitly not a substitute for manual keyboard-only
navigation and screen-reader testing (see `e2e/README.md`).

Current state: zero serious/critical violations across all scanned pages,
verified by running the suite directly against the live app during this
phase (not just written and assumed to pass).

## Performance testing

`e2e/lighthouse/run-audit.js` runs a real Lighthouse audit (not a
simulated/estimated score) against a running page, using a
Playwright-installed Chromium binary via `chrome-launcher`. Real,
un-throttled scores measured during this phase:

| Page | Performance | Accessibility | Best Practices | SEO |
|------|------------:|---------------:|----------------:|----:|
| Home | 96 | 100 | 96 | 100 |
| Browse | 93 | 100 | 96 | 90 |
| Title detail | 94 | 100 | 96 | 90 |
| Roulette | 86 | 100 | 96 | 90 |

These are close to the spec's 95+ target across the board, with roulette
trailing on performance due to a Cumulative Layout Shift that's harder to
fully eliminate (see below). CI enforces lower floors than the target
(80/90) specifically because headless, CPU-throttled CI runners are
measurably slower and less consistent than a real machine — see
`e2e/lighthouse/README.md` for the full reasoning.

### A real bug this caught: unreserved layout space causing high CLS

The home page's initial Lighthouse run scored performance 76/100 with a
Cumulative Layout Shift of 0.756 — far above a healthy score. The cause:
every content rail (`rail__track`) and browse grid (`title-grid`) is an
empty `<div>` at first paint (real content loads asynchronously after an
API call), so the page jumps from "mostly empty" to "fully populated" in
one large shift once data arrives. The fix — reserving space via
`min-height` sized to roughly match a populated row — brought the home
page to 96/100 and CLS down to 0.109, a real, measured improvement, not a
guess. The same pattern was then found and fixed on the roulette page's
filter chips and genre checkboxes. See `frontend/css/layout.css` and
`frontend/css/roulette.css` for the fixes, and `e2e/lighthouse/README.md`
for the specific before/after numbers and a documented follow-up (the
roulette page's CLS is improved but not fully eliminated).

## Production hardening: the frontend's nginx config

`frontend/nginx.conf` replaces nginx's stock static-file-only config with
one that actually supports a real deployment:

- **API proxying** (`/api/v1/` → the backend container). This closes a
  real gap found during this phase: `js/api.js` calls same-origin
  `/api/v1` whenever the page isn't served from `localhost`, but the
  previous `docker-compose.yml` mounted the frontend directory into stock
  nginx with no proxy configuration at all — every API call would have
  404'd in any real (non-localhost) deployment. This only "worked" in
  local dev because both services happened to be separately reachable at
  `localhost` either way, which masked the gap.
- **Security headers** (`X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `Permissions-Policy`).
- **Gzip compression** for text assets.
- **Cache-Control** on static assets — deliberately short + revalidated
  rather than long-lived/immutable, since this project has no build step
  and therefore no content-hashed filenames to bust a long cache on
  deploy (see the config file's comments for the full reasoning, and the
  real bug this itself caught: combining nginx's `expires` directive with
  an explicit `add_header Cache-Control` produces two separate
  `Cache-Control` headers in the same response — confirmed via a live
  test — fixed by using only the explicit header).

This config was validated with `nginx -t` and tested live (not just
written and assumed correct) — see `docs/TROUBLESHOOTING.md` for how to
reproduce that validation.

## CI structure

Four workflows, each independently triggerable and each covering a
distinct concern:

- **`backend-ci.yml`** — lint/format/type-check, the fast SQLite test
  suite, and the Postgres integration tier (as a separate job with its own
  `postgres:` service container).
- **`e2e-ci.yml`** — the end-to-end browser suite (`e2e/`) and the
  Lighthouse performance audits, both against real running dev servers
  spun up within the job.

Splitting Postgres integration and e2e/performance into their own jobs
(rather than steps within one big job) means a failure in one is
immediately attributable in the Actions UI, and jobs that don't depend on
each other run in parallel rather than serially.

## Known limitations going forward

- **No content-hashed static assets.** Without a build step, cache-busting
  on deploy relies on nginx's short `Cache-Control` + `must-revalidate`
  rather than truly immutable long-lived caching. A future build step
  (even a minimal one, just for hashing filenames) would improve this.
- **The roulette page's CLS is improved but not fully eliminated** — see
  `e2e/lighthouse/README.md`'s "Known follow-up" section.
- **No load/stress testing yet.** The performance testing here covers
  page-load metrics (Lighthouse), not concurrent-user throughput or
  database performance under load.
- **No structured logging/tracing/metrics beyond stdout logs and the two
  health-check endpoints** — see `docs/DEPLOYMENT.md`'s "What's NOT
  included yet" section.
