"""Market Data Service — fetches real-time data from Angel One with fallback."""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# These flags are set at import time by server.py or core/deps.py via try/except imports.
# They are populated by server.py on startup.
ANGEL_ONE_AVAILABLE: bool = False
get_angel_service_callable = None
SYMBOL_TOKENS: dict = {}
INDEX_TOKENS: dict = {}


def setup_market_data_service(
    angel_available: bool,
    get_angel_service_fn,
    symbol_tokens: dict,
    index_tokens: dict,
):
    """Called by server.py at startup to inject external service references."""
    global ANGEL_ONE_AVAILABLE, get_angel_service_callable, SYMBOL_TOKENS, INDEX_TOKENS
    ANGEL_ONE_AVAILABLE = angel_available
    get_angel_service_callable = get_angel_service_fn
    SYMBOL_TOKENS = symbol_tokens or {}
    INDEX_TOKENS = index_tokens or {}


class MarketDataService:
    """Service to fetch real-time market data from Angel One SmartAPI with fallback to simulated data."""

    # Fallback base prices for Indian stocks (used when API fails)
    STOCK_BASE_PRICES = {
        "RELIANCE": 2850, "TCS": 3950, "HDFCBANK": 1720, "INFY": 1820, "ICICIBANK": 1280,
        "HINDUNILVR": 2450, "ITC": 485, "SBIN": 825, "BHARTIARTL": 1650, "KOTAKBANK": 1890,
        "LT": 3650, "AXISBANK": 1180, "ASIANPAINT": 2280, "MARUTI": 11200, "TITAN": 3520,
        "BAJFINANCE": 7450, "WIPRO": 295, "HCLTECH": 1920, "SUNPHARMA": 1850, "ULTRACEMCO": 11800,
        "TATASTEEL": 155, "POWERGRID": 325, "NTPC": 385, "ONGC": 265, "TATAMOTORS": 780,
        "ADANIENT": 2400, "TECHM": 1650, "BAJAJFINSV": 1720, "INDUSINDBK": 1480, "JSWSTEEL": 920,
    }

    INDEX_BASE_VALUES = {
        "NIFTY": 23500, "BANKNIFTY": 49800, "FINNIFTY": 22100, "SENSEX": 77500, "BANKEX": 54200,
    }

    # Popular F&O stocks
    FO_STOCKS = [
        "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR",
        "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK",
        "ASIANPAINT", "MARUTI", "TITAN", "BAJFINANCE", "WIPRO", "HCLTECH",
        "SUNPHARMA", "ULTRACEMCO", "TATASTEEL", "POWERGRID", "NTPC", "ONGC",
        "TATAMOTORS", "ADANIENT", "TECHM", "BAJAJFINSV", "INDUSINDBK", "JSWSTEEL",
    ]

    # Data source tracking
    _use_live_data = True
    _last_api_error = None

    @staticmethod
    def _get_angel():
        if get_angel_service_callable:
            return get_angel_service_callable()
        return None

    @staticmethod
    def _generate_fallback_price(base_price: float, volatility: float = 0.02) -> Dict[str, float]:
        """Generate fallback simulated price - ONLY used when live mode is OFF."""
        import random
        random.seed(int(datetime.now(timezone.utc).timestamp() / 60))

        change_pct = (random.random() - 0.5) * volatility * 2
        price = base_price * (1 + change_pct)
        prev_close = base_price * (1 + (random.random() - 0.5) * 0.01)

        return {
            "price": round(price, 2),
            "prev_close": round(prev_close, 2),
            "change": round(price - prev_close, 2),
            "change_pct": round((price - prev_close) / prev_close * 100, 2),
            "open": round(prev_close * (1 + (random.random() - 0.5) * 0.005), 2),
            "high": round(max(price, prev_close) * (1 + random.random() * 0.01), 2),
            "low": round(min(price, prev_close) * (1 - random.random() * 0.01), 2),
            "volume": int(random.random() * 5000000 + 1000000),
        }

    @staticmethod
    async def get_stock_price(symbol: str, exchange: str = "NSE") -> Dict[str, Any]:
        """Get stock price - Live from Angel One or simulated based on toggle."""
        if MarketDataService._use_live_data and ANGEL_ONE_AVAILABLE:
            try:
                angel = MarketDataService._get_angel()
                if angel and angel.is_connected():
                    quote = angel.get_quote(symbol, exchange)
                    if quote and quote.get('price') is not None:
                        quote['data_source'] = 'angel_one_live'
                        return quote
            except Exception as e:
                logger.warning(f"Angel One API error for {symbol}: {e}")
                MarketDataService._last_api_error = str(e)

            return {
                "symbol": symbol, "exchange": exchange,
                "price": None, "prev_close": None, "open": None,
                "high": None, "low": None, "volume": None,
                "change": None, "change_pct": None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data_source": "angel_one_unavailable", "error": "API timeout - data unavailable",
            }

        base_price = MarketDataService.STOCK_BASE_PRICES.get(symbol, 1000)
        if exchange == "BSE":
            base_price = base_price * (1 + (hash(symbol) % 100 - 50) * 0.0001)

        price_data = MarketDataService._generate_fallback_price(base_price)
        return {
            "symbol": symbol, "exchange": exchange,
            "price": price_data["price"], "prev_close": price_data["prev_close"],
            "open": price_data["open"], "high": price_data["high"],
            "low": price_data["low"], "volume": price_data["volume"],
            "change": price_data["change"], "change_pct": price_data["change_pct"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data_source": "simulated",
        }

    @staticmethod
    async def get_index_data(index_name: str) -> Dict[str, Any]:
        """Get index data - Live from Angel One or simulated."""
        if MarketDataService._use_live_data and ANGEL_ONE_AVAILABLE:
            try:
                angel = MarketDataService._get_angel()
                if angel and angel.is_connected():
                    quote = angel.get_index_quote(index_name)
                    if quote and quote.get('value') is not None:
                        quote['data_source'] = 'angel_one_live'
                        return quote
            except Exception as e:
                logger.warning(f"Angel One API error for index {index_name}: {e}")

            return {
                "index": index_name, "value": None, "prev_close": None,
                "change": None, "change_pct": None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data_source": "angel_one_unavailable", "error": "API timeout - data unavailable",
            }

        base_value = MarketDataService.INDEX_BASE_VALUES.get(index_name, 20000)
        price_data = MarketDataService._generate_fallback_price(base_value, 0.015)
        return {
            "index": index_name, "value": price_data["price"],
            "prev_close": price_data["prev_close"],
            "change": price_data["change"], "change_pct": price_data["change_pct"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data_source": "simulated",
        }

    @staticmethod
    async def get_multiple_stocks(symbols: List[str]) -> List[Dict[str, Any]]:
        """Fetch multiple stocks."""
        results = []
        for symbol in symbols:
            nse_data = await MarketDataService.get_stock_price(symbol, "NSE")
            bse_data = await MarketDataService.get_stock_price(symbol, "BSE")
            if nse_data and nse_data.get('price', 0) > 0:
                results.append(nse_data)
            if bse_data and bse_data.get('price', 0) > 0:
                results.append(bse_data)
        return results

    @staticmethod
    def get_data_source_status() -> Dict[str, Any]:
        """Get current data source status."""
        if ANGEL_ONE_AVAILABLE:
            angel = MarketDataService._get_angel()
            session_status = angel.get_session_status() if angel else None
            return {
                "angel_one_available": True,
                "use_live_data": MarketDataService._use_live_data,
                "session_status": session_status,
                "last_api_error": MarketDataService._last_api_error,
            }
        return {
            "angel_one_available": False,
            "use_live_data": False,
            "session_status": None,
            "last_api_error": "Angel One service not configured",
        }

    @staticmethod
    def set_use_live_data(use_live: bool):
        """Toggle between live and simulated data."""
        MarketDataService._use_live_data = use_live
        logger.info(f"Data source set to: {'live' if use_live else 'simulated'}")
