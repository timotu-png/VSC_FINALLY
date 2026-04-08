# Market Data Component — Code Review

**Date:** 2026-04-08  
**Reviewer:** Claude Code (claude-sonnet-4-6)  
**Scope:** `backend/app/market/`, `backend/tests/market/`, `backend/pyproject.toml`

---

## Summary

The market data subsystem is well-implemented and ready to be integrated into the broader backend. The architecture is clean, the GBM math is correct, and the test suite is comprehensive. All 73 tests pass; linting is clean. A small number of issues are noted below — one minor latent bug, a few spec deviations, and one dependency concern.

---

## Test Results

```
73 passed in 2.69s
```

All tests pass on Python 3.13.7 (exceeds the `>=3.12` requirement).

### Coverage (actual, from this run)

| Module | Coverage |
|---|---|
| `models.py` | 100% |
| `cache.py` | 100% |
| `interface.py` | 100% |
| `seed_prices.py` | 100% |
| `factory.py` | 100% |
| `simulator.py` | 98% |
| `massive_client.py` | 94% |
| `stream.py` | 33% |
| **Overall** | **91%** |

> **Note:** `MARKET_DATA_SUMMARY.md` reports 84% overall coverage and 56% for `massive_client.py`. These figures are outdated — the actual numbers are 91% and 94% respectively. The summary should be updated.

The 33% on `stream.py` is expected: the SSE generator requires an ASGI test client and a running asyncio loop in a way the current test suite doesn't exercise. This is acceptable for the market data phase, but SSE behavior should be covered by E2E tests in `test/`.

---

## Linting

```
ruff check app/ tests/ — All checks passed!
```

Clean. No issues.

---

## Architecture Review

### Strengths

**Strategy pattern is well-executed.** `SimulatorDataSource` and `MassiveDataSource` both implement `MarketDataSource` faithfully. The factory is clean and correctly strips whitespace from the env var before checking for emptiness.

**GBM math is correct.** The Itô-correct form `S(t+dt) = S(t) * exp((μ - σ²/2)dt + σ√dt·Z)` is used (not the naive Euler form). The dt calculation (500ms / trading seconds per year) is sound. Using `math.exp` keeps prices strictly positive — a core GBM guarantee.

**Cholesky correlation is properly implemented.** The correlation matrix is valid (symmetric, positive definite for all correlation values used — all values are in [0.17, 0.6] and the matrix has ones on the diagonal). The rebuild-on-change approach is correct; n < 50 so O(n²) is fine.

**Thread safety is correct.** `PriceCache` uses a single `threading.Lock` wrapping every read and write. The version counter is bumped inside the lock, so readers never see a version advance without a corresponding price update.

**SSE version-gating is correct.** The stream loop compares `cache.version != last_version` before emitting. This avoids sending redundant events between simulator steps and correctly handles the Massive slow-poll case (~1 event per 15s).

**Error resilience.** Both source implementations catch exceptions in their loops and log rather than crash. The Massive client specifically handles `AttributeError`/`TypeError` on malformed snapshots per-ticker, so one bad entry doesn't drop the whole batch.

**Immediate cache seeding on `start()`.** Both implementations populate the cache before returning from `start()`, so the SSE endpoint has data to serve on the very first request. This addresses the cold-start concern from the earlier design review.

---

## Issues Found

### 1. `stream.py` — Module-level router is a latent duplicate-route bug (Minor)

**Severity: Low** — won't affect production (the router is only created once), but will cause silent test pollution.

```python
# stream.py — current code
router = APIRouter(prefix="/api/stream", tags=["streaming"])

def create_stream_router(price_cache: PriceCache) -> APIRouter:
    @router.get("/prices")          # ← registers on the module-level router
    async def stream_prices(...):
        ...
    return router
```

`router` is a module-level singleton. Each call to `create_stream_router()` registers an additional `GET /api/stream/prices` handler on the same router. In production this is called once, so it's harmless. But if tests or future code call it more than once (e.g., to test with different caches), FastAPI will register duplicate routes and the second handler silently shadows the first.

**Fix:** Move the `APIRouter` instantiation inside the factory function:

```python
def create_stream_router(price_cache: PriceCache) -> APIRouter:
    router = APIRouter(prefix="/api/stream", tags=["streaming"])

    @router.get("/prices")
    async def stream_prices(request: Request) -> StreamingResponse:
        ...

    return router
```

---

