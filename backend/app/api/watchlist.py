"""Watchlist API endpoints."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, field_validator

from app.db import Database, get_db
from app.market import MarketDataSource, PriceCache

from .deps import get_market_source, get_price_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

USER_ID = "default"
WATCHLIST_MAX = 50


class AddTickerRequest(BaseModel):
    ticker: str

    @field_validator("ticker")
    @classmethod
    def uppercase_ticker(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("ticker must not be empty")
        return v


# ---------------------------------------------------------------------------
# GET /api/watchlist
# ---------------------------------------------------------------------------


@router.get("")
async def get_watchlist(
    db: Annotated[Database, Depends(get_db)],
    price_cache: Annotated[PriceCache, Depends(get_price_cache)],
) -> dict:
    """Return watchlist tickers enriched with current prices."""
    tickers = await db.get_watchlist()
    result = []
    for ticker in tickers:
        update = price_cache.get(ticker)
        if update is not None:
            result.append(
                {
                    "ticker": ticker,
                    "price": update.price,
                    "change": update.change,
                    "change_percent": update.change_percent,
                    "direction": update.direction,
                }
            )
        else:
            result.append(
                {
                    "ticker": ticker,
                    "price": None,
                    "change": None,
                    "change_percent": None,
                    "direction": None,
                }
            )
    return {"tickers": result}


# ---------------------------------------------------------------------------
# POST /api/watchlist
# ---------------------------------------------------------------------------


@router.post("", status_code=201)
async def add_ticker(
    req: AddTickerRequest,
    db: Annotated[Database, Depends(get_db)],
    market_source: Annotated[MarketDataSource, Depends(get_market_source)],
) -> dict:
    """Add a ticker to the watchlist."""
    ticker = req.ticker

    count = await db.count_watchlist()
    if count >= WATCHLIST_MAX:
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "watchlist_full", "message": "Watchlist limit of 50 reached"}},
        )

    added_at = datetime.now(UTC).isoformat()
    try:
        await db.add_watchlist_ticker(USER_ID, ticker)
    except ValueError:
        # Already in watchlist — still return success, idempotent
        pass

    # Tell the market data source to start tracking this ticker
    try:
        await market_source.add_ticker(ticker)
    except Exception:
        logger.exception("Failed to add ticker '%s' to market source", ticker)

    return {"ticker": ticker, "added_at": added_at}


# ---------------------------------------------------------------------------
# DELETE /api/watchlist/{ticker}
# ---------------------------------------------------------------------------


@router.delete("/{ticker}", status_code=204)
async def remove_ticker(
    ticker: str,
    db: Annotated[Database, Depends(get_db)],
    market_source: Annotated[MarketDataSource, Depends(get_market_source)],
) -> Response:
    """Remove a ticker from the watchlist."""
    ticker = ticker.strip().upper()

    await db.remove_watchlist_ticker(USER_ID, ticker)

    # Only remove from market source if not still held in a position
    positions = await db.get_positions()
    held_tickers = {p["ticker"] for p in positions}
    if ticker not in held_tickers:
        try:
            await market_source.remove_ticker(ticker)
        except Exception:
            logger.exception("Failed to remove ticker '%s' from market source", ticker)

    return Response(status_code=204)
