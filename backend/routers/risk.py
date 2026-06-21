"""Risk management routes — position sizing, VaR, margin."""

from typing import List

from fastapi import APIRouter

from services.risk_service import RiskManager

router = APIRouter(prefix="/risk", tags=["Risk Management"])


@router.post("/position-size")
async def calculate_position_size(
    capital: float,
    risk_per_trade: float,
    stop_loss_pct: float,
    price: float,
):
    """Calculate position size."""
    return RiskManager.calculate_position_size(capital, risk_per_trade, stop_loss_pct, price)


@router.post("/var")
async def calculate_var(
    returns: List[float],
    confidence: float = 0.95,
    portfolio_value: float = 1000000,
):
    """Calculate Value at Risk."""
    return RiskManager.calculate_var(returns, confidence, portfolio_value)


@router.post("/margin")
async def calculate_margin(
    position_value: float,
    volatility: float = 15,
    is_futures: bool = True,
):
    """Calculate margin requirement."""
    return RiskManager.calculate_margin_requirement(position_value, volatility, is_futures)
