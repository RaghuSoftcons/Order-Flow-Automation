"""
File:        apps/api/src/orderflow_api/models/user.py
Created:     2026-04-26 17:20 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 17:20 EST

Change Log:
- 2026-04-26 17:20 EST | 1.0.0 | Initial Phase 0 scaffold.

User table: per-trader scoping. API key is hashed at rest.
Each user has a prop tier that maps to a risk template.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from orderflow_api.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))

    # sha256(salt + plaintext_key); plaintext is shown to the user once at creation.
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # e.g. "apex_100k", "etf_50k". Free-form here; risk template lookup validates.
    prop_tier: Mapped[str] = mapped_column(String(40))

    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    def __repr__(self) -> str:
        return f"<User {self.email} tier={self.prop_tier}>"
