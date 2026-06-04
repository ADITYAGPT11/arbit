"""
Option Chain API Tests
Tests for GET /api/options/underlyings, /api/options/expiries, /api/options/chain
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestOptionChainUnderlyings:
    """Tests for GET /api/options/underlyings endpoint"""
    
    def test_underlyings_returns_200(self):
        """Test that underlyings endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/options/underlyings", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/options/underlyings returns 200")
    
    def test_underlyings_returns_list(self):
        """Test that underlyings returns a list"""
        response = requests.get(f"{BASE_URL}/api/options/underlyings", timeout=30)
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) > 0, "Should have at least one underlying"
        print(f"✓ Underlyings returns list with {len(data)} items")
    
    def test_underlyings_contains_indices(self):
        """Test that underlyings contains major indices"""
        response = requests.get(f"{BASE_URL}/api/options/underlyings", timeout=30)
        data = response.json()
        names = [u['name'] for u in data]
        
        # Check for major indices
        assert "NIFTY" in names, "NIFTY should be in underlyings"
        assert "BANKNIFTY" in names, "BANKNIFTY should be in underlyings"
        print("✓ Underlyings contains NIFTY and BANKNIFTY")
    
    def test_underlyings_has_correct_structure(self):
        """Test that each underlying has required fields"""
        response = requests.get(f"{BASE_URL}/api/options/underlyings", timeout=30)
        data = response.json()
        
        for underlying in data[:5]:  # Check first 5
            assert "name" in underlying, "Underlying should have 'name'"
            assert "type" in underlying, "Underlying should have 'type'"
            assert "is_index" in underlying, "Underlying should have 'is_index'"
            assert "count" in underlying, "Underlying should have 'count'"
        print("✓ Underlyings have correct structure (name, type, is_index, count)")
    
    def test_underlyings_indices_first(self):
        """Test that indices appear before stocks"""
        response = requests.get(f"{BASE_URL}/api/options/underlyings", timeout=30)
        data = response.json()
        
        # First items should be indices
        first_5 = data[:5]
        for item in first_5:
            assert item['is_index'] == True, f"{item['name']} should be an index"
        print("✓ Indices appear first in the list")


