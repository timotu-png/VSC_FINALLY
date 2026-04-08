# FinAlly — AI Trading Workstation

## Project Specification

## 1. Vision

FinAlly (Finance Ally) is a visually stunning AI-powered trading workstation that streams live market data, lets users trade a simulated portfolio, and integrates an LLM chat assistant that can analyze positions and execute trades on the user's behalf. It looks and feels like a modern Bloomberg terminal with an AI copilot.

This is the capstone project for an agentic AI coding course. It is built entirely by Coding Agents demonstrating how orchestrated AI agents can produce a production-quality full-stack application. Agents interact through files in `planning/`.

## 2. User Experience

### First Launch

The user runs a single Docker command (or a provided start script). A browser opens to `http://localhost:8000`. No login, no signup. They immediately see:

- A watchlist of 10 default tickers with live-updating prices in a grid
- $30,000 in virtual cash
- A dark, data-rich trading terminal aesthetic
- An AI chat panel ready to assist

### What the User Can Do

- **Watch prices stream** — prices flash green (uptick) or red (downtick) with subtle CSS animations that fade
- **View sparkline mini-charts** — price action beside each ticker in the watchlist, accumulated on the frontend from the SSE stream since page load (sparklines fill in progressively)
- **Click a ticker** to see a larger detailed chart in the main chart area
- **Buy and sell shares** — market orders only, instant fill at current price, no fees, no confirmation dialog
- **Monitor their portfolio** — a heatmap (treemap) showing positions sized by weight and colored by P&L, plus a P&L chart tracking total portfolio value over time
- **View a positions table** — ticker, quantity, average cost, current price, unrealized P&L, % change
- **Chat with the AI assistant** — ask about their portfolio, get analysis, and have the AI execute trades and manage the watchlist through natural language
- **Manage the watchlist** — add/remove tickers manually or via the AI chat

### Visual Design

- **Dark theme**: backgrounds around `#0d1117` or `#1a1a2e`, muted gray borders, no pure black
- **Price flash animations**: brief green/red background highlight on price change, fading over ~500ms via CSS transitions
- **Connection status indicator**: a small colored dot in the header driven directly by `EventSource.readyState` — OPEN → green, CONNECTING → yellow, CLOSED → red. No custom reconnection bookkeeping.
- **Professional, data-dense layout**: inspired by Bloomberg/trading terminals — every pixel earns its place
- **Responsive but desktop-first**: optimized for wide screens, functional on tablet

### Color Scheme
- Accent Yellow: `#ecad0a`
- Blue Primary: `#209dd7`
- Purple Secondary: `#753991` (submit buttons)

## 3. Architecture Overview

### Single Container, Single Port

```
┌─────────────────────────────────────────────────┐
│  Docker Container (port 8000)                   │
│                                                 │
│  FastAPI (Python/uv)                            │
│  ├── /api/*          REST endpoints             │
│  ├── /api/stream/*   SSE streaming              │
│  └── /*              Static file serving         │
│                      (Next.js export)            │
│                                                 │
│  SQLite database (volume-mounted)               │
│  Background task: market data polling/sim        │
└─────────────────────────────────────────────────┘
```

- **Frontend**: Next.js with TypeScript, built as a static export (`output: 'export'`), served by FastAPI as static files
- **Backend**: FastAPI (Python), managed as a `uv` project
- **Database**: SQLite, single file at `db/finally.db`, volume-mounted for persistence
- **Real-time data**: Server-Sent Events (SSE) — simpler than WebSockets, one-way server→client push, works everywhere
- **AI integration**: LiteLLM → OpenRouter (Cerebras for fast inference), with structured outputs for trade execution
- **Market data**: Environment-variable driven — simulator by default, real data via Massive API if key provided

### Why These Choices

