"""
File:        apps/api/src/orderflow_api/routers/bootstrap.py
Created:     2026-08-17 19:02 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-08-17 19:02 EST

Change Log:
- 2026-08-17 19:02 EST | 1.0.0 | One-time admin-seed endpoint. Gated by
  BOOTSTRAP_TOKEN env var so it can be disabled after use.

POST /admin/bootstrap with header X-Bootstrap-Token:
  - If token matches BOOTSTRAP_TOKEN env var, seeds the standard 3 users
    (any missing ones) and returns their fresh API keys ONCE.
  - Existing users are NOT re-keyed; the response marks them "exists".
  - If BOOTSTRAP_TOKEN is empty (default in prod after first use), returns 404.
  - If the header is missing or wrong, returns 401.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from orderflow_api.auth import generate_api_key, hash_api_key
from orderflow_api.cli import SEED_USERS
from orderflow_api.config import get_settings
from orderflow_api.db import get_engine, init_db
from orderflow_api.models import User

router = APIRouter()


def _constant_time_eq(a: str, b: str) -> bool:
    return secrets.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


@router.post("/admin/bootstrap")
def bootstrap(
    x_bootstrap_token: str | None = Header(default=None, alias="X-Bootstrap-Token"),
) -> dict[str, object]:
    settings = get_settings()

    if not settings.bootstrap_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="bootstrap disabled (BOOTSTRAP_TOKEN not set)",
        )

    if not x_bootstrap_token or not _constant_time_eq(x_bootstrap_token, settings.bootstrap_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing X-Bootstrap-Token",
        )

    init_db()
    engine = get_engine()
    results: list[dict[str, object]] = []

    with Session(engine) as session:
        for spec in SEED_USERS:
            existing = session.scalar(select(User).where(User.email == spec["email"]))
            if existing:
                results.append({
                    "email": spec["email"],
                    "status": "exists",
                    "prop_tier": existing.prop_tier,
                    "is_admin": existing.is_admin,
                })
                continue

            plaintext = generate_api_key()
            user = User(
                email=spec["email"],
                display_name=spec["display_name"],
                prop_tier=spec["prop_tier"],
                is_admin=spec["is_admin"],
                api_key_hash=hash_api_key(plaintext),
            )
            session.add(user)
            session.commit()
            results.append({
                "email": spec["email"],
                "status": "created",
                "prop_tier": spec["prop_tier"],
                "is_admin": spec["is_admin"],
                "api_key": plaintext,
            })

    return {
        "results": results,
        "notice": (
            "API keys are shown once. Save them in your password manager. "
            "After bootstrapping, delete BOOTSTRAP_TOKEN from Railway Variables "
            "to disable this endpoint."
        ),
    }
