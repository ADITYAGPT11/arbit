"""Correlation Signal Service — Pairs trading signal generation & backtesting engine.

Improvements over v1:
- Cointegration filter (Engle-Granger test) — only trades truly mean-reverting pairs
- Dynamic hedge ratio (rolling OLS β) — makes spread stationary instead of raw ratio
- Transaction cost model — per-side cost for realistic backtest P&L
- Half-life estimation — reports how quickly the spread reverts
"""

import asyncio
import logging
import math
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from services.correlation_service import correlation_service

logger = logging.getLogger(__name__)

# ── Required: statsmodels (cointegration, OLS) ──
from statsmodels.tsa.stattools import coint, adfuller
from statsmodels.regression.linear_model import OLS
import statsmodels.api as sm


@dataclass
class BacktestParams:
    """Tunable parameters for the mean-reversion pairs trading strategy."""
    # Z-score thresholds
    entry_z: float = 2.0
    exit_z: float = 0.0
    stop_z: float = 3.0
    rolling_window: int = 20

    # Ratio mode (legacy)
    use_log_ratio: bool = False

    # ── NEW: Dynamic hedge ratio ──
    use_hedge_ratio: bool = True           # Use rolling OLS β instead of raw ratio
    beta_window: int = 60                  # Window for rolling OLS

    # ── NEW: Cointegration filter ──
    require_cointegrated: bool = True      # Skip if not cointegrated
    coint_pvalue: float = 0.05             # Max p-value for cointegration

    # ── NEW: Transaction costs ──
    transaction_cost_pct: float = 0.05     # Per-side cost (% of notional, e.g. 0.05 = 0.05%)


@dataclass
class TradeRecord:
    """A single backtest trade."""
    entry_date: str
    exit_date: Optional[str]
    entry_spread: float                     # Spread value at entry
    exit_spread: Optional[float]            # Spread value at exit
    side: str                               # "LONG_SPREAD" or "SHORT_SPREAD"
    pnl_pct: Optional[float]                # P&L as % of notional (after costs)
    gross_pnl_pct: Optional[float]          # P&L before costs
    cost_pct: Optional[float]               # Total cost for this trade (%)
    exit_reason: str                        # "TARGET", "STOP_LOSS", "LAST"


@dataclass
class BacktestResult:
    """Complete backtest result for one parameter set."""
    params: BacktestParams
    trades: List[Dict[str, Any]] = field(default_factory=list)
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    total_return_pct: float = 0.0
    annualized_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    profit_factor: float = 0.0
    avg_bars_held: float = 0.0
    num_observations: int = 0


