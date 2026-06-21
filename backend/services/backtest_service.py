"""Backtest Engine — runs simple backtest simulations."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

import numpy as np

from .performance_service import PerformanceAnalytics

logger = logging.getLogger(__name__)


class BacktestEngine:
    """Simple backtesting engine."""

    @staticmethod
    async def run_backtest(
        strategy: str, symbol: str,
        start_date: str, end_date: str,
        initial_capital: float = 1000000,
    ) -> Dict[str, Any]:
        """Run a simple backtest simulation."""
        np.random.seed(42)
        days = 252

        if strategy == "cross_exchange":
            daily_returns = np.random.normal(0.0005, 0.002, days)
        elif strategy == "cash_carry":
            daily_returns = np.random.normal(0.0003, 0.001, days)
        elif strategy == "statistical":
            daily_returns = np.random.normal(0.0008, 0.005, days)
        else:
            daily_returns = np.random.normal(0.0004, 0.003, days)

        equity = [initial_capital]
        for ret in daily_returns:
            equity.append(equity[-1] * (1 + ret))

        metrics = PerformanceAnalytics.calculate_metrics(daily_returns.tolist())

        trades = []
        for i in range(min(50, days)):
            date = datetime.now(timezone.utc) - timedelta(days=days - i)
            trades.append({
                "date": date.isoformat(),
                "symbol": symbol,
                "action": "BUY" if daily_returns[i] > 0 else "SELL",
                "price": round(1000 * (1 + np.sum(daily_returns[:i]) * 0.1), 2),
                "quantity": 100,
                "pnl": round(initial_capital * daily_returns[i], 2),
            })

        return {
            "strategy": strategy,
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": initial_capital,
            "final_capital": round(equity[-1], 2),
            "total_return_pct": round((equity[-1] / initial_capital - 1) * 100, 2),
            "metrics": metrics,
            "equity_curve": [round(e, 2) for e in equity[::5]],
            "trades": trades[-20:],
            "total_trades": len(trades),
        }
