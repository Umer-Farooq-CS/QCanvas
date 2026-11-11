"""
Regression tests for bugs found in the pre-workshop review.
"""
import asyncio
import json
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient

from conftest import bearer_for, make_user


# ---------------------------------------------------------------------------
# FastQSim online mode: successful cloud runs must be returned
# ---------------------------------------------------------------------------

def test_fastqsim_online_success_is_returned_not_rerun_locally(monkeypatch):
    from app.services import simulation_service as svc_module

    service = svc_module.SimulationService()
    job = SimpleNamespace(
        job_id="job-123",
        execution_time_seconds=0.25,
        cpu_seconds_total=0.1,
        peak_memory_mb=12.0,
        result=lambda: SimpleNamespace(counts={"00": 6, "11": 4}, probs={}, statevector=None),
    )
    service.fastqsim_client = SimpleNamespace(run=lambda **kwargs: job)
    monkeypatch.setattr(svc_module, "QSIM_AVAILABLE", True)
    monkeypatch.setattr(service, "_get_online_mode", lambda: True)
    monkeypatch.setattr(service, "_ensure_fastqsim_session", lambda force_refresh=False: (True, None))

    def local_run(*a, **k):
        raise AssertionError("local simulator must not run when the cloud run succeeded")

    monkeypatch.setattr(svc_module, "run_qasm", local_run)
    monkeypatch.setattr(svc_module, "RunArgs", lambda **k: k)

    result = service.execute_qasm_with_qsim("OPENQASM 3.0;\nqubit[2] q;", backend="cirq", shots=10)
    assert result["success"] is True
    assert result["results"]["counts"] == {"00": 6, "11": 4}
    assert result["results"]["metadata"]["online"] is True
    assert result["results"]["metadata"]["job_id"] == "job-123"
    assert result["results"]["probs"] == {"00": 0.6, "11": 0.4}


def test_fastqsim_online_retries_once_after_session_expiry(monkeypatch):
    from app.services import simulation_service as svc_module

    service = svc_module.SimulationService()
    attempts = []
    job = SimpleNamespace(job_id="job-2", result=lambda: SimpleNamespace(counts={"1": 5}))

    def run(**kwargs):
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("Session is no longer active")
        return job

    service.fastqsim_client = SimpleNamespace(run=run)
    refreshed = []
    monkeypatch.setattr(svc_module, "QSIM_AVAILABLE", True)
    monkeypatch.setattr(service, "_get_online_mode", lambda: True)
    monkeypatch.setattr(
        service, "_ensure_fastqsim_session", lambda force_refresh=False: (refreshed.append(force_refresh) or (True, None))
    )
    result = service.execute_qasm_with_qsim("OPENQASM 3.0;\nqubit q;", backend="cirq", shots=5)
    assert result["success"] is True
    assert len(attempts) == 2 and refreshed == [False, True]


def test_online_mode_lookup_is_cached(monkeypatch):
    from app.services import simulation_service as svc_module

    service = svc_module.SimulationService()
    monkeypatch.delenv("FASTQSIM_ONLINE_MODE", raising=False)
    calls = []
    monkeypatch.setattr(service, "_lookup_online_mode", lambda: calls.append(1) or False)
    for _ in range(5):
        assert service._get_online_mode() is False
    assert len(calls) == 1


# ---------------------------------------------------------------------------
# Gamification
# ---------------------------------------------------------------------------

def test_first_simulation_bonus_key_matches():
    from app.services.gamification_service import XP_REWARDS, first_time_bonus_xp

    assert first_time_bonus_xp("simulation_run") == XP_REWARDS["first_simulation"]
    assert first_time_bonus_xp("conversion") == XP_REWARDS["first_conversion"]
    assert first_time_bonus_xp("circuit_saved") is None


@pytest.fixture
def signed_in(app, override_db):
    from app.api.routes.auth import get_current_user

    user = make_user()
    app.dependency_overrides[get_current_user] = lambda: user
    yield user
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def award_spy(monkeypatch):
    from app.services.gamification_service import GamificationService

    calls = []

    def fake_award(db, user_id, activity_type, xp_amount=None, metadata=None):
        calls.append({"activity_type": activity_type, "xp_amount": xp_amount})
        return {"xp_gained": 100, "total_xp": 100, "level": 1, "old_level": 1, "level_up": False,
                "xp_to_next_level": 400, "is_first_time": False, "current_streak": 1, "new_achievements": []}

    monkeypatch.setattr(GamificationService, "award_xp", staticmethod(fake_award))
    return calls


def test_client_cannot_award_server_side_activities(app, signed_in, award_spy):
    client = TestClient(app)
    for activity in ("simulation_run", "conversion", "algorithm_shor", "made_up_type"):
        r = client.post("/api/gamification/activity", json={"activity_type": activity}, headers=bearer_for(signed_in.id))
        assert r.status_code == 400, (activity, r.text)
    assert award_spy == []


