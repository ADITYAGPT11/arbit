"""
Personal "system" auto-login for Angel One (DEV / single-operator mode).

If ALL personal credentials are set in backend/.env:
    ANGEL_API_KEY, ANGEL_CLIENT_ID, ANGEL_MPIN, ANGEL_TOTP_SECRET
then on backend startup we'll call SmartConnect.generateSession() once with TOTP,
and store the resulting tokens under user_id="_system" in BrokerSessionManager.

This is ADDITIVE to the multi-user publisher-login flow:
- Any real user can still call /api/brokers/angel_one/connect → their own session.
- Market-data routes use `any_active_for_broker("angel_one")` which picks up
  either the _system session or any user session (whichever is alive).

Re-login is attempted in the background every 6 hours (Angel One tokens expire
at the next 5:30 AM IST). Failures are non-fatal — market data falls back to
"angel_one_unavailable".
"""
from __future__ import annotations

import os
import logging
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import pyotp
from SmartApi import SmartConnect

from .base import BrokerProfile, BrokerSession
from .session_manager import session_manager

logger = logging.getLogger(__name__)

SYSTEM_USER_ID = "_system"
BROKER_ID = "angel_one"

# Angel One jwtToken expires daily at 05:30 IST. We refresh slightly before that.
# IST = UTC+5:30, so 05:30 IST == 00:00 UTC.
# Refresh every 4 hours during the day (cheap with refreshToken; full TOTP only on failure).
REFRESH_INTERVAL = timedelta(hours=4)

# Cache of the authenticated SmartConnect client (the SDK keeps internal state after generateSession;
# rebuilding from just access_token doesn't fully restore it — Angel One returns "Invalid Token").
_smart_client: Optional[SmartConnect] = None
_smart_client_lock = threading.Lock()


def _next_token_expiry_utc() -> datetime:
    """Return the next 05:30 IST (== 00:00 UTC) as a UTC datetime."""
    now = datetime.now(timezone.utc)
    expiry = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if expiry <= now:
        expiry = expiry + timedelta(days=1)
    return expiry


def get_client() -> Optional[SmartConnect]:
    """Return the live SmartConnect client from the system auto-login, or None."""
    with _smart_client_lock:
        return _smart_client


def _read_creds() -> Optional[dict]:
    creds = {
        "api_key": os.environ.get("ANGEL_API_KEY", "").strip(),
        "client_id": os.environ.get("ANGEL_CLIENT_ID", "").strip(),
        "mpin": os.environ.get("ANGEL_MPIN", "").strip(),
        "totp_secret": os.environ.get("ANGEL_TOTP_SECRET", "").strip(),
    }
    if not all(creds.values()):
        return None
    return creds


def is_enabled() -> bool:
    return _read_creds() is not None