| Decision | Rationale |
|---|---|
| SSE over WebSockets | One-way push is all we need; simpler, no bidirectional complexity, universal browser support |
| Static Next.js export | Single origin, no CORS issues, one port, one container, simple deployment |
| SQLite over Postgres | No auth = no multi-user = no need for a database server; self-contained, zero config |
| Single Docker container | Students run one command; no docker-compose for production, no service orchestration |
| uv for Python | Fast, modern Python project management; reproducible lockfile; what students should learn |
| Market orders only | Eliminates order book, limit order logic, partial fills — dramatically simpler portfolio math |

---

## 4. Directory Structure

```
finally/
├── frontend/                 # Next.js TypeScript project (static export)
├── backend/                  # FastAPI uv project (Python)
│   └── db/                   # Schema definitions, seed data, migration logic
├── planning/                 # Project-wide documentation for agents
│   ├── PLAN.md               # This document
│   └── ...                   # Additional agent reference docs
├── test/                     # Playwright E2E tests + docker-compose.test.yml
├── db/                       # Volume mount target (SQLite file lives here at runtime)
│   └── .gitkeep              # Directory exists in repo; finally.db is gitignored
├── Dockerfile                # Multi-stage build (Node → Python)
├── docker-compose.yml        # Canonical launcher — `docker compose up` starts the app
├── .env                      # Environment variables (gitignored, .env.example committed)
└── .gitignore
```

### Key Boundaries

- **`frontend/`** is a self-contained Next.js project. It knows nothing about Python. It talks to the backend via `/api/*` endpoints and `/api/stream/*` SSE endpoints. Internal structure is up to the Frontend Engineer agent.
- **`backend/`** is a self-contained uv project with its own `pyproject.toml`. It owns all server logic including database initialization, schema, seed data, API routes, SSE streaming, market data, and LLM integration. Internal structure is up to the Backend/Market Data agents.
- **`backend/db/`** contains schema SQL definitions and seed logic. The backend lazily initializes the database on first request — creating tables and seeding default data if the SQLite file doesn't exist or is empty.
- **`db/`** at the top level is the runtime volume mount point. The SQLite file (`db/finally.db`) is created here by the backend and persists across container restarts via Docker volume.
- **`planning/`** contains project-wide documentation, including this plan. All agents reference files here as the shared contract.
- **`test/`** contains Playwright E2E tests and supporting infrastructure (e.g., `docker-compose.test.yml`). Unit tests live within `frontend/` and `backend/` respectively, following each framework's conventions.
- **`docker-compose.yml`** is the single canonical launcher — cross-platform, idempotent, wires up the volume/env/port declaratively. No separate shell/PowerShell launch scripts.

---

## 5. Environment Variables

```bash
# Required: OpenRouter API key for LLM chat functionality
OPENROUTER_API_KEY=your-openrouter-api-key-here

# Optional: Massive (Polygon.io) API key for real market data
# If not set, the built-in market simulator is used (recommended for most users)
MASSIVE_API_KEY=

# Optional: Set to "true" for deterministic mock LLM responses (testing)
LLM_MOCK=false
```

### Behavior

- If `MASSIVE_API_KEY` is set and non-empty → backend uses Massive REST API for market data
- If `MASSIVE_API_KEY` is absent or empty → backend uses the built-in market simulator
- If `LLM_MOCK` equals the literal string `"true"` (case-insensitive) → backend returns deterministic mock LLM responses. Any other value (including empty, unset, `"false"`, `"0"`, etc.) → real LLM calls via OpenRouter.
- The backend reads `.env` from the project root (mounted into the container or read via docker `--env-file`)

---

## 6. Market Data

### Two Implementations, One Interface

Both the simulator and the Massive client implement the same abstract interface. The backend selects which to use based on the environment variable. All downstream code (SSE streaming, price cache, frontend) is agnostic to the source.

### Simulator (Default)

