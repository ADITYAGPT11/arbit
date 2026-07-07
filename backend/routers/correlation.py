"""Correlation Analysis Routes — Nifty 50 stock correlation endpoints."""

import logging
from fastapi import APIRouter, Query, Body

from services.correlation_service import correlation_service
from services.correlation_signal_service import correlation_signal_service, BacktestParams

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/correlation", tags=["Correlation Analysis"])


@router.get("/stocks")
async def get_stocks():
    """Get Nifty 50 stock list with sector mapping."""
    stocks = correlation_service.get_stocks()
    sectors = correlation_service.get_sectors()
    return {"stocks": stocks, "sectors": sectors}


@router.get("/matrix")
async def get_correlation_matrix(
    timeframe: int = Query(20, description="Lookback period in trading days", ge=5, le=756),
):
    """Compute the full Nifty 50 correlation matrix for the given timeframe."""
    result = await correlation_service.compute_matrix(timeframe)
    return result


@router.get("/pairs")
async def get_top_pairs(
    timeframe: int = Query(20, description="Lookback period", ge=5, le=756),
    min_corr: float = Query(0.0, description="Minimum absolute correlation filter", ge=0, le=1),
    limit: int = Query(20, description="Max pairs to return", ge=1, le=200),
    sector: str = Query("all", description="Filter by sector (use 'all' for no filter)"),
):
    """Get top correlated pairs across Nifty 50 stocks."""
    result = await correlation_service.get_top_pairs(timeframe, min_corr, limit, sector)
    return result


@router.get("/pair/{sym1}/{sym2}")
async def get_pair_analytics(
    sym1: str,
    sym2: str,
    timeframe: int = Query(252, description="Lookback period in trading days", ge=20, le=756),
):
    """Get detailed pair analysis: rolling correlation, spread, z-score, lead-lag."""
    sym1 = sym1.upper()
    sym2 = sym2.upper()
    result = await correlation_service.compute_pair_analytics(sym1, sym2, timeframe)
    return result


@router.get("/sectors")
async def get_sector_correlation(
    timeframe: int = Query(60, description="Lookback period", ge=5, le=756),
):
    """Get average intra-sector correlation for each sector."""
    result = await correlation_service.compute_matrix(timeframe)
    return {
        "sector_correlation": result["sector_correlation"],
        "timeframe": timeframe,
        "timeframe_label": result["timeframe_label"],
    }


# ── Pair Rankings & Optimal Parameters ──


@router.get("/pair-rankings")
async def get_pair_rankings(
    max_days: int = Query(252, description="Max lookback period", ge=60, le=756),
    include_all: bool = Query(False, description="Return ALL pairs (default: only best N)"),
    top_n: int = Query(0, description="Number of most liquid stocks to analyze (0 = all 50)", ge=0, le=50),
    limit: int = Query(50, description="Max top-ranked pairs to return", ge=10, le=200),
):
    """Comprehensive pair rankings for Nifty 50 stocks.

    Architecture:
    - Backend pre-computes ALL C(50,2) = 1,225 pairs in async batches (~30s)
    - Results are cached for 30 minutes — subsequent requests are instant
    - Only the top `limit` best-tradable pairs are returned to the frontend

    Returns:
        best_10: Top 10 pairs by composite score (with auto-backtest data)
        worst_10: Bottom 10 pairs (negative correlation, for hedging)
        best_pairs: Top `limit` pairs sorted by score (for the Correlation List view)
        total_pairs: Total number of pairs computed

    Set include_all=true to get ALL pairs (for data export / debugging).
    """
    result = await correlation_signal_service.compute_pair_rankings(
        max_days=max_days, include_all=include_all, top_n=top_n, limit=limit
    )
    return result


@router.get("/optimal-params")
async def get_optimal_params(
    max_days: int = Query(252, description="Max lookback period", ge=60, le=756),
    top_n: int = Query(10, description="Number of most liquid stocks to analyze", ge=0, le=50),
):
    """Find optimal strategy parameters via grid search on top-ranked pairs.

    Tests different values for entry_z, exit_z, stop_z, rolling_window,
    and use_hedge_ratio. Returns the best combination found.
    """
    result = await correlation_signal_service.find_optimal_params(max_days=max_days, top_n=top_n)
    return result


# ── Pairs Trading Signals & Backtesting ──


@router.get("/signals")
async def get_signals(
    min_z: float = Query(1.5, description="Minimum |z-score| to trigger a signal", ge=0.5, le=5.0),
    timeframe: int = Query(60, description="Lookback period for signal calculation", ge=20, le=756),
    limit: int = Query(20, description="Max signals to return", ge=1, le=50),
    require_cointegrated: bool = Query(False, description="Only show signals for cointegrated pairs"),
):
    """Scan all pairs and return active trading signals based on z-score extremes."""
    result = await correlation_signal_service.generate_signals(
        min_z=min_z, timeframe=timeframe, limit=limit,
        require_cointegrated=require_cointegrated,
    )
    return result


@router.post("/backtest")
async def run_backtest(
    sym1: str = Body(..., description="First stock symbol"),
    sym2: str = Body(..., description="Second stock symbol"),
    days: int = Body(252, description="Lookback period in trading days"),
    entry_z: float = Body(2.0, description="Z-score entry threshold"),
    exit_z: float = Body(0.0, description="Z-score exit threshold"),
    stop_z: float = Body(3.0, description="Z-score stop-loss threshold"),
    rolling_window: int = Body(20, description="Rolling window for z-score"),
    use_log_ratio: bool = Body(False, description="Use log ratio instead of raw ratio"),
    # New strategy improvements
    use_hedge_ratio: bool = Body(True, description="Use rolling OLS hedge ratio for stationary spread"),
    beta_window: int = Body(60, description="Rolling window for OLS beta estimation"),
    require_cointegrated: bool = Body(True, description="Skip pair if not cointegrated (Engle-Granger test)"),
    coint_pvalue: float = Body(0.05, description="Cointegration significance threshold"),
    transaction_cost_pct: float = Body(0.05, description="Per-side transaction cost in %% (brokerage + STT + slippage)"),
):
    """Run a historical backtest on a pair using the mean-reversion strategy.

    Improvements over v1:
    - Cointegration filter (Engle-Granger) — only trades if pair is truly mean-reverting
    - Dynamic hedge ratio (rolling OLS β) — creates a stationary spread instead of raw ratio
    - Transaction cost model — per-side cost for realistic P&L
    """
    sym1 = sym1.upper()
    sym2 = sym2.upper()
    params = BacktestParams(
        entry_z=entry_z,
        exit_z=exit_z,
        stop_z=stop_z,
        rolling_window=rolling_window,
        use_log_ratio=use_log_ratio,
        use_hedge_ratio=use_hedge_ratio,
        beta_window=beta_window,
        require_cointegrated=require_cointegrated,
        coint_pvalue=coint_pvalue,
        transaction_cost_pct=transaction_cost_pct,
    )
    result = await correlation_signal_service.backtest_pair(
        sym1, sym2, days=days, params=params
    )
    return result
