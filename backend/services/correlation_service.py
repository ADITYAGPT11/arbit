"""Correlation Analysis Service — Nifty 50 stock correlations across multiple timeframes."""
import asyncio
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Check whether nselib is available AND the NSE API is reachable
_HAS_NSELIB = False
_NSELIB_EXECUTOR = None
try:
    from nselib import capital_market
    _NSELIB_EXECUTOR = ThreadPoolExecutor(max_workers=5)
    # Quick probe — does the API actually respond?
    try:
        future = _NSELIB_EXECUTOR.submit(
            capital_market.price_volume_data,
            symbol="RELIANCE",
            from_date="20-05-2026",
            to_date="26-06-2026",
        )
        df = future.result(timeout=8)
        _HAS_NSELIB = df is not None and not df.empty
        if _HAS_NSELIB:
            logger.info("nselib available — using live NSE data")
        else:
            logger.info("nselib returned empty data — using synthetic prices")
    except (TimeoutError, Exception) as e:
        logger.info("nselib API unreachable (%s) — using synthetic data", e)
        _HAS_NSELIB = False
except ImportError:
    logger.info("nselib not installed — using synthetic price data")

# ── Nifty 50 constituents with sector mapping ──
# Sectors: Financial_Services, IT, Oil_Gas, FMCG, Auto, Pharma, Metals, Power, Telecom, Construction, Consumer, Media, Healthcare
NIFTY_50_STOCKS = [
    # Financial Services (10)
    {"symbol": "HDFCBANK",  "name": "HDFC Bank",            "sector": "Financial_Services"},
    {"symbol": "ICICIBANK", "name": "ICICI Bank",           "sector": "Financial_Services"},
    {"symbol": "KOTAKBANK", "name": "Kotak Mahindra Bank",  "sector": "Financial_Services"},
    {"symbol": "AXISBANK",  "name": "Axis Bank",            "sector": "Financial_Services"},
    {"symbol": "SBIN",      "name": "State Bank of India",  "sector": "Financial_Services"},
    {"symbol": "INDUSINDBK","name": "IndusInd Bank",         "sector": "Financial_Services"},
    {"symbol": "BAJFINANCE","name": "Bajaj Finance",        "sector": "Financial_Services"},
    {"symbol": "BAJAJFINSV","name": "Bajaj Finserv",        "sector": "Financial_Services"},
    {"symbol": "HDFCLIFE",  "name": "HDFC Life Insurance",  "sector": "Financial_Services"},
    {"symbol": "SBILIFE",   "name": "SBI Life Insurance",   "sector": "Financial_Services"},
    # IT (5)
    {"symbol": "TCS",       "name": "Tata Consultancy Services", "sector": "IT"},
    {"symbol": "INFY",      "name": "Infosys",              "sector": "IT"},
    {"symbol": "HCLTECH",   "name": "HCL Technologies",     "sector": "IT"},
    {"symbol": "WIPRO",     "name": "Wipro",                "sector": "IT"},
    {"symbol": "TECHM",     "name": "Tech Mahindra",        "sector": "IT"},
    # Oil & Gas (4)
    {"symbol": "RELIANCE",  "name": "Reliance Industries",  "sector": "Oil_Gas"},
    {"symbol": "ONGC",      "name": "Oil & Natural Gas Corp","sector": "Oil_Gas"},
    {"symbol": "BPCL",      "name": "Bharat Petroleum",     "sector": "Oil_Gas"},
    {"symbol": "HINDPETRO", "name": "Hindustan Petroleum",  "sector": "Oil_Gas"},
    # FMCG (5)
    {"symbol": "HINDUNILVR","name": "Hindustan Unilever",   "sector": "FMCG"},
    {"symbol": "ITC",       "name": "ITC Ltd",              "sector": "FMCG"},
    {"symbol": "NESTLEIND", "name": "Nestlé India",         "sector": "FMCG"},
    {"symbol": "BRITANNIA", "name": "Britannia Industries",  "sector": "FMCG"},
    {"symbol": "DABUR",     "name": "Dabur India",          "sector": "FMCG"},
    # Auto (5)
    {"symbol": "MARUTI",    "name": "Maruti Suzuki India",  "sector": "Auto"},
    {"symbol": "TATAMOTORS","name": "Tata Motors",          "sector": "Auto"},
    {"symbol": "M&M",       "name": "Mahindra & Mahindra",  "sector": "Auto"},    {"symbol": "BAJAJ-AUTO", "name": "Bajaj Auto",           "sector": "Auto"},
    {"symbol": "EICHERMOT", "name": "Eicher Motors",        "sector": "Auto"},
    # Pharma (4)
    {"symbol": "SUNPHARMA", "name": "Sun Pharmaceutical",   "sector": "Pharma"},
    {"symbol": "DIVISLAB",  "name": "Divi's Laboratories",  "sector": "Pharma"},
    {"symbol": "CIPLA",     "name": "Cipla",                "sector": "Pharma"},
    {"symbol": "DRREDDY",   "name": "Dr. Reddy's Labs",     "sector": "Pharma"},
    # Metals (3)
    {"symbol": "TATASTEEL", "name": "Tata Steel",           "sector": "Metals"},
    {"symbol": "JSWSTEEL",  "name": "JSW Steel",            "sector": "Metals"},
    {"symbol": "HINDALCO",  "name": "Hindalco Industries",  "sector": "Metals"},
    # Power (3)
    {"symbol": "NTPC",      "name": "NTPC Ltd",             "sector": "Power"},
    {"symbol": "POWERGRID", "name": "Power Grid Corp",      "sector": "Power"},
    {"symbol": "ADANIGREEN","name": "Adani Green Energy",   "sector": "Power"},
    # Telecom (1)
    {"symbol": "BHARTIARTL","name": "Bharti Airtel",        "sector": "Telecom"},
    # Construction & Engineering (4)
    {"symbol": "LT",        "name": "Larsen & Toubro",      "sector": "Construction"},
    {"symbol": "ULTRACEMCO","name": "UltraTech Cement",     "sector": "Construction"},
    {"symbol": "ADANIPORTS","name": "Adani Ports & SEZ",    "sector": "Construction"},
    {"symbol": "GRASIM",    "name": "Grasim Industries",    "sector": "Construction"},
    # Consumer (4)
    {"symbol": "TITAN",     "name": "Titan Company",        "sector": "Consumer"},
    {"symbol": "ASIANPAINT","name": "Asian Paints",         "sector": "Consumer"},
    {"symbol": "TRENT",     "name": "Trent Ltd",            "sector": "Consumer"},
    {"symbol": "DMART",     "name": "Avenue Supermarts (DMart)","sector": "Consumer"},
    # Healthcare (1)
    {"symbol": "APOLLOHOSP","name": "Apollo Hospitals",     "sector": "Healthcare"},
    # Media (1)
    {"symbol": "ZEEL",      "name": "Zee Entertainment",   "sector": "Media"},
]

