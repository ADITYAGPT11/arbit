"""Unit tests for CorrelationSignalService.

Tests all strategy components with synthetic data:
- Cointegration test (Engle-Granger)
- Half-life estimation
- Rolling OLS hedge ratio
- Spread computation (hedge ratio + ratio modes)
- Z-score computation
- P&L computation with transaction costs
- Full historical backtest
- PVR scoring
- Current signal detection
- Pair rankings with batch processing
- Metrics computation
- Optimal parameter grid search
- Signal generation
"""
from unittest.mock import patch

import numpy as np
import pytest

from services.correlation_service import CorrelationService
from services.correlation_signal_service import (
    CorrelationSignalService,
    BacktestParams,
    _rankings_cache_key,
    _PAIR_RANKINGS_CACHE,
)


@pytest.fixture
def service():
    return CorrelationSignalService()


# ── Cointegration Tests ──

class TestIsCointegrated:
    def test_cointegrated_pair(self, service, cointegrated_pair):
        """Truly cointegrated pair should pass."""
        p1, p2 = cointegrated_pair
        is_coint, pval, hl = service.is_cointegrated(p1, p2, 0.05)
        assert is_coint, f"Expected cointegrated, got p={pval:.4f}"
        assert pval <= 0.05
        assert 1 <= hl <= 500

    def test_independent_pair_not_cointegrated(self, service, independent_pair):
        """Independent pair should fail cointegration."""
        p1, p2 = independent_pair
        is_coint, pval, hl = service.is_cointegrated(p1, p2, 0.05)
        assert not is_coint

    def test_insufficient_data(self, service, short_prices):
        """Less than 30 data points → no cointegration."""
        is_coint, pval, hl = service.is_cointegrated(short_prices, short_prices)
        assert not is_coint
        assert pval == 1.0
        assert hl == 0.0

    def test_constant_prices(self, service, constant_prices):
        """Constant prices → should handle gracefully."""
        is_coint, pval, hl = service.is_cointegrated(constant_prices, constant_prices)
        assert isinstance(is_coint, bool)

    def test_same_prices_cointegrated(self, service, price_series_300):
        """Identical price series → spread = 0 → cointegrated."""
        is_coint, pval, hl = service.is_cointegrated(price_series_300, price_series_300, 0.05)
        assert is_coint

    def test_cointegrated_nan_handling(self, service):
        """Should not crash on NaN in prices."""
        prices = [100.0, float("nan"), 102.0, 103.0, float("nan"), 105.0] * 20
        is_coint, pval, hl = service.is_cointegrated(prices, prices, 0.05)
        assert isinstance(is_coint, bool)
        assert isinstance(pval, float)


# ── Half-Life Estimation Tests ──

class TestEstimateHalfLife:
    def test_half_life_mean_reverting(self, service):
        """Mean-reverting spread should give reasonable half-life."""
        rng = np.random.default_rng(42)
        phi = 0.85
        spread = np.zeros(200)
        for i in range(1, 200):
            spread[i] = phi * spread[i - 1] + rng.normal(0, 1)
        hl = service._estimate_half_life(spread)
        assert 1 <= hl <= 100

    def test_half_life_not_mean_reverting(self, service):
        """Random walk should return 999."""
        rng = np.random.default_rng(42)
        spread = np.cumsum(rng.normal(0, 1, 200))
        hl = service._estimate_half_life(spread)
        assert hl == 999.0

    def test_half_life_short_series(self, service, short_prices):
        """Less than 30 points → 0."""
        hl = service._estimate_half_life(np.array(short_prices))
        assert hl == 0.0

    def test_half_life_constant_spread(self, service):
        """Constant spread → mean-reverting (already at mean)."""
        spread = np.ones(100) * 10.0
        hl = service._estimate_half_life(spread)
        assert 1 <= hl <= 500

    def test_half_life_clamped(self, service):
        """Extreme gamma should clamp to [1, 500]."""
        rng = np.random.default_rng(42)
        spread = rng.normal(0, 0.001, 200)
        hl = service._estimate_half_life(spread)
        assert 1 <= hl <= 500


# ── Rolling Beta Tests ──

