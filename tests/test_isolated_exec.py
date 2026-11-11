"""
Tests for backend/app/services/isolated_exec.py and the isolated hybrid /
conversion paths.

No database or Docker needed.  On Windows/macOS the children use the `spawn`
start method (each run starts a fresh interpreter, a few seconds each); on
Linux they come from the warm, clean fork server.

Run:  python -m pytest tests/test_isolated_exec.py -v
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT), str(_ROOT / "backend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.services import isolated_exec as ie  # noqa: E402


# ---------------------------------------------------------------------------
# Job helpers (module level so the child process can import them)
# ---------------------------------------------------------------------------

def job_dump_env() -> dict:
    data = {"environ": dict(os.environ), "proc_environ": None}
    try:
        with open("/proc/self/environ", "rb") as fh:
            data["proc_environ"] = fh.read().decode("utf-8", "replace")
    except OSError as exc:
        data["proc_environ_error"] = type(exc).__name__
    return data


def job_hard_exit(code: int) -> None:
    os._exit(code)


def job_memory_error() -> None:
    raise MemoryError()


def job_return_odd_types() -> dict:
    return {"complex": 1 + 2j, "tuple": (1, 2), "set": {3}}


def job_allocate(megabytes: int) -> int:
    blob = bytearray(megabytes * 1024 * 1024)
    return len(blob)


def job_identity() -> dict:
    info = {"pid": os.getpid(), "modules": sorted(m for m in sys.modules if m.split(".")[0] in (
        "cirq", "qiskit", "pennylane", "app", "sqlalchemy", "uvicorn"))}
    if hasattr(os, "getuid"):
        info.update(uid=os.getuid(), euid=os.geteuid(), pgid=os.getpgid(0))
    try:
        info["fds"] = sorted(os.listdir("/proc/self/fd"))
        info["sockets"] = []
        for fd in info["fds"]:
            try:
                target = os.readlink(f"/proc/self/fd/{fd}")
            except OSError:
                continue
            if target.startswith("socket:"):
                info["sockets"].append(fd)
    except OSError:
        pass
    return info


def _process_gone(pid) -> bool:
    if pid is None:
        return True
    try:
        import psutil
    except ImportError:  # pragma: no cover
        return True
    if not psutil.pid_exists(pid):
        return True
    try:
        return psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
    except psutil.Error:
        return True


BELL = '''import cirq
from qcanvas import compile
import qsim

q = cirq.LineQubit.range(2)
circuit = cirq.Circuit([
    cirq.H(q[0]),
    cirq.CNOT(q[0], q[1]),
    cirq.measure(q[0], q[1], key='result')
])
qasm = compile(circuit, framework="cirq")
for i in range(3):
    result = qsim.run(qasm, shots=100, backend="cirq")
    print(f"Run {i+1}: {result.counts}")
'''


def _hybrid(code: str, timeout: float = 30):
    from qcanvas.sandbox import execute_sandboxed_job

    return ie.run_isolated(execute_sandboxed_job, kwargs={"code": code, "online_mode": False},
                           timeout=timeout, label="test")


# ---------------------------------------------------------------------------
# Timeouts, crashes, limits
# ---------------------------------------------------------------------------

def test_infinite_loop_is_killed_within_timeout():
    timeout = 2
    outcome = _hybrid("while True:\n    pass\n", timeout=timeout)
    assert not outcome.ok
    assert outcome.timed_out
    assert outcome.error_type == "TimeoutError"
    run_seconds = outcome.duration - outcome.startup_seconds
    assert run_seconds <= timeout + 2.5, f"took {run_seconds:.2f}s after start-up"
    assert _process_gone(outcome.pid), "child process is still alive"


def test_sleep_is_killed_too():
    outcome = _hybrid("import time\ntime.sleep(60)\n", timeout=1)
    assert outcome.timed_out and outcome.error_type == "TimeoutError"
    assert outcome.duration - outcome.startup_seconds <= 3.5


def test_child_crash_becomes_clean_error():
    outcome = ie.run_isolated(job_hard_exit, args=(7,), timeout=10)
    assert not outcome.ok
    assert outcome.error_type == "WorkerCrashed"
    assert "7" in outcome.error


def test_memory_error_in_child_is_reported():
    outcome = ie.run_isolated(job_memory_error, timeout=10)
    assert not outcome.ok and outcome.error_type == "MemoryError"


@pytest.mark.skipif(os.name != "posix", reason="RLIMIT_AS is POSIX only")
def test_address_space_limit_stops_huge_allocation():
    outcome = ie.run_isolated(job_allocate, args=(4096,), timeout=20, memory_mb=256)
    assert not outcome.ok
    assert outcome.error_type == "MemoryError"


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="fork server is Linux only")
def test_forkserver_children_are_warm_and_clean():
    if ie.START_METHOD != "forkserver":
        pytest.skip("USER_CODE_START_METHOD overrides the fork server")
    ie.run_isolated(job_identity, timeout=60)  # first job may wait for the preload
    outcome = ie.run_isolated(job_identity, timeout=20)
    assert outcome.ok, outcome.error
    info = outcome.value
    # Heavy libraries come pre-imported from the fork server ...
    assert any(m == "cirq" for m in info["modules"]), info["modules"]
    # ... the API itself (settings, DB engine, uvicorn) does not.
    assert "uvicorn" not in info["modules"] and "sqlalchemy" not in info["modules"]
    assert outcome.startup_seconds < 3, f"start-up took {outcome.startup_seconds:.2f}s"
    # Own process group (so the whole group can be killed).
    assert info["pgid"] == info["pid"]


@pytest.mark.skipif(not hasattr(os, "geteuid"), reason="POSIX only")
def test_child_drops_root_privileges():
    if os.geteuid() != 0 or ie.RUN_AS is None:
        pytest.skip("only relevant when the API runs as root")
    outcome = ie.run_isolated(job_identity, timeout=20)
    assert outcome.ok, outcome.error
    assert outcome.value["uid"] == ie.RUN_AS[0] != 0
    assert outcome.value["euid"] == ie.RUN_AS[0]


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="/proc is Linux only")
def test_child_does_not_inherit_listening_socket():
    import socket

    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen()
    try:
        outcome = ie.run_isolated(job_identity, timeout=20)
        assert outcome.ok, outcome.error
        if ie.START_METHOD in ("forkserver", "spawn"):
            assert str(server.fileno()) not in outcome.value.get("sockets", [])
    finally:
        server.close()


def test_results_are_json_not_pickle():
    outcome = ie.run_isolated(job_return_odd_types, timeout=10)
    assert outcome.ok
    assert outcome.value == {"complex": [1.0, 2.0], "tuple": [1, 2], "set": [3]}


# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------

SECRETS = {
    "SECRET_KEY": "s3cr3t-key",
    "DATABASE_URL": "postgresql://u:pw@db/x",
    "POSTGRES_PASSWORD": "pgpw",
    "AWS_SECRET_ACCESS_KEY": "awskey",
    "AWS_ACCESS_KEY_ID": "awsid",
    "RESEND_API_KEY": "resend",
    "OTP_PEPPER": "pepper",
    "CIRQ_RAG_API_KEY": "rag",
    "FASTQSIM_API_TOKEN": "fq-token",
    "FASTQUBIT_SESSION_TOKEN": "fq-session",
    "SOME_NEW_SERVICE_TOKEN": "tok",
    "GITHUB_PASSWORD": "gh",
}


def test_secrets_are_not_visible_in_child(monkeypatch):
    for key, value in SECRETS.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("QCANVAS_HARMLESS_FLAG", "1")
    outcome = ie.run_isolated(job_dump_env, timeout=20)
    assert outcome.ok, outcome.error
    env = outcome.value["environ"]
    for key, value in SECRETS.items():
        assert key not in env
        assert value not in "".join(env.values())
    # Not on the allow-list either.
    assert "QCANVAS_HARMLESS_FLAG" not in env
    # Thread pools of numeric libraries are pinned to one thread per job.
    assert env.get("OMP_NUM_THREADS") == "1"
    proc_env = outcome.value.get("proc_environ")
    if proc_env:  # Linux; with the fork server the env block itself is clean
        for value in SECRETS.values():
            if ie.START_METHOD == "forkserver":
                assert value not in proc_env


def test_explicit_env_passthrough(monkeypatch):
    outcome = ie.run_isolated(job_dump_env, timeout=20, env={"FASTQUBIT_SESSION_TOKEN": "per-run"})
    assert outcome.ok
    assert outcome.value["environ"].get("FASTQUBIT_SESSION_TOKEN") == "per-run"


def test_secret_name_classifier():
    for name in SECRETS:
        assert ie.is_secret_env_name(name), name
    for name in ("PATH", "HOME", "LANG", "PYTHONPATH", "OMP_NUM_THREADS"):
        assert not ie.is_secret_env_name(name), name


# ---------------------------------------------------------------------------
# Hybrid execution through the isolated path
# ---------------------------------------------------------------------------

def test_bell_example_returns_counts():
    outcome = _hybrid(BELL)
    assert outcome.ok, outcome.error
    data = outcome.value
    assert data["success"], data
    sims = data["simulation_results"]
    assert len(sims) == 3
    for sim in sims:
        counts = sim["counts"]
        assert sum(counts.values()) == 100
        assert set(counts) <= {"00", "11"}
    assert "Run 3:" in data["stdout"]


@pytest.mark.parametrize("code", [
    "import os\nos.system('echo pwned')",
    "__import__('os')",
    "import importlib\nimportlib.import_module('os')",
    "import random\nrandom._os.getpid()",
    "x = ().__class__.__base__.__subclasses__()",
])
def test_escape_attempts_blocked_in_child(code):
    outcome = _hybrid(code)
    assert outcome.ok  # the child itself worked fine...
    data = outcome.value
    assert not data["success"]  # ...but the user code was refused
    assert data["error_type"] == "SecurityViolationError", data


def test_concurrent_runs_do_not_mix_stdout_or_results():
    code_a = BELL.replace('print(f"Run', 'print(f"AAA Run')
    code_b = (
        "import cirq\nfrom qcanvas import compile\nimport qsim\n"
        "q = cirq.LineQubit(0)\n"
        "c = cirq.Circuit([cirq.X(q), cirq.measure(q, key='m')])\n"
        "qasm = compile(c, framework='cirq')\n"
        "for i in range(5):\n"
        "    r = qsim.run(qasm, shots=10, backend='cirq')\n"
        "    print('BBB', r.counts)\n"
    )
    from qcanvas.sandbox import execute_sandboxed_job

    async def both():
        return await asyncio.gather(
            ie.run_isolated_async(execute_sandboxed_job, kwargs={"code": code_a, "online_mode": False},
                                  timeout=60, label="a"),
            ie.run_isolated_async(execute_sandboxed_job, kwargs={"code": code_b, "online_mode": False},
                                  timeout=60, label="b"),
        )

    out_a, out_b = asyncio.run(both())
    assert out_a.ok and out_b.ok
    a, b = out_a.value, out_b.value
    assert a["success"] and b["success"], (a, b)
    assert "AAA" in a["stdout"] and "BBB" not in a["stdout"]
    assert "BBB" in b["stdout"] and "AAA" not in b["stdout"]
    assert len(a["simulation_results"]) == 3
    assert len(b["simulation_results"]) == 5
    assert all(set(s["counts"]) == {"1"} for s in b["simulation_results"])


# ---------------------------------------------------------------------------
# Concurrency cap / busy handling
# ---------------------------------------------------------------------------

def test_sync_busy_raises_503():
    acquired = 0
    try:
        while ie._thread_slots.acquire(blocking=False):
            acquired += 1
        with pytest.raises(ie.UserCodeBusyError) as info:
            ie.run_isolated(job_dump_env, timeout=5, queue_timeout=0.2)
        assert getattr(info.value, "status_code", None) == 503
        assert "try again" in str(info.value).lower()
    finally:
        for _ in range(acquired):
            ie._thread_slots.release()


def test_async_busy_raises_503(monkeypatch):
    monkeypatch.setattr(ie, "QUEUE_TIMEOUT", 0.2)

    async def scenario():
        sem = ie._get_loop_semaphore()
        for _ in range(ie.MAX_CONCURRENCY):
            await sem.acquire()
        started = time.monotonic()
        try:
            with pytest.raises(ie.UserCodeBusyError):
                await ie.run_isolated_async(job_dump_env, timeout=5)
        finally:
            for _ in range(ie.MAX_CONCURRENCY):
                sem.release()
        return time.monotonic() - started

    waited = asyncio.run(scenario())
    assert waited < 2


def test_event_loop_not_blocked_while_job_runs():
    async def scenario():
        ticks = 0

        async def ticker():
            nonlocal ticks
            while True:
                await asyncio.sleep(0.05)
                ticks += 1

        task = asyncio.create_task(ticker())
        outcome = await ie.run_isolated_async(job_hard_exit, args=(0,), timeout=10)
        task.cancel()
        return outcome, ticks

    outcome, ticks = asyncio.run(scenario())
    assert outcome.error_type == "WorkerCrashed"  # exited without a result
    assert ticks >= 3, "event loop was blocked while waiting for the child"


# ---------------------------------------------------------------------------
# Conversion through the isolated path
# ---------------------------------------------------------------------------

CONVERT_CASES = {
    "cirq": (
        "import cirq\n\n"
        "def get_circuit():\n"
        "    q0, q1 = cirq.LineQubit.range(2)\n"
        "    return cirq.Circuit(cirq.H(q0), cirq.CNOT(q0, q1), cirq.measure(q0, q1, key='m'))\n"
    ),
    "qiskit": (
        "from qiskit import QuantumCircuit\n\n"
        "def get_circuit():\n"
        "    qc = QuantumCircuit(2, 2)\n"
        "    qc.h(0)\n"
        "    qc.cx(0, 1)\n"
        "    qc.measure([0, 1], [0, 1])\n"
        "    return qc\n"
    ),
    "pennylane": (
        "import pennylane as qml\n\n"
        "def get_circuit():\n"
        "    dev = qml.device('default.qubit', wires=2)\n"
        "    @qml.qnode(dev)\n"
        "    def circuit():\n"
        "        qml.Hadamard(wires=0)\n"
        "        qml.CNOT(wires=[0, 1])\n"
        "        return qml.probs(wires=[0, 1])\n"
        "    return circuit\n"
    ),
}


@pytest.fixture(scope="module")
def conversion_service():
    from app.services.conversion_service import ConversionService

    return ConversionService()


@pytest.mark.parametrize("framework", sorted(CONVERT_CASES))
def test_isolated_conversion_returns_qasm(conversion_service, framework):
    result = asyncio.run(conversion_service.convert_to_qasm_isolated(
        CONVERT_CASES[framework], framework, "classic"))
    assert result["success"], result
    assert "OPENQASM 3" in result["qasm_code"]
    assert result["framework"] == framework


def test_isolated_conversion_infinite_loop_times_out(conversion_service):
    code = "import cirq\nwhile True:\n    pass\n"
    started = time.monotonic()
    result = asyncio.run(conversion_service.convert_to_qasm_isolated(code, "cirq", timeout=2))
    assert not result["success"]
    assert "timed out" in result["error"].lower()
    assert time.monotonic() - started < ie.STARTUP_TIMEOUT + 5


def test_isolated_conversion_does_not_leak_parent_env(conversion_service, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "parent-secret-value")
    code = (
        "import cirq, os\n"
        "q = cirq.LineQubit.range(1)\n"
        "c = cirq.Circuit([cirq.H(q[0])] * (1 if os.environ.get('SECRET_KEY') is None else 2))\n"
        "def get_circuit():\n"
        "    return c\n"
    )
    result = asyncio.run(conversion_service.convert_to_qasm_isolated(code, "cirq"))
    if result["success"]:
        # one H gate means SECRET_KEY was not visible to the user code
        assert result["qasm_code"].count("h q") <= 1, result["qasm_code"]


def test_parse_loop_expansion_is_bounded(conversion_service):
    from app.services import conversion_service as cs

    code = (
        "from qiskit import QuantumCircuit\n"
        "qc = QuantumCircuit(2)\n"
        "for i in range(1000000000):\n"
        "    qc.h(0)\n"
    )
    started = time.monotonic()
    result = conversion_service.parse_circuit_gates(code, "qiskit")
    assert time.monotonic() - started < 5
    assert result["success"]
    assert 0 < len(result["gates"]) <= cs.PARSE_MAX_GATES


def test_parse_small_loop_still_expanded(conversion_service):
    code = (
        "from qiskit import QuantumCircuit\n"
        "qc = QuantumCircuit(3)\n"
        "for i in range(3):\n"
        "    qc.h(i)\n"
    )
    result = conversion_service.parse_circuit_gates(code, "qiskit")
    assert result["success"]
    assert [g["qubit"] for g in result["gates"]] == [0, 1, 2]


# ---------------------------------------------------------------------------
# Hybrid HTTP route (no DB: only the hybrid router is mounted)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def hybrid_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.routes import hybrid

    app = FastAPI()
    app.include_router(hybrid.router)
    return TestClient(app), hybrid


def test_route_timeout_is_capped(hybrid_client):
    _, hybrid = hybrid_client
    cap = hybrid.HYBRID_MAX_EXECUTION_TIME
    assert hybrid.effective_timeout(None) == cap
    assert hybrid.effective_timeout(10 ** 9) == cap
    assert hybrid.effective_timeout(5) == min(5, cap)
    assert hybrid.effective_timeout(-3) == 1


def test_route_executes_bell_example(hybrid_client, monkeypatch):
    monkeypatch.setenv("FASTQSIM_ONLINE_MODE", "false")  # no AWS lookups in tests
    client, _ = hybrid_client
    resp = client.post("/api/hybrid/execute", json={"code": BELL, "framework": "cirq", "timeout": 30})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"], body
    assert len(body["simulation_results"]) == 3


def test_route_infinite_loop_returns_timeout(hybrid_client, monkeypatch):
    monkeypatch.setenv("FASTQSIM_ONLINE_MODE", "false")
    client, _ = hybrid_client
    resp = client.post("/api/hybrid/execute", json={"code": "while True:\n    pass\n", "timeout": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert not body["success"]
    assert body["error_type"] == "TimeoutError"


def test_route_busy_returns_503(hybrid_client, monkeypatch):
    monkeypatch.setenv("FASTQSIM_ONLINE_MODE", "false")
    client, hybrid = hybrid_client

    async def always_busy(*args, **kwargs):
        raise ie.UserCodeBusyError()

    monkeypatch.setattr(hybrid, "run_isolated_async", always_busy)
    resp = client.post("/api/hybrid/execute", json={"code": "print(1)"})
    assert resp.status_code == 503
    body = resp.json()
    assert body["error_type"] == "ServerBusy"
    assert "try again" in body["detail"].lower()
    assert resp.headers.get("retry-after")
