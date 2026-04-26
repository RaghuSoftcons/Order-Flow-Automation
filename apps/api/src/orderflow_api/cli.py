"""
File:        apps/api/src/orderflow_api/cli.py
Created:     2026-04-26 17:21 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 17:21 EST

Change Log:
- 2026-04-26 17:21 EST | 1.0.0 | Initial Phase 0 scaffold.

CLI utilities. Phase 0 supports:
  - `orderflow seed-users`  — creates Raghu + 2 placeholder traders, prints API keys once
  - `orderflow list-users`  — list all users (no keys)
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from orderflow_api.auth import generate_api_key, hash_api_key
from orderflow_api.db import get_engine, init_db
from orderflow_api.models import User
from sqlalchemy.orm import Session


SEED_USERS = [
    {
        "email": "raghu@softcons.net",
        "display_name": "Raghu",
        "prop_tier": "apex_100k",
        "is_admin": True,
    },
    {
        "email": "trader2@placeholder.local",
        "display_name": "Trader 2 (placeholder)",
        "prop_tier": "apex_50k",
        "is_admin": False,
    },
    {
        "email": "trader3@placeholder.local",
        "display_name": "Trader 3 (placeholder)",
        "prop_tier": "apex_50k",
        "is_admin": False,
    },
]


def cmd_seed_users() -> int:
    init_db()
    engine = get_engine()
    print("Seeding 3 users — SAVE THE PRINTED API KEYS, they are not recoverable.\n")
    with Session(engine) as session:
        for spec in SEED_USERS:
            existing = session.scalar(select(User).where(User.email == spec["email"]))
            if existing:
                print(f"  - {spec['email']:42}  EXISTS  tier={existing.prop_tier}")
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
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                print(f"  - {spec['email']:42}  CONFLICT, skipped")
                continue
            print(f"  - {spec['email']:42}  CREATED  tier={spec['prop_tier']}")
            print(f"    API_KEY={plaintext}")
    print("\nStore each API_KEY in your password manager. They cannot be retrieved later.")
    return 0


def cmd_list_users() -> int:
    init_db()
    engine = get_engine()
    with Session(engine) as session:
        users = session.scalars(select(User).order_by(User.created_at)).all()
    if not users:
        print("(no users)")
        return 0
    for u in users:
        admin = "[admin]" if u.is_admin else "       "
        disabled = "[DISABLED]" if u.disabled else ""
        print(f"  {admin}  {u.email:42}  tier={u.prop_tier:14}  {disabled}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="orderflow")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed-users", help="Create initial users + print their API keys once")
    sub.add_parser("list-users", help="List existing users (no keys)")
    args = parser.parse_args(argv)
    if args.cmd == "seed-users":
        return cmd_seed_users()
    if args.cmd == "list-users":
        return cmd_list_users()
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
