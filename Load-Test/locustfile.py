import os
import re
from urllib.parse import urlparse

from locust import HttpUser, between, events, task

PRODUCTION_HOSTS = {"qcanvas.codes", "www.qcanvas.codes", "api.qcanvas.codes"}
MAX_PRODUCTION_USERS = 200
MAX_PRODUCTION_SPAWN_RATE = 20
MAX_PRODUCTION_RUNTIME_SECONDS = 600  # 10 minutes

QISKIT_CODE = """from qiskit import QuantumCircuit
qc = QuantumCircuit(2, 2)
qc.h(0)
qc.cx(0, 1)
qc.measure([0, 1], [0, 1])
"""

QASM_CODE = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];
"""


def _runtime_seconds(value) -> int:
    # Safely handle if Locust passes an int or None instead of a string
    if not value or isinstance(value, int):
        return 0
    match = re.fullmatch(r"([1-9][0-9]*)(s|m)", str(value).strip().lower())
    if not match:
        return 0
    amount = int(match.group(1))
    return amount * (60 if match.group(2) == "m" else 1)


@events.test_start.add_listener
def enforce_production_limits(environment, **_kwargs):
    if not environment.host:
        return

    hostname = (urlparse(environment.host).hostname or "").lower()
    if hostname not in PRODUCTION_HOSTS:
        return

    if os.environ.get("LOAD_TEST_ALLOW_PRODUCTION") != "YES":
        raise RuntimeError(
            "Production load test blocked. Set LOAD_TEST_ALLOW_PRODUCTION=YES "
            "only after confirming the test window and monitoring are ready."
        )

    if not environment.host.lower().startswith("https://"):
        raise RuntimeError("Production load tests must use HTTPS.")

    options = environment.parsed_options
    if options:
        users = getattr(options, "users", None) or 0
        spawn_rate = getattr(options, "spawn_rate", None) or 0
        run_time = getattr(options, "run_time", None)

        if users > MAX_PRODUCTION_USERS:
            raise RuntimeError(f"Production load tests capped at {MAX_PRODUCTION_USERS} users.")
        if spawn_rate > MAX_PRODUCTION_SPAWN_RATE:
            raise RuntimeError(f"Spawn rate capped at {MAX_PRODUCTION_SPAWN_RATE}/sec.")
        if _runtime_seconds(run_time) > MAX_PRODUCTION_RUNTIME_SECONDS:
            raise RuntimeError("Production load tests capped at 10 minutes per run.")


class QCanvasWorkshopUser(HttpUser):
    wait_time = between(1, 3)

    @task(1)
    def compile_qiskit_circuit(self):
        # Double-check this path against your backend router (e.g. FastAPI / Express)
        self._post_and_check(
            "/api/converter/convert",
            {
                "code": QISKIT_CODE,
                "framework": "qiskit",
                "style": "classic",
            },
            "compile_qiskit",
        )

    @task(1)
    def simulate_qasm_circuit(self):
        # Double-check this path against your backend router
        self._post_and_check(
            "/api/simulator/execute",
            {
                "qasm_code": QASM_CODE,
                "backend": "statevector",
                "shots": 128,
            },
            "simulate_qasm",
        )

    def _post_and_check(self, path, payload, request_name):
        headers = {"Content-Type": "application/json"}
        with self.client.post(
            path,
            json=payload,
            headers=headers,
            name=request_name,
            timeout=30,
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}: {response.text[:100]}")
                return

            try:
                result = response.json()
            except ValueError:
                response.failure("Response was not valid JSON")
                return

            if not isinstance(result, dict) or result.get("success") is not True:
                response.failure(f"API response success!=True: {result}")