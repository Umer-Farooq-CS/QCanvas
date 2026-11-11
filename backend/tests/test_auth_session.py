"""
Session lifecycle tests: token lifetime, sliding refresh, absolute cap,
purpose-token rejection and logout revocation.

These call the route functions directly with lightweight stand-ins for the
User model and DB session, so they run without Postgres.
"""
import os
import sys
import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.api.routes import auth as auth_routes  # noqa: E402
from app.config.settings import settings  # noqa: E402
from app.models.database_models import UserRole  # noqa: E402
from app.utils.jwt_auth import create_access_token, verify_token  # noqa: E402


def _user(role=UserRole.USER, token_version=0):
    from datetime import datetime

    return SimpleNamespace(
        id="11111111-1111-1111-1111-111111111111",
        email="student@example.com",
        username="student",
        full_name="Student",
        role=role,
        is_active=True,
        is_verified=True,
        created_at=datetime(2026, 1, 1),
        last_login_at=None,
        bio=None,
        token_version=token_version,
        deleted_at=None,
    )


class _FakeQuery:
    def __init__(self, user):
        self._user = user

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._user


class _FakeDB:
    def __init__(self, user):
        self.user = user
        self.commits = 0

    def query(self, model):
        return _FakeQuery(self.user)

    def commit(self):
        self.commits += 1


def _creds(token):
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_token_lifetime_comes_from_settings_not_30_minutes():
    token = create_access_token({"sub": "u1", "tv": 0})
    payload = verify_token(token)
    lifetime = payload["exp"] - payload["iat"]
    assert lifetime == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert lifetime > 30 * 60, "the old hardcoded 30-minute expiry broke long sessions"


def test_token_carries_auth_time():
    before = int(time.time())
    payload = verify_token(create_access_token({"sub": "u1", "tv": 0}))
    assert before - 1 <= payload["auth_time"] <= int(time.time()) + 1


def test_refresh_issues_new_token_and_preserves_auth_time():
    user = _user()
    original_auth_time = int(time.time()) - 3600
    old = create_access_token({"sub": user.id, "tv": 0, "auth_time": original_auth_time})

    resp = auth_routes.refresh_access_token(credentials=_creds(old), current_user=user)

    new_payload = verify_token(resp.access_token)
    assert new_payload["sub"] == user.id
    assert new_payload["tv"] == 0
    assert new_payload["auth_time"] == original_auth_time
    assert resp.user.email == user.email


def test_refresh_refused_after_absolute_session_cap():
    user = _user()
    too_old = int(time.time()) - (settings.SESSION_MAX_AGE_DAYS * 86400 + 60)
    token = create_access_token({"sub": user.id, "tv": 0, "auth_time": too_old})

    with pytest.raises(HTTPException) as exc:
        auth_routes.refresh_access_token(credentials=_creds(token), current_user=user)
    assert exc.value.status_code == 401


def test_admin_approval_token_is_not_a_login_session():
    user = _user()
    approval = create_access_token({"sub": user.id, "intent": "admin_approval"})
    db = _FakeDB(user)

    with pytest.raises(HTTPException) as exc:
        auth_routes.get_current_user(credentials=_creds(approval), db=db)
    assert exc.value.status_code == 401
    assert auth_routes.get_optional_user(credentials=_creds(approval), db=db) is None


def test_valid_session_token_is_accepted():
    user = _user()
    token = create_access_token({"sub": user.id, "tv": 0})
    assert auth_routes.get_current_user(credentials=_creds(token), db=_FakeDB(user)) is user


def test_logout_revokes_all_tokens_for_regular_users():
    user = _user(token_version=3)
    db = _FakeDB(user)
    token = create_access_token({"sub": user.id, "tv": 3})

    auth_routes.logout(current_user=user, db=db)

    assert user.token_version == 4
    assert db.commits == 1
    with pytest.raises(HTTPException) as exc:
        auth_routes.get_current_user(credentials=_creds(token), db=db)
    assert exc.value.status_code == 401


def test_logout_does_not_revoke_shared_demo_account():
    user = _user(role=UserRole.DEMO, token_version=0)
    db = _FakeDB(user)

    auth_routes.logout(current_user=user, db=db)

    assert user.token_version == 0
    assert db.commits == 0


def test_anonymous_logout_is_harmless():
    assert auth_routes.logout(current_user=None, db=_FakeDB(None)) == {
        "message": "Successfully logged out"
    }
