"""Catalog ingestion: turns TMDB-shaped API responses into upserted rows.

Deliberately split into pure parsing functions (no I/O, trivially unit
tested with plain dicts) and persistence functions (async, touch the DB).
Nothing in this module calls the TMDB API directly — `tmdb_client.py` does
that, and the sync CLI (`scripts/sync_tmdb.py`) wires the two together. This
means the ingestion logic itself — status mapping, slug collision handling,
credit/genre/availability upserts — is fully testable with zero network
access, which is how it's verified in this environment.
"""

import logging
from datetime import date, datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CreditDepartment, MediaType, TitleStatus
from app.models.genre import Genre
from app.models.person import Credit, Person
from app.models.streaming import StreamingService, TitleAvailability
from app.models.title import Movie, Title, TVShow
from app.utils.slugify import build_title_slug

logger = logging.getLogger(__name__)

# TMDB's status strings, mapped onto our smaller, unified TitleStatus enum.
# Movie and TV shows use different vocabularies for "still coming out" —
# unifying them here means the rest of the app never has to know that.
_MOVIE_STATUS_MAP = {
    "Released": TitleStatus.RELEASED,
    "Rumored": TitleStatus.UPCOMING,
    "Planned": TitleStatus.UPCOMING,
    "In Production": TitleStatus.IN_PRODUCTION,
    "Post Production": TitleStatus.IN_PRODUCTION,
    "Canceled": TitleStatus.CANCELED,
}
_TV_STATUS_MAP = {
    "Returning Series": TitleStatus.IN_PRODUCTION,
    "Planned": TitleStatus.UPCOMING,
    "In Production": TitleStatus.IN_PRODUCTION,
    "Pilot": TitleStatus.UPCOMING,
    "Ended": TitleStatus.ENDED,
    "Canceled": TitleStatus.CANCELED,
}

# Only cast + these crew jobs are stored as Credits — TMDB's crew list
# includes dozens of niche departments (sound editor, gaffer, ...) that
# aren't useful for a "who made this" summary and would bloat every title's
# credit list for no user-facing benefit.
_CREW_JOB_TO_DEPARTMENT = {
    "Director": CreditDepartment.DIRECTOR,
    "Writer": CreditDepartment.WRITER,
    "Screenplay": CreditDepartment.WRITER,
    "Producer": CreditDepartment.PRODUCER,
}

# US-only for now — the schema supports per-region rows (see
# TitleAvailability.region), but ingesting every region multiplies API
# calls and storage for markets the app doesn't serve yet.
_AVAILABILITY_REGION = "US"


def parse_status(media_type: MediaType, tmdb_status: str | None) -> TitleStatus:
    """Map a TMDB status string onto our TitleStatus enum, defaulting to
    RELEASED for anything unrecognized rather than raising — a sync should
    degrade gracefully on an unexpected/new TMDB status value, not crash."""
    status_map = _MOVIE_STATUS_MAP if media_type == MediaType.MOVIE else _TV_STATUS_MAP
    return status_map.get(tmdb_status or "", TitleStatus.RELEASED)


