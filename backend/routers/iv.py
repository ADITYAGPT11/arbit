"""IV Analytics routes — IV dashboard, IV skew, max pain. No database, uses JSON file cache."""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException

from core.deps import is_angel_available, is_option_chain_available, is_iv_available

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/iv", tags=["IV Analytics"])

# JSON file cache for IV history (replaces MongoDB)
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
IV_HISTORY_FILE = DATA_DIR / "iv_history.json"
PRICE_HISTORY_FILE = DATA_DIR / "price_history.json"

try:
    from option_chain_service import get_option_chain_service
    from angel_one_service import get_angel_service, INDEX_TOKENS, SYMBOL_TOKENS
    from iv_analytics_service import (
        calculate_historical_volatility, calculate_iv_rank,
        calculate_iv_percentile, calculate_max_pain, build_iv_skew,
        get_atm_iv, detect_iv_signal, INDIA_VIX_TOKEN, INDIA_VIX_EXCHANGE,
    )
except ImportError:
    get_option_chain_service = None
    get_angel_service = None
    INDEX_TOKENS = {}
    SYMBOL_TOKENS = {}


def _ensure_data_dir():
    """Create data/ directory if it doesn't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path) -> dict:
    """Load JSON cache file, return empty dict if not exists."""
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load {path}: {e}")
    return {}


def _save_json(path: Path, data: dict):
    """Save JSON cache file atomically."""
    _ensure_data_dir()
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    tmp.replace(path)


def _get_iv_history(underlying: str) -> list:
    """Get stored IV history for an underlying from JSON cache."""
    data = _load_json(IV_HISTORY_FILE)
    return data.get(underlying, [])


def _save_iv_snapshot(underlying: str, date_str: str, atm_iv: float, vix: float | None, spot_price: float, expiry: str):
    """Append an IV snapshot to the JSON cache."""
    data = _load_json(IV_HISTORY_FILE)
    history = data.get(underlying, [])
    # Upsert: replace if date exists, else append
    for i, entry in enumerate(history):
        if entry["date"] == date_str:
            history[i] = {
                "date": date_str, "atm_iv": atm_iv, "vix": vix,
                "spot_price": spot_price, "expiry": expiry,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            break
    else:
        history.append({
            "date": date_str, "atm_iv": atm_iv, "vix": vix,
            "spot_price": spot_price, "expiry": expiry,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    # Keep only last 365 entries
    history.sort(key=lambda x: x["date"], reverse=True)
    data[underlying] = history[:365]
    _save_json(IV_HISTORY_FILE, data)


def _get_price_history(underlying: str) -> list:
    """Get stored price history from JSON cache."""
    data = _load_json(PRICE_HISTORY_FILE)
    return data.get(underlying, [])


def _save_price_snapshot(underlying: str, date_str: str, close: float):
    """Append a price snapshot to the JSON cache."""
    data = _load_json(PRICE_HISTORY_FILE)
    history = data.get(underlying, [])
    for i, entry in enumerate(history):
        if entry["date"] == date_str:
            history[i] = {"date": date_str, "close": close}
            break
    else:
        history.append({"date": date_str, "close": close})
    history.sort(key=lambda x: x["date"], reverse=True)
    data[underlying] = history[:365]
    _save_json(PRICE_HISTORY_FILE, data)


@router.get("/dashboard")
async def get_iv_dashboard(underlying: str = "NIFTY", expiry: str = None, num_strikes: int = 20):
    """Full IV dashboard — ATM IV, IV Rank, Percentile, HV, VIX, signals. Uses JSON file cache."""
    if not is_iv_available() or not is_option_chain_available():
        raise HTTPException(status_code=400, detail="IV analytics not available")

    oc_service = get_option_chain_service()
    angel = get_angel_service() if (is_angel_available() and get_angel_service) else None
    u = underlying.upper()

    if not expiry:
        expiries = oc_service.get_expiries(u)
        if expiries:
            expiry = expiries[0]["expiry"]
        else:
            raise HTTPException(status_code=404, detail=f"No expiries for {u}")

    try:
        exp_dt = datetime.strptime(expiry, "%d%b%Y")
        days_to_expiry = max(1, (exp_dt - datetime.now()).days)
    except ValueError:
        days_to_expiry = 30

    # Get spot price
    spot_price = 0
    if angel and angel.is_connected():
        def _fetch():
            sp = 0
            if u in INDEX_TOKENS:
                try:
                    data = angel.smart_api.getMarketData(mode="LTP", exchangeTokens={INDEX_TOKENS[u]["exchange"]: [INDEX_TOKENS[u]["token"]]})
                    if data.get("status") and data.get("data", {}).get("fetched"):
                        sp = float(data["data"]["fetched"][0].get("ltp", 0))
                except Exception as e:
                    logger.error(f"IV spot fetch error: {e}")
            elif u in SYMBOL_TOKENS:
                try:
                    data = angel.smart_api.getMarketData(mode="LTP", exchangeTokens={"NSE": [SYMBOL_TOKENS[u]["nse_token"]]})
                    if data.get("status") and data.get("data", {}).get("fetched"):
                        sp = float(data["data"]["fetched"][0].get("ltp", 0))
                except Exception as e:
                    logger.error(f"IV spot fetch error: {e}")
            return sp
        spot_price = await asyncio.to_thread(_fetch)

    if spot_price <= 0:
        fallbacks = {"NIFTY": 24000, "BANKNIFTY": 50000, "FINNIFTY": 22000}
        spot_price = fallbacks.get(u, 1000)

    # Build chain
    chain_result = await asyncio.to_thread(oc_service.build_option_chain, angel, u, expiry, spot_price, num_strikes)
    chain_data = chain_result.get("chain", [])

    atm_iv = get_atm_iv(chain_data, spot_price, days_to_expiry)
    iv_skew = build_iv_skew(chain_data, spot_price, days_to_expiry)
    max_pain = calculate_max_pain(chain_data)

    # Fetch India VIX
    vix_value = None
    if angel and angel.is_connected():
        def _fetch_vix():
            try:
                data = angel.smart_api.getMarketData(mode="LTP", exchangeTokens={INDIA_VIX_EXCHANGE: [INDIA_VIX_TOKEN]})
                if data.get("status") and data.get("data", {}).get("fetched"):
                    return float(data["data"]["fetched"][0].get("ltp", 0))
            except Exception as e:
                logger.error(f"VIX fetch error: {e}")
            return None
        vix_value = await asyncio.to_thread(_fetch_vix)

    # Historical data from JSON file cache (replaces MongoDB)
    iv_history = _get_iv_history(u)
    price_history = _get_price_history(u)

    iv_rank = None
    iv_percentile = None
    hv = None

    iv_values = [s["atm_iv"] for s in iv_history if s.get("atm_iv") and s["atm_iv"] > 0]
    if atm_iv and iv_values:
        iv_rank = calculate_iv_rank(atm_iv, iv_values)
        iv_percentile = calculate_iv_percentile(atm_iv, iv_values)

    if price_history:
        prices = [s["close"] for s in sorted(price_history, key=lambda x: x["date"]) if s.get("close")]
        hp = calculate_historical_volatility(prices, window=min(20, len(prices)))
        if hp:
            hv = round(hp * 100, 2)

    # Save today's snapshot
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if atm_iv and atm_iv > 0:
        _save_iv_snapshot(u, today_str, atm_iv, vix_value, spot_price, expiry)
    if spot_price > 0:
        _save_price_snapshot(u, today_str, spot_price)

    signal = detect_iv_signal(iv_rank, iv_percentile, atm_iv, hv)

    return {
        "underlying": u, "expiry": expiry, "days_to_expiry": days_to_expiry,
        "spot_price": spot_price, "atm_iv": atm_iv,
        "iv_rank": iv_rank, "iv_percentile": iv_percentile,
        "historical_volatility": hv, "india_vix": vix_value,
        "iv_history_count": len(iv_values), "seller_signal": signal,
        "max_pain": max_pain, "iv_skew": iv_skew,
        "totals": chain_result.get("totals"),
        "atm_strike": chain_result.get("atm_strike"),
        "data_source": chain_result.get("data_source"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/skew")
async def get_iv_skew(underlying: str = "NIFTY", expiry: str = None, num_strikes: int = 20):
    """Get IV skew across strikes for visualization."""
    dashboard = await get_iv_dashboard(underlying, expiry, num_strikes)
    return {
        "underlying": dashboard["underlying"], "expiry": dashboard["expiry"],
        "spot_price": dashboard["spot_price"], "atm_strike": dashboard["atm_strike"],
        "atm_iv": dashboard["atm_iv"], "skew": dashboard["iv_skew"],
    }


@router.get("/max-pain")
async def get_max_pain(underlying: str = "NIFTY", expiry: str = None):
    """Get max pain strike with pain distribution."""
    dashboard = await get_iv_dashboard(underlying, expiry, 25)
    return {
        "underlying": dashboard["underlying"], "expiry": dashboard["expiry"],
        "spot_price": dashboard["spot_price"], "max_pain": dashboard["max_pain"],
    }
