# PLAN.md Review

**Reviewer:** reviewer agent
**Date:** 2026-04-08
**Scope:** `planning/PLAN.md` (full document), cross-referenced against `planning/MARKET_DATA_SUMMARY.md` and `planning/archive/MARKET_DATA_REVIEW.md` to reflect the already-completed market data subsystem.

---

## 1. Overall Impression

PLAN.md is a well-structured specification. It is opinionated where it needs to be (single container, SSE, SQLite, market orders only), it contains an explicit "Design Decisions Log" that captures the reasoning for contested choices, and it has a usable API contract in §8. The market data subsystem it describes has already been built and reviewed (see `MARKET_DATA_SUMMARY.md`), and the code in `backend/app/market/` matches the spec closely — that's a strong signal the plan is implementable.

That said, the document still has several internal contradictions, a handful of under-specified areas that will cause downstream agents to guess, and a few decisions that are either over-engineered or under-justified for a "single-user demo with fake money." The issues below are ordered from blocking to minor, and a prioritized fix list appears at the end.

---

## 2. Internal Contradictions (Blocking)

### 2.1 Cash balance: $30,000 vs $10,000

§2 "First Launch" says the user starts with "**$30,000 in virtual cash**", but:

- §7 "users_profile" schema sets `cash_balance REAL (default: 10000.0)`
- §7 "Default Seed Data" repeats `cash_balance=10000.0`
- §12 E2E Tests assert "**$10k balance shown**"

Three sections agree on $10k; §2 is the outlier. This is a direct contradiction that implementing agents will resolve inconsistently — the frontend test suite will fail whichever they pick first. **Fix by picking one number and propagating it.** (The rest of the doc strongly suggests $10,000 is intended.)

### 2.2 SQLite path and volume mount inconsistency

§3 architecture diagram and §4 directory tree both place the SQLite file at `db/finally.db` at the project root, with the top-level `db/` directory as the "volume mount target."

§11 "Launching the App" says the compose file declares "a named volume mounted at **`/app/db`** for SQLite persistence." That is the in-container path, not the repo path — fine on its own. But the plan never tells the backend agent which filesystem path to open. A concrete statement like "the backend opens `${FINALLY_DB_PATH:-/app/db/finally.db}`, and compose mounts the named volume at `/app/db`" would eliminate ambiguity. As written, a backend agent that reads §4 literally will code `db/finally.db` (relative), which will break when the working directory isn't the project root.

### 2.3 `.env` says gitignored, but §9 says it's in the repo

§4 lists `.env` as gitignored with a committed `.env.example`. §9 "LLM Integration" then says plainly: "There is an OPENROUTER_API_KEY in the .env file in the project root." Those two statements can both be true at runtime, but the plan should be clearer that `.env` is an operator-provided file (not a repo artifact), and that `.env.example` is the template agents should create/update. Today, an agent reading §9 in isolation might commit a real key.

### 2.4 Port mapping vs Dockerfile `EXPOSE` are consistent; compose volume mount path is the gap

Not a contradiction, but worth flagging alongside 2.2: the compose snippet in §11 is prose only. A concrete YAML example would remove the remaining guesswork for the DevOps agent.

---

## 3. Missing Details That Will Block Implementers

### 3.1 `GET /api/portfolio` response shape is unspecified

§8 documents the trade endpoint contract in detail but leaves `/api/portfolio` and `/api/portfolio/history` as one-line descriptions. The frontend agent will invent a shape, and the backend agent will invent a different one. At minimum, specify:

```json
{
  "cash_balance": 10000.0,
  "total_value": 12345.67,
  "unrealized_pnl": 234.56,
  "positions": [
    { "ticker": "AAPL", "quantity": 10, "avg_cost": 180.00, "current_price": 190.50, "market_value": 1905.00, "unrealized_pnl": 105.00, "pnl_pct": 5.83 }
  ]
}
```

and for `/api/portfolio/history`:

```json
{ "snapshots": [ { "recorded_at": "...", "total_value": 10000.0 }, ... ] }
```

