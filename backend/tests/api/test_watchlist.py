"""Unit tests for watchlist API endpoints."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db import Database, set_db
from app.market import PriceCache


# ---------------------------------------------------------------------------
# Stub market source
# ---------------------------------------------------------------------------


class StubMarketSource:
    """Minimal MarketDataSource stub for testing."""

    def __init__(self):
        self.added: list[str] = []
        self.removed: list[str] = []

    async def add_ticker(self, ticker: str) -> None:
        self.added.append(ticker)

    async def remove_ticker(self, ticker: str) -> None:
        self.removed.append(ticker)

    def get_tickers(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db(tmp_path):
    """In-memory (temp file) database seeded with defaults."""
    db_path = str(tmp_path / "test.db")
    database = Database(db_path)
    await database.init()
    set_db(database)
    return database


@pytest.fixture
def price_cache():
    """PriceCache pre-populated with default tickers."""
    cache = PriceCache()
    for ticker, price in [
        ("AAPL", 190.0), ("GOOGL", 175.0), ("MSFT", 420.0),
        ("AMZN", 185.0), ("TSLA", 250.0), ("NVDA", 800.0),
        ("META", 500.0), ("JPM", 200.0), ("V", 275.0), ("NFLX", 640.0),
    ]:
        cache.update(ticker, price)
    return cache


@pytest.fixture
def market_source():
    return StubMarketSource()


@pytest_asyncio.fixture
async def client(db, price_cache, market_source):
    """AsyncClient wired to FastAPI test app."""
    from fastapi import FastAPI

    from app.api.deps import set_market_source, set_price_cache
    from app.api.watchlist import router as watchlist_router

    test_app = FastAPI()
    test_app.include_router(watchlist_router)

    set_price_cache(price_cache)
    set_market_source(market_source)

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# GET /api/watchlist
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_watchlist_returns_default_tickers(client):
    """GET /api/watchlist returns the 10 seeded default tickers."""
    resp = await client.get("/api/watchlist")
    assert resp.status_code == 200
    data = resp.json()
    assert "tickers" in data
    tickers = [item["ticker"] for item in data["tickers"]]
    assert set(tickers) == {"AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"}


@pytest.mark.asyncio
async def test_get_watchlist_enriched_with_prices(client):
    """Each watchlist entry has price data from the cache."""
    resp = await client.get("/api/watchlist")
    assert resp.status_code == 200
    for item in resp.json()["tickers"]:
        assert item["price"] is not None
        assert item["direction"] is not None


@pytest.mark.asyncio
async def test_get_watchlist_null_prices_for_untracked(client, db, price_cache):
    """Tickers added to DB but not in cache have null price fields."""
    await db.add_watchlist_ticker("default", "NEWCORP")
    resp = await client.get("/api/watchlist")
    assert resp.status_code == 200
    entry = next(
        (item for item in resp.json()["tickers"] if item["ticker"] == "NEWCORP"), None
    )
    assert entry is not None
    assert entry["price"] is None
    assert entry["direction"] is None


# ---------------------------------------------------------------------------
# POST /api/watchlist
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_ticker_success(client, market_source):
    """Adding a new ticker returns 201 and notifies the market source."""
    resp = await client.post("/api/watchlist", json={"ticker": "PYPL"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["ticker"] == "PYPL"
    assert "added_at" in data
    assert "PYPL" in market_source.added


@pytest.mark.asyncio
async def test_add_ticker_lowercase_uppercased(client):
    """Ticker is uppercased automatically."""
    resp = await client.post("/api/watchlist", json={"ticker": "pypl"})
    assert resp.status_code == 201
    assert resp.json()["ticker"] == "PYPL"


@pytest.mark.asyncio
async def test_add_ticker_duplicate_is_idempotent(client):
    """Adding an already-present ticker returns 201 without error."""
    resp = await client.post("/api/watchlist", json={"ticker": "AAPL"})
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_add_ticker_empty_string_rejected(client):
    """Empty ticker returns 422 validation error."""
    resp = await client.post("/api/watchlist", json={"ticker": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_add_ticker_over_limit(client, db):
    """Adding beyond 50-ticker limit returns 409 watchlist_full."""
    # The DB already has 10 seeded tickers; add 40 more to hit the cap
    for i in range(40):
        await db.add_watchlist_ticker("default", f"TICK{i:03d}")

    resp = await client.post("/api/watchlist", json={"ticker": "OVERLIMIT"})
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"]["code"] == "watchlist_full"


# ---------------------------------------------------------------------------
# DELETE /api/watchlist/{ticker}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_ticker_success(client, market_source):
    """Removing a watched ticker returns 204 and removes from market source."""
    resp = await client.delete("/api/watchlist/AAPL")
    assert resp.status_code == 204
    assert "AAPL" in market_source.removed


@pytest.mark.asyncio
async def test_delete_ticker_not_removed_from_source_if_held(client, db, market_source):
    """Ticker not removed from market source when an open position exists."""
    # Open a position in AAPL
    await db.upsert_position("default", "AAPL", 10.0, 190.0)

    resp = await client.delete("/api/watchlist/AAPL")
    assert resp.status_code == 204
    # Market source should NOT have been asked to remove AAPL
    assert "AAPL" not in market_source.removed


@pytest.mark.asyncio
async def test_delete_ticker_lowercase_uppercased(client, market_source):
    """Ticker path parameter is uppercased automatically."""
    resp = await client.delete("/api/watchlist/aapl")
    assert resp.status_code == 204
    assert "AAPL" in market_source.removed


@pytest.mark.asyncio
async def test_delete_nonexistent_ticker_still_204(client):
    """Deleting a ticker not in the watchlist still returns 204 (idempotent)."""
    resp = await client.delete("/api/watchlist/DOESNOTEXIST")
    assert resp.status_code == 204
