"""
Workshop load test for the QCanvas backend: one Locust user == one attendee.

    python -m locust -f scripts/loadtest/locustfile.py --headless \
        -u 200 -r 0.8 -t 6m --host http://127.0.0.1:8000 --csv scripts/loadtest/results_A

Per attendee:
  start      POST /api/auth/guest (private guest session), GET /api/folders/tree
  loop       think 5-20 s between steps:
             POST /api/files/                  save a Qiskit Bell-state file
             POST /api/converter/convert       Qiskit -> OpenQASM
             POST /api/simulator/execute-qsim  run that QASM (qiskit backend, 1024 shots)
             POST /api/converter/parse         ~15% of iterations (circuit diagram)
             POST /api/hybrid/execute          ~10% of iterations (hybrid Python program)
  stop       POST /api/auth/logout (purges the private guest workspace)

Result classification (so rate limiting is not confused with crashes). Anything
that is not a success shows up as its own stats row, named after the endpoint:
  "<endpoint> [429]"   rate limited
  "<endpoint> [503]"   server busy / capacity full
  "<endpoint> [5xx]"   other server errors (500, 502, 504 ...)
  "<endpoint> [conn]"  connection error / timeout, no HTTP status
  "<endpoint> [4xx]"   any other client error (should not happen)
  "<endpoint>"         successes (this row's latency is the "healthy" latency)
All of these except the plain endpoint row are counted as failures.

Env knobs: THINK_MIN / THINK_MAX (seconds), GUEST_RETRIES, REQUEST_TIMEOUT.
"""
import os
import random

import gevent
from locust import HttpUser, between, events, task

THINK_MIN = float(os.getenv("THINK_MIN", "5"))
THINK_MAX = float(os.getenv("THINK_MAX", "20"))
GUEST_RETRIES = int(os.getenv("GUEST_RETRIES", "8"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "60"))

BELL_QISKIT = """from qiskit import QuantumCircuit

qc = QuantumCircuit(2, 2)
qc.h(0)
qc.cx(0, 1)
qc.measure([0, 1], [0, 1])
"""

# Used if /convert did not give us QASM back (keeps the simulator step independent).
BELL_QASM_FALLBACK = """OPENQASM 3.0;
include "stdgates.inc";
bit[2] c;
qubit[2] q;
h q[0];
cx q[0], q[1];
c[0] = measure q[0];
c[1] = measure q[1];
"""

HYBRID_QISKIT = """from qiskit import QuantumCircuit
from qcanvas import compile
import qsim

qc = QuantumCircuit(2, 2)
qc.h(0)
qc.cx(0, 1)
qc.measure([0, 1], [0, 1])

qasm = compile(qc, framework="qiskit")
result = qsim.run(qasm, shots=100, backend="qiskit")
print("Counts:", result.counts)
"""

# Custom counters reported at the end of the run.
_guest_attempts = {"total": 0, "ok": 0, "429": 0, "503": 0, "other": 0, "gave_up": 0}


class Attendee(HttpUser):
    wait_time = between(THINK_MIN, THINK_MAX)  # think time between loop iterations' steps
    token = None
    n_files = 0

    # ------------------------------------------------------------------ helpers
    def _think(self):
        gevent.sleep(random.uniform(THINK_MIN, THINK_MAX))

    def _call(self, method, path, **kw):
        """Issue a request and classify the outcome into a named stats row."""
        headers = kw.pop("headers", {})
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        with self.client.request(
            method, path, headers=headers, catch_response=True, timeout=REQUEST_TIMEOUT, **kw
        ) as resp:
            code = resp.status_code
            suffix = None
            if code == 0:
                suffix = "conn"
            elif code == 429:
                suffix = "429"
            elif code == 503:
                suffix = "503"
            elif code >= 500:
                suffix = "5xx"
            elif code >= 400:
                suffix = "4xx"
            if suffix:
                resp.request_meta["name"] = f"{path} [{suffix}]"
                resp.failure(f"HTTP {code}" if code else "connection error/timeout")
            else:
                # Compute endpoints answer 200 with success=false on logic errors.
                try:
                    body = resp.json()
                except Exception:
                    body = None
                if isinstance(body, dict) and body.get("success") is False:
                    resp.request_meta["name"] = f"{path} [app-error]"
                    resp.failure(f"success=false: {str(body.get('error'))[:120]}")
                else:
                    resp.success()
            return resp

    # ------------------------------------------------------------------ lifecycle
    def on_start(self):
        for attempt in range(1, GUEST_RETRIES + 1):
            _guest_attempts["total"] += 1
            resp = self._call("POST", "/api/auth/guest")
            if resp.status_code in (200, 201):
                _guest_attempts["ok"] += 1
                self.token = resp.json().get("access_token")
                break
            key = str(resp.status_code) if resp.status_code in (429, 503) else "other"
            _guest_attempts[key] += 1
            # A real attendee reloads the page / clicks again after a few seconds.
            gevent.sleep(random.uniform(3, 10))
        if not self.token:
            _guest_attempts["gave_up"] += 1
            self.stop()
            return
        self._call("GET", "/api/folders/tree")

    def on_stop(self):
        if self.token:
            try:
                self._call("POST", "/api/auth/logout")  # purges the guest's data
            except Exception:
                pass

    # ------------------------------------------------------------------ the workshop loop
    @task
    def work_cycle(self):
        self.n_files += 1
        self._call(
            "POST",
            "/api/files/",
            json={"filename": f"bell_{self.n_files}.py", "content": BELL_QISKIT, "is_main": False},
        )
        self._think()

        qasm = BELL_QASM_FALLBACK
        resp = self._call(
            "POST", "/api/converter/convert", json={"code": BELL_QISKIT, "framework": "qiskit"}
        )
        if resp.status_code == 200:
            try:
                qasm = resp.json().get("qasm_code") or qasm
            except Exception:
                pass
        self._think()

        self._call(
            "POST",
            "/api/simulator/execute-qsim",
            json={"qasm_input": qasm, "backend": "qiskit", "shots": 1024},
        )

        if random.random() < 0.15:
            self._think()
            self._call(
                "POST", "/api/converter/parse", json={"code": BELL_QISKIT, "framework": "qiskit"}
            )
        if random.random() < 0.10:
            self._think()
            self._call(
                "POST",
                "/api/hybrid/execute",
                json={"code": HYBRID_QISKIT, "framework": "qiskit", "timeout": 30},
            )


@events.quitting.add_listener
def _report_guest_attempts(environment, **_):
    print("\nGUEST CREATION (incl. client retries): " + ", ".join(f"{k}={v}" for k, v in _guest_attempts.items()))
    try:
        with open(os.getenv("GUEST_SUMMARY_FILE", "guest_summary.txt"), "w") as fh:
            fh.write(repr(_guest_attempts))
    except OSError:
        pass
