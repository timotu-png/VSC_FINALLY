"""Tests for the FinAlly database module."""

import pytest

from app.db.database import Database
from app.db.schema import DEFAULT_TICKERS


@pytest.fixture
async def db(tmp_path):
    """Create an initialized in-memory database for each test."""
    # Use a temp file per test to avoid shared state; aiosqlite doesn't support ':memory:'
    # across multiple connections, so a tmp_path file gives us isolation.
    db_path = str(tmp_path / "test.db")
    database = Database(db_path)
    await database.init()
    return database


# ---------------------------------------------------------------------------
# Schema / Init
# ---------------------------------------------------------------------------


async def test_tables_created(tmp_path):
    """All expected tables should exist after init."""
    db_path = str(tmp_path / "test.db")
    database = Database(db_path)
    await database.init()

    import aiosqlite

    async with aiosqlite.connect(db_path) as conn:
        async with conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ) as cursor:
            tables = {row[0] for row in await cursor.fetchall()}

    expected = {
        "users_profile",
        "watchlist",
        "positions",
        "trades",
        "portfolio_snapshots",
        "chat_messages",
    }
    assert expected.issubset(tables)


async def test_seed_data_inserted(db: Database):
    """Default user and watchlist tickers should be present after init."""
    user = await db.get_user("default")
    assert user is not None
    assert user["id"] == "default"
    assert user["cash_balance"] == 30000.0

    watchlist = await db.get_watchlist("default")
    assert len(watchlist) == 10
    for ticker in DEFAULT_TICKERS:
        assert ticker in watchlist


async def test_seed_not_duplicated(tmp_path):
    """Calling init twice should not duplicate seed data."""
    db_path = str(tmp_path / "test.db")
    database = Database(db_path)
    await database.init()
    await database.init()  # second call — tables already exist, seed skipped

    watchlist = await database.get_watchlist("default")
    assert len(watchlist) == 10


# ---------------------------------------------------------------------------
# User / Cash
# ---------------------------------------------------------------------------


async def test_get_user_default(db: Database):
    """get_user returns the default user."""
    user = await db.get_user()
    assert user is not None
    assert user["cash_balance"] == 30000.0


async def test_get_user_not_found(db: Database):
    """get_user returns None for an unknown user."""
    result = await db.get_user("nonexistent")
    assert result is None


async def test_update_cash(db: Database):
    """update_cash should persist the new balance."""
    await db.update_cash("default", 12345.67)
    user = await db.get_user("default")
    assert user is not None
    assert abs(user["cash_balance"] - 12345.67) < 1e-6


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------


async def test_add_watchlist_ticker(db: Database):
    """Adding a new ticker increases the watchlist count."""
    before = await db.count_watchlist("default")
    await db.add_watchlist_ticker("default", "PLTR")
    after = await db.count_watchlist("default")
    assert after == before + 1

    watchlist = await db.get_watchlist("default")
    assert "PLTR" in watchlist


async def test_add_duplicate_watchlist_ticker_raises(db: Database):
    """Adding a ticker that already exists raises ValueError."""
    with pytest.raises(ValueError):
        await db.add_watchlist_ticker("default", "AAPL")


async def test_remove_watchlist_ticker(db: Database):
    """Removing a ticker decreases the watchlist count."""
    before = await db.count_watchlist("default")
    await db.remove_watchlist_ticker("default", "AAPL")
    after = await db.count_watchlist("default")
    assert after == before - 1

    watchlist = await db.get_watchlist("default")
    assert "AAPL" not in watchlist


async def test_remove_nonexistent_ticker_is_noop(db: Database):
    """Removing a ticker not in the watchlist does not raise."""
    before = await db.count_watchlist("default")
    await db.remove_watchlist_ticker("default", "NONEXISTENT")
    after = await db.count_watchlist("default")
    assert after == before


async def test_count_watchlist(db: Database):
    """count_watchlist returns the correct count."""
    count = await db.count_watchlist("default")
    assert count == 10


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------


async def test_upsert_position_insert(db: Database):
    """Upserting a new position creates a row."""
    await db.upsert_position("default", "AAPL", 10.0, 150.0)
    positions = await db.get_positions("default")
    aapl = next((p for p in positions if p["ticker"] == "AAPL"), None)
    assert aapl is not None
    assert aapl["quantity"] == 10.0
    assert aapl["avg_cost"] == 150.0


async def test_upsert_position_update(db: Database):
    """Upserting an existing position updates quantity and avg_cost."""
    await db.upsert_position("default", "AAPL", 10.0, 150.0)
    await db.upsert_position("default", "AAPL", 20.0, 160.0)
    positions = await db.get_positions("default")
    aapl = next((p for p in positions if p["ticker"] == "AAPL"), None)
    assert aapl is not None
    assert aapl["quantity"] == 20.0
    assert aapl["avg_cost"] == 160.0


async def test_delete_position(db: Database):
    """Deleting a position removes it from the list."""
    await db.upsert_position("default", "TSLA", 5.0, 200.0)
    await db.delete_position("default", "TSLA")
    positions = await db.get_positions("default")
    assert all(p["ticker"] != "TSLA" for p in positions)


async def test_delete_nonexistent_position_is_noop(db: Database):
    """Deleting a position that doesn't exist does not raise."""
    await db.delete_position("default", "NONEXISTENT")  # should not raise


async def test_get_positions_empty(db: Database):
    """get_positions returns empty list when no positions exist."""
    positions = await db.get_positions("default")
    assert positions == []


# ---------------------------------------------------------------------------
# Trades
# ---------------------------------------------------------------------------