class TestComputeRollingBeta:
    def test_rolling_beta_basic(self, service):
        """β should converge to true value."""
        rng = np.random.default_rng(42)
        n = 200
        b = np.cumsum(rng.normal(0, 1, n))
        true_beta = 1.5
        a = true_beta * b + rng.normal(0, 5, n)
        betas = service._compute_rolling_beta(a, b, window=60)
        assert len(betas) == n
        later = betas[150:]
        later_valid = later[~np.isnan(later)]
        if len(later_valid) > 0:
            assert abs(np.mean(later_valid) - true_beta) < 0.5

    def test_rolling_beta_short_data(self, service):
        """Insufficient data → all 1.0."""
        a = np.array([100.0, 101.0])
        b = np.array([200.0, 202.0])
        betas = service._compute_rolling_beta(a, b, window=60)
        assert np.allclose(betas, 1.0)

    def test_rolling_beta_unit_beta(self, service):
        """A == B → beta ≈ 1."""
        rng = np.random.default_rng(42)
        a = np.cumsum(rng.normal(0, 1, 200))
        betas = service._compute_rolling_beta(a, a, window=60)
        valid = betas[~np.isnan(betas)]
        assert len(valid) > 0
        assert np.allclose(valid, 1.0, atol=0.05)


# ── Spread Computation Tests ──

class TestComputeSpread:
    def test_spread_hedge_ratio_mode(self, service):
        """Default hedge ratio mode."""
        arr1 = np.array([100.0, 101.0, 102.0, 103.0, 104.0, 105.0])
        arr2 = np.array([50.0, 50.5, 51.0, 51.5, 52.0, 52.5])
        params = BacktestParams(use_hedge_ratio=True, beta_window=3)
        spread, betas = service._compute_spread(arr1, arr2, params)
        assert len(spread) == 6
        assert betas is not None
        assert len(betas) == 6

    def test_spread_ratio_mode(self, service):
        """Legacy ratio mode."""
        arr1 = np.array([100.0, 101.0, 102.0])
        arr2 = np.array([50.0, 51.0, 52.0])
        params = BacktestParams(use_hedge_ratio=False)
        spread, betas = service._compute_spread(arr1, arr2, params)
        assert betas is None
        assert abs(spread[0] - 2.0) < 0.01

    def test_spread_log_ratio_mode(self, service):
        """Log ratio mode."""
        arr1 = np.array([100.0, 101.0, 102.0])
        arr2 = np.array([50.0, 51.0, 52.0])
        params = BacktestParams(use_hedge_ratio=False, use_log_ratio=True)
        spread, _ = service._compute_spread(arr1, arr2, params)
        assert abs(spread[0] - np.log(2.0)) < 0.01

    def test_spread_empty_arrays(self, service):
        """Empty arrays should not crash."""
        spread, betas = service._compute_spread(np.array([]), np.array([]), BacktestParams())
        assert len(spread) == 0


# ── Z-Score Tests ──

class TestComputeZScore:
    def test_zscore_basic(self, service):
        series = np.arange(10.0, 21.0)
        z = service._compute_zscore(series, window=5)
        assert len(z) == 11
        assert np.isnan(z[0])  # first 4 are NaN
        assert not np.isnan(z[-1])
        assert z[-1] > 0  # upward trend → positive z

    def test_zscore_short_series(self, service):
        z = service._compute_zscore(np.array([1.0, 2.0, 3.0]), window=10)
        assert np.all(np.isnan(z))

    def test_zscore_constant(self, service):
        z = service._compute_zscore(np.ones(50) * 100.0, window=10)
        assert abs(z[-1]) < 1e-10


# ── P&L Computation Tests ──

class TestComputeTradePnl:
    def test_long_spread_profit(self, service):
        gross, net = service._compute_trade_pnl(1.0, 2.0, "LONG_SPREAD", 0.0005)
        assert abs(gross - 1.0) < 0.01
        assert abs(net - 0.999) < 0.01

    def test_short_spread_profit(self, service):
        gross, net = service._compute_trade_pnl(2.0, 1.0, "SHORT_SPREAD", 0.0005)
        assert abs(gross - 0.5) < 0.01
        assert abs(net - 0.499) < 0.01

    def test_long_spread_loss(self, service):
        gross, _ = service._compute_trade_pnl(2.0, 1.0, "LONG_SPREAD", 0.0005)
        assert abs(gross - (-0.5)) < 0.01

    def test_zero_entry_spread(self, service):
        gross, net = service._compute_trade_pnl(0.0, 1.0, "LONG_SPREAD", 0.001)
        assert abs(gross) < 1e-10
        assert abs(net - (-0.001)) < 1e-10

    def test_no_cost_net_equals_gross(self, service):
        gross, net = service._compute_trade_pnl(1.0, 1.1, "LONG_SPREAD", 0.0)
        assert abs(gross - net) < 1e-10


