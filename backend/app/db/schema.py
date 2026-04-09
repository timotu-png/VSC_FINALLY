"""SQL schema definitions for FinAlly database."""

PRAGMA_STATEMENTS = [
    "PRAGMA journal_mode=WAL",
    "PRAGMA foreign_keys=ON",
]

CREATE_TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS users_profile (
        id TEXT PRIMARY KEY,
        cash_balance REAL DEFAULT 30000.0,
        created_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS watchlist (
        id TEXT PRIMARY KEY,
        user_id TEXT DEFAULT 'default',
        ticker TEXT,
        added_at TEXT,
        UNIQUE(user_id, ticker)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS positions (
        id TEXT PRIMARY KEY,
        user_id TEXT DEFAULT 'default',
        ticker TEXT,
        quantity REAL,
        avg_cost REAL,
        updated_at TEXT,
        UNIQUE(user_id, ticker)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trades (
        id TEXT PRIMARY KEY,
        user_id TEXT DEFAULT 'default',
        ticker TEXT,
        side TEXT,
        quantity REAL,
        price REAL,
        executed_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS portfolio_snapshots (
        id TEXT PRIMARY KEY,
        user_id TEXT DEFAULT 'default',
        total_value REAL,
        recorded_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chat_messages (
        id TEXT PRIMARY KEY,
        user_id TEXT DEFAULT 'default',
        role TEXT,
        content TEXT,
        actions TEXT,
        created_at TEXT
    )
    """,
]

DEFAULT_TICKERS = [
    "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
    "NVDA", "META", "JPM", "V", "NFLX",
]
