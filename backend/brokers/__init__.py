"""
Brokers module — extensible registry for connecting users' broker accounts.

Design principles:
- No user credentials are persisted (DB or .env)
- Per-user broker sessions kept in-memory only
- OAuth-like / publisher-login redirect flows preferred over credential forms
- New brokers added by subclassing BrokerProvider and registering in registry.py
"""
from .base import BrokerProvider, BrokerSession, BrokerProfile
from .registry import BROKER_REGISTRY, get_broker, list_brokers
from .session_manager import session_manager

__all__ = [
    "BrokerProvider",
    "BrokerSession",
    "BrokerProfile",
    "BROKER_REGISTRY",
    "get_broker",
    "list_brokers",
    "session_manager",
]
