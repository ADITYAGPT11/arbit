"""
Option Chain Service for Angel One SmartAPI
- Downloads and caches instrument master with indexed lookups
- Builds T-shaped option chain with live data via batch API
- Optimized for low-latency repeated polling
"""

import logging
import requests
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)

INSTRUMENT_MASTER_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"

STRIKE_STEPS = {
    "NIFTY": 50, "BANKNIFTY": 100, "FINNIFTY": 50,
    "MIDCPNIFTY": 25, "SENSEX": 100, "NIFTYNXT50": 50,
}
DEFAULT_STRIKE_STEP = 50
INDEX_UNDERLYINGS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50"]


class OptionChainService:
    """Singleton service with indexed instrument master for fast option chain builds"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._instruments_raw = []
            cls._instance._last_download = 0.0
            cls._instance._cache_ttl = 3600
            # Indexed structures (built once per download)
            cls._instance._nfo_by_name: Dict[str, List[Dict]] = defaultdict(list)
            cls._instance._underlyings_cache = None
            cls._instance._expiries_cache: Dict[str, List] = {}
            # Response cache for option chain (short TTL for HFT polling)
            cls._instance._chain_cache: Dict[str, Tuple[float, Dict]] = {}
            cls._instance._chain_cache_ttl = 2.0  # 2 second cache
        return cls._instance

    def _ensure_instruments(self):
        """Download instrument master if stale, then index it"""
        now = time.time()
        if self._instruments_raw and (now - self._last_download) < self._cache_ttl:
            return

        try:
            logger.info("Downloading instrument master from Angel One...")
            resp = requests.get(INSTRUMENT_MASTER_URL, timeout=30)
            resp.raise_for_status()
            self._instruments_raw = resp.json()
            self._last_download = now
            logger.info(f"Instrument master loaded: {len(self._instruments_raw)} instruments")
            self._build_index()
        except Exception as e:
            logger.error(f"Failed to download instrument master: {e}")

    def _build_index(self):
        """Build indexed lookup structures for O(1) access"""
        self._nfo_by_name.clear()
        self._underlyings_cache = None
        self._expiries_cache.clear()
        self._chain_cache.clear()

        for inst in self._instruments_raw:
            if inst.get("exch_seg") == "NFO" and inst.get("instrumenttype") in ("OPTIDX", "OPTSTK"):
                name = inst.get("name", "")
                self._nfo_by_name[name].append(inst)

        logger.info(f"Indexed {len(self._nfo_by_name)} underlyings for option chain")

    def get_underlyings(self) -> List[Dict[str, Any]]:
        """Get available underlyings — cached after first build"""
        self._ensure_instruments()

        if self._underlyings_cache is not None:
            return self._underlyings_cache

        result = []
        for u in INDEX_UNDERLYINGS:
            if u in self._nfo_by_name:
                result.append({"name": u, "type": "OPTIDX", "is_index": True, "count": len(self._nfo_by_name[u])})

        stock_opts = sorted(
            [
                {"name": k, "type": "OPTSTK", "is_index": False, "count": len(v)}
                for k, v in self._nfo_by_name.items()
                if k not in INDEX_UNDERLYINGS and len(v) >= 50
            ],
            key=lambda x: x["name"],
        )
        result.extend(stock_opts)
        self._underlyings_cache = result
        return result

    def get_expiries(self, underlying: str) -> List[Dict[str, Any]]:
        """Get sorted expiry dates — cached per underlying"""
        self._ensure_instruments()

        if underlying in self._expiries_cache:
            return self._expiries_cache[underlying]

        expiries_raw = set()
        for inst in self._nfo_by_name.get(underlying, []):
            exp = inst.get("expiry", "")
            if exp:
                expiries_raw.add(exp)

        parsed = []
        for exp_str in expiries_raw:
            try:
                dt = datetime.strptime(exp_str, "%d%b%Y")
                parsed.append({"expiry": exp_str, "date": dt.strftime("%Y-%m-%d"), "timestamp": dt.timestamp()})
            except ValueError:
                parsed.append({"expiry": exp_str, "date": exp_str, "timestamp": 0})

        parsed.sort(key=lambda x: x["timestamp"])
        self._expiries_cache[underlying] = parsed
        return parsed

    def _get_option_instruments(self, underlying: str, expiry: str) -> Tuple[Dict[float, Dict], Dict[float, Dict]]:
        """Get CE and PE instrument maps — O(n) over filtered subset only"""
        self._ensure_instruments()
        ce_map = {}
        pe_map = {}

        for inst in self._nfo_by_name.get(underlying, []):
            if inst.get("expiry") != expiry:
                continue
            strike = float(inst.get("strike", 0)) / 100
            symbol = inst.get("symbol", "")
            if symbol.endswith("CE"):
                ce_map[strike] = inst
            elif symbol.endswith("PE"):
                pe_map[strike] = inst

        return ce_map, pe_map

    @staticmethod
    def _extract_option_data(inst: Dict, market_item: Dict) -> Dict[str, Any]:
        """Extract standardized option data from instrument + market data"""
        bid = 0
        ask = 0
        buy_data = market_item.get("best5BuyData")
        sell_data = market_item.get("best5SellData")
        if buy_data and len(buy_data) > 0:
            bid = float(buy_data[0].get("price", 0))
        if sell_data and len(sell_data) > 0:
            ask = float(sell_data[0].get("price", 0))

        return {
            "symbol": inst.get("symbol", ""),
            "token": inst.get("token", ""),
            "ltp": float(market_item.get("ltp", 0)),
            "change": float(market_item.get("netChange", 0)),
            "change_pct": float(market_item.get("percentChange", 0)),
            "oi": int(market_item.get("opnInterest", 0)),
            "oi_change": int(market_item.get("oiDayChange", 0)) if market_item.get("oiDayChange") else 0,
            "volume": int(market_item.get("tradeVolume", 0)),
            "iv": float(market_item.get("impliedVolatility", 0)) if market_item.get("impliedVolatility") else 0,
            "bid": bid,
            "ask": ask,
            "high": float(market_item.get("high", 0)),
            "low": float(market_item.get("low", 0)),
            "lot_size": int(inst.get("lotsize", 0)),
        }

    def build_option_chain(
        self, angel_service, underlying: str, expiry: str, spot_price: float, num_strikes: int = 15,
    ) -> Dict[str, Any]:
        """Build T-shaped option chain. Returns cached result if within TTL."""

        cache_key = f"{underlying}:{expiry}:{num_strikes}"
        now = time.time()
        if cache_key in self._chain_cache:
            ts, cached = self._chain_cache[cache_key]
            if (now - ts) < self._chain_cache_ttl:
                return cached

        ce_map, pe_map = self._get_option_instruments(underlying, expiry)
        if not ce_map and not pe_map:
            return {"error": f"No options found for {underlying} expiry {expiry}", "chain": []}

        strike_step = STRIKE_STEPS.get(underlying, DEFAULT_STRIKE_STEP)
        atm_strike = round(spot_price / strike_step) * strike_step
        all_strikes = sorted(set(list(ce_map.keys()) + list(pe_map.keys())))

        # Find ATM index
        if atm_strike in all_strikes:
            atm_idx = all_strikes.index(atm_strike)
        else:
            atm_idx = min(range(len(all_strikes)), key=lambda i: abs(all_strikes[i] - atm_strike))
            atm_strike = all_strikes[atm_idx]

        start_idx = max(0, atm_idx - num_strikes)
        end_idx = min(len(all_strikes), atm_idx + num_strikes + 1)
        selected_strikes = all_strikes[start_idx:end_idx]

        # Collect tokens for batch fetch
        tokens_to_fetch = []
        token_map = {}
        for strike in selected_strikes:
            if strike in ce_map:
                t = ce_map[strike]["token"]
                tokens_to_fetch.append(t)
                token_map[t] = ("CE", strike)
            if strike in pe_map:
                t = pe_map[strike]["token"]
                tokens_to_fetch.append(t)
                token_map[t] = ("PE", strike)

        # Batch fetch market data (max 50 per request)
        market_data = {}
        batch_size = 50
        if angel_service and angel_service.is_connected():
            for i in range(0, len(tokens_to_fetch), batch_size):
                batch = tokens_to_fetch[i : i + batch_size]
                try:
                    data = angel_service.smart_api.getMarketData(mode="FULL", exchangeTokens={"NFO": batch})
                    if data.get("status") and data.get("data", {}).get("fetched"):
                        for item in data["data"]["fetched"]:
                            tok = item.get("symbolToken")
                            if tok in token_map:
                                market_data[tok] = item
                except Exception as e:
                    logger.error(f"Option chain batch fetch error: {e}")

        # Build chain rows
        chain = []
        total_ce_oi = total_pe_oi = total_ce_vol = total_pe_vol = 0

        for strike in selected_strikes:
            row = {
                "strike": strike,
                "is_atm": strike == atm_strike,
                "is_itm_ce": strike < spot_price,
                "is_itm_pe": strike > spot_price,
                "ce": None,
                "pe": None,
            }

            if strike in ce_map:
                ce_token = ce_map[strike]["token"]
                md = market_data.get(ce_token, {})
                row["ce"] = self._extract_option_data(ce_map[strike], md)
                total_ce_oi += row["ce"]["oi"]
                total_ce_vol += row["ce"]["volume"]

            if strike in pe_map:
                pe_token = pe_map[strike]["token"]
                md = market_data.get(pe_token, {})
                row["pe"] = self._extract_option_data(pe_map[strike], md)
                total_pe_oi += row["pe"]["oi"]
                total_pe_vol += row["pe"]["volume"]

            chain.append(row)

        pcr = round(total_pe_oi / total_ce_oi, 2) if total_ce_oi > 0 else 0

        result = {
            "underlying": underlying,
            "expiry": expiry,
            "spot_price": spot_price,
            "atm_strike": atm_strike,
            "strike_step": strike_step,
            "chain": chain,
            "totals": {
                "ce_oi": total_ce_oi, "pe_oi": total_pe_oi,
                "ce_volume": total_ce_vol, "pe_volume": total_pe_vol,
                "pcr": pcr,
            },
            "data_source": "angel_one_live" if market_data else "no_market_data",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._chain_cache[cache_key] = (now, result)
        return result


option_chain_service = OptionChainService()

def get_option_chain_service() -> OptionChainService:
    return option_chain_service
