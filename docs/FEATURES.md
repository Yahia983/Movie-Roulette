# Features Guide

This phase added two things: a real-catalog ingestion pipeline (TMDB) and
Version 2 of the recommendation system per the original spec's roadmap.

## TMDB ingestion pipeline

### Why the client and the ingestion logic are separate modules

`app/services/tmdb_client.py` knows *how to talk to TMDB* — auth, endpoints,
pagination, rate-limit backoff — and nothing about what to do with the
response. `app/services/ingestion_service.py` knows *how to turn a TMDB
response into database rows* — upserts, slug collision handling, status
mapping — and never makes an HTTP call itself.

This split is why the ingestion logic has full test coverage
(`tests/test_ingestion_service.py`) in an environment with no access to the
real TMDB API: the tests feed it realistic TMDB-shaped Python dicts
directly. The client has its own separate tests
(`tests/test_tmdb_client.py`) using `httpx.MockTransport`, which exercises
the actual retry/backoff/error-mapping code paths without any real network
access either.

### Idempotency

Every sync is safe to re-run. `Title`, `Person`, and `Genre` all carry a
nullable, unique `tmdb_id` column (see `docs/DATABASE.md` for the migration
details) — `upsert_title` looks up by `tmdb_id` first and updates in place
if found, so running the same sync twice never creates duplicates. Credits
and streaming availability are fully replaced (not merged) on each re-sync,
so removals on the TMDB side (a corrected cast list, a dropped streaming
deal) are reflected too, not just additions.

### Running a sync

```bash
python scripts/sync_tmdb.py --media-type movie --pages 5
```

Requires `TMDB_API_KEY` in `.env`. Without it, the script exits with a
clear error (`TMDBNotConfiguredError`) rather than a stack trace.

### A subtle async SQLAlchemy bug class, found three times in this phase

Building the ingestion service and the recommendation service both hit
variations of the same underlying issue, which is worth documenting since
it's easy to reintroduce:

**The core problem:** a relationship attribute that hasn't been loaded via
an actual `SELECT` (with its configured `lazy="selectin"` strategy engaged)
is *unloaded*, even if you'd expect it to obviously be empty (e.g. a
brand-new row that can't have related rows yet). Touching an unloaded
relationship on a persistent object triggers a synchronous lazy-load
attempt, which fails under the async engine outside a fresh `await`.

This showed up three different ways:

1. **`db.refresh(title)`** expires relationship attributes regardless of
   `expire_on_commit=False`. Fixed by re-querying via `select()` instead of
   calling `refresh()`.
2. **A freshly-inserted object's collections are unloaded**, even though
   they're logically empty — assigning into them (`title.genres = [...]`)
   makes SQLAlchemy try to fetch the "current" value first, to diff against.
   Fixed by re-querying the object via `select()` immediately after the
   first flush, before touching any relationship.
3. **`db.add_all(child_rows)` bypasses the parent relationship entirely** —
   creating child rows with a matching foreign key and adding them directly
   to the session never updates the parent's in-memory collection, which
   then stays silently stale (wrong, not just outdated) for the rest of the
   session's lifetime, since re-querying the same primary key doesn't
   re-trigger already-loaded relationship state. Fixed by assigning through
   the relationship (`title.availability = new_rows`) instead of adding
   independently — this is *also* what correctly triggers `delete-orphan`
   cascade for the rows being replaced.

The common fix pattern: prefer a fresh `select()` over `db.get()` or
`db.refresh()` when a function's correctness depends on relationship state,
and always mutate collections *through* the relationship attribute, never
by constructing child rows with a matching foreign key and adding them
independently.

## Recommendation engine, Version 2

The original spec's roadmap described Version 2 as collaborative filtering,
embeddings, and semantic search. This implementation is deliberately
simpler — pure content-based scoring — for a concrete reason: **cold start**.
A collaborative filter or an embedding-similarity model needs either a lot
of interaction data or a lot of compute (and, for real embeddings, a model
+ vector index this environment can't reach — see the note in
`app/services/roulette_service.py`'s docstring for the same reasoning
applied to roulette). A small, early-stage catalog with thin rating history
has neither. Content-based scoring (shared genres, shared cast/crew) works
immediately with zero interaction history and degrades gracefully as the
catalog grows.

### `get_similar_titles` (content-based, per-title)

Scores every other title in the catalog against the source title by:

- **+3 per shared genre** (bounded to the source's first 10 genres)
- **+1 per shared cast/crew member** (bounded to the source's first 15
  credits, ordered by billing)

Genre overlap is weighted higher than a shared actor — two films sharing a
genre are far more reliably "similar" than two films that happen to share
one supporting cast member. Results are restricted to the same media type
(a movie and an unrelated TV show sharing a genre isn't "similar" in the
way a user means it), and fall back to popularity-ordered titles of the
same type when the source has no genres or credits to compare (a title
with incomplete catalog data shouldn't return nothing).

### `get_recommendations_for_user` ("for you", per-user)

Builds a genre-affinity profile from the user's favorites (flat +1.0
weight) and ratings (weighted by `_rating_weight`, so a 9/10 counts far
more than a 5/10, but even a middling rating counts *some* — engaging with
something at all is a weaker positive signal than not, not a negative one).
Titles the user has already favorited or rated are excluded from results.
Falls back to overall popularity for a user with no history yet — verified
directly against a fresh test user in `tests/test_recommendations.py`.

### What would change for a true Version 2

A future embeddings-based version would swap the scoring internals of both
functions — genre/cast overlap counting replaced with vector similarity —
without changing either function's signature or the API endpoints that call
them. That's the point of keeping the scoring logic isolated behind these
two function boundaries.
