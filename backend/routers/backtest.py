"""Backtest routes — run backtest simulations."""

from fastapi import APIRouter

from models.market import BacktestRequest
from services.backtest_service import BacktestEngine

router = APIRouter(prefix="/backtest", tags=["Backtesting"])


@router.post("")
async def run_backtest(request: BacktestRequest):
    """Run backtest."""
    return await BacktestEngine.run_backtest(
        request.strategy,
        request.symbol,
        request.start_date,
        request.end_date,
        request.initial_capital,
    )
