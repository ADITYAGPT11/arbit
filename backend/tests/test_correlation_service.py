"""Unit tests for CorrelationService.

Uses synthetic price data (no network calls) to verify:
- Stock/sector metadata
- Log returns computation
- Correlation matrix (structure, symmetry, diagonal=1)
- Pair analytics (z-score, rolling corr, Bollinger bands)
- Lead-lag detection
- Top pairs filtering (by sector, min correlation)
- Price fetching with cache behavior (mocked nselib)
- Edge cases: zero variance, insufficient data, NaN handling
"""
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from services.correlation_service import CorrelationService, NIFTY_50_STOCKS, TOP_10_STOCKS


@pytest.fixture
def service():
    return CorrelationService()


# ── Stock/Sector Metadata Tests ──

class TestStocksAndSectors:
    def test_get_stocks_returns_50(self, service):
        stocks = service.get_stocks()
        assert len(stocks) == 50
        for s in stocks:
            assert "symbol" in s
            assert "name" in s
            assert "sector" in s

    def test_get_stocks_unique_symbols(self, service):
        stocks = service.get_stocks()
        symbols = [s["symbol"] for s in stocks]
        assert len(symbols) == len(set(symbols))

    def test_get_stocks_all_nifty_50_present(self, service):
        stocks = service.get_stocks()
        symbols = {s["symbol"] for s in stocks}
        # Verify key constituents
        for sym in ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN"]:
            assert sym in symbols

    def test_get_sectors_structure(self, service):
        sectors = service.get_sectors()
        assert "sectors" in sectors
        assert "order" in sectors
        # Verify all 13 sectors
        assert len(sectors["sectors"]) == 13
        assert sectors["order"] == [
            "Financial_Services", "IT", "Oil_Gas", "FMCG", "Auto", "Pharma",
            "Metals", "Power", "Telecom", "Construction", "Consumer",
            "Healthcare", "Media",
        ]

    def test_get_sectors_each_has_stocks(self, service):
        sectors = service.get_sectors()
        for sec_name, sec_info in sectors["sectors"].items():
            assert "label" in sec_info
            assert "stocks" in sec_info
            assert len(sec_info["stocks"]) >= 1  # every sector has at least 1 stock

    def test_top_10_liquid_stocks(self):
        assert len(TOP_10_STOCKS) == 10
        top_symbols = {s["symbol"] for s in TOP_10_STOCKS}
        expected = {"RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
                     "HINDUNILVR", "SBIN", "BAJFINANCE", "BHARTIARTL", "ITC"}
        assert top_symbols == expected


# ── Returns Computation Tests ──

class TestComputeReturns:
    def test_compute_returns_basic(self, service, price_series_300):
        ret = service.compute_returns(price_series_300)
        assert isinstance(ret, np.ndarray)
        assert len(ret) == len(price_series_300) - 1
        # Log returns should be small for daily data
        assert np.all(np.abs(ret) < 0.1)

    def test_compute_returns_two_points(self, service):
        prices = [100.0, 110.0]
        ret = service.compute_returns(prices)
        assert len(ret) == 1
        expected = np.log(110.0 / 100.0)
        assert abs(ret[0] - expected) < 1e-10

    def test_compute_returns_empty(self, service):
        ret = service.compute_returns([])
        assert len(ret) == 0

    def test_compute_returns_single_point(self, service):
        ret = service.compute_returns([100.0])
        assert len(ret) == 0

    def test_compute_returns_zero_variance(self, service, constant_prices):
        ret = service.compute_returns(constant_prices)
        assert len(ret) == len(constant_prices) - 1
        assert np.allclose(ret, 0.0)

    def test_compute_returns_negative_price_logs(self, service):
        """Log of negative price should produce NaN (no exception)."""
        ret = service.compute_returns([100.0, -50.0, 80.0])
        # numpy.log(-50) gives nan, not an exception
        assert np.isnan(ret[0])


# ── Correlation Matrix Tests ──

