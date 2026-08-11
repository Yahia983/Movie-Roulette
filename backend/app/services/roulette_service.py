"""The roulette engine — MovieRoulette's signature feature.

Version 1 (this implementation) works by: (1) building the same filter set
used by browse/search via `title_service`, (2) applying roulette-specific
presets (hidden gems, Oscar winners) on top, (3) pulling a bounded candidate
pool, and (4) picking one result with popularity-weighted randomness so the
result leans toward things people are actually likely to enjoy without being
deterministic.

Why popularity-weighted rather than uniform-random: pure uniform selection
over the whole catalog would surface obscure/low-quality entries as often as
beloved ones, which undermines user trust in the "spin" fast. Why not just
"most popular" deterministically: that defeats the purpose of a discovery
tool — weighting (not maxing) keeps it serendipitous.

Version 2, per the spec's roadmap (collaborative filtering, embeddings,
semantic search, LLM-powered recommendations), replaces `_select_candidate`
with a smarter ranking function — everything else in this module (filter
building, spin logging) stays the same, which is the point of isolating this
as its own service.
"""

import random

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MediaType
from app.models.roulette import RouletteSpin
from app.models.title import Title
from app.schemas.roulette import RouletteFilters
from app.services.title_service import SortBy, TitleFilters, list_titles_for_candidates

_ALL_MEDIA_TYPES = (MediaType.MOVIE, MediaType.TV_SHOW)

# How many top candidates (per media type, after filtering) we consider for
# weighted random selection. Bounded rather than "all matches" so a single
# spin never has to pull thousands of rows, and so popularity-weighting
# stays meaningful (the 5000th-most-popular match shouldn't realistically
# compete with the 1st).
_CANDIDATE_POOL_SIZE = 200

# Floor added to every candidate's weight so even a popularity-0 title has a
# nonzero (if small) chance of being picked — otherwise brand-new or
# never-synced titles could never surface via roulette at all.
_MIN_WEIGHT = 1.0

# Thresholds for the "hidden gems" preset: well-reviewed but not widely
# popular. Simple constants for v1; a data-driven percentile cutoff is a
# natural Version 2 refinement once real popularity distribution data exists.
_HIDDEN_GEM_MIN_RATING = 7.0
_HIDDEN_GEM_MAX_POPULARITY = 20.0


def _to_title_filters(filters: RouletteFilters) -> TitleFilters:
    """Translate the roulette-specific filter schema into the shared
    TitleFilters used by browse/search, so both features stay in sync."""
    decade_bounds = filters.decade_bounds
    return TitleFilters(
        genre_ids=filters.genre_ids,
        min_rating=filters.min_rating,
        max_runtime_minutes=filters.max_runtime_minutes,
        min_runtime_minutes=filters.min_runtime_minutes,
        release_date_from=decade_bounds[0] if decade_bounds else None,
        release_date_to=decade_bounds[1] if decade_bounds else None,
        original_language=filters.original_language,
        sort_by=SortBy.POPULARITY,
    )


def _select_candidate(candidates: list[Title]) -> Title | None:
    """Popularity-weighted random pick from a candidate pool."""
    if not candidates:
        return None
    weights = [max(c.popularity, 0.0) + _MIN_WEIGHT for c in candidates]
    return random.choices(candidates, weights=weights, k=1)[0]


async def spin(
    db: AsyncSession,
    filters: RouletteFilters,
    user_id: int | None,
) -> tuple[Title | None, int]:
    """Run one roulette spin: filter, select, and log the result.

    Returns (selected title or None if nothing matched, total candidate
    count) — the count is surfaced to the frontend so the UI can show
    something honest like "1 of 340 matches" rather than nothing.
    """
    title_filters = _to_title_filters(filters)
    media_types = [filters.media_type] if filters.media_type else list(_ALL_MEDIA_TYPES)

    candidates: list[Title] = []
    total = 0
    for media_type in media_types:
        items, count = await list_titles_for_candidates(
            db,
            media_type,
            title_filters,
            limit=_CANDIDATE_POOL_SIZE,
        )
        candidates.extend(items)
        total += count

    if filters.oscar_winners:
        candidates = [c for c in candidates if c.is_oscar_winner]

    if filters.hidden_gems:
        candidates = [
            c
            for c in candidates
            if c.vote_average >= _HIDDEN_GEM_MIN_RATING
            and c.popularity < _HIDDEN_GEM_MAX_POPULARITY
        ]

    selected = _select_candidate(candidates)

    spin_record = RouletteSpin(
        user_id=user_id,
        filters=filters.model_dump(mode="json"),
        result_title_id=selected.id if selected else None,
    )
    db.add(spin_record)
    await db.commit()

    return selected, total
