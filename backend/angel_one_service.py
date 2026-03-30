"""
Angel One SmartAPI Integration Service
- Session management with auto-refresh
- Real-time market data for NSE/BSE
- Symbol token mapping
"""

import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import pyotp
from SmartApi import SmartConnect
import threading
import time

logger = logging.getLogger(__name__)

# Symbol token mapping for popular F&O stocks
# Format: {"SYMBOL": {"nse_token": "xxx", "bse_token": "xxx", "lot_size": xx}}
SYMBOL_TOKENS = {
    "RELIANCE": {"nse_token": "2885", "bse_token": "500325", "lot_size": 250},
    "TCS": {"nse_token": "11536", "bse_token": "532540", "lot_size": 150},
    "HDFCBANK": {"nse_token": "1333", "bse_token": "500180", "lot_size": 550},
    "INFY": {"nse_token": "1594", "bse_token": "500209", "lot_size": 300},
    "ICICIBANK": {"nse_token": "4963", "bse_token": "532174", "lot_size": 700},
    "HINDUNILVR": {"nse_token": "1394", "bse_token": "500696", "lot_size": 300},
    "ITC": {"nse_token": "1660", "bse_token": "500875", "lot_size": 1600},
    "SBIN": {"nse_token": "3045", "bse_token": "500112", "lot_size": 1500},
    "BHARTIARTL": {"nse_token": "10604", "bse_token": "532454", "lot_size": 475},
    "KOTAKBANK": {"nse_token": "1922", "bse_token": "500247", "lot_size": 400},
    "LT": {"nse_token": "11483", "bse_token": "500510", "lot_size": 150},
    "AXISBANK": {"nse_token": "5900", "bse_token": "532215", "lot_size": 625},
    "ASIANPAINT": {"nse_token": "236", "bse_token": "500820", "lot_size": 200},
    "MARUTI": {"nse_token": "10999", "bse_token": "532500", "lot_size": 50},
    "TITAN": {"nse_token": "14977", "bse_token": "500114", "lot_size": 175},
    "BAJFINANCE": {"nse_token": "317", "bse_token": "500034", "lot_size": 125},
    "WIPRO": {"nse_token": "3787", "bse_token": "507685", "lot_size": 1500},
    "HCLTECH": {"nse_token": "7229", "bse_token": "532281", "lot_size": 350},
    "SUNPHARMA": {"nse_token": "3351", "bse_token": "524715", "lot_size": 350},
    "ULTRACEMCO": {"nse_token": "11532", "bse_token": "532538", "lot_size": 50},
    "TATASTEEL": {"nse_token": "3499", "bse_token": "500470", "lot_size": 3375},
    "POWERGRID": {"nse_token": "14977", "bse_token": "532898", "lot_size": 2700},
    "NTPC": {"nse_token": "11630", "bse_token": "532555", "lot_size": 1575},
    "ONGC": {"nse_token": "2475", "bse_token": "500312", "lot_size": 1925},
    "TATAMOTORS": {"nse_token": "3456", "bse_token": "500570", "lot_size": 575},
    "ADANIENT": {"nse_token": "25", "bse_token": "512599", "lot_size": 250},
    "TECHM": {"nse_token": "13538", "bse_token": "532755", "lot_size": 300},
    "BAJAJFINSV": {"nse_token": "16675", "bse_token": "532978", "lot_size": 500},
    "INDUSINDBK": {"nse_token": "5258", "bse_token": "532187", "lot_size": 400},
    "JSWSTEEL": {"nse_token": "11723", "bse_token": "500228", "lot_size": 675},
}

# Index tokens
INDEX_TOKENS = {
    "NIFTY": {"token": "99926000", "exchange": "NSE"},
    "BANKNIFTY": {"token": "99926009", "exchange": "NSE"},
    "FINNIFTY": {"token": "99926037", "exchange": "NSE"},
    "SENSEX": {"token": "99919000", "exchange": "BSE"},
    "BANKEX": {"token": "99919016", "exchange": "BSE"},
}


