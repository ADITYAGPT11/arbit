"""
Backend tests for the new Brokers module (/api/brokers/*) and the
refactored /api/market/broker-status endpoint.

Scope (per review request):
 - Brokers registry shape & coming_soon flags
 - Auth gating on connect (401 when unauthenticated)
 - Callback redirect behaviour (missing state / invalid state)
 - Unknown broker handling (no 500)
 - Refactored Angel One service compatibility:
     * /api/market/broker-status returns 200 with expected fields
     * no "Direct login disabled" in last_error
 - In-memory state token mechanics (via brokers.session_manager)
"""

import os
import sys
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    # fallback to frontend env file (test runs inside container)
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().strip('"')
                    break
    except Exception:
        pass
BASE_URL = (BASE_URL or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not configured"

API = f"{BASE_URL}/api"


# ---------------- Fixtures ----------------

@pytest.fixture
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------------- /api/brokers/list ----------------

class TestBrokersList:
    """Public broker registry listing"""

    def test_list_unauthenticated_ok(self, client):
        r = client.get(f"{API}/brokers/list")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("available") is True, "BROKERS_MODULE_AVAILABLE should be true"
        assert data.get("authenticated") is False
        brokers = data.get("brokers")
        assert isinstance(brokers, list)
        assert len(brokers) == 5, f"Expected 5 brokers, got {len(brokers)}: {[b.get('broker_id') for b in brokers]}"

    def test_list_contains_expected_broker_ids(self, client):
        r = client.get(f"{API}/brokers/list")
        data = r.json()
        ids = {b["broker_id"] for b in data["brokers"]}
        assert ids == {"angel_one", "zerodha", "upstox", "fyers", "icici_direct"}, ids

    def test_angel_one_is_configured_and_others_coming_soon(self, client):
        r = client.get(f"{API}/brokers/list")
        by_id = {b["broker_id"]: b for b in r.json()["brokers"]}

        # Angel One: platform configured (ARBIT_ANGEL_API_KEY set), not coming_soon
        angel = by_id["angel_one"]
        assert angel["platform_configured"] is True
        assert angel.get("coming_soon") in (False, None)
        assert angel.get("enabled", True) is True
        assert angel["display_name"] == "Angel One"
        assert angel["auth_type"] == "redirect"

        # The other 4 must be coming_soon and not configured
        for bid in ("zerodha", "upstox", "fyers", "icici_direct"):
            b = by_id[bid]
            assert b["coming_soon"] is True, f"{bid} should be coming_soon"
            assert b["platform_configured"] is False, f"{bid} should not be platform_configured"

    def test_list_unauthenticated_is_connected_false_for_all(self, client):
        r = client.get(f"{API}/brokers/list")
        for b in r.json()["brokers"]:
            assert b["is_connected"] is False
            assert b["connected_at"] is None
            assert b["profile"] is None


# ---------------- /api/brokers/{broker_id}/connect ----------------

class TestBrokerConnectAuthGate:

    def test_connect_unauthenticated_requires_auth(self, client):
        r = client.post(f"{API}/brokers/angel_one/connect")
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"

    def test_coming_soon_broker_unauthenticated_returns_401_not_500(self, client):
        # Without auth the server can return 401 before checking coming_soon; what
        # matters is that it doesn't 500.
        r = client.post(f"{API}/brokers/zerodha/connect")
        assert r.status_code in (400, 401), r.status_code
        assert r.status_code != 500

    def test_connect_unknown_broker_no_500(self, client):
        r = client.post(f"{API}/brokers/unknown_id/connect")
        # Either 401 (auth first) or 404 (unknown) is acceptable; must not 500
        assert r.status_code in (401, 404), r.status_code
        assert r.status_code != 500

    def test_get_unknown_broker_connect_no_500(self, client):
        # GET on a POST route - FastAPI returns 405 Method Not Allowed (acceptable)
        r = client.get(f"{API}/brokers/unknown_id/connect")
        assert r.status_code in (401, 404, 405), r.status_code
        assert r.status_code != 500


# ---------------- /api/brokers/{broker_id}/callback ----------------

class TestBrokerCallback:
    """Callback is PUBLIC (no auth) — broker hits it after user login."""

    def test_callback_without_state_redirects_with_error(self, client):
        r = client.get(
            f"{API}/brokers/angel_one/callback",
            allow_redirects=False,
        )
        assert r.status_code == 302, f"Expected 302, got {r.status_code}: {r.text[:200]}"
        loc = r.headers.get("location", "")
        assert "/connect-broker" in loc, loc
        assert "status=error" in loc, loc
        # message=Missing+state+token  (urlencoded space = +)
        assert "Missing" in loc and "state" in loc.lower(), loc

    def test_callback_with_invalid_state_redirects_with_error(self, client):
        r = client.get(
            f"{API}/brokers/angel_one/callback",
            params={"state": "invalid_token_xyz"},
            allow_redirects=False,
        )
        assert r.status_code == 302, r.status_code
        loc = r.headers.get("location", "")
        assert "/connect-broker" in loc, loc
        assert "status=error" in loc, loc
        # urlencoded "State token expired or invalid"
        assert "State" in loc and ("expired" in loc.lower() or "invalid" in loc.lower()), loc

    def test_callback_unknown_broker_no_500(self, client):
        # Some bogus broker_id — should redirect with error, not 500.
        r = client.get(
            f"{API}/brokers/totally_fake/callback",
            params={"state": "anything"},
            allow_redirects=False,
        )
        # Without state mapping, expect 302 redirect (error)
        assert r.status_code in (302, 404), r.status_code
        assert r.status_code != 500


# ---------------- /api/market/broker-status (refactored legacy) ----------------

class TestBrokerStatus:
    """Refactored angel_one_service should remain backwards compatible."""

    def test_broker_status_200(self, client):
        r = client.get(f"{API}/market/broker-status")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "broker" in data
        assert "market" in data
        assert data["broker"]["broker"] == "angel_one"

    def test_credentials_configured_true(self, client):
        # ARBIT_ANGEL_API_KEY is set in .env
        r = client.get(f"{API}/market/broker-status")
        broker = r.json()["broker"]
        assert broker["credentials_configured"] is True, broker

    def test_is_connected_false_no_sessions(self, client):
        r = client.get(f"{API}/market/broker-status")
        broker = r.json()["broker"]
        assert broker["is_connected"] is False, broker

    def test_last_error_does_not_contain_direct_login_disabled(self, client):
        r = client.get(f"{API}/market/broker-status")
        broker = r.json()["broker"]
        last_err = (broker.get("last_error") or "")
        assert "Direct login disabled" not in last_err, f"Found stale message: {last_err}"


# ---------------- In-memory state machine (unit test via import) ----------------

class TestSessionManagerStateMachine:
    """Verify the in-memory state machine without going through HTTP."""

    @pytest.fixture(autouse=True)
    def _import_module(self):
        sys.path.insert(0, "/app/backend")
        from brokers.session_manager import BrokerSessionManager  # noqa
        self.BrokerSessionManager = BrokerSessionManager

    def test_create_then_consume_state(self):
        sm = self.BrokerSessionManager()
        state = sm.create_state(user_id="u1", broker_id="angel_one")
        assert isinstance(state, str) and len(state) > 10
        result = sm.consume_state(state)
        assert result == ("u1", "angel_one")
        # State is one-time-use
        assert sm.consume_state(state) is None

    def test_consume_invalid_state_returns_none(self):
        sm = self.BrokerSessionManager()
        assert sm.consume_state("bogus") is None

    def test_state_expiry(self):
        from datetime import timedelta
        sm = self.BrokerSessionManager()
        sm.STATE_TTL = timedelta(seconds=-1)  # already-expired tokens
        state = sm.create_state(user_id="u2", broker_id="angel_one")
        assert sm.consume_state(state) is None