SECTOR_ORDER = [
    "Financial_Services", "IT", "Oil_Gas", "FMCG", "Auto", "Pharma",
    "Metals", "Power", "Telecom", "Construction", "Consumer", "Healthcare", "Media"
]

SECTOR_LABELS = {
    "Financial_Services": "Financial Services",
    "Oil_Gas": "Oil & Gas",
    "Construction": "Construction & Engg",
    "Consumer": "Consumer Goods",
    "Healthcare": "Healthcare",
    "Media": "Media",
}

TIMEFRAME_LABELS = {
    5: "5 Days",
    10: "10 Days",
    20: "20 Days",
    60: "60 Days",
    126: "6 Months",
    252: "1 Year",
    504: "2 Years",
    756: "3 Years",
}

# Simple in-memory cache for fetched prices (key: days, value: (timestamp, prices_dict))
_PRICE_CACHE: Dict[int, Tuple[float, Dict[str, List[float]]]] = {}
_CACHE_TTL_SECONDS = 120  # 2 minutes

# Base prices for fallback synthetic data (approximate realistic prices)
_BASE_PRICES = {
    "HDFCBANK": 1720, "ICICIBANK": 1280, "KOTAKBANK": 1890, "AXISBANK": 1180,
    "SBIN": 825, "INDUSINDBK": 1480,    "BAJFINANCE": 7450, "BAJAJFINSV": 1720,
    "HDFCLIFE": 680, "SBILIFE": 1450,
    "TCS": 3950, "INFY": 1820, "HCLTECH": 1920, "WIPRO": 295, "TECHM": 1650,
    "RELIANCE": 2850, "ONGC": 265, "BPCL": 620, "HINDPETRO": 470,
    "HINDUNILVR": 2450, "ITC": 485, "NESTLEIND": 2500, "BRITANNIA": 5200, "DABUR": 560,
    "MARUTI": 11200, "TATAMOTORS": 780, "M&M": 2050,    "BAJAJ-AUTO": 9500, "EICHERMOT": 4500,
    "SUNPHARMA": 1850, "DIVISLAB": 3800, "CIPLA": 1520, "DRREDDY": 5400,
    "TATASTEEL": 155, "JSWSTEEL": 920, "HINDALCO": 680,
    "NTPC": 385, "POWERGRID": 325, "ADANIGREEN": 1800,
    "BHARTIARTL": 1650,
    "LT": 3650, "ULTRACEMCO": 11800, "ADANIPORTS": 1300, "GRASIM": 2600,
    "TITAN": 3520, "ASIANPAINT": 2280, "TRENT": 1500,    "DMART": 4200,
    "APOLLOHOSP": 6200, "ZEEL": 145,
}