Without this, the positions table and P&L chart in §10 cannot be built against a known contract.

### 3.2 `/api/chat` request/response shape is not specified

§8 lists the endpoint in one row. §9 describes the *LLM's* structured output but never states the over-the-wire shape of `POST /api/chat`. The plan should specify at least:

- Request: `{ "message": "..." }`
- Response: the LLM `message`, plus the `actions` array with per-item `{type, payload, status, error}`, plus the persisted `chat_messages.id` so the frontend can key react lists.

Also missing: whether `GET /api/chat/history` exists. The frontend chat panel has to populate itself on page load from *something* — either from an initial fetch of history, or from an empty state that starts fresh. §7 describes `chat_messages` storing history "with no truncation," which implies history is persistent and reloadable, but there is no endpoint to read it.

### 3.3 `GET /api/watchlist` response shape is unspecified

§8 says the response includes "latest prices," but is each entry `{ticker, price, previous_price, timestamp}` or just `{ticker, price}`? Does it include sparkline history? (Per §10 the sparkline is accumulated on the frontend from SSE since page load, so the answer should be no — but say so.)

### 3.4 Initial price bootstrapping on page load is ambiguous

§10 says sparklines are "accumulated on the frontend from the SSE stream since page load." With the Massive free tier emitting one event every ~15 seconds (per §6), a user on the real data path sees an **empty** watchlist (no prices, no sparkline, no session-change %) for up to 15 seconds after page load. This is a bad first impression for a "visually stunning" product (§1).

The plan should either:
- Have `/api/watchlist` and `/api/portfolio` return the current price cache snapshot so the UI has data immediately, then SSE takes over for live updates, or
- Have the SSE endpoint emit an immediate "initial snapshot" event on connect (the already-completed stream.py does not do this as far as the spec says).

This ambiguity affects the very first thing the user sees.

### 3.5 Authentication / `user_id` hardcoding

§7 says all tables include `user_id` defaulting to `"default"`. The backend is assumed to be single-user. But the plan never says explicitly: "every backend endpoint reads/writes only `user_id='default'`, and there is no auth middleware." An agent reading §7 might add a query param or header for `user_id`, defeating the simplicity. Be explicit that `user_id` is hardcoded server-side and not a request parameter.

### 3.6 Fractional shares and rounding

§7 allows `quantity REAL` (fractional). §8 says `quantity` is "number strictly greater than 0 (fractional allowed)". But the plan never specifies:
- Rounding precision for stored quantities (e.g., 4 decimal places?)
- Rounding of `avg_cost` after a partial buy (standard weighted average?)
- Rounding of cash balance (2 decimal places?)
- Whether the frontend trade bar accepts decimal input

Float accumulation bugs are a classic source of "I have 9.999999 shares and can't sell 10" errors. Define a precision policy.

### 3.7 Trade execution price source

§8 says the trade fills "at current price" from the price cache, but:
- Does it read `cache.get_price(ticker)` once at the moment the endpoint is hit, or does it snapshot it into the trade row atomically?
- What happens if the cache updates between price read and DB insert? (Fine — you already have the price in a local variable. But say so.)
- What about a staleness check? If the last price update was >30s ago (Massive path during market close?), should the endpoint return `503 price_unavailable` even though there is *a* price? §8 only says `503 price_unavailable` when the cache has "no entry yet," not when the entry is stale.

### 3.8 Portfolio snapshot task semantics

§7 says snapshots are recorded "every 5 minutes by a background task, and immediately after each trade execution." Details missing:
- Does the 5-minute task run continuously from process start, or only when there's activity? (Implication for an idle container.)
- Is the first snapshot recorded at process start, or after 5 minutes?
- What exactly goes into `total_value` — cash + Σ(quantity × current_price)? What if a position's ticker has no cached price? Skip it? Treat as zero? Use last-known?

### 3.9 Ticker symbol normalization and validation