class TestOptionChainExpiries:
    """Tests for GET /api/options/expiries endpoint"""
    
    def test_expiries_returns_200(self):
        """Test that expiries endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/options/expiries?underlying=NIFTY", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/options/expiries returns 200")
    
    def test_expiries_returns_list(self):
        """Test that expiries returns a list"""
        response = requests.get(f"{BASE_URL}/api/options/expiries?underlying=NIFTY", timeout=30)
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) > 0, "Should have at least one expiry"
        print(f"✓ Expiries returns list with {len(data)} items")
    
    def test_expiries_has_correct_structure(self):
        """Test that each expiry has required fields"""
        response = requests.get(f"{BASE_URL}/api/options/expiries?underlying=NIFTY", timeout=30)
        data = response.json()
        
        for expiry in data[:3]:  # Check first 3
            assert "expiry" in expiry, "Expiry should have 'expiry' field"
            assert "date" in expiry, "Expiry should have 'date' field"
            assert "timestamp" in expiry, "Expiry should have 'timestamp' field"
        print("✓ Expiries have correct structure (expiry, date, timestamp)")
    
    def test_expiries_sorted_by_date(self):
        """Test that expiries are sorted by date (nearest first)"""
        response = requests.get(f"{BASE_URL}/api/options/expiries?underlying=NIFTY", timeout=30)
        data = response.json()
        
        timestamps = [e['timestamp'] for e in data]
        assert timestamps == sorted(timestamps), "Expiries should be sorted by timestamp"
        print("✓ Expiries are sorted by date (nearest first)")
    
    def test_expiries_for_banknifty(self):
        """Test expiries for BANKNIFTY"""
        response = requests.get(f"{BASE_URL}/api/options/expiries?underlying=BANKNIFTY", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0, "BANKNIFTY should have expiries"
        print(f"✓ BANKNIFTY has {len(data)} expiries")


def get_first_nifty_expiry():
    """Helper to get the first available NIFTY expiry"""
    response = requests.get(f"{BASE_URL}/api/options/expiries?underlying=NIFTY", timeout=30)
    expiries = response.json()
    return expiries[0]['expiry'] if expiries else None


class TestOptionChain:
    """Tests for GET /api/options/chain endpoint"""
    
    def test_chain_returns_200(self):
        """Test that chain endpoint returns 200"""
        expiry = get_first_nifty_expiry()
        response = requests.get(
            f"{BASE_URL}/api/options/chain?underlying=NIFTY&expiry={expiry}&num_strikes=5",
            timeout=60
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/options/chain returns 200")
    
    def test_chain_has_required_fields(self):
        """Test that chain response has all required fields"""
        expiry = get_first_nifty_expiry()
        response = requests.get(
            f"{BASE_URL}/api/options/chain?underlying=NIFTY&expiry={expiry}&num_strikes=5",
            timeout=60
        )
        data = response.json()
        
        required_fields = ['underlying', 'expiry', 'spot_price', 'atm_strike', 'chain', 'totals']
        for field in required_fields:
            assert field in data, f"Response should have '{field}' field"
        print("✓ Chain response has all required fields")
    
    def test_chain_spot_price_valid(self):
        """Test that spot price is a valid positive number"""
        expiry = get_first_nifty_expiry()
        response = requests.get(
            f"{BASE_URL}/api/options/chain?underlying=NIFTY&expiry={expiry}&num_strikes=5",
            timeout=60
        )
        data = response.json()
        
        assert data['spot_price'] > 0, "Spot price should be positive"
        assert data['spot_price'] > 20000, "NIFTY spot should be > 20000"
        assert data['spot_price'] < 30000, "NIFTY spot should be < 30000"
        print(f"✓ Spot price is valid: {data['spot_price']}")
    
    def test_chain_atm_strike_near_spot(self):
        """Test that ATM strike is near spot price"""
        expiry = get_first_nifty_expiry()
        response = requests.get(
            f"{BASE_URL}/api/options/chain?underlying=NIFTY&expiry={expiry}&num_strikes=5",
            timeout=60
        )
        data = response.json()
        
        spot = data['spot_price']
        atm = data['atm_strike']
        diff = abs(spot - atm)
        
        # ATM should be within 50 points of spot (NIFTY strike step is 50)
        assert diff <= 50, f"ATM strike {atm} should be within 50 of spot {spot}"
        print(f"✓ ATM strike {atm} is near spot {spot} (diff: {diff})")
    
    def test_chain_has_ce_pe_data(self):
        """Test that chain rows have CE and PE data"""
        expiry = get_first_nifty_expiry()
        response = requests.get(
            f"{BASE_URL}/api/options/chain?underlying=NIFTY&expiry={expiry}&num_strikes=5",
            timeout=60
        )
        data = response.json()
        
        chain = data['chain']
        assert len(chain) > 0, "Chain should have rows"
        
        for row in chain:
            assert 'strike' in row, "Row should have strike"
            assert 'ce' in row, "Row should have CE data"
            assert 'pe' in row, "Row should have PE data"
        print(f"✓ Chain has {len(chain)} rows with CE and PE data")
    
    def test_chain_ce_pe_fields(self):
        """Test that CE/PE data has required fields (OI, volume, LTP, change)"""
        expiry = get_first_nifty_expiry()
        response = requests.get(
            f"{BASE_URL}/api/options/chain?underlying=NIFTY&expiry={expiry}&num_strikes=5",
            timeout=60
        )
        data = response.json()
        
        chain = data['chain']
        required_fields = ['oi', 'volume', 'ltp', 'change', 'iv']
        
        for row in chain[:3]:  # Check first 3 rows
            if row['ce']:
                for field in required_fields:
                    assert field in row['ce'], f"CE should have '{field}'"
            if row['pe']:
                for field in required_fields:
                    assert field in row['pe'], f"PE should have '{field}'"
        print("✓ CE/PE data has required fields (oi, volume, ltp, change, iv)")
    
    def test_chain_totals(self):
        """Test that chain has totals with PCR"""
        expiry = get_first_nifty_expiry()
        response = requests.get(
            f"{BASE_URL}/api/options/chain?underlying=NIFTY&expiry={expiry}&num_strikes=5",
            timeout=60
        )
        data = response.json()
        
        totals = data['totals']
        assert 'ce_oi' in totals, "Totals should have ce_oi"
        assert 'pe_oi' in totals, "Totals should have pe_oi"
        assert 'pcr' in totals, "Totals should have pcr"
        assert 'ce_volume' in totals, "Totals should have ce_volume"
        assert 'pe_volume' in totals, "Totals should have pe_volume"
        
        # PCR should be reasonable (between 0 and 10)
        pcr = totals['pcr']
        assert 0 <= pcr <= 10, f"PCR {pcr} should be between 0 and 10"
        print(f"✓ Totals present - CE OI: {totals['ce_oi']}, PE OI: {totals['pe_oi']}, PCR: {pcr}")
    
    def test_chain_atm_row_marked(self):
        """Test that ATM row is marked with is_atm=True"""
        expiry = get_first_nifty_expiry()
        response = requests.get(
            f"{BASE_URL}/api/options/chain?underlying=NIFTY&expiry={expiry}&num_strikes=5",
            timeout=60
        )
        data = response.json()
        
        chain = data['chain']
        atm_rows = [r for r in chain if r.get('is_atm')]
        
        assert len(atm_rows) == 1, "Should have exactly one ATM row"
        assert atm_rows[0]['strike'] == data['atm_strike'], "ATM row strike should match atm_strike"
        print(f"✓ ATM row correctly marked at strike {atm_rows[0]['strike']}")
    
    def test_chain_num_strikes_parameter(self):
        """Test that num_strikes parameter works"""
        expiry = get_first_nifty_expiry()
        response_5 = requests.get(
            f"{BASE_URL}/api/options/chain?underlying=NIFTY&expiry={expiry}&num_strikes=5",
            timeout=60
        )
        response_10 = requests.get(
            f"{BASE_URL}/api/options/chain?underlying=NIFTY&expiry={expiry}&num_strikes=10",
            timeout=60
        )
        
        chain_5 = response_5.json()['chain']
        chain_10 = response_10.json()['chain']
        
        # More strikes should return more rows
        assert len(chain_10) > len(chain_5), "num_strikes=10 should return more rows than num_strikes=5"
        print(f"✓ num_strikes parameter works: 5 strikes={len(chain_5)} rows, 10 strikes={len(chain_10)} rows")
    
    def test_chain_data_source(self):
        """Test that chain includes data_source field"""
        expiry = get_first_nifty_expiry()
        response = requests.get(
            f"{BASE_URL}/api/options/chain?underlying=NIFTY&expiry={expiry}&num_strikes=5",
            timeout=60
        )
        data = response.json()
        
        assert 'data_source' in data, "Response should have data_source field"
        # During market hours it should be 'angel_one_live', after hours could be 'no_market_data'
        valid_sources = ['angel_one_live', 'no_market_data']
        assert data['data_source'] in valid_sources, f"data_source should be one of {valid_sources}"
        print(f"✓ Data source: {data['data_source']}")


class TestOptionChainBanknifty:
    """Tests for BANKNIFTY option chain"""
    
    def test_banknifty_chain(self):
        """Test BANKNIFTY option chain"""
        # First get expiries
        exp_response = requests.get(f"{BASE_URL}/api/options/expiries?underlying=BANKNIFTY", timeout=30)
        expiries = exp_response.json()
        
        if len(expiries) > 0:
            first_expiry = expiries[0]['expiry']
            response = requests.get(
                f"{BASE_URL}/api/options/chain?underlying=BANKNIFTY&expiry={first_expiry}&num_strikes=5",
                timeout=60
            )
            assert response.status_code == 200
            data = response.json()
            
            assert data['underlying'] == 'BANKNIFTY'
            assert data['spot_price'] > 40000, "BANKNIFTY spot should be > 40000"
            assert data['strike_step'] == 100, "BANKNIFTY strike step should be 100"
            print(f"✓ BANKNIFTY chain works - Spot: {data['spot_price']}, ATM: {data['atm_strike']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
