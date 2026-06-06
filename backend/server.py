from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.gzip import GZipMiddleware
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import httpx
import asyncio
import json
import numpy as np
from scipy import stats

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app
app = FastAPI(title="Indian Markets Arbitrage Platform")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==================== MODELS ====================

class User(BaseModel):
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserSession(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    session_token: str
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class WatchlistItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    symbol: str
    exchange: str  # NSE or BSE
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Alert(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    alert_type: str  # arbitrage, spread, price
    symbol: Optional[str] = None
    threshold: float
    telegram_chat_id: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BacktestRequest(BaseModel):
    strategy: str
    symbol: str
    start_date: str
    end_date: str
    initial_capital: float = 1000000
    
class ArbitrageOpportunity(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str
    symbol: str
    nse_price: Optional[float] = None
    bse_price: Optional[float] = None
    futures_price: Optional[float] = None
    spot_price: Optional[float] = None
    spread_pct: float
    net_profit: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ==================== MARKET DATA SERVICE ====================

# Import Angel One Service
try:
    from angel_one_service import get_angel_service, SYMBOL_TOKENS, INDEX_TOKENS as ANGEL_INDEX_TOKENS
    ANGEL_ONE_AVAILABLE = True
except ImportError:
    ANGEL_ONE_AVAILABLE = False
    logger.warning("Angel One service not available, using simulated data")

# Import Option Chain Service
try:
    from option_chain_service import get_option_chain_service
    OPTION_CHAIN_AVAILABLE = True
except ImportError:
    OPTION_CHAIN_AVAILABLE = False
    logger.warning("Option chain service not available")

# Import IV Analytics Service
try:
    from iv_analytics_service import (
        calculate_iv, calculate_historical_volatility, calculate_iv_rank,
        calculate_iv_percentile, calculate_max_pain, build_iv_skew,
        get_atm_iv, detect_iv_signal, INDIA_VIX_TOKEN, INDIA_VIX_EXCHANGE
    )
    IV_ANALYTICS_AVAILABLE = True
except ImportError:
    IV_ANALYTICS_AVAILABLE = False
    logger.warning("IV analytics service not available")


class MarketDataService:
    """Service to fetch real-time market data from Angel One SmartAPI with fallback to simulated data"""
    
    # Fallback base prices for Indian stocks (used when API fails)
    STOCK_BASE_PRICES = {
        "RELIANCE": 2850, "TCS": 3950, "HDFCBANK": 1720, "INFY": 1820, "ICICIBANK": 1280,
        "HINDUNILVR": 2450, "ITC": 485, "SBIN": 825, "BHARTIARTL": 1650, "KOTAKBANK": 1890,
        "LT": 3650, "AXISBANK": 1180, "ASIANPAINT": 2280, "MARUTI": 11200, "TITAN": 3520,
        "BAJFINANCE": 7450, "WIPRO": 295, "HCLTECH": 1920, "SUNPHARMA": 1850, "ULTRACEMCO": 11800,
        "TATASTEEL": 155, "POWERGRID": 325, "NTPC": 385, "ONGC": 265, "TATAMOTORS": 780,
        "ADANIENT": 2400, "TECHM": 1650, "BAJAJFINSV": 1720, "INDUSINDBK": 1480, "JSWSTEEL": 920
    }
    
    INDEX_BASE_VALUES = {
        "NIFTY": 23500, "BANKNIFTY": 49800, "FINNIFTY": 22100, "SENSEX": 77500, "BANKEX": 54200
    }
    
    # Popular F&O stocks
    FO_STOCKS = [
        "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR", 
        "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK",
        "ASIANPAINT", "MARUTI", "TITAN", "BAJFINANCE", "WIPRO", "HCLTECH",
        "SUNPHARMA", "ULTRACEMCO", "TATASTEEL", "POWERGRID", "NTPC", "ONGC",
        "TATAMOTORS", "ADANIENT", "TECHM", "BAJAJFINSV", "INDUSINDBK", "JSWSTEEL"
    ]
    
    # Data source tracking
    _use_live_data = True  # Default to True - use Angel One live data
    _last_api_error = None
    
    @staticmethod
    def _generate_fallback_price(base_price: float, volatility: float = 0.02) -> Dict[str, float]:
        """Generate fallback simulated price - ONLY used when live mode is OFF"""
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
            "volume": int(random.random() * 5000000 + 1000000)
        }
    
    @staticmethod
    async def get_stock_price(symbol: str, exchange: str = "NSE") -> Dict[str, Any]:
        """Get stock price - Live from Angel One or simulated based on toggle"""
        
        # If live mode is ON, try Angel One API
        if MarketDataService._use_live_data and ANGEL_ONE_AVAILABLE:
            try:
                angel = get_angel_service()
                
                # Ensure we have a valid session
                if not angel.auth_token:
                    angel.login()
                
                if angel.auth_token:
                    quote = angel.get_quote(symbol, exchange)
                    
                    if quote and quote.get('price') is not None:
                        quote['data_source'] = 'angel_one_live'
                        return quote
                    
            except Exception as e:
                logger.warning(f"Angel One API error for {symbol}: {e}")
                MarketDataService._last_api_error = str(e)
            
            # Live mode ON but API failed - return blank data, NOT mock
            return {
                "symbol": symbol,
                "exchange": exchange,
                "price": None,
                "prev_close": None,
                "open": None,
                "high": None,
                "low": None,
                "volume": None,
                "change": None,
                "change_pct": None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data_source": "angel_one_unavailable",
                "error": "API timeout - data unavailable"
            }
        
        # Live mode is OFF - use simulated data
        base_price = MarketDataService.STOCK_BASE_PRICES.get(symbol, 1000)
        
        if exchange == "BSE":
            base_price = base_price * (1 + (hash(symbol) % 100 - 50) * 0.0001)
        
        price_data = MarketDataService._generate_fallback_price(base_price)
        
        return {
            "symbol": symbol,
            "exchange": exchange,
            "price": price_data["price"],
            "prev_close": price_data["prev_close"],
            "open": price_data["open"],
            "high": price_data["high"],
            "low": price_data["low"],
            "volume": price_data["volume"],
            "change": price_data["change"],
            "change_pct": price_data["change_pct"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data_source": "simulated"
        }
    
    @staticmethod
    async def get_index_data(index_name: str) -> Dict[str, Any]:
        """Get index data - Live from Angel One or simulated based on toggle"""
        
        # If live mode is ON, try Angel One API
        if MarketDataService._use_live_data and ANGEL_ONE_AVAILABLE:
            try:
                angel = get_angel_service()
                
                if not angel.auth_token:
                    angel.login()
                
                if angel.auth_token:
                    quote = angel.get_index_quote(index_name)
                    
                    if quote and quote.get('value') is not None:
                        quote['data_source'] = 'angel_one_live'
                        return quote
                    
            except Exception as e:
                logger.warning(f"Angel One API error for index {index_name}: {e}")
            
            # Live mode ON but API failed - return blank data
            return {
                "index": index_name,
                "value": None,
                "prev_close": None,
                "change": None,
                "change_pct": None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data_source": "angel_one_unavailable",
                "error": "API timeout - data unavailable"
            }
        
        # Live mode is OFF - use simulated data
        base_value = MarketDataService.INDEX_BASE_VALUES.get(index_name, 20000)
        price_data = MarketDataService._generate_fallback_price(base_value, 0.015)
        
        return {
            "index": index_name,
            "value": price_data["price"],
            "prev_close": price_data["prev_close"],
            "change": price_data["change"],
            "change_pct": price_data["change_pct"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data_source": "simulated"
        }
    
    @staticmethod
    async def get_multiple_stocks(symbols: List[str]) -> List[Dict[str, Any]]:
        """Fetch multiple stocks - Angel One API or fallback"""
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
        """Get current data source status"""
        if ANGEL_ONE_AVAILABLE:
            angel = get_angel_service()
            session_status = angel.get_session_status()
            return {
                "angel_one_available": True,
                "use_live_data": MarketDataService._use_live_data,
                "session_status": session_status,
                "last_api_error": MarketDataService._last_api_error
            }
        return {
            "angel_one_available": False,
            "use_live_data": False,
            "session_status": None,
            "last_api_error": "Angel One service not configured"
        }
    
    @staticmethod
    def set_use_live_data(use_live: bool):
        """Toggle between live and simulated data"""
        MarketDataService._use_live_data = use_live
        logger.info(f"Data source set to: {'live' if use_live else 'simulated'}")

# ==================== ARBITRAGE ENGINE ====================

class ArbitrageEngine:
    """Engine to detect various arbitrage opportunities"""
    
    # Transaction costs for Indian markets
    BROKERAGE_PCT = 0.03  # 0.03%
    STT_DELIVERY = 0.1    # 0.1% on delivery
    STT_INTRADAY = 0.025  # 0.025% on intraday
    STAMP_DUTY = 0.015    # 0.015%
    GST = 18              # 18% on brokerage
    SEBI_CHARGES = 0.0001 # 0.0001%
    
    @staticmethod
    def calculate_transaction_cost(value: float, is_delivery: bool = True) -> float:
        """Calculate total transaction cost"""
        brokerage = value * ArbitrageEngine.BROKERAGE_PCT / 100
        stt = value * (ArbitrageEngine.STT_DELIVERY if is_delivery else ArbitrageEngine.STT_INTRADAY) / 100
        stamp = value * ArbitrageEngine.STAMP_DUTY / 100
        gst = brokerage * ArbitrageEngine.GST / 100
        sebi = value * ArbitrageEngine.SEBI_CHARGES / 100
        return brokerage + stt + stamp + gst + sebi
    
    @staticmethod
    async def detect_cross_exchange_arbitrage(symbols: List[str]) -> List[Dict[str, Any]]:
        """Detect NSE vs BSE price differences using batch API for speed"""
        opportunities = []
        
        # Use batch fetching for speed
        if ANGEL_ONE_AVAILABLE and MarketDataService._use_live_data:
            try:
                angel = get_angel_service()
                if angel.is_connected():
                    nse_stocks = angel.get_multiple_stocks_batch(symbols, "NSE")
                    bse_stocks = angel.get_multiple_stocks_batch(symbols, "BSE")
                    
                    # Create lookup dictionaries
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
                            
                            # Slippage estimate (0.02% of trade value for liquid F&O stocks)
                            slippage_pct = 0.02
                            slippage = (buy_price + sell_price) * slippage_pct / 100
                            
                            net_profit = spread - total_txn_cost - slippage
                            net_profit_pct = (net_profit / buy_price) * 100
                            
                            # Show all opportunities with spread > 0.01% (lower threshold)
                            if spread_pct > 0.01:
                                opportunities.append({
                                    "type": "cross_exchange",
                                    "symbol": symbol,
                                    "nse_price": round(nse_price, 2),
                                    "bse_price": round(bse_price, 2),
                                    "spread": round(spread, 2),
                                    "spread_pct": round(spread_pct, 4),
                                    "buy_exchange": buy_exchange,
                                    "sell_exchange": "NSE" if buy_exchange == "BSE" else "BSE",
                                    "buy_price": round(buy_price, 2),
                                    "sell_price": round(sell_price, 2),
                                    "txn_cost": round(total_txn_cost, 2),
                                    "slippage": round(slippage, 2),
                                    "slippage_pct": slippage_pct,
                                    "net_profit_per_share": round(net_profit, 2),
                                    "net_profit_pct": round(net_profit_pct, 4),
                                    "is_profitable": net_profit > 0,
                                    "data_source": "angel_one_live",
                                    "timestamp": datetime.now(timezone.utc).isoformat()
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
                
                # Calculate net profit after costs
                buy_exchange = "BSE" if bse_price < nse_price else "NSE"
                buy_price = min(nse_price, bse_price)
                sell_price = max(nse_price, bse_price)
                
                buy_cost = ArbitrageEngine.calculate_transaction_cost(buy_price, False)
                sell_cost = ArbitrageEngine.calculate_transaction_cost(sell_price, False)
                
                net_profit = spread - buy_cost - sell_cost
                net_profit_pct = (net_profit / buy_price) * 100
                
                if spread_pct > 0.1:  # Only show if spread > 0.1%
                    opportunities.append({
                        "type": "cross_exchange",
                        "symbol": symbol,
                        "nse_price": round(nse_price, 2),
                        "bse_price": round(bse_price, 2),
                        "spread": round(spread, 2),
                        "spread_pct": round(spread_pct, 3),
                        "buy_exchange": buy_exchange,
                        "sell_exchange": "NSE" if buy_exchange == "BSE" else "BSE",
                        "net_profit_per_share": round(net_profit, 2),
                        "net_profit_pct": round(net_profit_pct, 3),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
        
        return sorted(opportunities, key=lambda x: x["spread_pct"], reverse=True)
    
    @staticmethod
    def calculate_cash_carry_arbitrage(spot_price: float, futures_price: float, 
                                        days_to_expiry: int, risk_free_rate: float = 7.0) -> Dict[str, Any]:
        """Calculate cash and carry arbitrage opportunity"""
        if spot_price <= 0 or futures_price <= 0 or days_to_expiry <= 0:
            return {"error": "Invalid input"}
        
        # Fair value of futures
        fair_value = spot_price * (1 + (risk_free_rate / 100) * (days_to_expiry / 365))
        
        # Basis
        basis = futures_price - spot_price
        basis_pct = (basis / spot_price) * 100
        
        # Annualized basis
        annualized_basis = (basis_pct / days_to_expiry) * 365
        
        # Mispricing
        mispricing = futures_price - fair_value
        mispricing_pct = (mispricing / fair_value) * 100
        
        # Transaction costs (buy spot + sell futures)
        total_cost = ArbitrageEngine.calculate_transaction_cost(spot_price, True) + \
                     ArbitrageEngine.calculate_transaction_cost(futures_price, False)
        
        # Net profit
        net_profit = basis - total_cost
        net_profit_pct = (net_profit / spot_price) * 100
        annualized_return = (net_profit_pct / days_to_expiry) * 365
        
        return {
            "spot_price": round(spot_price, 2),
            "futures_price": round(futures_price, 2),
            "fair_value": round(fair_value, 2),
            "basis": round(basis, 2),
            "basis_pct": round(basis_pct, 3),
            "annualized_basis": round(annualized_basis, 2),
            "mispricing": round(mispricing, 2),
            "mispricing_pct": round(mispricing_pct, 3),
            "days_to_expiry": days_to_expiry,
            "transaction_cost": round(total_cost, 2),
            "net_profit": round(net_profit, 2),
            "net_profit_pct": round(net_profit_pct, 3),
            "annualized_return": round(annualized_return, 2),
            "is_profitable": net_profit > 0,
            "strategy": "Buy Spot + Sell Futures" if futures_price > fair_value else "Sell Spot + Buy Futures"
        }
    
    @staticmethod
    def calculate_synthetic_futures_arbitrage(spot_price: float, call_price: float, 
                                               put_price: float, strike: float,
                                               futures_price: float) -> Dict[str, Any]:
        """Calculate synthetic futures vs actual futures arbitrage"""
        # Synthetic Future = Call - Put + Strike (using put-call parity)
        synthetic_future = call_price - put_price + strike
        
        # Mispricing
        mispricing = futures_price - synthetic_future
        mispricing_pct = (mispricing / synthetic_future) * 100 if synthetic_future > 0 else 0
        
        # Transaction costs (4 legs: buy call, sell put, and futures)
        total_cost = ArbitrageEngine.calculate_transaction_cost(call_price + put_price + futures_price, False)
        
        net_profit = abs(mispricing) - total_cost
        
        return {
            "spot_price": round(spot_price, 2),
            "call_price": round(call_price, 2),
            "put_price": round(put_price, 2),
            "strike": round(strike, 2),
            "synthetic_future": round(synthetic_future, 2),
            "actual_future": round(futures_price, 2),
            "mispricing": round(mispricing, 2),
            "mispricing_pct": round(mispricing_pct, 3),
            "transaction_cost": round(total_cost, 2),
            "net_profit": round(net_profit, 2),
            "is_profitable": net_profit > 0,
            "strategy": "Buy Synthetic + Sell Futures" if futures_price > synthetic_future else "Sell Synthetic + Buy Futures"
        }
    
    @staticmethod
    def calculate_calendar_spread(near_futures: float, far_futures: float,
                                   near_expiry_days: int, far_expiry_days: int) -> Dict[str, Any]:
        """Calculate calendar spread arbitrage"""
        spread = far_futures - near_futures
        spread_pct = (spread / near_futures) * 100 if near_futures > 0 else 0
        
        # Annualized spread
        days_diff = far_expiry_days - near_expiry_days
        annualized_spread = (spread_pct / days_diff) * 365 if days_diff > 0 else 0
        
        return {
            "near_futures": round(near_futures, 2),
            "far_futures": round(far_futures, 2),
            "spread": round(spread, 2),
            "spread_pct": round(spread_pct, 3),
            "near_expiry_days": near_expiry_days,
            "far_expiry_days": far_expiry_days,
            "annualized_spread": round(annualized_spread, 2),
            "strategy": "Buy Near + Sell Far" if spread > 0 else "Sell Near + Buy Far"
        }
    
    @staticmethod
    def calculate_statistical_arbitrage(prices1: List[float], prices2: List[float],
                                         lookback: int = 20) -> Dict[str, Any]:
        """Calculate statistical arbitrage (pairs trading) signals"""
        if len(prices1) < lookback or len(prices2) < lookback:
            return {"error": "Insufficient data"}
        
        prices1 = np.array(prices1[-lookback:])
        prices2 = np.array(prices2[-lookback:])
        
        # Calculate spread ratio
        ratio = prices1 / prices2
        
        # Z-score
        mean_ratio = np.mean(ratio)
        std_ratio = np.std(ratio)
        current_ratio = ratio[-1]
        z_score = (current_ratio - mean_ratio) / std_ratio if std_ratio > 0 else 0
        
        # Correlation
        correlation = np.corrcoef(prices1, prices2)[0, 1]
        
        # Half-life (mean reversion speed)
        spread = prices1 - prices2 * mean_ratio
        spread_lag = np.roll(spread, 1)[1:]
        spread_diff = np.diff(spread)
        
        try:
            slope, _, _, _, _ = stats.linregress(spread_lag, spread_diff)
            half_life = -np.log(2) / slope if slope < 0 else float('inf')
        except:
            half_life = float('inf')
        
        # Generate signal
        signal = "NEUTRAL"
        if z_score > 2:
            signal = "SHORT_SPREAD"  # Sell stock1, Buy stock2
        elif z_score < -2:
            signal = "LONG_SPREAD"   # Buy stock1, Sell stock2
        elif abs(z_score) < 0.5:
            signal = "EXIT"
        
        return {
            "current_ratio": round(current_ratio, 4),
            "mean_ratio": round(mean_ratio, 4),
            "z_score": round(z_score, 2),
            "correlation": round(correlation, 3),
            "half_life": round(half_life, 1) if half_life != float('inf') else "N/A",
            "signal": signal,
            "lookback": lookback
        }

# ==================== PERFORMANCE ANALYTICS ====================

class PerformanceAnalytics:
    """Calculate trading performance metrics"""
    
    @staticmethod
    def calculate_metrics(returns: List[float], risk_free_rate: float = 7.0) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics"""
        if not returns or len(returns) < 2:
            return {"error": "Insufficient data"}
        
        returns = np.array(returns)
        
        # Basic metrics
        total_return = (np.prod(1 + returns) - 1) * 100
        avg_return = np.mean(returns) * 100
        volatility = np.std(returns) * np.sqrt(252) * 100  # Annualized
        
        # Risk-adjusted metrics
        excess_returns = returns - (risk_free_rate / 100 / 252)
        sharpe_ratio = np.mean(excess_returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        
        # Sortino ratio (downside deviation)
        downside_returns = returns[returns < 0]
        downside_std = np.std(downside_returns) * np.sqrt(252) if len(downside_returns) > 0 else 0
        sortino_ratio = np.mean(excess_returns) * 252 / downside_std if downside_std > 0 else 0
        
        # Drawdown
        cumulative = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative - running_max) / running_max
        max_drawdown = np.min(drawdowns) * 100
        
        # Calmar ratio
        calmar_ratio = (total_return / 100) / abs(max_drawdown / 100) if max_drawdown != 0 else 0
        
        # Win rate
        winning_days = np.sum(returns > 0)
        total_days = len(returns)
        win_rate = (winning_days / total_days) * 100
        
        # Profit factor
        gross_profit = np.sum(returns[returns > 0])
        gross_loss = abs(np.sum(returns[returns < 0]))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        return {
            "total_return": round(total_return, 2),
            "avg_daily_return": round(avg_return, 3),
            "volatility": round(volatility, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "sortino_ratio": round(sortino_ratio, 2),
            "max_drawdown": round(max_drawdown, 2),
            "calmar_ratio": round(calmar_ratio, 2),
            "win_rate": round(win_rate, 1),
            "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else "N/A",
            "total_trades": total_days
        }
    
    @staticmethod
    def calculate_weekday_performance(trades: List[Dict]) -> Dict[str, Any]:
        """Analyze performance by weekday"""
        weekday_pnl = {i: [] for i in range(5)}  # Mon=0, Fri=4
        
        for trade in trades:
            if "date" in trade and "pnl" in trade:
                try:
                    date = datetime.fromisoformat(trade["date"].replace("Z", "+00:00"))
                    weekday = date.weekday()
                    if weekday < 5:  # Only weekdays
                        weekday_pnl[weekday].append(trade["pnl"])
                except:
                    pass
        
        weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        result = {}
        
        for i, name in enumerate(weekday_names):
            pnls = weekday_pnl[i]
            if pnls:
                result[name] = {
                    "total_pnl": round(sum(pnls), 2),
                    "avg_pnl": round(np.mean(pnls), 2),
                    "trade_count": len(pnls),
                    "win_rate": round(sum(1 for p in pnls if p > 0) / len(pnls) * 100, 1)
                }
            else:
                result[name] = {"total_pnl": 0, "avg_pnl": 0, "trade_count": 0, "win_rate": 0}
        
        return result

# ==================== RISK MANAGEMENT ====================

class RiskManager:
    """Risk management calculations"""
    
    @staticmethod
    def calculate_position_size(capital: float, risk_per_trade: float, 
                                 stop_loss_pct: float, price: float) -> Dict[str, Any]:
        """Calculate position size based on risk"""
        risk_amount = capital * (risk_per_trade / 100)
        stop_loss_amount = price * (stop_loss_pct / 100)
        
        shares = int(risk_amount / stop_loss_amount) if stop_loss_amount > 0 else 0
        position_value = shares * price
        
        return {
            "capital": capital,
            "risk_per_trade_pct": risk_per_trade,
            "risk_amount": round(risk_amount, 2),
            "stop_loss_pct": stop_loss_pct,
            "price": price,
            "recommended_shares": shares,
            "position_value": round(position_value, 2),
            "capital_utilization_pct": round((position_value / capital) * 100, 1)
        }
    
    @staticmethod
    def calculate_var(returns: List[float], confidence: float = 0.95, 
                      portfolio_value: float = 1000000) -> Dict[str, Any]:
        """Calculate Value at Risk"""
        if not returns:
            return {"error": "No returns data"}
        
        returns = np.array(returns)
        
        # Historical VaR
        var_pct = np.percentile(returns, (1 - confidence) * 100)
        var_amount = abs(var_pct * portfolio_value)
        
        # Parametric VaR (assuming normal distribution)
        mean = np.mean(returns)
        std = np.std(returns)
        z_score = stats.norm.ppf(1 - confidence)
        parametric_var_pct = mean + z_score * std
        parametric_var_amount = abs(parametric_var_pct * portfolio_value)
        
        return {
            "confidence_level": confidence * 100,
            "historical_var_pct": round(var_pct * 100, 2),
            "historical_var_amount": round(var_amount, 2),
            "parametric_var_pct": round(parametric_var_pct * 100, 2),
            "parametric_var_amount": round(parametric_var_amount, 2),
            "portfolio_value": portfolio_value
        }
    
    @staticmethod
    def calculate_margin_requirement(position_value: float, 
                                      volatility: float = 15,
                                      is_futures: bool = True) -> Dict[str, Any]:
        """Calculate SPAN margin requirement (simplified)"""
        # Simplified SPAN margin calculation
        if is_futures:
            span_margin_pct = max(10, volatility * 1.5)  # Minimum 10%
            exposure_margin_pct = 3.5
        else:
            span_margin_pct = max(15, volatility * 2)
            exposure_margin_pct = 5
        
        span_margin = position_value * (span_margin_pct / 100)
        exposure_margin = position_value * (exposure_margin_pct / 100)
        total_margin = span_margin + exposure_margin
        
        return {
            "position_value": position_value,
            "volatility": volatility,
            "span_margin_pct": round(span_margin_pct, 2),
            "span_margin": round(span_margin, 2),
            "exposure_margin_pct": round(exposure_margin_pct, 2),
            "exposure_margin": round(exposure_margin, 2),
            "total_margin": round(total_margin, 2),
            "leverage": round(position_value / total_margin, 1) if total_margin > 0 else 0
        }

# ==================== TELEGRAM ALERTS ====================

class TelegramService:
    """Send alerts via Telegram"""
    
    @staticmethod
    async def send_alert(chat_id: str, message: str, bot_token: str) -> bool:
        """Send Telegram message"""
        if not bot_token or not chat_id:
            logger.warning("Telegram not configured")
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": message,
                        "parse_mode": "HTML"
                    }
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Telegram error: {e}")
            return False
    
    @staticmethod
    def format_arbitrage_alert(opportunity: Dict) -> str:
        """Format arbitrage opportunity as Telegram message"""
        return f"""
🚨 <b>Arbitrage Alert!</b>

<b>Type:</b> {opportunity.get('type', 'Unknown')}
<b>Symbol:</b> {opportunity.get('symbol', 'N/A')}
<b>Spread:</b> {opportunity.get('spread_pct', 0):.2f}%
<b>Net Profit:</b> ₹{opportunity.get('net_profit_per_share', 0):.2f}/share

<b>Action:</b>
Buy on {opportunity.get('buy_exchange', 'N/A')} @ ₹{opportunity.get('nse_price' if opportunity.get('buy_exchange') == 'NSE' else 'bse_price', 0):.2f}
Sell on {opportunity.get('sell_exchange', 'N/A')} @ ₹{opportunity.get('bse_price' if opportunity.get('buy_exchange') == 'NSE' else 'nse_price', 0):.2f}

⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC
"""

# ==================== BACKTESTING ====================

class BacktestEngine:
    """Simple backtesting engine"""
    
    @staticmethod
    async def run_backtest(strategy: str, symbol: str, 
                           start_date: str, end_date: str,
                           initial_capital: float = 1000000) -> Dict[str, Any]:
        """Run a simple backtest simulation"""
        # Generate simulated historical data (in production, use actual historical data)
        np.random.seed(42)
        days = 252  # 1 year of trading days
        
        # Simulate daily returns
        if strategy == "cross_exchange":
            # Cross-exchange arbitrage typically has small but consistent returns
            daily_returns = np.random.normal(0.0005, 0.002, days)
        elif strategy == "cash_carry":
            # Cash and carry has more predictable returns
            daily_returns = np.random.normal(0.0003, 0.001, days)
        elif strategy == "statistical":
            # Statistical arbitrage has higher variance
            daily_returns = np.random.normal(0.0008, 0.005, days)
        else:
            daily_returns = np.random.normal(0.0004, 0.003, days)
        
        # Calculate equity curve
        equity = [initial_capital]
        for ret in daily_returns:
            equity.append(equity[-1] * (1 + ret))
        
        # Calculate metrics
        metrics = PerformanceAnalytics.calculate_metrics(daily_returns.tolist())
        
        # Generate trade log
        trades = []
        for i in range(min(50, days)):
            date = datetime.now(timezone.utc) - timedelta(days=days-i)
            trades.append({
                "date": date.isoformat(),
                "symbol": symbol,
                "action": "BUY" if daily_returns[i] > 0 else "SELL",
                "price": round(1000 * (1 + np.sum(daily_returns[:i]) * 0.1), 2),
                "quantity": 100,
                "pnl": round(initial_capital * daily_returns[i], 2)
            })
        
        return {
            "strategy": strategy,
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": initial_capital,
            "final_capital": round(equity[-1], 2),
            "total_return_pct": round((equity[-1] / initial_capital - 1) * 100, 2),
            "metrics": metrics,
            "equity_curve": [round(e, 2) for e in equity[::5]],  # Sample every 5 days
            "trades": trades[-20:],  # Last 20 trades
            "total_trades": len(trades)
        }

# ==================== AUTH HELPERS ====================

async def get_current_user(request: Request) -> Optional[User]:
    """Get current user from session token"""
    session_token = request.cookies.get("session_token")
    
    if not session_token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            session_token = auth_header[7:]
    
    if not session_token:
        return None
    
    session = await db.user_sessions.find_one(
        {"session_token": session_token},
        {"_id": 0}
    )
    
    if not session:
        return None
    
    expires_at = session.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    if expires_at < datetime.now(timezone.utc):
        return None
    
    user = await db.users.find_one(
        {"user_id": session["user_id"]},
        {"_id": 0}
    )
    
    return User(**user) if user else None

async def require_auth(request: Request) -> User:
    """Require authentication"""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

# ==================== API ROUTES ====================

# Health check
@api_router.get("/")
async def root():
    return {"message": "Indian Markets Arbitrage Platform API", "version": "1.0.0"}

@api_router.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

# ==================== AUTH ROUTES ====================

@api_router.post("/auth/session")
async def create_session(request: Request):
    """Exchange session_id for session_token (Emergent Auth)"""
    try:
        body = await request.json()
        session_id = body.get("session_id")
        
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id required")
        
        # Call Emergent Auth to get user data
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": session_id}
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid session")
            
            auth_data = response.json()
        
        # Create or update user
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        existing_user = await db.users.find_one({"email": auth_data["email"]}, {"_id": 0})
        
        if existing_user:
            user_id = existing_user["user_id"]
        else:
            await db.users.insert_one({
                "user_id": user_id,
                "email": auth_data["email"],
                "name": auth_data["name"],
                "picture": auth_data.get("picture"),
                "created_at": datetime.now(timezone.utc).isoformat()
            })
        
        # Create session
        session_token = auth_data.get("session_token", str(uuid.uuid4()))
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        
        await db.user_sessions.insert_one({
            "user_id": user_id,
            "session_token": session_token,
            "expires_at": expires_at.isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Set cookie
        response = JSONResponse({
            "user_id": user_id,
            "email": auth_data["email"],
            "name": auth_data["name"],
            "picture": auth_data.get("picture")
        })
        
        response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            secure=True,
            samesite="none",
            max_age=7 * 24 * 60 * 60,
            path="/"
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Auth error: {e}")
        raise HTTPException(status_code=500, detail="Authentication failed")

@api_router.get("/auth/me")
async def get_me(request: Request):
    """Get current user"""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return {
        "user_id": user.user_id,
        "email": user.email,
        "name": user.name,
        "picture": user.picture
    }

@api_router.post("/auth/logout")
async def logout(request: Request):
    """Logout user"""
    session_token = request.cookies.get("session_token")
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    
    response = JSONResponse({"message": "Logged out"})
    response.delete_cookie("session_token", path="/")
    return response

# ==================== MARKET DATA ROUTES ====================

@api_router.get("/market/indices")
async def get_indices():
    """Get major Indian indices - uses batch API for speed"""
    # If live mode, use batch fetching
    if MarketDataService._use_live_data and ANGEL_ONE_AVAILABLE:
        try:
            angel = get_angel_service()
            if angel.auth_token:
                results = angel.get_all_indices()
                if results:
                    for r in results:
                        r['data_source'] = 'angel_one_live'
                    return results
        except Exception as e:
            logger.warning(f"Batch index fetch failed: {e}")
        
        # Live mode but failed - return empty with error
        return [{
            "index": idx,
            "value": None,
            "prev_close": None,
            "change": None,
            "change_pct": None,
            "data_source": "angel_one_unavailable",
            "error": "API unavailable"
        } for idx in ["NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX", "BANKEX"]]
    
    # Simulated mode
    indices = ["NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX", "BANKEX"]
    tasks = [MarketDataService.get_index_data(idx) for idx in indices]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if isinstance(r, dict)]

@api_router.get("/market/stock/{symbol}")
async def get_stock(symbol: str, exchange: str = "NSE"):
    """Get stock price"""
    return await MarketDataService.get_stock_price(symbol.upper(), exchange.upper())

@api_router.get("/market/stocks")
async def get_stocks(symbols: str = None):
    """Get multiple stock prices - uses batch API for speed"""
    if symbols:
        symbol_list = [s.strip().upper() for s in symbols.split(",")]
    else:
        symbol_list = MarketDataService.FO_STOCKS[:5]  # Default to 5 stocks for faster loading
    
    # If live mode, use batch fetching
    if MarketDataService._use_live_data and ANGEL_ONE_AVAILABLE:
        try:
            angel = get_angel_service()
            if angel.auth_token:
                # Get NSE and BSE separately
                nse_results = angel.get_multiple_stocks_batch(symbol_list, "NSE")
                bse_results = angel.get_multiple_stocks_batch(symbol_list, "BSE")
                
                if nse_results or bse_results:
                    return nse_results + bse_results
        except Exception as e:
            logger.warning(f"Batch stock fetch failed: {e}")
        
        # Live mode but failed - return empty with error
        return [{
            "symbol": sym,
            "exchange": "NSE",
            "price": None,
            "data_source": "angel_one_unavailable",
            "error": "API unavailable"
        } for sym in symbol_list]
    
    # Simulated mode
    return await MarketDataService.get_multiple_stocks(symbol_list)

@api_router.get("/market/fo-stocks")
async def get_fo_stocks():
    """Get list of F&O stocks"""
    return {"stocks": MarketDataService.FO_STOCKS}

# ==================== DATA SOURCE MANAGEMENT ====================

@api_router.get("/market/data-source")
async def get_data_source_status():
    """Get current data source status (Angel One or simulated)"""
    return MarketDataService.get_data_source_status()

@api_router.post("/market/data-source/toggle")
async def toggle_data_source(use_live: bool = True):
    """Toggle between live Angel One data and simulated data"""
    MarketDataService.set_use_live_data(use_live)
    return {
        "use_live_data": use_live,
        "message": f"Data source set to {'Angel One Live' if use_live else 'Simulated'}"
    }

@api_router.post("/market/angel-one/login")
async def angel_one_login():
    """Manually trigger Angel One login"""
    if not ANGEL_ONE_AVAILABLE:
        raise HTTPException(status_code=400, detail="Angel One service not configured")
    
    try:
        angel = get_angel_service()
        # Reset attempts before trying
        angel.reset_login_attempts()
        success = angel.login()
        if success:
            return {
                "status": "success",
                "message": "Angel One login successful",
                "session_status": angel.get_session_status()
            }
        else:
            status = angel.get_session_status()
            raise HTTPException(
                status_code=401, 
                detail=f"Angel One login failed: {status.get('last_error', 'Unknown error')}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Angel One login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/market/angel-one/session")
async def get_angel_one_session():
    """Get Angel One session status with detailed info"""
    if not ANGEL_ONE_AVAILABLE:
        return {
            "available": False, 
            "message": "Angel One service not configured",
            "session_status": None
        }
    
    angel = get_angel_service()
    status = angel.get_session_status()
    
    return {
        "available": True,
        "session_status": status,
        "help": {
            "if_not_connected": "Call POST /api/market/angel-one/login to connect",
            "credentials_location": "Update credentials in /app/backend/.env and restart backend",
            "required_credentials": ["ANGEL_API_KEY", "ANGEL_CLIENT_ID", "ANGEL_MPIN", "ANGEL_TOTP_SECRET"]
        }
    }

@api_router.post("/market/angel-one/reset")
async def reset_angel_one():
    """Reset Angel One service - use after updating credentials"""
    if not ANGEL_ONE_AVAILABLE:
        raise HTTPException(status_code=400, detail="Angel One service not configured")
    
    angel = get_angel_service()
    angel.reset_login_attempts()
    
    # Try to login with new credentials
    success = angel.login()
    
    return {
        "status": "success" if success else "failed",
        "message": "Credentials reloaded" + (" and login successful" if success else " but login failed"),
        "session_status": angel.get_session_status()
    }

# ==================== BROKER STATUS ====================

def get_market_session_info() -> Dict[str, Any]:
    """Determine Indian market session status based on IST time"""
    ist = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist)
    weekday = now_ist.weekday()  # 0=Mon, 6=Sun
    
    time_str = now_ist.strftime("%H:%M")
    hour = now_ist.hour
    minute = now_ist.minute
    current_minutes = hour * 60 + minute
    
    # Market timings in minutes from midnight (IST)
    pre_open = 9 * 60           # 09:00
    market_open = 9 * 60 + 15   # 09:15
    market_close = 15 * 60 + 30 # 15:30
    post_close = 16 * 60        # 16:00
    
    is_weekend = weekday >= 5
    
    if is_weekend:
        session = "closed"
        session_label = "Weekend - Market Closed"
        next_open = "Monday 09:15 IST"
    elif current_minutes < pre_open:
        session = "pre_market"
        session_label = "Pre-Market"
        next_open = "09:15 IST"
    elif current_minutes < market_open:
        session = "pre_open"
        session_label = "Pre-Open Session"
        next_open = "09:15 IST"
    elif current_minutes < market_close:
        session = "market_open"
        session_label = "Market Open"
        mins_left = market_close - current_minutes
        next_open = f"Closes in {mins_left // 60}h {mins_left % 60}m"
    elif current_minutes < post_close:
        session = "post_market"
        session_label = "Post-Market / Closing Session"
        next_open = "Next trading day 09:15 IST"
    else:
        session = "closed"
        session_label = "Market Closed"
        next_open = "Next trading day 09:15 IST"
    
    return {
        "session": session,
        "session_label": session_label,
        "is_market_open": session == "market_open",
        "is_trading_hours": session in ("market_open", "pre_open"),
        "current_time_ist": now_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
        "next_event": next_open,
        "is_weekend": is_weekend
    }

@api_router.get("/market/broker-status")
async def get_broker_status():
    """Get comprehensive broker connection + market session status"""
    market_info = get_market_session_info()
    
    broker_status = {
        "broker": "angel_one",
        "is_available": ANGEL_ONE_AVAILABLE,
        "is_connected": False,
        "client_id": None,
        "session_expiry": None,
        "time_remaining": None,
        "last_error": None,
        "credentials_configured": False
    }
    
    if ANGEL_ONE_AVAILABLE:
        angel = get_angel_service()
        session = angel.get_session_status()
        broker_status.update({
            "is_connected": session["is_connected"],
            "client_id": session["client_id"],
            "session_expiry": session["session_expiry"],
            "time_remaining": session["time_remaining"],
            "last_error": session["last_error"],
            "credentials_configured": session["credentials_configured"],
            "last_login": session["last_login"],
            "login_attempts": session["login_attempts"]
        })
    
    # Determine overall data mode
    data_mode = "live" if broker_status["is_connected"] and MarketDataService._use_live_data else "simulated"
    
    return {
        "broker": broker_status,
        "market": market_info,
        "data_mode": data_mode,
        "use_live_data": MarketDataService._use_live_data
    }

# ==================== ARBITRAGE ROUTES ====================

@api_router.get("/arbitrage/cross-exchange")
async def get_cross_exchange_arbitrage(symbols: str = None):
    """Detect cross-exchange arbitrage opportunities"""
    if symbols:
        symbol_list = [s.strip().upper() for s in symbols.split(",")]
    else:
        symbol_list = MarketDataService.FO_STOCKS[:15]
    
    return await ArbitrageEngine.detect_cross_exchange_arbitrage(symbol_list)

@api_router.post("/arbitrage/cash-carry")
async def calculate_cash_carry(
    spot_price: float,
    futures_price: float,
    days_to_expiry: int,
    risk_free_rate: float = 7.0
):
    """Calculate cash and carry arbitrage"""
    return ArbitrageEngine.calculate_cash_carry_arbitrage(
        spot_price, futures_price, days_to_expiry, risk_free_rate
    )

@api_router.post("/arbitrage/synthetic")
async def calculate_synthetic(
    spot_price: float,
    call_price: float,
    put_price: float,
    strike: float,
    futures_price: float
):
    """Calculate synthetic futures arbitrage"""
    return ArbitrageEngine.calculate_synthetic_futures_arbitrage(
        spot_price, call_price, put_price, strike, futures_price
    )

@api_router.post("/arbitrage/calendar-spread")
async def calculate_calendar_spread(
    near_futures: float,
    far_futures: float,
    near_expiry_days: int,
    far_expiry_days: int
):
    """Calculate calendar spread"""
    return ArbitrageEngine.calculate_calendar_spread(
        near_futures, far_futures, near_expiry_days, far_expiry_days
    )

@api_router.post("/arbitrage/statistical")
async def calculate_statistical_arb(
    prices1: List[float],
    prices2: List[float],
    lookback: int = 20
):
    """Calculate statistical arbitrage signals"""
    return ArbitrageEngine.calculate_statistical_arbitrage(prices1, prices2, lookback)

# ==================== OPTION CHAIN ROUTES ====================

@api_router.get("/options/underlyings")
async def get_option_underlyings():
    """Get available underlyings for option chain"""
    if not OPTION_CHAIN_AVAILABLE:
        raise HTTPException(status_code=400, detail="Option chain service not available")
    
    oc_service = get_option_chain_service()
    return oc_service.get_underlyings()

@api_router.get("/options/expiries")
async def get_option_expiries(underlying: str = "NIFTY"):
    """Get available expiry dates for an underlying"""
    if not OPTION_CHAIN_AVAILABLE:
        raise HTTPException(status_code=400, detail="Option chain service not available")
    
    oc_service = get_option_chain_service()
    return oc_service.get_expiries(underlying.upper())

@api_router.get("/options/chain")
async def get_option_chain(underlying: str = "NIFTY", expiry: str = None, num_strikes: int = 15):
    """Get T-shaped option chain with live data — blocking calls run in thread pool"""
    if not OPTION_CHAIN_AVAILABLE:
        raise HTTPException(status_code=400, detail="Option chain service not available")
    
    oc_service = get_option_chain_service()
    
    if not expiry:
        expiries = oc_service.get_expiries(underlying.upper())
        if expiries:
            expiry = expiries[0]["expiry"]
        else:
            raise HTTPException(status_code=404, detail=f"No expiries found for {underlying}")
    
    # Get spot price — run blocking Angel One call in thread pool
    spot_price = 0
    if ANGEL_ONE_AVAILABLE:
        angel = get_angel_service()
        if angel.is_connected():
            def _fetch_spot():
                from angel_one_service import INDEX_TOKENS as IDX_TOKENS, SYMBOL_TOKENS as SYM_TOKENS
                u = underlying.upper()
                if u in IDX_TOKENS:
                    idx_info = IDX_TOKENS[u]
                    try:
                        data = angel.smart_api.getMarketData(mode="LTP", exchangeTokens={idx_info["exchange"]: [idx_info["token"]]})
                        if data.get("status") and data.get("data", {}).get("fetched"):
                            return float(data["data"]["fetched"][0].get("ltp", 0))
                    except Exception as e:
                        logger.error(f"Spot price fetch error for {u}: {e}")
                elif u in SYM_TOKENS:
                    try:
                        data = angel.smart_api.getMarketData(mode="LTP", exchangeTokens={"NSE": [SYM_TOKENS[u]["nse_token"]]})
                        if data.get("status") and data.get("data", {}).get("fetched"):
                            return float(data["data"]["fetched"][0].get("ltp", 0))
                    except Exception as e:
                        logger.error(f"Spot price fetch error for {u}: {e}")
                return 0
            spot_price = await asyncio.to_thread(_fetch_spot)
    
    if spot_price <= 0:
        fallback_spots = {
            "NIFTY": 24000, "BANKNIFTY": 50000, "FINNIFTY": 22000,
            "MIDCPNIFTY": 10500, "SENSEX": 78000, "NIFTYNXT50": 65000,
        }
        spot_price = fallback_spots.get(underlying.upper(), 1000)
    
    angel = get_angel_service() if ANGEL_ONE_AVAILABLE else None
    result = await asyncio.to_thread(oc_service.build_option_chain, angel, underlying.upper(), expiry, spot_price, num_strikes)
    return result

# ==================== IV ANALYTICS ROUTES ====================

@api_router.get("/iv/dashboard")
async def get_iv_dashboard(underlying: str = "NIFTY", expiry: str = None, num_strikes: int = 20):
    """Full IV dashboard for options sellers — ATM IV, IV Rank, Percentile, HV, VIX, signals"""
    if not IV_ANALYTICS_AVAILABLE or not OPTION_CHAIN_AVAILABLE:
        raise HTTPException(status_code=400, detail="IV analytics not available")

    oc_service = get_option_chain_service()
    u = underlying.upper()

    # Get expiry
    if not expiry:
        expiries = oc_service.get_expiries(u)
        if expiries:
            expiry = expiries[0]["expiry"]
        else:
            raise HTTPException(status_code=404, detail=f"No expiries for {u}")

    # Days to expiry
    try:
        exp_dt = datetime.strptime(expiry, "%d%b%Y")
        days_to_expiry = max(1, (exp_dt - datetime.now()).days)
    except ValueError:
        days_to_expiry = 30

    # Get spot price and option chain
    spot_price = 0
    angel = get_angel_service() if ANGEL_ONE_AVAILABLE else None

    if angel and angel.is_connected():
        def _fetch():
            from angel_one_service import INDEX_TOKENS as IDX, SYMBOL_TOKENS as SYM
            sp = 0
            if u in IDX:
                try:
                    data = angel.smart_api.getMarketData(mode="LTP", exchangeTokens={IDX[u]["exchange"]: [IDX[u]["token"]]})
                    if data.get("status") and data.get("data", {}).get("fetched"):
                        sp = float(data["data"]["fetched"][0].get("ltp", 0))
                except Exception as e:
                    logger.error(f"IV spot fetch error: {e}")
            elif u in SYM:
                try:
                    data = angel.smart_api.getMarketData(mode="LTP", exchangeTokens={"NSE": [SYM[u]["nse_token"]]})
                    if data.get("status") and data.get("data", {}).get("fetched"):
                        sp = float(data["data"]["fetched"][0].get("ltp", 0))
                except Exception as e:
                    logger.error(f"IV spot fetch error: {e}")
            return sp
        spot_price = await asyncio.to_thread(_fetch)

    if spot_price <= 0:
        fallbacks = {"NIFTY": 24000, "BANKNIFTY": 50000, "FINNIFTY": 22000}
        spot_price = fallbacks.get(u, 1000)

    # Build chain
    chain_result = await asyncio.to_thread(oc_service.build_option_chain, angel, u, expiry, spot_price, num_strikes)
    chain_data = chain_result.get("chain", [])

    # ATM IV
    atm_iv = get_atm_iv(chain_data, spot_price, days_to_expiry)

    # IV Skew
    iv_skew = build_iv_skew(chain_data, spot_price, days_to_expiry)

    # Max Pain
    max_pain = calculate_max_pain(chain_data)

    # Fetch India VIX
    vix_value = None
    if angel and angel.is_connected():
        def _fetch_vix():
            try:
                data = angel.smart_api.getMarketData(mode="LTP", exchangeTokens={INDIA_VIX_EXCHANGE: [INDIA_VIX_TOKEN]})
                if data.get("status") and data.get("data", {}).get("fetched"):
                    return float(data["data"]["fetched"][0].get("ltp", 0))
            except Exception as e:
                logger.error(f"VIX fetch error: {e}")
            return None
        vix_value = await asyncio.to_thread(_fetch_vix)

    # Historical data from MongoDB
    iv_history = []
    hv = None
    iv_rank = None
    iv_percentile = None

    try:
        # Get stored IV snapshots (last 252 trading days ~ 1 year)
        snapshots = await db.iv_snapshots.find(
            {"underlying": u},
            {"_id": 0, "atm_iv": 1, "date": 1}
        ).sort("date", -1).limit(252).to_list(252)

        if snapshots:
            iv_history = [s["atm_iv"] for s in snapshots if s.get("atm_iv") and s["atm_iv"] > 0]

        if atm_iv and iv_history:
            iv_rank = calculate_iv_rank(atm_iv, iv_history)
            iv_percentile = calculate_iv_percentile(atm_iv, iv_history)

        # Historical Volatility from price snapshots
        price_snapshots = await db.price_snapshots.find(
            {"underlying": u},
            {"_id": 0, "close": 1}
        ).sort("date", -1).limit(31).to_list(31)

        if price_snapshots:
            prices = [s["close"] for s in reversed(price_snapshots) if s.get("close")]
            hv_val = calculate_historical_volatility(prices, window=20)
            if hv_val:
                hv = round(hv_val * 100, 2)
    except Exception as e:
        logger.warning(f"Historical IV data fetch error: {e}")

    # Store today's snapshot (upsert)
    if atm_iv and atm_iv > 0:
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            await db.iv_snapshots.update_one(
                {"underlying": u, "date": today_str},
                {"$set": {
                    "underlying": u,
                    "date": today_str,
                    "atm_iv": atm_iv,
                    "vix": vix_value,
                    "spot_price": spot_price,
                    "expiry": expiry,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }},
                upsert=True
            )
        except Exception as e:
            logger.warning(f"IV snapshot save error: {e}")

    # Store price snapshot
    if spot_price > 0:
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            await db.price_snapshots.update_one(
                {"underlying": u, "date": today_str},
                {"$set": {
                    "underlying": u,
                    "date": today_str,
                    "close": spot_price,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }},
                upsert=True
            )
        except Exception as e:
            logger.warning(f"Price snapshot save error: {e}")

    # Seller signal
    signal = detect_iv_signal(iv_rank, iv_percentile, atm_iv, hv)

    return {
        "underlying": u,
        "expiry": expiry,
        "days_to_expiry": days_to_expiry,
        "spot_price": spot_price,
        "atm_iv": atm_iv,
        "iv_rank": iv_rank,
        "iv_percentile": iv_percentile,
        "historical_volatility": hv,
        "india_vix": vix_value,
        "iv_history_count": len(iv_history),
        "seller_signal": signal,
        "max_pain": max_pain,
        "iv_skew": iv_skew,
        "totals": chain_result.get("totals"),
        "atm_strike": chain_result.get("atm_strike"),
        "data_source": chain_result.get("data_source"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@api_router.get("/iv/skew")
async def get_iv_skew(underlying: str = "NIFTY", expiry: str = None, num_strikes: int = 20):
    """Get IV skew across strikes for visualization"""
    # Reuse the dashboard endpoint's logic for just the skew
    dashboard = await get_iv_dashboard(underlying, expiry, num_strikes)
    return {
        "underlying": dashboard["underlying"],
        "expiry": dashboard["expiry"],
        "spot_price": dashboard["spot_price"],
        "atm_strike": dashboard["atm_strike"],
        "atm_iv": dashboard["atm_iv"],
        "skew": dashboard["iv_skew"],
    }


@api_router.get("/iv/max-pain")
async def get_max_pain(underlying: str = "NIFTY", expiry: str = None):
    """Get max pain strike with pain distribution"""
    dashboard = await get_iv_dashboard(underlying, expiry, 25)
    return {
        "underlying": dashboard["underlying"],
        "expiry": dashboard["expiry"],
        "spot_price": dashboard["spot_price"],
        "max_pain": dashboard["max_pain"],
    }


# ==================== ANALYTICS ROUTES ====================

@api_router.post("/analytics/performance")
async def get_performance_metrics(returns: List[float], risk_free_rate: float = 7.0):
    """Calculate performance metrics"""
    return PerformanceAnalytics.calculate_metrics(returns, risk_free_rate)

@api_router.post("/analytics/weekday")
async def get_weekday_performance(trades: List[Dict]):
    """Analyze performance by weekday"""
    return PerformanceAnalytics.calculate_weekday_performance(trades)

# ==================== RISK MANAGEMENT ROUTES ====================

@api_router.post("/risk/position-size")
async def calculate_position_size(
    capital: float,
    risk_per_trade: float,
    stop_loss_pct: float,
    price: float
):
    """Calculate position size"""
    return RiskManager.calculate_position_size(capital, risk_per_trade, stop_loss_pct, price)

@api_router.post("/risk/var")
async def calculate_var(
    returns: List[float],
    confidence: float = 0.95,
    portfolio_value: float = 1000000
):
    """Calculate Value at Risk"""
    return RiskManager.calculate_var(returns, confidence, portfolio_value)

@api_router.post("/risk/margin")
async def calculate_margin(
    position_value: float,
    volatility: float = 15,
    is_futures: bool = True
):
    """Calculate margin requirement"""
    return RiskManager.calculate_margin_requirement(position_value, volatility, is_futures)

# ==================== ALERT ROUTES ====================

@api_router.post("/alerts")
async def create_alert(alert: Alert, request: Request):
    """Create a new alert"""
    user = await require_auth(request)
    alert.user_id = user.user_id
    
    alert_dict = alert.model_dump()
    alert_dict["created_at"] = alert_dict["created_at"].isoformat()
    await db.alerts.insert_one(alert_dict)
    
    return {"id": alert.id, "message": "Alert created"}

@api_router.get("/alerts")
async def get_alerts(request: Request):
    """Get user's alerts"""
    user = await require_auth(request)
    alerts = await db.alerts.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).to_list(100)
    return alerts

@api_router.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: str, request: Request):
    """Delete an alert"""
    user = await require_auth(request)
    result = await db.alerts.delete_one({"id": alert_id, "user_id": user.user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"message": "Alert deleted"}

@api_router.post("/alerts/test")
async def test_telegram_alert(chat_id: str, request: Request):
    """Test Telegram alert"""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise HTTPException(status_code=400, detail="Telegram not configured")
    
    success = await TelegramService.send_alert(
        chat_id,
        "🔔 <b>Test Alert</b>\n\nYour Telegram alerts are configured correctly!",
        bot_token
    )
    
    return {"success": success}

# ==================== BACKTEST ROUTES ====================

@api_router.post("/backtest")
async def run_backtest(request: BacktestRequest):
    """Run backtest"""
    return await BacktestEngine.run_backtest(
        request.strategy,
        request.symbol,
        request.start_date,
        request.end_date,
        request.initial_capital
    )

# ==================== WATCHLIST ROUTES ====================

@api_router.get("/watchlist")
async def get_watchlist(request: Request):
    """Get user's watchlist"""
    user = await require_auth(request)
    items = await db.watchlist.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).to_list(100)
    return items

@api_router.post("/watchlist")
async def add_to_watchlist(item: WatchlistItem, request: Request):
    """Add symbol to watchlist"""
    user = await require_auth(request)
    item.user_id = user.user_id
    
    # Check if already exists
    existing = await db.watchlist.find_one({
        "user_id": user.user_id,
        "symbol": item.symbol,
        "exchange": item.exchange
    })
    if existing:
        raise HTTPException(status_code=400, detail="Already in watchlist")
    
    item_dict = item.model_dump()
    item_dict["created_at"] = item_dict["created_at"].isoformat()
    await db.watchlist.insert_one(item_dict)
    
    return {"id": item.id, "message": "Added to watchlist"}

@api_router.delete("/watchlist/{item_id}")
async def remove_from_watchlist(item_id: str, request: Request):
    """Remove from watchlist"""
    user = await require_auth(request)
    result = await db.watchlist.delete_one({"id": item_id, "user_id": user.user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"message": "Removed from watchlist"}

# ==================== SETTINGS ROUTES ====================

@api_router.get("/settings")
async def get_settings(request: Request):
    """Get user settings"""
    user = await require_auth(request)
    settings = await db.settings.find_one(
        {"user_id": user.user_id},
        {"_id": 0}
    )
    return settings or {
        "user_id": user.user_id,
        "telegram_chat_id": None,
        "alert_threshold": 0.5,
        "default_capital": 1000000,
        "risk_per_trade": 2.0
    }

@api_router.put("/settings")
async def update_settings(settings: Dict[str, Any], request: Request):
    """Update user settings"""
    user = await require_auth(request)
    settings["user_id"] = user.user_id
    
    await db.settings.update_one(
        {"user_id": user.user_id},
        {"$set": settings},
        upsert=True
    )
    return {"message": "Settings updated"}

# Include router
app.include_router(api_router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip compression for large option chain / market data responses
app.add_middleware(GZipMiddleware, minimum_size=1000)

@app.on_event("startup")
async def startup_event():
    """Auto-login to Angel One on startup"""
    if ANGEL_ONE_AVAILABLE:
        try:
            angel = get_angel_service()
            success = angel.login()
            if success:
                logger.info("Angel One auto-login successful on startup")
            else:
                logger.warning("Angel One auto-login failed - will use simulated data until manual login")
        except Exception as e:
            logger.error(f"Angel One startup login error: {e}")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
    # Cleanup Angel One session
    if ANGEL_ONE_AVAILABLE:
        try:
            angel = get_angel_service()
            angel.logout()
        except:
            pass
