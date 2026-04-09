# DEPENDENCY REQUIRED: aiosqlite>=0.20.0
"""Database module for FinAlly.

Exports:
    Database  - async SQLite wrapper class
    get_db    - FastAPI dependency that yields the initialized Database instance
    set_db    - called by main.py at startup to register the Database singleton
"""

from app.db.database import Database

_db: Database | None = None


def set_db(db: Database) -> None:
    """Register the Database singleton. Called once at app startup."""
    global _db
    _db = db


async def get_db() -> Database:
    """FastAPI dependency: yields the shared Database instance."""
    if _db is None:
        raise RuntimeError("Database not initialized. Call set_db() at startup.")
    return _db


__all__ = ["Database", "get_db", "set_db"]
