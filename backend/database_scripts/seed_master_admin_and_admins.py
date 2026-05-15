"""
Seed one master admin account and three regular admin accounts into the QCanvas database.

Usage (from repo root):
  python backend/seed_master_admin_and_admins.py

Notes:
- Idempotent: creates missing accounts and updates existing ones to the expected admin state.
- Uses the configured master admin email when available, otherwise falls back to the provided default.
- Sets accounts active and verified so they can log in immediately in local/dev environments.
"""

from __future__ import annotations

import os
import sys
from typing import Iterable

# Add backend directory to path so `app.*` imports work when run from repo root.
backend_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, backend_dir)

from app.config.database import SessionLocal  # noqa: E402
from app.config.settings import settings  # noqa: E402
from app.models.database_models import User, UserRole  # noqa: E402


MASTER_ADMIN = {
    "email": (settings.MASTER_ADMIN_EMAIL or "muhammadirtazakhan2004@gmail.com").strip().lower(),
    "username": "masteradmin",
    "full_name": "Master Admin",
    "password": "MasterAdmin123!",
}

ADMIN_ACCOUNTS = [
    {
        "email": "admin1@qcanvas.local",
        "username": "admin1",
        "full_name": "QCanvas Admin 1",
        "password": "Admin123!@#",
    },
]


def _upsert_admin(db, row: dict, *, label: str) -> str:
    email = row["email"].strip().lower()
    username = row["username"].strip()

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        existing_username = db.query(User).filter(User.username == username).first()
        if existing_username is not None:
            username = f"{username}_seed"

        user = User(
            email=email,
            username=username,
            full_name=row["full_name"],
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True,
        )
        user.set_password(row["password"])
        db.add(user)
        db.commit()
        db.refresh(user)
        return f"✅ Created {label}: {user.email} (username={user.username})"

    changed = False
    if user.deleted_at is not None:
        user.restore()
        changed = True
    if user.role != UserRole.ADMIN:
        user.role = UserRole.ADMIN
        changed = True
    if not user.is_active:
        user.is_active = True
        changed = True
    if not user.is_verified:
        user.is_verified = True
        changed = True
    if user.full_name != row["full_name"]:
        user.full_name = row["full_name"]
        changed = True
    if user.username != username:
        user.username = username
        changed = True
    if changed:
        db.commit()
        return f"✅ Updated {label}: {user.email} (promoted/restored/verified)"

    return f"ℹ️  {label} exists: {user.email}"


def seed_accounts(accounts: Iterable[dict], *, label_prefix: str) -> int:
    db = SessionLocal()
    try:
        print("=" * 60)
        print("QCanvas - Seed Admin Accounts")
        print("=" * 60)
        print()

        print(_upsert_admin(db, MASTER_ADMIN, label="master admin"))
        for index, row in enumerate(accounts, start=1):
            print(_upsert_admin(db, row, label=f"admin {index}"))

        print()
        print("Login credentials (dev/local):")
        print(f"- Master admin: {MASTER_ADMIN['email']} / {MASTER_ADMIN['password']}")
        for row in accounts:
            print(f"- {row['email']} / {row['password']}")

        return 0
    except Exception as exc:
        db.rollback()
        print(f"❌ Seed failed: {exc}")
        return 1
    finally:
        db.close()


def main() -> int:
    return seed_accounts(ADMIN_ACCOUNTS, label_prefix="admin")


if __name__ == "__main__":
    raise SystemExit(main())