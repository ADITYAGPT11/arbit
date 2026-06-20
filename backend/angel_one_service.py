"""
Angel One SmartAPI Integration Service (REFACTORED)
- No longer logs in with personal credentials from .env
- Pulls auth_token / feed_token from the in-memory BrokerSessionManager
  (populated when a user connects via /api/brokers/angel_one/* publisher-login flow)
- If no user session is active, returns None / empty so server.py falls back to simulated data
"""

import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from SmartApi import SmartConnect
import threading

logger = logging.getLogger(__name__)

# Symbol token mapping for popular F&O stocks
SYMBOL_TOKENS = {
    "RELIANCE": {"nse_token": "2885", "bse_token": "500325", "lot_size": 250},
    "TCS": {"nse_token": "11536", "bse_token": "532540", "lot_size": 150},
    "HDFCBANK": {"nse_token": "1333", "bse_token": "500180", "lot_size": 550},
    "INFY": {"nse_token": "1594", "bse_token": "500209", "lot_size": 300},
    "ICICIBANK": {"nse_token": "4963", "bse_token": "532174", "lot_size": 700},
    "HINDUNILVR": {"nse_token": "1394", "bse_token": "500696", "lot_size": 300},
    "ITC": {"nse_token": "1660", "bse_token": "500875", "lot_size": 1600},
    "SBIN": {"nse_token": "3045", "bse_token": "500112", "lot_size": 1500},
    "BHARTIARTL": {"nse_token": "10604", "bse_token": "532454", "lot_size": 475},
    "KOTAKBANK": {"nse_token": "1922", "bse_token": "500247", "lot_size": 400},
    "LT": {"nse_token": "11483", "bse_token": "500510", "lot_size": 150},
    "AXISBANK": {"nse_token": "5900", "bse_token": "532215", "lot_size": 625},
    "ASIANPAINT": {"nse_token": "236", "bse_token": "500820", "lot_size": 200},
    "MARUTI": {"nse_token": "10999", "bse_token": "532500", "lot_size": 50},
    "TITAN": {"nse_token": "14977", "bse_token": "500114", "lot_size": 175},
    "BAJFINANCE": {"nse_token": "317", "bse_token": "500034", "lot_size": 125},
    "WIPRO": {"nse_token": "3787", "bse_token": "507685", "lot_size": 1500},
    "HCLTECH": {"nse_token": "7229", "bse_token": "532281", "lot_size": 350},
    "SUNPHARMA": {"nse_token": "3351", "bse_token": "524715", "lot_size": 350},
    "ULTRACEMCO": {"nse_token": "11532", "bse_token": "532538", "lot_size": 50},
    "TATASTEEL": {"nse_token": "3499", "bse_token": "500470", "lot_size": 3375},
    "POWERGRID": {"nse_token": "14977", "bse_token": "532898", "lot_size": 2700},
    "NTPC": {"nse_token": "11630", "bse_token": "532555", "lot_size": 1575},
    "ONGC": {"nse_token": "2475", "bse_token": "500312", "lot_size": 1925},
    "TATAMOTORS": {"nse_token": "3456", "bse_token": "500570", "lot_size": 575},
    "ADANIENT": {"nse_token": "25", "bse_token": "512599", "lot_size": 250},
    "TECHM": {"nse_token": "13538", "bse_token": "532755", "lot_size": 300},
    "BAJAJFINSV": {"nse_token": "16675", "bse_token": "532978", "lot_size": 500},
    "INDUSINDBK": {"nse_token": "5258", "bse_token": "532187", "lot_size": 400},
    "JSWSTEEL": {"nse_token": "11723", "bse_token": "500228", "lot_size": 675},
}

# Index tokens
INDEX_TOKENS = {
    "NIFTY": {"token": "99926000", "exchange": "NSE"},
    "BANKNIFTY": {"token": "99926009", "exchange": "NSE"},
    "FINNIFTY": {"token": "99926037", "exchange": "NSE"},
    "SENSEX": {"token": "99919000", "exchange": "BSE"},
    "BANKEX": {"token": "99919016", "exchange": "BSE"},
}