class AngelOneService:
    """Singleton service for Angel One SmartAPI integration with session management"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.api_key = os.environ.get('ANGEL_API_KEY')
        self.client_id = os.environ.get('ANGEL_CLIENT_ID')
        self.mpin = os.environ.get('ANGEL_MPIN')
        self.totp_secret = os.environ.get('ANGEL_TOTP_SECRET')
        
        self.smart_api = None
        self.auth_token = None
        self.refresh_token = None
        self.feed_token = None
        self.session_expiry = None
        self.last_login = None
        
        self._session_refresh_thread = None
        self._stop_refresh = False
        
        self._initialized = True
        logger.info("AngelOneService initialized")
    
    def _generate_totp(self) -> str:
        """Generate current TOTP code"""
        try:
            # Clean the TOTP secret (remove spaces, ensure uppercase)
            clean_secret = self.totp_secret.replace(" ", "").upper()
            totp = pyotp.TOTP(clean_secret)
            return totp.now()
        except Exception as e:
            logger.error(f"TOTP generation failed: {e}")
            logger.error(f"TOTP secret format issue - ensure it's a valid base32 string")
            return ""
    
    def login(self) -> bool:
        """Login to Angel One SmartAPI"""
        if not all([self.api_key, self.client_id, self.mpin, self.totp_secret]):
            logger.error("Missing Angel One credentials")
            logger.error(f"API Key: {'SET' if self.api_key else 'MISSING'}")
            logger.error(f"Client ID: {'SET' if self.client_id else 'MISSING'}")
            logger.error(f"MPIN: {'SET' if self.mpin else 'MISSING'}")
            logger.error(f"TOTP Secret: {'SET' if self.totp_secret else 'MISSING'}")
            return False
        
        try:
            self.smart_api = SmartConnect(api_key=self.api_key)
            # Increase timeout for API calls
            if hasattr(self.smart_api, 'session') and self.smart_api.session:
                self.smart_api.session.timeout = 30  # 30 seconds timeout
            
            totp = self._generate_totp()
            
            if not totp:
                logger.error("Failed to generate TOTP - check TOTP secret format")
                return False
            
            logger.info(f"Attempting Angel One login for client: {self.client_id}")
            data = self.smart_api.generateSession(self.client_id, self.mpin, totp)
            
            if data.get('status') and data.get('data'):
                self.auth_token = data['data'].get('jwtToken')
                self.refresh_token = data['data'].get('refreshToken')
                self.feed_token = self.smart_api.getfeedToken()
                self.last_login = datetime.now(timezone.utc)
                self.session_expiry = self.last_login + timedelta(hours=6)
                
                logger.info(f"Angel One login successful. Session valid until {self.session_expiry}")
                
                # Start session refresh thread
                self._start_session_refresh()
                
                return True
            else:
                error_msg = data.get('message', 'Unknown error')
                logger.error(f"Angel One login failed: {error_msg}")
                logger.error(f"Full response: {data}")
                return False
                
        except Exception as e:
            logger.error(f"Angel One login exception: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _start_session_refresh(self):
        """Start background thread to refresh session before expiry"""
        if self._session_refresh_thread and self._session_refresh_thread.is_alive():
            return
        
        self._stop_refresh = False
        self._session_refresh_thread = threading.Thread(target=self._session_refresh_loop, daemon=True)
        self._session_refresh_thread.start()
        logger.info("Session refresh thread started")
    
    def _session_refresh_loop(self):
        """Background loop to refresh session every 5 hours"""
        while not self._stop_refresh:
            # Wait 5 hours (session lasts 6+ hours, refresh before expiry)
            for _ in range(5 * 60 * 60):  # 5 hours in seconds
                if self._stop_refresh:
                    return
                time.sleep(1)
            
            # Refresh session
            try:
                logger.info("Refreshing Angel One session...")
                if self.refresh_token:
                    # Try to use refresh token first
                    try:
                        profile = self.smart_api.getProfile(self.refresh_token)
                        if profile.get('status'):
                            logger.info("Session refreshed via profile check")
                            self.session_expiry = datetime.now(timezone.utc) + timedelta(hours=6)
                            continue
                    except:
                        pass
                
                # If refresh fails, do full re-login
                self.login()
            except Exception as e:
                logger.error(f"Session refresh failed: {e}")
    
    def ensure_session(self) -> bool:
        """Ensure we have a valid session, login if needed"""
        if self.smart_api and self.auth_token:
            # Check if session is still valid
            if self.session_expiry and datetime.now(timezone.utc) < self.session_expiry:
                return True
        
        # Need to login
        return self.login()
    
    def get_ltp(self, symbol: str, exchange: str = "NSE") -> Optional[Dict[str, Any]]:
        """Get Last Traded Price for a symbol"""
        if not self.ensure_session():
            return None
        
        try:
            token_info = SYMBOL_TOKENS.get(symbol)
            if not token_info:
                logger.warning(f"Symbol {symbol} not found in token mapping")
                return None
            
            token = token_info.get(f"{exchange.lower()}_token")
            if not token:
                token = token_info.get("nse_token")  # Fallback to NSE
            
            trading_symbol = f"{symbol}-EQ"
            
            # Use ltpData with longer timeout
            data = self.smart_api.ltpData(exchange, trading_symbol, token)
            
            if data.get('status') and data.get('data'):
                ltp_data = data['data']
                return {
                    "symbol": symbol,
                    "exchange": exchange,
                    "price": float(ltp_data.get('ltp', 0)),
                    "open": float(ltp_data.get('open', 0)),
                    "high": float(ltp_data.get('high', 0)),
                    "low": float(ltp_data.get('low', 0)),
                    "prev_close": float(ltp_data.get('close', 0)),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            else:
                logger.warning(f"LTP fetch failed for {symbol}: {data.get('message')}")
                return None
                
        except Exception as e:
            # Don't log full error for timeout - it's expected sometimes
            if 'timeout' in str(e).lower():
                logger.debug(f"Timeout fetching LTP for {symbol}")
            else:
                logger.error(f"Error fetching LTP for {symbol}: {e}")
            return None
    
    def get_quote(self, symbol: str, exchange: str = "NSE") -> Optional[Dict[str, Any]]:
        """Get full quote for a symbol"""
        ltp_data = self.get_ltp(symbol, exchange)
        if ltp_data:
            # Calculate change
            if ltp_data['prev_close'] > 0:
                change = ltp_data['price'] - ltp_data['prev_close']
                change_pct = (change / ltp_data['prev_close']) * 100
            else:
                change = 0
                change_pct = 0
            
            ltp_data['change'] = round(change, 2)
            ltp_data['change_pct'] = round(change_pct, 2)
            ltp_data['volume'] = 0  # Volume not available in LTP, would need full quote
            
        return ltp_data
    
    def get_index_quote(self, index_name: str) -> Optional[Dict[str, Any]]:
        """Get index quote (NIFTY, BANKNIFTY, etc.)"""
        if not self.ensure_session():
            return None
        
        try:
            index_info = INDEX_TOKENS.get(index_name)
            if not index_info:
                logger.warning(f"Index {index_name} not found")
                return None
            
            exchange = index_info['exchange']
            token = index_info['token']
            
            # Use getMarketData for faster batch-capable fetching
            data = self.smart_api.getMarketData(mode="LTP", exchangeTokens={
                exchange: [token]
            })
            
            if data.get('status') and data.get('data', {}).get('fetched'):
                ltp_data = data['data']['fetched'][0]
                value = float(ltp_data.get('ltp', 0))
                
                # Note: getMarketData doesn't return OHLC, so we just return LTP
                return {
                    "index": index_name,
                    "value": value,
                    "prev_close": None,  # Not available in LTP mode
                    "change": None,
                    "change_pct": None,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            else:
                logger.warning(f"Index quote failed for {index_name}: {data.get('message')}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching index {index_name}: {e}")
            return None
    
    def get_all_indices(self) -> List[Dict[str, Any]]:
        """Get all indices in one batch call - much faster"""
        if not self.ensure_session():
            return []
        
        try:
            # Build token lists by exchange
            nse_tokens = []
            bse_tokens = []
            
            for index_name, info in INDEX_TOKENS.items():
                if info['exchange'] == 'NSE':
                    nse_tokens.append(info['token'])
                else:
                    bse_tokens.append(info['token'])
            
            exchange_tokens = {}
            if nse_tokens:
                exchange_tokens['NSE'] = nse_tokens
            if bse_tokens:
                exchange_tokens['BSE'] = bse_tokens
            
            data = self.smart_api.getMarketData(mode="LTP", exchangeTokens=exchange_tokens)
            
            if data.get('status') and data.get('data', {}).get('fetched'):
                results = []
                fetched = data['data']['fetched']
                
                # Map tokens back to index names
                token_to_name = {info['token']: name for name, info in INDEX_TOKENS.items()}
                
                for item in fetched:
                    token = item.get('symbolToken')
                    index_name = token_to_name.get(token)
                    if index_name:
                        results.append({
                            "index": index_name,
                            "value": float(item.get('ltp', 0)),
                            "prev_close": None,
                            "change": None,
                            "change_pct": None,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "trading_symbol": item.get('tradingSymbol')
                        })
                
                return results
            
            return []
                
        except Exception as e:
            logger.error(f"Error fetching all indices: {e}")
            return []
    
    def get_multiple_stocks_batch(self, symbols: List[str], exchange: str = "NSE") -> List[Dict[str, Any]]:
        """Get multiple stock LTPs in one batch call"""
        if not self.ensure_session():
            return []
        
        try:
            tokens = []
            symbol_map = {}  # token -> symbol
            
            for symbol in symbols:
                token_info = SYMBOL_TOKENS.get(symbol)
                if token_info:
                    token = token_info.get(f"{exchange.lower()}_token") or token_info.get("nse_token")
                    if token:
                        tokens.append(token)
                        symbol_map[token] = symbol
            
            if not tokens:
                return []
            
            data = self.smart_api.getMarketData(mode="LTP", exchangeTokens={
                exchange: tokens
            })
            
            if data.get('status') and data.get('data', {}).get('fetched'):
                results = []
                
                for item in data['data']['fetched']:
                    token = item.get('symbolToken')
                    symbol = symbol_map.get(token)
                    if symbol:
                        results.append({
                            "symbol": symbol,
                            "exchange": exchange,
                            "price": float(item.get('ltp', 0)),
                            "open": None,
                            "high": None,
                            "low": None,
                            "prev_close": None,
                            "change": None,
                            "change_pct": None,
                            "volume": None,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "data_source": "angel_one_live"
                        })
                
                return results
            
            return []
                
        except Exception as e:
            logger.error(f"Error batch fetching stocks: {e}")
            return []
    
    def logout(self):
        """Logout and cleanup"""
        self._stop_refresh = True
        if self.smart_api:
            try:
                self.smart_api.terminateSession(self.client_id)
            except:
                pass
        self.smart_api = None
        self.auth_token = None
        self.refresh_token = None
        logger.info("Angel One session terminated")
    
    def get_session_status(self) -> Dict[str, Any]:
        """Get current session status"""
        return {
            "is_logged_in": self.auth_token is not None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "session_expiry": self.session_expiry.isoformat() if self.session_expiry else None,
            "time_remaining": str(self.session_expiry - datetime.now(timezone.utc)) if self.session_expiry else None
        }


# Global instance
angel_service = AngelOneService()


def get_angel_service() -> AngelOneService:
    """Get the global Angel One service instance"""
    return angel_service
