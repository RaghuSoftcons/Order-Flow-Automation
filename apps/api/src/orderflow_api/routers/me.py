"""
File:        apps/api/src/orderflow_api/routers/me.py
Created:     2026-04-26 17:21 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 17:21 EST

Change Log:
- 2026-04-26 17:21 EST | 1.0.0 | Initial Phase 0 scaffold.

Returns the calling user's profile based on their X-API-Key header.
First protected endpoint — proves auth middleware is wired correctly.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from orderflow_api.auth import require_user
from orderflow_api.models import User
from orderflow_shared.risk.templates import lookup_template

router = APIRouter()


@router.get("/me")
def me(user: User = Depends(require_user)) -> dict[str, object]:
    template = lookup_template(user.prop_tier)
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "prop_tier": user.prop_tier,
        "is_admin": user.is_admin,
        "risk_template": template.to_dict() if template else None,
    }
