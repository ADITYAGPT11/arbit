"""
Broker registry — add new brokers here.

To add a new broker (e.g. Zerodha):
  1. Implement /app/backend/brokers/zerodha.py with class ZerodhaProvider(BrokerProvider)
  2. Import it below and add to BROKER_REGISTRY
  3. Done — UI auto-discovers it via /api/brokers/list
"""
from typing import Dict, List

from .base import BrokerProvider
from .angel_one import AngelOneProvider


# Coming-soon placeholder providers (still extend BrokerProvider so UI shows them
# in the broker list with a "Coming soon" badge).
class _ComingSoonBroker(BrokerProvider):
    auth_type = "redirect"
    coming_soon = True
    enabled = False

    def is_platform_configured(self) -> bool:
        return False

    def build_login_url(self, state: str) -> str:
        raise NotImplementedError("This broker is coming soon")

    def handle_callback(self, params):
        raise NotImplementedError("This broker is coming soon")


class ZerodhaProvider(_ComingSoonBroker):
    broker_id = "zerodha"
    display_name = "Zerodha"
    website = "https://kite.zerodha.com"
    logo_url = "https://kite.zerodha.com/static/images/kite-logo.svg"


class UpstoxProvider(_ComingSoonBroker):
    broker_id = "upstox"
    display_name = "Upstox"
    website = "https://upstox.com"
    logo_url = "https://upstox.com/app/themes/upstox/dist/img/upstox-logo.svg"


class FyersProvider(_ComingSoonBroker):
    broker_id = "fyers"
    display_name = "Fyers"
    website = "https://fyers.in"


class IciciDirectProvider(_ComingSoonBroker):
    broker_id = "icici_direct"
    display_name = "ICICI Direct"
    website = "https://www.icicidirect.com"


# ---- Active registry ----
BROKER_REGISTRY: Dict[str, BrokerProvider] = {
    AngelOneProvider.broker_id: AngelOneProvider(),
    ZerodhaProvider.broker_id: ZerodhaProvider(),
    UpstoxProvider.broker_id: UpstoxProvider(),
    FyersProvider.broker_id: FyersProvider(),
    IciciDirectProvider.broker_id: IciciDirectProvider(),
}


def get_broker(broker_id: str) -> BrokerProvider:
    broker = BROKER_REGISTRY.get(broker_id)
    if not broker:
        raise KeyError(f"Unknown broker: {broker_id}")
    return broker


def list_brokers() -> List[Dict]:
    return [b.info() for b in BROKER_REGISTRY.values()]
