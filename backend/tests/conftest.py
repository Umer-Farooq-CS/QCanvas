"""
Shared fixtures for the backend workshop-hardening tests.

These tests need no Postgres/Redis: DB sessions are faked through FastAPI
dependency overrides and settings are monkeypatched per test.
"""
import os
import sys
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
for path in (BACKEND_DIR, PROJECT_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)

# Only effective if nothing imported app.config.settings yet (the legacy
# backend/test_*.py modules may have); tests below don't rely on it.
os.environ.setdefault("RATE_LIMIT_STORAGE_URI", "memory://")


@pytest.fixture(scope="session")
def app():
    from app.main import app as fastapi_app

    return fastapi_app


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    from app.config.settings import settings
    from app.core.middleware import limiter
    from app.core import middleware as _mw

    # Starlette's TestClient connects as peer "testclient". Treat it as our
    # trusted load balancer so tests can simulate distinct clients via
    # X-Forwarded-For; real IP peers still go through the CIDR check.
    _real_trust = _mw._peer_is_trusted_proxy
    monkeypatch.setattr(
        _mw, "_peer_is_trusted_proxy",
        lambda peer: peer == "testclient" or _real_trust(peer),
    )
    from app.core.concurrency import simulation_runner, conversion_runner

    monkeypatch.setattr(settings, "AUDIT_LOG_ENABLED", False)
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    limiter.enabled = True
    try:
        limiter.reset()
    except Exception:
        pass
    simulation_runner.reset()
    conversion_runner.reset()
    yield
    try:
        limiter.reset()
    except Exception:
        pass


@pytest.fixture
def fake_db():
    db = MagicMock(name="db_session")
    # Typical query chain returns "not found".
    db.query.return_value.filter.return_value.first.return_value = None
    return db


@pytest.fixture
def override_db(app, fake_db):
    from app.config.database import get_db

    def _get_db():
        yield fake_db

    app.dependency_overrides[get_db] = _get_db
    yield fake_db
    app.dependency_overrides.pop(get_db, None)


def make_user(role=None, **extra):
    from app.models.database_models import UserRole

    return SimpleNamespace(
        id=uuid.uuid4(),
        username=extra.pop("username", "student"),
        role=role or UserRole.USER,
        is_active=True,
        **extra,
    )


def bearer_for(user_id) -> dict:
    from app.utils.jwt_auth import create_access_token

    token = create_access_token(data={"sub": str(user_id), "tv": 0})
    return {"Authorization": f"Bearer {token}"}
