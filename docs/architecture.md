<!--
File:        docs/architecture.md
Created:     2026-04-26 17:24 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 17:24 EST
-->

# Architecture

See full design doc one level up: `../../Order_Flow_Automation_Design_v1.md` (in the parent project folder, alongside the `.docx` version).

## Service shape (Phase 0)

Single Railway service `order-flow-automation` that hosts everything. Internal modules:

```
orderflow_api/
├── main.py           ← FastAPI entry
├── config.py         ← Settings from env vars
├── logging.py        ← structlog → JSON to stdout
├── db.py             ← SQLAlchemy engine factory (SQLite local / Postgres prod)
├── cache.py          ← Redis factory (fakeredis local / Redis prod)
├── auth.py           ← API-key middleware, hashing, generation
├── cli.py            ← seed-users / list-users
├── models/
│   └── user.py       ← User SQLAlchemy model
└── routers/
    ├── health.py     ← /health  (public)
    └── me.py         ← /me      (auth-protected)

orderflow_shared/     ← cross-service code (risk templates etc.)
└── risk/
    └── templates.py  ← Apex/ETF tier risk templates (5 sizes × 2 firms)
```

## Service split (Phase 3 onward)

The `services/` folder inside `orderflow_api` is structured so we can split into multiple Railway services without refactoring application code. See design doc §8.5.

## Persistence

| Layer | Phase 0 (dev) | Phase 0 (prod) | Phase 3+ (prod) |
|---|---|---|---|
| Users | in-memory SQLite (test) / file SQLite (local run) | SQLite on Railway disk *(temp)* | Postgres |
| Cache | fakeredis | fakeredis | Redis |
| Order book | n/a | n/a | Redis (Phase 1+) |

Note: Railway containers are ephemeral — local SQLite on Railway will lose data on redeploy. Attach the Postgres plugin once you want any persistence beyond a single container lifetime.
