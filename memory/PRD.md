# ArbitPRO - Indian Markets Arbitrage & F&O Analytics Platform

## Problem Statement
Build a production-grade Real-Time Multi-Exchange Arbitrage & F&O Analytics Platform for Indian Markets (NSE, BSE, MCX). Support NSE/BSE Cash, F&O, Index Derivatives. Arbitrage Engine (Cross-Exchange, Cash & Carry, Synthetic, Calendar Spreads, Statistical). Advanced Performance Analytics Dashboard. Ultra low-latency tick-by-tick processing. User requested: Angel One free API for real-time data, Telegram alerts, Google OAuth, and high performance.

## Architecture
- **Frontend**: React.js + TailwindCSS + Shadcn UI + Recharts
- **Backend**: FastAPI + Python (async) + GZip middleware
- **Database**: MongoDB (configured, minimal usage — live API data primary)
- **Broker API**: Angel One SmartAPI (live market data, batch API)
- **Auth**: Emergent-managed Google OAuth

## Key Files
- `/app/backend/server.py` — Main API (1600+ lines, routes + services)
- `/app/backend/angel_one_service.py` — Angel One session management, batch data
- `/app/backend/option_chain_service.py` — Instrument master, T-shaped chain builder
- `/app/frontend/src/components/Layout.jsx` — Responsive sidebar + mobile hamburger
- `/app/frontend/src/components/BrokerStatus.jsx` — Broker connection status
- `/app/frontend/src/pages/Dashboard.jsx` — Live market dashboard
- `/app/frontend/src/pages/OptionChain.jsx` — T-shaped option chain (auto-refresh 5s)

## What's Implemented

### Core Features (DONE)
- Angel One SmartAPI integration with auto-login, session management
- Live market indices (NIFTY, BANKNIFTY, FINNIFTY, SENSEX, BANKEX)
- Live F&O stock prices (NSE + BSE) via batch API
- Cross-exchange arbitrage scanner (NSE vs BSE)
- Cash & Carry, Synthetic, Calendar Spread, Statistical arbitrage calculators
- Performance analytics, risk management, backtesting modules
- Broker connection status with market session awareness (IST)
- Google OAuth via Emergent Auth

### T-Shaped Option Chain (DONE — June 2026)
- Real-time option chain with 5-second auto-refresh
- Instrument master download + indexed lookups (187K instruments)
- NIFTY, BANKNIFTY, FINNIFTY + 150+ stock options
- OI, Change in OI, Volume, IV, LTP, Change for CE and PE
- ATM strike highlighting, PCR calculation
- Summary bar: Total Call/Put OI, PCR, Volume

### Production & HFT Optimizations (DONE — June 2026)
- GZip response compression (77% reduction)
- asyncio.to_thread for blocking Angel One API calls
- In-memory response cache (2s TTL) for option chain polling
- Indexed instrument master (O(1) lookups vs O(n) scans)
- Batch API calls to Angel One (50 tokens per request)

### Mobile Responsive UI (DONE — June 2026)
- Hamburger menu sidebar toggle below 1024px
- Slide-in sidebar with overlay + close button
- Mobile header with logo + page name
- Responsive grids (2-col mobile, 5-col desktop for indices)
- Horizontal scroll for option chain table on mobile
- Adaptive summary cards (3 mobile, 5 desktop)
- Touch-friendly select controls

### IV Analytics — Options Seller's Toolkit (DONE — June 2026)
- Black-Scholes IV calculator (Newton-Raphson + Brent fallback, verified)
- ATM Implied Volatility computed from live option prices
- India VIX live feed (token 99926017 from Angel One)
- IV Rank: (Current IV - 52w Low) / (52w High - 52w Low) × 100
- IV Percentile: % of days where IV was below current
- Historical Volatility (HV): 20-day log returns, annualized √252
- IV Skew chart: CE IV (green) vs PE IV (red) across strikes
- Max Pain calculator: strike where total option buyer losses are maximized
- Seller Signal engine: SELL_PREMIUM / AVOID_SELLING / NEUTRAL with reasoning
- Daily IV & price snapshots stored in MongoDB (builds over time)
- Options Seller's Guide with educational reference cards

### UX Improvements (DONE — June 2026)
- Option chain banner: large bold symbol + blue expiry badge + spot price
- Labeled dropdowns (UNDERLYING, EXPIRY, STRIKES) for clarity
- CE = Green, PE = Red throughout (headers, LTP, ITM tints, summary bar)
- Dashboard arbitrage: full-width side-by-side NSE vs BSE cards
- BUY/SELL labels with green/red border tinting per exchange
- Cost breakdown: Gross Spread, Transaction Cost, Slippage (0.02%), Net Profit/Share
- Net profit color-coded green (profitable) / red (unprofitable)

## Pending / Backlog

### P0
- Telegram integration for arbitrage alerts

### P1
- WebSocket architecture for real-time data (replace REST polling)
- Deep-dive pages with live data for Cash & Carry, Synthetic, Calendar, Statistical
- Fix missing OHLC data (Change/Volume columns show "—" for batch LTP)

### P2
- PostgreSQL migration
- Backtesting with historical data
- Advanced Analytics Dashboard (Strategy PnL, Weekday performance)

### Refactoring
- Split server.py monolith into routes/, services/, models/ modules
