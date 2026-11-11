"""
Rate limiting for a workshop: 100-200 students behind ONE venue NAT IP, API
behind a load balancer. Nobody may be locked out by someone else's traffic,
while a single client still gets throttled.
"""
import uuid

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi.errors import RateLimitExceeded

from conftest import bearer_for, make_user


def _scope(headers=None, client=("10.0.0.5", 1234)):
    raw = [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in (headers or {}).items()]
    return {"type": "http", "method": "GET", "path": "/", "headers": raw, "client": client, "query_string": b""}


# ---------------------------------------------------------------------------
# Client identification
# ---------------------------------------------------------------------------

def test_client_ip_is_entry_appended_by_trusted_proxy(monkeypatch):
    from app.config.settings import settings
    from app.core.middleware import client_ip_from_scope

    monkeypatch.setattr(settings, "CLIENT_IP_HEADER", "")
    monkeypatch.setattr(settings, "FORWARDED_TRUSTED_HOPS", 1)
    # Client tried to spoof "6.6.6.6"; the ALB appended the real address.
    scope = _scope({"X-Forwarded-For": "6.6.6.6, 203.0.113.7"})
    assert client_ip_from_scope(scope) == "203.0.113.7"

    # Cloudflare -> ALB: the client address is second from the right.
    monkeypatch.setattr(settings, "FORWARDED_TRUSTED_HOPS", 2)
    scope = _scope({"X-Forwarded-For": "6.6.6.6, 198.51.100.9, 172.68.1.1"})
    assert client_ip_from_scope(scope) == "198.51.100.9"


def test_client_ip_fallbacks(monkeypatch):
    from app.config.settings import settings
    from app.core.middleware import client_ip_from_scope

    monkeypatch.setattr(settings, "FORWARDED_TRUSTED_HOPS", 1)
    monkeypatch.setattr(settings, "CLIENT_IP_HEADER", "")
    assert client_ip_from_scope(_scope()) == "10.0.0.5"

    monkeypatch.setattr(settings, "CLIENT_IP_HEADER", "CF-Connecting-IP")
    scope = _scope({"CF-Connecting-IP": "192.0.2.44", "X-Forwarded-For": "1.1.1.1"})
    assert client_ip_from_scope(scope) == "192.0.2.44"

    monkeypatch.setattr(settings, "CLIENT_IP_HEADER", "")
    monkeypatch.setattr(settings, "FORWARDED_TRUSTED_HOPS", 0)
    assert client_ip_from_scope(_scope({"X-Forwarded-For": "1.1.1.1"})) == "10.0.0.5"


def test_rate_limit_key_prefers_user_then_ip(monkeypatch):
    from starlette.requests import Request as StarletteRequest
    from app.config.settings import settings
    from app.core.middleware import rate_limit_key
    from app.utils.jwt_auth import create_access_token

    monkeypatch.setattr(settings, "FORWARDED_TRUSTED_HOPS", 1)
    monkeypatch.setattr(settings, "CLIENT_IP_HEADER", "")
    user_id = uuid.uuid4()

    req = StarletteRequest(_scope({**bearer_for(user_id), "X-Forwarded-For": "203.0.113.7"}))
    assert rate_limit_key(req) == f"user:{user_id}"

    # Purpose tokens (e.g. admin approval links) are not sessions.
    intent = create_access_token(data={"sub": str(user_id), "intent": "admin_approval"})
    req = StarletteRequest(_scope({"Authorization": f"Bearer {intent}", "X-Forwarded-For": "203.0.113.7"}))
    assert rate_limit_key(req) == "ip:203.0.113.7"

    req = StarletteRequest(_scope({"Authorization": "Bearer not-a-jwt", "X-Forwarded-For": "203.0.113.7"}))
    assert rate_limit_key(req) == "ip:203.0.113.7"


# ---------------------------------------------------------------------------
# Storage selection / degradation
# ---------------------------------------------------------------------------

def test_storage_falls_back_to_memory_when_redis_unreachable(monkeypatch):
    from app.config.settings import settings
    from app.core.middleware import resolve_rate_limit_storage

    monkeypatch.setattr(settings, "RATE_LIMIT_STORAGE_URI", "auto")
    monkeypatch.setattr(settings, "REDIS_URL", "redis://127.0.0.1:1/0")
    monkeypatch.setattr(settings, "RATE_LIMIT_REDIS_TIMEOUT_SECONDS", 0.2)
    assert resolve_rate_limit_storage() == "memory://"

    monkeypatch.setattr(settings, "RATE_LIMIT_STORAGE_URI", "memory://")
    assert resolve_rate_limit_storage() == "memory://"


def test_requests_still_served_and_limited_if_redis_dies(monkeypatch):
    """A limiter configured for Redis that is down must not fail requests."""
    from app.config.settings import settings
    from app.core import middleware

    monkeypatch.setattr(settings, "RATE_LIMIT_STORAGE_URI", "redis://127.0.0.1:1/0")
    monkeypatch.setattr(settings, "RATE_LIMIT_REDIS_TIMEOUT_SECONDS", 0.2)
    broken = middleware._build_limiter()

    mini = FastAPI()
    mini.state.limiter = broken
    mini.add_exception_handler(RateLimitExceeded, middleware.rate_limit_exceeded_handler)

    @mini.get("/ping")
    @broken.limit("3/minute")
    def ping(request: Request):
        return {"ok": True}

    client = TestClient(mini)
    codes = [client.get("/ping").status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200]
    assert codes[3:] == [429, 429]  # enforced by the in-memory fallback


