# Contributing

> Coding standards, PR conventions, and review checklist for ArbitPRO.

---

## 1. Ground Rules

1. **One concern per PR.** Don't bundle a refactor with a feature.
2. **Match the existing style** of the file you're editing. If the file violates these rules, fix the rule in a separate PR.
3. **No secrets in code or commits.** Use environment variables.
4. **Tests are part of the change.** A new feature without a test is incomplete.
5. **Run the quality gate** before pushing (see [QUALITY.md](QUALITY.md)).

---

## 2. Branching & Commit Messages

### Branch naming
```
feat/<short-kebab>          # new feature
fix/<short-kebab>           # bug fix
refactor/<short-kebab>      # refactor with no behavior change
docs/<short-kebab>          # docs only
test/<short-kebab>          # tests only
chore/<short-kebab>         # build/CI/deps
```

### Commit messages (Conventional Commits)
```
<type>(<scope>): <subject>

<body — wrap at 72 cols>

<footer>
```

Examples:
```
feat(iv): add Brent fallback for IV calculation when Newton diverges
fix(option-chain): clamp num_strikes to [5, 50] in route
refactor(server): split arbitrage logic into services/arbitrage.py
docs(arch): add data flow diagrams
```

Types: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `chore`, `build`, `ci`

---

## 3. Python Style

We use **PEP 8** + **Black** (line length 100) + **isort** + **flake8**.

### Imports (isort order)
```python
# stdlib
import os
from datetime import datetime, timezone

# third-party
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# local
from services.arbitrage import ArbitrageEngine
from core.db import db
```

### Naming
- `snake_case` for functions, variables, modules
- `PascalCase` for classes, Pydantic models
- `UPPER_SNAKE_CASE` for module-level constants (e.g. `STRIKE_STEPS`)
- Prefix private helpers with `_`

### Type hints
- **Required** on new public functions
- Use `Optional[X]` not `X | None` for Python 3.10 compat in some linters
- Pydantic for all request/response models

```python
from typing import Optional, List, Dict, Any

async def get_quote(symbol: str, exchange: str = "NSE") -> Optional[Dict[str, Any]]:
    ...
```

### Async discipline
- `async def` for anything that calls a network/DB API
- **Never** call blocking I/O directly inside `async def` — wrap in `asyncio.to_thread` or use a sync path
- Use `asyncio.gather` for independent parallel work

```python
# ✅ Good
results = await asyncio.gather(
    *[MarketDataService.get_stock_price(s) for s in symbols],
    return_exceptions=True,
)

# ❌ Bad
for s in symbols:
    result = await MarketDataService.get_stock_price(s)  # serial
```

### Error handling
- **Never** `except: pass` — at minimum log it
- Catch the narrowest exception class
- Convert to `HTTPException` at the route boundary, not in services

```python
# ✅ Good — service raises, route translates
# service
try:
    data = await client.post(...)
except httpx.TimeoutException as e:
    raise DataUnavailableError(f"Angel One timeout: {e}")

# route
try:
    return await service.fetch(...)
except DataUnavailableError as e:
    raise HTTPException(status_code=503, detail=str(e))
```

### Logging
- Use the module-level `logger` (`logger = logging.getLogger(__name__)`)
- Use lazy formatting: `logger.info("User %s logged in", user_id)` not f-strings
- Levels: `DEBUG` (verbose, dev), `INFO` (lifecycle events), `WARNING` (recoverable), `ERROR` (needs attention)

---

## 4. JavaScript / React Style

We use **ESLint** (React 19 + hooks rules) + **Prettier** (single quotes, semi, 100 cols).

### Component conventions
- **Functional components only.** No class components.
- **One component per file.** Filename matches component (`Dashboard.jsx` exports `Dashboard`).
- **Default export only for page components.** Named exports for utilities/hooks.
- **Co-locate small helpers** inside the component file; extract to `lib/` once reused.

### Hooks
- **All hooks at the top level.** No conditional hooks.
- **Stable references** via `useCallback` for functions passed to memoized children.
- **Effect deps** must be exhaustive. If you need to lie about deps, add a code comment explaining why.

```jsx
// ✅ Good
useEffect(() => {
  fetchIndices();
}, [fetchIndices]);

// ⚠️ If you must omit a dep, comment it
useEffect(() => {
  fetchIndices();
}, []); // eslint-disable-line react-hooks/exhaustive-deps -- intentional: mount-only
```

### Data fetching
- **No `useEffect` + raw `axios` in new code.** Use the planned `useApiQuery` hook (React Query) once it's added.
- **All API URLs** through the `API` constant from `App.js`.

### Accessibility
- Every interactive element needs a real `<button>` or `<a>`
- Use `aria-label` for icon-only buttons
- Forms need labels (not just placeholders)

---

## 5. Adding a New Feature — Checklist

Use this for any non-trivial PR.

- [ ] Read [ARCHITECTURE.md](ARCHITECTURE.md) to find the right module
- [ ] Update `TODO.md` and `docs/ROADMAP.md` (move item from backlog to in-progress)
- [ ] Implement in the correct module:
  - Route → `routes/`
  - Business logic → `services/`
  - Data shape → `models/`
  - Background job → `tasks/`
- [ ] Add `response_model=` to all new routes
- [ ] Add tests:
  - Unit test for any new pure function
  - Integration test (TestClient) for any new route
- [ ] Update `docs/ARCHITECTURE.md` if module boundaries changed
- [ ] Run the quality gate: `pytest` + `flake8 backend/` + `yarn build`
- [ ] Update the OpenAPI tag / summary / description

---

## 6. PR Template

When you open a PR, fill in this template:

```markdown
## What
<!-- 1-3 sentence summary -->

## Why
<!-- Link to issue / TODO item / ROADMAP entry -->

## How
<!-- Implementation notes, decisions, trade-offs -->

## Testing
<!-- What tests you added, what you ran, screenshots if UI -->

## Quality Gate
- [ ] `pytest backend/tests` passes
- [ ] `flake8 backend/` passes
- [ ] `yarn build` passes
- [ ] No new TODOs without a corresponding TODO.md entry

## Risk & Rollout
<!-- How risky? Feature-flagged? Backwards-compatible? -->
```

---

## 7. Code Review Checklist

Reviewers, work through this in order. If any box is unchecked, request changes.

### Correctness
- [ ] Logic matches the PR description
- [ ] Edge cases handled (empty inputs, None, zero, negative, very large)
- [ ] No off-by-one errors in loops/ranges
- [ ] Floating point handled correctly (`round`, `math.isclose`, tolerance)

### Safety
- [ ] No new `except: pass` or `except Exception: pass`
- [ ] No new hard-coded secrets / API keys
- [ ] No `print()` in production code (use `logger`)
- [ ] No `await` inside `for` loops where `gather` would do

### Tests
- [ ] New pure functions have unit tests
- [ ] New routes have at least one happy-path integration test
- [ ] Tests are deterministic (no `time.sleep`, no `np.random` without seed)
- [ ] Coverage on changed lines > 80% (run `pytest --cov`)

### Style
- [ ] Matches existing module conventions
- [ ] No unused imports / dead code
- [ ] Public functions have docstrings (one-line minimum)
- [ ] No comments that just restate the code

### Docs
- [ ] Public API change reflected in `docs/ARCHITECTURE.md`
- [ ] `TODO.md` updated
- [ ] `.env.example` updated if new env vars added

---

## 8. Release Process (light)

We don't do formal releases yet. Until we do:

1. PRs land on `main` after review
2. Versioning is implicit (date-based, see commit history)
3. Breaking changes must be flagged in the PR title: `feat!:` or `fix!:`
