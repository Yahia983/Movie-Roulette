# Database Guide

## Why joined-table inheritance for `Title`

Movies and TV shows share the large majority of their fields — name,
artwork, synopsis, genres, cast, ratings, popularity — and nearly every
cross-cutting feature (favorites, collections, search, the roulette engine)
needs to operate on "a piece of watchable media" without caring which kind
it is. A single `titles` table carries all shared fields; `movies` and
`tv_shows` each hold only their genuinely type-specific columns, joined 1:1
back to their `titles` row via a shared primary key.

**Practical implication for querying:** SQLAlchemy does *not* automatically
join the subtype table when you query the base `Title` class — accessing
`movie.runtime_minutes` on a row loaded via `select(Title)` triggers a
second, lazy query, which fails under the app's async session outside a
fresh `await`. Any code that needs subtype-specific columns must query the
concrete class directly: `select(Movie)` / `select(TVShow)`, or use
`db.get(Movie, id)`. See `title_service.get_title_by_slug`, which accepts an
explicit `model` parameter for exactly this reason.

## Schema overview

```
titles ── movies          (1:1, joined-table inheritance)
       └─ tv_shows        (1:1, joined-table inheritance)

titles ─┬─ title_genres ─── genres          (many-to-many)
        ├─ credits ──────── people          (many-to-many, with per-row metadata)
        └─ title_availability ── streaming_services

users ─┬─ favorites ──────────── titles     (composite PK, idempotent add)
       ├─ watch_later_items ──── titles     (composite PK, idempotent add)
       ├─ ratings ─────────────  titles     (composite PK, one rating per user/title)
       ├─ viewing_history ────── titles     (own PK — repeat views are separate rows)
       ├─ collections ─┬─ collection_items ── titles
       │                (user-owned; items carry position + added_at)
       └─ roulette_spins ──────  titles     (nullable user_id — anonymous spins allowed)
```

## Key design decisions

- **Composite primary keys for favorites/watch-later/ratings**
  (`user_id, title_id`), rather than a surrogate `id` — the relationship
  itself *is* the identity (a user either has favorited a title or hasn't),
  and the composite key makes "favorite this twice" naturally idempotent at
  the database level, not just in application logic.

- **Viewing history is NOT a composite-key table** — a user can view the
  same title many times, and each view is a distinct event, useful both for
  "recently viewed" and as a future recommendation signal.

- **`Title.popularity`/`vote_average`/`vote_count`** are aggregate stats from
  an external catalog (kept refreshable by a future sync job); **`ratings`**
  holds MovieRoulette's own users' scores. Keeping these separate means
  syncing external data can never clobber user-generated content.

- **`RouletteSpin.filters` is a JSON column**, not a normalized set of filter
  columns — the filter vocabulary is expected to grow (per the roadmap's
  Version 2 recommendation work), and JSON avoids a schema migration every
  time a new filter is added, at the cost of not being indexable/queryable
  by individual filter values. If filter analytics become a real need, that
  trade-off should be revisited.

- **Naming conventions** (`app/db/base.py`) ensure every constraint Alembic
  autogenerates has a deterministic, greppable name (e.g.
  `uq_favorites_user_id`) instead of a database-generated hash.

## Working with migrations

```bash
# After changing a model:
alembic revision --autogenerate -m "describe the change"

# Review the generated file before applying — autogenerate is a strong
# starting point, not a guarantee (it won't detect every kind of change,
# e.g. some check constraint modifications).
alembic upgrade head

# Roll back one revision:
alembic downgrade -1
```

New model modules must be imported in `app/models/__init__.py` or Alembic's
autogenerate will not see them (see that file's docstring for why).
