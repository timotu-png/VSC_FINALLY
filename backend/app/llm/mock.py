"""Deterministic mock LLM responder for testing and development."""

import re

from .models import LLMResponse, TradeRequest, WatchlistChange


def mock_response(message: str, portfolio_context: dict) -> LLMResponse:
    """Return a deterministic mock LLM response based on the user message.

    Patterns are matched in order (buy before sell, add before remove).
    """
    lower = message.lower()

    # buy N TICKER
    buy_match = re.search(r"buy\s+(\d+\.?\d*)\s+([a-zA-Z]+)", lower)
    if buy_match:
        quantity = float(buy_match.group(1))
        ticker = buy_match.group(2).upper()
        return LLMResponse(
            message=f"Buying {quantity} shares of {ticker}.",
            trades=[TradeRequest(ticker=ticker, side="buy", quantity=quantity)],
        )

    # sell N TICKER
    sell_match = re.search(r"sell\s+(\d+\.?\d*)\s+([a-zA-Z]+)", lower)
    if sell_match:
        quantity = float(sell_match.group(1))
        ticker = sell_match.group(2).upper()
        return LLMResponse(
            message=f"Selling {quantity} shares of {ticker}.",
            trades=[TradeRequest(ticker=ticker, side="sell", quantity=quantity)],
        )

    # add TICKER
    add_match = re.search(r"add\s+([a-zA-Z]+)", lower)
    if add_match:
        ticker = add_match.group(1).upper()
        return LLMResponse(
            message=f"Adding {ticker} to your watchlist.",
            watchlist_changes=[WatchlistChange(ticker=ticker, action="add")],
        )

    # remove TICKER
    remove_match = re.search(r"remove\s+([a-zA-Z]+)", lower)
    if remove_match:
        ticker = remove_match.group(1).upper()
        return LLMResponse(
            message=f"Removing {ticker} from your watchlist.",
            watchlist_changes=[WatchlistChange(ticker=ticker, action="remove")],
        )

    # portfolio summary
    if "portfolio" in lower:
        cash = portfolio_context.get("cash_balance", 0.0)
        positions = portfolio_context.get("positions", [])
        position_count = len(positions)
        return LLMResponse(
            message=(
                f"Your portfolio: ${cash:,.2f} cash, {position_count} position(s)."
            ),
        )

    # default echo
    return LLMResponse(message=f"Mock response: {message}")