- Generates prices using geometric Brownian motion (GBM) with configurable drift and volatility per ticker
- Updates at ~500ms intervals
- Correlated moves across tickers (e.g., tech stocks move together)
- Occasional random "events" — sudden 2-5% moves on a ticker for drama
- Starts from realistic seed prices (e.g., AAPL ~$190, GOOGL ~$175, etc.)
- Runs as an in-process background task — no external dependencies

### Massive API (Optional)

- REST API polling (not WebSocket) — simpler, works on all tiers
- Polls for the union of all watched tickers on a configurable interval
- Free tier (5 calls/min): poll every 15 seconds
- Paid tiers: poll every 2-15 seconds depending on tier
- Parses REST response into the same format as the simulator

### Shared Price Cache

- A single background task (simulator or Massive poller) writes to an in-memory price cache
- The cache holds the latest price, previous price, timestamp, and a monotonic version counter (incremented on every update) used for SSE change detection
- The cache's **active ticker set** is the union of the user's watchlist and any tickers held in `positions`. Removing a ticker from the watchlist does **not** drop it from the data source if there is still an open position — the portfolio still needs live prices to value it.
- SSE streams read from this cache and push updates to connected clients
- This architecture supports future multi-user scenarios without changes to the data layer

### SSE Streaming

- Endpoint: `GET /api/stream/prices`
- Long-lived SSE connection; client uses native `EventSource` API
- The stream loop wakes every ~500ms and checks the price cache's version counter. If the version has advanced since the last send, it pushes a snapshot of all tracked prices; otherwise it sleeps again. This means: with the simulator (updates ~500ms) clients see ~2 events/sec; with the Massive free tier (polls ~15s) clients see an event roughly every 15s. No empty heartbeat events are sent between updates.
- Each SSE event payload is a JSON object keyed by ticker, containing at minimum `ticker`, `price`, and `timestamp` per entry. The frontend computes change direction and deltas locally from the accumulated stream — `previous_price` is not required on the wire (the cache keeps it internally for direction detection).
- The stream emits a `retry: 1000` directive on connect so the browser auto-reconnects within ~1s on disconnection (EventSource built-in behavior).

---

## 7. Database

### SQLite with Lazy Initialization

The backend checks for the SQLite database on startup (or first request). If the file doesn't exist or tables are missing, it creates the schema and seeds default data. This means:

- No separate migration step
- No manual database setup
- Fresh Docker volumes start with a clean, seeded database automatically
- During lazy init the backend sets `PRAGMA journal_mode=WAL` so the portfolio-snapshot background task and trade-handler writes don't block each other. WAL also improves read concurrency for the SSE/portfolio endpoints.

### Schema

All tables include a `user_id` column defaulting to `"default"`. This is hardcoded for now (single-user) but enables future multi-user support without schema migration.

**users_profile** — User state (cash balance)
- `id` TEXT PRIMARY KEY (default: `"default"`)
- `cash_balance` REAL (default: `10000.0`)
- `created_at` TEXT (ISO timestamp)

**watchlist** — Tickers the user is watching
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `added_at` TEXT (ISO timestamp)
- UNIQUE constraint on `(user_id, ticker)`

**positions** — Current holdings (one row per ticker per user)
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `quantity` REAL (fractional shares supported)
- `avg_cost` REAL
- `updated_at` TEXT (ISO timestamp)
- UNIQUE constraint on `(user_id, ticker)`

**trades** — Trade history (append-only log)
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `side` TEXT (`"buy"` or `"sell"`)
- `quantity` REAL (fractional shares supported)
- `price` REAL
- `executed_at` TEXT (ISO timestamp)

**portfolio_snapshots** — Portfolio value over time (for P&L chart). Recorded every 5 minutes by a background task, and immediately after each trade execution. 5-minute cadence keeps row growth tractable (~288 rows/day) without any downsampling logic; it is plenty of resolution for a visually interesting P&L chart.
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `total_value` REAL
- `recorded_at` TEXT (ISO timestamp)

