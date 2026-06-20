# Buffy's Context Memory — ArbitPRO

> **Purpose:** Persistent memory for Buffy (Codebuff AI agent) across sessions. Updated whenever context changes significantly. Last updated: 2026-06-20.

---

## 1. PROJECT IDENTITY

| Field | Value |
|-------|-------|
| **Name** | ArbitPRO |
| **Description** | Production-grade, real-time multi-exchange arbitrage & F&O analytics platform for Indian markets (NSE, BSE, MCX) |
| **Location** | `D:/arbit/` |
| **Backend URL** | http://localhost:8000 |
| **Frontend URL** | http://localhost:3000 |
| **API Docs** | http://localhost:8000/docs |
| **Database** | MongoDB at localhost:27017/arbitpro |
| **Git Branch** | `main` (origin/main up to date) |

---

## 2. TECH STACK

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 19 · React Router 7 · TailwindCSS · Radix UI · Recharts · sonner · lucide-react · CRACO |
| **Backend** | FastAPI 0.110 · Pydantic 2 · asyncio · httpx · Motor (async MongoDB) |
| **Broker API** | Angel One SmartAPI (`smartapi-python` 1.5.5) · `pyotp` 2.9 |
| **Database** | MongoDB 6.0+ (Motor 3.3.1 async driver) |
| **Auth** | Emergent Auth (Google OAuth, session cookies) |
| **Numerics** | NumPy 2.4 · SciPy 1.17 (Black-Scholes, stats) |
| **Python** | 3.12.10 |
| **Node** | 20+ |
| **Lint/Format** | flake8, black, isort (Python) · ESLint (JS) |
| **Testing** | pytest (backend) · Jest/RTL (planned for frontend) |

---

## 3. ARCHITECTURE OVERVIEW

### High-Level Flow
```
React Frontend (CRACO/SSR) ←→ HTTPS/WSS → FastAPI Backend (async) ←→ Angel One SmartAPI
                                                    ↓
                                              MongoDB (users/alerts/snapshots)
```

### Backend (1856-line `server.py` — refactor target!)
The backend is a monolith in `server.py` with inline classes serving as modules:
- **MarketDataService** — live/simulated stock and index data; `_use_live_data` toggle
- **ArbitrageEngine** — cross-exchange, cash & carry, synthetic, calendar spread, statistical
- **PerformanceAnalytics** — Sharpe, Sortino, Calmar, drawdown, win rate
- **RiskManager** — position sizing, VaR (historical + parametric), SPAN margin
- **TelegramService** — alert sending via Telegram bot API
- **BacktestEngine** — simulated returns backtesting
- **Auth helpers** — session management, cookie-based auth

**Actual service files** (separated):
- `backend/angel_one_service.py` — Angel One SmartAPI wrapper (singleton)
- `backend/option_chain_service.py` — T-shaped option chain builder (singleton)
- `backend/iv_analytics_service.py` — Black-Scholes IV, IV Rank, IV Percentile, Max Pain, HV, IV Skew

### Frontend (`frontend/src/`)
- **App.js** — Router + AuthProvider + Toaster + AuthCallback
- **Layout.jsx** — Sidebar + mobile responsive header + BrokerStatus
- **BrokerStatus.jsx** — Broker connection panel in sidebar
- **Pages (13):** Dashboard, OptionChain, IVAnalytics, ArbitrageScanner, CashCarryArbitrage, SyntheticArbitrage, CalendarSpread, StatisticalArbitrage, PerformanceAnalytics, RiskManagement, AlertsConfig, Backtesting, Login
- **UI Components (20+)** — Shadcn Radix-based primitives
- **Custom CSS** — `App.css` with trading-terminal dark theme
- **Tailwind** — Configured in `tailwind.config.js`

---

## 4. KEY PATTERNS & CONVENTIONS

### Data Source Flow
```
User clicks "Use Live Data" toggle
  → MarketDataService._use_live_data = True/False
  → True  = Try Angel One API → fallback to blank data (NOT simulated, null prices)
  → False = Use deterministic seed-based simulated prices
```

### Option Chain
- **Instrument master**: 187K NFO instruments downloaded at startup → `defaultdict(list)` keyed by underlying name
- **Cache**: 2s in-memory TTL cache for option chain responses (`_chain_cache` dict)
- **Batch API**: Max 50 tokens per request to Angel One
- **Blocking calls**: All SmartAPI calls wrapped in `asyncio.to_thread()`

### IV Analytics
- **IV**: Newton-Raphson → Brent method fallback → None
- **Risk-free rate**: 6.5% (RBI repo rate)
- **HV**: Log returns, 20-day window, annualized √252
- **Snapshots**: Daily upsert to MongoDB `iv_snapshots` and `price_snapshots`

