"""Correlation Analysis Routes — Nifty 50 stock correlation endpoints."""

import logging
from fastapi import APIRouter, Query

from services.correlation_service import correlation_service

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
