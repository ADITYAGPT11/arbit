"""Telegram Service — sends alerts via Telegram Bot API."""

import logging
from datetime import datetime, timezone
from typing import Dict, Any

import httpx

logger = logging.getLogger(__name__)


class TelegramService:
    """Send alerts via Telegram."""

    @staticmethod
    async def send_alert(chat_id: str, message: str, bot_token: str) -> bool:
        """Send Telegram message."""
        if not bot_token or not chat_id:
            logger.warning("Telegram not configured")
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Telegram error: {e}")
            return False

    @staticmethod
    def format_arbitrage_alert(opportunity: Dict) -> str:
        """Format arbitrage opportunity as Telegram message."""
        buy_exchange = opportunity.get('buy_exchange', 'N/A')
        buy_key = 'nse_price' if buy_exchange == 'NSE' else 'bse_price'
        sell_key = 'bse_price' if buy_exchange == 'NSE' else 'nse_price'

        return (
            f"🚨 <b>Arbitrage Alert!</b>\n\n"
            f"<b>Type:</b> {opportunity.get('type', 'Unknown')}\n"
            f"<b>Symbol:</b> {opportunity.get('symbol', 'N/A')}\n"
            f"<b>Spread:</b> {opportunity.get('spread_pct', 0):.2f}%\n"
            f"<b>Net Profit:</b> ₹{opportunity.get('net_profit_per_share', 0):.2f}/share\n\n"
            f"<b>Action:</b>\n"
            f"Buy on {buy_exchange} @ ₹{opportunity.get(buy_key, 0):.2f}\n"
            f"Sell on {opportunity.get('sell_exchange', 'N/A')} @ ₹{opportunity.get(sell_key, 0):.2f}\n\n"
            f"⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )
