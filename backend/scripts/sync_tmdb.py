"""CLI entrypoint for syncing the catalog from TMDB.

Usage:
    python scripts/sync_tmdb.py --media-type movie --pages 5
    python scripts/sync_tmdb.py --media-type tv --pages 5

Requires TMDB_API_KEY to be set in the environment/.env. Each TMDB "page" of
the popular list is 20 titles, and each title costs one extra API call for
full details (credits + streaming availability), so `--pages 5` for movies
is ~100 title-detail requests — mind TMDB's rate limits on large syncs.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.enums import MediaType  # noqa: E402
from app.services.ingestion_service import sync_popular_titles  # noqa: E402
from app.services.tmdb_client import TMDBClient, TMDBNotConfiguredError  # noqa: E402


async def main(media_type: MediaType, pages: int) -> None:
    async with TMDBClient() as client:
        async with AsyncSessionLocal() as db:
            try:
                count = await sync_popular_titles(db, client, media_type, pages=pages)
            except TMDBNotConfiguredError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                sys.exit(1)
            print(f"Synced {count} {media_type.value} titles from TMDB.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--media-type", choices=["movie", "tv"], required=True)
    parser.add_argument("--pages", type=int, default=1, help="TMDB pages to sync (20 titles/page)")
    args = parser.parse_args()

    resolved_media_type = MediaType.MOVIE if args.media_type == "movie" else MediaType.TV_SHOW
    asyncio.run(main(resolved_media_type, args.pages))
