"""Shared fixtures for correlation module tests.

Provides:
- Synthetic price series with known statistical properties
- Mocked nselib for network-dependent tests
- Pre-built return arrays for PVR/metric tests
"""
from typing import Dict, List, Tuple

import numpy as np
import pytest


# ── Helpers ──

def make_synthetic_prices(
    n_days: int = 300,
    base_price: float = 1000.0,
    daily_vol: float = 0.015,
    drift: float = 0.0005,
    seed: int = 42,
) -> List[float]:
    """Generate a realistic price series with known properties.

    Uses Geometric Brownian Motion: P(t) = P(0) * exp(Σ(μ - ½σ² + σ·ε))
    """
    rng = np.random.default_rng(seed)
    log_returns = rng.normal(drift - 0.5 * daily_vol ** 2, daily_vol, n_days)
    prices = base_price * np.exp(np.cumsum(log_returns))
    return [round(float(p), 2) for p in prices]


def make_correlated_prices(
    n_days: int = 300,
    base_price1: float = 1700.0,
    base_price2: float = 1300.0,
    correlation: float = 0.85,
    seed: int = 42,
) -> Tuple[List[float], List[float]]:
    """Generate two price series with a target correlation.

    Uses Cholesky decomposition to create correlated random walks.
    """
    rng = np.random.default_rng(seed)
    cov = np.array([[1.0, correlation], [correlation, 1.0]])
    L = np.linalg.cholesky(cov)

    n = n_days
    vol1, vol2 = 0.015, 0.018
    drift1, drift2 = 0.0005, 0.0004

    uncorr = rng.normal(0, 1, (n, 2))
    corr_normal = uncorr @ L.T

    returns1 = drift1 + vol1 * corr_normal[:, 0]
    returns2 = drift2 + vol2 * corr_normal[:, 1]

    prices1 = base_price1 * np.exp(np.cumsum(returns1))
    prices2 = base_price2 * np.exp(np.cumsum(returns2))
    return [round(float(p), 2) for p in prices1], [round(float(p), 2) for p in prices2]


def make_cointegrated_pair(
    n_days: int = 300,
    seed: int = 42,
) -> Tuple[List[float], List[float]]:
    """Generate a truly cointegrated pair.

    A = random walk, B = A + stationary AR(1) noise.
    The spread A - B should be stationary → cointegrated.
    """
    rng = np.random.default_rng(seed)
    # Random walk for A
    a_returns = rng.normal(0.0005, 0.015, n_days)
    a = 1000.0 * np.exp(np.cumsum(a_returns))

    # Stationary gap: AR(1) with φ=0.8 → mean-reverting
    phi = 0.8
    gap = np.zeros(n_days)
    for i in range(1, n_days):
        gap[i] = phi * gap[i - 1] + rng.normal(0, 2.0)

    b = a + gap + 500  # add offset so prices aren't identical
    return [round(float(p), 2) for p in a], [round(float(p), 2) for p in b]


def make_independent_prices(
    n_days: int = 300,
    seed: int = 42,
) -> Tuple[List[float], List[float]]:
    """Generate two completely independent price series (correlation ≈ 0)."""
    rng = np.random.default_rng(seed)
    p1 = 1000.0 * np.exp(np.cumsum(rng.normal(0.0003, 0.015, n_days)))
    p2 = 800.0 * np.exp(np.cumsum(rng.normal(0.0002, 0.020, n_days)))
    return [round(float(p), 2) for p in p1], [round(float(p), 2) for p in p2]


# ── Fixtures ──


@pytest.fixture
def price_series_300() -> List[float]:
    """300-day synthetic price series (RELIANCE-like)."""
    return make_synthetic_prices(300, 2800.0, seed=1)


@pytest.fixture
def price_series_200() -> List[float]:
    """200-day synthetic price series (TCS-like)."""
    return make_synthetic_prices(200, 3900.0, seed=2)


@pytest.fixture
def correlated_pair() -> Tuple[List[float], List[float]]:
    """Two price series with ~0.85 correlation (HDFCBANK-ICICIBANK like)."""
    return make_correlated_prices(300, 1700.0, 1300.0, 0.85, seed=10)


@pytest.fixture
def cointegrated_pair() -> Tuple[List[float], List[float]]:
    """A truly cointegrated pair for backtest testing."""
    return make_cointegrated_pair(300, seed=20)


@pytest.fixture
def independent_pair() -> Tuple[List[float], List[float]]:
    """Two independent price series (correlation ≈ 0)."""
    return make_independent_prices(300, seed=30)


@pytest.fixture
def price_dict_5stocks() -> Dict[str, List[float]]:
    """Prices dict with 5 stocks for matrix/ranking tests."""
    symbols = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"]
    prices = {}
    for i, sym in enumerate(symbols):
        prices[sym] = make_synthetic_prices(300, 1000.0 + i * 500, seed=i)
    return prices


@pytest.fixture
def short_prices() -> List[float]:
    """Short price series (< 30 days) — triggers edge cases."""
    return [round(100.0 + i * 0.5 + float(np.random.default_rng(99).normal(0, 1)), 2)
            for i in range(20)]


@pytest.fixture
def constant_prices() -> List[float]:
    """Constant price series (zero variance edge case)."""
    return [1000.0] * 100



