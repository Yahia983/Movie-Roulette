"""Pydantic schemas package. Unlike app/models, there's no need to
force-import every submodule here — schemas have no ORM-metadata-registration
side effect, so each API module simply imports what it needs directly.
"""