def test_client_xp_amount_is_ignored(app, signed_in, award_spy):
    r = TestClient(app).post(
        "/api/gamification/activity",
        json={"activity_type": "tutorial_completed", "xp_amount": 999999},
        headers=bearer_for(signed_in.id),
    )
    assert r.status_code == 201, r.text
    assert award_spy == [{"activity_type": "tutorial_completed", "xp_amount": None}]


def test_client_activity_reporting_is_rate_limited(app, signed_in, award_spy, monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "RATE_LIMIT_GAMIFICATION_ACTIVITY", "2/hour")
    client = TestClient(app)
    headers = bearer_for(signed_in.id)
    codes = [
        client.post("/api/gamification/activity", json={"activity_type": "tutorial_completed"}, headers=headers).status_code
        for _ in range(3)
    ]
    assert codes == [201, 201, 429]


def test_qsim_history_backend_enum_mapping():
    from app.api.routes import simulator
    from app.models.database_models import SimulationBackend

    added = []
    db = MagicMock()
    db.add.side_effect = added.append
    result = {"success": True, "results": {"counts": {}, "metadata": {"execution_time": "12.5ms"}}}

    for backend, expected in (("density_matrix", SimulationBackend.DENSITY_MATRIX), ("cirq", SimulationBackend.STATEVECTOR)):
        added.clear()
        simulator._record_qsim_success(db, str(uuid.uuid4()), {}, backend, 100, "OPENQASM 3.0;", result)
        sims = [obj for obj in added if obj.__class__.__name__ == "Simulation"]
        assert sims and sims[-1].backend == expected
        assert sims[-1].execution_time_ms == 12


# ---------------------------------------------------------------------------
# Files: ownerless files
# ---------------------------------------------------------------------------

def _file_db(fake_db, owner_id):
    file_obj = SimpleNamespace(id=1, user_id=owner_id)
    fake_db.query.return_value.filter.return_value.first.return_value = file_obj
    return file_obj


def test_regular_user_cannot_delete_ownerless_file(app, signed_in, override_db):
    _file_db(override_db, None)
    r = TestClient(app).delete("/api/files/1")
    assert r.status_code == 403
    override_db.delete.assert_not_called()


def test_owner_can_still_delete_own_file(app, signed_in, override_db):
    _file_db(override_db, signed_in.id)
    r = TestClient(app).delete("/api/files/1")
    assert r.status_code == 204
    override_db.delete.assert_called_once()


def test_admin_can_delete_ownerless_file(app, override_db):
    from app.api.routes.auth import get_current_user
    from app.models.database_models import UserRole

    admin = make_user(role=UserRole.ADMIN)
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        _file_db(override_db, None)
        assert TestClient(app).delete("/api/files/1").status_code == 204
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Cirq agent proxy: no credential forwarding, Retry-After preserved
# ---------------------------------------------------------------------------

def test_cirq_proxy_sends_only_api_key_and_returns_retry_after(app, override_db, monkeypatch):
    from app.api.routes import cirq_agent_proxy
    from app.api.routes.auth import get_current_user
    from app.config.settings import settings
    from app.models.database_models import UserRole

    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = {k.lower(): v for k, v in request.headers.items()}
        seen["url"] = str(request.url)
        return httpx.Response(429, json={"detail": "slow down"}, headers={"Retry-After": "17"})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        cirq_agent_proxy.httpx, "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    monkeypatch.setattr(settings, "CIRQ_RAG_API_KEY", "server-key")
    monkeypatch.setattr(settings, "CIRQ_AGENT_URL", "http://cirq.internal:8000")
    admin = make_user(role=UserRole.ADMIN)
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        r = TestClient(app).post(
            "/api/cirq-agent/api/v1/generate",
            json={"prompt": "bell state"},
            headers={"Authorization": "Bearer user-session-jwt", "Cookie": "session=abc", "X-Custom": "1"},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 429
    assert r.headers["Retry-After"] == "17"
    sent = seen["headers"]
    assert sent.get("x-api-key") == "server-key"
    assert "authorization" not in sent
    assert "cookie" not in sent
    assert "x-custom" not in sent
    assert sent.get("content-type") == "application/json"
    assert seen["url"] == "http://cirq.internal:8000/api/v1/generate"


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------

def _fake_request():
    from starlette.requests import Request

    return Request({"type": "http", "method": "GET", "path": "/x", "headers": [], "query_string": b""})


def test_unhandled_errors_do_not_leak_details(monkeypatch):
    from app.config.settings import settings
    from app.main import global_exception_handler

    monkeypatch.setattr(settings, "DEBUG", False)
    resp = asyncio.run(global_exception_handler(_fake_request(), RuntimeError("password=hunter2 at /srv/db.py")))
    body = json.loads(resp.body)
    assert resp.status_code == 500
    assert "hunter2" not in resp.body.decode()
    assert "type" not in body

    monkeypatch.setattr(settings, "DEBUG", True)
    resp = asyncio.run(global_exception_handler(_fake_request(), RuntimeError("visible in debug")))
    body = json.loads(resp.body)
    assert body["detail"] == "visible in debug" and body["type"] == "RuntimeError"
