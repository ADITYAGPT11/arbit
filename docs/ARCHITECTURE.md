# Architecture

> System design, module boundaries, and data flow for ArbitPRO.

---

## 1. Goals & Non-Goals

### Goals
- Detect arbitrage opportunities across NSE/BSE with transaction-cost-aware net profit
- Provide a credible IV-analytics toolkit for options sellers
- Stay responsive under market-open load (option chain polls every 5s)
- Keep the codebase testable and modular

### Non-Goals (current iteration)
- Order placement (we are read-only; the broker integration is for **market data**)
- Multi-user tenancy beyond alerts/watchlists
- Mobile native apps (responsive web only)

---

## 2. System Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                          React Frontend                            │
│                                                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │  Pages   │  │ Components│  │  Hooks   │  │  AuthContext     │   │
│  │ (12)     │  │ (Layout,  │  │ (custom) │  │  (Google OAuth)  │   │
│  │          │  │  Broker-  │  │          │  │                  │   │
│  │          │  │  Status)  │  │          │  │                  │   │
│  └─────┬────┘  └─────┬────┘  └─────┬────┘  └────────┬─────────┘   │
│        │             │             │                │             │
│        └─────────────┴─────────────┴────────────────┘             │
│                              │                                     │
│                         Axios (REST)                                │
│                         (planned: WebSocket)                        │
└──────────────────────────────┬─────────────────────────────────────┘
                               │
                          HTTPS / WSS
                               │
┌──────────────────────────────┴─────────────────────────────────────┐
│                          FastAPI Backend                           │
│                                                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐   │
│  │   routes/    │  │  services/   │  │  core/                 │   │
│  │  (per domain │─►│  (business   │  │  (config, db, deps,    │   │
│  │   auth, mkt, │  │   logic)     │  │   middleware, errors)  │   │
│  │   arb, opt,  │  │              │  │                        │   │
│  │   iv, etc.)  │  │              │  │                        │   │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬───────────┘   │
│         │                 │                       │               │
│         └─────────────────┴───────────────────────┘               │
│                              │                                     │
│                     ┌────────┴────────┐                            │
│                     │  External APIs  │                            │
│                     │  • Angel One    │                            │
│                     │  • Emergent     │                            │
│                     │  • Telegram Bot │                            │
│                     └────────┬────────┘                            │
└──────────────────────────────┬─────────────────────────────────────┘
                               │
                          Motor (async)
                               │
                       ┌───────┴────────┐
                       │    MongoDB     │
                       │ (users, alerts,│
                       │  watchlists,   │
                       │  iv_snapshots, │
                       │  price_snaps)  │
                       └────────────────┘