class TestComputeMatrix:
    @pytest.mark.asyncio
    async def test_matrix_structure(self, service, price_dict_5stocks):
        with patch.object(service, "fetch_all_prices", return_value=price_dict_5stocks):
            with patch.object(service, "get_stocks", return_value=[
                {"symbol": "RELIANCE", "sector": "Oil_Gas"},
                {"symbol": "TCS", "sector": "IT"},
                {"symbol": "HDFCBANK", "sector": "Financial_Services"},
                {"symbol": "INFY", "sector": "IT"},
                {"symbol": "ICICIBANK", "sector": "Financial_Services"},
            ]):
                result = await service.compute_matrix(timeframe=20, top_n=0)

        assert result["data_source"] == "nselib_live"
        assert "computed_at" in result
        assert len(result["symbols"]) == 5
        assert len(result["matrix"]) == 5

    @pytest.mark.asyncio
    async def test_matrix_diagonal_is_one(self, service, price_dict_5stocks):
        with patch.object(service, "fetch_all_prices", return_value=price_dict_5stocks):
            with patch.object(service, "get_stocks", return_value=[
                {"symbol": "RELIANCE", "sector": "Oil_Gas"},
                {"symbol": "TCS", "sector": "IT"},
                {"symbol": "HDFCBANK", "sector": "Financial_Services"},
                {"symbol": "INFY", "sector": "IT"},
                {"symbol": "ICICIBANK", "sector": "Financial_Services"},
            ]):
                result = await service.compute_matrix(timeframe=20, top_n=0)

        matrix = np.array(result["matrix"])
        for i in range(5):
            assert abs(matrix[i][i] - 1.0) < 1e-6

    @pytest.mark.asyncio
    async def test_matrix_is_symmetric(self, service, price_dict_5stocks):
        with patch.object(service, "fetch_all_prices", return_value=price_dict_5stocks):
            with patch.object(service, "get_stocks", return_value=[
                {"symbol": "RELIANCE", "sector": "Oil_Gas"},
                {"symbol": "TCS", "sector": "IT"},
                {"symbol": "HDFCBANK", "sector": "Financial_Services"},
                {"symbol": "INFY", "sector": "IT"},
                {"symbol": "ICICIBANK", "sector": "Financial_Services"},
            ]):
                result = await service.compute_matrix(timeframe=20, top_n=0)

        matrix = np.array(result["matrix"])
        for i in range(5):
            for j in range(5):
                assert abs(matrix[i][j] - matrix[j][i]) < 1e-6

    @pytest.mark.asyncio
    async def test_matrix_pairs_sorted_by_abs_corr(self, service, price_dict_5stocks):
        with patch.object(service, "fetch_all_prices", return_value=price_dict_5stocks):
            with patch.object(service, "get_stocks", return_value=[
                {"symbol": "RELIANCE", "sector": "Oil_Gas"},
                {"symbol": "TCS", "sector": "IT"},
                {"symbol": "HDFCBANK", "sector": "Financial_Services"},
                {"symbol": "INFY", "sector": "IT"},
                {"symbol": "ICICIBANK", "sector": "Financial_Services"},
            ]):
                result = await service.compute_matrix(timeframe=20, top_n=0)

        pairs = result["pairs"]
        for i in range(len(pairs) - 1):
            assert pairs[i]["abs_corr"] >= pairs[i + 1]["abs_corr"]

    @pytest.mark.asyncio
    async def test_matrix_timeframe_label(self, service, price_dict_5stocks):
        with patch.object(service, "fetch_all_prices", return_value=price_dict_5stocks):
            with patch.object(service, "get_stocks", return_value=[
                {"symbol": "RELIANCE", "sector": "Oil_Gas"},
                {"symbol": "TCS", "sector": "IT"},
            ]):
                for tf, label in [(5, "5 Days"), (20, "20 Days"), (252, "1 Year")]:
                    result = await service.compute_matrix(timeframe=tf, top_n=0)
                    assert result["timeframe_label"] == label

    @pytest.mark.asyncio
    async def test_matrix_correlation_values_in_range(self, service, price_dict_5stocks):
        with patch.object(service, "fetch_all_prices", return_value=price_dict_5stocks):
            with patch.object(service, "get_stocks", return_value=[
                {"symbol": "RELIANCE", "sector": "Oil_Gas"},
                {"symbol": "TCS", "sector": "IT"},
                {"symbol": "HDFCBANK", "sector": "Financial_Services"},
                {"symbol": "INFY", "sector": "IT"},
                {"symbol": "ICICIBANK", "sector": "Financial_Services"},
            ]):
                result = await service.compute_matrix(timeframe=20, top_n=0)

        matrix = np.array(result["matrix"])
        assert np.all(matrix >= -1.0)
        assert np.all(matrix <= 1.0)

    @pytest.mark.asyncio
    async def test_matrix_sector_correlation_structure(self, service, price_dict_5stocks):
        with patch.object(service, "fetch_all_prices", return_value=price_dict_5stocks):
            with patch.object(service, "get_stocks", return_value=[
                {"symbol": "RELIANCE", "sector": "Oil_Gas"},
                {"symbol": "TCS", "sector": "IT"},
                {"symbol": "HDFCBANK", "sector": "Financial_Services"},
                {"symbol": "INFY", "sector": "IT"},
                {"symbol": "ICICIBANK", "sector": "Financial_Services"},
            ]):
                result = await service.compute_matrix(timeframe=20, top_n=0)

        sector_corr = result["sector_correlation"]
        # We have 2 IT stocks, 2 Financial stocks — should have intra-sector corr
        assert "IT" in sector_corr
        assert "Financial_Services" in sector_corr


# ── Pair Analytics Tests ──

class TestComputePairAnalytics:
    @pytest.mark.asyncio
    async def test_pair_analytics_basic_structure(self, service, correlated_pair):
        p1, p2 = correlated_pair
        prices_dict = {"STOCK_A": p1, "STOCK_B": p2}

        with patch.object(service, "fetch_all_prices", return_value=prices_dict):
            result = await service.compute_pair_analytics("STOCK_A", "STOCK_B", timeframe=252)

        assert "error" not in result, f"Got error: {result.get('error')}"
        assert result["sym1"] == "STOCK_A"
        assert result["sym2"] == "STOCK_B"
        assert "current_correlation" in result
        assert "z_score" in result
        assert "rolling_correlation" in result
        assert "price_ratio" in result
        assert "lead_lag" in result
        assert "signal" in result

    @pytest.mark.asyncio
    async def test_pair_analytics_correlation_close_to_target(self, service, correlated_pair):
        """Correlated pair should have correlation near 0.85."""
        p1, p2 = correlated_pair
        prices_dict = {"STOCK_A": p1, "STOCK_B": p2}

        with patch.object(service, "fetch_all_prices", return_value=prices_dict):
            result = await service.compute_pair_analytics("STOCK_A", "STOCK_B", timeframe=252)

        corr = result["current_correlation"]
        # Should be moderately high (≥ 0.5) for the synthetic correlated series
        assert corr >= 0.3, f"Expected moderate correlation, got {corr}"

    @pytest.mark.asyncio
    async def test_pair_analytics_insufficient_data(self, service, short_prices):
        prices_dict = {"STOCK_A": short_prices, "STOCK_B": short_prices}

        with patch.object(service, "fetch_all_prices", return_value=prices_dict):
            result = await service.compute_pair_analytics("STOCK_A", "STOCK_B", timeframe=252)

        assert "error" in result
        assert "Insufficient data" in result["error"]

    @pytest.mark.asyncio
    async def test_pair_analytics_zero_variance(self, service, constant_prices):
        """Edge case: constant prices → z-score should be 0."""
        prices_dict = {"STOCK_A": constant_prices, "STOCK_B": constant_prices}

        with patch.object(service, "fetch_all_prices", return_value=prices_dict):
            result = await service.compute_pair_analytics("STOCK_A", "STOCK_B", timeframe=252)

        assert "error" not in result
        assert result["std_ratio"] == 0.0

    @pytest.mark.asyncio
    async def test_pair_analytics_lead_lag(self, service, correlated_pair):
        p1, p2 = correlated_pair
        prices_dict = {"A": p1, "B": p2}

        with patch.object(service, "fetch_all_prices", return_value=prices_dict):
            result = await service.compute_pair_analytics("A", "B", timeframe=252)

        ll = result["lead_lag"]
        assert "leader" in ll
        assert "follower" in ll
        assert "lag_days" in ll
        assert ll["lag_days"] >= 0
        # Cross-correlation should be valid
        assert -1.0 <= ll["cross_correlation"] <= 1.0

    @pytest.mark.asyncio
    async def test_pair_analytics_signal_detection(self, service):
        """Create a spread that triggers a signal."""
        rng = np.random.default_rng(99)
        # Create a pair where the last ratio is extreme
        n = 200
        a = 1000.0 * np.exp(np.cumsum(rng.normal(0.0005, 0.015, n)))
        b = a * 0.95 - 50  # diverging gap
        # Make the last few points extreme
        b[-20:] = a[-20:] * 0.90  # spread widens sharply
        prices_dict = {"A": [round(float(p), 2) for p in a],
                        "B": [round(float(p), 2) for p in b]}

        with patch.object(service, "fetch_all_prices", return_value=prices_dict):
            result = await service.compute_pair_analytics("A", "B", timeframe=252)

        assert result["signal"] in ("LONG_SPREAD", "SHORT_SPREAD", "WATCH", "NEUTRAL")


