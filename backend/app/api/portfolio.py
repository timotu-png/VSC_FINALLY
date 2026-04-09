"""Portfolio API endpoints: positions, trades, history."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.db import Database, get_db
from app.market import PriceCache

from .deps import get_price_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

USER_ID = "default"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class TradeRequest(BaseModel):
    ticker: str
    quantity: float
    side: str

    @field_validator("ticker")
    @classmethod
    def uppercase_ticker(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("quantity")
    @classmethod
    def positive_quantity(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("quantity must be greater than 0")
        return v

    @field_validator("side")
    @classmethod
    def valid_side(cls, v: str) -> str:
        if v not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        return v


# ---------------------------------------------------------------------------
# Helper: build uniform error response
# ---------------------------------------------------------------------------


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message}},
    )


# ---------------------------------------------------------------------------
# GET /api/portfolio
# ---------------------------------------------------------------------------


@router.get("")
async def get_portfolio(
    db: Annotated[Database, Depends(get_db)],
    price_cache: Annotated[PriceCache, Depends(get_price_cache)],
) -> dict:
    """Return current positions, cash balance, total value, and unrealized P&L."""
    user = await db.get_user()
    cash_balance: float = user["cash_balance"]
    positions_raw = await db.get_positions()

    positions = []
    total_position_value = 0.0
    total_unrealized_pnl = 0.0

    for pos in positions_raw:
        ticker = pos["ticker"]
        qty: float = pos["quantity"]
        avg_cost: float = pos["avg_cost"]

        price_update = price_cache.get(ticker)
        current_price = price_update.price if price_update else None

        if current_price is not None:
            unrealized_pnl = (current_price - avg_cost) * qty
            pnl_percent = ((current_price - avg_cost) / avg_cost * 100) if avg_cost else 0.0
            position_value = current_price * qty
        else:
            unrealized_pnl = None
            pnl_percent = None
            position_value = avg_cost * qty  # fallback for total

        total_position_value += position_value
        if unrealized_pnl is not None:
            total_unrealized_pnl += unrealized_pnl

        positions.append(
            {
                "ticker": ticker,
                "quantity": qty,
                "avg_cost": avg_cost,
                "current_price": current_price,
                "unrealized_pnl": unrealized_pnl,
                "pnl_percent": pnl_percent,
            }
        )

    total_value = cash_balance + total_position_value

    return {
        "positions": positions,
        "cash_balance": cash_balance,
        "total_value": total_value,
        "unrealized_pnl": total_unrealized_pnl,
    }


# ---------------------------------------------------------------------------
# POST /api/portfolio/trade
# ---------------------------------------------------------------------------


@router.post("/trade")
async def execute_trade(
    req: TradeRequest,
    db: Annotated[Database, Depends(get_db)],
    price_cache: Annotated[PriceCache, Depends(get_price_cache)],
) -> dict:
    """Execute a market order (buy or sell)."""
    ticker = req.ticker
    quantity = req.quantity
    side = req.side

    # --- Check ticker in cache ---
    price_update = price_cache.get(ticker)
    if price_update is None:
        # Not tracked at all
        raise _error(404, "unknown_ticker", f"Ticker '{ticker}' is not tracked by the price cache")

    current_price = price_update.price
    if current_price is None or current_price <= 0:
        raise _error(503, "price_unavailable", f"No price available yet for '{ticker}'")

    user = await db.get_user()
    cash_balance: float = user["cash_balance"]
    positions = await db.get_positions()
    position_map = {p["ticker"]: p for p in positions}

    if side == "buy":
        cost = quantity * current_price
        if cash_balance < cost:
            raise _error(
                409,
                "insufficient_cash",
                f"Need ${cost:.2f} but only ${cash_balance:.2f} available",
            )

        new_cash = cash_balance - cost
        await db.update_cash(USER_ID, new_cash)

        existing = position_map.get(ticker)
        if existing:
            old_qty = existing["quantity"]
            old_avg = existing["avg_cost"]
            new_qty = old_qty + quantity
            new_avg = (old_qty * old_avg + quantity * current_price) / new_qty
        else:
            new_qty = quantity
            new_avg = current_price

        await db.upsert_position(USER_ID, ticker, new_qty, new_avg)

    else:  # sell
        existing = position_map.get(ticker)
        held_qty = existing["quantity"] if existing else 0.0
        if held_qty < quantity:
            raise _error(
                409,
                "insufficient_shares",
                f"Only {held_qty} shares available, cannot sell {quantity}",
            )

        proceeds = quantity * current_price
        new_cash = cash_balance + proceeds
        await db.update_cash(USER_ID, new_cash)

        new_qty = held_qty - quantity
        if new_qty <= 0:
            await db.delete_position(USER_ID, ticker)
            new_qty = 0.0
            new_avg = 0.0
        else:
            new_avg = existing["avg_cost"]
            await db.upsert_position(USER_ID, ticker, new_qty, new_avg)

    trade = await db.insert_trade(USER_ID, ticker, side, quantity, current_price)

    # Trigger portfolio snapshot
    await _record_snapshot(db, price_cache)

    # Build position response
    if side == "buy":
        position_resp = {"ticker": ticker, "quantity": new_qty, "avg_cost": new_avg}
    else:
        if new_qty > 0:
            position_resp = {"ticker": ticker, "quantity": new_qty, "avg_cost": new_avg}
        else:
            position_resp = {"ticker": ticker, "quantity": 0.0, "avg_cost": 0.0}

    updated_user = await db.get_user()

    return {
        "trade": trade,
        "cash_balance": updated_user["cash_balance"],
        "position": position_resp,
    }


# ---------------------------------------------------------------------------
# GET /api/portfolio/history
# ---------------------------------------------------------------------------


@router.get("/history")
async def get_portfolio_history(
    db: Annotated[Database, Depends(get_db)],
) -> dict:
    """Return portfolio value snapshots for the P&L chart."""
    snapshots = await db.get_portfolio_history()
    return {"snapshots": snapshots}


# ---------------------------------------------------------------------------
# Internal helper: record portfolio snapshot
# ---------------------------------------------------------------------------


async def _record_snapshot(db: Database, price_cache: PriceCache) -> None:
    """Compute and persist current total portfolio value as a snapshot."""
    try:
        user = await db.get_user()
        cash_balance: float = user["cash_balance"]
        positions = await db.get_positions()

        total_value = cash_balance
        for pos in positions:
            price = price_cache.get_price(pos["ticker"])
            if price is not None:
                total_value += price * pos["quantity"]
            else:
                total_value += pos["avg_cost"] * pos["quantity"]

        await db.insert_portfolio_snapshot(USER_ID, total_value)
    except Exception:
        logger.exception("Failed to record portfolio snapshot")
