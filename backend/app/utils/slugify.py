"""URL-safe slug generation.

Split into its own tiny module because both the ingestion pipeline and any
future "create a title manually" admin tooling need identical slugging
behavior — one implementation, not a copy in each caller.
"""

import re
import unicodedata


def slugify(text: str) -> str:
    """Convert arbitrary text into a lowercase, hyphenated, URL-safe slug.

    Normalizes unicode (e.g. "Amélie" -> "amelie") rather than stripping
    accented characters outright, since transliteration keeps the slug
    recognizable instead of dropping meaningful letters.
    """
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return slug or "untitled"


def build_title_slug(name: str, year: int | None) -> str:
    """Build the slug used in title URLs: "the-matrix-1999".

    The year suffix is what disambiguates two titles with the same name
    (a real, common occurrence in film catalogs — remakes, reboots, and
    coincidental name collisions all happen) without needing a numeric
    fallback suffix that would make URLs less predictable/shareable.
    """
    base = slugify(name)
    return f"{base}-{year}" if year else base
