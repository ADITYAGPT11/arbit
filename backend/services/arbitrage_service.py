"""Arbitrage Engine — detects cross-exchange, cash-carry, synthetic, calendar, and stat-arb opportunities."""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

import numpy as np
from scipy import stats

from .market_data_service import MarketDataService

logger = logging.getLogger(__name__)

ANGEL_ONE_AVAILABLE: bool = False
get_angel_service_callable = None


def setup_arbitrage_service(
    angel_available: bool,
    get_angel_service_fn,
):
    global ANGEL_ONE_AVAILABLE, get_angel_service_callable
    ANGEL_ONE_AVAILABLE = angel_available
    get_angel_service_callable = get_angel_service_fn


class ArbitrageEngine:
    """Engine to detect various arbitrage opportunities."""

    # Transaction costs for Indian markets
    BROKERAGE_PCT = 0.03   # 0.03%
    STT_DELIVERY = 0.1     # 0.1% on delivery
    STT_INTRADAY = 0.025   # 0.025% on intraday
    STAMP_DUTY = 0.015     # 0.015%
    GST = 18               # 18% on brokerage
    SEBI_CHARGES = 0.0001  # 0.0001%

    @staticmethod
    def calculate_transaction_cost(value: float, is_delivery: bool = True) -> float:
        """Calculate total transaction cost."""
        brokerage = value * ArbitrageEngine.BROKERAGE_PCT / 100
        stt = value * (ArbitrageEngine.STT_DELIVERY if is_delivery else ArbitrageEngine.STT_INTRADAY) / 100
        stamp = value * ArbitrageEngine.STAMP_DUTY / 100
        gst = brokerage * ArbitrageEngine.GST / 100
        sebi = value * ArbitrageEngine.SEBI_CHARGES / 100
        return brokerage + stt + stamp + gst + sebi

    @staticmethod
    async def detect_cross_exchange_arbitrage(symbols: List[str]) -> List[Dict[str, Any]]:
        """Detect NSE vs BSE price differences using batch API for speed."""
        opportunities = []

        # Use batch fetching for speed
        if ANGEL_ONE_AVAILABLE and MarketDataService._use_live_data:
            try:
                angel = get_angel_service_callable() if get_angel_service_callable else None
                if angel and angel.is_connected():
                    nse_stocks = angel.get_multiple_stocks_batch(symbols, "NSE")
                    bse_stocks = angel.get_multiple_stocks_batch(symbols, "BSE")

                    nse_prices = {s['symbol']: s['price'] for s in nse_stocks if s.get('price')}
                    bse_prices = {s['symbol']: s['price'] for s in bse_stocks if s.get('price')}

                    for symbol in symbols:
                        nse_price = nse_prices.get(symbol, 0)
                        bse_price = bse_prices.get(symbol, 0)

                        if nse_price > 0 and bse_price > 0:
                            spread = abs(nse_price - bse_price)
                            spread_pct = (spread / min(nse_price, bse_price)) * 100

                            buy_exchange = "BSE" if bse_price < nse_price else "NSE"
                            buy_price = min(nse_price, bse_price)
                            sell_price = max(nse_price, bse_price)

                            buy_cost = ArbitrageEngine.calculate_transaction_cost(buy_price, False)
                            sell_cost = ArbitrageEngine.calculate_transaction_cost(sell_price, False)
                            total_txn_cost = buy_cost + sell_cost

                            slippage_pct = 0.02
                            slippage = (buy_price + sell_price) * slippage_pct / 100

                            net_profit = spread - total_txn_cost - slippage
                            net_profit_pct = (net_profit / buy_price) * 100

                            if spread_pct > 0.01:
                                opportunities.append({
                                    "type": "cross_exchange", "symbol": symbol,
                                    "nse_price": round(nse_price, 2), "bse_price": round(bse_price, 2),
                                    "spread": round(spread, 2), "spread_pct": round(spread_pct, 4),
                                    "buy_exchange": buy_exchange,
                                    "sell_exchange": "NSE" if buy_exchange == "BSE" else "BSE",
                                    "buy_price": round(buy_price, 2), "sell_price": round(sell_price, 2),
                                    "txn_cost": round(total_txn_cost, 2),
                                    "slippage": round(slippage, 2), "slippage_pct": slippage_pct,
                                    "net_profit_per_share": round(net_profit, 2),
                                    "net_profit_pct": round(net_profit_pct, 4),
                                    "is_profitable": net_profit > 0,
                                    "data_source": "angel_one_live",
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                })

                    return sorted(opportunities, key=lambda x: x["spread_pct"], reverse=True)
            except Exception as e:
                logger.error(f"Batch arbitrage detection error: {e}")

        # Fallback to individual fetching (slower)
        for symbol in symbols:
            nse_data = await MarketDataService.get_stock_price(symbol, "NSE")
            bse_data = await MarketDataService.get_stock_price(symbol, "BSE")

            nse_price = nse_data.get("price") if nse_data else 0
            bse_price = bse_data.get("price") if bse_data else 0

            if nse_price and nse_price > 0 and bse_price and bse_price > 0:
                spread = abs(nse_price - bse_price)
                spread_pct = (spread / min(nse_price, bse_price)) * 100

                buy_exchange = "BSE" if bse_price < nse_price else "NSE"
                buy_price = min(nse_price, bse_price)
                sell_price = max(nse_price, bse_price)

                buy_cost = ArbitrageEngine.calculate_transaction_cost(buy_price, False)
                sell_cost = ArbitrageEngine.calculate_transaction_cost(sell_price, False)
                net_profit = spread - buy_cost - sell_cost
                net_profit_pct = (net_profit / buy_price) * 100

                if spread_pct > 0.1:
                    opportunities.append({
                        "type": "cross_exchange", "symbol": symbol,
                        "nse_price": round(nse_price, 2), "bse_price": round(bse_price, 2),
                        "spread": round(spread, 2), "spread_pct": round(spread_pct, 3),
                        "buy_exchange": buy_exchange,
                        "sell_exchange": "NSE" if buy_exchange == "BSE" else "BSE",
                        "net_profit_per_share": round(net_profit, 2),
                        "net_profit_pct": round(net_profit_pct, 3),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

        return sorted(opportunities, key=lambda x: x["spread_pct"], reverse=True)

    @staticmethod
    def calculate_cash_carry_arbitrage(
        spot_price: float, futures_price: float,
        days_to_expiry: int, risk_free_rate: float = 7.0,
    ) -> Dict[str, Any]:
        """Calculate cash and carry arbitrage opportunity."""
        if spot_price <= 0 or futures_price <= 0 or days_to_expiry <= 0:
            return {"error": "Invalid input"}

        fair_value = spot_price * (1 + (risk_free_rate / 100) * (days_to_expiry / 365))
        basis = futures_price - spot_price
        basis_pct = (basis / spot_price) * 100
        annualized_basis = (basis_pct / days_to_expiry) * 365
        mispricing = futures_price - fair_value
        mispricing_pct = (mispricing / fair_value) * 100

        total_cost = ArbitrageEngine.calculate_transaction_cost(spot_price, True) + \
                     ArbitrageEngine.calculate_transaction_cost(futures_price, False)

        net_profit = basis - total_cost
        net_profit_pct = (net_profit / spot_price) * 100
        annualized_return = (net_profit_pct / days_to_expiry) * 365

        return {
            "spot_price": round(spot_price, 2), "futures_price": round(futures_price, 2),
            "fair_value": round(fair_value, 2), "basis": round(basis, 2),
            "basis_pct": round(basis_pct, 3), "annualized_basis": round(annualized_basis, 2),
            "mispricing": round(mispricing, 2), "mispricing_pct": round(mispricing_pct, 3),
            "days_to_expiry": days_to_expiry, "transaction_cost": round(total_cost, 2),
            "net_profit": round(net_profit, 2), "net_profit_pct": round(net_profit_pct, 3),
            "annualized_return": round(annualized_return, 2), "is_profitable": net_profit > 0,
            "strategy": "Buy Spot + Sell Futures" if futures_price > fair_value else "Sell Spot + Buy Futures",
        }

    @staticmethod
    def calculate_synthetic_futures_arbitrage(
        spot_price: float, call_price: float, put_price: float,
        strike: float, futures_price: float,
    ) -> Dict[str, Any]:
        """Calculate synthetic futures vs actual futures arbitrage."""
        synthetic_future = call_price - put_price + strike
        mispricing = futures_price - synthetic_future
        mispricing_pct = (mispricing / synthetic_future) * 100 if synthetic_future > 0 else 0
        total_cost = ArbitrageEngine.calculate_transaction_cost(call_price + put_price + futures_price, False)
        net_profit = abs(mispricing) - total_cost

        return {
            "spot_price": round(spot_price, 2), "call_price": round(call_price, 2),
            "put_price": round(put_price, 2), "strike": round(strike, 2),
            "synthetic_future": round(synthetic_future, 2),
            "actual_future": round(futures_price, 2),
            "mispricing": round(mispricing, 2), "mispricing_pct": round(mispricing_pct, 3),
            "transaction_cost": round(total_cost, 2), "net_profit": round(net_profit, 2),
            "is_profitable": net_profit > 0,
            "strategy": "Buy Synthetic + Sell Futures" if futures_price > synthetic_future else "Sell Synthetic + Buy Futures",
        }

    @staticmethod
    def calculate_calendar_spread(
        near_futures: float, far_futures: float,
        near_expiry_days: int, far_expiry_days: int,
    ) -> Dict[str, Any]:
        """Calculate calendar spread arbitrage."""
        spread = far_futures - near_futures
        spread_pct = (spread / near_futures) * 100 if near_futures > 0 else 0
        days_diff = far_expiry_days - near_expiry_days
        annualized_spread = (spread_pct / days_diff) * 365 if days_diff > 0 else 0

        return {
            "near_futures": round(near_futures, 2), "far_futures": round(far_futures, 2),
            "spread": round(spread, 2), "spread_pct": round(spread_pct, 3),
            "near_expiry_days": near_expiry_days, "far_expiry_days": far_expiry_days,
            "annualized_spread": round(annualized_spread, 2),
            "strategy": "Buy Near + Sell Far" if spread > 0 else "Sell Near + Buy Far",
        }

    @staticmethod
    def calculate_statistical_arbitrage(
        prices1: List[float], prices2: List[float], lookback: int = 20,
    ) -> Dict[str, Any]:
        """Calculate statistical arbitrage (pairs trading) signals."""
        if len(prices1) < lookback or len(prices2) < lookback:
            return {"error": "Insufficient data"}

        prices1 = np.array(prices1[-lookback:])
        prices2 = np.array(prices2[-lookback:])

        ratio = prices1 / prices2
        mean_ratio = np.mean(ratio)
        std_ratio = np.std(ratio)
        current_ratio = ratio[-1]
        z_score = (current_ratio - mean_ratio) / std_ratio if std_ratio > 0 else 0

        correlation = np.corrcoef(prices1, prices2)[0, 1]

        spread = prices1 - prices2 * mean_ratio
        spread_lag = np.roll(spread, 1)[1:]
        spread_diff = np.diff(spread)

        try:
            slope, _, _, _, _ = stats.linregress(spread_lag, spread_diff)
            half_life = -np.log(2) / slope if slope < 0 else float('inf')
        except Exception:
            half_life = float('inf')

        signal = "NEUTRAL"
        if z_score > 2:
            signal = "SHORT_SPREAD"
        elif z_score < -2:
            signal = "LONG_SPREAD"
        elif abs(z_score) < 0.5:
            signal = "EXIT"

        return {
            "current_ratio": round(current_ratio, 4), "mean_ratio": round(mean_ratio, 4),
            "z_score": round(z_score, 2), "correlation": round(correlation, 3),
            "half_life": round(half_life, 1) if half_life != float('inf') else "N/A",
            "signal": signal, "lookback": lookback,
        }