class CorrelationService:
    """Correlation analysis for Nifty 50 stocks across multiple timeframes."""

    @staticmethod
    def get_stocks() -> List[Dict[str, Any]]:
        """Return Nifty 50 stock list with sector info."""
        return NIFTY_50_STOCKS

    @staticmethod
    def get_sectors() -> Dict[str, Any]:
        """Return sector groupings."""
        sectors = defaultdict(list)
        for s in NIFTY_50_STOCKS:
            sectors[s["sector"]].append(s["symbol"])
        return {
            "sectors": {k: {"label": SECTOR_LABELS.get(k, k.replace("_", " ")), "stocks": v}
                        for k, v in sectors.items()},
            "order": SECTOR_ORDER,
        }

    @staticmethod
    async def _fetch_historical_prices(symbol: str, days: int) -> Optional[pd.DataFrame]:
        """Fetch historical daily data using nselib (non-blocking). Returns DataFrame with 'close' column."""
        if not _HAS_NSELIB:
            return None
        try:
            from nselib import capital_market
            loop = asyncio.get_running_loop()
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=days + 30)  # buffer for weekends/holidays

            df = await asyncio.wait_for(
                loop.run_in_executor(
                    _NSELIB_EXECUTOR,
                    lambda: capital_market.price_volume_data(
                        symbol=symbol,
                        from_date=start.strftime("%d-%m-%Y"),
                        to_date=end.strftime("%d-%m-%Y"),
                    ),
                ),
                timeout=5,  # 5s per stock
            )

            if df is not None and not df.empty:
                if isinstance(df, pd.DataFrame):
                    # nselib returns columns like 'Close Price', 'Open Price', etc. with spaces
                    df = df.rename(columns={
                        "Close Price": "close",
                        "Open Price": "open",
                        "High Price": "high",
                        "Low Price": "low",
                        "Total Traded Quantity": "volume",
                        "Date": "DATE",
                    })
                    # Convert price/volume columns to numeric
                    for col in ["close", "open", "high", "low", "volume"]:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                    df = df.sort_values("DATE")
                    df = df.tail(days)
                    return df
        except asyncio.TimeoutError:
            logger.debug(f"nselib timed out for {symbol}")
        except Exception as e:
            logger.debug(f"nselib fetch failed for {symbol}: {e}")
        return None

    @staticmethod
    def _generate_synthetic_prices(symbol: str, days: int, seed_offset: int = 0) -> List[float]:
        """Fallback: generate correlated synthetic prices when nsepython fails.
        Uses local Random/RNG instances so global random state is never touched."""
        base = _BASE_PRICES.get(symbol, 1000)
        seed = hash(symbol) % 10000 + seed_offset
        rng = random.Random(seed)
        nrng = np.random.default_rng(seed)

        prices = [base]
        vol = 0.012 + (seed % 50) * 0.0002  # 1.2-2.2% daily vol
        drift = 0.0003 + (seed % 30) * 0.00001  # slight upward bias

        for _ in range(days):
            ret = float(nrng.normal(drift, vol))
            prices.append(round(prices[-1] * (1 + ret), 2))
        return prices

    async def fetch_price_data(self, symbol: str, days: int) -> Optional[List[float]]:
        """Fetch close prices for a symbol. Tries nselib, falls back to synthetic."""
        df = await self._fetch_historical_prices(symbol, days)
        if df is not None and "close" in df.columns:
            return df["close"].dropna().tolist()
        return None

    async def fetch_all_prices(self, days: int) -> Dict[str, List[float]]:
        """Fetch close prices for all Nifty 50 stocks. Returns dict of symbol -> prices.
        Uses in-memory cache to avoid re-fetching within CACHE_TTL_SECONDS.
        Fetches stocks in parallel batches for speed, with a total timeout.
        If nselib is too slow, falls back to synthetic data."""
        now = time.time()
        if days in _PRICE_CACHE:
            cached_at, cached_data = _PRICE_CACHE[days]
            if now - cached_at < _CACHE_TTL_SECONDS:
                return cached_data

        prices_dict: Dict[str, List[float]] = {}
        failed_stocks: List[str] = []

        if _HAS_NSELIB:
            symbols = [s["symbol"] for s in NIFTY_50_STOCKS]
            batch_size = 5

            async def _fetch_batches() -> None:
                """Fetch all stocks in parallel batches."""
                nonlocal failed_stocks, prices_dict
                batch_failures: List[str] = []
                batch_successes: Dict[str, List[float]] = {}

                for batch_start in range(0, len(symbols), batch_size):
                    batch = symbols[batch_start:batch_start + batch_size]
                    results = await asyncio.gather(*[
                        self._fetch_historical_prices(sym, days) for sym in batch
                    ], return_exceptions=True)

                    for sym, df in zip(batch, results):
                        if isinstance(df, Exception):
                            batch_failures.append(sym)
                        elif df is not None and "close" in df.columns:
                            prices = df["close"].dropna().tolist()
                            if len(prices) >= days * 0.5:
                                batch_successes[sym] = prices
                                continue
                        batch_failures.append(sym)

                    # Brief cooldown between batches to avoid rate limiting
                    if batch_start + batch_size < len(symbols):
                        await asyncio.sleep(1.0)

                failed_stocks = batch_failures
                prices_dict = batch_successes

            # 50 stocks × 5s max per stock / 5 per batch = ~50s + 9s cooldown ≈ 60s
            # Use 90s for safety margin — this is a one-time cost (cached for 2 min)
            total_timeout = 90
            try:
                await asyncio.wait_for(_fetch_batches(), timeout=total_timeout)
                logger.info(
                    "nselib fetched %d/%d stocks (%.0fs timeout)",
                    len(prices_dict), len(symbols), total_timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "nselib fetch timed out after %.0fs — falling back to synthetic data",
                    total_timeout,
                )
                failed_stocks = symbols  # fall back all to synthetic
                prices_dict = {}
        else:
            failed_stocks = [s["symbol"] for s in NIFTY_50_STOCKS]

        # Generate synthetic data for failed stocks
        for sym in failed_stocks:
            prices_dict[sym] = self._generate_synthetic_prices(sym, days)

        # Align all price series to the same length
        min_len = min(len(p) for p in prices_dict.values())
        result = {sym: p[-min_len:] for sym, p in prices_dict.items()}

        # Cache the result
        _PRICE_CACHE[days] = (time.time(), result)
        return result

    @staticmethod
    def compute_returns(prices: List[float]) -> np.ndarray:
        """Compute daily log returns from price series."""
        arr = np.array(prices, dtype=float)
        return np.diff(np.log(arr))

    async def compute_matrix(self, timeframe: int = 20) -> Dict[str, Any]:
        """Compute the full correlation matrix for all Nifty 50 stocks."""
        prices_dict = await self.fetch_all_prices(timeframe)

        symbols = [s["symbol"] for s in NIFTY_50_STOCKS]
        n = len(symbols)
        matrix = np.zeros((n, n))
        pairs = []

        returns_dict = {}
        for sym in symbols:
            p = prices_dict.get(sym, [])
            if len(p) < 2:
                returns_dict[sym] = np.array([0.0])
            else:
                returns_dict[sym] = self.compute_returns(p)

        # Compute pairwise correlations
        for i in range(n):
            for j in range(i, n):
                ri = returns_dict[symbols[i]]
                rj = returns_dict[symbols[j]]
                if len(ri) < 2 or len(rj) < 2:
                    corr = 0.0
                else:
                    corr = float(np.corrcoef(ri, rj)[0, 1])
                    # Handle NaN (occurs when one series has zero variance)
                    if np.isnan(corr):
                        corr = 0.0
                    corr = round(max(-1, min(1, corr)), 4)
                matrix[i][j] = corr
                matrix[j][i] = corr

                if i != j:
                    pairs.append({
                        "sym1": symbols[i],
                        "sym2": symbols[j],
                        "correlation": corr,
                        "abs_corr": abs(corr),
                    })

        # Sort pairs by absolute correlation descending
        pairs.sort(key=lambda x: x["abs_corr"], reverse=True)

        # Compute sector-level correlation (average correlation within sector)
        sector_corr = self._compute_sector_correlation(matrix, symbols)

        return {
            "symbols": symbols,
            "stocks": [{"symbol": s, "sector": next(
                st["sector"] for st in NIFTY_50_STOCKS if st["symbol"] == s
            )} for s in symbols],
            "sectors": self.get_sectors(),
            "matrix": matrix.tolist(),
            "pairs": pairs,
            "sector_correlation": sector_corr,
            "timeframe": timeframe,
            "timeframe_label": TIMEFRAME_LABELS.get(timeframe, f"{timeframe} Days"),
            "data_source": "nselib_live" if _HAS_NSELIB else "synthetic_fallback",
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _compute_sector_correlation(matrix: np.ndarray, symbols: List[str]) -> Dict[str, float]:
        """Average intra-sector correlation."""
        symbol_to_sector = {s["symbol"]: s["sector"] for s in NIFTY_50_STOCKS}
        sector_pairs = defaultdict(list)

        n = len(symbols)
        for i in range(n):
            for j in range(i + 1, n):
                sec_i = symbol_to_sector.get(symbols[i])
                sec_j = symbol_to_sector.get(symbols[j])
                if sec_i and sec_j and sec_i == sec_j:
                    sector_pairs[sec_i].append(matrix[i][j])

        result = {}
        for sector, corrs in sector_pairs.items():
            if corrs:
                result[sector] = round(float(np.mean(corrs)), 4)
        return result

    async def compute_pair_analytics(
        self, sym1: str, sym2: str, timeframe: int = 252
    ) -> Dict[str, Any]:
        """Detailed analysis for a specific pair - rolling correlation, spread, z-score, lead-lag."""
        prices_dict = await self.fetch_all_prices(timeframe)
        p1 = prices_dict.get(sym1, [])
        p2 = prices_dict.get(sym2, [])

        if len(p1) < 20 or len(p2) < 20:
            return {"error": f"Insufficient data for {sym1}/{sym2}"}

        min_len = min(len(p1), len(p2))
        p1 = p1[-min_len:]
        p2 = p2[-min_len:]

        arr1 = np.array(p1, dtype=float)
        arr2 = np.array(p2, dtype=float)
        ratio = arr1 / arr2

        # Overall correlation
        ret1 = self.compute_returns(p1)
        ret2 = self.compute_returns(p2)
        overall_corr = float(np.corrcoef(ret1, ret2)[0, 1])

        # Rolling correlation (60-day window)
        df = pd.DataFrame({"ret1": ret1, "ret2": ret2})
        roll_corr = df["ret1"].rolling(window=min(60, len(df) // 2)).corr(df["ret2"])
        roll_data = [
            {"date": (datetime.now(timezone.utc) - timedelta(days=len(roll_corr) - i)).strftime("%Y-%m-%d"),
             "correlation": round(float(v), 4) if not pd.isna(v) else None}
            for i, v in enumerate(roll_corr) if not pd.isna(v)
        ]

        # Spread analysis (price ratio)
        ratio_mean = float(np.mean(ratio))
        ratio_std = float(np.std(ratio))
        current_ratio = float(ratio[-1])
        z_score = (current_ratio - ratio_mean) / ratio_std if ratio_std > 0 else 0

        # Bollinger Bands on ratio
        ratio_series = pd.Series(ratio)
        bb_window = min(20, len(ratio) // 4)
        rolling_mean = ratio_series.rolling(window=bb_window).mean()
        rolling_std = ratio_series.rolling(window=bb_window).std()
        upper_band = rolling_mean + 2 * rolling_std
        lower_band = rolling_mean - 2 * rolling_std

        ratio_chart = []
        for i in range(len(ratio)):
            ratio_chart.append({
                "date": (datetime.now(timezone.utc) - timedelta(days=len(ratio) - i)).strftime("%Y-%m-%d"),
                "ratio": round(float(ratio[i]), 4),
                "upper_band": round(float(upper_band.iloc[i]), 4) if not pd.isna(upper_band.iloc[i]) else None,
                "lower_band": round(float(lower_band.iloc[i]), 4) if not pd.isna(lower_band.iloc[i]) else None,
                "mean": round(float(rolling_mean.iloc[i]), 4) if not pd.isna(rolling_mean.iloc[i]) else None,
            })

        # Lead-lag detection (cross-correlation)
        lead_lag = self._detect_lead_lag(ret1, ret2, sym1, sym2)

        # Correlation stability
        valid_corr = roll_corr.dropna()
        stability = float(valid_corr.std()) if len(valid_corr) > 0 else 0
        stability_score = max(0, min(100, round((1 - stability) * 100, 1)))

        # Signal detection
        signal = "NEUTRAL"
        signal_reasoning = []
        if abs(z_score) > 2:
            signal = "SHORT_SPREAD" if z_score > 2 else "LONG_SPREAD"
            signal_reasoning.append(
                f"Spread is {abs(z_score):.1f}σ from mean — {'overbought' if z_score > 2 else 'oversold'}"
            )
        elif abs(z_score) > 1.5:
            signal = "WATCH"
            signal_reasoning.append(f"Spread is {abs(z_score):.1f}σ from mean — approaching threshold")

        # Get sectors
        sym1_sector = next((s["sector"] for s in NIFTY_50_STOCKS if s["symbol"] == sym1), "Unknown")
        sym2_sector = next((s["sector"] for s in NIFTY_50_STOCKS if s["symbol"] == sym2), "Unknown")
        same_sector = sym1_sector == sym2_sector

        return {
            "sym1": sym1, "sym2": sym2,
            "sym1_sector": sym1_sector, "sym2_sector": sym2_sector,
            "same_sector": same_sector,
            "current_correlation": round(overall_corr, 4),
            "z_score": round(z_score, 2),
            "current_ratio": round(current_ratio, 4),
            "mean_ratio": round(ratio_mean, 4),
            "std_ratio": round(ratio_std, 4),
            "correlation_stability": stability_score,
            "signal": signal,
            "signal_reasoning": signal_reasoning,
            "rolling_correlation": roll_data,
            "price_ratio": ratio_chart,
            "lead_lag": lead_lag,
            "timeframe": timeframe,
            "num_observations": len(ratio),
            "timeframe_label": TIMEFRAME_LABELS.get(timeframe, f"{timeframe} Days"),
        }

    @staticmethod
    def _detect_lead_lag(
        ret1: np.ndarray, ret2: np.ndarray, sym1: str, sym2: str
    ) -> Dict[str, Any]:
        """Detect which stock leads using max cross-correlation at different lags."""
        max_lag = min(10, len(ret1) // 10)
        best_lag = 0
        best_cross_corr = -1

        for lag in range(-max_lag, max_lag + 1):
            if lag < 0:
                r1 = ret1[:lag]
                r2 = ret2[-lag:]
            elif lag > 0:
                r1 = ret1[lag:]
                r2 = ret2[:-lag]
            else:
                r1, r2 = ret1, ret2

            if len(r1) < 3:
                continue
            corr = float(np.corrcoef(r1, r2)[0, 1])
            if abs(corr) > abs(best_cross_corr):
                best_cross_corr = corr
                best_lag = lag

        if best_lag > 0:
            leader = sym1
            follower = sym2
        elif best_lag < 0:
            leader = sym2
            follower = sym1
        else:
            leader, follower = "Neither", "Neither"

        return {
            "leader": leader,
            "follower": follower if best_lag != 0 else "Neither",
            "lag_days": abs(best_lag),
            "cross_correlation": round(float(best_cross_corr), 4),
        }

    async def get_top_pairs(
        self, timeframe: int = 20, min_corr: float = 0.0,
        limit: int = 20, sector: str = "all"
    ) -> Dict[str, Any]:
        """Get top correlated pairs with metadata."""
        result = await self.compute_matrix(timeframe)
        pairs = result["pairs"]

        # Filter by sector
        if sector != "all":
            sector_stocks = {s["symbol"] for s in NIFTY_50_STOCKS if s["sector"] == sector}
            pairs = [
                p for p in pairs
                if p["sym1"] in sector_stocks or p["sym2"] in sector_stocks
            ]

        # Filter by min correlation
        pairs = [p for p in pairs if abs(p["correlation"]) >= min_corr]

        # Add sector info and stability (estimated)
        symbol_to_sector = {s["symbol"]: s["sector"] for s in NIFTY_50_STOCKS}
        for p in pairs[:limit]:
            p["sym1_sector"] = symbol_to_sector.get(p["sym1"])
            p["sym2_sector"] = symbol_to_sector.get(p["sym2"])
            p["same_sector"] = p["sym1_sector"] == p["sym2_sector"]

        return {
            "timeframe": timeframe,
            "timeframe_label": TIMEFRAME_LABELS.get(timeframe, f"{timeframe} Days"),
            "total_pairs": len(pairs),
            "pairs": pairs[:limit],
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }


# Singleton
correlation_service = CorrelationService()


def get_correlation_service() -> CorrelationService:
    return correlation_service
