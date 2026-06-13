# 🤖 Model Handbook — ArbitPRO

> **Single source of truth for any AI model joining the ArbitPRO project.**
> Read this FIRST to understand the project, its state, conventions, and what to do next.

---

## 1. Quick Facts

| Property | Value |
|----------|-------|
| **Project** | ArbitPRO — Indian Markets Arbitrage & F&O Analytics Platform |
| **Stack** | FastAPI (Python) + React 19 (TailwindCSS, Radix UI, Recharts) |
| **Broker API** | Angel One SmartAPI (`smartapi-python`) |
| **Database** | MongoDB (Motor async driver) |
| **Auth** | Emergent Auth (Google OAuth, session cookies) |
| **Test framework** | `pytest` (backend) |
| **Lint/Format** | `flake8`, `black`, `isort` (Python) |

**Project location:** `D:/arbit/`

**Running state:** Backend http://localhost:8000 • Frontend http://localhost:3000

---

## 2. Project Snapshot

### ✅ What's Complete & Working

| Feature | Status | Details |
|---------|--------|---------|
| Angel One SmartAPI integration | ✅ Live | Auto-login, session mgmt, batch API, TOTP |
| Live market indices (5) | ✅ Live | NIFTY, BANKNIFTY, FINNIFTY, SENSEX, BANKEX |
| Live F&O stock prices (NSE + BSE) | ✅ Live | 30 stocks via batch API |
| Cross-exchange arbitrage scanner | ✅ Live | NSE vs BSE with full cost breakdown |
| Cash & Carry, Synthetic, Calendar Spread, Statistical | ✅ Implemented | Pure math, no live data dependency yet |
| T-shaped option chain | ✅ Live | 187K instrument master, 5s auto-refresh, CE=Green/PE=Red |
| IV Analytics dashboard | ✅ Live | BS IV, ATM IV, IV Rank, IV Percentile, HV (20d), India VIX |
| IV Skew chart + Max Pain calculator | ✅ Live | Full endpoints + UI |
| Seller Signal engine | ✅ Live | SELL_PREMIUM / AVOID_SELLING / NEUTRAL |
| MongoDB snapshots (IV + price) | ✅ Live | Daily upsert, builds 52w history |
| Performance analytics | ✅ Implemented | Sharpe, Sortino, Calmar, VaR, drawdown |
| Risk management | ✅ Implemented | Position sizing, VaR, SPAN margin |
| Backtesting (simulated) | ✅ Implemented | Equity curve + trade log |
| Auth (Google OAuth) | ✅ Live | Emergent Auth integration |
| Broker status + market session awareness | ✅ Live | IST-aware, weekend detection |
| Mobile-responsive UI | ✅ Done | Hamburger sidebar, responsive grids |
| GZip compression + 2s cache | ✅ Done | Option chain responses ~77% smaller |
| API endpoints (40+) | ✅ Working | All routes tested in iterations 1-6 |

### 🟡 What's In Progress / Partially Done

| Item | Status | Notes |
|------|--------|-------|
| `README.md` rewrite | ✅ Done but not committed | 237-line comprehensive README replacing 1-line stub |
| `docs/` skeleton creation | ✅ Done but not committed | ARCHITECTURE.md, CONTRIBUTING.md, TESTING.md, QUALITY.md, ROADMAP.md all written |
| `TODO.md` | ✅ Created — handoff notes populated | Task tracker with setup sprint status |
| `backend/.flake8` | ✅ Created but not "wired" | Config file exists, not yet verified working |
| `backend/pyproject.toml` | ✅ Created but not "wired" | Config for black, isort, pytest, coverage, mypy |
| `test_result.md` | ⚠️ Half-done | Testing protocol header written but **NO actual test data logged** below the marker |
| Backend refactor (server.py split) | ❌ Not started | server.py is 1856 lines — target: `routes/`, `services/`, `models/`, `core/` |
| Telegram alert scheduler | ❌ Not started | Background `asyncio` task needed |
| WebSocket streaming | ❌ Not started | Replace 5s REST polling |
| GitHub Actions CI | ❌ Not started | No `.github/workflows/` yet |
| Real backtesting (historical data) | ❌ Not started | Uses simulated returns currently |
| Frontend test suite | ❌ Not started | Jest + React Testing Library not wired |

### ✅ Setup Sprint (2026-06-14)

| Item | Status |
|------|--------|
| Python 3.12.10 installed via winget | ✅ |
| `.venv` created, 131 backend deps installed | ✅ |
| `emergentintegrations` removed from requirements.txt (not on PyPI) | ✅ |
| MongoDB connected at localhost:27017/arbitpro | ✅ |
| Backend running on http://localhost:8000 (health check green) | ✅ |
| Frontend running on http://localhost:3000 (compiled successfully) | ✅ |
| Frontend `@/` alias fixed → relative imports in index.js | ✅ |
| `.env` files created (backend + frontend) | ✅ |

