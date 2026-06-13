# Quality

> Quality gates, lint, typecheck, CI, and code review standards for ArbitPRO.

---

## 1. The Quality Gate

Every PR must pass **all** of these before merge. Locally, run them with the one-liner below.

```bash
# From repo root
cd backend && flake8 . && pytest --cov --cov-fail-under=70 && cd ../frontend && yarn build
```

| Gate                | Tool             | Pass criteria                          |
|---------------------|------------------|----------------------------------------|
| Lint (Python)       | `flake8`         | Zero errors                            |
| Lint (JS)           | `eslint`         | Zero errors                            |
| Format (Python)     | `black --check`  | No diff                                 |
| Format (JS)         | `prettier --check` | No diff                              |
| Type check (Py)     | `mypy` (planned) | Zero errors on `services/` and `routes/` |
| Unit + integration  | `pytest`         | All pass, coverage ≥ 70% global, ≥ 80% on changed files |
| Build (frontend)    | `yarn build`     | Exits 0                                 |
| Smoke (backend)     | `uvicorn` boots  | `/api/health` returns 200               |

> CI runs the same gate on every PR. A green check from CI is the **only** source of truth.

---

## 2. Python — Lint & Format

### flake8

Config: `backend/.flake8`
```ini
[flake8]
max-line-length = 100
extend-ignore = E203, W503, E501
exclude = .venv, build, dist, __pycache__
```

Run:
```bash
cd backend
flake8 .
```

### black
```bash
black --check .        # CI mode
black .                # format in place
```

### isort
```bash
isort --check-only .   # CI mode
isort .                # fix
```

### mypy (planned)
Config: `backend/mypy.ini`
```ini
[mypy]
python_version = 3.11
strict_optional = True
warn_unused_ignores = True
ignore_missing_imports = True
```

---

## 3. JavaScript / React — Lint & Format

### ESLint
Config: `frontend/.eslintrc.json` (extends `react-app` + `react-hooks`)

```bash
cd frontend
yarn lint
```

### Prettier (planned)
```json
{
  "singleQuote": false,
  "semi": true,
  "printWidth": 100,
  "trailingComma": "es5"
}
```

---

## 4. Pre-commit Hooks (planned)

We use `pre-commit` to run the gate **before** push:

`.pre-commit-config.yaml`
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.10.0
    hooks: [{ id: black }]
  - repo: https://github.com/pycqa/flake8
    rev: 7.1.0
    hooks: [{ id: flake8 }]
  - repo: https://github.com/pycqa/isort
    rev: 5.13.0
    hooks: [{ id: isort }]
  - repo: https://github.com/pre-commit/mirrors-prettier
    rev: v3.3.3
    hooks: [{ id: prettier }]
```

Install:
```bash
pip install pre-commit
pre-commit install
```

---

## 5. CI — GitHub Actions

Workflow: `.github/workflows/ci.yml`

Runs on:
- Every push to `main`
- Every PR targeting `main`

Jobs:
1. **backend-lint** — `flake8`, `black --check`, `isort --check`
2. **backend-test** — `pytest --cov` with Mongo service container
3. **frontend-lint** — `yarn lint`
4. **frontend-build** — `yarn build`
5. **smoke** — boots the backend and curls `/api/health`

The workflow file is added in the **CI scaffold** task; see `TODO.md`.

---

## 6. Code Review Checklist

See [CONTRIBUTING.md §7](CONTRIBUTING.md#7-code-review-checklist) for the full reviewer walkthrough.

Quick version (must be all-green):
- ✅ Correctness — matches PR description, edge cases handled
- ✅ Safety — no swallowed exceptions, no hard-coded secrets
- ✅ Tests — unit for new logic, integration for new routes
- ✅ Style — matches module, no dead code
- ✅ Docs — ARCHITECTURE updated, TODO.md updated, .env.example updated

---

## 7. Release Readiness Criteria

A feature is "production-ready" only when:
1. All quality gates pass on CI
2. At least one other engineer has reviewed and approved
3. ARCHITECTURE.md is current
4. Feature flag or rollback path exists (for high-risk changes)
5. Logs are structured and search-able
6. Failure modes are tested (timeout, network error, bad input)

---

## 8. Monitoring & Observability (planned)

We don't have metrics yet. When we add them:
- **Prometheus** `/metrics` endpoint on backend
- Key metrics: request latency (p50/p95), error rate per route, Angel One API call latency, cache hit ratio, login success rate
- **Structured logs** with `request_id` for tracing
- **Health check** extended to ping Mongo and Angel session

---

## 9. Dependency Hygiene

- **Pin versions** in `requirements.txt` and `package.json` (already done)
- **Renovate / Dependabot** (planned) — auto-PR for minor/patch bumps
- Review major version bumps in a dedicated PR with a migration note
- Audit quarterly: `pip-audit`, `npm audit`