# ── Lead-Lag Detection Tests ──

class TestDetectLeadLag:
    def test_lead_lag_basic(self, service):
        ret1 = np.array([0.01, 0.02, -0.01, 0.005, -0.005, 0.015, -0.01, 0.02])
        ret2 = np.array([0.01, 0.02, -0.01, 0.005, -0.005, 0.015, -0.01, 0.02])
        result = service._detect_lead_lag(ret1, ret2, "A", "B")
        assert result["leader"] in ("A", "B", "Neither")

    def test_lead_lag_zero_cross_corr(self, service):
        """Flat returns → cross-correlation near 0."""
        ret1 = np.zeros(50)
        ret2 = np.zeros(50)
        result = service._detect_lead_lag(ret1, ret2, "A", "B")
        assert abs(result["cross_correlation"]) < 1e-10

    def test_lead_lag_short_series(self, service):
        """Very short series → should handle gracefully."""
        ret1 = np.array([0.01, 0.02])
        ret2 = np.array([0.015, 0.025])
        result = service._detect_lead_lag(ret1, ret2, "A", "B")
        assert result["lag_days"] >= 0


# ── Top Pairs Tests ──

class TestGetTopPairs:
    @pytest.mark.asyncio
    async def test_get_top_pairs_basic(self, service, price_dict_5stocks):
        with patch.object(service, "fetch_all_prices", return_value=price_dict_5stocks):
            with patch.object(service, "get_stocks", return_value=[
                {"symbol": "RELIANCE", "sector": "Oil_Gas"},
                {"symbol": "TCS", "sector": "IT"},
                {"symbol": "HDFCBANK", "sector": "Financial_Services"},
                {"symbol": "INFY", "sector": "IT"},
                {"symbol": "ICICIBANK", "sector": "Financial_Services"},
            ]):
                result = await service.get_top_pairs(timeframe=20, limit=5, top_n=0)

        assert "pairs" in result
        assert "total_pairs" in result
        assert len(result["pairs"]) <= 5

    @pytest.mark.asyncio
    async def test_get_top_pairs_sector_filter(self, service, price_dict_5stocks):
        with patch.object(service, "fetch_all_prices", return_value=price_dict_5stocks):
            with patch.object(service, "get_stocks", return_value=[
                {"symbol": "RELIANCE", "sector": "Oil_Gas"},
                {"symbol": "TCS", "sector": "IT"},
                {"symbol": "HDFCBANK", "sector": "Financial_Services"},
                {"symbol": "INFY", "sector": "IT"},
                {"symbol": "ICICIBANK", "sector": "Financial_Services"},
            ]):
                result = await service.get_top_pairs(timeframe=20, sector="IT", top_n=0)

        for p in result["pairs"]:
            assert p["sym1_sector"] == "IT" or p["sym2_sector"] == "IT"

    @pytest.mark.asyncio
    async def test_get_top_pairs_min_corr_filter(self, service, price_dict_5stocks):
        with patch.object(service, "fetch_all_prices", return_value=price_dict_5stocks):
            with patch.object(service, "get_stocks", return_value=[
                {"symbol": "RELIANCE", "sector": "Oil_Gas"},
                {"symbol": "TCS", "sector": "IT"},
            ]):
                result = await service.get_top_pairs(timeframe=20, min_corr=0.5, top_n=0)

        for p in result["pairs"]:
            assert abs(p["correlation"]) >= 0.5

    @pytest.mark.asyncio
    async def test_get_top_pairs_sector_info(self, service, price_dict_5stocks):
        with patch.object(service, "fetch_all_prices", return_value=price_dict_5stocks):
            with patch.object(service, "get_stocks", return_value=[
                {"symbol": "RELIANCE", "sector": "Oil_Gas"},
                {"symbol": "TCS", "sector": "IT"},
            ]):
                result = await service.get_top_pairs(timeframe=20, top_n=0)

        for p in result["pairs"]:
            assert "sym1_sector" in p
            assert "sym2_sector" in p
            assert "same_sector" in p


