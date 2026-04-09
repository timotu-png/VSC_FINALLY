"""FastAPI application entrypoint for FinAlly backend."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Load .env from project root (two levels up: backend/app/main.py → backend/ → project root)
_ROOT = Path(__file__).parent.parent.parent
load_dotenv(_ROOT / ".env")

from app.api.chat import router as chat_router  # noqa: E402
from app.api.deps import set_market_source, set_price_cache  # noqa: E402
from app.api.health import router as health_router  # noqa: E402
from app.api.portfolio import router as portfolio_router  # noqa: E402
from app.api.watchlist import router as watchlist_router  # noqa: E402
from app.db import Database, set_db  # noqa: E402
from app.market import PriceCache, create_market_data_source, create_stream_router  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# ---------------------------------------------------------------------------
# Resolve paths from env vars
# ---------------------------------------------------------------------------

_BACKEND_DIR = Path(__file__).parent.parent
DB_PATH = os.environ.get("DB_PATH", str(_ROOT / "db" / "finally.db"))
STATIC_DIR = os.environ.get("STATIC_DIR", str(_BACKEND_DIR / "static"))

# ---------------------------------------------------------------------------
# Snapshot background task
# ---------------------------------------------------------------------------


async def _snapshot_loop(db: Database, price_cache: PriceCache, interval: int = 300) -> None:
    """Record a portfolio snapshot every `interval` seconds (default 5 minutes)."""
    try:
        while True:
            await asyncio.sleep(interval)
            try:
                from app.api.portfolio import _record_snapshot

                await _record_snapshot(db, price_cache)
            except Exception:
                logger.exception("Error in portfolio snapshot background task")
    except asyncio.CancelledError:
        pass


# ---------------------------------------------------------------------------
# FastAPI lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    # --- Startup ---
    logger.info("FinAlly backend starting up")

    # Initialise database
    db = Database(DB_PATH)
    await db.init()
    set_db(db)

    # Initialise price cache and market data source
    price_cache = PriceCache()
    market_source = create_market_data_source(price_cache)

    set_price_cache(price_cache)
    set_market_source(market_source)

    # Initialise LLM client
    try:
        from app.llm import LLMClient, set_llm_client

        llm_client = LLMClient()
        set_llm_client(llm_client)
    except ImportError:
        logger.warning("app.llm not available yet — LLM features disabled")

    # Start market data source with watchlist tickers
    seed_tickers = await db.get_watchlist()
    await market_source.start(seed_tickers)

    # Start portfolio snapshot background task
    snapshot_task = asyncio.create_task(_snapshot_loop(db, price_cache))

    # Attach SSE streaming router (needs the cache to be ready).
    # IMPORTANT: this must be included before the static file mount so that
    # FastAPI's route table resolves /api/stream/prices before the catch-all
    # StaticFiles mount at "/" intercepts it.
    stream_router = create_stream_router(price_cache)
    app.include_router(stream_router)

    # Mount static frontend files here (inside lifespan, after all API routers)
    # so that the static catch-all mount does NOT shadow any API route.
    if os.path.isdir(STATIC_DIR):
        # Only mount once — guard against double-mount if lifespan somehow reruns
        already_mounted = any(
            getattr(r, "path", None) == "/" and getattr(r, "name", None) == "static"
            for r in app.routes
        )
        if not already_mounted:
            app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    else:
        logger.warning("Static directory '%s' not found — frontend not served", STATIC_DIR)

    logger.info("FinAlly backend ready")

    yield  # Application is running

    # --- Shutdown ---
    logger.info("FinAlly backend shutting down")
    snapshot_task.cancel()
    try:
        await snapshot_task
    except asyncio.CancelledError:
        pass

    await market_source.stop()
    logger.info("FinAlly backend stopped")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="FinAlly API",
    description="AI Trading Workstation backend",
    version="0.1.0",
    lifespan=lifespan,
)

# Register API routers
app.include_router(health_router)
app.include_router(portfolio_router)
app.include_router(watchlist_router)
app.include_router(chat_router)

# NOTE: Static file mount is registered inside the lifespan context (above),
# AFTER all API routers, so that /api/* routes are never shadowed by the
# catch-all StaticFiles mount at "/".  Do NOT add a mount here.