**chat_messages** — Conversation history with LLM. No truncation — growth is bounded in practice by a single-user demo and rows are small; accepted risk.
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `role` TEXT (`"user"` or `"assistant"`)
- `content` TEXT
- `actions` TEXT (JSON — for assistant messages, a list of the actions the LLM requested with their execution result. Each entry has the form `{"type": "trade"|"watchlist", "payload": {...}, "status": "success"|"error", "error": "…"|null}`. Null for user messages.)
- `created_at` TEXT (ISO timestamp)

### Default Seed Data

- One user profile: `id="default"`, `cash_balance=10000.0`
- Ten watchlist entries: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX

---

## 8. API Endpoints

### Market Data
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stream/prices` | SSE stream of live price updates |

### Portfolio
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/portfolio` | Current positions, cash balance, total value, unrealized P&L |
| POST | `/api/portfolio/trade` | Execute a trade: `{ticker, quantity, side}` |
| GET | `/api/portfolio/history` | Portfolio value snapshots over time (for P&L chart) |

#### `POST /api/portfolio/trade` contract

Request body:
```json
{ "ticker": "AAPL", "quantity": 10, "side": "buy" }
```

- `ticker` — non-empty string, uppercased server-side, must be present in the price cache
- `quantity` — number strictly greater than 0 (fractional allowed); negative or zero is rejected
- `side` — exactly `"buy"` or `"sell"`

Success response (`200 OK`):
```json
{
  "trade": { "id": "...", "ticker": "AAPL", "side": "buy", "quantity": 10, "price": 190.50, "executed_at": "..." },
  "cash_balance": 8095.00,
  "position": { "ticker": "AAPL", "quantity": 10, "avg_cost": 190.50 }
}
```

Error responses use a uniform shape `{ "error": { "code": "...", "message": "..." } }`:
- `400 bad_request` — malformed JSON, missing fields, non-positive quantity, unknown side
- `404 unknown_ticker` — ticker not tracked by the price cache
- `409 insufficient_cash` — buy order exceeds available cash
- `409 insufficient_shares` — sell order exceeds current position quantity
- `503 price_unavailable` — price cache has no entry yet for an otherwise-valid ticker

The same validation path is shared by manual trades and LLM-initiated trades (§9).

