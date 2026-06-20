"""
Angel One SmartAPI provider — Publisher Login (redirect) flow.

User experience (Teji-Mandi-like):
1. UI calls POST /api/brokers/angel_one/connect with state token.
2. Backend returns Angel One publisher-login URL.
3. User logs in on Angel One's own site (Client ID + MPIN + OTP) — we never see these.
4. Angel One redirects to our /api/brokers/angel_one/callback with auth_token, feed_token, refresh_token.
5. Backend exchanges/validates the token, fetches profile, stores session IN MEMORY.

Platform-level credentials required (from Angel One SmartAPI dashboard, ONE TIME, by app owner):
    ARBIT_ANGEL_API_KEY      — public API key (safe to send to client)
    ARBIT_ANGEL_REDIRECT_URL — registered redirect URL (must EXACTLY match SmartAPI app)

Reference: https://smartapi.angelbroking.com/docs/Authentication
"""
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from urllib.parse import urlencode

from SmartApi import SmartConnect

from .base import BrokerProvider, BrokerSession, BrokerProfile

logger = logging.getLogger(__name__)

# Angel One tokens are valid until ~5:30 AM IST next day. We conservatively cap at 12h.
DEFAULT_TOKEN_TTL_HOURS = 12


class AngelOneProvider(BrokerProvider):
    broker_id = "angel_one"
    display_name = "Angel One"
    auth_type = "redirect"
    logo_url = "https://www.angelone.in/assets/images/logo.svg"
    website = "https://www.angelone.in"

    LOGIN_BASE_URL = "https://smartapi.angelbroking.com/publisher-login"

    def __init__(self) -> None:
        # Re-read at every access so users editing .env don't need to restart code
        pass

    # ----------- Platform config -----------

    @property
    def api_key(self) -> str:
        return os.environ.get("ARBIT_ANGEL_API_KEY", "").strip()

    @property
    def api_secret(self) -> str:
        # Optional; not required for publisher-login flow but kept for future use
        return os.environ.get("ARBIT_ANGEL_API_SECRET", "").strip()

    @property
    def redirect_url(self) -> str:
        return os.environ.get("ARBIT_ANGEL_REDIRECT_URL", "").strip()

    def is_platform_configured(self) -> bool:
        return bool(self.api_key)

    # ----------- Auth flow -----------

    def build_login_url(self, state: str) -> str:
        if not self.is_platform_configured():
            raise RuntimeError(
                "Angel One platform credentials not configured. "
                "Set ARBIT_ANGEL_API_KEY in backend/.env"
            )
        params = {"api_key": self.api_key, "state": state}
        return f"{self.LOGIN_BASE_URL}?{urlencode(params)}"

    def handle_callback(self, params: Dict[str, Any]) -> BrokerSession:
        """
        Angel One publisher login redirects with these query params on success:
          auth_token, feed_token, refresh_token, state

        On failure it may return: status=false, message=...
        """
        auth_token = params.get("auth_token") or params.get("authToken")
        refresh_token = params.get("refresh_token") or params.get("refreshToken")
        feed_token = params.get("feed_token") or params.get("feedToken")

        if not auth_token:
            err = params.get("message") or params.get("error") or "Missing auth_token in callback"
            raise ValueError(f"Angel One login failed: {err}")

        # Fetch profile to verify token & capture client_id + name
        profile = self._fetch_profile(auth_token, refresh_token)

        expires_at = datetime.now(timezone.utc) + timedelta(hours=DEFAULT_TOKEN_TTL_HOURS)

        return BrokerSession(
            user_id="",  # filled in by router
            broker_id=self.broker_id,
            auth_token=auth_token,
            refresh_token=refresh_token,
            feed_token=feed_token,
            expires_at=expires_at,
            profile=profile,
        )

    def _fetch_profile(self, auth_token: str, refresh_token: Optional[str]) -> Optional[BrokerProfile]:
        """Call Angel One's getProfile endpoint to verify token and grab client_id."""
        try:
            sc = SmartConnect(api_key=self.api_key)
            # The SDK uses access_token internally for authenticated calls
            sc.setAccessToken(auth_token)
            if refresh_token:
                try:
                    sc.setRefreshToken(refresh_token)
                except Exception:
                    pass
            resp = sc.getProfile(refresh_token) if refresh_token else sc.getProfile()
            if not resp or not resp.get("status"):
                logger.warning("Angel One getProfile returned non-success: %s", resp)
                return None
            data = resp.get("data", {}) or {}
            return BrokerProfile(
                broker_id=self.broker_id,
                client_id=data.get("clientcode") or data.get("clientCode") or "",
                name=data.get("name"),
                email=data.get("email"),
                exchanges=data.get("exchanges", []) or [],
                products=data.get("products", []) or [],
                raw=data,
            )
        except Exception as e:
            logger.warning("Angel One getProfile failed: %s", e)
            return None

    # ----------- Optional: market data -----------

    def get_ltp(self, session: BrokerSession, symbol: str, exchange: str = "NSE") -> Optional[Dict[str, Any]]:
        """Lightweight LTP fetch using the user's session token."""
        try:
            sc = SmartConnect(api_key=self.api_key)
            sc.setAccessToken(session.auth_token)
            # Symbol token lookup is delegated to the legacy SYMBOL_TOKENS map; not
            # implementing here to avoid duplication. Routes can call the existing
            # angel_one_service.get_quote() patterns once a session is available.
            return None
        except Exception as e:
            logger.warning("Angel One LTP fetch failed: %s", e)
            return None
