"""Import every ORM model so it registers on `Base.metadata`.

Why this file matters: SQLAlchemy only knows about a model once its module
has been imported somewhere. Alembic's autogenerate compares the *database*
against `Base.metadata` — if a model module was never imported, autogenerate
silently thinks that table shouldn't exist and would emit a DROP TABLE for it.
Centralizing the imports here (and importing this module from alembic/env.py)
means adding a new model file is enough; nothing else needs to remember to
wire it in.
"""

from app.models.collection import Collection, CollectionItem
from app.models.favorite import Favorite
from app.models.genre import Genre
from app.models.person import Credit, Person
from app.models.rating import Rating
from app.models.roulette import RouletteSpin
from app.models.streaming import StreamingService, TitleAvailability
from app.models.title import Movie, Title, TVShow
from app.models.user import User
from app.models.viewing_history import ViewingHistoryEntry
from app.models.watch_later import WatchLaterItem

__all__ = [
    "Collection",
    "CollectionItem",
    "Credit",
    "Favorite",
    "Genre",
    "Person",
    "Rating",
    "RouletteSpin",
    "StreamingService",
    "TitleAvailability",
    "Movie",
    "Title",
    "TVShow",
    "User",
    "ViewingHistoryEntry",
    "WatchLaterItem",
]