§8 says the trade endpoint uppercases the ticker server-side. But:
- Is there any whitelist/blacklist of allowed tickers, or is every uppercase alpha string accepted?
- When the LLM (§9) adds a ticker to the watchlist, does the backend verify it exists at Massive/the simulator before committing? The simulator only knows the 10 seeded tickers plus whatever has been added — what happens on `add_ticker("PYPL")` for the simulator? (The market data subsystem has `add_ticker`, but does the simulator have a seed price for arbitrary symbols?)

This is a concrete gap: the simulator's `seed_prices.py` has entries for the default 10. What happens when an LLM call or user adds e.g. `PYPL`? The spec should either (a) limit the watchlist to a known ticker list in simulator mode, or (b) specify that arbitrary symbols get a default starting price (e.g., $100) and default GBM params.

### 3.10 Watchlist and positions ticker case sensitivity

§8 uppercases tickers on the trade endpoint. Does the watchlist endpoint do the same? Is `"aapl"` distinct from `"AAPL"` in the DB? The UNIQUE constraint on `(user_id, ticker)` doesn't save you if one entry is lowercase. Normalize on write, everywhere.

### 3.11 LLM mock: ambiguous trigger parsing

§9's mock table says the trigger is `buy <N> <TICKER>`. Concretely, what does the mock do with "I want to buy 10 AAPL please" vs "buy some AAPL"? The spec says "keyed off substrings in the user's message (case-insensitive)" which suggests a regex like `\bbuy\s+(\d+(?:\.\d+)?)\s+([A-Z]+)\b`. Write that regex down — agents and test authors need to agree. Also: what if the message contains multiple matching patterns (e.g., "buy 10 AAPL and sell 5 TSLA")? One action each? First match only? Be explicit.

### 3.12 LLM structured output: schema enforcement

§9 gives a schema sketch but does not say *how* structured output is enforced. The cerebras-inference skill is referenced, but the plan should state: "Use a Pydantic model + LiteLLM's `response_format={'type':'json_schema',...}`" or whatever the chosen mechanism is. Without this, two agents may pick different enforcement approaches (prompt-only vs response_format vs tool-call schemas), and tests that expect a particular failure mode (e.g., `graceful handling of malformed responses`, §12) will be non-deterministic.

### 3.13 SSE and trade/watchlist CRUD interaction

When the user adds a ticker via `POST /api/watchlist`, the backend has to:
1. Insert into the `watchlist` table.
2. Call `source.add_ticker(ticker)` on the market data source.
3. Wait for the price cache to populate? Or return immediately?

Currently undefined. If the endpoint returns before the price is cached, the frontend sees a watchlist entry with no price until the next poll — could be 15s on Massive free tier. Consider: (a) awaiting the first fetch, (b) returning a stub `{price: null}`, or (c) using a seed price immediately for the simulator. Pick one.

### 3.14 No spec for how the backend initializes the market data source at startup

The market data SUMMARY shows the intended usage, but PLAN.md doesn't say whose responsibility it is to kick off `source.start([...])` with the initial watchlist on FastAPI startup, nor how it stays synchronized with DB watchlist changes. A one-paragraph lifecycle description in §6 would close this gap.

---

## 4. Architectural and Consistency Issues

### 4.1 SSE active ticker set vs watchlist

