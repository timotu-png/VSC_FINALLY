"""Health check endpoint."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
async def health_check() -> dict:
    """Return application health status."""
    return {"status": "ok", "timestamp": datetime.now(UTC).isoformat()}
