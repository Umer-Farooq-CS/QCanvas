"""
Concurrency/safety behaviour of the compute endpoints and middleware:
the event loop stays responsive during simulations, simulations are bounded,
oversized circuits are rejected, and the audit log never touches the request path.
"""
import asyncio
import threading
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from conftest import make_user

QASM = 'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\nh q[0];\ncx q[0], q[1];\n'


@pytest.fixture
def anonymous(app):
    from app.api.routes.auth import get_optional_user

    app.dependency_overrides[get_optional_user] = lambda: None
    yield
    app.dependency_overrides.pop(get_optional_user, None)


@pytest.fixture
def slow_simulation(monkeypatch):
    """Replace the simulator with a blocking (CPU-like) call and track concurrency."""
    from app.api.routes import simulator

    state = {"running": 0, "max_running": 0, "calls": 0, "duration": 0.5}
    lock = threading.Lock()

    def fake_run(qasm_code, backend="cirq", shots=1024):
        with lock:
            state["running"] += 1
            state["calls"] += 1
            state["max_running"] = max(state["max_running"], state["running"])
        try:
            time.sleep(state["duration"])  # blocks the calling thread like a real simulation
        finally:
            with lock:
                state["running"] -= 1
        return {"success": True, "results": {"counts": {"00": shots}, "metadata": {}}, "backend": backend, "shots": shots}

    monkeypatch.setattr(simulator.simulation_service, "execute_qasm_with_qsim", fake_run)
    monkeypatch.setattr(simulator, "_record_qsim_success", lambda *a, **k: None)
    return state


def _async_client(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# Event loop responsiveness + bounded concurrency
# ---------------------------------------------------------------------------

def test_event_loop_stays_responsive_during_simulation(app, override_db, anonymous, slow_simulation, monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "SIM_MAX_CONCURRENCY", 2)
    slow_simulation["duration"] = 1.0

    async def scenario():
        async with _async_client(app) as client:
            sims = [
                asyncio.create_task(client.post("/api/simulator/execute-qsim", json={"qasm_input": QASM}))
                for _ in range(2)
            ]
            await asyncio.sleep(0.2)  # simulations are now running
            health_times = []
            for _ in range(5):
                t0 = time.perf_counter()
                r = await client.get("/api/health")
                health_times.append(time.perf_counter() - t0)
                assert r.status_code == 200
            results = await asyncio.gather(*sims)
            return health_times, results

    health_times, results = asyncio.run(scenario())
    assert all(r.status_code == 200 for r in results)
    # Before the fix each health check waited for the simulation to finish (~1s).
    assert max(health_times) < 0.3, health_times


def test_simulations_are_bounded_per_worker(app, override_db, anonymous, slow_simulation, monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "SIM_MAX_CONCURRENCY", 2)
    monkeypatch.setattr(settings, "SIM_QUEUE_TIMEOUT_SECONDS", 30)
    slow_simulation["duration"] = 0.3

    async def scenario():
        async with _async_client(app) as client:
            return await asyncio.gather(
                *[client.post("/api/simulator/execute-qsim", json={"qasm_input": QASM}) for _ in range(6)]
            )

    results = asyncio.run(scenario())
    assert [r.status_code for r in results] == [200] * 6
    assert slow_simulation["calls"] == 6
    assert slow_simulation["max_running"] <= 2


def test_busy_simulator_returns_503_with_retry_after(app, override_db, anonymous, slow_simulation, monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "SIM_MAX_CONCURRENCY", 1)
    monkeypatch.setattr(settings, "SIM_QUEUE_TIMEOUT_SECONDS", 0.2)
    slow_simulation["duration"] = 1.0

    async def scenario():
        async with _async_client(app) as client:
            return await asyncio.gather(
                *[client.post("/api/simulator/execute-qsim", json={"qasm_input": QASM}) for _ in range(2)]
            )

    codes = sorted(r.status_code for r in asyncio.run(scenario()))
    assert codes == [200, 503]


def test_db_connection_released_before_simulation(app, override_db, slow_simulation, monkeypatch):
    """The auth lookup's pooled connection must not be pinned for the whole simulation."""
    from app.api.routes.auth import get_optional_user

    user = make_user()
    app.dependency_overrides[get_optional_user] = lambda: user
    closed_before_run = []

    from app.api.routes import simulator

    def run(qasm_code, backend="cirq", shots=1024):
        closed_before_run.append(override_db.close.called)
        return {"success": True, "results": {"counts": {}, "metadata": {}}, "backend": backend, "shots": shots}

    monkeypatch.setattr(simulator.simulation_service, "execute_qasm_with_qsim", run)
    try:
        r = TestClient(app).post("/api/simulator/execute-qsim", json={"qasm_input": QASM})
        assert r.status_code == 200
        assert closed_before_run == [True]
    finally:
        app.dependency_overrides.pop(get_optional_user, None)


# ---------------------------------------------------------------------------
# Server-side caps
# ---------------------------------------------------------------------------

def test_count_declared_qubits():
    from app.api.routes.simulator import count_declared_qubits

    assert count_declared_qubits(QASM) == 2
    assert count_declared_qubits("OPENQASM 2.0;\nqreg q[5];\nqreg a[3];\ncreg c[5];") == 8
    assert count_declared_qubits("OPENQASM 3.0;\nqubit a;\nqubit b;\nqubit[4] r;") == 6
    assert count_declared_qubits("OPENQASM 3.0;\nconst int n = 30;\nqubit[n] q;") == 30
    assert count_declared_qubits("OPENQASM 3.0;\n// qubit[100] big;\n/* qubit[50] x; */\nqubit[3] q;") == 3


@pytest.mark.parametrize(
    "payload, fragment",
    [
        ({"qasm_input": "OPENQASM 3.0;\nqubit[30] q;\nh q[0];"}, "at most 24 qubits"),
        ({"qasm_input": "OPENQASM 2.0;\nqreg q[25];\nh q[0];"}, "at most 24 qubits"),
        ({"qasm_input": QASM, "shots": 1_000_000}, "maximum is 100,000 shots"),
        ({"qasm_input": QASM, "shots": -5}, "cannot be negative"),
        ({"qasm_input": QASM, "shots": "lots"}, "whole number"),
        ({"qasm_input": QASM + "// " + "x" * 300_000}, "too large"),
    ],
)
def test_simulation_caps_reject_with_clear_message(app, override_db, anonymous, slow_simulation, monkeypatch, payload, fragment):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "SIM_MAX_QUBITS", 24)
    monkeypatch.setattr(settings, "SIM_MAX_SHOTS", 100_000)
    r = TestClient(app).post("/api/simulator/execute-qsim", json=payload)
    assert r.status_code == 400
    body = r.json()
    assert body["success"] is False
    assert fragment in body["error"]
    assert slow_simulation["calls"] == 0


