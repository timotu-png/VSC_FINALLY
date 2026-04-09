"""Unit tests for portfolio API endpoints."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db import Database, set_db
from app.market import PriceCache


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
    """PriceCache pre-populated with a few tickers."""
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    cache.update("GOOGL", 175.0)
    cache.update("TSLA", 250.0)
    return cache


@pytest_asyncio.fixture
async def client(db, price_cache):
    """AsyncClient wired to the FastAPI app with injected db + price_cache."""
    from fastapi import FastAPI

    from app.api.deps import set_market_source, set_price_cache
    from app.api.health import router as health_router
    from app.api.portfolio import router as portfolio_router

    test_app = FastAPI()
    test_app.include_router(health_router)
    test_app.include_router(portfolio_router)

    # Inject dependencies
    set_price_cache(price_cache)

    # Minimal market source stub (not needed for portfolio routes)
    class _StubMarketSource:
        async def add_ticker(self, ticker): pass
        async def remove_ticker(self, ticker): pass
        def get_tickers(self): return []

    set_market_source(_StubMarketSource())

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# GET /api/portfolio
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_portfolio_empty(client):
    """Portfolio with no positions returns correct shape and default cash."""
    resp = await client.get("/api/portfolio")
    assert resp.status_code == 200
    data = resp.json()
    assert "positions" in data
    assert "cash_balance" in data
    assert "total_value" in data
    assert "unrealized_pnl" in data
    assert data["positions"] == []
    assert data["cash_balance"] == pytest.approx(30000.0)
    assert data["total_value"] == pytest.approx(30000.0)


@pytest.mark.asyncio
async def test_get_portfolio_with_position(client, db, price_cache):
    """After buying, portfolio reflects position and updated cash."""
    # Buy 10 AAPL at $190 → cost $1900, cash = 28100
    resp = await client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 10, "side": "buy"},
    )
    assert resp.status_code == 200

    resp = await client.get("/api/portfolio")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["positions"]) == 1
    pos = data["positions"][0]
    assert pos["ticker"] == "AAPL"
    assert pos["quantity"] == pytest.approx(10.0)
    assert pos["avg_cost"] == pytest.approx(190.0)
    assert pos["current_price"] == pytest.approx(190.0)
    assert pos["unrealized_pnl"] == pytest.approx(0.0)
    assert data["cash_balance"] == pytest.approx(28100.0)
    # total_value = cash + position = 28100 + 10*190 = 30000
    assert data["total_value"] == pytest.approx(30000.0)


# ---------------------------------------------------------------------------
# POST /api/portfolio/trade — success cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trade_buy_success(client):
    """Buying shares returns correct trade, cash, and position."""
    resp = await client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 5, "side": "buy"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["trade"]["ticker"] == "AAPL"
    assert data["trade"]["side"] == "buy"
    assert data["trade"]["quantity"] == pytest.approx(5.0)
    assert data["trade"]["price"] == pytest.approx(190.0)
    assert data["cash_balance"] == pytest.approx(30000.0 - 5 * 190.0)
    assert data["position"]["ticker"] == "AAPL"
    assert data["position"]["quantity"] == pytest.approx(5.0)


@pytest.mark.asyncio
async def test_trade_sell_success(client):
    """Selling previously bought shares succeeds."""
    await client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 10, "side": "buy"},
    )
    resp = await client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 4, "side": "sell"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["trade"]["side"] == "sell"
    assert data["position"]["quantity"] == pytest.approx(6.0)


@pytest.mark.asyncio
async def test_trade_sell_all_success(client):
    """Selling all shares results in zero position."""
    await client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 10, "side": "buy"},
    )
    resp = await client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 10, "side": "sell"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["position"]["quantity"] == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_trade_buy_avg_cost_recalculation(client):
    """Buying more of the same ticker recalculates average cost correctly."""
    # First buy: 10 @ 190 → avg = 190
    await client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 10, "side": "buy"},
    )
    # Simulate price change
    from app.api.deps import get_price_cache
    get_price_cache().update("AAPL", 200.0)

    # Second buy: 10 @ 200 → avg = (10*190 + 10*200) / 20 = 195
    resp = await client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 10, "side": "buy"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["position"]["avg_cost"] == pytest.approx(195.0)
    assert data["position"]["quantity"] == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# POST /api/portfolio/trade — error cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trade_unknown_ticker(client):
    """Unknown ticker returns 404 unknown_ticker."""
    resp = await client.post(
        "/api/portfolio/trade",
        json={"ticker": "UNKNOWN", "quantity": 1, "side": "buy"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"]["code"] == "unknown_ticker"


@pytest.mark.asyncio
async def test_trade_insufficient_cash(client):
    """Buying more than cash allows returns 409 insufficient_cash."""
    resp = await client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 1000, "side": "buy"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"]["code"] == "insufficient_cash"


@pytest.mark.asyncio
async def test_trade_insufficient_shares(client):
    """Selling more than held returns 409 insufficient_shares."""
    resp = await client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 1, "side": "sell"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"]["code"] == "insufficient_shares"


@pytest.mark.asyncio
async def test_trade_zero_quantity(client):
    """Zero quantity returns 422 validation error."""
    resp = await client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 0, "side": "buy"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_trade_negative_quantity(client):
    """Negative quantity returns 422 validation error."""
    resp = await client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": -5, "side": "buy"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_trade_invalid_side(client):
    """Invalid side returns 422 validation error."""
    resp = await client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 1, "side": "hold"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_trade_ticker_uppercased(client):
    """Lowercase ticker is uppercased by the endpoint."""
    resp = await client.post(
        "/api/portfolio/trade",
        json={"ticker": "aapl", "quantity": 1, "side": "buy"},
    )
    assert resp.status_code == 200
    assert resp.json()["trade"]["ticker"] == "AAPL"


# ---------------------------------------------------------------------------
# GET /api/portfolio/history
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_portfolio_history_empty(client):
    """History returns empty list when no snapshots recorded."""
    resp = await client.get("/api/portfolio/history")
    assert resp.status_code == 200
    data = resp.json()
    assert "snapshots" in data
    assert data["snapshots"] == []


@pytest.mark.asyncio
async def test_get_portfolio_history_after_trade(client, db):
    """History has a snapshot after a trade is executed."""
    await client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 1, "side": "buy"},
    )
    resp = await client.get("/api/portfolio/history")
    assert resp.status_code == 200
    snapshots = resp.json()["snapshots"]
    assert len(snapshots) >= 1
    assert "total_value" in snapshots[0]
    assert "recorded_at" in snapshots[0]
