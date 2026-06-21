"""FastAPI deps — service availability flags only. No auth, no database."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

logger = logging.getLogger(__name__)

# ── Service availability flags (populated by server.py on startup) ──

_ANGEL_ONE_AVAILABLE: bool = False
_BROKERS_MODULE_AVAILABLE: bool = False
_OPTION_CHAIN_AVAILABLE: bool = False
_IV_ANALYTICS_AVAILABLE: bool = False


def set_service_flags(
    angel_one: bool = False,
    brokers: bool = False,
    option_chain: bool = False,
    iv_analytics: bool = False,
):
    """Called by server.py at startup after try/except imports."""
    global _ANGEL_ONE_AVAILABLE, _BROKERS_MODULE_AVAILABLE, _OPTION_CHAIN_AVAILABLE, _IV_ANALYTICS_AVAILABLE
    _ANGEL_ONE_AVAILABLE = angel_one
    _BROKERS_MODULE_AVAILABLE = brokers
    _OPTION_CHAIN_AVAILABLE = option_chain
    _IV_ANALYTICS_AVAILABLE = iv_analytics


def is_brokers_available() -> bool:
    return _BROKERS_MODULE_AVAILABLE


def is_angel_available() -> bool:
    return _ANGEL_ONE_AVAILABLE


def is_iv_available() -> bool:
    return _IV_ANALYTICS_AVAILABLE


def is_option_chain_available() -> bool:
    return _OPTION_CHAIN_AVAILABLE


def get_market_session_info() -> Dict[str, Any]:
    """Determine Indian market session status based on IST time."""
    ist = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist)
    weekday = now_ist.weekday()
    current_minutes = now_ist.hour * 60 + now_ist.minute

    pre_open = 9 * 60
    market_open = 9 * 60 + 15
    market_close = 15 * 60 + 30
    post_close = 16 * 60
    is_weekend = weekday >= 5

    if is_weekend:
        session = "closed"
        session_label = "Weekend - Market Closed"
        next_open = "Monday 09:15 IST"
    elif current_minutes < pre_open:
        session = "pre_market"
        session_label = "Pre-Market"
        next_open = "09:15 IST"
    elif current_minutes < market_open:
        session = "pre_open"
        session_label = "Pre-Open Session"
        next_open = "09:15 IST"
    elif current_minutes < market_close:
        session = "market_open"
        session_label = "Market Open"
        mins_left = market_close - current_minutes
        next_open = f"Closes in {mins_left // 60}h {mins_left % 60}m"
    elif current_minutes < post_close:
        session = "post_market"
        session_label = "Post-Market / Closing Session"
        next_open = "Next trading day 09:15 IST"
    else:
        session = "closed"
        session_label = "Market Closed"
        next_open = "Next trading day 09:15 IST"

    return {
        "session": session,
        "session_label": session_label,
        "is_market_open": session == "market_open",
        "is_trading_hours": session in ("market_open", "pre_open"),
        "current_time_ist": now_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
        "next_event": next_open,
        "is_weekend": is_weekend,
    }
