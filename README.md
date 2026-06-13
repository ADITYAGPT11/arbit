# ArbitPRO

> **Production-grade, real-time multi-exchange arbitrage & F&O analytics platform for Indian markets (NSE, BSE, MCX).**

ArbitPRO detects cross-exchange, cash & carry, synthetic, calendar-spread, and statistical-arbitrage opportunities on Indian equities and derivatives, with an options-seller's IV analytics toolkit, risk management, and Telegram alerting — all in a single FastAPI + React application.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Quickstart](#quickstart)
- [Configuration](#configuration)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Documentation](#documentation)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## Features

### Arbitrage Engines
- **Cross-exchange** — NSE vs BSE LTP comparisons with transaction-cost-aware net profit
- **Cash & Carry** — spot vs futures basis, fair-value, annualized return
- **Synthetic futures** — put-call parity mispricing
- **Calendar spreads** — inter-expiry futures spread, annualized
- **Statistical (pairs trading)** — z-score, correlation, half-life, mean-reversion signals

### Options & IV Analytics
- **T-shaped option chain** with 5-second auto-refresh, 187K instrument master
- **Black-Scholes IV** (Newton-Raphson + Brent fallback)
- **ATM IV, IV Rank, IV Percentile, Historical Volatility (20d)**
- **India VIX** live feed
- **IV Skew** chart and **Max Pain** calculator
- **Seller signal engine** — `SELL_PREMIUM` / `AVOID_SELLING` / `NEUTRAL`

### Performance & Risk
- **Performance metrics** — Sharpe, Sortino, max drawdown, Calmar, profit factor, weekday PnL
- **Risk** — position sizing, historical + parametric VaR, SPAN margin
- **Backtesting** (simulated; see [Roadmap](docs/ROADMAP.md) for historical upgrade)

### Platform
- **Angel One SmartAPI** integration with auto-login, TOTP, batch APIs
- **Market session awareness** (IST) with broker-status component
- **Google OAuth** via Emergent Auth
- **Telegram alerts** (service implemented; scheduler in progress)
- **Watchlists, alerts, settings** (user-scoped, MongoDB)
- **Mobile-responsive UI** (hamburger sidebar, adaptive grids)
- **Production optimizations** — GZip middleware, `asyncio.to_thread`, 2s response cache

---

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full system design, module boundaries, and data flow.

**High-level:**

```
┌─────────────────┐    HTTPS/WSS    ┌──────────────────┐    SmartAPI    ┌──────────────┐
│  React Frontend │ ──────────────► │  FastAPI Backend │ ─────────────► │  Angel One   │
│  (CRACO/SSR)    │ ◄────────────── │  (async)         │ ◄───────────── │  (NSE/BSE)   │
└─────────────────┘                 └──────────────────┘                └──────────────┘
                                            │
                                            ▼
                                    ┌──────────────┐
                                    │   MongoDB    │
                                    │ (users/alerts│
                                    │  /snapshots) │
                                    └──────────────┘
```

---

## Tech Stack

| Layer       | Technology                                                                |
|-------------|---------------------------------------------------------------------------|
| Frontend    | React 19 · React Router 7 · TailwindCSS · Radix UI · Recharts · sonner    |
| Build       | CRACO · Create React App                                                  |
| Backend     | FastAPI 0.110 · Pydantic 2 · `asyncio` · `httpx`                          |
| Broker API  | Angel One SmartAPI (`smartapi-python`) · `pyotp`                          |
| Database    | MongoDB (Motor async driver)                                              |
| Auth        | Emergent Auth (Google OAuth, session cookies)                             |
| Numerics    | NumPy · SciPy (Black-Scholes, statistics)                                 |
| Lint/Format | `flake8`, `black`, `isort` (Python) · ESLint, Prettier (JS, planned)      |
| Testing     | `pytest` (backend) · Jest/RTL (frontend, planned)                         |
| CI          | GitHub Actions (planned — see [docs/QUALITY.md](docs/QUALITY.md))        |

---

## Quickstart

### Prerequisites

- **Python** 3.11+
- **Node.js** 20+ and **Yarn** 1.22+
- **MongoDB** 6.0+ (local or Atlas)
- **Angel One** trading account with SmartAPI access (API key, MPIN, TOTP secret)

### 1. Clone & install

```bash
git clone <your-fork-url> arbit
cd arbit

# Backend
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # fill in credentials (see Configuration)

# Frontend
cd ../frontend
yarn install
cp .env.example .env       # set REACT_APP_BACKEND_URL=http://localhost:8000
```

### 2. Run

```bash
# Terminal 1 — backend (from /backend)
uvicorn server:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — frontend (from /frontend)
yarn start                 # opens http://localhost:3000
```

The backend auto-logs into Angel One on startup. If credentials are missing, the app gracefully falls back to simulated data (clearly labelled in the UI).

### 3. Health check

```bash
curl http://localhost:8000/api/health
# {"status":"healthy","timestamp":"2026-..."}
```

OpenAPI docs: <http://localhost:8000/docs>

---

## Configuration

### Backend (`backend/.env`)

| Variable             | Required | Description                                          |
|----------------------|----------|------------------------------------------------------|
| `MONGO_URL`          | ✅       | MongoDB connection string (e.g. `mongodb://localhost:27017`) |
| `DB_NAME`            | ✅       | Database name (e.g. `arbitpro`)                      |
| `ANGEL_API_KEY`      | ⚠️ Live  | Angel One SmartAPI key                               |
| `ANGEL_CLIENT_ID`    | ⚠️ Live  | Angel One client ID                                  |
| `ANGEL_MPIN`         | ⚠️ Live  | Angel One MPIN                                       |
| `ANGEL_TOTP_SECRET`  | ⚠️ Live  | Base32 TOTP secret                                   |
| `TELEGRAM_BOT_TOKEN` | Optional | Telegram bot token (alerts)                          |

> ⚠️ **Never commit `.env`.** The repository's `.gitignore` excludes it; verify before pushing.

### Frontend (`frontend/.env`)

| Variable                 | Required | Description                  |
|--------------------------|----------|------------------------------|
| `REACT_APP_BACKEND_URL`  | ✅       | Backend origin (no trailing `/api`) |

---

## Development Workflow

1. Pick a task from [TODO.md](TODO.md) or [docs/ROADMAP.md](docs/ROADMAP.md)
2. Create a branch: `git checkout -b feat/<short-name>`
3. Implement with tests (see [docs/TESTING.md](docs/TESTING.md))
4. Run the quality gate: `pytest` + `flake8` + `yarn build` (see [docs/QUALITY.md](docs/QUALITY.md))
5. Open a PR using the template in [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)

---

## Testing

```bash
# Backend unit + integration
cd backend
pytest tests/ -v

# Frontend (once configured)
cd frontend
yarn test
```

See [docs/TESTING.md](docs/TESTING.md) for the full strategy (unit / integration / contract / E2E).

---

## Documentation

| Document                                          | Purpose                                          |
|---------------------------------------------------|--------------------------------------------------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)      | System design, module boundaries, data flow      |
| [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)      | Coding standards, PR template, review checklist  |
| [docs/TESTING.md](docs/TESTING.md)                | Testing strategy & conventions                   |
| [docs/QUALITY.md](docs/QUALITY.md)                | Quality gates, lint, typecheck, CI               |
| [docs/ROADMAP.md](docs/ROADMAP.md)                | Feature backlog with effort / impact             |
| [memory/PRD.md](memory/PRD.md)                    | Original product requirements document           |
| [TODO.md](TODO.md)                                | Persistent, dated task tracker                   |

---

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md). Tier 1 priorities:

1. **WebSocket streaming** (replace 5s REST polling)
2. **Real backtesting** with NSE bhavcopy / Angel One historicals
3. **Telegram alert scheduler** (background `asyncio` task)
4. **Backend refactor** — split `server.py` into `routes/`, `services/`, `models/`

---

## Contributing

Read [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) before opening a PR. The TL;DR:

- Match the existing code style (see CONTRIBUTING)
- Add tests for any new logic
- Run the quality gate locally before pushing
- Keep PRs small and focused

---

## License

TBD. Until a license is added, treat this as **all rights reserved** by the authors.
