"""
IV Analytics Service — Options Seller's Toolkit
- Black-Scholes IV calculation (Newton-Raphson + Brent fallback)
- IV Rank, IV Percentile from historical snapshots
- Historical Volatility (HV) from price returns
- IV Skew across strikes
- Max Pain from OI data
- India VIX integration
- Daily IV snapshot storage in MongoDB
"""

import logging
import math
import numpy as np
from scipy.stats import norm
from scipy.optimize import newton, brentq
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Risk-free rate for India (RBI repo rate approx)
RISK_FREE_RATE = 0.065  # 6.5%

# India VIX token for Angel One
INDIA_VIX_TOKEN = "99926017"
INDIA_VIX_EXCHANGE = "NSE"


# ==================== BLACK-SCHOLES MODEL ====================

def bs_price(S: float, K: float, T: float, sigma: float,
             r: float = RISK_FREE_RATE, option_type: str = "call") -> float:
    """Black-Scholes European option price.
    S: spot, K: strike, T: time to expiry (years), sigma: volatility (decimal),
    r: risk-free rate (decimal), option_type: 'call' or 'put'
    """
    if T <= 0:
        return max(S - K, 0.0) if option_type == "call" else max(K - S, 0.0)
    if sigma <= 0:
        df = math.exp(-r * T)
        return max(S - K * df, 0.0) if option_type == "call" else max(K * df - S, 0.0)

    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T

    if option_type == "call":
        return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    else:
        return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def bs_vega(S: float, K: float, T: float, sigma: float,
            r: float = RISK_FREE_RATE) -> float:
    """Black-Scholes vega: dPrice/dSigma"""
    if T <= 0 or sigma <= 0:
        return 0.0
    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * sqrt_T)
    return S * norm.pdf(d1) * sqrt_T


def calculate_iv(market_price: float, S: float, K: float, T: float,
                 option_type: str = "call", r: float = RISK_FREE_RATE) -> Optional[float]:
    """Calculate implied volatility using Newton-Raphson with Brent fallback.
    Returns IV as decimal (e.g. 0.20 = 20%) or None if unsolvable.
    """
    if market_price <= 0 or S <= 0 or K <= 0 or T <= 0:
        return None

    # Sanity: price must exceed intrinsic
    intrinsic = max(S - K, 0.0) if option_type == "call" else max(K - S, 0.0)
    if market_price < intrinsic * 0.95:  # Allow small tolerance
        return None

    # Upper bound: price can't exceed spot (call) or strike (put)
    upper_bound = S if option_type == "call" else K * math.exp(-r * T)
    if market_price > upper_bound * 1.05:
        return None

    def objective(sig):
        return bs_price(S, K, T, sig, r, option_type) - market_price

    def vega_fn(sig):
        return bs_vega(S, K, T, sig, r)

    # Newton-Raphson (fast path)
    try:
        iv = newton(func=objective, x0=0.25, fprime=vega_fn, tol=1e-8, maxiter=100)
        if 0.001 < iv < 5.0:
            return round(iv, 6)
    except Exception:
        pass

    # Brent method (robust fallback)
    try:
        lo, hi = 0.001, 5.0
        f_lo, f_hi = objective(lo), objective(hi)
        if f_lo * f_hi > 0:
            return None
        iv = brentq(objective, lo, hi, xtol=1e-8, maxiter=200)
        if 0.001 < iv < 5.0:
            return round(iv, 6)
    except Exception:
        pass

    return None


# ==================== IV ANALYTICS ====================

def calculate_historical_volatility(prices: List[float], window: int = 20) -> Optional[float]:
    """Calculate annualized historical volatility from daily close prices.
    Uses log returns with annualization factor sqrt(252).
    """
    if len(prices) < window + 1:
        return None
    prices = np.array(prices[-(window + 1):])
    log_returns = np.log(prices[1:] / prices[:-1])
    hv = np.std(log_returns) * math.sqrt(252)
    return round(float(hv), 6)