### Market Session (IST)
```python
market_open = 9*60+15  # 09:15 IST
market_close = 15*60+30 # 15:30 IST
# Returns: market_open, pre_market, post_market, closed, pre_open
```

### Auth
- Google OAuth via Emergent Auth
- Session token stored in `httponly`, `secure`, `samesite=none` cookie
- 7-day TTL in `user_sessions` collection
- Fallback: `Authorization: Bearer` header

### API Responses
- CE = Green (#22c55e), PE = Red (#ef4444) throughout
- `data_source` field on all data responses: `angel_one_live`, `simulated`, `angel_one_unavailable`
- GZip middleware on responses > 1KB

### Testing
- Current tests: HTTP-based integration tests using `requests` hitting live backend
- Target: unit tests for pure functions, integration tests with TestClient
- Tests in `backend/tests/`: test_iv_analytics.py, test_option_chain.py, test_broker_status.py, test_ux_improvements.py

---

## 5. FILE SYSTEM MAP

```
D:/arbit/
├── README.md                         # Project docs
├── TODO.md                           # Task tracker (DON'T overwrite!)
├── backend_test.py
├── auth_testing.md
│
├── backend/
│   ├── server.py                     # MAIN ⚠️ 1856-lines monolith — refactor target
│   ├── angel_one_service.py          # Angel One SmartAPI singleton
│   ├── option_chain_service.py       # Option chain builder + instrument master
│   ├── iv_analytics_service.py       # BS IV, IV Rank, Max Pain, HV, IV Skew
│   ├── .flake8                       # Flake8 config (created, not wired)
│   ├── pyproject.toml                # Black, isort, pytest, coverage, mypy config
│   ├── requirements.txt              # Pinned Python deps
│   └── tests/
│       ├── test_iv_analytics.py      # 18 tests
│       ├── test_option_chain.py      # ~20 tests
│       ├── test_broker_status.py     # ~15 tests
│       └── test_ux_improvements.py   # ~10 tests
│
├── frontend/
│   ├── package.json                  # React 19, Radix UI, Recharts, sonner, etc.
│   ├── yarn.lock
│   ├── craco.config.js
│   ├── tailwind.config.js
│   ├── components.json               # Shadcn config
│   ├── public/index.html
│   ├── plugins/
│   │   ├── health-check/             # Webpack health plugin
│   │   └── visual-edits/             # Babel metadata plugin
│   └── src/
│       ├── App.js                    # Router + AuthProvider + Toaster
│       ├── App.css                   # Trading terminal dark theme (custom CSS)
│       ├── index.css                 # Tailwind + Shadcn CSS vars
│       ├── index.js                  # Entry point
│       ├── components/
│       │   ├── Layout.jsx            # Sidebar + mobile header
│       │   ├── BrokerStatus.jsx      # Broker connection status panel
│       │   └── ui/                   # 20+ Shadcn Radix primitives
│       ├── hooks/use-toast.js
│       ├── lib/utils.js              # cn() helper
│       └── pages/                    # 13 page components
│
├── docs/
│   ├── ARCHITECTURE.md               # System design, modules, data flow
│   ├── CONTRIBUTING.md               # Coding standards, PR template
│   ├── TESTING.md                    # Testing strategy & conventions
│   ├── QUALITY.md                    # Lint/format/CI gates
│   ├── ROADMAP.md                    # Feature backlog with impact/effort
│   └── MODEL_HANDBOOK.md            # AI model onboarding guide
│
├── memory/
│   ├── .gitkeep
│   ├── PRD.md                        # Original product requirements
│   └── buffy/
│       └── CONTEXT_MEMORY.md         # ← THIS FILE (Buffy's persistent memory)
│
├── scripts/
│   ├── start.ps1                     # One-click server launcher
│   └── stop.ps1                      # One-click server stopper
│
├── tests/
│   ├── __init__.py
│   └── test_reports/                 # JSON iteration test reports
│       ├── iteration_1.json through iteration_6.json
│       └── pytest/                   # XML pytest results
│
├── test_result.md                    # Testing protocol (header written, NO data)
└── yarn.lock
```

---

## 6. GIT STATE (Current: 2026-06-20)

### Modified (unstaged)
- `TODO.md` — Updated with setup sprint tasks
- `docs/MODEL_HANDBOOK.md` — Updated with script references

### Untracked
- `scripts/` — start.ps1, stop.ps1

### Previously created files (may still exist)
The following were created in earlier sessions but their git status is unknown:
- `backend/.flake8`, `backend/pyproject.toml`
- `backend/.env`, `frontend/.env` (secrets — DO NOT COMMIT)
- All `docs/*.md` files
- `README.md` (rewritten from stub)

**Never commit .env files!** They contain secrets and are in .gitignore.

---

## 7. STATUS OF FEATURES

### ✅ Complete & Working
- Angel One SmartAPI integration (auto-login, session mgmt, batch API, TOTP)
- Live market indices (5 indices via batch API)
- Live F&O stock prices (30 stocks, NSE + BSE)
- Cross-exchange arbitrage scanner (NSE vs BSE with cost breakdown)
- Cash & Carry, Synthetic, Calendar Spread, Statistical arbitrage
- T-shaped option chain (187K instrument master, 5s auto-refresh)
- IV Analytics (BS IV, ATM IV, IV Rank, IV Percentile, HV, India VIX)
- IV Skew chart + Max Pain calculator
- Seller Signal engine (SELL_PREMIUM / AVOID_SELLING / NEUTRAL)
- MongoDB snapshots (IV + price, daily upsert)
- Performance analytics (Sharpe, Sortino, Calmar, VaR, drawdown)
- Risk management (position sizing, VaR, SPAN margin)
- Backtesting (simulated)
- Google OAuth via Emergent Auth
- Broker status + market session awareness (IST)
- Mobile-responsive UI (hamburger sidebar, responsive grids)
- GZip compression + 2s cache
- 40+ API endpoints
- Start/stop scripts

### 🟡 In Progress / Partially Done
- `backend/.flake8`, `pyproject.toml` — configs exist but not wired/verified
- `test_result.md` — header written, NO test data logged

### ❌ Not Started
- Backend refactor (split server.py → routes/, services/, models/, core/)
- Telegram alert scheduler (background asyncio task)
- WebSocket streaming (replace 5s REST polling)
- GitHub Actions CI
- Real backtesting (historical data)
- Frontend test suite
- Pre-commit hooks
- Production CORS (currently allow_origins=["*"])
- Rate limiting
- Redis cache

---

## 8. ENVIRONMENT VARIABLES

### `backend/.env`
```
MONGO_URL=mongodb://localhost:27017
DB_NAME=arbitpro
ANGEL_API_KEY=your_angel_api_key
ANGEL_CLIENT_ID=your_client_id
ANGEL_MPIN=your_mpin
ANGEL_TOTP_SECRET=your_totp_secret
TELEGRAM_BOT_TOKEN=optional_telegram_token
```

### `frontend/.env`
```
REACT_APP_BACKEND_URL=http://localhost:8000
```

---

## 9. START/STOP COMMANDS

```powershell
# Start both servers
powershell -ExecutionPolicy Bypass -File scripts/start.ps1

# Stop both servers
powershell -ExecutionPolicy Bypass -File scripts/stop.ps1

# Backend only
cd D:/arbit/backend
.venv/Scripts/activate
uvicorn server:app --reload --host 0.0.0.0 --port 8000

# Frontend only
cd D:/arbit/frontend
npm start
```

---

## 10. TESTING COMMANDS

```bash
# All backend tests
cd D:/arbit/backend
python -m pytest tests/ -v

# Single test file
python -m pytest tests/test_iv_analytics.py -v

# With coverage
python -m pytest --cov=. --cov-report=term-missing

# Lint
flake8 backend/
```

---

## 11. IMPORTANT BEHAVIOR NOTES

### Angel One Connectivity
- Angel One credentials may not be configured (they're in .env which has secrets).
- When `_use_live_data=True` and Angel One fails → returns **blank/null data** (not simulated).
- When `_use_live_data=False` → uses `random.seed()` with minute-level timestamps for deterministic simulation.
- Login attempts are capped at 3; service has `reset_login_attempts()` method.

### Option Chain Behavior
- Instrument master downloads from Angel One's CDN on startup (1h cache TTL).
- If no market data available, chain still builds but with zero prices.
- 2s in-memory cache for repeated polling.

### Server Status
- Both backend and frontend are currently running on this machine.
- To check: `curl http://localhost:8000/api/health`

### Error Handling Patterns
- Services raise domain exceptions → routes catch and convert to HTTPException
- Never `except: pass` — always log the narrowest exception
- Blocking Angel One calls wrapped in `asyncio.to_thread()`

---

## 12. KEY PROMPTS & RESPONSE PATTERNS

- **When user asks me to do something**: Understand context first, read relevant files, then do it. Be proactive but ask for clarification on ambiguous or significant actions.
- **When implementing**: Make minimal changes, reuse existing patterns, preserve existing behavior.
- **When editing code**: Follow project conventions (CE=Green/PE=Red, data_source field, error handling patterns).
- **When asked about services**: Use gravity_index tool to research before recommending.
- **Git discipline**: Don't commit unless asked. Don't push destructive commands.

---

*Last updated: 2026-06-20. Buffy's persistent memory for ArbitPRO.*