async def test_insert_trade(db: Database):
    """insert_trade returns a complete trade record dict."""
    trade = await db.insert_trade("default", "NVDA", "buy", 3.0, 500.0)

    assert trade["id"] is not None
    assert trade["user_id"] == "default"
    assert trade["ticker"] == "NVDA"
    assert trade["side"] == "buy"
    assert trade["quantity"] == 3.0
    assert trade["price"] == 500.0
    assert trade["executed_at"] is not None


async def test_insert_multiple_trades(db: Database):
    """Multiple trade inserts are each persisted independently."""
    t1 = await db.insert_trade("default", "AAPL", "buy", 10.0, 190.0)
    t2 = await db.insert_trade("default", "AAPL", "sell", 5.0, 195.0)
    assert t1["id"] != t2["id"]
    assert t1["side"] == "buy"
    assert t2["side"] == "sell"


# ---------------------------------------------------------------------------
# Portfolio Snapshots
# ---------------------------------------------------------------------------


async def test_insert_portfolio_snapshot(db: Database):
    """Inserting a snapshot and retrieving history works correctly."""
    await db.insert_portfolio_snapshot("default", 31000.0)
    history = await db.get_portfolio_history("default")
    assert len(history) == 1
    assert abs(history[0]["total_value"] - 31000.0) < 1e-6


async def test_portfolio_history_ordered_asc(db: Database):
    """Portfolio history is returned in ascending chronological order."""
    await db.insert_portfolio_snapshot("default", 30000.0)
    await db.insert_portfolio_snapshot("default", 31000.0)
    await db.insert_portfolio_snapshot("default", 32000.0)

    history = await db.get_portfolio_history("default")
    assert len(history) == 3
    values = [h["total_value"] for h in history]
    assert values == sorted(values)


async def test_portfolio_history_limit(db: Database):
    """get_portfolio_history respects the limit parameter."""
    for i in range(10):
        await db.insert_portfolio_snapshot("default", 30000.0 + i * 100)

    history = await db.get_portfolio_history("default", limit=5)
    assert len(history) == 5


# ---------------------------------------------------------------------------
# Chat Messages
# ---------------------------------------------------------------------------


async def test_insert_chat_message_user(db: Database):
    """Inserting a user chat message returns a valid record."""
    msg = await db.insert_chat_message("default", "user", "Hello, FinAlly!")
    assert msg["id"] is not None
    assert msg["role"] == "user"
    assert msg["content"] == "Hello, FinAlly!"
    assert msg["actions"] is None
    assert msg["created_at"] is not None


async def test_insert_chat_message_assistant_with_actions(db: Database):
    """Inserting an assistant message with actions serializes/deserializes correctly."""
    actions = [{"type": "trade", "payload": {"ticker": "AAPL", "side": "buy", "quantity": 5}, "status": "success", "error": None}]
    msg = await db.insert_chat_message("default", "assistant", "Bought 5 AAPL for you.", actions=actions)
    assert msg["actions"] == actions


async def test_get_chat_history(db: Database):
    """get_chat_history returns messages in chronological order."""
    await db.insert_chat_message("default", "user", "Message 1")
    await db.insert_chat_message("default", "assistant", "Response 1")
    await db.insert_chat_message("default", "user", "Message 2")

    history = await db.get_chat_history("default")
    assert len(history) == 3
    assert history[0]["content"] == "Message 1"
    assert history[1]["content"] == "Response 1"
    assert history[2]["content"] == "Message 2"


async def test_get_chat_history_limit_20(db: Database):
    """get_chat_history returns at most 20 messages by default."""
    for i in range(25):
        await db.insert_chat_message("default", "user", f"Message {i}")

    history = await db.get_chat_history("default")
    assert len(history) == 20


async def test_get_chat_history_limit_20_returns_latest(db: Database):
    """When there are more than 20 messages, the most recent 20 are returned."""
    for i in range(25):
        await db.insert_chat_message("default", "user", f"Message {i}")

    history = await db.get_chat_history("default", limit=20)
    # Should have messages 5-24 (the last 20), in ascending order
    assert history[0]["content"] == "Message 5"
    assert history[-1]["content"] == "Message 24"


async def test_get_chat_history_empty(db: Database):
    """get_chat_history returns empty list when no messages exist."""
    history = await db.get_chat_history("default")
    assert history == []


async def test_chat_actions_deserialized(db: Database):
    """Actions stored as JSON are returned as Python objects."""
    actions = [{"type": "watchlist", "payload": {"ticker": "PLTR", "action": "add"}, "status": "success", "error": None}]
    await db.insert_chat_message("default", "assistant", "Added PLTR to watchlist.", actions=actions)

    history = await db.get_chat_history("default")
    assert len(history) == 1
    assert history[0]["actions"] == actions


# ---------------------------------------------------------------------------
# get_db / set_db dependency
# ---------------------------------------------------------------------------


async def test_get_db_raises_when_not_initialized():
    """get_db raises RuntimeError if set_db has not been called."""
    from app.db import _db as original_db
    import app.db as db_module

    # Temporarily clear _db
    original = db_module._db
    db_module._db = None
    try:
        with pytest.raises(RuntimeError, match="Database not initialized"):
            await db_module.get_db()
    finally:
        db_module._db = original


async def test_set_db_and_get_db(tmp_path):
    """set_db registers the instance; get_db returns it."""
    import app.db as db_module

    original = db_module._db
    db_path = str(tmp_path / "test2.db")
    database = Database(db_path)
    await database.init()

    db_module.set_db(database)
    try:
        result = await db_module.get_db()
        assert result is database
    finally:
        db_module._db = original
