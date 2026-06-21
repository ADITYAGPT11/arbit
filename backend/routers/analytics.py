"""Analytics routes — performance metrics, weekday analysis."""

from typing import List, Dict

from fastapi import APIRouter

from services.performance_service import PerformanceAnalytics

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.post("/performance")
async def get_performance_metrics(returns: List[float], risk_free_rate: float = 7.0):
    """Calculate performance metrics."""
    return PerformanceAnalytics.calculate_metrics(returns, risk_free_rate)


@router.post("/weekday")
async def get_weekday_performance(trades: List[Dict]):
    """Analyze performance by weekday."""
    return PerformanceAnalytics.calculate_weekday_performance(trades)
