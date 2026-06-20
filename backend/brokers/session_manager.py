"""
In-memory broker session manager.

* Keyed by (user_id, broker_id) — a user can connect multiple brokers concurrently.
* Sessions are NEVER persisted. Lost on backend restart by design.
* Also stores short-lived OAuth/redirect 'state' tokens to map callback → user.
"""
import logging
import secrets
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List, Tuple

from .base import BrokerSession

logger = logging.getLogger(__name__)


class BrokerSessionManager:
    def __init__(self) -> None:
        self._sessions: Dict[Tuple[str, str], BrokerSession] = {}
        # state_token -> (user_id, broker_id, created_at)
        self._states: Dict[str, Tuple[str, str, datetime]] = {}
        self._lock = threading.RLock()
        self.STATE_TTL = timedelta(minutes=10)

    # ------------------------- State (CSRF) tokens -------------------------

    def create_state(self, user_id: str, broker_id: str) -> str:
        state = secrets.token_urlsafe(24)
        with self._lock:
            self._cleanup_states_locked()
            self._states[state] = (user_id, broker_id, datetime.now(timezone.utc))
        return state

    def consume_state(self, state: str) -> Optional[Tuple[str, str]]:
        """Return (user_id, broker_id) if state is valid and not expired, else None.
        Consumes the state (one-time-use)."""
        with self._lock:
            entry = self._states.pop(state, None)
        if not entry:
            return None
        user_id, broker_id, created = entry
        if datetime.now(timezone.utc) - created > self.STATE_TTL:
            return None
        return user_id, broker_id

    def _cleanup_states_locked(self) -> None:
        now = datetime.now(timezone.utc)
        expired = [s for s, (_, _, t) in self._states.items() if now - t > self.STATE_TTL]
        for s in expired:
            self._states.pop(s, None)

    # ------------------------- Session storage -------------------------

    def set(self, session: BrokerSession) -> None:
        if not session.user_id or not session.broker_id:
            raise ValueError("BrokerSession requires user_id and broker_id")
        with self._lock:
            self._sessions[(session.user_id, session.broker_id)] = session
        logger.info(
            "Broker session stored: user=%s broker=%s expires_at=%s",
            session.user_id, session.broker_id, session.expires_at,
        )

    def get(self, user_id: str, broker_id: str) -> Optional[BrokerSession]:
        with self._lock:
            s = self._sessions.get((user_id, broker_id))
        if s and not s.is_valid():
            self.delete(user_id, broker_id)
            return None
        return s

    def delete(self, user_id: str, broker_id: str) -> None:
        with self._lock:
            self._sessions.pop((user_id, broker_id), None)

    def list_for_user(self, user_id: str) -> List[BrokerSession]:
        with self._lock:
            return [s for (uid, _), s in self._sessions.items() if uid == user_id]

    def any_active_for_broker(self, broker_id: str) -> Optional[BrokerSession]:
        """Used by market-data routes as a fallback: pick any logged-in user's session
        of a given broker. Useful for shared public data (LTP, quotes)."""
        with self._lock:
            for (_, bid), s in self._sessions.items():
                if bid == broker_id and s.is_valid():
                    return s
        return None


session_manager = BrokerSessionManager()
