# Testing

> Testing strategy, conventions, and how to run the test suite.

---

## 1. Strategy — The Test Pyramid

We follow the standard pyramid: **lots of fast unit tests, fewer integration tests, a small number of E2E tests.**

```
       /\
      /  \      E2E  (Playwright)        — few, slow, brittle
     /────\        → user-journey sanity
    /      \
   / Integ  \   Integration (TestClient)   — route + service + DB
  /          \    → no external network
 /──────────── \
/    Unit      \  Unit (pytest, pure fn)   — fast, deterministic
────────────────
```

| Layer       | Speed     | Scope                            | Network   | Count target |
|-------------|-----------|----------------------------------|-----------|--------------|
| Unit        | < 10 ms   | One function / one class         | No        | 80%+         |
| Integration | < 1 s     | One route + service + Mongo      | No        | 15%          |
| Contract    | < 5 s     | One external API shape           | Yes (mock)| 4%           |
| E2E         | 10-60 s   | User journey (login → dashboard) | Yes       | 1%           |

---

## 2. Backend (pytest)

### Layout
```
backend/tests/
├── conftest.py              # shared fixtures (test app, test db, mock Angel)
├── unit/
│   ├── test_arbitrage.py    # cash_carry, synthetic, calendar, statistical
│   ├── test_iv_analytics.py # bs_price, iv_rank, iv_percentile, max_pain
│   ├── test_performance.py  # sharpe, sortino, calmar
│   ├── test_risk.py         # var, position_size, margin
│   └── test_market_session.py
├── integration/
│   ├── test_auth.py         # session creation, /me, logout
│   ├── test_market.py       # /market/* routes with mocked Angel
│   ├── test_arbitrage.py    # /arbitrage/* routes
│   ├── test_options.py      # /options/* + /iv/* routes
│   ├── test_alerts.py       # CRUD on alerts (auth required)
│   ├── test_watchlist.py
│   └── test_backtest.py
├── contract/
│   └── test_angel_one_quote.py  # record/replay real SmartAPI response
└── e2e/
    └── test_dashboard_journey.py
```

### Conventions

#### File & function naming
- `test_<module>.py` mirrors the source file
- `test_<function>_<scenario>` describes a single behavior

```python
def test_calculate_cash_carry_returns_annualized_basis():
    ...

def test_calculate_cash_carry_raises_on_zero_spot():
    ...
```

#### One assertion concept per test
It's fine to have multiple `assert` lines if they verify one concept, but don't mix "returns correct spread" with "raises on bad input" in the same test.

#### Use parametrize for cases
```python
@pytest.mark.parametrize("spot,fut,dte,expected_sign", [
    (100, 101, 30, +1),   # contango → profitable
    (100,  99, 30, -1),   # backwardation
    (100, 100.5, 30,  0), # roughly fair
])
def test_cash_carry_sign(spot, fut, dte, expected_sign):
    result = ArbitrageEngine.calculate_cash_carry_arbitrage(spot, fut, dte)
    assert (result["net_profit"] > 0) == (expected_sign > 0)
```

#### Floating point
Use `pytest.approx` (or `math.isclose`):
```python
assert result["net_profit_pct"] == pytest.approx(0.45, abs=1e-6)
```

#### Determinism
- **Never** `np.random` without `np.random.seed(42)`
- **Never** `datetime.now()` — use `freezegun` to freeze time
- **Never** `time.sleep` in tests

### Fixtures (`conftest.py`)

| Fixture          | Scope        | Purpose                                     |
|------------------|--------------|---------------------------------------------|
| `event_loop`     | session      | Single asyncio loop for the session         |
| `app`            | function     | Fresh FastAPI app per test                  |
| `client`         | function     | `TestClient(app)` for HTTP calls            |
| `db`             | function     | Real Mongo connection, wiped between tests  |
| `mock_angel`     | function     | `monkeypatch`-ed Angel One service          |
| `auth_user`      | function     | Created user + session_token, sets cookie   |

### Mocking external services

**Angel One** is the only true external dependency. Use a fake:

```python
@pytest.fixture
def mock_angel(monkeypatch):
    class FakeAngel:
        def __init__(self):
            self.auth_token = "fake.jwt.token"
            self.is_connected = lambda: True
        def get_quote(self, symbol, exchange="NSE"):
            return {"symbol": symbol, "price": 100.0, ...}
        # ... etc
    monkeypatch.setattr("services.market_data.get_angel_service", lambda: FakeAngel())
```

**MongoDB** uses the real instance for integration tests (cleaner than mocking), with a per-test DB name:

```python
@pytest.fixture
async def db():
    test_db_name = f"arbitpro_test_{uuid.uuid4().hex[:8]}"
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[test_db_name]
    yield db
    await client.drop_database(test_db_name)
```

### Running

```bash
cd backend

# All tests
pytest

# With coverage
pytest --cov=services --cov=routes --cov-report=term-missing

# Only unit
pytest tests/unit -v

# Only one file
pytest tests/unit/test_arbitrage.py -v

# Stop on first failure
pytest -x

# Show local variables on failure
pytest -l
```

### Coverage gates
- `pytest --cov-fail-under=70` is the **CI floor** (global)
- New code should land with **> 80% line coverage**
- Pure-math services (`iv_analytics`, `arbitrage`) target **> 90%**

---

## 3. Frontend (Jest + React Testing Library)

> Not yet wired up. This is the target state.

### Planned layout
```
frontend/src/
├── __tests__/
│   ├── components/
│   │   ├── Layout.test.jsx
│   │   └── BrokerStatus.test.jsx
│   ├── pages/
│   │   ├── Dashboard.test.jsx
│   │   └── OptionChain.test.jsx
│   ├── hooks/
│   │   └── useApiQuery.test.js
│   └── lib/
│       └── format.test.js
└── setupTests.js          # jest-dom matchers, MSW server
```

### Conventions
- Test **behavior**, not implementation
- Query by `role` / `label` / `text`, **not** by className or testid (testid is OK for e2e hooks)
- Mock the API with **MSW** (Mock Service Worker) — not axios directly — so tests cover real fetch paths
- One render per test; use `rerender` only when explicitly testing re-renders

```jsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { server } from "../mocks/server";
import Dashboard from "./Dashboard";

test("shows live indices on load", async () => {
  render(<Dashboard />);
  expect(await screen.findByText("NIFTY")).toBeInTheDocument();
});
```

### Running (once configured)
```bash
cd frontend
yarn test                  # interactive
yarn test --watchAll=false # CI mode
yarn test --coverage
```

---

## 4. End-to-End (Playwright) — planned

```
e2e/
├── auth.spec.ts           # Google OAuth callback (mocked)
├── dashboard.spec.ts      # load dashboard, see live indices
├── option-chain.spec.ts   # switch underlying, verify chain updates
└── alert-flow.spec.ts     # login → create alert → see in list
```

- 1 happy-path per critical user journey
- Mock Angel One at the network level (Playwright `route.fulfill`)
- Run against a dockerized stack in CI

---

## 5. What to Test When

| Change type                | Minimum tests to add                          |
|----------------------------|-----------------------------------------------|
| New pure function          | 1 unit test per branch (parametrize)          |
| New route                  | 1 integration happy-path + 1 auth check       |
| New service method         | 2-3 unit tests + 1 integration                |
| Bug fix                    | 1 regression test that fails before the fix   |
| Refactor (no behavior)     | Existing tests must still pass                |
| Config / dependency bump   | CI green; add a smoke test if risk warrants  |

---

## 6. Anti-Patterns to Avoid

❌ **Testing implementation details** (`expect(component.state.foo).toBe(...)`)
❌ **Snapshot tests for non-trivial components** (creates maintenance burden)
❌ **`await new Promise(r => setTimeout(r, 100))`** — find a real signal
❌ **Mocking the system under test** — mock collaborators, not the function being tested
❌ **Shared mutable state between tests** — always start from a clean fixture
❌ **`pytest.raises(Exception)`** — catch the specific exception class
