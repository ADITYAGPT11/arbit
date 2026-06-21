"""Risk Management — position sizing, VaR, margin calculations."""

import logging
from typing import Dict, Any, List

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


class RiskManager:
    """Risk management calculations."""

    @staticmethod
    def calculate_position_size(
        capital: float, risk_per_trade: float,
        stop_loss_pct: float, price: float,
    ) -> Dict[str, Any]:
        """Calculate position size based on risk."""
        risk_amount = capital * (risk_per_trade / 100)
        stop_loss_amount = price * (stop_loss_pct / 100)
        shares = int(risk_amount / stop_loss_amount) if stop_loss_amount > 0 else 0
        position_value = shares * price

        return {
            "capital": capital,
            "risk_per_trade_pct": risk_per_trade,
            "risk_amount": round(risk_amount, 2),
            "stop_loss_pct": stop_loss_pct,
            "price": price,
            "recommended_shares": shares,
            "position_value": round(position_value, 2),
            "capital_utilization_pct": round((position_value / capital) * 100, 1),
        }

    @staticmethod
    def calculate_var(
        returns: List[float], confidence: float = 0.95,
        portfolio_value: float = 1000000,
    ) -> Dict[str, Any]:
        """Calculate Value at Risk."""
        if not returns:
            return {"error": "No returns data"}

        returns = np.array(returns)

        var_pct = np.percentile(returns, (1 - confidence) * 100)
        var_amount = abs(var_pct * portfolio_value)

        mean = np.mean(returns)
        std = np.std(returns)
        z_score = stats.norm.ppf(1 - confidence)
        parametric_var_pct = mean + z_score * std
        parametric_var_amount = abs(parametric_var_pct * portfolio_value)

        return {
            "confidence_level": confidence * 100,
            "historical_var_pct": round(var_pct * 100, 2),
            "historical_var_amount": round(var_amount, 2),
            "parametric_var_pct": round(parametric_var_pct * 100, 2),
            "parametric_var_amount": round(parametric_var_amount, 2),
            "portfolio_value": portfolio_value,
        }

    @staticmethod
    def calculate_margin_requirement(
        position_value: float, volatility: float = 15,
        is_futures: bool = True,
    ) -> Dict[str, Any]:
        """Calculate SPAN margin requirement (simplified)."""
        if is_futures:
            span_margin_pct = max(10, volatility * 1.5)
            exposure_margin_pct = 3.5
        else:
            span_margin_pct = max(15, volatility * 2)
            exposure_margin_pct = 5

        span_margin = position_value * (span_margin_pct / 100)
        exposure_margin = position_value * (exposure_margin_pct / 100)
        total_margin = span_margin + exposure_margin

        return {
            "position_value": position_value,
            "volatility": volatility,
            "span_margin_pct": round(span_margin_pct, 2),
            "span_margin": round(span_margin, 2),
            "exposure_margin_pct": round(exposure_margin_pct, 2),
            "exposure_margin": round(exposure_margin, 2),
            "total_margin": round(total_margin, 2),
            "leverage": round(position_value / total_margin, 1) if total_margin > 0 else 0,
        }