def parse_date(value: str | None) -> date | None:
    """TMDB dates are "YYYY-MM-DD" strings, or empty strings for unset dates
    (not omitted keys) — both cases must become None, not a parse error."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        logger.warning("Unparseable TMDB date: %r", value)
        return None


def parse_release_year(tmdb_data: dict[str, Any], media_type: MediaType) -> int | None:
    date_key = "release_date" if media_type == MediaType.MOVIE else "first_air_date"
    parsed = parse_date(tmdb_data.get(date_key))
    return parsed.year if parsed else None


async def get_or_create_genre(db: AsyncSession, tmdb_genre: dict[str, Any]) -> Genre:
    """Upsert a single genre by its TMDB id."""
    tmdb_id = tmdb_genre["id"]
    existing = (
        await db.execute(select(Genre).where(Genre.tmdb_id == tmdb_id))
    ).scalar_one_or_none()
    if existing:
        return existing

    from app.utils.slugify import slugify

    genre = Genre(name=tmdb_genre["name"], slug=slugify(tmdb_genre["name"]), tmdb_id=tmdb_id)
    db.add(genre)
    await db.flush()
    return genre


async def get_or_create_person(db: AsyncSession, tmdb_person: dict[str, Any]) -> Person:
    """Upsert a person (cast/crew member) by their TMDB id."""
    tmdb_id = tmdb_person["id"]
    existing = (
        await db.execute(select(Person).where(Person.tmdb_id == tmdb_id))
    ).scalar_one_or_none()
    if existing:
        # Refresh the photo in case it's changed since last sync; name
        # changes are rare enough not to bother reconciling automatically.
        existing.profile_path = tmdb_person.get("profile_path") or existing.profile_path
        return existing

    from app.utils.slugify import slugify

    person = Person(
        name=tmdb_person["name"],
        slug=slugify(tmdb_person["name"]),
        tmdb_id=tmdb_id,
        profile_path=tmdb_person.get("profile_path"),
    )
    db.add(person)
    await db.flush()
    return person


async def _unique_slug(db: AsyncSession, base_slug: str, model: type[Title]) -> str:
    """Guarantee slug uniqueness across the whole `titles` table (the
    unique constraint is on the base table, not per-subtype), falling back
    to a numeric suffix in the rare case two titles share both name and year."""
    candidate = base_slug
    suffix = 2
    while True:
        existing = (
            await db.execute(select(Title.id).where(Title.slug == candidate))
        ).scalar_one_or_none()
        if existing is None:
            return candidate
        candidate = f"{base_slug}-{suffix}"
        suffix += 1


async def _sync_genres_for_title(db: AsyncSession, title: Title, tmdb_data: dict[str, Any]) -> None:
    genres = []
    for tmdb_genre in tmdb_data.get("genres", []):
        genres.append(await get_or_create_genre(db, tmdb_genre))
    title.genres = genres


async def _sync_credits_for_title(
    db: AsyncSession, title: Title, tmdb_data: dict[str, Any]
) -> None:
    credits_data = tmdb_data.get("credits", {})
    if not credits_data:
        return

    # Replace rather than merge: re-running a sync should make credits
    # exactly match the source data, including removals (e.g. a corrected
    # cast list upstream), not just append.
    title.credits = []
    await db.flush()

    new_credits: list[Credit] = []

    for cast_member in credits_data.get("cast", [])[:20]:
        person = await get_or_create_person(db, cast_member)
        new_credits.append(
            Credit(
                title_id=title.id,
                person_id=person.id,
                department=CreditDepartment.CAST,
                character_name=cast_member.get("character"),
                display_order=cast_member.get("order", 0),
            )
        )

    for crew_member in credits_data.get("crew", []):
        department = _CREW_JOB_TO_DEPARTMENT.get(crew_member.get("job", ""))
        if department is None:
            continue
        person = await get_or_create_person(db, crew_member)
        new_credits.append(
            Credit(
                title_id=title.id,
                person_id=person.id,
                department=department,
                character_name=None,
                display_order=0,
            )
        )

    title.credits = new_credits


async def _get_or_create_streaming_service(
    db: AsyncSession, provider: dict[str, Any]
) -> StreamingService:
    tmdb_provider_id = provider["provider_id"]
    slug = f"tmdb-{tmdb_provider_id}"
    existing = (
        await db.execute(select(StreamingService).where(StreamingService.slug == slug))
    ).scalar_one_or_none()
    if existing:
        return existing

    service = StreamingService(
        name=provider["provider_name"], slug=slug, logo_path=provider.get("logo_path")
    )
    db.add(service)
    await db.flush()
    return service


async def _sync_availability_for_title(
    db: AsyncSession, title: Title, tmdb_data: dict[str, Any]
) -> None:
    providers_data = (
        tmdb_data.get("watch/providers", {}).get("results", {}).get(_AVAILABILITY_REGION)
    )
    if not providers_data:
        return

    title.availability = []
    await db.flush()

    new_rows: list[TitleAvailability] = []
    for provider in providers_data.get("flatrate", []):
        service = await _get_or_create_streaming_service(db, provider)
        new_rows.append(
            TitleAvailability(
                title_id=title.id,
                streaming_service_id=service.id,
                region=_AVAILABILITY_REGION,
                watch_url=providers_data.get("link"),
            )
        )
    title.availability = new_rows


def _apply_scalar_fields(
    title: "Movie | TVShow",
    media_type: MediaType,
    tmdb_data: dict[str, Any],
    name: str,
    release_date: date | None,
) -> None:
    """Assign every plain-column field (as opposed to relationships) from a
    TMDB response onto a Title/Movie/TVShow row. Split out so it can run
    *before* a new row's first flush (required — `title` is NOT NULL) while
    still being shared with the update path."""
    title.title = name
    title.overview = tmdb_data.get("overview") or None
    title.tagline = tmdb_data.get("tagline") or None
    title.poster_path = tmdb_data.get("poster_path")
    title.backdrop_path = tmdb_data.get("backdrop_path")
    title.release_date = release_date
    title.original_language = tmdb_data.get("original_language")
    title.status = parse_status(media_type, tmdb_data.get("status"))
    title.popularity = tmdb_data.get("popularity", 0.0)
    title.vote_average = tmdb_data.get("vote_average", 0.0)
    title.vote_count = tmdb_data.get("vote_count", 0)

    if isinstance(title, Movie):
        title.runtime_minutes = tmdb_data.get("runtime")
        title.budget = tmdb_data.get("budget") or None
        title.revenue = tmdb_data.get("revenue") or None
    else:
        title.number_of_seasons = tmdb_data.get("number_of_seasons")
        title.number_of_episodes = tmdb_data.get("number_of_episodes")
        title.in_production = bool(tmdb_data.get("in_production", False))
        title.last_air_date = parse_date(tmdb_data.get("last_air_date"))
        episode_run_times = tmdb_data.get("episode_run_time") or []
        title.episode_runtime_minutes = episode_run_times[0] if episode_run_times else None


async def upsert_title(db: AsyncSession, media_type: MediaType, tmdb_data: dict[str, Any]) -> Title:
    """Upsert one title (movie or TV show) from a TMDB details response.

    Idempotent on `tmdb_id`: running this twice with the same input updates
    the existing row in place rather than creating a duplicate.
    """
    tmdb_id = tmdb_data["id"]
    model = Movie if media_type == MediaType.MOVIE else TVShow

    existing = (
        await db.execute(select(model).where(Title.tmdb_id == tmdb_id))
    ).scalar_one_or_none()

    name = tmdb_data["title"] if media_type == MediaType.MOVIE else tmdb_data["name"]
    release_date_key = "release_date" if media_type == MediaType.MOVIE else "first_air_date"
    release_date = parse_date(tmdb_data.get(release_date_key))

    if existing is None:
        year = parse_release_year(tmdb_data, media_type)
        slug = await _unique_slug(db, build_title_slug(name, year), model)
        new_row = model(tmdb_id=tmdb_id, slug=slug)
        _apply_scalar_fields(new_row, media_type, tmdb_data, name, release_date)
        db.add(new_row)
        await db.flush()
        # Re-query rather than continue using `new_row` directly: a
        # freshly-flushed object's relationship collections are considered
        # *unloaded* (not "loaded empty"), and `lazy="selectin"` only
        # engages as part of executing a SELECT — it does not retroactively
        # apply to an object that was inserted directly. Assigning into an
        # unloaded collection (e.g. `title.genres = [...]` below) would
        # otherwise make SQLAlchemy fetch the "current" value first to
        # diff against, which is a synchronous lazy load that fails outside
        # a fresh await under the async engine. Re-fetching through
        # `select()` here loads the (empty) relationships properly up front.
        title: Movie | TVShow = cast(
            "Movie | TVShow",
            (await db.execute(select(model).where(model.id == new_row.id))).scalar_one(),
        )
    else:
        title = cast("Movie | TVShow", existing)
        _apply_scalar_fields(title, media_type, tmdb_data, name, release_date)

    await db.flush()

    await _sync_genres_for_title(db, title, tmdb_data)
    await _sync_credits_for_title(db, title, tmdb_data)
    await _sync_availability_for_title(db, title, tmdb_data)

    await db.commit()

    # Deliberately NOT `db.refresh(title)` here: refresh() expires
    # relationship attributes regardless of `expire_on_commit`, which would
    # force a lazy (synchronous) reload of genres/credits/availability on
    # next access — exactly the kind of implicit IO that fails under an
    # async session outside a fresh await. Re-querying instead leverages
    # each relationship's configured `lazy="selectin"` strategy so
    # everything is eagerly loaded together, in this same await.
    refreshed = (await db.execute(select(model).where(model.tmdb_id == tmdb_id))).scalar_one()
    return refreshed


async def sync_popular_titles(
    db: AsyncSession,
    tmdb_client: Any,
    media_type: MediaType,
    pages: int = 1,
) -> int:
    """Fetch and upsert `pages` worth of TMDB's "popular" list for one media
    type. Returns the count of titles synced.

    `tmdb_client` is typed as `Any` rather than `TMDBClient` to keep this
    function trivially usable with a test double — it only needs to expose
    `get_popular` and `get_details` with matching signatures.
    """
    tmdb_media_type = "movie" if media_type == MediaType.MOVIE else "tv"
    synced = 0

    for page in range(1, pages + 1):
        page_data = await tmdb_client.get_popular(tmdb_media_type, page=page)
        for summary in page_data.get("results", []):
            try:
                details = await tmdb_client.get_details(tmdb_media_type, summary["id"])
                await upsert_title(db, media_type, details)
                synced += 1
            except Exception:
                # One bad title (malformed upstream data, a transient
                # per-item error) should never abort an entire sync run —
                # log and continue so the rest of the page still lands.
                logger.exception(
                    "Failed to sync %s id=%s; continuing with next title",
                    tmdb_media_type,
                    summary.get("id"),
                )
                await db.rollback()

    return synced
