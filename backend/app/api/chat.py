"""Chat API endpoint — LLM integration with auto-execution of trades/watchlist."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.db import Database, get_db
from app.market import MarketDataSource, PriceCache

from .deps import get_market_source, get_price_cache
from .portfolio import _record_snapshot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

USER_ID = "default"
MAX_TRADES_PER_RESPONSE = 5
MAX_TRADE_PCT_OF_PORTFOLIO = 0.20


class ChatRequest(BaseModel):
    message: str


# ---------------------------------------------------------------------------
# POST /api/chat
# ---------------------------------------------------------------------------


@router.post("")
async def chat(
    req: ChatRequest,
    db: Annotated[Database, Depends(get_db)],
    price_cache: Annotated[PriceCache, Depends(get_price_cache)],
    market_source: Annotated[MarketDataSource, Depends(get_market_source)],
) -> dict:
    """Process a chat message through the LLM and auto-execute any actions."""
    try:
        from app.llm import get_llm_client  # late import — module built by another engineer
        llm_client = get_llm_client()
    except ImportError:
        from fastapi import HTTPException as _HTTPException
        raise _HTTPException(status_code=503, detail={"error": {"code": "llm_unavailable", "message": "LLM module not yet available"}})

    # 1. Build portfolio context
    portfolio_context = await _build_portfolio_context(db, price_cache)
    total_value: float = portfolio_context["total_value"]

    # 2. Load conversation history (last 20 messages)
    history = await db.get_chat_history(limit=20)

    # 3. Call LLM
    llm_response = await llm_client.process_chat(req.message, portfolio_context, history)

    # 4. Auto-execute trades
    actions: list[dict] = []
    trades = getattr(llm_response, "trades", []) or []
    watchlist_changes = getattr(llm_response, "watchlist_changes", []) or []

    trade_count = 0
    for trade in trades:
        ticker = trade.ticker.strip().upper()
        side = trade.side
        quantity = trade.quantity

        if trade_count >= MAX_TRADES_PER_RESPONSE:
            actions.append(
                {
                    "type": "trade",
                    "payload": {"ticker": ticker, "side": side, "quantity": quantity},
                    "status": "error",
                    "error": "too_many_trades",
                }
            )
            continue

        # Notional cap: reject if > 20% of total portfolio value
        price_update = price_cache.get(ticker)
        current_price = price_update.price if price_update else None

        if current_price is not None:
            notional = quantity * current_price
            if notional > MAX_TRADE_PCT_OF_PORTFOLIO * total_value:
                actions.append(
                    {
                        "type": "trade",
                        "payload": {"ticker": ticker, "side": side, "quantity": quantity},
                        "status": "error",
                        "error": "trade_too_large",
                    }
                )
                trade_count += 1
                continue

        # Run through same validation as POST /api/portfolio/trade
        error_code, error_msg = await _validate_and_execute_trade(
            db, price_cache, ticker, side, quantity
        )

        if error_code is None:
            await _record_snapshot(db, price_cache)
            actions.append(
                {
                    "type": "trade",
                    "payload": {"ticker": ticker, "side": side, "quantity": quantity},
                    "status": "success",
                    "error": None,
                }
            )
        else:
            actions.append(
                {
                    "type": "trade",
                    "payload": {"ticker": ticker, "side": side, "quantity": quantity},
                    "status": "error",
                    "error": error_code,
                }
            )

        trade_count += 1

    # 5. Auto-execute watchlist changes
    for wl_change in watchlist_changes:
        ticker = wl_change.ticker.strip().upper()
        action = wl_change.action  # "add" or "remove"

        wl_error = await _execute_watchlist_change(db, market_source, ticker, action)
        actions.append(
            {
                "type": "watchlist",
                "payload": {"ticker": ticker, "action": action},
                "status": "success" if wl_error is None else "error",
                "error": wl_error,
            }
        )

    # 6. Persist messages
    await db.insert_chat_message(USER_ID, "user", req.message, actions=None)
    await db.insert_chat_message(USER_ID, "assistant", llm_response.message, actions=actions)

    # 7. Return full response
    return {"message": llm_response.message, "actions": actions}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _build_portfolio_context(db: Database, price_cache: PriceCache) -> dict:
    """Build portfolio context dict for the LLM."""
    user = await db.get_user()
    cash_balance: float = user["cash_balance"]
    positions_raw = await db.get_positions()
    watchlist_tickers = await db.get_watchlist()

    positions = []
    total_position_value = 0.0

    for pos in positions_raw:
        ticker = pos["ticker"]
        qty: float = pos["quantity"]
        avg_cost: float = pos["avg_cost"]
        price_update = price_cache.get(ticker)
        current_price = price_update.price if price_update else avg_cost

        market_value = current_price * qty
        unrealized_pnl = (current_price - avg_cost) * qty
        pnl_percent = ((current_price - avg_cost) / avg_cost * 100) if avg_cost else 0.0

        total_position_value += market_value
        positions.append(
            {
                "ticker": ticker,
                "quantity": qty,
                "avg_cost": avg_cost,
                "current_price": current_price,
                "market_value": market_value,
                "unrealized_pnl": unrealized_pnl,
                "pnl_percent": pnl_percent,
            }
        )

    watchlist = []
    for ticker in watchlist_tickers:
        update = price_cache.get(ticker)
        watchlist.append(
            {
                "ticker": ticker,
                "price": update.price if update else None,
                "change_percent": update.change_percent if update else None,
            }
        )

    total_value = cash_balance + total_position_value

    return {
        "cash_balance": cash_balance,
        "total_value": total_value,
        "positions": positions,
        "watchlist": watchlist,
    }


async def _validate_and_execute_trade(
    db: Database,
    price_cache: PriceCache,
    ticker: str,
    side: str,
    quantity: float,
) -> tuple[str | None, str | None]:
    """Validate and execute a trade. Returns (error_code, error_message) or (None, None)."""
    if quantity <= 0:
        return "bad_request", "quantity must be greater than 0"
    if side not in ("buy", "sell"):
        return "bad_request", "side must be 'buy' or 'sell'"

    price_update = price_cache.get(ticker)
    if price_update is None:
        return "unknown_ticker", f"Ticker '{ticker}' is not tracked"

    current_price = price_update.price
    if current_price is None or current_price <= 0:
        return "price_unavailable", f"No price available for '{ticker}'"

    user = await db.get_user()
    cash_balance: float = user["cash_balance"]
    positions = await db.get_positions()
    position_map = {p["ticker"]: p for p in positions}

    if side == "buy":
        cost = quantity * current_price
        if cash_balance < cost:
            return "insufficient_cash", f"Need ${cost:.2f}, have ${cash_balance:.2f}"

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
            return "insufficient_shares", f"Only {held_qty} shares available"

        proceeds = quantity * current_price
        new_cash = cash_balance + proceeds
        await db.update_cash(USER_ID, new_cash)

        new_qty = held_qty - quantity
        if new_qty <= 0:
            await db.delete_position(USER_ID, ticker)
        else:
            await db.upsert_position(USER_ID, ticker, new_qty, existing["avg_cost"])

    await db.insert_trade(USER_ID, ticker, side, quantity, current_price)
    return None, None


async def _execute_watchlist_change(
    db: Database,
    market_source: MarketDataSource,
    ticker: str,
    action: str,
) -> str | None:
    """Execute a watchlist add or remove. Returns error string or None."""
    try:
        if action == "add":
            count = await db.count_watchlist()
            if count >= 50:
                return "watchlist_full"
            await db.add_watchlist_ticker(USER_ID, ticker)
            await market_source.add_ticker(ticker)
        elif action == "remove":
            await db.remove_watchlist_ticker(USER_ID, ticker)
            positions = await db.get_positions()
            held_tickers = {p["ticker"] for p in positions}
            if ticker not in held_tickers:
                await market_source.remove_ticker(ticker)
        else:
            return f"unknown_action: {action}"
    except Exception as exc:
        logger.exception("Watchlist change failed for %s/%s", action, ticker)
        return str(exc)
    return None
