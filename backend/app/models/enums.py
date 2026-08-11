"""Enums shared across ORM models.

Kept in their own module (rather than defined inline in title.py or
credit.py) so any model can import them without risking a circular import —
e.g. both `Title` and future service-layer filter logic need `MediaType`.
"""

import enum


class MediaType(str, enum.Enum):
    """Discriminator for the `titles` polymorphic hierarchy."""

    MOVIE = "movie"
    TV_SHOW = "tv_show"


class TitleStatus(str, enum.Enum):
    """Production/release status, relevant to both movies and TV shows."""

    RELEASED = "released"
    IN_PRODUCTION = "in_production"
    UPCOMING = "upcoming"
    CANCELED = "canceled"
    ENDED = "ended"


class CreditDepartment(str, enum.Enum):
    """What role a person played in a title's credits.

    Modeled as a single `credits` table with a department discriminator
    rather than separate cast/director/writer tables — every department
    shares the same shape (title, person, optional character name, ordering)
    and querying "everyone who worked on this title" is one table, not a
    UNION across several.
    """

    CAST = "cast"
    DIRECTOR = "director"
    WRITER = "writer"
    PRODUCER = "producer"
