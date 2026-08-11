"""Seed a small, realistic dataset for local development and manual testing.

Not part of the app's runtime code — a standalone script invoked manually
(`python scripts/seed_dev_data.py`) since seed data is a dev/demo concern,
not something the API itself should ever do implicitly on startup.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import date  # noqa: E402

from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.enums import TitleStatus  # noqa: E402
from app.models.genre import Genre  # noqa: E402
from app.models.title import Movie, TVShow  # noqa: E402


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        genres = {
            name: Genre(name=name, slug=name.lower().replace(" ", "-"))
            for name in ["Action", "Science Fiction", "Drama", "Comedy", "Animation"]
        }
        db.add_all(genres.values())
        await db.flush()

        movie = Movie(
            title="The Last Signal",
            slug="the-last-signal-2019",
            overview="A deep-space communications officer receives a message that shouldn't exist.",
            release_date=date(2019, 6, 14),
            status=TitleStatus.RELEASED,
            popularity=42.5,
            vote_average=7.8,
            vote_count=1204,
            runtime_minutes=118,
            genres=[genres["Science Fiction"], genres["Drama"]],
        )

        show = TVShow(
            title="Late Shift Diner",
            slug="late-shift-diner",
            overview="Regulars and strangers cross paths at a 24-hour diner over one long year.",
            release_date=date(2021, 3, 2),
            status=TitleStatus.ENDED,
            popularity=18.2,
            vote_average=8.4,
            vote_count=530,
            number_of_seasons=2,
            number_of_episodes=16,
            in_production=False,
            genres=[genres["Drama"], genres["Comedy"]],
        )

        db.add_all([movie, show])
        await db.commit()
        print(f"Seeded: {movie.title!r} (movie), {show.title!r} (tv_show), {len(genres)} genres")


if __name__ == "__main__":
    asyncio.run(seed())
