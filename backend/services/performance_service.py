"""Performance Analytics — calculates trading performance metrics."""

import logging
from datetime import datetime
from typing import Dict, Any, List

import numpy as np

logger = logging.getLogger(__name__)


class PerformanceAnalytics:
    """Calculate trading performance metrics."""

    @staticmethod
    def calculate_metrics(returns: List[float], risk_free_rate: float = 7.0) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics."""
        if not returns or len(returns) < 2:
            return {"error": "Insufficient data"}

        returns = np.array(returns)

        total_return = (np.prod(1 + returns) - 1) * 100
        avg_return = np.mean(returns) * 100
        volatility = np.std(returns) * np.sqrt(252) * 100

        excess_returns = returns - (risk_free_rate / 100 / 252)
        sharpe_ratio = np.mean(excess_returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0

        downside_returns = returns[returns < 0]
        downside_std = np.std(downside_returns) * np.sqrt(252) if len(downside_returns) > 0 else 0
        sortino_ratio = np.mean(excess_returns) * 252 / downside_std if downside_std > 0 else 0

        cumulative = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative - running_max) / running_max
        max_drawdown = np.min(drawdowns) * 100

        calmar_ratio = (total_return / 100) / abs(max_drawdown / 100) if max_drawdown != 0 else 0

        winning_days = np.sum(returns > 0)
        total_days = len(returns)
        win_rate = (winning_days / total_days) * 100

        gross_profit = np.sum(returns[returns > 0])
        gross_loss = abs(np.sum(returns[returns < 0]))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        return {
            "total_return": round(total_return, 2),
            "avg_daily_return": round(avg_return, 3),
            "volatility": round(volatility, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "sortino_ratio": round(sortino_ratio, 2),
            "max_drawdown": round(max_drawdown, 2),
            "calmar_ratio": round(calmar_ratio, 2),
            "win_rate": round(win_rate, 1),
            "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else "N/A",
            "total_trades": total_days,
        }

    @staticmethod
    def calculate_weekday_performance(trades: List[Dict]) -> Dict[str, Any]:
        """Analyze performance by weekday."""
        weekday_pnl = {i: [] for i in range(5)}

        for trade in trades:
            if "date" in trade and "pnl" in trade:
                try:
                    date = datetime.fromisoformat(trade["date"].replace("Z", "+00:00"))
                    weekday = date.weekday()
                    if weekday < 5:
                        weekday_pnl[weekday].append(trade["pnl"])
                except Exception:
                    pass

        weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        result = {}
        for i, name in enumerate(weekday_names):
            pnls = weekday_pnl[i]
            if pnls:
                result[name] = {
                    "total_pnl": round(sum(pnls), 2),
                    "avg_pnl": round(np.mean(pnls), 2),
                    "trade_count": len(pnls),
                    "win_rate": round(sum(1 for p in pnls if p > 0) / len(pnls) * 100, 1),
                }
            else:
                result[name] = {"total_pnl": 0, "avg_pnl": 0, "trade_count": 0, "win_rate": 0}

        return result
