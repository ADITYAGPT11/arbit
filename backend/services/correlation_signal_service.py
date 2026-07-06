"""Correlation Signal Service — Pairs trading signal generation & backtesting engine.

Improvements over v1:
- Cointegration filter (Engle-Granger test) — only trades truly mean-reverting pairs
- Dynamic hedge ratio (rolling OLS β) — makes spread stationary instead of raw ratio
- Transaction cost model — per-side cost for realistic backtest P&L
- Half-life estimation — reports how quickly the spread reverts
"""

import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from services.correlation_service import correlation_service

logger = logging.getLogger(__name__)

# ── Optional statsmodels (cointegration, OLS) ──
_HAS_STATSMODELS = False
try:
    from statsmodels.tsa.stattools import coint, adfuller
    from statsmodels.regression.linear_model import OLS
    import statsmodels.api as sm
    _HAS_STATSMODELS = True
except ImportError:
    logger.warning("statsmodels not installed — cointegration filter and hedge ratio disabled")


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
        if not _HAS_STATSMODELS or len(prices1) < 30 or len(prices2) < 30:
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
        if not _HAS_STATSMODELS or len(spread) < 30:
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
        if not _HAS_STATSMODELS or len(arr1) < window + 5:
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
        if params.use_hedge_ratio and _HAS_STATSMODELS:
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
        """
        if params is None:
            params = BacktestParams()

        # ── Fetch prices ──
        prices_dict = await correlation_service.fetch_all_prices(days)
        p1 = prices_dict.get(sym1, [])
        p2 = prices_dict.get(sym2, [])

        min_data = max(params.rolling_window + 5, params.beta_window + 5)
        if len(p1) < min_data or len(p2) < min_data:
            return {"error": f"Insufficient data for {sym1}/{sym2} — need at least {min_data} days"}

        min_len = min(len(p1), len(p2))
        p1_arr = np.array(p1[-min_len:], dtype=float)
        p2_arr = np.array(p2[-min_len:], dtype=float)

        # ── Cointegration pre-check (always run the test if statsmodels available) ──
        coint_passed = True
        coint_pvalue = 1.0
        half_life = 0.0
        if _HAS_STATSMODELS:
            coint_passed, coint_pvalue, half_life = self.is_cointegrated(
                p1_arr.tolist(), p2_arr.tolist(), params.coint_pvalue
            )

        coint_info = {
            "cointegrated": coint_passed,
            "coint_pvalue": round(coint_pvalue, 4),
            "half_life_days": round(half_life, 1),
            "coint_filter_active": params.require_cointegrated,
        }

        if params.require_cointegrated and not coint_passed and _HAS_STATSMODELS:
            # Still compute synthetic spread for informational metrics
            spread, betas = self._compute_spread(p1_arr, p2_arr, params)
            z_scores = self._compute_zscore(spread, params.rolling_window)
            return {
                "error": f"Pair {sym1}/{sym2} is not cointegrated (p={coint_pvalue:.4f}, threshold={params.coint_pvalue}). "
                         f"Mean-reversion strategy unreliable — try a different pair or disable the cointegration filter.",
                "sym1": sym1, "sym2": sym2,
                "coint_info": coint_info,
                "num_observations": len(spread),
            }

        # ── Compute spread ──
        spread, betas = self._compute_spread(p1_arr, p2_arr, params)
        z_scores = self._compute_zscore(spread, params.rolling_window)
        cost_pct = params.transaction_cost_pct / 100.0

        # ── Walk through and trade ──
        trades = []
        current_trade = None  # { side, entry_idx, entry_spread, ... }
        daily_equity = [0.0]  # cumulative net P&L %

        # Determine when we have valid z-scores
        start_idx = max(params.rolling_window, params.beta_window if params.use_hedge_ratio else 0)

        for i in range(start_idx, len(spread)):
            z = z_scores[i]
            if np.isnan(z):
                daily_equity.append(daily_equity[-1])
                continue

            # ── With an open trade: check stop-loss or target exit ──
            if current_trade is not None:
                # Stop-loss check
                if abs(z) >= params.stop_z:
                    gross_pnl, net_pnl = self._compute_trade_pnl(
                        current_trade["entry_spread"], spread[i],
                        current_trade["side"], cost_pct,
                    )
                    trades.append({
                        "entry_date": current_trade["entry_date"],
                        "exit_date": self._idx_to_date(i, days),
                        "entry_spread": round(float(current_trade["entry_spread"]), 6),
                        "exit_spread": round(float(spread[i]), 6),
                        "side": current_trade["side"],
                        "pnl_pct": round(net_pnl * 100, 2),
                        "gross_pnl_pct": round(gross_pnl * 100, 2),
                        "cost_pct": round(cost_pct * 200, 2),  # entry + exit
                        "exit_reason": "STOP_LOSS",
                        "bars_held": i - current_trade["entry_idx"],
                    })
                    last_mtm = current_trade.get("last_mtm_pnl", 0.0)
                    daily_equity.append(daily_equity[-1] + net_pnl - last_mtm)
                    current_trade = None
                    continue

                # Target exit check
                if abs(z) <= params.exit_z:
                    gross_pnl, net_pnl = self._compute_trade_pnl(
                        current_trade["entry_spread"], spread[i],
                        current_trade["side"], cost_pct,
                    )
                    trades.append({
                        "entry_date": current_trade["entry_date"],
                        "exit_date": self._idx_to_date(i, days),
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

                # Mark-to-market
                equity_at_entry = current_trade.get("equity_at_entry", daily_equity[-1])
                # MTM uses gross P&L (costs only applied at exit)
                mtm_ret = current_trade["_mtm_fn"](spread[i])
                current_trade["last_mtm_pnl"] = mtm_ret
                daily_equity.append(equity_at_entry + mtm_ret)
                continue

            # ── No open trade: check entry signals ──
            if z < -params.entry_z:
                # LONG_SPREAD: spread is too low, bet it rises
                mtm_fn = lambda s, entry=spread[i]: (s - entry) / abs(entry)
                current_trade = {
                    "side": "LONG_SPREAD",
                    "entry_idx": i,
                    "entry_spread": float(spread[i]),
                    "entry_date": self._idx_to_date(i, days),
                    "equity_at_entry": daily_equity[-1],
                    "last_mtm_pnl": 0.0,
                    "_mtm_fn": mtm_fn,
                }
                daily_equity.append(daily_equity[-1])  # no change on entry
            elif z > params.entry_z:
                # SHORT_SPREAD: spread is too high, bet it falls
                mtm_fn = lambda s, entry=spread[i]: (entry - s) / abs(entry)
                current_trade = {
                    "side": "SHORT_SPREAD",
                    "entry_idx": i,
                    "entry_spread": float(spread[i]),
                    "entry_date": self._idx_to_date(i, days),
                    "equity_at_entry": daily_equity[-1],
                    "last_mtm_pnl": 0.0,
                    "_mtm_fn": mtm_fn,
                }
                daily_equity.append(daily_equity[-1])
            else:
                daily_equity.append(daily_equity[-1])

        # ── Close any open trade at end of data ──
        if current_trade is not None:
            gross_pnl, net_pnl = self._compute_trade_pnl(
                current_trade["entry_spread"], spread[-1],
                current_trade["side"], cost_pct,
            )
            trades.append({
                "entry_date": current_trade["entry_date"],
                "exit_date": self._idx_to_date(len(spread) - 1, days),
                "entry_spread": round(float(current_trade["entry_spread"]), 6),
                "exit_spread": round(float(spread[-1]), 6),
                "side": current_trade["side"],
                "pnl_pct": round(net_pnl * 100, 2),
                "gross_pnl_pct": round(gross_pnl * 100, 2),
                "cost_pct": round(cost_pct * 200, 2),
                "exit_reason": "LAST",
                "bars_held": len(spread) - 1 - current_trade["entry_idx"],
            })

        # ── Compute metrics ──
        result = self._compute_metrics(trades, daily_equity, days)

        # ── Equity curve (sampled for charting) ──
        step = max(1, len(daily_equity) // 100)
        equity_curve = []
        for i in range(0, len(daily_equity), step):
            equity_curve.append({
                "date": self._idx_to_date(i + start_idx, days),
                "equity": round(100 + daily_equity[i] * 100, 2),
            })

        # ── Spread stats ──
        beta_values = betas.tolist() if betas is not None else []
        avg_beta = float(np.nanmean(betas)) if betas is not None and not np.all(np.isnan(betas)) else 1.0

        return {
            "sym1": sym1,
            "sym2": sym2,
            "days": days,
            "params": {
                "entry_z": params.entry_z,
                "exit_z": params.exit_z,
                "stop_z": params.stop_z,
                "rolling_window": params.rolling_window,
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
                "profit_factor": round(result.profit_factor, 2),
                "avg_bars_held": round(result.avg_bars_held, 1),
            },
            "trades": trades[-50:],
            "total_trades_count": len(trades),
            "equity_curve": equity_curve,
            "num_observations": len(spread),
        }

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
        profit_factor = gross_wins / gross_losses if gross_losses > 0 else float("inf")

        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
        years = days / 252
        annualized_return = ((1 + total_return / 100) ** (1 / years) - 1) * 100 if years > 0 else 0

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

    async def compute_pair_rankings(self, max_days: int = 252, include_all: bool = False) -> Dict[str, Any]:
        """Compute comprehensive rankings for ALL 1225 pairs.

        For each pair, pre-computes:
        - Correlation at 5d, 10d, 20d, 60d, 126d, 252d
        - Consistency across timeframes (low std = stable relationship)
        - Cointegration test (p-value + half-life)
        - Composite tradability score (0-100)

        Returns best 10, worst 10, each with current signal info (z-score, trade levels).
        If include_all=True, returns ALL pairs sorted by score (for the Correlation List view).
        """
        prices_dict = await correlation_service.fetch_all_prices(max_days)
        symbols = [s["symbol"] for s in correlation_service.get_stocks()]
        symbol_to_sector = {s["symbol"]: s["sector"] for s in correlation_service.get_stocks()}

        timeframes = [tf for tf in [5, 10, 20, 60, 126, 252] if tf <= max_days]
        pairs = []

        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                sym1, sym2 = symbols[i], symbols[j]

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

                # Consistency — how stable is correlation across timeframes
                corr_vals = list(tf_corrs.values())
                consistency = round(1.0 - min(1.0, float(np.std(corr_vals))), 2) if len(corr_vals) > 1 else 0.50

                # Average absolute correlation
                avg_abs = float(np.mean([abs(v) for v in corr_vals])) if corr_vals else 0.0

                # Cointegration test (using longest available data)
                p1_full = prices_dict.get(sym1, [])
                p2_full = prices_dict.get(sym2, [])
                is_coint = False
                coint_pval = 1.0
                hl = 0.0
                if _HAS_STATSMODELS and len(p1_full) >= 30 and len(p2_full) >= 30:
                    is_coint, coint_pval, hl = self.is_cointegrated(p1_full, p2_full, 0.05)

                # Composite score (0-100)
                score = self._compute_tradability_score(
                    avg_abs, consistency, is_coint, coint_pval, hl
                )

                pairs.append({
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
                    "score": score,
                })

        # Sort by score descending
        pairs.sort(key=lambda x: x["score"], reverse=True)

        # ── Compute live signal ──
        # For include_all=True: enrich ALL 1225 pairs (Correlation List needs signals per row)
        # For default: only enrich best_10 + worst_10 (saves ~2s on Rankings tab load)
        if include_all:
            for p in pairs:
                p1 = prices_dict.get(p["sym1"], [])
                p2 = prices_dict.get(p["sym2"], [])
                signal_info = self._compute_current_signal(p1, p2)
                p.update(signal_info)

        best_10 = pairs[:10]
        worst_10 = pairs[-10:]

        for p in best_10 + worst_10:
            if "z_score" not in p:  # skip if already enriched via include_all
                p1 = prices_dict.get(p["sym1"], [])
                p2 = prices_dict.get(p["sym2"], [])
                signal_info = self._compute_current_signal(p1, p2)
                p.update(signal_info)

        result = {
            "best_10": best_10,
            "worst_10": worst_10,
            "total_pairs": len(pairs),
            "timeframes": timeframes,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        if include_all:
            result["all_pairs"] = pairs  # all 1225 pairs

        return result

    @staticmethod
    def _compute_tradability_score(
        avg_abs_corr: float,
        consistency: float,
        coint_passed: bool,
        coint_pvalue: float,
        half_life: float,
    ) -> int:
        """Composite score 0-100 for how tradeable a pair is.

        Weighting:
        - Abs correlation (0-25): higher is better for mean reversion
        - Consistency (0-20): stable across timeframes
        - Cointegration (0-35): statistically mean-reverting
        - Half-life bonus (0-20): fast enough reversion
        """
        score = 0

        # Average absolute correlation (0-25)
        if avg_abs_corr >= 0.7:
            score += 25
        elif avg_abs_corr >= 0.5:
            score += 18
        elif avg_abs_corr >= 0.3:
            score += 10
        else:
            score += 3

        # Consistency (0-20)
        score += max(0, min(20, int(consistency * 20)))

        # Cointegration (0-35)
        if coint_passed and coint_pvalue < 0.01:
            score += 35
        elif coint_passed and coint_pvalue < 0.05:
            score += 30
        elif not _HAS_STATSMODELS:
            score += 10  # neutral when statsmodels unavailable
        elif coint_pvalue < 0.10:
            score += 15
        else:
            score += 2

        # Half-life bonus (0-20) — ideal range 5-20 days
        if 5 < half_life < 20:
            score += 20
        elif 3 < half_life < 60:
            score += 12
        elif half_life > 0:
            score += 5

        return min(100, max(0, score))

    # ── Optimal Parameter Finder (Grid Search) ──

    async def find_optimal_params(self, max_days: int = 252) -> Dict[str, Any]:
        """Grid search over strategy parameters to find what works best.

        Tests each parameter independently against defaults on top-ranked pairs.
        Finds optimal: entry_z, exit_z, stop_z, rolling_window, use_hedge_ratio.
        """
        # Get top pairs for testing
        rankings = await self.compute_pair_rankings(max_days)
        # Select top pairs that are cointegrated (or highest scored)
        test_pairs = []
        for p in rankings.get("best_10", []):
            if len(test_pairs) >= 5:
                break
            if _HAS_STATSMODELS and p.get("cointegrated", False):
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
                if require_cointegrated and _HAS_STATSMODELS:
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
            "has_statsmodels": _HAS_STATSMODELS,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


# Singleton
correlation_signal_service = CorrelationSignalService()