### 🔴 Known Issues

| Issue | Priority | Location |
|-------|----------|----------|
| Missing OHLC data (Change/Volume = "—") | P1 | `/api/market/stocks` — batch LTP doesn't return OHLC |
| CORS `allow_origins=["*"]` | Medium | `server.py` — must tighten for production |
| No rate limiting | Medium | FastAPI — per-IP throttling needed |
| `test_result.md` has no data | Medium | Testing protocol exists but no logged results |
| No pre-commit hooks | Low | Quality gate not automated before commits |
| `emergentintegrations` package unavailable on PyPI | Low | Removed from requirements.txt — never imported in code |

---

## 3. Git State (Uncommitted Changes)

**All of these are untracked or unstaged — nothing is committed yet.**

Untracked files:
```text
TODO.md
backend/.flake8
backend/pyproject.toml
backend/.env                 # Created (contains secrets — DO NOT COMMIT)
frontend/.env                # Created (contains URL — DO NOT COMMIT)
docs/
```

Modified files (unstaged):
```text
README.md                    # Rewritten from 1-line stub
backend/requirements.txt     # Removed emergentintegrations
frontend/src/index.js        # Changed @/ aliases to relative imports
```

> **Do NOT commit `.env` files** — they are in `.gitignore` and contain secrets.
> **Ask the user** before committing anything.

---

## 3a. Server Status

Both servers are currently running on this machine:

| Server | URL | Status |
|--------|-----|--------|
| Backend (FastAPI) | http://localhost:8000 | ✅ Healthy |
| API Docs (Swagger) | http://localhost:8000/docs | ✅ Available |
| Frontend (React) | http://localhost:3000 | ✅ Compiled |

**To restart the servers:**
```powershell
# Terminal 1 — Backend
cd D:\arbit\backend
.venv\Scripts\activate
uvicorn server:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — Frontend
cd D:\arbit\frontend
npm start
```

---

## 4. Project Structure Map

```
D:/arbit/
├── README.md                        # Project docs (rewritten, unstaged)
├── TODO.md                          # Task tracker (created, unstaged)
├── backend/
│   ├── server.py                    # ⚠️ 1856-lines — refactor target
│   ├── angel_one_service.py         # Angel One SmartAPI wrapper
│   ├── option_chain_service.py      # Option chain + instrument master
│   ├── iv_analytics_service.py      # BS IV, IV Rank, Max Pain, etc.
│   ├── .flake8                      # Flake8 config (created, not wired)
│   ├── pyproject.toml               # Black, isort, pytest, mypy config
│   ├── requirements.txt             # Python deps (pinned)
│   └── tests/
│       ├── test_iv_analytics.py     # 18 tests (API-based, live server)
│       ├── test_option_chain.py     # Option chain API tests
│       ├── test_broker_status.py    # Broker + market session tests
│       └── test_ux_improvements.py  # UI/UX integration tests
├── frontend/
│   ├── src/
│   │   ├── App.js                   # Router + AuthProvider + Toaster
│   │   ├── components/
│   │   │   ├── Layout.jsx           # Sidebar + mobile header
│   │   │   ├── BrokerStatus.jsx     # Broker connection status
│   │   │   └── ui/                  # Shadcn Radix primitives (20+)
│   │   └── pages/
│   │       ├── Dashboard.jsx
│   │       ├── OptionChain.jsx
│   │       ├── IVAnalytics.jsx
│   │       ├── ArbitrageScanner.jsx
│   │       ├── CashCarryArbitrage.jsx
│   │       ├── SyntheticArbitrage.jsx
│   │       ├── CalendarSpread.jsx
│   │       ├── StatisticalArbitrage.jsx
│   │       ├── PerformanceAnalytics.jsx
│   │       ├── RiskManagement.jsx
│   │       ├── Backtesting.jsx
│   │       ├── AlertsConfig.jsx
│   │       └── Login.jsx
│   └── package.json
├── docs/
│   ├── ARCHITECTURE.md              # System design, data flow, modules
│   ├── CONTRIBUTING.md              # Coding standards, PR template
│   ├── TESTING.md                   # Testing strategy & conventions
│   ├── QUALITY.md                   # Lint/format/CI gates
│   ├── ROADMAP.md                   # Feature backlog with impact/effort
│   └── MODEL_HANDBOOK.md            # ← THIS FILE: AI onboarding guide
├── memory/
│   └── PRD.md                       # Original product requirements
└── test_result.md                   # Testing protocol (needs data!)
```

---

## 5. Key Architecture Decisions

### Data Source Flow
```
User clicks "Use Live Data" toggle
  → MarketDataService._use_live_data = True/False
  → True  = Try Angel One API → fallback to blank data (NOT simulated)
  → False = Use deterministic seed-based simulated prices
```

