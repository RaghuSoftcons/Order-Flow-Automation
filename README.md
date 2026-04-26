<!--
File:        README.md
Created:     2026-04-26 17:19 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 17:19 EST

Change Log:
- 2026-04-26 17:19 EST | 1.0.0 | Initial Phase 0 scaffold.
-->

# Order Flow Automation

AI-assisted order flow analysis and execution for prop futures (Apex/ETF via NinjaTrader bridge) and Schwab equities. Three-trader working group.

See full design: [Order_Flow_Automation_Design_v1.md](../Order_Flow_Automation_Design_v1.md) (in parent project folder).

## Stack

- Python 3.12 + FastAPI + uvicorn
- Pydantic v2 schemas
- SQLAlchemy with SQLite (local dev) / Postgres (Railway prod)
- Redis (Railway plugin) / fakeredis (local dev)
- Anthropic Claude API (Haiku reads, Sonnet decisions, Opus rare)
- Deployed to Railway via NIXPACKS, GitHub-connected auto-deploy

## Phase 0 (current)

Foundation only: FastAPI app, auth middleware, health endpoint, user table, no market logic yet.

## Local development

```bash
# Create venv and install deps (Python 3.12+)
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
pip install -e ".[dev]"

# Run tests
pytest -v

# Start locally
cp .env.example .env
# Edit .env and set API_KEY_SALT
python -m orderflow_api.cli seed-users
uvicorn orderflow_api.main:app --reload --app-dir apps/api/src
```

Then hit http://localhost:8000/health.

## Repository layout

```
apps/
  api/src/orderflow_api/      ← FastAPI service
packages/
  shared/src/orderflow_shared/ ← Pydantic schemas, risk templates, instrument metadata
tests/
  unit/                        ← Fast pure-Python tests (monkeypatch, TestClient)
  integration/                 ← Slower end-to-end tests
docs/                          ← Architecture, deployment, NT bridge setup
scripts/                       ← One-off utilities (seed_users, etc.)
```

## Deployment

Railway watches the `main` branch and auto-deploys on push. See [docs/deployment.md](docs/deployment.md).

## Tests

All tests run in-process with no external services (SQLite + fakeredis + monkeypatched HTTP clients):

```bash
pytest -v
```

## Conventions

- Every source file has a header with name, created/modified timestamps (EST), version, change log
- File naming convention for NinjaScript: `DescriptiveName_Claude_V#.cs`
- Tokens, API keys, and secrets stay in environment variables — never in source
- No live order routing in Phase 0–2; advisory only