```

---

## 3. Backend Module Layout (target)

The current backend has a single `server.py` (1856 lines) which is a known refactor target. The **target layout**:

```
backend/
├── server.py                 # FastAPI app factory + middleware + lifespan only
├── core/
│   ├── config.py             # pydantic-settings, env loading
│   ├── db.py                 # Motor client + db accessor
│   ├── deps.py               # FastAPI dependencies (auth, services)
│   ├── errors.py             # Exception handlers
│   └── logging.py            # Structured logging setup
├── models/                   # Pydantic models
│   ├── user.py
│   ├── alert.py
│   ├── watchlist.py
│   └── market.py
├── services/                 # Stateless / singleton business logic
│   ├── angel_one.py          # (existing angel_one_service.py)
│   ├── option_chain.py       # (existing option_chain_service.py)
│   ├── iv_analytics.py       # (existing iv_analytics_service.py)
│   ├── market_data.py        # (extract from server.py: MarketDataService)
│   ├── arbitrage.py          # (extract: ArbitrageEngine)
│   ├── performance.py        # (extract: PerformanceAnalytics)
│   ├── risk.py               # (extract: RiskManager)
│   ├── backtest.py           # (extract: BacktestEngine)
│   ├── telegram.py           # (extract: TelegramService)
│   └── session.py            # (extract: market session logic)
├── routes/                   # FastAPI routers — one per domain
│   ├── auth.py
│   ├── market.py
│   ├── arbitrage.py
│   ├── options.py
│   ├── iv.py
│   ├── analytics.py
│   ├── risk.py
│   ├── alerts.py
│   ├── backtest.py
│   ├── watchlist.py
│   └── settings.py
├── tasks/                    # Background async jobs
│   └── alert_scheduler.py    # (planned — P0)
├── tests/
│   ├── unit/                 # No network — pure functions
│   ├── integration/          # Hit in-process FastAPI via TestClient
│   └── contract/             # Verify SmartAPI response shapes
└── requirements.txt
```

### Why this layout?

- **Routes are thin** — parse + validate input, call services, return `response_model=`
- **Services own business logic** — easy to unit-test without HTTP
- **`core/` holds cross-cutting concerns** — config, db, auth, errors
- **`tasks/` is explicit** — anything with a lifespan or background loop lives here

---

## 4. Frontend Module Layout (current)

```
frontend/src/
├── App.js                    # Router + AuthProvider + Toaster
├── components/
│   ├── Layout.jsx            # Sidebar + mobile header + BrokerStatus
│   ├── BrokerStatus.jsx
│   └── ui/                   # Shadcn primitives (Radix-based)
├── hooks/
│   └── use-toast.js
├── lib/
│   └── utils.js              # `cn()` helper
└── pages/
    ├── Dashboard.jsx
    ├── OptionChain.jsx
    ├── IVAnalytics.jsx
    ├── ArbitrageScanner.jsx
    ├── CashCarryArbitrage.jsx
    ├── SyntheticArbitrage.jsx
    ├── CalendarSpread.jsx
    ├── StatisticalArbitrage.jsx
    ├── PerformanceAnalytics.jsx
    ├── RiskManagement.jsx
    ├── AlertsConfig.jsx
    ├── Backtesting.jsx
    └── Login.jsx
```

### Planned additions
- `hooks/useWebSocket.js` — shared WS connection for streaming data
- `hooks/useApiQuery.js` — React Query wrapper (replaces raw `useEffect + axios`)
- `lib/apiClient.js` — central Axios instance with interceptors
- `lib/format.js` — number/percent/IST formatters

---

## 5. Data Flow

### Read path: live market data

```
┌──────────┐  GET /api/market/indices        ┌────────────┐
│ Dashboard│ ───────────────────────────────► │  route     │
│  (React) │                                  │  /market   │
└──────────┘ ◄───────── JSON ───────────────  └─────┬──────┘
                                                      │
                                              MarketDataService
                                                      │
                                              AngelOneService
                                                  (batch LTP)
                                                      │
                                          ┌───────────┴───────────┐
                                          ▼                       ▼
                                  Angel One REST          Fallback to
                                  (live data)             simulated
```

### Write path: alert

```
AlertsConfig.jsx
   │  POST /api/alerts (with session cookie)
   ▼
routes/alerts.py
   │  require_auth → User
   │  insert to db.alerts
   ▼
MongoDB
   │
   │  (background, every Ns — planned)
   ▼
tasks/alert_scheduler.py
   │  for each active alert, evaluate condition
   │  if hit → TelegramService.send_alert(...)
   ▼
Telegram Bot API
```

### Heavy path: option chain

```
OptionChain.jsx          polls every 5s
   │  GET /api/options/chain?underlying=NIFTY&expiry=...
   ▼
