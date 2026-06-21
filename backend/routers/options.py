"""Option chain routes — underlyings, expiries, T-shaped option chain."""

import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException

from core.deps import is_angel_available, is_option_chain_available

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/options", tags=["Options"])

try:
    from option_chain_service import get_option_chain_service
    from angel_one_service import get_angel_service, SYMBOL_TOKENS, INDEX_TOKENS
except ImportError:
    get_option_chain_service = None
    get_angel_service = None
    SYMBOL_TOKENS = {}
    INDEX_TOKENS = {}


@router.get("/underlyings")
async def get_option_underlyings():
    """Get available underlyings for option chain."""
    if not is_option_chain_available():
        raise HTTPException(status_code=400, detail="Option chain service not available")

    oc_service = get_option_chain_service()
    return oc_service.get_underlyings()


@router.get("/expiries")
async def get_option_expiries(underlying: str = "NIFTY"):
    """Get available expiry dates for an underlying."""
    if not is_option_chain_available():
        raise HTTPException(status_code=400, detail="Option chain service not available")

    oc_service = get_option_chain_service()
    return oc_service.get_expiries(underlying.upper())


@router.get("/chain")
async def get_option_chain(underlying: str = "NIFTY", expiry: str = None, num_strikes: int = 15):
    """Get T-shaped option chain with live data — blocking calls run in thread pool."""
    if not is_option_chain_available():
        raise HTTPException(status_code=400, detail="Option chain service not available")

    oc_service = get_option_chain_service()

    if not expiry:
        expiries = oc_service.get_expiries(underlying.upper())
        if expiries:
            expiry = expiries[0]["expiry"]
        else:
            raise HTTPException(status_code=404, detail=f"No expiries found for {underlying}")

    # Get spot price — run blocking Angel One call in thread pool
    spot_price = 0
    angel = get_angel_service() if (is_angel_available() and get_angel_service) else None

    if angel and angel.is_connected():
        def _fetch_spot():
            u = underlying.upper()
            if u in INDEX_TOKENS:
                idx_info = INDEX_TOKENS[u]
                try:
                    data = angel.smart_api.getMarketData(mode="LTP", exchangeTokens={idx_info["exchange"]: [idx_info["token"]]})
                    if data.get("status") and data.get("data", {}).get("fetched"):
                        return float(data["data"]["fetched"][0].get("ltp", 0))
                except Exception as e:
                    logger.error(f"Spot price fetch error for {u}: {e}")
            elif u in SYMBOL_TOKENS:
                try:
                    data = angel.smart_api.getMarketData(mode="LTP", exchangeTokens={"NSE": [SYMBOL_TOKENS[u]["nse_token"]]})
                    if data.get("status") and data.get("data", {}).get("fetched"):
                        return float(data["data"]["fetched"][0].get("ltp", 0))
                except Exception as e:
                    logger.error(f"Spot price fetch error for {u}: {e}")
            return 0

        spot_price = await asyncio.to_thread(_fetch_spot)

    if spot_price <= 0:
        fallback_spots = {
            "NIFTY": 24000, "BANKNIFTY": 50000, "FINNIFTY": 22000,
            "MIDCPNIFTY": 10500, "SENSEX": 78000, "NIFTYNXT50": 65000,
        }
        spot_price = fallback_spots.get(underlying.upper(), 1000)

    result = await asyncio.to_thread(
        oc_service.build_option_chain, angel, underlying.upper(), expiry, spot_price, num_strikes,
    )
    return result
