"""
Test suite for Broker Status and Market Session features
Tests the new broker-status endpoint and related functionality
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBrokerStatusEndpoint:
    """Tests for GET /api/market/broker-status endpoint"""
    
    def test_broker_status_returns_200(self):
        """Verify broker-status endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/market/broker-status", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Broker status endpoint returns 200")
    
    def test_broker_status_has_broker_object(self):
        """Verify response contains broker connection state"""
        response = requests.get(f"{BASE_URL}/api/market/broker-status", timeout=30)
        data = response.json()
        
        assert "broker" in data, "Response missing 'broker' object"
        broker = data["broker"]
        
        # Check required broker fields
        assert "is_available" in broker, "Missing is_available field"
        assert "is_connected" in broker, "Missing is_connected field"
        assert "client_id" in broker, "Missing client_id field"
        assert "session_expiry" in broker, "Missing session_expiry field"
        assert "time_remaining" in broker, "Missing time_remaining field"
        assert "last_error" in broker, "Missing last_error field"
        assert "credentials_configured" in broker, "Missing credentials_configured field"
        
        print(f"✓ Broker object has all required fields")
        print(f"  - is_connected: {broker['is_connected']}")
        print(f"  - client_id: {broker['client_id']}")
    
    def test_broker_status_has_market_session_info(self):
        """Verify response contains market session information"""
        response = requests.get(f"{BASE_URL}/api/market/broker-status", timeout=30)
        data = response.json()
        
        assert "market" in data, "Response missing 'market' object"
        market = data["market"]
        
        # Check required market session fields
        assert "session" in market, "Missing session field"
        assert "session_label" in market, "Missing session_label field"
        assert "is_market_open" in market, "Missing is_market_open field"
        assert "is_trading_hours" in market, "Missing is_trading_hours field"
        assert "current_time_ist" in market, "Missing current_time_ist field"
        assert "next_event" in market, "Missing next_event field"
        assert "is_weekend" in market, "Missing is_weekend field"
        
        print(f"✓ Market session info has all required fields")
        print(f"  - session: {market['session']}")
        print(f"  - session_label: {market['session_label']}")
        print(f"  - is_market_open: {market['is_market_open']}")
        print(f"  - is_weekend: {market['is_weekend']}")
    
    def test_broker_status_has_data_mode(self):
        """Verify response contains data_mode indicator"""
        response = requests.get(f"{BASE_URL}/api/market/broker-status", timeout=30)
        data = response.json()
        
        assert "data_mode" in data, "Response missing 'data_mode' field"
        assert data["data_mode"] in ["live", "simulated"], f"Invalid data_mode: {data['data_mode']}"
        
        assert "use_live_data" in data, "Response missing 'use_live_data' field"
        assert isinstance(data["use_live_data"], bool), "use_live_data should be boolean"
        
        print(f"✓ Data mode indicator present: {data['data_mode']}")
    
    def test_weekend_market_session_label(self):
        """Verify weekend shows correct session label"""
        response = requests.get(f"{BASE_URL}/api/market/broker-status", timeout=30)
        data = response.json()
        market = data["market"]
        
        # If it's weekend, verify the label
        if market["is_weekend"]:
            assert "Weekend" in market["session_label"], f"Weekend label should contain 'Weekend', got: {market['session_label']}"
            assert market["session"] == "closed", f"Weekend session should be 'closed', got: {market['session']}"
            assert market["is_market_open"] == False, "Market should not be open on weekend"
            print(f"✓ Weekend session correctly shows: {market['session_label']}")
        else:
            print(f"✓ Not weekend - session: {market['session_label']}")


class TestAngelOneLoginEndpoint:
    """Tests for POST /api/market/angel-one/login endpoint"""
    
    def test_angel_one_login_endpoint_exists(self):
        """Verify angel-one login endpoint exists"""
        response = requests.post(f"{BASE_URL}/api/market/angel-one/login", timeout=30)
        # Should return 200 (success) or 401 (already logged in or failed)
        # Should NOT return 404
        assert response.status_code != 404, "Angel One login endpoint not found"
        print(f"✓ Angel One login endpoint exists (status: {response.status_code})")
    
    def test_angel_one_session_endpoint(self):
        """Verify angel-one session status endpoint"""
        response = requests.get(f"{BASE_URL}/api/market/angel-one/session", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "available" in data, "Missing 'available' field"
        assert "session_status" in data, "Missing 'session_status' field"
        
        print(f"✓ Angel One session endpoint working")
        print(f"  - available: {data['available']}")


class TestCrossExchangeArbitrage:
    """Tests for GET /api/arbitrage/cross-exchange endpoint"""
    
    def test_cross_exchange_returns_200(self):
        """Verify cross-exchange endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/arbitrage/cross-exchange", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Cross-exchange arbitrage endpoint returns 200")
    
    def test_cross_exchange_returns_live_data(self):
        """Verify cross-exchange returns data with data_source field"""
        response = requests.get(
            f"{BASE_URL}/api/arbitrage/cross-exchange?symbols=RELIANCE,TCS,INFY",
            timeout=60
        )
        data = response.json()
        
        assert isinstance(data, list), "Response should be a list"
        
        if len(data) > 0:
            opp = data[0]
            assert "symbol" in opp, "Missing symbol field"
            assert "nse_price" in opp, "Missing nse_price field"
            assert "bse_price" in opp, "Missing bse_price field"
            assert "spread_pct" in opp, "Missing spread_pct field"
            assert "data_source" in opp, "Missing data_source field"
            
            print(f"✓ Cross-exchange returns {len(data)} opportunities")
            print(f"  - First opportunity: {opp['symbol']} with {opp['spread_pct']}% spread")
            print(f"  - Data source: {opp['data_source']}")
        else:
            print("✓ Cross-exchange returns empty list (no opportunities)")


class TestMarketDataEndpoints:
    """Tests for market data endpoints"""
    
    def test_market_indices(self):
        """Verify market indices endpoint"""
        response = requests.get(f"{BASE_URL}/api/market/indices", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        if len(data) > 0:
            index = data[0]
            assert "index" in index, "Missing index field"
            print(f"✓ Market indices returns {len(data)} indices")
            for idx in data:
                print(f"  - {idx.get('index')}: {idx.get('value')}")
    
    def test_market_stocks(self):
        """Verify market stocks endpoint"""
        response = requests.get(f"{BASE_URL}/api/market/stocks", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Market stocks returns {len(data)} stocks")
    
    def test_data_source_status(self):
        """Verify data source status endpoint"""
        response = requests.get(f"{BASE_URL}/api/market/data-source", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "angel_one_available" in data, "Missing angel_one_available field"
        assert "use_live_data" in data, "Missing use_live_data field"
        
        print(f"✓ Data source status endpoint working")
        print(f"  - Angel One available: {data['angel_one_available']}")
        print(f"  - Use live data: {data['use_live_data']}")


class TestHealthEndpoints:
    """Tests for health check endpoints"""
    
    def test_root_endpoint(self):
        """Verify root API endpoint"""
        response = requests.get(f"{BASE_URL}/api/", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Root API endpoint working")
    
    def test_health_endpoint(self):
        """Verify health check endpoint"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("status") == "healthy", f"Expected healthy status, got: {data}"
        print("✓ Health endpoint returns healthy status")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
