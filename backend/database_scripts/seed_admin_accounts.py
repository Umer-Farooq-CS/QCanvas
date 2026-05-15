"""
Seed three admin accounts into the QCanvas database.

Usage (from repo root):
  python backend/seed_admin_accounts.py

Notes:
- Idempotent: will create missing accounts; existing accounts will be promoted to admin.
- Sets is_verified=True to avoid OTP-gated login flows in local/dev.
"""

from __future__ import annotations

import os
import sys

# Add backend directory to path so `app.*` imports work when run from repo root.
backend_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, backend_dir)

from app.config.database import SessionLocal  # noqa: E402
from app.models.database_models import User, UserRole  # noqa: E402


ADMINS = [
    {
        "email": "admin1@qcanvas.local",
        "username": "admin1",
        "full_name": "QCanvas Admin 1",
        "password": "Admin123!@#",
    },
    {
        "email": "admin2@qcanvas.local",
        "username": "admin2",
        "full_name": "QCanvas Admin 2",
        "password": "Admin123!@#",
    },
    {
        "email": "admin3@qcanvas.local",
        "username": "admin3",
        "full_name": "QCanvas Admin 3",
        "password": "Admin123!@#",
    },
]


def seed() -> int:
    db = SessionLocal()
    try:
        for row in ADMINS:
            email = row["email"].strip().lower()
            username = row["username"].strip()

            user = (
                db.query(User)
                .filter(User.email == email)
                .first()
            )

            if user is None:
                # Ensure username uniqueness if user exists with same username.
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
                print(f"✅ Created admin: {user.email} (username={user.username})")
            else:
                changed = False
                if user.deleted_at is not None:
                    user.restore()
                    changed = True
                if user.role != UserRole.ADMIN:
                    user.role = UserRole.ADMIN
                    changed = True
                if not user.is_verified:
                    user.is_verified = True
                    changed = True
                if changed:
                    db.commit()
                    print(f"✅ Updated admin: {user.email} (role/promoted/restored)")
                else:
                    print(f"ℹ️  Admin exists: {user.email}")

        print("\nLogin credentials (dev/local):")
        for row in ADMINS:
            print(f"- {row['email']} / {row['password']}")
        return 0
    except Exception as e:
        db.rollback()
        print(f"❌ Seed failed: {e}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(seed())