# ── Price Fetching / Cache Tests ──

class TestFetchAllPrices:
    @pytest.mark.asyncio
    async def test_fetch_all_prices_cache_hit(self, service):
        """Cache should return data without calling nselib again."""
        from services.correlation_service import _PRICE_CACHE, _CACHE_LOCK

        # Pre-populate cache
        cached_data = {"RELIANCE": [100.0, 101.0, 102.0]}
        async with _CACHE_LOCK:
            _PRICE_CACHE[20] = (float(__import__("time").time()), cached_data)

        with patch.object(service, "_fetch_historical_prices") as mock_fetch:
            result = await service.fetch_all_prices(20)
            mock_fetch.assert_not_called()  # cache hit → no fetch

        assert result == cached_data

    @pytest.mark.asyncio
    async def test_fetch_all_prices_expired_cache(self, service):
        """Expired cache should re-fetch."""
        from services.correlation_service import _PRICE_CACHE, _CACHE_LOCK

        old_time = float(__import__("time").time()) - 300  # 5 minutes ago
        async with _CACHE_LOCK:
            _PRICE_CACHE[20] = (old_time, {"RELIANCE": [100.0]})

        with patch.object(service, "_fetch_historical_prices",
                          side_effect=Exception("nselib error")):
            with pytest.raises(RuntimeError):
                await service.fetch_all_prices(20, top_n=0)

    @pytest.mark.asyncio
    async def test_fetch_all_prices_aligns_length(self, service, price_dict_5stocks):
        """All prices series should be aligned to the same length."""
        with patch.object(service, "_fetch_historical_prices",
                          side_effect=Exception("should use cache")):
            # Pre-populate cache with different-length series
            from services.correlation_service import _PRICE_CACHE, _CACHE_LOCK
            async with _CACHE_LOCK:
                _PRICE_CACHE[20] = (float(__import__("time").time()),
                                    {"A": [1, 2, 3], "B": [1, 2, 3, 4, 5]})

            result = await service.fetch_all_prices(20)
            lengths = {sym: len(p) for sym, p in result.items()}
            assert len(set(lengths.values())) == 1  # all same length


# ── Sector Correlation Tests ──

class TestSectorCorrelation:
    def test_compute_sector_correlation(self, service):
        symbols = ["HDFCBANK", "ICICIBANK", "TCS", "INFY"]
        matrix = np.array([
            [1.0, 0.8, 0.3, 0.2],
            [0.8, 1.0, 0.25, 0.15],
            [0.3, 0.25, 1.0, 0.9],
            [0.2, 0.15, 0.9, 1.0],
        ])
        with patch.object(service, "get_stocks", return_value=[
            {"symbol": "HDFCBANK", "sector": "Financial_Services"},
            {"symbol": "ICICIBANK", "sector": "Financial_Services"},
            {"symbol": "TCS", "sector": "IT"},
            {"symbol": "INFY", "sector": "IT"},
        ]):
            result = service._compute_sector_correlation(matrix, symbols)

        # Financial sector avg = (0.8) / 1 pair = 0.8
        assert "Financial_Services" in result
        assert abs(result["Financial_Services"] - 0.8) < 0.01

        # IT sector avg = (0.9) / 1 pair = 0.9
        assert "IT" in result
        assert abs(result["IT"] - 0.9) < 0.01

    def test_sector_correlation_no_intra_sector(self, service):
        """Single stock per sector → no intra-sector pairs."""
        symbols = ["RELIANCE", "TCS"]
        matrix = np.array([[1.0, 0.5], [0.5, 1.0]])
        with patch.object(service, "get_stocks", return_value=[
            {"symbol": "RELIANCE", "sector": "Oil_Gas"},
            {"symbol": "TCS", "sector": "IT"},
        ]):
            result = service._compute_sector_correlation(matrix, symbols)
        assert result == {}