§6 says "The cache's **active ticker set** is the union of the user's watchlist and any tickers held in `positions`." Good. But the SSE payload is described (§6) as "a JSON object keyed by ticker, containing at minimum `ticker`, `price`, and `timestamp` per entry." This means the frontend receives prices for tickers that are *not* in the watchlist (because they're held as positions but removed from the watchlist). The frontend spec in §10 does not say how to handle this: do these tickers appear in the positions table (yes, presumably) but not the watchlist panel (also yes)? Make it explicit that the watchlist panel filters to `watchlist ∩ SSE stream` while the positions table filters to `positions ∩ SSE stream`. Both views read from the same stream.

### 4.2 Connection status: three states vs reality

§2/§13 says "OPEN → green, CONNECTING → yellow, CLOSED → red. No third 'reconnecting' state." This is a clean rule, but `EventSource.readyState` has exactly three values: `0 (CONNECTING)`, `1 (OPEN)`, `2 (CLOSED)`. A disconnect triggers an automatic reconnect which puts readyState back to `CONNECTING` (0) → the indicator goes yellow during reconnection attempts. That is exactly the "reconnecting" state the plan says it doesn't have, just named differently. The spec is technically consistent but the disclaimer is misleading — the indicator *will* flash yellow during reconnects. Consider rewording as "we use CONNECTING to cover both initial connect and auto-reconnect, which is what the browser already does."

### 4.3 Next.js static export vs FastAPI routing

§3 says Next.js is built as a static export and served by FastAPI. This works but has two gotchas not addressed:
- Next.js static export with dynamic routes requires explicit paths. The plan has no dynamic routes in the UI, so probably fine — but state that explicitly to set a boundary for the frontend agent.
- FastAPI needs a catch-all route that serves `index.html` for any non-`/api/*` path so client-side navigation and direct URL access both work. This should be called out in §11 (Docker) or §3 so the backend agent doesn't implement just `StaticFiles(directory=..., html=True)` and discover the SPA fallback is wrong for some paths.

### 4.4 Trade notional cap definition

§9 caps per-trade notional at "20% of current total portfolio value." Define "current total portfolio value":
- Before or after the trade?
- Does it include cash? (Yes, presumably, since the plan uses "total portfolio value" interchangeably with cash + positions in §8.)
- What if total portfolio value is zero (edge case: fresh account with no cash)? A divide-by-zero guard should be spelled out.

Also: with only $10k starting cash, 20% = $2k, which means the default user literally cannot buy a single share of a $3000 stock via chat. That's probably fine but worth noting.

### 4.5 "5 trades per response" guardrail with the LLM Mock

§9 mock contract maps any `buy <N> <TICKER>` substring to a single trade. The guardrail test ("at most 5 trades") therefore can't be exercised against the mock without a bigger mock. If any E2E scenario is expected to test this, add it explicitly to the mock contract (e.g., a "bulk buy" trigger) or to the unit-test plan.

### 4.6 Conversation-history size estimate missing

§9 uses a fixed 20-message window. §9 also says "Cerebras inference is fast enough that a loading indicator is sufficient." Fine. But with no per-message length cap, a chatty user could paste a 50KB message and each of the last 20 turns becomes part of the prompt → 1MB of context. `gpt-oss-120b` has a context window, and Cerebras has its own limits. Add a per-message length cap (e.g., 4KB) at the API layer to bound this.

---

## 5. Risks and Edge Cases Not Addressed

### 5.1 Price cache cold start (repeated)

Covered in 3.4. Biggest UX risk for the Massive path.

### 5.2 Trade during a price flash

If a user types a quantity, sees "estimated notional = $1,900," and hits Buy at the exact millisecond the price updates, the actual fill price can differ from the preview. This is normal slippage but the plan should say: "the trade executes at the price cached at the moment the backend handles the request; the preview is indicative only." Otherwise a user will hit a `500` error (or succeed with a surprising number) and file a bug.

### 5.3 Selling a position that drops from the cache

A user holds TSLA, removes TSLA from the watchlist. §6 correctly says the cache keeps TSLA because it's a position. But: what if the Massive API returns an error for TSLA specifically (delisted, suspended)? The cache stops updating TSLA, the user's portfolio value freezes at the stale price, and a sell might execute at an old price. The plan should define a staleness policy for trades (see 3.7).

### 5.4 Multiple browser tabs

Multiple tabs → multiple SSE connections → no problem (stateless). But multiple tabs → concurrent trade POSTs → SQLite busy errors or lost updates? WAL mode helps reads but doesn't serialize writes. A trade and a snapshot writing simultaneously will still collide. The plan says WAL "so the portfolio-snapshot background task and trade-handler writes don't block each other" — but WAL doesn't eliminate write contention, it reduces *reader/writer* contention. Two writers still serialize. Consider adding "all writes wrap in `BEGIN IMMEDIATE` and retry on SQLITE_BUSY" or similar.

### 5.5 Concurrent chat + trade race

While the LLM is generating, a user could submit a manual trade in the trade bar. When the LLM response arrives and auto-executes its own trades, they race with the manual trade for cash. Both go through the same validator so cash is checked per-trade, but the order is nondeterministic. This is probably fine — document it as expected behavior rather than discovering it as a "bug."

### 5.6 Database migration (future schema changes)

§7 says "No separate migration step" — lazy init creates the schema if it's missing. But if schema evolves (adding a column to `positions`), existing DB volumes break. Out of scope for v1, but acknowledge it as "future work" or explicitly as "not supported — delete the volume to upgrade."

### 5.7 LLM trusted to not hallucinate tickers

Nothing in §9 instructs the LLM to verify tickers before adding them. The mock doesn't either. A user who asks the LLM "find me a good biotech" could get a hallucinated `SYMB` added to the watchlist, which the simulator can't price (see 3.9). Add to the system prompt: "only use tickers from the watchlist or well-known US equities."

---

## 6. Testability

### 6.1 Good parts

The E2E scenario list in §12 is concrete and covers the happy path. `LLM_MOCK=true` is a good design for deterministic E2E. The mock trigger table is documented and (correctly) called out as a contract the tests depend on.

### 6.2 Gaps

- **No SSE test specifics.** §12 lists "SSE resilience: disconnect and verify reconnection" but doesn't say how to induce a disconnect from Playwright. The prior MARKET_DATA_REVIEW already flagged that `stream.py` has no dedicated tests (31% coverage). Consider listing "backend SSE integration test with httpx.AsyncClient" as an explicit test.
- **No guardrail tests.** None of §9's guardrails (≤5 trades, ≤20% notional, `too_many_trades`, `trade_too_large`) appear in the test scenario list. These are the business-critical safety rails — they must be tested, and against the real auto-execution pipeline, not just the validator in isolation.
- **No snapshot cadence test.** The 5-minute snapshot task and the post-trade snapshot both need tests. Verify at least that a snapshot is written immediately after a trade executes.
- **No test of the "action results feed back into next turn's context" claim** (§9). This is the mechanism for LLM self-correction and deserves at least one test.
- **No LLM structured-output failure test.** §12 mentions "graceful handling of malformed responses" but does not specify a mechanism for injecting malformed responses (the mock is by construction always valid). Either add a separate "malformed response" injector or drop the requirement.

### 6.3 Test data isolation

E2E tests share a SQLite file if not careful. The plan's `docker-compose.test.yml` should mount an ephemeral volume (or tmpfs) and reset the DB between test runs. Not specified.

---

## 7. Over-Engineering / Under-Justification

### 7.1 `user_id` column on every table

Justified as "enables future multi-user support without schema migration." But §1 says this is a "capstone project," and §9 says "it's a single-user demo with fake money." Multi-user is not a roadmap item. Carrying `user_id` on every row, every query, every UNIQUE index adds schema surface for a future that isn't planned. On the other hand, it's cheap and the rationale is documented — leaving it as-is is defensible. Flag as "acceptable but reconsider if it complicates the backend agent's implementation."

### 7.2 Guardrails for fake-money trades

§9's 5-trade cap and 20% notional cap are reasonable, but the rationale ("fake money, stakes are zero") in the same section undercuts them. If the stakes are zero, why limit the fun? The real reason is probably: (a) protect the UX from runaway LLM output, (b) keep the portfolio-snapshot cadence tractable. Say that explicitly. Right now the guardrails feel bolted on.

### 7.3 Session-change % anchored to first observed price

§10 says this "keeps the simulator and Massive data paths symmetric and needs no extra backend state." True, but it means:
- Refresh the page → session change % resets to 0
- Two tabs → two different session change percentages
- A user who watches the app for 30 minutes will see a session change % that is *nothing like* the real-day change on their real broker.

This is going to confuse people. Accept it if you must, but document the user-visible quirk more clearly ("Session change % is since page load, not market open").

### 7.4 SQLite journal_mode=WAL for "concurrency"

See 5.4. WAL is cheap to enable and is a good default, but the plan's stated reason ("snapshot task and trade-handler writes don't block each other") is subtly wrong — WAL doesn't make concurrent writers non-blocking; it lets writers not block readers. Two writes still serialize. Consider rewording to "WAL improves read-under-write concurrency for SSE / portfolio endpoints" (which is in the same sentence — just drop the writer/writer claim).

### 7.5 `/api/portfolio/history` as a separate endpoint

Could be rolled into `/api/portfolio` as a `snapshots` field. Not a big deal; the current split is defensible for payload size. Note only for completeness.

---

## 8. Minor Issues, Nits, and Polish

- §2 "First Launch": "(or a provided start script)" — but §4 and §11 explicitly say there are no launch scripts. Delete this parenthetical.
- §4 directory tree shows `finally/` as the root dir but the actual repo is `VSCODE_FINALLY/`. Use a placeholder like `<project-root>/` or match reality.
- §8 Watchlist POST: request body should be `{"ticker": "..."}` — state that explicitly (one-line gap).
- §8 Watchlist soft cap: the word "soft" usually implies "warn but allow." Here it hard-rejects with `409`. Call it a "hard cap" for clarity.
- §9 "Structured Output Schema": say whether `trades` and `watchlist_changes` default to `[]` or may be absent. Pydantic models should have `default_factory=list`.
- §9 mock trigger table uses `<N>` for quantity but doesn't say whether N is integer-only or fractional. With fractional shares supported elsewhere, the mock should accept `buy 0.5 AAPL`.
- §10 "EventSource" — note that native `EventSource` does not support custom headers, which is fine here (same-origin, no auth) but worth knowing if the project ever adds auth.
- §11 "CMD: uvicorn serving FastAPI app" — specify `uvicorn app.main:app --host 0.0.0.0 --port 8000` so the backend agent and Dockerfile agree on the module path.
- §12 "Disconnect and verify reconnection" — pick the mechanism (e.g., Playwright `route.abort()` on the SSE URL? Network offline mode? Server restart?).
- §13 "Design Decisions Log" — add the resolutions from this review (cash balance = $10k, `/api/portfolio` response shape, etc.) after fixing them upstream.
- The word "Massive" is used as the brand name for a Polygon.io wrapper. Add one sentence clarifying this the first time it appears (§3), so new agents don't try to pip-install a package called "massive." The MARKET_DATA_SUMMARY already clarifies this; the main PLAN should too.

---

## 9. Consistency with Completed Market Data Subsystem

Cross-checking §6 against `MARKET_DATA_SUMMARY.md` and the reviewed code:

| PLAN.md §6 claim | Matches delivered code? |
|---|---|
| Abstract interface, two implementations | Yes — `MarketDataSource` ABC, `SimulatorDataSource`, `MassiveDataSource` |
| Simulator uses GBM with correlated moves | Yes — Cholesky-decomposed sector correlation |
| Random "events" 2–5% | Yes — `~0.1%` chance per tick per ticker |
| Seed prices realistic | Yes — `seed_prices.py` |
| PriceCache with version counter | Yes — `cache.py` |
| SSE version-driven emission | Yes — `stream.py` |
| Massive polls REST | Yes — `massive_client.py` |
| `retry: 1000` SSE directive | Yes — per the archive review |

**Discrepancies/risks vs completed code:**
- §6 says the active ticker set is watchlist ∪ positions. The market data subsystem supports `add_ticker`/`remove_ticker`, but the *glue* that keeps this set synchronized with the DB watchlist and positions is not yet written. The plan should explicitly assign this responsibility to the backend agent (in §6 or a new subsection).
- §6 says the SSE emits no heartbeats. The completed `stream.py` matches this. But a 15-second Massive interval with no heartbeats means load balancers / proxies that timeout idle connections after <15s will kill the stream. Not a problem for localhost/Docker-single-container, but worth a line of acknowledgment.
- The archived `MARKET_DATA_REVIEW.md` flagged that `/api/stream/prices` has no integration test (31% coverage on `stream.py`). PLAN.md's §12 should explicitly list an SSE backend test so this gap doesn't persist into the integrated build.

---

## 10. Prioritized Recommendations

**P0 — Fix before any implementer starts (blocking contradictions):**
1. Reconcile the cash balance to $10,000 across §2, §7, §12. (§2.1 above)
2. Define the absolute DB file path the backend opens and how compose mounts it (`/app/db/finally.db`, env-overridable). (§2.2)
3. Specify the `GET /api/portfolio` response shape. (§3.1)
4. Specify the `POST /api/chat` request + response shape, including whether `actions` are embedded and whether an `id` is returned. (§3.2)
5. Decide + document whether chat history is reloaded on page load (add `GET /api/chat/history` if so). (§3.2)
6. Specify the `GET /api/watchlist` response shape. (§3.3)
7. Define how the price cache is warmed before the first UI render so the watchlist isn't blank on the Massive path. (§3.4)
8. Define simulator behavior when an arbitrary ticker (not in `seed_prices.py`) is added via the watchlist or LLM. (§3.9)

**P1 — Fix before the backend agent starts:**
9. Document fractional-share precision and rounding policy (quantity, avg_cost, cash_balance). (§3.6)
10. Document trade price staleness policy (what counts as "stale," when to 503). (§3.7, §5.3)
11. Specify the portfolio-snapshot task lifecycle: start cadence, behavior with missing prices, first-snapshot timing. (§3.8)
12. Specify ticker normalization (uppercase, trim, whitelist?) across all write paths. (§3.10)
13. Explicitly state that `user_id` is hardcoded server-side and never a request parameter. (§3.5)
14. Describe how the backend synchronizes the market-data-source ticker set with the DB watchlist and positions at startup and on CRUD. (§3.13, §3.14, §9 gap)
15. Specify how structured output is enforced (LiteLLM `response_format`, Pydantic model name). (§3.12)
16. Document LLM mock regex grammar precisely, including multi-match behavior. (§3.11)
17. Add a per-chat-message length cap. (§4.6)
18. Correct the WAL wording (readers vs writers). (§5.4, §7.4)

**P2 — Strengthen the testing and UX specs:**
19. Add explicit E2E/unit tests for guardrails (`too_many_trades`, `trade_too_large`). (§6.2)
20. Add a backend SSE integration test to cover the stream router. (§6.2)
21. Pick the "disconnect" mechanism for the SSE reconnection E2E test. (§6.2)
22. Clarify watchlist-panel vs positions-table filtering against the SSE stream. (§4.1)
23. Clarify user-visible meaning of "session change %" and document the page-reload quirk. (§7.3)
24. Define "total portfolio value" precisely for the 20% cap (includes cash, pre-trade, non-zero guard). (§4.4)

**P3 — Polish:**
25. Fix §2 "or a provided start script" (delete). (§8)
26. Use `<project-root>/` instead of `finally/` in §4. (§8)
27. State catch-all SPA fallback requirement in §3/§11. (§4.3)
28. Clarify `.env` vs `.env.example` in §4 and §9. (§2.3)
29. Reword "soft cap" → "hard cap" in §8. (§8)
30. Add a one-liner in §3 explaining that "Massive" is a Polygon.io wrapper. (§8)
31. Add a concrete `docker-compose.yml` YAML example in §11. (§2.4)
32. In §13, add decisions that result from fixing the above, once done.

---

## 11. Summary

PLAN.md is a solid foundation — the architecture is coherent, the design decisions log shows a mature project, and the completed market data subsystem demonstrates the plan is buildable. The review surfaces mostly *gaps and ambiguities* rather than bad decisions. The single biggest risk is the **$10k vs $30k cash contradiction** (trivial to fix but will ship as a bug if unnoticed). The second biggest is **undefined response shapes for the non-trade endpoints**, which will cause frontend/backend agents to drift unless fixed before they start. Everything else is improvable in place.

Once the P0 items are resolved, this document is ready to drive the frontend, backend-api, and LLM agents concurrently.
