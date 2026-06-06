"""
IV Analytics API Tests
Tests for IV Dashboard, IV Skew, Max Pain, and Seller Signal endpoints
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestIVDashboard:
    """Tests for GET /api/iv/dashboard endpoint"""
    
    def test_iv_dashboard_returns_200(self):
        """IV dashboard endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/iv/dashboard?underlying=NIFTY", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: IV dashboard returns 200")
    
    def test_iv_dashboard_has_required_fields(self):
        """IV dashboard should return all required fields"""
        response = requests.get(f"{BASE_URL}/api/iv/dashboard?underlying=NIFTY", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        required_fields = [
            "underlying", "expiry", "days_to_expiry", "spot_price",
            "atm_iv", "iv_rank", "iv_percentile", "historical_volatility",
            "india_vix", "seller_signal", "max_pain", "iv_skew"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        print(f"PASS: All {len(required_fields)} required fields present")
    
    def test_atm_iv_is_valid_percentage(self):
        """ATM IV should be between 5-100% for NIFTY"""
        response = requests.get(f"{BASE_URL}/api/iv/dashboard?underlying=NIFTY", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        atm_iv = data.get("atm_iv")
        assert atm_iv is not None, "ATM IV should not be None"
        assert 5 <= atm_iv <= 100, f"ATM IV {atm_iv}% should be between 5-100%"
        print(f"PASS: ATM IV = {atm_iv}% (valid range 5-100%)")
    
    def test_india_vix_is_fetched(self):
        """India VIX should be fetched from Angel One (token 99926017)"""
        response = requests.get(f"{BASE_URL}/api/iv/dashboard?underlying=NIFTY", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        india_vix = data.get("india_vix")
        # VIX can be None if market is closed, but if present should be 5-50 range
        if india_vix is not None:
            assert 5 <= india_vix <= 50, f"India VIX {india_vix} should be between 5-50"
            print(f"PASS: India VIX = {india_vix} (valid range 5-50)")
        else:
            print("INFO: India VIX is None (market may be closed)")
    
    def test_max_pain_has_valid_strike(self):
        """Max Pain should return a valid strike within the chain"""
        response = requests.get(f"{BASE_URL}/api/iv/dashboard?underlying=NIFTY", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        max_pain = data.get("max_pain")
        assert max_pain is not None, "Max pain should not be None"
        assert "max_pain_strike" in max_pain, "Max pain should have max_pain_strike"
        
        strike = max_pain["max_pain_strike"]
        spot = data.get("spot_price", 0)
        
        # Max pain strike should be within 10% of spot price
        if spot > 0:
            diff_pct = abs(strike - spot) / spot * 100
            assert diff_pct < 10, f"Max pain strike {strike} is {diff_pct:.1f}% from spot {spot}"
            print(f"PASS: Max Pain strike = {strike} ({diff_pct:.1f}% from spot {spot})")
        else:
            print(f"PASS: Max Pain strike = {strike}")
    
    def test_max_pain_has_pain_distribution(self):
        """Max Pain should include pain distribution array"""
        response = requests.get(f"{BASE_URL}/api/iv/dashboard?underlying=NIFTY", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        max_pain = data.get("max_pain")
        assert max_pain is not None
        assert "pain_distribution" in max_pain, "Max pain should have pain_distribution"
        
        pain_dist = max_pain["pain_distribution"]
        assert isinstance(pain_dist, list), "Pain distribution should be a list"
        assert len(pain_dist) > 0, "Pain distribution should not be empty"
        
        # Check structure of pain distribution entries
        first_entry = pain_dist[0]
        assert "strike" in first_entry, "Pain entry should have strike"
        assert "total_pain" in first_entry, "Pain entry should have total_pain"
        
        print(f"PASS: Pain distribution has {len(pain_dist)} entries")
    
    def test_iv_skew_has_ce_and_pe_iv(self):
        """IV Skew should return ce_iv and pe_iv for each strike"""
        response = requests.get(f"{BASE_URL}/api/iv/dashboard?underlying=NIFTY", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        iv_skew = data.get("iv_skew")
        assert iv_skew is not None, "IV skew should not be None"
        assert isinstance(iv_skew, list), "IV skew should be a list"
        assert len(iv_skew) > 0, "IV skew should not be empty"
        
        # Check structure
        first_entry = iv_skew[0]
        assert "strike" in first_entry, "Skew entry should have strike"
        assert "ce_iv" in first_entry, "Skew entry should have ce_iv"
        assert "pe_iv" in first_entry, "Skew entry should have pe_iv"
        assert "moneyness" in first_entry, "Skew entry should have moneyness"
        
        # Count entries with valid IV values
        valid_ce = sum(1 for s in iv_skew if s.get("ce_iv") and s["ce_iv"] > 0)
        valid_pe = sum(1 for s in iv_skew if s.get("pe_iv") and s["pe_iv"] > 0)
        
        print(f"PASS: IV Skew has {len(iv_skew)} strikes, {valid_ce} CE IVs, {valid_pe} PE IVs")
    
    def test_seller_signal_has_valid_values(self):
        """Seller signal should return SELL_PREMIUM, AVOID_SELLING, or NEUTRAL"""
        response = requests.get(f"{BASE_URL}/api/iv/dashboard?underlying=NIFTY", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        signal = data.get("seller_signal")
        assert signal is not None, "Seller signal should not be None"
        assert "signal" in signal, "Seller signal should have signal field"
        assert "reasoning" in signal, "Seller signal should have reasoning array"
        
        valid_signals = ["SELL_PREMIUM", "AVOID_SELLING", "NEUTRAL"]
        assert signal["signal"] in valid_signals, f"Signal {signal['signal']} not in {valid_signals}"
        assert isinstance(signal["reasoning"], list), "Reasoning should be a list"
        
        print(f"PASS: Seller signal = {signal['signal']} with {len(signal['reasoning'])} reasons")
    
    def test_iv_rank_and_percentile_building(self):
        """IV Rank and Percentile should be null or valid when building history"""
        response = requests.get(f"{BASE_URL}/api/iv/dashboard?underlying=NIFTY", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        iv_rank = data.get("iv_rank")
        iv_percentile = data.get("iv_percentile")
        iv_history_count = data.get("iv_history_count", 0)
        
        # If history count < 5, rank/percentile should be null (building)
        if iv_history_count < 5:
            print(f"INFO: Building IV history ({iv_history_count}/5 days). Rank/Percentile are null.")
        else:
            # If we have enough history, values should be 0-100
            if iv_rank is not None:
                assert 0 <= iv_rank <= 100, f"IV Rank {iv_rank} should be 0-100"
            if iv_percentile is not None:
                assert 0 <= iv_percentile <= 100, f"IV Percentile {iv_percentile} should be 0-100"
            print(f"PASS: IV Rank = {iv_rank}%, IV Percentile = {iv_percentile}%")


class TestIVSkewEndpoint:
    """Tests for GET /api/iv/skew endpoint"""
    
    def test_iv_skew_returns_200(self):
        """IV skew endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/iv/skew?underlying=NIFTY", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: IV skew endpoint returns 200")
    
    def test_iv_skew_has_required_fields(self):
        """IV skew should return underlying, expiry, spot_price, atm_strike, skew"""
        response = requests.get(f"{BASE_URL}/api/iv/skew?underlying=NIFTY", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["underlying", "expiry", "spot_price", "atm_strike", "atm_iv", "skew"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        print(f"PASS: IV skew has all required fields")
    
    def test_iv_skew_data_structure(self):
        """IV skew entries should have strike, moneyness, ce_iv, pe_iv"""
        response = requests.get(f"{BASE_URL}/api/iv/skew?underlying=NIFTY", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        skew = data.get("skew", [])
        assert len(skew) > 0, "Skew should have entries"
        
        for entry in skew[:5]:  # Check first 5
            assert "strike" in entry
            assert "moneyness" in entry
            assert "ce_iv" in entry
            assert "pe_iv" in entry
            assert "ce_ltp" in entry
            assert "pe_ltp" in entry
        
        print(f"PASS: IV skew has {len(skew)} entries with correct structure")


class TestMaxPainEndpoint:
    """Tests for GET /api/iv/max-pain endpoint"""
    
    def test_max_pain_returns_200(self):
        """Max pain endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/iv/max-pain?underlying=NIFTY", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Max pain endpoint returns 200")
    
    def test_max_pain_has_required_fields(self):
        """Max pain should return underlying, expiry, spot_price, max_pain"""
        response = requests.get(f"{BASE_URL}/api/iv/max-pain?underlying=NIFTY", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["underlying", "expiry", "spot_price", "max_pain"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        print(f"PASS: Max pain has all required fields")
    
    def test_max_pain_calculation_is_minimum(self):
        """Max pain strike should have minimum total_pain in distribution"""
        response = requests.get(f"{BASE_URL}/api/iv/max-pain?underlying=NIFTY", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        max_pain = data.get("max_pain")
        assert max_pain is not None
        
        mp_strike = max_pain["max_pain_strike"]
        mp_pain = max_pain["total_pain_at_max_pain"]
        pain_dist = max_pain["pain_distribution"]
        
        # Verify max pain strike has minimum pain
        min_pain_entry = min(pain_dist, key=lambda x: x["total_pain"])
        
        assert min_pain_entry["strike"] == mp_strike, \
            f"Max pain strike {mp_strike} should have minimum pain, but {min_pain_entry['strike']} has less"
        
        print(f"PASS: Max pain strike {mp_strike} correctly has minimum pain ({mp_pain:,.0f})")


class TestIVAnalyticsWithDifferentUnderlyings:
    """Test IV analytics with different underlyings"""
    
    def test_banknifty_iv_dashboard(self):
        """IV dashboard should work for BANKNIFTY"""
        response = requests.get(f"{BASE_URL}/api/iv/dashboard?underlying=BANKNIFTY", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        assert data["underlying"] == "BANKNIFTY"
        assert data.get("atm_iv") is not None
        print(f"PASS: BANKNIFTY IV dashboard works, ATM IV = {data['atm_iv']}%")
    
    def test_finnifty_iv_dashboard(self):
        """IV dashboard should work for FINNIFTY"""
        response = requests.get(f"{BASE_URL}/api/iv/dashboard?underlying=FINNIFTY", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        assert data["underlying"] == "FINNIFTY"
        print(f"PASS: FINNIFTY IV dashboard works")


class TestMongoDBStorage:
    """Test that IV and price snapshots are stored in MongoDB"""
    
    def test_iv_snapshot_stored(self):
        """Calling IV dashboard should store snapshot in MongoDB"""
        # First call to trigger storage
        response = requests.get(f"{BASE_URL}/api/iv/dashboard?underlying=NIFTY", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        # iv_history_count should be >= 1 after first call
        assert data.get("iv_history_count", 0) >= 1, "IV history count should be at least 1"
        print(f"PASS: IV snapshot stored, history count = {data['iv_history_count']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
