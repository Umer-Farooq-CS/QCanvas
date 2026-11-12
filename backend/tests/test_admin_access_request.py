"""
Admin-access requests (existing user asks for admin rights; the master admin
approves through an emailed link). Exercises the real routes through the
FastAPI app with the database and current user stubbed.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app.api.routes import auth as auth_routes
from app.config.database import get_db
from app.models.database_models import UserRole


def _user(role=UserRole.USER, requested_at=None):
    return SimpleNamespace(
        id="22222222-2222-2222-2222-222222222222",
        email="student@example.com",
        username="student",
        full_name="Student One",
        role=role,
        is_active=True,
        is_verified=True,
        email_verified_at=None,
        admin_access_requested_at=requested_at,
        token_version=0,
        deleted_at=None,
    )


class _DB:
    def __init__(self, user):
        self.user = user
        self.commits = 0

    def query(self, *_a, **_k):
        return self

    def filter(self, *_a, **_k):
        return self

    def first(self):
        return self.user

    def commit(self):
        self.commits += 1

    def refresh(self, _obj):
        pass


@pytest.fixture
def setup(app, monkeypatch):
    state = {"user": _user(), "emails": [], "email_ok": True}
    db = _DB(state["user"])

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[auth_routes.get_current_user] = lambda: state["user"]

    def _send(full_name, username, email, approval_link):
        state["emails"].append(approval_link)
        return SimpleNamespace(success=state["email_ok"], error=None if state["email_ok"] else "SMTP down")

    monkeypatch.setattr(auth_routes.EmailService, "send_admin_approval_request", staticmethod(_send))
    client = TestClient(app)
    yield client, state, db
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(auth_routes.get_current_user, None)


def _token_from(link: str) -> str:
    return parse_qs(urlparse(link).query)["token"][0]


def test_full_flow_request_then_approve(setup):
    client, state, db = setup
    assert client.get("/api/auth/admin/request").json()["status"] == "not_requested"

    r = client.post("/api/auth/admin/request")
    assert r.status_code == 200 and r.json()["status"] == "pending"
    assert state["user"].admin_access_requested_at is not None
    assert len(state["emails"]) == 1

    # A second request while pending does not send another email.
    r2 = client.post("/api/auth/admin/request")
    assert r2.json()["status"] == "pending"
    assert len(state["emails"]) == 1

    approve = client.post("/api/auth/admin/approve", json={"token": _token_from(state["emails"][0])})
    assert approve.status_code == 200, approve.text
    assert state["user"].role == UserRole.ADMIN
    assert client.get("/api/auth/admin/request").json()["status"] == "approved"


def test_guest_cannot_request(setup):
    client, state, _ = setup
    state["user"].role = UserRole.DEMO
    r = client.post("/api/auth/admin/request")
    assert r.status_code == 403
    assert state["emails"] == []


def test_email_failure_rolls_back_the_request(setup):
    client, state, _ = setup
    state["email_ok"] = False
    r = client.post("/api/auth/admin/request")
    assert r.status_code == 500
    assert state["user"].admin_access_requested_at is None
    assert client.get("/api/auth/admin/request").json()["status"] == "not_requested"


def test_expired_request_cannot_be_approved(setup):
    client, state, _ = setup
    client.post("/api/auth/admin/request")
    link = state["emails"][0]
    state["user"].admin_access_requested_at = datetime.utcnow() - timedelta(hours=25)
    r = client.post("/api/auth/admin/approve", json={"token": _token_from(link)})
    assert r.status_code == 400
    assert state["user"].role == UserRole.USER


def test_approval_link_is_not_a_login_token(app, setup):
    """The emailed token must not work as a bearer token for the user."""
    client, state, _ = setup
    client.post("/api/auth/admin/request")
    token = _token_from(state["emails"][0])
    app.dependency_overrides.pop(auth_routes.get_current_user, None)  # use the real auth check
    r = client.get("/api/auth/admin/request", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_signup_approval_token_cannot_promote_a_regular_user(setup):
    """Old-style 'admin_approval' tokens only activate pending admin signups."""
    client, state, _ = setup
    from app.utils.jwt_auth import create_access_token

    token = create_access_token(data={"sub": state["user"].id, "intent": "admin_approval"}, expires_delta=timedelta(hours=1))
    r = client.post("/api/auth/admin/approve", json={"token": token})
    assert r.status_code == 400
    assert state["user"].role == UserRole.USER