# ── Backtest Tests (patched to avoid nselib calls) ──

class TestBacktestPair:
    @pytest.mark.asyncio
    async def test_backtest_cointegrated_pair(self, service, cointegrated_pair):
        p1, p2 = cointegrated_pair
        prices_dict = {"A": p1, "B": p2}
        with patch("services.correlation_signal_service.correlation_service.fetch_all_prices",
                   return_value=prices_dict):
            params = BacktestParams(entry_z=1.5, exit_z=0.0, stop_z=3.0,
                                    rolling_window=20, use_hedge_ratio=True,
                                    require_cointegrated=True, transaction_cost_pct=0.05)
            result = await service.backtest_pair("A", "B", days=252, params=params)
        assert "metrics" in result, f"Backtest failed: {result.get('error')}"
        m = result["metrics"]
        assert m["total_trades"] >= 0
        assert isinstance(m["sharpe_ratio"], float)
        assert "spread_series" in result
        assert "equity_curve" in result

    @pytest.mark.asyncio
    async def test_backtest_returns_metrics(self, service, cointegrated_pair):
        p1, p2 = cointegrated_pair
        prices_dict = {"A": p1, "B": p2}
        with patch("services.correlation_signal_service.correlation_service.fetch_all_prices",
                   return_value=prices_dict):
            result = await service.backtest_pair("A", "B")
        if "metrics" in result:
            for k in ["total_return_pct", "annualized_return_pct", "sharpe_ratio",
                       "max_drawdown_pct", "win_rate", "total_trades", "profit_factor"]:
                assert k in result["metrics"]

    @pytest.mark.asyncio
    async def test_backtest_insufficient_data(self, service, short_prices):
        prices_dict = {"A": short_prices, "B": short_prices}
        with patch("services.correlation_signal_service.correlation_service.fetch_all_prices",
                   return_value=prices_dict):
            result = await service.backtest_pair("A", "B")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_backtest_no_trades(self, service):
        rng = np.random.default_rng(42)
        n = 200
        a = np.cumsum(rng.normal(0.0005, 0.01, n)) + 1000
        b = a + rng.normal(0, 5, n)
        prices_dict = {"A": [round(float(p), 2) for p in a],
                       "B": [round(float(p), 2) for p in b]}
        with patch("services.correlation_signal_service.correlation_service.fetch_all_prices",
                   return_value=prices_dict):
            params = BacktestParams(entry_z=5.0, exit_z=0.0)
            result = await service.backtest_pair("A", "B", days=200, params=params)
        if "metrics" in result:
            assert result["metrics"]["total_trades"] == 0

    @pytest.mark.asyncio
    async def test_backtest_hedge_ratio_disabled(self, service, cointegrated_pair):
        p1, p2 = cointegrated_pair
        prices_dict = {"A": p1, "B": p2}
        with patch("services.correlation_signal_service.correlation_service.fetch_all_prices",
                   return_value=prices_dict):
            params = BacktestParams(entry_z=1.5, use_hedge_ratio=False, require_cointegrated=False)
            result = await service.backtest_pair("A", "B", params=params)
        assert "metrics" in result

    @pytest.mark.asyncio
    async def test_backtest_spread_series_structure(self, service, cointegrated_pair):
        p1, p2 = cointegrated_pair
        prices_dict = {"A": p1, "B": p2}
        with patch("services.correlation_signal_service.correlation_service.fetch_all_prices",
                   return_value=prices_dict):
            result = await service.backtest_pair("A", "B", days=252)
        if "spread_series" in result:
            for pt in result["spread_series"][:5]:
                assert "date" in pt
                assert "spread" in pt
                assert "zscore" in pt
                assert isinstance(pt["date"], str)
                assert isinstance(pt["spread"], float)

    @pytest.mark.asyncio
    async def test_backtest_equity_curve_structure(self, service, cointegrated_pair):
        p1, p2 = cointegrated_pair
        prices_dict = {"A": p1, "B": p2}
        with patch("services.correlation_signal_service.correlation_service.fetch_all_prices",
                   return_value=prices_dict):
            result = await service.backtest_pair("A", "B", days=252)
        if "equity_curve" in result and result["equity_curve"]:
            assert result["equity_curve"][0]["equity"] == 100.0


# ── PVR Scoring Tests ──

class TestComputePVR:
    def test_pvr_perfect_correlation(self, service):
        ret = np.random.default_rng(42).normal(0, 0.02, 100)
        pvr_spread, pvr_hedge, score = service._compute_pvr(ret, ret)
        assert abs(pvr_spread - 1.0) < 0.01
        assert score == 100

    def test_pvr_no_correlation(self, service):
        rng = np.random.default_rng(42)
        ret1, ret2 = rng.normal(0, 0.02, 200), rng.normal(0, 0.02, 200)
        pvr_spread, _, score = service._compute_pvr(ret1, ret2)
        assert pvr_spread < 0.3

    def test_pvr_short_series(self, service):
        pvr_spread, pvr_hedge, score = service._compute_pvr(
            np.array([0.01, 0.02, 0.03]), np.array([0.015, 0.025, 0.035])
        )
        assert score == 0

    def test_pvr_zero_variance(self, service):
        pvr_spread, pvr_hedge, score = service._compute_pvr(np.zeros(50), np.zeros(50))
        assert score == 0

    def test_pvr_nan_handling(self, service):
        ret1 = np.array([0.01, 0.02, float("nan"), 0.03, float("inf"), 0.04] * 20)
        ret2 = np.array([0.015, 0.025, 0.035, float("nan"), 0.045, 0.05] * 20)
        pvr_spread, pvr_hedge, score = service._compute_pvr(ret1, ret2)
        assert 0 <= score <= 100
        assert 0.0 <= pvr_spread <= 1.0
        assert 0.0 <= pvr_hedge <= 1.0


# ── Current Signal Tests ──

class TestComputeCurrentSignal:
    def test_signal_neutral(self, service):
        rng = np.random.default_rng(42)
        a = np.cumsum(rng.normal(0.0005, 0.01, 100)) + 1000
        b = a + rng.normal(0, 2, 100)
        signal = service._compute_current_signal(
            [round(float(p), 2) for p in a], [round(float(p), 2) for p in b],
            rolling_window=20, entry_z=2.0,
        )
        assert signal["signal"] == "NEUTRAL"

    def test_signal_short_spread(self, service):
        rng = np.random.default_rng(1)
        n = 100
        a = np.cumsum(rng.normal(0.0005, 0.01, n)) + 1000
        b = np.copy(a) / 0.9
        b[-10:] = a[-10:] * 0.80  # ratio spikes high
        signal = service._compute_current_signal(
            [round(float(p), 2) for p in a], [round(float(p), 2) for p in b],
            rolling_window=20, entry_z=1.5,
        )
        assert signal["signal"] == "SHORT_SPREAD"

    def test_signal_long_spread(self, service):
        rng = np.random.default_rng(2)
        n = 100
        a = np.cumsum(rng.normal(0.0005, 0.01, n)) + 1000
        b = a * 1.15
        b[-10:] = a[-10:] * 1.25  # ratio drops low
        signal = service._compute_current_signal(
            [round(float(p), 2) for p in a], [round(float(p), 2) for p in b],
            rolling_window=20, entry_z=1.5,
        )
        assert signal["signal"] == "LONG_SPREAD"

    def test_signal_insufficient_data(self, service, short_prices):
        signal = service._compute_current_signal(short_prices, short_prices)
        assert signal["signal"] == "NEUTRAL"
        assert signal["z_score"] == 0.0

    def test_signal_structure(self, service, price_series_300):
        signal = service._compute_current_signal(price_series_300, price_series_300)
        required = {"z_score", "signal", "current_ratio", "mean_ratio",
                     "std_ratio", "entry_level_up", "entry_level_down"}
        assert required.issubset(signal.keys())
        assert signal["signal"] in ("NEUTRAL", "LONG_SPREAD", "SHORT_SPREAD")


