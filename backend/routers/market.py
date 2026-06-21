"""Market data routes — indices, stock prices, data source management, broker status. No auth needed."""

import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException

from core.deps import is_angel_available, get_market_session_info
from services.market_data_service import MarketDataService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/market", tags=["Market Data"])

try:
    from angel_one_service import get_angel_service
except ImportError:
    get_angel_service = None


@router.get("/indices")
async def get_indices():
    """Get major Indian indices - uses batch API for speed."""
    if MarketDataService._use_live_data and is_angel_available():
        try:
            angel = get_angel_service()
            if angel and angel.is_connected():
                results = angel.get_all_indices()
                if results:
                    for r in results:
                        r['data_source'] = 'angel_one_live'
                    return results
        except Exception as e:
            logger.warning(f"Batch index fetch failed: {e}")

        return [{
            "index": idx, "value": None, "prev_close": None,
            "change": None, "change_pct": None,
            "data_source": "angel_one_unavailable", "error": "API unavailable",
        } for idx in ["NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX", "BANKEX"]]

    indices = ["NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX", "BANKEX"]
    tasks = [MarketDataService.get_index_data(idx) for idx in indices]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if isinstance(r, dict)]


@router.get("/stock/{symbol}")
async def get_stock(symbol: str, exchange: str = "NSE"):
    """Get stock price."""
    return await MarketDataService.get_stock_price(symbol.upper(), exchange.upper())


@router.get("/stocks")
async def get_stocks(symbols: str = None):
    """Get multiple stock prices - uses batch API for speed."""
    if symbols:
        symbol_list = [s.strip().upper() for s in symbols.split(",")]
    else:
        symbol_list = MarketDataService.FO_STOCKS[:5]

    if MarketDataService._use_live_data and is_angel_available():
        try:
            angel = get_angel_service()
            if angel and angel.is_connected():
                nse_results = angel.get_multiple_stocks_batch(symbol_list, "NSE")
                bse_results = angel.get_multiple_stocks_batch(symbol_list, "BSE")
                if nse_results or bse_results:
                    return nse_results + bse_results
        except Exception as e:
            logger.warning(f"Batch stock fetch failed: {e}")

        return [{
            "symbol": sym, "exchange": "NSE", "price": None,
            "data_source": "angel_one_unavailable", "error": "API unavailable",
        } for sym in symbol_list]

    return await MarketDataService.get_multiple_stocks(symbol_list)


@router.get("/fo-stocks")
async def get_fo_stocks():
    """Get list of F&O stocks."""
    return {"stocks": MarketDataService.FO_STOCKS}


@router.get("/data-source")
async def get_data_source_status():
    """Get current data source status (Angel One or simulated)."""
    return MarketDataService.get_data_source_status()


@router.post("/data-source/toggle")
async def toggle_data_source(use_live: bool = True):
    """Toggle between live Angel One data and simulated data."""
    MarketDataService.set_use_live_data(use_live)
    return {
        "use_live_data": use_live,
        "message": f"Data source set to {'Angel One Live' if use_live else 'Simulated'}",
    }


@router.post("/angel-one/login")
async def angel_one_login():
    """Manually trigger Angel One login."""
    if not is_angel_available():
        raise HTTPException(status_code=400, detail="Angel One service not configured")
    try:
        angel = get_angel_service()
        angel.reset_login_attempts()
        success = angel.login()
        if success:
            return {"status": "success", "message": "Angel One login successful", "session_status": angel.get_session_status()}
        else:
            status = angel.get_session_status()
            raise HTTPException(status_code=401, detail=f"Angel One login failed: {status.get('last_error', 'Unknown error')}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Angel One login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/angel-one/session")
async def get_angel_one_session():
    """Get Angel One session status with detailed info."""
    if not is_angel_available():
        return {"available": False, "message": "Angel One service not configured", "session_status": None}
    angel = get_angel_service()
    status = angel.get_session_status()
    return {
        "available": True, "session_status": status,
        "help": {
            "if_not_connected": "Call POST /api/market/angel-one/login to connect",
            "credentials_location": "Update credentials in /app/backend/.env and restart backend",
            "required_credentials": ["ANGEL_API_KEY", "ANGEL_CLIENT_ID", "ANGEL_MPIN", "ANGEL_TOTP_SECRET"],
        },
    }


@router.post("/angel-one/reset")
async def reset_angel_one():
    """Reset Angel One service - use after updating credentials."""
    if not is_angel_available():
        raise HTTPException(status_code=400, detail="Angel One service not configured")
    angel = get_angel_service()
    angel.reset_login_attempts()
    success = angel.login()
    return {
        "status": "success" if success else "failed",
        "message": "Credentials reloaded" + (" and login successful" if success else " but login failed"),
        "session_status": angel.get_session_status(),
    }


@router.get("/broker-status")
async def get_broker_status():
    """Get comprehensive broker connection + market session status. No auth needed."""
    market_info = get_market_session_info()
    broker_status = {
        "broker": "angel_one",
        "is_available": is_angel_available(),
        "is_connected": False,
        "client_id": None, "session_expiry": None,
        "time_remaining": None, "last_error": None,
        "credentials_configured": False,
    }
    if is_angel_available():
        angel = get_angel_service()
        session = angel.get_session_status()
        broker_status.update({
            "is_connected": session["is_connected"],
            "client_id": session["client_id"],
            "session_expiry": session["session_expiry"],
            "time_remaining": session["time_remaining"],
            "last_error": session["last_error"],
            "credentials_configured": session["credentials_configured"],
            "last_login": session["last_login"],
            "login_attempts": session["login_attempts"],
        })
    data_mode = "live" if broker_status["is_connected"] and MarketDataService._use_live_data else "simulated"
    return {"broker": broker_status, "market": market_info, "data_mode": data_mode, "use_live_data": MarketDataService._use_live_data}