class AngelOneService:
    """
    Service for Angel One SmartAPI — token-less wrapper.
    Looks up an active broker session (from BrokerSessionManager) on each call.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.last_error: Optional[str] = None
        logger.info("AngelOneService initialized (publisher-login mode)")

    # --------------- session lookup ---------------

    @property
    def api_key(self) -> str:
        return os.environ.get("ARBIT_ANGEL_API_KEY", "").strip()

    def _get_active_session(self):
        """Pull any active publisher-login session from the in-memory manager."""
        try:
            from brokers import session_manager
        except Exception as e:
            self.last_error = f"brokers module not available: {e}"
            return None
        return session_manager.any_active_for_broker("angel_one")

    def _make_smart_api(self, auth_token: str) -> Optional[SmartConnect]:
        if not self.api_key:
            self.last_error = "ARBIT_ANGEL_API_KEY missing in backend/.env"
            return None
        try:
            sc = SmartConnect(api_key=self.api_key)
            sc.setAccessToken(auth_token)
            return sc
        except Exception as e:
            self.last_error = f"SmartConnect init failed: {e}"
            logger.error(self.last_error)
            return None

    def is_connected(self) -> bool:
        return self._get_active_session() is not None

    # --------------- public data methods ---------------

    def get_ltp(self, symbol: str, exchange: str = "NSE") -> Optional[Dict[str, Any]]:
        session = self._get_active_session()
        if not session:
            return None
        sc = self._make_smart_api(session.auth_token)
        if not sc:
            return None
        try:
            token_info = SYMBOL_TOKENS.get(symbol)
            if not token_info:
                return None
            token = token_info.get(f"{exchange.lower()}_token") or token_info.get("nse_token")
            trading_symbol = f"{symbol}-EQ"
            data = sc.ltpData(exchange, trading_symbol, token)
            if data.get("status") and data.get("data"):
                ltp_data = data["data"]
                return {
                    "symbol": symbol,
                    "exchange": exchange,
                    "price": float(ltp_data.get("ltp", 0)),
                    "open": float(ltp_data.get("open", 0)),
                    "high": float(ltp_data.get("high", 0)),
                    "low": float(ltp_data.get("low", 0)),
                    "prev_close": float(ltp_data.get("close", 0)),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
        except Exception as e:
            logger.debug(f"LTP fetch error for {symbol}: {e}")
        return None

    def get_quote(self, symbol: str, exchange: str = "NSE") -> Optional[Dict[str, Any]]:
        ltp_data = self.get_ltp(symbol, exchange)
        if ltp_data:
            prev = ltp_data.get("prev_close", 0)
            price = ltp_data.get("price", 0)
            if prev and prev > 0:
                ltp_data["change"] = round(price - prev, 2)
                ltp_data["change_pct"] = round(((price - prev) / prev) * 100, 2)
            else:
                ltp_data["change"] = 0
                ltp_data["change_pct"] = 0
            ltp_data["volume"] = 0
        return ltp_data

    def get_all_indices(self) -> List[Dict[str, Any]]:
        session = self._get_active_session()
        if not session:
            return []
        sc = self._make_smart_api(session.auth_token)
        if not sc:
            return []
        try:
            nse_tokens, bse_tokens = [], []
            for _, info in INDEX_TOKENS.items():
                (nse_tokens if info["exchange"] == "NSE" else bse_tokens).append(info["token"])

            exchange_tokens = {}
            if nse_tokens:
                exchange_tokens["NSE"] = nse_tokens
            if bse_tokens:
                exchange_tokens["BSE"] = bse_tokens

            data = sc.getMarketData(mode="LTP", exchangeTokens=exchange_tokens)
            if data.get("status") and data.get("data", {}).get("fetched"):
                token_to_name = {info["token"]: name for name, info in INDEX_TOKENS.items()}
                results = []
                for item in data["data"]["fetched"]:
                    token = item.get("symbolToken")
                    index_name = token_to_name.get(token)
                    if index_name:
                        results.append({
                            "index": index_name,
                            "value": float(item.get("ltp", 0)),
                            "prev_close": None,
                            "change": None,
                            "change_pct": None,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "trading_symbol": item.get("tradingSymbol"),
                        })
                return results
        except Exception as e:
            logger.error(f"Error fetching indices: {e}")
        return []

    def get_multiple_stocks_batch(self, symbols: List[str], exchange: str = "NSE") -> List[Dict[str, Any]]:
        session = self._get_active_session()
        if not session:
            return []
        sc = self._make_smart_api(session.auth_token)
        if not sc:
            return []
        try:
            tokens = []
            symbol_map = {}
            for symbol in symbols:
                token_info = SYMBOL_TOKENS.get(symbol)
                if token_info:
                    token = token_info.get(f"{exchange.lower()}_token") or token_info.get("nse_token")
                    if token:
                        tokens.append(token)
                        symbol_map[token] = symbol
            if not tokens:
                return []

            data = sc.getMarketData(mode="LTP", exchangeTokens={exchange: tokens})
            if data.get("status") and data.get("data", {}).get("fetched"):
                results = []
                for item in data["data"]["fetched"]:
                    token = item.get("symbolToken")
                    symbol = symbol_map.get(token)
                    if symbol:
                        results.append({
                            "symbol": symbol,
                            "exchange": exchange,
                            "price": float(item.get("ltp", 0)),
                            "open": None,
                            "high": None,
                            "low": None,
                            "prev_close": None,
                            "change": None,
                            "change_pct": None,
                            "volume": None,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "data_source": "angel_one_live",
                        })
                return results
        except Exception as e:
            logger.error(f"Error batch fetching stocks: {e}")
        return []

    def get_session_status(self) -> Dict[str, Any]:
        session = self._get_active_session()
        is_connected = session is not None
        return {
            "is_connected": is_connected,
            "client_id": (session.profile.client_id[:4] + "***") if (session and session.profile and session.profile.client_id) else None,
            "last_login": session.connected_at.isoformat() if session else None,
            "session_expiry": session.expires_at.isoformat() if session and session.expires_at else None,
            "time_remaining": str(session.expires_at - datetime.now(timezone.utc)) if session and session.expires_at and is_connected else None,
            "last_error": self.last_error,
            "login_attempts": 0,
            "credentials_configured": bool(self.api_key),
            "auth_mode": "publisher_login",
        }

    # --------------- legacy no-op methods (kept for server.py compat) ---------------

    def login(self) -> bool:
        """Legacy method. New flow uses publisher-login (per-user). Always False."""
        # No error message — this is expected at startup, not an actual failure.
        return False

    def ensure_session(self) -> bool:
        return self._get_active_session() is not None

    def reset_login_attempts(self):
        self.last_error = None

    def logout(self):
        """No-op — sessions are owned by BrokerSessionManager, disconnect via /api/brokers/{id}/disconnect."""
        self.last_error = None


# Global instance
angel_service = AngelOneService()


def get_angel_service() -> AngelOneService:
    return angel_service