# ── Single Pair Computation Tests ──

class TestComputeSinglePair:
    @pytest.mark.asyncio
    async def test_single_pair_structure(self, service, price_dict_5stocks):
        prices_dict = price_dict_5stocks
        full_returns = {sym: CorrelationService.compute_returns(prices_dict[sym])
                        for sym in prices_dict}
        timeframes = [5, 10, 20, 60]
        symbol_to_sector = {"RELIANCE": "Oil_Gas", "TCS": "IT",
                            "HDFCBANK": "Financial_Services",
                            "INFY": "IT", "ICICIBANK": "Financial_Services"}
        result = await service._compute_single_pair(
            "RELIANCE", "TCS", prices_dict, full_returns, timeframes, symbol_to_sector
        )
        assert result["sym1"] == "RELIANCE"
        assert result["sym2"] == "TCS"
        for key in ["correlations", "avg_abs_corr", "consistency", "cointegrated",
                     "pvr_spread", "pvr_hedge", "score", "z_score", "signal"]:
            assert key in result

    @pytest.mark.asyncio
    async def test_single_pair_multi_timeframe_corrs(self, service, price_dict_5stocks):
        prices_dict = price_dict_5stocks
        full_returns = {sym: CorrelationService.compute_returns(prices_dict[sym])
                        for sym in prices_dict}
        symbol_to_sector = {"RELIANCE": "Oil_Gas", "TCS": "IT"}
        result = await service._compute_single_pair(
            "RELIANCE", "TCS", prices_dict, full_returns, [5, 10, 20], symbol_to_sector
        )
        for tf in [5, 10, 20]:
            assert f"{tf}d" in result["correlations"]
            assert -1.0 <= result["correlations"][f"{tf}d"] <= 1.0

    @pytest.mark.asyncio
    async def test_single_pair_score_range(self, service, price_dict_5stocks):
        prices_dict = price_dict_5stocks
        full_returns = {sym: CorrelationService.compute_returns(prices_dict[sym])
                        for sym in prices_dict}
        symbol_to_sector = {"RELIANCE": "Oil_Gas", "TCS": "IT"}
        result = await service._compute_single_pair(
            "RELIANCE", "TCS", prices_dict, full_returns, [5, 10, 20], symbol_to_sector
        )
        assert 0 <= result["score"] <= 100

    @pytest.mark.asyncio
    async def test_single_pair_empty_prices(self, service):
        result = await service._compute_single_pair("A", "B", {}, {}, [], {})
        assert result["sym1"] == "A"
        assert result["score"] == 0


# ── Metrics Computation Tests ──

class TestComputeMetrics:
    def test_empty_trades(self, service):
        result = service._compute_metrics([], [0.0], 252)
        assert result.total_trades == 0
        assert result.total_return_pct == 0.0
        assert result.sharpe_ratio == 0.0

    def test_all_winning_trades(self, service):
        trades = [{"pnl_pct": 1.0, "bars_held": 5}, {"pnl_pct": 2.0, "bars_held": 3},
                   {"pnl_pct": 1.5, "bars_held": 4}]
        daily_equity = [0.0, 0.01, 0.03, 0.02, 0.04, 0.045]
        result = service._compute_metrics(trades, daily_equity, 252)
        assert result.win_rate == 100.0
        assert result.winning_trades == 3
        assert result.losing_trades == 0
        assert result.profit_factor == 999.0

    def test_mixed_trades(self, service):
        trades = [{"pnl_pct": 2.0, "bars_held": 5}, {"pnl_pct": -1.0, "bars_held": 3},
                   {"pnl_pct": 1.5, "bars_held": 4}, {"pnl_pct": -0.5, "bars_held": 2}]
        daily_equity = [0.0, 0.02, 0.01, 0.03, 0.015, 0.035]
        result = service._compute_metrics(trades, daily_equity, 252)
        assert result.total_trades == 4
        assert result.winning_trades == 2
        assert result.losing_trades == 2
        assert result.sharpe_ratio > 0
        assert result.avg_bars_held > 0

    def test_drawdown_calculation(self, service):
        trades = [{"pnl_pct": 10.0, "bars_held": 1}]
        daily_equity = [0.0, 0.10, 0.08, 0.05, 0.12, 0.15]
        result = service._compute_metrics(trades, daily_equity, 252)
        assert result.max_drawdown_pct > 0


