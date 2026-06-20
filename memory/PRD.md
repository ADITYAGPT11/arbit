# ARBIT — Product Requirements Document

## Original Problem Statement
Build a "Connect Broker" module starting with Angel One, mimicking professional platforms like Teji Mandi. Users must be redirected to the broker's official login page to enter credentials — NO storage of MPIN / TOTP / password / API secrets in the database or .env. The architecture must be extensible to support more brokers in the future.

## Core Requirements
- Use broker's OAuth/Publisher-Login redirect flow (Angel One = Publisher Login).
- Do NOT store user-specific broker credentials in MongoDB or .env. Only platform-level API key lives in .env.
- Maintain in-memory session (BrokerSessionManager) for user tokens — lost on backend restart by design.
- Dedicated "/connect-broker" UI page.
- Extensible registry: drop in a new BrokerProvider subclass → UI auto-discovers it.

## What's Built (as of Feb 2026)

### Backend (`/app/backend/`)
- `brokers/base.py` — abstract `BrokerProvider`, `BrokerSession`, `BrokerProfile` dataclasses.
- `brokers/angel_one.py` — Angel One publisher-login implementation (`build_login_url`, `handle_callback` using SmartConnect SDK).
- `brokers/registry.py` — `BROKER_REGISTRY` dict: angel_one (active) + zerodha / upstox / fyers / icici_direct (coming-soon placeholders).
- `brokers/session_manager.py` — thread-safe in-memory store: `set/get/delete/list_for_user/any_active_for_broker` + CSRF state tokens (`create_state/consume_state`, 10 min TTL).
- `server.py` routes:
  - `GET  /api/brokers/list` — public, returns 5 brokers with platform_configured + per-user is_connected.
  - `POST /api/brokers/{broker_id}/connect` — auth required, returns publisher-login URL + state token.
  - `GET  /api/brokers/{broker_id}/callback` — public redirect target from broker; consumes state, stores session, redirects to `/connect-broker?status=...`.
  - `GET  /api/brokers/sessions` — auth required, lists user's active sessions.
  - `POST /api/brokers/{broker_id}/disconnect` — auth required, clears in-memory session.
- `angel_one_service.py` — refactored to pull tokens from `session_manager.any_active_for_broker("angel_one")` instead of personal `.env` creds. Legacy `login()` is now a silent no-op.

### Frontend (`/app/frontend/src/`)
- `pages/ConnectBroker.jsx` — Connect Broker UI: lists 5 brokers, Connect/Disconnect buttons, OAuth callback toast handling, "platform not configured" warnings, login prompt for unauthenticated users.
- `App.js` — `/connect-broker` route wired.
- `components/Layout.jsx` — "Connect Broker" sidebar nav item (Plug icon).
- `components/BrokerStatus.jsx` — legacy sidebar widget now redirects to `/connect-broker` instead of calling deprecated `/api/market/angel-one/login`.

### Configuration
- `backend/.env`:
  - `ARBIT_ANGEL_API_KEY=rbFr048b` (user-provided, Feb 2026)
  - `ARBIT_ANGEL_API_SECRET=` (optional; not needed for publisher-login)
  - `ARBIT_ANGEL_REDIRECT_URL=https://broker-integrator.preview.emergentagent.com/api/brokers/angel_one/callback`

## Testing Status
- iter7: brokers pytest suite 18/18 pass. Found 2 regressions in server.py callers → fixed.
- iter8: regressions verified fixed. Brokers feature is production-ready *up to actual end-to-end Angel One login* (which requires a real user MPIN/OTP test).

## Pending / Blocked

### P0 — End-to-end OAuth verification (requires user action)
Once you (or any user) clicks Connect on Angel One:
1. You should be redirected to `https://smartapi.angelbroking.com/publisher-login?api_key=rbFr048b&state=...`
2. You log in with Client ID + MPIN + OTP on Angel One's site
3. Angel One redirects to `https://broker-integrator.preview.emergentagent.com/api/brokers/angel_one/callback?auth_token=...&feed_token=...&state=...`
4. Backend stores the session in memory; you land back at `/connect-broker?status=success`.
**Cannot self-test** — needs real Angel One credentials and a logged-in ARBIT user. *Awaiting user smoke-test.*

### P1 — Optional polish
- Expose `auth_mode: "publisher_login"` field on `/api/market/broker-status` so the UI can render publisher-login-specific copy (low impact).
- Hide / deprecate the legacy `/api/market/angel-one/login` and `/api/market/angel-one/reset` endpoints — they're soft-broken (return 401) and could confuse callers.

### P2 — Future brokers
- Implement `ZerodhaProvider` (Kite Connect OAuth 2.0).
- Implement `UpstoxProvider` (OAuth 2.0).
- Implement `FyersProvider` (OAuth 2.0).
- Implement `IciciDirectProvider` (Breeze Connect).
For each: subclass `BrokerProvider`, implement `build_login_url` + `handle_callback`, swap from `_ComingSoonBroker` to active in `BROKER_REGISTRY`.

### P3 — Refactoring
- `server.py` is 2003 lines. Split into `/app/backend/routers/{brokers,market,arbitrage,auth}.py`.
- `broker_callback` hard-codes same-origin `/connect-broker` redirect — fragile if frontend host diverges in production. Use a `FRONTEND_URL` env var.

## Architecture Notes
- **No DB storage of broker tokens.** This is a hard requirement; do not change.
- **State tokens** (CSRF) are one-time-use, 10-min TTL.
- **Sessions** expire after 12 hours (Angel One tokens are valid until ~5:30 AM IST next day; we cap conservatively).
- **`any_active_for_broker()`** lets shared market-data routes (indices, stocks) use *any* logged-in user's session to fetch quotes. This is intentional — quotes are public data, the user who logged in just provides the auth token to call the SDK.

## Tech Stack
React + FastAPI + MongoDB. SmartAPI Python SDK for Angel One. Emergent-managed Google OAuth for app-level user authentication.