def test_pennylane_has_its_own_lower_cap(app, override_db, anonymous, slow_simulation, monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "SIM_MAX_QUBITS", 24)
    monkeypatch.setattr(settings, "SIM_MAX_QUBITS_PENNYLANE", 12)
    client = TestClient(app)
    qasm = "OPENQASM 3.0;\nqubit[16] q;"
    r = client.post("/api/simulator/execute-qsim", json={"qasm_input": qasm, "backend": "pennylane"})
    assert r.status_code == 400 and "at most 12 qubits" in r.json()["error"]
    assert client.post("/api/simulator/execute-qsim", json={"qasm_input": qasm, "backend": "cirq"}).status_code == 200


def test_caps_are_configurable(app, override_db, anonymous, slow_simulation, monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "SIM_MAX_QUBITS", 30)
    r = TestClient(app).post("/api/simulator/execute-qsim", json={"qasm_input": "OPENQASM 3.0;\nqubit[30] q;"})
    assert r.status_code == 200
    assert slow_simulation["calls"] == 1


def test_legacy_execute_has_lower_qubit_cap(app, override_db, anonymous, monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "SIM_LEGACY_MAX_QUBITS", 16)
    client = TestClient(app)
    r = client.post("/api/simulator/execute", json={"qasm_code": "OPENQASM 3.0;\nqubit[20] q;"})
    assert r.status_code == 400
    assert "at most 16 qubits" in r.json()["detail"]
    ok = client.post("/api/simulator/execute", json={"qasm_code": QASM, "shots": 100})
    assert ok.status_code == 200 and ok.json()["success"] is True


# ---------------------------------------------------------------------------
# Converter offloading
# ---------------------------------------------------------------------------