⚠️ **Important:** When `_use_live_data=True` and Angel One fails, the API returns **blank data** (null prices, not simulated). When `_use_live_data=False`, it uses `random.seed()` with minute-level timestamps for deterministic simulation.

### Option Chain
- **Instrument master**: 187K NFO instruments loaded at startup into `defaultdict(list)` keyed by underlying name
- **Cache**: 2s in-memory TTL cache for option chain responses
- **Blocking calls**: All Angel One SmartAPI calls wrapped in `asyncio.to_thread()`

### IV Analytics
- **IV Calculation**: Newton-Raphson (fast) → Brent method (fallback) → None (unsolvable)
- **Risk-free rate**: 6.5% (RBI repo rate)
- **HV**: Log returns, 20-day window, annualized √252
- **Stored in MongoDB**: `iv_snapshots` + `price_snapshots` collections

### Market Session Awareness (IST)
```python
hours = 60 * 9 + 15  # 09:15 IST = market open
hours = 60 * 15 + 30 # 15:30 IST = market close
# Weekday check → weekend detection
# Returns: market_open, pre_market, post_market, closed
```

---

## 6. Code Conventions (Non-Negotiable)

### Python
- **Type hints** on all new public functions (`: Optional[X]`, `List[Dict]`, etc.)
- **Async discipline**: `async def` for network/DB calls, `asyncio.to_thread()` for blocking SmartAPI calls
- **Error handling**: Never `except: pass` — always log the narrowest exception
- **Imports order**: stdlib → third-party → local (isort manages this)
- **Class naming**: `PascalCase` for services/models, `snake_case` for functions/variables

### JavaScript/React
- **Functional components only** — no class components
- **One component per file** — filename = component name
- **All hooks at top level** — no conditional hooks
- **`useCallback`** for functions passed to memoized children
- **`aria-label`** for icon-only buttons

### Testing
- **API-based tests** (current pattern): `requests.get(BASE_URL + endpoint)` — these hit a live server
- **Pure function tests** (target pattern): Direct function calls without HTTP
- `pytest.approx` for floating point comparisons
- `freezegun` for time-dependent tests (planned)
- Tests are in `backend/tests/` and run with `pytest`

---

## 7. Testing State

### Current Tests (all use `requests` — hit live backend)

| File | Tests | Type |
|------|-------|------|
| `test_iv_analytics.py` | 18 | API integration (HTTP) |
| `test_option_chain.py` | ~20 | API integration (HTTP) |
| `test_broker_status.py` | ~15 | API integration (HTTP) |
| `test_ux_improvements.py` | ~10 | API integration (HTTP) |

**To run tests:**
```bash
# Start backend first
cd D:/arbit/backend && uvicorn server:app --reload --port 8000

# In another terminal
cd D:/arbit/backend && python -m pytest tests/ -v

# Or run with coverage
python -m pytest --cov=.. --cov-report=term-missing
```

### What's Missing
- Unit tests for pure math functions (arbitrage, IV, performance)
- `conftest.py` with shared fixtures
- `mongomock` or test DB for DB-dependent tests
- Frontend tests (Jest + RTL not wired)
- E2E tests (Playwright not wired)

---

## 8. 🚦 Priority Task Queue (from TODO.md)

### Tier 1 — Highest impact (do these first)

| # | Task | Effort | What to do |
|---|------|--------|------------|
| 1 | **Telegram alert scheduler** | M | Create `backend/tasks/alert_scheduler.py` — background `asyncio` task that evaluates active alerts and sends via Telegram |
| 2 | **WebSocket streaming** | L | Replace 5s REST polling — add WS endpoint, frontend `useWebSocket` hook |
| 3 | **Backend refactor** (split server.py) | M | Move services → `services/`, routes → `routes/`, models → `models/`, core → `core/` |
| 4 | **Real backtesting** | M-L | NSE bhavcopy + Angel One historicals instead of simulated returns |
| 5 | **Persistent Angel session** | S | Store `refresh_token` in MongoDB, auto re-login |

### Tier 2 — Next up

| # | Task | Notes |
|---|------|-------|
| 6 | React Query + `useApiQuery` hook | Replace raw `useEffect + axios` |
| 7 | Fix missing OHLC data | Change/Volume show "—" for batch LTP |
| 8 | GitHub Actions CI | `.github/workflows/ci.yml` |
| 9 | Tighten CORS | Replace `["*"]` with env-driven list |

---

## 9. 🎯 What Was Left Unfinished

The **last session was interrupted** (model quota exhausted) during the documentation sprint. Here's exactly what was in progress:

1. **Documentation skeleton** was ~90% complete:
   - All 6 `docs/` files written ✅
   - `README.md` rewritten ✅
   - `TODO.md` created but needs its own status updated from `[~]` to `[x]`
   - `backend/.flake8` and `backend/pyproject.toml` created but not tested/wired