# ── Pair Rankings Tests ──

class TestComputePairRankings:
    @pytest.mark.asyncio
    async def test_rankings_structure(self, service, price_dict_5stocks):
        with patch("services.correlation_signal_service.correlation_service.fetch_all_prices",
                   return_value=price_dict_5stocks):
            with patch("services.correlation_signal_service.correlation_service.get_stocks",
                       return_value=[
                           {"symbol": "RELIANCE", "sector": "Oil_Gas"},
                           {"symbol": "TCS", "sector": "IT"},
                           {"symbol": "HDFCBANK", "sector": "Financial_Services"},
                           {"symbol": "INFY", "sector": "IT"},
                           {"symbol": "ICICIBANK", "sector": "Financial_Services"},
                       ]):
                result = await service.compute_pair_rankings(max_days=252, top_n=0, limit=5)

        assert "best_pairs" in result
        assert "best_10" in result
        assert "worst_10" in result
        assert result["total_pairs"] == 10  # C(5,2)

    @pytest.mark.asyncio
    async def test_rankings_sorted_by_score(self, service, price_dict_5stocks):
        with patch("services.correlation_signal_service.correlation_service.fetch_all_prices",
                   return_value=price_dict_5stocks):
            with patch("services.correlation_signal_service.correlation_service.get_stocks",
                       return_value=[
                           {"symbol": "RELIANCE", "sector": "Oil_Gas"},
                           {"symbol": "TCS", "sector": "IT"},
                           {"symbol": "HDFCBANK", "sector": "Financial_Services"},
                           {"symbol": "INFY", "sector": "IT"},
                           {"symbol": "ICICIBANK", "sector": "Financial_Services"},
                       ]):
                result = await service.compute_pair_rankings(max_days=252, top_n=0, limit=10)
        pairs = result["best_pairs"]
        for i in range(len(pairs) - 1):
            assert pairs[i]["score"] >= pairs[i + 1]["score"]

    @pytest.mark.asyncio
    async def test_rankings_limit(self, service, price_dict_5stocks):
        with patch("services.correlation_signal_service.correlation_service.fetch_all_prices",
                   return_value=price_dict_5stocks):
            with patch("services.correlation_signal_service.correlation_service.get_stocks",
                       return_value=[
                           {"symbol": "RELIANCE", "sector": "Oil_Gas"},
                           {"symbol": "TCS", "sector": "IT"},
                           {"symbol": "HDFCBANK", "sector": "Financial_Services"},
                           {"symbol": "INFY", "sector": "IT"},
                           {"symbol": "ICICIBANK", "sector": "Financial_Services"},
                       ]):
                result = await service.compute_pair_rankings(max_days=252, top_n=0, limit=3)
        assert len(result["best_pairs"]) <= 3

    @pytest.mark.asyncio
    async def test_rankings_cache_behavior(self, service, price_dict_5stocks):
        with patch("services.correlation_signal_service.correlation_service.fetch_all_prices",
                   return_value=price_dict_5stocks) as mock_fetch:
            with patch("services.correlation_signal_service.correlation_service.get_stocks",
                       return_value=[
                           {"symbol": "RELIANCE", "sector": "Oil_Gas"},
                           {"symbol": "TCS", "sector": "IT"},
                       ]):
                _PAIR_RANKINGS_CACHE.clear()
                await service.compute_pair_rankings(max_days=252, top_n=0)
                call_count_1 = mock_fetch.call_count
                await service.compute_pair_rankings(max_days=252, top_n=0)
                assert mock_fetch.call_count == call_count_1  # cache hit

    def test_rankings_cache_key(self):
        assert _rankings_cache_key(252, 0) == _rankings_cache_key(252, 0)
        assert _rankings_cache_key(252, 0) != _rankings_cache_key(126, 10)


# ── Build Ranking Response Tests ──

