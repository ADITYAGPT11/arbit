# TODO

> **Persistent, dated task tracker.** Update this as you work — it's the single source of truth for what's in progress, blocked, or done.
>
> Conventions:
> - One line per task
> - Prefix: `[ ]` pending · `[~]` in progress · `[x]` done · `[!]` blocked · `[-]` cancelled
> - Tag with the relevant module/scope in brackets: `[be]`, `[fe]`, `[ci]`, `[docs]`, `[refactor]`
> - Include a date stamp when status changes
> - Link to the PR or issue in parentheses when one exists

---

## 🔥 Tier 1 — Doing first

- [x] [docs] Create professional README + docs/ skeleton — 2026-06-13
- [x] [docs] Write ARCHITECTURE / CONTRIBUTING / TESTING / QUALITY / ROADMAP — 2026-06-13
- [x] [docs] Create TODO.md (this file) — 2026-06-13
- [x] [docs] Create MODEL_HANDBOOK.md (AI model onboarding guide) — 2026-06-13
- [ ] [ci]  Add GitHub Actions workflow (lint + test + build)
- [ ] [be]  Wire flake8/black/isort configs (backend/.flake8, pyproject.toml)
- [ ] [be]  **Refactor**: split `backend/server.py` → `routes/`, `services/`, `models/`, `core/`
- [ ] [be]  **Telegram alert scheduler** (background `asyncio` task)
- [ ] [be]  **WebSocket streaming** endpoint (replace 5s REST polling)
- [ ] [be]  **Real backtesting** with NSE bhavcopy + Angel One historicals
- [ ] [be]  **Persistent Angel One session** (store `refresh_token` in Mongo, auto re-login)
- [ ] [infra] **Production CORS** — Replace `["*"]` with env-driven allowlist
- [ ] [chore] **Commit documentation sprint** — Stage and commit docs/, .env.example files

## ✅ Just now — 2026-06-14 Setup Sprint

- [x] [be] Install Python 3.12.10 via winget — 2026-06-14
- [x] [be] Create `.venv` and install all 131 backend deps — 2026-06-14
- [x] [be] Remove `emergentintegrations` from requirements.txt (unavailable package, never imported) — 2026-06-14
- [x] [be] Create `backend/.env` with MONGO_URL + DB_NAME — 2026-06-14
- [x] [fe] Create `frontend/.env` with REACT_APP_BACKEND_URL — 2026-06-14
- [x] [fe] Install frontend deps (1494 packages via npm) — 2026-06-14
- [x] [fe] Fix `@/` alias imports → relative imports in `frontend/src/index.js` — 2026-06-14
- [x] [infra] Start backend on :8000 (health check green) — 2026-06-14
- [x] [infra] Start frontend on :3000 (compiled successfully) — 2026-06-14
- [x] [infra] Local MongoDB connected at localhost:27017/arbitpro — 2026-06-14
- [x] [scripts] Create `scripts/start.ps1` — one-click server launcher with prerequisite checks — 2026-06-14
- [x] [scripts] Create `scripts/stop.ps1` — one-click server stopper — 2026-06-14

## ⚡ Tier 2 — Next up

- [ ] [be]  Order-book depth + top-of-book arbitrage
- [ ] [fe]  React Query + `useApiQuery` hook (replace raw `useEffect + axios`)
- [ ] [fe]  Multi-leg options strategy builder + payoff diagram
- [ ] [be]  Calendar-spread auto-scanner
- [ ] [fe]  In-app notification center
- [ ] [be]  User-defined pairs watchlist (z-score alerts)
- [ ] [be]  Position tracker (PnL by leg)
- [ ] [infra] Redis cache (replace in-memory 2s cache)

## 💡 Tier 3 — Hygiene & polish

- [ ] [fe]  Frontend test suite (Jest + React Testing Library)
- [ ] [fe]  E2E tests (Playwright)
- [ ] [chore] Pre-commit hooks
- [ ] [be]  mypy strict on `services/` & `routes/`
- [ ] [be]  Structured JSON logging + request-id correlation
- [ ] [be]  Rate limiting (per-IP)
- [ ] [chore] Renovate / Dependabot
- [ ] [infra] Docker compose for full stack
- [ ] [be]  CORS allowlist (env-driven, drop `["*"]`)
- [ ] [fe]  CSV export for any table
- [ ] [fe]  Dark/light theme toggle (Radix + next-themes already installed)
- [ ] [be]  TimescaleDB / InfluxDB for IV history

## 🐛 Known bugs / minor

- [ ] [be]  Fix missing OHLC data (Change/Volume show "—" for batch LTP) — from PRD P1
- [ ] [fe]  Add `--depth` and `--strikes` URL params to OptionChain share-link

---

## ✅ Done

_(append completed items with date and PR link)_

- [x] [docs] Create `docs/` directory and seed it — 2026-06-13
- [x] [docs] Write `README.md` (replaces 1-line stub) — 2026-06-13
- [x] [docs] Write `docs/ARCHITECTURE.md` — 2026-06-13
- [x] [docs] Write `docs/CONTRIBUTING.md` — 2026-06-13
- [x] [docs] Write `docs/TESTING.md` — 2026-06-13
- [x] [docs] Write `docs/QUALITY.md` — 2026-06-13
- [x] [docs] Write `docs/ROADMAP.md` — 2026-06-13
- [x] [docs] Create `docs/MODEL_HANDBOOK.md` — 2026-06-13

---

## 📝 Handoff Notes

> **Cross-model communication channel.** When switching models, write a note here describing what was done and what's left.

- **2026-06-13** — Model (DeepSeek V4 Flash) finished documentation sprint: all 6 `docs/` files + README + TODO.md + MODEL_HANDBOOK.md created. Backend config files (.flake8, pyproject.toml) created but not yet wired. Tests exist but are HTTP-based (no unit tests yet). `test_result.md` has protocol header but no data. Model ran out of quota mid-session.
- **2026-06-14** — Full setup sprint completed. Python 3.12 installed via winget, .venv created, all backend/frontend deps installed. .env files created. Fixed `@/` alias issue in index.js. Backend running on :8000. Frontend running on :3000. MongoDB connected (local). Next: configure Angel One credentials for live data, or pick up Tier 1 feature work.

---

## 🚫 Won't do (for now)

_(capture deliberate non-goals here so we don't relitigate them)_

- Order **placement** (we are read-only — would need SEBI compliance review)
- Native mobile apps (responsive web only)
- Multi-tenant SaaS pricing tiers

---

## How to use this file

```bash
# When you start work
# 1. Change [ ] → [~] and add a date

# When you finish
# 2. Move the line to the "Done" section with [x] and PR link
# 3. Update docs/ROADMAP.md if the item came from there
```

> Rule of thumb: if an item is on this list for **> 2 weeks without movement**, move it to a "Backlog" section at the bottom of `docs/ROADMAP.md` and revisit during planning.
