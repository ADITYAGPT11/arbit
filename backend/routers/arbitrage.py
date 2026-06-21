"""Arbitrage routes — all arbitrage opportunity detection endpoints."""

from typing import List

from fastapi import APIRouter

from services.market_data_service import MarketDataService
from services.arbitrage_service import ArbitrageEngine

router = APIRouter(prefix="/arbitrage", tags=["Arbitrage"])


@router.get("/cross-exchange")
async def get_cross_exchange_arbitrage(symbols: str = None):
    """Detect cross-exchange arbitrage opportunities."""
    if symbols:
        symbol_list = [s.strip().upper() for s in symbols.split(",")]
    else:
        symbol_list = MarketDataService.FO_STOCKS[:15]
    return await ArbitrageEngine.detect_cross_exchange_arbitrage(symbol_list)


@router.post("/cash-carry")
async def calculate_cash_carry(
    spot_price: float,
    futures_price: float,
    days_to_expiry: int,
    risk_free_rate: float = 7.0,
):
    """Calculate cash and carry arbitrage."""
    return ArbitrageEngine.calculate_cash_carry_arbitrage(
        spot_price, futures_price, days_to_expiry, risk_free_rate,
    )


@router.post("/synthetic")
async def calculate_synthetic(
    spot_price: float,
    call_price: float,
    put_price: float,
    strike: float,
    futures_price: float,
):
    """Calculate synthetic futures arbitrage."""
    return ArbitrageEngine.calculate_synthetic_futures_arbitrage(
        spot_price, call_price, put_price, strike, futures_price,
    )


@router.post("/calendar-spread")
async def calculate_calendar_spread(
    near_futures: float,
    far_futures: float,
    near_expiry_days: int,
    far_expiry_days: int,
):
    """Calculate calendar spread."""
    return ArbitrageEngine.calculate_calendar_spread(
        near_futures, far_futures, near_expiry_days, far_expiry_days,
    )


@router.post("/statistical")
async def calculate_statistical_arb(
    prices1: List[float],
    prices2: List[float],
    lookback: int = 20,
):
    """Calculate statistical arbitrage signals."""
    return ArbitrageEngine.calculate_statistical_arbitrage(prices1, prices2, lookback)
