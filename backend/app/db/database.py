"""Async SQLite database module for FinAlly."""

import json
import uuid
from datetime import datetime

import aiosqlite

from app.db.schema import CREATE_TABLES_SQL, DEFAULT_TICKERS, PRAGMA_STATEMENTS


def _now() -> str:
    return datetime.utcnow().isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


class Database:
    """Async SQLite database wrapper for FinAlly."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def init(self) -> None:
        """Create tables (with WAL mode) and seed with default data if empty."""
        async with aiosqlite.connect(self._db_path) as db:
            # Enable WAL mode so snapshot task and trade handler don't block each other
            for pragma in PRAGMA_STATEMENTS:
                await db.execute(pragma)

            # Create all tables
            for sql in CREATE_TABLES_SQL:
                await db.execute(sql)

            await db.commit()

            # Seed default data if the database is empty
            async with db.execute("SELECT COUNT(*) FROM users_profile") as cursor:
                row = await cursor.fetchone()
                count = row[0] if row else 0

            if count == 0:
                await self._seed(db)
                await db.commit()

    async def _seed(self, db: aiosqlite.Connection) -> None:
        """Insert default user and watchlist entries."""
        now = _now()

        # Default user profile with $30,000 starting cash
        await db.execute(
            "INSERT INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
            ("default", 30000.0, now),
        )

        # Default watchlist tickers
        for ticker in DEFAULT_TICKERS:
            await db.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                (_new_id(), "default", ticker, now),
            )

    # ---------------------------------------------------------------------------
    # User / Cash
    # ---------------------------------------------------------------------------

    async def get_user(self, user_id: str = "default") -> dict | None:
        """Return the user profile dict or None if not found."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT id, cash_balance, created_at FROM users_profile WHERE id = ?",
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    return None
                return dict(row)

    async def update_cash(self, user_id: str, new_balance: float) -> None:
        """Update the cash balance for a user."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
                (new_balance, user_id),
            )
            await db.commit()

    # ---------------------------------------------------------------------------
    # Watchlist
    # ---------------------------------------------------------------------------

    async def get_watchlist(self, user_id: str = "default") -> list[str]:
        """Return the list of ticker strings on the user's watchlist."""
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY added_at ASC",
                (user_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]

    async def add_watchlist_ticker(self, user_id: str, ticker: str) -> None:
        """Add a ticker to the watchlist. Raises ValueError if it already exists."""
        async with aiosqlite.connect(self._db_path) as db:
            try:
                await db.execute(
                    "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                    (_new_id(), user_id, ticker, _now()),
                )
                await db.commit()
            except aiosqlite.IntegrityError as exc:
                raise ValueError(f"Ticker {ticker!r} already in watchlist for user {user_id!r}") from exc

    async def remove_watchlist_ticker(self, user_id: str, ticker: str) -> None:
        """Remove a ticker from the watchlist."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
                (user_id, ticker),
            )
            await db.commit()

    async def count_watchlist(self, user_id: str = "default") -> int:
        """Return the number of tickers in the user's watchlist."""
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM watchlist WHERE user_id = ?",
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    # ---------------------------------------------------------------------------
    # Positions
    # ---------------------------------------------------------------------------

    async def get_positions(self, user_id: str = "default") -> list[dict]:
        """Return list of position dicts: {ticker, quantity, avg_cost, updated_at}."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT ticker, quantity, avg_cost, updated_at FROM positions WHERE user_id = ?",
                (user_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def upsert_position(
        self, user_id: str, ticker: str, quantity: float, avg_cost: float
    ) -> None:
        """Insert or update a position for the user."""
        now = _now()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, ticker)
                DO UPDATE SET quantity = excluded.quantity,
                              avg_cost = excluded.avg_cost,
                              updated_at = excluded.updated_at
                """,
                (_new_id(), user_id, ticker, quantity, avg_cost, now),
            )
            await db.commit()

    async def delete_position(self, user_id: str, ticker: str) -> None:
        """Delete a position row (called when quantity reaches zero)."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
                (user_id, ticker),
            )
            await db.commit()

    # ---------------------------------------------------------------------------
    # Trades
    # ---------------------------------------------------------------------------

    async def insert_trade(
        self,
        user_id: str,
        ticker: str,
        side: str,
        quantity: float,
        price: float,
    ) -> dict:
        """Insert a trade record and return the full trade dict."""
        trade_id = _new_id()
        executed_at = _now()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (trade_id, user_id, ticker, side, quantity, price, executed_at),
            )
            await db.commit()
        return {
            "id": trade_id,
            "user_id": user_id,
            "ticker": ticker,
            "side": side,
            "quantity": quantity,
            "price": price,
            "executed_at": executed_at,
        }

    # ---------------------------------------------------------------------------
    # Portfolio Snapshots
    # ---------------------------------------------------------------------------

    async def insert_portfolio_snapshot(self, user_id: str, total_value: float) -> None:
        """Record a portfolio value snapshot."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at)
                VALUES (?, ?, ?, ?)
                """,
                (_new_id(), user_id, total_value, _now()),
            )
            await db.commit()

    async def get_portfolio_history(
        self, user_id: str = "default", limit: int = 500
    ) -> list[dict]:
        """Return portfolio value snapshots ordered by recorded_at ASC."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT id, user_id, total_value, recorded_at
                FROM portfolio_snapshots
                WHERE user_id = ?
                ORDER BY recorded_at ASC
                LIMIT ?
                """,
                (user_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    # ---------------------------------------------------------------------------
    # Chat Messages
    # ---------------------------------------------------------------------------

    async def get_chat_history(
        self, user_id: str = "default", limit: int = 20
    ) -> list[dict]:
        """Return the last N chat messages ordered by created_at ASC."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            # Fetch the last `limit` rows by ordering DESC, then reverse in Python
            async with db.execute(
                """
                SELECT id, user_id, role, content, actions, created_at
                FROM (
                    SELECT id, user_id, role, content, actions, created_at
                    FROM chat_messages
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                )
                ORDER BY created_at ASC
                """,
                (user_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
                result = []
                for row in rows:
                    record = dict(row)
                    # Deserialize the actions JSON field
                    if record["actions"] is not None:
                        try:
                            record["actions"] = json.loads(record["actions"])
                        except (json.JSONDecodeError, TypeError):
                            record["actions"] = None
                    result.append(record)
                return result

    async def insert_chat_message(
        self,
        user_id: str,
        role: str,
        content: str,
        actions: list | None = None,
    ) -> dict:
        """Insert a chat message and return the full message dict."""
        message_id = _new_id()
        created_at = _now()
        actions_json = json.dumps(actions) if actions is not None else None

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO chat_messages (id, user_id, role, content, actions, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (message_id, user_id, role, content, actions_json, created_at),
            )
            await db.commit()

        return {
            "id": message_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "actions": actions,
            "created_at": created_at,
        }