def calculate_iv_rank(current_iv: float, iv_history: List[float]) -> Optional[float]:
    """IV Rank = (Current IV - 52w Low) / (52w High - 52w Low) × 100
    Range: 0-100. High rank = IV is expensive relative to its range.
    """
    if not iv_history or len(iv_history) < 5:
        return None
    iv_low = min(iv_history)
    iv_high = max(iv_history)
    if iv_high == iv_low:
        return 50.0
    rank = ((current_iv - iv_low) / (iv_high - iv_low)) * 100
    return round(max(0, min(100, rank)), 1)


def calculate_iv_percentile(current_iv: float, iv_history: List[float]) -> Optional[float]:
    """IV Percentile = % of days where IV was BELOW current IV.
    Range: 0-100. High percentile = current IV is higher than most historical readings.
    """
    if not iv_history or len(iv_history) < 5:
        return None
    below = sum(1 for iv in iv_history if iv < current_iv)
    percentile = (below / len(iv_history)) * 100
    return round(percentile, 1)


def calculate_max_pain(chain: List[Dict]) -> Optional[Dict[str, Any]]:
    """Calculate Max Pain strike — where total option buyer losses are maximized.
    Options sellers profit most when expiry settles at max pain.
    """
    if not chain:
        return None

    strikes = []
    for row in chain:
        strike = row.get("strike", 0)
        ce_oi = row.get("ce", {}).get("oi", 0) if row.get("ce") else 0
        pe_oi = row.get("pe", {}).get("oi", 0) if row.get("pe") else 0
        if strike > 0:
            strikes.append({"strike": strike, "ce_oi": ce_oi, "pe_oi": pe_oi})

    if not strikes:
        return None

    # For each possible expiry price, calculate total pain (loss to buyers)
    min_pain = float("inf")
    max_pain_strike = strikes[0]["strike"]
    pain_at_strikes = []

    for test_strike in strikes:
        test_price = test_strike["strike"]
        total_pain = 0

        for s in strikes:
            # CE buyer pain: if test_price < strike, CE expires worthless → buyer loses full premium (proportional to OI)
            # If test_price > strike, CE has intrinsic but less than what was paid
            # Simplified: pain = OI × max(0, strike - test_price) for puts, max(0, test_price - strike) for calls
            # Actually: pain to CE buyers = CE_OI × max(strike - test_price, 0) [they lose when price below strike]
            # Wait, that's wrong. Let me recalculate.
            # CE buyer profit = max(test_price - strike, 0). CE buyer pain = -profit (when it's negative).
            # But we want total pain = sum of (intrinsic payoff × OI) for all options.
            # Max pain = strike where sum of all option intrinsic values is MINIMUM.

            ce_intrinsic = max(test_price - s["strike"], 0) * s["ce_oi"]
            pe_intrinsic = max(s["strike"] - test_price, 0) * s["pe_oi"]
            total_pain += ce_intrinsic + pe_intrinsic

        pain_at_strikes.append({"strike": test_price, "total_pain": total_pain})

        if total_pain < min_pain:
            min_pain = total_pain
            max_pain_strike = test_price

    return {
        "max_pain_strike": max_pain_strike,
        "total_pain_at_max_pain": round(min_pain, 0),
        "pain_distribution": pain_at_strikes,
    }


