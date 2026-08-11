"""Aggregates all v1 endpoint routers into a single router.

Why a dedicated aggregator: as features land (auth, movies, tv-shows,
roulette, recommendations, collections...) each gets its own endpoints module
with its own router. This file is the single place that wires them together,
so `main.py` never needs to change when a new feature module is added — it
just includes `api_router` once.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    collections,
    favorites,
    genres,
    health,
    history,
    movies,
    ratings,
    recommendations,
    roulette,
    tv_shows,
    users,
    watch_later,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(genres.router, prefix="/genres", tags=["genres"])
api_router.include_router(movies.router, prefix="/movies", tags=["movies"])
api_router.include_router(tv_shows.router, prefix="/tv-shows", tags=["tv-shows"])
api_router.include_router(favorites.router, prefix="/favorites", tags=["favorites"])
api_router.include_router(watch_later.router, prefix="/watch-later", tags=["watch-later"])
api_router.include_router(ratings.router, prefix="/ratings", tags=["ratings"])
api_router.include_router(history.router, prefix="/history", tags=["history"])
api_router.include_router(collections.router, prefix="/collections", tags=["collections"])
api_router.include_router(roulette.router, prefix="/roulette", tags=["roulette"])
api_router.include_router(
    recommendations.router, prefix="/recommendations", tags=["recommendations"]
)