class CorrelationSignalService:
    """Generates pairs trading signals and runs historical backtests.

    Strategy improvements:
    - Cointegration test to ensure pairs are truly mean-reverting
    - Rolling OLS hedge ratio for a stationary spread
    - Realistic transaction costs
    """

    # ── Cointegration ──

    @staticmethod
    def is_cointegrated(
        prices1: List[float],
        prices2: List[float],
        pvalue_threshold: float = 0.05,
    ) -> Tuple[bool, float, float]:
        """Engle-Granger cointegration test.

        Returns:
            (is_cointegrated, p_value, half_life_days)
        """
        if len(prices1) < 30 or len(prices2) < 30:
            return False, 1.0, 0.0

        a = np.array(prices1, dtype=float)
        b = np.array(prices2, dtype=float)

        try:
            # Engle-Granger test
            score, pvalue, _ = coint(a, b, maxlag=5)
            is_coint = bool(pvalue <= pvalue_threshold)  # cast to Python bool (not numpy.bool_)

            # Half-life of mean reversion via ADF on spread
            spread = a - b  # simple spread for half-life estimation
            hl = CorrelationSignalService._estimate_half_life(spread)

            return is_coint, float(pvalue), hl
        except Exception as e:
            logger.debug(f"Cointegration test failed: {e}")
            return False, 1.0, 0.0

    @staticmethod
    def _estimate_half_life(spread: np.ndarray) -> float:
        """Estimate half-life of mean reversion using OLS: ΔS(t) = α + γ·S(t-1) + ε.

        Half-life = -ln(2) / γ  (where γ < 0 indicates mean reversion).
        Returns 0 if not computable, 999 if not mean-reverting.
        """
        if len(spread) < 30:
            return 0.0
        try:
            y = np.diff(spread)
            x = sm.add_constant(spread[:-1])
            model = OLS(y, x).fit()
            gamma = model.params[1]
            if gamma < 0:
                half_life = -math.log(2) / gamma
                return min(max(half_life, 1), 500)  # clamp 1-500 days
            return 999.0  # not mean-reverting
        except Exception:
            return 0.0

    # ── Rolling OLS Hedge Ratio ──

    @staticmethod
    def _compute_rolling_beta(
        arr1: np.ndarray, arr2: np.ndarray, window: int
    ) -> np.ndarray:
        """Compute rolling OLS beta: A = α + β·B + ε.

        Returns β series (NaN for first `window` points).
        """
        if len(arr1) < window + 5:
            return np.full_like(arr1, 1.0)

        betas = np.full_like(arr1, np.nan)
        for i in range(window, len(arr1)):
            y = arr1[i - window:i]
            x = arr2[i - window:i]
            X = sm.add_constant(x)
            try:
                model = OLS(y, X).fit()
                betas[i] = model.params[1]
            except Exception:
                betas[i] = 1.0
        return betas

    # ── Spread Computation ──

    @staticmethod
    def _compute_spread(
        arr1: np.ndarray,
        arr2: np.ndarray,
        params: BacktestParams,
    ) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """Compute the trading spread series.

        Two modes:
        1. Hedge ratio mode (default): spread = A - β·B  (rolling OLS)
        2. Ratio mode (legacy): spread = A / B  (or log(A/B))

        Returns:
            (spread_values, beta_values_or_None)
        """
        if params.use_hedge_ratio:
            betas = CorrelationSignalService._compute_rolling_beta(
                arr1, arr2, params.beta_window
            )
            # Use last valid beta for initial points (clamp forward)
            last_valid = 1.0
            for i in range(len(betas)):
                if np.isnan(betas[i]):
                    betas[i] = last_valid
                else:
                    last_valid = betas[i]
            spread = arr1 - betas * arr2
            return spread, betas
        else:
            # Legacy ratio mode
            ratio = arr1 / arr2
            if params.use_log_ratio:
                ratio = np.log(ratio)
            return ratio, None

    @staticmethod
    def _compute_zscore(series: np.ndarray, window: int) -> np.ndarray:
        """Rolling z-score of a series."""
        if len(series) < window:
            return np.full_like(series, np.nan)
        df = pd.Series(series)
        roll_mean = df.rolling(window=window).mean()
        roll_std = df.rolling(window=window).std()
        z = (df - roll_mean) / roll_std
        return z.values

    # ── P&L Computation ──

    @staticmethod
    def _compute_trade_pnl(
        entry_spread: float,
        exit_spread: float,
        side: str,
        cost_pct: float = 0.0,
    ) -> Tuple[float, float]:
        """Compute P&L and cost for a trade.

        LONG_SPREAD: profit when spread rises  →  P&L = (exit - entry) / |entry|
        SHORT_SPREAD: profit when spread falls →  P&L = (entry - exit) / |entry|

        Returns:
            (gross_pnl_pct, net_pnl_pct)  — after applying transaction cost
        """
        if abs(entry_spread) < 1e-10:
            return 0.0, -cost_pct  # no signal, just cost

        raw_ret = (exit_spread - entry_spread) / abs(entry_spread)
        if side == "SHORT_SPREAD":
            raw_ret = -raw_ret

        # Cost: entry + exit
        total_cost = cost_pct * 2
        net_ret = raw_ret - total_cost

        return raw_ret, net_ret

    # ── Shared trading loop (extracted to avoid duplication) ──

    @staticmethod
    def _run_trading_loop(
        spread: np.ndarray,
        z_scores: np.ndarray,
        dates: List[str],
        params: BacktestParams,
        cost_pct: float,
    ) -> Tuple[List[Dict[str, Any]], List[float]]:
        """Walk through the spread/z-score series and execute trades.

        Shared between backtest_pair (OHLC data) and _backtest_pair_fallback
        (fetch_all_prices) so the entry/exit/stop/MTM logic is never duplicated.

        Returns:
            (trades, daily_equity) — daily_equity bars from start_idx onward
        """
        trades = []
        current_trade = None
        daily_equity = [0.0]

        start_idx = max(params.rolling_window, params.beta_window if params.use_hedge_ratio else 0)

        for i in range(start_idx, len(spread)):
            z = z_scores[i]
            if np.isnan(z):
                daily_equity.append(daily_equity[-1])
                continue

            if current_trade is not None:
                if abs(z) >= params.stop_z:
                    gross_pnl, net_pnl = CorrelationSignalService._compute_trade_pnl(
                        current_trade["entry_spread"], spread[i],
                        current_trade["side"], cost_pct,
                    )
                    trades.append({
                        "entry_date": current_trade["entry_date"],
                        "exit_date": dates[i],
                        "entry_spread": round(float(current_trade["entry_spread"]), 6),
                        "exit_spread": round(float(spread[i]), 6),
                        "side": current_trade["side"],
                        "pnl_pct": round(net_pnl * 100, 2),
                        "gross_pnl_pct": round(gross_pnl * 100, 2),
                        "cost_pct": round(cost_pct * 200, 2),
                        "exit_reason": "STOP_LOSS",
                        "bars_held": i - current_trade["entry_idx"],
                    })
                    last_mtm = current_trade.get("last_mtm_pnl", 0.0)
                    daily_equity.append(daily_equity[-1] + net_pnl - last_mtm)
                    current_trade = None
                    continue

                if abs(z) <= params.exit_z:
                    gross_pnl, net_pnl = CorrelationSignalService._compute_trade_pnl(
                        current_trade["entry_spread"], spread[i],
                        current_trade["side"], cost_pct,
                    )
                    trades.append({
                        "entry_date": current_trade["entry_date"],
                        "exit_date": dates[i],
                        "entry_spread": round(float(current_trade["entry_spread"]), 6),
                        "exit_spread": round(float(spread[i]), 6),
                        "side": current_trade["side"],
                        "pnl_pct": round(net_pnl * 100, 2),
                        "gross_pnl_pct": round(gross_pnl * 100, 2),
                        "cost_pct": round(cost_pct * 200, 2),
                        "exit_reason": "TARGET",
                        "bars_held": i - current_trade["entry_idx"],
                    })
                    last_mtm = current_trade.get("last_mtm_pnl", 0.0)
                    daily_equity.append(daily_equity[-1] + net_pnl - last_mtm)
                    current_trade = None
                    continue

                equity_at_entry = current_trade.get("equity_at_entry", daily_equity[-1])
                mtm_ret = current_trade["_mtm_fn"](spread[i])
                current_trade["last_mtm_pnl"] = mtm_ret
                daily_equity.append(equity_at_entry + mtm_ret)
                continue

            if z < -params.entry_z:
                mtm_fn = lambda s, entry=spread[i]: (s - entry) / abs(entry)
                current_trade = {
                    "side": "LONG_SPREAD",
                    "entry_idx": i,
                    "entry_spread": float(spread[i]),
                    "entry_date": dates[i],
                    "equity_at_entry": daily_equity[-1],
                    "last_mtm_pnl": 0.0,
                    "_mtm_fn": mtm_fn,
                }
                daily_equity.append(daily_equity[-1])
            elif z > params.entry_z:
                mtm_fn = lambda s, entry=spread[i]: (entry - s) / abs(entry)
                current_trade = {
                    "side": "SHORT_SPREAD",
                    "entry_idx": i,
                    "entry_spread": float(spread[i]),
                    "entry_date": dates[i],
                    "equity_at_entry": daily_equity[-1],
                    "last_mtm_pnl": 0.0,
                    "_mtm_fn": mtm_fn,
                }
                daily_equity.append(daily_equity[-1])
            else:
                daily_equity.append(daily_equity[-1])

        # ── Close any open trade at end of data ──
        if current_trade is not None:
            gross_pnl, net_pnl = CorrelationSignalService._compute_trade_pnl(
                current_trade["entry_spread"], spread[-1],
                current_trade["side"], cost_pct,
            )
            trades.append({
                "entry_date": current_trade["entry_date"],
                "exit_date": dates[-1],
                "entry_spread": round(float(current_trade["entry_spread"]), 6),
                "exit_spread": round(float(spread[-1]), 6),
                "side": current_trade["side"],
                "pnl_pct": round(net_pnl * 100, 2),
                "gross_pnl_pct": round(gross_pnl * 100, 2),
                "cost_pct": round(cost_pct * 200, 2),
                "exit_reason": "LAST",
                "bars_held": len(spread) - 1 - current_trade["entry_idx"],
            })

        return trades, daily_equity

    @staticmethod
    def _build_backtest_response(
        sym1: str, sym2: str, days: int,
        spread: np.ndarray, z_scores: np.ndarray, betas: Optional[np.ndarray],
        dates: List[str], trades: List[Dict[str, Any]], daily_equity: List[float],
        params: BacktestParams, coint_info: Dict[str, Any],
        price_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build the final backtest response dict from computed data.

        Shared between backtest_pair (OHLC) and _backtest_pair_fallback
        (fetch_all_prices) so the response formatting is never duplicated.
        """
        # ── Compute metrics ──
        result = CorrelationSignalService._compute_metrics(trades, daily_equity, days)

        start_idx = max(params.rolling_window, params.beta_window if params.use_hedge_ratio else 0)

        # ── Equity curve (sampled for charting) ──
        step = max(1, len(daily_equity) // 100)
        equity_curve = []
        for i in range(0, len(daily_equity), step):
            data_idx = i + start_idx
            eq_date = dates[data_idx] if data_idx < len(dates) else dates[-1]
            equity_curve.append({
                "date": eq_date,
                "equity": round(100 + daily_equity[i] * 100, 2),
            })

        # ── Spread & Z-score series ──
        spread_series = []
        for i in range(len(spread)):
            spread_series.append({
                "date": dates[i],
                "spread": round(float(spread[i]), 4),
                "zscore": round(float(z_scores[i]), 4) if not np.isnan(z_scores[i]) else None,
            })

        # ── Entry/exit markers ──
        markers = []
        for t in trades:
            markers.append({"date": t["entry_date"], "type": "entry", "side": t["side"], "spread": t["entry_spread"], "pnl_pct": t["pnl_pct"]})
            markers.append({"date": t["exit_date"], "type": "exit", "side": t["side"], "spread": t["exit_spread"], "pnl_pct": t["pnl_pct"]})

        # ── Spread stats ──
        beta_values = betas.tolist() if betas is not None else []
        avg_beta = float(np.nanmean(betas)) if betas is not None and not np.all(np.isnan(betas)) else 1.0

        return {
            "sym1": sym1, "sym2": sym2, "days": days,
            "price_data": price_data,
            "params": {
                "entry_z": params.entry_z, "exit_z": params.exit_z,
                "stop_z": params.stop_z, "rolling_window": params.rolling_window,
                "use_log_ratio": params.use_log_ratio,
                "use_hedge_ratio": params.use_hedge_ratio,
                "beta_window": params.beta_window,
                "require_cointegrated": params.require_cointegrated,
                "coint_pvalue": params.coint_pvalue,
                "transaction_cost_pct": params.transaction_cost_pct,
            },
            "coint_info": coint_info,
            "spread_stats": {
                "avg_beta": round(avg_beta, 4) if params.use_hedge_ratio else 1.0,
                "beta_series": [round(b, 4) for b in beta_values[::max(1, len(beta_values)//50)]][:50],
            },
            "metrics": {
                "total_return_pct": round(result.total_return_pct, 2),
                "annualized_return_pct": round(result.annualized_return_pct, 2),
                "sharpe_ratio": round(result.sharpe_ratio, 2),
                "max_drawdown_pct": round(result.max_drawdown_pct, 2),
                "win_rate": round(result.win_rate, 1),
                "total_trades": result.total_trades,
                "winning_trades": result.winning_trades,
                "losing_trades": result.losing_trades,
                "avg_win_pct": round(result.avg_win_pct, 2),
                "avg_loss_pct": round(result.avg_loss_pct, 2),
                "profit_factor": round(result.profit_factor, 2) if result.profit_factor is not None else None,
                "avg_bars_held": round(result.avg_bars_held, 1),
            },
            "trades": trades[-50:],
            "total_trades_count": len(trades),
            "equity_curve": equity_curve,
            "spread_series": spread_series,
            "markers": markers,
            "num_observations": len(spread),
        }

    # ── Backtest ──

    async def backtest_pair(
        self,
        sym1: str,
        sym2: str,
        days: int = 252,
        params: Optional[BacktestParams] = None,
    ) -> Dict[str, Any]:
        """Run a full historical backtest on a pair using mean-reversion strategy.

        Strategy:
        1. Check cointegration (if required) — skip if not cointegrated
        2. Compute spread as rolling-OLS residual (or raw ratio legacy)
        3. Compute rolling z-score of the spread
        4. Entry when |z| > entry_z; exit when |z| < exit_z; stop at stop_z
        5. Apply transaction costs on every entry and exit

        Uses live OHLC data from nselib for both prices and dates, ensuring
        all time series (spread, z-score, equity curve) use real trading-day
        dates instead of synthetic calendar-day dates.
        """
        if params is None:
            params = BacktestParams()

        # ── Fetch OHLC data (single source of truth for prices + real trading dates) ──
        try:
            ohlc1 = await correlation_service.fetch_ohlc(sym1, days)
            ohlc2 = await correlation_service.fetch_ohlc(sym2, days)
        except Exception as e:
            logger.error(f"OHLC fetch failed for backtest {sym1}/{sym2}: {e}")
            return await self._backtest_pair_fallback(sym1, sym2, days, params)

        if not ohlc1 or not ohlc2:
            return await self._backtest_pair_fallback(sym1, sym2, days, params)

        p1 = ohlc1["close"]
        p2 = ohlc2["close"]
        dates = ohlc1["dates"]  # Use sym1's dates (both symbols cover the same trading days)

        min_data = max(params.rolling_window + 5, params.beta_window + 5)
        if len(p1) < min_data or len(p2) < min_data:
            return {"error": f"Insufficient data for {sym1}/{sym2} — need at least {min_data} days"}

        min_len = min(len(p1), len(p2))
        p1_arr = np.array(p1[-min_len:], dtype=float)
        p2_arr = np.array(p2[-min_len:], dtype=float)
        dates = dates[-min_len:]

        # ── Cointegration pre-check ──
        coint_passed, coint_pvalue, half_life = self.is_cointegrated(
            p1_arr.tolist(), p2_arr.tolist(), params.coint_pvalue
        )

        coint_info = {
            "cointegrated": coint_passed,
            "coint_pvalue": round(coint_pvalue, 4),
            "half_life_days": round(half_life, 1),
            "coint_filter_active": params.require_cointegrated,
        }

        if params.require_cointegrated and not coint_passed:
            spread, betas = self._compute_spread(p1_arr, p2_arr, params)
            return {
                "error": f"Pair {sym1}/{sym2} is not cointegrated (p={coint_pvalue:.4f}, threshold={params.coint_pvalue}).",
                "sym1": sym1, "sym2": sym2,
                "price_data": None,
                "coint_info": coint_info,
                "num_observations": len(spread),
            }

        # ── Compute spread ──
        spread, betas = self._compute_spread(p1_arr, p2_arr, params)
        z_scores = self._compute_zscore(spread, params.rolling_window)
        cost_pct = params.transaction_cost_pct / 100.0

        # ── Run trading loop (shared with fallback) ──
        trades, daily_equity = self._run_trading_loop(spread, z_scores, dates, params, cost_pct)

        # ── Build response (shared with fallback) ──
        return self._build_backtest_response(
            sym1, sym2, days, spread, z_scores, betas,
            dates, trades, daily_equity, params, coint_info,
            price_data={"sym1": ohlc1, "sym2": ohlc2},
        )

    async def _backtest_pair_fallback(
        self,
        sym1: str,
        sym2: str,
        days: int = 252,
        params: Optional[BacktestParams] = None,
    ) -> Dict[str, Any]:
        """Fallback backtest that uses fetch_all_prices + _idx_to_date.

        Used when OHLC data is unavailable (nselib timeout, etc.).
        Dates use synthetic calendar-day dating — charts won't align with
        actual trading dates, but metrics are still valid.
        """
        if params is None:
            params = BacktestParams()

        prices_dict = await correlation_service.fetch_all_prices(days, top_n=0)
        p1 = prices_dict.get(sym1, [])
        p2 = prices_dict.get(sym2, [])

        min_data = max(params.rolling_window + 5, params.beta_window + 5)
        if len(p1) < min_data or len(p2) < min_data:
            return {"error": f"Insufficient data for {sym1}/{sym2} — need at least {min_data} days"}

        min_len = min(len(p1), len(p2))
        p1_arr = np.array(p1[-min_len:], dtype=float)
        p2_arr = np.array(p2[-min_len:], dtype=float)

        # Generate synthetic calendar-day dates
        dates = [self._idx_to_date(i, days) for i in range(min_len)]

        # ── Cointegration pre-check ──
        coint_passed, coint_pvalue, half_life = self.is_cointegrated(
            p1_arr.tolist(), p2_arr.tolist(), params.coint_pvalue
        )

        coint_info = {
            "cointegrated": coint_passed,
            "coint_pvalue": round(coint_pvalue, 4),
            "half_life_days": round(half_life, 1),
            "coint_filter_active": params.require_cointegrated,
        }

        if params.require_cointegrated and not coint_passed:
            return {
                "error": f"Pair {sym1}/{sym2} is not cointegrated (p={coint_pvalue:.4f}, threshold={params.coint_pvalue}).",
                "sym1": sym1, "sym2": sym2,
                "price_data": None,
                "coint_info": coint_info,
                "num_observations": min_len,
            }

        # ── Compute spread ──
        spread, betas = self._compute_spread(p1_arr, p2_arr, params)
        z_scores = self._compute_zscore(spread, params.rolling_window)
        cost_pct = params.transaction_cost_pct / 100.0

        # ── Run trading loop (shared with backtest_pair) ──
        trades, daily_equity = self._run_trading_loop(spread, z_scores, dates, params, cost_pct)

        # ── Build response (shared with backtest_pair) ──
        return self._build_backtest_response(
            sym1, sym2, days, spread, z_scores, betas,
            dates, trades, daily_equity, params, coint_info,
            price_data=None,
        )

    # ── Helpers ──

    @staticmethod
    def _idx_to_date(idx: int, total_days: int) -> str:
        return (datetime.now(timezone.utc) - timedelta(days=total_days - idx)).strftime("%Y-%m-%d")

    @staticmethod
    def _compute_metrics(
        trades: List[Dict[str, Any]],
        daily_equity: List[float],
        days: int,
    ) -> BacktestResult:
        total_trades = len(trades)
        if total_trades == 0:
            return BacktestResult(params=BacktestParams())

        winning = [t for t in trades if t.get("pnl_pct", 0) > 0]
        losing = [t for t in trades if t.get("pnl_pct", 0) <= 0]
        win_count = len(winning)
        loss_count = len(losing)

        total_return = sum(t.get("pnl_pct", 0) for t in trades)
        avg_win = sum(t["pnl_pct"] for t in winning) / win_count if win_count > 0 else 0
        avg_loss = sum(t["pnl_pct"] for t in losing) / loss_count if loss_count > 0 else 0

        gross_wins = sum(t["pnl_pct"] for t in winning)
        gross_losses = abs(sum(t["pnl_pct"] for t in losing))
        profit_factor = round(gross_wins / gross_losses, 2) if gross_losses > 0 else None  # no losing trades → undefined

        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
        years = days / 252

        # Annualized return from equity curve (accounts for compounding)
        if years > 0 and len(daily_equity) > 1:
            total_factor = (100.0 + daily_equity[-1]) / 100.0
            total_return = round((total_factor - 1.0) * 100, 4)  # overwrite simple sum
            annualized_return = (total_factor ** (1.0 / years) - 1.0) * 100.0
        else:
            annualized_return = 0.0

        daily_returns = np.diff(daily_equity)
        sharpe = 0.0
        if len(daily_returns) > 1 and np.std(daily_returns) > 0:
            sharpe = np.mean(daily_returns) / np.std(daily_returns) * math.sqrt(252)

        # Convert P&L to equity scale (starts at 1.0) so peak denominator is always >= 1.0
        equity_arr = 1.0 + np.array(daily_equity)
        peak = np.maximum.accumulate(equity_arr)
        drawdown = (peak - equity_arr) / peak * 100
        max_dd = float(np.max(drawdown)) if len(drawdown) > 0 else 0.0

        avg_bars = np.mean([t.get("bars_held", 0) for t in trades]) if total_trades > 0 else 0

        return BacktestResult(
            params=BacktestParams(),
            trades=trades,
            total_return_pct=total_return,
            annualized_return_pct=annualized_return,
            sharpe_ratio=sharpe,
            max_drawdown_pct=max_dd,
            win_rate=win_rate,
            total_trades=total_trades,
            winning_trades=win_count,
            losing_trades=loss_count,
            avg_win_pct=avg_win,
            avg_loss_pct=avg_loss,
            profit_factor=profit_factor,
            avg_bars_held=avg_bars,
            num_observations=len(daily_equity),
        )

    # ── Current Signal for a Pair ──

    @staticmethod
    def _compute_current_signal(
        prices1: List[float],
        prices2: List[float],
        rolling_window: int = 20,
        entry_z: float = 2.0,
    ) -> Dict[str, Any]:
        """Compute the current z-score, signal direction, and trade levels for a pair.

        Returns signal info dict or empty neutral dict if insufficient data.
        """
        if len(prices1) < rolling_window + 5 or len(prices2) < rolling_window + 5:
            return {
                "z_score": 0.0, "signal": "NEUTRAL",
                "current_ratio": 0.0, "mean_ratio": 0.0,
                "entry_level_up": 0.0, "entry_level_down": 0.0,
            }

        arr1 = np.array(prices1, dtype=float)
        arr2 = np.array(prices2, dtype=float)
        ratio = arr1 / arr2

        df = pd.Series(ratio)
        roll_mean = df.rolling(window=rolling_window).mean()
        roll_std = df.rolling(window=rolling_window).std()
        z = (df - roll_mean) / roll_std
        current_z = float(z.iloc[-1])
        current_ratio = float(ratio[-1])
        mean_r = float(roll_mean.iloc[-1])
        std_r = float(roll_std.iloc[-1])

        if current_z < -entry_z:
            signal = "LONG_SPREAD"
        elif current_z > entry_z:
            signal = "SHORT_SPREAD"
        else:
            signal = "NEUTRAL"

        return {
            "z_score": round(current_z, 4),
            "signal": signal,
            "current_ratio": round(current_ratio, 6),
            "mean_ratio": round(mean_r, 6),
            "std_ratio": round(std_r, 6),
            "entry_level_up": round(mean_r + entry_z * std_r, 6),
            "entry_level_down": round(mean_r - entry_z * std_r, 6),
            "rolling_window": rolling_window,
        }

    # ── Pair Rankings (Multi-Timeframe + Stability + Score) ──

    async def _compute_single_pair(
        self,
        sym1: str,
        sym2: str,
        prices_dict: Dict[str, List[float]],
        full_returns: Dict[str, np.ndarray],
        timeframes: List[int],
        symbol_to_sector: Dict[str, str],
    ) -> Dict[str, Any]:
        """Compute all analytics for a single stock pair.

        Used by the batch processor to compute pairs in parallel.
        """
        # Multi-timeframe correlations
        tf_corrs = {}
        for tf in timeframes:
            p1 = prices_dict.get(sym1, [])
            p2 = prices_dict.get(sym2, [])
            if len(p1) >= tf and len(p2) >= tf:
                r1 = correlation_service.compute_returns(p1[-tf:])
                r2 = correlation_service.compute_returns(p2[-tf:])
                if len(r1) >= 2 and len(r2) >= 2:
                    c = float(np.corrcoef(r1, r2)[0, 1])
                    if np.isnan(c):
                        c = 0.0
                    tf_corrs[f"{tf}d"] = round(c, 4)

        # Consistency
        corr_vals = list(tf_corrs.values())
        consistency = round(1.0 - min(1.0, float(np.std(corr_vals))), 2) if len(corr_vals) > 1 else 0.50
        avg_abs = float(np.mean([abs(v) for v in corr_vals])) if corr_vals else 0.0

        # Cointegration test
        p1_full = prices_dict.get(sym1, [])
        p2_full = prices_dict.get(sym2, [])
        is_coint = False
        coint_pval = 1.0
        hl = 0.0
        if len(p1_full) >= 30 and len(p2_full) >= 30:
            is_coint, coint_pval, hl = self.is_cointegrated(p1_full, p2_full, 0.05)

        # PVR Score
        r1_full = full_returns.get(sym1, np.array([0.0]))
        r2_full = full_returns.get(sym2, np.array([0.0]))
        pvr_spread, pvr_hedge, score = self._compute_pvr(r1_full, r2_full)

        # Live signal (z-score, entry/stop levels)
        signal_info = self._compute_current_signal(p1_full, p2_full)

        return {
            "sym1": sym1,
            "sym2": sym2,
            "sym1_sector": symbol_to_sector.get(sym1),
            "sym2_sector": symbol_to_sector.get(sym2),
            "correlations": tf_corrs,
            "avg_abs_corr": round(avg_abs, 4),
            "consistency": consistency,
            "cointegrated": is_coint,
            "coint_pvalue": round(coint_pval, 4),
            "half_life_days": round(hl, 1),
            "pvr_spread": round(pvr_spread * 100, 1),
            "pvr_hedge": round(pvr_hedge * 100, 1),
            "score": score,
            **signal_info,
        }

    async def compute_pair_rankings(
        self,
        max_days: int = 252,
        include_all: bool = False,
        top_n: int = 0,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Compute comprehensive pair rankings for Nifty 50 stocks.

        Architecture:
        - Pre-computes ALL C(50,2) = 1,225 pairs in async batches
        - Results are cached for 30 min on the backend
        - Only the top N best/tradable pairs are returned to the frontend

        Args:
            max_days: Max lookback period.
            include_all: If True, return ALL pairs (for full data export).
            top_n: Number of most liquid stocks to analyze. 0 = all 50.
            limit: Max number of top-ranked pairs to return (default 50).

        Returns:
            Dict with best_10, worst_10, and best_pairs (top N by score).
            Each pair includes: correlations, PVR score, live signal, entry/stop levels.
        """
        cache_key = _rankings_cache_key(max_days, top_n)
        now = time.time()

        # ── Check cache ──
        if cache_key in _PAIR_RANKINGS_CACHE:
            cached_at, cached_data = _PAIR_RANKINGS_CACHE[cache_key]
            if now - cached_at < _CACHE_TTL_SECONDS:
                logger.info("Using cached pair rankings (%d pairs)", len(cached_data.get("all_pairs", [])))
                # Return only what's needed from cache
                return self._build_ranking_response(cached_data, include_all, limit)

        # ── Cache miss: compute from scratch ──
        logger.info("Computing pair rankings from scratch (cache miss)")
        prices_dict = await correlation_service.fetch_all_prices(max_days, top_n=top_n)
        symbols = sorted(prices_dict.keys())
        symbol_to_sector = {s["symbol"]: s["sector"] for s in correlation_service.get_stocks()}

        timeframes = [tf for tf in [5, 10, 20, 60, 126, 252] if tf <= max_days]

        # ── Pre-compute full returns for each symbol ──
        full_returns: Dict[str, np.ndarray] = {}
        for sym in symbols:
            prices = prices_dict.get(sym, [])
            if len(prices) >= 10:
                full_returns[sym] = correlation_service.compute_returns(prices)
            else:
                full_returns[sym] = np.array([0.0])

        # ── Generate all pair combinations map ──
        pair_combos: List[Tuple[str, str]] = []
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                pair_combos.append((symbols[i], symbols[j]))

        total_pairs = len(pair_combos)
        logger.info("Generated %d pair combinations from %d stocks", total_pairs, len(symbols))

        # ── Process pairs in async batches ──
        BATCH_SIZE = 50
        MAX_CONCURRENT = 10  # semaphore limit for concurrent pair computations
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        async def _compute_with_limit(s1: str, s2: str) -> Optional[Dict[str, Any]]:
            async with semaphore:
                try:
                    return await self._compute_single_pair(
                        s1, s2, prices_dict, full_returns, timeframes, symbol_to_sector
                    )
                except Exception as e:
                    logger.error("Pair computation failed for %s/%s: %s", s1, s2, e)
                    return None

        all_pairs: List[Dict[str, Any]] = []
        for batch_start in range(0, total_pairs, BATCH_SIZE):
            batch = pair_combos[batch_start:batch_start + BATCH_SIZE]
            batch_results = await asyncio.gather(*[
                _compute_with_limit(s1, s2) for s1, s2 in batch
            ])
            for r in batch_results:
                if r is not None:
                    all_pairs.append(r)
            logger.info(
                "Batch %d/%d complete — %d/%d pairs computed",
                batch_start // BATCH_SIZE + 1,
                (total_pairs + BATCH_SIZE - 1) // BATCH_SIZE,
                len(all_pairs),
                total_pairs,
            )

        # Sort by score descending
        all_pairs.sort(key=lambda x: x["score"], reverse=True)

        # ── Enrich best_10 + worst_10 with backtest metrics inline ──
        # This runs before caching so cached data always has bt_sharpe, bt_return, etc.
        default_params = BacktestParams(
            entry_z=2.0, exit_z=0.0, stop_z=3.0,
            rolling_window=20, use_hedge_ratio=True,
            require_cointegrated=False,
            transaction_cost_pct=0.05,
        )
        enrichment_pairs = all_pairs[:10] + (all_pairs[-10:] if len(all_pairs) >= 10 else [])
        for p in enrichment_pairs:
            try:
                bt = await self.backtest_pair(p["sym1"], p["sym2"], days=min(max_days, 252), params=default_params)
                if "metrics" in bt:
                    m = bt["metrics"]
                    p["bt_return"] = m.get("total_return_pct")
                    p["bt_sharpe"] = m.get("sharpe_ratio")
                    p["bt_win_rate"] = m.get("win_rate")
                    p["bt_trades"] = m.get("total_trades")
                    p["bt_max_dd"] = m.get("max_drawdown_pct")
                    p["bt_profit_factor"] = m.get("profit_factor")
            except Exception as e:
                logger.debug("Auto-backtest failed for %s/%s: %s", p["sym1"], p["sym2"], e)

        # ── Cache the full result (including backtest data) ──
        cached_payload = {
            "all_pairs": all_pairs,
            "timeframes": timeframes,
            "symbol_to_sector": symbol_to_sector,
            "total_pairs": total_pairs,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        _PAIR_RANKINGS_CACHE[cache_key] = (time.time(), cached_payload)
        logger.info("Cached %d pair rankings with backtest data (TTL: %ds)", total_pairs, _CACHE_TTL_SECONDS)

        # ── Build response ──
        return self._build_ranking_response(cached_payload, include_all, limit)

    def _build_ranking_response(
        self,
        cached_payload: Dict[str, Any],
        include_all: bool = False,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Build the API response from cached pair data.

        Returns best_10, worst_10, and top `limit` best_pairs.
        Backtest metrics are already populated in the cached data.
        """
        all_pairs = cached_payload["all_pairs"]
        if not all_pairs:
            return {
                "best_10": [],
                "worst_10": [],
                "best_pairs": [],
                "total_pairs": 0,
                "timeframes": cached_payload.get("timeframes", []),
                "generated_at": cached_payload.get("generated_at", ""),
            }

        timeframes = cached_payload["timeframes"]
        total_pairs = cached_payload["total_pairs"]

        best_10_raw = all_pairs[:10]
        worst_10_raw = all_pairs[-10:] if len(all_pairs) >= 10 else []
        best_pairs_raw = all_pairs[:limit] if not include_all else all_pairs

        return {
            "best_10": best_10_raw,
            "worst_10": worst_10_raw,
            "best_pairs": best_pairs_raw,
            "total_pairs": total_pairs,
            "timeframes": timeframes,
            "generated_at": cached_payload["generated_at"],
            "cached": True,
        }

    # ── Portfolio Variance Reduction (PVR) Scoring ──

    @staticmethod
    def _compute_pvr(
        returns1: np.ndarray,
        returns2: np.ndarray,
    ) -> Tuple[float, float, float]:
        """Compute Portfolio Variance Reduction for a pair.

        Two modes:
        1. **PVR_spread** (short-pairs mode): Variance reduction from a long-short
           spread (A - β·B). This equals ρ² — the squared correlation. High for both
           strongly positive AND strongly negative pairs.

        2. **PVR_hedge** (buy-both hedge mode): Variance reduction from holding a
           long-only min-variance portfolio of both stocks. This captures the
           diversification/hedging benefit — buying two negatively-correlated stocks.

        The final **PVR** = max(PVR_spread, PVR_hedge), so the pair is scored
        on whichever strategy suits it best.

        Returns:
            (pvr_spread, pvr_hedge, score_0_100)
        """
        # Drop any NaN/inf values
        mask = ~(np.isnan(returns1) | np.isnan(returns2) | np.isinf(returns1) | np.isinf(returns2))
        r1, r2 = returns1[mask], returns2[mask]

        if len(r1) < 10:
            return 0.0, 0.0, 0

        var1 = float(np.var(r1, ddof=1))
        var2 = float(np.var(r2, ddof=1))

        if var1 < 1e-15 or var2 < 1e-15:
            return 0.0, 0.0, 0

        std1, std2 = np.sqrt(var1), np.sqrt(var2)
        cov = float(np.cov(r1, r2)[0, 1])
        corr = cov / (std1 * std2)
        corr = max(-1.0, min(1.0, corr))  # clamp to avoid numerical drift

        # ── PVR Spread (short-pairs mode) — A - β·B
        # β = cov / var2 → σ²(spread) = σ²(A) · (1 - ρ²)
        # PVR_spread = 1 - σ²(spread) / σ²(A) = ρ²
        pvr_spread = max(0.0, corr * corr)

        # ── PVR Hedge (buy-both mode) — min-variance long-only portfolio
        # Optimal weights: w1* = (var2 - cov) / (var1 + var2 - 2·cov), clipped to [0, 1]
        denom = var1 + var2 - 2.0 * cov
        if denom > 1e-15:
            w1 = (var2 - cov) / denom
            w1 = max(0.0, min(1.0, w1))
            w2 = 1.0 - w1
            port_var = w1 ** 2 * var1 + w2 ** 2 * var2 + 2.0 * w1 * w2 * cov
        else:
            port_var = min(var1, var2)

        baseline_var = min(var1, var2)
        if baseline_var > 1e-15:
            pvr_hedge = max(0.0, 1.0 - port_var / baseline_var)
        else:
            pvr_hedge = 0.0

        # Final score = best of both modes
        best_pvr = max(pvr_spread, pvr_hedge)
        score = min(100, max(0, int(round(best_pvr * 100))))

        return pvr_spread, pvr_hedge, score

    # ── Optimal Parameter Finder (Grid Search) ──

    async def find_optimal_params(self, max_days: int = 252, top_n: int = 10) -> Dict[str, Any]:
        """Grid search over strategy parameters to find what works best.

        Tests each parameter independently against defaults on top-ranked pairs.
        Finds optimal: entry_z, exit_z, stop_z, rolling_window, use_hedge_ratio.

        Args:
            max_days: Max lookback period.
            top_n: Number of most liquid stocks to analyze. 0 = all 50, 10 = top 10.
        """
        # Get top pairs for testing
        rankings = await self.compute_pair_rankings(max_days, top_n=top_n)
        # Select top pairs that are cointegrated (or highest scored)
        test_pairs = []
        for p in rankings.get("best_10", []):
            if len(test_pairs) >= 5:
                break
            if p.get("cointegrated", False):
                test_pairs.append(p)
        # Fallback: top 3 by score if no cointegrated pairs found
        if not test_pairs and rankings.get("best_10"):
            test_pairs = rankings["best_10"][:3]

        if not test_pairs:
            return {"error": "No pairs available for parameter optimization"}

        # ── Base parameters ──
        base_params = BacktestParams(
            entry_z=2.0, exit_z=0.0, stop_z=3.0,
            rolling_window=20, use_hedge_ratio=True,
            require_cointegrated=False,
            transaction_cost_pct=0.05,
        )

        param_tests = {
            "entry_z": {"values": [1.5, 2.0, 2.5], "base": 2.0},
            "exit_z": {"values": [0.0, 0.5, 1.0], "base": 0.0},
            "stop_z": {"values": [2.5, 3.0, 4.0], "base": 3.0},
            "rolling_window": {"values": [15, 20, 30], "base": 20},
            "use_hedge_ratio": {"values": [True, False], "base": True},
        }

        param_results = {}

        for param_name, config in param_tests.items():
            param_results[param_name] = {
                "tested_values": [],
                "best_value": config["base"],
                "best_avg_sharpe": -999,
            }

            for val in config["values"]:
                # Create params with this one value changed
                p = BacktestParams(
                    entry_z=base_params.entry_z,
                    exit_z=base_params.exit_z,
                    stop_z=base_params.stop_z,
                    rolling_window=base_params.rolling_window,
                    use_hedge_ratio=base_params.use_hedge_ratio,
                    require_cointegrated=False,
                    transaction_cost_pct=0.05,
                )
                setattr(p, param_name, val)

                # Run backtest on each test pair
                sharpe_sum = 0
                return_sum = 0
                count = 0
                for tp in test_pairs:
                    try:
                        result = await self.backtest_pair(
                            tp["sym1"], tp["sym2"], days=min(max_days, 252), params=p
                        )
                        if "metrics" in result:
                            sharpe = result["metrics"].get("sharpe_ratio", 0)
                            if sharpe > -10:  # filter extreme outliers
                                sharpe_sum += sharpe
                                return_sum += result["metrics"].get("total_return_pct", 0)
                                count += 1
                    except Exception:
                        continue

                avg_sharpe = round(sharpe_sum / count, 3) if count > 0 else -999
                avg_return = round(return_sum / count, 2) if count > 0 else 0

                entry = {
                    "value": val,
                    "avg_sharpe": avg_sharpe,
                    "avg_return_pct": avg_return,
                    "pairs_tested": count,
                }
                param_results[param_name]["tested_values"].append(entry)

                if avg_sharpe > param_results[param_name]["best_avg_sharpe"]:
                    param_results[param_name]["best_value"] = val
                    param_results[param_name]["best_avg_sharpe"] = avg_sharpe

        # Build recommended params from best values
        recommended = BacktestParams(
            entry_z=param_results["entry_z"]["best_value"],
            exit_z=param_results["exit_z"]["best_value"],
            stop_z=param_results["stop_z"]["best_value"],
            rolling_window=param_results["rolling_window"]["best_value"],
            use_hedge_ratio=param_results["use_hedge_ratio"]["best_value"],
            require_cointegrated=True,
            transaction_cost_pct=0.05,
        )

        return {
            "recommended_params": {
                "entry_z": recommended.entry_z,
                "exit_z": recommended.exit_z,
                "stop_z": recommended.stop_z,
                "rolling_window": recommended.rolling_window,
                "use_hedge_ratio": recommended.use_hedge_ratio,
            },
            "param_details": param_results,
            "pairs_used": [{"sym1": p["sym1"], "sym2": p["sym2"]} for p in test_pairs],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ── Signal Generation ──

    async def generate_signals(
        self,
        min_z: float = 1.5,
        timeframe: int = 60,
        limit: int = 20,
        require_cointegrated: bool = False,
    ) -> Dict[str, Any]:
        """Scan all pairs and return those with active trading signals.

        If require_cointegrated is True, also runs cointegration test on
        each candidate pair — only returns signals for cointegrated pairs.
        """
        matrix_result = await correlation_service.compute_matrix(timeframe)
        pairs = matrix_result["pairs"]
        symbol_to_sector = {s["symbol"]: s["sector"] for s in matrix_result["stocks"]}

        signals = []
        for pair in pairs:
            try:
                analytics = await correlation_service.compute_pair_analytics(
                    pair["sym1"], pair["sym2"], max(timeframe, 60)
                )
                if "error" in analytics:
                    continue

                z = analytics.get("z_score", 0)
                if abs(z) < min_z:
                    continue

                # Check cointegration if required
                is_coint = True
                coint_pval = 1.0
                hl = 0.0
                if require_cointegrated:
                    prices_dict = await correlation_service.fetch_all_prices(timeframe)
                    pr1 = prices_dict.get(pair["sym1"], [])
                    pr2 = prices_dict.get(pair["sym2"], [])
                    is_coint, coint_pval, hl = self.is_cointegrated(pr1, pr2, 0.05)
                    if not is_coint:
                        continue

                signal_type = "LONG_SPREAD" if z < 0 else "SHORT_SPREAD"
                signals.append({
                    "sym1": pair["sym1"],
                    "sym2": pair["sym2"],
                    "sym1_sector": symbol_to_sector.get(pair["sym1"]),
                    "sym2_sector": symbol_to_sector.get(pair["sym2"]),
                    "correlation": pair["correlation"],
                    "z_score": z,
                    "signal": signal_type,
                    "current_ratio": analytics.get("current_ratio"),
                    "mean_ratio": analytics.get("mean_ratio"),
                    "signal_reasoning": analytics.get("signal_reasoning", []),
                    "cointegrated": is_coint,
                    "coint_pvalue": round(coint_pval, 4),
                    "half_life_days": round(hl, 1),
                })
                if len(signals) >= limit:
                    break
            except Exception as e:
                logger.debug(f"Signal fetch failed for {pair['sym1']}/{pair['sym2']}: {e}")
                continue

        signals.sort(key=lambda x: abs(x["z_score"]), reverse=True)

        return {
            "signals": signals,
            "total_pairs_scanned": len(pairs),
            "active_signals": len(signals),
            "timeframe": timeframe,
            "min_z": min_z,
            "require_cointegrated": require_cointegrated,
            "has_statsmodels": True,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


# ── Pair Rankings Cache ──
_PAIR_RANKINGS_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL_SECONDS = 1800  # 30 minutes


def _rankings_cache_key(max_days: int, top_n: int) -> str:
    return f"rankings_{max_days}_{top_n}"


# Singleton
correlation_signal_service = CorrelationSignalService()
