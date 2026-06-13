# Roadmap

> Feature backlog with **impact**, **effort**, and **status**. Use this to pick work; update as items move.

**Legend**
- Impact: 🔥 high · ⚡ medium · 💡 low
- Effort: S (< 1d) · M (1-3d) · L (1w) · XL (2w+)
- Status: 🟡 in progress · ⏳ queued · ✅ done · ❌ cancelled

---

## Tier 1 — Highest impact

| # | Feature                              | Impact | Effort | Status | Notes                                  |
|---|--------------------------------------|--------|--------|--------|----------------------------------------|
| 1 | **WebSocket streaming**              | 🔥     | L      | ⏳     | Replace 5s REST polling; biggest UX win |
| 2 | **Real backtesting** (bhavcopy)      | 🔥     | M-L    | ⏳     | NSE daily bhavcopy + Angel One historical |
| 3 | **Telegram alert scheduler**         | 🔥     | M      | ⏳     | Background `asyncio` task; wires P0    |
| 4 | **Backend refactor** (split server)  | 🔥     | M      | ⏳     | `routes/`, `services/`, `models/`, `core/` |
| 5 | **Persistent Angel session**         | 🔥     | S      | ⏳     | Store `refresh_token` in Mongo, auto re-login |

---

## Tier 2 — Differentiating features

| # | Feature                                       | Impact | Effort | Status |
|---|-----------------------------------------------|--------|--------|--------|
| 6 | Order-book depth + TOB arbitrage              | 🔥     | M      | ⏳     |
| 7 | Multi-leg options strategy builder + payoff   | ⚡     | L      | ⏳     |
| 8 | Calendar-spread auto-scanner                  | ⚡     | M      | ⏳     |
| 9 | In-app notification center                    | ⚡     | S      | ⏳     |
| 10| User-defined pairs watchlist (z-score alerts) | ⚡     | M      | ⏳     |
| 11| Per-strike intraday candles (volume profile)  | 💡     | L      | ⏳     |
| 12| React Query + `useApiQuery` hook             | ⚡     | S-M    | ⏳     |
| 13| OpenAPI-generated typed TS client             | 💡     | S      | ⏳     |
| 14| Position tracker (PnL by leg)                 | ⚡     | M      | ⏳     |
| 15| Community-shared watchlists / signal templates| 💡     | L      | ⏳     |
| 16| Dark/light theme toggle                       | 💡     | S      | ⏳     |
| 17| Prometheus metrics + Grafana dashboard        | 💡     | M      | ⏳     |
| 18| Redis cache (replace in-memory)               | ⚡     | M      | ⏳     |
| 19| TimescaleDB / InfluxDB for IV history         | 💡     | M      | ⏳     |

---

## Tier 3 — Platform / hygiene

| # | Feature                                | Impact | Effort |
|---|----------------------------------------|--------|--------|
| 20| Frontend test suite (Jest + RTL)       | ⚡     | M      |
| 21| E2E tests (Playwright)                 | ⚡     | M      |
| 22| Pre-commit hooks                       | 💡     | S      |
| 23| mypy strict on `services/` & `routes/` | 💡     | S      |
| 24| Structured JSON logging + request-id   | 💡     | S      |
| 25| Rate limiting (per-IP)                 | 💡     | S      |
| 26| Renovate / Dependabot                  | 💡     | S      |
| 27| Docker compose for full stack          | 💡     | M      |
| 28| CORS allowlist (env-driven)            | 💡     | S      |
| 29| CSV export for any table               | 💡     | S      |
| 30| Pinned migration tooling (Alembic-style for Mongo) | 💡 | S |

---

## Carried over from the original PRD backlog

From `memory/PRD.md` — still open:

### P0
- [ ] Telegram integration for arbitrage alerts → covered by Tier 1 #3

### P1
- [ ] WebSocket architecture for real-time data → covered by Tier 1 #1
- [ ] Deep-dive pages with live data for Cash & Carry, Synthetic, Calendar, Statistical → split: each page is S, but live data depends on #1
- [ ] Fix missing OHLC data (Change/Volume columns show "—" for batch LTP) → Tier 1 polish

### P2
- [ ] PostgreSQL migration → not on this roadmap; reconsider when we add user-facing PnL/positions at scale
- [ ] Backtesting with historical data → covered by Tier 1 #2
- [ ] Advanced Analytics Dashboard (Strategy PnL, Weekday performance) → Tier 2 #14

### Refactoring
- [ ] Split `server.py` monolith into `routes/`, `services/`, `models/` → covered by Tier 1 #4

---

## How to pick up an item

1. Move it to **In Progress** in `TODO.md` (and add a `🟡` here)
2. Create branch: `git checkout -b feat/<short-name>`
3. Read [CONTRIBUTING.md](CONTRIBUTING.md) and [TESTING.md](TESTING.md)
4. Implement + test
5. Update this file: change `⏳` → `✅` and add the PR link
