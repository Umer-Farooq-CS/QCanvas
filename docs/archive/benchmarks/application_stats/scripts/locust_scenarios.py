"""
locust_scenarios.py
===================
Locust user class definitions for QCanvas load testing.
Used by nb02_load_test.ipynb (as a reference / standalone).

To run standalone:
    locust -f locust_scenarios.py --headless -u 20 -r 5 -t 60s \
           --host http://localhost:8000

Or import the classes into a notebook via importlib.
"""

import json
import random

try:
    from locust import HttpUser, task, between, events
    LOCUST_AVAILABLE = True
except ImportError:
    LOCUST_AVAILABLE = False
    print("locust not installed – install with: pip install locust")

# ── Sample payloads ────────────────────────────────────────────────────────────

CIRQ_BELL = {
    "code": (
        "import cirq\n"
        "q0, q1 = cirq.LineQubit.range(2)\n"
        "circuit = cirq.Circuit([\n"
        "    cirq.H(q0),\n"
        "    cirq.CNOT(q0, q1),\n"
        "    cirq.measure(q0, q1, key='result')\n"
        "])"
    ),
    "framework": "cirq",
}

QISKIT_BELL = {
    "code": (
        "from qiskit import QuantumCircuit\n"
        "qc = QuantumCircuit(2, 2)\n"
        "qc.h(0)\n"
        "qc.cx(0, 1)\n"
        "qc.measure([0, 1], [0, 1])"
    ),
    "framework": "qiskit",
}

PENNYLANE_BELL = {
    "code": (
        "import pennylane as qml\n"
        "dev = qml.device('default.qubit', wires=2)\n"
        "@qml.qnode(dev)\n"
        "def bell_state():\n"
        "    qml.Hadamard(wires=0)\n"
        "    qml.CNOT(wires=[0, 1])\n"
        "    return qml.probs(wires=[0, 1])"
    ),
    "framework": "pennylane",
}

SIM_PAYLOAD = {
    "qasm_code": (
        "OPENQASM 3.0;\n"
        "qubit[2] q;\n"
        "bit[2] c;\n"
        "h q[0];\n"
        "cx q[0], q[1];\n"
        "c[0] = measure q[0];\n"
        "c[1] = measure q[1];\n"
    ),
    "backend": "statevector",
    "shots": 512,
}

CONVERSION_PAYLOADS = [CIRQ_BELL, QISKIT_BELL, PENNYLANE_BELL]


# ── Locust user classes ────────────────────────────────────────────────────────

if LOCUST_AVAILABLE:

    class HealthCheckUser(HttpUser):
        """Just hammers the health endpoint — baseline for max RPS."""
        wait_time = between(0.1, 0.5)

        @task
        def health(self):
            self.client.get("/api/health")


    class ConversionUser(HttpUser):
        """Simulates a user converting circuits from all 3 frameworks."""
        wait_time = between(1, 3)

        @task(3)
        def convert_cirq(self):
            self.client.post(
                "/api/converter/convert",
                json=CIRQ_BELL,
                name="/api/converter/convert [cirq]",
            )

        @task(3)
        def convert_qiskit(self):
            self.client.post(
                "/api/converter/convert",
                json=QISKIT_BELL,
                name="/api/converter/convert [qiskit]",
            )

        @task(2)
        def convert_pennylane(self):
            self.client.post(
                "/api/converter/convert",
                json=PENNYLANE_BELL,
                name="/api/converter/convert [pennylane]",
            )


    class SimulationUser(HttpUser):
        """Simulates a user running the quantum simulator."""
        wait_time = between(2, 5)

        @task
        def simulate(self):
            self.client.post(
                "/api/simulator/simulate",
                json=SIM_PAYLOAD,
                name="/api/simulator/simulate [statevector]",
            )


    class MixedWorkloadUser(HttpUser):
        """
        Realistic mixed workload: conversion 60%, simulation 30%, health 10%.
        Use this class to model a typical active user session.
        """
        wait_time = between(0.5, 2)

        @task(6)
        def convert(self):
            payload = random.choice(CONVERSION_PAYLOADS)
            self.client.post(
                "/api/converter/convert",
                json=payload,
                name=f"/api/converter/convert [{payload['framework']}]",
            )

        @task(3)
        def simulate(self):
            self.client.post(
                "/api/simulator/simulate",
                json=SIM_PAYLOAD,
                name="/api/simulator/simulate",
            )

        @task(1)
        def health(self):
            self.client.get("/api/health")


# ── Programmatic locust runner (for use inside notebooks) ─────────────────────

def run_locust_programmatic(
    host: str = "http://localhost:8000",
    users: int = 20,
    spawn_rate: int = 5,
    run_time: str = "60s",
    user_class: str = "MixedWorkloadUser",
    output_csv: str = "locust_results",
) -> str:
    """
    Returns the shell command string to run locust for a given scenario.
    The notebook can display this and optionally run it with subprocess.
    """
    return (
        f"locust -f locust_scenarios.py "
        f"--headless "
        f"--host {host} "
        f"-u {users} "
        f"-r {spawn_rate} "
        f"-t {run_time} "
        f"--only-summary "
        f"--csv {output_csv} "
        f"--class-picker {user_class}"
    )