class TestBuildRankingResponse:
    def test_build_empty(self, service):
        result = service._build_ranking_response(
            {"all_pairs": [], "timeframes": [], "total_pairs": 0, "generated_at": ""}
        )
        assert result["best_10"] == []
        assert result["worst_10"] == []
        assert result["best_pairs"] == []
        assert result["total_pairs"] == 0

    def test_build_with_data(self, service):
        pairs = [{"score": 100 - i, "sym1": f"A{i}", "sym2": f"B{i}"} for i in range(20)]
        result = service._build_ranking_response(
            {"all_pairs": pairs, "timeframes": [5, 10, 20], "total_pairs": 20, "generated_at": "2026-01-01"},
            include_all=False, limit=5,
        )
        assert len(result["best_10"]) == 10
        assert len(result["worst_10"]) == 10
        assert len(result["best_pairs"]) == 5
        assert result["cached"] is True

    def test_build_include_all(self, service):
        pairs = [{"score": i, "sym1": f"A{i}", "sym2": f"B{i}"} for i in range(20)]
        result = service._build_ranking_response(
            {"all_pairs": pairs, "timeframes": [5, 10, 20], "total_pairs": 20, "generated_at": "2026-01-01"},
            include_all=True, limit=5,
        )
        assert len(result["best_pairs"]) == 20  # all pairs


# ── Signal Generation Tests ──

class TestGenerateSignals:
    @pytest.mark.asyncio
    async def test_generate_signals_structure(self, service):
        matrix_result = {
            "pairs": [
                {"sym1": "RELIANCE", "sym2": "TCS", "correlation": 0.5},
                {"sym1": "HDFCBANK", "sym2": "ICICIBANK", "correlation": 0.8},
            ],
            "stocks": [
                {"symbol": "RELIANCE", "sector": "Oil_Gas"},
                {"symbol": "TCS", "sector": "IT"},
                {"symbol": "HDFCBANK", "sector": "Financial_Services"},
                {"symbol": "ICICIBANK", "sector": "Financial_Services"},
            ],
        }
        with patch("services.correlation_signal_service.correlation_service.compute_matrix",
                   return_value=matrix_result):
            with patch("services.correlation_signal_service.correlation_service.compute_pair_analytics",
                       return_value={
                           "z_score": 2.5, "signal": "SHORT_SPREAD",
                           "current_ratio": 1.05, "mean_ratio": 1.0,
                           "signal_reasoning": ["Spread is 2.5σ from mean"],
                       }):
                result = await service.generate_signals(min_z=2.0, limit=5)

        assert "signals" in result
        assert "total_pairs_scanned" in result
        assert "active_signals" in result
        assert result["has_statsmodels"] is True

    @pytest.mark.asyncio
    async def test_generate_signals_empty(self, service):
        with patch("services.correlation_signal_service.correlation_service.compute_matrix",
                   return_value={
                       "pairs": [{"sym1": "A", "sym2": "B", "correlation": 0.1}],
                       "stocks": [{"symbol": "A", "sector": "IT"}, {"symbol": "B", "sector": "IT"}],
                   }):
            with patch("services.correlation_signal_service.correlation_service.compute_pair_analytics",
                       return_value={"z_score": 0.5, "signal": "NEUTRAL"}):
                result = await service.generate_signals(min_z=2.0)
        assert len(result["signals"]) == 0
        assert result["active_signals"] == 0


# ── Optimal Params Tests ──

class TestFindOptimalParams:
    @pytest.mark.asyncio
    async def test_optimal_params_structure(self, service, price_dict_5stocks):
        with patch("services.correlation_signal_service.correlation_service.fetch_all_prices",
                   return_value=price_dict_5stocks):
            with patch("services.correlation_signal_service.correlation_service.get_stocks",
                       return_value=[
                           {"symbol": "RELIANCE", "sector": "Oil_Gas"},
                           {"symbol": "TCS", "sector": "IT"},
                       ]):
                result = await service.find_optimal_params(max_days=252, top_n=0)

        assert "recommended_params" in result
        assert "param_details" in result
        for param in ["entry_z", "exit_z", "stop_z", "rolling_window", "use_hedge_ratio"]:
            assert param in result["recommended_params"]