def test_conversion_uses_isolated_child_process(app, override_db, anonymous, monkeypatch):
    """/convert must go through the isolated runner (user code may be exec'd)."""
    from app.api.routes import converter

    calls = []

    async def fake_isolated(code, framework, style="classic"):
        calls.append((framework, style))
        return {"success": True, "qasm_code": "OPENQASM 3.0;", "framework": framework,
                "qasm_version": "3.0", "conversion_stats": None}

    def in_process_must_not_run(*a, **k):
        raise AssertionError("in-process conversion must not be used by /convert")

    monkeypatch.setattr(converter.conversion_service, "convert_to_qasm_isolated", fake_isolated)
    monkeypatch.setattr(converter.conversion_service, "convert_to_qasm", in_process_must_not_run)
    r = TestClient(app).post("/api/converter/convert", json={"code": "qc = QuantumCircuit(1)", "framework": "qiskit"})
    assert r.status_code == 200, r.text
    assert r.json()["success"] is True
    assert calls == [("qiskit", "classic")]


# ---------------------------------------------------------------------------
# Audit log middleware
# ---------------------------------------------------------------------------

class _RecordingWriter:
    def __init__(self, fail=False):
        self.records = []
        self.fail = fail

    def submit(self, record):
        if self.fail:
            raise RuntimeError("queue exploded")
        self.records.append(record)


def _mini_app(writer):
    from fastapi import FastAPI
    from app.core.middleware import AuditLogMiddleware

    mini = FastAPI()

    @mini.get("/api/things")
    def things():
        return {"ok": True}

    @mini.get("/api/health")
    def health():
        return {"status": "healthy"}

    @mini.get("/api/boom")
    def boom():
        raise RuntimeError("boom")

    mini.add_middleware(AuditLogMiddleware, writer=writer)
    return mini


def test_audit_middleware_records_without_db_on_request_path(monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "AUDIT_LOG_ENABLED", True)
    monkeypatch.setattr(settings, "FORWARDED_TRUSTED_HOPS", 1)
    writer = _RecordingWriter()
    client = TestClient(_mini_app(writer), raise_server_exceptions=False)

    assert client.get("/api/things", headers={"X-Forwarded-For": "6.6.6.6, 203.0.113.9"}).status_code == 200
    assert client.get("/api/health").status_code == 200  # skipped: noise
    assert client.options("/api/things").status_code in (200, 405)  # skipped
    assert client.get("/api/boom").status_code == 500

    paths = [(r["path"], r["status_code"]) for r in writer.records]
    assert paths == [("/api/things", 200), ("/api/boom", 500)]
    assert writer.records[0]["ip"] == "203.0.113.9"


def test_audit_failures_never_fail_the_request(monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "AUDIT_LOG_ENABLED", True)
    client = TestClient(_mini_app(_RecordingWriter(fail=True)))
    assert client.get("/api/things").status_code == 200


def test_audit_writer_batches_and_survives_db_errors():
    from app.core.middleware import AuditLogWriter

    executed = []

    class FakeSession:
        def __init__(self, broken=False):
            self.broken = broken

        def execute(self, stmt, rows):
            if self.broken:
                raise RuntimeError("database is down")
            executed.append(list(rows))

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    writer = AuditLogWriter(session_factory=FakeSession, batch_size=50, flush_interval=0.05, max_queue=100)
    for i in range(120):
        writer.submit({"path": f"/api/x/{i}", "method": "GET", "status_code": 200, "ip": "1.2.3.4",
                       "user_agent": "pytest", "token": None, "response_time_ms": 3})
    writer.shutdown(timeout=2)
    total = sum(len(batch) for batch in executed)
    assert total + writer.dropped == 120
    assert all(len(batch) <= 50 for batch in executed)
    assert executed and executed[0][0]["endpoint"].startswith("/api/x/")

    broken = AuditLogWriter(session_factory=lambda: FakeSession(broken=True), batch_size=10, flush_interval=0.05)
    broken.submit({"path": "/api/y", "method": "POST", "status_code": 201})
    broken.shutdown(timeout=2)  # must not raise
    assert broken.dropped == 1


def test_security_headers_still_applied(app):
    r = TestClient(app).get("/api/health")
    assert r.status_code == 200
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert "Content-Security-Policy" in r.headers


def test_health_is_served_without_redirect(app):
    client = TestClient(app)
    for path in ("/api/health", "/api/health/", "/health"):
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 200, path
