"""Shared FastAPI dependency functions for API route handlers."""

from __future__ import annotations

from app.market import PriceCache

# Module-level reference set by main.py at startup
_price_cache: PriceCache | None = None
_market_source = None


def set_price_cache(cache: PriceCache) -> None:
    """Called by main.py during lifespan startup."""
    global _price_cache
    _price_cache = cache


def set_market_source(source) -> None:
    """Called by main.py during lifespan startup."""
    global _market_source
    _market_source = source


def get_price_cache() -> PriceCache:
    """FastAPI dependency: return the application-level PriceCache."""
    if _price_cache is None:
        raise RuntimeError("PriceCache has not been initialised")
    return _price_cache


def get_market_source():
    """FastAPI dependency: return the application-level MarketDataSource."""
    if _market_source is None:
        raise RuntimeError("MarketDataSource has not been initialised")
    return _market_source
