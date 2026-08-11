"""Recommendation engine, Version 2 per the project roadmap.

Two distinct features, both content-based rather than the originally
envisioned embeddings/collaborative-filtering approach — deliberately: with
a small early-stage catalog and thin interaction history, a real
collaborative filter has too little signal to beat a well-tuned
content-based heuristic (classic cold-start problem). Both functions are
written so a future embedding-based ranker can replace their internals
without changing the public interface — see the module docstring in
`roulette_service.py` for the same design principle applied there.

1. `get_similar_titles` — "More like this" on a detail page. Scores every
   other title in the catalog by shared genres and shared cast/crew,
   weighted, then breaks ties with popularity.

2. `get_recommendations_for_user` — "Recommended for you". Builds a genre
   affinity profile from a user's favorites and ratings (higher-rated genres
   count more), then scores unseen titles against that profile.
"""

from collections import Counter, defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.favorite import Favorite
from app.models.person import Credit
from app.models.rating import Rating
from app.models.title import Title
from app.models.title import title_genres as title_genres_table

# How many of a title's own genres/people to compare against, per limb of
# the score. Bounding this keeps the query cost predictable regardless of
# how large a title's own genre/cast list happens to be.
_MAX_COMPARISON_GENRES = 10
_MAX_COMPARISON_PEOPLE = 15

# Relative weight of a shared genre vs. a shared cast/crew member in the
# similarity score. Genre overlap is a stronger, more reliable "these are
# actually similar" signal than sharing one actor across two otherwise
# unrelated films, so it's weighted higher.
_GENRE_WEIGHT = 3
_PERSON_WEIGHT = 1


# A user's rating (1-10) is folded into their genre-affinity weight via this
# function rather than used as a flat multiplier, so a mediocre 5/10 rating
# contributes less to "this user likes this genre" than an enthusiastic
# 9/10 — but even a low rating still counts *some*, since watching and
# rating something at all is a weaker positive signal than not engaging.
def _rating_weight(score: int) -> float:
    return max(score - 4, 1) / 6.0


async def get_similar_titles(db: AsyncSession, title_id: int, limit: int = 12) -> list[Title]:
    """Content-based "more like this": shared genres + shared cast/crew,
    weighted, ranked, with popularity breaking ties.

    Returns titles of the SAME media type as the source title — mixing
    movies and TV shows into one "similar" list reads as a bug to users
    even when the content is thematically related (a movie and its own
    spin-off series are "related," not interchangeably "similar").
    """
    # A plain `select()` (not `db.get()`) is deliberate: `Session.get()`
    # returns an already-identity-mapped object as-is without necessarily
    # re-running `selectin` eager loaders for relationships that were never
    # previously touched on that in-memory object, which fails the same way
    # documented in ingestion_service.py — a lazy load attempted outside a
    # fresh await. A `select()` reliably triggers each relationship's
    # configured loader strategy regardless of prior identity-map state.
    source = (await db.execute(select(Title).where(Title.id == title_id))).scalar_one_or_none()
    if source is None:
        return []

    genre_ids = [g.id for g in source.genres[:_MAX_COMPARISON_GENRES]]
    person_ids = [
        c.person_id
        for c in sorted(source.credits, key=lambda c: c.display_order)[:_MAX_COMPARISON_PEOPLE]
    ]

    if not genre_ids and not person_ids:
        # Nothing to compare against — fall back to popular titles of the
        # same media type rather than returning nothing.
        stmt = (
            select(Title)
            .where(Title.media_type == source.media_type, Title.id != title_id)
            .order_by(Title.popularity.desc())
            .limit(limit)
        )
        return list((await db.execute(stmt)).scalars().all())

    candidate_ids: Counter[int] = Counter()

    if genre_ids:
        genre_matches = await db.execute(
            select(title_genres_table.c.title_id)
            .where(title_genres_table.c.genre_id.in_(genre_ids))
            .where(title_genres_table.c.title_id != title_id)
        )
        for (matched_title_id,) in genre_matches:
            candidate_ids[matched_title_id] += _GENRE_WEIGHT

    if person_ids:
        person_matches = await db.execute(
            select(Credit.title_id)
            .where(Credit.person_id.in_(person_ids))
            .where(Credit.title_id != title_id)
        )
        for (matched_title_id,) in person_matches:
            candidate_ids[matched_title_id] += _PERSON_WEIGHT

    if not candidate_ids:
        return []

    # Only fetch full Title rows for a bounded top-N candidate set, rather
    # than every scored title — scoring can surface hundreds of weak
    # one-point matches in a large catalog, and we only need the winners.
    top_candidate_ids = [tid for tid, _ in candidate_ids.most_common(limit * 3)]

    stmt = select(Title).where(
        Title.id.in_(top_candidate_ids), Title.media_type == source.media_type
    )
    candidates = list((await db.execute(stmt)).scalars().all())

    candidates.sort(key=lambda t: (candidate_ids[t.id], t.popularity), reverse=True)
    return candidates[:limit]


