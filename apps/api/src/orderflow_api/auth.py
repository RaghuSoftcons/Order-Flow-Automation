"""
File:        apps/api/src/orderflow_api/auth.py
Created:     2026-04-26 17:20 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 17:20 EST

Change Log:
- 2026-04-26 17:20 EST | 1.0.0 | Initial Phase 0 scaffold.

API key auth. Caller sends `X-API-Key: <plaintext>`. We hash with the salt
and look up by hash. No plaintext is ever stored or logged.
"""

from __future__ import annotations

import hashlib
import secrets

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from orderflow_api.config import get_settings
from orderflow_api.db import get_session
from orderflow_api.models import User


def hash_api_key(plaintext: str, salt: str | None = None) -> str:
    if salt is None:
        salt = get_settings().api_key_salt
    return hashlib.sha256(f"{salt}:{plaintext}".encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    """URL-safe random key for new users. Show to the user once at creation."""
    return f"ofa_{secrets.token_urlsafe(32)}"


def require_user(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    session: Session = Depends(get_session),
) -> User:
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing X-API-Key header",
        )
    key_hash = hash_api_key(x_api_key)
    user = session.scalar(select(User).where(User.api_key_hash == key_hash))
    if user is None or user.disabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or disabled api key",
        )
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin only",
        )
    return user