def build_iv_skew(chain: List[Dict], spot_price: float, expiry_days: int) -> List[Dict[str, Any]]:
    """Build IV skew data from option chain — calculates IV for each strike using B-S model."""
    if not chain or spot_price <= 0 or expiry_days <= 0:
        return []

    T = expiry_days / 365.0
    skew = []

    for row in chain:
        strike = row.get("strike", 0)
        if strike <= 0:
            continue

        entry = {
            "strike": strike,
            "moneyness": round((strike / spot_price - 1) * 100, 2),  # % from spot
            "ce_iv": None,
            "pe_iv": None,
            "ce_ltp": 0,
            "pe_ltp": 0,
        }

        # Calculate CE IV
        if row.get("ce") and row["ce"].get("ltp", 0) > 0:
            entry["ce_ltp"] = row["ce"]["ltp"]
            # Use Angel One's IV if available and non-zero
            if row["ce"].get("iv", 0) > 0:
                entry["ce_iv"] = round(row["ce"]["iv"], 2)
            else:
                iv = calculate_iv(row["ce"]["ltp"], spot_price, strike, T, "call")
                if iv is not None:
                    entry["ce_iv"] = round(iv * 100, 2)  # Convert to percentage

        # Calculate PE IV
        if row.get("pe") and row["pe"].get("ltp", 0) > 0:
            entry["pe_ltp"] = row["pe"]["ltp"]
            if row["pe"].get("iv", 0) > 0:
                entry["pe_iv"] = round(row["pe"]["iv"], 2)
            else:
                iv = calculate_iv(row["pe"]["ltp"], spot_price, strike, T, "put")
                if iv is not None:
                    entry["pe_iv"] = round(iv * 100, 2)

        skew.append(entry)

    return skew


def get_atm_iv(chain: List[Dict], spot_price: float, expiry_days: int) -> Optional[float]:
    """Get ATM implied volatility (average of ATM CE and PE IV)."""
    skew = build_iv_skew(chain, spot_price, expiry_days)
    if not skew:
        return None

    # Find closest to ATM
    atm_entry = min(skew, key=lambda x: abs(x["moneyness"]))
    ivs = [v for v in [atm_entry.get("ce_iv"), atm_entry.get("pe_iv")] if v is not None and v > 0]
    if ivs:
        return round(sum(ivs) / len(ivs), 2)
    return None


def detect_iv_signal(iv_rank: Optional[float], iv_percentile: Optional[float],
                     current_iv: Optional[float], hv: Optional[float]) -> Dict[str, Any]:
    """Detect IV expansion/crush signals for options sellers."""
    signal = "NEUTRAL"
    strength = 0
    reasoning = []

    if iv_rank is not None:
        if iv_rank >= 80:
            signal = "SELL_PREMIUM"
            strength += 3
            reasoning.append(f"IV Rank {iv_rank}% — IV is near 52-week highs, premiums are rich")
        elif iv_rank >= 60:
            strength += 1
            reasoning.append(f"IV Rank {iv_rank}% — IV is above average")
        elif iv_rank <= 20:
            signal = "AVOID_SELLING"
            strength -= 2
            reasoning.append(f"IV Rank {iv_rank}% — IV is near lows, premiums are cheap")

    if iv_percentile is not None:
        if iv_percentile >= 80:
            if signal != "SELL_PREMIUM":
                signal = "SELL_PREMIUM"
            strength += 2
            reasoning.append(f"IV Percentile {iv_percentile}% — Higher than {iv_percentile}% of observations")
        elif iv_percentile <= 20:
            if signal == "NEUTRAL":
                signal = "AVOID_SELLING"
            strength -= 1
            reasoning.append(f"IV Percentile {iv_percentile}% — Lower than most historical readings")

    if current_iv is not None and hv is not None and hv > 0:
        iv_hv_ratio = current_iv / hv
        if iv_hv_ratio > 1.3:
            if signal != "SELL_PREMIUM":
                signal = "SELL_PREMIUM"
            strength += 2
            reasoning.append(f"IV/HV ratio {iv_hv_ratio:.2f} — Options overpriced vs realized vol")
        elif iv_hv_ratio < 0.8:
            if signal == "NEUTRAL":
                signal = "AVOID_SELLING"
            strength -= 1
            reasoning.append(f"IV/HV ratio {iv_hv_ratio:.2f} — Options underpriced vs realized vol")

    return {
        "signal": signal,
        "strength": max(-5, min(5, strength)),
        "reasoning": reasoning,
    }