def login_now() -> Optional[BrokerSession]:
    """Perform one TOTP-based login. Returns the BrokerSession on success, None on failure."""
    creds = _read_creds()
    if not creds:
        logger.info("System auto-login skipped — personal Angel One credentials not configured")
        return None

    try:
        sc = SmartConnect(api_key=creds["api_key"])
        totp_code = pyotp.TOTP(creds["totp_secret"]).now()
        data = sc.generateSession(creds["client_id"], creds["mpin"], totp_code)

        if not data or not data.get("status"):
            logger.error("System auto-login failed: %s", data)
            return None

        d = data.get("data") or {}
        auth_token = d.get("jwtToken") or d.get("jwt")
        refresh_token = d.get("refreshToken")
        feed_token = sc.getfeedToken()

        if not auth_token:
            logger.error("System auto-login: no jwtToken in response: %s", data)
            return None

        # Fetch profile (best-effort)
        profile_obj = None
        try:
            prof = sc.getProfile(refresh_token) if refresh_token else None
            if prof and prof.get("status") and prof.get("data"):
                p = prof["data"]
                profile_obj = BrokerProfile(
                    broker_id=BROKER_ID,
                    client_id=p.get("clientcode") or creds["client_id"],
                    name=p.get("name"),
                    email=p.get("email"),
                    exchanges=p.get("exchanges") or [],
                    products=p.get("products") or [],
                )
        except Exception as e:
            logger.debug("getProfile failed (non-fatal): %s", e)

        if not profile_obj:
            profile_obj = BrokerProfile(broker_id=BROKER_ID, client_id=creds["client_id"])

        session = BrokerSession(
            user_id=SYSTEM_USER_ID,
            broker_id=BROKER_ID,
            auth_token=auth_token,
            refresh_token=refresh_token,
            feed_token=feed_token,
            # Angel One jwtToken expires daily at 05:30 IST (== 00:00 UTC).
            expires_at=_next_token_expiry_utc(),
            profile=profile_obj,
        )
        session_manager.set(session)
        with _smart_client_lock:
            global _smart_client
            _smart_client = sc
        logger.info(
            "System auto-login OK (Angel One) client=%s***",
            (profile_obj.client_id[:4] if profile_obj.client_id else "????")
        )
        return session
    except Exception as e:
        logger.error("System auto-login error: %s", e, exc_info=True)
        return None


# ---------------- refresh-token based refresh (no TOTP needed) ----------------

def refresh_session() -> Optional[BrokerSession]:
    """
    Mint a new jwtToken using the existing refreshToken — no MPIN/TOTP required.
    Returns the refreshed BrokerSession on success, None on failure (caller should fall back to login_now).
    """
    existing = session_manager.get(SYSTEM_USER_ID, BROKER_ID)
    if not existing or not existing.refresh_token:
        return None

    client = get_client()
    if client is None:
        return None

    try:
        data = client.generateToken(existing.refresh_token)
        if not data or not data.get("status"):
            logger.warning("Refresh-token call failed: %s", data)
            return None

        d = data.get("data") or {}
        new_jwt = d.get("jwtToken") or d.get("jwt")
        new_refresh = d.get("refreshToken") or existing.refresh_token
        new_feed = d.get("feedToken") or existing.feed_token

        if not new_jwt:
            logger.warning("Refresh response missing jwtToken: %s", data)
            return None

        # Update the SDK client's internal token so cached calls keep working.
        try:
            client.setAccessToken(new_jwt)
            if new_feed and hasattr(client, "setFeedToken"):
                client.setFeedToken(new_feed)
        except Exception:
            pass

        refreshed = BrokerSession(
            user_id=SYSTEM_USER_ID,
            broker_id=BROKER_ID,
            auth_token=new_jwt,
            refresh_token=new_refresh,
            feed_token=new_feed,
            expires_at=_next_token_expiry_utc(),
            connected_at=existing.connected_at,  # preserve original login time
            profile=existing.profile,
        )
        session_manager.set(refreshed)
        logger.info("System session refreshed via refresh-token (no TOTP). next expiry=%s", refreshed.expires_at)
        return refreshed
    except Exception as e:
        logger.warning("refresh_session error: %s", e)
        return None


# ---------------- background refresher ----------------

_stop_event = threading.Event()
_thread: Optional[threading.Thread] = None


def _refresh_loop() -> None:
    """Sleep for REFRESH_INTERVAL, then refresh. Prefer refresh-token; fall back to full login."""
    while not _stop_event.wait(REFRESH_INTERVAL.total_seconds()):
        if not is_enabled():
            continue
        # Cheap path first
        if refresh_session() is None:
            # Refresh-token didn't work — re-do the full TOTP login
            logger.info("Refresh-token failed, falling back to full TOTP login")
            login_now()


def start_background_refresher() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    if not is_enabled():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_refresh_loop, name="system-broker-refresh", daemon=True)
    _thread.start()
    logger.info("System broker refresher started (every %s)", REFRESH_INTERVAL)


def stop_background_refresher() -> None:
    _stop_event.set()
