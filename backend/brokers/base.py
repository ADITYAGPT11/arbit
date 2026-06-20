"""
Abstract base class for broker providers.
Each broker (Angel One, Zerodha, Upstox, Fyers, ICICI Direct...) implements this contract.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List


@dataclass
class BrokerProfile:
    """User profile returned by the broker after auth"""
    broker_id: str
    client_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    exchanges: List[str] = field(default_factory=list)
    products: List[str] = field(default_factory=list)
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("raw", None)
        return d


@dataclass
class BrokerSession:
    """In-memory session for a user's broker connection."""
    user_id: str
    broker_id: str
    auth_token: str
    refresh_token: Optional[str] = None
    feed_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    profile: Optional[BrokerProfile] = None

    def is_valid(self) -> bool:
        if not self.auth_token:
            return False
        if self.expires_at and datetime.now(timezone.utc) >= self.expires_at:
            return False
        return True

    def to_public_dict(self) -> Dict[str, Any]:
        """Public-safe view (no tokens)"""
        return {
            "broker_id": self.broker_id,
            "is_connected": self.is_valid(),
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "profile": self.profile.to_dict() if self.profile else None,
        }


class BrokerProvider(ABC):
    """
    Abstract broker provider. Each broker subclasses this.

    The redirect/publisher-login flow is preferred where supported, so that
    end-users never share their MPIN / PIN / TOTP / password with our server.
    """

    broker_id: str = ""
    display_name: str = ""
    auth_type: str = "redirect"  # "redirect" | "credential" | "oauth2"
    logo_url: Optional[str] = None
    website: Optional[str] = None
    enabled: bool = True
    coming_soon: bool = False

    def info(self) -> Dict[str, Any]:
        """Static info shown in the UI broker selector."""
        return {
            "broker_id": self.broker_id,
            "display_name": self.display_name,
            "auth_type": self.auth_type,
            "logo_url": self.logo_url,
            "website": self.website,
            "enabled": self.enabled,
            "coming_soon": self.coming_soon,
            "platform_configured": self.is_platform_configured(),
        }

    @abstractmethod
    def is_platform_configured(self) -> bool:
        """Whether the platform-level credentials (API Key etc.) are available."""

    @abstractmethod
    def build_login_url(self, state: str) -> str:
        """Construct the broker's publisher-login / OAuth authorise URL."""

    @abstractmethod
    def handle_callback(self, params: Dict[str, Any]) -> BrokerSession:
        """
        Handle the redirect-back from the broker. `params` contains query-string args.
        Must return a BrokerSession (without user_id yet — caller fills that in).
        Raises ValueError / RuntimeError on failure.
        """

    def disconnect(self, session: BrokerSession) -> None:
        """Optional: tell the broker to invalidate the token. Default no-op."""
        return None

    # ---------- Optional data methods (override in concrete providers) ----------

    def get_ltp(self, session: BrokerSession, symbol: str, exchange: str = "NSE") -> Optional[Dict[str, Any]]:
        return None

    def get_quote(self, session: BrokerSession, symbol: str, exchange: str = "NSE") -> Optional[Dict[str, Any]]:
        return None