### Watchlist
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/watchlist` | Current watchlist tickers with latest prices |
| POST | `/api/watchlist` | Add a ticker: `{ticker}` |
| DELETE | `/api/watchlist/{ticker}` | Remove a ticker |

The watchlist has a soft cap of **50 tickers**. Adds beyond that cap return `409 watchlist_full`. This protects the Massive free tier (5 calls/min) from pathological LLM behavior that would otherwise blow out the polling budget.

### Chat
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Send a message, receive complete JSON response (message + executed actions) |

### System
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check (for Docker/deployment) |

---

## 9. LLM Integration

When writing code to make calls to LLMs, use cerebras-inference skill to use LiteLLM via OpenRouter to the `openrouter/openai/gpt-oss-120b` model with Cerebras as the inference provider. Structured Outputs should be used to interpret the results.

There is an OPENROUTER_API_KEY in the .env file in the project root.

### How It Works

When the user sends a chat message, the backend:

1. Loads the user's current portfolio context (cash, positions with P&L, watchlist with live prices, total portfolio value)
2. Loads the **last 20 messages** from the `chat_messages` table (fixed window — simple, bounded prompt size, no token-budget math needed)
3. Constructs a prompt with a system message, portfolio context, conversation history, and the user's new message
4. Calls the LLM via LiteLLM → OpenRouter, requesting structured output, using the cerebras-inference skill
5. Parses the complete structured JSON response
6. Auto-executes any trades or watchlist changes specified in the response, recording a per-action result (success or validation error) for each
7. Stores the user message and the assistant message (with its `actions` result array) in `chat_messages`
8. Returns the complete response to the frontend in a single payload (no token-by-token streaming — Cerebras inference is fast enough that a loading indicator is sufficient)

### Structured Output Schema

The LLM is instructed to respond with JSON matching this schema:

```json
{
  "message": "Your conversational response to the user",
  "trades": [
    {"ticker": "AAPL", "side": "buy", "quantity": 10}
  ],
  "watchlist_changes": [
    {"ticker": "PYPL", "action": "add"}
  ]
}
```

- `message` (required): The conversational text shown to the user
- `trades` (optional): Array of trades to auto-execute. Each trade goes through the same validation as manual trades (sufficient cash for buys, sufficient shares for sells)
- `watchlist_changes` (optional): Array of watchlist modifications

### Auto-Execution

Trades specified by the LLM execute automatically — no confirmation dialog. This is a deliberate design choice:
- It's a simulated environment with fake money, so the stakes are zero
- It creates an impressive, fluid demo experience
- It demonstrates agentic AI capabilities — the core theme of the course

**Guardrails** (enforced server-side, regardless of what the LLM returns):
- At most **5 trades** per assistant response. Any extras are dropped with a `too_many_trades` error recorded on the dropped entries.
- Per-trade notional capped at **20% of current total portfolio value**. Exceeding this is rejected with `trade_too_large`.
- Every trade is re-run through the same validation used by `POST /api/portfolio/trade` (positive quantity, known ticker, sufficient cash/shares).

**Failure handling — single-LLM-call model.** Validation runs after the LLM has already produced its conversational `message`, so we do **not** re-prompt the LLM. Instead, each action's result (success or specific error code) is attached to the action in the response payload. The frontend renders:
- The LLM's `message` as the assistant bubble
- Below it, one small system-attributed line per action: a green confirmation for successes, a red "⚠ could not execute — {reason}" for failures

No second LLM call, no hidden failures. The LLM's next turn sees the action results in its conversation-history context (serialized into the prior assistant message), so it can self-correct in the following exchange if the user follows up.

**Rate limiting.** `/api/chat` is **not** rate-limited in the core build. A caller hammering the endpoint could rapidly thrash the portfolio, but this is a single-user demo with fake money — accepted risk, documented here rather than engineered around.

### System Prompt Guidance

The LLM should be prompted as "FinAlly, an AI trading assistant" with instructions to:
- Analyze portfolio composition, risk concentration, and P&L
- Suggest trades with reasoning
- Execute trades when the user asks or agrees
- Manage the watchlist proactively
- Be concise and data-driven in responses
- Always respond with valid structured JSON

### LLM Mock Mode

When `LLM_MOCK=true`, the backend returns deterministic mock responses instead of calling OpenRouter. This enables:
- Fast, free, reproducible E2E tests
- Development without an API key
- CI/CD pipelines

**Mock contract.** The mock is a simple rule-based responder, keyed off substrings in the user's message (case-insensitive). E2E tests rely on this contract — do not change it without updating the tests.

| Trigger substring | Mock behavior |
|---|---|
| `buy <N> <TICKER>` | Returns a `message` confirming the buy and a single `trades` entry `{ticker, side: "buy", quantity: N}` |
| `sell <N> <TICKER>` | Returns a `message` confirming the sell and a single `trades` entry `{ticker, side: "sell", quantity: N}` |
| `add <TICKER>` | Returns a `message` and a `watchlist_changes` entry `{ticker, action: "add"}` |
| `remove <TICKER>` | Returns a `message` and a `watchlist_changes` entry `{ticker, action: "remove"}` |
| `portfolio` | Returns a `message` summarizing cash + position count from the injected context, no actions |
| anything else | Returns `message: "Mock response: <echo of user message>"`, no actions |

Mock responses are produced synchronously with no network I/O. The mock still goes through the same auto-execution pipeline and guardrails so tests exercise the real trade path.

---

## 10. Frontend Design

### Layout

The frontend is a single-page application with a dense, terminal-inspired layout. The specific component architecture and layout system is up to the Frontend Engineer, but the UI should include these elements:

- **Watchlist panel** — grid/table of watched tickers with: ticker symbol, current price (flashing green/red on change), session change %, and a sparkline mini-chart (accumulated from SSE since page load). "Session change %" is anchored to the **first price observed by the frontend since page load** — not a true trading-day open. This keeps the simulator and Massive data paths symmetric and needs no extra backend state.
- **Main chart area** — larger chart for the currently selected ticker, with at minimum price over time. Clicking a ticker in the watchlist selects it here. The selected ticker is **frontend-only state** (React state + URL hash for shareability); the backend has no `selected_ticker` concept.
- **Portfolio heatmap** — treemap visualization where each rectangle is a position, sized by portfolio weight, colored by P&L (green = profit, red = loss)
- **P&L chart** — line chart showing total portfolio value over time, using data from `portfolio_snapshots`
- **Positions table** — tabular view of all positions: ticker, quantity, avg cost, current price, unrealized P&L, % change
- **Trade bar** — input area with ticker field, quantity field, buy button, sell button. Market orders, instant fill. Before submission the trade bar shows a live preview: the current price for the typed ticker (pulled from the SSE cache) and the estimated notional (`quantity × price`). If the ticker is unknown or the quantity is invalid, the buy/sell buttons are disabled.
- **AI chat panel** — docked/collapsible sidebar. Message input, scrolling conversation history, loading indicator while waiting for LLM response. For each assistant message the UI renders the `message` text followed by one small status line per action in `actions`: green check for successes, red warning with the error message for failures.
- **Header** — portfolio total value (updating live), connection status indicator, cash balance

### Technical Notes

- Use `EventSource` for SSE connection to `/api/stream/prices`
- **Single charting library: Lightweight Charts** (canvas-based, from TradingView). Used for the main chart, the watchlist sparklines, and the P&L chart — one dependency, consistent look, good performance. The heatmap/treemap is a separate concern; use `d3-hierarchy` + plain SVG for it (too specialized for Lightweight Charts).
- Price flash effect: on receiving a new price, briefly apply a CSS class with background color transition, then remove it
- All API calls go to the same origin (`/api/*`) — no CORS configuration needed
- Tailwind CSS for styling with a custom dark theme

---

## 11. Docker & Deployment

### Multi-Stage Dockerfile

```
Stage 1: Node 20 slim
  - Copy frontend/
  - npm install && npm run build (produces static export)

Stage 2: Python 3.12 slim
  - Install uv
  - Copy backend/
  - uv sync (install Python dependencies from lockfile)
  - Copy frontend build output into a static/ directory
  - Expose port 8000
  - CMD: uvicorn serving FastAPI app
```

FastAPI serves the static frontend files and all API routes on port 8000.

### Launching the App

A single `docker-compose.yml` at the project root is the canonical launcher. It declares:
- the image build (from the `Dockerfile`)
- port mapping `8000:8000`
- a named volume mounted at `/app/db` for SQLite persistence
- `env_file: .env` for `OPENROUTER_API_KEY` / `MASSIVE_API_KEY` / `LLM_MOCK`

The README's entire "run it" section is:

```bash
docker compose up        # start (builds on first run)
docker compose down      # stop (volume persists)
```

Compose is cross-platform (Mac/Linux/Windows), idempotent, and handles every piece of wiring declaratively. No separate shell or PowerShell scripts.

---

## 12. Testing Strategy

### Unit Tests (within `frontend/` and `backend/`)

**Backend (pytest)**:
- Market data: simulator generates valid prices, GBM math is correct, Massive API response parsing works, both implementations conform to the abstract interface
- Portfolio: trade execution logic, P&L calculations, edge cases (selling more than owned, buying with insufficient cash, selling at a loss)
- LLM: structured output parsing handles all valid schemas, graceful handling of malformed responses, trade validation within chat flow
- API routes: correct status codes, response shapes, error handling

**Frontend (React Testing Library or similar)**:
- Component rendering with mock data
- Price flash animation triggers correctly on price changes
- Watchlist CRUD operations
- Portfolio display calculations
- Chat message rendering and loading state

### E2E Tests (in `test/`)

**Infrastructure**: A separate `docker-compose.test.yml` in `test/` that spins up the app container plus a Playwright container. This keeps browser dependencies out of the production image.

**Environment**: Tests run with `LLM_MOCK=true` by default for speed and determinism.

**Key Scenarios**:
- Fresh start: default watchlist appears, $10k balance shown, prices are streaming
- Add and remove a ticker from the watchlist
- Buy shares: cash decreases, position appears, portfolio updates
- Sell shares: cash increases, position updates or disappears
- Portfolio visualization: heatmap renders with correct colors, P&L chart has data points
- AI chat (mocked): send a message, receive a response, trade execution appears inline
- SSE resilience: disconnect and verify reconnection

---

## 13. Design Decisions Log

Key resolutions from the doc_review pass. All have been incorporated into the sections above; this log records the reasoning in one place.

- **SSE cadence is version-driven, not time-driven.** The stream loop polls the cache every ~500ms but only emits when the cache version advances. Simulator → ~2 events/s; Massive free tier → ~1 event / 15s. (§6)
- **Active ticker set = watchlist ∪ positions.** Removing a watchlist entry that is still held does not drop the ticker from the data source. (§6)
- **Session change %** is anchored to the first price observed by the frontend since page load — no "open" price from the backend. Keeps simulator and Massive paths symmetric. (§10)
- **Chat failure handling: single LLM call.** The LLM's `message` is shown as-is; per-action success/error results are attached and rendered as small system-attributed status lines under the bubble. No re-prompt, no silent failures. (§9)
- **Conversation window: last 20 messages.** Fixed, simple, no token-budget math. (§9)
- **Auto-execution guardrails:** ≤5 trades per response, ≤20% of portfolio value per trade, plus the same validation as manual trades. (§9)
- **Selected ticker** is frontend-only state (React + URL hash). The backend has no `selected_ticker` concept. (§10)
- **Connection status** maps `EventSource.readyState` directly: OPEN → green, CONNECTING → yellow, CLOSED → red. No third "reconnecting" state. (§2)
- **Snapshot cadence: every 5 minutes + on trade.** ~288 rows/day, no downsampling/retention logic needed. (§7)
- **Chat history** is not truncated — single-user demo, rows are small, accepted risk. (§7)
- **Trade endpoint contract** is fully specified with error codes (`400`, `404`, `409`, `503`) and a uniform error envelope. (§8)
- **Watchlist soft cap: 50 tickers** to protect the Massive free-tier polling budget. (§8)
- **LLM mock** is a rule-based responder with a documented trigger table that E2E tests rely on. (§9)
- **Single charting library: Lightweight Charts** for main/sparkline/P&L. Heatmap uses `d3-hierarchy` + SVG. (§10)
- **Single launcher: `docker compose up`.** No shell or PowerShell launch scripts. No optional cloud-deployment section. (§4, §11)
- **SQLite WAL mode** is enabled at lazy init so the snapshot task and trade handler don't block each other. (§7)
- **`/api/chat` is not rate-limited** in the core build — accepted risk for a single-user demo. (§9)
- **`chat_messages.actions`** stores per-action results (`type`, `payload`, `status`, `error`) so the UI can render confirmations vs errors deterministically without joining the trades table. (§7)
- **SSE payload** contains `ticker`, `price`, `timestamp` per entry; frontend computes direction/deltas locally from the accumulated stream. (§6)
- **`LLM_MOCK` parsing:** the literal string `"true"` (case-insensitive) enables mock mode; anything else is treated as false. (§5)
