#!/usr/bin/env python3
import requests
import sys
import json
from datetime import datetime
import time

class ArbitragePlatformTester:
    def __init__(self, base_url="https://indian-futures-hub.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.session_token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []
        self.passed_tests = []

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None, params=None, send_as_list=False):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        
        if headers:
            test_headers.update(headers)
        if self.session_token:
            test_headers['Authorization'] = f'Bearer {self.session_token}'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, params=params, timeout=10)
            elif method == 'POST':
                if send_as_list and data:
                    # Send data directly as list
                    response = requests.post(url, json=data, headers=test_headers, params=params, timeout=10)
                elif params:
                    # Send as query parameters
                    response = requests.post(url, headers=test_headers, params=data, timeout=10)
                else:
                    # Send as JSON body
                    response = requests.post(url, json=data, headers=test_headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.passed_tests.append(name)
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    json_response = response.json()
                    if isinstance(json_response, list) and len(json_response) > 0:
                        print(f"   Response: {len(json_response)} items")
                    elif isinstance(json_response, dict):
                        print(f"   Response keys: {list(json_response.keys())[:5]}")
                except:
                    print(f"   Response: {response.text[:100]}")
                return True, response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
            else:
                self.failed_tests.append(f"{name} - Expected {expected_status}, got {response.status_code}")
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    print(f"   Error response: {response.json()}")
                except:
                    print(f"   Error response: {response.text[:200]}")
                return False, {}

        except Exception as e:
            self.failed_tests.append(f"{name} - Error: {str(e)}")
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_health_endpoints(self):
        """Test basic health endpoints"""
        print("\n" + "="*50)
        print("🔧 TESTING HEALTH ENDPOINTS")
        print("="*50)
        
        self.run_test("Health Check", "GET", "", 200)
        self.run_test("API Health", "GET", "health", 200)

    def test_market_data_endpoints(self):
        """Test market data endpoints"""
        print("\n" + "="*50)
        print("📊 TESTING MARKET DATA ENDPOINTS")
        print("="*50)
        
        self.run_test("Market Indices", "GET", "market/indices", 200)
        self.run_test("Stock Price - RELIANCE", "GET", "market/stock/RELIANCE", 200)
        self.run_test("Stock Price - TCS NSE", "GET", "market/stock/TCS?exchange=NSE", 200)
        self.run_test("Multiple Stocks", "GET", "market/stocks", 200)
        self.run_test("Multiple Stocks - Custom", "GET", "market/stocks?symbols=RELIANCE,TCS,INFY", 200)
        self.run_test("F&O Stocks List", "GET", "market/fo-stocks", 200)

    def test_arbitrage_endpoints(self):
        """Test arbitrage calculation endpoints"""
        print("\n" + "="*50)
        print("⚖️ TESTING ARBITRAGE ENDPOINTS")
        print("="*50)
        
        # Cross-exchange arbitrage
        self.run_test("Cross-Exchange Arbitrage", "GET", "arbitrage/cross-exchange", 200)
        self.run_test("Cross-Exchange with Symbols", "GET", "arbitrage/cross-exchange?symbols=RELIANCE,TCS", 200)
        
        # Cash and carry arbitrage
        cash_carry_data = {
            "spot_price": 2850.0,
            "futures_price": 2870.0,
            "days_to_expiry": 30,
            "risk_free_rate": 7.0
        }
        self.run_test("Cash & Carry Arbitrage", "POST", "arbitrage/cash-carry", 200, cash_carry_data, params=True)
        
        # Synthetic futures arbitrage
        synthetic_data = {
            "spot_price": 2850.0,
            "call_price": 45.0,
            "put_price": 25.0,
            "strike": 2850.0,
            "futures_price": 2870.0
        }
        self.run_test("Synthetic Futures Arbitrage", "POST", "arbitrage/synthetic", 200, synthetic_data, params=True)
        
        # Calendar spread
        calendar_data = {
            "near_futures": 2850.0,
            "far_futures": 2870.0,
            "near_expiry_days": 15,
            "far_expiry_days": 45
        }
        self.run_test("Calendar Spread", "POST", "arbitrage/calendar-spread", 200, calendar_data, params=True)
        
        # Statistical arbitrage
        statistical_data = {
            "prices1": [100, 101, 102, 99, 100, 103, 101, 100, 102, 99, 100, 101, 102, 100, 99, 101, 103, 102, 100, 101],
            "prices2": [200, 202, 204, 198, 200, 206, 202, 200, 204, 198, 200, 202, 204, 200, 198, 202, 206, 204, 200, 202],
            "lookback": 20
        }
        self.run_test("Statistical Arbitrage", "POST", "arbitrage/statistical", 200, statistical_data)

    def test_analytics_endpoints(self):
        """Test performance analytics endpoints"""
        print("\n" + "="*50)
        print("📈 TESTING ANALYTICS ENDPOINTS")
        print("="*50)
        
        # Performance metrics
        returns_data = {
            "returns": [0.01, -0.005, 0.02, 0.015, -0.01, 0.008, 0.012, -0.003, 0.009, 0.006],
            "risk_free_rate": 7.0
        }
        self.run_test("Performance Metrics", "POST", "analytics/performance", 200, returns_data)
        
        # Weekday performance
        trades_data = {
            "trades": [
                {"date": "2024-01-15T10:00:00Z", "pnl": 150},
                {"date": "2024-01-16T10:00:00Z", "pnl": -50},
                {"date": "2024-01-17T10:00:00Z", "pnl": 200},
                {"date": "2024-01-18T10:00:00Z", "pnl": 75},
                {"date": "2024-01-19T10:00:00Z", "pnl": -25}
            ]
        }
        self.run_test("Weekday Performance", "POST", "analytics/weekday", 200, trades_data)

    def test_risk_management_endpoints(self):
        """Test risk management endpoints"""
        print("\n" + "="*50)
        print("⚠️ TESTING RISK MANAGEMENT ENDPOINTS")
        print("="*50)
        
        # Position sizing
        position_data = {
            "capital": 1000000.0,
            "risk_per_trade": 2.0,
            "stop_loss_pct": 5.0,
            "price": 2850.0
        }
        self.run_test("Position Size Calculation", "POST", "risk/position-size", 200, position_data)
        
        # Value at Risk
        var_data = {
            "returns": [0.01, -0.015, 0.02, 0.005, -0.01, 0.008, 0.012, -0.003, 0.009, -0.006],
            "confidence": 0.95,
            "portfolio_value": 1000000.0
        }
        self.run_test("Value at Risk (VaR)", "POST", "risk/var", 200, var_data)
        
        # Margin calculation
        margin_data = {
            "position_value": 500000.0,
            "volatility": 15.0,
            "is_futures": True
        }
        self.run_test("Margin Requirement", "POST", "risk/margin", 200, margin_data)

    def test_backtest_endpoints(self):
        """Test backtesting endpoints"""
        print("\n" + "="*50)
        print("🔄 TESTING BACKTEST ENDPOINTS")
        print("="*50)
        
        backtest_data = {
            "strategy": "cross_exchange",
            "symbol": "RELIANCE",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 1000000.0
        }
        self.run_test("Backtest Cross Exchange", "POST", "backtest", 200, backtest_data)
        
        # Test other strategies
        for strategy in ["cash_carry", "statistical"]:
            strategy_data = backtest_data.copy()
            strategy_data["strategy"] = strategy
            self.run_test(f"Backtest {strategy.title()}", "POST", "backtest", 200, strategy_data)

    def create_test_user(self):
        """Create test user and session using MongoDB"""
        print("\n" + "="*50)
        print("👤 CREATING TEST USER FOR AUTH TESTING")
        print("="*50)
        
        import subprocess
        import time
        
        timestamp = int(time.time())
        user_id = f"test-user-{timestamp}"
        session_token = f"test_session_{timestamp}"
        
        # Create user and session in MongoDB
        mongo_script = f'''
        use('test_database');
        db.users.insertOne({{
            user_id: "{user_id}",
            email: "test.user.{timestamp}@example.com",
            name: "Test User",
            picture: "https://via.placeholder.com/150",
            created_at: new Date()
        }});
        db.user_sessions.insertOne({{
            user_id: "{user_id}",
            session_token: "{session_token}",
            expires_at: new Date(Date.now() + 7*24*60*60*1000),
            created_at: new Date()
        }});
        '''
        
        try:
            result = subprocess.run(
                ['mongosh', '--eval', mongo_script],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                self.session_token = session_token
                print(f"✅ Test user created successfully")
                print(f"   User ID: {user_id}")
                print(f"   Session Token: {session_token}")
                return True
            else:
                print(f"❌ Failed to create test user: {result.stderr}")
                return False
        except Exception as e:
            print(f"❌ Error creating test user: {e}")
            return False

    def test_auth_endpoints(self):
        """Test authentication endpoints"""
        if not self.session_token:
            print("⚠️ Skipping auth tests - no session token available")
            return
            
        print("\n" + "="*50)
        print("🔐 TESTING AUTH ENDPOINTS")
        print("="*50)
        
        # Test authenticated endpoints
        self.run_test("Get Current User", "GET", "auth/me", 200)
        
        # Test user-specific endpoints
        self.run_test("Get User Settings", "GET", "settings", 200)
        self.run_test("Get User Watchlist", "GET", "watchlist", 200)
        self.run_test("Get User Alerts", "GET", "alerts", 200)

    def cleanup_test_data(self):
        """Clean up test data from database"""
        if not self.session_token:
            return
            
        print("\n🧹 Cleaning up test data...")
        import subprocess
        
        cleanup_script = '''
        use('test_database');
        db.users.deleteMany({email: /test\.user\./});
        db.user_sessions.deleteMany({session_token: /test_session/});
        db.watchlist.deleteMany({user_id: /test-user-/});
        db.alerts.deleteMany({user_id: /test-user-/});
        '''
        
        try:
            subprocess.run(['mongosh', '--eval', cleanup_script], capture_output=True, timeout=10)
            print("✅ Test data cleaned up")
        except:
            print("⚠️ Could not clean up test data")

    def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting Indian Markets Arbitrage Platform Backend Tests")
        print(f"Backend URL: {self.base_url}")
        print(f"Started at: {datetime.now()}")
        
        # Test non-auth endpoints first
        self.test_health_endpoints()
        self.test_market_data_endpoints()
        self.test_arbitrage_endpoints()
        self.test_analytics_endpoints()
        self.test_risk_management_endpoints()
        self.test_backtest_endpoints()
        
        # Create test user and test auth endpoints
        if self.create_test_user():
            self.test_auth_endpoints()
            self.cleanup_test_data()
        
        # Print summary
        print("\n" + "="*60)
        print("📊 TEST SUMMARY")
        print("="*60)
        print(f"Total tests run: {self.tests_run}")
        print(f"Tests passed: {self.tests_passed}")
        print(f"Tests failed: {len(self.failed_tests)}")
        print(f"Success rate: {(self.tests_passed/self.tests_run*100):.1f}%" if self.tests_run > 0 else "0%")
        
        if self.failed_tests:
            print("\n❌ Failed Tests:")
            for failure in self.failed_tests:
                print(f"  - {failure}")
        
        if self.passed_tests:
            print(f"\n✅ Passed Tests ({len(self.passed_tests)}):")
            for test in self.passed_tests[:10]:  # Show first 10
                print(f"  - {test}")
            if len(self.passed_tests) > 10:
                print(f"  ... and {len(self.passed_tests) - 10} more")
        
        return self.tests_passed == self.tests_run

def main():
    tester = ArbitragePlatformTester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())