# ---------------------------------------------------------------------------
# Auth endpoints: a whole venue behind one IP can log in
# ---------------------------------------------------------------------------

def test_auth_literal_limits_are_replaced_by_configurable_ones(app):
    from app.core.middleware import limiter

    for name in (
        "app.api.routes.auth.login",
        "app.api.routes.auth.register",
        "app.api.routes.auth.send_signup_otp",
        "app.api.routes.auth.verify_signup_otp",
    ):
        assert name in limiter._dynamic_route_limits, name


def test_two_hundred_logins_from_one_ip_are_not_rate_limited(app, override_db):
    client = TestClient(app)
    headers = {"X-Forwarded-For": "198.51.100.23"}  # the venue NAT
    statuses = set()
    for i in range(200):
        r = client.post(
            "/api/auth/login",
            json={"email": f"student{i}@example.com", "password": "not-the-password"},
            headers=headers,
        )
        statuses.add(r.status_code)
    assert 429 not in statuses, statuses


def test_login_limit_is_configurable_and_returns_friendly_429(app, override_db, monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN", "3/minute")
    client = TestClient(app)
    headers = {"X-Forwarded-For": "198.51.100.24"}
    body = {"email": "someone@example.com", "password": "x" * 8}
    for _ in range(3):
        assert client.post("/api/auth/login", json=body, headers=headers).status_code != 429

    r = client.post("/api/auth/login", json=body, headers=headers)
    assert r.status_code == 429
    retry_after = int(r.headers["Retry-After"])
    assert 1 <= retry_after <= 60
    data = r.json()
    assert data["code"] == "rate_limited"
    assert data["retry_after"] == retry_after
    assert "try again" in data["detail"]

    # A different client IP has its own bucket.
    other = client.post("/api/auth/login", json=body, headers={"X-Forwarded-For": "192.0.2.1"})
    assert other.status_code != 429


def test_retry_after_is_exposed_to_browsers_via_cors(app, override_db, monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN", "1/minute")
    client = TestClient(app)
    headers = {"X-Forwarded-For": "198.51.100.25", "Origin": "https://qcanvas.codes"}
    body = {"email": "someone@example.com", "password": "x" * 8}
    client.post("/api/auth/login", json=body, headers=headers)
    r = client.post("/api/auth/login", json=body, headers=headers)
    assert r.status_code == 429
    assert "retry-after" in r.headers.get("access-control-expose-headers", "").lower()


# ---------------------------------------------------------------------------
# Compute endpoints: per-user buckets
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_simulation(monkeypatch):
    from app.api.routes import simulator

    calls = []

    def fake_run(qasm_code, backend="cirq", shots=1024):
        calls.append((backend, shots))
        return {"success": True, "results": {"counts": {"0": shots}, "metadata": {}}, "backend": backend, "shots": shots}

    monkeypatch.setattr(simulator.simulation_service, "execute_qasm_with_qsim", fake_run)
    monkeypatch.setattr(simulator, "_record_qsim_success", lambda *a, **k: None)
    return calls


QASM = 'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\nh q[0];\ncx q[0], q[1];\n'


def test_many_users_behind_one_ip_each_get_their_own_compute_bucket(app, override_db, fake_simulation, monkeypatch):
    from app.config.settings import settings
    from app.api.routes.auth import get_optional_user

    monkeypatch.setattr(settings, "RATE_LIMIT_COMPUTE_PER_USER", "2/minute")
    app.dependency_overrides[get_optional_user] = lambda: None
    try:
        client = TestClient(app)
        for _ in range(150):
            headers = {**bearer_for(uuid.uuid4()), "X-Forwarded-For": "198.51.100.30"}
            r = client.post("/api/simulator/execute-qsim", json={"qasm_input": QASM, "shots": 10}, headers=headers)
            assert r.status_code == 200, r.text
    finally:
        app.dependency_overrides.pop(get_optional_user, None)


def test_single_user_is_throttled_on_compute(app, override_db, fake_simulation, monkeypatch):
    from app.config.settings import settings
    from app.api.routes.auth import get_optional_user

    monkeypatch.setattr(settings, "RATE_LIMIT_COMPUTE_PER_USER", "3/minute")
    user = make_user()
    app.dependency_overrides[get_optional_user] = lambda: user
    try:
        client = TestClient(app)
        headers = {**bearer_for(user.id), "X-Forwarded-For": "198.51.100.31"}
        codes = [
            client.post("/api/simulator/execute-qsim", json={"qasm_input": QASM}, headers=headers).status_code
            for _ in range(4)
        ]
        assert codes == [200, 200, 200, 429]
    finally:
        app.dependency_overrides.pop(get_optional_user, None)


def test_rate_limiting_can_be_disabled(app, override_db, monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN", "1/minute")
    from app.core.middleware import limiter

    limiter.enabled = False
    client = TestClient(app)
    body = {"email": "someone@example.com", "password": "x" * 8}
    codes = {client.post("/api/auth/login", json=body).status_code for _ in range(3)}
    assert 429 not in codes