### 2. SSE payload includes unrequested fields (Spec deviation, benign)

**Severity: Very Low** — more data is sent than the spec requires. Not harmful; costs a few extra bytes per event.

`PriceUpdate.to_dict()` includes `previous_price`, `change`, `change_percent`, and `direction` in the SSE payload. PLAN.md §6 states:

> "The frontend computes change direction and deltas locally from the accumulated stream — `previous_price` is not required on the wire."

The extra fields don't break anything and may actually be convenient for the frontend to use directly. However, the frontend should not *depend* on them, since the spec says it computes these locally. This is fine to leave as-is but should be documented as a deliberate deviation so the frontend engineer knows the data is available.

---

### 3. `massive` package is an unconditional main dependency (Dependency concern)

**Severity: Low**

```toml
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "numpy>=2.0.0",
    "massive>=1.0.0",    # ← always installed
    "rich>=13.0.0",
]
```

The `massive` package (Polygon.io client) is installed in every environment, including the Docker image, even when `MASSIVE_API_KEY` is not set and the Simulator is used. This adds an unused dependency to the production image.

The import in `massive_client.py` is now at the top level (a previous review fixed lazy imports), so the package must be present at import time. Since the file is always imported via `factory.py` → `from .massive_client import MassiveDataSource`.

**Options (in order of preference):**
1. Accept it — `massive` is small and this is a demo app. Simplest.
2. Move `massive` to an optional dependency group `[project.optional-dependencies] massive = ["massive>=1.0.0"]` and restore lazy imports in `massive_client.py` behind a `TYPE_CHECKING` guard. More complex.

For a demo/course project, option 1 is recommended.

---

### 4. TSLA appears in `CORRELATION_GROUPS["tech"]` but is special-cased away (Confusing, not wrong)

**Severity: Cosmetic**

```python
CORRELATION_GROUPS = {
    "tech": {"AAPL", "GOOGL", "MSFT", "AMZN", "META", "NVDA", "NFLX"},  # TSLA absent ✓
    "finance": {"JPM", "V"},
}
```

Actually, checking `seed_prices.py` — TSLA is *not* in the tech set. The earlier design documents mentioned this as a concern but it was correctly resolved. The code is fine. Ignore this item.

---

### 5. `conftest.py` — vestigial fixture (Cosmetic)

```python
@pytest.fixture
def event_loop_policy():
    """Use the default event loop policy for all async tests."""
    import asyncio
    return asyncio.DefaultEventLoopPolicy()
```

This fixture is never used by any test. `pytest-asyncio` with `asyncio_mode = "auto"` handles event loop setup via config, not fixtures. The fixture can be deleted.

---

### 6. `MARKET_DATA_SUMMARY.md` coverage numbers are stale (Documentation)

The summary states 84% overall coverage and 56% for `massive_client.py`. Current measured values are 91% and 94%. The summary should be updated to reflect the actual state.

---

## Integration Readiness Checklist

These are not bugs in the market data code — they are things the next agent must handle when wiring up the full FastAPI application.

| Item | Status | Notes |
|---|---|---|
| `create_stream_router(cache)` wired into FastAPI app | ⏳ Pending | Returns an `APIRouter`; app must `include_router()` it |
| `create_market_data_source(cache)` called on startup | ⏳ Pending | Must `await source.start(watchlist_tickers)` in FastAPI lifespan |
| `source.stop()` called on shutdown | ⏳ Pending | Use FastAPI `lifespan` context manager |
| Active ticker set = watchlist ∪ positions | ⏳ Pending | PLAN.md §6 — portfolio tickers must be added to source even if not on watchlist |
| Watchlist add/remove syncs to `source.add_ticker/remove_ticker` | ⏳ Pending | Trade handler must also call `source.add_ticker` for newly acquired positions |
| Static frontend served by FastAPI | ⏳ Pending | Out of scope for market data component |

---

## Verdict

**Approved for integration.** The market data subsystem is production-quality code for the scope of this project. The one actionable bug (module-level router) is low-risk and easy to fix. The other findings are cosmetic or accepted trade-offs for a demo application.

Recommended actions before closing out this component:

1. Fix the `create_stream_router` module-level router bug (5-minute fix).
2. Delete the unused `event_loop_policy` fixture in `conftest.py`.
3. Update `MARKET_DATA_SUMMARY.md` coverage numbers (91% overall, 94% massive_client).

Everything else can be left as-is.
