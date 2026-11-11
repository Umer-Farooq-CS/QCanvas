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


def test_anonymous_logout_is_harmless():
    assert auth_routes.logout(current_user=None, db=_FakeDB(None)) == {
        "message": "Successfully logged out"
    }


# --------------------------------------------------------------------------
# Private guest ("Try demo") workspaces
# --------------------------------------------------------------------------
from datetime import datetime, timedelta  # noqa: E402

from app.services import guest_service  # noqa: E402


class _RecordingQuery(_FakeQuery):
    def __init__(self, user, model, log):
        super().__init__(user)
        self.model = model
        self.log = log

    def delete(self, synchronize_session=False):
        self.log.append(self.model.__name__)
        return 0


class _GuestDB(_FakeDB):
    def __init__(self, user=None):
        super().__init__(user)
        self.added = []
        self.deleted_models = []

    def query(self, model):
        return _RecordingQuery(self.user, model, self.deleted_models)

    def add(self, obj):
        self.added.append(obj)
        if getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.utcnow()

    def refresh(self, obj):
        pass

    def rollback(self):
        pass


def test_each_guest_gets_a_distinct_private_account():
    db = _GuestDB()
    a = guest_service.create_guest(db)
    b = guest_service.create_guest(db)
    assert a.id != b.id
    assert a.email != b.email and a.username != b.username
    assert a.role == UserRole.DEMO and b.role == UserRole.DEMO
    assert a.email.endswith("." + "invalid"), "guest emails must be undeliverable"
    # Password is random and never returned to the client.
    assert not a.verify_password("demo123")


def test_guest_expires_after_ttl():
    fresh = _user(role=UserRole.DEMO)
    fresh.created_at = datetime.utcnow()
    old = _user(role=UserRole.DEMO)
    old.created_at = datetime.utcnow() - timedelta(hours=settings.GUEST_ACCOUNT_TTL_HOURS + 1)
    regular = _user(role=UserRole.USER)
    regular.created_at = datetime(2020, 1, 1)

    assert not guest_service.is_expired_guest(fresh)
    assert guest_service.is_expired_guest(old)
    assert not guest_service.is_expired_guest(regular), "TTL only applies to guests"


def test_expired_guest_token_is_rejected():
    old = _user(role=UserRole.DEMO)
    old.created_at = datetime.utcnow() - timedelta(hours=settings.GUEST_ACCOUNT_TTL_HOURS + 1)
    token = create_access_token({"sub": old.id, "tv": 0})
    db = _FakeDB(old)
    with pytest.raises(HTTPException) as exc:
        auth_routes.get_current_user(credentials=_creds(token), db=db)
    assert exc.value.status_code == 401
    assert auth_routes.get_optional_user(credentials=_creds(token), db=db) is None


def test_guest_logout_purges_workspace_and_kills_tokens():
    guest = _user(role=UserRole.DEMO)
    guest.created_at = datetime.utcnow()
    db = _GuestDB(guest)
    token = create_access_token({"sub": guest.id, "tv": 0})

    auth_routes.logout(current_user=guest, db=db)

    assert {"File", "Folder", "Project"} <= set(db.deleted_models)
    assert db.deleted_models.index("File") < db.deleted_models.index("Folder") < db.deleted_models.index("Project")
    assert guest.is_active is False and guest.deleted_at is not None
    assert guest.token_version == 1
    with pytest.raises(HTTPException):
        auth_routes.get_current_user(credentials=_creds(token), db=db)


def test_purge_guest_refuses_regular_accounts():
    with pytest.raises(ValueError):
        guest_service.purge_guest(_GuestDB(), _user(role=UserRole.USER))


def test_password_login_to_guest_or_legacy_shared_demo_is_refused():
    legacy = _user(role=UserRole.DEMO)
    legacy.email = "demo@qcanvas.dev"
    legacy.verify_password = lambda pw: True
    raw_login = getattr(auth_routes.login, "__wrapped__", auth_routes.login)
    payload = SimpleNamespace(email="demo@qcanvas.dev", password="demo123")

    with pytest.raises(HTTPException) as exc:
        raw_login(request=None, payload=payload, db=_FakeDB(legacy))
    assert exc.value.status_code == 403


def test_guest_endpoint_returns_working_session():
    db = _GuestDB()
    raw = getattr(auth_routes.create_guest_session, "__wrapped__", auth_routes.create_guest_session)
    resp = raw(request=None, db=db)
    assert resp.user.role == "demo"
    assert verify_token(resp.access_token)["sub"] == resp.user.id
