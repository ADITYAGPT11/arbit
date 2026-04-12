"""
Angel One SmartAPI Integration Service
- Robust session management with auto-recovery
- Real-time market data for NSE/BSE
- Clear error reporting
"""

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import pyotp
from SmartApi import SmartConnect
import threading
import time

logger = logging.getLogger(__name__)

# Symbol token mapping for popular F&O stocks
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
    """Service for Angel One SmartAPI with robust session management"""
    
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
        
        # Load credentials
        self.api_key = os.environ.get('ANGEL_API_KEY', '').strip()
        self.client_id = os.environ.get('ANGEL_CLIENT_ID', '').strip()
        self.mpin = os.environ.get('ANGEL_MPIN', '').strip()
        self.totp_secret = os.environ.get('ANGEL_TOTP_SECRET', '').strip()
        
        # Session state
        self.smart_api = None
        self.auth_token = None
        self.refresh_token = None
        self.feed_token = None
        self.session_expiry = None
        self.last_login = None
        self.last_error = None
        self.login_attempts = 0
        self.max_login_attempts = 3
        
        # Validate credentials on init
        self._validate_credentials()
        
        self._initialized = True
        logger.info("AngelOneService initialized")
    
    def _validate_credentials(self):
        """Check if all credentials are present"""
        missing = []
        if not self.api_key:
            missing.append("ANGEL_API_KEY")
        if not self.client_id:
            missing.append("ANGEL_CLIENT_ID")
        if not self.mpin:
            missing.append("ANGEL_MPIN")
        if not self.totp_secret:
            missing.append("ANGEL_TOTP_SECRET")
        
        if missing:
            self.last_error = f"Missing credentials: {', '.join(missing)}"
            logger.error(self.last_error)
            return False
        
        # Check TOTP format
        try:
            clean_secret = self.totp_secret.replace(" ", "").upper()
            pyotp.TOTP(clean_secret).now()
        except Exception as e:
            self.last_error = f"Invalid TOTP secret format: {e}"
            logger.error(self.last_error)
            return False
        
        return True
    
    def _generate_totp(self) -> str:
        """Generate TOTP code"""
        try:
            clean_secret = self.totp_secret.replace(" ", "").upper()
            totp = pyotp.TOTP(clean_secret)
            code = totp.now()
            logger.debug(f"Generated TOTP: {code}")
            return code
        except Exception as e:
            self.last_error = f"TOTP generation failed: {e}"
            logger.error(self.last_error)
            return ""
    
    def login(self) -> bool:
        """Login to Angel One SmartAPI"""
        # Check if we've exceeded max attempts
        if self.login_attempts >= self.max_login_attempts:
            logger.warning(f"Max login attempts ({self.max_login_attempts}) exceeded. Please check credentials.")
            return False
        
        # Validate credentials first
        if not self._validate_credentials():
            return False
        
        self.login_attempts += 1
        
        try:
            logger.info(f"Attempting Angel One login for client: {self.client_id} (attempt {self.login_attempts})")
            
            self.smart_api = SmartConnect(api_key=self.api_key)
            totp = self._generate_totp()
            
            if not totp:
                return False
            
            data = self.smart_api.generateSession(self.client_id, self.mpin, totp)
            
            if data.get('status') and data.get('data'):
                self.auth_token = data['data'].get('jwtToken')
                self.refresh_token = data['data'].get('refreshToken')
                self.feed_token = self.smart_api.getfeedToken()
                self.last_login = datetime.now(timezone.utc)
                self.session_expiry = self.last_login + timedelta(hours=6)
                self.last_error = None
                self.login_attempts = 0  # Reset on success
                
                logger.info(f"Angel One login successful! Session valid until {self.session_expiry}")
                return True
            else:
                error_msg = data.get('message', 'Unknown error')
                self.last_error = f"Login failed: {error_msg}"
                logger.error(self.last_error)
                logger.error(f"Full response: {data}")
                return False
                
        except Exception as e:
            self.last_error = f"Login exception: {str(e)}"
            logger.error(self.last_error)
            return False
    
    def reset_login_attempts(self):
        """Reset login attempts counter - call this after updating credentials"""
        self.login_attempts = 0
        self.last_error = None
        # Reload credentials from env
        self.api_key = os.environ.get('ANGEL_API_KEY', '').strip()
        self.client_id = os.environ.get('ANGEL_CLIENT_ID', '').strip()
        self.mpin = os.environ.get('ANGEL_MPIN', '').strip()
        self.totp_secret = os.environ.get('ANGEL_TOTP_SECRET', '').strip()
        logger.info("Login attempts reset. Credentials reloaded.")
    
    def ensure_session(self) -> bool:
        """Ensure valid session exists"""
        if self.auth_token and self.session_expiry:
            if datetime.now(timezone.utc) < self.session_expiry:
                return True
        
        # Need to login
        return self.login()
    
    def is_connected(self) -> bool:
        """Check if we have a valid connection"""
        return self.auth_token is not None and self.session_expiry and datetime.now(timezone.utc) < self.session_expiry
    
    def get_ltp(self, symbol: str, exchange: str = "NSE") -> Optional[Dict[str, Any]]:
        """Get Last Traded Price for a symbol"""
        if not self.ensure_session():
            return None
        
        try:
            token_info = SYMBOL_TOKENS.get(symbol)
            if not token_info:
                return None
            
            token = token_info.get(f"{exchange.lower()}_token") or token_info.get("nse_token")
            trading_symbol = f"{symbol}-EQ"
            
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
            return None
                
        except Exception as e:
            logger.debug(f"LTP fetch error for {symbol}: {e}")
            return None
    
    def get_quote(self, symbol: str, exchange: str = "NSE") -> Optional[Dict[str, Any]]:
        """Get full quote with calculated change"""
        ltp_data = self.get_ltp(symbol, exchange)
        if ltp_data:
            prev = ltp_data.get('prev_close', 0)
            price = ltp_data.get('price', 0)
            if prev and prev > 0:
                ltp_data['change'] = round(price - prev, 2)
                ltp_data['change_pct'] = round(((price - prev) / prev) * 100, 2)
            else:
                ltp_data['change'] = 0
                ltp_data['change_pct'] = 0
            ltp_data['volume'] = 0
        return ltp_data
    
    def get_all_indices(self) -> List[Dict[str, Any]]:
        """Get all indices in one batch call"""
        if not self.ensure_session():
            return []
        
        try:
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
                token_to_name = {info['token']: name for name, info in INDEX_TOKENS.items()}
                
                for item in data['data']['fetched']:
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
            logger.error(f"Error fetching indices: {e}")
            return []
    
    def get_multiple_stocks_batch(self, symbols: List[str], exchange: str = "NSE") -> List[Dict[str, Any]]:
        """Get multiple stock LTPs in one batch call"""
        if not self.ensure_session():
            return []
        
        try:
            tokens = []
            symbol_map = {}
            
            for symbol in symbols:
                token_info = SYMBOL_TOKENS.get(symbol)
                if token_info:
                    token = token_info.get(f"{exchange.lower()}_token") or token_info.get("nse_token")
                    if token:
                        tokens.append(token)
                        symbol_map[token] = symbol
            
            if not tokens:
                return []
            
            data = self.smart_api.getMarketData(mode="LTP", exchangeTokens={exchange: tokens})
            
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
    
    def get_session_status(self) -> Dict[str, Any]:
        """Get detailed session status"""
        is_connected = self.is_connected()
        
        return {
            "is_connected": is_connected,
            "client_id": self.client_id[:4] + "***" if self.client_id else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "session_expiry": self.session_expiry.isoformat() if self.session_expiry else None,
            "time_remaining": str(self.session_expiry - datetime.now(timezone.utc)) if self.session_expiry and is_connected else None,
            "last_error": self.last_error,
            "login_attempts": self.login_attempts,
            "credentials_configured": all([self.api_key, self.client_id, self.mpin, self.totp_secret])
        }
    
    def logout(self):
        """Cleanup session"""
        if self.smart_api:
            try:
                self.smart_api.terminateSession(self.client_id)
            except:
                pass
        self.smart_api = None
        self.auth_token = None
        self.refresh_token = None
        logger.info("Angel One session terminated")


# Global instance
angel_service = AngelOneService()

def get_angel_service() -> AngelOneService:
    return angel_service
