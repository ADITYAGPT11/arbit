"""
Option Chain Service for Angel One SmartAPI
- Downloads and caches instrument master
- Builds T-shaped option chain with live data
- Supports NIFTY, BANKNIFTY, FINNIFTY and stock options
"""

import os
import logging
import requests
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

INSTRUMENT_MASTER_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"

# Strike step size per underlying
STRIKE_STEPS = {
    "NIFTY": 50,
    "BANKNIFTY": 100,
    "FINNIFTY": 50,
    "MIDCPNIFTY": 25,
    "SENSEX": 100,
    "NIFTYNXT50": 50,
}

# Default strike step for stock options
DEFAULT_STRIKE_STEP = 50

# Index underlyings supported
INDEX_UNDERLYINGS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50"]


class OptionChainService:
    """Service to build option chain data from Angel One"""

    _instance = None
    _instruments: List[Dict] = []
    _last_download: float = 0
    _cache_ttl = 3600  # Re-download master every 1 hour

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _ensure_instruments(self):
        """Download instrument master if not cached or stale"""
        now = time.time()
        if self._instruments and (now - self._last_download) < self._cache_ttl:
            return

        try:
            logger.info("Downloading instrument master from Angel One...")
            resp = requests.get(INSTRUMENT_MASTER_URL, timeout=30)
            resp.raise_for_status()
            self._instruments = resp.json()
            self._last_download = now
            logger.info(f"Instrument master loaded: {len(self._instruments)} instruments")
        except Exception as e:
            logger.error(f"Failed to download instrument master: {e}")
            if not self._instruments:
                self._instruments = []

    def get_underlyings(self) -> List[Dict[str, Any]]:
        """Get list of available underlyings for option chain"""
        self._ensure_instruments()

        underlyings = {}
        for inst in self._instruments:
            if inst.get("exch_seg") == "NFO" and inst.get("instrumenttype") in ("OPTIDX", "OPTSTK"):
                name = inst.get("name", "")
                if name not in underlyings:
                    underlyings[name] = {"name": name, "type": inst["instrumenttype"], "count": 0}
                underlyings[name]["count"] += 1

        # Sort: indices first, then stocks
        result = []
        for u in INDEX_UNDERLYINGS:
            if u in underlyings:
                result.append({**underlyings[u], "is_index": True})

        stock_opts = sorted(
            [v for k, v in underlyings.items() if k not in INDEX_UNDERLYINGS and v["count"] >= 50],
            key=lambda x: x["name"],
        )
        for s in stock_opts:
            result.append({**s, "is_index": False})

        return result

    def get_expiries(self, underlying: str) -> List[Dict[str, Any]]:
        """Get available expiry dates for an underlying"""
        self._ensure_instruments()

        inst_type = "OPTIDX" if underlying in INDEX_UNDERLYINGS else "OPTSTK"
        expiries_raw = set()

        for inst in self._instruments:
            if (
                inst.get("exch_seg") == "NFO"
                and inst.get("name") == underlying
                and inst.get("instrumenttype") == inst_type
            ):
                exp = inst.get("expiry", "")
                if exp:
                    expiries_raw.add(exp)

        # Parse and sort by actual date
        parsed = []
        for exp_str in expiries_raw:
            try:
                dt = datetime.strptime(exp_str, "%d%b%Y")
                parsed.append({"expiry": exp_str, "date": dt.strftime("%Y-%m-%d"), "timestamp": dt.timestamp()})
            except ValueError:
                parsed.append({"expiry": exp_str, "date": exp_str, "timestamp": 0})

        parsed.sort(key=lambda x: x["timestamp"])
        return parsed

    def _get_option_instruments(
        self, underlying: str, expiry: str
    ) -> Tuple[Dict[float, Dict], Dict[float, Dict]]:
        """Get CE and PE instrument maps for a given underlying and expiry"""
        self._ensure_instruments()

        inst_type = "OPTIDX" if underlying in INDEX_UNDERLYINGS else "OPTSTK"
        ce_map = {}  # strike -> instrument
        pe_map = {}

        for inst in self._instruments:
            if (
                inst.get("exch_seg") == "NFO"
                and inst.get("name") == underlying
                and inst.get("expiry") == expiry
                and inst.get("instrumenttype") == inst_type
            ):
                strike = float(inst.get("strike", 0)) / 100  # Convert from paise
                symbol = inst.get("symbol", "")

                if symbol.endswith("CE"):
                    ce_map[strike] = inst
                elif symbol.endswith("PE"):
                    pe_map[strike] = inst

        return ce_map, pe_map

    def build_option_chain(
        self,
        angel_service,
        underlying: str,
        expiry: str,
        spot_price: float,
        num_strikes: int = 15,
    ) -> Dict[str, Any]:
        """Build T-shaped option chain with live data from Angel One"""

        ce_map, pe_map = self._get_option_instruments(underlying, expiry)

        if not ce_map and not pe_map:
            return {"error": f"No options found for {underlying} expiry {expiry}", "chain": []}

        # Determine strike step
        strike_step = STRIKE_STEPS.get(underlying, DEFAULT_STRIKE_STEP)

        # Calculate ATM strike
        atm_strike = round(spot_price / strike_step) * strike_step

        # Get all unique strikes sorted
        all_strikes = sorted(set(list(ce_map.keys()) + list(pe_map.keys())))

        # Find strikes around ATM
        if atm_strike in all_strikes:
            atm_idx = all_strikes.index(atm_strike)
        else:
            # Find nearest
            atm_idx = min(range(len(all_strikes)), key=lambda i: abs(all_strikes[i] - atm_strike))
            atm_strike = all_strikes[atm_idx]

        start_idx = max(0, atm_idx - num_strikes)
        end_idx = min(len(all_strikes), atm_idx + num_strikes + 1)
        selected_strikes = all_strikes[start_idx:end_idx]

        # Collect tokens for batch fetching
        tokens_to_fetch = []  # (token, strike, option_type)
        token_map = {}

        for strike in selected_strikes:
            if strike in ce_map:
                token = ce_map[strike]["token"]
                tokens_to_fetch.append(token)
                token_map[token] = {"strike": strike, "type": "CE", "symbol": ce_map[strike]["symbol"]}
            if strike in pe_map:
                token = pe_map[strike]["token"]
                tokens_to_fetch.append(token)
                token_map[token] = {"strike": strike, "type": "PE", "symbol": pe_map[strike]["symbol"]}

        # Fetch market data in batches (max 50 tokens per request)
        market_data = {}
        batch_size = 50

        if angel_service and angel_service.is_connected():
            for i in range(0, len(tokens_to_fetch), batch_size):
                batch_tokens = tokens_to_fetch[i : i + batch_size]
                try:
                    data = angel_service.smart_api.getMarketData(
                        mode="FULL", exchangeTokens={"NFO": batch_tokens}
                    )
                    if data.get("status") and data.get("data", {}).get("fetched"):
                        for item in data["data"]["fetched"]:
                            tok = item.get("symbolToken")
                            if tok in token_map:
                                market_data[tok] = item
                except Exception as e:
                    logger.error(f"Option chain batch fetch error: {e}")

        # Build chain rows
        chain = []
        for strike in selected_strikes:
            row = {
                "strike": strike,
                "is_atm": strike == atm_strike,
                "is_itm_ce": strike < spot_price,
                "is_itm_pe": strike > spot_price,
                "ce": None,
                "pe": None,
            }

            # CE data
            if strike in ce_map:
                ce_token = ce_map[strike]["token"]
                ce_data = market_data.get(ce_token, {})
                row["ce"] = {
                    "symbol": ce_map[strike]["symbol"],
                    "token": ce_token,
                    "ltp": float(ce_data.get("ltp", 0)),
                    "change": float(ce_data.get("netChange", 0)),
                    "change_pct": float(ce_data.get("percentChange", 0)),
                    "oi": int(ce_data.get("opnInterest", 0)),
                    "oi_change": int(ce_data.get("oiDayChange", 0)) if ce_data.get("oiDayChange") else 0,
                    "volume": int(ce_data.get("tradeVolume", 0)),
                    "iv": float(ce_data.get("impliedVolatility", 0)) if ce_data.get("impliedVolatility") else 0,
                    "bid": float(ce_data.get("best5BuyData", [{}])[0].get("price", 0)) if ce_data.get("best5BuyData") else 0,
                    "ask": float(ce_data.get("best5SellData", [{}])[0].get("price", 0)) if ce_data.get("best5SellData") else 0,
                    "high": float(ce_data.get("high", 0)),
                    "low": float(ce_data.get("low", 0)),
                    "lot_size": int(ce_map[strike].get("lotsize", 0)),
                }

            # PE data
            if strike in pe_map:
                pe_token = pe_map[strike]["token"]
                pe_data = market_data.get(pe_token, {})
                row["pe"] = {
                    "symbol": pe_map[strike]["symbol"],
                    "token": pe_token,
                    "ltp": float(pe_data.get("ltp", 0)),
                    "change": float(pe_data.get("netChange", 0)),
                    "change_pct": float(pe_data.get("percentChange", 0)),
                    "oi": int(pe_data.get("opnInterest", 0)),
                    "oi_change": int(pe_data.get("oiDayChange", 0)) if pe_data.get("oiDayChange") else 0,
                    "volume": int(pe_data.get("tradeVolume", 0)),
                    "iv": float(pe_data.get("impliedVolatility", 0)) if pe_data.get("impliedVolatility") else 0,
                    "bid": float(pe_data.get("best5BuyData", [{}])[0].get("price", 0)) if pe_data.get("best5BuyData") else 0,
                    "ask": float(pe_data.get("best5SellData", [{}])[0].get("price", 0)) if pe_data.get("best5SellData") else 0,
                    "high": float(pe_data.get("high", 0)),
                    "low": float(pe_data.get("low", 0)),
                    "lot_size": int(pe_map[strike].get("lotsize", 0)),
                }

            chain.append(row)

        # Compute totals
        total_ce_oi = sum(r["ce"]["oi"] for r in chain if r["ce"])
        total_pe_oi = sum(r["pe"]["oi"] for r in chain if r["pe"])
        total_ce_vol = sum(r["ce"]["volume"] for r in chain if r["ce"])
        total_pe_vol = sum(r["pe"]["volume"] for r in chain if r["pe"])
        pcr = round(total_pe_oi / total_ce_oi, 2) if total_ce_oi > 0 else 0

        return {
            "underlying": underlying,
            "expiry": expiry,
            "spot_price": spot_price,
            "atm_strike": atm_strike,
            "strike_step": strike_step,
            "chain": chain,
            "totals": {
                "ce_oi": total_ce_oi,
                "pe_oi": total_pe_oi,
                "ce_volume": total_ce_vol,
                "pe_volume": total_pe_vol,
                "pcr": pcr,
            },
            "data_source": "angel_one_live" if market_data else "no_market_data",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Singleton
option_chain_service = OptionChainService()


def get_option_chain_service() -> OptionChainService:
    return option_chain_service