2. **Testing state file** (`test_result.md`):
   - The protocol/instructions header is written
   - **No actual test data has been logged below the "Testing Data" section**
   - If you need to use the testing protocol, you need to populate the YAML-style data

3. **Nothing has been committed** — all docs work is untracked/staged

### Do NOT redo what's already done
- If docs/ exist with content, DON'T overwrite them
- If TODO.md exists, read and UPDATE it, don't rewrite from scratch
- If test files exist, DON'T recreate them

---

## 10. 🧠 Model Handover Protocol

When switching between AI models (e.g., Claude → ChatGPT → Codebuff), follow this handoff:

### For the LEAVING model:
1. **Update TODO.md** — mark all completed items `[x]`, in-progress `[~]`
2. **Write a concise handoff note** in `TODO.md` under "## Handoff Notes" section with:
   - What was done
   - What was tried but failed
   - What the next model should do first
   - Key files modified
3. **Don't commit** unless explicitly asked

### For the JOINING model:
1. **Read this handbook FIRST** (docs/MODEL_HANDBOOK.md)
2. **Read TODO.md** — check "## Handoff Notes" for the last model's status
3. **Check git status** — `cd D:/arbit && git status` to see uncommitted work
4. **Read the relevant doc files** — ARCHITECTURE.md if adding features, TESTING.md before writing tests
5. **Don't overwrite existing docs** — read before writing
6. **Ask the user** before taking significant actions
7. **Run tests** before and after changes

---

## 11. 💡 Managing Multiple Free Model Tiers

Based on the user's question about managing free usage across models:

### Strategy: Model Specialization

| Model | Best For | Free Tier Strategy |
|-------|----------|-------------------|
| **Codebuff (DeepSeek V4 Flash)** | **Coding & orchestration** — edit files, run commands, search codebase | Use for active development; handles the full tool chain |
| **ChatGPT (GPT-4o / o3-mini)** | **Architecture & planning** — reason about complex decisions, design patterns | Use for thinking-heavy tasks; paste code snippets for analysis |
| **Claude (Sonnet/Opus)** | **Documentation & UI** — writing docs, generating JSX/CSS, creative design | Use for frontend work and documentation writing |
| **Gemini** | **Research & analysis** — reading large codebases, summarizing | Use for one-shot code review and analysis |

### Practical Tips

1. **Keep TODO.md updated** — This is your cross-model memory. Every model reads and writes to it.
2. **This handbook is your anchor** — Any new model reads this first to get up to speed instantly.
3. **Use the `## Handoff Notes` section** in TODO.md as the communication channel between models.
4. **Batch context requests** — When asking a model to understand a file, read it first and paste the most relevant sections rather than making the model re-read the whole codebase.
5. **Don't regenerate what exists** — Always check if a file already has content before asking a model to create it.
6. **Free tier limits** are usually per-model and reset periodically (hourly/daily/monthly). Rotate between models if one hits its limit.
7. **Use the cheapest model for simple tasks** — formatting, linting, renaming variables, reading files.

### If a Model Runs Out Mid-Task (like last time)

1. **Stop immediately** — Note exactly what was in progress
2. **Write a handoff note** in TODO.md with:
   ```
   ## Handoff Notes
   - 2026-06-13: Model [name] ran out of quota mid-[task description]
   - Files modified: [list]
   - What's left: [precise description of remaining work]
   - Next model should: [specific instructions]
   ```
3. **Don't commit** — The next model needs to see the dirty working tree
4. **Switch models** with this handbook as the onboarding document

---

## 12. Quick Reference: Common Commands

```bash
# Backend
cd D:/arbit/backend
uvicorn server:app --reload --port 8000          # Start server
python -m pytest tests/ -v                        # Run all tests
python -m pytest tests/test_iv_analytics.py -v    # Single test file
flake8 .                                          # Lint check
black --check .                                   # Format check

# Frontend
cd D:/arbit/frontend
yarn start                                        # Start dev server
yarn build                                        # Production build

# Git
cd D:/arbit
git status                                        # Check current state
git diff                                          # See unstaged changes
git add -A && git commit -m "message"             # Commit all
```

---

## 13. Environment Variables Required

```bash
# backend/.env
MONGO_URL=mongodb://localhost:27017
DB_NAME=arbitpro
ANGEL_API_KEY=your_angel_api_key
ANGEL_CLIENT_ID=your_client_id
ANGEL_MPIN=your_mpin
ANGEL_TOTP_SECRET=your_totp_secret
TELEGRAM_BOT_TOKEN=optional_telegram_token

# frontend/.env
REACT_APP_BACKEND_URL=http://localhost:8000
```

---

*Last updated: 2026-06-14 — Setup sprint completed. Both servers running.*
