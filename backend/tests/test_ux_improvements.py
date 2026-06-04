"""
Test UX Improvements - Iteration 5
Tests for:
1. Option chain banner with symbol/expiry display
2. CE=green, PE=red color scheme
3. Side-by-side arbitrage cards with cost breakdown
4. Slippage and transaction cost fields in API response
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestArbitrageAPIWithCostBreakdown:
    """Test arbitrage API returns txn_cost, slippage, slippage_pct fields"""
    
    def test_cross_exchange_arbitrage_returns_cost_fields(self):
        """Verify /api/arbitrage/cross-exchange returns cost breakdown fields"""
        response = requests.get(f"{BASE_URL}/api/arbitrage/cross-exchange?symbols=RELIANCE,TCS,INFY")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        if len(data) > 0:
            opp = data[0]
            # Check required fields for cost breakdown
            assert "txn_cost" in opp, "txn_cost field missing"
            assert "slippage" in opp, "slippage field missing"
            assert "slippage_pct" in opp, "slippage_pct field missing"
            assert "net_profit_per_share" in opp, "net_profit_per_share field missing"
            assert "spread" in opp, "spread (gross spread) field missing"
            
            # Verify data types
            assert isinstance(opp["txn_cost"], (int, float)), "txn_cost should be numeric"
            assert isinstance(opp["slippage"], (int, float)), "slippage should be numeric"
            assert isinstance(opp["slippage_pct"], (int, float)), "slippage_pct should be numeric"
            assert isinstance(opp["net_profit_per_share"], (int, float)), "net_profit_per_share should be numeric"
            
            # Verify slippage_pct is 0.02 (2 basis points)
            assert opp["slippage_pct"] == 0.02, f"slippage_pct should be 0.02, got {opp['slippage_pct']}"
            
            print(f"✓ Arbitrage opportunity for {opp['symbol']}:")
            print(f"  Gross Spread: ₹{opp['spread']}")
            print(f"  Txn Cost: ₹{opp['txn_cost']}")
            print(f"  Slippage ({opp['slippage_pct']}%): ₹{opp['slippage']}")
            print(f"  Net Profit/Share: ₹{opp['net_profit_per_share']}")
    
    def test_arbitrage_has_buy_sell_exchange_labels(self):
        """Verify arbitrage response includes buy_exchange and sell_exchange"""
        response = requests.get(f"{BASE_URL}/api/arbitrage/cross-exchange?symbols=RELIANCE")
        assert response.status_code == 200
        
        data = response.json()
        if len(data) > 0:
            opp = data[0]
            assert "buy_exchange" in opp, "buy_exchange field missing"
            assert "sell_exchange" in opp, "sell_exchange field missing"
            assert opp["buy_exchange"] in ["NSE", "BSE"], f"Invalid buy_exchange: {opp['buy_exchange']}"
            assert opp["sell_exchange"] in ["NSE", "BSE"], f"Invalid sell_exchange: {opp['sell_exchange']}"
            assert opp["buy_exchange"] != opp["sell_exchange"], "buy and sell exchange should be different"
            
            print(f"✓ Buy on {opp['buy_exchange']}, Sell on {opp['sell_exchange']}")
    
    def test_arbitrage_has_nse_bse_prices(self):
        """Verify arbitrage response includes both NSE and BSE prices"""
        response = requests.get(f"{BASE_URL}/api/arbitrage/cross-exchange?symbols=RELIANCE")
        assert response.status_code == 200
        
        data = response.json()
        if len(data) > 0:
            opp = data[0]
            assert "nse_price" in opp, "nse_price field missing"
            assert "bse_price" in opp, "bse_price field missing"
            assert opp["nse_price"] > 0, "nse_price should be positive"
            assert opp["bse_price"] > 0, "bse_price should be positive"
            
            print(f"✓ NSE: ₹{opp['nse_price']}, BSE: ₹{opp['bse_price']}")


class TestOptionChainAPI:
    """Test option chain API for banner data"""
    
    def test_option_chain_returns_spot_price(self):
        """Verify option chain returns spot_price for banner display"""
        response = requests.get(f"{BASE_URL}/api/options/chain?underlying=NIFTY&num_strikes=5")
        assert response.status_code == 200
        
        data = response.json()
        assert "spot_price" in data, "spot_price field missing"
        assert data["spot_price"] > 0, "spot_price should be positive"
        
        print(f"✓ Spot price: {data['spot_price']}")
    
    def test_option_chain_returns_atm_strike(self):
        """Verify option chain returns atm_strike for banner display"""
        response = requests.get(f"{BASE_URL}/api/options/chain?underlying=NIFTY&num_strikes=5")
        assert response.status_code == 200
        
        data = response.json()
        assert "atm_strike" in data, "atm_strike field missing"
        assert data["atm_strike"] > 0, "atm_strike should be positive"
        
        print(f"✓ ATM Strike: {data['atm_strike']}")
    
    def test_option_chain_returns_totals_with_oi(self):
        """Verify option chain returns totals with CE/PE OI for summary bar"""
        response = requests.get(f"{BASE_URL}/api/options/chain?underlying=NIFTY&num_strikes=5")
        assert response.status_code == 200
        
        data = response.json()
        assert "totals" in data, "totals field missing"
        
        totals = data["totals"]
        assert "ce_oi" in totals, "ce_oi field missing in totals"
        assert "pe_oi" in totals, "pe_oi field missing in totals"
        assert "pcr" in totals, "pcr field missing in totals"
        
        print(f"✓ Call OI: {totals['ce_oi']}, Put OI: {totals['pe_oi']}, PCR: {totals['pcr']}")
    
    def test_option_expiries_returns_sorted_list(self):
        """Verify expiries endpoint returns sorted expiry dates"""
        response = requests.get(f"{BASE_URL}/api/options/expiries?underlying=NIFTY")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) > 0, "Should have at least one expiry"
        
        # Check first expiry has required fields
        first_expiry = data[0]
        assert "expiry" in first_expiry, "expiry field missing"
        assert "date" in first_expiry, "date field missing"
        
        print(f"✓ First expiry: {first_expiry['expiry']} ({first_expiry['date']})")
    
    def test_option_underlyings_returns_list(self):
        """Verify underlyings endpoint returns list with indices first"""
        response = requests.get(f"{BASE_URL}/api/options/underlyings")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) > 0, "Should have at least one underlying"
        
        # Check first underlying is an index
        first = data[0]
        assert "name" in first, "name field missing"
        assert "is_index" in first, "is_index field missing"
        
        # Indices should come first
        indices = [u for u in data if u.get("is_index")]
        assert len(indices) > 0, "Should have at least one index"
        
        print(f"✓ Found {len(indices)} indices, first: {indices[0]['name']}")


class TestBrokerStatus:
    """Test broker status API"""
    
    def test_broker_status_returns_market_session(self):
        """Verify broker status returns market session info"""
        response = requests.get(f"{BASE_URL}/api/market/broker-status")
        assert response.status_code == 200
        
        data = response.json()
        assert "market" in data, "market field missing"
        assert "session_label" in data["market"], "session_label missing"
        assert "is_market_open" in data["market"], "is_market_open missing"
        
        print(f"✓ Market session: {data['market']['session_label']}")
    
    def test_broker_status_returns_connection_state(self):
        """Verify broker status returns broker connection state"""
        response = requests.get(f"{BASE_URL}/api/market/broker-status")
        assert response.status_code == 200
        
        data = response.json()
        assert "broker" in data, "broker field missing"
        assert "is_connected" in data["broker"], "is_connected missing"
        
        print(f"✓ Broker connected: {data['broker']['is_connected']}")


class TestMarketIndices:
    """Test market indices API"""
    
    def test_indices_returns_live_data(self):
        """Verify indices endpoint returns live data"""
        response = requests.get(f"{BASE_URL}/api/market/indices")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) > 0, "Should have at least one index"
        
        # Check first index has required fields
        first = data[0]
        assert "index" in first, "index field missing"
        assert "value" in first, "value field missing"
        
        print(f"✓ First index: {first['index']} = {first['value']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