routes/options.py
   │
   ├──► asyncio.to_thread(oc_service.build_option_chain, ...)
   │         │
   │         ├─► _nfo_by_name[underlying]    (O(1) lookup)
   │         ├─► _chain_cache.get(key)        (2s TTL)
   │         └─► Angel One batched LTP/Quote
   │
   ▼
{ chain: [...], totals: {...}, atm_strike: ..., data_source: "angel_one_live" }
```

---

## 6. Cross-Cutting Concerns

### Authentication
- **Google OAuth** via Emergent Auth
- Server exchanges `session_id` (URL fragment) for a server-issued opaque `session_token`
- Stored in `user_sessions` collection with 7-day TTL
- Set as `httponly`, `secure`, `samesite=none` cookie
- `core/deps.py:get_current_user` decodes from cookie or `Authorization: Bearer`

### CORS
- **Dev**: `allow_origins=["*"]` is acceptable because cookies use `samesite=none`
- **Prod**: explicit origin list via env (`CORS_ALLOWED_ORIGINS`)

### Compression
- `GZipMiddleware(minimum_size=1000)` — option chain responses shrink ~77%
- Cached for 2s in-process; replace with Redis when scaling horizontally (P2)

### Concurrency
- All Angel One calls are blocking → wrapped in `asyncio.to_thread`
- Singleton services (`AngelOneService`, `OptionChainService`) are safe under FastAPI's single-event-loop model

### Logging
- Stdlib `logging` with consistent format
- **Planned**: structured JSON logging + request-id correlation in `core/logging.py`

---

## 7. Performance Characteristics

| Endpoint                         | Latency (p50, live) | Notes                       |
|----------------------------------|---------------------|-----------------------------|
| `GET /api/health`                | <5 ms               | No DB hit                   |
| `GET /api/market/indices`        | ~200-400 ms         | 1 batch call (5 indices)    |
| `GET /api/market/stocks`         | ~400-800 ms         | 2 batch calls (NSE + BSE)   |
| `GET /api/options/chain`         | ~300-600 ms         | Indexed lookup + 1 batch    |
| `GET /api/iv/dashboard`          | ~500-900 ms         | Chain build + VIX + DB      |
| `GET /api/arbitrage/cross-exchange` | ~600-1200 ms     | 2 batch calls (15 symbols)  |

### Optimizations applied
- **2s response cache** for option chain polling
- **`asyncio.to_thread`** so blocking SmartAPI calls don't stall the event loop
- **Indexed instrument master** (`defaultdict(list)` by underlying name)
- **Batch API** (50 tokens per request)
- **GZip** at 1KB threshold

---

## 8. Data Persistence

### MongoDB collections

| Collection          | Purpose                              | Indexes                          |
|---------------------|--------------------------------------|----------------------------------|
| `users`             | OAuth user profiles                  | `email` unique                   |
| `user_sessions`     | Active session tokens                | `session_token` unique, TTL 7d   |
| `alerts`            | User-defined alerts                  | `user_id`, `(user_id, is_active)`|
| `watchlist`         | User watchlist                       | `user_id`                        |
| `settings`          | User preferences                     | `user_id` unique                 |
| `iv_snapshots`      | Daily IV history (builds 52w data)   | `(underlying, date)` unique      |
| `price_snapshots`   | Daily close prices for HV            | `(underlying, date)` unique      |

### Cache strategy
- **In-memory TTL caches** for hot reads (option chain, indices)
- **MongoDB** for cold/aggregate reads (IV history, user data)
- **No external cache yet** — Redis is on the roadmap for multi-worker deploys

---

## 9. External Dependencies

| Service       | Used for                  | Failure mode                  |
|---------------|---------------------------|-------------------------------|
| Angel One     | Market data, session      | Fall back to simulated (UI shows `data_source`) |
| Emergent Auth | Google OAuth              | Login broken; everything else works |
| Telegram      | Alerts                    | Alert skipped, logged warning |
| MongoDB       | Persistence               | Read endpoints degrade; live data still works  |

---

## 10. Security Considerations

- ✅ `httponly`, `secure` session cookies
- ✅ `.env` excluded from VCS
- ⚠️ CORS `allow_origins=["*"]` — must tighten in prod
- ⚠️ No rate limiting — add per-IP throttling for public endpoints
- ⚠️ No CSRF token (relies on `samesite=none` + bearer fallback)
- ⚠️ No input sanitization on free-form numeric inputs (FastAPI/Pydantic handles types but not magnitude)

---

## 11. Open Architectural Questions

1. **Multi-worker scaling** — FastAPI behind Gunicorn needs shared cache (Redis) and shared Angel One session (token store in Redis or DB)
2. **WS strategy** — one WS per browser tab vs. single server-side fanout (we plan the latter)
3. **Time-series store** — when IV history grows, move from Mongo to TimescaleDB / InfluxDB
4. **Backtest storage** — should backtest results be persisted? (TBD; currently stateless)
