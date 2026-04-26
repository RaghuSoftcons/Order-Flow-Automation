<!--
File:        docs/deployment.md
Created:     2026-04-26 17:24 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 17:24 EST

Change Log:
- 2026-04-26 17:24 EST | 1.0.0 | Initial Phase 0 scaffold.
-->

# Deployment

## Railway

Auto-deploy from GitHub `main` branch:

1. Railway project: `Order-Flow-Automation` (currently auto-named `overflowing-joy`).
2. Service `order-flow-automation` is connected to `RaghuSoftcons/Order-Flow-Automation`.
3. Every push to `main` triggers an automatic deploy via NIXPACKS.

### Required environment variables (set in Railway → Variables tab)

| Variable | Required | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes (Phase 2+) | Claude API key, never paste in chat |
| `API_KEY_SALT` | Yes | Random secret. Generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `ENVIRONMENT` | Optional | Defaults to `development`. Set to `production` on Railway |
| `LOG_LEVEL` | Optional | Defaults to `INFO` |
| `DATABASE_URL` | Auto-set | Railway Postgres plugin populates this |
| `REDIS_URL` | Auto-set | Railway Redis plugin populates this |

### Plugins (attach in Railway dashboard)

- **Postgres** — adds `DATABASE_URL` automatically (used in Phase 3+; Phase 0–2 fall back to SQLite if unset)
- **Redis** — adds `REDIS_URL` automatically (used in Phase 1+; Phase 0 falls back to fakeredis if unset)

For Phase 0, neither plugin is strictly required — the app starts with SQLite + fakeredis.

### Healthcheck

Railway hits `GET /health` (configured in `railway.json`). Expects HTTP 200 with `{"status": "ok"}`.

## Local development

```bash
cd repo
python -m venv .venv
source .venv/Scripts/activate     # Windows Git Bash
pip install -e ".[dev]"

# Optional: copy .env.example → .env and edit (defaults are dev-safe)
pytest -v
python -m orderflow_api.cli seed-users   # prints API keys ONCE — save them
uvicorn orderflow_api.main:app --reload --app-dir apps/api/src
```

Then:
- http://localhost:8000/health
- `curl -H "X-API-Key: <key from seed>" http://localhost:8000/me`

## Phase progression

| Phase | Deployment changes |
|---|---|
| 0 (now) | Single Railway service, no plugins required |
| 1 | Attach Redis plugin; deploy NinjaScript add-on to local NT |
| 2 | Add `ANTHROPIC_API_KEY` to Railway Variables |
| 3 | Attach Postgres plugin; split into separate Railway services |
| 4 | Add Schwab env vars; wire existing Schwab integration |
| 5a/5b | Per-user dashboards, audit logs |