async def get_recommendations_for_user(
    db: AsyncSession, user_id: int, limit: int = 20
) -> list[Title]:
    """ "Recommended for you": rank unseen titles by the user's genre
    affinity, derived from their favorites (flat positive signal) and
    ratings (weighted by score).

    Titles the user has already favorited or rated are excluded — a
    recommendation feed showing things a user already knows about isn't
    useful, and is the single most common complaint about naive
    recommendation systems.
    """
    favorite_title_ids_result = await db.execute(
        select(Favorite.title_id).where(Favorite.user_id == user_id)
    )
    favorite_title_ids = {row[0] for row in favorite_title_ids_result}

    ratings_result = await db.execute(
        select(Rating.title_id, Rating.score).where(Rating.user_id == user_id)
    )
    ratings = {row[0]: row[1] for row in ratings_result}

    seen_title_ids = favorite_title_ids | set(ratings.keys())
    if not seen_title_ids:
        # No signal yet for this user — fall back to overall popular titles
        # rather than an empty feed, same cold-start fallback philosophy as
        # get_similar_titles above.
        stmt = select(Title).order_by(Title.popularity.desc()).limit(limit)
        return list((await db.execute(stmt)).scalars().all())

    # Build the genre affinity profile: favorites count as a solid positive
    # (weight 1.0); ratings are weighted by how much the user liked it.
    # A plain defaultdict(float) rather than Counter here — typeshed's
    # Counter is hardcoded to int-valued counts, and this needs fractional
    # weights (see _rating_weight); Counter's convenient `.most_common()`
    # is reproduced manually below via sorted().
    genre_weights: dict[int, float] = defaultdict(float)

    genre_rows = await db.execute(
        select(title_genres_table.c.title_id, title_genres_table.c.genre_id).where(
            title_genres_table.c.title_id.in_(seen_title_ids)
        )
    )
    title_to_genres: dict[int, list[int]] = {}
    for title_id, genre_id in genre_rows:
        title_to_genres.setdefault(title_id, []).append(genre_id)

    for title_id in favorite_title_ids:
        for genre_id in title_to_genres.get(title_id, []):
            genre_weights[genre_id] += 1.0

    for title_id, score in ratings.items():
        for genre_id in title_to_genres.get(title_id, []):
            genre_weights[genre_id] += _rating_weight(score)

    if not genre_weights:
        stmt = select(Title).order_by(Title.popularity.desc()).limit(limit)
        return list((await db.execute(stmt)).scalars().all())

    top_genre_ids = [
        genre_id
        for genre_id, _ in sorted(genre_weights.items(), key=lambda kv: kv[1], reverse=True)[:8]
    ]

    candidate_rows = await db.execute(
        select(title_genres_table.c.title_id, title_genres_table.c.genre_id).where(
            title_genres_table.c.genre_id.in_(top_genre_ids)
        )
    )
    candidate_scores: dict[int, float] = defaultdict(float)
    for title_id, genre_id in candidate_rows:
        if title_id in seen_title_ids:
            continue
        candidate_scores[title_id] += genre_weights[genre_id]

    if not candidate_scores:
        stmt = select(Title).order_by(Title.popularity.desc()).limit(limit)
        return list((await db.execute(stmt)).scalars().all())

    top_candidate_ids = [
        tid
        for tid, _ in sorted(candidate_scores.items(), key=lambda kv: kv[1], reverse=True)[
            : limit * 3
        ]
    ]
    candidates = list(
        (await db.execute(select(Title).where(Title.id.in_(top_candidate_ids)))).scalars().all()
    )

    candidates.sort(key=lambda t: (candidate_scores[t.id], t.popularity), reverse=True)
    return candidates[:limit]
